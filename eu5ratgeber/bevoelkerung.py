"""Bevölkerung: alles zur Bevölkerung des Spielerlandes an einer Stelle.

Quellen:
  - Spielstand (Momentaufnahme, `roh`): jede Pop (Typ, Kultur, Religion, Status, Größe, Zufriedenheit, Bildung),
    je Ort `population.pop_stats` (Veränderung letzter Monat je Pop-Typ und Ursache, Arbeitslose),
    `changes_culture` / `changes_religion`, `last_months_migrations` (einzelne Wanderungen).
  - Mod (live, /api/alles): Land-, Orts-, Provinz- und Pop-Werte, Land-Modifikatoren und Aufschlüsselungs-Texte,
    ausgewählt nach Stichworten (PARAM).
Beobachtet: je Pop-Typ ist "last" die Summe der "changes" (Test Holland 1339).
"""
import json
import re

from . import history

# Ursachen der Veränderung, wie sie im Spielstand stehen
CHANGE_NAMES = {"Reproduction": "Wachstum", "PromotionIn": "Aufstieg herein", "PromotionOut": "Aufstieg hinaus",
                "DemotionIn": "Abstieg herein", "DemotionOut": "Abstieg hinaus", "MigrationIn": "Zuwanderung",
                "MigrationOut": "Abwanderung", "Assimilation": "Assimilation", "Conversion": "Bekehrung"}
# Stichworte für "alle Parameter, die mit der Bevölkerung zusammenhängen" (Schlüssel der Live-Werte/Modifikatoren/Texte)
PARAM = re.compile(r"pop|migra|litera|satisf|assimil|convers|growth|cultur|religi|food|employ|capacity|promot|demot|"
                   r"reproduc|heathen|heretic|faith|tolerat|accepted|primary|starv|slave|peasant|burgher|noble|clergy|"
                   r"laborer|soldier|tribesm|unrest|rebel", re.I)


def _sum_changes(target, changes):
    for kind, v in (changes or {}).items():
        target[kind] = target.get(kind, 0.0) + (v or 0.0)


def _data_changes(block, key):
    """{"MigrationOut": {"data": [{"culture": 1057, "change": -0.002}]}} -> {1057: {"MigrationOut": -0.002}}"""
    out = {}
    for kind, v in (block or {}).items():
        for e in (v or {}).get("data", []):
            out.setdefault(e.get(key), {})[kind] = out.get(e.get(key), {}).get(kind, 0.0) + (e.get("change") or 0.0)
    return out


def build(db, pid, names, modtypes=None):
    r = history.roh(db, pid)
    if not r:
        return None
    roh = r["roh"]
    tag_row = db.execute("SELECT tag FROM momentaufnahmen WHERE partie_id=? ORDER BY jahr DESC LIMIT 1", (pid,)).fetchone()
    live = history.live_alles(db, tag_row[0]) if tag_row else {"werte": {}, "texte": {}, "datum": {}}
    W = live["werte"]
    loc_keys = history.location_keys(db)

    def loc_name(i):
        try:
            k = history.location_key(loc_keys, int(i))
        except (ValueError, TypeError):
            k = None
        return names(k) if k else f"Ort {i}"

    # Namen für Kultur/Religion: live (Mod 0.14: alle vorkommenden), sonst Spielstand, sonst Kennung
    cul_names = {str(k): names(v.get("name")) for k, v in (roh.get("kulturen") or {}).items()}
    cul_names.update({str(k): v["name"] for k, v in W.get("kultur", {}).items() if v.get("name")})
    rel = roh.get("religion") or {}
    rel_names = {str(rel.get("index")): names(rel.get("key"))} if rel else {}
    rel_names.update({str(k): v["name"] for k, v in W.get("religion", {}).items() if v.get("name")})

    # ---- Pops: je Typ, Kultur, Religion
    typen, kulturen, religionen = {}, {}, {}
    total = 0.0
    for p in (roh.get("pops") or {}).values():
        s = p.get("size") or 0.0
        total += s
        t = typen.setdefault(p.get("type"), {"groesse": 0.0, "pops": 0, "zuf": 0.0, "bild": 0.0})
        t["groesse"] += s
        t["pops"] += 1
        t["zuf"] += s * (p.get("satisfaction") or 0.0)
        t["bild"] += s * (p.get("literacy") or 0.0)
        k = kulturen.setdefault(str(p.get("culture")), {"groesse": 0.0, "status": set()})
        k["groesse"] += s
        if p.get("status"):
            k["status"].add(p["status"])
        religionen.setdefault(str(p.get("religion")), {"groesse": 0.0})["groesse"] += s

    # ---- Orte: Veränderung je Typ/Ursache, Arbeitslose, Wanderungen
    orte, alle_changes, typ_changes, typ_arbeitslos = [], {}, {}, {}
    cul_changes, rel_changes, wanderung = {}, {}, {}
    live_orte = W.get("ort", {})
    for lid, o in (roh.get("orte") or {}).items():
        pop = o.get("population") or {}
        ch, arbeitslos, groesse_typ = {}, 0.0, {}
        for typ, st in (pop.get("pop_stats") or {}).items():
            _sum_changes(ch, st.get("changes"))
            _sum_changes(typ_changes.setdefault(typ, {}), st.get("changes"))
            arbeitslos += st.get("unemployed") or 0.0
            typ_arbeitslos[typ] = typ_arbeitslos.get(typ, 0.0) + (st.get("unemployed") or 0.0)
        _sum_changes(alle_changes, ch)
        for c, v in _data_changes(pop.get("changes_culture"), "culture").items():
            _sum_changes(cul_changes.setdefault(str(c), {}), v)
        for c, v in _data_changes(pop.get("changes_religion"), "religion").items():
            _sum_changes(rel_changes.setdefault(str(c), {}), v)
        for m in pop.get("last_months_migrations") or []:
            key = (lid, str(m.get("destination")), m.get("pop_type"))
            wanderung[key] = wanderung.get(key, 0.0) + (m.get("amount") or 0.0)
        pops_hier = [roh["pops"].get(str(i)) for i in pop.get("pops") or [] if str(i) in (roh.get("pops") or {})]
        for p in pops_hier:
            groesse_typ[p.get("type")] = groesse_typ.get(p.get("type"), 0.0) + (p.get("size") or 0.0)
        g = sum(groesse_typ.values())
        lv = live_orte.get(str(lid)) or live_orte.get(lid) or {}
        orte.append({
            "id": int(lid), "name": loc_name(lid), "groesse": g, "veraenderung": sum(ch.values()), "ursachen": ch,
            "arbeitslos": arbeitslos, "typen": groesse_typ,
            "zufriedenheit": (sum((p.get("size") or 0) * (p.get("satisfaction") or 0) for p in pops_hier) / g) if g else None,
            "bildung": (sum((p.get("size") or 0) * (p.get("literacy") or 0) for p in pops_hier) / g) if g else None,
            # live (Mod): Kapazität, Wachstum, Wanderungsanziehung, Beschäftigung, Nahrung
            "kapazitaet": lv.get("location_max_population"), "auslastung": lv.get("GetCapacityPercentage"),
            "wachstum_live": lv.get("GetPopGrowth"), "anziehung": lv.get("migration_attraction"),
            "beschaeftigung": lv.get("employment_percentage"), "nahrung_prod": lv.get("food_production"),
            "nahrung_verbr": lv.get("food_consumption"), "ueberbevoelkert": lv.get("IsOverPopulationCapacity"),
            "bekehrung": lv.get("monthly_conversion"),
        })
    orte.sort(key=lambda o: -o["groesse"])

    typ_list = [{"typ": t, "name": names(t), "groesse": v["groesse"], "anteil": v["groesse"] / total if total else None,
                 "pops": v["pops"], "zufriedenheit": v["zuf"] / v["groesse"] if v["groesse"] else None,
                 "bildung": v["bild"] / v["groesse"] if v["groesse"] else None,
                 "arbeitslos": typ_arbeitslos.get(t, 0.0), "ursachen": typ_changes.get(t, {}),
                 "veraenderung": sum(typ_changes.get(t, {}).values())}
                for t, v in typen.items()]
    typ_list.sort(key=lambda x: -x["groesse"])
    kul_list = [{"id": k, "name": cul_names.get(k, f"Kultur {k}"), "groesse": v["groesse"],
                 "anteil": v["groesse"] / total if total else None, "status": sorted(v["status"]),
                 "ursachen": cul_changes.get(k, {}), "veraenderung": sum(cul_changes.get(k, {}).values())}
                for k, v in kulturen.items()]
    kul_list.sort(key=lambda x: -x["groesse"])
    rel_list = [{"id": k, "name": rel_names.get(k, f"Religion {k}"), "groesse": v["groesse"],
                 "anteil": v["groesse"] / total if total else None, "staatsreligion": k == str(rel.get("index")),
                 "ursachen": rel_changes.get(k, {}), "veraenderung": sum(rel_changes.get(k, {}).values())}
                for k, v in religionen.items()]
    rel_list.sort(key=lambda x: -x["groesse"])
    wand = [{"von": loc_name(a), "nach": loc_name(b), "typ": names(t), "menge": m}
            for (a, b, t), m in sorted(wanderung.items(), key=lambda x: -x[1])]

    # ---- alle Live-Parameter zur Bevölkerung (Mod), Land-Modifikatoren ≠ 0 mit Namen
    land = next(iter(W.get("land", {}).values()), {})
    lmod = next(iter(W.get("landmod", {}).values()), {})
    mt = modtypes or {}

    def mname(k):
        return (mt.get(k) or {}).get("name") or k
    parameter = {
        "land": {k: v for k, v in sorted(land.items()) if PARAM.search(k) and k != "name"},
        # percent: Wert als Anteil (0.1 = 10 %), already_percent: Wert schon in Prozent (_modifikator_typen.json)
        "modifikatoren": [{"key": k, "name": mname(k), "wert": v, "prozent": (mt.get(k) or {}).get("percent") == "yes"}
                          for k, v in sorted(lmod.items()) if v and PARAM.search(k)],
        "provinzen": {(v.get("name") or k): {f: x for f, x in v.items() if PARAM.search(f)}
                      for k, v in W.get("provinz", {}).items()},
    }
    texte = {}
    for bereich in ("land", "ort", "provinz", "pop", "stand", "kultur", "religion"):
        for oid, felder in (live.get("texte", {}).get(bereich) or {}).items():
            sel = {f: t for f, t in felder.items() if PARAM.search(f)}
            if sel:
                label = loc_name(oid) if bereich == "ort" else str(oid)
                texte.setdefault(bereich, {})[label] = sel
    return {
        "datum": r["datum"], "live_datum": (live.get("datum") or {}).get("land"),
        "gesamt": total, "gesamt_live": land.get("total_population"),
        "veraenderung": sum(alle_changes.values()), "veraenderung_live": land.get("monthly_population_change"),
        "ursachen": alle_changes, "ursachen_namen": CHANGE_NAMES,
        "bildung": land.get("average_country_literacy"), "kapazitaet": sum(o["kapazitaet"] or 0 for o in orte) or None,
        "arbeitslos": sum(o["arbeitslos"] for o in orte),
        "zufriedenheit": (sum(t["zufriedenheit"] * t["groesse"] for t in typ_list if t["zufriedenheit"] is not None) / total)
        if total else None,
        "typen": typ_list, "kulturen": kul_list, "religionen": rel_list, "orte": orte, "wanderung": wand,
        "parameter": parameter, "texte": texte,
    }


def load_modtypes(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}
