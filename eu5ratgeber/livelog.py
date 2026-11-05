"""Monatszeilen des Daten-Mods aus logs/debug.log mitlesen (Echtzeit ohne Speichern).

Der Mod schreibt je Monat (Format in tools/build_mod.py):
    RG1  <TAG> jahr=… monat=… tag=… schluessel=wert …          Land
    RG1L <TAG> <ort-id> schluessel=wert …                        je eigenem Ort
    RG1B <TAG> <gebäude-id> <ort-id> schluessel=wert … typ=<Typname mit Leerzeichen>   je eigenem Gebäude
    RG1M <markt-id> <zentrum-ort-id> schluessel=wert …           je Markt mit eigener Präsenz
    RG1D <beziehung> <TAG> schluessel=wert …                     je verbundenem/benachbartem/Rivalen-/Kriegsland
    RG1F <seite> <heer|flotte> <TAG> <einheit-id> <ort-id> … name=… fuehrer=…   ab 0.19 je Armee/Flotte im Krieg
RG1L/B/M folgen im selben Monatsimpuls auf RG1 und übernehmen Land und Datum von dort.
Ab Mod 0.24 (1.4 kürzt jeden Logeintrag auf 1.024 Byte) kommen lange Zeilen in Stücken: das erste wie bisher, die weiteren
mit „+“ hinter der Zeilenart (RG1+ WAL …, RG1M+ <markt-id> <zentrum> …) – sie ergänzen den Eintrag des ersten Stücks.
Ab 0.9/0.10/0.11 weitere Zeilenarten (POSITIONS/ART unten); RG1I <schlüssel> <Text> trägt Rohtexte der
Oberfläche (Aufschlüsselungen), die über mehrere Logzeilen gehen können.
debug.log wird bei jedem Spielstart neu angelegt - der Leser merkt das an der kleineren Datei
und beginnt wieder vorn. Deshalb sollte der Ratgeber laufen, während gespielt wird.
"""
import base64
import binascii
import hashlib
import os
import re

from . import pfade

LOG = os.path.join(pfade.nutzer(), "logs", "debug.log")
LINE = re.compile(r"\b(RG2|RG1[LBMDSQCWTKXAPRVGEHUNIF]?)(\+?) (.+?)\s*$")
NEW_ENTRY = re.compile(rb"^\[\d\d:\d\d:\d\d\]")    # jede Logzeile beginnt mit der Uhrzeit; sonst Fortsetzung
UHRZEIT = re.compile(rb"^\[(\d\d:\d\d:\d\d)\]")
# Knopf „Im Browser öffnen“ der Seitenleiste im Spiel (Mod 0.28): scripted gui rg_browser schreibt per debug_log diese Zeile
BROWSER = b"RG_BROWSER"
FIELD = re.compile(r"(\w+)=(\S*)")
BUILDING_KEY = re.compile(r"BUILDING_TYPE,(\w+)")   # typ=\x15TOOLTIP:BUILDING_TYPE,temple \x15L; Tempel\x15!\x15!
DECIMALS = 3   # wie LOG_DECIMALS im Mod
# 1.4 (Beta 1.4.4, Test 0.23): jeder Logeintrag endet nach 1.024 Byte ab „common/…txt:<Zeile>: “ (build_mod.LOG_GRENZE).
# Gekürzte Einträge enden mit einem NUL-Zeichen (1.023 Byte + NUL; Test 0.23 und 0.24: alle gekürzten Einträge, sonst keiner).
# Nur daran erkannt – unter 1.3 waren vollständige Zeilen bis ~5 KB lang (Prüfer 27.10.)
GEKUERZT = 1024
POSITIONS = {"RG1": ("tag",), "RG1L": ("tag", "id"), "RG1B": ("tag", "id", "ort"),
             "RG1M": ("id", "zentrum"), "RG1D": ("beziehung", "anderes"),
             # ab Mod 0.9
             "RG1S": ("tag",), "RG1Q": ("tag", "id"), "RG1C": ("rolle", "id"), "RG1W": ("id",),
             "RG1T": ("id", "gut", "von", "nach"), "RG1K": ("id",), "RG1X": ("id",), "RG1A": ("einheit", "id"),
             "RG1P": ("id",),
             # ab Mod 0.10
             "RG1R": ("tag",), "RG1V": (), "RG1G": ("id",),
             # ab Mod 0.11 (Untertan: eigenes Kürzel als "anderes", sonst hielte der Leser es für ein fremdes Land)
             "RG1E": ("tag",), "RG1H": ("id",), "RG1U": ("anderes",), "RG1N": (),
             # ab Mod 0.19: Armeen/Flotten der Kriegsteilnehmer (Seite eigen/verbuendet/feind); Land als "anderes" wie RG1U
             "RG1F": ("seite", "einheit", "anderes", "id", "ort")}
ART = {"RG1": "land", "RG1L": "ort", "RG1B": "gebaeude", "RG1M": "markt", "RG1D": "diplomatie",
       "RG1S": "staende", "RG1Q": "pops", "RG1C": "charakter", "RG1W": "krieg", "RG1T": "handel",
       "RG1K": "kredit", "RG1X": "katastrophe", "RG1A": "einheit", "RG1P": "preise",
       "RG1R": "modifikatoren", "RG1V": "privileg", "RG1G": "kabinett",
       "RG1E": "finanzen", "RG1H": "handel_kosten", "RG1U": "untertan", "RG1N": "stand_einkommen", "RG1I": "text",
       "RG1F": "kriegseinheit"}
# Textfelder am Zeilenende (dürfen Leerzeichen enthalten), in der Reihenfolge der Zeile
TEXT_FIELDS = {"RG1B": ("typ",), "RG1C": ("name",), "RG1W": ("name",), "RG1X": ("name",),
               "RG1V": ("stand", "name"), "RG1G": ("aktion", "person"), "RG1N": ("name",), "RG1F": ("mann", "name", "fuehrer")}
# Zahlen aus Datenfunktionen der Oberfläche können Farbcodes tragen ("V; 97.15%!")
FORMATTED = {"RG1G", "RG1E", "RG1H", "RG1U", "RG1N"}
IDS = {"id", "ort", "zentrum", "von", "nach"}
# Gescheiterte Proben (Test 0.17/0.17.1, 02.–04.10.): ihre Zeilen kommen beim Neu-Einlesen eines alten debug.log wieder –
# deshalb hier verworfen statt nur in der Datenbank gelöscht. Bauwert je Ort/Gebäudetyp (Objekt-Argumente im Log-Text
# leer), Handelsvorteil über gespeicherte Scopes/GetCountry (hv_a, hv_b, handelsvorteil = 0 oder Fehler), leere Texte.
VERWORFEN_ARTEN = {"a.bauwert"}
VERWORFEN_FELDER = {"a.marktvorteil": {"hv_a", "hv_b", "handelsvorteil"}, "a.reichweite": {"hv_a", "hv_b", "handelsvorteil"}}
VERWORFEN_TEXTE = {("bauwert", None), ("gebaeudetyp", "kosten"), ("gebaeudetyp", "GetBuildCostAndTime")}


def verworfen(rec):
    """True, wenn die Zeile aus einer gescheiterten Probe stammt (Felder solcher Proben werden entfernt)."""
    art = rec.get("art")
    if art in VERWORFEN_ARTEN:
        return True
    if art in VERWORFEN_FELDER:
        for k in VERWORFEN_FELDER[art]:
            rec["werte"].pop(k, None)
        return not rec["werte"] and art == "a.marktvorteil" and rec.get("name") is None
    if art == "text":
        return (rec.get("bereich"), None) in VERWORFEN_TEXTE or (rec.get("bereich"), rec.get("feld")) in VERWORFEN_TEXTE
    return False


def num(s):
    """Zahl aus dem Log; Dezimaltrenner ist der Trenner vor den letzten DECIMALS Ziffern."""
    s = s.strip()
    if not s:
        return None
    m = re.search(r"[.,](\d{%d})$" % DECIMALS, s)
    if m:
        whole = re.sub(r"[.,\s]", "", s[:m.start()])
        s = f"{whole}.{m.group(1)}"
    else:
        s = re.sub(r"[,\s]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def ident(s):
    """Kennung (ID) - ganzzahlig, mögliche Tausendertrenner entfernen."""
    t = re.sub(r"[.,\s]", "", s)
    return int(t) if t.isdigit() else s


TOOLTIP = re.compile(r"TOOLTIP:\w+,(\w+)\s*L;\s*(.*)$")


def clean_text(v):
    """Lokalisierter Text aus dem Log -> Anzeigename.
    Formen (Test 0.10): "\\x15TOOLTIP:CHARACTER,16674 \\x15L; Jan Joris de Jong\\x15!\\x15!",
    "TOOLTIP:ESTATE_TYPE,peasants_estate L; peasants_estate! Gemeinenstand!!" -> letzter Abschnitt vor "!"."""
    v = v.replace("\x15", "").strip()
    m = TOOLTIP.search(v)
    if not m:
        return v
    parts = [p.strip() for p in m.group(2).split("!") if p.strip()]
    return parts[-1] if parts else m.group(1)


# Oberflächentexte (RG1I, Test 0.12): \x15<Stil> … \x15! umschließt Abschnitte (Stil "L;", "Y;L;", "positive_value",
# "TOOLTIP:GOODS,fine_cloth" …), \x16<name>! ist ein Symbol. Verschachtelte Tooltips stehen als
# "\x15TOOLTIP:STRINGPAIRLIST,<base64> <sichtbarer Text>\x15!" darin (base64 = wieder so ein Text, beliebig tief).
NESTED = re.compile(r"\x15TOOLTIP:STRINGPAIRLIST,([A-Za-z0-9+/=]*) ?")
TIP_CODE = re.compile(r"\x15TOOLTIP:[A-Z_]+,[^ \x15]* ?")
STYLE_CODE = re.compile(r"\x15[A-Za-z_]+(?:;[A-Za-z_]*)*;? ?")
ICON_CODE = re.compile(r"\x16[^!\s]*!?")
MARK = re.compile(r"\ue000(\d+)\ue001")
FEHLERREST = re.compile(r"\s*\(?ERROR:\[[^\]\s]*\]?\|?\)?")


def decode_text(s, depth=0):
    """Oberflächentext -> lesbarer Text; verschachtelte Tooltips eingerückt unter der Zeile, an der sie hängen."""
    nested = []

    def keep(m):
        nested.append(m.group(1))
        return f"\ue000{len(nested) - 1}\ue001"
    s = NESTED.sub(keep, s)
    s = ICON_CODE.sub("", STYLE_CODE.sub("", TIP_CODE.sub("", s).replace("\x15!", ""))).replace("\xa0", " ")
    out = []
    for line in s.split("\n"):
        refs = [int(i) for i in MARK.findall(line)]
        # Spieltexte mit entfernten Funktionen (Beta 1.4.4: „(ERROR:[PROVINCE.GetArmyLevyPercentage|)“) – Rest entfernen
        line = FEHLERREST.sub("", line)
        line = re.sub(r" {2,}", " ", MARK.sub("", line)).strip()
        if line:
            out.append("  " * depth + line)
        for i in refs:
            try:
                sub = base64.b64decode(nested[i], validate=True).decode("utf-8", "replace")
            except (ValueError, binascii.Error):
                continue
            if depth < 8:
                out.append(decode_text(sub, depth + 1))
    return "\n".join(x for x in out if x)


FORMAT_CODES = re.compile(r"=V;?\s*")   # Farbcodes vor Werten, z. B. "fortschritt=V; 97.15%!" (RG1G, Test 0.10)
VALUE_CODES = re.compile(r"=(?:\x15[^ \x15!]* ?)+")   # Stil-/Tooltip-Codes direkt hinter "="


def parse_line(line):
    """Eine Logzeile -> dict mit art, Positionsfeldern und werte; None, wenn keine RG1-Zeile."""
    m = LINE.search(line)
    if not m:
        return None
    kind, plus, rest = m.group(1), m.group(2), m.group(3)
    if kind == "RG1I":           # "RG1I <art> <id> <feld> <Text>" - Text roh, Fortsetzungszeilen hängt der LogReader an
        parts = rest.split(" ", 3)
        if len(parts) < 3:
            return None
        art, id_, feld = parts[0], ident(parts[1]), parts[2]
        text = parts[3] if len(parts) > 3 else ""
        if id_ == "-" and "¦" in text:   # ab 0.14: Typen ohne Kennung (Gesetz, Privileg …) -> "<Name>¦<Text>"
            name, text = text.split("¦", 1)
            id_ = clean_text(name) or "-"
        return {"art": ART[kind], "schluessel": f"{art}:{id_}:{feld}", "bereich": art, "id": id_, "feld": feld,
                "text": text, "werte": {}}
    if kind == "RG2":            # "RG2 <art> <id> schluessel=wert … [name=<Text>]" (ab Mod 0.12, alle Werte)
        name = None
        if " name=" in rest:
            rest, name = rest.split(" name=", 1)
            name = clean_text(name)
        # formatierte Werte (z. B. Modifikator als Text): "k=\x15G +5.00%\x15!" -> "k=+5.00"
        rest = VALUE_CODES.sub("=", ICON_CODE.sub("", rest))
        rest = re.sub(r"(\d)%", r"\1", FORMAT_CODES.sub("=", rest.replace("\x15", ""))).replace("!", " ")
        tokens = rest.split()
        if len(tokens) < 2 or "=" in tokens[0] or "=" in tokens[1]:
            return None
        art, id_ = tokens[0], tokens[1]
        if ":" in id_:           # "HOL:3" = dritter Teil der Modifikatoren von HOL
            id_ = id_.split(":")[0]
        rec = {"art": "a." + re.sub(r"\d+$", "", art), "id": ident(id_) if id_ != "-" else (name or "-"),
               "werte": {k: (num(v) if num(v) is not None else (v or None)) for k, v in FIELD.findall(" ".join(tokens[2:]))}}
        if name is not None:
            rec["name"] = name
        if plus:
            rec["fortsetzung"] = True
        return rec
    texts = {}
    fields = TEXT_FIELDS.get(kind, ())
    if fields and f" {fields[0]}=" in rest:
        rest, tail = rest.split(f" {fields[0]}=", 1)
        for cur, nxt in zip(fields, (*fields[1:], None)):
            if nxt and f" {nxt}=" in tail:
                texts[cur], tail = tail.split(f" {nxt}=", 1)
            else:
                texts[cur], tail = tail, ""
    typ = texts.pop("typ", None)
    if kind in FORMATTED:        # "fortschritt=V; 97.15%!" / "tage=V -364 Tage!" -> Zahlen
        rest = re.sub(r"(\d)%", r"\1", FORMAT_CODES.sub("=", rest.replace("\x15", ""))).replace("!", " ")
    tokens = rest.split()
    names = POSITIONS[kind]
    if len(tokens) < len(names) or any("=" in t for t in tokens[:len(names)]):
        return None
    rec = {"art": ART[kind]}
    for n, t in zip(names, tokens):
        rec[n] = ident(t) if n in IDS else t
    for k, v in texts.items():
        rec[k] = clean_text(v)
    # Zahl, sonst Text (z. B. Fortschritt "104.34%" aus Cabinet.GetActionProgress)
    rec["werte"] = {k: (num(v) if num(v) is not None else (v or None))
                    for k, v in FIELD.findall(" ".join(tokens[len(names):]))}
    if typ is not None:
        k = BUILDING_KEY.search(typ)
        rec["key"] = k.group(1) if k else typ.strip()
    if plus:
        rec["fortsetzung"] = True    # ab Mod 0.24: weiteres Stück einer langen Zeile
    elif kind == "RG1":
        w = rec["werte"]
        if not all(isinstance(w.get(k), float) for k in ("jahr", "monat", "tag")):
            return None
        rec.update(jahr=int(w.pop("jahr")), monat=int(w.pop("monat")), tagnr=int(w.pop("tag")))
    return rec


# je read_new höchstens so viele Bytes (31.10.: eine debug.log von 709 MB nach 150 Spielmonaten wurde in einem Stück gelesen –
# minutenlang ohne Zwischenstand, ~1 GB Speicher); die Aufrufer lesen weiter, solange LogReader.mehr gilt
MAX_LESEN = 32 * 1024 * 1024
KOPF = 4096          # Kennung der Datei: die ersten Bytes (das Spiel legt debug.log bei jedem Start neu an, mit Uhrzeiten im Kopf)


class LogReader:
    def __init__(self, path=LOG):
        self.path = path
        self.pos = 0
        self.ctx = None      # (tag, jahr, monat, tagnr) der letzten RG1-Zeile
        self.pending = None  # Textzeile (RG1I), die noch Fortsetzungszeilen bekommen kann
        self.letzter = {}    # Land -> letzter Monat (jahr*12+monat) in dieser Datei; rückwärts = älterer Spielstand geladen
        self.mehr = False    # die Datei hat noch ungelesene Bytes (read_new liest höchstens MAX_LESEN)
        self.kopf = None     # Kennung des Dateikopfs beim letzten Lesen (neue debug.log erkennen, auch wenn sie schon größer ist)

    def _neu_angelegt(self):
        """Hat das Spiel debug.log neu angelegt? Der Kopf (erste Bytes mit Uhrzeiten) ist dann ein anderer. Größer als der alte
        Lesestand kann die neue Datei schon sein: im Hintergrund startet der Ratgeber mit dem Spiel (Wächter, 03.11.)."""
        if not self.pos or not self.kopf:
            return False
        return self._kennung(int(self.kopf.split(":", 1)[0])) != self.kopf

    def _kennung(self, n):
        """Kennung der Datei aus ihren ersten n Bytes (sha1) – None, wenn sie fehlt oder kürzer ist."""
        try:
            with open(self.path, "rb") as f:
                kopf = f.read(n)
        except OSError:
            return None
        return f"{n}:{hashlib.sha1(kopf).hexdigest()}" if len(kopf) == n else None

    def zustand(self):
        """Lesestand zum Speichern (history.logstand_speichern), erst nachdem die gelesenen Zeilen gespeichert sind: ein Neustart
        des Ratgebers liest dieselbe debug.log dann ab hier weiter statt von vorn (31.10.)."""
        n = min(self.pos, KOPF)
        return {"kennung": self._kennung(n), "pos": self.pos, "ctx": list(self.ctx) if self.ctx else None,
                "pending": self.pending, "letzter": self.letzter}

    def fortsetzen(self, z):
        """Gespeicherten Lesestand übernehmen, wenn es dieselbe debug.log ist (gleicher Kopf) und sie nicht kürzer wurde -> True;
        sonst bleibt alles beim Lesen von vorn."""
        if not isinstance(z, dict) or not z.get("pos") or not z.get("kennung"):
            return False
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return False
        n = int(str(z["kennung"]).split(":", 1)[0])
        if size < z["pos"] or self._kennung(n) != z["kennung"]:
            return False
        self.pos, self.pending, self.letzter = z["pos"], z.get("pending"), dict(z.get("letzter") or {})
        self.ctx = tuple(z["ctx"]) if z.get("ctx") else None
        self.mehr = size > self.pos
        self.kopf = z["kennung"]
        return True

    def read_new(self):
        """Neue Zeilen seit dem letzten Aufruf; Detailzeilen mit Land und Datum der RG1-Zeile davor.
        Texte (RG1I) können mehrzeilig sein: Zeilen ohne Uhrzeit am Anfang gehören zur Textzeile davor;
        sie wird erst ausgegeben, wenn die nächste Logzeile beginnt."""
        try:
            size = os.path.getsize(self.path)
        except FileNotFoundError:
            return []
        if size < self.pos or self._neu_angelegt():     # neue Datei nach Spielstart
            self.pos, self.ctx, self.pending, self.letzter, self.kopf = 0, None, None, {}, None
        with open(self.path, "rb") as f:
            f.seek(self.pos)
            data = f.read(MAX_LESEN)
        self.mehr = self.pos + len(data) < size
        end = data.rfind(b"\n") + 1  # nur vollständige Zeilen
        self.pos += end
        if self.pos and (self.kopf is None or int(self.kopf.split(":", 1)[0]) < min(self.pos, KOPF)):
            self.kopf = self._kennung(min(self.pos, KOPF))
        out = []
        for raw in data[:end].splitlines():
            if self.pending is not None:
                if not NEW_ENTRY.match(raw):
                    self.pending["text"] += "\n" + raw.decode("utf-8", "replace")
                    continue
                t = self.pending["text"]
                if t.endswith("\x00"):
                    self.pending["gekuerzt"] = True     # 1.4: Text am Ende abgeschnitten
                self.pending["text"] = decode_text(t.rstrip("\x00"))
                out.append(self.pending)
                self.pending = None
            if BROWSER in raw and b"jomini_effect_impl" in raw:
                m = UHRZEIT.match(raw)       # Uhrzeit der Zeile: der Ratgeber reagiert nur auf frische Klicks
                out.append({"art": "browser", "zeit": m.group(1).decode() if m else None})
                continue
            if b"RG1" not in raw and b"RG2" not in raw:
                continue
            # nur Ausgaben des debug_log-Effekts; "Data error in loc string 'RG2 …'" (pdx_data_localize, error.log-Kopie im
            # debug.log) enthält den Rohtext der Zeile und ergab Müll mit Schlüsseln wie "[THIS.GetMarket.GetID]" (Test 0.17.1)
            if b"jomini_effect_impl" not in raw:
                continue
            rec = parse_line(raw.decode("utf-8", "replace"))
            if not rec or verworfen(rec):
                continue
            if raw.endswith(b"\x00") and rec["art"] != "text":
                # gekürzte Zahlenzeile (Mod vor 0.24 unter 1.4): letzter Wert evtl. halb – verwerfen
                if rec["werte"]:
                    rec["werte"].pop(next(reversed(rec["werte"])))
                rec["gekuerzt"] = True
            if rec["art"] == "land" and not rec.get("fortsetzung"):
                self.ctx = (rec["tag"], rec["jahr"], rec["monat"], rec["tagnr"])
                # Datum springt in derselben Datei zurück: Spielstand neu geladen (25.10.) -> spätere Monate verwerfen
                ym = rec["jahr"] * 12 + rec["monat"]
                if ym < self.letzter.get(rec["tag"], ym):
                    out.append({"art": "zeitsprung", "tag": rec["tag"], "ab": ym})
                self.letzter[rec["tag"]] = ym
            elif self.ctx is None:
                continue             # Detailzeile ohne Monatskopf (Datei mitten im Impuls begonnen)
            else:
                tag, j, mo, d = self.ctx
                if "tag" not in rec:
                    rec["tag"] = tag     # Zeilen ohne eigenes Land gehören zum letzten Kopf
                elif rec["tag"] != tag:
                    continue             # gehört zu einem anderen Land als der letzte Kopf
                rec.update(jahr=j, monat=mo, tagnr=d)
            if rec["art"] == "text":
                self.pending = rec
            else:
                out.append(rec)
        return out
