"""Armeebuilder (0.31 Teil 3, Nutzer 08.11.: „dazu noch ein armeebuilder, mit vorschlag zu armeegröße und zusammensetzung, äquivalent
für marine“): was wir haben, was das Spiel erwartet, was ein Krieg verlangt, und ein Vorschlag, womit die Lücke gefüllt wird.

Quellen (Spielwerte):
- Daten-Mod, neuester Monat (Landeswerte): Regimenter und Schiffe je Kategorie (sucount_<kategorie>), stehendes Heer
  (regular_army_size, Tsd. Mann), Obergrenze der Regulärtruppen (expected_army_size, Tsd. Mann – im Militärfenster „Regulärtruppen
  ausheben … / …“), Aufgebote (country_total_army_levy_size), Mannstärke, Seeleute, Schiffe und erwartete Marinegröße, Saldo.
- Spielwissen: Einheiten (unit_types: Kategorie, combat_power, max_strength × REGIMENT_SIZE = Mann je Regiment, maintenance_demand),
  Kategorien (unit_categories), Unterhaltsgüter (goods_demand), freigeschaltet über die erforschten Fortschritte (unlock_unit),
  defines: REGIMENT_SIZE, AVERAGE_FRONTAGE, AI_MINIMUM_AUXILIARY_RATIO, AI_HEAVY_SHIP_RATIO_FOR_TRANSPORTS.
- Spielstand: Preise im Heimatmarkt; Kriegsplan (kriegsplan.build) für den Bedarf eines Kriegs.

Regeln des Ratgebers (gekennzeichnet, weil das Spiel keine Zusammensetzung vorgibt – seine Formationsvorlieben gewichten alle Kategorien
gleich, unit_formation_preference):
- Größe: das stehende Heer bis zur Obergrenze des Spiels, höchstens so groß, wie die Mannstärke trägt: Zuwachs je Monat (yearly_manpower / 12)
  × AI_DESIRED_ARMY_MANPOWER_RECOVERY_MONTHS – so viel Zuwachs will die KI des Spiels, um ihr ganzes Heer neu aufzustellen. Fasst die
  Höchst-Mannstärke kein Kampfregiment, gibt es keinen Vorschlag. Der Krieg mit dem besten Ziel nennt zusätzlich die fehlende Militärstärke.
- Zusammensetzung: Tross mindestens AI_MINIMUM_AUXILIARY_RATIO (so viel hält die KI des Spiels immer), Kavallerie höchstens ein Drittel der
  Kampfregimenter (Flanken), der Rest Infanterie; je Kategorie die Einheit mit der höchsten Kampfkraft je Gold Unterhalt.
- Gold je Monat = Unterhaltsgüter je Regiment × Preis im Heimatmarkt – eine Schätzung ohne Regler und Modifikatoren.
- Krieg: nur Länder in Reichweite (kriegsplan.REICHWEITE); ist keins erreichbar, nennt die Kachel das nächste als „außer Reichweite“.

Mannstärke (Test 08.11.: Walachei seit 1337 Mannstärke 0, darum ließ sich kein Vorschlag ausheben): laut Spiel kommt sie aus
Mannstärke-Gebäuden oder bestimmten Fortschritten (game_concept_manpower_desc). mannstaerke_quellen nennt die Gebäude mit Monatlicher
Mannstärke (local_manpower in modifier oder capital_modifier), deren country_potential für uns zutrifft und die frei sind (kein Fortschritt
schaltet sie frei – wie die Serjeantry – oder ein erforschter) oder durch einen für uns sichtbaren Fortschritt frei würden. Beleg aus der
Datenbank: Holland hatte bis 1344 Mannstärke 0, nach der Serjeantry in Den Haag stieg die Obergrenze bis 1350 auf 0,72 Tsd.
Der Wert der Spieldatei gilt bei voller Belegschaft; ein neues Gebäude füllt sich nach und nach mit Arbeitern (pop_type soldiers), die
Mannstärke wächst mit (Nutzer 08.11., Walachei 1358.1–3 nachgerechnet) – darum nennen Kachel und Empfehlung den besetzten Anteil.
"""
import math

from . import besonderheiten, sprache, techbaum, wirtschaftsplan as W
from .sprache import ue

KAV_ANTEIL = 1 / 3          # Regel des Ratgebers: Kavallerie höchstens ein Drittel der Kampfregimenter
INFANTERIE = ("army_heavy_infantry", "army_light_infantry")
KAVALLERIE = ("army_heavy_cavalry", "army_light_cavalry")
HEER = (*INFANTERIE, *KAVALLERIE, "army_artillery", "army_auxiliary")
MARINE = ("navy_heavy_ship", "navy_light_ship", "navy_galley", "navy_transport")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def define(defines, name, vorgabe):
    """Wert eines defines aus irgendeiner Gruppe (NMilitary, NAI …) des Spielwissens."""
    for g in (defines or {}).values():
        v = ((g or {}).get("def") or {}).get(name) if isinstance(g, dict) else None
        if _num(v):
            return v
    return vorgabe


def einheiten(last, vg, names=None, defines=None):
    """Freigeschaltete Einheiten mit Kampfkraft, Mann je Regiment, Unterhaltsgütern und Gold je Monat (Schätzung)."""
    nm = names or (lambda k: k)
    ut, uc, gd = vg("unit_types") or {}, vg("unit_categories") or {}, vg("goods_demand") or {}
    groesse = define(defines, "REGIMENT_SIZE", 1000)
    gueter = {g["gut"]: g for g in (last.get("markt") or {}).get("gueter") or [] if g.get("gut")}
    out = []
    for k in sorted(W._freigeschaltet(vg, last, "unlock_unit")):
        kat = W._einheit(ut, k, "category")
        if kat not in HEER + MARINE:
            continue
        kd = (uc.get(kat) or {}).get("def") or {}
        unterhalt = W._einheit(ut, k, "maintenance_demand") or kd.get("maintenance_demand")
        mengen = W._mengen(gd, unterhalt) if unterhalt else {}
        preise = {g: (gueter.get(g) or {}).get("preis") for g in mengen}
        gold = sum(m * preise[g] for g, m in mengen.items()) if mengen and all(_num(p) for p in preise.values()) else None
        cp, st = W._einheit(ut, k, "combat_power"), W._einheit(ut, k, "max_strength")
        out.append({"key": k, "name": (ut.get(k) or {}).get("name") or nm(k), "kategorie": kat,
                    "kategorie_name": (uc.get(kat) or {}).get("name") or nm(kat), "heer": kat in HEER,
                    "kampfkraft": cp if _num(cp) else None, "mann": st * groesse if _num(st) and st > 0 else None,
                    "gueter": {((gueter.get(g) or {}).get("name") or nm(g)): m for g, m in mengen.items()}, "gold": gold,
                    "je_gold": cp / gold if _num(cp) and _num(gold) and gold > 0 else None})
    return out


def _beste(E, kategorien):
    """Einheit mit der höchsten Kampfkraft je Gold unter den Kategorien; ohne Preis die mit der höchsten Kampfkraft."""
    k = [e for e in E if e["kategorie"] in kategorien]
    return max(k, key=lambda e: (e["je_gold"] or 0, e["kampfkraft"] or 0), default=None)


def mischung(mann, inf, kav, tross, tross_anteil, aufrunden=True):
    """Regimenter für etwa `mann` Mann nach der Regel oben -> [(Einheit, Anzahl)]. aufrunden: mindestens so viele Mann (Krieg);
    sonst höchstens so viele (Obergrenze des Spiels – Test 08.11.: 1.700 Mann bei einer Grenze von 1.234)."""
    if not mann or mann <= 0 or not inf or not inf.get("mann"):
        return []
    a = tross_anteil if tross and tross.get("mann") else 0
    k = KAV_ANTEIL if kav and kav.get("mann") else 0
    je = a * ((tross or {}).get("mann") or 0) + (1 - a) * ((1 - k) * inf["mann"] + k * ((kav or {}).get("mann") or 0))
    n = max(1, math.ceil(mann / je) if aufrunden else math.floor(mann / je))
    n_t = round(a * n) if a else 0
    n_k = round(k * (n - n_t)) if k else 0
    n_i = n - n_t - n_k
    summe = lambda: n_i * inf["mann"] + n_k * ((kav or {}).get("mann") or 0) + n_t * ((tross or {}).get("mann") or 0)   # noqa: E731
    # Runden je Kategorie kann über die Grenze bzw. unter den Bedarf führen (Test 08.11.: 5.100 Mann bei 5.000) – mit Infanterie ausgleichen
    while not aufrunden and summe() > mann and n_i > 1:
        n_i -= 1
    while aufrunden and summe() < mann:
        n_i += 1
    if not aufrunden and summe() > mann:
        # nicht einmal die Mischung passt (Test 08.11.: Mannstärke trägt 72 Mann) – ein Regiment Infanterie, wenn es passt, sonst nichts
        return [(inf, 1)] if inf["mann"] <= mann else []
    out = [(inf, n_i), (kav, n_k), (tross, n_t)]
    return [(e, x) for e, x in out if e and x > 0]


def _alle(d, feld):
    """Alle Werte eines Felds in einem Block, auch verschachtelt."""
    out = []
    if isinstance(d, dict):
        for k, v in d.items():
            if k == feld:
                out += [x for x in (v if isinstance(v, list) else [v]) if isinstance(x, str)]
            else:
                out += _alle(v, feld)
    elif isinstance(d, list):
        for v in d:
            out += _alle(v, feld)
    return out


def _hat(b, key):
    """Kommt der Schlüssel im Block vor (auch verschachtelt)?"""
    if isinstance(b, dict):
        return any(k == key or _hat(v, key) for k, v in b.items())
    if isinstance(b, list):
        return any(_hat(v, key) for v in b)
    return False


def _zeitalter_nr(z):
    """age_2_renaissance -> 2; sonst None."""
    t = str(z or "").split("_")
    return int(t[1]) if len(t) > 2 and t[1].isdigit() else None


class _QuellenBedingung(besonderheiten.Bedingung):
    """Für die Quellen-Suche gilt has_advance als erfüllbar – der Fortschritt steht dann als Weg in „durch“ (Prüfer 08.11.)."""

    def knoten(self, k, x, scope):
        if k.rstrip("?=") == "has_advance" and isinstance(x, str):
            return [ue(t"Fortschritt {self.name('advances', x)}"), True, []]
        return super().knoten(k, x, scope)


def _plaetze(d, sv, stufe):
    """Arbeitsplätze eines Gebäudes: employment_size (Zahl oder Skriptwert wie manpower_employment = 1,0) × Stufe."""
    g = d.get("employment_size")
    if isinstance(g, str):
        g = (sv.get(g) or {}).get("def") if isinstance(sv.get(g), dict) else None
    return g * max(stufe or 1, 1) if _num(g) and g > 0 else None


def mannstaerke_quellen(last, vg, names=None, dlcs=None, belegung=None):
    """Mannstärke-Gebäude, die für uns infrage kommen (Regel oben): [{key, name, wert, wert_text, hauptstadt, frei, durch, gebaut, belegt,
    ort, ort_key, ort_id}] – frei zuerst, dann nach Zeitalter und Wert. durch = [{key, name, erforscht, zeitalter}]: für uns sichtbare
    Fortschritte, die es freischalten. ort: bei Gebäuden nur für die Hauptstadt (counts_as_capital / is_capital) unsere Hauptstadt.
    wert: Monatliche Mannstärke laut Spieldatei bei voller Belegschaft – sie wächst mit den Arbeitern (Nutzer 08.11.: „die sergentry tickt
    hoch, je mehr arbeiter desto höher max 15 ist der wert“; Walachei 1358.1–3: Belegschaft 11,3 / 12,6 / 13,9 %, Zuwachs 1,50 / 1,67 /
    1,83 Mann je Monat – im selben Verhältnis); je Stufe (building_types/readme.txt: modifier „multiplied by building level“).
    belegt: Anteil besetzter Arbeitsplätze aller gebauten Gebäude dieser Art, nach Arbeitsplätzen gewichtet – belegung {Gebäude-ID:
    Anteil} aus dem Daten-Mod (CalcEmploymentPercent), sonst Beschäftigte laut Spielstand / Arbeitsplätze. stufen: Summe der Stufen der
    gebauten; wert_voll(_text): wert × stufen = Monatliche Mannstärke aller gebauten bei voller Belegschaft."""
    nm = names or (lambda k: k)
    bt, adv = vg("building_types") or {}, vg("advances") or {}
    if not bt or not last:
        return []
    F = techbaum.fakten(last, vg, None, techbaum.installierte_dlcs() if dlcs is None else dlcs)
    B = _QuellenBedingung(F, vg, nm)
    mt = vg("_modifikator_typen") or {}
    sv = vg("script_values") or {}
    erforscht = set(F.get("erforscht") or [])
    durch = {}
    for a, e in adv.items():
        for b in _alle(e.get("def") if isinstance(e, dict) else None, "unlock_building"):
            durch.setdefault(b, []).append(a)
    gebaut, besetzt, stufen = {}, {}, {}
    for g in last.get("gebaeude") or []:
        typ = g.get("typ")
        gebaut[typ] = gebaut.get(typ, 0) + 1                                # auch im Bau (Stufe noch leer)
        st = g.get("stufe")
        stufen[typ] = stufen.get(typ, 0) + (st if _num(st) and st > 0 else 0)
        pl = _plaetze(((bt.get(typ) or {}).get("def") or {}) if isinstance(bt.get(typ), dict) else {}, sv, st)
        a = (belegung or {}).get(str(g.get("id")))
        if not _num(a):
            a = g["beschaeftigt"] / pl if _num(g.get("beschaeftigt")) and pl else None
        if _num(a):
            b = besetzt.setdefault(typ, [0.0, 0.0])       # besetzte Plätze, Plätze (Prüfer 08.11.: Stufe 3 voll + Stufe 1 leer = 75 %)
            b[0] += min(max(a, 0.0), 1.0) * (pl or 1.0)
            b[1] += pl or 1.0
    hs = next((o for o in last.get("orte") or [] if o.get("hauptstadt")), None) or {}
    out = []
    for k, e in bt.items():
        d = e.get("def") if isinstance(e, dict) else None
        if not isinstance(d, dict):
            continue
        wert = next((m.get("local_manpower") for m in (d.get("modifier"), d.get("capital_modifier"))
                     if isinstance(m, dict) and _num(m.get("local_manpower"))), None)
        if not _num(wert) or wert <= 0 or (d.get("country_potential") and B.pruefe(d["country_potential"]) is not True):
            continue
        # Fortschritte, die es freischalten: unlock_building oder has_advance im country_potential (kurultai)
        alle = durch.get(k, []) + [x for x in (techbaum._ohne(a) for a in _alle(d.get("country_potential"), "has_advance")) if x in adv]
        wege = [a for a in dict.fromkeys(alle) if not ((adv[a].get("def") or {}).get("potential"))
                or B.pruefe(adv[a]["def"]["potential"]) is True]
        if alle and not wege:
            continue                                                         # nur über Fortschritte anderer Länder
        nur_hs = _hat(d.get("location_potential"), "counts_as_capital") or _hat(d.get("allow"), "is_capital")
        out.append({"key": k, "name": e.get("name") or nm(k), "wert": wert,
                    "wert_text": techbaum.wert("local_manpower", wert, mt, {})[0],
                    "hauptstadt": nur_hs, "frei": not alle or any(a in erforscht for a in wege), "gebaut": gebaut.get(k, 0),
                    "belegt": besetzt[k][0] / besetzt[k][1] if besetzt.get(k) and besetzt[k][1] > 0 else None,
                    "stufen": stufen.get(k, 0), "wert_voll": wert * stufen[k] if stufen.get(k) else None,
                    "wert_voll_text": techbaum.wert("local_manpower", wert * stufen[k], mt, {})[0] if stufen.get(k) else None,
                    "durch": [{"key": a, "name": adv[a].get("name") or nm(a), "erforscht": a in erforscht,
                               "zeitalter": (adv[a].get("def") or {}).get("age")} for a in wege],
                    "ort": hs.get("name") if nur_hs else None, "ort_key": hs.get("key") if nur_hs else None,
                    "ort_id": hs.get("id") if nur_hs else None})
    out.sort(key=lambda x: (not x["frei"], _frueheste(x), -x["wert"], x["name"]))
    return out


def _frueheste(q):
    """Frühestes Zeitalter der freischaltenden Fortschritte; frei ohne Fortschritt 0."""
    z = [n for n in (_zeitalter_nr(a.get("zeitalter")) for a in q["durch"]) if n is not None]
    return min(z) if z else 0


def naechste_quelle(quellen, zeitalter=None):
    """Was als Nächstes Mannstärke bringt: ein freies, noch nicht gebautes Gebäude (Hauptstadt-Gebäude gibt es einmal je Land), sonst der
    Fortschritt zum nächsten Gebäude des jetzigen oder eines früheren Zeitalters -> („bauen“ | „forschen“, Quelle) oder None."""
    for q in quellen:
        if q["frei"] and not q["gebaut"]:
            return "bauen", q
    jetzt = _zeitalter_nr(zeitalter)
    for q in quellen:
        if not q["frei"] and (jetzt is None or _frueheste(q) <= jetzt):
            return "forschen", q
    return None


def kein_regiment_text(mpx, kleinstes):
    """Grund, wenn die Höchst-Mannstärke kein Kampfregiment fasst (Kachel und Empfehlung)."""
    zahl, mann = sprache.zahl(mpx, 3), sprache.zahl(kleinstes, 0)
    return ue(t"Höchst-Mannstärke {zahl} Tsd. – weniger als ein Kampfregiment ({mann} Mann): so lässt sich kein Regulärregiment ausheben.")


VOLL_BELEGT = 0.99    # ab diesem Anteil besetzter Arbeitsplätze gilt ein Gebäude als voll (wie die Ausbau-Empfehlung, empfehlungen.py)


def prozent(x):
    """Anteil als ganze Prozent, gerundet wie die Seite (fmt(x * 100, 0) in web/armee.js und ingame_kacheln)."""
    return sprache.zahl(x * 100, 0)


def fuellt_sich(quellen):
    """Gebaute Mannstärke-Gebäude, die noch nicht voll besetzt sind -> [Text] (Kachel und Empfehlung). Obergrenze: alle gebauten Stufen."""
    return [ue(t"{q['name']} erst zu {prozent(q['belegt'])} % besetzt: die Mannstärke wächst mit den Arbeitern bis "
               t"{q.get('wert_voll_text') or q['wert_text']} je Monat (laut Spieldatei bei voller Belegschaft).")
            for q in quellen if q.get("gebaut") and _num(q.get("belegt")) and q["belegt"] < VOLL_BELEGT]


def build(last, land, vg, names=None, defines=None, kp=None, belegung=None):
    """Heer und Marine: Stand, Obergrenze laut Spiel, Krieg, Vorschlag, Grenzen. land: Landeswerte des Daten-Mods (neuester Monat);
    belegung: {Gebäude-ID: Anteil besetzter Arbeitsplätze} des Daten-Mods (mannstaerke_quellen)."""
    if not last or not land:
        return {}
    E = einheiten(last, vg, names, defines)
    groesse = define(defines, "REGIMENT_SIZE", 1000)
    tross_anteil = define(defines, "AI_MINIMUM_AUXILIARY_RATIO", 0.15)
    tsd = lambda k: land[k] * groesse if _num(land.get(k)) else None   # noqa: E731
    jetzt, grenze = tsd("regular_army_size"), tsd("expected_army_size")
    inf, kav, tross = _beste(E, INFANTERIE), _beste(E, KAVALLERIE), _beste(E, ("army_auxiliary",))
    luecke = max(0.0, grenze - (jetzt or 0)) if _num(grenze) else None
    # Größe nach der Mannstärke (Test 08.11. nach der Serjeantry: Höchst-Mannstärke 0,091 Tsd., Zuwachs 18 Mann im Jahr – der Vorschlag
    # nannte trotzdem 1.200 Mann): die KI des Spiels will so viel Zuwachs, dass sie ihr ganzes Heer in AI_DESIRED_ARMY_MANPOWER_RECOVERY_MONTHS
    # Monaten neu aufstellen kann – der Vorschlag bleibt darunter. Ausheben kostet Mannstärke (das Spiel zeigt nur Einheiten, für die sie
    # reicht); fasst die Höchst-Mannstärke kein Kampfregiment, lässt sich keins ausheben.
    mp, mpx = land.get("manpower"), land.get("max_manpower")
    zuwachs = land["yearly_manpower"] / 12 if _num(land.get("yearly_manpower")) else land.get("monthly_manpower")
    monate = define(defines, "AI_DESIRED_ARMY_MANPOWER_RECOVERY_MONTHS", 48)
    traegt = zuwachs * monate * groesse if _num(zuwachs) else None
    gedeckelt = _num(traegt) and _num(grenze) and traegt < grenze
    ziel = traegt if gedeckelt else grenze
    kampf = [e["mann"] for e in (inf, kav) if e and _num(e.get("mann"))]
    kleinstes = min(kampf) if kampf else None
    kein_regiment = _num(mpx) and (mpx <= 0 or (kleinstes is not None and mpx * groesse < kleinstes))
    rest = ziel - (jetzt or 0) if _num(ziel) else None
    vorschlag = [] if kein_regiment else mischung(max(0.0, rest) if _num(rest) else None, inf, kav, tross, tross_anteil, aufrunden=False)
    # warum leer (Kopfwert): fasst kein Regiment / trägt mehr als das Heer, aber kein Regiment Infanterie – die kleinste Einheit des
    # Vorschlags (Prüfer 08.11.: sonst „ausgeschöpft“ ohne Heer) / Heer schon so groß, wie die Mannstärke trägt / Obergrenze
    leer = (None if vorschlag else "mannstaerke" if kein_regiment else "zu_wenig" if gedeckelt and inf and _num(rest) and rest > 0
            else "traegt" if gedeckelt else "obergrenze")
    # Krieg: das erste Ziel des Kriegsplans in Reichweite, dem Stärke fehlt (mit Verbündeten geschätzt, sonst gegen das Land allein);
    # ist keins erreichbar, das erste außer Reichweite nur zur Anzeige (Test 08.11.: Ungarn +82.828 Mann bei 2,8 Tsd. eigener Stärke)
    krieg, ausser, erreichbar = None, None, False
    for x in (kp or {}).get("laender") or []:
        s = x.get("staerke") or {}
        f = s.get("fehlt_buendnis") if _num(s.get("fehlt_buendnis")) and s["fehlt_buendnis"] > 0 else s.get("fehlt")
        if x.get("stufe") not in ("jetzt", "bald", "schaffen"):
            continue
        # ein erreichbares Ziel ohne fehlende Stärke: „kein Ziel mit fehlender Stärke“, nicht „außer Reichweite“ (Prüfer 08.11.)
        erreichbar = erreichbar or x.get("erreichbar") is not False
        if not _num(f) or f <= 0:
            continue
        if x.get("erreichbar") is False:
            ausser = ausser or {"tag": x["tag"], "name": x["name"], "fehlt_mann": f * groesse, "verhaeltnis": s.get("buendnis"),
                                "mit_verbuendeten": f == s.get("fehlt_buendnis")}
            continue
        krieg = {"tag": x["tag"], "name": x["name"], "fehlt_mann": f * groesse, "mit_verbuendeten": f == s.get("fehlt_buendnis"),
                 "mischung": [{"einheit": e["name"], "anzahl": n} for e, n in mischung(f * groesse, inf, kav, tross, tross_anteil)]}
        break
    gold = sum((e["gold"] or 0) * n for e, n in vorschlag) if vorschlag and all(_num(e["gold"]) for e, _ in vorschlag) else None
    qu = mannstaerke_quellen(last, vg, names, belegung=belegung)
    # knapp: warum sich gar kein Regulärregiment aufstellen lässt – Grenze in der Kachel, Anlass und erster Grund der Empfehlung
    # „Mannstärke schaffen“ (empfehlungen.r_armee)
    grenzen, knapp, getragen = [], None, None
    if gedeckelt and not kein_regiment:
        zahl, je = sprache.zahl(traegt, 0), sprache.zahl(zuwachs * groesse, 1)
        # Spielwert (Prüfer 08.11.): die KI richtet ihren Zuwachs nach dem Heer, nicht das Heer nach dem Zuwachs
        getragen = ue(t"Die Mannstärke trägt etwa {zahl} Mann (Zuwachs {je} Mann je Monat × {monate:.0f} Monate): so viel Zuwachs will die "
                      t"KI des Spiels, um ihr ganzes Heer in dieser Zeit neu aufstellen zu können.")
        if vorschlag:
            getragen += ue(" Der Vorschlag bleibt darunter.")
        elif leer == "zu_wenig":
            mann = sprache.zahl(inf["mann"], 0)
            getragen += (ue(t" Für ein weiteres Regiment {inf['name']} ({mann} Mann) reicht das nicht.") if jetzt
                         else ue(t" Für ein Regiment {inf['name']} ({mann} Mann) reicht das nicht."))
        else:
            getragen += ue(" Das stehende Heer ist schon so groß.")
    if _num(mpx) and mpx <= 0:
        knapp = ue("Mannstärke 0 (Spielwert): ohne Mannstärke lassen sich keine Regulärtruppen ausheben – im Krieg nur Aufgebote.")
    elif kein_regiment:
        knapp = kein_regiment_text(mpx, kleinstes)
    elif leer == "zu_wenig" and not jetzt:
        knapp = getragen
    if knapp:
        grenzen.append(knapp)
    elif vorschlag and _num(mp) and mp * groesse < sum((e["mann"] or 0) * n for e, n in vorschlag):
        zahl = sprache.zahl(mp, 2)
        grenzen.append(ue(t"Mannstärke {zahl} Tsd. reicht nicht für den ganzen Vorschlag – nach und nach ausheben."))
    if getragen and getragen != knapp:
        grenzen.append(getragen)
    if knapp or gedeckelt:
        grenzen += fuellt_sich(qu)                     # Nutzer 08.11.: die Serjeantry tickt mit den Arbeitern hoch
    saldo = land.get("monthly_balance")
    if _num(gold) and _num(saldo) and gold > saldo:
        grenzen.append(ue("Der Unterhalt des Vorschlags ist höher als der Saldo je Monat."))
    heer = {"regimenter": {k: land.get(f"sucount_{k}") for k in HEER if _num(land.get(f"sucount_{k}"))},
            "jetzt": jetzt, "grenze": grenze, "luecke": luecke, "aufgebote": tsd("country_total_army_levy_size"),
            "militaerstaerke": land.get("military_strength"), "mannstaerke": mp, "max_mannstaerke": mpx,
            "vorschlag": [{"key": e["key"], "einheit": e["name"], "kategorie": e["kategorie_name"], "anzahl": n,
                           "mann": (e["mann"] or 0) * n, "gold": (e["gold"] * n) if _num(e["gold"]) else None} for e, n in vorschlag],
            "zuwachs": zuwachs, "traegt": traegt, "erholung_monate": monate, "kleinstes_regiment": kleinstes,
            "kein_regiment": bool(kein_regiment), "knapp": knapp,
            # warum der Vorschlag leer ist (Kopfwert in Seitenleiste und Seite): mannstaerke | zu_wenig | traegt | obergrenze
            "vorschlag_leer": leer,
            "gold": gold, "saldo": saldo, "krieg": krieg, "ausser_reichweite": None if krieg or erreichbar else ausser, "grenzen": grenzen,
            "quellen": qu,
            "naechste_quelle": naechste_quelle(qu, (last.get("meta") or {}).get("zeitalter"))}
    schiffe, erwartet = land.get("navy_size"), land.get("expected_navy_size")
    marine = {"schiffe": {k: land.get(f"sucount_{k}") for k in MARINE if _num(land.get(f"sucount_{k}"))},
              "jetzt": schiffe, "erwartet": erwartet, "seeleute": land.get("sailors"), "max_seeleute": land.get("max_sailors"),
              "luecke": max(0, round(erwartet - (schiffe or 0))) if _num(erwartet) else None,
              "schutz_anteil": define(defines, "AI_HEAVY_SHIP_RATIO_FOR_TRANSPORTS", 0.25)}
    return {"heer": heer, "marine": marine, "einheiten": E, "tross_anteil": tross_anteil, "kav_anteil": KAV_ANTEIL,
            "frontbreite": define(defines, "AVERAGE_FRONTAGE", 12), "regiment": groesse}
