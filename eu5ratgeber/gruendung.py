"""Kachel Ländergründung (Nutzerwunsch 30.10.): welche größeren Länder wir gründen können und wie wir am besten vorgehen –
Wirtschaft, Militär, Diplomatie, Staat; mit Auswahl, wenn es mehrere Gründungen gibt (z. B. Brandenburg -> Preußen -> Deutschland).

Quellen:
- Spieldateien in_game/common/formable_countries (163 mit DLC „Across the Pillars“) samt readme.txt: level („Players can only form
  countries of higher level“), required_locations_fraction (Standard 1,0), capital_required (Standard nein), potential_requires_own
  (Standard ja: ohne eigenen Ort in den geforderten Gebieten zeigt das Spiel die Gründung nicht), rule (historical/plausible/
  fantasy), potential (Knopf sichtbar), allow (Knopf klickbar), form_effect, geforderte continents/sub_continents/regions/areas/
  provinces/locations. Kartenhierarchie aus in_game/map_data/definitions.txt (wissen._hierarchy).
- Spielregel „Gründbare Länder“ (main_menu/common/game_rules: no_ahistorical_formable_countries = nur historical,
  allow_plausible_… = auch plausible, allow_ahistorical_… = alle): aktive Einstellung im Spielstand unter game_rules.setting.
- Spielstand (ab Format 17, Feld „gruendung“ der Momentaufnahme): Fakten für die Bedingungen und die Besitzer der Orte in den
  geforderten Gebieten – nur für Gründungen, deren potential für uns nicht sicher falsch ist, und die danach möglichen (Kette).
  Ältere Momentaufnahmen: Fakten aus roh (ohne geduldete Kulturen und Verbündete), Besitzer unbekannt.
- Daten-Mod (neuester Monat): Stände-Macht (power_<stand>), Grad (Trigger formable_level, Text „gründbarer Grad“), im Krieg
  (dip_IsAtWar), Bürgerkrieg (IsInCivilWar); ab 0.25 je Gründung, die das Spiel uns zeigt (is_formable_visible), der
  Gebietsfortschritt laut Spiel (location_progress_for_formable: Anteil an den nötigen Orten, 0–1 – Test 31.10.: Walachei 0,687
  = 44 von 64, wie im Reiter „Gründbare“). Die Probetexte von 0.25 (Anforderungen, Orte, Wirkung) brauchen ein Land; seit 0.25.1
  gestrichen.

Grad (30.10., Nutzerfrage nach den fehlenden Kosten): NICHT der Rang. Der Daten-Mod schreibt formable_level schon seit 0.12 (land,
fremd): Walachei 0 bei Rang Herzogtum (2), Bulgarien 1 bei Großreich, Ungarn 3, England 2. Bei 14 von 16 Ländern mit Werten ist er
die Stufe der Gründung mit dem eigenen Kürzel (BUL_f 1, HUN_f 3, ENG_f 2 …), sonst 0; Ashikaga und Yuan haben 4 bei Gründung 3 (vom
Spiel gesetzt, in keiner Spieldatei). Daher: Grad = Daten-Mod, sonst die Stufe der eigenen Gründung, sonst 0 (Regel des Ratgebers).

Annahmen (offen, auf der Seite genannt):
- Gezählt werden nur besitzbare Orte: Meereszonen, Seen, unpassierbare Berge und non_ownable (in_game/map_data/default.map) nicht.
- Der geforderte Anteil gilt für alle geforderten Orte zusammen; Orte unserer Klientelländer zählen nicht mit.
- NOT = { A B }: das Spiel dokumentiert nur „negates content of trigger“. Stimmen „keins davon“ und „nicht alle zugleich“ überein,
  gilt das Ergebnis, sonst „?“.
"""
import glob
import json
import math
import os
import re

from . import gamedata, wiki, wissen
from . import sprache

# Spielregel „Gründbare Länder“ -> höchste erlaubte rule-Stufe der Gründungen
REGEL_STUFE = {"historical": 0, "plausible": 1, "fantasy": 2}
REGEL_EINSTELLUNG = {"no_ahistorical_formable_countries": 0, "allow_plausible_ahistorical_formable_countries": 1,
                     "allow_ahistorical_formable_countries": 2}
REGEL_NAME = {"historical": "historisch", "plausible": "plausibel", "fantasy": "ahistorisch"}
# geforderte Gebiete: Feld der Spieldatei -> Ebene der Kartenhierarchie, Anzeige, Spielbegriff (Wiki)
EBENEN = (("continents", "kontinent", "Kontinent", "continent"), ("sub_continents", "subkontinent", "Subkontinent", "sub_continent"),
          ("regions", "region", "Region", "region"), ("areas", "gebiet", "Gebiet", "area"),
          ("provinces", "provinz", "Provinz", "province"), ("locations", None, "Ort", "location"))
VERGLEICH = {"<": "weniger als", ">": "mehr als", "<=": "höchstens", ">=": "mindestens", "=": "genau", "!=": "nicht"}
ROEMISCH = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}
# Regel des Ratgebers: „fast gründbar“, wenn höchstens so viele Orte fehlen und alle bekannten Bedingungen erfüllt sind
FAST_ORTE = 3
# Regel des Ratgebers: Verteidigungsbündnis mindestens so viel stärker als das Land allein -> „erst isolieren“
BUENDNIS_FAKTOR = 1.5
AMPEL_RANG = {"gruen": 0, "gelb": 1, "rot": 2, "grau": 3}
# Reihenfolge der Länder für Militär und Vorschlag (Regel des Ratgebers): Länder ohne Mod-Werte vor „rot“
MIL_RANG = {"gruen": 0, "gelb": 1, None: 2, "grau": 2, "rot": 3}

_DATEIEN = {}
_KARTE = {}


def _de(v, d=2):
    return sprache.ziffern(f"{v:,.{d}f}")


def _pz(v, d=0):
    return _de(v * 100, d) + " %"


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _spieldateien(ordner):
    """common-Ordner direkt aus den Spieldateien (Einlesen eines Spielstands: dort gibt es kein vollständiges Spielwissen)."""
    if ordner not in _DATEIEN:
        _DATEIEN[ordner] = gamedata.load_defs(ordner)
    return _DATEIEN[ordner]


_DLC = {}


def _dlc_name(key):
    """Anzeigename eines DLC: game/dlc/<ordner>/<name>.dlc.json nennt localizable_name, der Text steht in
    dlc/D000_shared/main_menu/localization/dlc/german (z. B. d008_fate_of_the_phoenix -> „Fate of the Phoenix“)."""
    if not _DLC:
        loc = {}
        for fn in glob.glob(os.path.join(glob.escape(gamedata.GAME_DIR), "dlc", "*", "**", sprache.ORDNER, "*.yml"), recursive=True):
            with open(fn, encoding="utf-8-sig", errors="replace") as f:
                for line in f:
                    m = gamedata.LOC_LINE.match(line)
                    if m:
                        loc[m.group(1)] = m.group(2)
        for fn in glob.glob(os.path.join(glob.escape(gamedata.GAME_DIR), "dlc", "*", "*.dlc.json")):
            try:
                j = json.load(open(fn, encoding="utf-8-sig"))
            except (OSError, ValueError):
                continue
            t = gamedata.clean_loc(loc.get(j.get("localizable_name") or ""), loc)
            if j.get("name") and t:
                _DLC[j["name"]] = t
        _DLC.setdefault("", "")
    return _DLC.get(str(key))


def _karte():
    """Kartenhierarchie und besitzbare Orte: {ebene: {schlüssel: [orte]}} und Menge der nicht besitzbaren Orte (default.map)."""
    if not _KARTE:
        m = wissen._parse_file(os.path.join(wissen.GAME, "in_game", "map_data", "default.map"))
        aus = set()
        for k in ("sea_zones", "lakes", "impassable_mountains", "non_ownable"):
            aus.update(x for x in (m.get(k) or []) if isinstance(x, str))
        hier = wissen._hierarchy()
        index = {e: {} for _, e, _, _ in EBENEN if e}
        for ort, h in hier.items():
            if ort in aus:
                continue
            for e in index:
                if h.get(e):
                    index[e].setdefault(h[e], []).append(ort)
        _KARTE.update(hier=hier, aus=aus, index=index)
    return _KARTE


class Wissen:
    """Spielwissen für die Gründungen. quelle: Funktion ordner -> {schlüssel: {name, beschreibung, def}} (vollständiges Spielwissen,
    Server) oder None (Spieldateien, beim Einlesen eines Spielstands)."""

    def __init__(self, quelle=None):
        self.quelle = quelle
        self._roh, self._defs = {}, {}

    def roh(self, ordner):
        if ordner not in self._roh:
            if self.quelle:
                self._roh[ordner] = self.quelle(ordner) or {}
            else:
                self._roh[ordner] = {k: {"name": None, "def": v} for k, v in _spieldateien(ordner).items()}
        return self._roh[ordner]

    def defs(self, ordner):
        if ordner not in self._defs:
            self._defs[ordner] = {k: e.get("def") for k, e in self.roh(ordner).items() if isinstance(e, dict)}
        return self._defs[ordner]

    def gibt(self, ordner, key):
        return key in self.roh(ordner)

    def rang_stufe(self, rang):
        d = self.defs("country_ranks").get(rang)
        return d.get("level") if isinstance(d, dict) and _num(d.get("level")) else None

    def grad(self, tag):
        """Grad eines Landes ohne Daten-Mod: Stufe der Gründung mit diesem Kürzel, sonst 0 (passt bei 14 von 16 Ländern mit
        formable_level im Daten-Mod, 30.10.)."""
        lv = [d.get("level") for d in self.defs("formable_countries").values()
              if isinstance(d, dict) and tag and d.get("tag") == tag and _num(d.get("level"))]
        return max(lv) if lv else 0

    def kultur(self, k):
        d = self.defs("cultures").get(k)
        return d if isinstance(d, dict) else {}

    def sprache(self, k):
        """Sprache einer Kultur: (Sprache, Dialekt) – das Feld language der Kultur kann ein Dialekt sein (preußisch:
        low_german_dialect); Dialekte stehen in languages unter dialects."""
        x = self.kultur(k).get("language")
        if not isinstance(x, str):
            return None, None
        if x in self.defs("languages"):
            return x, None
        for lk, ld in self.defs("languages").items():
            if isinstance(ld, dict) and isinstance(ld.get("dialects"), dict) and x in ld["dialects"]:
                return lk, x
        return None, x

    def religionsgruppe(self, r):
        d = self.defs("religions").get(r)
        return d.get("group") if isinstance(d, dict) else None


def _ohne(s, praefix):
    """'culture_group:german_group' -> 'german_group'."""
    s = str(s)
    return s.split(":", 1)[1] if s.startswith(praefix + ":") else s


def _zeitalter_nr(k):
    m = re.match(r"age_(\d+)", str(k or ""))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- Fakten
def fakten_momentaufnahme(snap):
    """Fakten für die Bedingungen aus einer Momentaufnahme (auch Format 16: roh.land, roh.kulturen …). Nicht darin: geduldete
    Kulturen (nur Kennungen), Verbündete, Organisationen der Welt, Spielregel – die liefert erst das Feld gruendung (Format 17)."""
    roh = snap.get("roh") or {}
    L = roh.get("land") or {}
    meta = snap.get("meta") or {}
    rh = L.get("country_rank_history") or []
    rang = next((x.get("country_rank") for x in reversed(rh if isinstance(rh, list) else [rh]) if isinstance(x, dict)), None)
    kult = {str(k): (v or {}).get("culture_definition") for k, v in (roh.get("kulturen") or {}).items() if isinstance(v, dict)}
    prim = kult.get(str(L.get("primary_culture")))
    akz = [kult.get(str(i)) for i in (L.get("accepted_cultures") or []) if isinstance(i, int)]
    tol_ids = [i for i in (L.get("tolerated_cultures") or []) if isinstance(i, int)]
    rel = roh.get("religion") or {}
    orgs = [o for o in (roh.get("organisationen") or {}).values() if isinstance(o, dict)]
    adv = L.get("researched_advances")
    return {
        "tag": meta.get("tag"), "tag_original": L.get("original_tag") or meta.get("tag"), "rang": rang,
        "kultur": prim, "kulturen_akzeptiert": [k for k in akz if k], "kulturen_geduldet": None if tol_ids else [],
        "religion": rel.get("key") or rel.get("definition"), "religionsgruppe": rel.get("group"),
        "regierungsform": meta.get("regierungsform"), "reformen": [r for r in (snap.get("reformen") or []) if isinstance(r, str)],
        "privilegien": [p for p in (snap.get("privilegien") or []) if isinstance(p, str)],
        "hauptstadt": next((o.get("key") for o in snap.get("orte") or [] if o.get("hauptstadt")), None),
        "orte": sorted(o["key"] for o in snap.get("orte") or [] if o.get("key")),
        "krieg": bool(snap.get("kriege")) if "kriege" in snap else None, "buergerkrieg": None,
        "untertanen": sorted(u["tag"] for u in snap.get("untertanen") or [] if u.get("tag")),
        "oberherr": None, "untertan": None, "verbuendete": None,
        "io": sorted({o.get("type") for o in orgs if o.get("type")}),
        "io_leiter": sorted({o.get("type") for o in orgs if o.get("type") and o.get("leader") == meta.get("land_id")}),
        "io_welt": None,
        "zeitalter": meta.get("zeitalter"), "jahr": int(str(meta.get("datum", "0")).split(".")[0] or 0) or None,
        "fortschritte": sorted(k for k, v in adv.items() if v == "yes") if isinstance(adv, dict)
        else sorted(a.get("key") for a in (snap.get("forschung") or {}).get("fortschritte") or [] if a.get("key")),
        "hofsprache": L.get("court_language"),
        "lebende": sorted({x["tag"] for x in snap.get("laender_militaer") or [] if x.get("tag")}) or None,
        "stand_macht": {e["stand"]: (e.get("mod") or {}).get("power") for e in snap.get("staende") or []
                        if _num((e.get("mod") or {}).get("power"))},
        "stand_macht_quelle": "Spielstand (Variablen des Daten-Mods)",
        "regel": None,
    }


_OWNER = re.compile(rb"\n(\t*)owner=(\d+)")


def _besitzer(raw):
    """Besitzer eines Orts aus dem Rohtext: das flachste owner= (tiefere Blöcke können eigene owner-Felder haben)."""
    best = None
    for m in _OWNER.finditer(raw or b""):
        if best is None or len(m.group(1)) < len(best[0]):
            best = (m.group(1), int(m.group(2)))
    return best[1] if best else None


def spielstand(save, c, cid, tags, locnames, snap, W=None):
    """Feld „gruendung“ der Momentaufnahme (Format 17): Fakten, die nur der Spielstand kennt (zusatz – der Rest steht schon in der
    Momentaufnahme), die Gründungen, die für uns infrage kommen, samt Kette (kandidaten), und die fremden Besitzer der Orte in deren
    geforderten Gebieten (besitz: {Kürzel: [Orte]}). Nur diese Orte – so bleibt die Datenbank klein (Walachei 1338.4: 3 Gebiete,
    83 fremde Orte, 6,5 KB gepackt je Momentaufnahme)."""
    W = W or Wissen()
    F = fakten_momentaufnahme(snap)
    Z = {"kulturen_geduldet": [k for k in ((save.entry("culture_manager/database", i) or {}).get("culture_definition")
                                           for i in c.get("tolerated_cultures") or [] if isinstance(i, int)) if k]}
    # Verbündete und Oberherr aus den Beziehungen (roh.beziehungen: scripted_mutual mit relation_type alliance; dependency)
    verb, ober = set(), None
    for r in (snap.get("roh") or {}).get("beziehungen") or []:
        objs = {(x.get("target") or {}).get("object") for x in r.get("named_targets") or [] if isinstance(x, dict)}
        anderes = r.get("second") if r.get("first") == cid else r.get("first")
        if r.get("art") == "scripted_mutual" and "alliance" in objs and tags.get(anderes):
            verb.add(tags[anderes])
        if r.get("art") == "dependency" and r.get("second") == cid and tags.get(r.get("first")):
            ober = tags[r["first"]]
    Z["verbuendete"], Z["oberherr"], Z["untertan"] = sorted(verb), ober, ober is not None
    welt = set()
    for _, raw in save.raw_entries("international_organization_manager/database"):
        m = sorted(re.findall(rb"\n(\t*)type=(\w+)", raw), key=lambda x: len(x[0]))
        if m:
            welt.add(m[0][1].decode())
    Z["io_welt"] = sorted(welt)
    if "game_rules" in save.blocks:
        st = (save.block("game_rules") or {}).get("setting") or []
        Z["regel"] = next((x for x in st if x in REGEL_EINSTELLUNG), None)
    F.update(Z)
    kand = kandidaten(W, F)
    R = set()
    for k in kand:
        R |= set(benoetigt(W.defs("formable_countries").get(k) or {})[1])
    eigene = set(F["orte"])
    pos = {k: i + 1 for i, k in enumerate(locnames)}          # Orts-ID n = Index n-1 (snapshot.loc_key)
    besitz = {}
    for ort in sorted(R - eigene):
        lid = pos.get(ort)
        o = _besitzer(save.raw_entry("locations/locations", lid)) if lid else None
        if o is not None and o != cid and tags.get(o):
            besitz.setdefault(tags[o], []).append(ort)
    return {"zusatz": Z, "kandidaten": sorted(kand), "besitz": besitz}


# ---------------------------------------------------------------- Bedingungen
def _paare(b):
    """Kinder eines Blocks als (Schlüssel, Wert); wiederholte Schlüssel (Liste) einzeln."""
    if not isinstance(b, dict):
        return []
    out = []
    for k, v in b.items():
        if k == "_items":
            continue
        for x in (v if isinstance(v, list) else [v]):
            out.append((k, x))
    return out


def _und(w):
    return False if any(x is False for x in w) else None if any(x is None for x in w) else True


def _oder(w):
    return True if any(x is True for x in w) else None if any(x is None for x in w) else False


def _nicht(x):
    return None if x is None else not x


def _jn(v):
    return {"yes": True, "no": False}.get(str(v).lower())


class Pruefer:
    """Wertet Bedingungen (potential, allow, limit) mit den Fakten aus: je Knoten Text (deutsch), ok (True/False/None = unbekannt),
    Kinder, Wiki-Verweis und – wenn nicht erfüllt – die Handlung samt Bereich (staat, militaer, diplomatie)."""

    def __init__(self, W, F, names=None):
        self.W, self.F, self.nm = W, F, names or (lambda k: k)

    # Namen
    def n(self, k):
        return self.nm(str(k))

    def wiki_begriff(self, k):
        return f"wiki/{k}" if self.W.gibt("game_concepts", k) else None

    def wiki_ordner(self, ordner, k):
        # nur Ordner, die das Wiki führt (wiki.im_wiki) – Gründungen und Kulturgruppen stehen nicht darin (Prüfer 30.10.)
        return f"wiki/{ordner}/{k}" if self.W.gibt(ordner, k) and wiki.im_wiki(ordner) else None

    def gruppe_adj(self, g):
        n = self.n(g)
        return (n[:1].lower() + n[1:] + "en") if n and n != g else "geforderten"

    # Knoten
    @staticmethod
    def k(text, ok, **x):
        return {"text": text, "ok": ok, **{a: b for a, b in x.items() if b not in (None, [], "")}}

    def block(self, b, scope=("land",), neg=False):
        """Kinder eines Blocks (UND), ausgewertet. Ein einzelnes trigger_if mit trigger_else_if/trigger_else im selben Block ist
        eine Fallkette (nur der erste zutreffende Zweig gilt); mehrere trigger_if ohne sonst stehen je für sich."""
        kette = isinstance(b, dict) and isinstance(b.get("trigger_if"), dict) and ("trigger_else_if" in b or "trigger_else" in b)
        out = []
        for k, v in _paare(b):
            if kette and k in ("trigger_else_if", "trigger_else"):
                continue
            if kette and k == "trigger_if":
                out.append(self._kette(b, scope, neg))
                continue
            out.append(self.knoten(k, v, scope, neg))
        return out

    def knoten(self, key, val, scope=("land",), neg=False):
        F, n = self.F, self.n
        key = str(key)
        if key.endswith("?="):                     # null-sicherer Vergleich wie „=“
            key = key[:-2]
        # Logik
        if key in ("AND", "OR", "NOT", "not", "NOR", "NAND"):
            sub_neg = neg != (key in ("NOT", "not", "NOR", "NAND"))
            kinder = self.block(val, scope, sub_neg)
            w = [x["ok"] for x in kinder]
            if key == "AND":
                return self.k("Alle folgenden:", _und(w), kinder=kinder, art="und") if len(kinder) > 1 else (kinder[0] if kinder else self.k("–", True))
            if key == "OR":
                return self.k("Mindestens eines der folgenden Dinge muss zutreffen:", _oder(w), kinder=kinder, art="oder")
            if key == "NOR":
                return self.k("Keines der folgenden darf zutreffen:", _nicht(_oder(w)), kinder=kinder, art="nicht")
            if key == "NAND":
                return self.k("Nicht alle der folgenden zugleich:", _nicht(_und(w)), kinder=kinder, art="nicht")
            if len(kinder) == 1:
                return self.k("Darf nicht zutreffen:", _nicht(w[0]), kinder=kinder, art="nicht")
            nor, nand = _nicht(_oder(w)), _nicht(_und(w))
            return self.k("Darf nicht zutreffen (NICHT mit mehreren Bedingungen):", nor if nor == nand else None, kinder=kinder,
                          art="nicht", hinweis=None if nor == nand else
                          "Ob das Spiel hier „keins davon“ oder „nicht alle zugleich“ meint, ist nicht belegt – deshalb offen.")
        if key in ("trigger_if", "trigger_else_if", "trigger_else"):
            return self._wenn(key, val, scope, neg)
        if key == "custom_tooltip":
            return self._tooltip(val, scope, neg)
        if key == "always":
            j = _jn(val)
            return self.k("Immer" if j else "Nie (Sonderregel des Spiels)", j)
        # Bereiche (Scope-Wechsel)
        if key in ("culture", "any_primary_or_accepted_or_tolerated_culture") and isinstance(val, dict):
            return self._kultur(key, val, neg)
        if key.startswith("c:") and isinstance(val, dict):
            return self._fremd(key[2:], val, neg)
        if key == "any_owned_location" and isinstance(val, dict):
            return self._eigene_orte(val, neg)
        if scope[0] == "kultur":
            return self._kultur_atom(key, val, scope[1], neg)
        if scope[0] == "fremd":
            return self._fremd_atom(key, val, scope[1], neg)
        if scope[0] == "ort":
            return self._ort_atom(key, val, scope[1])
        return self._land_atom(key, val, neg)

    def _zweig(self, val, scope, neg):
        """(Vorbedingung erfüllt?, Knoten Vorbedingung, Knoten Inhalt) eines trigger_if/else-Zweigs."""
        val = val if isinstance(val, dict) else {}
        lim = self.block(val.get("limit"), scope) if "limit" in val else []
        kinder = self.block({k: v for k, v in val.items() if k != "limit"}, scope, neg)
        bed = _und([x["ok"] for x in lim]) if lim else True
        return bed, self.k("Vorbedingung:", bed, kinder=lim, art="vorbedingung"), self.k("dann gilt:", _und([x["ok"] for x in kinder]),
                                                                              kinder=kinder, art="und")

    def _wenn(self, key, val, scope, neg):
        """Einzelnes trigger_if (ohne sonst): trifft die Vorbedingung nicht zu, entfällt die Bedingung."""
        bed, vk, ik = self._zweig(val, scope, neg)
        if key == "trigger_else":                  # ohne trigger_if im selben Block (kommt nicht vor): Inhalt gilt
            return self.k("Sonst:", ik["ok"], kinder=ik.get("kinder"), art="und")
        ok = ik["ok"] if bed is True else True if bed is False else None
        return self.k("Wenn die Vorbedingung zutrifft:", ok, kinder=[vk, ik], art="wenn",
                      hinweis="Vorbedingung trifft nicht zu – entfällt" if bed is False else None)

    def _kette(self, b, scope, neg):
        """Fallkette trigger_if / trigger_else_if … / trigger_else: der erste Zweig mit zutreffender Vorbedingung gilt."""
        zweige = [b["trigger_if"]] + [x for x in (b.get("trigger_else_if") if isinstance(b.get("trigger_else_if"), list)
                                                  else [b["trigger_else_if"]] if "trigger_else_if" in b else [])]
        kinder, ok, fertig = [], None, False
        for z in zweige:
            bed, vk, ik = self._zweig(z, scope, neg)
            kinder.append(self.k("Fall:", ik["ok"] if bed is True else None if bed is None else True, kinder=[vk, ik], art="wenn",
                                 hinweis="trifft nicht zu" if bed is False else "dieser Fall gilt" if bed is True else None))
            if not fertig:
                if bed is True:
                    ok, fertig = ik["ok"], True
                elif bed is None:
                    ok, fertig = None, True
        if "trigger_else" in b:
            kk = self.block(b["trigger_else"], scope, neg)
            inhalt = _und([x["ok"] for x in kk])
            kinder.append(self.k("Sonst:", inhalt, kinder=kk, art="und", hinweis="entfällt" if fertig else "dieser Fall gilt",
                                 entfaellt=True if fertig else None))
            if not fertig:
                ok, fertig = inhalt, True
        return self.k("Je nach Fall:", ok if fertig else True, kinder=kinder, art="kette")

    def _tooltip(self, val, scope, neg):
        """custom_tooltip: der Spieltext steht für die Bedingung; always = no darin = auf diesem Weg nie erfüllt."""
        val = val if isinstance(val, dict) else {}
        txt = self._loc_text(val.get("text"))
        nie = _jn(val.get("always")) is False
        kinder = self.block({k: v for k, v in val.items() if k not in ("text", "always")}, scope, neg)
        ok = False if nie else _und([x["ok"] for x in kinder]) if kinder else None
        return self.k(txt or "Sonderbedingung des Spiels (Text nicht auflösbar)", ok, kinder=kinder, art="und",
                      hinweis="laut Spieldatei auf diesem Weg nie erfüllt – nur über den Weg im Spieltext" if nie else None)

    def _loc_text(self, key):
        loc = getattr(self.nm, "loc", None)
        t = loc.get(str(key)) if loc else None
        if not t:
            return None
        # [GetCountry('ENG').GetNameWithFlag] -> Ländername, [GetUniqueInternationalOrganization('hre').GetName] -> Name
        t = re.sub(r"\[GetCountry\('(\w+)'\)\.\w+(?:\|\w*)?\]", lambda m: self.n(m.group(1)), t)
        t = re.sub(r"\[GetUniqueInternationalOrganization\('(\w+)'\)\.\w+(?:\|\w*)?\]", lambda m: self.n(m.group(1)), t)
        return gamedata.clean_loc(t, loc)

    # Kultur
    def _kulturen(self, alle):
        F = self.F
        ks = [F.get("kultur")] + ((F.get("kulturen_akzeptiert") or []) + (F.get("kulturen_geduldet") or []) if alle else [])
        return [k for k in ks if k], alle and F.get("kulturen_geduldet") is None

    def _kultur(self, key, val, neg):
        alle = key != "culture"
        ks, unvollst = self._kulturen(alle)
        je = [(k, self.block(val, ("kultur", k), neg)) for k in ks]
        ws = [_und([x["ok"] for x in kinder]) for _, kinder in je]
        ok = _oder(ws) if ws else None
        if ok is False and unvollst:
            ok = None
        vorlage = je[0][1] if je else self.block(val, ("kultur", None), neg)
        wer = "Primärkultur" if not alle else "Primär-, akzeptierte oder geduldete Kultur"
        if len(vorlage) == 1 and not vorlage[0].get("kinder"):
            x = vorlage[0]
            text = f"{wer}: {x['text']}"
            ist = ", ".join(f"{self.n(k)}: {'ja' if w else 'nein' if w is False else '?'}" for k, w in zip(ks, ws))
            return self.k(text, ok, ist=ist, wiki=x.get("wiki"), handlung=f"Kultur-Bedingung erfüllen: {text}", bereich="staat",
                          hinweis="geduldete Kulturen nicht im Spielstand-Auszug" if unvollst else None)
        return self.k(f"{wer} erfüllt:", ok, kinder=vorlage, art="und")

    def _kultur_atom(self, key, val, kultur, neg):
        W, n = self.W, self.n
        kd = W.kultur(kultur) if kultur else {}
        if key == "has_culture_group":
            g = _ohne(val, "culture_group")
            ok = (g in (kd.get("culture_groups") or [])) if kd else None
            return self.k(f"gehört zur {self.gruppe_adj(g)} Kulturgruppe", ok, wiki=self.wiki_ordner("culture_groups", g)
                          or self.wiki_begriff("culture_group"))
        if key in ("language", "culture.language"):
            s = _ohne(val, "language")
            spr, _ = W.sprache(kultur) if kultur else (None, None)
            return self.k(f"Sprache ist {n(s)}", (spr == s) if spr else None)
        if key in ("dialect", "culture.dialect"):
            s = _ohne(val, "dialect")
            spr, dia = W.sprache(kultur) if kultur else (None, None)
            return self.k(f"Dialekt ist {n(s)}", (dia == s) if (spr or dia) else None)
        if key == "this" or key == "culture":
            c = _ohne(val, "culture")
            return self.k(f"ist {n(c)}", (kultur == c) if kultur else None)
        return self._skript_oder_unbekannt(key, val, ("kultur", kultur), neg)

    # anderes Land (c:XXX = { … })
    def _fremd(self, tag, val, neg):
        kinder = self.block(val, ("fremd", tag), neg)
        return self.k(f"{self.n(tag)}:", _und([x["ok"] for x in kinder]), kinder=kinder, art="und")

    def _fremd_atom(self, key, val, tag, neg):
        F, n = self.F, self.n
        if key in ("is_subject_or_below_of", "is_subject_of") and str(val).lower() == "root":
            ok = True if tag in (F.get("untertanen") or []) else None
            return self.k(f"ist unser Klientelland{' (oder darunter)' if key == 'is_subject_or_below_of' else ''}", ok,
                          wiki=self.wiki_begriff("subject"), handlung=f"{n(tag)} zum Klientelland machen oder vernichten",
                          bereich="diplomatie")
        if key == "in_union_with" and str(val).lower() == "root":
            return self.k("ist in einer Union mit uns", None, wiki=self.wiki_begriff("union"))
        if key == "has_presence_in":
            return self.k(f"ist in {n(_ohne(val, 'region'))} vertreten", None)
        return self._skript_oder_unbekannt(key, val, ("fremd", tag), neg)

    # eigene Orte (any_owned_location = { … })
    def _eigene_orte(self, val, neg):
        orte = self.F.get("orte") or []
        je = [_und([x["ok"] for x in self.block(val, ("ort", o))]) for o in orte]
        vorlage = self.block(val, ("ort", None))
        ok = _oder(je) if orte else False
        return self.k("Mindestens ein eigener Ort:", ok, kinder=vorlage, art="und")

    def _ort_atom(self, key, val, ort):
        h = (_karte()["hier"].get(ort) or {}) if ort else {}
        art = {"region": "region", "area": "gebiet", "province": "provinz", "continent": "kontinent",
               "sub_continent": "subkontinent"}.get(key)
        if art:
            z = _ohne(_ohne(val, "province_definition"), key)
            return self.k(f"liegt in {self.n(z)}", (h.get(art) == z) if ort else None)
        return self.k("weitere Ortsbedingung der Spieldatei (vom Ratgeber nicht ausgewertet)", None)

    # eigenes Land
    def _land_atom(self, key, val, neg):
        F, W, n = self.F, self.W, self.n
        v = str(val)
        if key == "owns":
            o = _ohne(v, "location")
            ok = o in set(F.get("orte") or [])
            return self.k(f"Besitzt {n(o)}", ok, wiki=self.wiki_begriff("location"), ort=o,
                          handlung=(f"{n(o)} erobern oder erwerben" if not neg else f"{n(o)} abgeben"), bereich="militaer")
        if key in ("culture", "culture.language", "culture.dialect"):
            x = self._kultur_atom({"culture": "this"}.get(key, key), val, F.get("kultur"), neg)
            return self.k(f"Primärkultur: {x['text']}", x["ok"], ist=n(F["kultur"]) if F.get("kultur") else None,
                          handlung=f"Kultur-Bedingung erfüllen: Primärkultur {x['text']}", bereich="staat")
        if key == "at_war":
            j = _jn(v)
            k = F.get("krieg")
            ok = None if k is None else (k == j)
            return self.k("Ist im Krieg" if j else "Hat Frieden", ok, wiki=self.wiki_begriff("war" if j else "peace"),
                          ist=None if k is None else ("im Krieg" if k else "kein Krieg"),
                          handlung="Laufende Kriege beenden (Frieden schließen)" if not j else None, bereich="staat")
        if key == "in_civil_war":
            j = _jn(v)
            k = F.get("buergerkrieg")
            return self.k("Ist in einem Bürgerkrieg" if j else "Ist NICHT in einem Bürgerkrieg", None if k is None else (k == j),
                          wiki=self.wiki_begriff("civil_war"))
        if key == "has_estate_privilege":
            p = _ohne(v, "estate_privilege")
            stand = (W.defs("estate_privileges").get(p) or {}).get("estate") if isinstance(W.defs("estate_privileges").get(p), dict) else None
            ok = p in set(F.get("privilegien") or [])
            st = f" ({n(stand)})" if stand else ""
            return self.k(f"Hat das Privileg „{n(p)}“{st}", ok, wiki=self.wiki_ordner("estate_privileges", p) or self.wiki_begriff("estate_privilege"),
                          handlung=f"Privileg „{n(p)}“{st} gewähren" if not neg else f"Privileg „{n(p)}“{st} entziehen", bereich="staat")
        if key == "has_reform":
            r = _ohne(v, "government_reform")
            ok = r in set(F.get("reformen") or [])
            return self.k(f"Hat die Regierungsreform „{n(r)}“", ok,
                          wiki=self.wiki_ordner("government_reforms", r) or self.wiki_begriff("government_reform"),
                          handlung=f"Regierungsreform „{n(r)}“ einführen" if not neg else f"Regierungsreform „{n(r)}“ abschaffen",
                          bereich="staat")
        m = re.match(r"estate_power\(estate_type:(\w+)\)(<=|>=|<|>|=)?$", key)
        if m:
            e, op = m.group(1), m.group(2) or "="
            ist = (F.get("stand_macht") or {}).get(e)
            ok = None
            if _num(ist) and _num(val):
                ok = {"<": ist < val, ">": ist > val, "<=": ist <= val, ">=": ist >= val, "=": ist == val}[op]
            ziel = {"<": "unter", "<=": "auf höchstens", ">": "über", ">=": "auf mindestens", "=": "auf"}[op]
            if neg:
                ziel = {"<": "auf mindestens", "<=": "über", ">": "auf höchstens", ">=": "unter", "=": "weg von"}[op]
            return self.k(f"Unser {n(e)} hat {VERGLEICH[op]} {_pz(val, 0) if _num(val) else val} Standes-Macht", ok,
                          ist=_pz(ist, 1) if _num(ist) else None, wiki=self.wiki_begriff("estate_power"),
                          handlung=f"Macht des {n(e)}s {ziel} {_pz(val, 0) if _num(val) else val} bringen"
                          + (f" (jetzt {_pz(ist, 1)})" if _num(ist) else ""), bereich="staat")
        if key in ("religion", "religion.group", "religion.group!="):
            gruppe = key != "religion"
            z = _ohne(_ohne(v, "religion_group"), "religion")
            ist = F.get("religionsgruppe") if gruppe else F.get("religion")
            ok = None if not ist else ((ist == z) != key.endswith("!="))
            was = "Religionsgruppe" if gruppe else "Religion"
            return self.k(f"{was} ist {'NICHT ' if key.endswith('!=') else ''}{n(z)}", ok, ist=n(ist) if ist else None,
                          wiki=self.wiki_ordner("religion_groups" if gruppe else "religions", z) or self.wiki_begriff("religion"),
                          handlung=f"{was} wechseln", bereich="staat")
        if key in ("tag", "this", "this!="):
            t = _ohne(v, "c")
            ok = (F.get("tag") == t) != (key == "this!=")
            return self.k(f"Ist {'NICHT ' if key == 'this!=' else ''}{n(t)}", ok)
        if key == "has_or_had_tag":
            # bisherige Kürzel: heute und zu Spielbeginn (original_tag); hat das Land nie gewechselt, ist die Liste vollständig
            t = v
            bisher = set(F.get("tags_bisher") or [F.get("tag"), F.get("tag_original")])
            vollst = F.get("tags_bisher") is not None or F.get("tag") == F.get("tag_original")
            ok = True if t in bisher else (False if vollst else None)
            return self.k(f"Ist oder war {n(t)}", ok)
        if key == "country_exists":
            t = _ohne(v, "c")
            leb = F.get("lebende")
            return self.k(f"{n(t)} existiert", None if leb is None else t in set(leb),
                          handlung=f"{n(t)} vernichten oder unterwerfen" if neg else None, bereich="militaer")
        if key == "country_rank":
            r = _ohne(v, "country_rank")
            return self.k(f"Rang ist „{n(r)}“", (F.get("rang") == r) if F.get("rang") else None, ist=n(F["rang"]) if F.get("rang") else None,
                          wiki=self.wiki_ordner("country_ranks", r) or self.wiki_begriff("country_rank"))
        m = re.match(r"country_rank_level(<=|>=|<|>|=|!=)?$", key)
        if m:
            op = m.group(1) or "="
            ist = F.get("stufe")
            ok = None if not _num(ist) or not _num(val) else {"<": ist < val, ">": ist > val, "<=": ist <= val, ">=": ist >= val,
                                                              "=": ist == val, "!=": ist != val}[op]
            return self.k(f"Rang-Stufe {VERGLEICH[op]} {val}", ok, ist=str(ist) if _num(ist) else None, wiki=self.wiki_begriff("country_rank"))
        if key == "current_age":
            return self.k(f"Es ist das Zeitalter „{n(v)}“", (F.get("zeitalter") == v) if F.get("zeitalter") else None,
                          wiki=self.wiki_ordner("age", v) or self.wiki_begriff("age"))
        if key == "current_age_or_later":
            a = (val or {}).get("age") if isinstance(val, dict) else v
            i, j = _zeitalter_nr(F.get("zeitalter")), _zeitalter_nr(a)
            return self.k(f"Es ist das Zeitalter „{n(a)}“ oder später", None if i is None or j is None else i >= j,
                          wiki=self.wiki_ordner("age", a) or self.wiki_begriff("age"))
        m = re.match(r"current_year(<=|>=|<|>|=)?$", key)
        if m:
            op, ist = m.group(1) or "=", F.get("jahr")
            ok = None if not _num(ist) or not _num(val) else {"<": ist < val, ">": ist > val, "<=": ist <= val, ">=": ist >= val, "=": ist == val}[op]
            return self.k(f"Derzeitiges Jahr ist {VERGLEICH[op]} {val}", ok)
        if key in ("is_member_of_international_organization", "is_leader_of_international_organization", "exists"):
            io = _ohne(v, "international_organization")
            feld = {"exists": "io_welt", "is_leader_of_international_organization": "io_leiter"}.get(key, "io")
            liste = F.get(feld)
            ok = None if liste is None else io in set(liste)
            text = {"exists": f"{n(io)} existiert", "is_leader_of_international_organization": f"Führt {n(io)}"}.get(
                key, f"Ist Mitglied von {n(io)}")
            return self.k(text, ok, wiki=self.wiki_begriff("holy_roman_empire") if io == "hre" else self.wiki_begriff("international_organization"))
        if key == "is_member_of_international_organization_of_type":
            io = (val or {}).get("type") if isinstance(val, dict) else v
            liste = F.get("io")
            return self.k(f"Ist Mitglied einer Organisation der Art „{n(io)}“", None if liste is None else io in set(liste),
                          wiki=self.wiki_begriff("international_organization"))
        if key in ("government_type", "government_type!="):
            g = _ohne(v, "government_type")
            ist = F.get("regierungsform")
            ok = None if not ist else ((ist == g) != key.endswith("!="))
            return self.k(f"Regierungsform ist {'NICHT ' if key.endswith('!=') else ''}{n(g)}", ok, ist=n(ist) if ist else None,
                          wiki=self.wiki_begriff("government_type"))
        if key == "is_subject":
            j, ist = _jn(v), F.get("untertan")
            return self.k("Ist ein Klientelland eines anderen Landes" if j else "Ist KEIN Klientelland eines anderen Landes",
                          None if ist is None else ist == j, wiki=self.wiki_begriff("subject"),
                          handlung="Unabhängigkeit erlangen" if not j else None, bereich="diplomatie")
        if key == "has_advance":
            a = _ohne(v, "advance_type")
            return self.k(f"Hat den Fortschritt „{n(a)}“", a in set(F.get("fortschritte") or []),
                          techbaum=f"techbaum/{a}" if self.W.gibt("advances", a) else None,
                          handlung=f"Fortschritt „{n(a)}“ erforschen", bereich="staat")
        if key == "court_language":
            s = _ohne(_ohne(v, "language"), "dialect")
            ist = F.get("hofsprache")
            return self.k(f"Die Hofsprache ist {n(s)}", None if not ist else ist == s, ist=n(ist) if ist else None,
                          wiki=self.wiki_begriff("court_language"))
        if key == "is_hegemon":
            return self.k("Ist ein Hegemon" if _jn(v) else "Ist KEIN Hegemon", None, wiki=self.wiki_begriff("hegemony"))
        if key == "has_dlc":
            dn = _dlc_name(v)
            return self.k(f"Hat den DLC „{dn}“" if dn else "Hat eine bestimmte Erweiterung (DLC)", None)
        if key.startswith("global_var:") or key == "has_variable" or key.startswith("var:"):
            return self.k("Spielvariable (Ergebnis eines Ereignisses oder einer Situation) – nicht im Spielstand-Auszug", None)
        if key.startswith("situation:") or key == "is_situation_active":
            return self.k("Bedingung an eine Situation des Spiels (nicht ausgewertet)", None)
        if key in ("has_ruler", "ruler"):
            return self.k("Bedingung an den Herrscher (nicht ausgewertet)", None)
        if key.startswith("international_organization:") or key.startswith("region:") or key.startswith("province_definition:") \
                or key.startswith("location:"):
            return self.k("Bedingung an eine Organisation oder ein Gebiet des Spiels (nicht ausgewertet)", None)
        return self._skript_oder_unbekannt(key, val, ("land",), neg)

    def _skript_oder_unbekannt(self, key, val, scope, neg):
        st = self.W.defs("scripted_triggers").get(key)
        if isinstance(st, dict) and _jn(val) is not None:
            loc = getattr(self.nm, "loc", None) or {}
            text = gamedata.clean_loc(loc.get(f"{key}_tt") or loc.get(key) or "", loc) or "Sonderbedingung des Spiels"
            kinder = self.block(st, scope, neg if _jn(val) else not neg)
            ok = _und([x["ok"] for x in kinder])
            if _jn(val) is False:
                return self.k(f"Darf nicht zutreffen: {text}", _nicht(ok), kinder=kinder, art="und")
            return self.k(text, ok, kinder=kinder, art="und")
        return self.k("Weitere Bedingung der Spieldatei (vom Ratgeber nicht ausgewertet)", None)


# ---------------------------------------------------------------- Gebiet
def benoetigt(d):
    """Geforderte Gebiete einer Gründung: ([{feld, ebene, key, orte}], Menge aller geforderten besitzbaren Orte)."""
    K = _karte()
    einheiten, alle = [], set()
    for feld, ebene, anz, begriff in EBENEN:
        for key in (d.get(feld) or []) if isinstance(d.get(feld), list) else ([d[feld]] if isinstance(d.get(feld), str) else []):
            orte = K["index"][ebene].get(key, []) if ebene else ([key] if key not in K["aus"] else [])
            einheiten.append({"feld": feld, "art": anz, "begriff": begriff, "key": key, "orte": orte})
            alle.update(orte)
    return einheiten, alle


def _regel_ok(d, F):
    """True/False/None: erlaubt die Spielregel „Gründbare Länder“ diese Gründung?"""
    r = REGEL_STUFE.get(d.get("rule") or "historical", 0)
    e = REGEL_EINSTELLUNG.get(F.get("regel"))
    return None if e is None else r <= e


def _stufe(W, F):
    return F.get("stufe") if _num(F.get("stufe")) else W.grad(F.get("tag"))


def _nach_gruendung(W, F, key, d, names=None):
    """Fakten nach der Gründung: neues Kürzel (die bisherigen bleiben für has_or_had_tag), Rang und Regierungsform aus form_effect
    (Bedingungen mit den heutigen Fakten)."""
    G = dict(F)
    G["tag"] = d.get("tag") or G.get("tag")
    G["stufe"] = d.get("level") if _num(d.get("level")) else G.get("stufe")      # Grad danach = Stufe der Gründung
    if F.get("tags_bisher") is not None or F.get("tag") == F.get("tag_original"):
        G["tags_bisher"] = sorted((set(F.get("tags_bisher") or []) | {F.get("tag"), F.get("tag_original"), G["tag"]}) - {None})
    for x in effekte(W, F, d, names):
        if x.get("ok") is False:
            continue
        if x.get("rang"):
            G["rang"] = x["rang"]
        if x.get("regierungsform"):
            G["regierungsform"] = x["regierungsform"]
    return G


def _gebiet(W, k):
    """Geforderte Orte einer Gründung (je Wissen zwischengespeichert)."""
    c = W.__dict__.setdefault("_gebiete", {})
    if k not in c:
        c[k] = benoetigt(W.defs("formable_countries").get(k) or {})[1]
    return c[k]


def infrage(W, G, k, stufe, bezug):
    """Warum die Gründung k nach den Fakten G nicht infrage kommt (None = kommt infrage): Grad nicht höher als `stufe`, Spielregel
    verbietet sie, potential sicher falsch, oder ihr Gebiet berührt `bezug` nicht (unsere Orte bzw. das Gebiet der vorigen Gründung) –
    ohne eigenen Ort darin zeigt das Spiel sie nicht (potential_requires_own, Standard ja)."""
    d = W.defs("formable_countries").get(k)
    if not isinstance(d, dict):
        return "keine"
    lv = d.get("level")
    if _num(stufe) and _num(lv) and lv <= stufe:
        return "stufe"
    if _regel_ok(d, G) is False:
        return "regel"
    if _und([x["ok"] for x in Pruefer(W, G).block(d.get("potential"))]) is False:
        return "potential"
    if _jn(d.get("potential_requires_own")) is not False and not (_gebiet(W, k) & set(bezug)):
        return "gebiet"
    return None


def kandidaten(W, F, tiefe=3):
    """Gründungen, die für uns infrage kommen (infrage), samt der danach möglichen bis zu `tiefe` Schritte: deren Gebiet muss das der
    vorigen Gründung oder unsere Orte berühren (Regel des Ratgebers)."""
    out = set()
    eigene = set(F.get("orte") or [])

    def schritt(G, stufe, bezug, n):
        for k in W.defs("formable_countries"):
            if k in out or infrage(W, G, k, stufe, bezug):
                continue
            out.add(k)
            if n > 1:
                d = W.defs("formable_countries")[k]
                H = _nach_gruendung(W, G, k, d)
                schritt(H, max(_stufe(W, H) or 0, d.get("level") or 0), _gebiet(W, k) | eigene, n - 1)
    schritt(F, _stufe(W, F), eigene, tiefe)
    return out


# ---------------------------------------------------------------- Wirkung
def effekte(W, F, d, names=None):
    """form_effect als Liste lesbarer Wirkungen: {text, ok (Bedingung erfüllt?), bedingung, rang, regierungsform, techbaum}."""
    P = Pruefer(W, F, names)
    n = P.n
    sv = W.defs("script_values")
    out = []

    def wert(x):
        if _num(x):
            return x
        y = sv.get(x) if isinstance(x, str) else None
        return y if _num(y) else None

    def gehe(b, bed=None, ok=True):
        for k, v in _paare(b):
            if k in ("if", "else_if"):
                vv = v if isinstance(v, dict) else {}
                lim = P.block(vv.get("limit"))
                w = _und([x["ok"] for x in lim])
                text = "; ".join(_kurz(x) for x in lim)
                gehe({a: b2 for a, b2 in vv.items() if a != "limit"}, (bed + "; " if bed else "") + text,
                     ok if w is True else (False if w is False else None) if ok is not False else False)
            elif k == "else":
                gehe(v, (bed + "; " if bed else "") + "sonst", None)
            elif k == "hidden_effect" or k == "change_country_color":
                continue
            elif k == "set_country_rank_effect":
                r = _ohne((v or {}).get("rank") if isinstance(v, dict) else v, "country_rank")
                out.append({"text": f"Rang wird „{n(r)}“", "rang": r, "bedingung": bed, "ok": ok,
                            "wiki": P.wiki_ordner("country_ranks", r)})
            elif k == "change_government_type":
                g = _ohne(v, "government_type")
                out.append({"text": f"Regierungsform wird {n(g)}", "regierungsform": g, "bedingung": bed, "ok": ok,
                            "wiki": P.wiki_begriff("government_type")})
            elif k in ("add_legitimacy", "add_stability", "add_government_power", "add_prestige"):
                was = {"add_legitimacy": "Legitimität", "add_stability": "Stabilität", "add_government_power": "Regierungsmacht",
                       "add_prestige": "Prestige"}[k]
                z = wert(v)
                out.append({"text": f"{was} {'+' + _de(z, 0) if _num(z) else '(Wert laut Spieldatei)'}", "bedingung": bed, "ok": ok,
                            "wiki": P.wiki_begriff({"add_legitimacy": "legitimacy", "add_stability": "stability",
                                                    "add_prestige": "prestige"}.get(k, ""))})
            elif k == "set_capital":
                out.append({"text": f"Hauptstadt wird {n(_ohne(v, 'location'))}", "bedingung": bed, "ok": ok, "wiki": P.wiki_begriff("capital")})
            elif k == "move_capital_event_effect":
                z = _ohne((v or {}).get("to") if isinstance(v, dict) else v, "location")
                out.append({"text": f"Hauptstadt soll nach {n(z)} verlegt werden (Ereignis)", "bedingung": bed, "ok": ok,
                            "wiki": P.wiki_begriff("capital")})
            elif k == "set_court_language":
                out.append({"text": f"Hofsprache wird {n(_ohne(_ohne(v, 'dialect'), 'language'))}", "bedingung": bed, "ok": ok,
                            "wiki": P.wiki_begriff("court_language")})
            elif k in ("unlock_casus_belli_effect", "unlock_policy_effect", "unlock_government_reform_effect"):
                t = (v or {}).get("type") if isinstance(v, dict) else v
                was = {"unlock_casus_belli_effect": "Kriegsgrund", "unlock_policy_effect": "Politik",
                       "unlock_government_reform_effect": "Regierungsreform"}[k]
                out.append({"text": f"{was} „{n(t)}“ wird freigeschaltet", "bedingung": bed, "ok": ok})
            elif k in ("add_reform", "remove_reform", "add_replacing_gov_reform"):
                r = _ohne((v or {}).get("reform") if isinstance(v, dict) else v, "government_reform")
                out.append({"text": f"Regierungsreform „{n(r)}“ wird {'abgeschafft' if k == 'remove_reform' else 'eingeführt'}",
                            "bedingung": bed, "ok": ok, "wiki": P.wiki_ordner("government_reforms", r)})
            elif k == "add_country_modifier":
                m = (v or {}).get("modifier") if isinstance(v, dict) else v
                j = (v or {}).get("years") if isinstance(v, dict) else None
                # Name: STATIC_MODIFIER_NAME_<schlüssel> (Lokalisierung static_modifiers)
                nm = (W.roh("static_modifiers").get(m) or {}).get("name") or n(f"STATIC_MODIFIER_NAME_{m}")
                txt = f"Landesmodifikator „{nm}“" if nm != f"STATIC_MODIFIER_NAME_{m}" else "Ein Landesmodifikator"
                out.append({"text": txt + (f" für {j} Jahre" if _num(j) else ""), "bedingung": bed, "ok": ok})
            elif k == "research_advance":
                a = _ohne(v, "advance_type")
                out.append({"text": f"Fortschritt „{n(a)}“ wird erforscht", "bedingung": bed, "ok": ok,
                            "techbaum": f"techbaum/{a}" if W.gibt("advances", a) else None})
            elif k == "change_societal_value":
                t = (v or {}).get("type") if isinstance(v, dict) else v
                out.append({"text": f"Gesellschaftswert „{n(t)}“ verschiebt sich", "bedingung": bed, "ok": ok})
            elif k.startswith("trigger_event"):
                out.append({"text": "Löst ein Ereignis aus", "bedingung": bed, "ok": ok})
            else:
                out.append({"text": "Weitere Wirkung der Spieldatei (vom Ratgeber nicht übersetzt)", "bedingung": bed, "ok": ok})
    gehe(d.get("form_effect"))
    return out


def rang_vergleich(W, alt, neu):
    """Rang-Modifikatoren (country_ranks rank_modifier) heute und nach dem Rangwechsel: [{key, name, alt, neu, prozent, ja_nein}]."""
    if not neu or neu == alt:
        return []
    ra = (W.defs("country_ranks").get(alt) or {}).get("rank_modifier") or {} if alt else {}
    rn = (W.defs("country_ranks").get(neu) or {}).get("rank_modifier") or {}
    out = []
    for m in list(dict.fromkeys([*rn, *ra])):
        t = (W.roh("_modifikator_typen").get(m) or {}) if W.quelle else {}
        a, b = ra.get(m), rn.get(m)
        if a == b or str(m).startswith("ai_"):
            continue
        out.append({"key": m, "name": t.get("name") or m, "alt": a, "neu": b, "prozent": t.get("percent") == "yes",
                    "ja_nein": t.get("boolean") == "yes"})
    return out


def fortschritte_fuer(W, tag, names=None):
    """Fortschritte, deren potential das Kürzel nennt (has_or_had_tag / tag) – mit der Gründung erforschbar (Techbaum)."""
    if not tag:
        return []
    out = []

    def nennt(x, neg=False):
        """Kürzel steht in der Bedingung – nicht unter NOT/NOR (swedish_roots: has_or_had_tag = SCA, NOT = { has_or_had_tag = SWE },
        Prüfer 30.10.)."""
        if isinstance(x, list):
            return any(nennt(y, neg) for y in x)
        if not isinstance(x, dict):
            return False
        for a, b in x.items():
            if a in ("has_or_had_tag", "tag") and not neg and tag in (b if isinstance(b, list) else [b]):
                return True
            if isinstance(b, (dict, list)) and nennt(b, neg or a in ("NOT", "NOR")):
                return True
        return False
    for k, e in W.roh("advances").items():
        d = (e or {}).get("def")
        if isinstance(d, dict) and nennt(d.get("potential")):
            out.append({"key": k, "name": (e or {}).get("name") or (names(k) if names else k), "zeitalter": d.get("age"),
                        "techbaum": f"techbaum/{k}"})
    return sorted(out, key=lambda x: (_zeitalter_nr(x["zeitalter"]) or 9, x["name"]))


# ---------------------------------------------------------------- Kachel
def _kurz(x):
    """Bedingung als eine Zeile (für Bedingungen von Wirkungen): Gruppen mit ihren Kindern."""
    k = x.get("kinder") or []
    if not k:
        return x["text"]
    innen = "; ".join(_kurz(y) for y in k)
    return {"nicht": f"nicht ({innen})", "oder": f"eines von ({innen})"}.get(x.get("art"), innen)


def _handlungen(knoten, out, umgekehrt=False):
    """Nicht erfüllte Blätter mit Handlung einsammeln. Unter NICHT/NOR (umgekehrt) stört, was zutrifft – dessen Handlung wurde
    schon mit neg ausgewertet („Privileg entziehen“). Vorbedingungen von trigger_if sind keine Forderung und bleiben weg."""
    for x in knoten:
        if x.get("art") == "vorbedingung" or x.get("entfaellt"):
            continue
        stoert = (x.get("ok") is True) if umgekehrt else (x.get("ok") is False)
        if x.get("ok") is not None and not stoert:
            continue
        if x.get("kinder"):
            _handlungen(x["kinder"], out, umgekehrt != (x.get("art") == "nicht"))
        elif stoert and x.get("handlung"):
            out.append({"bereich": x.get("bereich") or "staat", "text": x["handlung"], "bedingung": x["text"], "ist": x.get("ist"),
                        "ort": x.get("ort")})
        elif x.get("ok") is None:
            out.append({"bereich": "staat", "text": f"Im Spiel prüfen: {x['text']}", "bedingung": x["text"], "offen": True})


def build(last, quelle=None, names=None, nachbarn=None, lv=None, land=None, spiel=None):
    """Daten der Kachel Ländergründung. quelle: Funktion ordner -> vollständiges Spielwissen (history._voll). Ein Fehler hier soll
    die übrige Seite nicht verhindern – dann nur {"fehler": …}."""
    if not last:
        return None
    try:
        return _build(last, quelle, names, nachbarn, lv, land, spiel)
    except Exception as e:                       # noqa: BLE001
        return {"fehler": f"{type(e).__name__}: {e}"}


def _build(last, quelle, names, nachbarn, lv, land, spiel=None):
    nm = names or (lambda k: k)
    W = Wissen(quelle)
    feld = last.get("gruendung") if isinstance(last.get("gruendung"), dict) and "zusatz" in last.get("gruendung") else None
    F = fakten_momentaufnahme(last)
    if feld:
        F.update(feld["zusatz"])
    quellen = {}
    # Daten-Mod (neuester Monat) vor Spielstand: Stände-Macht, Rang-Stufe, Krieg, Bürgerkrieg
    r = (lv or [])[-1] if lv else {}
    sm = {k[6:]: v for k, v in r.items() if k.startswith("power_") and k.endswith("_estate") and _num(v)}
    if sm:
        F["stand_macht"], F["stand_macht_quelle"] = sm, f"Daten-Mod {r.get('datum')}"
    land = land or {}
    if _num(land.get("formable_level")):
        F["stufe"], quellen["stufe"] = int(land["formable_level"]), "Daten-Mod (formable_level, Grad laut Spiel)"
    else:
        F["stufe"], quellen["stufe"] = W.grad(F.get("tag")), ("Regel des Ratgebers: Stufe der Gründung mit unserem Kürzel, sonst 0 "
                                                             "(ohne Daten-Mod)")
    # ab Mod 0.25: Gründungen, die das Spiel uns zeigt, mit Gebietsfortschritt laut Spiel
    sp_werte = (spiel or {}).get("werte") or {}
    if _num(land.get("dip_IsAtWar")):
        F["krieg"] = land["dip_IsAtWar"] > 0
    if _num(land.get("IsInCivilWar")):
        F["buergerkrieg"] = land["IsInCivilWar"] > 0
    besitz = (feld or {}).get("besitz") or {}
    kand = set((feld or {}).get("kandidaten") or [])
    eigene = set(F.get("orte") or [])
    owner_von = {o: t for t, orte in besitz.items() for o in orte}
    nb = {x["tag"]: x for x in (nachbarn or {}).get("laender") or []}
    SP = (nachbarn or {}).get("spielstand") or {}
    sp = {z[0]: dict(zip(SP.get("spalten") or [], z)) for z in SP.get("zeilen") or []}
    fc = W.roh("formable_countries")
    P = Pruefer(W, F, nm)
    stufe = F.get("stufe")
    # infrage: höherer Grad, Spielregel erlaubt, potential nicht sicher falsch, eigener Ort im geforderten Gebiet (sonst zeigt das
    # Spiel die Gründung nicht) – die übrigen nur gezählt
    optionen, ausgeschlossen = [], {"stufe": 0, "regel": 0, "potential": 0, "gebiet": 0, "keine": 0}
    for key, e in fc.items():
        d = (e or {}).get("def")
        grund = infrage(W, F, key, stufe, eigene)
        if grund:
            ausgeschlossen[grund] += 1
            continue
        pot = P.block(d.get("potential"))
        optionen.append(_option(W, P, F, key, e, d, pot, _und([x["ok"] for x in pot]), eigene, owner_von,
                                key in kand, bool(feld), nb, sp, nm))
    keys = {o["key"] for o in optionen}
    for o in optionen:
        w = sp_werte.get(o["key"])
        o["spiel"] = _spiel_vergleich(w, o["gebiet"]) if w else {"sichtbar": False} if sp_werte else None
    # laut Spiel sichtbar, aber vom Ratgeber ausgeschlossen (z. B. Grad oder potential anders beurteilt)
    sp_extra = [{"key": k, "name": fc_name(W, k, nm), "fortschritt": (sp_werte[k] or {}).get("fortschritt")}
                for k in sorted(sp_werte) if k not in keys and k in fc]
    for o in optionen:
        o["danach"] = [{"key": k, "name": fc_name(W, k, nm), "stufe": W.defs("formable_countries")[k].get("level"),
                        "grad": ROEMISCH.get(W.defs("formable_countries")[k].get("level")), "option": k in keys}
                       for k in o.pop("danach_alle")]
    # Standard der Auswahl: die am weitesten erfüllte (gründbar zuerst, dann Fortschritt aus Gebiet und Bedingungen)
    optionen.sort(key=lambda o: (not o["gruendbar"], -o["fortschritt"], o["stufe"] or 0, o["name"]))
    standard = optionen[0]["key"] if optionen else None
    regel = F.get("regel")
    loc = getattr(nm, "loc", {}) or {}
    adj = nm(f"{F.get('tag')}_ADJ") if F.get("tag") else None
    vorlage = loc.get("TAB_TOOLTIP_CONTENT_TITLE") or ""
    fenster = (re.sub(r"\[Player\.GetAdjective\w*(?:\|\w*)?\]", adj, vorlage)
               if adj and adj != f"{F.get('tag')}_ADJ" and "[Player.GetAdjective" in vorlage else None)
    staende = {e.get("stand") for e in last.get("staende") or []}
    return {
        "datum": last["meta"].get("datum"), "format17": bool(feld), "standard": standard, "optionen": optionen,
        "spiel_mod": bool(sp_werte), "spiel_extra": sp_extra,
        "ausgeschlossen": ausgeschlossen, "fast_orte": FAST_ORTE,
        "fehler_spielstand": (last.get("gruendung") or {}).get("fehler") if isinstance(last.get("gruendung"), dict) else None,
        "stand": {"tag": F.get("tag"), "name": nm(F.get("tag")), "rang": F.get("rang"), "rang_name": nm(F.get("rang")) if F.get("rang") else None,
                  "stufe": stufe, "grad": ROEMISCH.get(stufe), "stufe_quelle": quellen["stufe"],
                  "regel": regel, "regel_name": gamedata.clean_loc(loc.get(f"setting_{regel}"), loc) if regel else None,
                  "kultur": nm(F.get("kultur")) if F.get("kultur") else None,
                  "kulturgruppen": [nm(g) for g in W.kultur(F.get("kultur")).get("culture_groups") or []] if F.get("kultur") else [],
                  "religion": nm(F.get("religion")) if F.get("religion") else None,
                  "regierungsform": nm(F.get("regierungsform")) if F.get("regierungsform") else None,
                  "hauptstadt": nm(F.get("hauptstadt")) if F.get("hauptstadt") else None,
                  "krieg": F.get("krieg"), "hre": ("hre" in (F.get("io") or [])) if F.get("io") is not None else None,
                  # nur Stände, die es bei uns gibt (der Daten-Mod schreibt alle, auch Dhimmi oder Kosaken mit 0)
                  "stand_macht": {k: v for k, v in (F.get("stand_macht") or {}).items() if not staende or k in staende},
                  "stand_namen": {k: nm(k) for k in (F.get("stand_macht") or {}) if not staende or k in staende},
                  "stand_macht_quelle": F.get("stand_macht_quelle"), "orte": len(eigene),
                  "verbuendete": [nm(t) for t in F.get("verbuendete") or []] if F.get("verbuendete") is not None else None,
                  "untertanen": [nm(t) for t in F.get("untertanen") or []]},
        # Weg im Spiel (Lokalisierung): Fenster „<Adjektiv>e Inhalte“ (TAB_TOOLTIP_CONTENT_TITLE), Reiter „Gründbare“
        # (game_concept_formables), Knopf „„<Name>“ gründen“ (FORM_COUNTRY); Hinweis „Gründbares Land“ (ALERT_POSSIBLE_FORMABLE_COUNTRIES_TITLE)
        "weg": {"fenster": fenster, "reiter": nm("game_concept_formables"), "hinweis": nm("ALERT_POSSIBLE_FORMABLE_COUNTRIES_TITLE")},
        "wiki": {k: P.wiki_begriff(k) for k in ("formable_country", "tier", "country_rank", "estate_power", "estate_privilege",
                                               "government_reform", "truce", "casus_belli", "subject", "alliance", "annexation",
                                               "area", "region", "location", "capital", "integration") if P.wiki_begriff(k)},
    }


def _option(W, P, F, key, e, d, pot, pok, eigene, owner_von, mit_besitz, format17, nb, sp, nm):
    """Eine Gründung: Bedingungen, Gebiet, Besitzer, Wirkung, Empfehlungen je Bereich. mit_besitz: die Momentaufnahme enthält die
    Besitzer ihrer Orte (Kandidat beim Einlesen)."""
    einheiten, R = benoetigt(d)
    frac = d.get("required_locations_fraction") if _num(d.get("required_locations_fraction")) else 1.0
    unsere = R & eigene
    n_alle = len(R)
    noetig = math.ceil(frac * n_alle - 1e-9) if n_alle else 0
    fehlt = max(0, noetig - len(unsere))
    hauptstadt_noetig = _jn(d.get("capital_required")) is True
    hs_ok = (F.get("hauptstadt") in R) if F.get("hauptstadt") else None
    sichtbar = (bool(unsere) if _jn(d.get("potential_requires_own")) is not False else True)
    allow = P.block(d.get("allow"))
    aok = _und([x["ok"] for x in allow]) if allow else True
    n_ok = sum(1 for x in allow if x["ok"] is True)
    n_offen = sum(1 for x in allow if x["ok"] is None)
    gebiet_ok = fehlt == 0 and n_alle > 0 and (not hauptstadt_noetig or hs_ok is True)
    # je Einheit: unsere / alle, Besitzer
    E = []
    for u in einheiten:
        o = set(u["orte"])
        E.append({"art": u["art"], "key": u["key"], "name": nm(u["key"]), "alle": len(o), "unsere": len(o & eigene),
                  "wiki": P.wiki_begriff(u["begriff"])})
    # fremde Besitzer der fehlenden Orte
    fremd = {}
    ohne = 0
    for ort in sorted(R - eigene):
        t = owner_von.get(ort)
        if t:
            fremd.setdefault(t, []).append(ort)
        else:
            ohne += 1
    untertanen, verb = set(F.get("untertanen") or []), set(F.get("verbuendete") or [])
    besitzer = []
    for t, orte in fremd.items():
        x = nb.get(t) or {}
        b = x.get("bewertung") or {}
        w = x.get("werte") or {}
        dv, cs = w.get("defensive_alliance_strength"), w.get("country_strength")
        besitzer.append({
            "tag": t, "name": nm(t), "orte": len(orte), "beispiele": [nm(o) for o in orte[:6]],
            "untertan": t in untertanen, "verbuendet": t in verb, "oberherr": t == F.get("oberherr"),
            "ampel": b.get("stufe"), "gruende": b.get("gruende") or [], "hinweise": b.get("hinweise") or [],
            "verhaeltnis": b.get("verhaeltnis"), "unendlich": b.get("unendlich"),
            "waffenstillstand": (x.get("diplomatie") or {}).get("truce"), "kriegsgrund": "kb_ziel" in (x.get("beziehungen") or []),
            "beziehungen": x.get("beziehungen") or [],
            "buendnis_faktor": dv / cs if _num(dv) and _num(cs) and cs > 0 else None,
            "mil_rang": (sp.get(t) or {}).get("mil_rang"), "rang": (sp.get(t) or {}).get("rang"),
            "mod": bool(x)})
    besitzer.sort(key=lambda b: (-b["orte"], AMPEL_RANG.get(b["ampel"] or "grau", 3), b["name"]))
    # Handlungen aus nicht erfüllten Bedingungen (bei „Besitzt X“ mit dem heutigen Besitzer)
    hand = []
    _handlungen(allow, hand)
    for h in hand:
        if h.get("ort") and owner_von.get(h["ort"]):
            h["text"] += f" (Besitzer: {nm(owner_von[h['ort']])})"
    # Wirkung
    eff = effekte(W, F, d, nm)
    neu_rang = next((x["rang"] for x in eff if x.get("rang") and x.get("ok") is not False), None)
    # Kette: danach möglich mit den Fakten nach der Gründung (Grad über dem der Gründung und dem neuen Rang, Gebiet berührt das
    # dieser Gründung oder unsere Orte – Regel des Ratgebers)
    G = _nach_gruendung(W, F, key, d, nm)
    st = max(d.get("level") or 0, _stufe(W, G) or 0)
    danach = [k2 for k2 in W.defs("formable_countries") if k2 != key and not infrage(W, G, k2, st, R | eigene)]
    danach.sort(key=lambda k2: (W.defs("formable_countries")[k2].get("level") or 0, fc_name(W, k2, nm)))
    gruendbar = bool(sichtbar and pok is True and aok is True and gebiet_ok)
    fortschritt = (min(1.0, (len(unsere) / noetig) if noetig else 0.0) * 0.6
                   + (n_ok / len(allow) if allow else 1.0) * 0.4)
    # ohne Besitzer: Momentaufnahme vor Format 17 oder die Gründung war beim Einlesen keine Kandidatin (Stufe aus dem Rang des
    # Spielstands, hier aus dem Daten-Mod – Prüfer 30.10.)
    besitz_fehlt = None if format17 and mit_besitz else "format" if not format17 else "kandidat"
    emp = _empfehlungen(F, d, besitzer, ohne, fehlt, hand, eff, neu_rang, W, nm, format17 and mit_besitz, besitz_fehlt)
    return {
        "key": key, "tag": d.get("tag"), "name": e.get("name") or nm(key), "beschreibung": e.get("beschreibung"),
        "stufe": d.get("level"), "grad": ROEMISCH.get(d.get("level")), "regel": d.get("rule") or "historical",
        "regel_name": REGEL_NAME.get(d.get("rule") or "historical"), "regel_ok": _regel_ok(d, F),
        "potential": pot, "potential_ok": pok, "sichtbar": sichtbar,
        "bedingungen": allow, "bedingungen_ok": aok, "bedingungen_erfuellt": n_ok, "bedingungen_offen": n_offen,
        "bedingungen_alle": len(allow),
        "gebiet": {"einheiten": E, "alle": n_alle, "unsere": len(unsere), "anteil": len(unsere) / n_alle if n_alle else 0.0,
                   "gefordert": frac, "noetig": noetig, "fehlt": fehlt, "hauptstadt_noetig": hauptstadt_noetig, "hauptstadt_ok": hs_ok,
                   "ok": gebiet_ok, "ohne_besitzer": ohne if mit_besitz and format17 else None,
                   "besitz_bekannt": bool(format17 and mit_besitz), "besitz_fehlt": besitz_fehlt},
        "besitzer": besitzer if format17 and mit_besitz else [],
        "wirkung": eff, "rang_neu": neu_rang, "rang_neu_name": nm(neu_rang) if neu_rang else None,
        "rang_neu_wiki": P.wiki_ordner("country_ranks", neu_rang) if neu_rang else None,
        "rang_modifikatoren": rang_vergleich(W, F.get("rang"), neu_rang),
        "fortschritte": fortschritte_fuer(W, d.get("tag"), nm),
        "danach_alle": danach, "gruendbar": gruendbar,
        "fast": bool(not gruendbar and sichtbar and pok is True and aok is True and n_alle and 0 < fehlt <= FAST_ORTE
                     and (not hauptstadt_noetig or hs_ok is True)),
        "fortschritt": round(fortschritt, 4), "empfehlungen": emp,
        "wiki": P.wiki_ordner("formable_countries", key),
    }


def _spiel_vergleich(w, g):
    """Gebietsfortschritt laut Spiel neben der Zählung des Ratgebers. location_progress_for_formable ist der Anteil an den nötigen
    Orten (Test 0.25, 31.10.: Walachei 0,687 = 44 von 64 wie am Eintrag im Reiter „Gründbare“; der Mod rundet auf 3 Stellen).
    orte: daraus mit unserer Zahl nötiger Orte (≈); gleich: dieselbe Zählung wie der Ratgeber (eigene Orte ohne Klientelländer)."""
    f = w.get("fortschritt")
    out = {"sichtbar": True, "fortschritt": f}
    if _num(f) and g.get("noetig"):
        eigen = g["unsere"] / g["noetig"]
        out["orte"] = round(f * g["noetig"])
        out["gleich"] = abs(f - eigen) < 0.0015 or abs(f - min(1.0, eigen)) < 0.0015
    return out


def fc_name(W, k, nm):
    return (W.roh("formable_countries").get(k) or {}).get("name") or nm(k)


def _empfehlungen(F, d, besitzer, ohne, fehlt, hand, eff, neu_rang, W, nm, besitz_bekannt, besitz_fehlt=None):
    """Empfehlungen je Bereich (Regeln des Ratgebers, Begründung aus den Daten)."""
    mil, dip, staat, wirt = [], [], [], []
    for h in hand:
        {"militaer": mil, "diplomatie": dip}.get(h["bereich"], staat).append(
            {"text": h["text"], "grund": f"Bedingung „{h['bedingung']}“ nicht erfüllt" + (f" (jetzt: {h['ist']})" if h.get("ist") else "")
             if not h.get("offen") else "Bedingung vom Ratgeber nicht auswertbar", "offen": h.get("offen")})
    if not besitz_bekannt and fehlt:
        mil.append({"text": f"Es fehlen {fehlt} Orte – " + (
                        "Besitzer stehen erst in Momentaufnahmen ab Format 17 (nächster Spielstand)" if besitz_fehlt != "kandidat" else
                        "ihre Besitzer hat der Ratgeber beim Einlesen nicht gesammelt: nach dem Rang im Spielstand war diese Gründung "
                        "noch keine Option (Stufe jetzt aus dem Daten-Mod)"),
                    "grund": "Spielstand ohne Besitzerliste für diese Gründung", "offen": True})
    # Reihenfolge Militär (Regel des Ratgebers): erst die Ampel des Landes (grün, gelb, ohne Mod-Werte, rot), dann die meisten
    # benötigten Orte; Klientelländer, Verbündete und Oberherr gehören zur Diplomatie
    mil_besitzer = sorted((b for b in besitzer if not (b["untertan"] or b["verbuendet"] or b["oberherr"])),
                          key=lambda b: (MIL_RANG.get(b["ampel"], 2), -b["orte"], b["name"]))
    plan, summe = [], 0
    for b in [b for b in besitzer if b["untertan"]] + mil_besitzer:
        if summe >= fehlt:
            break
        n = min(b["orte"], fehlt - summe)
        plan.append({"tag": b["tag"], "name": b["name"], "orte": n, "von": b["orte"], "weg": "eingliedern" if b["untertan"] else "erobern",
                     "ampel": b["ampel"]})
        summe += n
    for b in [b for b in besitzer if b["untertan"] or b["verbuendet"] or b["oberherr"]] + mil_besitzer:
        orte = f"{b['orte']} benötigte{'r' if b['orte'] == 1 else ''} Ort{'e' if b['orte'] != 1 else ''} ({', '.join(b['beispiele'][:4])}{' …' if b['orte'] > 4 else ''})"
        if b["untertan"]:
            dip.append({"text": f"{b['name']} eingliedern (Annexion): {orte}",
                        "grund": "Klientelland – seine Orte zählen erst nach der Eingliederung (Annahme des Ratgebers)"})
            continue
        if b["verbuendet"]:
            dip.append({"text": f"{b['name']} ist verbündet und besitzt {orte}",
                        "grund": "Gegen einen Verbündeten erst nach Ende des Bündnisses vorgehen (Regel des Ratgebers)"})
            continue
        if b["oberherr"]:
            dip.append({"text": f"{b['name']} ist unser Oberherr und besitzt {orte}", "grund": "erst Unabhängigkeit (Regel des Ratgebers)"})
            continue
        grund = []
        if b["ampel"]:
            grund.append({"gruen": "Ampel grün", "gelb": "Ampel gelb", "rot": "Ampel rot", "grau": "Ampel grau"}[b["ampel"]]
                         + (f" ({'; '.join(b['gruende'][:2])})" if b["gruende"] else ""))
        else:
            grund.append("keine Mod-Werte zu diesem Land (keine Beziehung zu uns) – Stärke unbekannt"
                         + (f"; Militär-Rang {b['mil_rang']} laut Spielstand" if b.get("mil_rang") else ""))
        if b["waffenstillstand"] == 1:
            grund.append("Waffenstillstand mit uns")
        if b["kriegsgrund"]:
            grund.append("Kriegsgrund vorhanden")
        mil.append({"text": f"Von {b['name']} holen: {orte}", "grund": "; ".join(grund), "ampel": b["ampel"], "tag": b["tag"]})
        if _num(b.get("buendnis_faktor")) and b["buendnis_faktor"] >= BUENDNIS_FAKTOR:
            dip.append({"text": f"{b['name']} isolieren: Verteidigungsbündnis {_de(b['buendnis_faktor'], 1)}-mal so stark wie das Land allein",
                        "grund": f"Daten-Mod (defensive_alliance_strength ÷ country_strength); ab {_de(BUENDNIS_FAKTOR, 1)}-fach erst Bündnisse "
                                 "lösen oder eigene Verbündete gewinnen (Regel des Ratgebers)"})
    if ohne and besitz_bekannt:
        mil.append({"text": f"{ohne} benötigte Orte haben keinen Besitzer", "grund": "Spielstand: Ort ohne Besitzer", "offen": True})
    mods = rang_vergleich(W, F.get("rang"), neu_rang)
    if mods:
        wirt.append({"text": f"Neuer Rang „{nm(neu_rang)}“: " + ", ".join(
            f"{m['name']} {_wert(m['alt'], m)} → {_wert(m['neu'], m)}" for m in mods[:6]) + (" …" if len(mods) > 6 else ""),
            "grund": "Spieldatei country_ranks (rank_modifier)"})
    fs = fortschritte_fuer(W, d.get("tag"), nm)
    if fs:
        wirt.append({"text": f"{len(fs)} Fortschritte nur für {nm(d.get('tag'))} werden erforschbar – die vergangener Zeitalter "
                             "möglicherweise nicht mehr",
                     "grund": "Spieldatei advances: potential nennt das Kürzel; readme dort: „advances do not become retroactively "
                              "visible“ (Prüfer 30.10.)"})
    wirt.append({"text": "Kosten der Gründung selbst: in den Spieldateien nicht angegeben – offen",
                 "grund": "formable_countries enthält keinen Preis", "offen": True})
    return {"militaer": mil, "diplomatie": dip, "staat": staat, "wirtschaft": wirt,
            # Vorschlag für die fehlenden Orte in der Reihenfolge oben (Regel des Ratgebers); reicht nur, wenn summe >= fehlt
            "plan": {"schritte": plan, "summe": summe, "fehlt": fehlt} if plan else None}


def _wert(v, m):
    if v is None:
        return "–"
    if m.get("ja_nein") or isinstance(v, str):
        return {"yes": "ja", "no": "nein"}.get(str(v), str(v))
    if m.get("prozent"):
        return _pz(v, 0)
    return _de(v, 2).rstrip("0").rstrip(",")
