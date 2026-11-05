"""Wo Spiel, Nutzerdaten, Mod und die Daten des Ratgebers liegen – auf jedem Rechner selbst gefunden (Release im Workshop, 05.11.).

Spiel: Steam-Ordner aus der Registry, Bibliotheken aus steamapps/libraryfolders.vdf.
Nutzerdaten: Ordner „Dokumente“ laut Windows, dazu die üblichen Orte unter OneDrive. Gibt es mehrere Kopien, gilt die zuletzt benutzte
(eine alte Kopie in OneDrive darf nicht gewinnen).
Mod: der im aktiven Playset eingeschaltete Mod mit unserer ID (playsets.json nennt den Ordner, lokal oder Workshop), sonst der lokale
Ordner, sonst der Workshop-Ordner von Steam.
Daten des Ratgebers: beim Entwickeln Dev/data, in der Exe %LOCALAPPDATA%\\EU5 Ratgeber\\data (der Ordner der Exe kann schreibgeschützt sein).

Zum Prüfen überschreibbar: EU5_RATGEBER_SPIEL (…/game), EU5_RATGEBER_NUTZER, EU5_RATGEBER_STEAM, EU5_RATGEBER_DATEN.
"""
import functools
import glob
import json
import os
import re
import sys

APP_ID = "3450310"
SPIEL_NAME = "Europa Universalis V"
MOD_ID = "eu5_ratgeber_daten"
PROGRAMM = "EU5 Ratgeber"


def eingefroren():
    """Läuft die fertige Exe (PyInstaller) statt der Quelltexte?"""
    return bool(getattr(sys, "frozen", False))


def paket_ordner():
    """Mitgelieferte Dateien (web, analysis): beim Entwickeln Dev, in der Exe der entpackte Ordner."""
    if eingefroren():
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def daten_ordner():
    """Beschreibbare Daten des Ratgebers (Datenbank, Spielwissen, Protokolle)."""
    if os.environ.get("EU5_RATGEBER_DATEN"):
        return os.environ["EU5_RATGEBER_DATEN"]
    if eingefroren():
        return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), PROGRAMM, "data")
    return os.path.join(paket_ordner(), "data")


def atomar_schreiben(pfad, inhalt):
    """Erst in eine Hilfsdatei, dann umbenennen: ein abgebrochener Lauf hinterlässt keine halbe Datei, an der jeder weitere Start scheitert."""
    tmp = f"{pfad}.{os.getpid()}.tmp"
    with open(tmp, "wb") as f:
        f.write(inhalt)
    os.replace(tmp, pfad)


def _ohne_doppelte(pfade):
    gesehen, out = set(), []
    for p in pfade:
        if not p:
            continue
        p = os.path.normpath(p)
        k = os.path.normcase(p)
        if k not in gesehen:
            gesehen.add(k)
            out.append(p)
    return out


# ---------------------------------------------------------------- Nutzerdaten
def _dokumente_windows():
    """Ordner „Dokumente“ laut Windows (SHGetKnownFolderPath) – folgt einer Umleitung, z. B. nach OneDrive oder auf ein anderes Laufwerk."""
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
        kennung = GUID.from_buffer_copy(uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le)    # FOLDERID_Documents
        pfad = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(kennung), 0, None, ctypes.byref(pfad)):
            return None
        wert = pfad.value
        ctypes.windll.ole32.CoTaskMemFree(pfad)
        return wert
    except (AttributeError, OSError, ValueError):
        return None


def dokumente_kandidaten():
    heim = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    onedrive = [os.environ.get(k) for k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")] + [os.path.join(heim, "OneDrive")]
    return _ohne_doppelte([_dokumente_windows(), os.path.join(heim, "Documents"), os.path.join(heim, "Dokumente")]
                          + [os.path.join(o, n) for o in onedrive if o for n in ("Documents", "Dokumente")])


def _zuletzt_benutzt(ordner):
    zeiten = []
    for rel in ("pdx_settings.json", "playsets.json", os.path.join("logs", "debug.log")):
        try:
            zeiten.append(os.path.getmtime(os.path.join(ordner, rel)))
        except OSError:
            pass
    return max(zeiten, default=0)


def nutzer_waehlen(dokumente):
    """Ordner des Spiels unter den Dokumenten: von mehreren Kopien die zuletzt benutzte, ohne Kopie (Spiel nie gestartet) der erste."""
    ordner = [os.path.join(d, "Paradox Interactive", SPIEL_NAME) for d in dokumente]
    da = [o for o in ordner if os.path.isdir(o)]
    return max(da, key=_zuletzt_benutzt) if da else (ordner[0] if ordner else "")


@functools.lru_cache(maxsize=1)
def nutzer():
    return os.environ.get("EU5_RATGEBER_NUTZER") or nutzer_waehlen(dokumente_kandidaten())


# ---------------------------------------------------------------- Steam und Spiel
def _registry(wurzel, schluessel, wert):
    try:
        import winreg
        with winreg.OpenKey(getattr(winreg, wurzel), schluessel) as k:
            return winreg.QueryValueEx(k, wert)[0]
    except (ImportError, OSError):
        return None


def steam_ordner():
    return (os.environ.get("EU5_RATGEBER_STEAM") or _registry("HKEY_CURRENT_USER", r"Software\Valve\Steam", "SteamPath")
            or _registry("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
            or os.path.join(os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)", "Steam"))


def bibliotheken_lesen(steam):
    """Steam-Bibliotheken laut libraryfolders.vdf, dann der Steam-Ordner selbst (vdf zuerst: dort steht die richtige Schreibweise)."""
    try:
        s = open(os.path.join(steam, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="replace").read()
    except OSError:
        s = ""
    return _ohne_doppelte([m[1].replace("\\\\", "\\") for m in re.finditer(r'"path"\s+"((?:[^"\\]|\\.)*)"', s)] + [steam])


@functools.lru_cache(maxsize=1)
def bibliotheken():
    return bibliotheken_lesen(steam_ordner())


def spiel_waehlen(libs):
    """Ordner …/Europa Universalis V/game in der ersten Bibliothek, die das Spiel enthält."""
    ordner = [os.path.join(b, "steamapps", "common", SPIEL_NAME, "game") for b in libs]
    for o in ordner:
        if os.path.isdir(os.path.join(o, "in_game")):
            return o
    return ordner[0] if ordner else ""


@functools.lru_cache(maxsize=1)
def spiel():
    return os.environ.get("EU5_RATGEBER_SPIEL") or spiel_waehlen(bibliotheken())


# ---------------------------------------------------------------- Mod
def mod_id(ordner):
    try:
        return json.load(open(os.path.join(ordner, ".metadata", "metadata.json"), encoding="utf-8-sig")).get("id")
    except (OSError, ValueError, AttributeError):
        return None


def aktive_mods(nutzer_ordner):
    """Eingeschaltete Mods des aktiven Playsets (Ordner in Ladereihenfolge)."""
    try:
        d = json.load(open(os.path.join(nutzer_ordner, "playsets.json"), encoding="utf-8-sig"))
        for p in d.get("playsets") or []:
            if p.get("isActive"):
                return [os.path.normpath(m["path"]) for m in p.get("orderedListMods") or [] if m.get("isEnabled") and m.get("path")]
    except (OSError, ValueError, AttributeError, TypeError):       # auch eine Datei in fremdem Aufbau darf den Start nicht aufhalten
        pass
    return []


def mod_aktiv(ordner, nutzer_ordner=None):
    """Ist der Mod im aktiven Playset eingeschaltet? Ohne playsets.json lässt sich das nicht sagen: dann True."""
    nutzer_ordner = nutzer_ordner or nutzer()
    if not os.path.exists(os.path.join(nutzer_ordner, "playsets.json")):
        return True
    k = os.path.normcase(os.path.normpath(ordner))
    return k in [os.path.normcase(p) for p in aktive_mods(nutzer_ordner)]


def workshop_mods(libs):
    return [p for b in libs for p in sorted(glob.glob(os.path.join(glob.escape(b), "steamapps", "workshop", "content", APP_ID, "*")))]


def mod_waehlen(nutzer_ordner, libs):
    """Ordner unseres Mods; ohne Mod der lokale Pfad (dort gibt es dann nichts zu lesen oder zu schreiben)."""
    lokal = os.path.join(nutzer_ordner, "mod", MOD_ID)
    for p in aktive_mods(nutzer_ordner) + [lokal] + workshop_mods(libs):
        if mod_id(p) == MOD_ID:
            return os.path.normpath(p)
    return lokal


def mod_ordner():
    """Bei jedem Aufruf neu: ein Abo oder ein anderes Playset kommt ohne Neustart des Ratgebers an."""
    return mod_waehlen(nutzer(), bibliotheken())
