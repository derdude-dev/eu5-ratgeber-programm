"""Vollständiges Spielwissen aus den Spieldateien (Ziel des Nutzers 28.09.: alle Informationen, die das Spiel hat).

    data/spielwissen/<version>/<ordner>.json   jede Definition eines common-Ordners, zerlegt, mit Namen/Beschreibung
    data/spielwissen/<version>/_index.json     Ordner, Anzahl, Felder
    data/spielwissen/<version>/_modifikator_quellen.json
        Rückwärtsindex: Modifikator -> [(ordner, definition, pfad, wert)] - woher ein Wert kommen kann
    data/spielwissen/<version>/_modifikator_typen.json   percent/boolean/decimals je Modifikator (Anzeige)

Ordner: alle unter game/**/common (in_game, main_menu, loading_screen, dlc). Ausgelassen nur reine Grafik/Ton/
Oberflächen-Daten (Wappen, Gene, Musik …). Gebaut beim ersten Start einer neuen Spielversion (~1 min).
"""
import collections
import json
import os
import re

from . import gamedata, pdx, pfade
from . import sprache

GAME = gamedata.GAME_DIR
SKIP = {"coat_of_arms", "ethnicities", "genes", "persistent_dna", "music_player_tracks", "flag_definitions",
        "named_colors", "tutorial_lesson_chains", "tutorial_lessons", "modifier_icons", "attribute_columns", "dlc",
        "effect_localization", "trigger_localization", "graphic", "jomini"}
FORMAT = 3       # 2: Konstanten in den Modifikator-Quellen aufgelöst; 3: Namen mit [Show…('x')|l], [Concept('x', 'Text')] (29.10.)


def folders():
    """{ordner: [Dateien]} über alle common-Verzeichnisse des Spiels."""
    out = collections.defaultdict(list)
    for root, dirs, files in os.walk(GAME):
        # relativ zum Spielordner - der Steam-Pfad selbst enthält "steamapps/common"
        parts = os.path.relpath(root, GAME).replace("\\", "/").split("/")
        if "common" not in parts:
            continue
        i = parts.index("common")
        if len(parts) <= i + 1:
            continue
        name = parts[i + 1]
        if name in SKIP or any(p in SKIP for p in parts[i + 1:]):
            continue
        out[name] += [os.path.join(root, f) for f in files if f.endswith(".txt")]
    return out


def _walk(v, path, visit):
    if isinstance(v, dict):
        for k, x in v.items():
            visit(k, x, path)
            _walk(x, path + [k], visit)
    elif isinstance(v, list):
        for x in v:
            _walk(x, path, visit)


def build(out_dir, names=None, modifier_names=None):
    names = names or gamedata.Names()
    os.makedirs(out_dir, exist_ok=True)
    mods = set(modifier_names or [])
    quellen = collections.defaultdict(list)
    index = {}
    for folder, files in sorted(folders().items()):
        defs = {}
        for fn in sorted(files):
            try:
                parsed = pdx.parse(open(fn, "rb").read().lstrip(b"\xef\xbb\xbf"))
            except Exception as e:                       # einzelne Datei nicht den Bau abbrechen lassen
                defs[f"_fehler:{os.path.basename(fn)}"] = str(e)
                continue
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if k != "_items":
                        defs[k] = v
        rows = {}
        fields = collections.Counter()
        for k, v in defs.items():
            k = str(k)                                   # manche Ordner haben Zahlen als Schlüssel
            nm = names(k) if not k.startswith(("@", "_")) else k
            desc = names.loc.get(f"{k}_desc")
            rows[k] = {"name": nm if nm != k else None, "beschreibung": gamedata.clean_loc(desc, names.loc) if desc else None,
                       "def": v}
            if isinstance(v, dict):
                fields.update(v.keys())
            if mods:
                def visit(key, val, path, _k=k):
                    if key in mods and isinstance(val, (int, float, str)):
                        quellen[key].append([folder, _k, "/".join(map(str, path)), val])
                _walk(v, [], visit)
        with open(os.path.join(out_dir, f"{folder}.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        index[folder] = {"anzahl": len(rows), "felder": fields.most_common(40), "dateien": len(files)}
    # benannte Konstanten (small_tax_income_efficiency_bonus …) auflösen: der Zahlenwert kommt dazu
    from .wissen import _constants
    const = _constants()
    for rows_ in quellen.values():
        for q in rows_:
            if isinstance(q[3], str) and isinstance(const.get(q[3]), (int, float)):
                q.append(const[q[3]])
    with open(os.path.join(out_dir, "_modifikator_quellen.json"), "w", encoding="utf-8") as f:
        json.dump(quellen, f, ensure_ascii=False)
    pfade.atomar_schreiben(os.path.join(out_dir, "_index.json"), json.dumps(index, ensure_ascii=False).encode("utf-8"))
    return index


def modifier_types(out_dir, names):
    """Name (MODIFIER_TYPE_NAME_<x>) und percent / boolean / decimals je Modifikator (für die Anzeige)."""
    p = os.path.join(out_dir, "modifier_type_definitions.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p, encoding="utf-8"))
    out = {}
    for k, v in d.items():
        e = {f: v["def"].get(f) for f in ("percent", "boolean", "decimals", "already_percent", "color", "game_data")
             if isinstance(v["def"], dict) and f in v["def"]}
        raw = names.loc.get(f"MODIFIER_TYPE_NAME_{k}")
        e["name"] = (gamedata.clean_loc(raw, names.loc) if raw else None) or k
        out[k] = e
    return out


def ensure(cache_dir, version, names=None, modifier_names=None, log=print):
    version = version.split("/")[0]                      # wissen._version() hängt "/f<Format>" an
    zusatz = "" if sprache.DEUTSCH else f"_{sprache.ORDNER}"     # Namen je Sprache; Wiki, Techbaum und Startstrategie liegen in diesem Ordner
    out = os.path.join(cache_dir, "spielwissen", re.sub(r"[^\w.-]", "_", f"{version}_f{FORMAT}{zusatz}"))
    typen = os.path.join(out, "_modifikator_typen.json")          # entsteht zuletzt: fehlt sie, brach der Bau ab
    if not (os.path.exists(os.path.join(out, "_index.json")) and os.path.exists(typen)):
        log(f"Spielwissen (vollständig) wird gebaut: {out}")
        names = names or gamedata.Names()
        build(out, names, modifier_names)
        pfade.atomar_schreiben(typen, json.dumps(modifier_types(out, names), ensure_ascii=False).encode("utf-8"))
    return out


def load_folder(out, folder):
    p = os.path.join(out, f"{os.path.basename(folder)}.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
