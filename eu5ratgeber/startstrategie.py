"""Kachel Startstrategie (Nutzerwunsch 31.10.): alles, was man am Anfang einer Partie einstellt – Kabinett, Gesetze mit ihren
Politlinien (Spiel: „Erlass bestimmter Politlinien“), Privilegien, Regierungsreformen, Gesellschaftswerte, erste Gebäude, erste
Forschung, Diplomatie und Bündnisvorschläge –, jeweils mit Bezug zum Schwerpunkt des Wirtschaftsplans (wirtschaftsplan.FOKUS).
Der Server rechnet alle Schwerpunkte, die Seite (web/startstrategie.js) zeigt den gewählten (store-Schlüssel rg_wp_fokus).

Quellen – nichts erfunden, eigene Regeln heißen „Regel des Ratgebers“ (REGELN, PUNKTE):
- Spieldateien (vollständiges Spielwissen data/spielwissen/<version>/<ordner>.json): cabinet_actions (ability, potential, allow,
  country/province/location_modifier, societal_values, years/months/days, allow_multiple, select_trigger, is_finished; readme:
  „all modifiers are multiplied by 1 + (effective ability + cabinet efficiency)*…“), laws (Politlinien = Blöcke im Gesetz mit
  country_modifier, years, estate_preferences, potential, allow, price; INJECT:-Einträge eingemischt), estate_privileges,
  government_reforms (government, age, major, societal_values, potential, allow), societal_values (left/right_modifier),
  advances (unlock_* = Freischaltung), prices, defines, rival_criteria, ai_diplochance (royal_marriage), scripted_relations
  (alliance), scripted_triggers (alliance_can_exist), script_values (alliance_upkeep_cost).
- Spielstand (neueste Momentaufnahme): Kabinett, Gesetze, Privilegien, Reformen, Gesellschaftswerte, Stände, Verbündete,
  Beziehungsverbesserungen (roh.beziehungen opinion_improvement).
- Daten-Mod, nur wenn er zu dieser Partie gehört (history.live_gehoert): freie Kabinetts-/Reformplätze, Wirksamkeit je Platz
  (GetEffectiveSkill, Tooltip GetEffectiveSkillTooltip), Personen mit Fähigkeiten, Stände (Zufriedenheit, Ziel, Macht),
  Gesellschaftswerte (sv_…) und ihre Verschiebung (monthly_towards_…), Politischer Einfluss, Diplomaten, Rivalen, Werte je Land.
- Vorhandene Pläne: Bauplan (wirtschaftsplan/bauplan), Fortschritts-Vorschlag (techbaum.vorschlaege), Nachbarn (Ampel),
  Ländergründung (Besitzer fehlender Orte) – nur verwiesen bzw. kurz übernommen, nicht neu gerechnet.

Belegt am Spiel (Daten-Mod Walachei 1339.11, Tooltip GetEffectiveSkillTooltip): Gesamtsteigerung einer Kabinettsaktion =
Summe aus Minister-Fähigkeit × 0,005 („72 durch Serban Caradja: +36.00%“, CABINET_ACTION_SKILL_MODIFIER = 0.005), Fähigkeit des
Herrschers/der Regentin × 0,005 („54 durch Regentin …: +27.00%“) und weiteren Posten („Herrscherrecht +5.00%“, „Kronmacht
+7.89%“) = 75,89 % = GetEffectiveSkill 0,7589; Wirkung = Grundwert × (1 + Gesamtsteigerung): Kontrollmaximum 10 % → „+17.58%“,
monatliche Kontrolle 1 % → „+1.75%“ (increase_control_province). Die readme nennt 0,05 – das Define 0,005 passt zum Tooltip.
"""
import json
import os
import re

from . import gruendung, pfade, techbaum, wiki, wirtschaftsplan

FORMAT = 3           # Aufbau des Zwischenspeichers _startstrategie_f<FORMAT>.json; erhöhen, wenn sich statisch() ändert

# ---------------------------------------------------------------- Bewertung je Schwerpunkt (Regel des Ratgebers)
# wie techbaum.vorschlaege: Punkte für Wirkungen in günstiger Richtung; ungünstige Wirkungen derselben Listen ziehen ihre Punkte
# ab (Nutzer 01.11.: „Leute ausweisen“ bekam 10 Punkte für Wachstum aus der Migrationsgeschwindigkeit, obwohl es die
# Migrationsanziehung um 2,0 senkt); ungünstige außerhalb der Listen stehen als Nachteil ohne Abzug
PUNKTE = {
    "gut_ausstoss": "15 − 1 je Rang (mind. 6), 12 wenn das Gut im Heimatmarkt fehlt – Ausstoß-Modifikator eines Schwerpunkt-Guts",
    "fokus_mod": "15 – landesweite Entsprechung der Schwerpunkt-Wirkung der Gebäude (local_x → global_x, Liste im Wirtschaftsplan)",
    "fokus_lokal": "15 – Schwerpunkt-Wirkung der Gebäude im gewählten Ort bzw. in der Provinz (Kabinettsaktion mit Ziel)",
    "thema_mod": "10 – Modifikator aus der Themenliste des Schwerpunkts (dieselbe Liste wie im Techbaum, techbaum.THEMA_REGEL)",
    "thema_lokal": "5 – örtliche Entsprechung eines Modifikators der Themenliste (wirkt nur im gewählten Ort bzw. in der Provinz)",
    "gesellschaft": "5 – schiebt einen Gesellschaftswert zum günstigen Pol des Schwerpunkts (Abschnitt Gesellschaftswerte)",
}
ZUFRIEDEN_MIN = 0.5      # Stand unter 50 % Zufriedenheit: nur mit Warnung vorschlagen
MACHT_MAX = 0.5          # Privileg hebt die Macht eines Stands, der schon so viel hat: nur mit Warnung (Regel des Ratgebers)
BEHALTEN_AB = 0.5        # Kabinettsaktion mit Ende (is_finished) ab diesem Fortschritt erst abschließen
MINISTER_MIN = 10        # Fähigkeitspunkte Vorsprung, ab denen ein anderer Minister vorgeschlagen wird (Austausch kostet Einfluss)
TOP_ACHSEN = 3           # Gesellschaftswerte je Schwerpunkt
TOP_BAU, TOP_FORSCHUNG, TOP_BUENDNIS, ERSTE = 5, 3, 3, 5
SCHIEBER = 6             # Einträge je Liste „was schiebt dorthin“
# Reihenfolge der Bereiche für „Erste Schritte“ (Regel des Ratgebers)
ERSTE_REIHE = ("kabinett", "forschung", "politlinie", "privileg", "bau", "buendnis", "reform", "rivale", "minister")
REGELN = {
    "bewertung": "Regel des Ratgebers: Punkte je Wirkung nach den Listen des Schwerpunkts (Wirtschaftsplan und Techbaum) – günstige "
                 "Richtung (Farbe des Modifikators im Spiel) zählt dazu, ungünstige aus denselben Listen ziehen ab; ungünstige "
                 "außerhalb der Listen stehen als Nachteil ohne Abzug da.",
    "erste_schritte": "Regel des Ratgebers: je Bereich der beste Vorschlag, in fester Reihenfolge – Kabinett (Aktion zuweisen kostet "
                      "nichts), Forschung, Politlinie und Privileg (je 20 Politischer Einfluss), Bau, Bündnis, Reform (nur mit freiem "
                      "Platz), Rivale (nur mit freiem Platz), zuletzt ein reiner Ministertausch; die ersten fünf stehen oben. "
                      "Vorschläge mit Warnung (ein Stand fiele unter 50 % Zufriedenheit oder hat schon 50 % Macht) kommen nicht "
                      "hinein. Der Politische Einfluss wird in dieser Reihenfolge abgezogen – reicht er nicht, steht „erst sparen“ dabei.",
    "abweichung": "Gezählt wird jede Einstellung, deren Vorschlag vom jetzigen Stand abweicht: Kabinettsplatz (Aktion oder Minister), "
                  "Politlinie, Privileg (höchstens eins je Stand), Reform (nur mit freiem Platz), Rivale (nur mit freiem Platz), "
                  "Bündnis (ein Vorschlag mit erfüllten Bedingungen). Gebäude und Forschung sind Pläne, keine Einstellungen.",
    "kabinett": f"Regel des Ratgebers: die Aktionen mit den meisten Punkten auf die Plätze; eine Aktion mit Ende ab "
                f"{int(BEHALTEN_AB * 100)} % Fortschritt erst abschließen, bei unbekanntem Fortschritt behalten; behalten, wenn der "
                f"Vorschlag nicht mehr Punkte hat. Aktionen mit Ziel: ob ein passendes Ziel da ist, prüft das Spiel (Stand als Ziel: "
                f"Zufriedenheit und Macht ausgewertet). Minister: "
                f"die Person mit der höchsten Fähigkeit der Aktion, ab {MINISTER_MIN} Punkten Vorsprung (Austausch kostet Einfluss).",
    "gesetze": "Regel des Ratgebers: je Gesetz die Politlinie mit den meisten Punkten; die jetzige bleibt bei Gleichstand. Fiele "
               f"dadurch ein Stand unter {int(ZUFRIEDEN_MIN * 100)} % Zielzufriedenheit (Wirkung neu − jetzt), steht das als Warnung "
               "dabei. Gesetze, die nicht änderbar (allow) oder gesperrt (locked) sind, bekommen keinen Vorschlag.",
    "privilegien": "Regel des Ratgebers: je Stand das mögliche Privileg mit den meisten Punkten. Sinkt dadurch die Zielzufriedenheit "
                   f"eines Stands unter {int(ZUFRIEDEN_MIN * 100)} % oder hebt es die Macht eines Stands, der schon "
                   f"{int(MACHT_MAX * 100)} % hat, steht das als Warnung dabei.",
    "reformen": "Regel des Ratgebers: die mögliche Reform mit den meisten Punkten – vorgeschlagen nur, wenn ein Platz frei ist.",
    "gesellschaft": f"Regel des Ratgebers: je Achse die Wirkung beider Pole bewerten; günstig ist der Pol mit mehr Punkten. Gezeigt werden "
                    f"die {TOP_ACHSEN} Achsen mit dem größten Vorsprung.",
    "buendnis": "Regel des Ratgebers: Kandidaten sind Länder mit Werten des Daten-Mods (Nachbarn, Großmächte, Rivalen …). Reihung: "
                "Bedingungen erfüllbar, Schutz (sie haben einen Kriegsgrund gegen uns), dann Stärkegewinn (ihre Landesstärke ÷ unser "
                "Verteidigungsbündnis). „Besser nicht“: Rivalen, Länder mit Orten für eine Gründung und Kriegsgelegenheiten (ein "
                "Bündnis verbietet den Krieg).",
    "rivalen": "Regel des Ratgebers: nur bei freiem Rivalenplatz; Kandidaten mit Kriegsgrund gegen uns oder schlechter Meinung von uns, "
               "nicht unter den Bündnis-Kandidaten.",
}

# Felder eines Gesetzes, die keine Politlinie sind (laws/readme.txt)
GESETZ_FELDER = {"potential", "allow", "locked", "custom_tags", "type", "law_category", "law_gov_group", "law_country_group",
                 "law_religion_group", "unique", "requires_vote", "has_levels", "no_vajrayana_policy", "show_tags_in_ui"}
FREI_FELDER = ("unlock_cabinet_action", "unlock_policy", "unlock_law", "unlock_estate_privilege", "unlock_government_reform")
PREISE = ("set_cabine_action", "replace_cabinet_member", "set_policy", "change_policy", "grant_privilege", "revoke_privilege",
          "remove_government_reform", "replace_rival", "send_diplomat")
DEFINES = {"NCountry": ("CABINET_ACTION_SKILL_MODIFIER", "SOCIAL_VALUE_REQUIREMENT_FOR_REFORM", "BASE_ESTATE_POWER_FROM_CABINET",
                        "GRANT_PRIVILEGE_SATISFACTION_IMPACT", "GRANT_PRIVILEGE_PENALTY_FOR_OTHERS_SCALE",
                        "REVOKE_PRIVILEGE_SATISFACTION_IMPACT", "SOCIETAL_VALUE_MIN", "SOCIETAL_VALUE_MAX"),
           "NDiplomacy": ("RIVAL_OPINION_THRESHOLD", "RIVAL_TARGET_MIN_RELATIVE_STRENGTH", "REMOVE_RIVAL_COOLDOWN",
                          "RANGE_MULTIPLIER_FOR_RIVALRY")}
# alliance_can_exist (scripted_triggers): Bedingungen in Worten, je mit dem Schlüssel, der in der Spieldatei stehen muss (Test)
BUENDNIS_BEDINGUNGEN = (
    ("opinion", "beide Seiten: Meinung voneinander mindestens 0"),
    ("is_rival_of", "keiner ist Rivale des anderen"),
    ("is_subject_of", "keiner ist Klientelland des anderen"),
    ("has_blocked_treaties", "keine gesperrten Verträge"),
    ("modifier:allowed_alliance", "beide dürfen Bündnisse schließen (Modifikator allowed_alliance)"),
    ("in_union_with", "keine Personalunion miteinander"),
    ("coalition", "keine Koalition gegeneinander"),
    ("is_rebel_country", "keine Aufständischen"),
    ("can_create_subject_alliance", "Regeln für Klientelländer (can_create_subject_alliance)"),
    ("is_hegemon", "nicht beide Hegemon"),
)
FAEHIGKEIT = {"adm": "Verwaltung", "dip": "Diplomatie", "mil": "Militär"}      # ability der Kabinettsaktionen
ZIELART = {"province": "Provinz", "location": "Ort", "area": "Gebiet", "region": "Region", "culture": "Kultur", "religion": "Religion",
           "estate": "Stand", "country": "Land", "character": "Person", "value": "Wert", "boolean": "Ja/Nein"}

F_OBERHERR = "oberherr"   # Fakt aus dem Feld gruendung der Momentaufnahme (Format 17): kein Oberherr -> is_subject_of = nein
# Beziehungen (Daten-Mod RG1D), deren Länder als Bündnispartner infrage kommen – „grossmacht“ allein (every_other_great_power, weltweit)
# nicht: ob sie in Diplomatiereichweite liegen, kennt der Ratgeber nicht (Regel des Ratgebers)
NAH = ("nachbar", "freund", "feind", "heirat", "union", "kriegsverbuendet", "kb_gegen_uns", "kb_ziel", "rivale", "hist_rivale")

_CACHE = {}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _liste(v):
    return v if isinstance(v, list) else [] if v is None else [v]


def _block(v):
    """potential/allow als Block; leere Liste ([] = leerer Block in der Spieldatei) -> None."""
    return v if isinstance(v, dict) and v else None


def _de(v, d=2):
    return techbaum._de(v, d)


def _pz(v, d=1):
    return _de(v * 100, d) + " %"


def _dauer(d):
    for f, viel, eins in (("years", "Jahre", "Jahr"), ("months", "Monate", "Monat"), ("weeks", "Wochen", "Woche"), ("days", "Tage", "Tag")):
        if _num(d.get(f)):
            return f"{_de(d[f], 1)} {eins if d[f] == 1 else viel}"
    return None


def _mods(block, ebene, mt, const, gruppe=0):
    """Wirkungen eines Modifikator-Blocks (auch Liste von Blöcken mit potential_trigger/scale) wie im Spiel:
    [schlüssel, name, anzeige, richtung, ebene, zahl, bedingt]. bedingt = Nummer des Blocks mit eigener Bedingung (0 = immer);
    Blöcke mit Bedingung gelten je nach Lage (appease_estate: je gewählten Stand einer) – bewerte() zählt davon nur den besten."""
    out = []
    for i, b in enumerate(_liste(block)):
        if not isinstance(b, dict):
            continue
        if _nie(b.get("potential_trigger")):
            continue                 # gilt nie (appease_estate: Vorauswahl „display only, never applies“, always = no)
        bedingt = gruppe + i + 1 if any(k in b for k in ("potential_trigger", "scale")) else 0
        for m, v in b.items():
            if m not in mt:
                continue
            txt, zahl, ri = techbaum.wert(m, v, mt, const)
            out.append([m, mt[m].get("name") or m, txt, ri, ebene, zahl, bedingt])
    return out


def _nie(t):
    """Bedingung, die nie gilt: always = no oben oder in einem custom_tooltip oben (Prüfer 31.10.: appease_estate)."""
    if not isinstance(t, dict):
        return False
    return t.get("always") == "no" or any(isinstance(x, dict) and x.get("always") == "no" for x in _liste(t.get("custom_tooltip")))


def _kosten(d, nm):
    if not isinstance(d, dict) or not d:
        return "kostenlos"
    return ", ".join(f"{nm(k)} {_de(v, 2)}" for k, v in d.items() if _num(v)) or "kostenlos"


def _pole(achse):
    l, r = achse.split("_vs_", 1)
    return l, r


# ---------------------------------------------------------------- feste Daten je Spielversion
def statisch(voll, vg, names=None):
    """Kataloge (Kabinettsaktionen, Gesetze mit Politlinien, Privilegien, Reformen, Gesellschaftswerte) mit Wirkungen wie im Spiel,
    Freischaltungen, Preise, Defines, Bündnis-, Rivalen- und Heiratsregeln – einmal je Spielversion (Speicher und
    data/spielwissen/<version>/_startstrategie_f<FORMAT>.json, nur mit Spielnamen auf die Platte)."""
    if voll in _CACHE:
        return _CACHE[voll]
    pfad = os.path.join(voll, f"_startstrategie_f{FORMAT}.json") if voll else None
    if pfad and os.path.exists(pfad):
        with open(pfad, encoding="utf-8") as f:
            _CACHE[voll] = json.load(f)
        return _CACHE[voll]
    nm = names or (lambda k: k)
    adv = vg("advances") or {}
    mt = vg("_modifikator_typen") or {}
    const = techbaum._konstanten(vg, adv)
    frei = {f: {} for f in FREI_FELDER}
    for k, e in adv.items():
        d = e.get("def") if isinstance(e, dict) else None
        if isinstance(d, dict):
            for f in FREI_FELDER:
                for x in _liste(d.get(f)):
                    if isinstance(x, str):
                        frei[f].setdefault(x, []).append(k)
    adv_namen = {a: (adv.get(a) or {}).get("name") or nm(a) for f in frei.values() for xs in f.values() for a in xs}

    def mods(d):
        return (_mods(d.get("country_modifier"), "land", mt, const) + _mods(d.get("province_modifier"), "provinz", mt, const)
                + _mods(d.get("location_modifier"), "ort", mt, const))

    K = {}
    for k, e in (vg("cabinet_actions") or {}).items():
        d = (e or {}).get("def")
        if not isinstance(d, dict):
            continue
        sel = [x for x in _liste(d.get("select_trigger")) if isinstance(x, dict) and x.get("looking_for_a")]
        ziel = [x["looking_for_a"] for x in sel]
        K[k] = {"n": e.get("name") or nm(k), "b": e.get("beschreibung"), "f": d.get("ability"), "w": mods(d),
                "mehrfach": d.get("allow_multiple") == "yes", "ziel": [ZIELART.get(z, z) for z in ziel], "zt": ziel,
                "z_en": sel[0].get("enabled") if len(sel) == 1 and isinstance(sel[0].get("enabled"), dict) else None,
                "z_vis": sel[0].get("visible") if len(sel) == 1 and isinstance(sel[0].get("visible"), dict) else None,
                "dauer": _dauer(d),
                "sv": d.get("societal_values") if _num(d.get("societal_values")) else None, "ende": "is_finished" in d,
                "effekt": any(x in d for x in ("on_activate", "on_fully_activated")),
                "pot": _block(d.get("potential")), "allow": _block(d.get("allow")), "frei": frei["unlock_cabinet_action"].get(k, [])}
    # Gesetze: INJECT:<gesetz> fügt Politlinien in ein bestehendes Gesetz ein
    roh = vg("laws") or {}
    gesetze = {k: {"name": e.get("name"), "b": e.get("beschreibung"), "def": dict((e or {}).get("def") or {})}
               for k, e in roh.items() if not k.startswith("INJECT:") and isinstance((e or {}).get("def"), dict)}
    for k, e in roh.items():
        if k.startswith("INJECT:") and k[7:] in gesetze:
            gesetze[k[7:]]["def"].update({pk: pv for pk, pv in ((e or {}).get("def") or {}).items() if isinstance(pv, dict)})
    preise = vg("prices") or {}
    G = {}
    for k, e in gesetze.items():
        d = e["def"]
        if d.get("type") not in (None, "country"):
            continue                                     # Gesetze internationaler Organisationen
        pol = {}
        for pk, pv in d.items():
            if pk in GESETZ_FELDER or not isinstance(pv, dict):
                continue
            pp = pv.get("price")
            pol[pk] = {"n": nm(pk), "w": mods(pv), "dauer": _dauer(pv),
                       "staende": [s for s in _liste(pv.get("estate_preferences")) if isinstance(s, str)],
                       "pot": _block(pv.get("potential")), "allow": _block(pv.get("allow")), "frei": frei["unlock_policy"].get(pk, []),
                       "einzig": pv.get("unique") == "yes",
                       "preis": _kosten((preise.get(pp) or {}).get("def"), nm) if isinstance(pp, str) else None}
        G[k] = {"n": e["name"] or nm(k), "kat": d.get("law_category"), "pot": _block(d.get("potential")),
                "allow": _block(d.get("allow")), "locked": _block(d.get("locked")), "frei": frei["unlock_law"].get(k, []),
                "pol": pol}
    PR = {}
    for k, e in (vg("estate_privileges") or {}).items():
        d = (e or {}).get("def")
        if isinstance(d, dict) and isinstance(d.get("estate"), str):
            PR[k] = {"n": e.get("name") or nm(k), "b": e.get("beschreibung"), "stand": d["estate"], "w": mods(d), "dauer": _dauer(d),
                     "pot": _block(d.get("potential")), "allow": _block(d.get("allow")), "frei": frei["unlock_estate_privilege"].get(k, [])}
    RF = {}
    for k, e in (vg("government_reforms") or {}).items():
        d = (e or {}).get("def")
        if not isinstance(d, dict) or k.startswith("INJECT:"):
            continue
        RF[k] = {"n": e.get("name") or nm(k), "b": e.get("beschreibung"), "gov": d.get("government"), "age": d.get("age"),
                 "major": d.get("major") == "yes", "einzig": d.get("unique") == "yes",
                 "sv": [str(x)[:-6] for x in _liste(d.get("societal_values")) if str(x).endswith("_focus")],
                 "w": mods(d), "dauer": _dauer(d), "pot": _block(d.get("potential")), "allow": _block(d.get("allow")),
                 "frei": frei["unlock_government_reform"].get(k, [])}
    for k, e in (vg("government_reforms") or {}).items():
        d = (e or {}).get("def")
        if k.startswith("INJECT:") and k[7:] in RF and isinstance(d, dict):    # Zusatzwirkungen (DLC) zu einer Reform
            RF[k[7:]]["w"] += _mods(d.get("country_modifier"), "land", mt, const, 100)
    AX = {}
    for k, e in (vg("societal_values") or {}).items():
        d = (e or {}).get("def")
        if not isinstance(d, dict) or "_vs_" not in k:
            continue
        l, r = _pole(k)
        AX[k] = {"n": e.get("name") or nm(k), "l": l, "r": r, "ln": nm(l + "_focus"), "rn": nm(r + "_focus"),
                 "wl": _mods(d.get("left_modifier"), "land", mt, const), "wr": _mods(d.get("right_modifier"), "land", mt, const),
                 "age": d.get("age")}
    defs = {}
    D = vg("defines") or {}
    for grp, keys in DEFINES.items():
        dd = (D.get(grp) or {}).get("def") if isinstance(D.get(grp), dict) else None
        for x in keys:
            defs[x] = dd.get(x) if isinstance(dd, dict) else None
    st = vg("scripted_triggers") or {}
    ace = json.dumps((st.get("alliance_can_exist") or {}).get("def") or {})
    rel = ((vg("scripted_relations") or {}).get("alliance") or {}).get("def") or {}
    rm = ((vg("ai_diplochance") or {}).get("royal_marriage") or {}).get("def") or {}
    rc = {}
    for t, e in (vg("rival_criteria") or {}).items():
        d = (e or {}).get("def") or {}
        rc[t] = {"n": e.get("name") or nm(t), "enabled": "enabled" in d, "ai_rule": "ai_rule" in d}
    S = {"format": FORMAT, "kabinett": K, "gesetze": G, "privilegien": PR, "reformen": RF, "achsen": AX, "frei": frei,
         "adv_namen": adv_namen, "zeitalter": [a for a, _ in sorted(((k, v) for k, v in (vg("age") or {}).items()
                                                                      if isinstance(v.get("def"), dict)),
                                                                     key=lambda kv: kv[1]["def"].get("year") or 0)],
         "preise": {k: {"name": (preise.get(k) or {}).get("name") or k, "text": _kosten((preise.get(k) or {}).get("def"), nm),
                        "zahl": ((preise.get(k) or {}).get("def") or {}).get("political_influence")
                        if isinstance((preise.get(k) or {}).get("def"), dict) else None}
                    for k in PREISE if k in preise},
         "defines": defs,
         "buendnis": {"bedingungen": [[k, t, k in ace] for k, t in BUENDNIS_BEDINGUNGEN],
                      "felder": {k: rel.get(k) for k in ("disallow_war", "uses_diplo_capacity", "military_access", "called_in_defensively",
                                                         "called_in_offensively", "break_on_war", "block_when_at_war",
                                                         "diplomatic_capacity_cost")},
                      # Annahme durch die KI: Faktoren wants_to_give_diplo_chance (dazu wants_to_give mit weiteren Posten)
                      "ki": {k: v for k, v in (rel.get("wants_to_give_diplo_chance") or {}).items() if _num(v)},
                      "unterhalt": _unterhalt_regeln(vg)},
         "heirat": {k: v for k, v in rm.items() if _num(v)}, "rivalen_regeln": rc}
    _CACHE[voll] = S
    if pfad and names is not None:
        pfade.atomar_schreiben(pfad, json.dumps(S, ensure_ascii=False).encode("utf-8"))
    return S


def _unterhalt_regeln(vg):
    """Bestandteile von alliance_upkeep_cost (script_values) nach ihrem desc-Schlüssel – Zahlen aus der Spieldatei."""
    d = ((vg("script_values") or {}).get("alliance_upkeep_cost") or {}).get("def") or {}
    out = {}
    for t in _liste(d.get("add")):
        if isinstance(t, dict) and t.get("desc"):
            sub = t.get("subtract") if isinstance(t.get("subtract"), dict) else {}
            dv = t.get("divide")
            out[t["desc"]] = {"value": t.get("value") if _num(t.get("value")) else None, "add": t.get("add") if _num(t.get("add")) else None,
                              "multiply": t.get("multiply"), "min": t.get("min"), "max": t.get("max"),
                              "divide_min": dv.get("min") if isinstance(dv, dict) else None,
                              "subtract_divide": sub.get("divide") if _num(sub.get("divide")) else None,
                              "subtract": t.get("subtract") if _num(t.get("subtract")) else None}
    for t in _liste(d.get("if")):
        a = t.get("add") if isinstance(t, dict) else None
        if isinstance(a, dict) and a.get("desc") and _num(a.get("value")):
            out[a["desc"]] = {"value": a["value"]}
    return out


def unterhalt(R, eco_wir, eco_sie, meinung_sie, grossmacht):
    """Diplomatiekapazität eines Bündnisses nach alliance_upkeep_cost (Spieldatei): Grundwert + Wirtschaftsverhältnis (ihre ÷ unsere
    Wirtschaftsgrundlage × Faktor, begrenzt) + (Wert − ihre Meinung von uns ÷ Teiler) + Großmacht-Zuschlag. ANNAHME: first = wir
    (der Unterhalt, den wir zahlen), second = sie. Blocksättigung (powerful_ally_weight) und Regionalmacht kennt der Ratgeber nicht
    – sie kämen dazu. -> (Summe oder None, [Bestandteile als Text])"""
    teile, summe = [], 0.0
    b = (R.get("UPKEEP_BASE_VALUE") or {}).get("value")
    e = R.get("RELATIVE_ECO_BASE") or {}
    o = R.get("UPKEEP_TARGET_OPINION") or {}
    if not _num(b) or not _num(e.get("multiply")) or not _num(o.get("add")) or not _num(o.get("subtract_divide")):
        return None, ["Aufbau von alliance_upkeep_cost unbekannt – nicht gerechnet"]
    summe += b
    teile.append(f"Grundwert {_de(b)}")
    if _num(eco_wir) and _num(eco_sie):
        x = eco_sie / max(eco_wir, e.get("divide_min") or 0) * e["multiply"] if max(eco_wir, e.get("divide_min") or 0) else None
        if x is not None:
            x = min(e["max"], x) if _num(e.get("max")) else x
            x = max(e["min"], x) if _num(e.get("min")) else x
            summe += x
            teile.append(f"Wirtschaft {_de(eco_sie, 1)} ÷ {_de(eco_wir, 1)} × {_de(e['multiply'])} = {_de(x)}"
                         + (f" (begrenzt auf {_de(e['min'])}–{_de(e['max'])})" if _num(e.get("min")) and _num(e.get("max")) else ""))
    else:
        return None, teile + ["Wirtschaftsgrundlage fehlt (Daten-Mod)"]
    if _num(meinung_sie):
        y = o["add"] - meinung_sie / o["subtract_divide"]
        summe += y
        teile.append(f"Meinung: {_de(o['add'])} − ({_de(meinung_sie, 0)} ÷ {_de(o['subtract_divide'], 0)}) = {_de(y)}")
    else:
        return None, teile + ["Meinung unbekannt"]
    g = (R.get("UPKEEP_THEY_GREAT_POWER") or {}).get("value")
    if grossmacht and _num(g):
        summe += g
        teile.append(f"Großmacht +{_de(g)}")
    teile.append("ohne Blocksättigung und Regionalmacht-Zuschlag (unbekannt)")
    return round(summe, 3), teile


# ---------------------------------------------------------------- Bedingungen
class Pruefer(gruendung.Pruefer):
    """gruendung.Pruefer mit den Bedingungen, die in Kabinettsaktionen, Politlinien, Privilegien und Reformen häufig sind:
    Freischaltung durch Fortschritte (has_unlocked_*_trigger), Erweiterungen (installiert im Spielordner, wie im Techbaum),
    Zahl der Orte, Institutionen, kulturelle Einheit (Daten-Mod), Aktion läuft schon (scope:is_active), or/and klein geschrieben."""

    def __init__(self, W, F, names, X):
        super().__init__(W, F, names)
        self.X = X
        self.aktiv = False

    def knoten(self, key, val, scope=("land",), neg=False):
        k = str(key)
        k0 = k[:-2] if k.endswith("?=") else k
        X = self.X
        if k0 in ("or", "and", "nor", "nand"):
            return super().knoten(k0.upper(), val, scope, neg)
        m = re.match(r"^has_unlocked_(cabinet_action|policy|law|estate_privilege|government_reform)_trigger$", k0)
        if m and isinstance(val, dict) and isinstance(val.get("type"), str):
            return self.frei_knoten("unlock_" + m.group(1), val["type"])
        if k0 == "has_dlc" and X.get("dlcs") is not None:
            name = gruendung._dlc_name(val) or str(val)
            return self.k(f"Erweiterung „{name}“ (installiert laut Spielordner)", str(val).lower() in X["dlcs"])
        m = re.match(r"^num_locations(>=|<=|>|<)?$", k0)
        if m and _num(val) and _num(X.get("orte")):
            op = m.group(1) or "="
            ok = techbaum.VERGLEICH[op](X["orte"], val) if op in techbaum.VERGLEICH else X["orte"] == val
            return self.k(f"Zahl der Orte {gruendung.VERGLEICH.get(op, op)} {_de(val, 0)}", ok, ist=str(X["orte"]))
        if k0 == "has_embraced_institution" and X.get("institutionen") is not None:
            i = gruendung._ohne(val, "institution")
            return self.k(f"Institution „{self.n(i)}“ eingeführt", i in set(X["institutionen"]))
        m = re.match(r"^(cultural|religious)_unity(>=|<=|>|<)$", k0)
        ist = X.get("einheit" if m and m.group(1) == "cultural" else "rel_einheit") if m else None
        if m and _num(val) and _num(ist):
            return self.k(f"{'Kulturelle' if m.group(1) == 'cultural' else 'Religiöse'} Einheit {gruendung.VERGLEICH[m.group(2)]} "
                          f"{_pz(val, 0)}", techbaum.VERGLEICH[m.group(2)](ist, val), ist=_pz(ist, 1))
        if k0.startswith("modifier:") and gruendung._jn(val) is not None and X.get("landmod"):
            mk = k0[9:]
            v = X["landmod"].get(mk)
            name = ((X.get("mt") or {}).get(mk) or {}).get("name") or mk
            j = gruendung._jn(val)
            return self.k(f"Landesmodifikator „{name}“ {'vorhanden' if j else 'nicht vorhanden'} (Daten-Mod)",
                          None if not _num(v) else (v > 0) == j, ist=_de(v) if _num(v) else None)
        if k0 in ("has_law", "has_policy") and isinstance(val, str) and X.get("gesetze") is not None:
            x = gruendung._ohne(gruendung._ohne(val, "law"), "policy")
            menge = set(X["gesetze"]) if k0 == "has_law" else set(X["gesetze"].values())
            return self.k(f"{'Gesetz' if k0 == 'has_law' else 'Politlinie'} „{self.n(x)}“ gilt", x in menge)
        m = re.match(r"^societal_value:(\w+?)(>=|<=|>|<)$", k0)
        if m and _num(val) and _num((X.get("sv") or {}).get(m.group(1))):
            v = X["sv"][m.group(1)]
            return self.k(f"Gesellschaftswert {self.n(m.group(1))} {gruendung.VERGLEICH[m.group(2)]} {_de(val, 0)}",
                          techbaum.VERGLEICH[m.group(2)](v, val), ist=_de(v, 0))
        if k0 == "is_subject_of" and F_OBERHERR in self.F and self.F.get("untertan") is False:
            return self.k(f"Ist Klientelland von {self.n(gruendung._ohne(val, 'c'))}", False)
        if k0 == "scope:is_active":
            j = gruendung._jn(val)
            return self.k("Aktion läuft bereits" if j else "Aktion läuft noch nicht", None if j is None else self.aktiv == j)
        return super().knoten(key, val, scope, neg)

    def frei_knoten(self, feld, item):
        adv = (self.X.get("frei") or {}).get(feld, {}).get(item) or []
        if not adv:
            return self.k("Freigeschaltet (nur durch Ereignis oder Effekt – kein Fortschritt schaltet es frei)", None)
        er = self.X.get("erforscht") or set()
        namen = " oder ".join(f"„{(self.X.get('adv_namen') or {}).get(a) or a}“" for a in adv)
        ok = any(a in er for a in adv)
        return self.k(f"Freigeschaltet durch Fortschritt {namen}", ok, techbaum=f"techbaum/{adv[0]}",
                      handlung=None if ok else f"Fortschritt {namen} erforschen", bereich="staat")


def _und(w):
    return gruendung._und(list(w))


def pruefe(P, e, aktiv=False, frei_feld=None, extra=()):
    """Status eines Eintrags: a aktiv (jetzt eingestellt), n nicht für uns (potential falsch), g gesperrt (allow oder Freischaltung
    falsch), u unklar (potential nicht auswertbar), v sichtbar, aber Wahl offen (potential erfüllt, allow/Freischaltung nicht
    auswertbar), m möglich (alles erfüllt); dazu der Bedingungsbaum (Knoten wie gruendung.Pruefer)."""
    P.aktiv = aktiv
    knoten = []
    pot = P.block(e["pot"]) if e.get("pot") else []
    pot_ok = _und(x["ok"] for x in pot) if pot else True
    if pot:
        knoten.append(P.k("Sichtbar für uns (potential):", pot_ok, kinder=pot, art="und"))
    al = P.block(e["allow"]) if e.get("allow") else []
    al_ok = _und(x["ok"] for x in al) if al else True
    if al:
        knoten.append(P.k("Wählbar (allow):", al_ok, kinder=al, art="und"))
    fr_ok = True
    if e.get("frei") and frei_feld:
        n = P.frei_knoten(frei_feld, e["_key"]) if e.get("_key") else None
        if n:
            knoten.append(n)
            fr_ok = n["ok"]
    sonst = list(extra)
    knoten += sonst
    rest = _und([al_ok, fr_ok] + [x["ok"] for x in sonst])
    if aktiv:
        st = "a"
    elif pot_ok is False:
        st = "n"
    elif rest is False:
        st = "g"
    elif pot_ok is None:
        st = "u"
    elif rest is None:
        st = "v"
    else:
        st = "m"
    return st, knoten


# ---------------------------------------------------------------- Bewertung
def fokus_kontext(fk, wp=None, mt=None):
    """Listen eines Schwerpunkts: Themenliste (techbaum.THEMA_REGEL), Schwerpunkt-Wirkungen der Gebäude (wirtschaftsplan.FOKUS[k][3])
    und ihre landesweite Entsprechung, Rang der Schwerpunkt-Güter (Bedarfstabelle des Wirtschaftsplans)."""
    regel = techbaum.THEMA_REGEL.get(fk)
    mt = mt or {}
    lokal = set((wirtschaftsplan.FOKUS.get(fk) or (None, None, None, ()))[3])
    F = ((wp or {}).get("fokusse") or {}).get(fk) or {}
    G = (wp or {}).get("gueter") or {}
    return {"fk": fk, "thema": regel[0] if regel else None, "muster": re.compile(regel[1]) if regel else None, "lokal": lokal,
            "glob": {"global_" + m[6:]: m for m in lokal if m.startswith("local_") and "global_" + m[6:] in mt},
            "mt": mt, "rang": {r["gut"]: i + 1 for i, r in enumerate(F.get("gueter") or [])},
            "fehlt": {r["gut"] for r in F.get("fehlen") or []}, "gutname": {g: (x or {}).get("name") or g for g, x in G.items()}}


AUSSTOSS = re.compile(r"^global_(\w+)_output_modifier$")


def bewerte(w, C, guenstig=None, unguenstig=None):
    """Punkte, Gründe [[punkte, text, art]] (art: direkt / gesellschaft) und Nachteile [text] einer Wirkungsliste für den
    Schwerpunkt C (fokus_kontext).
    guenstig/unguenstig: {pol: Name des günstigen Pols} der wichtigsten Gesellschaftswerte."""
    p, gr, na = 0, [], []
    gruppen = {}
    for m, mn, txt, ri, ebene, zahl, bedingt in w:
        t = f"{mn} {txt}" + (" (im Ziel)" if ebene != "land" else "") + (" (nur unter Bedingung)" if bedingt else "")
        if m.startswith("monthly_towards_"):
            pol = m[16:]
            if guenstig and pol in guenstig and (not _num(zahl) or zahl > 0):
                p += 5
                gr.append([5, f"{t} – „{guenstig[pol]}“ ist für den Schwerpunkt günstig", "gesellschaft"])
            elif unguenstig and pol in unguenstig and (not _num(zahl) or zahl > 0):
                na.append(f"{t} – schiebt weg von „{unguenstig[pol]}“")
            continue
        treffer = None
        mo = AUSSTOSS.match(m)
        if mo and (mo.group(1) in C["rang"] or mo.group(1) in C["fehlt"]):
            n = C["rang"].get(mo.group(1))
            g = C["gutname"].get(mo.group(1)) or mo.group(1)
            treffer = (12 if n is None else max(6, 15 - (n - 1)),
                       f"Schwerpunkt-Gut {g}" + ("" if n else ", im Heimatmarkt nicht vorhanden"))
        elif m in C["glob"]:
            treffer = (15, f"landesweit wie die Schwerpunkt-Wirkung „{(C['mt'].get(C['glob'][m]) or {}).get('name') or C['glob'][m]}“")
        elif m in C["lokal"]:
            treffer = (15, "Schwerpunkt-Wirkung der Gebäude (Wirtschaftsplan)")
        elif C["muster"] and C["muster"].match(m):
            treffer = (10, f"Thema {C['thema']}")
        elif m.startswith("local_") and C["muster"] and C["muster"].match("global_" + m[6:]):
            treffer = (5, f"Thema {C['thema']}, nur im Ziel")
        if not treffer:
            if ri == -1:
                na.append(f"{t} – ungünstig")          # außerhalb der Listen: kein Abzug, aber genannt (Prüfer 31.10.)
            continue
        if ri == 1 and bedingt:
            gruppen.setdefault(bedingt, []).append([treffer[0], f"{t} – {treffer[1]}", "direkt"])
        elif ri == 1:
            p += treffer[0]
            gr.append([treffer[0], f"{t} – {treffer[1]}", "direkt"])
        elif ri == -1:
            if bedingt:
                na.append(f"{t} – ungünstig ({treffer[1]})")
            else:                                    # ungünstig in den Listen des Schwerpunkts: Abzug (Nutzer 01.11.)
                p -= treffer[0]
                na.append(f"{t} – ungünstig ({treffer[1]}, −{treffer[0]} Punkte)")
    if gruppen:                                  # Blöcke mit eigener Bedingung: nur der beste zählt
        beste = max(gruppen.values(), key=lambda g: sum(x[0] for x in g))
        p += sum(x[0] for x in beste)
        gr += beste
    gr.sort(key=lambda g: -g[0])
    return p, gr, na


def achsen_fokus(S, aktive, C):
    """Günstiger Pol je aktiver Achse für den Schwerpunkt: [{achse, seite, vorsprung, punkte, gruende}], größter Vorsprung zuerst."""
    out = []
    for ak in aktive:
        a = S["achsen"].get(ak)
        if not a:
            continue
        pl, gl, _ = bewerte(a["wl"], C)
        pr, grr, _ = bewerte(a["wr"], C)
        if pl == pr:
            continue
        seite = "l" if pl > pr else "r"
        out.append({"achse": ak, "seite": seite, "pol": a[seite], "pol_name": a[seite + "n"],
                    "gegen": a["r" if seite == "l" else "l"], "gegen_name": a[("r" if seite == "l" else "l") + "n"],
                    "vorsprung": abs(pl - pr), "punkte": {"l": pl, "r": pr},
                    "gruende": _texte(gl if seite == "l" else grr)})
    out.sort(key=lambda x: (-x["vorsprung"], x["achse"]))
    return out


def gesellschaft_stand(ak, wert, landmod):
    """Stand einer Achse: Wert (−100 links … +100 rechts), jetziger Pol (pol_jetzt), Verschiebung je Monat = monthly_towards_<rechts> −
    monthly_towards_<links> (MECHANIK.md, geprüft 30.09.), Grenze = 100 × Verschiebung."""
    l, r = _pole(ak)
    a, b = (landmod or {}).get("monthly_towards_" + r), (landmod or {}).get("monthly_towards_" + l)
    drift = round(a - b, 4) if _num(a) and _num(b) else None
    return {"wert": wert, "pol_jetzt": (r if wert > 0 else l if wert < 0 else None) if _num(wert) else None,
            "drift": drift, "richtung": (r if drift > 0 else l) if _num(drift) and abs(drift) >= 0.005 else None,
            "grenze": round(100 * abs(drift), 2) if _num(drift) and abs(drift) >= 0.005 else None}


def pol_wert(ak, pol, wert):
    """Wert einer Achse in Richtung eines Pols (links = −Wert, rechts = +Wert)."""
    l, r = _pole(ak)
    return None if not _num(wert) else (-wert if pol == l else wert if pol == r else None)


VORSCHLAGBAR = ("m", "v", "a")    # Status, aus denen ein Vorschlag kommen darf (u: potential offen – vielleicht gar nicht für uns)


def direkt(v):
    """Hat eine Bewertung (punkte, gruende, nachteile) Punkte aus einer direkten Wirkung – nicht nur aus Gesellschaftswerten?
    Regel des Ratgebers: allein für das Verschieben eines Gesellschaftswerts wird nichts vorgeschlagen."""
    return bool(v) and any(len(g) < 3 or g[2] != "gesellschaft" for g in v[1])


def _texte(gr):
    return [g[1] for g in gr]


# ---------------------------------------------------------------- Kabinett
def kabinett_vorschlag(plaetze, K, status, P_, personen=None, behalten=None, faktor=0.005):
    """Aktion und Minister je Platz (REGELN["kabinett"]). plaetze: [{platz, aktion, person, adm, dip, mil, fortschritt}] (None =
    freier Platz), P_: {aktion: (punkte, gruende, nachteile)}, status: {aktion: Status}. personen: [{name, adm, dip, mil,
    im_kabinett}] (Daten-Mod) oder None. faktor = CABINET_ACTION_SKILL_MODIFIER (Steigerung je Fähigkeitspunkt)."""
    behalten = BEHALTEN_AB if behalten is None else behalten

    def pkt(k):
        return (P_.get(k) or (0,))[0] if k else -1
    # vorschlagbar: alle Bedingungen erfüllt (m), sichtbar mit offener Wahl (v) oder schon eingestellt (a), mit direkter Wirkung
    rang = sorted([k for k, s in status.items() if s in VORSCHLAGBAR and pkt(k) > 0 and direkt(P_.get(k))],
                  key=lambda k: (-pkt(k), status[k] not in ("m", "a"), (K.get(k) or {}).get("n") or k))
    out = [{"platz": p.get("platz"), "jetzt": p, "vorschlag": None, "grund": None} for p in plaetze]
    belegt = set()
    for s in out:
        j = s["jetzt"]
        if j.get("aktion") and (K.get(j["aktion"]) or {}).get("ende"):
            if _num(j.get("fortschritt")) and j["fortschritt"] >= behalten:
                s["vorschlag"], s["grund"] = j["aktion"], f"erst abschließen ({_pz(j['fortschritt'], 0)} erreicht)"
                belegt.add(j["aktion"])
            elif not _num(j.get("fortschritt")):     # dreiwertig: unbekannt ist nicht „unter 50 %“ (Prüfer 31.10.)
                s["vorschlag"], s["grund"] = j["aktion"], "behalten – Aktion mit Ende, Fortschritt unbekannt (im Spiel prüfen)"
                belegt.add(j["aktion"])
    rest = [s for s in out if not s["vorschlag"]]
    wunsch = [k for k in rang if k not in belegt][:len(rest)]
    for s in rest:
        a = s["jetzt"].get("aktion")
        if a and a in wunsch:
            s["vorschlag"], s["grund"] = a, "behalten – gehört zu den besten Aktionen"
            wunsch.remove(a)
            belegt.add(a)
    for s in sorted([s for s in rest if not s["vorschlag"]], key=lambda s: pkt(s["jetzt"].get("aktion"))):
        a = s["jetzt"].get("aktion")
        if wunsch and pkt(wunsch[0]) > pkt(a):
            s["vorschlag"] = wunsch.pop(0)
            s["grund"] = f"mehr Punkte ({pkt(s['vorschlag'])} statt {max(0, pkt(a))})" if a else "freier Platz"
        else:
            s["vorschlag"], s["grund"] = a, "behalten – kein besserer Vorschlag" if a else "kein Vorschlag"
    # Minister: höchste Fähigkeit der Aktion unter den freien Personen – erst die Plätze ohne Person, dann der größte Vorsprung
    vergeben = {(x["jetzt"].get("adm"), x["jetzt"].get("dip"), x["jetzt"].get("mil")) for x in out if x["jetzt"].get("person")}
    for s in out:
        s["abweichung"] = bool(s["vorschlag"]) and s["vorschlag"] != s["jetzt"].get("aktion")
        s["faehigkeit"] = (K.get(s["vorschlag"]) or {}).get("f") if s["vorschlag"] else None
        s["minister"] = None

    def bester(s):
        f = s["faehigkeit"]
        frei = [p for p in personen or [] if not p.get("im_kabinett") and _num(p.get(f))
                and (p.get("adm"), p.get("dip"), p.get("mil")) not in vergeben] if f else []
        if not frei:
            return None, None
        b = max(frei, key=lambda p: (p[f], p.get("name") or ""))
        j = s["jetzt"].get(f)
        return b, b[f] - (j if _num(j) else 0)
    offen = [s for s in out if s["faehigkeit"]]
    while offen and personen is not None:
        kand = [(not s["jetzt"].get("person"), v, s, b) for s in offen for b, v in [bester(s)] if b is not None
                and (not s["jetzt"].get("person") or v >= MINISTER_MIN)]
        if not kand:
            break
        _, v, s, b = max(kand, key=lambda x: (x[0], x[1], -out.index(x[2])))
        f = s["faehigkeit"]
        s["minister"] = {"name": b.get("name"), "wert": b[f], "jetzt": s["jetzt"].get(f), "vorsprung": v, "mehr": round(v * faktor, 4)}
        vergeben.add((b.get("adm"), b.get("dip"), b.get("mil")))
        if s["jetzt"].get("person"):
            s["abweichung"] = True
        offen.remove(s)
    return out


# ---------------------------------------------------------------- Erste Schritte und Abweichungen
def erste_schritte(vorschlaege, n=ERSTE):
    """Die ersten n Handlungen: je Bereich (ERSTE_REIHE) der erste Vorschlag, in dieser Reihenfolge (REGELN["erste_schritte"]).
    vorschlaege: {bereich: [schritt, …]} – Schritt = {text, warum, link, kosten}."""
    out = []
    for b in ERSTE_REIHE:
        xs = [x for x in vorschlaege.get(b) or [] if x]
        if xs:
            out.append({**xs[0], "bereich": b})
        if len(out) >= n:
            break
    return out


def einfluss_rechnen(schritte, pi):
    """Politischen Einfluss der ersten Schritte in ihrer Reihenfolge abziehen (Regel des Ratgebers, Prüfer 31.10.): reicht der
    Bestand nicht, „erst sparen“ – auch für die folgenden Schritte mit Preis. Ohne bekannten Bestand bleibt nur der Preis."""
    rest, sparen = (pi if _num(pi) else None), False
    for x in schritte:
        z = x.pop("einfluss", None)
        if not _num(z) or z <= 0 or rest is None:
            continue
        if not sparen and rest >= z:
            rest -= z
            x["kosten"] = f"{x.get('kosten') or ''} – danach {_de(rest, 1)} übrig".lstrip(" –")
        else:
            x["kosten"] = (f"{x.get('kosten') or ''} – erst sparen: " + (f"{_de(rest, 1)} da, {_de(z - rest, 1)} fehlen"
                                                                      if not sparen else "nach dem Schritt davor")).lstrip(" –")
            x["sparen"], sparen = True, True
    return schritte


def abweichungen(F):
    """Zähler je Bereich (REGELN["abweichung"]) aus den Vorschlägen eines Schwerpunkts."""
    z = {"kabinett": sum(1 for s in F.get("kabinett") or [] if s.get("abweichung")),
         "gesetze": sum(1 for g in F.get("gesetze") or [] if g.get("abweichung")),
         "privilegien": sum(1 for g in F.get("privilegien") or [] if g.get("abweichung")),
         "reformen": 1 if (F.get("reform") or {}).get("abweichung") else 0,
         "rivalen": 1 if (F.get("rivale") or {}).get("abweichung") else 0,
         "buendnis": 1 if (F.get("buendnis") or {}).get("abweichung") else 0}
    z["summe"] = sum(z.values())
    return z


# ---------------------------------------------------------------- Daten-Mod
def live_daten(db, tag, ld=None, lv=None):
    """Werte des Daten-Mods für die Kachel (neuester Monat je Art) – nur aufrufen, wenn er zur Partie gehört."""
    from . import empfehlungen                     # spät: empfehlungen bindet history ein
    land, datum = empfehlungen._neueste(db, tag, "a.land")
    kab = empfehlungen._neueste(db, tag, "a.kabinett")[0]
    fremd = empfehlungen._neueste(db, tag, "a.fremd")[0]
    return {"datum": datum, "land": next(iter(land.values()), {}),
            "landmod": next(iter(empfehlungen._neueste(db, tag, "a.landmod")[0].values()), {}),
            "kabinett": kab, "kabinett_kurz": (ld or {}).get("kabinett") or [],
            "personen": empfehlungen._neueste(db, tag, "a.person")[0], "staende": empfehlungen._neueste(db, tag, "a.stand")[0],
            "orte": empfehlungen._neueste(db, tag, "a.ort")[0],
            "fremd_eco": {t: v.get("GetEconomicalBase") for t, v in fremd.items() if _num(v.get("GetEconomicalBase"))},
            "diplomatie": (ld or {}).get("diplomatie") or [], "monat": (lv or [{}])[-1] if lv else {},
            "skill_texte": {i: empfehlungen._text(db, tag, "kabinett", i, "GetEffectiveSkillTooltip") for i in kab}}


# ---------------------------------------------------------------- Hauptteil
def fuer_series(db, last, voll, vg, names=None, wp=None, tv=None, nb=None, gr=None, ld=None, lv=None, live_ok=False):
    """Aufruf aus history.series: Daten-Mod nur, wenn er zur Partie gehört (live_ok = history.live_gehoert). Jeder Fehler – auch
    beim Lesen des Daten-Mods – endet als {"fehler": …}, series() läuft weiter."""
    if not last or not vg:
        return None
    try:
        live = live_daten(db, (last.get("meta") or {}).get("tag"), ld, lv) if live_ok else None
    except Exception as e:                       # noqa: BLE001
        return {"fehler": f"Daten-Mod: {type(e).__name__}: {e}"}
    return build(last, voll, vg, names, wp, tv, nb, gr, live)


def build(last, voll, vg, names=None, wp=None, tv=None, nb=None, gr=None, live=None):
    """Daten der Kachel Startstrategie (history.series). Ein Fehler hier darf die übrige Seite nicht verhindern -> {"fehler": …}."""
    if not last or not vg:
        return None
    try:
        return _build(last, voll, vg, names, wp, tv, nb, gr, live)
    except Exception as e:                       # noqa: BLE001
        return {"fehler": f"{type(e).__name__}: {e}"}


def _build(last, voll, vg, names, wp, tv, nb, gr, live):
    nm = names or (lambda k: k)
    S = statisch(voll, vg, names)
    live = live or {}
    L, LM, MON = live.get("land") or {}, live.get("landmod") or {}, live.get("monat") or {}
    mt = vg("_modifikator_typen") or {}
    W = gruendung.Wissen(vg)
    F = gruendung.fakten_momentaufnahme(last)
    feld = last.get("gruendung") if isinstance(last.get("gruendung"), dict) and "zusatz" in last.get("gruendung") else None
    if feld:
        F.update(feld["zusatz"])
    sm = {k[6:]: v for k, v in MON.items() if k.startswith("power_") and k.endswith("_estate") and _num(v)}
    if sm:
        F["stand_macht"] = sm
    if _num(L.get("dip_IsAtWar")):
        F["krieg"] = L["dip_IsAtWar"] > 0
    erforscht = set(F.get("fortschritte") or [])
    gs = last.get("gesellschaft") or {}
    sv = {ak: (MON.get("sv_" + ak) if _num(MON.get("sv_" + ak)) else gs.get(ak)) for ak in gs if ak in S["achsen"]}
    X = {"frei": S["frei"], "erforscht": erforscht, "adv_namen": S["adv_namen"], "dlcs": techbaum.installierte_dlcs(),
         "landmod": LM or None, "mt": mt, "gesetze": last.get("gesetze") if isinstance(last.get("gesetze"), dict) else None,
         "sv": sv, "rel_einheit": L.get("GetReligiousUnity"),
         "orte": len(last.get("orte") or []), "institutionen": (last.get("forschung") or {}).get("institutionen"),
         "einheit": L.get("GetCulturalUnity")}
    P = Pruefer(W, F, nm, X)
    meta = last.get("meta") or {}
    zeit = S["zeitalter"]
    z_jetzt = zeit.index(meta["zeitalter"]) if meta.get("zeitalter") in zeit else None
    pi = L.get("political_influence") if _num(L.get("political_influence")) else MON.get("political_influence")

    def wiki_o(ordner, k):
        return P.wiki_ordner(ordner, k)

    # ---- Gesellschaftswerte: aktive Achsen (Spielstand; −999 = nicht aktiv), Wert live vor Spielstand (sv oben)
    achsen = [{"key": ak, "n": S["achsen"][ak]["n"], "l": S["achsen"][ak]["l"], "r": S["achsen"][ak]["r"],
               "ln": S["achsen"][ak]["ln"], "rn": S["achsen"][ak]["rn"], "wl": S["achsen"][ak]["wl"], "wr": S["achsen"][ak]["wr"],
               "wiki": wiki_o("societal_values", ak), **gesellschaft_stand(ak, sv[ak], LM)} for ak in sv]

    # ---- Privilegien unserer Stände
    staende_jetzt = [e for e in last.get("staende") or [] if e.get("stand")]
    unsere = {e["stand"] for e in staende_jetzt}
    gew = set(p for p in last.get("privilegien") or [] if isinstance(p, str))
    priv_status, priv_bed = {}, {}
    for pk, e in S["privilegien"].items():
        if e["stand"] not in unsere:
            continue
        st, bed = pruefe(P, {**e, "_key": pk}, pk in gew, "unlock_estate_privilege")
        priv_status[pk] = st
        if st != "n":
            priv_bed[pk] = bed
    lst = live.get("staende") or {}
    staende = []
    for e in staende_jetzt:
        s = e["stand"]
        x = lst.get(s) or {}
        staende.append({"stand": s, "name": e.get("name") or nm(s),
                        "zufriedenheit": x.get("satisfaction") if _num(x.get("satisfaction")) else e.get("satisfaction"),
                        "ziel": x.get("target_satisfaction") if _num(x.get("target_satisfaction")) else None,
                        "macht": sm.get(s) if _num(sm.get(s)) else (e.get("mod") or {}).get("power"),
                        "privilegien": x.get("num_privileges"), "moeglich": x.get("num_possible_privileges"),
                        "gewaehrt": sorted((p for p in gew if (S["privilegien"].get(p) or {}).get("stand") == s),
                                           key=lambda p: S["privilegien"][p]["n"])})

    # ---- Provinzen mit unseren Orten (Ziele von Kabinettsaktionen): Wohlstand, Kontrolle, Hauptstadt je Ort – Daten-Mod (a.ort,
    # monatlich) vor Spielstand (wohlstand, kontrolle, hauptstadt); Provinz laut Kartenhierarchie (map_data/definitions.txt)
    provinzen = _provinzen(last, live.get("orte") or {})

    # ---- Kabinett: Plätze (Spielstand), Werte des Mods je Platz, wenn er dieselbe Aktion meint
    kurz = {str(x.get("id")): x for x in live.get("kabinett_kurz") or []}
    plaetze = []
    for k in sorted(last.get("kabinett") or [], key=lambda k: (k.get("platz") is None, k.get("platz") or 0)):
        i = str(k.get("platz"))
        a = (live.get("kabinett") or {}).get(i) or {}
        kz = kurz.get(i) or {}
        gleich = bool(kz) and kz.get("aktion") == k.get("aktion_name")
        plaetze.append({**{f: k.get(f) for f in ("platz", "aktion", "aktion_name", "person", "adm", "dip", "mil", "stand", "seit", "ziele")},
                        "fortschritt": a.get("GetActionNumProgress") if gleich and _num(a.get("GetActionNumProgress")) else None,
                        "wirksam": a.get("GetEffectiveSkill") if gleich and _num(a.get("GetEffectiveSkill")) else None,
                        "wirksam_text": (live.get("skill_texte") or {}).get(i) if gleich else None,
                        "mod_andere_aktion": kz.get("aktion") if kz and not gleich else None})
    offen = int(L["num_open_cabinet_positions"]) if _num(L.get("num_open_cabinet_positions")) else None
    plaetze_alle = plaetze + [{"platz": None, "frei": True} for _ in range(offen or 0)]
    personen = None
    if live.get("personen"):
        personen = [{"name": p.get("name"), "adm": p.get("adm"), "dip": p.get("dip"), "mil": p.get("mil"),
                     "im_kabinett": p.get("HoldsCabinetPosition") == 1, "alter": p.get("GetAge")}
                    for p in live["personen"].values()
                    if p.get("IsAdult") == 1 and not any(p.get(x) == 1 for x in ("IsRuler", "IsRegent", "IsHeir", "IsConsort"))]
    aktiv_k = {p["aktion"] for p in plaetze if p.get("aktion")}
    K = S["kabinett"]
    kab_status, kab_bed = {}, {}
    for k, e in K.items():
        st, bed = pruefe(P, {**e, "_key": k}, k in aktiv_k, "unlock_cabinet_action", _ziel_knoten(P, e, staende, provinzen, nm))
        kab_status[k] = st
        if st != "n":
            kab_bed[k] = bed

    # ---- Gesetze und Politlinien (nur Gesetze, die der Spielstand nennt)
    gesetze_jetzt = last.get("gesetze") or {}
    pol_status, pol_bed = {}, {}
    for lk, pk_jetzt in gesetze_jetzt.items():
        LG = S["gesetze"].get(lk) or {}
        extra_g = []                                 # Gesetz änderbar (allow) und nicht gesperrt (locked) – laws/readme.txt
        if LG.get("allow"):
            al = P.block(LG["allow"])
            extra_g.append(P.k("Gesetz änderbar (allow des Gesetzes):", _und(x["ok"] for x in al), kinder=al, art="und"))
        if LG.get("locked"):
            lo = P.block(LG["locked"])
            lo_ok = _und(x["ok"] for x in lo)
            extra_g.append(P.k("Gesetz nicht gesperrt – gesperrt, wenn (locked):", None if lo_ok is None else not lo_ok,
                               kinder=lo, art="und"))
        for pk, e in (LG.get("pol") or {}).items():
            st, bed = pruefe(P, {**e, "_key": pk}, pk == pk_jetzt, "unlock_policy", extra_g if pk != pk_jetzt else ())
            pol_status[(lk, pk)] = st
            pol_bed[(lk, pk)] = bed

    # ---- Reformen
    reformen_jetzt = [r for r in last.get("reformen") or [] if isinstance(r, str)]
    major_jetzt = any((S["reformen"].get(r) or {}).get("major") for r in reformen_jetzt)
    ref_status, ref_bed = {}, {}
    for rk, e in S["reformen"].items():
        if e.get("gov") and F.get("regierungsform") and e["gov"] != F["regierungsform"]:
            continue
        extra = []
        if e.get("gov"):
            extra.append(P.k(f"Regierungsform {nm(e['gov'])}", None if not F.get("regierungsform") else e["gov"] == F["regierungsform"]))
        if e.get("age") in zeit:
            extra.append(P.k(f"ab dem Zeitalter „{nm(e['age'])}“ (Feld age)", None if z_jetzt is None else z_jetzt >= zeit.index(e["age"])))
        for pol in e.get("sv") or []:
            ak = next((a for a in S["achsen"] if pol in _pole(a)), None)
            v = pol_wert(ak, pol, sv.get(ak)) if ak else None
            ziel = S["defines"].get("SOCIAL_VALUE_REQUIREMENT_FOR_REFORM")
            extra.append(P.k(f"Gesellschaftswert „{nm(pol + '_focus')}“ mindestens {_de(ziel, 0) if _num(ziel) else '?'} "
                             "(SOCIAL_VALUE_REQUIREMENT_FOR_REFORM)", None if not _num(v) or not _num(ziel) else v >= ziel,
                             ist=_de(v, 0) if _num(v) else None))
        if e.get("major") and rk not in reformen_jetzt:
            extra.append(P.k("nur eine große Reform je Land (major)", not major_jetzt))
        st, bed = pruefe(P, {**e, "_key": rk}, rk in reformen_jetzt, "unlock_government_reform", extra)
        ref_status[rk] = st
        if st != "n":
            ref_bed[rk] = bed
    ref_offen = int(L["num_open_reform_slots"]) if _num(L.get("num_open_reform_slots")) else None

    # ---- je Schwerpunkt
    fokusse = {}
    diplo = _diplomatie(S, last, F, L, live, nb, gr, nm, P)
    for fk in wirtschaftsplan.FOKUS:
        C = fokus_kontext(fk, wp, mt)
        AF = achsen_fokus(S, list(sv), C)
        top = AF[:TOP_ACHSEN]
        guenstig = {a["pol"]: a["pol_name"] for a in top}
        unguenstig = {a["gegen"]: a["pol_name"] for a in top}
        fokusse[fk] = _fokus(fk, C, S, top, guenstig, unguenstig, plaetze_alle, personen, kab_status, gesetze_jetzt, pol_status,
                             staende, priv_status, gew, reformen_jetzt, ref_status, ref_offen, sv, LM, wp, tv, diplo, pi, nm)
    # an die Seite: nur gezeigte Einträge (Status nicht „nicht für uns“), ohne Rohbedingungen und Beschreibung (steht im Wiki)
    return {
        "datum": meta.get("datum"), "mod_datum": live.get("datum"), "mit_mod": bool(live),
        "fokus_namen": {k: v[0] for k, v in wirtschaftsplan.FOKUS.items()}, "themen": {k: v[0] for k, v in techbaum.THEMA_REGEL.items()},
        "stand_namen": {s: nm(s) for s in sorted({e["stand"] for e in S["privilegien"].values()}
                                                  | {x for g in S["gesetze"].values() for p in g["pol"].values() for x in p["staende"]})},
        "punkte": PUNKTE, "regeln": REGELN, "preise": S["preise"], "defines": S["defines"],
        "einfluss": pi, "einfluss_monat": L.get("monthly_political_influence") if _num(L.get("monthly_political_influence")) else None,
        "kabinett": {"plaetze": plaetze, "offen": offen, "personen": personen,
                     "aktionen": {k: _seite(K[k], kab_status[k], kab_bed[k], wiki_o("cabinet_actions", k)) for k in kab_bed},
                     "nicht_fuer_uns": sum(1 for s in kab_status.values() if s == "n")},
        "gesetze": {lk: {"n": (S["gesetze"].get(lk) or {}).get("n") or nm(lk), "kat": (S["gesetze"].get(lk) or {}).get("kat"),
                         "jetzt": pk, "wiki": wiki_o("laws", lk),
                         "pol": {p: _seite(e, pol_status[(lk, p)], pol_bed[(lk, p)], f"wiki/policies/{p}")
                                 for p, e in ((S["gesetze"].get(lk) or {}).get("pol") or {}).items() if pol_status[(lk, p)] != "n"},
                         "nicht_fuer_uns": sum(1 for p in ((S["gesetze"].get(lk) or {}).get("pol") or {})
                                               if pol_status[(lk, p)] == "n")}
                    for lk, pk in gesetze_jetzt.items()},
        "privilegien": {"staende": staende,
                        "katalog": {p: _seite(S["privilegien"][p], priv_status[p], priv_bed[p], wiki_o("estate_privileges", p))
                                    for p in priv_bed}},
        "reformen": {"jetzt": reformen_jetzt, "offen": ref_offen,
                     "katalog": {r: _seite(S["reformen"][r], ref_status[r], ref_bed[r], wiki_o("government_reforms", r), knapp=True)
                                 for r in ref_bed}},
        "gesellschaft": {"achsen": achsen},
        "diplomatie": diplo,
        "fokusse": fokusse,
        "wiki": {k: P.wiki_begriff(k) for k in ("cabinet", "cabinet_actions", "policies", "laws", "estate_privileges", "estates",
                                               "government_reforms", "societal_values", "alliance", "rivals", "diplomats",
                                               "royal_marriage", "improve_relations", "political_influence", "estate_satisfaction",
                                               "crown_power", "diplomatic_capacity") if P.wiki_begriff(k)},
    }


def _falsch(knoten):
    """Texte der nicht erfüllten Blätter eines Bedingungsbaums (für „gesperrt: …“)."""
    out = []
    for x in knoten:
        if x.get("ok") is False:
            out += (_falsch(x.get("kinder") or []) if x.get("kinder") else []) or [x["text"].rstrip(":")]
    return out


def _seite(e, st, bed, wiki, knapp=False):
    """Eintrag für die Seite: ohne Rohbedingungen und Beschreibung; der Bedingungsbaum nur, wo etwas offen oder falsch ist (bei
    „möglich“ und „aktiv“ ist alles erfüllt). knapp: gesperrte Einträge nur mit Name und Grund (Reformen späterer Zeitalter)."""
    grund = "; ".join(dict.fromkeys(_falsch(bed))) if st == "g" else None
    if knapp and st == "g":
        return {"n": e.get("n"), "status": st, "grund": grund, "wiki": wiki}
    out = {f: v for f, v in e.items() if f not in ("pot", "allow", "b", "z_en", "z_vis", "locked")}
    out.update(status=st, wiki=wiki, grund=grund)
    if st in ("u", "v", "g"):
        out["bed"] = bed
    return out


def _fokus(fk, C, S, top, guenstig, unguenstig, plaetze, personen, kab_status, gesetze_jetzt, pol_status, staende, priv_status,
           gew, reformen_jetzt, ref_status, ref_offen, sv, LM, wp, tv, diplo, pi, nm):
    K = S["kabinett"]
    pk_kab = {}
    for k, st in kab_status.items():
        if st == "n":
            continue
        p, g, n = bewerte(K[k]["w"], C, guenstig, unguenstig)
        if K[k].get("sv") and top:
            p += 5
            g.append([5, f"kann einen Gesellschaftswert gezielt verschieben (societal_values {_de(K[k]['sv'])} laut Spieldatei) – "
                         f"günstig: „{top[0]['pol_name']}“", "gesellschaft"])
        pk_kab[k] = (p, g, n)
    kab = kabinett_vorschlag([p if not p.get("frei") else {"platz": None} for p in plaetze], K, kab_status, pk_kab, personen,
                             faktor=S["defines"].get("CABINET_ACTION_SKILL_MODIFIER") or 0.005)
    leer = (0, [], [])
    for s in kab:
        a = s.get("vorschlag")
        v = pk_kab.get(a) or leer
        s["punkte"], s["gruende"], s["nachteile"] = (v[0], _texte(v[1]), v[2]) if a else (0, [], [])
        j = s["jetzt"].get("aktion")
        s["punkte_jetzt"] = (pk_kab.get(j) or leer)[0] if j else None
        s["gruende_jetzt"] = _texte((pk_kab.get(j) or leer)[1]) if j else []
        s["warnungen"] = _warnungen(K[a]["w"], staende, nm, K[j]["w"] if j in K else None) if a in K and a != j else []
    kab_alle = {k: v[0] for k, v in pk_kab.items() if v[0] > 0}
    # Gesetze: je Gesetz die beste vorschlagbare Politlinie mit direkter Wirkung; die jetzige bleibt bei Gleichstand
    ges = []
    for lk, pj in gesetze_jetzt.items():
        pol = (S["gesetze"].get(lk) or {}).get("pol") or {}
        werte = {p: bewerte(pol[p]["w"], C, guenstig, unguenstig) for p in pol if pol_status.get((lk, p)) not in (None, "n")}
        if not werte:
            continue
        vj = (werte.get(pj) or leer)[0]
        kand = [p for p in werte if p != pj and pol_status[(lk, p)] in VORSCHLAGBAR and direkt(werte[p]) and werte[p][0] > vj]
        best = max(kand, key=lambda p: (werte[p][0], pol_status[(lk, p)] == "m", pol[p]["n"])) if kand else pj
        w = werte.get(best) or leer
        ges.append({"gesetz": lk, "jetzt": pj, "vorschlag": best, "abweichung": best != pj, "status": pol_status.get((lk, best)),
                    "warnungen": _warnungen(pol[best]["w"], staende, nm, pol[pj]["w"] if pj in pol else None) if best != pj else [],
                    "punkte_jetzt": vj, "punkte": w[0], "gruende": _texte(w[1]), "nachteile": w[2],
                    "gruende_jetzt": _texte((werte.get(pj) or leer)[1]), "alle": {p: v[0] for p, v in werte.items()}})
    ges.sort(key=lambda g: (not g["abweichung"], -(g["punkte"] - g["punkte_jetzt"]), g["gesetz"]))
    # Privilegien: je Stand das beste vorschlagbare, Wirkung auf die Zielzufriedenheit aller Stände
    PR = S["privilegien"]
    priv = []
    for e in staende:
        s = e["stand"]
        werte = {p: bewerte(PR[p]["w"], C, guenstig, unguenstig) for p, st in priv_status.items()
                 if st not in ("n", "a") and PR[p]["stand"] == s}
        kand = [p for p, v in werte.items() if priv_status[p] in VORSCHLAGBAR and v[0] > 0 and direkt(v)]
        best = max(kand, key=lambda p: (werte[p][0], priv_status[p] == "m", PR[p]["n"])) if kand else None
        w = werte.get(best) or leer
        priv.append({"stand": s, "vorschlag": best, "abweichung": bool(best), "punkte": w[0], "gruende": _texte(w[1]),
                     "nachteile": w[2],
                     "warnungen": _warnungen(PR[best]["w"], staende, nm) + _macht_warnung(PR[best]["w"], e) if best else [],
                     "status": priv_status.get(best) if best else None,
                     "gewaehrt_punkte": {p: bewerte(PR[p]["w"], C, guenstig, unguenstig)[0] for p in e["gewaehrt"] if p in PR},
                     "alle": {p: werte[p][0] for p in kand if p != best}})
    # Reformen: Vorschlag nur mit freiem Platz (Daten-Mod num_open_reform_slots)
    RF = S["reformen"]
    rwerte = {r: bewerte(RF[r]["w"], C, guenstig, unguenstig) for r, st in ref_status.items() if st in ("m", "v", "u")}
    rkand = [r for r, v in rwerte.items() if ref_status[r] in VORSCHLAGBAR and v[0] > 0 and direkt(v)]
    rbest = max(rkand, key=lambda r: (rwerte[r][0], ref_status[r] == "m", RF[r]["n"])) if rkand else None
    w = rwerte.get(rbest) or leer
    reform = {"vorschlag": rbest, "punkte": w[0], "gruende": _texte(w[1]), "nachteile": w[2], "status": ref_status.get(rbest),
              "warnungen": _warnungen(RF[rbest]["w"], staende, nm) if rbest else [],
              "offen": ref_offen, "abweichung": bool(rbest) and bool(ref_offen),
              "weitere": [r for r in sorted(rkand, key=lambda r: (-rwerte[r][0], RF[r]["n"])) if r != rbest][:4],
              "jetzt_punkte": {r: bewerte(RF[r]["w"], C, guenstig, unguenstig)[0] for r in reformen_jetzt if r in RF},
              "alle": {r: v[0] for r, v in rwerte.items() if v[0] > 0}}
    # Gesellschaftswerte: günstiger Pol und was dorthin schiebt
    ges_w = []
    for a in top:
        m = "monthly_towards_" + a["pol"]
        g = "monthly_towards_" + a["gegen"]
        wirkt, moeglich, gegen = [], [], []
        for lk, pj in gesetze_jetzt.items():
            for p, e in ((S["gesetze"].get(lk) or {}).get("pol") or {}).items():
                hat = [x for x in e["w"] if x[0] == m]
                hat_g = [x for x in e["w"] if x[0] == g]
                eintrag = {"art": "Politlinie", "key": p, "gesetz": lk, "name": e["n"], "wert": (hat or hat_g or [[0, 0, ""]])[0][2],
                           "status": pol_status.get((lk, p))}
                if p == pj and hat:
                    wirkt.append(eintrag)
                elif p == pj and hat_g:
                    gegen.append(eintrag)
                elif hat and pol_status.get((lk, p)) in ("m", "v", "u"):
                    moeglich.append(eintrag)
        for p, e in PR.items():
            hat = [x for x in e["w"] if x[0] == m]
            hat_g = [x for x in e["w"] if x[0] == g]
            eintrag = {"art": "Privileg", "key": p, "name": e["n"], "wert": (hat or hat_g or [[0, 0, ""]])[0][2],
                       "status": priv_status.get(p)}
            if p in gew and hat:
                wirkt.append(eintrag)
            elif p in gew and hat_g:
                gegen.append(eintrag)
            elif hat and priv_status.get(p) in ("m", "v", "u"):
                moeglich.append(eintrag)
        for r, e in RF.items():
            hat = [x for x in e["w"] if x[0] == m]
            hat_g = [x for x in e["w"] if x[0] == g]
            eintrag = {"art": "Reform", "key": r, "name": e["n"], "wert": (hat or hat_g or [[0, 0, ""]])[0][2],
                       "status": ref_status.get(r)}
            if r in reformen_jetzt and hat:
                wirkt.append(eintrag)
            elif r in reformen_jetzt and hat_g:
                gegen.append(eintrag)
            elif hat and ref_status.get(r) in ("m", "v", "u"):
                moeglich.append(eintrag)
        kab_sv = [k for k, e in K.items() if e.get("sv") and kab_status.get(k) in ("m", "v", "u", "a")]
        # mögliche zuerst (m, v vor u), sonst Reihenfolge der Spieldatei
        moeglich.sort(key=lambda x: x.get("status") == "u")
        st = gesellschaft_stand(a["achse"], sv.get(a["achse"]), LM)
        ges_w.append({**a, **st, "zum_pol": pol_wert(a["achse"], a["pol"], sv.get(a["achse"])),
                      "zieht_hin": st["richtung"] == a["pol"] if st["richtung"] else None,
                      "wirkt": wirkt[:SCHIEBER], "moeglich": moeglich[:SCHIEBER], "gegen": gegen[:SCHIEBER],
                      "kabinett": [{"key": k, "name": K[k]["n"], "wert": _de(K[k]["sv"])} for k in kab_sv]})
    # Bau und Forschung: nur übernommen
    plan = (((wp or {}).get("fokusse") or {}).get(fk) or {}).get("plan") or []
    bau = [{k: s.get(k) for k in ("nr", "was", "ort", "warum", "kosten", "gruppe", "voraussetzung")} for s in plan[:TOP_BAU]]
    tf = ((tv or {}).get("fokusse") or {}).get(fk) or {}
    forschung = forschung_liste(tf)
    # Erste Schritte
    preise = S["preise"]
    pol_preis = (preise.get("set_policy") or {}).get("zahl")
    priv_preis = (preise.get("grant_privilege") or {}).get("zahl")
    kab_preis = (preise.get("set_cabine_action") or {}).get("zahl")
    tausch_preis = (preise.get("replace_cabinet_member") or {}).get("zahl")

    def einfluss_text(z):
        return f"{_de(z, 0)} Politischer Einfluss" if _num(z) and z > 0 else None
    V = {b: [] for b in ERSTE_REIHE}
    for s in kab:
        if not s["abweichung"] or s.get("warnungen"):
            continue
        a, j, m = s["vorschlag"], s["jetzt"], s.get("minister")
        nr = f"Platz {s['platz'] + 1}" if _num(s["platz"]) else "Neuer Platz"
        tausch = bool(m and j.get("person"))
        if a == j.get("aktion"):                     # nur der Minister ändert sich -> eigener Bereich, zuletzt (Prüfer 31.10.)
            if m:
                V["minister"].append({
                    "text": f"{nr}: Minister {m['name']} statt {j.get('person') or '–'} für „{K[a]['n'] if a in K else j.get('aktion_name')}“",
                    "warum": f"{FAEHIGKEIT.get(s['faehigkeit'], s['faehigkeit'])} {_de(m['wert'], 0)} statt "
                             f"{_de(m['jetzt'], 0) if _num(m['jetzt']) else '–'}: Gesamtsteigerung +{_de(m['mehr'] * 100, 1)} %-Pkt. "
                             "(CABINET_ACTION_SKILL_MODIFIER)",
                    "kosten": einfluss_text(tausch_preis) if tausch else None, "einfluss": tausch_preis if tausch else None,
                    "link": "#regierung"})
            continue
        txt = f"{nr}: „{K[a]['n']}“" + (f" statt „{K[j['aktion']]['n'] if j['aktion'] in K else j.get('aktion_name')}“"
                                         if j.get("aktion") else "")
        if m:
            txt += f", Minister {m['name']} ({FAEHIGKEIT.get(s['faehigkeit'], s['faehigkeit'])} {_de(m['wert'], 0)})"
        z = (kab_preis if _num(kab_preis) else 0) + (tausch_preis if tausch and _num(tausch_preis) else 0)
        V["kabinett"].append({"text": txt, "warum": "; ".join(s["gruende"][:2]) or s.get("grund") or "",
                              "kosten": "; ".join(x for x in (
                                  (preise.get("set_cabine_action") or {}).get("text"),
                                  f"Minister tauschen: {(preise.get('replace_cabinet_member') or {}).get('text')}" if tausch else None)
                                  if x) or None,
                              "einfluss": z or None, "link": "#regierung"})
    s1 = forschung_schritt(forschung)
    if s1:
        V["forschung"].append(s1)
    for g in ges:
        if g["abweichung"] and not g["warnungen"]:
            pol = S["gesetze"][g["gesetz"]]["pol"]
            V["politlinie"].append({"text": f"„{pol[g['vorschlag']]['n']}“ ({S['gesetze'][g['gesetz']]['n']}) statt "
                                            f"„{pol[g['jetzt']]['n'] if g['jetzt'] in pol else nm(g['jetzt'])}“",
                                    "warum": "; ".join(g["gruende"][:2]), "kosten": einfluss_text(pol_preis), "einfluss": pol_preis,
                                    "link": "#startstrategie"})
            break
    for p in sorted([p for p in priv if p["vorschlag"] and not p["warnungen"]], key=lambda p: -p["punkte"])[:1]:
        V["privileg"].append({"text": f"„{PR[p['vorschlag']]['n']}“ ({nm(p['stand'])}) gewähren",
                              "warum": "; ".join(p["gruende"][:2]), "kosten": einfluss_text(priv_preis), "einfluss": priv_preis,
                              "link": "#staende"})
    if bau:
        V["bau"].append({"text": f"{bau[0]['was']}" + (f" in {bau[0]['ort']}" if bau[0].get("ort") else ""),
                         "warum": bau[0].get("warum") or "", "kosten": bau[0].get("kosten"), "link": "#wirtschaftsplan"})
    b = diplo.get("buendnis_vorschlag")
    if b:
        V["buendnis"].append({"text": b["text"], "warum": b["warum"], "kosten": b.get("kosten"), "link": "#nachbarn"})
    if reform["abweichung"] and not reform["warnungen"]:
        V["reform"].append({"text": f"„{RF[rbest]['n']}“ einführen", "warum": "; ".join(reform["gruende"][:2]),
                            "kosten": None, "link": "#regierung"})
    rv = diplo.get("rivale_vorschlag")
    if rv:
        V["rivale"].append({"text": rv["text"], "warum": rv["warum"], "kosten": None, "link": "#diplomatie"})
    out = {"name": wirtschaftsplan.FOKUS[fk][0], "thema": C["thema"], "kabinett": kab, "kabinett_punkte": kab_alle, "gesetze": ges,
           "privilegien": priv,
           "reform": reform, "gesellschaft": ges_w, "bau": bau, "forschung": forschung,
           "forschung_fehler": (tv or {}).get("fehler"),
           "buendnis": {"abweichung": bool(b) and b.get("art") == "anbieten"}, "rivale": {"abweichung": bool(rv)},
           "erste_schritte": einfluss_rechnen(erste_schritte(V), pi)}
    out["abweichungen"] = abweichungen(out)
    return out


def forschung_liste(tf, n=TOP_FORSCHUNG):
    """Die ersten n aus dem Fortschritts-Vorschlag (techbaum.vorschlaege): jetzt erforschbare, danach Ziele mit kurzem Weg."""
    out = [{k: e.get(k) for k in ("key", "name", "punkte", "kosten", "monate", "laeuft", "thema")}
           | {"grund": (e.get("gruende") or [""])[0], "ziel": False} for e in (tf.get("eintraege") or [])[:n]]
    for z in tf.get("ziele") or []:
        if len(out) >= n:
            break
        out.append({k: z.get(k) for k in ("key", "name", "punkte", "laeuft", "thema")}
                   | {"kosten": z.get("weg_kosten"), "monate": z.get("weg_monate"), "grund": (z.get("gruende") or [""])[0], "ziel": True,
                      "weg": [{k: w.get(k) for k in ("key", "name", "status", "gesperrt", "rest")} for w in z.get("weg") or []]})
    return out


def forschung_schritt(forschung):
    """Erster Forschungsschritt: der erste Vorschlag, der nicht schon läuft; bei einem Ziel der erste freie Schritt des Wegs
    (jetzt erforschbar, nicht gesperrt). Läuft dieser Schritt schon, ist nichts zu tun."""
    for e in forschung:
        if not e.get("ziel"):
            if not e.get("laeuft"):
                return {"text": f"„{e['name']}“ erforschen", "warum": e.get("grund") or "",
                        "kosten": f"{_de(e['kosten'], 2)} Forschung" if _num(e.get("kosten")) else None, "link": f"#techbaum/{e['key']}"}
            return None
        weg = e.get("weg") or []
        if any(w.get("gesperrt") for w in weg):
            continue
        frei = next((w for w in weg if w.get("status") == "j"), None)
        if frei and frei.get("rest") is not None:          # dieser Schritt ist die laufende Forschung (Rest laut Daten-Mod)
            return None
        if frei:
            return {"text": f"„{frei['name']}“ erforschen (Weg zu „{e['name']}“)", "warum": e.get("grund") or "",
                    "kosten": f"Weg {_de(e['kosten'], 2)} Forschung" if _num(e.get("kosten")) else None,
                    "link": f"#techbaum/{e['key']}"}
    return None


def _warnungen(w, staende, nm, alt=None):
    """Warnungen: Zielzufriedenheit eines Stands sinkt unter ZUFRIEDEN_MIN (oder liegt schon darunter und sinkt weiter).
    Änderung = Wirkung des Neuen − Wirkung des Ersetzten (alt: jetzige Politlinie bzw. Kabinettsaktion; Prüfer 31.10.). Ziel aus
    dem Daten-Mod (target_satisfaction), sonst die Zufriedenheit des Spielstands – dann so benannt."""
    def summe(ws, s):
        return sum(x[5] for x in ws or [] if x[0] in (f"{s}_target_satisfaction", "global_estate_target_satisfaction") and _num(x[5]))
    out = []
    for e in staende:
        s = e["stand"]
        d = round(summe(w, s) - summe(alt, s), 6)
        hat_ziel = _num(e.get("ziel"))
        basis = e["ziel"] if hat_ziel else e.get("zufriedenheit")
        if d < 0 and _num(basis) and basis + d < ZUFRIEDEN_MIN:
            out.append(f"{e['name']}: {'Zielzufriedenheit' if hat_ziel else 'Zufriedenheit (Ziel unbekannt)'} {_pz(basis, 1)} → "
                       f"{_pz(basis + d, 1)} (unter {_pz(ZUFRIEDEN_MIN, 0)})")
    return out


def _macht_warnung(w, e):
    """Regel des Ratgebers: hebt ein Privileg die Macht seines Stands (global_<stand>_power), der schon MACHT_MAX hat -> Warnung."""
    m = e.get("macht")
    x = next((x for x in w if x[0] == f"global_{e['stand']}_power" and _num(x[5]) and x[5] > 0), None)
    if x and _num(m) and m >= MACHT_MAX:
        return [f"{e['name']}: Macht schon {_pz(m, 1)} – {x[1]} {x[2]} hebt sie weiter (Regel des Ratgebers: ab "
                f"{_pz(MACHT_MAX, 0)} nur mit Hinweis)"]
    return []


def _staende_waehlbar(en, staende):
    """Stände, die das enabled eines Ziels „Stand“ erfüllen – nur Vergleiche von satisfaction/power (appease_estate:
    satisfaction < 0.5); sonst None (nicht auswertbar)."""
    feld = {"satisfaction": "zufriedenheit", "power": "macht"}
    tests = []
    for k, v in (en or {}).items():
        m = re.match(r"^(satisfaction|power)(>=|<=|>|<)$", k)
        if not m or not _num(v):
            return None
        tests.append((feld[m.group(1)], m.group(2), v))
    if not tests:
        return None
    out = []
    for s in staende:
        if not all(_num(s.get(f)) for f, _, _ in tests):
            return None
        if all(techbaum.VERGLEICH[op](s[f], v) for f, op, v in tests):
            out.append(s)
    return out


# Bedingungen eines Provinz-Ziels, die nur Doppelbelegung ausschließen – übergangen (prüft das Spiel)
DOPPELT = {"cabinet_already_performing_same_task_on_target", "cabinet_control_area_action_covers_province"}
ORT_FELD = {"prosperity": "Wohlstand", "local_control": "Kontrolle"}


def _provinzen(last, mod_orte):
    """{provinz: [{name, prosperity, local_control, is_capital}]} für unsere Orte – Daten-Mod (a.ort, Kennung = Orts-ID) vor
    Spielstand. Provinz aus der Kartenhierarchie (gruendung._karte); ohne sie {}."""
    try:
        hier = gruendung._karte()["hier"]
    except Exception:                            # noqa: BLE001 – ohne Spieldateien keine Provinzen
        return {}
    out = {}
    for o in last.get("orte") or []:
        prov = (hier.get(str(o.get("key"))) or {}).get("provinz")
        if not prov:
            continue
        m = mod_orte.get(str(o.get("id"))) or {}
        out.setdefault(prov, []).append({
            "name": o.get("name"),
            "prosperity": m["prosperity"] if _num(m.get("prosperity")) else o.get("wohlstand"),
            "local_control": m["local_control"] if _num(m.get("local_control")) else o.get("kontrolle"),
            "is_capital": (m["IsCapital"] > 0) if _num(m.get("IsCapital")) else bool(o.get("hauptstadt"))})
    return out


def _ort_test(block, o):
    """Bedingungen an einen Ort (Inhalt von any_location_in_province): Vergleiche von prosperity/local_control, is_capital, count
    -> True/False, sonst None (nicht auswertbar)."""
    ok = True
    for k, v in block.items():
        if k == "count":
            continue
        m = re.match(r"^(prosperity|local_control)(>=|<=|>|<)$", k)
        if m and _num(v):
            x = o.get(m.group(1))
            if not _num(x):
                return None
            ok = ok and techbaum.VERGLEICH[m.group(2)](x, v)
        elif k == "is_capital" and v in ("yes", "no"):
            ok = ok and o["is_capital"] == (v == "yes")
        else:
            return None
    return ok


def _provinz_test(block, orte):
    """visible/enabled eines Provinz-Ziels gegen unsere Orte der Provinz -> True/False/None. Ausgewertet: any_location_in_province
    (mit count = all: alle unsere Orte) und province_average_control (Schnitt unserer Orte); „läuft schon auf diesem Ziel“ (DOPPELT)
    übergangen; alles andere -> None. Orte anderer Besitzer in der Provinz kennt der Ratgeber nicht."""
    if not block:
        return True
    if not isinstance(block, dict):
        return None
    ok = True
    for k, v in block.items():
        if k in ("NOT", "not") and all(isinstance(x, dict) and x and set(x) <= DOPPELT for x in _liste(v)):
            continue
        if k == "any_location_in_province" and isinstance(v, dict):
            w = [_ort_test(v, o) for o in orte]
            if None in w or not w:
                return None
            r = all(w) if v.get("count") == "all" else any(w)
        else:
            m = re.match(r"^province_average_control(>=|<=|>|<)$", k)
            xs = [o.get("local_control") for o in orte]
            if not (m and _num(v) and xs and all(_num(x) for x in xs)):
                return None
            r = techbaum.VERGLEICH[m.group(1)](sum(xs) / len(xs), v)
        ok = ok and r
    return ok


def _ziel_text(bloecke):
    """Bedingung eines Provinz-Ziels in Worten (nur die ausgewerteten Teile)."""
    teile = []
    for b in bloecke:
        for k, v in (b or {}).items() if isinstance(b, dict) else ():
            if k == "any_location_in_province" and isinstance(v, dict):
                xs = []
                for kk, vv in v.items():
                    m = re.match(r"^(prosperity|local_control)(>=|<=|>|<)$", kk)
                    if m and _num(vv):
                        xs.append(f"{ORT_FELD[m.group(1)]} {m.group(2)} {_pz(vv, 0) if m.group(1) == 'local_control' else _de(vv)}")
                    elif kk == "is_capital":
                        xs.append("Hauptstadt" if vv == "yes" else "nicht Hauptstadt")
                if xs:
                    teile.append(("alle unsere Orte" if v.get("count") == "all" else "ein Ort") + " mit " + ", ".join(xs))
            m = re.match(r"^province_average_control(>=|<=|>|<)$", k)
            if m and _num(v):
                teile.append(f"Kontrolle im Schnitt {m.group(1)} {_pz(v, 0)}")
    return "; ".join(dict.fromkeys(teile))


def _ziel_knoten(P, e, staende, provinzen=None, nm=None):
    """Knoten für das Ziel einer Kabinettsaktion (select_trigger, Prüfer 31.10.): Stand als Ziel mit auswertbarem enabled ->
    erfüllt, wenn ein Stand es erfüllt. Provinz als Ziel (Nutzer 01.11.: „Erholungsbemühungen“ nur in einer verwüsteten Provinz):
    visible und enabled je Provinz mit unseren Orten -> erfüllt, wenn eine Provinz passt; gesperrt, wenn keine passt und alle
    auswertbar sind. Sonst (andere Ziele, nicht auswertbare Bedingungen): prüft das Spiel -> offen."""
    if not e.get("zt"):
        return []
    if e["zt"] == ["province"] and provinzen:
        bloecke = [b for b in (e.get("z_vis"), e.get("z_en")) if b]
        passt, offen = [], False
        for prov, orte in sorted(provinzen.items()):
            r = _und([_provinz_test(b, orte) for b in bloecke]) if bloecke else True
            if r is None:
                offen = True
            elif r:
                passt.append(prov)
        text = _ziel_text(bloecke)
        nm = nm or (lambda k: k)
        if passt:
            namen = ", ".join(nm(p) for p in passt[:4]) + (" …" if len(passt) > 4 else "")
            return [P.k(f"Eine unserer Provinzen ist als Ziel wählbar{f' ({text})' if text else ''}: {namen}", True)]
        if not offen:
            return [P.k(f"Keine unserer Provinzen ist als Ziel wählbar{f' – verlangt: {text}' if text else ''} (select_trigger)",
                        False)]
    if e["zt"] == ["estate"]:
        ok = _staende_waehlbar(e.get("z_en"), staende)
        if ok is not None:
            return [P.k("Ein Stand ist als Ziel wählbar (select_trigger enabled)" + (f": {', '.join(s['name'] for s in ok)}" if ok else
                                                                                   " – keiner erfüllt die Bedingung"), bool(ok))]
    return [P.k(f"Passendes Ziel ({', '.join(e.get('ziel') or e['zt'])}) vorhanden (select_trigger) – prüft das Spiel", None)]


def buendnis_vorschlag(gut, frei_kap=None):
    """Erster Bündnis-Schritt (Regel des Ratgebers) aus den gereihten Kandidaten ohne „besser nicht“: der erste mit allen bekannten
    Bedingungen erfüllt und Unterhalt in der freien Diplomatiekapazität -> „anbieten“; sonst der erste, bei dem nur ihre Meinung
    von uns unter 0 liegt -> „Beziehungen verbessern“ (ein Diplomat hebt ihre Meinung; unsere Meinung von ihnen hebt er nicht)."""
    for k in gut:
        if k["ok"] is True and (k["unterhalt"] is None or frei_kap is None or k["unterhalt"] <= frei_kap):
            return {"text": f"Bündnis mit {k['name']} anbieten",
                    "warum": f"Stärke {_de(k['staerke'], 1) if _num(k['staerke']) else '?'}"
                             + (f" = {_pz(k['gewinn'], 0)} unseres Verteidigungsbündnisses" if _num(k["gewinn"]) else "")
                             + ("; sie haben einen Kriegsgrund gegen uns – ein Bündnis verbietet den Krieg" if k["schutz"] else ""),
                    "kosten": f"Diplomatiekapazität ≈ {_de(k['unterhalt'])} von {_de(frei_kap)} frei"
                    if _num(k["unterhalt"]) and _num(frei_kap) else None, "tag": k["tag"], "name": k["name"], "art": "anbieten"}
    for k in gut:
        falsch = [x for x in k["bedingungen"] if x["ok"] is False]
        if any(x["text"].startswith("Ihre Meinung") for x in falsch) and all(x["text"].startswith("Ihre Meinung") or x.get("krieg")
                                                                              for x in falsch):
            return {"text": f"Beziehungen zu {k['name']} verbessern (Diplomat)",
                    "warum": "für ein Bündnis muss die Meinung auf beiden Seiten mindestens 0 sein (alliance_can_exist) – "
                             + "; ".join(f"{x['text']}: jetzt {x['ist']}" for x in falsch if x.get("ist"))
                             + (f"; Stärke {_de(k['staerke'], 1)} = {_pz(k['gewinn'], 0)} unseres Verteidigungsbündnisses"
                                if _num(k["staerke"]) and _num(k["gewinn"]) else ""),
                    "kosten": None, "tag": k["tag"], "art": "verbessern"}
    return None


def _diplomatie(S, last, F, L, live, nb, gr, nm, P):
    """Diplomatie, Rivalen, Heirat und Bündnisse – unabhängig vom Schwerpunkt."""
    meta = last.get("meta") or {}
    dip = {d.get("tag"): d for d in live.get("diplomatie") or [] if d.get("tag") and d.get("tag") != meta.get("tag")}
    nbl = {r["tag"]: r for r in (nb or {}).get("laender") or []}
    wir = (nb or {}).get("wir") or {}
    verb = set(F.get("verbuendete") or [])
    # Länder mit Orten für eine Gründung (Kachel Ländergründung)
    gruendung_orte = {}
    for o in (gr or {}).get("optionen") or [] if isinstance(gr, dict) else []:
        for b in o.get("besitzer") or []:
            gruendung_orte.setdefault(b["tag"], []).append(o.get("name"))
    eco_wir = L.get("GetEconomicalBase")
    R = S["buendnis"]["unterhalt"]
    # im Krieg kein Bündnis anbieten (alliance: block_when_at_war = yes) – Daten-Mod, sonst Kriege der Momentaufnahme
    krieg = F.get("krieg") if F.get("krieg") is not None else (bool(last.get("kriege")) if "kriege" in last else None)
    kandidaten, fern = [], []
    for t, d in dip.items():
        bez = set(d.get("beziehungen") or [])
        if t in verb or "krieg" in bez or "untertan" in bez or "oberherr" in bez:
            continue
        if not bez & set(NAH):
            fern.append({"tag": t, "name": d.get("name") or nm(t), "beziehungen": sorted(bez), "staerke": d.get("country_strength")})
            continue
        o_sie, o_wir = d.get("op_them"), d.get("op_us")
        bed = [{"text": "Ihre Meinung von uns mindestens 0", "ok": None if not _num(o_sie) else o_sie >= 0,
                "ist": _de(o_sie, 0) if _num(o_sie) else None},
               {"text": "Unsere Meinung von ihnen mindestens 0", "ok": None if not _num(o_wir) else o_wir >= 0,
                "ist": _de(o_wir, 0) if _num(o_wir) else None},
               {"text": "Nicht unser Rivale", "ok": "rivale" not in bez},
               {"text": "Wir sind nicht im Krieg (block_when_at_war)", "ok": None if krieg is None else not krieg, "krieg": True}]
        ok = gruendung._und([x["ok"] for x in bed])
        stark = d.get("country_strength") if _num(d.get("country_strength")) else (nbl.get(t) or {}).get("werte", {}).get("country_strength")
        verteid = wir.get("defensive_alliance_strength")
        gewinn = stark / verteid if _num(stark) and _num(verteid) and verteid > 0 else None
        nicht = []
        if "rivale" in bez:
            nicht.append("unser Rivale – Rivalen nehmen keine freundschaftlichen Verträge an (Spielbegriff Rivale)")
        if t in gruendung_orte:
            nicht.append(f"besitzt Orte für die Gründung von {', '.join(sorted(set(gruendung_orte[t])))} – ein Bündnis verbietet den Krieg "
                         "(scripted_relations alliance: disallow_war = yes)")
        amp = ((nbl.get(t) or {}).get("bewertung") or {}).get("stufe")
        if amp in ("gruen", "gelb") and "kb_ziel" in bez:
            nicht.append(f"Kriegsgelegenheit laut Kachel Nachbarn (Ampel {'grün' if amp == 'gruen' else 'gelb'}) – ein Bündnis verbietet den Krieg")
        u, u_teile = unterhalt(R, eco_wir, (live.get("fremd_eco") or {}).get(t), o_sie, "grossmacht" in bez)
        kandidaten.append({"tag": t, "name": d.get("name") or nm(t), "beziehungen": sorted(bez), "bedingungen": bed, "ok": ok,
                           "staerke": stark, "gewinn": gewinn, "schutz": "kb_gegen_uns" in bez, "meinung_sie": o_sie,
                           "meinung_wir": o_wir, "vertrauen": d.get("trust_them"), "besser_nicht": nicht,
                           "unterhalt": u, "unterhalt_teile": u_teile, "ampel": amp})
    kandidaten.sort(key=lambda k: (bool(k["besser_nicht"]), k["ok"] is False and "rivale" in k["beziehungen"],
                                   not k["schutz"], -(k["gewinn"] or 0), k["name"]))
    gut = [k for k in kandidaten if not k["besser_nicht"]][:TOP_BUENDNIS]
    frei_kap = L.get("dip_GetMaxCapacity") - L.get("dip_GetUsedDiplomaticCapacity") \
        if _num(L.get("dip_GetMaxCapacity")) and _num(L.get("dip_GetUsedDiplomaticCapacity")) else None
    bv = buendnis_vorschlag(gut, frei_kap)
    # Rivalen
    riv = [{"tag": t, "name": d.get("name") or nm(t), "meinung_wir": d.get("op_us"), "meinung_sie": d.get("op_them")}
           for t, d in dip.items() if "rivale" in (d.get("beziehungen") or [])]
    n_riv, n_mog = L.get("num_rivals"), L.get("num_possible_rivals")
    schwelle = S["defines"].get("RIVAL_OPINION_THRESHOLD")
    gut_tags = {k["tag"] for k in gut}
    rk = []
    for t, d in dip.items():
        bez = set(d.get("beziehungen") or [])
        if "rivale" in bez or t in gut_tags or t in verb or "untertan" in bez or "oberherr" in bez or not bez & set(NAH):
            continue
        o_wir = d.get("op_us")
        if _num(schwelle) and _num(o_wir) and o_wir >= schwelle:
            continue
        if "kb_gegen_uns" in bez or (_num(d.get("op_them")) and d["op_them"] < 0):
            rk.append({"tag": t, "name": d.get("name") or nm(t), "kb_gegen_uns": "kb_gegen_uns" in bez, "meinung_sie": d.get("op_them"),
                       "meinung_wir": o_wir, "beziehungen": sorted(bez)})
    rk.sort(key=lambda x: (not x["kb_gegen_uns"], x["meinung_sie"] if _num(x["meinung_sie"]) else 0, x["name"]))
    rv = None
    if _num(n_riv) and _num(n_mog) and n_riv < n_mog and rk:
        rv = {"text": f"„{rk[0]['name']}“ als Rivalen wählen", "warum": ("hat einen Kriegsgrund gegen uns" if rk[0]["kb_gegen_uns"] else
                                                                  f"ihre Meinung von uns {_de(rk[0]['meinung_sie'], 0)}")
              + f"; frei: {_de(n_mog - n_riv, 0)} von {_de(n_mog, 0)} Rivalenplätzen"}
    # Beziehungsverbesserungen (Spielstand)
    bv_laufend = [{"seit": r.get("start_date"), "automatisch": r.get("automation_initiated") == "yes"}
                  for r in (last.get("roh") or {}).get("beziehungen") or [] if r.get("art") == "opinion_improvement"
                  and r.get("first") == meta.get("land_id")]
    # Heirat: Faktoren der Spieldatei, je Kandidat die bekannten Angaben
    heirat = [{"tag": k["tag"], "name": k["name"], "rivale": "rivale" in k["beziehungen"], "meinung_sie": k["meinung_sie"],
               "vertrauen": k["vertrauen"]} for k in gut]
    return {"kandidaten": kandidaten, "fern": sorted(fern, key=lambda x: x["name"]), "vorschlaege": [k["tag"] for k in gut],
            "buendnis_vorschlag": bv,
            "verbuendete": sorted(verb), "verbuendete_namen": [nm(t) for t in sorted(verb)],
            "wir": {"verteidigung": wir.get("defensive_alliance_strength"), "angriff": wir.get("offensive_alliance_strength"),
                    "staerke": wir.get("country_strength"), "wirtschaft": eco_wir},
            "kapazitaet": {"frei": frei_kap, "max": L.get("dip_GetMaxCapacity"), "benutzt": L.get("dip_GetUsedDiplomaticCapacity")},
            "diplomaten": {"jetzt": L.get("num_of_diplomats"), "max": L.get("dip_GetMaxNumOfDiplomats")},
            "beziehungen_laufend": bv_laufend,
            "rivalen": riv, "rivalen_zahl": n_riv, "rivalen_moeglich": n_mog, "rivalen_kandidaten": rk[:5], "rivale_vorschlag": rv,
            "rivalen_regeln": S["rivalen_regeln"], "heirat": heirat, "heirat_faktoren": S["heirat"],
            "ki_faktoren": S["buendnis"].get("ki") or {}, "krieg": krieg,
            "regeln": S["buendnis"]["bedingungen"], "felder": S["buendnis"]["felder"], "mit_mod": bool(dip)}
