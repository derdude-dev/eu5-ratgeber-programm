"""Spielwissen aus den Spieldateien: Karte, Güter, Gebäude/Produktionsmethoden, Privilegien, Namen.

Einmal gebaut und in data/spielwissen.json zwischengespeichert; neu gebaut, wenn sich die Spielversion
(logs/code_revisions.log) ändert.

Quellen (Pfade relativ zu game/):
  in_game/map_data/definitions.txt          Kontinent > Subkontinent > Region > Gebiet > Provinz > Orte
  in_game/map_data/location_templates.txt   je Ort topography, vegetation, climate, raw_material, …
  in_game/common/goods                      Kategorie, Grundpreis, Nahrung, Pop-Nachfrage
  in_game/common/building_types             Kategorie, Pop-Typ, Produktionsmethoden (eigene oder geteilte)
  in_game/common/production_methods         geteilte Produktionsmethoden
  in_game/common/estate_privileges          Stand und country_modifier
  main_menu/common/script_values            benannte Konstanten (z. B. medium_privilege_target_satisfaction)
  Lokalisierung                             Namen; Modifikatoren unter MODIFIER_TYPE_NAME_<name>
"""
import glob
import json
import os
import re

from . import gamedata, pdx, pfade
from . import sprache

GAME = gamedata.GAME_DIR
REVISIONS = os.path.join(pfade.nutzer(), "logs", "code_revisions.log")
PM_META = {"produced", "output", "category", "debug_max_profit", "potential", "allow", "is_default",
           "employment_size", "no_upkeep", "ai_weight"}


def _parse_file(path):
    with open(path, "rb") as f:
        return pdx.parse(f.read().lstrip(b"\xef\xbb\xbf"))


FORMAT = 4       # erhöhen, wenn sich der Aufbau von spielwissen.json ändert (4: Namen mit [Show…('x')|l], 29.10.)


def _version():
    # Spielversion auch auf Beta-Zweigen („release/next“, 27.10.) – spielversion.spiel_version
    from . import spielversion
    # Namen stehen in der Sprache des Spiels im Spielwissen: je Sprache eine Fassung (Deutsch wie bisher)
    return f"{spielversion.spiel_version() or '?'}/f{FORMAT}" + ("" if sprache.DEUTSCH else f"/{sprache.ORDNER}")


def _hierarchy():
    tree = _parse_file(os.path.join(GAME, "in_game", "map_data", "definitions.txt"))
    out = {}

    def walk(node, path):
        if isinstance(node, list):                   # unterste Ebene: Liste der Orte einer Provinz
            cont, sub, reg, area, prov = (path + [None] * 5)[:5]
            for loc in node:
                out[str(loc)] = {"kontinent": cont, "subkontinent": sub, "region": reg, "gebiet": area, "provinz": prov}
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [k])
    walk(tree, [])
    return out


def _templates():
    t = _parse_file(os.path.join(GAME, "in_game", "map_data", "location_templates.txt"))
    keep = ("topography", "vegetation", "climate", "raw_material", "natural_harbor_suitability", "culture", "religion")
    return {k: {f: v.get(f) for f in keep if f in v} for k, v in t.items() if isinstance(v, dict)}


def _constants():
    out = {}
    for fn in glob.glob(os.path.join(glob.escape(GAME), "main_menu", "common", "script_values", "*.txt")):
        for k, v in _parse_file(fn).items():
            if isinstance(v, (int, float)):
                out[k] = v
    return out


def _resolve(v, const):
    if isinstance(v, str) and v in const:
        return const[v]
    return v


def _pm(name, body):
    inputs = {k: v for k, v in body.items() if isinstance(v, (int, float)) and k not in PM_META}
    return {"name": name, "inputs": inputs, "produced": body.get("produced"), "output": body.get("output"),
            "category": body.get("category")}


def _buildings(shared_pms):
    out = {}
    for k, b in gamedata.load_defs("building_types").items():
        if not isinstance(b, dict):
            continue
        # Jeder Block unique_/possible_production_methods ist eine eigene Gruppe (mehrere Blöcke möglich,
        # z. B. fine_cloth_guild); "gruppe" zählt sie durch.
        pms = []
        gruppe = 0
        for block in pdx.as_list(b.get("unique_production_methods")):
            if isinstance(block, dict):
                gruppe += 1
                pms += [{**_pm(n, pb), "gruppe": gruppe} for n, pb in block.items() if isinstance(pb, dict)]
        raw = b.get("possible_production_methods")
        # ein Block = Liste von Namen; mehrere Blöcke = Liste von Listen
        blocks = [raw] if isinstance(raw, list) and all(isinstance(x, str) for x in raw) else \
            [x if isinstance(x, list) else [x] for x in pdx.as_list(raw)]
        for names in blocks:
            gruppe += 1
            for name in names:
                if isinstance(name, str) and name in shared_pms:
                    pms.append({**shared_pms[name], "gruppe": gruppe})
        out[k] = {"category": b.get("category"), "pop_type": b.get("pop_type"), "pms": pms}
    return out


def _goods():
    out = {}
    for k, g in gamedata.load_defs("goods").items():
        if isinstance(g, dict):
            out[k] = {f: g.get(f) for f in ("category", "method", "default_market_price", "food", "transport_cost",
                                             "demand_add", "demand_multiply") if f in g}
    return out


def _privileges(const):
    out = {}
    for k, p in gamedata.load_defs("estate_privileges").items():
        if isinstance(p, dict):
            mods = p.get("country_modifier") if isinstance(p.get("country_modifier"), dict) else {}
            out[k] = {"estate": p.get("estate"), "modifiers": {m: _resolve(v, const) for m, v in mods.items()}}
    return out


def build(names=None):
    names = names or gamedata.Names()
    shared = {}
    for k, v in gamedata.load_defs("production_methods").items():
        if isinstance(v, dict):
            shared[k] = _pm(k, v)
    const = _constants()
    buildings = _buildings(shared)
    goods = _goods()
    # Verwendung der Güter: wer produziert sie, wer verbraucht sie (Gebäude/Produktionsmethode)
    for bk, b in buildings.items():
        for pm in b["pms"]:
            if pm["produced"] in goods:
                goods[pm["produced"]].setdefault("produziert_von", []).append({"gebaeude": bk, "pm": pm["name"], "menge": pm["output"]})
            for g, amt in pm["inputs"].items():
                if g in goods:
                    goods[g].setdefault("verbraucht_von", []).append({"gebaeude": bk, "pm": pm["name"], "menge": amt})
    privileges = _privileges(const)
    loc = names.loc
    mod_names = {k[len("MODIFIER_TYPE_NAME_"):]: gamedata.clean_loc(v, loc) or k[len("MODIFIER_TYPE_NAME_"):]
                 for k, v in loc.items() if k.startswith("MODIFIER_TYPE_NAME_")}

    def n(k):
        return names(k)

    return {
        "version": _version(),
        "hierarchie": _hierarchy(),
        "ortsmerkmale": _templates(),
        "gueter": goods,
        "gebaeude": buildings,
        "privilegien": privileges,
        "namen": {
            "modifikatoren": mod_names,
            "gueter": {k: n(k) for k in goods},
            "gebaeude": {k: n(k) for k in buildings},
            "pms": {pm["name"]: n(pm["name"]) for b in buildings.values() for pm in b["pms"]},
            "privilegien": {k: n(k) for k in privileges},
        },
    }


def load(cache_dir, names=None):
    """Spielwissen aus dem Cache; neu bauen, wenn die Spielversion wechselt."""
    path = os.path.join(cache_dir, "spielwissen.json")
    ver = _version()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") == ver:
            return data
    except (OSError, ValueError):                       # fehlt oder ist beschädigt: neu bauen
        pass
    data = build(names)
    os.makedirs(cache_dir, exist_ok=True)
    pfade.atomar_schreiben(path, json.dumps(data, ensure_ascii=False).encode("utf-8"))
    return data
