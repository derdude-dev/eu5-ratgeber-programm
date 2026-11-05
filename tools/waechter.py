"""Wächter des EU5 Ratgebers – startet den Ratgeber mit dem Spiel, ohne Konsolenfenster (Nutzerwunsch 03.11.: „der mod soll
anstatt über die .bat gestartet werden wenn das eigentliche spiel startet und der prozess soll im hintergrund laufen, die konsole
soll nicht mehr zu sehen sein“; Weg gewählt: Wächter im Windows-Autostart).

Läuft unsichtbar (pythonw) ab der Anmeldung bei Windows, prüft alle TAKT s, ob eu5.exe läuft, und startet dann einmal je
Spielsitzung tools/ratgeber.py start --hintergrund (ebenfalls pythonw). Der Ratgeber beendet sich selbst mit dem Spiel. Kaum
Last: eine Prozessliste je TAKT (Toolhelp32 über ctypes, ohne Hilfsprogramm und ohne Fenster). Nur ein Wächter zugleich (Sperre
über einen lokalen Port). Protokoll: data/waechter.log.

    pythonw tools/waechter.py                 # Dauerbetrieb (so startet ihn der Autostart)
    python tools/waechter.py --einmal         # einmal prüfen und ggf. starten
    python tools/waechter.py --autostart an   # Verknüpfung im Autostart-Ordner anlegen (aus: entfernen)

In der Exe: „EU5 Ratgeber.exe waechter“ (tools/programm.py), sie startet sich dann selbst mit „start --hintergrund“.
"""
import argparse
import ctypes
import errno
import os
import socket
import subprocess
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from eu5ratgeber import pfade  # noqa: E402

ROOT = pfade.paket_ordner()
LOGDATEI = os.path.join(pfade.daten_ordner(), "waechter.log")
SPIEL = "eu5.exe"
TAKT = 5                      # s zwischen zwei Prüfungen
SPERRE = 8764                 # Port nur als Sperre (ein Wächter); der Ratgeber selbst liegt auf 8765, seine Sperre auf 9765
PORT = 8765
RATGEBER_LOG = os.path.join(pfade.daten_ordner(), "ratgeber.log")
ANLAUF = 180                  # s: so lange darf der Ratgeber nach dem Start brauchen, bis seine Seite antwortet
VERSUCHE = 3                  # Starts je Spielsitzung höchstens (Absturz beim Laden -> nicht endlos neu)
VERKNUEPFUNG = "EU5 Ratgeber Waechter.lnk"
LOG_GRENZE = 2_000_000


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOGDATEI), exist_ok=True)
        if os.path.exists(LOGDATEI) and os.path.getsize(LOGDATEI) > 1_000_000:
            os.replace(LOGDATEI, LOGDATEI + ".1")
        with open(LOGDATEI, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass
    if sys.stdout:
        print(time.strftime("%H:%M:%S"), msg, flush=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def prozesse(name):
    """Prozess-IDs aller laufenden Prozesse mit diesem Dateinamen (Groß-/Kleinschreibung egal)."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)              # TH32CS_SNAPPROCESS
    if not snap or snap == ctypes.c_void_p(-1).value:
        return []
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        out, ok = [], k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            if e.szExeFile.lower() == name.lower():
                out.append(e.th32ProcessID)
            ok = k32.Process32NextW(snap, ctypes.byref(e))
        return out
    finally:
        k32.CloseHandle(snap)


def spiel_laeuft():
    return bool(prozesse(SPIEL))


def port_offen(port):
    """Nimmt jemand auf 127.0.0.1:port Verbindungen an? Reiner Verbindungsaufbau – ohne Anfrage, die im Ratgeber auf die Sperre der
    Datenbank warten müsste (Prüfung 03.11.: /api/partien lief unter Last in die Zeitgrenze -> zweiter Start)."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def ratgeber_laeuft():
    """Läuft ein Ratgeber oder lädt er noch? Seine Sperre (PORT + 1000) ist belegt. Die Seite allein sagt es nicht: Auf PORT kann ein
    anderes Programm lauschen (AnkiConnect nimmt denselben Port), dann käme der Ratgeber nie."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", PORT + 1000))
        return False
    except OSError as e:
        return port_belegt(e)
    finally:
        s.close()


def port_belegt(e):
    """Fehler beim bind: wirklich belegt? Sonst ist der Port nur gesperrt (von Windows für Hyper-V reserviert)."""
    return getattr(e, "winerror", None) == 10048 or e.errno == errno.EADDRINUSE


def kuerzen(pfad, grenze):
    """Zu großes Protokoll als .1 beiseitelegen. Geht nur, solange kein Prozess die Datei offen hält: unter Windows scheitert das Umbenennen
    dann. Darum vor dem Start des Ratgebers (Prüfung 05.11.), und ein Fehlschlag ist egal."""
    try:
        if os.path.getsize(pfad) > grenze:
            os.replace(pfad, pfad + ".1")
    except OSError:
        pass


def pythonw():
    """pythonw.exe neben dem laufenden Python (kein Konsolenfenster)."""
    p = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return p if os.path.exists(p) else sys.executable


def ratgeber_befehl():
    """Befehl und Arbeitsordner für den Start im Hintergrund."""
    if pfade.eingefroren():
        return [sys.executable, "start", "--hintergrund"], os.path.dirname(sys.executable)
    return [pythonw(), os.path.join(ROOT, "tools", "ratgeber.py"), "start", "--hintergrund"], ROOT


def ratgeber_starten():
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) \
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # Ausgaben in die Logdatei des Ratgebers – auch Fehler vor seiner eigenen Umleitung (Import, Argumente; Prüfung 03.11.)
    os.makedirs(os.path.dirname(RATGEBER_LOG), exist_ok=True)
    kuerzen(RATGEBER_LOG, LOG_GRENZE)
    befehl, ordner = ratgeber_befehl()
    with open(RATGEBER_LOG, "ab") as aus:
        subprocess.Popen(befehl, cwd=ordner, stdin=subprocess.DEVNULL, stdout=aus, stderr=aus, creationflags=flags, close_fds=True)


def pruefen(sitzung):
    """Ein Durchlauf. sitzung = {pid: [starts, letzter Start]} der laufenden Spielsitzungen (wird fortgeschrieben)."""
    pids = prozesse(SPIEL)
    for alt in [p for p in sitzung if p not in pids]:
        log(f"Spiel beendet (Prozess {alt}) – der Ratgeber beendet sich selbst")
        del sitzung[alt]
    if not pids:
        return
    pid = pids[0]
    starts, zuletzt = sitzung.setdefault(pid, [0, 0.0])
    if ratgeber_laeuft() or (starts and time.monotonic() - zuletzt < ANLAUF):
        return
    if starts >= VERSUCHE:
        if starts == VERSUCHE:
            log(f"Ratgeber nach {VERSUCHE} Starts nicht erreichbar – Fehler in data/ratgeber.log; kein weiterer Versuch")
            sitzung[pid][0] += 1
        return
    log(f"Spiel läuft (Prozess {pid}) – Ratgeber wird im Hintergrund gestartet" + (f" (Versuch {starts + 1})" if starts else ""))
    ratgeber_starten()
    sitzung[pid] = [starts + 1, time.monotonic()]


def autostart(an):
    """Verknüpfung im Autostart-Ordner des Nutzers anlegen bzw. entfernen (WScript.Shell, ohne Adminrechte)."""
    if pfade.eingefroren():
        ziel, argumente, ordner = sys.executable, "waechter", os.path.dirname(sys.executable)
    else:
        ziel, argumente, ordner = pythonw(), '"' + os.path.join(ROOT, "tools", "waechter.py") + '"', ROOT

    def q(s):                                                # einfaches Anführungszeichen im Pfad (O'Brien) für PowerShell verdoppeln
        return s.replace("'", "''")
    # Stop: sonst endet das Skript mit Code 0, auch wenn die Verknüpfung nicht gespeichert wurde
    ps = ("$ErrorActionPreference = 'Stop'; $o = [Environment]::GetFolderPath('Startup'); $p = Join-Path $o '" + VERKNUEPFUNG + "'; "
          + ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p); "
             f"$s.TargetPath = '{q(ziel)}'; $s.Arguments = '{q(argumente)}'; $s.WorkingDirectory = '{q(ordner)}'; "
             "$s.Description = 'EU5 Ratgeber: startet den Ratgeber im Hintergrund, sobald Europa Universalis V läuft'; "
             "$s.WindowStyle = 7; $s.Save(); $p" if an else "if (Test-Path $p) { Remove-Item $p }; $p"))
    # als Bytes: PowerShell schreibt in der OEM-Codepage, „ü“ im Benutzernamen ist in cp1252 nicht lesbar (stdout wäre None)
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        raise SystemExit(f"Autostart {'anlegen' if an else 'entfernen'} gescheitert: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout.decode("utf-8", "replace").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--einmal", action="store_true", help="einmal prüfen und ggf. starten")
    ap.add_argument("--autostart", choices=["an", "aus"], help="Verknüpfung im Autostart-Ordner anlegen/entfernen")
    a = ap.parse_args()
    if a.autostart:
        print(f"Autostart {a.autostart}: {autostart(a.autostart == 'an')}")
        return
    sitzung = {}
    if a.einmal:
        pruefen(sitzung)
        return
    sperre = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sperre.bind(("127.0.0.1", SPERRE))                  # zweiter Wächter -> Port belegt -> beenden
    except OSError:
        log("Wächter läuft schon – kein zweiter")
        return
    log(f"Wächter gestartet (alle {TAKT} s: {SPIEL}?)")
    while True:
        try:
            pruefen(sitzung)
        except Exception as e:                               # noqa: BLE001 – der Wächter darf nicht sterben
            log(f"FEHLER {type(e).__name__}: {e}")
        time.sleep(TAKT)


if __name__ == "__main__":
    main()
