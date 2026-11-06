"""EU5 Ratgeber starten: Spielstände einlesen, Wächter und Webseite.

    python tools/ratgeber.py einlesen      # alle Spielstände einmal einlesen
    python tools/ratgeber.py start         # Wächter + Webseite auf http://127.0.0.1:8765
    pythonw tools/ratgeber.py start --hintergrund   # ohne Konsole (startet tools/waechter.py mit dem Spiel, 03.11.)

Im Hintergrund: Meldungen in data/ratgeber.log, kein Browser beim Start (Knopf „Im Browser öffnen“ in der Seitenleiste des
Spiels), Ende mit dem Spiel statt mit dem Browser-Tab.

Der Wächter prüft alle 20 s den Speicherordner. Ein Spielstand wird erst eingelesen, wenn seine
Größe zwei Prüfungen lang gleich bleibt (das Spiel schreibt 300-450 MB).
Außerdem liest er die Monatszeilen des Daten-Mods aus logs/debug.log mit (Echtzeit ohne Speichern).
"""
import argparse
import glob
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from eu5ratgeber import bevoelkerung, gamedata, history, livelog, pfade, spielversion, wissen, wissen_voll  # noqa: E402
from eu5ratgeber import wiki  # noqa: E402  (Mechanik-Wiki, 30.10.)
from eu5ratgeber import techbaum  # noqa: E402  (Ansicht Fortschritte, 30.10.)
from eu5ratgeber import ingame  # noqa: E402  (Seitenleiste im Spiel, Mod 0.26, 02.11.)
import waechter  # noqa: E402  (läuft das Spiel? – Hintergrundbetrieb, 03.11.)
from eu5ratgeber.sprache import ue  # noqa: E402

WISSEN_VOLL = None   # Ordner des vollständigen Spielwissens, gesetzt in main()
_MODTYPES = None


def modtypes():
    """Name und Anzeigeformat je Modifikator (data/spielwissen/<ver>/_modifikator_typen.json), einmal geladen."""
    global _MODTYPES
    if _MODTYPES is None:
        _MODTYPES = bevoelkerung.load_modtypes(os.path.join(WISSEN_VOLL, "_modifikator_typen.json"))
    return _MODTYPES

DATEN = pfade.daten_ordner()
DB_PATH = os.path.join(DATEN, "verlauf.sqlite")
SAVES = spielversion.SAVES
WEB = os.path.join(pfade.paket_ordner(), "web", "index.html")
PORT = 8765
POLL = 20
LOG_TAKT = 2                                     # s: debug.log lesen (Seitenleiste im Spiel, 03.11.)

lock = threading.Lock()

# Server endet mit dem Browser-Tab (Nutzerwunsch 02.10.): jede geöffnete Seite meldet sich an (/api/hallo, auch bei jedem
# Neuladen der Daten), beim Schließen ab (/api/tschuess per sendBeacon). Ist nach einer Abmeldung TAB_GNADE Sekunden lang
# keine Seite mehr angemeldet, beendet sich der Server – ein Neuladen der Seite meldet sich in der Zeit wieder an.
# Bewusst ohne Zeitüberschreitung: schlafende Hintergrund-Tabs (Edge, Chrome) senden nichts, sollen den Server aber nicht beenden.
TAB_GNADE = 15
TABS = set()
tab_lock = threading.Lock()
SERVER = None
# Hintergrundbetrieb (Wächter, 03.11.): ohne Konsole, Meldungen in LOGDATEI; Ende SPIEL_GNADE s nach dem Spiel, solange keine
# Seite im Browser offen ist – ein Browser-Tab beendet ihn nicht, solange das Spiel läuft
HINTERGRUND = False
LOGDATEI = os.path.join(DATEN, "ratgeber.log")
SPIEL_GNADE = 30
TAB_HOECHSTENS = 600                 # s ohne Spiel: dann Ende auch mit offenem Tab (ein Tab ohne Abmeldung hielte ihn sonst ewig)
ENDE = threading.Event()             # Hintergrund: der Wächter-Faden liest debug.log ein letztes Mal und beendet dann
ENDE_GRUND = {"text": ""}
SPERRE_ABSTAND = 1000                # Sperre des Ratgebers auf PORT + 1000 (8765 -> 9765), belegt vor dem Einlesen


class PortBelegt(Exception):
    """Auf dem Port der Seite lauscht ein anderes Programm."""


def beenden(grund):
    log(ue(t"{grund} – Ratgeber wird beendet"))
    with lock:                       # keine Datenbank-Schreibung mittendrin abbrechen
        SERVER.shutdown()


def tab_pruefen():
    with tab_lock:
        if TABS:
            return
    if (HINTERGRUND or pfade.eingefroren()) and waechter.spiel_laeuft():
        return                       # im Hintergrund und in der Exe endet der Ratgeber mit dem Spiel (spiel_pruefen)
    beenden(ue("Browser-Tab geschlossen"))


def spiel_pruefen():
    """Hintergrund: Ende, sobald das Spiel SPIEL_GNADE s weg ist und keine Seite offen ist (sonst beim Schließen des Tabs, spätestens
    nach TAB_HOECHSTENS s). Beenden über den Wächter-Faden (ENDE): er liest die debug.log vorher ein letztes Mal (Prüfung 03.11.);
    antwortet er nicht (hängt in einem Spielstand), nach 3 Minuten direkt.
    Exe von Hand gestartet: das gilt erst, wenn das Spiel einmal lief, und eine offene Seite hält ihn ohne Zeitgrenze – man liest sie auch
    ohne Spiel; das Ende kommt dann mit dem Tab (tab_pruefen)."""
    weg, gesehen = None, HINTERGRUND
    while True:
        time.sleep(10)
        if waechter.spiel_laeuft():
            weg, gesehen = None, True
            continue
        if not gesehen:
            continue
        weg = weg or time.monotonic()
        with tab_lock:
            offen = bool(TABS)
        dauer = time.monotonic() - weg
        if (not offen and dauer >= SPIEL_GNADE) or (HINTERGRUND and dauer >= TAB_HOECHSTENS):
            ENDE_GRUND["text"] = ue("Spiel beendet") + (ue(" (Browser-Tab noch offen)") if offen else "")
            ENDE.set()
            time.sleep(180)
            beenden(ENDE_GRUND["text"] + ue(" – Wächter-Faden antwortet nicht"))
            return


def log(msg):
    if HINTERGRUND or not sys.stdout:            # Exe und pythonw: kein stdout
        try:
            os.makedirs(os.path.dirname(LOGDATEI), exist_ok=True)
            with open(LOGDATEI, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
        except OSError:
            pass
    else:                            # im Hintergrund leitet der Wächter stdout in dieselbe Logdatei (doppelt)
        print(time.strftime("%H:%M:%S"), msg, flush=True)


BROWSER = {"aktiv": False, "start": None, "zuletzt": 0.0}   # aktiv: nur im Wächter von „start“, nicht bei „einlesen“
BROWSER_SPERRE = 15                  # s: Doppelklick öffnet nur einen Tab


def _sekunde(t):
    return t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec


def browser_klick(recs, jetzt=None):
    """Knopf „Im Browser öffnen“ im Spiel (Mod 0.28: scripted gui rg_browser -> RG_BROWSER im debug.log): Browser öffnen. Klicks
    ab dem Start des Ratgebers gelten immer (auch wenn der Wächter-Faden gerade einen Spielstand liest – Prüfung 03.11.), ältere
    derselben debug.log nur bis 60 s vor dem Start (Klick, während der Ratgeber noch lud) – ein Neustart wiederholt keine alten."""
    if not BROWSER["aktiv"]:
        return False
    j = _sekunde(jetzt or time.localtime())
    start = BROWSER["start"] if BROWSER["start"] is not None else j
    for r in recs:
        try:
            h, m, s = (int(x) for x in str(r.get("zeit")).split(":"))
        except ValueError:
            continue
        z = h * 3600 + m * 60 + s
        nach_start = (z - start) % 86400 <= (j - start) % 86400       # zwischen Start und jetzt (über Mitternacht)
        if nach_start or (start - z) % 86400 <= 60:
            if time.monotonic() - BROWSER["zuletzt"] < BROWSER_SPERRE:
                return False
            BROWSER["zuletzt"] = time.monotonic()
            log(ue("Knopf „Im Browser öffnen“ im Spiel – Browser wird geöffnet"))
            webbrowser.open(f"http://127.0.0.1:{PORT}")
            return True
    return False


def scan(db, names, stable):
    """Liest fertige, neue Spielstände ein. stable: {pfad: (größe, mtime)} der letzten Prüfung."""
    for path in sorted(glob.glob(os.path.join(glob.escape(SAVES), "*.eu5")), key=os.path.getmtime):
        try:
            st = os.stat(path)
        except FileNotFoundError:
            continue
        sig = (st.st_size, st.st_mtime)
        if stable is not None and stable.get(path) != sig:
            stable[path] = sig            # erst beim nächsten Durchlauf, wenn unverändert
            continue
        try:
            history.ingest(db, path, names, log, lock)    # Sperre nur um die Datenbankzugriffe
        except Exception as e:           # ein kaputter Stand soll den Wächter nicht stoppen
            log(ue(t"{os.path.basename(path)}: FEHLER {e}"))


def spielstaende(db):
    with lock:
        return db.execute("SELECT COUNT(*) FROM momentaufnahmen").fetchone()[0]


def scan_und_schreiben(db, names, stable, wis):
    """Neue Spielstände einlesen; kam einer dazu, die Seitenleiste sofort schreiben. Sonst gäbe erst der nächste Spielmonat den Anlass, im
    pausierten Spiel also keiner (Test 06.11.). -> True, wenn geschrieben."""
    vorher = spielstaende(db)
    scan(db, names, stable)
    if spielstaende(db) == vorher:
        return False
    ingame_schreiben(db, names, wis)
    return True


def read_log(db, reader):
    """Neue Monatszeilen des Daten-Mods aus debug.log übernehmen – in Stücken von höchstens livelog.MAX_LESEN, bis die Datei
    gelesen ist; nach jedem Stück den Lesestand speichern (ein Neustart liest dieselbe debug.log ab dort weiter, 31.10.).
    -> True, wenn neue Zeilen gespeichert wurden (Seitenleiste im Spiel neu schreiben)."""
    neu = False
    while True:
        alt = reader.pos
        neu = _read_log_stueck(db, reader) or neu
        if reader.pos != alt:
            with lock:
                history.logstand_speichern(db, reader.path, reader.zustand())
        if not reader.mehr or reader.pos == alt:
            break
    return neu


def _read_log_stueck(db, reader):
    recs = reader.read_new()
    klicks = [r for r in recs if r["art"] == "browser"]
    if klicks:
        browser_klick(klicks)
        recs = [r for r in recs if r["art"] != "browser"]
    if recs:
        for teil in history.monats_stuecke(recs):    # je Monat unter der Sperre: die Seite wartet nicht auf die ganze Datei
            with lock:
                history.store_log(db, teil)
            time.sleep(0.01)                         # Sperre wirklich freigeben – sonst holt dieser Thread sie sofort wieder
        for z in (r for r in recs if r["art"] == "zeitsprung"):
            log(ue(t"debug.log: Spielstand neu geladen ({z['tag']} zurück auf {(z['ab'] - 1) // 12}.{(z['ab'] - 1) % 12 + 1}) – "
                t"spätere Monate verworfen"))
        last = next((r for r in reversed(recs) if "jahr" in r), recs[-1])
        n = {a: sum(r["art"] == a for r in recs) for a in ("land", "ort", "gebaeude", "markt", "diplomatie",
                                                            "finanzen", "stand_einkommen", "text")}
        log(ue(t"debug.log: {n['land']} Monat(e), {n['ort']} Orte, {n['gebaeude']} Gebäude, {n['markt']} Märkte, "
            t"{n['diplomatie']} Diplomatie, {n['finanzen']} Finanzen, {n['stand_einkommen']} Stände-Einkommen, "
            t"{n['text']} Texte - zuletzt {last['tag']} {last['jahr']}.{last['monat']}"))
    return bool(recs)


FREMD_GEPRUEFT = set()


def fremde_nachladen(db, names):
    """Mod ab 0.17 meldet monatlich die Märkte in Handelsreichweite, Spielstände kommen nur halbjährlich. Passt die
    neueste Momentaufnahme nicht zur Liste (erste Meldung, Reichweite geändert), denselben Spielstand noch einmal
    einlesen, solange er im Speicherordner liegt (Autosaves rotieren per Umbenennen - Suche über Partie und Datum)."""
    with lock:
        alt = history.fremde_veraltet(db, FREMD_GEPRUEFT)
    for pid, datum in alt:
        for path in sorted(glob.glob(os.path.join(glob.escape(SAVES), "*.eu5")), key=os.path.getmtime, reverse=True):
            try:
                if history.is_text_save(path) and history.peek_meta(path) == (pid, datum):
                    log(ue(t"fremde Märkte: {os.path.basename(path)} ({datum}) wird neu eingelesen"))
                    history.ingest(db, path, names, log, lock, force=True)
                    break
            except Exception as e:
                log(ue(t"{os.path.basename(path)}: FEHLER {e}"))


# Spiel-Update erkennen (24.10., Patch 1.4 am 28.10.): Steam-Build und die vom Mod überdeckte Spieldatei gegen den Stand
# beim Bau des Mods. Steam aktualisiert, während das Spiel nicht läuft – also auch bei offenem Ratgeber; Prüfung je Durchlauf
# des Wächters (liest zwei kleine Dateien). Neue Warnungen ins Konsolenfenster, alle oben auf die Seite (/api/pruefung).
PRUEFUNG = {"warnungen": []}


def pruefung_aktualisieren():
    global PRUEFUNG
    try:
        neu = spielversion.pruefen()
    except Exception as e:                       # die Prüfung darf den Ratgeber nicht stoppen
        neu = {"warnungen": [{"stufe": "mittel", "text": ue(t"Prüfung Spiel/Mod gescheitert: {type(e).__name__}: {e}"), "tun": ""}]}
    if INGAME["fehlversuche"] >= INGAME_GEDULD:
        neu["warnungen"].append({"stufe": "hoch", "text": ue(t"Die Texte für die Seitenleiste lassen sich nicht schreiben: {INGAME['fehler']}"),
                                 "tun": ue("Schreibrechte für den Ordner des Mods prüfen.")})
    alt = {w["text"] for w in PRUEFUNG.get("warnungen", [])}
    for w in neu["warnungen"]:
        if w["text"] not in alt:
            log(ue(t"ACHTUNG: {w['text']}") + (f" – {w['tun']}" if w.get("tun") else ""))
    PRUEFUNG = neu
    return alt != {w["text"] for w in neu["warnungen"]}       # geändert -> Seitenleiste im Spiel neu schreiben


def browser_wenn_bereit(sekunden=180):
    """Seite öffnen, sobald sie antwortet: Ein anderer Start kann noch laden (erster Start rund 30 s), sonst sähe man eine tote Seite."""
    for _ in range(sekunden):
        if waechter.port_offen(PORT):
            webbrowser.open(f"http://127.0.0.1:{PORT}")
            return
        time.sleep(1)
    log(ue(t"Seite antwortet nach {sekunden} s nicht: http://127.0.0.1:{PORT}"))


def ingame_schreiben(db, names, wis):
    """Seitenleiste im Spiel (Mod 0.26): Texte aller Schwerpunkte für die Partie der laufenden Sitzung neu schreiben
    (eu5ratgeber/ingame.py). Nur, wenn der Mod mit Seitenleiste installiert ist; ein Fehler hält den Wächter nicht an."""
    if not (ingame.mod_ordner() / ingame.GUI_DATEI).exists():
        return
    try:
        with lock:
            pid = ingame.aktuelle_partie(db)
            d = ingame.daten(db, pid, names, wis, WISSEN_VOLL) if pid else None
        # Warnungen der Prüfung Spiel/Mod (Spiel-Update …) auch in der Übersicht im Spiel – das Konsolenfenster fehlt im
        # Hintergrundbetrieb (03.11.)
        warnungen = PRUEFUNG.get("warnungen") or []
        # Ohne Spielstand dieser Partie nichts stehen lassen: Sonst zeigt eine neue Partie die Empfehlungen der alten (Test 06.11.: Walachei in Bulgarien)
        if not d:
            ingame.schreiben(ingame.nur_hinweis(warnungen or [{"text": ue(
                "Der Ratgeber läuft und wartet auf den ersten Spielstand dieser Partie. Einmal speichern oder auf das Autosave warten, dann „Aktualisieren“ drücken.")}]))
        if d and ingame.schreiben(ingame.texte(d, pruef=warnungen)) and not INGAME["geschrieben"]:
            log(ue(t"Seitenleiste im Spiel: Texte geschrieben ({(d.get('meta') or {}).get('land')}, {ingame.LIVE_DATEI.name})"))
            INGAME["geschrieben"] = True
        INGAME["fehlversuche"] = 0
    except OSError as e:                         # keine Schreibrechte im Workshop-Ordner, Datei gesperrt: auf der Seite melden
        INGAME["fehlversuche"] += 1
        INGAME["fehler"] = f"{type(e).__name__}: {e}"
        if INGAME["fehlversuche"] == INGAME_GEDULD:
            log(ue(t"Fenster im Spiel: FEHLER {INGAME['fehler']}"))
    except Exception as e:                       # noqa: BLE001
        log(ue(t"Fenster im Spiel: FEHLER {type(e).__name__}: {e}"))


INGAME = {"geschrieben": False, "fehlversuche": 0, "fehler": ""}
INGAME_GEDULD = 3                    # Fehlversuche in Folge: ein einzelner kann daher kommen, dass das Spiel die Datei gerade liest


def watcher(db, names, reader, wis=None):
    # beim Start alles Vorhandene sofort einlesen, Spielstände und debug.log nebeneinander: history.connect leert „dateien“, solange
    # alte Momentaufnahmen im Format zurückliegen – ohne „dateien“ ordnet live_gehoert den Daten-Mod keiner Partie zu (31.10.: nach
    # einer debug.log von 88 MB zeigte die Seite sonst minutenlang „ohne Daten-Mod“)
    BROWSER.update(aktiv=True, start=_sekunde(time.localtime()))    # Knopf „Im Browser öffnen“ (Mod 0.28) ab hier
    t = threading.Thread(target=scan, args=(db, names, None), daemon=True)
    t.start()
    read_log(db, reader)
    t.join()
    ingame_schreiben(db, names, wis)             # Fenster im Spiel (Mod 0.26): erster Stand
    stable = {}
    # debug.log alle LOG_TAKT s, Spielstände und Prüfung alle POLL s (Test 0.26.2, 03.11.: neue Texte kamen im Spiel erst nach
    # 10–15 s an – im Schnitt 10 s Wartezeit bei POLL = 20 plus 1,6 s Rechnen). Texte erst schreiben, wenn ein Takt nichts Neues
    # brachte: der Monat steht dann vollständig im Log; bei schnellem Spiel (jeder Takt bringt Neues) spätestens nach 10 s, und
    # höchstens alle SCHREIB_ABSTAND s (Rechnen ~1,5 s unter der Sperre – Prüfung 03.11.).
    offen, naechster, geschrieben = None, 0.0, 0.0
    while True:
        try:
            if ENDE.is_set():                    # Hintergrund: Spiel weg – debug.log ein letztes Mal, dann Ende (spiel_pruefen)
                read_log(db, reader)
                beenden(ENDE_GRUND["text"])
                return
            neu = read_log(db, reader)
            if neu and offen is None:
                offen = time.monotonic()
            if (offen is not None and (not neu or time.monotonic() - offen >= 10)
                    and time.monotonic() - geschrieben >= SCHREIB_ABSTAND):
                ingame_schreiben(db, names, wis)
                offen, geschrieben = None, time.monotonic()
            if time.monotonic() >= naechster:
                if pruefung_aktualisieren() and offen is None:
                    ingame_schreiben(db, names, wis)
                if scan_und_schreiben(db, names, stable, wis):
                    offen, geschrieben = None, time.monotonic()
                fremde_nachladen(db, names)
                naechster = time.monotonic() + POLL
        except Exception as e:                   # noqa: BLE001 – der Faden darf nicht still sterben (Prüfung 03.11.)
            log(ue(t"Wächter-Faden: FEHLER {type(e).__name__}: {e}"))
            time.sleep(POLL)
        time.sleep(LOG_TAKT)


SCHREIB_ABSTAND = 15


def sperre_belegen():
    """Sperre des Ratgebers (Port PORT + SPERRE_ABSTAND) – vor dem Einlesen, damit ein zweiter Start (Wächter, .bat) schon während
    des Ladens merkt, dass einer läuft (Prüfung 03.11.). -> Socket (offen halten) oder None, wenn schon belegt."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", PORT + SPERRE_ABSTAND))
        return s
    except OSError as e:
        s.close()
        return None if waechter.port_belegt(e) else s        # nur gesperrt (Hyper-V): dann ohne Sperre weiter


def laeuft_schon():
    """True, wenn jemand unter PORT antwortet – reiner Verbindungsaufbau ohne die Sperre der Datenbank (die Abfrage /api/partien wartete
    unter Last auf ingame_schreiben, Prüfung 03.11.). Ob das ein Ratgeber ist, sagt die Sperre (sperre_belegen)."""
    return waechter.port_offen(PORT)


def make_handler(db, names, wis):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json; charset=utf-8", kopf=None):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            for k, v in (kopf or {}).items():     # z. B. Content-Encoding: gzip (/api/wiki)
                self.send_header(k, v)
            self.end_headers()
            try:
                self.wfile.write(data)
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                pass                      # Browser hat die Seite schon verlassen

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path in ("/", "/wiki", "/techbaum"):    # eigene Ansichten (30.10., web/ansichten.js) auf derselben Seite
                with open(WEB, "rb") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")
            if u.path.endswith(".js") and "/" not in u.path[1:]:      # app.js, browser.js aus web/
                p = os.path.join(os.path.dirname(WEB), os.path.basename(u.path))
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        return self.send(200, f.read(), "text/javascript; charset=utf-8")
            if u.path == "/api/partien":
                with lock:
                    return self.send(200, history.partien(db))
            if u.path == "/api/alles":             # ab Mod 0.12: alle Werte und Texte des Spielerlandes
                with lock:
                    row = db.execute("SELECT tag FROM momentaufnahmen WHERE partie_id=? ORDER BY jahr DESC LIMIT 1",
                                     (q.get("partie", [""])[0],)).fetchone()
                    d = history.live_alles(db, row[0]) if row else None
                if d:                              # Namen/Format der Modifikatoren (Kacheln zeigen sie deutsch)
                    mt = modtypes()
                    keys = {k for art, objs in d["werte"].items() if art.endswith("mod")
                            for o in objs.values() for k in o}
                    d["modnamen"] = {k: {"name": mt[k].get("name"), "percent": mt[k].get("percent") == "yes",
                                         "already_percent": mt[k].get("already_percent") == "yes",
                                         "boolean": mt[k].get("boolean") == "yes"}
                                     for k in keys if k in mt}
                return self.send(200 if d else 404, d or {"fehler": ue("Partie unbekannt")})
            if u.path == "/api/roh":               # ab Format 4: alle Spielstand-Einträge zum Spielerland
                with lock:
                    d = history.roh(db, q.get("partie", [""])[0])
                return self.send(200 if d else 404, d or {"fehler": ue("Partie unbekannt")})
            if u.path == "/api/daten":
                with lock:
                    d = history.series(db, q.get("partie", [""])[0], names, wis, voll=WISSEN_VOLL)
                return self.send(200 if d else 404, d or {"fehler": ue("Partie unbekannt")})
            if u.path == "/api/bevoelkerung":      # Kachel Bevölkerung: Spielstand-Pops + Live-Werte/Texte
                with lock:
                    d = bevoelkerung.build(db, q.get("partie", [""])[0], names, modtypes())
                return self.send(200 if d else 404, d or {"fehler": ue("Partie unbekannt")})
            if u.path == "/api/wissen":            # vollständiges Spielwissen je Ordner (data/spielwissen/…)
                ordner = q.get("ordner", ["_index"])[0]
                p = os.path.join(WISSEN_VOLL, os.path.basename(ordner) + ".json")
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        return self.send(200, f.read())
                return self.send(404, {"fehler": ue("Ordner unbekannt")})
            if u.path == "/api/wiki":              # Mechanik-Wiki (30.10., eu5ratgeber/wiki.py): je Spielversion einmal gebaut
                gz = "gzip" in self.headers.get("Accept-Encoding", "")
                data = wiki.laden(WISSEN_VOLL, names.loc, modtypes(), wis["version"], log, gz=gz)
                return self.send(200, data, kopf={"Content-Encoding": "gzip"} if gz else None)
            if u.path == "/api/techbaum":          # Ansicht Fortschritte (30.10., eu5ratgeber/techbaum.py): alle Fortschritte
                techbaum.statisch(WISSEN_VOLL, names)      # ohne Sperre: einmal je Spielversion (Zwischenspeicher _techbaum_f1)
                with lock:                                 # + Stand der Partie; ~3 MB, gepackt ~0,9 MB (gemessen 30.10.)
                    d = techbaum.api(db, q.get("partie", [""])[0], WISSEN_VOLL, names, wis)
                if not d:
                    return self.send(404, {"fehler": ue("Partie unbekannt")})
                data = json.dumps(d, ensure_ascii=False).encode("utf-8")
                if "gzip" in self.headers.get("Accept-Encoding", ""):
                    import gzip
                    return self.send(200, gzip.compress(data, 5), kopf={"Content-Encoding": "gzip"})
                return self.send(200, data)
            if u.path == "/api/pruefung":          # Spiel-Update erkannt? (Warnung oben auf der Seite)
                return self.send(200, PRUEFUNG)
            if u.path == "/api/namen":             # Anzeigenamen für Schlüssel (Lokalisierung)
                keys = q.get("k", [""])[0].split(",")
                return self.send(200, {k: names(k) for k in keys[:5000] if k})
            self.send(404, {"fehler": ue("nicht gefunden")})

        def do_POST(self):
            u = urlparse(self.path)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            try:
                with lock:
                    if u.path in ("/api/hallo", "/api/tschuess"):
                        tid = str(body.get("id", ""))[:40]
                        with tab_lock:
                            if u.path == "/api/hallo":
                                TABS.add(tid)
                            else:
                                TABS.discard(tid)
                                threading.Timer(TAB_GNADE, tab_pruefen).start()
                    elif u.path == "/api/markierung":
                        history.add_mark(db, body["partie"], body["datum"], body.get("text", "").strip()[:200])
                    elif u.path == "/api/markierung/loeschen":
                        history.delete_mark(db, int(body["id"]))
                    else:
                        return self.send(404, {"fehler": ue("nicht gefunden")})
                self.send(200, {"ok": True})
            except (KeyError, ValueError) as e:
                self.send(400, {"fehler": ue(t"ungültig: {e}")})
    return H


def main():
    global PORT, DB_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("befehl", choices=["einlesen", "start"])
    ap.add_argument("--browser", action="store_true", help="Seite im Browser öffnen, sobald sie erreichbar ist")
    # zum Prüfen neben dem laufenden Ratgeber: eigene Datenbank (Kopie) und eigener Port (02.10.)
    ap.add_argument("--port", type=int, default=PORT, help=f"Port der Webseite (Standard {PORT})")
    ap.add_argument("--db", default=DB_PATH, help="Datenbank (Standard data/verlauf.sqlite)")
    ap.add_argument("--hintergrund", action="store_true",
                    help="ohne Konsole (Wächter): Meldungen in data/ratgeber.log, Ende mit dem Spiel")
    a = ap.parse_args()
    PORT, DB_PATH = a.port, a.db
    if a.hintergrund:
        global HINTERGRUND
        HINTERGRUND = True
    # Doppelstart verhindern (02.10.: zwei Server am selben Port - Windows erlaubt das wegen SO_REUSEADDR ohne Fehler,
    # beide schrieben in dieselbe Datenbank, die Seite hing): läuft schon ein Ratgeber, nur den Browser öffnen
    sperre = sperre_belegen() if a.befehl == "start" else None
    if a.befehl == "start" and sperre is None:
        log(ue(t"Ratgeber läuft schon (oder lädt noch): http://127.0.0.1:{PORT} - kein zweiter Start"))
        if a.browser:
            browser_wenn_bereit()
        return
    if a.befehl == "start" and laeuft_schon():
        raise PortBelegt(ue(t"Port {PORT} wird von einem anderen Programm benutzt, zum Beispiel AnkiConnect. Beende es und starte den Ratgeber neu."))
    if a.hintergrund or not sys.stderr:
        os.makedirs(os.path.dirname(LOGDATEI), exist_ok=True)
        waechter.kuerzen(LOGDATEI, waechter.LOG_GRENZE)
        # pythonw hat kein stderr: Ausnahmen (auch in Threads) sonst spurlos – in die Logdatei
        sys.stderr = open(LOGDATEI, "a", encoding="utf-8", buffering=1)
    pruefung_aktualisieren()                     # vor dem Einlesen: Warnung steht oben im Konsolenfenster
    db = history.connect(DB_PATH)
    names = gamedata.Names()
    log(ue(t"Datenbank {DB_PATH}"))
    wis = wissen.load(DATEN, names)
    log(ue(t"Spielwissen {wis['version']}: {len(wis['gebaeude'])} Gebäude, {len(wis['gueter'])} Güter"))
    global WISSEN_VOLL
    WISSEN_VOLL = wissen_voll.ensure(DATEN, wis["version"], names, gamedata.modifikatoren(), log)
    log(ue(t"Spielwissen vollständig: {WISSEN_VOLL}"))
    reader = livelog.LogReader()
    if reader.fortsetzen(history.logstand_laden(db, reader.path)):
        log(ue(t"debug.log: weiter ab {reader.pos / 1e6:.0f} MB (Lesestand gespeichert, dieselbe Datei)"))
    if a.befehl == "einlesen":
        read_log(db, reader)
        scan(db, names, None)
        for p in history.partien(db):
            log(ue(t"Partie {p['name']} ({p['land']}): {p['anzahl']} Stände bis {p['bis']}"))
        return
    # Webseite sofort, Einlesen im Hintergrund (viele neue Stände können Minuten dauern; ebenso eine lange debug.log – 31.10.:
    # 88 MB nach 19 Spielmonaten, die Seite kam erst nach Minuten, weil read_log vor dem Server lief)
    threading.Thread(target=watcher, args=(db, names, reader, wis), daemon=True).start()
    ThreadingHTTPServer.allow_reuse_address = False      # zweiter Server am selben Port -> Fehler statt stiller Doppelung
    global SERVER
    try:
        srv = SERVER = ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(db, names, wis))
    except OSError as e:
        log(ue(t"Port {PORT} ist belegt ({e}) - läuft schon ein Ratgeber? Kein zweiter Start."))
        return
    if HINTERGRUND:
        log(ue(t"Webseite: http://127.0.0.1:{PORT}  (im Hintergrund; Ende mit dem Spiel)"))
        threading.Thread(target=spiel_pruefen, daemon=True).start()
    else:
        log(ue(t"Webseite: http://127.0.0.1:{PORT}  (Beenden mit Strg+C oder durch Schließen des Browser-Tabs)"))
        if pfade.eingefroren():
            threading.Thread(target=spiel_pruefen, daemon=True).start()
    if a.browser:
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except PortBelegt as e:
        log(str(e))
