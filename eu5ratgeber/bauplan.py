"""Bauplan – Stufe 4 des Wirtschaftsplans (Nutzerwunsch 25.10.): konkrete Schritte je Schwerpunkt – was, wo, in welcher
Reihenfolge. Dazu Gebäude ohne Güter (Markt und Handel, Militär, Zivil) und Straßen.

Reihenfolge – feste Plätze je Gruppe, damit Gebäude ohne Güter und Straßen nicht verdrängt werden:
  1 Ausbau mit bekannten Spielwerten (bis 4) – Rohstoff (Mod: Steuergrundlage je Stufe, Kosten, Bauzeit) und eigene Gebäude
    unter der Höchststufe, deren laufende Produktionsmethode ein Gut des Schwerpunkts herstellt; nach Spielwert je Stufe
  2 Neubau eines Herstellers (bis 4) – Voraussetzung (fehlendes Eingangsgut) als eigener Schritt davor; Ort: Ortsart,
    Orts- und Baubedingung (location_potential, allow), kein Nachfolger im Ort, Pops des Typs, bester Marktzugang
  3 Gebäude mit Wirkung auf den Schwerpunkt (bis 3) – Markt und Handel, Militär, Zivil; sofort baubare vor denen mit fehlendem
    Fortschritt (früheres Zeitalter zuerst), dann nach Zahl der passenden Modifikatoren; Festungen nur bis zur Festungsgrenze
  4 Straßen zur Hauptstadt (bis 2) für Orte ohne Straße, nach Steuer
Gold-Baukosten neuer Gebäude und Straßen sind nicht berechenbar (Baumenü bzw. Straßenbau – Preis je Entfernung); gezeigt werden
die Baugüter laut Spieldatei.

Ortsbedingungen werden dreiwertig ausgewertet: erfüllt / nicht erfüllt / nicht prüfbar. Ortsmerkmale kommen als Spielwerte aus
dem Daten-Mod (a.ort: HasRiver, IsCoastal, HasPort, IsMarketCenter, IsCapital, location_population_percentage, rank_index,
num_roads), sonst aus Spielstand und Spieldateien (Küste/Hafen: map_data/ports.csv – stimmt für alle 8 Orte Hollands mit dem
Mod überein). Nicht prüfbar: See, Kultur, Religion, Integration, Bedingungen mit scope:, am Besitzer.
Prüfung 25.10. (ein Prüfer, 16 Befunde eingearbeitet).
"""
import csv
import os

from . import gamedata
from . import sprache

KATEGORIE = {"trade_category": "Markt und Handel", "military_category": "Militär", "defense_category": "Militär",
             "naval_category": "Militär", "government_category": "Zivil", "infrastructure_category": "Zivil",
             "cultural_category": "Zivil", "religious_category": "Zivil", "estate_category": "Zivil",
             "village_category": "Zivil", "colonial_category": "Zivil"}
# Markt- und Handelsmodifikatoren: ein Gebäude, dessen Nutzen für den Schwerpunkt darunter fällt, zählt zu „Markt und Handel“,
# auch wenn die Spielkategorie anders heißt (Marktdorf: Dörfer, Ortsmarkt: Standesgebäude – Prüfung 25.10.)
MARKT = {"local_merchant_capacity", "local_merchant_power", "local_trade_center_power", "local_market_access",
         "local_trades_per_burgher", "maximum_stockpile_capacity", "merchant_capacity_from_building", "merchant_power_from_building"}
# Modifikatoren mit Nutzen, wenn sie sinken (Unruhe, Bewegungskosten …)
NEGATIV_GUT = {"local_unrest", "movement_cost", "local_food_decay_modifier", "local_navy_attrition",
               "local_pop_join_rebel_threshold"}
# Wirkung je Schwerpunkt (Modifikatoren aus building_types modifier/capital_modifier, Bestand 25.10.)
WIRKUNG = {
    "grundwirtschaft": ("local_production_efficiency", "local_market_access", "local_merchant_capacity", "maximum_stockpile_capacity",
                        "local_trade_center_power", "local_raw_material_output", "local_max_control", "local_proximity_source",
                        "max_constructions_at_same_time"),
    "gewinn": ("local_production_efficiency", "local_market_access", "local_trade_center_power", "local_merchant_power",
               "local_raw_material_output", "local_max_control"),
    "bevoelkerung": ("local_population_growth", "local_clergy_pop_growth", "local_population_capacity",
                     "local_population_capacity_modifier", "local_monthly_food", "local_monthly_food_modifier", "local_food_capacity",
                     "local_migration_attraction", "local_life_expectancy", "local_disease_resistance", "local_food_decay_modifier"),
    "landheer": ("local_manpower", "can_recruit_regiment_in_this_location", "max_regiments_trained_at_same_time",
                 "local_levy_size_modifier", "manpower_to_building_owner", "local_garrison_size", "local_supply_limit_modifier"),
    "marine": ("local_sailors", "can_build_ships_in_this_location", "max_ships_built_at_same_time", "local_ship_build_speed",
               "local_navy_levy_size_modifier", "sailors_to_building_owner", "harbor_suitability", "local_repair_speed",
               "local_maritime_presence"),
    "expansion": ("local_sailors", "harbor_suitability", "local_maritime_presence", "max_ships_built_at_same_time",
                  "local_migration_attraction"),
    "export": ("local_merchant_capacity", "local_merchant_power", "local_trade_center_power", "local_market_access",
               "local_trades_per_burgher", "maximum_stockpile_capacity", "merchant_capacity_from_building",
               "merchant_power_from_building"),
    "import": ("local_merchant_capacity", "local_merchant_power", "local_trade_center_power", "local_market_access",
               "local_trades_per_burgher", "maximum_stockpile_capacity", "merchant_capacity_from_building",
               "merchant_power_from_building"),
    "bau": ("max_constructions_at_same_time", "local_proximity_source", "movement_cost"),
    "verwaltung": ("local_max_control", "local_proximity_source", "local_crown_estate_power", "local_monthly_development_modifier",
                   "local_institution_growth_modifier", "local_monthly_literacy", "local_max_literacy"),
    "lebensstandard": ("local_unrest", "local_life_expectancy", "local_disease_resistance", "local_migration_attraction",
                       "local_pop_promotion_speed", "local_monthly_literacy"),
}
# Militärische Wirkung in den Schwerpunkten Landarmee und Marine: Grobgruppe „Militär“ auch bei anderer Spielkategorie
# (Adelsanwerbezentrum: Standesgebäude mit Mannstärke); beim Erkunden zählen Seeleute nicht als Militär
MILITAER = set(WIRKUNG["landheer"]) | set(WIRKUNG["marine"])
STRASSE_FOKUS = {"grundwirtschaft", "gewinn", "landheer", "export", "import", "verwaltung", "bau"}
PLAETZE = {1: 4, 2: 4, 3: 3, 4: 2}
ZEITALTER = ("age_1_traditions", "age_2_renaissance", "age_3_discovery", "age_4_reformation", "age_5_absolutism",
             "age_6_revolutions")
LOGIK = ("OR", "AND", "NOT", "NOR")

_PORTS = None


def ports():
    """Orte mit Hafenplatz an einer Seezone (map_data/ports.csv) – Ersatz für IsCoastal/HasPort ohne Mod-Werte."""
    global _PORTS
    if _PORTS is None:
        try:
            with open(os.path.join(gamedata.GAME_DIR, "in_game", "map_data", "ports.csv"), encoding="utf-8-sig") as f:
                _PORTS = {r[0] for r in csv.reader(f, delimiter=";") if r and r[0] and r[0] != "LandProvince"}
        except OSError:
            _PORTS = set()
    return _PORTS


def _ohne_praefix(v):
    return str(v).split(":", 1)[-1]


def _vergleich(k, ist, soll):
    if ist is None:
        return None
    for op in (">=", "<=", "!=", ">", "<", "="):
        if k.endswith(op):
            try:
                ist, soll = float(ist), float(soll)
            except (TypeError, ValueError):
                return None
            return {">=": ist >= soll, "<=": ist <= soll, "!=": ist != soll, ">": ist > soll, "<": ist < soll, "=": ist == soll}[op]
    return None


def bedingung(cond, ort):
    """(Ergebnis True/False/None, nicht prüfbare Schlüssel). ort: Ortsfakten (siehe ortsfakten). Wiederholte Schlüssel stehen
    als Liste; wiederholte Logik-Blöcke (zwei OR = { }) gelten je für sich und werden im Eltern-Block verknüpft."""
    offen = set()
    hier = ort.get("hierarchie") or {}
    merk = ort.get("merkmale") or {}

    def ja(v):
        return v in ("yes", True)

    def gleich(feld, v):
        return None if ort.get(feld) is None else ort[feld] == ja(v)

    def atom(k, v):
        if k in LOGIK:
            return block(v, k)
        if isinstance(v, str) and "scope:" in v:
            offen.add(k)
            return None
        if k == "custom_tooltip":
            return block({x: y for x, y in v.items() if x != "text"} if isinstance(v, dict) else {}, "AND")
        if k == "always":
            return ja(v)
        if k == "is_capital":
            return gleich("hauptstadt", v)
        if k == "is_coastal":
            return gleich("kueste", v)
        if k == "is_port":
            return gleich("hafen", v)
        if k == "has_river":
            r = gleich("fluss", v)
            if r is None:
                offen.add(k)
            return r
        if k == "raw_material":
            return ort.get("rohstoff") == _ohne_praefix(v)
        if k in ("vegetation", "topography", "climate"):
            return merk.get(k) == _ohne_praefix(v) if merk.get(k) else None
        if k in ("region", "continent", "sub_continent", "area", "province"):
            h = {"region": "region", "continent": "kontinent", "sub_continent": "subkontinent", "area": "gebiet",
                 "province": "provinz"}[k]
            return hier.get(h) == _ohne_praefix(v) if hier.get(h) else None
        if k == "this" and isinstance(v, str) and v.startswith("location:"):
            return ort.get("key") == _ohne_praefix(v)
        if k == "is_market_center":
            return gleich("marktzentrum", v)
        if k == "has_building":
            return _ohne_praefix(v) in ort["gebaeude_typen"]
        if k == "has_road_to_capital":
            return gleich("strasse_zur_hauptstadt", v)
        for feld, wert in (("num_roads", ort.get("num_roads")), ("development", ort.get("entwicklung")),
                           ("rank_index", ort.get("rang_index")), ("location_population_percentage", ort.get("bev_anteil"))):
            if k.startswith(feld):
                r = _vergleich(k, wert, v)
                if r is None:
                    offen.add(k)
                return r
        if k == "owner.capital!=" and v == "this":
            return None if ort.get("hauptstadt") is None else not ort["hauptstadt"]
        if k == "is_overseas_for_owner":
            return gleich("ueberseeisch", v)
        offen.add(k)
        return None

    def block(b, art="AND"):
        teile = []
        for x in (b if isinstance(b, list) else [b]):
            if not isinstance(x, dict):
                continue
            for k, v in x.items():
                for y in (v if isinstance(v, list) else [v]):
                    teile.append(atom(k, y))
        if art in ("OR", "NOT", "NOR"):
            r = True if any(t is True for t in teile) else None if any(t is None for t in teile) else False
            return r if art == "OR" else (None if r is None else not r)      # NOT = NOR (Paradox-Skript)
        return False if any(t is False for t in teile) else None if any(t is None for t in teile) else True

    if cond is None:
        return True, offen
    r = block(cond)
    return r, (offen if r is None else set())             # nicht prüfbare Teile nur nennen, wenn sie entscheiden


def ortsfakten(last, wis, ort_werte=None):
    """Je eigenem Ort die Merkmale für Ortsbedingungen und Standortwahl – Spielwerte aus dem Mod, wo vorhanden."""
    zentren = {(last.get("markt") or {}).get("zentrum_id")} | {m.get("zentrum_id") for m in last.get("maerkte") or []}
    hier = wis.get("hierarchie") or {}
    hs = next((o for o in last.get("orte") or [] if o.get("hauptstadt")), None)
    kontinent = (hier.get(hs.get("key")) or {}).get("kontinent") if hs else None
    typen = {}
    for b in last.get("gebaeude") or []:
        typen.setdefault(b.get("ort_id"), set()).add(b.get("typ"))
    out = []
    for o in last.get("orte") or []:
        k = o.get("key")
        w = (ort_werte or {}).get(str(o["id"])) or (ort_werte or {}).get(o["id"]) or {}

        def mod(feld, ersatz=None):
            v = w.get(feld)
            return bool(v) if isinstance(v, (int, float)) else ersatz
        out.append({"id": o["id"], "key": k, "name": o["name"], "rang": o.get("rang"), "rohstoff": o.get("rohstoff"),
                    "entwicklung": o.get("entwicklung"), "steuer": o.get("steuer"), "marktzugang": o.get("marktzugang"),
                    "naehe": o.get("naehe"),
                    "hauptstadt": mod("IsCapital", o.get("hauptstadt") if "hauptstadt" in o else None),
                    "marktzentrum": mod("IsMarketCenter", o["id"] in zentren),
                    "kueste": mod("IsCoastal", k in ports()), "hafen": mod("HasPort", k in ports()),
                    "fluss": mod("HasRiver"), "bev_anteil": w.get("location_population_percentage"),
                    "rang_index": w.get("rank_index"),
                    "num_roads": w.get("num_roads") if isinstance(w.get("num_roads"), (int, float)) else len(o.get("strassen") or []),
                    "strasse_zur_hauptstadt": bool(o.get("strasse_zur_hauptstadt")),
                    "strassen": o.get("strassen") or [], "merkmale": (wis.get("ortsmerkmale") or {}).get(k) or {},
                    "hierarchie": hier.get(k) or {}, "gebaeude_typen": typen.get(o["id"], set()),
                    # Übersee = anderer Kontinent als die Hauptstadt (Annäherung an is_overseas_for_owner)
                    "ueberseeisch": ((hier.get(k) or {}).get("kontinent") != kontinent) if kontinent else None,
                    "pops": {t: (v or {}).get("groesse") or 0 for t, v in (o.get("pops_typen") or {}).items()}})
    return out


def _fmt(v, d=2):
    return sprache.ziffern(f"{v:,.{d}f}")


def _sgn(v, d=2):
    return ("+" if v > 0 else "") + _fmt(v, d)


def plane(key, F, c):
    """Schritte für einen Schwerpunkt. c: Kontext aus wirtschaftsplan.build (G, GEB, geb_info, hersteller, baubar, gs, orte,
    eigene, rgo, bt, gd, wis, unterhalt, modtxt, mengen, rt, preise, land, nm, min_anteil)."""
    G, gs, orte, nm = c["G"], c["gs"], c["orte"], c["nm"]
    GEB = c["GEB"]
    gruppen = {1: [], 2: [], 3: [], 4: []}
    belegt = set()                                    # (Gebäudeart, Ort) schon im Plan
    abgeloest = {}                                    # Art -> Arten, die sie ablösen (castle löst stockade ab)
    for a, s in gs.items():
        for x in s.get("loest_ab") or []:
            abgeloest.setdefault(x, set()).add(a)

    def gname(g):
        return G.get(g, {}).get("name") or g

    def geb(a):
        if a not in GEB:
            GEB[a] = c["geb_info"](a)
        return GEB[a]

    def alter(a):
        z = (gs.get(a) or {}).get("fortschritt_zeitalter")
        return ZEITALTER.index(z) if z in ZEITALTER else 9

    def fehlt_text(a):
        s = gs.get(a) or {}
        if not s.get("fortschritt"):
            return []
        z = s.get("fortschritt_zeitalter")
        return [f"Fortschritt fehlt: {', '.join(s['fortschritt'])}" + (f" ({nm(z)})" if z else "")]

    def verfuegbar(g):
        x = G.get(g) or {}
        return bool(x.get("eigene_rgo") or x.get("eigene_gebaeude") or (x.get("angebot") or 0) > 0)

    def ort_ok(a, o):
        """(True/None, offen) – Ortsart, kein Nachfolger im Ort, location_potential und allow; False -> None."""
        d = (c["bt"].get(a) or {}).get("def") or {}
        if d.get(o["rang"]) != "yes" or a in o["gebaeude_typen"] or (abgeloest.get(a, set()) & o["gebaeude_typen"]):
            return None
        r1, o1 = bedingung(d.get("location_potential"), o)
        r2, o2 = bedingung(d.get("allow"), o)
        if r1 is False or r2 is False:
            return None
        return (r1 is True and r2 is True), sorted(o1 | o2)

    def standort(a):
        """Bester eigener Ort für einen Neubau: Bedingung erfüllt vor nicht prüfbar, Pops des Typs, Marktzugang."""
        b = geb(a)
        kand = []
        for o in orte:
            if (a, o["id"]) in belegt:
                continue
            r = ort_ok(a, o)
            if not r:
                continue
            pops = o["pops"].get(b.get("pop_typ"), 0) if b.get("pop_typ") else 1
            if b.get("pop_typ") and pops <= 0:
                continue
            kand.append((0 if r[0] else 1, -pops, -(o["marktzugang"] or 0), o, r[1], pops))
        if not kand:
            return None
        kand.sort(key=lambda t: t[:3])
        return kand[0][3], kand[0][4], kand[0][5]

    def baugueter_text(b):
        return ", ".join(f"{gname(g)} {_fmt(m)}" for g, m in (b.get("baugueter") or {}).items()) or "–"

    ziele = [r for r in F["gueter"] if F["reihung"] == "wert" or (r["knapp"] and r["anteil"] >= c["min_anteil"])]
    ziele += [r for r in F["fehlen"] if not r.get("nur_rohstoff")]

    def anteil_text(r):
        return f"{_fmt(r['anteil'] * 100, 1)} % Anteil im Schwerpunkt" + (f", Preis {_fmt(G[r['gut']]['verh'])}× Grundpreis"
                                                                         if G[r["gut"]].get("verh") else "")

    # ---- Gruppe 1: Ausbau mit Spielwerten (Rohstoff, eigene Gebäude mit laufender Methode für das Gut)
    for r in ziele:
        g = r["gut"]
        if G[g].get("kategorie") == "raw_material":
            for x in sorted((x for x in c["rgo"].get(g, []) if isinstance(x.get("steuer_je_stufe"), (int, float))),
                            key=lambda x: -x["steuer_je_stufe"])[:1]:
                gruppen[1].append({
                    "wert": x["steuer_je_stufe"], "art": "rohstoff", "kategorie": "Produktion", "gut": g, "ort": x["ort"],
                    "gebaeude": None, "was": f"Rohstoff {gname(g)} ausbauen", "warum": f"{gname(g)}: {anteil_text(r)}",
                    "voraussetzung": "–", "wirkung": f"Steuergrundlage {_sgn(x['steuer_je_stufe'])} je Stufe (Spielwert, Mod)",
                    "kosten": (f"{_fmt(x['kosten'], 1)} Gold" + (f", {x['tage']} Tage" if x.get("tage") else "")) if x.get("kosten") else "Baumenü",
                    "quelle": "Spielwert"})
        for e in c["eigene"]:
            if g in e.get("produziert", []) and e.get("ausbaufaehig") and (e["typ"], e["ort_id"]) not in belegt:
                belegt.add((e["typ"], e["ort_id"]))
                gruppen[1].append({
                    "wert": e["gewinn_je_stufe"] or 0, "art": "ausbau", "kategorie": "Produktion", "gut": g, "ort": e["ort"],
                    "gebaeude": e["typ"], "was": f"{geb(e['typ'])['name']} ausbauen auf Stufe {e['stufe'] + 1:.0f}",
                    "warum": f"stellt mit der laufenden Methode {gname(g)} her ({anteil_text(r)})", "voraussetzung": "–",
                    "wirkung": f"Gewinn {_sgn(e['gewinn_je_stufe'] or 0, 3)} je Stufe"
                               + (f", Steuergrundlage {_sgn(e['steuer_je_stufe'], 3)}" if e.get("steuer_je_stufe") is not None else "")
                               + " (Spielwert, Mod: Durchschnitt je Stufe)",
                    "kosten": "Baumenü", "quelle": "Spielwert"})
                break
    gruppen[1].sort(key=lambda s: -s["wert"])

    # ---- Gruppe 2: Neubau, Voraussetzungen zuerst
    def neubau(g, r, tiefe=0):
        for a in sorted(c["hersteller"](g), key=lambda a: -((geb(a).get("gewinn") or {}).get("je_stufe") or 0)):
            st = standort(a)
            if not st:
                continue
            o, offen, pops = st
            b = geb(a)
            pm = max((p for p in b["pms"] if p["produziert"] == g), key=lambda p: p.get("menge") or 0, default=None)
            fehlend = [i for i in (pm or {}).get("eingang", {}) if not verfuegbar(i)]
            vor = []
            if tiefe == 0:
                for i in fehlend:
                    vor += neubau(i, None, 1)
            belegt.add((a, o["id"]))
            gw = b.get("gewinn")
            return vor + [{
                "art": "neubau", "kategorie": "Produktion", "gut": g, "ort": o["name"], "gebaeude": a,
                "was": f"{b['name']} neu bauen" + (f" (Methode {(c['wis'].get('namen') or {}).get('pms', {}).get(pm['name']) or pm['name']})"
                                                     if pm and len([p for p in b["pms"] if p["produziert"]]) > 1 else ""),
                "warum": (f"{gname(g)} {'fehlt im Markt' if G[g].get('preis') is None else 'ist knapp' if (r or {}).get('knapp') else 'ist gefragt'}"
                          + (f" ({anteil_text(r)})" if r else " – Eingangsgut für den nächsten Schritt")),
                "voraussetzung": "; ".join(
                    [f"Eingang {gname(i)} fehlt im Markt – Schritt davor" for i in fehlend]
                    + [f"{nm(b['pop_typ']) if b.get('pop_typ') else 'Pops'} in {o['name']}: {_fmt(pops, 1)} Tsd."]
                    + ([f"Bedingung nicht prüfbar: {', '.join(offen)}"] if offen else [])) or "–",
                "wirkung": (f"Gewinn je Stufe {_fmt(gw['je_stufe'], 3)} ({gw['quelle']}, {gw['gebaeude']} Gebäude – Spielwert, Durchschnitt)"
                            if gw else "Gewinn unbekannt (keine solchen Gebäude im Spielstand)"),
                "kosten": f"Baumenü; Baugüter je Stufe: {baugueter_text(b)}", "quelle": "Spielwert" if gw else "unbekannt"}]
        return []

    for r in ziele:
        if len(gruppen[2]) >= PLAETZE[2]:
            break
        neu = neubau(r["gut"], r)
        if len(gruppen[2]) + len(neu) <= PLAETZE[2]:          # Voraussetzung und Schritt nur zusammen
            gruppen[2] += neu

    # ---- Gruppe 3: Gebäude mit Wirkung (Markt und Handel, Militär, Zivil)
    mods = WIRKUNG.get(key, ())
    land = c.get("land") or {}
    festung_frei = (land.get("GetFortLimit") - land.get("used_fort_limit")) if isinstance(land.get("GetFortLimit"), (int, float)) \
        and isinstance(land.get("used_fort_limit"), (int, float)) else None
    kand = []
    for a, e in c["bt"].items():
        d = e.get("def") or {}
        s = gs.get(a) or {}
        if s.get("sonder") and not s.get("freischaltung"):
            continue                                  # Denkmäler/Ereignisgebäude
        land_ok = not s.get("landbedingung") or s.get("land_erfuellt")
        if not (c["baubar"](a) or (s.get("freischaltung") and s.get("erreichbar") and land_ok)):
            continue                                  # nur baubar oder mit erreichbarem Fortschritt (nicht: andere Kulturen/Regierungen)
        m = {x: v for x, v in (d.get("modifier") or {}).items() if x in mods} if isinstance(d.get("modifier"), dict) else {}
        h = {x: v for x, v in (d.get("capital_modifier") or {}).items() if x in mods} if isinstance(d.get("capital_modifier"), dict) else {}
        nutzen = [x for x, v in {**m, **h}.items()
                  if v == "yes" or (isinstance(v, (int, float)) and (v < 0 if x in NEGATIV_GUT else v > 0))]
        if nutzen:
            kand.append((1 if s.get("fortschritt") else 0, alter(a), -len(nutzen), a, m, h, d, nutzen))
    kand.sort(key=lambda t: (t[0], t[1], t[2], (c["bt"].get(t[3]) or {}).get("name") or t[3]))
    gewaehlt = set()
    hauptstadt = next((o for o in orte if o["hauptstadt"]), None)
    festungen = 0
    for _, _, _, a, m, h, d, nutzen in kand:
        if len(gruppen[3]) >= PLAETZE[3]:
            break
        kette = abgeloest.get(a, set()) | set((gs.get(a) or {}).get("loest_ab") or [])
        if kette & gewaehlt:
            continue                                  # aus derselben Ablösekette nur ein Gebäude
        fest = "local_garrison_size" in (d.get("modifier") or {})
        if fest and festung_frei is not None and festungen + 1 > festung_frei:
            continue                                  # Festungsgrenze (Mod: GetFortLimit − used_fort_limit)
        if h and not m:                               # wirkt nur in der Hauptstadt
            r = ort_ok(a, hauptstadt) if hauptstadt else None
            if not r:
                continue
            o, offen = hauptstadt, r[1]
        else:
            st = standort(a)
            if not st:
                continue
            o, offen = st[0], st[1]
        b, s = geb(a), gs.get(a) or {}
        belegt.add((a, o["id"]))
        gewaehlt.add(a)
        festungen += fest
        wtxt = [c["modtxt"](x, v) for x, v in m.items()] + [c["modtxt"](x, v) + " (in der Hauptstadt)" for x, v in h.items()]
        uk = c["unterhalt"](a)
        kat = KATEGORIE.get(d.get("category"), "Zivil")
        if kat != "Militär" and set(nutzen) & MARKT:
            kat = "Markt und Handel"
        elif kat != "Militär" and key in ("landheer", "marine") and set(nutzen) & MILITAER:
            kat = "Militär"
        kat_spiel = c["nm"](d["category"]) if d.get("category") else None
        gruppen[3].append({
            "art": "wirkung", "kategorie": kat, "kategorie_spiel": kat_spiel, "gut": None, "ort": o["name"],
            "gebaeude": a, "was": f"{b['name']} bauen",
            "warum": f"{kat_spiel or 'Gebäude'} mit Wirkung auf den Schwerpunkt"
                     + (f" – bei uns schon ×{s['bei_uns']} an anderem Ort" if s.get("bei_uns") else ""),
            "voraussetzung": "; ".join(fehlt_text(a) + ([f"Bedingung nicht prüfbar: {', '.join(offen)}"] if offen else [])
                                       + ([f"Festungsgrenze: {_fmt(land['used_fort_limit'], 1)} von {_fmt(land['GetFortLimit'], 2)} belegt"]
                                          if fest and festung_frei is not None else [])) or "–",
            "wirkung": ", ".join(wtxt) + " je Stufe (Spieldatei)",
            "kosten": f"Baumenü; Baugüter je Stufe: {baugueter_text(b)}" + (f"; Unterhalt {uk}" if uk else ""),
            "quelle": "Spieldatei"})

    # ---- Gruppe 4: Straßen zur Hauptstadt
    hs = next((o for o in orte if o["hauptstadt"]), None)
    rt = (c["rt"].get("gravel_road") or {}).get("def") or {}
    if key in STRASSE_FOKUS and hs and rt:
        preis = ((c["preise"].get(rt.get("price_per_unit_distance")) or {}).get("def") or {}).get("gold")
        bg = ", ".join(f"{gname(g)} {_fmt(v)}" for g, v in c["mengen"](rt.get("construction_demand")).items()) or "–"
        name = (c["rt"].get("gravel_road") or {}).get("name") or "Schotterstraße"
        felder = ", ".join(f"{k} {_sgn(v)}" for k, v in rt.items() if k in ("movement_cost", "market_access", "pop_movement", "proximity"))
        ohne = sorted((o for o in orte if not o["strasse_zur_hauptstadt"] and not o["hauptstadt"]), key=lambda o: -(o["steuer"] or 0))
        for o in ohne[:PLAETZE[4]]:
            gruppen[4].append({
                "art": "strasse", "kategorie": "Straße", "gut": None, "ort": o["name"], "gebaeude": None,
                "was": f"{name} {hs['name']} → {o['name']}",
                "warum": f"{o['name']} hat keine Straße zur Hauptstadt (Spielstand road_to_capital; Nähe {_fmt(o['naehe'] or 0, 0)}, "
                         f"Steuer {_fmt(o['steuer'] or 0)})",
                "voraussetzung": "Weg über Nachbarorte nicht geprüft",
                "wirkung": f"Spieldatei road_types ({name}): {felder} – Bedeutung der Felder nicht am Spiel geprüft",
                "kosten": (f"{_fmt(preis, 0)} Gold je Entfernungseinheit" if preis else "Straßenbau im Spiel") + f"; Baugüter: {bg}",
                "quelle": "Spieldatei"})

    schritte = []
    for n in (1, 2, 3, 4):
        for s in gruppen[n][:PLAETZE[n]]:
            s["gruppe"] = n
            s.pop("wert", None)
            schritte.append(s)
    for i, s in enumerate(schritte, 1):
        s["nr"] = i
    return schritte
