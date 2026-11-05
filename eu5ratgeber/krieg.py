"""Kriegskachel (Nutzerwunsch 25.10.): je laufendem Krieg Seiten, Kräfte, Armeen mit Heerführern, Einheitentypen, Lage.

Quellen, je Krieg zusammengeführt über die Kriegs-ID (Mod GetWar.GetID = Schlüssel in war_manager/database):
- Daten-Mod, neuester Monat: RG1W (Dauer, Stillstand, Kriegspunkte; ab 0.19 Kriegsführer, Teilnehmerzahl, Kriegsziel-Fortschritt,
  Verluste), RG2 krieg (GetWarScore, HasTickingWarScore …), Texte RG1I krieg (Beschreibung, Punkte-Aufschlüsselung),
  RG1D krieg/kriegsverbuendet (Meinung, relative Stärke, Kriegsmüdigkeit), RG2 fremd und RG2 land (Mannstärke, Seeleute,
  Regimenter, Schiffe … je Land), ab 0.19 RG1F (Armeen/Flotten) und RG1C fuehrer (Heerführer).
- Spielstand (Format 13, snapshot.kriege): Teilnehmer mit Seite und Beitrittsgrund, Kriegspunkte und Verluste je Teilnehmer,
  Kriegsziel, besetzte Orte, Schlachten, Militär je Teilnehmer (Armeen, Regimenter nach Typ, Heerführer, Fortschritte).
Ein Krieg, den es im neuesten Mod-Monat nicht mehr gibt, erscheint nicht (beendet); ohne Mod-Daten gilt der Spielstand.
"""
import json
import re

from .snapshot import KATEGORIEN
from .wirtschaftsplan import _einheit, _freigeschaltet

# Werte je Land aus RG2 fremd / RG2 land (Spiel-Trigger, Scope country): Heer in Tausend Mann (army_size, England 24,06 bei 58
# Regimentern), Flotte in Schiffen (navy_size, England 37 = 37 Schiffe im Spielstand), Mannstärke/Seeleute in Tausend
KRAEFTE = ("army_size", "navy_size", "num_regiments", "regular_army_size", "regular_navy_size", "potential_army_size",
           "country_total_army_levy_size", "manpower", "max_manpower", "monthly_manpower", "sailors", "max_sailors",
           "monthly_sailors", "army_tradition", "navy_tradition", "military_strength", "war_exhaustion", "stability",
           "possible_military_leaders", "num_forts", "great_power_ranking")
SUMMEN = ("army_size", "navy_size", "num_regiments", "regular_army_size", "country_total_army_levy_size", "manpower",
          "max_manpower", "sailors", "max_sailors", "military_strength")
DIPLO = ("rel_strength", "war_exhaustion", "stability", "op_them", "op_us", "army_size", "navy_size", "country_strength")
TEXTE = {"GetWarDescription": "beschreibung", "GetWarScoreBreakdown": "aufschluesselung",
         "GetOriginalDefendersList": "verteidiger_ursprung", "GetPotentialBattleLocations": "schlachtorte"}


def _ym(db, tag, art):
    r = db.execute("SELECT MAX(jahr*12+monat) FROM monat_extra WHERE tag=? AND art=?", (tag, art)).fetchone()
    return r[0] if r else None


def _zeilen(db, tag, art, ym):
    if not ym:
        return {}
    return {k: json.loads(w) for k, w in db.execute(
        "SELECT schluessel, werte FROM monat_extra WHERE tag=? AND art=? AND jahr*12+monat=?", (tag, art, ym))}


def _datum(ym):
    return f"{(ym - 1) // 12}.{(ym - 1) % 12 + 1}.1" if ym else None


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def live_daten(db, tag):
    """Mod-Daten zum Krieg aus dem neuesten Monat (Monatswerte des Landes). Kriege, Einheiten und Heerführer nur, wenn sie im
    neuesten Monat stehen; Landeswerte (RG2 fremd, je nach Mod-Takt monatlich oder je Quartal) aus ihrem neuesten Monat."""
    lm = db.execute("SELECT MAX(jahr*12+monat) FROM monatswerte WHERE tag=?", (tag,)).fetchone()[0]
    if not lm:
        return None
    kriege = {}
    for k, w in _zeilen(db, tag, "krieg", lm).items():
        if w.get("id") is not None:
            kriege[str(w["id"])] = w
    rg2 = _zeilen(db, tag, "a.krieg", lm)
    texte = {}
    for (w,) in db.execute("SELECT werte FROM monat_extra WHERE tag=? AND art='text' ORDER BY jahr, monat", (tag,)):
        e = json.loads(w)
        if e.get("bereich") == "krieg" and str(e.get("id")) in kriege and e.get("feld") in TEXTE:
            texte.setdefault(str(e["id"]), {})[TEXTE[e["feld"]]] = e.get("text", "")
    dip = {}
    for anderes, bez, werte in db.execute(
            "SELECT anderes, beziehung, werte FROM monat_diplomatie WHERE tag=? AND jahr*12+monat=? "
            "AND beziehung IN ('krieg', 'kriegsverbuendet')", (tag, lm)):
        d = dip.setdefault(anderes, {"beziehungen": []})
        d["beziehungen"].append(bez)
        d.update({k: v for k, v in json.loads(werte).items() if k in DIPLO})
    fym = _ym(db, tag, "a.fremd")
    fremd = _zeilen(db, tag, "a.fremd", fym)
    land = next(iter(_zeilen(db, tag, "a.land", _ym(db, tag, "a.land")).values()), {})
    einheiten = list(_zeilen(db, tag, "kriegseinheit", lm).values())
    fuehrer = {str(w.get("id")): w for w in _zeilen(db, tag, "charakter", lm).values() if w.get("rolle") == "fuehrer"}
    return {"monat": lm, "datum": _datum(lm), "kriege": kriege, "rg2": rg2, "texte": texte, "dip": dip, "fremd": fremd,
            "fremd_datum": _datum(fym), "land": land, "einheiten": einheiten, "fuehrer": fuehrer}


def _mann(t):
    """Stärke wie im Spiel angezeigt (Unit.GetVisualStrength): „821“, „12,345“, ab 100.000 „123K“ (VALUE_LIMIT_SHOW_K)."""
    m = re.match(r"^\s*([\d.,]+)\s*([KM]?)\s*$", str(t or ""))
    if not m:
        return None
    if not m.group(2):
        return int(re.sub(r"[.,]", "", m.group(1)))
    return round(float(m.group(1).replace(",", ".")) * (1000 if m.group(2) == "K" else 1000000))


def _kraefte(werte):
    return {k: werte.get(k) for k in KRAEFTE if _num(werte.get(k))}


def _technik(voll_get, names, fortschritte):
    """Einheitentypen, die die erforschten Fortschritte freischalten (unlock_unit), je Kategorie mit Zeitalter (Spieldateien)."""
    if not fortschritte or not voll_get:
        return None
    ut = voll_get("unit_types") or {}
    frei = _freigeschaltet(voll_get, {"forschung": {"fortschritte": [{"key": k} for k in fortschritte]}}, "unlock_unit")
    kat = {}
    for k in sorted(frei):
        c = _einheit(ut, k, "category")
        if isinstance(c, str):
            kat.setdefault(c, []).append({"typ": k, "name": names(k), "zeitalter": _einheit(ut, k, "age")})
    return {"fortschritte": len(fortschritte), "einheiten": kat, "typen": sorted(frei),
            "kategorie_namen": {c: names(c) for c in kat}}


def build(db, last, names=None, voll_get=None, ortname=None):
    """Liste der laufenden Kriege für die Kacheln (je Krieg eine)."""
    nm = names or (lambda k: k)
    on = ortname or (lambda i: str(i))
    tag = (last or {}).get("meta", {}).get("tag")
    if not tag:
        return []
    lv = live_daten(db, tag)
    snap = {str(w["id"]): w for w in (last.get("kriege") or [])}
    datum_sp = last["meta"].get("datum")
    # aktuelle Kriege: laut Mod (neuester Monat, RG1W gibt es seit Mod 0.9); ist der Spielstand neuer als der letzte Mod-Monat
    # (ohne Mod gespielt), die des Spielstands
    # Mod-Monatszeilen tragen Tag 1: ein Spielstand vom 20. ist neuer als der Mod-Monat desselben Monats (Prüfung 25.10.)
    sj, sm, sd = (int(x) for x in (str(datum_sp).split(".") + ["1", "1"])[:3])
    live_neuer = bool(lv) and (lv["monat"] > sj * 12 + sm or (lv["monat"] == sj * 12 + sm and sd <= 1))
    ids = list(lv["kriege"]) if live_neuer else list(snap)
    eigen_tech = None
    out = []
    for wid in ids:
        L = (lv or {}).get("kriege", {}).get(wid) or {}
        S = snap.get(wid)
        r2 = (lv or {}).get("rg2", {}).get(wid) or {}
        tx = (lv or {}).get("texte", {}).get(wid) or {}
        dip = (lv or {}).get("dip") or {}
        fremd = (lv or {}).get("fremd") or {}
        teil = {}
        if S:
            for t in S["teilnehmer"]:
                if t["status"] != "Active":
                    continue
                teil[t["tag"]] = {"tag": t["tag"], "name": t["name"], "seite": t["seite"], "grund": t["grund"],
                                  "gerufen_von": t.get("gerufen_von"), "beitritt": t["beitritt"], "punkte": t["punkte"],
                                  "verluste": t["verluste"], "militaer": t.get("militaer"), "quelle": "Spielstand"}
        wir_seite = S["wir"] if S else None
        if not wir_seite and L:
            fa, fv = L.get("fuehrer_a"), L.get("fuehrer_v")
            verb = {k for k, d in dip.items() if "kriegsverbuendet" in d["beziehungen"]} | {tag}
            wir_seite = "Verteidiger" if fv in verb else "Angreifer" if fa in verb else None
        # ohne Spielstand und ohne Kriegsführer (vor Mod 0.19): Seiten nur als „unsere Seite“ / „Gegner“ (Beziehung krieg)
        wir_seite = wir_seite or "unsere Seite"
        gegen = {"Angreifer": "Verteidiger", "Verteidiger": "Angreifer"}.get(wir_seite, "Gegner")
        # Länder, die seit dem Spielstand beigetreten sind (nur bei einem einzigen Krieg eindeutig zuzuordnen)
        if len(ids) == 1:
            for k, d in dip.items():
                if k not in teil:
                    seite = wir_seite if "kriegsverbuendet" in d["beziehungen"] else gegen
                    teil[k] = {"tag": k, "name": nm(k), "seite": seite, "grund": None, "quelle": "Mod"}
        if tag not in teil:
            teil[tag] = {"tag": tag, "name": nm(tag), "seite": wir_seite, "grund": None, "quelle": "Mod"}
        # noch im Krieg laut Mod: Gegner über RG1D krieg (seit 0.7), Verbündete über RG1D kriegsverbuendet (ab 0.19)
        mit_verb = any("kriegsverbuendet" in d["beziehungen"] for d in dip.values())
        for k, t in teil.items():
            t["wir"] = k == tag
            rel = (dip.get(k) or {}).get("beziehungen") or []
            t["im_krieg_live"] = (None if not L or k == tag else "krieg" in rel if t["seite"] == gegen
                                  else "kriegsverbuendet" in rel if mit_verb else None)
            werte = (lv or {}).get("land") if k == tag else fremd.get(k)
            t["kraefte"] = _kraefte(werte or {})
            t["diplomatie"] = {x: v for x, v in (dip.get(k) or {}).items() if x != "beziehungen"}
            m = t.get("militaer") or {}
            t["technik"] = _technik(voll_get, nm, m.get("fortschritte"))
            if k == tag:
                eigen_tech = t["technik"]
            t.pop("militaer", None)
            t["typen_im_einsatz"] = m.get("typen") or {}
            t["typ_namen"] = m.get("typ_namen") or {}
            t["spielstand"] = {x: m.get(x) for x in ("mannstaerke", "max_mannstaerke", "seeleute", "max_seeleute",
                                                     "armeetradition", "heer_unterhalt", "flotte_unterhalt")} if m else {}
        # Seiten summieren (Mod-Werte), fehlende Länder zählen; ohne einen einzigen Wert bleibt die Summe None (nicht 0).
        # Länder, die laut Mod nicht mehr im Krieg sind (Separatfrieden nach dem Spielstand), zählen nicht mit.
        seiten = {}
        for t in teil.values():
            if t["im_krieg_live"] is False:
                continue
            s = seiten.setdefault(t["seite"] or "?", {"laender": 0, "ohne_werte": 0, **{k: None for k in SUMMEN}})
            s["laender"] += 1
            if not t["kraefte"]:
                s["ohne_werte"] += 1
            for k in SUMMEN:
                if _num(t["kraefte"].get(k)):
                    s[k] = (s[k] or 0) + t["kraefte"][k]
        dabei = {k for k, t in teil.items() if t["im_krieg_live"] is not False}
        # Armeen und Flotten: Mod (RG1F, ab 0.19) oder Spielstand
        einheiten = []
        sp_fuehrer = {}
        for t in (S or {}).get("teilnehmer", []):
            for f in (t.get("militaer") or {}).get("fuehrer", []):
                sp_fuehrer[str(f["id"])] = f
        live_e = [e for e in (lv or {}).get("einheiten", []) if e.get("anderes") in dabei] if live_neuer else []
        if live_e:
            for e in live_e:
                fid = str(int(e["fuehrer_id"])) if _num(e.get("fuehrer_id")) else None
                lf, sf = (lv["fuehrer"].get(fid) or {}) if fid else {}, sp_fuehrer.get(fid) or {}
                kat = {k[8:]: int(v) for k, v in e.items() if k.startswith("sucount_") and _num(v) and v}
                flotte = e.get("einheit") == "flotte"
                anzeige = _mann(e.get("mann"))
                einheiten.append({"land": e["anderes"], "seite": teil[e["anderes"]]["seite"], "art": e.get("einheit"),
                                  "name": e.get("name"), "ort_id": e.get("ort"), "ort": on(e.get("ort")),
                                  "mann": None if flotte else anzeige, "schiffe": anzeige if flotte else None,
                                  "staerke_pct": e.get("strength_pct"), "moral_pct": e.get("morale"),
                                  "proviant_pct": e.get("food"), "erfahrung_pct": e.get("experience"),
                                  "untereinheiten": e.get("subunits"), "kategorien": kat, "quelle": "Mod",
                                  "fuehrer": ({"id": fid, "name": e.get("fuehrer") or lf.get("name") or sf.get("name"),
                                               "mil": lf.get("mil", sf.get("mil")), "adm": lf.get("adm", sf.get("adm")),
                                               "dip": lf.get("dip", sf.get("dip")), "alter": lf.get("age"),
                                               "eigenschaft": sf.get("eigenschaft_name"), "merkmale": sf.get("merkmale")}
                                              if fid else None)})
        elif S:
            for t in S["teilnehmer"]:
                if t["tag"] not in dabei:
                    continue
                for e in (t.get("militaer") or {}).get("einheiten", []):
                    f = sp_fuehrer.get(str(e.get("fuehrer_id"))) if e.get("fuehrer_id") is not None else None
                    heer = e["art"] == "heer"
                    einheiten.append({"land": t["tag"], "seite": t["seite"], "art": e["art"], "name": None,
                                      "ort_id": e.get("ort_id"), "ort": e.get("ort"),
                                      # strength je Regiment 1,0 = 1.000 Mann (REGIMENT_SIZE); Flotte: Zahl der Schiffe
                                      "mann": round(e["staerke"] * 1000) if heer else None,
                                      "schiffe": None if heer else e.get("untereinheiten"), "moral": e.get("moral"),
                                      "untereinheiten": e.get("untereinheiten"), "typen": e.get("typen"),
                                      "quelle": "Spielstand",
                                      "fuehrer": {"id": f["id"], "name": f["name"], "mil": f["mil"], "adm": f["adm"],
                                                  "dip": f["dip"], "eigenschaft": f.get("eigenschaft_name"),
                                                  "merkmale": f.get("merkmale")} if f else None})
        # Schlachten aus unserer Sicht: unsere Kriegsseite = Schlachtseite, in der ein Land unserer Seite kämpft (auch Länder,
        # die den Krieg inzwischen verlassen haben). war_score der Schlacht gilt aus Sicht des Schlacht-Angreifers (geprüft an
        # 5 Schlachten 25.10.: Mechelen +9,70 – Angreifer Brabant/Holland/Braunschweig siegt; Antwerpen −2,04 – Angreifer
        # Aquitanien verliert; Turnhout −0,48, Maastricht +0,005, 1345.8.6 −5,05 ebenso)
        unsere = {k for k, t in teil.items() if t["seite"] == wir_seite} | {
            t["tag"] for t in (S or {}).get("teilnehmer", []) if t["seite"] == wir_seite}
        schlachten = []
        for b in (S or {}).get("schlachten", []):
            a_unser = bool(set(b["angreifer"]["laender"]) & unsere)
            wir_a = wir_seite == "Angreifer"
            ws = b.get("kriegspunkte")
            schlachten.append({**b, "unsere_seite_siegt": b["angreiferseite_siegt"] == wir_a,
                               "unsere": "angreifer" if a_unser else "verteidiger",
                               "punkte_wir": (ws if a_unser else -ws) if _num(ws) else None})
        # GetWarScore gilt aus Sicht des Angreifers; die Punkte-Aufschlüsselung des Spiels ergibt genau diesen Wert (1351.2:
        # −23,00 tickend − 4,74 Schlachten + 2,10 Besetzung = −25,64; RG1W score = war_score_in_war 3,16 ist eine andere Größe)
        ws = r2.get("GetWarScore")
        punkte_spiel = (ws if wir_seite == "Angreifer" else -ws if wir_seite == "Verteidiger" else None) if _num(ws) else None
        zk = re.match(r"Kriegsziel:\s*(Angreifer|Verteidiger) kontrolliert", str(tx.get("aufschluesselung") or ""))
        zt = re.search(r"Kriegsziel ist (.+?)\.?\s*$", str(tx.get("beschreibung") or ""))
        ziel = (S or {}).get("kriegsziel")
        if ziel:
            bes = {b["ort_id"]: b for b in S["besetzt"]}
            ziel = {**ziel, "orte": [{**o, "kontrolleur": (bes.get(o["id"]) or {}).get("kontrolleur"),
                                      "besitzer": (bes.get(o["id"]) or {}).get("besitzer")} for o in ziel["orte"]]}
        out.append({
            # Spieltext „1.. Englisch-Holländischer Krieg“ (Ordinalzahl samt Punkt + Punkt) -> „1. …“
            "id": wid, "name": re.sub(r"(\d)\.\.", r"\1.", str(L.get("name") or (S or {}).get("name") or wid)).replace("\xa0", " "),
            "datum_live": (lv or {}).get("datum") if L else None, "datum_spielstand": datum_sp if S else None,
            "fremd_datum": (lv or {}).get("fremd_datum"),
            "dauer": L.get("length"), "stillstand": L.get("stalling"), "punkte_wir": L.get("score"),
            "punkte_seite": L.get("score_side"), "kriegspunkte": ws, "punkte_spiel": punkte_spiel,
            "ziel_kontrolle": zk.group(1) if zk else None, "kriegsziel_text": zt.group(1) if zt else None,
            "ticking": r2.get("HasTickingWarScore"), "eroberung": r2.get("IsConquestWar"),
            "fuehrer_a": L.get("fuehrer_a"), "fuehrer_v": L.get("fuehrer_v"), "anz_a": L.get("anz_a"),
            "anz_v": L.get("anz_v") or r2.get("GetDefenderCount"), "ziel_fortschritt": L.get("ziel_fortschritt"),
            "verluste_live": {k: L.get(k) for k in ("verl_a_mann", "verl_a_schiffe", "verl_v_mann", "verl_v_schiffe")
                              if _num(L.get(k))},
            "texte": tx,
            "beginn": (S or {}).get("beginn"), "wir_seite": wir_seite, "gegen_seite": gegen,
            "kriegsziel": ziel, "teilnehmer": sorted(teil.values(), key=lambda t: (t["seite"] != wir_seite, not t["wir"],
                                                                                   -(t["kraefte"].get("army_size") or 0))),
            "seiten": seiten, "einheiten": einheiten, "besetzt": (S or {}).get("besetzt", []), "schlachten": schlachten,
            "schlachten_gesamt": (S or {}).get("schlachten_gesamt"), "verluste": (S or {}).get("verluste"),
            "pop_verluste": (S or {}).get("pop_verluste"), "stillstand_jahre": (S or {}).get("stillstand_jahre")})
    for w in out:
        w["technik_wir"] = eigen_tech
        # Spielnamen für die Seite: Einheitenkategorien, Einheitentypen (Spielstand), Zeitalter
        typen = {x for t in (snap.get(w["id"]) or {}).get("teilnehmer", []) for x in ((t.get("militaer") or {}).get("typen") or {})}
        w["namen"] = {**{c: nm(c) for c in KATEGORIEN}, **{x: nm(x) for x in typen},
                      **{a: nm(a) for t in w["teilnehmer"] for es in ((t.get("technik") or {}).get("einheiten") or {}).values()
                         for a in {e["zeitalter"] for e in es} if a}}
    return out
