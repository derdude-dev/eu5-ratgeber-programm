"""Fortschritte (Techbaum) als eigene Ansicht des Ratgebers (Nutzerwunsch 30.10.): alle Fortschritte des Spiels mit Suche,
Wirkungen, Freischaltungen, Vorgängern und Nachfolgern, dem Stand des Spielers und einem Vorschlag je Schwerpunkt des
Wirtschaftsplans. Seite: web/techbaum.js (#techbaum, #techbaum/<schlüssel>), Server: GET /api/techbaum?partie=<id>.

Quellen – nichts erfunden:
- Spielwissen advances.json (alle game/**/common/advances): Name, Beschreibung, Felder. Datei je Fortschritt aus den Spieldateien
  in_game/common/advances/*.txt und dlc/*/in_game/common/advances/*.txt (Schlüssel auf oberster Ebene); Thema = Einordnung des
  Ratgebers nach dem Dateinamen (THEMEN). Einträge ohne Block (Konstanten wie @fort_limit_modifier_increase = 0.1) fallen weg.
- Namen der Wirkungen/Freischaltungen: _modifikator_typen.json (Anzeigeformat wie im Spiel) und die Ordner des Spielwissens.
- Stand: neueste Momentaufnahme (Spielstand) – erforschte Fortschritte, Zeitalter (current_age), Regierungsform, Land, Kultur,
  Religion, Hauptstadt, Konzentration je Zeitalter (age_preferences); laufende Forschung und Forschung je Monat: Daten-Mod.

Voraussetzungen (requires, 16 Fortschritte haben zwei): ANNAHME „alle nötig“. Belegt ist nur die Darstellung des Spiels – eine
Liste „Voraussetzungen:“ mit ✓/✗ je Fortschritt (COUNTRY_ADVANCE_PREREQUISITES_LABEL, COUNTRY_ADVANCE_PREREQ_DONE/MISSING) und je
fehlendem Fortschritt eine Zeile „Benötigt „X““ (ADVANCE_REQUIRES_ADVANCE). Die Regel selbst steht in keiner Datei. Gegenprobe
Walachei: industry_promotion_advance (verlangt guilds und more_merchants_age_of_trad) ist ab Spielbeginn 1337.4.1 ohne guilds
erforscht – vom Spielbeginn gesetzt, kein Beleg für „einer reicht“.

Forschungskosten: das Feld research_cost ist ein Faktor, dessen Wirkung nicht belegt ist. Gerechnet wird nur, was Defines
(NCountry: BASE_RESEARCH_COST 25, BASE_UNIQUE_RESEARCH_COST 5, AGE_RESEARCH_MODIFIER 0.15, PREVIOUS_AGE_REDUCTION −8) und
Spielwerte (Daten-Mod: „Benötigt x von y“ mit Aufschlüsselung; Tooltips des Forschungsfensters) gemeinsam belegen – siehe
kosten().
"""
import glob
import html
import json
import os
import re

from . import gamedata, pfade, wiki
from . import sprache

FORMAT = 2           # Aufbau des Zwischenspeichers _techbaum_f<FORMAT>.json; erhöhen, wenn sich statisch() ändert
#                      2 (30.10., Prüfer): Wiki-Verweise nur auf Ordner, die das Wiki führt; Politiken direkt
GAME = gamedata.GAME_DIR

# ---------------------------------------------------------------- Themen (Regel des Ratgebers: Einordnung nach der Spieldatei)
# (Muster des Dateinamens ohne .txt, Thema) – das erste passende Muster gilt
THEMEN = [
    (r"^0_age_of_", "Allgemein"), (r"^1_building_unlocks$", "Gebäude"), (r"^2_army_unlocks$", "Landheer"),
    (r"^2_ship_unlocks$", "Flotte"), (r"^3_cabinet_actions_unlocks$", "Kabinettsaktionen"),
    (r"^3_character_interaction_unlocks$", "Interaktionen"), (r"^3_fort_level$", "Festungen"),
    (r"^3_production_method_unlocks$", "Produktionsmethoden"), (r"^3_reform_unlocks$", "Reformen"),
    (r"^3_road_unlocks$", "Straßen"), (r"^3_supply_limit$", "Versorgung"),
    (r"^4_choices_adm$", "Konzentration: Verwaltungsfähigkeit"), (r"^4_choices_dip$", "Konzentration: Diplomatiefähigkeit"),
    (r"^4_choices_mil$", "Konzentration: Militärfähigkeit"), (r"^diplomacy_unlocks$", "Diplomatie"),
    (r"^canal_advances$", "Kanäle"), (r"^government_", "Regierungsform"), (r"^ctype_", "Landestyp"), (r"^estate_", "Stände"),
    (r"^religion_", "Religion"), (r"^culture_", "Kultur"),
    (r"^(country_|d009_country_|D008_byzantine|japanese_unique)", "Land (einzigartig)"),
    (r"^(region_|d009_region_|d009_saqaliba|new_world|colonial_nations|frankokratia|beyliks)", "Region"),
]
THEMA_SONST = "Sonstiges"
# Konzentration je Zeitalter (Feld for; Spielstand age_preferences = ADM/DIP/MIL) – Namen laut game_concept_adm/dip/mil
KONZENTRATION = {"adm": "Verwaltungsfähigkeit", "dip": "Diplomatiefähigkeit", "mil": "Militärfähigkeit"}

# Freischaltungen: Feld -> (Ordner des Spielwissens für Name und Wiki-Verweis, Bezeichnung)
FREI = {
    "unlock_building": ("building_types", "Gebäude"), "unlock_unit": ("unit_types", "Einheit"),
    "unlock_production_method": (None, "Produktionsmethode"), "unlock_law": ("laws", "Gesetz"),
    "unlock_policy": (None, "Gesetzesoption"), "unlock_government_reform": ("government_reforms", "Reform"),
    "unlock_estate_privilege": ("estate_privileges", "Privileg"), "unlock_cabinet_action": ("cabinet_actions", "Kabinettsaktion"),
    "unlock_levy": ("levies", "Aufgebot"), "unlock_chivalric_order": ("chivalric_orders", "Ritterorden"),
    "unlock_subject_type": ("subject_types", "Untertanenart"), "unlock_town_rights": ("town_rights", "Stadtrecht"),
    "unlock_heir_selection": ("heir_selections", "Erbfolge"), "unlock_casus_belli": ("casus_belli", "Kriegsgrund"),
    "unlock_road_type": ("road_types", "Straßenart"), "unlock_ability": ("unit_abilities", "Fähigkeit"),
    "unlock_interaction": ("character_interactions", "Charakter-Interaktion"),
    "unlock_country_interaction": ("country_interactions", "Länder-Interaktion"),
    "unlock_diplomacy": ("country_interactions", "Diplomatie"), "unlock_relation_type": (None, "Beziehungsart"),
}
# Felder, die keine Wirkung sind (Aufbau, Bedingungen, KI)
FELDER = {"age", "icon", "requires", "potential", "allow", "government", "country_type", "for", "research_cost", "depth",
          "ai_weight", "ai_preference_tags", "content_priority", "in_tree_of", "allow_children", "starting_technology_level",
          "pure_tooltip_entry", "modifier_while_progressing"}

# ---------------------------------------------------------------- Vorschlag je Schwerpunkt (Regel des Ratgebers)
# Punkte je Grund; Summe = Reihung, bei Gleichstand billiger (Forschungskosten), dann niedrigere Stufe im Baum, dann Name.
# n = Rang des Guts im Schwerpunkt (Bedarfstabelle der Kachel Wirtschaftsplan, 1 = vorne).
PUNKTE = {
    "gut_gebaeude": "30 − 2 je Rang (mind. 10), +5 wenn knapp – schaltet ein Gebäude frei, das ein Schwerpunkt-Gut herstellt",
    "gut_fehlt": "12 – Gebäude oder Methode für ein Schwerpunkt-Gut, das im Heimatmarkt fehlt",
    "gut_methode": "20 − 1 je Rang (mind. 8) – Produktionsmethode für ein Schwerpunkt-Gut",
    "gut_ausstoss": "15 − 1 je Rang (mind. 6) – Ausstoß-Modifikator eines Schwerpunkt-Guts",
    "gebaeude_wirkung": "20 – schaltet ein Gebäude mit Schwerpunkt-Wirkung frei (Liste „Gebäude mit Wirkung“ im Wirtschaftsplan)",
    "fokus_mod": "15 – landesweiter Modifikator zur Schwerpunkt-Wirkung der Gebäude (local_x -> global_x)",
    "einheit": "20 – schaltet eine Einheit des Schwerpunkts frei (Landheer: army_…, Marine: navy_…)",
    "thema_mod": "10 – Modifikator aus der Themenliste des Schwerpunkts (THEMA_REGEL), nur günstige Richtung",
    "thema_frei": "8 – Freischaltung aus der Themenliste des Schwerpunkts",
}
# Themenliste je Schwerpunkt: (Beschreibung, Muster der Modifikatoren, Freischaltungs-Felder)
THEMA_REGEL = {
    "grundwirtschaft": ("Produktion und Rohstoffe", r"^(global_production_efficiency|global_raw_material_output|"
                        r"global_max_rgo_size_modifier|expand_rgo_\w+_cost_modifier|global_monthly_prosperity|"
                        r"global_monthly_development)$", ()),
    "gewinn": ("Produktion, Wohlstand und Steuern", r"^(global_production_efficiency|tax_income_efficiency|global_monthly_prosperity|"
               r"global_non_rural_monthly_prosperity|global_max_rgo_size_modifier|global_raw_material_output|"
               r"minting_income_factor)$", ()),
    "bevoelkerung": ("Wachstum, Nahrung und Zuzug", r"^(global_population_growth|global_population_capacity_modifier|"
                     r"global_monthly_food_modifier|global_food_capacity(_modifier)?|"           # nicht global_life_expectancy:
                     # „Charakterlebenserwartung“ (Prüfer 30.10.)
                     r"global_migration_\w+|\w*migration_attraction)$", ()),
    "landheer": ("Landheer", r"^(global_manpower_modifier|land_\w+|discipline|military_tactics|army_\w+|regiment_\w+|"
                 r"global_regiment_\w+|siege_ability|global_levy_size_modifier|global_supply_limit_modifier|"
                 r"global_hostile_attrition)$", ("unlock_levy",)),
    "marine": ("Flotte", r"^(global_sailors_modifier|naval_\w+|navy_\w+|ship_\w+|privateer_\w+|global_navy_levy_size_modifier|"
               r"global_maritime_presence_modifier|blockade_\w+)$", ()),
    "expansion": ("Erkundung und Kolonisierung", r"^(may_explore|can_colonize|colonial_\w+|exploration_\w+|global_colonial_\w+|"
                  r"colonist\w*|expedition\w*)$", ()),
    "export": ("Handel (Ausfuhr)", r"^(global_merchant_capacity_modifier|trade_range(_modifier)?|export_efficiency|"
               r"selling_efficiency|trade_(land|sea)_efficiency|global_trade_center_power|global_merchant_power|"
               r"merchant_power_\w+|global_trades_per_burgher|max_tariff|merchant_maintenance_efficiency)$", ()),
    "import": ("Handel (Einfuhr)", r"^(global_merchant_capacity_modifier|trade_range(_modifier)?|trade_(land|sea)_efficiency|"
               r"global_merchant_power|merchant_power_\w+|global_trades_per_burgher|merchant_maintenance_efficiency)$", ()),
    "bau": ("Bauen", r"^(global_build_buildings_efficiency|global_urban_build_buildings_efficiency|"
            r"global_rural_build_buildings_efficiency|global_construction_speed|build_\w+_road_cost_modifier|"
            r"global_road_building_time|town_upgrade_cost_modifier)$", ("unlock_road_type", "unlock_town_rights")),
    "verwaltung": ("Verwaltung und Hof", r"^(legislative_efficiency|country_cabinet_efficiency|court_spending_efficiency|"
                   r"government_reform_slots|global_integration_speed_modifier|global_monthly_control|stability_\w+|"
                   r"government_size|bureaucracy_\w+|monthly_political_influence\w*|diplomatic_capacity(_modifier)?)$",
                   ("unlock_law", "unlock_government_reform", "unlock_estate_privilege", "unlock_cabinet_action",
                    "unlock_policy")),
    "lebensstandard": ("Zufriedenheit der Stände", r"^(global_estate_target_satisfaction|\w+_estate_target_satisfaction|"
                       r"\w+_estate_satisfaction_recovery)$", ()),
}
EINHEIT_PREFIX = {"landheer": "army_", "marine": "navy_"}
TOP = 6              # Vorschläge je Schwerpunkt (jetzt erforschbar)
TOP_ZIELE = 4        # Ziele je Schwerpunkt (tiefer, kurzer Weg)
ZIEL_SCHRITTE = 3    # höchstens so viele fehlende Voraussetzungen vor dem Ziel

STATUS = {"e": "erforscht", "j": "jetzt erforschbar", "v": "Voraussetzungen fehlen", "s": "späteres Zeitalter",
          "n": "nicht für uns", "u": "unklar (Bedingung nicht auswertbar)"}


def _liste(v):
    return v if isinstance(v, list) else [] if v is None else [v]


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _de(v, d=2):
    """Zahl in der Schreibweise der Ausgabe, höchstens d Nachkommastellen, ohne Nullen am Ende."""
    s = sprache.ziffern(f"{abs(v):,.{d}f}")
    if sprache.KOMMA in s:
        s = s.rstrip("0").rstrip(sprache.KOMMA)
    return ("−" if v < 0 and s != "0" else "") + s


def _sgn(v, d=2):
    return ("+" if v > 0 else "") + _de(v, d)


def _voll_get(voll):
    from .history import _voll                       # spät: history bindet dieses Modul ein
    return lambda o: _voll(voll, o)


def _top_keys(text):
    """Schlüssel auf oberster Ebene einer Spieldatei (Klammertiefe 0; Zeichenketten und Kommentare übersprungen)."""
    out, tiefe = [], 0
    for m in re.finditer(r'"(?:[^"\\]|\\.)*"|#[^\n]*|([\w.@:\-]+)\s*=\s*\{|\{|\}', text):
        s = m.group(0)
        if s[0] in '"#':
            continue
        if m.group(1):
            if tiefe == 0:
                out.append(m.group(1))
            tiefe += 1
        elif s == "{":
            tiefe += 1
        else:
            tiefe = max(0, tiefe - 1)
    return out


def dateien(game_dir=GAME):
    """{schlüssel: Datei relativ zum Spielordner} aller Fortschritte (Hauptspiel und DLC); bei doppelten Schlüsseln gilt die
    spätere Datei in derselben Reihenfolge wie beim Bau des Spielwissens (sortierte Pfade)."""
    fs = sorted(glob.glob(os.path.join(glob.escape(game_dir), "in_game", "common", "advances", "*.txt"))
                + glob.glob(os.path.join(glob.escape(game_dir), "dlc", "*", "in_game", "common", "advances", "*.txt")))
    out = {}
    for f in fs:
        with open(f, encoding="utf-8-sig", errors="replace") as fh:
            for k in _top_keys(fh.read()):
                out[k] = os.path.relpath(f, game_dir).replace(os.sep, "/")
    return out


def thema(datei):
    base = os.path.splitext(os.path.basename(datei or ""))[0]
    for muster, name in THEMEN:
        if re.search(muster, base):
            return name
    return THEMA_SONST


# ---------------------------------------------------------------- Werte wie im Spiel
def _konstanten(vg, adv):
    """Benannte Werte: script_values (Zahl) und Konstanten der Fortschrittsdateien (@x = 0.1 im Spielwissen advances)."""
    out = {k: v["def"] for k, v in (vg("script_values") or {}).items() if isinstance(v, dict) and _num(v.get("def"))}
    out.update({k: v["def"] for k, v in adv.items() if k.startswith("@") and isinstance(v, dict) and _num(v.get("def"))})
    return out


def wert(m, v, mt, const):
    """(Anzeige wie im Spiel, Zahl, Richtung): Prozent/Ja-Nein laut Modifikator-Typ, benannte Werte aufgelöst. Richtung 1 =
    günstig, −1 = ungünstig (color = bad: höher ist schlechter), 0 = neutral oder unbekannt."""
    t = mt.get(m) or {}
    if isinstance(v, str) and v in const:
        v = const[v]
    if v == "yes":
        return "ja", None, 1
    if not _num(v):
        return f"{v} (Skriptwert, nicht aufgelöst)", None, 0
    if t.get("boolean") == "yes":
        return ("ja" if v else "nein"), v, 1 if v else -1
    d = int(t["decimals"]) if str(t.get("decimals", "")).isdigit() else None
    if (t.get("game_data") or {}).get("format") in ("FormatManPower", "FormatPopCaps"):
        # Mannstärke, Seeleute, Bevölkerungsgrenze zählen in Tausend wie Pops (wie wirtschaftsplan.modtxt)
        txt = _sgn(v, 3) + " Tsd."
    elif t.get("percent") == "yes":
        txt = _sgn(v * 100, d if d is not None else 2) + " %"
    elif t.get("already_percent") == "yes":
        txt = _sgn(v, d if d is not None else 2) + " %"
    else:
        txt = _sgn(v, d if d is not None else (3 if abs(v) < 0.1 else 2))
    farbe = t.get("color")
    richtung = 0 if farbe == "neutral" or v == 0 else (1 if (v > 0) != (farbe == "bad") else -1)
    return txt, v, richtung


# ---------------------------------------------------------------- statische Daten je Spielversion
_CACHE = {}


def statisch(voll, names=None, vg=None, game_dir=GAME):
    """Alle Fortschritte mit Namen, Thema, Datei, Vorgängern/Nachfolgern, Wirkungen und Freischaltungen – einmal je Spielversion
    (Speicher und data/spielwissen/<version>/_techbaum_f<FORMAT>.json; nur mit Spielnamen auf die Platte)."""
    if voll in _CACHE:
        return _CACHE[voll]
    pfad = os.path.join(voll, f"_techbaum_f{FORMAT}.json") if voll else None
    if pfad and os.path.exists(pfad):
        with open(pfad, encoding="utf-8") as f:
            _CACHE[voll] = json.load(f)
        return _CACHE[voll]
    vg = vg or _voll_get(voll)
    nm = names or (lambda k: k)
    adv = vg("advances") or {}
    mt = vg("_modifikator_typen") or {}
    const = _konstanten(vg, adv)
    ages = sorted(((k, v) for k, v in (vg("age") or {}).items() if isinstance(v.get("def"), dict)),
                  key=lambda kv: kv[1]["def"].get("year") or 0)
    alter = [{"key": k, "name": v.get("name") or nm(k), "jahr": v["def"].get("year")} for k, v in ages]
    a_idx = {a["key"]: i for i, a in enumerate(alter)}
    datei = dateien(game_dir) if game_dir and os.path.isdir(game_dir) else {}
    wis_geb = (_wissen_gebaeude(voll) or {}) if voll else {}
    pm_geb = {pm.get("name"): (art, pm.get("produced")) for art, b in wis_geb.items() for pm in b.get("pms") or []}
    gesetz_von = {}                                      # Gesetzesoption -> Gesetz (laws: Option = Block im Gesetz)
    for lk, lv in (vg("laws") or {}).items():
        for ok, ov in ((lv or {}).get("def") or {}).items():
            if isinstance(ov, dict):
                gesetz_von.setdefault(ok, lk)
    ordner = {o: (vg(o) or {}) for o, _ in FREI.values() if o}
    ut = vg("unit_types") or {}

    def einheit_kat(k, seen=()):
        d = (ut.get(k) or {}).get("def") or {}
        if "category" in d:
            return d["category"]
        c = d.get("copy_from")
        return einheit_kat(c, seen + (k,)) if isinstance(c, str) and c not in seen else None

    def name_in(o, k):
        e = (ordner.get(o) or {}).get(k) or {}
        n = e.get("name") or nm(k)
        return n if n != k else (nm(k) or k)

    F = {}
    for k, e in adv.items():
        d = e.get("def")
        if not isinstance(d, dict):
            continue                                     # Konstante (@x = 0.1) oder Fehler – kein Fortschritt
        w, s = [], []
        for m, v in d.items():
            if m in FELDER or m.startswith("unlock_") or m not in mt:
                continue
            txt, zahl, ri = wert(m, v, mt, const)
            if (mt[m].get("boolean") == "yes" or v == "yes") and v in ("yes", 1):
                s.append([m, mt[m].get("name") or m])
            else:
                w.append([m, mt[m].get("name") or m, txt, ri])
        for m, v in ((d.get("modifier_while_progressing") or {}) if isinstance(d.get("modifier_while_progressing"), dict)
                     else {}).items():
            if m in mt:
                txt, zahl, ri = wert(m, v, mt, const)
                w.append([m, (mt[m].get("name") or m) + " (während der Forschung)", txt, ri])
        u = []
        for feld, (o, label) in FREI.items():
            for x in _liste(d.get(feld)):
                if not isinstance(x, str):
                    continue
                if feld == "unlock_production_method":
                    art, gut = pm_geb.get(x, (None, None))
                    bn = (ordner["building_types"].get(art) or {}).get("name") or nm(art) if art else None
                    u.append([feld, label, x, nm(x) + (f" ({bn})" if bn else ""),
                              f"#wiki/building_types/{art}" if art in ordner["building_types"] and wiki.im_wiki("building_types")
                              else "", gut])
                elif feld == "unlock_policy":
                    law = gesetz_von.get(x)
                    lname = name_in("laws", law) if law else None
                    # #wiki/policies/<politik> öffnet das Gesetz und springt zur Politik (wiki.js wkFinde, Prüfer 30.10.)
                    u.append([feld, label, x, nm(x) + (f" ({lname})" if lname else ""),
                              f"#wiki/policies/{x}" if law else "", None])
                else:
                    da = o and x in (ordner.get(o) or {}) and wiki.im_wiki(o)
                    extra = einheit_kat(x) if feld == "unlock_unit" else None
                    u.append([feld, label, x, name_in(o, x) if o else nm(x), f"#wiki/{o}/{x}" if da else "", extra])
        tipps = [nm(x) for x in _liste(d.get("pure_tooltip_entry")) if isinstance(x, str)]
        dt = datei.get(k)
        # Spieltexte enthalten &amp; (merchants_and_trade: „Händler &amp; Handel“) – angezeigt wird „&“
        F[k] = {"n": html.unescape(e.get("name") or nm(k)), "b": html.unescape(e["beschreibung"]) if e.get("beschreibung") else None, "z": a_idx.get(d.get("age")), "i": d.get("icon"),
                "rc": d.get("research_cost") if _num(d.get("research_cost")) else None, "dp": d.get("depth"),
                "dt": dt, "th": thema(dt) if dt else THEMA_SONST,
                "dlc": (dt.split("/")[1] if dt and dt.startswith("dlc/") else None),
                "r": [x for x in dict.fromkeys(_liste(d.get("requires"))) if isinstance(x, str)], "nf": [],
                "g": d.get("government"), "ct": d.get("country_type"), "fo": d.get("for"),
                "itb": d.get("in_tree_of"), "w": w, "s": s, "u": u, "tt": tipps,
                # nur für den Server (Bedingungen auswerten), nicht an die Seite
                "pot": d.get("potential"), "allow": d.get("allow")}
    for k, a in F.items():                               # Nachfolger: wer verlangt diesen Fortschritt
        for r in a["r"]:
            if r in F and k not in F[r]["nf"]:
                F[r]["nf"].append(k)
    # Stufe im Baum: 0 ohne Vorgänger, sonst 1 + höchste Stufe der Vorgänger (requires bleiben im selben Zeitalter)
    stufe = {}

    def tiefe(k, weg=()):
        if k in stufe:
            return stufe[k]
        rs = [r for r in F[k]["r"] if r in F and r not in weg]
        stufe[k] = 1 + max(tiefe(r, weg + (k,)) for r in rs) if rs else 0
        return stufe[k]
    for k in F:
        F[k]["t"] = tiefe(k)
    defs = ((vg("defines") or {}).get("NCountry") or {}).get("def") or {}
    S = {"format": FORMAT, "zeitalter": alter, "fortschritte": F, "konst": const,
         "themen": [t for _, t in THEMEN if any(a["th"] == t for a in F.values())]
         + ([THEMA_SONST] if any(a["th"] == THEMA_SONST for a in F.values()) else []),
         "kosten_defines": {x: defs.get(x) for x in ("BASE_RESEARCH_COST", "BASE_UNIQUE_RESEARCH_COST",
                                                     "AGE_RESEARCH_MODIFIER", "PREVIOUS_AGE_REDUCTION")},
         "dateien_gefunden": len([k for k in F if F[k]["dt"]])}
    _CACHE[voll] = S
    if pfad and names is not None and datei:
        pfade.atomar_schreiben(pfad, json.dumps(S, ensure_ascii=False).encode("utf-8"))
    return S


def _wissen_gebaeude(voll):
    """Gebäude mit Produktionsmethoden aus data/spielwissen.json (wissen.py; liegt neben dem Ordner spielwissen/)."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(voll))), "spielwissen.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("gebaeude") or {}


# ---------------------------------------------------------------- Fakten des Spielstands für Bedingungen
def installierte_dlcs(game_dir=GAME):
    d = os.path.join(game_dir, "dlc")
    return sorted(x.lower() for x in os.listdir(d)) if os.path.isdir(d) else None


def fakten(last, vg, wis=None, dlcs=None):
    """Was die Bedingungen (potential, allow) über unser Land wissen können – aus der Momentaufnahme (roh = Spielstand).
    None = unbekannt (die Bedingung bleibt dann unklar)."""
    roh = last.get("roh") or {}
    L = roh.get("land") or {}
    meta = last.get("meta") or {}
    kul = (roh.get("kulturen") or {}).get(str(L.get("primary_culture"))) or {}
    kultur = kul.get("culture_definition")
    cdef = ((vg("cultures") or {}).get(kultur) or {}).get("def") or {} if kultur else {}
    rel = roh.get("religion") or {}
    hier = (wis or {}).get("hierarchie") or {}
    ortkey = {o.get("id"): o.get("key") for o in last.get("orte") or []}

    def ort(lid):
        k = ortkey.get(lid)
        return hier.get(k) if k else None
    tag = meta.get("tag")
    return {
        "tag": tag, "original_tag": L.get("original_tag"),
        # „hat oder hatte“: heutiges Kennzeichen, Ursprung (original_tag) und Definition des Landes – frühere Kennzeichen nach
        # einer Umbildung kennt der Spielstand nicht (Regel des Ratgebers)
        "tags": sorted({x for x in (tag, L.get("original_tag"), L.get("definition")) if isinstance(x, str)}) if tag else None,
        "kultur": kultur, "kulturgruppen": _liste(cdef.get("culture_groups")) if kultur else None,
        "sprache": kul.get("language") or cdef.get("language"),
        "religion": rel.get("key") or rel.get("definition"), "religionsgruppe": rel.get("group"),
        "regierung": meta.get("regierungsform"), "landestyp": L.get("type"),
        "reformen": list(last.get("reformen") or []) if last.get("reformen") is not None else None,
        "orte": len(last.get("orte") or []) if last.get("orte") is not None else None,
        "institutionen": (last.get("forschung") or {}).get("institutionen"),
        "erforscht": [x.get("key") for x in (last.get("forschung") or {}).get("fortschritte") or []]
        if last.get("forschung") is not None else None,
        # Stände mit existence = yes (snapshot.py übernimmt nur diese)
        "staende": [e.get("stand") for e in last.get("staende") or []] if last.get("staende") is not None else None,
        "hauptstadt": ort(L.get("capital")),
        # original_capital: Hauptstadt bei Spielbeginn (game_start_capital) – ANNAHME, der Spielstand nennt das Feld so
        "ur_hauptstadt": ort(L.get("game_start_capital")),
        # aktive Erweiterungen: Spielstand-Kopf (enabled_dlcs), falls die Momentaufnahme ihn trägt, sonst installierte (Spielordner dlc/)
        "dlcs": [str(x).lower() for x in (meta.get("dlcs") if meta.get("dlcs") is not None else dlcs)]
        if (meta.get("dlcs") is not None or dlcs is not None) else None,
        "dlcs_quelle": "Spielstand" if meta.get("dlcs") is not None else "Spielordner (installiert)" if dlcs is not None else None,
        "zeitalter": meta.get("zeitalter"),
        "zeitalter_folge": [k for k, v in sorted(((k, v) for k, v in (vg("age") or {}).items() if isinstance(v.get("def"), dict)),
                                                 key=lambda kv: kv[1]["def"].get("year") or 0)],
        "konzentration": {k: str(v).lower() for k, v in (L.get("age_preferences") or {}).items()},
        # zusammengelegte Kultur (Effekt merge_culture_group, Kultur-Vereinigung): unsere Kultur steht als feste Kultur in
        # cultures.json -> keine zusammengelegte (ANNAHME; der Spielstand nennt keine Zusammenlegung)
        "kultur_fest": bool(kultur and kultur in (vg("cultures") or {})),
    }


# ---------------------------------------------------------------- Bedingungen auswerten (drei Werte: True, False, None)
def _und(werte):
    return False if any(w is False for w in werte) else True if all(w is True for w in werte) else None


def _oder(werte):
    return True if any(w is True for w in werte) else False if all(w is False for w in werte) else None


def _nicht(w):
    return None if w is None else not w


def _ohne(v):
    return v.split(":", 1)[1] if isinstance(v, str) and ":" in v else v


ORT_FELD = {"region": ("region", "Region"), "area": ("gebiet", "Gebiet"), "sub_continent": ("subkontinent", "Subkontinent"),
            "continent": ("kontinent", "Kontinent"), "province": ("provinz", "Provinz")}
ORT_SCOPE = {"capital": ("hauptstadt", "Hauptstadt"), "original_capital": ("ur_hauptstadt", "Hauptstadt bei Spielbeginn")}
VERGLEICH = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}


class Bedingung:
    """Wertet potential/allow eines Fortschritts gegen die Fakten aus und beschreibt sie lesbar: Knoten [Text, ok, Kinder],
    ok = True/False/None. NOR: keiner der Einträge darf zutreffen; NAND: nicht alle zugleich. NOT mit mehreren Einträgen: die
    Spieldoku sagt nur „negates content of trigger“ (docs/triggers.log) – stimmen „keins davon“ und „nicht alle zugleich“ überein,
    gilt das Ergebnis, sonst offen (wie gruendung.py; Prüfer 30.10.)."""

    def __init__(self, F, vg, names=None):
        self.F, self.nm = F, names or (lambda k: k)
        self.vg = vg
        self.tiefe = 0                                   # Verschachtelung der scripted_triggers (Schutz vor Schleifen)

    def name(self, ordner, k):
        k = _ohne(k)
        e = (self.vg(ordner) or {}).get(k) if ordner else None
        n = (e or {}).get("name") or self.nm(k)
        return n if n and n != k else k

    def block(self, d, scope="land", modus="und"):
        knoten = []
        for k, v in (d.items() if isinstance(d, dict) else []):
            for x in _liste(v):
                knoten.append(self.knoten(str(k), x, scope))
        ok = (_und if modus == "und" else _oder)([n[1] for n in knoten])
        return knoten, ok

    def pruefe(self, d):
        return self.block(d)[1] if d else True

    def baum(self, d):
        return self.block(d)[0] if d else []

    def knoten(self, k, x, scope):
        F = self.F
        if k == "NOT":
            kinder, _ = self.block(x, scope)
            w = [n[1] for n in kinder]
            nor, nand = _nicht(_oder(w)), _nicht(_und(w))
            return ["keine davon:" if nor == nand else "nicht (mehrere Bedingungen – ob „keins davon“ oder „nicht alle zugleich“, "
                    "ist nicht belegt):", nor if nor == nand else None, kinder]
        if k in ("OR", "AND", "NOR", "NAND"):
            kinder, ok = self.block(x, scope, "oder" if k in ("OR", "NOR") else "und")
            text = {"OR": "eine davon:", "AND": "alle:", "NOT": "keine davon:", "NOR": "keine davon:",
                    "NAND": "nicht alle:"}[k]
            return [text, _nicht(ok) if k in ("NOT", "NOR", "NAND") else ok, kinder]
        if k in ("custom_tooltip", "custom_description") and isinstance(x, dict):
            kinder, ok = self.block({a: b for a, b in x.items() if a not in ("text", "subject", "object")}, scope)
            return [f"Spieltext {x.get('text')}:", ok, kinder]
        if k in ("current_age", "current_age_or_later"):
            folge = F.get("zeitalter_folge") or []
            ziel = _ohne(x.get("age") if isinstance(x, dict) else x)
            if F.get("zeitalter") in folge and ziel in folge:
                i, j = folge.index(F["zeitalter"]), folge.index(ziel)
                ok = i == j if k == "current_age" else i >= j
            else:
                ok = None
            return [f"Zeitalter {self.name('age', ziel)}" + (" oder später" if k == "current_age_or_later" else ""), ok, []]
        st = (self.vg("scripted_triggers") or {}).get(k)
        if st and isinstance(st.get("def"), dict) and x in ("yes", "no") and self.tiefe < 6:
            self.tiefe += 1
            try:
                kinder, ok = self.block(st["def"], scope)
            finally:
                self.tiefe -= 1
            return [f"Spielbedingung {k}{' = nein' if x == 'no' else ''} (scripted_triggers):",
                    ok if x == "yes" else _nicht(ok), kinder]
        m = re.match(r"^([\w.:]+?)(\?=|>=|<=|>|<)?$", k)
        k0, op = (m.group(1), m.group(2)) if m else (k, None)
        # Gültigkeitsbereiche: Kultur, Hauptstadt (Ort)
        if scope == "kultur":
            if k0 == "has_culture_group":
                g = F.get("kulturgruppen")
                return [f"Kulturgruppe {self.name('culture_groups', x)}", None if g is None else _ohne(x) in g, []]
            if k0 == "merged_culture_group_contains_culture":
                # Spieldoku (triggers.log): „True if this merged culture was formed from a culture group that contained the target
                # culture“ – nur zusammengelegte Kulturen; eine feste Kultur aus cultures.json ist keine
                ok = None if not F.get("kultur") else (False if F.get("kultur_fest") else None)
                return [f"zusammengelegte Kultur, entstanden aus einer Gruppe mit {self.name('cultures', x)}", ok, []]
        if scope.startswith("ort:"):
            h = F.get(scope[4:])
            if k0 in ORT_FELD:
                feld, label = ORT_FELD[k0]
                return [f"{label} {self.nm(_ohne(x))}", None if h is None else h.get(feld) == _ohne(x), []]
        teile = k0.split(".")
        if teile[0] in ORT_SCOPE:
            feld, label = ORT_SCOPE[teile[0]]
            if len(teile) == 2 and teile[1] in ORT_FELD:
                kinder, ok = self.block({teile[1]: x}, "ort:" + feld)
            elif isinstance(x, dict):
                kinder, ok = self.block(x, "ort:" + feld)
            else:
                return [f"{k} = {x}", None, []]
            return [f"{label}:", ok, kinder]
        if k0 == "culture" and isinstance(x, dict):
            kinder, ok = self.block(x, "kultur")
            return ["Kultur:", ok, kinder]
        if k0 == "culture":
            return [f"Kultur {self.name('cultures', x)}", None if F.get("kultur") is None else _ohne(x) == F["kultur"], []]
        if k0 == "culture.language":
            return [f"Sprache der Kultur {self.name('languages', x)}",
                    None if F.get("sprache") is None else _ohne(x) == F["sprache"], []]
        if k0 == "religion" and isinstance(x, str):
            return [f"Religion {self.name('religions', x)}", None if F.get("religion") is None else _ohne(x) == F["religion"], []]
        if k0 == "religion.group":
            return [f"Religionsgruppe {self.name('religion_groups', x)}",
                    None if F.get("religionsgruppe") is None else _ohne(x) == F["religionsgruppe"], []]
        if k0 in ("has_or_had_tag", "tag", "original_tag") and isinstance(x, str):
            menge = {"has_or_had_tag": F.get("tags"), "tag": [F.get("tag")] if F.get("tag") else None,
                     "original_tag": [F.get("original_tag")] if F.get("original_tag") else None}[k0]
            text = {"has_or_had_tag": "Land ist oder war", "tag": "Land ist", "original_tag": "Ursprüngliches Land"}[k0]
            return [f"{text} {self.nm(x)} ({x})", None if menge is None else x in menge, []]
        if k0 == "has_dlc":
            d = F.get("dlcs")
            return [f"Erweiterung {x}", None if d is None else str(x).lower() in d, []]
        if k0 == "government_type":
            return [f"Regierungsform {self.name('government_types', x)}",
                    None if F.get("regierung") is None else _ohne(x) == F["regierung"], []]
        if k0 == "has_reform":
            r = F.get("reformen")
            return [f"Reform {self.name('government_reforms', x)}", None if r is None else _ohne(x) in r, []]
        if k0 == "has_unlocked_advance_trigger" and isinstance(x, dict) and isinstance(x.get("type"), str):
            e = F.get("erforscht")
            a = (self.vg("advances") or {}).get(x["type"]) or {}
            return [f"Fortschritt {a.get('name') or x['type']} erforscht", None if e is None else x["type"] in e, []]
        if k0 == "has_embraced_institution":
            i = F.get("institutionen")
            return [f"Institution {self.name('institution', x)} eingeführt", None if i is None else _ohne(x) in i, []]
        if k0 == "country_has_estate":
            s = F.get("staende")
            return [f"Land hat den Stand {self.name('estates', x)}", None if s is None else _ohne(x) in s, []]
        if k0 == "num_locations" and op in VERGLEICH and _num(x):
            n = F.get("orte")
            return [f"Zahl der Orte {op} {x}", None if n is None else VERGLEICH[op](n, x), []]
        return [f"{k} = {json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x} (nicht auswertbar)", None, []]


# ---------------------------------------------------------------- Stand des Spielers
def kosten(a, z_jetzt, S, einzigartig=(), gelernt=None):
    """Forschungskosten, nur wo Defines und Spielwerte sie gemeinsam belegen (Prüfung 30.10., Tooltips 31.10.):
      Fortschritt des laufenden oder eines späteren Zeitalters: Grundwert × (1 + AGE_RESEARCH_MODIFIER × Index des Zeitalters) –
      der Zuschlag je Zeitalter wird addiert, nicht vervielfacht. Grundwert BASE_RESEARCH_COST = 25, für Fortschritte nur eines
      Landes BASE_UNIQUE_RESEARCH_COST = 5. Belege:
        Zeitalter 1:                    25,00 (Walachei 1338: „Grundwert: 25“)
        Zeitalter 2, laufend:           25 × 1,15 = 28,75 (Holland 1350: „Fortschritt aus dem Zeitalter der Renaissance: +15.00%“)
        Zeitalter 3, im Zeitalter 1:    25 × 1,30 = 32,50 (Walachei, Tooltip „Operation“; vervielfacht wären es 33,06)
        einzigartig, Zeitalter 2:       5 × 1,15 = 5,75   (Walachei, Tooltip „Gründung der Kanzlei“)
      Zeitalter 4–6 nach derselben Regel (Zuschlag addiert, belegt bis Zeitalter 3).
      Fortschritt des vorigen Zeitalters im Zeitalter 2:      25 + PREVIOUS_AGE_REDUCTION = 17   (Holland 1345–1352: „Vorheriges
                                                              Zeitalter: -8.00“, 17,00)
    Nicht belegt (-> None, das Spiel zeigt die Kosten): Feld research_cost (Spieltext „Zusatzkosten für …“), sonstige Fortschritte
    älterer Zeitalter, einzigartige älterer Zeitalter.
    gelernt (kostenbelege, Selbstprüfung 30.10.): ein Fall, den eine Aufschlüsselung des Spiels belegt (Zeitalter des Fortschritts,
    gleiches/früheres Zeitalter, research_cost, einzigartig), gilt für alle Fortschritte mit demselben Fall; zeigt ein Beleg ab
    Zeitalter 3 die Rechenart des Zuschlags, gilt sie für alle Fortschritte des laufenden Zeitalters ohne Besonderheit."""
    D = S.get("kosten_defines") or {}
    base, mod, prev = D.get("BASE_RESEARCH_COST"), D.get("AGE_RESEARCH_MODIFIER"), D.get("PREVIOUS_AGE_REDUCTION")
    z = a.get("z")
    if not (_num(base) and _num(mod) and _num(prev)) or z is None or z_jetzt is None:
        return None
    einzig = bool(a.get("einzig") or a.get("n") in einzigartig)
    if gelernt:
        rel = "gleich" if z == z_jetzt else "vorher" if z < z_jetzt else None
        # belegte Rechenart vor dem einzelnen Fall: genauer (das Spiel zeigt Kosten auf zwei Stellen gerundet)
        modus = gelernt.get("modus")
        if modus and rel == "gleich" and a.get("rc") is None and not einzig and z >= 2:
            return round(base * ((1 + mod) ** z if modus == "vervielfacht" else 1 + mod * z), 4)
        werte = (gelernt.get("faelle") or {}).get(_fall(z, rel, a.get("rc"), einzig))
        if werte and len(werte) == 1:
            return werte[0]
    if a.get("rc") is not None:
        return None
    if z >= z_jetzt:
        b = D.get("BASE_UNIQUE_RESEARCH_COST") if einzig else base
        return round(b * (1 + mod * z), 4) if _num(b) else None
    if z_jetzt == 1 and z == 0 and not einzig:
        return round(base + prev, 4)
    return None


def _fall(z, rel, rc, einzig):
    """Schlüssel eines Kostenfalls: Zeitalter des Fortschritts, gleiches/früheres Zeitalter, research_cost, einzigartig."""
    return f"{z}|{rel}|{rc}|{int(bool(einzig))}"


# Kosten aus Tooltips des Forschungsfensters („Zu Forschungsreihe hinzufügen“ – x Forschungsfortschritt), Screenshots des
# Nutzers 31.10. (Walachei 1.4.6, Zeitalter der Traditionen): nur die Summe, keine Aufschlüsselung.
# (Land, Fortschritt, Index des laufenden Zeitalters, Kosten laut Spiel)
TOOLTIP_BELEGE = (("WAL", "surgery_advance", 0, 32.5), ("WAL", "boyar_regime", 0, 5.75))

KOSTEN_ZEILE = re.compile(r"^\s*(.+?):\s*([+-]?\d+(?:[.,]\d+)?)\s*(%?)\s*$")
KOSTEN_ART = (("Grundwert", "grund"), ("Vorheriges", "vorher"), ("Fortschritt aus dem Zeitalter", "zeitalter"),
              ("Zusatzkosten", "zusatz"), ("Einzigartig", "einzig"))


def kostenbelege(db, S):
    """Selbstprüfung der Forschungskosten (Nutzerwunsch 30.10.): jede laufende Forschung, die der Daten-Mod geschrieben hat (ab
    0.16 je Monat: Name, „Benötigt x von y“, Aufschlüsselung „Forschungskosten“ – Spieltexte RESEARCH_COST_TT,
    PREVIOUS_AGE_RESEARCH_COST, SPECIAL_RESEARCH_COST, COUNTRY_UNIQUE_RESEARCH_COST), dazu die Tooltip-Belege (TOOLTIP_BELEGE),
    gegen die Formel des Ratgebers. Dazu, was
    die Aufschlüsselungen über die offenen Teile verraten: Zuschlag je Zeitalter (ab Zeitalter 3 vervielfacht oder addiert? Define
    AGE_RESEARCH_MODIFIER „multiplied per age“), Feld research_cost („Zusatzkosten für …“ in Prozent?), einzigartige Fortschritte.
    Fälle (_fall) nur aus Belegen mit Grundwert = BASE_RESEARCH_COST und ohne unbekannte Zeilen; widersprechen sich Belege, gilt
    der Fall nicht (Regel des Ratgebers). Alle Länder und Partien der Datenbank – die Formel hängt nicht vom Land ab."""
    out = {"belege": [], "gelernt": {}, "faelle": {}, "modus": None}
    if db is None:
        return out
    rows = db.execute("SELECT tag, jahr, monat, schluessel, werte FROM monat_extra WHERE art='text' AND "
                      "(schluessel LIKE 'land:%:forsch_fortschritt_name' OR schluessel LIKE 'land:%:forsch_fortschritt_info' "
                      "OR schluessel LIKE 'land:%:forsch_kosten')").fetchall()
    je = {}
    for tag, j, m, k, w in rows:
        je.setdefault((tag, j, m), {})[k.rsplit(":", 1)[1]] = ((json.loads(w) or {}).get("text") or "").replace("\x15", "")
    A, D = S["fortschritte"], S.get("kosten_defines") or {}
    base, mod = D.get("BASE_RESEARCH_COST"), D.get("AGE_RESEARCH_MODIFIER")
    gesehen, faelle = {}, {}
    zuschlag, zusatz, einzig_w, andere = {}, [], [], set()
    for (tag, j, m), t in sorted(je.items()):
        name = (t.get("forsch_fortschritt_name") or "").strip()
        mm = re.search(r"Benötigt\s*([\d.]+)\s*von\s*([\d.]+)", t.get("forsch_fortschritt_info") or "")
        if not name or not mm:
            continue
        y = float(mm.group(2))
        if (tag, name, y) in gesehen:
            gesehen[(tag, name, y)]["bis"] = f"{j}.{m}"
            continue
        zeilen = []
        for z in (t.get("forsch_kosten") or "").split("\n"):
            mz = KOSTEN_ZEILE.match(z)
            if mz:
                label = mz.group(1).strip()
                art = next((a for p, a in KOSTEN_ART if label.startswith(p)), "andere")
                zeilen.append({"text": label, "wert": float(mz.group(2).replace(",", ".")), "prozent": mz.group(3) == "%",
                               "art": art})
        arten = {x["art"] for x in zeilen}
        # Zeitalter-Zeile nennt das Zeitalter des Fortschritts (Name wie in age): Zuschlag je Zeitalter
        z_zeile = next((x for x in zeilen if x["art"] == "zeitalter"), None)
        z_idx = next((i for i, za in enumerate(S["zeitalter"]) if z_zeile and za["name"] and za["name"] in z_zeile["text"]), None)
        kand = sorted(k for k, a in A.items() if a["n"] == name)
        if z_idx is not None and len(kand) > 1:
            kand = [k for k in kand if A[k].get("z") == z_idx] or kand
        key = kand[0] if kand else None
        a = A.get(key) or {}
        rel = "vorher" if "vorher" in arten else "gleich"
        einzig = "einzig" in arten or _einzig(a.get("pot"))
        z = a.get("z")
        formel = kosten({**a, "einzig": einzig}, z if rel == "gleich" or z is None else z + 1, S) if a else None
        b = {"tag": tag, "von": f"{j}.{m}", "bis": f"{j}.{m}", "name": name, "key": key, "mehrdeutig": len(kand) > 1,
             "zeitalter": z, "research_cost": a.get("rc"), "spiel": y, "zeilen": zeilen, "formel": formel,
             "vergleich": "gleich" if _num(formel) and abs(formel - y) < 0.01 else "abweichung" if _num(formel) else "offen"}
        gesehen[(tag, name, y)] = b
        out["belege"].append(b)
        if z_zeile and z_idx is not None:
            zuschlag.setdefault(z_idx, set()).add(z_zeile["wert"])
        for x in zeilen:
            if x["art"] == "zusatz":
                zusatz.append({"name": name, "research_cost": a.get("rc"), "prozent": x["wert"],
                               "passt": _num(a.get("rc")) and abs(x["wert"] - a["rc"] * 100) < 0.01})
            elif x["art"] == "einzig":
                einzig_w.append(x["wert"])
            elif x["art"] == "andere":
                andere.add(x["text"])
        grund = next((x["wert"] for x in zeilen if x["art"] == "grund"), None)
        if key and z is not None and grund == base and "andere" not in arten:
            faelle.setdefault(_fall(z, rel, a.get("rc"), einzig), set()).add(y)
    out["faelle"] = {k: sorted(v) for k, v in faelle.items()}
    # Rechenart des Zuschlags: ab Zeitalter 3 unterscheiden sich addiert (mod × n) und vervielfacht ((1 + mod)^n − 1)
    modus = set()
    for i, ws in zuschlag.items():
        if i >= 2 and _num(mod):
            for w in ws:
                modus.add("vervielfacht" if abs(w - 100 * ((1 + mod) ** i - 1)) < 0.01 else
                          "addiert" if abs(w - 100 * mod * i) < 0.01 else "anders")
    out["belege"].sort(key=lambda b: (b["tag"], [int(x) for x in b["von"].split(".")]))
    # Tooltip-Belege: nur die Summe; ab Zeitalter 3 (ohne research_cost, nicht einzigartig) zeigt sie die Rechenart des Zuschlags
    for tag, key, zj, y in TOOLTIP_BELEGE:
        a = A.get(key)
        if not a:
            continue
        einzig = _einzig(a.get("pot"))
        formel = kosten({**a, "einzig": einzig}, zj, S)
        out["belege"].append({"tag": tag, "von": "Tooltip", "bis": "Tooltip", "quelle": "tooltip", "name": a["n"], "key": key,
                              "mehrdeutig": False, "zeitalter": a.get("z"), "research_cost": a.get("rc"), "spiel": y, "zeilen": [],
                              "formel": formel, "einzig": einzig,
                              "vergleich": "gleich" if _num(formel) and abs(formel - y) < 0.01 else "abweichung" if _num(formel) else "offen"})
        i = a.get("z")
        if i is not None and i >= 2 and a.get("rc") is None and not einzig and _num(base) and _num(mod):
            modus.add("vervielfacht" if abs(y - base * (1 + mod) ** i) < 0.01 else "addiert" if abs(y - base * (1 + mod * i)) < 0.01
                      else "anders")
    out["modus"] = next(iter(modus)) if len(modus) == 1 and "anders" not in modus else None
    out["gelernt"] = {"zuschlag": {str(i): sorted(ws) for i, ws in sorted(zuschlag.items())},
                      "modus_belege": sorted(modus), "zusatz": zusatz, "einzig": sorted(set(einzig_w)), "andere": sorted(andere)}
    return out


def _einzig(pot):
    """Bedingung nennt ein Land (has_or_had_tag, tag, original_tag) -> einzigartig, Kosten nicht belegt."""
    return bool(re.search(r'"(has_or_had_tag|tag|original_tag)"', json.dumps(pot))) if pot else False


def laufend(db, tag):
    """Laufende Forschung laut Daten-Mod (ab 0.16): Name, „Benötigt x von y“, Kostenaufschlüsselung, Fertigdatum, Monat."""
    out = {}
    if db is None or not tag:
        return out
    for feld, k in (("forsch_fortschritt_name", "name"), ("forsch_fortschritt_info", "info"), ("forsch_kosten", "kosten_text"),
                    ("forsch_dauer", "dauer"), ("GetUniqueAdvancesInfo", "einzigartig_text")):
        row = db.execute("SELECT jahr, monat, werte FROM monat_extra WHERE tag=? AND art='text' AND schluessel=? "
                         "ORDER BY jahr DESC, monat DESC LIMIT 1", (tag, f"land:{tag}:{feld}")).fetchone()
        if row:
            out[k] = (json.loads(row[2]) or {}).get("text")
            out.setdefault("datum", f"{row[0]}.{row[1]}")
    m = re.search(r"Benötigt\s*([\d.]+)\s*von\s*([\d.]+)", out.get("info") or "")
    if m:
        out["fortschritt"], out["kosten"] = float(m.group(1)), float(m.group(2))
    row = db.execute("SELECT werte FROM monat_extra WHERE tag=? AND art='a.landmod' ORDER BY jahr DESC, monat DESC LIMIT 1",
                     (tag,)).fetchone()
    lm = json.loads(row[0]) if row else {}
    # Forschung je Monat = research_speed × (1 + research_speed_modifier) – geprüft 30.09. (Kachel Forschung, app.js)
    if _num(lm.get("research_speed")):
        out["je_monat"] = round(lm["research_speed"] * (1 + (lm.get("research_speed_modifier") or 0)), 4)
    return out


def stand(S, last, F, vg, names=None, live=None, gelernt=None):
    """Status je Fortschritt für unser Land: e erforscht, j jetzt erforschbar, v Voraussetzungen fehlen, s späteres Zeitalter,
    n nicht für uns, u unklar – dazu Bedingungen als Baum, Kosten (wo belegt), laufende Forschung."""
    A = S["fortschritte"]
    erforscht = {x.get("key") for x in (last.get("forschung") or {}).get("fortschritte") or []}
    z_idx = {a["key"]: i for i, a in enumerate(S["zeitalter"])}
    z_jetzt = z_idx.get(F.get("zeitalter"))
    live = live or {}
    einzig = [s.strip() for s in str(live.get("einzigartig_text") or "").split("\n")[1:] if s.strip()]
    B = Bedingung(F, vg, names)
    status, bed, kost, grund = {}, {}, {}, {}
    for k, a in A.items():
        baum = []
        teile = []
        if a.get("pot"):
            kinder, ok = B.block(a["pot"])
            baum.append(["Bedingung (potential):", ok, kinder])
            teile.append(ok)
        if a.get("g"):
            ok = None if not F.get("regierung") else a["g"] == F["regierung"]
            baum.append([f"Regierungsform {B.name('government_types', a['g'])} (government)", ok, []])
            teile.append(ok)
        if a.get("ct"):
            ok = None if not F.get("landestyp") else a["ct"] == F["landestyp"]
            baum.append([f"Landestyp {a['ct']} (country_type; wir: {F.get('landestyp') or 'unbekannt'})", ok, []])
            teile.append(ok)
        if a.get("fo"):
            age = S["zeitalter"][a["z"]]["key"] if a.get("z") is not None else None
            gew = (F.get("konzentration") or {}).get(age)
            spaeter = z_jetzt is not None and a.get("z") is not None and a["z"] > z_jetzt
            ok = (a["fo"] == gew) if gew else (True if spaeter else None)
            baum.append([f"Konzentration im Zeitalter auf „{KONZENTRATION.get(a['fo'], a['fo'])}“ (for; Spielstand: "
                         f"{KONZENTRATION.get(gew, gew) if gew else 'noch nicht gewählt' if spaeter else 'unbekannt'})", ok, []])
            teile.append(ok)
        fuer_uns = _und(teile)
        allow = None
        if a.get("allow"):
            kinder, allow = B.block(a["allow"])
            baum.append(["Erforschbar nur wenn (allow):", allow, kinder])
        if baum:
            bed[k] = baum
        fehlt = [r for r in a["r"] if r not in erforscht]
        if k in erforscht:
            st = "e"
        elif fuer_uns is False:
            st = "n"
        elif fuer_uns is None:
            st = "u"
        elif z_jetzt is not None and a.get("z") is not None and a["z"] > z_jetzt:
            st = "s"
        elif fehlt or allow is False:
            st = "v"
            if allow is False:
                grund[k] = "erst wenn: " + "; ".join(_falsch(kinder)) + " (allow)"
        elif allow is None and a.get("allow"):
            st = "u"
        else:
            st = "j"
        status[k] = st
        if st in ("j", "v", "u", "s"):                  # spätere Zeitalter: Kosten belegt (Tooltip Operation, 31.10.)
            c = kosten({**a, "einzig": _einzig(a.get("pot"))}, z_jetzt, S, einzig, gelernt)
            if c is not None:
                kost[k] = c
    # laufende Forschung: Name (Daten-Mod) -> Schlüssel unter den nicht erforschten
    lk = None
    if live.get("name"):
        kand = [k for k, a in A.items() if a["n"] == live["name"] and status.get(k) != "e"]
        kand.sort(key=lambda k: status.get(k) != "j")
        lk = kand[0] if kand else None
    return {"zeitalter_idx": z_jetzt, "status": status, "bed": bed, "kosten": kost, "grund": grund,
            "erforscht": len([k for k in A if status.get(k) == "e"]), "laufend": {**live, "key": lk},
            "einzigartig": einzig}


def _falsch(knoten):
    """Texte der nicht erfüllten Blätter eines Bedingungsbaums (für „erst wenn …“)."""
    out = []
    for text, ok, kinder in knoten:
        if ok is False:
            out += (_falsch(kinder) if kinder else []) or [text.rstrip(":")]
    return out


def weg(k, A, status):
    """Fehlende Vorgänger von k (ohne k) in Forschungsreihenfolge: erst die Wurzeln, dann tiefer (Stufe, Name)."""
    out, gesehen = [], set()

    def sammle(x):
        for r in A.get(x, {}).get("r") or []:
            if r in A and r not in gesehen and status.get(r) != "e":
                gesehen.add(r)
                sammle(r)
                out.append(r)
    sammle(k)
    return sorted(out, key=lambda x: (A[x].get("t") or 0, A[x]["n"]))


# ---------------------------------------------------------------- Vorschlag je Schwerpunkt
def vorschlaege(S, st, wp, gs=None, mt=None, wis_geb=None):
    """Bewertung der jetzt erforschbaren Fortschritte (und tieferer Ziele mit kurzem Weg) je Schwerpunkt des Wirtschaftsplans
    (wirtschaftsplan.build) nach PUNKTE/THEMA_REGEL. Jede Zeile nennt ihre Gründe konkret."""
    A, status, kost = S["fortschritte"], st["status"], st["kosten"]
    mt, gs, wis_geb = mt or {}, gs or {}, wis_geb or {}
    G, GEB = (wp or {}).get("gueter") or {}, (wp or {}).get("gebaeude") or {}
    je_monat = (st.get("laufend") or {}).get("je_monat")
    konst = S.get("konst") or {}

    def gname(g):
        return (G.get(g) or {}).get("name") or g

    def produziert(art):
        return {pm.get("produced") for pm in (wis_geb.get(art) or {}).get("pms") or [] if pm.get("produced")}
    out = {}
    for fk, F in ((wp or {}).get("fokusse") or {}).items():
        rang = {r["gut"]: (i + 1, r) for i, r in enumerate(F.get("gueter") or [])}
        fehlt = {r["gut"]: r for r in F.get("fehlen") or []}
        wirk = set(F.get("wirkung") or [])
        fmods = {}
        for m in F.get("modifikatoren") or []:
            g = "global_" + m[6:] if m.startswith("local_") else None
            if g and g in mt:
                fmods[g] = m
        regel = THEMA_REGEL.get(fk)
        muster = re.compile(regel[1]) if regel else None

        def gut_text(g):
            if g in rang:
                n, r = rang[g]
                return "Schwerpunkt-Gut" + (" (knapp im Heimatmarkt)" if r.get("knapp") else ""), n, r.get("knapp")
            return f"im Heimatmarkt nicht vorhanden (Anteil {_de((fehlt[g].get('anteil') or 0) * 100, 0)} %)", None, False

        def bewerte(k):
            a = A[k]
            gruende, punkte = [], 0
            for feld, label, x, name, link, extra in a["u"]:
                if feld == "unlock_building":
                    s = gs.get(x) or {}
                    if s.get("freischaltung") and s.get("fortschritt") is None:
                        continue                                  # schon über einen anderen, erforschten Fortschritt freigeschaltet
                    for g in sorted(produziert(x)):
                        if g in rang or g in fehlt:
                            t, n, knapp = gut_text(g)
                            p = 12 if n is None else max(10, 30 - 2 * (n - 1)) + (5 if knapp else 0)
                            gruende.append([p, f"schaltet {name} frei – stellt {gname(g)} her, {t}"])
                            punkte += p
                    if x in wirk:
                        mw = ", ".join(f"{(mt.get(m) or {}).get('name') or m} {wert(m, v, mt, konst)[0]}"
                                       for m, v in {**((GEB.get(x) or {}).get("wirkung") or {}),
                                                    **((GEB.get(x) or {}).get("wirkung_hauptstadt") or {})}.items())
                        gruende.append([20, f"schaltet {name} frei – Gebäude mit Schwerpunkt-Wirkung ({mw})"])
                        punkte += 20
                elif feld == "unlock_production_method" and extra and (extra in rang or extra in fehlt):
                    t, n, _ = gut_text(extra)
                    p = 12 if n is None else max(8, 20 - (n - 1))
                    gruende.append([p, f"schaltet Produktionsmethode {name} frei – stellt {gname(extra)} her, {t}"])
                    punkte += p
                elif feld == "unlock_unit" and fk in EINHEIT_PREFIX and isinstance(extra, str) \
                        and extra.startswith(EINHEIT_PREFIX[fk]):
                    gruende.append([20, f"schaltet Einheit {name} frei ({extra})"])
                    punkte += 20
                elif regel and feld in regel[2]:
                    gruende.append([8, f"schaltet {label} {name} frei – Thema {regel[0]}"])
                    punkte += 8
            for m, mname, txt, ri in a["w"] + [[m, n2, "ja", 1] for m, n2 in a["s"]]:
                if ri != 1:
                    continue                                      # nur Wirkungen in günstiger Richtung zählen
                mo = re.match(r"^global_(\w+)_output_modifier$", m)
                if mo and (mo.group(1) in rang or mo.group(1) in fehlt):
                    t, n, _ = gut_text(mo.group(1))
                    p = 12 if n is None else max(6, 15 - (n - 1))
                    gruende.append([p, f"Wirkung {mname} {txt} – {t}"])
                    punkte += p
                elif m in fmods:
                    gruende.append([15, f"Wirkung {mname} {txt} – landesweit wie die Schwerpunkt-Wirkung "
                                        f"„{(mt.get(fmods[m]) or {}).get('name') or fmods[m]}“ der Gebäude"])
                    punkte += 15
                elif muster and muster.match(m):
                    gruende.append([10, f"Wirkung {mname} {txt} – Thema {regel[0]}"])
                    punkte += 10
            gruende.sort(key=lambda g: -g[0])
            return punkte, gruende

        def zeile(k, punkte, gruende, w=None):
            c = kost.get(k)
            e = {"key": k, "name": A[k]["n"], "punkte": punkte, "gruende": [f"{t} ({p} Punkte)" for p, t in gruende],
                 "kosten": c, "rc": A[k].get("rc"), "monate": round(c / je_monat, 1) if c and je_monat else None,
                 "thema": A[k].get("th"), "zeitalter": A[k].get("z"),
                 "laeuft": k == (st.get("laufend") or {}).get("key")}
            if w is not None:
                schritte = w + [k]
                lf = st.get("laufend") or {}

                def rest(x):
                    """laufende Forschung: nur der Rest (Kosten − schon erforscht laut Daten-Mod, Prüfer 30.10.)"""
                    c = kost.get(x)
                    if x == lf.get("key") and _num(c) and _num(lf.get("fortschritt")):
                        return round(max(0.0, c - lf["fortschritt"]), 4)
                    return c
                summe = [rest(x) for x in schritte]
                e["weg"] = [{"key": x, "name": A[x]["n"], "kosten": kost.get(x), "status": status.get(x),
                             "gesperrt": (st.get("grund") or {}).get(x),
                             "rest": rest(x) if x == lf.get("key") else None} for x in schritte]
                e["weg_kosten"] = round(sum(summe), 4) if all(_num(x) for x in summe) else None
                e["weg_monate"] = round(e["weg_kosten"] / je_monat, 1) if e["weg_kosten"] and je_monat else None
            return e

        def ordnung(e):
            return (-e["punkte"], e["kosten"] if _num(e["kosten"]) else 1e9, A[e["key"]].get("t") or 0, e["name"])
        jetzt, ziele = [], []
        for k, a in A.items():
            s = status.get(k)
            if s not in ("j", "v"):
                continue
            punkte, gruende = bewerte(k)
            if punkte <= 0:
                continue
            if s == "j":
                jetzt.append(zeile(k, punkte, gruende))
            else:
                w = weg(k, A, status)
                if len(w) <= ZIEL_SCHRITTE and all(status.get(x) in ("j", "v") for x in w):
                    ziele.append(zeile(k, punkte, gruende, w))
        jetzt.sort(key=ordnung)
        # Ziele mit gesperrtem Schritt (Bedingung allow, z. B. Institution noch nicht eingeführt) nach hinten
        ziele.sort(key=lambda e: (any(w.get("gesperrt") for w in e["weg"]), -e["punkte"], len(e["weg"]),
                                  e["weg_kosten"] if _num(e["weg_kosten"]) else 1e9, e["name"]))
        out[fk] = {"name": F.get("name") or fk, "eintraege": jetzt[:TOP], "ziele": ziele[:TOP_ZIELE],
                   "anzahl": len(jetzt), "thema": regel[0] if regel else None}
    return out


REIHUNG = ("Reihung (Regel des Ratgebers): Summe der Punkte aller Gründe – " + "; ".join(PUNKTE.values())
           + ". Bei Gleichstand zuerst die billigeren (Forschungskosten, wo belegt), dann niedrigere Stufe im Baum. Ziele: noch nicht "
           f"erforschbar, höchstens {ZIEL_SCHRITTE} fehlende Voraussetzungen, alle für uns erforschbar; Wege mit gesperrtem Schritt "
           "(Bedingung „allow“, z. B. Institution noch nicht eingeführt) hinten, sonst nach Punkten, dann kürzerem Weg. "
           "Schwerpunkt-Güter, Gebäude mit Wirkung und Modifikatoren aus der Kachel Wirtschaftsplan.")


def fuer_series(db, last, voll, names=None, wis=None, wp=None, gs=None, live_ok=True):
    """Vorschläge je Schwerpunkt für die Kachel Forschung und die Empfehlungen (history.series): klein, ohne Statusliste.
    Ein Fehler hier soll die Seite nicht leeren -> {"fehler": …}."""
    if not voll or not last:
        return {}
    try:
        return _fuer_series(db, last, voll, names, wis, wp, gs, live_ok)
    except Exception as e:                           # neue Ansicht: lieber Meldung als leere Seite
        return {"fehler": f"{type(e).__name__}: {e}"}


def _fuer_series(db, last, voll, names, wis, wp, gs, live_ok=True):
    vg = _voll_get(voll)
    S = statisch(voll, names, vg)
    F = fakten(last, vg, wis, installierte_dlcs())
    # Daten-Mod nur für die aktive Partie des Landes (history.live_gehoert, Prüfer 30.10.); Kosten mit den Fällen der Selbstprüfung
    KB = kostenbelege(db, S)
    st = stand(S, last, F, vg, names, laufend(db, (last.get("meta") or {}).get("tag")) if live_ok else {}, KB)
    mt = vg("_modifikator_typen") or {}
    z = st["zeitalter_idx"]
    return {"datum": (last.get("meta") or {}).get("datum"), "zeitalter": S["zeitalter"][z]["name"] if z is not None else None,
            "laufend": st["laufend"], "fokusse": vorschlaege(S, st, wp, gs, mt, (wis or {}).get("gebaeude")),
            "regel": REIHUNG, "punkte": PUNKTE, "themen": {k: v[0] for k, v in THEMA_REGEL.items()}}


def api(db, pid, voll, names=None, wis=None):
    """Antwort /api/techbaum: alle Fortschritte (ohne die Rohbedingungen) und der Stand der Partie."""
    import zlib
    row =db.execute("SELECT json FROM momentaufnahmen WHERE partie_id=? ORDER BY jahr DESC LIMIT 1", (pid,)).fetchone()
    if not row or not voll:
        return None
    last = json.loads(zlib.decompress(row[0]))
    from .history import live_gehoert              # history importiert dieses Modul
    vg = _voll_get(voll)
    S = statisch(voll, names, vg)
    F = fakten(last, vg, wis, installierte_dlcs())
    tag = last["meta"].get("tag")
    KB = kostenbelege(db, S)                        # Selbstprüfung der Kosten (30.10.) – alle Partien der Datenbank
    st = stand(S, last, F, vg, names, laufend(db, tag) if live_gehoert(db, pid, tag) else {}, KB)
    # an die Seite ohne Rohbedingungen und leere Felder; Datei und Thema als Nummer in die Listen dateien/themen (~3 statt ~3,7 MB)
    dateien_ = sorted({a["dt"] for a in S["fortschritte"].values() if a.get("dt")})
    d_idx, t_idx = {d: i for i, d in enumerate(dateien_)}, {t: i for i, t in enumerate(S["themen"])}
    A = {}
    for k, a in S["fortschritte"].items():
        e = {f: v for f, v in a.items() if f not in ("pot", "allow", "dt", "th", "dlc") and v not in (None, [], "")}
        e["th"] = t_idx.get(a["th"], 0)
        if a.get("dt"):
            e["dt"] = d_idx[a["dt"]]
        A[k] = e
    meta = last["meta"]
    return {"format": FORMAT, "version": os.path.basename(voll), "datum": meta.get("datum"), "tag": meta.get("tag"),
            "land": meta.get("land"), "zeitalter": S["zeitalter"], "themen": S["themen"], "dateien": dateien_, "fortschritte": A,
            "kosten_defines": S["kosten_defines"], "status_namen": STATUS, "konzentration": KONZENTRATION,
            "fakten": F, "kostenpruefung": KB, **st}
