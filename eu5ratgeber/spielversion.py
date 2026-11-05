"""Spiel-Updates erkennen (Nutzerwunsch 24.10.: Patch 1.4 „Rio Salado“ am 28.10.).

Der Daten-Mod überdeckt `in_game/common/on_action/country_monthly.txt` mit einer Kopie der Spieldatei plus einer Zeile.
Nach einem Spiel-Update überdeckt er die neue Fassung mit der alten – das Spiel verliert neue Monatsabläufe, umbenannte
Funktionen erzeugen Fehler. Erkannt wird das, bevor das Spiel startet:
  - Steam-Build (steamapps/appmanifest_3450310.acf) – ändert sich sofort beim Update
  - Fingerabdruck der überdeckten Spieldateien beim Bau des Mods (rg_basis.json im Mod, ab 24.10.) – bei älteren Mods
    Vergleich der Mod-Kopie ohne die eigene Zeile mit der Spieldatei
  - Spielversion laut logs/code_revisions.log (erst nach dem ersten Spielstart) gegen die Version des Mods
Genutzt vom Ratgeber-Server (Warnung oben auf der Seite) und von tools/patch_pruefung.py (ganzer Bericht).
"""
import hashlib
import json
import os
import re
import time

from . import gamedata, pfade, version

GAME = gamedata.GAME_DIR                                            # …/Europa Universalis V/game
STEAMAPPS = os.path.dirname(os.path.dirname(os.path.dirname(GAME)))  # …/steamapps
APP_ID = "3450310"
USER = pfade.nutzer()
MOD = pfade.mod_ordner()
REVISIONS = os.path.join(USER, "logs", "code_revisions.log")
DEBUG_LOG = os.path.join(USER, "logs", "debug.log")
SAVES = os.path.join(USER, "save games")
BASIS = "rg_basis.json"                       # im Mod-Ordner, von tools/build_mod.py geschrieben
MARKE = "# EU5 Ratgeber - Daten"              # die eine eingefügte Zeile in country_monthly.txt
INHALT = ("in_game", "main_menu", "loading_screen")


def _zeit(t):
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(t)) if t else None


def steam():
    """{build, zeit (letztes Update, Unix), datum, zweig, update_offen} aus dem Steam-Manifest; {} ohne Manifest."""
    p = os.path.join(STEAMAPPS, f"appmanifest_{APP_ID}.acf")
    try:
        s = open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return {}
    def feld(k):
        m = re.search(rf'"{k}"\s+"([^"]*)"', s)
        return m.group(1) if m else None
    zeit = int(feld("lastupdated") or 0)
    flags = int(feld("StateFlags") or 0)
    # offen: Steam-Flag 2 (Update nötig) oder ein Ziel-Build, der noch nicht installiert ist – nach dem Update steht
    # TargetBuildID = buildid im Manifest (1.4-Beta 27.10.: 26105915 = 26105915, vorher fälschlich „Update steht aus“)
    ziel = feld("TargetBuildID")
    return {"build": feld("buildid"), "zeit": zeit, "datum": _zeit(zeit), "zweig": feld("BetaKey"),
            "update_offen": bool(flags & 2) or (ziel not in (None, "0", feld("buildid")))}


def _zweig():
    try:
        m = re.search(r"game_branch: \S*/release/(\S+)", open(REVISIONS, encoding="utf-8", errors="replace").read())
        return m.group(1) if m else None
    except OSError:
        return None


def spiel_version():
    """Spielversion wie „1.4.3“. Der Zweig in code_revisions.log nennt sie bei Veröffentlichungen (release/1.3.11); auf
    Beta-Zweigen heißt er „release/next“ (1.4-Beta, 27.10.) – dann aus debug.log („… does not match game version 1.4.3“,
    schreibt das Spiel beim Start, wenn ein Mod nicht passt) oder aus dem neuesten Spielstand seit dem letzten Spielstart
    (metadata version="1.4.3"); sonst der Zweigname, None ohne Log."""
    zweig = _zweig()
    if zweig and re.fullmatch(r"\d+\.\d+\.\d+", zweig):
        return zweig
    try:
        start = os.path.getmtime(REVISIONS)
    except OSError:
        return zweig
    try:
        with open(DEBUG_LOG, "rb") as f:
            m = re.search(rb"game version (\d+\.\d+\.\d+)", f.read(5 << 20))
        if m:
            return m.group(1).decode()
    except OSError:
        pass
    try:
        neu = [os.path.join(SAVES, n) for n in os.listdir(SAVES) if n.endswith(".eu5")]
    except OSError:
        neu = []
    for p in sorted((p for p in neu if os.path.getmtime(p) >= start - 60), key=os.path.getmtime, reverse=True):
        with open(p, "rb") as f:
            m = re.search(rb'\bversion="(\d+\.\d+\.\d+)"', f.read(4096))
        if m:
            return m.group(1).decode()
    return zweig


def log_version():
    """{version, zweig, zeit} des letzten Spielstarts laut logs/code_revisions.log (Version über spiel_version); {} ohne Log."""
    try:
        t = os.path.getmtime(REVISIONS)
    except OSError:
        return {}
    return {"version": spiel_version(), "zweig": _zweig(), "zeit": t, "datum": _zeit(t)}


def sha(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ueberdeckt(mod=MOD):
    """Relative Pfade der Spieldateien, die der Mod mit eigener Fassung überdeckt (gleicher Pfad im Spiel)."""
    out = []
    for top in INHALT:
        for root, _, files in os.walk(os.path.join(mod, top)):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), mod).replace("\\", "/")
                if os.path.exists(os.path.join(GAME, rel)):
                    out.append(rel)
    return sorted(out)


def mod_info(mod=MOD):
    """{version, spiel, basis} des installierten Mods; {} wenn nicht installiert."""
    try:
        meta = json.load(open(os.path.join(mod, ".metadata", "metadata.json"), encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    try:
        basis = json.load(open(os.path.join(mod, BASIS), encoding="utf-8-sig"))
    except (OSError, ValueError):
        basis = None
    return {"version": meta.get("version"), "spiel": meta.get("supported_game_version"), "basis": basis}


def _ohne_marke(text):
    return "".join(z for z in text.splitlines(keepends=True) if MARKE not in z)


def ueberdeckung_aktuell(rel, basis=None, mod=MOD):
    """True, wenn die Spieldatei seit dem Bau des Mods gleich geblieben ist. Mit rg_basis.json über den gespeicherten
    Fingerabdruck, sonst (Mods vor dem 24.10.) Mod-Kopie ohne die eigene Zeile gegen die Spieldatei."""
    spiel = os.path.join(GAME, rel)
    alt = ((basis or {}).get("vanilla") or {}).get(rel)
    if alt:
        return sha(spiel) == alt
    lies = lambda p: open(p, encoding="utf-8-sig", errors="replace", newline="").read()
    return _ohne_marke(lies(os.path.join(mod, rel))) == lies(spiel)


def _tun(entwickler, spieler):
    """Was zu tun ist: Spieler haben die Werkzeuge in tools/ nicht."""
    return spieler if pfade.eingefroren() else entwickler


def pruefen(mod=None):
    """Warnungen zum Stand Spiel ↔ Daten-Mod: {"warnungen": [{stufe, text, tun}], "steam", "spiel", "mod"}.
    Ohne installierten Mod warnt nur die Exe (beim Entwickeln kann der Ratgeber ohne Mod laufen)."""
    mod = mod or pfade.mod_ordner()
    st, lv, mi = steam(), log_version(), mod_info(mod)
    out = {"warnungen": [], "steam": st, "spiel": lv, "mod": {k: v for k, v in mi.items() if k != "basis"}}
    if not mi:
        if pfade.eingefroren():
            out["warnungen"].append({"stufe": "hoch", "text": "Der Mod EU5 Ratgeber wurde nicht gefunden.",
                                     "tun": "Mod im Workshop abonnieren und im Playset einschalten."})
        return out
    basis = mi.get("basis") or {}
    # rg_basis.json schreibt der Bau; die Nummer in metadata.json kann das Upload-Fenster des Spiels ändern
    gebaut = basis.get("mod_version") or mi.get("version")
    if gebaut != version.MOD_VERSION:
        out["warnungen"].append({
            "stufe": "hoch", "text": f"Mod {gebaut} und Programm passen nicht zusammen, das Programm erwartet Mod {version.MOD_VERSION}.",
            "tun": _tun("python tools/build_mod.py --install", "Neueste Fassung von Mod und Programm holen.")})
    if pfade.eingefroren() and not pfade.mod_aktiv(mod):
        out["warnungen"].append({"stufe": "hoch", "text": "Der Mod EU5 Ratgeber ist im aktiven Playset nicht eingeschaltet.",
                                 "tun": "Im Spiel unter Mods & DLC einschalten."})
    tun = _tun("Vor dem nächsten Spielstart: python tools/patch_pruefung.py – bis der Mod neu gebaut ist, Mod im Launcher abschalten.",
               "Mod im Playset abschalten, bis im Workshop ein Update erscheint.")
    tun_klein = _tun("python tools/patch_pruefung.py", "Der Mod kann weiterlaufen. Ist etwas nötig, erscheint ein Update im Workshop.")
    geaendert = []
    for rel in ueberdeckt(mod):
        try:
            if not ueberdeckung_aktuell(rel, basis, mod):
                geaendert.append(rel)
        except OSError:
            continue
    alt_build, neu_build = basis.get("steam_build"), st.get("build")
    build_neu = bool(alt_build and neu_build and alt_build != neu_build)
    seit = f" (Steam-Build {alt_build} → {neu_build}, {st.get('datum')})" if build_neu else ""
    if geaendert:
        out["warnungen"].append({
            "stufe": "hoch",
            "text": f"Spiel-Update{seit}: {', '.join(geaendert)} hat sich geändert – der Daten-Mod {mi.get('version')} "
                    f"überdeckt die neue Fassung noch mit der alten.",
            "tun": tun})
    elif build_neu:
        out["warnungen"].append({
            "stufe": "mittel",
            "text": f"Spiel-Update{seit} – die vom Mod überdeckte Datei ist gleich geblieben, die Namen im Mod sind aber "
                    f"noch nicht gegen die neue Version geprüft.",
            "tun": tun_klein})
    if st.get("update_offen"):
        out["warnungen"].append({"stufe": "mittel", "text": "Steam meldet ein ausstehendes Spiel-Update.",
                                 "tun": _tun("Nach dem Update: python tools/patch_pruefung.py", "Update in Steam abwarten.")})
    if not out["warnungen"] and lv.get("version") and mi.get("spiel") and lv["version"] != mi["spiel"]:
        out["warnungen"].append({
            "stufe": "mittel",
            "text": f"Spielversion {lv['version']} (letzter Start {lv.get('datum')}), Daten-Mod gebaut für {mi['spiel']}.",
            "tun": tun_klein})
    return out
