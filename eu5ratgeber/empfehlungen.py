"""Empfehlungen (Regeln) auf den Daten – Kachel „Empfehlungen“ (Nutzerwunsch 02.10.).

Jede Regel liefert eine Handlung („was tun“), die Begründung mit Zahlen und die Wirkung:
  berechnet  – Formel geprüft (MECHANIK.md), Zahl vorher ausgerechnet
  Spielwert  – Zahl stammt so aus dem Spiel (z. B. Gewinn je Stufe der Ausbau-Ansicht)
  messen     – keine geprüfte Formel; nach dem Umsetzen markieren, die Kachel Entscheidungen misst vorher/nachher
Der Zustand selbst (Warnungen) steht weiter in den Kachelköpfen, hier nur die Handlung (keine doppelten Texte).

Quellen: Momentaufnahmen (Spielstand), Monatswerte des Daten-Mods (monatswerte, monat_details, monat_extra).
"""
import json
import math
import re

from . import handel, startstrategie
from . import sprache
from .sprache import ue

PRIO = {"hoch": 0, "mittel": 1, "niedrig": 2}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(v)


def _ym(datum):
    y, m = (int(x) for x in str(datum).split(".")[:2])
    return y * 12 + m


def _de(v, d=2):
    """Zahl in der Schreibweise der Ausgabe: 1234.5 -> 1.234,50"""
    return sprache.ziffern(f"{v:,.{d}f}")


def _sgn(v, d=2):
    return ("+" if v > 0 else "") + _de(v, d)


def _pz(v, d=1):
    return ue(t"{_de(v * 100, d)} %")


# ---------------------------------------------------------------- Datenzugriff
def _neueste(db, tag, art):
    """{schluessel: werte} des neuesten Monats einer Zeilenart in monat_extra, dazu das Datum 'J.M.1'."""
    row = db.execute("SELECT MAX(jahr*12+monat) FROM monat_extra WHERE tag=? AND art=?", (tag, art)).fetchone()
    if not row or row[0] is None:
        return {}, None
    ym = row[0]
    out = {k: json.loads(w) for k, w in db.execute(
        "SELECT schluessel, werte FROM monat_extra WHERE tag=? AND art=? AND jahr*12+monat=?", (tag, art, ym))}
    return out, f"{(ym - 1) // 12}.{(ym - 1) % 12 + 1}.1"


def _text(db, tag, bereich, id_, feld):
    """Neuester Spieltext (RG1I) eines Feldes."""
    row = db.execute("SELECT werte FROM monat_extra WHERE tag=? AND art='text' AND schluessel=? ORDER BY jahr DESC, monat DESC LIMIT 1",
                     (tag, f"{bereich}:{id_}:{feld}")).fetchone()
    return json.loads(row[0]).get("text", "") if row else ""


def _gebaeude_monate(db, tag):
    """Gebäudezeilen des Mods je Monat: {ym: {id: {typ, ort_id, werte…}}}."""
    out = {}
    for j, m, i, k, b, w in db.execute("SELECT jahr, monat, id, schluessel, bezug, werte FROM monat_details "
                                       "WHERE tag=? AND art='gebaeude'", (tag,)):
        t = re.search(r"BUILDING_TYPE,(\w+)", k or "")
        out.setdefault(j * 12 + m, {})[i] = {"typ": t.group(1) if t else k, "ort_id": b, **json.loads(w)}
    return out


def _preise(db, tag, markt_id):
    """Monatliche Preise im Markt (Zeilenart preise, Daten-Mod): {ym: {gut: preis}}."""
    out = {}
    for j, m, w in db.execute("SELECT jahr, monat, werte FROM monat_extra WHERE tag=? AND art='preise' AND schluessel=?",
                              (tag, f":{markt_id}")):
        e = json.loads(w)
        out[j * 12 + m] = {k[6:]: v for k, v in e.items() if k.startswith("price_") and _num(v)}
    return out


def _snap_vor(snaps, datum, monate):
    """Neueste Momentaufnahme, die mindestens `monate` vor dem Datum liegt (sonst die älteste)."""
    ziel = _ym(datum) - monate
    alt = [s for s in snaps if _ym(s["meta"]["datum"]) <= ziel]
    return alt[-1] if alt else snaps[0]


def _wert_vor(lv, key, monate):
    """(alter Wert, Datum) aus den Monatszeilen, ~`monate` vor der letzten Zeile mit diesem Wert."""
    L = [r for r in lv if _num(r.get(key))]
    if len(L) < 2:
        return None, None
    ziel = _ym(L[-1]["datum"]) - monate
    alt = [r for r in L if _ym(r["datum"]) <= ziel]
    r = alt[-1] if alt else None
    return (r[key], r["datum"]) if r else (None, None)


def _produziert(wis, typ, pm_namen):
    """Ausgabegut je Stufe aus den laufenden Methoden (Spieldateien)."""
    out = {}
    for pm in (wis.get("gebaeude", {}).get(typ) or {}).get("pms", []):
        if pm["name"] in pm_namen and pm.get("produced"):
            out[pm["produced"]] = out.get(pm["produced"], 0) + (pm.get("output") or 0)
    return out


def _ist_produktion(wis, typ):
    return any(pm.get("produced") for pm in (wis.get("gebaeude", {}).get(typ) or {}).get("pms", []))


def _rec(id_, prio, bereich, titel, gruende, handlung, wirkung_art, wirkung, kachel, marker):
    return {"id": id_, "prio": prio, "bereich": bereich, "titel": titel, "gruende": [g for g in gruende if g],
            "handlung": handlung, "wirkung": {"art": wirkung_art, "text": wirkung}, "kachel": kachel, "marker": marker}


# ---------------------------------------------------------------- Schwerpunkt
# Nutzer 05.11. („sind jetzt alle empfehlungen … mit dem gewählten schwerpunkt verknüpft?“ – nur 2 von 18 Regeln waren es). Der Server kennt
# die Wahl nicht (Seite: localStorage rg_wp_fokus, Spiel: Variable rg_fokus). Darum je Schwerpunkt: Empfehlungen mit Feld „fokus“
# (Handelsbestellung, Fortschritt, Ausbau), an allgemeinen Empfehlungen Punkte „fokus_wert“ {fk: [Punkte, Grund]} und eine fertige
# Reihenfolge „rang“ {fk: Stelle} für Seite und Spiel. Krieg und Krankheit bleiben unabhängig. Punkte wie startstrategie.PUNKTE.
KARTEN = 8                                             # Karten der Seitenleiste (ingame.EMPFEHLUNGEN)
HANDEL_PUNKTE = {"export": 10, "import": 10, "gewinn": 5}    # Regel des Ratgebers: Handel gehört zu diesen Schwerpunkten


def _fokusse(ctx):
    """{Schwerpunkt: (Eintrag im Wirtschaftsplan, startstrategie.fokus_kontext)}; ohne Wirtschaftsplan leer."""
    return ctx.get("fokus") or {}


def _gut_punkte(g, C, nm):
    """(Punkte, Grund) eines Guts: 15 − 1 je Rang (mind. 6), 12, wenn es im Heimatmarkt fehlt (startstrategie.PUNKTE gut_ausstoss)."""
    n = C["rang"].get(g)
    if n:
        return max(6, 16 - n), ue(t"{nm(g)} ist Schwerpunkt-Gut")
    if g in C["fehlt"]:
        return 12, ue(t"{nm(g)} ist Schwerpunkt-Gut und fehlt im Heimatmarkt")
    return 0, ""


def _gebaeude_fokus(typ, gueter, F, C, nm):
    """(Punkte, Grund) eines Gebäudetyps: Schwerpunkt-Wirkung des Gebäudes 15 (fokus_lokal), sonst sein bestes Schwerpunkt-Gut."""
    if typ in (F.get("wirkung") or ()):
        return 15, ue(t"{nm(typ)} hat Schwerpunkt-Wirkung")
    return max((_gut_punkte(g, C, nm) for g in gueter), key=lambda x: x[0], default=(0, ""))


def _stand_fokus(block, ctx, C):
    """(Punkte, Grund) der Wirkungen, die die Zufriedenheit eines Stands bringt – dieselbe Bewertung wie die Startstrategie."""
    werte = {m: ctx["script_value"](v) for m, v in block.items()}
    w = [[x[0], x[1], "", *x[3:]] for x in startstrategie._mods({m: v for m, v in werte.items() if _num(v)}, "land", ctx["modtypen"], {})]
    p, gr, _ = startstrategie.bewerte(w, C)
    return p, " ".join(gr[0][1].split()) if gr else ""


def _fokus_wert(rec, werte):
    """Punkte {fk: (Punkte, Grund)} an die Empfehlung – nur Schwerpunkte, zu denen sie passt."""
    w = {fk: [p, g] for fk, (p, g) in werte.items() if p > 0}
    if w:
        rec["fokus_wert"] = w
    return rec


def reihe(recs, fk):
    """Empfehlungen für Schwerpunkt fk in ihrer Reihenfolge: Priorität, in ihr zuerst Empfehlungen zum Schwerpunkt, dann nach Punkten.
    Unter den ersten KARTEN steht immer eine zum Schwerpunkt, wenn es eine gibt (sonst sähe man im Spiel keine)."""
    def treffer(r):
        return r.get("fokus") == fk and r.get("fokus_treffer", True)

    def punkte(r):
        return 1000 if treffer(r) else ((r.get("fokus_wert") or {}).get(fk) or (0,))[0]
    E = sorted((r for r in recs if not r.get("fokus") or r.get("fokus") == fk), key=lambda r: (PRIO.get(r["prio"], 9), -punkte(r)))
    if not any(treffer(r) for r in E[:KARTEN]):
        rest = [i for i, r in enumerate(E) if treffer(r)]
        if rest:
            E.insert(KARTEN - 1, E.pop(rest[0]))
    return E


# ---------------------------------------------------------------- Regeln
def r_steuergrundlage(ctx):
    """Steuergrundlage fällt ≥ 10 % in 12 Monaten -> je Ort aufteilen in Reichtum und Kontrolle.
    Spielbegriff „Reichtum“: Gewinn aus Rohstoffen, Gebäuden und Bürgerhandel; Steuergrundlage ≈ Reichtum × Kontrolle
    (Hoorn 5,41 × 46,6 % = 2,52, Spiel 2,49 – nicht exakt, MECHANIK.md „Orte“)."""
    lv, snaps, nm = ctx["lv"], ctx["snaps"], ctx["names"]
    if not lv or not _num(lv[-1].get("tax_base")):
        return []
    jetzt = lv[-1]["tax_base"]
    alt, alt_dat = _wert_vor(lv, "tax_base", 12)
    if not _num(alt) or alt <= 0 or (jetzt - alt) / alt > -0.10:
        return []
    s1, s0 = snaps[-1], _snap_vor(snaps, alt_dat, 0)
    o0 = {o["id"]: o for o in s0.get("orte", [])}
    teile = []
    for o in s1.get("orte", []):
        a = o0.get(o["id"])
        if not a or not all(_num(x) for x in (a.get("moegliche_steuer"), a.get("kontrolle"), o.get("moegliche_steuer"), o.get("kontrolle"))):
            continue
        reich = (o["moegliche_steuer"] - a["moegliche_steuer"]) * a["kontrolle"]
        kontr = o["moegliche_steuer"] * (o["kontrolle"] - a["kontrolle"])
        teile.append((o.get("name") or str(o["id"]), reich, kontr))
    sum_r, sum_k = sum(t[1] for t in teile), sum(t[2] for t in teile)
    top = sorted(teile, key=lambda t: t[1])[:3]
    g_jetzt = lv[-1].get("gebaeude_gewinn")
    g_alt, _ = _wert_vor(lv, "gebaeude_gewinn", 12)
    # größte Rückgänge je Gebäudetyp (Gebäudezeilen des Mods, gleiche Monate wie die Steuergrundlage)
    gm = ctx["geb_monate"]
    typ_txt = ""
    if gm:
        y1 = max(gm)
        y0 = max((y for y in gm if y <= _ym(alt_dat)), default=None)
        if y0:
            def je_typ(ym):
                out = {}
                for b in gm[ym].values():
                    out[b["typ"]] = out.get(b["typ"], 0) + (b.get("profit") or 0)
                return out
            t0, t1 = je_typ(y0), je_typ(y1)
            d = sorted(((k, t1.get(k, 0) - v) for k, v in t0.items()), key=lambda x: x[1])[:3]
            typ_txt = ", ".join(f"{nm(k)} {_sgn(v)}" for k, v in d if v < -0.05)
    return [_rec(
        "steuergrundlage", "hoch", "Wirtschaft",
        ue(t"Steuergrundlage sinkt: {_de(alt)} → {_de(jetzt)} seit {alt_dat} ({_sgn((jetzt - alt) / alt * 100, 0)} %)"),
        [ue(t"Je Ort zerlegt (Spielstand {s0['meta']['datum']} → {s1['meta']['datum']}): durch Reichtum {_sgn(sum_r)}, "
         t"durch Kontrolle {_sgn(sum_k)}. Größte Rückgänge: ") + ", ".join(f"{n} {_sgn(r)}" for n, r, _ in top if r < 0) + ".",
         ue("Reichtum eines Orts = Gewinn aus Rohstoffen, Gebäuden und Bürgerhandel (Spielbegriff „Reichtum“); "
         "Steuergrundlage ≈ Reichtum × Kontrolle."),
         _num(g_alt) and _num(g_jetzt) and ue(t"Gewinn der Gebäude im selben Zeitraum {_de(g_alt)} → {_de(g_jetzt)}")
         + (ue(t"; größte Rückgänge: {typ_txt}") if typ_txt else "") + "."],
        ue("Die Ursache liegt ") + (ue("beim Reichtum, nicht bei der Kontrolle") if sum_r < sum_k else ue("bei der Kontrolle"))
        + ue(": Gebäude ohne Gewinn und fallende Preise der eigenen Güter angehen (eigene Empfehlungen unten)."),
        "messen", ue("Keine geprüfte Formel für den Weg vom Gebäudegewinn zur Steuergrundlage – nach dem Umsetzen markieren."),
        "orte", ue("Steuergrundlage: Ursache angegangen"))]


def _snap_preis(snaps, ym, gut):
    """Preis eines Guts im Heimatmarkt laut der neuesten Momentaufnahme bis zum Monat ym: (Preis, Datum)."""
    alt = [s for s in snaps if _ym(s["meta"]["datum"]) <= ym and s.get("markt")]
    if not alt:
        return None, None
    g = next((x for x in alt[-1]["markt"].get("gueter", []) if x["gut"] == gut), None)
    return (g.get("preis"), alt[-1]["meta"]["datum"]) if g else (None, None)


def r_gebaeude_ohne_gewinn(ctx):
    """Gebäude mit Gewinn ≤ 0 in den letzten 3 Monaten oder ohne Beschäftigte (stillgelegt) – je Typ zusammengefasst.
    Nur Gebäude mit Produktion (Methode mit Ausgabegut laut Spieldateien). Einzeln nur Typen, die früher zusammen
    mindestens 0,5 Gewinn brachten; die übrigen als eine Sammel-Empfehlung. Unrentable Gebäude entlassen 10 % der
    Arbeiter je Monat (NEconomy, MECHANIK.md)."""
    gm, wis, nm, snaps = ctx["geb_monate"], ctx["wis"], ctx["names"], ctx["snaps"]
    if len(gm) < 3:
        return []
    monate = sorted(gm)                  # ältere Monate nur Januar (DETAIL_MONTHS) -> Abstände kalendarisch rechnen
    last3 = monate[-3:]
    pma = ctx["last"].get("gebaeude_pm") or {}
    orte = {o["id"]: o.get("name") for o in ctx["last"].get("orte", [])}
    preis_jetzt = {g["gut"]: g.get("preis") for g in (ctx["last"].get("markt") or {}).get("gueter", [])}

    def schlecht(b):
        return b is not None and ((b.get("profit") or 0) <= 0 or (b.get("employed") or 0) <= 0)

    je_typ = {}
    for bid, b in gm[monate[-1]].items():
        if not _ist_produktion(wis, b["typ"]) or not all(schlecht(gm[ym].get(bid)) for ym in last3):
            continue
        seit = monate[-1]                         # erster Monat der lückenlosen Folge ohne Gewinn
        for ym in reversed(monate):
            if schlecht(gm[ym].get(bid)):
                seit = ym
            else:
                break
        best_ym, bester = max(((ym, gm[ym][bid].get("profit") or 0) for ym in monate if bid in gm[ym]), key=lambda x: x[1])
        t = je_typ.setdefault(b["typ"], {"orte": [], "still": 0, "seit": seit, "ab_anfang": False, "bester": 0.0,
                                         "best_ym": best_ym, "best_einzel": -1.0, "moeglich": 0.0, "pms": set()})
        t["orte"].append(orte.get(b["ort_id"], str(b["ort_id"])))
        t["still"] += (b.get("employed") or 0) <= 0
        t["seit"] = min(t["seit"], seit)
        t["ab_anfang"] |= seit == monate[0]
        if bester > t["best_einzel"]:              # Preisvergleich zum besten Monat des stärksten Gebäudes
            t["best_einzel"], t["best_ym"] = bester, best_ym
        t["bester"] += max(bester, 0)
        t["moeglich"] += b.get("potential_profit") or 0
        t["pms"].update((pma.get(str(bid)) or {}).get("pms") or [])
    out, klein = [], []
    for typ, t in sorted(je_typ.items(), key=lambda x: -x[1]["bester"]):
        anz, mon = len(t["orte"]), monate[-1] - t["seit"] + 1
        dauer = (ue("seit Beginn der Monatsdaten") if t["ab_anfang"] else ue(t"seit {mon} Monat(en)"))
        if t["bester"] < 0.5:
            still = ue(t", {t['still']} stillgelegt") if t["still"] else ""
            klein.append(f"{nm(typ)} ({anz}{still}, {dauer})")
            continue
        preise = []
        for g in _produziert(wis, typ, t["pms"]):
            p0, d0 = _snap_preis(snaps, t["best_ym"], g)
            if _num(p0) and _num(preis_jetzt.get(g)):
                preise.append(ue(t"Preis {nm(g)} {_de(p0)} ({d0}, bester Monat) → {_de(preis_jetzt[g])}"))
        andere = [nm(pm["name"]) for pm in (wis.get("gebaeude", {}).get(typ) or {}).get("pms", []) if pm["name"] not in t["pms"]]
        rec = _rec(
            f"geb:{typ}", "hoch" if t["bester"] >= 1.0 else "mittel", "Wirtschaft",
            ue(t"{nm(typ)}: {anz} Gebäude ohne Gewinn") + (ue(t", {t['still']} stillgelegt") if t["still"] else ""),
            [ue(t"In {', '.join(t['orte'])} {dauer} Gewinn ≤ 0 oder keine Beschäftigten (Daten-Mod); früher zusammen bis "
             t"{_sgn(t['bester'])} je Monat, möglich laut Spiel jetzt {_sgn(t['moeglich'])}."),
             preise and "; ".join(preise) + ue(" (Heimatmarkt, Spielstand)."),
             ue("Unrentable Gebäude entlassen je Monat 10 % ihrer Arbeiter (Spielmechanik).")],
            ue("Nicht weiter ausbauen. Im Spiel die Produktionsmethode prüfen")
            + (ue(t" (andere laut Spieldatei: {', '.join(andere)})") if andere else ue(" (der Typ hat keine andere Methode)"))
            + ue("; sonst die Arbeiter in rentablere Gebäude lenken."),
            "messen", ue("Den Gewinn nach einem Wechsel zeigt das Spiel erst danach – nach dem Umsetzen markieren."),
            "produktion", ue(t"{nm(typ)}: Methode/Ausbau geändert"))
        out.append(_fokus_wert(rec, {fk: _gebaeude_fokus(typ, _produziert(wis, typ, t["pms"]), F, C, nm)
                                     for fk, (F, C) in _fokusse(ctx).items()}))
    if klein:
        out.append(_rec(
            "geb:klein", "niedrig", "Wirtschaft", ue(t"Weitere {len(klein)} Gebäudetypen ohne Gewinn (früher unter 0,5 je Monat)"),
            ["; ".join(klein) + "."],
            ue("Nicht ausbauen; Methode prüfen, wenn Arbeiter fehlen."), "messen", ue("Kleine Beträge."),
            "produktion", ue("Gebäude ohne Gewinn bereinigt")))
    return out


def r_preis_ueberangebot(ctx):
    """Gut, das wir herstellen: Angebot > Nachfrage × 1,05 im Heimatmarkt, Preis −10 % oder mehr in 24 Monaten und unsere
    Stufen dafür sind im selben Zeitraum gestiegen -> nicht weiter ausbauen. Zeigt unseren Anteil am Angebot
    (Stufe × Ausgabe der laufenden Methode, ohne Zu-/Abschläge) – das Angebot kommt oft überwiegend von anderen."""
    last, wis, nm = ctx["last"], ctx["wis"], ctx["names"]
    markt = last.get("markt") or {}
    if not markt.get("gueter"):
        return []
    pma = last.get("gebaeude_pm") or {}
    s24 = _snap_vor(ctx["snaps"], last["meta"]["datum"], 24)
    stufe_alt = {b["id"]: b.get("stufe") or 0 for b in s24.get("gebaeude", [])}
    ours, stufen, stufen_alt, typen = {}, {}, {}, {}
    for b in last.get("gebaeude", []):
        pms = (pma.get(str(b["id"])) or {}).get("pms") or []
        for g, o in _produziert(wis, b.get("typ"), pms).items():
            lv = b.get("stufe") or 0
            ours[g] = ours.get(g, 0) + o * lv
            stufen[g] = stufen.get(g, 0) + lv
            stufen_alt[g] = stufen_alt.get(g, 0) + stufe_alt.get(b["id"], 0)
            typen.setdefault(g, set()).add(b.get("typ"))
    preis_alt = {g["gut"]: g.get("preis") for g in (s24.get("markt") or {}).get("gueter", [])}
    out = []
    for x in markt["gueter"]:
        g = x["gut"]
        a, n, p, p0 = x.get("angebot"), x.get("nachfrage"), x.get("preis"), preis_alt.get(g)
        if g not in ours or not all(_num(v) for v in (a, n, p, p0)) or p0 <= 0:
            continue
        if not (a > n * 1.05 and (p - p0) / p0 <= -0.10 and stufen[g] > stufen_alt[g]):
            continue
        anteil = ours[g] / a if a else 0
        rec = _rec(
            f"preis:{g}", "mittel", "Wirtschaft",
            ue(t"{nm(g)}: Überangebot im {(ue('Markt ') + markt['zentrum']) if markt.get('zentrum') else ue('Heimatmarkt')}, "
            t"Preis {_de(p0)} → {_de(p)} ({_sgn((p - p0) / p0 * 100, 0)} % seit {s24['meta']['datum']})"),
            [ue(t"Angebot {_de(a, 1)} > Nachfrage {_de(n, 1)} (Spielstand {last['meta']['datum']})."),
             ue(t"Unsere Stufen dafür ({', '.join(nm(t) for t in sorted(typen[g]))}) {stufen_alt[g]:.0f} → {stufen[g]:.0f}; "
             t"unser Anteil am Angebot ≈ {_pz(anteil, 0)} (Stufe × Ausgabe laut Methode {_de(ours[g], 1)}, ohne Zu-/Abschläge)."),
             ue("Der Preis nähert sich monatlich um 5 % dem Zielpreis (Spieldefine MONTHLY_PRICE_CHANGE).")],
            ue(t"{nm(g)} nicht weiter ausbauen; neue Stufen eher in Güter mit Nachfrage über Angebot (Güterkachel: knappe Güter)."),
            "messen", ue("Preiswirkung eigener Stufen ist nicht berechenbar – nach dem Umsetzen markieren."),
            "gueter", ue(t"{nm(g)}: Ausbau gestoppt"))
        out.append(_fokus_wert(rec, {fk: _gut_punkte(g, C, nm) for fk, (_, C) in _fokusse(ctx).items()}))
    return out


def _satz(text):
    """GetSatisfactionTooltip: 'Derzeit: 45.16%' / 'Monatliche Veränderung: +1.32%' / 'Ausgewogenheit: 49.98%' (ESTATE_SATISFACTION_TOOLTIP;
    auf Englisch 'Estate Satisfaction: …' / 'Monthly Change: …' / 'Satisfaction Equilibrium: …')."""
    def f(label):
        m = re.search("(?:" + label + r"):\s*([-+]?[\d.]+)%", text or "")
        return float(m.group(1)) / 100 if m else None
    return f("Derzeit|Estate Satisfaction"), f("Monatliche Veränderung|Monthly Change"), f("Ausgewogenheit|Satisfaction Equilibrium")


def r_staende(ctx):
    """Stand mit Ausgewogenheit (Zielzufriedenheit) unter 50 %: die Wirkung der Zufriedenheit ist negativ
    (voller Wert × (Zufriedenheit − 0,5), geprüft am Bürgerstand 1.1.1345: Handelsvorteil 0,5 × −0,045 = −2,25 %).
    Posten „Steuern für <Stand>“ = Steuer ÷ steuerpflichtiges Einkommen (geprüft: Adel 1,867 ÷ 5,24 = 35,63 %)
    -> 1 Punkt weniger Steuer = +1 Punkt Ausgewogenheit, kostet steuerpflichtiges Einkommen × 1 %.
    Unter 25 % keine Steuern und keine Aufgebote (GetCollectTaxesInfo, GetRaiseLevyInfo)."""
    lv, db, tag, nm, voll = ctx["lv"], ctx["db"], ctx["tag"], ctx["names"], ctx["voll_estates"]
    if not lv:
        return []
    r = lv[-1]
    mt = ctx["modtypen"]
    out = []
    for e in ("nobles_estate", "burghers_estate", "clergy_estate", "peasants_estate"):
        tax, taxable = r.get(f"tax_{e}"), r.get(f"taxable_{e}")
        jetzt, aend, ziel = _satz(_text(db, tag, "stand", e, "GetSatisfactionTooltip"))
        if not _num(ziel) or not _num(jetzt):
            continue
        name = nm(e)
        sat_def = ((voll.get(e) or {}).get("def") or {}).get("satisfaction") or {}
        wirk = []
        for m, v in sat_def.items():
            val = ctx["script_value"](v)
            if not _num(val):
                continue
            t = mt.get(m) or {}
            pro = val * 0.01                      # je Punkt Zufriedenheit
            wirk.append(f"{t.get('name') or m} {ue(t'{_sgn(pro * 100, 2)} %') if t.get('percent') == 'yes' else _sgn(pro, 3)}")
        impact = _text(db, tag, "stand", e, "GetSatisfactionImpact").strip().replace("\n", "; ")
        if jetzt < 0.25:
            out.append(_rec(
                f"stand25:{e}", "hoch", "Stände", ue(t"{name} unter 25 % ({_pz(jetzt)}): keine Steuern, keine Aufgebote"),
                [ue(t"Ausgewogenheit {_pz(ziel)}, monatliche Veränderung {_sgn(aend * 100) if _num(aend) else '?'} %.")],
                ue(t"Ausgewogenheit von {name} über 25 % bringen (Steuer senken oder Privileg)."),
                "berechnet", ue("Unter 25 % zahlt der Stand nichts und stellt keine Aufgebote (Spieltexte)."),
                "staende", ue(t"{name}: Zufriedenheit angehoben")))
            continue
        if ziel >= 0.5 or not _num(tax) or not _num(taxable) or taxable <= 0 or tax <= 0:
            continue
        pp = math.ceil((0.5 - ziel) * 1000 + 1e-9) / 10          # Punkte, auf 0,1 aufgerundet
        kosten = taxable * pp / 100
        satz = tax / taxable
        rec = _rec(
            f"stand:{e}", "mittel" if jetzt < 0.5 else "niedrig", "Stände",
            ue(t"{name}: Steuer um {_de(pp, 1)} Punkte senken – Ausgewogenheit {_pz(ziel, 2)} → 50 %"),
            [ue(t"Zufriedenheit {_pz(jetzt, 2)}, Veränderung {_sgn(aend * 100) if _num(aend) else '?'} % je Monat, Ziel (Ausgewogenheit) "
             t"{_pz(ziel, 2)} – unter 50 % kehrt sich die Wirkung um") + (ue(t" (jetzt: {impact})") if impact else "") + ".",
             ue(t"Posten „Steuern für {name}“ = Steuer {_de(tax, 3)} ÷ steuerpflichtiges Einkommen {_de(taxable, 2)} = {_pz(satz, 2)}."),
             wirk and ue("Je Punkt Zufriedenheit über 50 % laut Spieldatei: ") + ", ".join(wirk) + "."],
            ue(t"Steuersatz für {name} senken, bis „Steuern für {name}“ bei {_pz(satz - pp / 100, 2)} steht."),
            "berechnet", ue(t"Kostet {_de(kosten, 3)} Gold je Monat; jeder weitere Punkt {_de(taxable / 100, 3)}."),
            "staende", ue(t"Steuer {name} gesenkt"))
        out.append(_fokus_wert(rec, {fk: _stand_fokus(sat_def, ctx, C) for fk, (_, C) in _fokusse(ctx).items()}))
    return out


def r_ungenutzt(ctx):
    """Ungenutzte Mittel: Diplomaten am oder über dem Maximum (darüber kein Zuwachs, Spieltext „Wir gewinnen +0.00 Diplomaten
    pro Monat … Maximum“); Gold > 12 Monate Überschuss ohne Schulden."""
    lv, land = ctx["lv"], ctx["land"]
    out = []
    dn, dm = land.get("dip_GetNumOfDiplomats"), land.get("dip_GetMaxNumOfDiplomats")
    if _num(dn) and _num(dm) and dm > 0 and dn >= dm:
        out.append(_rec(
            "diplomaten", "niedrig", "Diplomatie", ue(t"Diplomaten voll ({_de(dn, 1)} / {_de(dm, 1)}) – Zuwachs verfällt"),
            [ue("Über dem Maximum wächst nichts nach (Spieltext: „Wir gewinnen +0.00 Diplomaten pro Monat“).")],
            ue("Diplomaten einsetzen (Beziehungen verbessern, Verträge, Ansprüche)."),
            "messen", ue("Nutzen hängt von der Aktion ab."), "diplomatie", ue("Diplomaten eingesetzt")))
    r = lv[-1] if lv else {}
    gold, saldo, schuld = r.get("gold"), r.get("saldo_spiel"), r.get("debt_total") or 0
    if _num(gold) and _num(saldo) and saldo > 0 and schuld <= 0 and gold > 12 * saldo:
        bau = ctx["bau"]
        out.append(_rec(
            "gold", "niedrig", "Wirtschaft", ue(t"{_de(gold, 0)} Gold liegen ungenutzt ({_de(gold / saldo, 0)} Monate Überschuss)"),
            [ue(t"Saldo {_sgn(saldo)} je Monat (Wirtschaftsfenster), keine Schulden; im Bau laut Spielstand: {len(bau)}.")],
            ue("Gold einsetzen – die besten Ausbauten laut Spiel stehen in der Empfehlung „Ausbau“."),
            "messen", ue("Wirkung je nach Verwendung."), "finanzen", ue("Gold investiert")))
    return out


def r_ausbau(ctx):
    """Was sich zu bauen lohnt – nur Werte des Spiels (Nutzerwunsch 02.10.: „muss im Mod drin sein“):
    - Ausbau vorhandener Gebäude: Building.GetProfitPerLevel (Ausbau-Ansicht des Spiels „+x Reichtum“), dazu
      GetTaxBaseValuePerLevel und GetIncomeToOwnerPerLevel; nur unter der Höchststufe, nichts im Bau, voll besetzt
      (mehr Stufen ohne Arbeiter bringen nichts).
    - Rohstoff: Location.GetRGOProfitPerLevel, Kosten und Bauzeit aus GetUpgradeRGOBuildCostAndTime (Mod ab 0.17.1).
    Neue Gebäudetypen fehlen: Gewinn und Kosten zeigt nur das Baumenü (GetBuildingTypeProfitInLocation mit Objekt-Argumenten),
    für den Mod unerreichbar (Test 0.17/0.17.1).
    Je Schwerpunkt eine Empfehlung (05.11.): Gebäude und Rohstoffe, die zum Schwerpunkt passen, zuerst, darunter nach Gewinn."""
    gw, gm, nm, wis = ctx["geb_werte"], ctx["geb_monate"], ctx["names"], ctx["wis"]
    orte = {o["id"]: o.get("name") for o in ctx["last"].get("orte", [])}
    rohstoff = {str(o["id"]): o.get("rohstoff") for o in ctx["last"].get("orte", [])}
    pma = ctx["last"].get("gebaeude_pm") or {}
    kand = []
    akt = gm[max(gm)] if gm else {}
    for bid, w in gw.items():
        try:
            bid_i = int(bid)
        except ValueError:
            continue
        d = akt.get(bid_i) or {}
        lvl, mx, ppl = w.get("GetLevel"), w.get("GetMaxLevel"), w.get("GetProfitPerLevel")
        if not all(_num(x) for x in (lvl, mx, ppl)) or lvl >= mx or ppl <= 0:
            continue
        if (w.get("GetLevelsUnderConstruction") or 0) > 0 or (w.get("GetLevelsUnderUpgrade") or 0) > 0:
            continue
        if not (_num(d.get("employed")) and _num(d.get("employment_size")) and d["employment_size"] > 0
                and d["employed"] >= d["employment_size"] * 0.99):
            continue
        wo = ue(t"{nm(d.get('typ') or '?')} in {orte.get(d.get('ort_id'), d.get('ort_id'))}")
        kand.append({"wert": ppl, "wo": wo, "typ": d.get("typ"), "ort_id": d.get("ort_id"), "ort": orte.get(d.get("ort_id")),
                     "gueter": _produziert(wis, d.get("typ"), (pma.get(str(bid)) or {}).get("pms") or ()),
                     "text": ue(t"{wo} (Stufe {lvl:.0f}/{mx:.0f}): {_sgn(ppl)} Gewinn je Stufe")
                             + (ue(t", Steuergrundlage {_sgn(w['GetTaxBaseValuePerLevel'])}") if _num(w.get("GetTaxBaseValuePerLevel")) else "")})
    rgo = sorted(({"wert": w["GetRGOProfitPerLevel"], "ort": orte.get(int(k)) if str(k).isdigit() else k, "k": k, "gut": rohstoff.get(str(k))}
                  for k, w in ctx["ort_werte"].items() if _num(w.get("GetRGOProfitPerLevel")) and w["GetRGOProfitPerLevel"] > 0),
                 key=lambda x: -x["wert"])
    if not kand and not rgo:
        return []
    kand.sort(key=lambda x: -x["wert"])
    if not _fokusse(ctx):
        return [_ausbau_rec(ctx, kand, rgo)]
    return [_ausbau_rec(ctx, kand, rgo, fk, F, C) for fk, (F, C) in _fokusse(ctx).items()]


def _ausbau_rec(ctx, kand, rgo, fk=None, F=None, C=None):
    """Empfehlung Ausbau; mit Schwerpunkt stehen passende Gebäude und Rohstoffe vorn (die Sortierung behält den Gewinn als Reihenfolge)."""
    nm = ctx["names"]

    def geb_p(x):
        return _gebaeude_fokus(x["typ"], x["gueter"], F, C, nm) if fk else (0, "")

    def roh_p(x):
        return _gut_punkte(x["gut"], C, nm) if fk else (0, "")
    kand = sorted(kand, key=lambda x: geb_p(x)[0] <= 0)
    rgo = sorted(rgo, key=lambda x: roh_p(x)[0] <= 0)[:3]
    gut_geb = kand[0] if kand and geb_p(kand[0])[0] > 0 else None
    gut_roh = rgo[0] if rgo and roh_p(rgo[0])[0] > 0 else None
    gruende = []
    if kand:
        gruende.append(ue("Ausbau, Gewinn je Stufe laut Spiel (Ausbau-Ansicht): ") + "; ".join(x["text"] for x in kand[:5]) + ".")
    if rgo:
        def rgo_text(x):
            gold, tage = _rgo_kosten(ctx, x["k"])   # Mod ab 0.17.1 (Hauptstadt), ab 0.18 je Ort
            return f"{x['ort']} {_sgn(x['wert'])}" + (ue(t" für {_de(gold, 0)} Gold") + (ue(t", {tage} Tage Bauzeit") if tage else "") if _num(gold) else "")
        # Location.GetRGOProfitPerLevel zeigt das Spiel mit dem Symbol der Steuergrundlage (location_tooltips.gui) – davon
        # erreicht die Krone nur den Steueranteil der Stände -> keine Amortisation in Monaten
        gruende.append(ue("Rohstoff, Steuergrundlage je Stufe und Ausbaukosten laut Spiel (Location.GetRGOProfitPerLevel, "
                       "GetUpgradeRGOBuildCostAndTime): ") + "; ".join(rgo_text(x) for x in rgo) + ".")
    wahl = gut_geb or (None if gut_roh else (kand[0] if kand else None))
    if gut_geb:
        titel = ue(t"Ausbau für „{F['name']}“: {gut_geb['wo']} ({_sgn(gut_geb['wert'])} Gewinn je Stufe)")
        gruende.insert(0, ue(t"Passt zum Schwerpunkt: {gut_geb['wo']} – {geb_p(gut_geb)[1]}."))
    elif gut_roh:
        titel = ue(t"Ausbau für „{F['name']}“: Rohstoff in {gut_roh['ort']} ({_sgn(gut_roh['wert'])} Steuergrundlage je Stufe)")
        gruende.insert(0, ue(t"Passt zum Schwerpunkt: Rohstoff in {gut_roh['ort']} – {roh_p(gut_roh)[1]}."))
    elif kand:
        titel = ue(t"Ausbau: {kand[0]['wo']} bringt am meisten je Stufe ({_sgn(kand[0]['wert'])} Gewinn)")
    else:
        titel = ue(t"Ausbau: Rohstoff in {rgo[0]['ort']} bringt am meisten je Stufe ({_sgn(rgo[0]['wert'])} Steuergrundlage)")
    if fk and not (gut_geb or gut_roh):
        gruende.insert(0, ue(t"Kein Ausbau passt zum Schwerpunkt „{F['name']}“ – Reihenfolge nach Gewinn."))
    rec = _rec(
        f"ausbau:{fk}" if fk else "ausbau", "mittel", "Wirtschaft", titel,
        gruende,
        ue("Vorne in der Liste anfangen. Gewinn und Kosten neuer Gebäudetypen zeigt nur das Baumenü des Spiels – für einen Mod "
        "sind sie nicht erreichbar (Test 0.17/0.17.1)."),
        "Spielwert", ue("Gewinn je Stufe und Rohstoff-Ausbaukosten so, wie das Spiel sie anzeigt; Kosten vorhandener Gebäude fehlen."),
        "produktion", ue("Ausbau nach Empfehlung"))
    if wahl:                                    # Ort für den Klick in der Seitenleiste im Spiel (Test 0.28.3: öffnete nur das Baumenü)
        rec["ort_id"], rec["ort"] = wahl["ort_id"], wahl["ort"]
    elif str(rgo[0]["k"]).isdigit():
        x = gut_roh or rgo[0]
        rec["ort_id"], rec["ort"] = int(x["k"]), x["ort"]
    if fk:
        rec["fokus"], rec["fokus_name"] = fk, F["name"]
        if not (gut_geb or gut_roh):
            rec["fokus_treffer"] = False         # steht nicht vor den allgemeinen Empfehlungen
    return rec


def _rgo_kosten(ctx, ort_id):
    """Rohstoff-Ausbau laut Spiel (Mod ab 0.17.1, Text Location.GetUpgradeRGOBuildCostAndTime: „Standardmäßige Bauzeit:
    225Tage / Baukosten: 171“) -> (Gold, Tage) oder (None, None). Der Text schreibt Dezimalpunkte („Baukosten: 84.3“, Test 0.18
    an allen 8 Orten: 70.2 / 84.3 / 98.3 / 140 / 168) – vorher als Tausenderpunkt gelesen (84.3 -> 843)."""
    t = _text(ctx["db"], ctx["tag"], "ort", ort_id, "GetUpgradeRGOBuildCostAndTime")
    k = re.search(r"(?:Baukosten|Building Costs):\s*(\d+(?:\.\d+)?)", t or "")
    z = re.search(r"(?:Bauzeit|Building Time):\s*(\d+)", t or "")
    gold = float(k.group(1)) if k else None
    return gold, (int(z.group(1)) if z else None)


def _aktion_text(a, mt=None):
    """„Die Erkrankten absondern (10 Stabilität: Seuchenwiderstand +15 %)“ aus krankheiten_wissen.aktionen."""
    preis = ", ".join(ue(t"{_de(v, 0)} Stabilität") if k == "stability" else (ue("Gold (mit dem Einkommen skaliert)") if k == "scaled_gold"
                      else f"{k} {v}") for k, v in (a.get("preis") or {}).items())
    w, ja = [], []
    for m in a.get("wirkung") or []:
        for x in m.get("werte") or []:
            if _num(x.get("wert")):
                w.append(f"{x['name']} {ue(t'{_sgn(x["wert"] * 100, 0)} %') if x.get('prozent') else _sgn(x['wert'], 2)}"
                         + (f" × {x['skal']}" if x.get("skal") else ""))
            elif x.get("roh") == "yes":
                ja.append(x["name"])                       # z. B. „Pesthaus möglich“ – nie abschneiden
    return f"{a['name']} ({'; '.join(p for p in (preis, ', '.join(w[:3] + ja)) if p)})"


def r_krankheit(ctx):
    """Krankheit in eigenen Orten (Daten-Mod 0.18: disease_presence je Ort; sonst Spielstand) oder im Heimatmarkt
    (Spielstand: befallene Orte des Ausbruchs, die Mitglied unseres Markts sind) -> Aktionen und Gebäude laut Spieldateien.
    Die Wirkung auf Tote ist nicht berechenbar -> messen."""
    kr = ctx["last"].get("krankheiten") or {}
    kw = ctx["kw"] or {}
    if not kr and not ctx["seuche_orte"]:
        return []
    nm, orte = ctx["names"], {str(o["id"]): o.get("name") for o in ctx["last"].get("orte", [])}
    namen = {k: v.get("name") or nm(k) for k, v in (kr.get("krankheiten") or {}).items()}
    befallen = {}                                             # krankheit -> [(ort, anteil)]
    for oid, w in ctx["seuche_orte"].items():                # live (Mod 0.18)
        for f, v in w.items():
            if f.startswith("pres_") and _num(v) and v > 0:
                befallen.setdefault(f[5:], []).append((orte.get(str(oid), str(oid)), v))
    if not ctx["seuche_orte"]:                               # sonst Spielstand
        for oid, ks in (kr.get("orte") or {}).items():
            for k, v in ks.items():
                if (v.get("ausbreitung") or 0) > 0:
                    befallen.setdefault(k, []).append((orte.get(oid, oid), v["ausbreitung"]))
    # Aktionen und Pesthaus gibt es nur, solange die Situation Schwarzer Tod läuft (generic_actions/black_death.txt:
    # visible situation_is_active; building_types pest_house: country_potential is_situation_active + enable_pest_house)
    bd_aktiv = ctx["seuche_land"].get("bd_aktiv") == 1 or (kr.get("schwarzer_tod") or {}).get("status") == "active"
    akt = [_aktion_text(a) for a in kw.get("aktionen") or [] if a.get("gruppe") in ("bd_disease_control_actions",)] if bd_aktiv else []
    def geb_text(g):
        teile = [ue(t"{x['name']} {_sgn(x['wert'] * 100, 0)} %") for x in g.get("wirkung") or []
                 if x.get("prozent") and _num(x.get("wert"))]
        return (f"{g['name']} ({', '.join(teile)})" if teile else g["name"]) + (f" – {g['bedingung']}" if g.get("bedingung") else "")
    def geb(pest):
        return [geb_text(g) for g in kw.get("gebaeude") or [] if pest or g.get("key") != "pest_house"]
    out = []
    for k, liste in sorted(befallen.items()):
        name = namen.get(k) or nm(k)
        tote = ctx["seuche_land"].get(f"tote_{k}")
        pest = k == "bubonic_plague" and bd_aktiv
        g = geb(pest)
        out.append(_rec(
            f"krank:{k}", "hoch", "Krankheiten", ue(t"{name} in {len(liste)} eigenen Orten"),
            [ue("Ausbreitung: ") + ", ".join(f"{o} {_pz(v, 1)}" for o, v in sorted(liste, key=lambda x: -x[1])) + ".",
             _num(tote) and ue(t"Tote im Land durch {name} bisher: {_de(math.floor(tote * 1000), 0)} (Daten-Mod)."),
             pest and akt and ue("Aktionen der Situation Schwarzer Tod (eine je Gruppe): ") + "; ".join(akt) + ".",
             g and ue("Gebäude mit Seuchenwiderstand: ") + "; ".join(g) + "."],
            (ue("Seuchenwiderstand erhöhen und Ausbreitung bremsen – passende Aktion im Situationsfenster, Pesthaus in den befallenen "
             "Orten (nach der Aktion) bzw. Krankenhaus.") if pest else
             ue("Seuchenwiderstand erhöhen – Krankenhaus in großen Orten (Entwicklung ab 20).")),
            "messen", ue("Wie viele Tote eine Maßnahme verhindert, rechnet das Spiel nicht vor – nach dem Umsetzen markieren."),
            "krankheiten", ue(t"{name}: Maßnahme gegen Ausbreitung")))
    if befallen:
        return out
    markt = (ctx["last"].get("markt") or {}).get("zentrum") or ue("Heimatmarkt")
    for a in kr.get("ausbrueche") or []:
        if a.get("orte_markt_anzahl"):
            name = a.get("krankheit_name") or nm(a["krankheit"])
            out.append(_rec(
                f"krankmarkt:{a['id']}", "mittel", "Krankheiten",
                ue(t"{name} im Markt {markt}: {a['orte_markt_anzahl']} Orte befallen"),
                [ue("Befallen: ") + ", ".join(f"{o['name']} {_pz(o['ausbreitung'], 0)}" for o in a.get("orte_markt") or []) + ".",
                 ue("Krankheiten springen laut Spieldatei auf Nachbarorte, zum Marktzentrum, über dessen Handelspartner und zur "
                 "Hauptstadt des Besitzers über (diseases/readme.txt)."),
                 geb(False) and ue("Gebäude mit Seuchenwiderstand: ") + "; ".join(geb(False)) + "."],
                ue("Vorsorgen: Seuchenwiderstand in Orten nahe am Marktzentrum erhöhen (Krankenhaus)")
                + (ue("; bei der Pest kommen die Aktionen des Schwarzen Tods in Frage („Das Land abschotten“ sperrt den Außenhandel).")
                   if a.get("krankheit") == "bubonic_plague" and bd_aktiv else "."),
                "messen", ue("Nach dem Umsetzen markieren."), "krankheiten", ue(t"{name}: Vorsorge")))
    return out


def r_krieg(ctx):
    """Krieg (Nutzerwunsch 25.10., Kriegskachel Punkt 4; Prüfung 25.10. eingearbeitet) – je laufendem Krieg (krieg.build):
    - Kriegsziel: kontrolliert laut Spieltext (Punkte-Aufschlüsselung, Daten-Mod) die Gegenseite das Kriegsziel -> hoch; ohne
      Spieltext nur „Zielort besetzt“ aus dem Spielstand (das Kriegsziel kann eine ganze Provinz sein) -> mittel;
    - Gegner-Heere in eigenen Orten, je Ort zusammengefasst (Daten-Mod ab 0.19 bzw. Spielstand);
    - Kräfteverhältnis: Heer der Seiten (Summe army_size, Spielwerte) ab 1,5 : 1, auch wenn unsere Seite kein Heer hat;
    - Gegner mit dem größten Heer unter 10 % Mannstärke: als Grund beim Kräfteverhältnis, wenn wir unterlegen sind, sonst Rat
      „Druck machen“.
    Landesweit (einmal, nicht je Krieg): eigene Mannstärke unter 25 % des Höchstwerts, Kriegsmüdigkeit ab der Hälfte des
    Höchstwerts. Sind sie knapp bzw. hoch, entfallen die Offensiv-Räte (Überzahl nutzen, Druck machen); die Gelegenheiten
    stehen dann als Gründe in der Landesregel. Kriegspunkte = Spielwert GetWarScore aus unserer Sicht (die Aufschlüsselung
    des Spiels ergibt ihn). Die Schwellen sind Regeln des Ratgebers, die Zahlen Spielwerte."""
    out = []
    eigene = {o.get("id") for o in ctx["last"].get("orte") or []}
    land = ctx["land"]
    kriege = ctx["kriege"]
    if not kriege:
        return out
    # Landeswerte (für alle Kriege gleich)
    ich0 = next((t for t in kriege[0]["teilnehmer"] if t["wir"]), {})
    kr = ich0.get("kraefte") or {}
    mp, mx, mm = kr.get("manpower"), kr.get("max_manpower"), kr.get("monthly_manpower")
    mp_knapp = _num(mp) and _num(mx) and mx > 0 and mp < 0.25 * mx
    we, wm = kr.get("war_exhaustion"), land.get("curmax_war_exhaustion")
    muede = _num(we) and _num(wm) and wm > 0 and we >= 0.5 * wm
    gelegenheiten = []
    for w in kriege:
        kid, k, name = w["id"], f"krieg_{w['id']}", w["name"]
        wir, geg = w.get("wir_seite"), w.get("gegen_seite")
        sw, sg = (w.get("seiten") or {}).get(wir) or {}, (w.get("seiten") or {}).get(geg) or {}
        T = {t["tag"]: t for t in w["teilnehmer"]}
        quelle = ue(t"Daten-Mod {w.get('fremd_datum') or w.get('datum_live') or ''}").strip()
        pw = w["punkte_spiel"] if _num(w.get("punkte_spiel")) else w.get("punkte_wir")
        punkte = ue(t"Kriegspunkte {_sgn(pw, 1)} (Spielwert)") if _num(pw) else ""
        a, b = sw.get("army_size"), sg.get("army_size")
        heer_txt = (ue(t"Heer unsere Seite {_de(a, 1)} Tsd., Gegner {_de(b, 1)} Tsd. Mann (Summe army_size je Land, {quelle}).")
                    if _num(a) and _num(b) else "")
        # Kriegsziel
        ziel_orte = (w.get("kriegsziel") or {}).get("orte") or []
        ziel_txt = w.get("kriegsziel_text") or ", ".join(o["name"] for o in ziel_orte) or ue("Kriegsziel")
        if w.get("ziel_kontrolle"):
            if w["ziel_kontrolle"] == geg and geg in ("Angreifer", "Verteidiger"):
                verteidigen = wir == "Verteidiger"
                out.append(_rec(
                    f"krieg_ziel:{kid}", "hoch", "Militär",
                    ue(t"{name}: Kriegsziel „{ziel_txt}“ ") + (ue("in Hand der Gegner") if verteidigen else ue("noch beim Verteidiger")),
                    [ue(t"Laut Spiel kontrolliert der {ue(geg)} das Kriegsziel (Punkte-Aufschlüsselung, Daten-Mod {w.get('datum_live')})."),
                     ue("Wer das Kriegsziel hält, bekommt laufend Kriegspunkte") + (ue(" (HasTickingWarScore = ja).") if w.get("ticking") else "."),
                     punkte],
                    (ue("Kriegsziel zurückerobern") if verteidigen else ue("Kriegsziel erobern"))
                    + (ue(t": Armee zu {', '.join(o['name'] for o in ziel_orte)} und belagern.") if ziel_orte else "."),
                    "messen", ue("Kriegspunkte im Verlauf beobachten."), k, ue("Kriegsziel ") + (ue("zurückerobert") if verteidigen else ue("erobert"))))
        else:
            hg = [o for o in ziel_orte if o.get("kontrolleur") and (T.get(o["kontrolleur"]) or {}).get("seite") == geg]
            if hg:
                out.append(_rec(
                    f"krieg_zielort:{kid}", "mittel", "Militär",
                    ue(t"{name}: Zielort {', '.join(o['name'] for o in hg)} besetzt von {(T.get(hg[0]['kontrolleur']) or {}).get('name', hg[0]['kontrolleur'])}"),
                    [ue(t"Spielstand {w.get('datum_spielstand')}; ob das ganze Kriegsziel beim Gegner liegt, zeigt erst der Spieltext "
                     t"(Daten-Mod)."), punkte],
                    ue("Zielort zurückgewinnen, bevor er dem Gegner Kriegspunkte bringt."),
                    "messen", ue("Kontrolle des Orts beobachten."), k, ue("Zielort zurückgewonnen")))
        # Gegner-Heere in eigenen Orten, je Ort zusammengefasst
        je_ort = {}
        for e in w.get("einheiten") or []:
            if e.get("seite") == geg and e.get("art") == "heer" and e.get("ort_id") in eigene:
                je_ort.setdefault(e["ort_id"], []).append(e)
        for oid, es in je_ort.items():
            mann = sum(e["mann"] for e in es if _num(e.get("mann")))
            laender = sorted({(T.get(e["land"]) or {}).get("name", e["land"]) for e in es})
            fuehrer = [ue(t"{e['fuehrer']['name']} (Militär {_de(e['fuehrer']['mil'], 0)})") for e in es
                       if e.get("fuehrer") and _num(e["fuehrer"].get("mil"))]
            q = ue(t"Daten-Mod {w.get('datum_live')}") if es[0].get("quelle") == "Mod" else ue(t"Spielstand {w.get('datum_spielstand')}")
            out.append(_rec(
                f"krieg_feind_ort:{kid}:{oid}", "hoch", "Militär",
                ue(t"Gegner-Heer in {es[0].get('ort')}: {_de(mann, 0)} Mann ({', '.join(laender)})"),
                [ue(t"Ort gehört uns; {len(es)} Heer(e) laut {q}") + (ue(t", Heerführer {', '.join(fuehrer)}") if fuehrer else "") + ".",
                 heer_txt],
                ue("Eigene Armeen sammeln und das Heer stellen, wenn wir dort überlegen sind; sonst die Festung halten lassen."),
                "messen", ue("Belagerung und Kontrolle des Orts beobachten."), k, ue(t"Gegner in {es[0].get('ort')} gestellt")))
        # Gegner mit dem größten Heer ohne Mannstärke (nur Länder, die noch im Krieg sind)
        g = max((t for t in w["teilnehmer"] if t["seite"] == geg and t.get("im_krieg_live") is not False
                 and _num((t.get("kraefte") or {}).get("army_size"))), key=lambda t: t["kraefte"]["army_size"], default=None)
        g_leer = None
        if g:
            gp, gx = g["kraefte"].get("manpower"), g["kraefte"].get("max_manpower")
            if _num(gp) and _num(gx) and gx > 0 and gp < 0.1 * gx:
                g_leer = (ue(t"{g['name']} hat kaum Mannstärke: {_de(gp, 3)} von {_de(gx, 2)} Tsd. – Verluste kann es kaum ersetzen "
                          t"(stellt das größte Heer der Gegner, {_de(g['kraefte']['army_size'], 1)} Tsd. Mann, {quelle})."))
        # Kräfteverhältnis (unsere Seite ohne Heer zählt als unterlegen)
        unterlegen = _num(a) and _num(b) and b > 0 and (a == 0 or b >= 1.5 * a)
        ueberlegen = _num(a) and _num(b) and a > 0 and a >= 1.5 * b
        if _num(a) and _num(b):
            regs = ue(t"Regimenter {_de(sw.get('num_regiments') or 0, 0)} gegen {_de(sg.get('num_regiments') or 0, 0)}.")
            ohne = (ue(t"Ohne Werte: {sw.get('ohne_werte', 0)} Länder unserer Seite, {sg.get('ohne_werte', 0)} der Gegner.")
                    if sw.get("ohne_werte") or sg.get("ohne_werte") else "")
            if unterlegen:
                out.append(_rec(
                    f"krieg_unterlegen:{kid}", "hoch", "Militär",
                    ue(t"{name}: unsere Seite hat kein Heer, Gegner {_de(b, 1)} Tsd. Mann") if a == 0
                    else ue(t"{name}: Heer der Gegner {_de(b / a, 1)}× so groß"),
                    [heer_txt, ohne, regs, g_leer, punkte],
                    ue("Keine Feldschlacht gegen die Hauptarmee ohne Überzahl am Ort; Armeen mit Verbündeten zusammenlegen, Festungen halten "
                    "und Frieden prüfen, solange die Kriegspunkte es erlauben."),
                    "messen", ue("Kräfteverhältnis und Kriegspunkte im Verlauf beobachten."), k, ue("Kräfte gebündelt")))
            elif ueberlegen:
                if mp_knapp or muede:
                    gelegenheiten.append(ue(t"{name}: unsere Seite hat {_de(a / b, 1)}× so viel Heer ({_de(a, 1)} gegen {_de(b, 1)} Tsd. Mann)."))
                else:
                    out.append(_rec(
                        f"krieg_ueberlegen:{kid}", "mittel", "Militär", ue(t"{name}: unsere Seite hat {_de(a / b, 1)}× so viel Heer"),
                        [heer_txt, ohne, regs, g_leer, punkte],
                        ue("Die Überzahl nutzen: Gegner-Armeen stellen, Orte der Gegner belagern und Kriegspunkte für den Frieden sammeln."),
                        "messen", ue("Kriegspunkte im Verlauf beobachten."), k, ue("Offensive begonnen")))
        if g_leer and not unterlegen and not ueberlegen:
            if mp_knapp or muede:
                gelegenheiten.append(f"{name}: {g_leer}")
            else:
                out.append(_rec(
                    f"krieg_gegner_leer:{kid}", "mittel", "Militär",
                    ue(t"{g['name']} hat kaum Mannstärke: {_de(g['kraefte']['manpower'], 3)} von {_de(g['kraefte']['max_manpower'], 2)} Tsd."),
                    [g_leer, punkte],
                    ue(t"Jetzt Druck machen: Armeen von {g['name']} stellen und seine Orte belagern."),
                    "messen", ue("Kriegspunkte im Verlauf beobachten."), k, ue(t"Druck auf {g['name']}")))
    # Landesregeln einmal (Kachel: erster Krieg)
    k0 = f"krieg_{kriege[0]['id']}"
    abwaegen = ([ue("Abwägen gegen die Gelegenheiten: ") + " ".join(gelegenheiten)] if gelegenheiten else [])
    if mp_knapp:
        voll = ue(t", voll in etwa {_de((mx - mp) / mm, 0)} Monaten") if _num(mm) and mm > 0 else ""
        out.append(_rec(
            "krieg_mannstaerke", "mittel", "Militär", ue(t"Mannstärke knapp: {_de(mp, 2)} von {_de(mx, 2)} Tsd."),
            [ue(t"Zuwachs {_de(mm or 0, 3)} Tsd. je Monat{voll} (Spielwerte, Daten-Mod).")] + abwaegen,
            ue("Verluste durch Zermürbung und verlustreiche Belagerungen begrenzen, bis die Mannstärke wieder steigt."),
            "messen", ue("Mannstärke im Verlauf beobachten."), k0, ue("Verluste begrenzt")))
    if muede:
        out.append(_rec(
            "krieg_muedigkeit", "mittel", "Militär", ue(t"Kriegsmüdigkeit {_de(we, 2)} von höchstens {_de(wm, 0)}"),
            [ue("Spielwerte (Daten-Mod).")] + ([] if mp_knapp else abwaegen),
            ue("Frieden anstreben, solange die Kriegspunkte es erlauben."),
            "messen", ue("Kriegsmüdigkeit nach dem Frieden beobachten."), k0, ue("Frieden geschlossen")))
    return out


def r_kriegsgelegenheit(ctx):
    """Kriegsgelegenheit (Nutzerwunsch 25.10., Kachel Nachbarn Punkt 4): Länder mit grüner Ampel (Kriegsgrund, kein
    Waffenstillstand, unser Offensivbündnis mindestens 1,5 : 1 gegen ihr Verteidigungsbündnis – nachbarn.bewertung), die drei
    mit dem besten Verhältnis. Sind wir schon im Krieg oder liegt unsere Mannstärke unter der Hälfte, steht das als
    Einschränkung dabei."""
    nb = ctx["nachbarn"] or {}
    wir = nb.get("wir") or {}
    out = []
    if nb.get("veraltet"):
        return out                                    # Mod-Werte deutlich älter als der Spielstand (nachbarn.build)
    gruen = [r for r in nb.get("laender") or [] if r["bewertung"]["stufe"] == "gruen"][:3]
    einschr = []
    if wir.get("kriege"):
        einschr.append(ue(t"Wir sind schon in {wir['kriege']} Krieg(en)."))
    mp, mx = wir.get("manpower"), wir.get("max_manpower")
    if _num(mp) and _num(mx) and mx > 0 and mp < 0.5 * mx:
        einschr.append(ue(t"Unsere Mannstärke ist nur {_de(mp, 2)} von {_de(mx, 2)} Tsd."))
    for r in gruen:
        b = r["bewertung"]
        w = r["werte"]
        heer = (ue(t"Heer {_de(w['army_size'], 1)} Tsd. Mann gegen unser {_de(wir.get('army_size') or 0, 1)} Tsd.")
                if _num(w.get("army_size")) else "")
        out.append(_rec(
            f"kriegsgelegenheit:{r['tag']}", "mittel", "Militär", ue(t"Kriegsgelegenheit: {r['name']} ({_de(b['verhaeltnis'], 1)} : 1)")
            if _num(b.get("verhaeltnis")) else ue(t"Kriegsgelegenheit: {r['name']}"),
            [*(g[0].upper() + g[1:] + "." for g in b["gruende"]), heer, *(h[0].upper() + h[1:] + "." for h in b["hinweise"]),
             *einschr, ue(t"Spielwerte laut Daten-Mod {nb.get('fremd_datum') or ''}.")],
            ue(t"Krieg gegen {r['name']} vorbereiten: Kriegsgrund nutzen, Armeen sammeln, Verbündete rufen."),
            "messen", ue("Kriegsverlauf in der Kriegskachel beobachten."), "nachbarn", ue(t"Krieg gegen {r['name']} erklärt")))
    return out


# Schwelle der Regel „Zölle“ (Regel des Ratgebers): Zölle ab 10 % des Routengewinns vor Zoll, ab 25 % Wichtigkeit „mittel“
ZOLL_SCHWELLE, ZOLL_SCHWELLE_MITTEL = 0.10, 0.25


def r_zoelle(ctx):
    """Zölle auf unseren Routen (Patch 1.4, 27.10.) – Daten aus handel.build: Trade.GetTariffValue je Route (negativ = wir zahlen,
    im Gewinn schon abgezogen – nachgerechnet 27.10.), Spieltexte GetTariffInfo (Land, Satz, Gut), Spielstand (Meinungsabzug).
    Handlung: Zollbefreiung erbitten (Diplomatie) oder die Kapazität über eine Handelsbestellung mit Mindestgewinn umlenken.
    Wirkung berechnet: Gewinn der Routen + Zoll; Anteil der Staatskasse = × Modifikator Handelseinnahmen (geprüft 29.09.)."""
    hz = ctx.get("handel") or {}
    routen = hz.get("routen") or []
    bezahlt = -sum(x["zoll"] for x in routen if _num(x.get("zoll")) and x["zoll"] < 0)
    vor = hz.get("gewinn_vor_zoll")
    if bezahlt <= 0 or not _num(vor) or vor <= 0 or bezahlt / vor < ZOLL_SCHWELLE:
        return []
    anteil = bezahlt / vor
    zahler = [g for g in hz.get("je_land") or [] if g["betrag"] < 0]
    top = zahler[0] if zahler else None
    n = sum(1 for x in routen if _num(x.get("zoll")) and x["zoll"] < 0)
    gruende = [ue(t"{n} Route(n) zahlen zusammen {_de(bezahlt)} Gold Zoll je Monat = {_pz(anteil)} des Routengewinns vor Zoll "
               t"({_de(hz['gewinn'])} + {_de(bezahlt)}; der Zoll ist im Gewinn schon abgezogen). Daten-Mod {hz.get('datum')}.")]
    for g in zahler[:3]:
        saetze = {}
        for e in g["eintraege"]:
            saetze.setdefault((e["art"], e["richtung"], e["satz"]), []).append(e["gut"])
        teile = [ue(t"{_zollart(r, a)} {_pz(s, 0)} auf "
                 t"{', '.join(sorted(set(gs)))}") for (a, r, s), gs in sorted(saetze.items())]
        gruende.append(ue(t"{g['land']}: {_de(g['betrag'])} je Monat") + (f" ({'; '.join(teile)})" if teile else "")
                       + (ue(t"; Meinungsabzug durch Ausfuhrzölle {_de(g['meinung'])} (Spielstand)") if _num(g.get("meinung")) else "")
                       + ".")
    unter = set(hz.get("unter_mindest") or [])
    um = [x for x in routen if x["id"] in unter and _num(x.get("zoll")) and x["zoll"] < 0]
    if um and _num(hz.get("mindestgewinn")):
        gruende.append(ue(t"{len(um)} dieser Routen liegen unter {_de(hz['mindestgewinn'])} Gewinn je Händlerkapazität, dem "
                       t"Standard-Mindestgewinn einer Handelsbestellung (Define DEFAULT_TRADE_ORDER_MIN_PROFIT): ")
                       + ", ".join(f"{x.get('gut_name') or x.get('gut')} {_de(x['je_kap'])}" for x in um[:5]) + ".")
    gruende.append(ue("„Zollbefreiung erbitten“ (Diplomatie): Bereitschaft der KI laut scripted_relations/tariff_exemption.txt "
                   "= −75 + ihr Vertrauen in uns + ihre Meinung von uns (positive ÷ 5); Rivale −100, eigenes Klientelland 1.000. "
                   "Die Beziehung ist als Befreiung von Einfuhrzöllen definiert (is_exempt_from_import_tariff) – ob sie "
                   "Ausfuhrzölle erlässt, ist ungeprüft."))
    ti = (hz.get("modifikatoren") or {}).get("trade_income")
    wirkung = ue(t"Entfällt der Zoll, steigt der Gewinn der Routen um bis zu {_de(bezahlt)} Gold je Monat") + (
        ue(t"; die Staatskasse erhält davon den Anteil Handelseinnahmen {_pz(ti)} = {_de(bezahlt * ti)}.") if _num(ti) else ".")
    return [_rec("zoelle", "mittel" if anteil >= ZOLL_SCHWELLE_MITTEL else "niedrig", "Handel",
                 ue(t"Zölle kosten {_de(bezahlt)} Gold je Monat ({_pz(anteil, 0)} des Routengewinns)")
                 + (ue(t" – größter Posten {top['land']} {_de(top['betrag'])}") if top else ""),
                 gruende,
                 ue(t"Bei {top['land'] if top else ue('dem Marktbesitzer')} „Zollbefreiung erbitten“ (Diplomatie); sonst die Kapazität "
                 t"dieser Routen über eine Handelsbestellung mit Mindestgewinn in Märkte ohne Zoll lenken."),
                 "berechnet", wirkung, "handel", ue("Zollbefreiung erbeten / Routen umgelenkt"))]


# ---------------------------------------------------------------- Handelsbestellungen (Nutzerwunsch 29.10.)
# Daten aus handel.build: pruefung (je Bestellung und Ware: Routen live und je Monat, Lage im Markt, Preise in Reichweite,
# Ausfuhrzoll), vorschlaege (je Schwerpunkt des Wirtschaftsplans), defines_handel (Schwellen aus den Defines). Spielregeln mit
# Quelle in handel.py und analysis/MECHANIK.md („Zölle und Handelsbestellungen“).
def _zollart(richtung, art):
    """Ausfuhrzoll, Einfuhrzoll, Ausfuhr-Subvention oder Einfuhr-Subvention."""
    if art == "zoll":
        return ue("Ausfuhrzoll") if richtung == "ausfuhr" else ue("Einfuhrzoll")
    return ue("Ausfuhr-Subvention") if richtung == "ausfuhr" else ue("Einfuhr-Subvention")


def _richtung(r):
    return ue("Einfuhr") if r == "einfuhr" else ue("Ausfuhr")


def r_bestellung_ohne_route(ctx):
    """Waren einer Handelsbestellung seit mindestens 3 Monaten ohne Route (Regel des Ratgebers, handel.OHNE_ROUTE_MONATE) – mit
    den belegten Gründen aus handel.pruefung. „mittel“, wenn eine Ware gegen die Lage im Markt der Bestellung läuft (Ausfuhr bei
    Nachfrage > Angebot, Einfuhr bei Angebot ≥ Nachfrage), sonst „niedrig“. Ohne Route bindet ein Eintrag keine Kapazität (Spiel:
    die Bestellung setzt die zugewiesene Kapazität nicht zwingend ein) – Wirkung messen."""
    hz = ctx.get("handel") or {}
    out = []
    for b in (hz.get("pruefung") or {}).get("bestellungen") or []:
        ohne = [g for g in b.get("gueter") or [] if not g.get("routen") and (g.get("ohne_seit") or 0) >= handel.OHNE_ROUTE_MONATE]
        if not ohne:
            continue
        markt = b.get("markt_name") or b.get("markt")
        gruende, tun, gegen = [], [], False
        for g in ohne:
            lg = g.get("lage") or {}
            gruende.append(f"{g['gut_name']} ({_richtung(g['richtung'])}): " + " ".join(g.get("befund") or []))
            s = lg.get("saldo")
            if g["richtung"] == "ausfuhr" and _num(s) and s < 0:
                gegen = True
                tun.append(ue(t"{g['gut_name']}: Ausfuhreintrag entfernen – {markt} ist selbst knapp"))
            elif g["richtung"] == "einfuhr" and _num(s) and s >= 0:
                gegen = True
                tun.append(ue(t"{g['gut_name']}: Einfuhreintrag streichen, außer er soll nur Handelsgewinn bringen – {markt} hat genug"))
            elif g.get("letzte") and _num(b.get("mindestgewinn")) and (w := [v for _, v, gen in g["letzte"]["serie"] if _num(v) and gen != 0]) \
                    and w[-1] < b["mindestgewinn"]:
                tun.append(ue(t"{g['gut_name']}: Mindestgewinn nur senken, wenn der Handel auch mit wenig Gewinn gewollt ist"))
            else:
                tun.append(ue(t"{g['gut_name']}: im Spiel prüfen"))
        k = b.get("kap") or {}
        if _num(k.get("kapazitaet")):
            be, au = b.get("bestellung") or {}, b.get("automatik") or {}
            gruende.append(ue(t"Unsere Händlerkapazität in {markt}: {_de(k['kapazitaet'])}, genutzt {_de(k['genutzt'])} (Spielstand) – "
                           t"Routen der Bestellung {_de(be.get('kapazitaet') or 0)}, der Automatisierung {_de(au.get('kapazitaet') or 0)} "
                           t"(Daten-Mod {hz.get('datum') or ''})."))
        gruende.append(ue("Ohne gewinnbringende Route sucht die KI jeden Tag weiter; die beste Route und ihren Gewinn je "
                       "Händlerkapazität zeigt das Spiel in der Bestellung („Die beste Route ist … minimal benötigt …“) – den Wert "
                       "kann der Ratgeber nicht lesen."))
        out.append(_rec(
            f"bestellung_ohne_route:{b['id']}", "mittel" if gegen else "niedrig", "Handel",
            ue(t"Handelsbestellung {markt} ohne Route: ") + ", ".join(
                f"{g['gut_name']} ({_richtung(g['richtung'])}) " + (ue(t"in {g['monate']} Monaten nie") if g.get("nie")
                                                                   else ue(t"seit {g['ohne_seit']} Monaten")) for g in ohne),
            gruende,
            ue(t"In der Bestellung Nr. {b['id']} ({markt}): ") + "; ".join(tun) + ".",
            "messen", ue("Ohne Route bindet ein Eintrag keine Händlerkapazität (Spiel: die Bestellung setzt die zugewiesene Kapazität "
            "nicht zwingend ein). Bereinigen verhindert, dass eine Route gegen die Lage im eigenen Markt entsteht, wenn sich die Preise "
            "ändern – nach dem Umsetzen markieren."),
            "handel", ue(t"Handelsbestellung {markt} bereinigt")))
    return out


def r_bestellung_gewinn(ctx):
    """Routen einer Handelsbestellung verdienen je Händlerkapazität deutlich weniger als die Automatisierung im selben Markt:
    Automatisierung ≥ Bestellung × 1,25 (Define NAI.AI_STEAL_MERCHANT_CAPACITY_PROFIT_MARGIN – ab diesem Abstand verschiebt die KI
    selbst Kapazität zur besseren Route), beide mit mindestens 0,1 Kapazität (TRADE_ORDER_MIN_TRADE_CAPACITY). Gewinn je
    Kapazität = GetProfitPerMerchantCapacity (Daten-Mod). Wirkung messen."""
    hz = ctx.get("handel") or {}
    df = hz.get("defines_handel") or {}
    faktor, min_tc = df.get("AI_STEAL_MERCHANT_CAPACITY_PROFIT_MARGIN", 1.25), df.get("TRADE_ORDER_MIN_TRADE_CAPACITY", 0.1)
    out = []
    for b in (hz.get("pruefung") or {}).get("bestellungen") or []:
        be, au = b.get("bestellung") or {}, b.get("automatik") or {}
        if not (_num(be.get("je_kap")) and _num(au.get("je_kap")) and (be.get("kapazitaet") or 0) >= min_tc
                and (au.get("kapazitaet") or 0) >= min_tc and be["je_kap"] > 0 and au["je_kap"] >= be["je_kap"] * faktor):
            continue
        markt = b.get("markt_name") or b.get("markt")
        verlauf = [f"{g['gut_name']} " + " → ".join(f"{_de(v)} ({m})" for m, v, _ in g["letzte"]["serie"] if _num(v))
                   for g in b.get("gueter") or [] if g.get("routen") and g.get("letzte")]
        kap_txt = (ue(t"{_de(b['kapazitaet_bestellung'], 0)} % unserer Händlerkapazität") if b.get("anteil")
                   else ue(t"{_de(b['kapazitaet_bestellung'])} Händlerkapazität")) if _num(b.get("kapazitaet_bestellung")) else ue("ihre Kapazität")
        out.append(_rec(
            f"bestellung_gewinn:{b['id']}", "niedrig", "Handel",
            ue(t"Handelsbestellung {markt}: {_de(be['je_kap'])} je Händlerkapazität, Automatisierung {_de(au['je_kap'])}"),
            [ue(t"Routen der Bestellung Nr. {b['id']}: {be['routen']} mit {_de(be['kapazitaet'])} Kapazität, Gewinn {_de(be['gewinn'])}; "
             t"Automatisierung in {markt}: {au['routen']} Route(n) mit {_de(au['kapazitaet'])} Kapazität, Gewinn {_de(au['gewinn'])} "
             t"(Daten-Mod {hz.get('datum') or ''})."),
             verlauf and ue("Gewinn je Händlerkapazität der Bestellung zuletzt: ") + "; ".join(verlauf) + ue(" (Daten-Mod)."),
             ue(t"Ab dem {_de(faktor)}-fachen Gewinn je Kapazität verschiebt die KI selbst Kapazität zur besseren Route (Define "
             t"AI_STEAL_MERCHANT_CAPACITY_PROFIT_MARGIN)."),
             ue("Je näher der beste Gewinn einer Ware am Mindestgewinn der Bestellung liegt, desto weniger Kapazität gibt die Bestellung "
             "ihr (Spieltext zum Mindestgewinn). Deutung, nicht belegt: ob frei werdende Kapazität der Automatisierung zufällt."),
             ue(t"Der Wert der Automatisierung gilt für {_de(au['kapazitaet'])} Kapazität; mehr Kapazität auf derselben Ware drückt den "
             t"Preis (Spieltext zum Mindestgewinn) – ob er auf der Menge der Bestellung hält, ist offen.")],
            ue(t"Prüfen, ob die Bestellung Nr. {b['id']} so viel Kapazität braucht ({kap_txt}")
            + (ue(t", Mindestgewinn {_de(b['mindestgewinn'])}") if _num(b.get("mindestgewinn")) else "") + ue("): ihre Kapazität schrittweise "
            "senken und beobachten, ob die Automatisierung mehr verdient – nur wenn die Bestellung keinem anderen Zweck dient. Den "
            "Mindestgewinn nicht über den laufenden Gewinn je Kapazität heben, sonst baut das Spiel die Route der Bestellung ab."),
            "messen", ue("Ob die Automatisierung mit mehr Kapazität ihren Gewinn je Kapazität hält, zeigt erst der Versuch – nach dem "
            "Umsetzen markieren, die Kachel Entscheidungen vergleicht den Handel vorher und nachher."),
            "handel", ue(t"Handelsbestellung {markt}: Kapazität/Mindestgewinn geändert")))
    return out


def r_routen_unter_mindest(ctx):
    """Routen unter dem Mindestgewinn je Händlerkapazität (live, mindestens 0,1 Kapazität): Routen einer Bestellung unter deren
    Mindestgewinn (wenn eingeschaltet), Routen der Automatisierung unter 0,25 (Define NAI.AI_PERFORMANCE_TRADE_PROFIT_PER_WEIGHT_CUTOFF:
    darunter überspringt die KI eine Route; gleich dem Standard-Mindestgewinn einer Bestellung). Geschützte Routen zählen nicht."""
    hz = ctx.get("handel") or {}
    df = hz.get("defines_handel") or {}
    min_tc = df.get("TRADE_ORDER_MIN_TRADE_CAPACITY", 0.1)
    auto_min = df.get("AI_PERFORMANCE_TRADE_PROFIT_PER_WEIGHT_CUTOFF", hz.get("mindestgewinn"))
    zu = {}                                   # Route -> Mindestgewinn ihrer Bestellung (nur eingeschaltet)
    for p in (hz.get("pruefung") or {}).get("bestellungen") or []:
        for g in p.get("gueter") or []:
            for r in g.get("routen") or []:
                zu[r["id"]] = p.get("mindestgewinn")
    best, auto = [], []
    for x in hz.get("routen") or []:
        if not _num(x.get("je_kap")) or (x.get("kapazitaet") or 0) < min_tc:
            continue
        if x.get("herkunft") == "bestellung" and _num(zu.get(x["id"])) and x["je_kap"] < zu[x["id"]]:
            best.append((x, zu[x["id"]]))
        elif x.get("herkunft") == "automatik" and _num(auto_min) and x["je_kap"] < auto_min:
            auto.append((x, auto_min))
    if not best and not auto:
        return []

    def txt(x, m):
        return (ue(t"{x.get('gut_name') or x.get('gut')} {x.get('von_name') or x.get('von')} → {x.get('nach_name') or x.get('nach')}: "
                t"{_de(x['je_kap'])} je Händlerkapazität (Mindest {_de(m)}), {_de(x.get('kapazitaet') or 0)} Kapazität"))
    tun = []
    if best:
        tun.append(ue("Routen einer Bestellung unter ihrem Mindestgewinn baut das Spiel nach und nach ab (Spieltext „Tendenz: "
                   "fallend“) – nichts tun oder die Ware aus der Bestellung nehmen"))
    if auto:
        tun.append(ue("für die Kapazität der Automatisierung eine Handelsbestellung im Gewinnschwerpunkt mit Mindestgewinn anlegen "
                   "(z. B. „Beliebige Ausfuhr“) – Bestellungen nutzen die Kapazität vor der Automatisierung"))
    return [_rec(
        "routen_unter_mindest", "niedrig", "Handel",
        ue(t"{len(best) + len(auto)} Route(n) unter dem Mindestgewinn je Händlerkapazität"),
        [(ue("Bestellung: ") + "; ".join(txt(x, m) for x, m in best) + ".") if best else None,
         (ue("Automatisierung: ") + "; ".join(txt(x, m) for x, m in auto) + ".") if auto else None,
         ue(t"Daten-Mod {hz.get('datum') or ''}; Mindestgewinn einer Bestellung laut Spiel: darunter keine neuen Routen (Standard "
         t"{_de(hz.get('mindestgewinn') or 0.25)}, Define DEFAULT_TRADE_ORDER_MIN_PROFIT).")],
        "; ".join(t[0].upper() + t[1:] for t in tun) + ".",
        "messen", ue("Was die Kapazität anderswo verdient, zeigt erst das Spiel – nach dem Umsetzen markieren."),
        "handel", ue("Routen unter Mindestgewinn umgelenkt"))]


def r_bestellung_zoll(ctx):
    """Vermeidbare Zölle auf den Routen einer Handelsbestellung ab 10 % ihres Gewinns vor Zoll (Schwelle wie die Regel „Zölle“).
    Die Zölle des Besitzers des Bestellungsmarkts – Ausfuhrzoll auf alles, was den Markt verlässt, Einfuhrzoll auf alles, was
    hineinkommt (game_concept_tariffs_desc) – zahlt jede Route der Bestellung; sie deckt die Regel „Zölle“ ab (Zollbefreiung) und
    zählen hier nicht. Zölle anderer Länder (Ausgangsmarkt einer Einfuhr, Zielmarkt einer Ausfuhr) lassen sich über die erlaubten
    Märkte meiden („Angepasste Auswahl“). Prüfer 29.10.: vorher doppelt mit „Zölle“ und falsch für den Einfuhrzoll des Besitzers.
    Wirkung berechnet: Zoll ist im Gewinn schon abgezogen (nachgerechnet 27.10.)."""
    hz = ctx.get("handel") or {}
    live = {x["id"]: x for x in hz.get("routen") or []}
    out = []
    for b in (hz.get("pruefung") or {}).get("bestellungen") or []:
        if not _num(b.get("zoll_anteil")) or b["zoll_anteil"] < ZOLL_SCHWELLE:
            continue
        markt = b.get("markt_name") or b.get("markt")
        besitzer = (hz.get("bestellmarkt_besitzer") or {}).get(str(b.get("markt")))
        routen = [live[r["id"]] for g in b.get("gueter") or [] for r in g.get("routen") or [] if r["id"] in live]
        eintr = [(e, x) for x in routen for e in x.get("texte") or []]
        fest = [e for e, x in eintr if besitzer and e["land"] == besitzer]
        anders = [(e, x) for e, x in eintr if e not in fest]
        if not anders:
            continue                                  # nur Zölle des Marktbesitzers: Regel „Zölle“ (Zollbefreiung)
        # Betrag des vermeidbaren Teils: ganze Route, wenn alle ihre Einträge vermeidbar sind (GetTariffValue genau), sonst die
        # Textwerte (2 Stellen, abgeschnitten)
        bez = 0.0
        for x in routen:
            ea = [e for e, xx in anders if xx is x]
            if ea:
                bez += -(x.get("zoll") or 0) if len(ea) == len(x.get("texte") or []) else sum(abs(e["wert"]) for e in ea)
        vor = -(b.get("zoll") or 0) / b["zoll_anteil"] if b.get("zoll_anteil") else None
        if not vor or bez / vor < ZOLL_SCHWELLE:
            continue
        ti = (hz.get("modifikatoren") or {}).get("trade_income")
        laender = sorted({e["land"] for e, _ in anders})
        out.append(_rec(
            f"bestellung_zoll:{b['id']}", "niedrig", "Handel",
            ue(t"Handelsbestellung {markt}: {_de(bez)} Gold Zoll je Monat an {', '.join(laender)} vermeidbar "
            t"({_pz(bez / vor, 0)} des Gewinns vor Zoll)"),
            ["; ".join(sorted({ue(t"{e['land']}: {_zollart(e['richtung'], 'zoll')} {_pz(e['satz'], 0)} auf "
                               t"{e['gut']}") for e, _ in anders})) + ue(t" (Spieltext je Route, Daten-Mod {hz.get('datum') or ''})."),
             ue("Einen Ausfuhrzoll erhebt der Besitzer des Ausgangsmarkts, einen Einfuhrzoll der des Zielmarkts (Spielbegriffe); diese "
             "Märkte sind nicht der Markt der Bestellung und lassen sich über die erlaubten Märkte meiden."),
             fest and ue(t"Die Zölle von {besitzer} als Besitzer von {markt} zahlt jede Route der Bestellung – dazu die Empfehlung „Zölle“.")],
            ue("In der Bestellung die erlaubten Märkte („Angepasste Auswahl“) auf Märkte ohne Zoll von ") + ", ".join(laender)
            + ue(" beschränken."),
            "berechnet", ue(t"Entfällt der Zoll, steigt der Gewinn dieser Routen um bis zu {_de(bez)} Gold je Monat")
            + (ue(t"; die Staatskasse erhält davon den Anteil Handelseinnahmen {_pz(ti)} = {_de(bez * ti)}.") if _num(ti) else ".")
            + ue(" Ob andere Märkte gleich viel bringen, zeigt erst das Spiel."),
            "handel", ue(t"Handelsbestellung {markt}: erlaubte Märkte geändert")))
    return out


def r_haendler_frei(ctx):
    """Ungenutzte Händlerkapazität in einem Markt (Spielstand: merchant capacity − used) ab 0,5 – so groß sind die kleinsten
    Routen, die die KI gern anlegt (Define NAI.AI_MINIMUM_TRADE_SIZE). Ungenutzte Kapazität bringt keinen Gewinn."""
    hz = ctx.get("handel") or {}
    df = hz.get("defines_handel") or {}
    grenze = df.get("AI_MINIMUM_TRADE_SIZE", 0.5)
    out = []
    for mid, k in ((hz.get("pruefung") or {}).get("kapazitaet") or {}).items():
        if not _num(k.get("frei")) or k["frei"] < grenze:
            continue
        out.append(_rec(
            f"haendler_frei:{mid}", "niedrig", "Handel",
            ue(t"{_de(k['frei'])} Händlerkapazität in {k['markt']} ungenutzt"),
            [ue(t"Kapazität {_de(k['kapazitaet'])}, genutzt {_de(k['genutzt'])} (Spielstand {ctx['last']['meta']['datum']})."),
             ue(t"Routen unter {_de(grenze)} Kapazität vermeidet die KI (Define AI_MINIMUM_TRADE_SIZE) – der freie Teil reicht für eine "
             t"Route; die Automatisierung hat offenbar keine gefunden, die sich lohnt.")],
            ue(t"Eine Handelsbestellung für {k['markt']} anlegen (z. B. „Beliebige Ausfuhr“ oder „Beliebige Einfuhr“ im "
            t"Gewinnschwerpunkt) – Vorschläge zum gewählten Schwerpunkt stehen in der Kachel Wirtschaftsplan."),
            "messen", ue("Ungenutzte Kapazität verdient nichts; was eine Route bringt, zeigt erst das Spiel – nach dem Umsetzen markieren."),
            "handel", ue(t"Händlerkapazität in {k['markt']} genutzt")))
    return out


def _vorschlag_text(e, markt, datum):
    """Ein Vorschlag als Satz mit Zahlen (handel.vorschlaege)."""
    zoll = (ue(t"Ausfuhrzoll {e['zoll_land_name']} {_de(e['zoll_satz'] * 100, 0)} %") if _num(e.get("zoll_satz")) and e["zoll_satz"] > 0
            else ue("ohne Ausfuhrzoll laut Spielstand"))
    fuer = ue(t" für {e['fuer_name']}") if e.get("fuer_name") else ""
    if e["richtung"] == "einfuhr":
        lage = (ue(t"in {markt} Nachfrage {_de(e['nachfrage_hier'])} > Angebot {_de(e['angebot_hier'])}; in {e['markt']} Angebot "
                t"{_de(e['angebot_dort'])}, Nachfrage {_de(e['nachfrage_dort'])}"))
    else:
        lage = (ue(t"in {markt} Überschuss {_de(e['angebot_hier'] - e['nachfrage_hier'])}; in {e['markt']} Nachfrage "
                t"{_de(e['nachfrage_dort'])}, Angebot {_de(e['angebot_dort'])}"))
    t = (ue(t"{e['gut_name']}{fuer}: hier {_de(e['preis_hier'])} Gold, in {e['markt']} {_de(e['preis_dort'])} – Vorteil "
         t"{_de(e['netto'])} je Einheit nach Zoll ({zoll}); {lage} (Spielstand {datum})."))
    b = e.get("bestellung") or {}
    if b.get("art") == "gleich":
        t += ue(t" Steht schon in Bestellung Nr. {b['id']}") + (ue(" (mit Route).") if b.get("route") else ue(" (ohne Route)."))
    elif b.get("art") == "gegen":
        aus = b.get("richtung") == "ausfuhr"
        t += (ue(t" Achtung: Bestellung Nr. {b['id']} führt {e['gut_name']} aus – für diesen Schwerpunkt wäre {_richtung(e['richtung'])} richtig.") if aus else
              ue(t" Achtung: Bestellung Nr. {b['id']} führt {e['gut_name']} ein – für diesen Schwerpunkt wäre {_richtung(e['richtung'])} richtig."))
    return t


def r_bestellung_fokus(ctx):
    """Vorschläge für Handelsbestellungen je Schwerpunkt des Wirtschaftsplans (handel.vorschlaege). Der Server kennt die Wahl
    des Schwerpunkts nicht (Browser, localStorage rg_wp_fokus): je Schwerpunkt eine Empfehlung mit Feld „fokus“, die Seite zeigt
    nur die des gewählten. Wirkung messen: den Gewinn je Händlerkapazität einer neuen Route zeigt erst das Spiel."""
    hz = ctx.get("handel") or {}
    V = hz.get("vorschlaege") or {}
    datum = ctx["last"]["meta"]["datum"]
    out = []
    for fk, F in (V.get("fokusse") or {}).items():
        neu = [e for e in F.get("eintraege") or [] if (e.get("bestellung") or {}).get("art") != "gleich"]
        if not neu and F.get("food_aktiv") and F.get("eintrag"):
            # Nahrungsschwerpunkt greift (Markt unter 60 % und verliert Nahrung), ohne einzelne lohnende Ware (Prüfer 29.10.)
            n = F.get("nahrung") or {}
            r = _rec(
                f"bestellung_fokus:{fk}", "mittel", "Handel",
                ue(t"Schwerpunkt {F['name']}: Einfuhrbestellung „{F['eintrag']['name']}“ im Nahrungsschwerpunkt ({V.get('markt')})"),
                [ue(t"{V.get('markt')}: Nahrungsbestand {_pz(n.get('bestand'), 0)}, {_de(n.get('bilanz'), 1)} Nahrung je Monat "
                 t"(Daten-Mod) – der Nahrungsschwerpunkt füllt Märkte unter {_pz(n.get('grenze'), 0)} "
                 t"Nahrungsbestand auf, die Nahrung verlieren (Spieltext TRADE_ORDER_MODE_FOOD_INFO).") if _num(n.get("bestand"))
                 and _num(n.get("bilanz")) else F["modus"]["text"]] + list(F.get("hinweise") or []),
                ue(t"Im Spiel für den Markt {V.get('markt')} eine Handelsbestellung mit dem Eintrag „{F['eintrag']['name']}“ im Modus "
                t"„{F['modus']['name']}“ anlegen. Einzelheiten: Kachel Wirtschaftsplan."),
                "messen", ue("Wie viel Nahrung die Bestellung bringt, zeigt erst das Spiel – nach dem Umsetzen markieren."),
                "wirtschaftsplan", ue(t"Handelsbestellung {F['name']}: {F['eintrag']['name']}"))
            r["fokus"], r["fokus_name"] = fk, F["name"]
            out.append(r)
            continue
        if not neu:
            continue
        markt = V.get("markt")
        gueter = ", ".join(e["gut_name"] for e in neu)
        eintrag = ue("Einfuhreintrag hinzufügen") if F["richtung"] == "einfuhr" else ue("Ausfuhreintrag hinzufügen")
        mg = (ue(t", „Min. Gewinn“ {_de(F['mindestgewinn'])} (Standard)") if _num(F.get("mindestgewinn"))
              else ue(" – ohne Mindestgewinn sind Verluste möglich (Spieltext zum Mindestgewinn)"))
        e0 = F.get("eintrag")
        r = _rec(
            f"bestellung_fokus:{fk}", "mittel", "Handel",
            ue(t"Schwerpunkt {F['name']}: {F['bestellart']} für {', '.join(e['gut_name'] for e in neu[:3])} ({markt})"),
            [_vorschlag_text(e, markt, datum) for e in neu[:3]] + list(F.get("hinweise") or []) + list((V.get("hinweise") or [])[:1]),
            ue(t"Im Spiel für den Markt {markt} eine angepasste Handelsbestellung („Benutzerdefiniert“) anlegen: „{eintrag}“ – "
            t"{gueter}; Modus „{F['modus']['name']}“{mg}.")
            + (ue(t" Statt einzelner Waren geht auch der Eintrag „{e0['name']}“.") if e0 else "") + ue(" Einzelheiten: Kachel Wirtschaftsplan."),
            "messen", ue("Den Vorteil je Einheit nach Zoll rechnet der Ratgeber (Preise laut Spielstand, Ausfuhrzoll = Satz × "
            "Einkaufswert); den Gewinn je Händlerkapazität zeigt erst das Spiel in der Bestellung – die Kapazität je Einheit hängt von "
            "Entfernung und Gut ab. Nach dem Umsetzen markieren."),
            "wirtschaftsplan", ue(t"Handelsbestellung {F['name']}: {gueter}"))
        r["fokus"], r["fokus_name"] = fk, F["name"]
        out.append(r)
    return out


def _forschung_kosten(e, je_monat):
    """Kostensatz eines Fortschritts (techbaum.vorschlaege): belegt gerechnet oder Hinweis aufs Spiel."""
    if _num(e.get("kosten")):
        t = ue(t"Kosten {_de(e['kosten'])} Forschungsfortschritt (Defines, am Spielwert geprüft)")
        return t + (ue(t", bei {_de(je_monat)} je Monat ≈ {_de(e['monate'], 1)} Monate (Ableitung des Ratgebers).")
                    if _num(e.get("monate")) else ".")
    return (ue("Kosten zeigt das Spiel im Forschungsfenster") + (ue(t" (Feld research_cost {_de(e['rc'])} laut Spieldatei, Wirkung "
                                                              t"nicht belegt)") if _num(e.get("rc")) else "") + ".")


def r_forschung_fokus(ctx):
    """Fortschritt passend zum Schwerpunkt des Wirtschaftsplans (Ansicht Fortschritte, techbaum.vorschlaege; Nutzerwunsch 30.10.).
    Wie r_bestellung_fokus je Schwerpunkt eine Empfehlung mit Feld „fokus“ – der Server kennt die Wahl nicht, die Seite zeigt nur
    die des gewählten. Vorrang hat der beste jetzt erforschbare Fortschritt außer der laufenden Forschung, sonst der Weg zum besten
    Ziel. Wirkung messen: die Werte stehen in der Spieldatei, was sie bringen, zeigt erst das Spiel."""
    T = ctx.get("techbaum") or {}
    lf = T.get("laufend") or {}
    je = lf.get("je_monat")
    datum = T.get("datum") or ctx["last"]["meta"]["datum"]
    out = []
    for fk, F in (T.get("fokusse") or {}).items():
        e = next((x for x in F.get("eintraege") or [] if not x.get("laeuft")), None)
        # Ziele mit gesperrtem Schritt (allow, z. B. Institution fehlt) nur, wenn es kein offenes gibt – dann mit der Sperre als
        # erstem Schritt und niedriger Priorität (Prüfer 30.10.: Walachei „Meritokratie → Abakus“ ohne die Institution)
        ziele = F.get("ziele") or []
        z = None if e else next((x for x in ziele if not any(w.get("gesperrt") for w in x["weg"])), None)
        zg = None if e or z else next(iter(ziele), None)
        if not e and not z and not zg:
            continue
        nach = ue(t" (nach der laufenden Forschung „{lf['name']}“)") if lf.get("name") else ""
        if e:
            titel = ue(t"Schwerpunkt {F['name']}: Fortschritt „{e['name']}“ erforschen")
            gruende = list(e["gruende"][:3]) + [_forschung_kosten(e, je)]
            weitere = [x["name"] for x in F.get("eintraege") or [] if x is not e and not x.get("laeuft")][:3]
            if weitere:
                gruende.append(ue("Weitere für diesen Schwerpunkt: ") + ", ".join(weitere) + ".")
            handlung = (ue(t"Im Forschungsfenster „{e['name']}“ als nächsten Fortschritt wählen{nach} – jetzt erforschbar laut Spielstand "
                        t"{datum}. Einzelheiten: Ansicht Fortschritte."))
            marker = ue(t"Forschung {e['name']}")
        else:
            z = z or zg
            schritte = " → ".join(w["name"] for w in z["weg"])
            titel = ue(t"Schwerpunkt {F['name']}: auf „{z['name']}“ hinarbeiten ({len(z['weg'])} Schritte)")
            gesperrt = [ue(t"„{w['name']}“ {w['gesperrt']}") for w in z["weg"] if w.get("gesperrt")]
            gruende = (list(z["gruende"][:3])
                       + [ue(t"Weg: {schritte}; ") + (ue(t"zusammen {_de(z['weg_kosten'])} Forschungsfortschritt (Defines, am Spielwert "
                                                  t"geprüft)") + (ue(t", ≈ {_de(z['weg_monate'], 1)} Monate (Ableitung)") if _num(z.get("weg_monate"))
                                                                else "") if _num(z.get("weg_kosten"))
                                                  else ue("Kosten zeigt das Spiel")) + "."] + gesperrt)
            laeuft = z["weg"][0]["key"] == lf.get("key")
            sperre = next((w for w in z["weg"] if w.get("gesperrt")), None)
            handlung = ((ue(t"Erst die Sperre von „{sperre['name']}“ aufheben ({sperre['gesperrt']}); danach im Forschungsfenster der "
                         t"Reihe nach erforschen: {schritte}") if sperre else
                         ue(t"Im Forschungsfenster der Reihe nach erforschen: {schritte}"))
                        + (ue(" – der erste Schritt läuft schon.") if laeuft else ".") + ue(" Einzelheiten: Ansicht Fortschritte."))
            marker = ue(t"Forschung {z['weg'][0]['name']}")
        r = _rec(f"forschung_fokus:{fk}", "niedrig" if zg and not e and z is zg else "mittel", "Forschung", titel, gruende,
                 handlung, "messen",
                 ue("Die Werte der Wirkungen stehen so in der Spieldatei (advances); was sie in Gold, Wachstum oder Truppen bringen, zeigt "
                 "erst das Spiel – nach dem Erforschen markieren."), "forschung", marker)
        r["fokus"], r["fokus_name"] = fk, F["name"]
        out.append(r)
    return out


def r_gruendung(ctx):
    """Kachel Ländergründung (30.10., gruendung.build): „Jetzt gründbar“, wenn Gebiet, Hauptstadt-Bedingung und alle Bedingungen
    (allow, potential) erfüllt sind; „fast gründbar“, wenn alle bekannten Bedingungen erfüllt sind und höchstens gruendung.FAST_ORTE
    Orte fehlen (Regel des Ratgebers). Der Weg im Spiel steht in der Lokalisierung: Fenster „<Adjektiv>e Inhalte“
    (TAB_TOOLTIP_CONTENT_TITLE), Reiter „Gründbare“ (game_concept_formables), Knopf „„<Name>“ gründen“ (FORM_COUNTRY), Hinweis
    „Gründbares Land“ (ALERT_POSSIBLE_FORMABLE_COUNTRIES_TITLE)."""
    G = ctx.get("gruendung") or {}
    weg = G.get("weg") or {}
    out = []
    for o in G.get("optionen") or []:
        g = o["gebiet"]
        gebiet = (ue(t"Gebiet: {g['unsere']} von {g['alle']} geforderten Orten ({_pz(g['anteil'], 0)}), gefordert "
                  t"{_pz(g['gefordert'], 0)} = {g['noetig']} Orte (Spieldatei formable_countries)."))
        wirkung = "; ".join(x["text"] for x in o.get("wirkung") or [] if x.get("ok") is not False) or ue("laut Spieldatei keine weitere Wirkung")
        if o.get("gruendbar"):
            out.append(_rec(
                f"gruendung:{o['key']}", "hoch", "Ländergründung", ue(t"Jetzt gründbar: {o['name']} (Grad {o.get('grad') or '?'})"),
                [gebiet, ue(t"Bedingungen: alle {o['bedingungen_alle']} erfüllt.") if o["bedingungen_alle"] else ue("Keine weiteren Bedingungen."),
                 ue(t"Wirkung (form_effect): {wirkung}.")],
                ue("Im Spiel ") + (ue(t"im Fenster „{weg['fenster']}“ ") if weg.get("fenster") else "")
                + ue(t"den Reiter „{weg.get('reiter') or ue('Gründbare')}“ (neben „Entscheidungen“) öffnen und „„{o['name']}“ gründen“ wählen – "
                t"auch über den Hinweis „{weg.get('hinweis') or ue('Gründbares Land')}“."),
                "Spielwert", ue(t"Laut Spieldatei: {wirkung}. Name, Flagge und Farbe des Landes wechseln (Europedia „Gründbares Land“)."),
                "gruendung", ue(t"Gegründet: {o['name']}")))
        elif o.get("fast"):
            mil = [m["text"] for m in (o.get("empfehlungen") or {}).get("militaer") or [] if not m.get("offen")][:2]
            out.append(_rec(
                f"gruendung_fast:{o['key']}", "mittel", "Ländergründung",
                ue(t"Fast gründbar: {o['name']} – es fehlen {g['fehlt']} Orte"),
                [gebiet, ue(t"Bedingungen: alle {o['bedingungen_alle']} erfüllt.") if o["bedingungen_alle"] else ue("Keine weiteren Bedingungen."),
                 ue(t"„Fast“ = höchstens {G.get('fast_orte')} fehlende Orte (Regel des Ratgebers).")],
                (" ".join(mil) + "." if mil else ue(t"{g['fehlt']} weitere geforderte Orte erwerben.")) + ue(" Einzelheiten: Kachel Ländergründung."),
                "messen", ue("Was der Erwerb kostet, hängt vom Weg ab (Krieg, Eingliederung) – nach dem Umsetzen markieren."),
                "gruendung", ue(t"Gebiet für {o['name']} erweitert")))
    return out


REGELN = (r_krieg, r_kriegsgelegenheit, r_krankheit, r_steuergrundlage, r_gebaeude_ohne_gewinn, r_preis_ueberangebot, r_staende, r_ausbau,
          r_zoelle, r_bestellung_ohne_route, r_bestellung_gewinn, r_routen_unter_mindest, r_bestellung_zoll, r_haendler_frei,
          r_bestellung_fokus, r_forschung_fokus, r_gruendung, r_ungenutzt)


def build(db, snaps, lv, names=None, wis=None, voll_estates=None, script_values=None, modtypen=None, bau=None, kw=None,
          kriege=None, nachbarn=None, handel=None, techbaum=None, gruendung=None, wp=None):
    """Alle Empfehlungen, sortiert nach Wichtigkeit. Fehler einer Regel stoppen die anderen nicht (Meldung in der Liste)."""
    if not snaps:
        return []
    last = snaps[-1]
    tag = last["meta"]["tag"]
    nm = names or (lambda k: k)
    sv = script_values or {}

    def script_value(v):
        if _num(v):
            return v
        d = sv.get(v) if isinstance(v, str) else None
        return d.get("def") if isinstance(d, dict) and _num(d.get("def")) else None

    land, _ = _neueste(db, tag, "a.land")
    ctx = {"db": db, "tag": tag, "snaps": snaps, "last": last, "lv": lv or [], "names": nm, "wis": wis or {},
           "voll_estates": voll_estates or {}, "script_value": script_value, "modtypen": modtypen or {},
           "bau": bau or [], "land": next(iter(land.values()), {}) if land else {},
           "geb_monate": _gebaeude_monate(db, tag), "geb_werte": _neueste(db, tag, "a.gebaeude")[0],
           "ort_werte": _neueste(db, tag, "a.ort")[0],
           # ab Mod 0.18: Krankheiten je Ort und im Land; krankheiten_wissen (Spieldateien) für Aktionen und Gebäude
           "seuche_orte": _neueste(db, tag, "a.seucheort")[0], "seuche_land": next(iter(_neueste(db, tag, "a.seucheland")[0].values()), {}),
           "kw": kw or {},
           # ab 25.10.: laufende Kriege (krieg.build) für die Kriegsregeln
           "kriege": kriege or [],
           # ab 25.10.: Kachel Nachbarn und Kriegsgelegenheiten (nachbarn.build) für die Regel Kriegsgelegenheit
           "nachbarn": nachbarn or {},
           # ab 27.10. (Patch 1.4): Zölle und Herkunft der Routen (handel.build) für die Regel Zölle; ab 29.10. auch Prüfung der
           # Handelsbestellungen und Vorschläge je Schwerpunkt (Regeln r_bestellung_*, r_routen_unter_mindest, r_haendler_frei)
           "handel": handel or {},
           # ab 30.10.: Fortschritte je Schwerpunkt (techbaum.fuer_series) für die Regel r_forschung_fokus
           "techbaum": techbaum or {},
           # ab 30.10.: Kachel Ländergründung (gruendung.build) für die Regel r_gruendung
           "gruendung": gruendung or {},
           # ab 05.11.: Schwerpunkte des Wirtschaftsplans (Abschnitt „Schwerpunkt“ oben)
           "fokus": {fk: (F, startstrategie.fokus_kontext(fk, wp, modtypen or {})) for fk, F in ((wp or {}).get("fokusse") or {}).items()}}
    out = []
    for regel in REGELN:
        try:
            out += regel(ctx)
        except Exception as e:                         # eine kaputte Regel soll die Kachel nicht leeren
            out.append(_rec(f"fehler:{regel.__name__}", "niedrig", "Ratgeber", ue(t"Regel {regel.__name__} fehlgeschlagen"),
                            [f"{type(e).__name__}: {e}"], "–", "messen", "–", "empfehlungen", ""))
    datum = (lv[-1]["datum"] if lv else last["meta"]["datum"])
    for r in out:
        r["datum"] = datum
        if r["bereich"] == "Handel" and not r.get("fokus"):
            for fk, p in HANDEL_PUNKTE.items():
                if fk in ctx["fokus"]:
                    r.setdefault("fokus_wert", {})[fk] = [p, ue("Handel gehört dazu")]
        # im Text der Name des Schwerpunkts (Nutzer 05.11.: „nicht die nummer sondern der name des schwerpunktes“)
        for fk, w in (r.get("fokus_wert") or {}).items():
            w[1] = f"{ctx['fokus'][fk][0]['name']} ({w[1]})"
    out.sort(key=lambda r: PRIO.get(r["prio"], 9))
    for fk in ctx["fokus"]:
        for i, r in enumerate(reihe(out, fk)):
            r.setdefault("rang", {})[fk] = i
    return out
