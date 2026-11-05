"""Kachel Nachbarn und Kriegsgelegenheiten (Nutzerwunsch 25.10.): Stärke der Nachbarn und selbst gewählter Länder, Ampel
„Krieg möglich?“ mit Begründung.

Quellen:
- Daten-Mod, neuester Monat: RG1D je Land mit Beziehung (nachbar, rivale, kb_ziel = wir haben einen Kriegsgrund, kb_gegen_uns …)
  mit relativer Stärke (relative_strength), ab 0.20 relative Bündnisstärke (relative_defensive_alliance_strength gegen uns),
  Waffenstillstand (has_truce_with), im Krieg (at_war), Krieg ohne Kriegsgrund möglich (can_declare_no_cb_war_on);
  RG2 fremd je Land alle Landeswerte (army_size, defensive_alliance_strength …), RG2 land für uns (offensive_alliance_strength …).
- Spielstand (Format 14, snapshot.laender_militaer): alle lebenden Länder – Rang, Militärwertung des Spiels, Mannstärke,
  Regimenter, Schiffe, Mann, Fortschritte, laufende Kriege. Für Länder ohne Beziehung zu uns gibt es nur diese Werte.
Ampel (Regeln des Ratgebers, die Zahlen sind Spielwerte): Verhältnis unseres Offensivbündnisses (offensive_alliance_strength:
wir samt allen, die wir in einen Angriffskrieg rufen können) zu ihrem Verteidigungsbündnis (defensive_alliance_strength: sie samt
allen, die sie verteidigen); grün ab 1,5 mit Kriegsgrund und ohne Waffenstillstand, gelb ab 1,0 oder nur Krieg ohne Kriegsgrund,
rot bei Waffenstillstand, ohne jeden möglichen Kriegsgrund oder unter 1,0; grau ohne Bündnisstärke (nur Spielstand).
"""
import json

from . import sprache
from .sprache import ue

GRUEN, GELB = 1.5, 1.0
# Beziehungen, deren Länder die Kachel ohne Auswahl zeigt
STANDARD = ("nachbar", "kb_ziel", "rivale", "kb_gegen_uns")
WERTE = ("army_size", "navy_size", "num_regiments", "manpower", "max_manpower", "sailors", "max_sailors", "military_strength",
         "country_strength", "defensive_alliance_strength", "offensive_alliance_strength", "stability", "war_exhaustion",
         "army_tradition", "great_power_ranking", "num_forts")
DIPLO = ("rel_strength", "rel_def", "truce", "at_war", "ohne_kb", "antagonism", "op_them", "op_us")
SPALTEN = ("tag", "name", "rang", "mil_wertung", "mil_rang", "mannstaerke", "max_mannstaerke", "seeleute", "max_seeleute",
           "armeetradition", "fortschritte", "orte", "kriege", "regimenter", "schiffe", "mann", "ohne_staerke")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _de(v, d=2):
    return sprache.ziffern(f"{v:,.{d}f}")


def _zeilen(db, tag, art):
    r = db.execute("SELECT MAX(jahr*12+monat) FROM monat_extra WHERE tag=? AND art=?", (tag, art)).fetchone()
    if not r or not r[0]:
        return {}, None
    return ({k: json.loads(w) for k, w in db.execute(
        "SELECT schluessel, werte FROM monat_extra WHERE tag=? AND art=? AND jahr*12+monat=?", (tag, art, r[0]))},
        f"{(r[0] - 1) // 12}.{(r[0] - 1) % 12 + 1}.1")


def bewertung(r, wir, veraltet=None):
    """Ampel und Gründe für einen Angriff auf das Land r (Mod-Werte); Hinweise ändern die Ampel nicht. veraltet: Text, wenn die
    Mod-Werte deutlich älter als der Spielstand sind (dann grau). Prüfung 25.10.: Kriegsgegner und Kriegsverbündete nie als
    Gelegenheit; Grün nur mit bekanntem Waffenstillstand (ab Mod 0.20); Verteidigungsbündnis 0 = bestes Verhältnis."""
    o, v = wir.get("offensive_alliance_strength"), r["werte"].get("defensive_alliance_strength")
    verh = o / v if _num(o) and _num(v) and v > 0 else (float("inf") if _num(o) and o > 0 and v == 0 else None)
    d = r["diplomatie"]
    kb = "kb_ziel" in r["beziehungen"]
    gruende, hinweise = [], []
    if veraltet:
        stufe = "grau"
        gruende.append(veraltet)
    elif "krieg" in r["beziehungen"]:
        stufe = "rot"
        gruende.append(ue("wir sind bereits im Krieg mit ihnen (Kriegskachel)"))
    elif "kriegsverbuendet" in r["beziehungen"]:
        stufe = "rot"
        gruende.append(ue("Verbündeter in einem unserer Kriege"))
    elif verh is None:
        stufe = "grau"
        gruende.append(ue("Bündnisstärke unbekannt – keine Mod-Werte (nur Spielstand)"))
    elif d.get("truce") == 1:
        stufe = "rot"
        gruende.append(ue("Waffenstillstand mit uns"))
    elif not kb and d.get("ohne_kb") == 0:
        stufe = "rot"
        gruende.append(ue("kein Kriegsgrund, und ein Krieg ohne Kriegsgrund ist laut Spiel nicht möglich"))
    elif verh < GELB:
        stufe = "rot"
        gruende.append(ue(t"ihr Verteidigungsbündnis ist stärker: {_de(v)} gegen unser Offensivbündnis {_de(o)}"))
    else:
        stufe = "gruen" if kb and verh >= GRUEN and d.get("truce") == 0 else "gelb"
        gruende.append(ue(t"unser Offensivbündnis {_de(o)} gegen ihr Verteidigungsbündnis {_de(v)} = {_de(verh, 1)} : 1")
                       if verh != float("inf") else ue(t"unser Offensivbündnis {_de(o)}, ihres 0"))
        if not kb:
            gruende.append(ue("kein Kriegsgrund – nur Krieg ohne Kriegsgrund") + (ue(" (laut Spiel möglich)") if d.get("ohne_kb") == 1
                                                                              else ue(" (ob möglich: ab Mod 0.20)")))
        elif verh < GRUEN:
            gruende.append(ue(t"Überlegenheit unter {_de(GRUEN, 1)} : 1"))
        if d.get("truce") is None:
            gruende.append(ue("Waffenstillstand unbekannt (ab Mod 0.20) – deshalb höchstens gelb"))
    if kb and stufe != "grau":
        gruende.insert(0, ue("Kriegsgrund vorhanden"))
    w = r["werte"]
    if d.get("at_war") == 1 and "krieg" not in r["beziehungen"]:
        hinweise.append(ue("ist schon im Krieg – Kräfte gebunden"))
    if _num(w.get("manpower")) and _num(w.get("max_manpower")) and w["max_manpower"] > 0 and w["manpower"] < 0.25 * w["max_manpower"]:
        hinweise.append(ue(t"Mannstärke knapp ({_de(w['manpower'])} von {_de(w['max_manpower'])} Tsd.)"))
    if _num(w.get("stability")) and w["stability"] < 0:
        hinweise.append(ue(t"Stabilität {_de(w['stability'], 1)}"))
    return {"stufe": stufe, "verhaeltnis": None if verh == float("inf") else verh, "unendlich": verh == float("inf"),
            "gruende": gruende, "hinweise": hinweise}


def build(db, last, names=None, kriege=None):
    """Länder mit Mod-Daten (bewertet) und Spielstand-Werte aller Länder (für die Auswahl) – für die Kachel."""
    nm = names or (lambda k: k)
    tag = (last or {}).get("meta", {}).get("tag")
    if not tag:
        return None
    lm = db.execute("SELECT MAX(jahr*12+monat) FROM monatswerte WHERE tag=?", (tag,)).fetchone()[0]
    fremd, fdatum = _zeilen(db, tag, "a.fremd")
    land = next(iter(_zeilen(db, tag, "a.land")[0].values()), {})
    mw = db.execute("SELECT werte FROM monatswerte WHERE tag=? AND jahr*12+monat=?", (tag, lm)).fetchone() if lm else None
    mw = json.loads(mw[0]) if mw else {}
    dip = {}
    if lm:
        for anderes, bez, werte in db.execute(
                "SELECT anderes, beziehung, werte FROM monat_diplomatie WHERE tag=? AND jahr*12+monat=?", (tag, lm)):
            d = dip.setdefault(anderes, {"beziehungen": [], "werte": {}})
            d["beziehungen"].append(bez)
            d["werte"].update(json.loads(werte))
    sp = {x["tag"]: x for x in (last.get("laender_militaer") or [])}
    # Mod-Werte mehr als einen Monat älter als der Spielstand (ohne Daten-Mod weitergespielt): Ampel grau, keine Empfehlung
    sj, sm = (int(x) for x in str(last["meta"].get("datum")).split(".")[:2])
    veraltet = (ue(t"Mod-Werte ({(lm - 1) // 12}.{(lm - 1) % 12 + 1}) älter als der Spielstand ({last['meta'].get('datum')})")
                if lm and sj * 12 + sm > lm + 1 else None)
    wir = {k: land.get(k) for k in WERTE if _num(land.get(k))}
    wir.update({"gold": mw.get("gold"), "saldo": land.get("monthly_balance"), "kriege": len(kriege or []),
                "sp": sp.get(tag)})
    laender = []
    for k, d in dip.items():
        if k == tag:
            continue
        r = {"tag": k, "name": nm(k), "beziehungen": sorted(set(d["beziehungen"])),
             "werte": {x: (fremd.get(k) or {}).get(x) for x in WERTE if _num((fremd.get(k) or {}).get(x))},
             "diplomatie": {x: d["werte"].get(x) for x in DIPLO if _num(d["werte"].get(x))},
             "sp": sp.get(k), "standard": any(b in STANDARD for b in d["beziehungen"])}
        # Heer und Flotte stehen auch in RG1D (army_size, navy_size), falls RG2 fremd fehlt
        for x in ("army_size", "navy_size"):
            if x not in r["werte"] and _num(d["werte"].get(x)):
                r["werte"][x] = d["werte"][x]
        r["bewertung"] = bewertung(r, wir, veraltet)
        laender.append(r)
    rang = {"gruen": 0, "gelb": 1, "rot": 2, "grau": 3}
    laender.sort(key=lambda r: (rang[r["bewertung"]["stufe"]], -(1e9 if r["bewertung"]["unendlich"] else r["bewertung"]["verhaeltnis"] or 0),
                                r["name"]))
    alle = sorted(sp.values(), key=lambda x: nm(x["tag"]))
    return {"datum_live": f"{(lm - 1) // 12}.{(lm - 1) % 12 + 1}.1" if lm else None, "fremd_datum": fdatum, "veraltet": veraltet,
            "datum_spielstand": last["meta"].get("datum") if sp else None, "wir": wir, "laender": laender,
            "schwellen": {"gruen": GRUEN, "gelb": GELB},
            # alle lebenden Länder (Spielstand) als Tabelle ohne wiederholte Schlüssel – Auswahl und Werte gewählter Länder
            "spielstand": {"spalten": list(SPALTEN),
                           "zeilen": [[nm(x["tag"]) if s == "name" else x.get(s) for s in SPALTEN] for x in alle]}}
