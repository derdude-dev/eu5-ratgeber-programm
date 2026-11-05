"""Einstieg der Exe „EU5 Ratgeber“ (tools/build_exe.py).

    EU5 Ratgeber.exe                    Doppelklick: Ratgeber starten, Seite im Browser öffnen; beim ersten Mal Frage nach dem Autostart
    EU5 Ratgeber.exe start …            wie tools/ratgeber.py (…  --hintergrund: so startet ihn der Wächter)
    EU5 Ratgeber.exe waechter [--autostart an|aus]   wie tools/waechter.py

Die Exe hat kein Konsolenfenster: Meldungen stehen in %LOCALAPPDATA%\\EU5 Ratgeber\\data\\ratgeber.log, Wichtiges kommt als Windows-Fenster.
Im Hintergrund nie ein Fenster: Es öffnete sich hinter dem Spiel im Vollbild, und solange es offen ist, gilt der Ratgeber als laufend.
"""
import ctypes
import json
import os
import subprocess
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eu5ratgeber import pfade  # noqa: E402
import ratgeber  # noqa: E402
import waechter  # noqa: E402

JA = 6


def fenster(text, frage=False):
    """Windows-Meldung; mit frage Ja/Nein, Ergebnis True bei Ja."""
    return ctypes.windll.user32.MessageBoxW(None, text, pfade.PROGRAMM, 0x24 if frage else 0x40) == JA


def im_hintergrund():
    return "--hintergrund" in sys.argv or sys.argv[1:2] == ["waechter"]


def melden(text):
    """Fehler melden: im Hintergrund nur ins Protokoll."""
    os.makedirs(pfade.daten_ordner(), exist_ok=True)
    with open(os.path.join(pfade.daten_ordner(), "ratgeber.log"), "a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")
    if not im_hintergrund():
        fenster(text)


def einstellungen_datei():
    return os.path.join(pfade.daten_ordner(), "einstellungen.json")


def einstellungen_lesen():
    try:
        d = json.load(open(einstellungen_datei(), encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def einstellungen_schreiben(autostart):
    p = einstellungen_datei()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    pfade.atomar_schreiben(p, json.dumps({"autostart": autostart, "exe": sys.executable}).encode("utf-8"))


def autostart_einrichten():
    """Verknüpfung auf diese Exe. Ein Fehlschlag darf den Ratgeber nicht aufhalten."""
    try:
        waechter.autostart(True)
        return True
    except (Exception, SystemExit) as e:                    # noqa: BLE001 – autostart meldet Fehler mit SystemExit
        fenster(f"Der Autostart ließ sich nicht einrichten. Der Ratgeber läuft trotzdem, starte ihn dann von Hand.\n\n{e}")
        return False


def erster_start():
    """Einmal fragen, ob der Wächter in den Autostart soll; nichts geschieht ungefragt. Liegt die Exe später woanders (neue Version in einem
    anderen Ordner), zeigt die Verknüpfung sonst weiter auf die alte."""
    e = einstellungen_lesen()
    if e is not None:
        if e.get("autostart") and e.get("exe") != sys.executable:
            einstellungen_schreiben(autostart_einrichten())
        return
    an = fenster("Soll der Ratgeber künftig von selbst starten, sobald du Europa Universalis V startest?\n\n"
                 "Dafür läuft ab der Windows-Anmeldung ein kleiner Wächter im Hintergrund. Abschalten: siehe LIESMICH.txt.", frage=True)
    an = an and autostart_einrichten()
    einstellungen_schreiben(an)
    if an:
        subprocess.Popen([sys.executable, "waechter"], cwd=os.path.dirname(sys.executable), close_fds=True)
    fenster("Beim ersten Start baut der Ratgeber sein Spielwissen aus den Spieldateien auf. Das dauert etwa eine halbe Minute, danach "
            "öffnet sich die Seite im Browser.")


def main():
    args = sys.argv[1:]
    if args[:1] == ["waechter"]:
        sys.argv = sys.argv[:1] + args[1:]
        waechter.main()
        return
    if not os.path.isdir(os.path.join(pfade.spiel(), "in_game")):
        melden("Europa Universalis V wurde nicht gefunden. Der Ratgeber sucht in allen Steam-Bibliotheken dieses Benutzers.")
        return
    if not args:
        erster_start()
        sys.argv += ["start", "--browser"]
    ratgeber.main()


if __name__ == "__main__":
    try:
        main()
    except ratgeber.PortBelegt as e:
        melden(str(e))
    except Exception:                                       # noqa: BLE001 – ohne Konsole sonst spurlos
        melden(traceback.format_exc() + "\nDer Ratgeber wurde mit einem Fehler beendet. Einzelheiten: "
               + os.path.join(pfade.daten_ordner(), "ratgeber.log"))
