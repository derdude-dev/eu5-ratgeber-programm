"""Verlauf über Spielstände: Momentaufnahmen in SQLite, Zeitreihen für die Webseite.

Je Spielstand eine Momentaufnahme (zlib-komprimiertes JSON), Schlüssel Partie + Datum + Land.
Autosaves überschreiben sich reihum - deshalb liest der Wächter jeden neuen Stand sofort ein.
"""
import contextlib
import json
import os
import re
import sqlite3
import time
import zlib

from . import empfehlungen, handel, krieg, nachbarn, snapshot, wirtschaftsplan
from . import sprache
from . import techbaum                       # Ansicht Fortschritte (30.10.): Vorschlag je Schwerpunkt für Forschung/Empfehlungen
from . import gruendung                      # Kachel Ländergründung (30.10.)
from . import startstrategie                 # Kachel Startstrategie (31.10.)
from .savefile import SaveFile

SCHEMA = """
CREATE TABLE IF NOT EXISTS momentaufnahmen (
    partie_id TEXT, datum TEXT, land_id INTEGER,
    partie TEXT, jahr REAL, tag TEXT, land TEXT,
    datei TEXT, eingelesen TEXT, json BLOB,
    PRIMARY KEY (partie_id, datum, land_id)
);
CREATE TABLE IF NOT EXISTS dateien (
    pfad TEXT PRIMARY KEY, mtime REAL, groesse INTEGER, ergebnis TEXT
);
CREATE TABLE IF NOT EXISTS markierungen (
    id INTEGER PRIMARY KEY AUTOINCREMENT, partie_id TEXT, datum TEXT, text TEXT, angelegt TEXT
);
CREATE TABLE IF NOT EXISTS monatswerte (
    tag TEXT, jahr INTEGER, monat INTEGER, tagnr INTEGER, werte TEXT, erfasst TEXT,
    PRIMARY KEY (tag, jahr, monat)
);
CREATE TABLE IF NOT EXISTS monat_diplomatie (
    tag TEXT, jahr INTEGER, monat INTEGER, anderes TEXT, beziehung TEXT, werte TEXT,
    PRIMARY KEY (tag, jahr, monat, anderes, beziehung)
);
CREATE TABLE IF NOT EXISTS monat_extra (
    art TEXT, tag TEXT, jahr INTEGER, monat INTEGER, schluessel TEXT, werte TEXT,
    PRIMARY KEY (art, tag, jahr, monat, schluessel)
);
CREATE TABLE IF NOT EXISTS ortsliste (
    hash TEXT PRIMARY KEY, orte TEXT
);
CREATE TABLE IF NOT EXISTS monat_details (
    art TEXT, tag TEXT, jahr INTEGER, monat INTEGER, id INTEGER, schluessel TEXT, bezug INTEGER, werte TEXT,
    PRIMARY KEY (art, tag, jahr, monat, id)
);
CREATE TABLE IF NOT EXISTS logstand (
    pfad TEXT PRIMARY KEY, stand TEXT
);
CREATE INDEX IF NOT EXISTS ix_extra_monat ON monat_extra (tag, jahr, monat);
CREATE INDEX IF NOT EXISTS ix_details_monat ON monat_details (tag, jahr, monat);
"""
# Tabellen mit Mod-Werten je Land und Monat (Neuladen: Monat bzw. spätere Monate löschen, store_log)
MONAT_TABELLEN = ("monat_extra", "monat_details", "monat_diplomatie")
# Detailzeilen (Orte, Gebäude, Märkte): die letzten DETAIL_MONTHS Monate vollständig, ältere nur Januar
DETAIL_MONTHS = 36
TEXT_MONTHS = 3
EXTRA_ARTS = ("staende", "pops", "charakter", "krieg", "handel", "kredit", "katastrophe", "einheit", "preise",
              "modifikatoren", "privileg", "kabinett",
              # ab Mod 0.11
              "finanzen", "handel_kosten", "untertan", "stand_einkommen", "text",
              # ab Mod 0.19: Armeen und Flotten aller Kriegsteilnehmer (RG1F)
              "kriegseinheit")
# Monatlich geschriebene Listen (je Krieg, Katastrophe, Kredit, Einheit): fehlen sie im neuesten Monat, gibt es keine mehr –
# der letzte Monat mit Einträgen wäre veraltet (Krieg beendet, Kredit getilgt). Kriegskachel 25.10.
AKTUELLE_LISTEN = ("krieg", "katastrophe", "kredit", "einheit", "kriegseinheit")


def jahr(datum):
    """'1337.7.2' -> 1337.49... (für Achsen und Sortierung)."""
    y, m, d = (int(x) for x in datum.split(".")[:3])   # eine Stundenangabe (4. Teil) fällt weg
    return y + (m - 1) / 12 + (d - 1) / 365


# Aufbau der Momentaufnahme; höher = neue Felder. Ältere Stände werden neu eingelesen, solange die Datei da ist.
# 2 (28.09.): Gesellschaftswerte, Privilegien, Gesetze, Reformen, Kabinett, Pops je Ort, Heimatmarkt-Details
# 3 (28.09.): Forschung, Untertanen mit Angliederung, Marktnamen, Seeleute-Kosten
# 4 (28.09.): roh = alle Einträge des Spielstands zum Spielerland (ungekürzt), aktive Produktionsmethoden
# 5 (29.09.): maerkte = alle Märkte mit eigenen Orten oder eigenen Händlern (je eine Kachel)
# 6 (29.09.): Ortsnamen korrigiert (Orts-ID n = Index n-1 der Ortsliste, vorher um eins verschoben)
# 7 (29.09.): aktive Produktionsmethoden aller Gebäude (auch ohne _maintenance im Namen, z. B. clay_bricks)
# 8 (30.09., kurz): „ortssaldo“ = Feld possible – falsch zugeordnet, ungenutzt; der Ortssaldo wird in app.js berechnet
# 9 (30.09.): Marinepräsenz des Landes je Seezone (seepraesenz) für den Handelsvorteil
# 10 (04.10.): Krankheiten (disease_outbreak_manager, situation_manager/black_death) – Kachel Krankheiten
# 11 (25.10.): Gewinn je Gebäudeart in den Märkten und weltweit (gebaeude_gewinne) – Kachel Wirtschaftsplan
# 12 (25.10.): Straßen je Ort, Straße zur Hauptstadt, Hauptstadt, Marktzentrum (zentrum_id) – Bauplan
# 13 (25.10.): laufende Kriege mit Seiten, Verlusten, Schlachten, Besetzung und Militär je Teilnehmer – Kriegskachel
# 14 (25.10.): Militärauszug aller lebenden Länder – Kachel Nachbarn und Kriegsgelegenheiten (wählbare Länder)
# 15 (27.10., Patch 1.4): Zölle (Sätze je Gut, Zolleinnahmen, Marktbesitzer, Meinungsabzug), Handelsbestellungen roh, unsere
#    Handelsrouten aus trade_manager – Karte „Handelsbestellungen und Zölle“. Alle Spielstände werden neu eingelesen.
# 16 (29.10., Test 1.4.5): Handelsbestellungen über trade_order_refs des Landes zugeordnet (die Bestellung nennt kein Land)
# 17 (30.10.): Feld gruendung – Spielregel „Gründbare Länder“, geduldete Kulturen, Verbündete, Oberherr, Organisationen der Welt und
#    die fremden Besitzer der Orte, die infrage kommende Gründungen fordern (Kachel Ländergründung, eu5ratgeber/gruendung.py)
SNAPSHOT_FORMAT = 17


def connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.executescript(SCHEMA)
    cols = [r[1] for r in db.execute("PRAGMA table_info(momentaufnahmen)")]
    if "format" not in cols:
        db.execute("ALTER TABLE momentaufnahmen ADD COLUMN format INTEGER DEFAULT 1")
    if db.execute("SELECT 1 FROM momentaufnahmen WHERE format < ? LIMIT 1", (SNAPSHOT_FORMAT,)).fetchone():
        db.execute("DELETE FROM dateien")      # alle Dateien neu prüfen; veraltete Stände werden neu gebaut
    db.commit()
    return db


def is_text_save(path):
    with open(path, "rb") as f:
        head = f.read(31).decode("ascii", "replace")
    return head.startswith("SAV") and head[15:19] == "0004"


def peek_meta(path):
    """(playthrough_id, datum) aus dem metadata-Block am Dateianfang, ohne die Datei zu parsen."""
    with open(path, "rb") as f:
        head = f.read(65536)
    pid = re.search(rb'\n\tplaythrough_id="([^"]+)"', head)
    dat = re.search(rb"\n\tdate=(\d+\.\d+\.\d+)", head)
    return (pid.group(1).decode(), dat.group(1).decode()) if pid and dat else (None, None)


def reichweite(db, tag):
    """Märkte in Handelsreichweite des Landes (Mod ab 0.17: RG2 reichweite, Trigger in_trade_range_of), neuester Monat:
    [{id, name, handelsvorteil}] nach Name."""
    row = db.execute("SELECT MAX(jahr*12+monat) FROM monat_extra WHERE tag=? AND art='a.reichweite'", (tag,)).fetchone()
    if not row or row[0] is None:
        return []
    out = []
    for k, w in db.execute("SELECT schluessel, werte FROM monat_extra WHERE tag=? AND art='a.reichweite' AND jahr*12+monat=?",
                           (tag, row[0])):
        e = json.loads(w)
        if str(k).isdigit():
            out.append({"id": int(k), "name": e.get("name") or k, "handelsvorteil": e.get("hv")})   # Mod ab 0.18
    return sorted(out, key=lambda x: str(x["name"]))


def reichweite_ids(db):
    """{tag: [Markt-IDs in Reichweite]} aller Länder mit Mod-Daten (für das Einlesen der fremden Märkte)."""
    out = {}
    for (tag,) in db.execute("SELECT DISTINCT tag FROM monat_extra WHERE art='a.reichweite'"):
        out[tag] = [x["id"] for x in reichweite(db, tag)]
    return out


def fremde_veraltet(db, geprueft):
    """Neueste Momentaufnahme je Land, deren fremde Märkte nicht zur aktuellen Reichweite-Liste passen (die Liste kommt
    monatlich aus dem Mod, die Spielstände nur halbjährlich): [(partie_id, datum)]. geprueft: Menge schon geprüfter
    (Momentaufnahme, Liste) – das Entpacken der Momentaufnahme läuft nur, wenn sich eins von beiden geändert hat."""
    out = []
    for tag, ids in reichweite_ids(db).items():
        row = db.execute("SELECT partie_id, datum FROM momentaufnahmen WHERE tag=? ORDER BY jahr DESC LIMIT 1", (tag,)).fetchone()
        if not row or not ids:
            continue
        sig = (row[0], row[1], tuple(sorted(ids)))
        if sig in geprueft:
            continue
        geprueft.add(sig)
        js = db.execute("SELECT json FROM momentaufnahmen WHERE partie_id=? AND datum=? AND tag=?", (row[0], row[1], tag)).fetchone()
        s = json.loads(zlib.decompress(js[0]))
        if sorted(s.get("fremde_ids") or []) != sorted(ids):
            out.append((row[0], row[1]))
    return out


def ingest(db, path, names, log=print, lock=None, force=False):
    """Liest einen Spielstand ein, wenn er neu oder geändert ist. Gibt eine Kurzmeldung zurück.
    lock: nur um die Datenbankzugriffe - das Zerlegen (25-60 s) läuft ohne, damit die Webseite antwortet.
    force: auch einlesen, wenn derselbe Stand schon da ist (fremde Märkte nachladen, 02.10.)."""
    guard = lock or contextlib.nullcontext()
    st = os.stat(path)
    with guard:
        row = db.execute("SELECT mtime, groesse FROM dateien WHERE pfad=?", (path,)).fetchone()
        fremde = reichweite_ids(db)
    if not force and row and row[0] == st.st_mtime and row[1] == st.st_size:
        return None
    name = os.path.basename(path)
    known = None
    if is_text_save(path):
        pid, datum = peek_meta(path)
        with guard:
            known = db.execute("SELECT land FROM momentaufnahmen WHERE partie_id=? AND datum=? AND format >= ?",
                               (pid, datum, SNAPSHOT_FORMAT)).fetchone() if pid else None
    s = None
    if not is_text_save(path):
        msg = "binär - übersprungen (Startoption -force_text_save fehlt?)"
    elif known and not force:
        # Autosaves rotieren per Umbenennen - derselbe Stand ist schon eingelesen
        msg = f"{known[0]} {datum} schon vorhanden"
    else:
        t0 = time.time()
        sv = SaveFile(path)
        # fremde Märkte in Handelsreichweite (Liste aus dem Daten-Mod) mit vollem Marktbild – nur diese, alle 130 Märkte
        # kosteten 36 s und 9 MB je Spielstand (gemessen 02.10.)
        s = snapshot.build(sv, names, fremde=lambda tag: fremde.get(tag, []))
        m = s["meta"]
        msg = f"{m['land']} {m['datum']} ({time.time() - t0:.0f} s)"
    with guard:
        if s is not None:
            store_location_list(db, sv)
            db.execute("INSERT OR REPLACE INTO momentaufnahmen (partie_id, datum, land_id, partie, jahr, tag, land, "
                       "datei, eingelesen, json, format) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                           m["partie_id"], m["datum"], m["land_id"], m["partie"], jahr(m["datum"]), m["tag"], m["land"],
                           name, time.strftime("%Y-%m-%d %H:%M:%S"),
                           zlib.compress(json.dumps(s, ensure_ascii=False).encode("utf-8"), 6), SNAPSHOT_FORMAT))
        db.execute("INSERT OR REPLACE INTO dateien VALUES (?,?,?,?)", (path, st.st_mtime, st.st_size, msg))
        db.commit()
    log(f"{name}: {msg}")
    return msg


def logstand_laden(db, pfad):
    """Gespeicherter Lesestand der debug.log (livelog.LogReader.zustand) oder None."""
    row = db.execute("SELECT stand FROM logstand WHERE pfad=?", (pfad,)).fetchone()
    return json.loads(row[0]) if row else None


def logstand_speichern(db, pfad, stand):
    """Lesestand nach dem Speichern der gelesenen Zeilen sichern (31.10.: Neustart liest die debug.log nicht wieder von vorn)."""
    db.execute("INSERT OR REPLACE INTO logstand VALUES (?,?)", (pfad, json.dumps(stand, ensure_ascii=False)))
    db.commit()


def monats_stuecke(recs):
    """Zeilen aus debug.log in Monatsimpulse teilen (je ab der Landzeile RG1, ohne deren Fortsetzungen). store_log nacheinander
    je Stück ergibt dasselbe wie alle Zeilen auf einmal, die Sperre der Datenbank wird aber zwischen den Monaten frei (31.10.:
    eine debug.log von 88 MB hielt die Seite sonst ~2,5 Minuten auf)."""
    out = []
    for r in recs:
        if not out or (r["art"] == "land" and not r.get("fortsetzung")):
            out.append([])
        out[-1].append(r)
    return out


def store_log(db, recs, commit=True):
    """Zeilen aus debug.log speichern; derselbe Monat überschreibt (z. B. nach Neuladen). commit=False: innerer Aufruf
    (_ergaenzen) – der äußere schreibt einmal am Ende."""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    months = set()
    for r in recs:
        if r["art"] == "zeitsprung":
            # Neuladen eines älteren Spielstands in derselben Spielsitzung (LogReader, 25.10.): die späteren Monate gehören zu
            # einem verworfenen Verlauf – sonst blieben z. B. ein dort noch laufender Krieg und sein letzter Monat stehen
            for t in ("monatswerte",) + MONAT_TABELLEN:
                db.execute(f"DELETE FROM {t} WHERE tag=? AND jahr*12+monat > ?", (r["tag"], r["ab"]))
            continue
        if r.get("fortsetzung"):
            # ab Mod 0.24: weiteres Stück einer langen Zeile (1.4 kürzt Logeinträge) -> Werte zum Eintrag des ersten Stücks
            _ergaenzen(db, r)
            continue
        if r["art"] == "land":
            # neuer Monatsimpuls (die Landzeile RG1 kommt zuerst): was dieser Monat bisher hatte, gilt nicht mehr – Neuladen,
            # beendete Kriege, getilgte Kredite; die Zeilen des Impulses folgen
            for t in MONAT_TABELLEN:
                db.execute(f"DELETE FROM {t} WHERE tag=? AND jahr=? AND monat=?", (r["tag"], r["jahr"], r["monat"]))
            db.execute("INSERT OR REPLACE INTO monatswerte VALUES (?,?,?,?,?,?)",
                       (r["tag"], r["jahr"], r["monat"], r["tagnr"], json.dumps(r["werte"]), now))
            months.add((r["tag"], r["jahr"], r["monat"]))
        elif r["art"] == "diplomatie":
            db.execute("INSERT OR REPLACE INTO monat_diplomatie VALUES (?,?,?,?,?,?)",
                       (r["tag"], r["jahr"], r["monat"], r["anderes"], r["beziehung"], json.dumps(r["werte"])))
        elif r["art"].startswith("a."):
            # ab Mod 0.12 (RG2): alle Werte je Scope; eine Zeile kann in Stücken kommen -> im Monat zusammenführen
            key = str(r["id"])
            row = db.execute("SELECT werte FROM monat_extra WHERE art=? AND tag=? AND jahr=? AND monat=? AND schluessel=?",
                             (r["art"], r["tag"], r["jahr"], r["monat"], key)).fetchone()
            werte = {**(json.loads(row[0]) if row else {}), **r["werte"]}
            if r.get("name") is not None:
                werte["name"] = r["name"]
            db.execute("INSERT OR REPLACE INTO monat_extra VALUES (?,?,?,?,?,?)",
                       (r["art"], r["tag"], r["jahr"], r["monat"], key, json.dumps(werte, ensure_ascii=False)))
        elif r["art"] in EXTRA_ARTS:
            # ab Mod 0.9: Stände-Zusatz, Pops je Ort, Charaktere, Kriege, Handel, Kredite, Katastrophen,
            # Einheiten, Preise. Positionsfelder (rolle, name, gut, von, nach …) wandern mit in die Werte.
            extra = {k: v for k, v in r.items() if k not in ("art", "tag", "jahr", "monat", "tagnr", "werte")}
            db.execute("INSERT OR REPLACE INTO monat_extra VALUES (?,?,?,?,?,?)",
                       (r["art"], r["tag"], r["jahr"], r["monat"], _extra_schluessel(r), json.dumps({**extra, **r["werte"]})))
        elif not any(r["werte"].values()):
            continue    # nur Nullen: Wert im falschen Scope ausgewertet (so in Mod 0.5) - unbrauchbar
        else:
            bezug = r.get("ort") if r["art"] == "gebaeude" else r.get("zentrum")
            db.execute("INSERT OR REPLACE INTO monat_details VALUES (?,?,?,?,?,?,?,?)",
                       (r["art"], r["tag"], r["jahr"], r["monat"], r["id"], r.get("key"), bezug,
                        json.dumps(r["werte"])))
    for tag, j, m in months:
        cut = j * 12 + m - DETAIL_MONTHS
        db.execute("DELETE FROM monat_details WHERE tag=? AND jahr*12+monat < ? AND monat != 1", (tag, cut))
        db.execute("DELETE FROM monat_diplomatie WHERE tag=? AND jahr*12+monat < ? AND monat != 1", (tag, cut))
        db.execute("DELETE FROM monat_extra WHERE tag=? AND jahr*12+monat < ? AND monat != 1", (tag, cut))
        # Aufschlüsselungs-Texte sind groß: nur die letzten TEXT_MONTHS Monate plus jeweils Januar behalten
        db.execute("DELETE FROM monat_extra WHERE art='text' AND tag=? AND jahr*12+monat < ? AND monat != 1",
                   (tag, j * 12 + m - TEXT_MONTHS))
    if recs and commit:
        db.commit()
    return len(recs)


def _extra_schluessel(r):
    if r["art"] == "privileg":         # ohne ID: Stand + Name sind eindeutig
        return f"{r.get('stand', '')}:{r.get('name', '')}"
    if r["art"] in ("text", "untertan", "stand_einkommen"):
        return str(r.get("schluessel") or r.get("anderes") or r.get("name"))
    return f"{r.get('rolle', r.get('einheit', ''))}:{r.get('id', 0)}"


def _ergaenzen(db, r):
    """Stück einer langen Logzeile (RG1+, RG1M+ …, Mod 0.24) mit dem Eintrag desselben Monats zusammenführen."""
    if r["art"] == "land":
        row = db.execute("SELECT werte FROM monatswerte WHERE tag=? AND jahr=? AND monat=?",
                         (r["tag"], r["jahr"], r["monat"])).fetchone()
        if row:
            db.execute("UPDATE monatswerte SET werte=? WHERE tag=? AND jahr=? AND monat=?",
                       (json.dumps({**json.loads(row[0]), **r["werte"]}), r["tag"], r["jahr"], r["monat"]))
        return
    r = {k: v for k, v in r.items() if k != "fortsetzung"}
    # ohne eigenen Commit (31.10.: je Stück ein Commit – ~1.900 je Monat, 8 von 11 s Speicherzeit eines Monats)
    if r["art"].startswith("a."):
        store_log(db, [r], commit=False)     # RG2 führt Stücke ohnehin zusammen
        return
    if r["art"] == "diplomatie":
        sql = ("SELECT werte FROM monat_diplomatie WHERE tag=? AND jahr=? AND monat=? AND anderes=? AND beziehung=?",
               (r["tag"], r["jahr"], r["monat"], r["anderes"], r["beziehung"]))
    elif r["art"] in EXTRA_ARTS:
        sql = ("SELECT werte FROM monat_extra WHERE art=? AND tag=? AND jahr=? AND monat=? AND schluessel=?",
               (r["art"], r["tag"], r["jahr"], r["monat"], _extra_schluessel(r)))
    else:
        sql = ("SELECT werte FROM monat_details WHERE art=? AND tag=? AND jahr=? AND monat=? AND id=?",
               (r["art"], r["tag"], r["jahr"], r["monat"], r["id"]))
    row = db.execute(*sql).fetchone()
    if row:
        r["werte"] = {**json.loads(row[0]), **r["werte"]}
    store_log(db, [r], commit=False)


def store_location_list(db, save):
    """Ortsliste des Spielstands (Index = Orts-ID) einmal je Kartenstand ablegen - für Namen im Live-Log."""
    comp = save.meta.get("compatibility") or {}
    h = str(comp.get("locations_hash"))
    if comp.get("locations") and not db.execute("SELECT 1 FROM ortsliste WHERE hash=?", (h,)).fetchone():
        db.execute("INSERT INTO ortsliste VALUES (?,?)", (h, json.dumps(comp["locations"])))


def location_keys(db):
    row = db.execute("SELECT orte FROM ortsliste ORDER BY rowid DESC LIMIT 1").fetchone()
    return json.loads(row[0]) if row else []


def location_key(keys, lid):
    """Orts-ID -> Schlüssel: ID n steht an Index n-1 (siehe snapshot.loc_key)."""
    return keys[lid - 1] if isinstance(lid, int) and 0 < lid <= len(keys) else None


def _ortname(db, names=None):
    """Orts-ID -> Name über die Ortsliste des Spielstands (auch Seezonen)."""
    keys = location_keys(db)

    def f(i):
        k = location_key(keys, i)
        return (names(k) if names else k) if k else (str(i) if i is not None else None)
    return f


def live_details(db, tag, names=None):
    """Neuester Monat mit Detailzeilen für ein Land: Orte, Gebäude, Märkte, mit Namen."""
    row = db.execute("SELECT jahr, monat FROM monat_details WHERE tag=? ORDER BY jahr DESC, monat DESC LIMIT 1",
                     (tag,)).fetchone()
    if not row:
        row = db.execute("SELECT jahr, monat FROM monat_extra WHERE tag=? ORDER BY jahr DESC, monat DESC LIMIT 1",
                         (tag,)).fetchone()
    if not row:
        return None
    j, m = row
    nm = names or (lambda k: k)
    keys = location_keys(db)

    def ort(i):
        k = location_key(keys, i)
        return nm(k) if k else str(i)

    out = {"datum": f"{j}.{m}.1", "orte": [], "gebaeude": [], "maerkte": []}
    for art, id_, key, bezug, werte in db.execute(
            "SELECT art, id, schluessel, bezug, werte FROM monat_details WHERE tag=? AND jahr=? AND monat=?",
            (tag, j, m)):
        e = {"id": id_, **json.loads(werte)}
        if art == "ort":
            e["name"] = ort(id_)
            out["orte"].append(e)
        elif art == "gebaeude":
            # key = Typ-Schlüssel ("brewery"); ältere Zeilen enthalten noch den ganzen Tooltip
            k = re.search(r"BUILDING_TYPE,(\w+)", key or "")
            key = k.group(1) if k else key
            e.update(typ=key, name=nm(key) if key else "?", ort_id=bezug, ort=ort(bezug))
            out["gebaeude"].append(e)
        else:
            e.update(name=ort(bezug), zentrum_id=bezug)
            out["maerkte"].append(e)
    # Diplomatie: je anderes Land eine Zeile, Beziehungen (Nachbar, Rivale …) zusammengefasst
    dip = {}
    for anderes, bez, werte in db.execute(
            "SELECT anderes, beziehung, werte FROM monat_diplomatie WHERE tag=? AND jahr=? AND monat=?",
            (tag, j, m)):
        d = dip.setdefault(anderes, {"tag": anderes, "name": nm(anderes), "beziehungen": [], **json.loads(werte)})
        d["beziehungen"].append(bez)
    out["diplomatie"] = sorted(dip.values(), key=lambda d: d["name"])
    # ab Mod 0.9: weitere Zeilenarten, je Art aus dem neuesten Monat, in dem es sie gibt (Jahreszeilen nur im
    # Januar). RG2 (a.*) und Texte liefert live_alles() getrennt - sie sind groß.
    extra = {a: [] for a in EXTRA_ARTS if a != "text"}
    latest = 0
    lm = db.execute("SELECT MAX(jahr*12+monat) FROM monatswerte WHERE tag=?", (tag,)).fetchone()[0]
    for art, ym in db.execute("SELECT art, MAX(jahr*12+monat) FROM monat_extra WHERE tag=? GROUP BY art", (tag,)).fetchall():
        if art == "text" or art.startswith("a."):
            continue
        if art in AKTUELLE_LISTEN and lm and ym < lm:
            continue                       # im neuesten Monat keine Einträge mehr -> keine (alte nicht zeigen)
        latest = max(latest, ym)
        for (werte,) in db.execute("SELECT werte FROM monat_extra WHERE tag=? AND art=? AND jahr*12+monat=?", (tag, art, ym)):
            e = json.loads(werte)
            if art == "pops":
                e["ort"] = ort(e.get("id"))
            elif art == "handel":
                e["gut_name"] = nm(e.get("gut"))
            elif art == "untertan":
                e["name"] = nm(e.get("anderes"))
            extra.setdefault(art, []).append(e)
    if latest:
        out["extra_datum"] = _ym_datum(latest)
    out.update(extra)
    return out


def _ym_datum(ym):
    """jahr*12+monat -> 'J.M.1'."""
    return f"{(ym - 1) // 12}.{(ym - 1) % 12 + 1}.1"


def live_alles(db, tag):
    """Ab Mod 0.12: alle Werte je Scope (RG2) und Aufschlüsselungs-Texte (RG1I), je Art/Schlüssel der neueste Stand.
    -> {"werte": {art: {id: {feld: wert, "name": …}}}, "texte": {bereich: {id: {feld: text}}}, "datum": {art: 'J.M.1'}}"""
    werte, datum = {}, {}
    for art, ym in db.execute("SELECT art, MAX(jahr*12+monat) FROM monat_extra WHERE tag=? AND art LIKE 'a.%' GROUP BY art",
                              (tag,)).fetchall():
        datum[art[2:]] = _ym_datum(ym)
        werte[art[2:]] = {k: json.loads(w) for k, w in db.execute(
            "SELECT schluessel, werte FROM monat_extra WHERE tag=? AND art=? AND jahr*12+monat=?", (tag, art, ym))}
    texte = {}
    for (w,) in db.execute("SELECT werte FROM monat_extra WHERE tag=? AND art='text' ORDER BY jahr, monat", (tag,)):
        e = json.loads(w)
        if "bereich" in e:                     # Format ab 0.12: RG1I <art> <id> <feld> <Text>
            t = e.get("text", "")
            if e.get("gekuerzt"):              # 1.4: Logeintrag nach 1.024 Byte abgeschnitten (livelog.GEKUERZT)
                t += "\n… (vom Spiel gekürzt: 1.4 schreibt höchstens 1.024 Byte je Logeintrag)"
            texte.setdefault(e["bereich"], {}).setdefault(str(e["id"]), {})[e["feld"]] = t
    return {"werte": werte, "texte": texte, "datum": datum}


def live_gehoert(db, pid, tag):
    """Gehören die Werte des Daten-Mods (nur nach Kürzel abgelegt) zu dieser Partie? Ja, wenn sie die Partie dieses Landes mit
    dem jüngsten Spielstand (Dateizeit) ist – das Spiel, das gerade läuft, schreibt Mod-Zeilen und Autosaves. Ältere Partien
    desselben Landes zeigten sonst Werte der laufenden (Prüfer 30.10.: Walachei 1.4.4 mit der laufenden Forschung von 1338.4).
    Die Eingelesen-Zeit taugt nicht: beim Neueinlesen nach einem Formatwechsel ist ihre Reihenfolge zufällig."""
    row = db.execute("SELECT m.partie_id FROM momentaufnahmen m JOIN dateien d ON d.pfad LIKE '%' || m.datei WHERE m.tag=? "
                     "ORDER BY d.mtime DESC LIMIT 1", (tag,)).fetchone()
    return bool(row) and row[0] == pid


def gruendung_spiel(db, tag):
    """Ab Mod 0.25 (Kachel Ländergründung): je Gründung, die das Spiel uns zeigt (RG2 gruendung, neuester Monat), sichtbar und
    Gebietsfortschritt laut Spiel (Anteil an den nötigen Orten, 0–1). Die Probetexte von 0.25 (RG1I gruendung …) bleiben
    ungelesen – ohne Land unbrauchbar (Test 31.10.)."""
    werte, datum = empfehlungen._neueste(db, tag, "a.gruendung")
    return {"werte": werte, "datum": datum}


def live(db, tag, von_jahr=None):
    q = "SELECT jahr, monat, tagnr, werte FROM monatswerte WHERE tag=?"
    args = [tag]
    if von_jahr is not None:
        q += " AND jahr >= ?"
        args.append(int(von_jahr))
    rows = db.execute(q + " ORDER BY jahr, monat", args).fetchall()
    # einzelne Monatswerte aus den Mod-Bereichen dazu (für Verläufe): Werte wie im Wirtschaftsfenster des Spiels
    # (GetIncomeValue, monthly_balance = GetIncomeValue − Reglerkosten, geprüft 29 Monate), Gewinn der Handelsrouten
    # (EconomyView.GetTradeBalance) und Modifikator trade_income (Handelseinnahmen = Gewinn × Modifikator)
    extra = {}
    for art, feld, name in (("a.land", "GetIncomeValue", "einkommen_spiel"), ("a.land", "monthly_balance", "saldo_spiel"),
                            ("a.land", "eco_GetTradeBalance", "handel_gewinn"), ("a.landmod", "trade_income", "handel_mod")):
        for j, m, w in db.execute("SELECT jahr, monat, werte FROM monat_extra WHERE art=? AND tag=?", (art, tag)):
            v = json.loads(w).get(feld)
            if v is not None:
                extra.setdefault((j, m), {})[name] = v
    # Gesellschaftswerte je Monat (sv_<achse>, a.land) – zeigen, ob eine Achse trotz Verschiebung stillsteht (30.09.)
    for j, m, w in db.execute("SELECT jahr, monat, werte FROM monat_extra WHERE art='a.land' AND tag=?", (tag,)):
        for k, v in json.loads(w).items():
            if k.startswith("sv_") and isinstance(v, (int, float)):
                extra.setdefault((j, m), {})[k] = v
    # Summe Gewinn / möglicher Gewinn aller Gebäude je Monat (Gebäudezeilen des Mods, monatlich seit 0.5)
    for j, m, g, pg in db.execute("SELECT jahr, monat, SUM(json_extract(werte,'$.profit')), SUM(json_extract(werte,'$.potential_profit')) "
                                  "FROM monat_details WHERE art='gebaeude' AND tag=? GROUP BY jahr, monat", (tag,)):
        if g is not None:
            extra.setdefault((j, m), {}).update(gebaeude_gewinn=round(g, 3), gebaeude_moeglich=round(pg or 0, 3))
    return [{"datum": f"{j}.{m}.{d}", "jahr": jahr(f"{j}.{m}.{d}"), **json.loads(w), **extra.get((j, m), {})} for j, m, d, w in rows]


def partien(db):
    rows = db.execute("""SELECT partie_id, MAX(partie), MAX(land), COUNT(*), MIN(datum), MAX(jahr)
                         FROM momentaufnahmen GROUP BY partie_id ORDER BY MAX(eingelesen) DESC""").fetchall()
    out = []
    for pid, partie, land, n, _, maxj in rows:
        last = db.execute("SELECT datum FROM momentaufnahmen WHERE partie_id=? ORDER BY jahr DESC LIMIT 1",
                          (pid,)).fetchone()[0]
        out.append({"id": pid, "name": partie, "land": land, "anzahl": n, "bis": last})
    return out


def roh(db, pid):
    """Rohdaten (alle Einträge zum Spielerland) der neuesten Momentaufnahme einer Partie."""
    row = db.execute("SELECT json, datum FROM momentaufnahmen WHERE partie_id=? ORDER BY jahr DESC LIMIT 1", (pid,)).fetchone()
    if not row:
        return None
    s = json.loads(zlib.decompress(row[0]))
    return {"datum": row[1], "roh": s.get("roh") or {}}


def _load(db, pid):
    rows = db.execute("SELECT json FROM momentaufnahmen WHERE partie_id=? ORDER BY jahr", (pid,)).fetchall()
    return [json.loads(zlib.decompress(r[0])) for r in rows]


def _months_back(datum, n):
    """Monatsschlüssel 'JJJJ.MM' für n Monate vor dem Datum."""
    y, m = (int(x) for x in datum.split(".")[:2])
    k = y * 12 + (m - 1) - n
    return f"{k // 12}.{k % 12 + 1:02d}"


def wissen_auszug(wis, last, names, mod_keys=()):
    """Spielwissen, soweit die Seite es für diesen Stand braucht (spielwissen.json ist ~10 MB).
    mod_keys: Modifikatoren der Live-Zeile RG1R, für die Namen gebraucht werden."""
    if not wis:
        return {}
    nm = names or (lambda k: k)
    orte = {}
    for o in last.get("orte", []):
        key = o.get("key")
        h = wis["hierarchie"].get(key, {})
        t = wis["ortsmerkmale"].get(key, {})
        orte[str(o["id"])] = {**{k: v for k, v in h.items()}, **{f"{k}_name": nm(v) for k, v in h.items() if v},
                              **t, **{f"{k}_name": nm(v) for k, v in t.items() if isinstance(v, str)},
                              "rang_name": nm(o.get("rang"))}
    typen = {b.get("typ") for b in last.get("gebaeude", [])}
    gebaeude = {k: wis["gebaeude"][k] for k in typen if k in wis["gebaeude"]}
    privs = {}
    for p in last.get("privilegien", []):
        d = wis["privilegien"].get(p)
        if d:
            privs[p] = {"name": wis["namen"]["privilegien"].get(p, p), "stand": d["estate"], "stand_name": nm(d["estate"]),
                        "wirkungen": [{"modifikator": m, "name": wis["namen"]["modifikatoren"].get(m, m), "wert": v}
                                      for m, v in d["modifiers"].items()]}
    return {"orte": orte, "gebaeude": gebaeude, "gueter": wis["gueter"], "privilegien": privs,
            "namen": {"gueter": wis["namen"]["gueter"], "gebaeude": wis["namen"]["gebaeude"], "pms": wis["namen"]["pms"],
                      "modifikatoren": {m: wis["namen"]["modifikatoren"].get(m, m)
                                        for m in {"tolerance_own", "tolerance_heretic", "tolerance_heathen", *mod_keys}},
                      "kategorien": {c: nm(c) for c in {x.get("category") for x in [*gebaeude.values(), *wis["gueter"].values()]} if c},
                      "gesellschaft": {k: nm(k) for k in last.get("gesellschaft", {})},
                      "gesetze": {v: nm(v) for v in (last.get("gesetze") or {}).values() if isinstance(v, str)},
                      "gesetz_kategorien": {k: nm(k) for k in (last.get("gesetze") or {})},
                      "reformen": {v: nm(v) for v in (last.get("reformen") or []) if isinstance(v, str)}}}


def gebaeude_status(voll, last):
    """Kachel Güter (24.10.): je Gebäudeart, wie sie für uns steht – laut Spieldateien (building_types: is_special,
    country_potential; advances: unlock_building) und den erforschten Fortschritten des Spielstands:
    {art: {bei_uns, sonder, landbedingung, fortschritt: [Namen] oder None}}. fortschritt = keiner der freischaltenden Fortschritte
    erforscht. Ersetzt die Gütertexte des Mods (Goods.GetSources/GetDemandsForBuildings): ohne Land ausgewertet ließen sie 86 von
    126 Quellen und 1.552 von 1.713 Nachfrage-Einträgen aus (Test 0.18, 24.10.). Bedingungen des Orts sind nicht geprüft."""
    if not voll:
        return {}
    bt, adv = _voll(voll, "building_types"), _voll(voll, "advances")
    erforscht = {a.get("key") for a in (last.get("forschung") or {}).get("fortschritte") or []}
    frei_durch = {}

    def walk(x, a):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "unlock_building":
                    for b in (v if isinstance(v, list) else [v]):
                        frei_durch.setdefault(b, []).append(a)
                else:
                    walk(v, a)
        elif isinstance(x, list):
            for v in x:
                walk(v, a)
    for a, e in adv.items():
        walk(e.get("def"), a)
    eigene = {}
    for b in last.get("gebaeude") or []:
        eigene[b.get("typ")] = eigene.get(b.get("typ"), 0) + 1
    # Erreichbar (Bauplan 25.10.): ein nicht erforschter Fortschritt ist für uns erreichbar, wenn er keine Bedingung (potential)
    # hat oder dieselbe wie ein schon erforschter – Polder (niederländische Kulturgruppe) wie die erforschte flämische
    # Tuchmacherei; Kalari (Indien) nicht – und sein Feld government (z. B. steppe_horde: Kurultai, Karawanserei) zu unserer
    # Regierungsform passt. Andere Bedingungen sind nicht auswertbar und gelten als nicht erreichbar.
    belegt = {json.dumps(((adv.get(a) or {}).get("def") or {}).get("potential"), sort_keys=True) for a in erforscht}
    regierung = (last.get("meta") or {}).get("regierungsform")

    def erreichbar(a):
        d = (adv.get(a) or {}).get("def") or {}
        p, g = d.get("potential"), d.get("government")
        if g and (not regierung or g != regierung):
            return False
        return p is None or json.dumps(p, sort_keys=True) in belegt

    # Landesbedingung (country_potential) gilt als erfüllt, wenn eine Gebäudeart, die wir haben, dieselbe trägt (Beleg wie oben)
    land_belegt = {json.dumps((bt.get(t) or {}).get("def", {}).get("country_potential"), sort_keys=True)
                   for t in eigene if isinstance((bt.get(t) or {}).get("def"), dict) and "country_potential" in bt[t]["def"]}

    def zeitalter(fa):
        offen = [a for a in fa if a not in erforscht]
        alter = sorted({((adv.get(a) or {}).get("def") or {}).get("age") for a in offen} - {None})
        return alter[0] if alter else None
    out = {}
    for k, e in bt.items():
        d = e.get("def")
        if not isinstance(d, dict):
            continue
        fa = frei_durch.get(k) or []
        out[k] = {"bei_uns": eigene.get(k, 0), "sonder": d.get("is_special") == "yes", "landbedingung": "country_potential" in d,
                  "fortschritt": None if not fa or any(a in erforscht for a in fa)
                  else [(adv.get(a) or {}).get("name") or a for a in fa],
                  # Fortschritte, die freischalten (auch erforschte) – Sondergebäude damit sind baubar (Polder), andere nicht
                  "freischaltung": [(adv.get(a) or {}).get("name") or a for a in fa] or None,
                  "erreichbar": not fa or any(a in erforscht for a in fa) or any(erreichbar(a) for a in fa),
                  "fortschritt_zeitalter": None if not fa or any(a in erforscht for a in fa) else zeitalter(fa),
                  "land_erfuellt": "country_potential" not in d
                                   or json.dumps(d["country_potential"], sort_keys=True) in land_belegt,
                  # löst diese Arten ab (castle: obsolete = stockade) – im Ort mit dem Nachfolger nicht mehr empfehlen
                  "loest_ab": [x for x in (d.get("obsolete") if isinstance(d.get("obsolete"), list) else [d.get("obsolete")])
                               if isinstance(x, str)]}
    return out


_VOLL_CACHE = {}


def _voll(voll, ordner):
    """Ein Ordner des vollständigen Spielwissens (data/spielwissen/<version>_f2/<ordner>.json), zwischengespeichert."""
    if not voll:
        return {}
    p = os.path.join(voll, ordner + ".json")
    if p not in _VOLL_CACHE:
        _VOLL_CACHE[p] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    return _VOLL_CACHE[p]


def _zahlen(v):
    """Grundwerte eines Skriptblocks für Spannen („1,1–1,9“): value-Zahlen und -Listen des Felds und seiner if/else_if/else-
    Zweige. add/subtract/multiply/divide sind Abwandlungen, keine Werte (sonst Beulenpest 0,2 aus subtract = { 0.2 0.7 })."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [v]
    out = []
    if isinstance(v, list):
        for x in v:                                          # Liste von Zweigen oder Zahlen
            out += _zahlen(x)
    elif isinstance(v, dict):
        x = v.get("value")
        if isinstance(x, (int, float, list)) and not isinstance(x, bool):
            out += [y for y in (x if isinstance(x, list) else [x]) if isinstance(y, (int, float)) and not isinstance(y, bool)]
        for k in ("if", "else_if", "else"):
            if isinstance(v.get(k), (dict, list)):
                out += _zahlen(v[k])
    return out


def _kurzwert(v):
    """Wert eines Krankheitsfelds: Zahl, sonst Grundwert und Spanne über alle Bedingungen (laut Spieldatei)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return {"grund": v}
    if isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v):
        return {"grund": None, "min": min(v), "max": max(v), "zufall": True}      # [0.3, 0.6] = Spanne je Ausbruch
    if isinstance(v, dict):
        z = _zahlen(v)
        g = v.get("value") if isinstance(v.get("value"), (int, float)) else None
        bedingt = any(k != "value" for k in v)                # nur value = { 0.85 0.95 } -> Zufall je Ausbruch
        return {"grund": g, "min": min(z) if z else None, "max": max(z) if z else None, "bedingt": bedingt, "zufall": not bedingt}
    return None


def buerokratien(voll, names=None):
    """Bürokratien laut Spieldateien (1.4.5: 60, davon 26 aus dem DLC „Across the Pillars“): Name, Beschreibung und ihr
    Wirkungs-Modifikator <schlüssel>_impact_modifier (Spielname „Auswirkung (…)“; zu jeder der 60 Bürokratien genau einer)
    mit seinen Quellen. Die Seite zeigt eingeführte Bürokratien (Daten-Mod buerokratie) und jede mit Auswirkung ≠ 0."""
    q, mt = _voll(voll, "_modifikator_quellen"), _voll(voll, "_modifikator_typen")
    out = {}
    for k, b in _voll(voll, "bureaucracies").items():
        if not isinstance(b, dict):
            continue
        m = f"{k}_impact_modifier"
        out[k] = {"name": b.get("name") or k, "beschreibung": b.get("beschreibung"),
                  "wirkung": m if m in mt else None, "quellen": handel.quellen_liste(q, names, m) if m in mt else []}
    return out


def einfluss_preise(voll, names=None):
    """1.4: Aktionen, die Politischen Einfluss kosten (in_game/common/prices, Schlüssel political_influence) mit Name, Preis und
    weiteren Kosten derselben Aktion; teuerste zuerst."""
    out = []
    for k, p in _voll(voll, "prices").items():
        d = (p or {}).get("def") if isinstance(p, dict) else None
        if isinstance(d, dict) and isinstance(d.get("political_influence"), (int, float)):
            out.append({"key": k, "name": p.get("name") or k, "einfluss": d["political_influence"],
                        "weitere": [_kosten_text(x, y, names) for x, y in d.items()
                                    if x != "political_influence" and isinstance(y, (int, float))]})
    return sorted(out, key=lambda x: (-x["einfluss"], x["name"]))


def _kosten_text(k, v, names=None):
    """Bestandteil eines Preises lesbar: „Stabilität 50“; scaled_gold wie in empfehlungen „mit dem Einkommen skaliert“ samt
    Faktor der Spieldatei."""
    z = f"{v:g}".replace(".", sprache.KOMMA)
    if k.startswith("scaled_"):
        n = names(k[7:]) if names else k[7:]
        return f"{n} ({'mit dem Einkommen ' if k == 'scaled_gold' else ''}skaliert, Faktor {z})"
    return f"{names(k) if names else k} {z}"


def krankheiten_wissen(voll, names=None):
    """Kachel Krankheiten (04.10.): Grundwerte der 7 Krankheiten (in_game/common/diseases), die Aktionen der Situation
    Schwarzer Tod (generic_actions mit select_trigger.visible situation:black_death) mit Preis (prices) und Wirkung
    (add_country_modifier → static_modifiers), Gebäude mit Seuchenwiderstand (Pesthaus, Krankenhaus)."""
    if not voll:
        return {}
    dis, ga, pr, sm = _voll(voll, "diseases"), _voll(voll, "generic_actions"), _voll(voll, "prices"), _voll(voll, "static_modifiers")
    sv, mt, bt = _voll(voll, "script_values"), _voll(voll, "_modifikator_typen"), _voll(voll, "building_types")

    def wert(x):
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            return x
        d = (sv.get(x) or {}).get("def") if isinstance(x, str) else None
        return d if isinstance(d, (int, float)) else None

    def mods(d):
        out = []
        for m, x in (d or {}).items():
            if m == "game_data" or not isinstance(mt.get(m), dict):
                continue
            t = mt[m]
            out.append({"key": m, "name": t.get("name") or m, "wert": wert(x), "roh": x if wert(x) is None else None,
                        "prozent": t.get("percent") == "yes"})
        return out

    def faktoren(x):
        """Zahlen 0 < f < 1 eines size-Blocks (Faktoren wie 0.1 × Monatseinkommen, 0.85 × Kontrolle)."""
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            return [x] if 0 < x < 1 else []
        if isinstance(x, dict):
            return [f for k, y in x.items() if k not in ("min", "max", "limit") for f in faktoren(y)]
        if isinstance(x, list):
            return [f for y in x for f in faktoren(y)]
        return []

    def modifikatoren_aus(effect):
        """(Name, Ebene, size-Block) aus add_country_modifier/add_location_modifier in einem Effektblock (rekursiv)."""
        out = []
        if isinstance(effect, dict):
            for k, x in effect.items():
                if k in ("add_country_modifier", "add_location_modifier"):
                    for y in (x if isinstance(x, list) else [x]):            # ein Block oder eine Liste von Blöcken
                        if isinstance(y, dict) and y.get("modifier"):
                            out.append((y["modifier"], "Land" if k == "add_country_modifier" else "Ort", y.get("size")))
                elif isinstance(x, (dict, list)):
                    out += modifikatoren_aus(x)
        elif isinstance(effect, list):
            for x in effect:
                out += modifikatoren_aus(x)
        return out

    def wirkung(effect):
        """Je Modifikator einmal; mit size (z. B. „Heilmittel beschaffen“: Monatseinkommen × 0,05–0,1) zählt der Wert der
        Spieldatei nur als Grundwert -> Kennzeichen skal an jedem Wert („× Monatseinkommen × 0,05–0,1“)."""
        je = {}
        for m, ebene, size in modifikatoren_aus(effect):
            e = je.setdefault(m, {"ebene": ebene, "sizes": []})
            if size is not None:
                e["sizes"].append(size)
        out = []
        for m, e in je.items():
            werte = mods((sm.get(m) or {}).get("def"))
            if e["sizes"]:
                s = json.dumps(e["sizes"])
                basis = ("Monatseinkommen" if "monthly_income_total" in s else "Kontrolle des Orts" if "local_control" in s
                         else "Größe laut Spieldatei")
                f = [str(x).replace(".", sprache.KOMMA) for x in sorted({round(x, 4) for z in e["sizes"] for x in faktoren(z)})]
                skal = basis + (f" × {f[0]}" if len(f) == 1 else f" × {f[0]}–{f[-1]}" if f else "")
                for w in werte:
                    w["skal"] = skal
            out.append({"modifikator": m, "ebene": e["ebene"], "name": (sm.get(m) or {}).get("name") or m, "werte": werte})
        return out

    krank = {}
    for k, e in dis.items():
        d = e.get("def") or {}
        krank[k] = {"name": e.get("name") or k, "beschreibung": e.get("beschreibung"),
                    "werte": {f: _kurzwert(d.get(f)) for f in ("monthly_spawn_chance", "r0", "mortality_rate",
                              "monthly_resistance_reduction", "location_spread_threshold", "calc_interval_days",
                              "percentage_to_meet_their_fate_on_calc", "character_mortality_chance") if f in d},
                    "ort_wirkung": mods(d.get("location_modifier") if isinstance(d.get("location_modifier"), dict) else {})}
    aktionen = []
    for k, e in ga.items():
        d = e.get("def") or {}
        st = d.get("select_trigger")                     # ein Block oder eine Liste von Blöcken
        sichtbar = any(isinstance(x, dict) and "situation:black_death" in json.dumps(x.get("visible"))   # auch in OR = { … }
                       for x in (st if isinstance(st, list) else [st]))
        if d.get("type") != "situation" or not sichtbar or k.startswith("stop_"):
            continue
        preis_key = str(d.get("price") or "").replace("price:", "")
        aktionen.append({"key": k, "name": e.get("name") or k, "beschreibung": e.get("beschreibung"),
                         "gruppe": d.get("exclusive_group"), "preis": ((pr.get(preis_key) or {}).get("def") if preis_key else None),
                         "wirkung": wirkung(d.get("effect"))})
    pest_aktion = next((a["name"] for a in aktionen
                        if any(w.get("key") == "enable_pest_house" for m in a["wirkung"] for w in m["werte"])), None)
    bedingung = {"pest_house": "nur während des Schwarzen Tods und erst nach der Aktion "
                               + (f"„{pest_aktion}“" if pest_aktion else "mit „Pesthaus möglich“") + "; wird danach entfernt",
                 "hospital": "Fortschritt " + ((_voll(voll, "advances").get("hospital_advance") or {}).get("name") or "hospital_advance")
                             + ", Ort mit Entwicklung ab 20"}
    gebaeude = [{"key": k, "name": (bt.get(k) or {}).get("name") or k, "beschreibung": (bt.get(k) or {}).get("beschreibung"),
                 "bedingung": bedingung[k], "wirkung": mods(((bt.get(k) or {}).get("def") or {}).get("modifier"))}
                for k in ("pest_house", "hospital") if k in bt]
    return {"krankheiten": krank, "aktionen": aktionen, "gebaeude": gebaeude}


def forschung_info(db, last, names=None, voll=None):
    """Kachel Forschung (30.09.): erforschte Fortschritte je Zeitalter (Zeitalter aus den Spieldateien, advances/<key>.def.age)
    und die Institutionen der Welt aus dem Spielstand (institution_manager). Feld months zählt, solange die Institution noch
    nicht entstanden ist, und bleibt beim Entstehen stehen (Bankwesen 1342.8: origin gesetzt, months bleibt 6) -> „entstanden
    nach x Monaten im Zeitalter“."""
    roh = last.get("roh") or {}
    L = roh.get("land") or {}
    adv, ages, inst = _voll(voll, "advances"), _voll(voll, "age"), _voll(voll, "institution")
    je = {}
    for k in (L.get("researched_advances") or {}):
        a = adv.get(k) or {}
        age = (a.get("def") or {}).get("age") or ""
        je.setdefault(age, []).append(a.get("name") or (names(k) if names else k))
    zeitalter = [{"key": a, "name": (ages.get(a) or {}).get("name") or a or "ohne Zeitalter", "fortschritte": sorted(je[a])}
                 for a in [*ages, *[x for x in je if x not in ages]] if a in je]
    keys = location_keys(db)
    eingefuehrt = set(L.get("institutions") or {})
    welt = []
    for k, v in ((roh.get("institution_manager") or {}).get("institutions") or {}).items():
        if not isinstance(v, dict) or v.get("active") != "yes":
            continue
        ok = location_key(keys, v.get("origin"))
        welt.append({"key": k, "name": (inst.get(k) or {}).get("name") or (names(k) if names else k),
                     "eingefuehrt": k in eingefuehrt, "entstanden": v.get("origin") is not None,
                     "ursprung": (names(ok) if names and ok else ok), "monate": v.get("months")})
    return {"zeitalter": zeitalter, "institutionen": welt}


def series(db, pid, names=None, wis=None, voll=None):
    """Alles, was die Webseite für eine Partie braucht."""
    snaps = _load(db, pid)
    if not snaps:
        return None
    punkte = []
    monate = {}
    for s in snaps:
        w, r = s["wirtschaft"], s["ressourcen"]
        orte = s["orte"]
        kon = [o["kontrolle"] for o in orte if isinstance(o.get("kontrolle"), (int, float))]
        mit = [b["gewinn"] for b in s["gebaeude"] if isinstance(b.get("gewinn"), (int, float))]
        p = {
            "datum": s["meta"]["datum"], "jahr": jahr(s["meta"]["datum"]),
            "einkommen": w["einkommen"], "ausgaben": w["ausgaben"], "saldo": w["saldo"],
            "gold": r.get("gold"), "stabilitaet": r.get("stability"), "inflation": r.get("inflation"),
            "prestige": r.get("prestige"),
            "handelswert": (w.get("letzter_monat") or {}).get("monthly_trade_value"),
            # knappe Güter im Heimatmarkt: Nachfrage mehr als 5 % über Angebot und Preis steigt (wie die Marktkachel)
            "knapp": sum(1 for x in (s.get("markt") or {}).get("gueter", []) if ist_knapp(x)),
            # je Markt: Marktwert wie im Spiel (Σ Preis × Nachfrage, geprüft 1.2.1342: 800,03 zu 799,98 im Marktfenster)
            # und Produktionswert (Σ Preis × Produktion)
            "marktwert": {str(mm["id"]): sum((x.get("preis") or 0) * (x.get("nachfrage") or 0) for x in mm.get("gueter", []))
                          for mm in (s.get("maerkte") or ([s["markt"]] if s.get("markt") else []))},
            "produktionswert": {str(mm["id"]): sum((x.get("preis") or 0) * sum((x.get("produktion") or {}).values())
                                                   for x in mm.get("gueter", []))
                                for mm in (s.get("maerkte") or ([s["markt"]] if s.get("markt") else []))},
            "steuer_orte": sum(o["steuer"] or 0 for o in orte),
            "moegliche_steuer": sum(o["moegliche_steuer"] or 0 for o in orte),
            "kontrolle_mittel": sum(kon) / len(kon) if kon else None,
            "orte": len(orte), "gebaeude": len(s["gebaeude"]),
            "gebaeude_gewinn": sum(mit) if mit else None,
            "staende": {e["stand"]: {"zufriedenheit": e.get("satisfaction"),
                                     "macht": (e.get("mod") or {}).get("power")} for e in s["staende"]},
        }
        punkte.append(p)
        # 12-Monats-Verläufe: letzter Wert = aktueller Monat; spätere Stände überschreiben
        for key, arr in (("einkommen", w.get("einkommen_12_monate")), ("saldo", w.get("saldo_12_monate"))):
            for i, v in enumerate(arr or []):
                monate.setdefault(_months_back(s["meta"]["datum"], len(arr) - 1 - i), {})[key] = v
    last = snaps[-1]
    y_last = int(last["meta"]["datum"].split(".")[0])
    jahre = {}
    for key, arr in (("bevoelkerung", last["verlauf_jahre"].get("bevoelkerung")),
                     ("steuerbasis", last["verlauf_jahre"].get("steuerbasis"))):
        for i, v in enumerate(arr or []):
            jahre.setdefault(y_last - len(arr) + 1 + i, {})[key] = v
    marks = [{"id": i, "datum": d, "jahr": jahr(d), "text": t} for i, d, t in db.execute(
        "SELECT id, datum, text FROM markierungen WHERE partie_id=? ORDER BY datum", (pid,))]
    return {
        "meta": last["meta"], "punkte": punkte,
        "monate": [{"monat": k, **v} for k, v in sorted(monate.items())],
        "jahre": [{"jahr": k, **v} for k, v in sorted(jahre.items())],
        "aktuell": {**{k: last[k] for k in ("wirtschaft", "ressourcen", "staende", "gebaeude", "orte", "markt",
                                            "gesellschaft", "privilegien", "gesetze", "reformen", "kabinett",
                                            "forschung", "untertanen", "markt_namen", "gebaeude_pm", "maerkte",
                                            "seepraesenz", "fremde_maerkte", "fremde_ids", "krankheiten")
                       if k in last}, "bau": bauliste(last, names)},
        "gebaeude_status": (gs := gebaeude_status(voll, last)),
        # Kachel Wirtschaftsplan (25.10.): Bedarf je Schwerpunkt, Ketten, Gewinn je Gebäudeart (Spielstand) – Stufen 1–3
        "wirtschaftsplan": (wp := wirtschaftsplan.build(
            last, wis, lambda o: _voll(voll, o), gs, empfehlungen._neueste(db, last["meta"]["tag"], "a.gebaeude")[0],
            empfehlungen._neueste(db, last["meta"]["tag"], "a.ort")[0],
            lambda oid: empfehlungen._rgo_kosten({"db": db, "tag": last["meta"]["tag"]}, oid), names,
            next(iter(empfehlungen._neueste(db, last["meta"]["tag"], "a.land")[0].values()), {})) if voll else {}),
        "wissen": wissen_auszug(wis, last, names,
                                ((ld := live_details(db, last["meta"]["tag"], names) or {}).get("modifikatoren") or [{}])[0]),
        "markierungen": marks,
        # Monatswerte aus debug.log für dieses Land ab dem Jahr der ersten Momentaufnahme
        "live": (lv := live(db, last["meta"]["tag"], int(snaps[0]["meta"]["datum"].split(".")[0]))),
        # deutsche Namen der Pop-Typen aus der Monatszeile (Felder pop_<typ>)
        "pop_namen": {k[4:]: (names(k[4:]) if names else k[4:]) for k in (lv[-1] if lv else {}) if k.startswith("pop_")},
        "live_details": ld or None,
        # Kachel je Krieg (25.10.): Seiten, Kräfte, Armeen mit Heerführern, Einheitentypen, Lage (Mod + Spielstand Format 13)
        "kriege": (kr := krieg.build(db, last, names, lambda o: _voll(voll, o) if voll else {},
                                     _ortname(db, names))),
        # Kachel Nachbarn und Kriegsgelegenheiten (25.10.): Stärke der Länder mit Beziehung, Ampel, Spielstand aller Länder
        "nachbarn": (nb := nachbarn.build(db, last, names, kr)),
        # Kachel Ländergründung (30.10.): Gründungen, die infrage kommen – Bedingungen, Gebiet, Besitzer (Spielstand ab Format 17),
        # Wirkung, Kette, Empfehlungen je Bereich; Daten-Mod für Stände-Macht, Rang-Stufe und Krieg (nach "nachbarn" – nutzt nb)
        # Daten-Mod nur, wenn er zu dieser Partie gehört (live_gehoert, Prüfer 30.10.)
        "gruendung": (gr := gruendung.build(last, (lambda o: _voll(voll, o)) if voll else None, names, nb,
                                            lv if (lg := live_gehoert(db, pid, last["meta"]["tag"])) else None,
                                            next(iter(empfehlungen._neueste(db, last["meta"]["tag"], "a.land")[0].values()), {})
                                            if lg else {}, gruendung_spiel(db, last["meta"]["tag"]) if lg else None)),
        # Karte „Handelsbestellungen und Zölle“ (27.10., Patch 1.4): Zölle je Route und Land, Herkunft der Routen, Spielstand
        # (zoelle/handelsbestellungen der Momentaufnahme gehen nur hierüber an die Seite – alle Zollsätze der Welt sind ~70 KB);
        # ab 29.10. Prüfung der Handelsbestellungen und Vorschläge je Schwerpunkt des Wirtschaftsplans (wp)
        "handel_zoelle": (hz := handel.build(db, last, names, _voll(voll, "defines"), _voll(voll, "_modifikator_quellen"), wp)),
        "preis_verlauf": preis_verlauf(db, last["meta"]["tag"]),
        "markt_verlauf": markt_verlauf(db, last["meta"]["tag"]),
        "forschung_info": forschung_info(db, last, names, voll),
        # Ansicht Fortschritte (30.10.): Fortschritte je Schwerpunkt des Wirtschaftsplans (wp) – Kachel Forschung, Empfehlungen
        "techbaum_vorschlag": (tv := techbaum.fuer_series(db, last, voll, names, wis, wp, gs, live_ok=lg) if voll else {}),
        # Kachel Startstrategie (31.10.): Kabinett, Politlinien, Privilegien, Reformen, Gesellschaftswerte, erste Gebäude/Forschung,
        # Diplomatie und Bündnisse je Schwerpunkt (nach techbaum_vorschlag – nutzt wp, tv, nb, gr; Daten-Mod nur mit lg). Ein Fehler
        # endet als {"fehler": …} und hält series() nicht auf
        "startstrategie": startstrategie.fuer_series(db, last, voll, (lambda o: _voll(voll, o)) if voll else None, names, wp, tv, nb,
                                                     gr, ld, lv, lg),
        "gueter_namen": {g["gut"]: g["name"] for g in (last.get("markt") or {}).get("gueter", [])},
        # erkannte Entscheidungen aus Momentaufnahmen und Monatswerten (Kachel Entscheidungen, 01.10.; nach "live" - nutzt lv)
        "aenderungen": aenderungen(snaps, lv, names),
        # Empfehlungen (Regeln, 02.10.): Handlung, Begründung mit Zahlen, Wirkung (berechnet / Spielwert / messen)
        "empfehlungen": empfehlungen.build(db, snaps, lv, names, wis, _voll(voll, "estates"), _voll(voll, "script_values"),
                                           _voll(voll, "_modifikator_typen"), bauliste(last, names),
                                           kw := krankheiten_wissen(voll, names), kr, nb, hz, techbaum=tv, gruendung=gr, wp=wp),
        # Kachel Krankheiten: Grundwerte, Aktionen des Schwarzen Tods, Gebäude mit Seuchenwiderstand (Spieldateien)
        "krankheiten_wissen": kw,
        # 1.4: Preise in Politischem Einfluss (Regierungskachel)
        "einfluss_preise": einfluss_preise(voll, names),
        # 1.4.5: Bürokratien mit Wirkungs-Modifikator und Quellen (Regierungskachel)
        "buerokratien": buerokratien(voll, names),
        # Märkte in Handelsreichweite (Mod ab 0.17, RG2 reichweite): Kennung und Name für die Kachelauswahl
        "reichweite": reichweite(db, last["meta"]["tag"]),
    }


# Regler im Wirtschaftsfenster (Mod-Monatszeile slider_<art>)
REGLER_NAMEN = {"court": "Hof", "diplomatic": "Diplomatie", "army": "Heer", "navy": "Flotte", "fort": "Festungen",
                "cultural": "Kultur", "colonial": "Kolonien", "exploration": "Erkundung", "food": "Nahrung", "upkeep": "Unterhalt"}


def aenderungen(snaps, lv, names=None):
    """Erkannte Entscheidungen (Kachel Entscheidungen, Nutzerwunsch 01.10.).

    Aus aufeinanderfolgenden Momentaufnahmen: Privilegien, Gesetze, Reformen, Kabinettsaktionen, Gebäude, Orte – Datum =
    spätere Momentaufnahme („zwischen von und bis“), Kabinettsaktionen mit ihrem Startdatum. Momentaufnahmen mit leerer Liste
    zählen nicht (einige frühe Stände 1337/1338 haben keine Privilegien/Gesetze – sonst „alles entzogen und neu vergeben“).
    Aus den Monatswerten des Mods: Herrscherwechsel (Regierungszeit fällt), Regler (Änderung ≥ 5 Prozentpunkte), Anzahl
    Privilegien (genauer Monat; verfeinert das Datum der Privilegien aus den Momentaufnahmen), Reformen, Untertanen, Rivalen.
    """
    nm = (lambda k: names(k) if names and k else k)
    out = []
    jetzt = {g["id"]: g for s in snaps for g in (s.get("gebaeude") or [])}   # spätere Stände überschreiben frühere

    def ev(datum, art, text, von=None):
        out.append({"datum": datum, "jahr": jahr(datum), "art": art, "text": text, "von": von})

    for a, b in zip(snaps, snaps[1:]):
        von, bis = a["meta"]["datum"], b["meta"]["datum"]
        pa, pb = set(a.get("privilegien") or []), set(b.get("privilegien") or [])
        if pa and pb:
            for k in sorted(pb - pa):
                ev(bis, "Privileg", f"Privileg vergeben: {nm(k)}", von)
            for k in sorted(pa - pb):
                ev(bis, "Privileg", f"Privileg entzogen: {nm(k)}", von)
        ga, gb = a.get("gesetze") or {}, b.get("gesetze") or {}
        if ga and gb:
            for k in sorted(set(ga) | set(gb)):
                if ga.get(k) != gb.get(k):
                    ev(bis, "Gesetz", f"{nm(k)}: {nm(ga.get(k)) or '–'} → {nm(gb.get(k)) or '–'}", von)
        ra, rb = set(a.get("reformen") or []), set(b.get("reformen") or [])
        if ra and rb:
            for k in sorted(rb - ra):
                ev(bis, "Reform", f"Reform eingeführt: {nm(k)}", von)
            for k in sorted(ra - rb):
                ev(bis, "Reform", f"Reform abgeschafft: {nm(k)}", von)
        ka = {(k.get("platz"), k.get("aktion"), k.get("seit")) for k in (a.get("kabinett") or [])}
        for k in b.get("kabinett") or []:
            if (k.get("platz"), k.get("aktion"), k.get("seit")) not in ka and k.get("seit"):
                ziel = ", ".join(str(v) for v in (k.get("ziele") or {}).values() if not re.match(r"^\w+:\d+$", str(v)))
                text = f"Kabinett: {k.get('aktion_name') or nm(k.get('aktion'))}"
                if ziel:
                    text += f" ({ziel})"
                if k.get("person"):
                    text += f" – {k['person']}"
                ev(k["seit"], "Kabinett", text)
        # Gebäude über ihre feste Nummer vergleichen: frühe Momentaufnahmen (bis 1340) tragen noch die um eins verschobenen
        # Ortsnamen (Fehler vor dem 29.09.) - Name und Ort deshalb aus der neuesten Momentaufnahme, in der die Nummer vorkommt
        if a.get("gebaeude") and b.get("gebaeude"):
            ga, gb = {g["id"]: g for g in a["gebaeude"]}, {g["id"]: g for g in b["gebaeude"]}
            def wo(i, g):
                g = jetzt.get(i, g)
                return f"{g.get('name') or nm(g.get('typ'))} in {g.get('ort')}"
            for i, g in gb.items():
                x, y = (ga[i].get("stufe") if i in ga else None), g.get("stufe")
                if i not in ga:
                    ev(bis, "Gebäude", f"{wo(i, g)} {'gebaut (Stufe ' + str(y) + ')' if y else 'Bau begonnen'}", von)
                elif (x or 0) != (y or 0):
                    ev(bis, "Gebäude", f"{wo(i, g)} {'fertig (Stufe ' + str(y) + ')' if not x else 'ausgebaut' if (y or 0) > x else 'zurückgestuft'}"
                       f"{f' (Stufe {x} → {y})' if x else ''}", von)
            for i, g in ga.items():
                if i not in gb:
                    ev(bis, "Gebäude", f"{wo(i, g)} abgerissen", von)
        if a.get("orte") and b.get("orte") and len(a["orte"]) != len(b["orte"]):
            ev(bis, "Orte", f"Orte: {len(a['orte'])} → {len(b['orte'])}", von)

    # Monatswerte (Mod): genauer Monat
    prev = None
    priv_monate = []
    for r in lv or []:
        if prev:
            d = r["datum"]
            if isinstance(r.get("ruler_reign"), (int, float)) and isinstance(prev.get("ruler_reign"), (int, float)) \
                    and r["ruler_reign"] < prev["ruler_reign"]:
                ev(d, "Herrscher", "Herrscherwechsel (Regierungszeit beginnt neu)")
            for k, n in REGLER_NAMEN.items():
                x, y = prev.get("slider_" + k), r.get("slider_" + k)
                if isinstance(x, (int, float)) and isinstance(y, (int, float)) and abs(y - x) >= 0.05:
                    ev(d, "Regler", f"Regler {n}: {round(x * 100)} % → {round(y * 100)} %")
            for k, n in (("privileges", None), ("reforms", "Reformen"), ("subjects", "Klientelländer"), ("rivals", "Rivalen")):
                x, y = prev.get(k), r.get(k)
                if isinstance(x, (int, float)) and isinstance(y, (int, float)) and x != y:
                    if k == "privileges":
                        priv_monate.append((jahr(d), d))
                    else:
                        ev(d, n, f"{n}: {x:g} → {y:g}")
        prev = r
    # Privilegien aus den Momentaufnahmen auf den Monat setzen, in dem sich die Anzahl geändert hat (falls im Zeitraum genau einer)
    for e in out:
        if e["art"] == "Privileg" and e["von"]:
            treffer = [d for j, d in priv_monate if jahr(e["von"]) < j <= e["jahr"]]
            if len(treffer) == 1:
                e["datum"], e["jahr"], e["von"] = treffer[0], jahr(treffer[0]), None
    return sorted(out, key=lambda e: (-e["jahr"], e["art"], e["text"]))


def preis_verlauf(db, tag, n=24):
    """Preise im Heimatmarkt je Monat (Mod-Zeile „preise“, price_<gut>), letzte n Monate: {monate, gueter: {gut: [..]}}."""
    rows = db.execute("SELECT jahr, monat, werte FROM monat_extra WHERE art='preise' AND tag=? ORDER BY jahr, monat",
                      (tag,)).fetchall()[-n:]
    gueter = {}
    for i, (_, _, w) in enumerate(rows):
        for k, v in json.loads(w).items():
            if k.startswith("price_") and isinstance(v, (int, float)):
                gueter.setdefault(k[6:], [None] * len(rows))[i] = v
    return {"monate": [f"{j}.{m}" for j, m, _ in rows], "gueter": gueter}


def ist_knapp(x):
    """Knapp = Nachfrage mehr als 5 % über Angebot und der Preis steigt (letzter Schritt im Preisverlauf des Spielstands).
    Ohne steigenden Preis behandelt das Spiel das Gut nicht als knapp (Lübeck 1342: Zucker Nachfrage 0,001, kein
    Angebot, 1,0 auf Vorrat, Preis fällt stetig 6,36 → 3,21). Ohne Preisverlauf nur die Mengenregel."""
    if not (x.get("nachfrage") or 0) > (x.get("angebot") or 0) * 1.05:
        return False
    pv = [v for v in (x.get("preisverlauf") or []) if isinstance(v, (int, float))]
    return pv[-1] > pv[-2] if len(pv) > 1 else True


def markt_verlauf(db, tag, n=24):
    """Je Markt die Monatswerte des Mods (Zeilen a.markt, monatlich seit 0.15), letzte n Monate:
    {markt_id: {monate, orte, bev, nahrung, nahrung_max, nahrung_saldo, haendlermacht}}; dazu unser Handelsvorteil im
    Heimatmarkt (Zeile „preise“: merchant_power). Bevölkerung und Nahrung stimmen mit Spielstand und Marktfenster überein
    (1.2.1342); GetTotalValueTraded des Mods (587,7) weicht vom Marktwert im Spiel ab (799,98) und wird nicht genutzt."""
    out = {}
    for j, m, k, w in db.execute("SELECT jahr, monat, schluessel, werte FROM monat_extra WHERE art='a.markt' AND tag=? "
                                 "ORDER BY jahr, monat", (tag,)):
        e = json.loads(w)
        r = out.setdefault(str(k), {"monate": [], "orte": [], "bev": [], "nahrung": [], "nahrung_max": [],
                                    "nahrung_saldo": [], "haendlermacht": [], "wir": []})
        r["monate"].append(f"{j}.{m}")
        for feld, key in (("orte", "market_location_count"), ("bev", "market_population"), ("nahrung", "market_food"),
                          ("nahrung_max", "market_max_food"), ("nahrung_saldo", "market_monthly_food_balance"),
                          ("haendlermacht", "total_merchant_power")):
            r[feld].append(e.get(key))
        r["wir"].append(None)
    for j, m, w in db.execute("SELECT jahr, monat, werte FROM monat_extra WHERE art='preise' AND tag=?", (tag,)):
        e = json.loads(w)
        r = out.get(str(e.get("id")))
        if r and f"{j}.{m}" in r["monate"]:
            r["wir"][r["monate"].index(f"{j}.{m}")] = e.get("merchant_power")
    return {k: {f: v[-n:] for f, v in r.items()} for k, r in out.items()}


def bauliste(s, names=None):
    """Bauprojekte des Landes aus dem Spielstand (roh.bauprojekte, ab Format 4): Gebäude, Ort, Fortschritt
    (progress von total), ob Güter gerade angefordert werden (has_active_demand), fehlende Güter (missing > 0), bisher
    bezahltes Gold. Gebäude ohne Eintrag in roh.gebaeude (Neubau) tragen nur den Bedarfsschlüssel (demand)."""
    roh = s.get("roh") or {}
    geb = roh.get("gebaeude") or {}
    orte = {o.get("id"): o.get("name") for o in s.get("orte", [])}
    out = []
    for pid, b in (roh.get("bauprojekte") or {}).items():
        if not isinstance(b, dict):
            continue
        g = geb.get(str(b.get("building"))) or {}
        typ = g.get("type")
        miss = {k: v for k, v in (b.get("missing") or {}).items() if k != "demand" and isinstance(v, (int, float)) and v > 0}
        out.append({"id": pid, "gebaeude_id": b.get("building"), "typ": typ, "name": (names(typ) if names and typ else typ),
                    "bedarf": b.get("demand"), "stufe": g.get("level"), "ort_id": b.get("location"),
                    "ort": orte.get(b.get("location")), "fortschritt": b.get("progress"), "gesamt": b.get("total"),
                    "aktiv": b.get("has_active_demand") == "yes", "fehlt": miss,
                    "gold": (b.get("actual_currency_spent") or {}).get("gold")})
    return sorted(out, key=lambda x: -(x["fortschritt"] or 0))


def add_mark(db, pid, datum, text):
    jahr(datum)  # prüft das Format
    db.execute("INSERT INTO markierungen (partie_id, datum, text, angelegt) VALUES (?,?,?,?)",
               (pid, datum, text, time.strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()


def delete_mark(db, mid):
    db.execute("DELETE FROM markierungen WHERE id=?", (mid,))
    db.commit()
