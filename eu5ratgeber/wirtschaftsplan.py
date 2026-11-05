"""Kachel Wirtschaftsplan (Nutzerwunsch 25.10.): welche Güter und Produktionsketten ein Land aufbauen sollte, mit wählbarem
Schwerpunkt. Stufen 1–3 (die Reihenfolge als Plan – Stufe 4 – folgt später):

1 Bedarf     Güter des Heimatmarkts, gewichtet nach dem Schwerpunkt (Spieldateien bzw. Markt) und gereiht nach Knappheit
             (Preis ÷ Grundpreis, Spielstand). Ohne Preis = im Markt nicht vorhanden (eigene Gruppe).
2 Ketten     je Gut die Gebäudearten mit ihren Produktionsmethoden und Eingangsgütern (Spieldateien), je Eingangsgut die
             Verfügbarkeit (eigene Rohstoffe, eigene Gebäude mit laufender Methode und Belegschaft, Markt, billigster Markt in
             Reichweite); je Gebäudeart die Lage für uns (history.gebaeude_status), passende eigene Orte (Ortsart), Bedingungen,
             Pop-Typ, Baugüter.
3 Lohnt es   Gewinn je Stufe derselben Gebäudeart laut Spielstand (last_months_profit aller Gebäude – fehlt das Feld, ist der
             Gewinn 0: Heimatmarkt, sonst Märkte in Reichweite, sonst Welt) und für eigene ausbaufähige Gebäude die Werte des
             Mods (Gewinn und Steuergrundlage je Stufe). Gold-Baukosten neuer Gebäude sind nicht berechenbar: das Spiel zeigt
             sie nur im Baumenü, und der Rohstoff-Ausbau Den Haag (168 Gold) ließ sich aus prices/goods_demand nicht nachrechnen.

Prüfung 25.10. (ein Prüfer, Befunde eingearbeitet): Einheiten über die Freischaltungen der erforschten Fortschritte statt nach
Zeitalter; Gewinn, Baugüter und Veredelung nur aus Gebäuden, die wir bauen können; fehlender Gewinn = 0; Mindestanteil für die
Gruppe „knapp“; Gebäude mit Wirkung auch über capital_modifier und freischaltbare Sondergebäude (Polder); „bei uns“ nach der
laufenden Produktionsmethode und Belegschaft.
"""
import collections

from . import bauplan

ORTSARTEN = ("rural_settlement", "town", "city", "megalopolis")
# Schwerpunkte: Name, Erklärung (Seite), Reihung (knapp = Anteil × Preis/Grundpreis, wert = nur Anteil), Modifikatoren der
# Gebäude mit Wirkung (building_types modifier / capital_modifier)
FOKUS = {
    "grundwirtschaft": ("Grundwirtschaft aufbauen", "Güter nach ihrem Marktwert im Heimatmarkt (Preis × Nachfrage), gereiht nach "
                        "Knappheit.", "knapp", ()),
    "gewinn": ("Gewinn und Steuergrundlage", "Güter, deren für uns baubare Gebäude (bei uns vorhanden oder freigeschaltet) am meisten "
               "verdienen – Gewinn je Stufe laut Spielstand, Quelle je Zeile; Gewinn wird Reichtum und damit Steuergrundlage.",
               "wert", ()),
    "bevoelkerung": ("Bevölkerungswachstum", "Nahrungsgüter nach ihrem Nahrungswert (Spieldatei goods: food), gereiht nach "
                     "Knappheit; dazu Gebäude mit Wirkung auf Wachstum, Bevölkerungsgrenze, Nahrung und Zuzug.", "knapp",
                     ("local_population_growth", "local_clergy_pop_growth", "local_population_capacity",
                      "local_population_capacity_modifier", "local_monthly_food", "local_monthly_food_modifier",
                      "local_food_capacity", "local_migration_attraction")),
    "landheer": ("Landarmee-Güter", "Güter für Aufstellung und Unterhalt der Regimenter, die das Land freigeschaltet hat "
                 "(unlock_unit der erforschten Fortschritte; goods_demand regiment_construction/regiment_maintenance), gereiht nach "
                 "Knappheit; dazu Gebäude mit Wirkung auf Rekrutierung und Mannstärke.", "knapp",
                 ("local_manpower", "can_recruit_regiment_in_this_location", "max_regiments_trained_at_same_time",
                  "local_levy_size_modifier", "manpower_to_building_owner")),
    "marine": ("Marine-Güter", "Güter für Bau und Unterhalt der Schiffe, die das Land freigeschaltet hat (unlock_unit der erforschten "
               "Fortschritte; goods_demand ship_construction/ship_maintenance), gereiht nach Knappheit; dazu Gebäude mit Wirkung "
               "auf Werften und Seeleute.", "knapp",
               ("local_sailors", "can_build_ships_in_this_location", "max_ships_built_at_same_time", "local_ship_build_speed",
                "local_navy_levy_size_modifier", "sailors_to_building_owner")),
    "expansion": ("Erkunden und Kolonisieren", "Güter für Kolonien, Kolonie-Charter, Erkundung zu Land und See und Konquistadoren "
                  "(goods_demand colony_construction, simple_colony_construction, colonial_charter_maintenance, "
                  "create_land/sea_exploration, create_conquistador), gereiht nach Knappheit.", "knapp", ()),
    "export": ("Exportwirtschaft aufbauen", "Güter, die in Märkten in Reichweite teurer sind als bei uns: Preisvorteil × Nachfrage "
               "dort (Spielstand) – ohne Transportkosten und Zölle.", "wert", ()),
    "import": ("Importwirtschaft (Veredelung)", "Güter, die wir herstellen können und deren Eingangsgüter in Märkten in Reichweite "
               "billiger sind als bei uns: Einkaufsvorteil je Einheit der günstigsten Produktionsmethode einer für uns baubaren "
               "Gebäudeart (Spielstand, Spieldateien) – ohne Transportkosten und Zölle; nur Güter mit Preis im Heimatmarkt.",
               "wert", ()),
    "bau": ("Baugüter", "Güter für den Bau der Gebäudearten, die wir bauen können (construction_demand je Gebäudeart gleich gewichtet), "
            "für Stadtrechte und für Straßen (Schotter, gepflastert), gereiht nach Knappheit.", "knapp", ()),
    "verwaltung": ("Verwaltung und Hof", "Güter für Regierungshandlungen – Privilegien, Kabinett, Institutionen, Reformen, "
                   "Hauptstadt (goods_demand government_activities) – und den Unterhalt der Bürokratie (bureaucracy_maintenance), "
                   "gereiht nach Knappheit.", "knapp", ()),
    "lebensstandard": ("Lebensstandard der Pops", "Güter nach dem Verbrauch der Pops im Heimatmarkt (Spielstand: Verbrauch „Pops“ × "
                       "Preis), gereiht nach Knappheit – gedeckter Bedarf hält die Stände zufrieden.", "knapp", ()),
}
REGIERUNG_BAU = ("build_town_demand", "build_city_demand", "build_megalopolis_demand")
STRASSEN = ("road_maintenance", "maintain_gravel_road_demand", "maintain_paved_road_demand")
EXPANSION = ("colony_construction", "simple_colony_construction", "colonial_charter_maintenance", "create_land_exploration",
             "create_sea_exploration", "create_conquistador")
TOP = 12           # Güter je Schwerpunkt in der Tabelle
KETTEN = 6         # davon mit Produktionsketten
MIN_ANTEIL = 0.02  # Gruppe „knapp“ erst ab 2 % Anteil am Schwerpunkt (sonst stehen Kleinstanteile vor den Hauptgütern)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _mengen(gd, key, seen=()):
    """Güter-Mengen eines goods_demand-Eintrags (copy_from aufgelöst)."""
    d = (gd.get(key) or {}).get("def") or {}
    if isinstance(d.get("copy_from"), str) and d["copy_from"] not in seen:
        return _mengen(gd, d["copy_from"], seen + (key,))
    return {g: v for g, v in d.items() if _num(v) and v > 0}


def _einheit(ut, k, feld, seen=()):
    d = (ut.get(k) or {}).get("def") or {}
    if feld in d:
        return d[feld]
    c = d.get("copy_from")
    return _einheit(ut, c, feld, seen + (k,)) if isinstance(c, str) and c not in seen else None


def _addiere(ziel, mengen, f=1.0, je_eintrag=False):
    """je_eintrag: ein Bedarfseintrag zählt insgesamt 1 (sonst bestimmt der Eintrag mit den größten Mengen das Bild – z. B.
    Hauptstadt-Umzug mit 5 Mauerwerk gegen je 1 Papier für Privilegien und Kabinett)."""
    s = sum(mengen.values()) if je_eintrag else 1
    for g, v in mengen.items():
        ziel[g] = ziel.get(g, 0) + v * f / (s or 1)


def _freigeschaltet(voll_get, last, feld):
    """Schlüssel, die die erforschten Fortschritte über <feld> (unlock_unit, unlock_building …) freischalten."""
    adv = voll_get("advances") or {}
    erforscht = {a.get("key") for a in (last.get("forschung") or {}).get("fortschritte") or []}
    out = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == feld:
                    out.update(v if isinstance(v, list) else [v])
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for a in erforscht:
        walk((adv.get(a) or {}).get("def"))
    return out


def build(last, wis, voll_get, gs, geb_werte=None, ort_werte=None, rgo_kosten=None, names=None, land_werte=None):
    """Alle Schwerpunkte für die Seite. voll_get(ordner) liefert einen Ordner des Spielwissens (history._voll)."""
    if not last or not wis or not last.get("markt"):
        return {}
    nm = names or (lambda k: k)
    goods = wis["gueter"]
    gn, bn = wis["namen"]["gueter"], wis["namen"]["gebaeude"]
    bt, gd, ut = voll_get("building_types") or {}, voll_get("goods_demand") or {}, voll_get("unit_types") or {}
    heimat = last["markt"]
    hm = {g["gut"]: g for g in heimat.get("gueter") or []}
    fremd = [m for m in (last.get("maerkte") or []) if not m.get("heimat")] + list(last.get("fremde_maerkte") or [])
    orte = last.get("orte") or []
    eigene_geb = collections.Counter(b.get("typ") for b in last.get("gebaeude") or [])

    def baubar(art):
        """bei uns vorhanden oder freigeschaltet (ohne Sonderbau, fehlenden Fortschritt und Landesbedingung – die gilt als
        erfüllt, wenn eine Gebäudeart, die wir haben, dieselbe trägt)."""
        s = gs.get(art) or {}
        return bool(s.get("bei_uns")) or not (s.get("sonder") or s.get("fortschritt")
                                              or (s.get("landbedingung") and not s.get("land_erfuellt")))

    # eigene Herstellung: Gebäude mit laufender Produktionsmethode für das Gut und Belegschaft (gebaeude_pm, Spielstand)
    pm_gut = {(art, pm.get("name")): pm.get("produced") for art, b in wis["gebaeude"].items() for pm in b.get("pms") or []}
    aktiv = collections.defaultdict(set)
    besch = {str(b.get("id")): b.get("beschaeftigt") for b in last.get("gebaeude") or []}
    for bid, x in (last.get("gebaeude_pm") or {}).items():
        if not (besch.get(str(bid)) or 0) > 0:
            continue
        for pm in x.get("pms") or []:
            g = pm_gut.get((x.get("typ"), pm))
            if g:
                aktiv[g].add(x.get("typ"))

    # ---------------------------------------------------------------- Gut: Lage im Heimatmarkt und in Reichweite
    def gut_info(g):
        x, base = hm.get(g) or {}, (goods.get(g) or {}).get("default_market_price")
        p = x.get("preis") if _num(x.get("preis")) and x.get("preis") > 0 else None
        ang = x.get("angebot") or 0
        imp = sum(v for k, v in (x.get("angebot_quellen") or {}).items() if k in ("Trade", "BurgherTrades"))
        exp_ = (x.get("verbrauch") or {}).get("Trade", 0)
        fp = [(m2.get("zentrum") or m2.get("id"), y["preis"], y.get("nachfrage") or 0)
              for m2 in fremd for y in m2.get("gueter") or [] if y.get("gut") == g and _num(y.get("preis")) and y["preis"] > 0]
        return {"name": gn.get(g, g), "kategorie": (goods.get(g) or {}).get("category"), "preis": p, "grundpreis": base,
                "verh": round(p / base, 3) if p and base else None, "nachfrage": x.get("nachfrage"), "angebot": x.get("angebot"),
                "vorrat": x.get("vorrat"), "einfuhr": round(imp / ang, 3) if ang else None,
                "ausfuhr": round(exp_ / x["nachfrage"], 3) if x.get("nachfrage") else None,
                "verlauf": [round(v, 4) for v in (x.get("preisverlauf") or [])[-24:]],
                "fremd_min": min(fp, key=lambda t: t[1])[:2] if fp else None,
                "fremd_max": max(fp, key=lambda t: t[1])[:2] if fp else None,
                "eigene_rgo": sorted({o["name"] for o in orte if o.get("rohstoff") == g}),
                "eigene_gebaeude": sorted(aktiv.get(g, ())), "nahrung": (goods.get(g) or {}).get("food")}
    G = {g: gut_info(g) for g in goods}

    # ---------------------------------------------------------------- Stufe 3: Gewinn je Gebäudeart (Spielstand)
    gg = last.get("gebaeude_gewinne") or {}
    gm = gg.get("maerkte") or {}
    hid = str(heimat.get("id"))
    fremd_ids = [str(m2.get("id")) for m2 in fremd]

    def gewinn(art):
        e = (gm.get(hid) or {}).get(art)
        if e and e[1] > 0:
            return {"quelle": "Heimatmarkt", "gebaeude": e[0], "stufen": e[1], "je_stufe": round(e[2] / e[1], 4),
                    "eigene": e[3], "laender": e[4]}
        z = [((gm.get(m2) or {}).get(art)) for m2 in fremd_ids]
        z = [x for x in z if x and x[1] > 0]
        if z:
            st, gw, n = sum(x[1] for x in z), sum(x[2] for x in z), sum(x[0] for x in z)
            return {"quelle": "Märkte in Reichweite", "gebaeude": n, "stufen": st, "je_stufe": round(gw / st, 4), "maerkte": len(z)}
        w = (gg.get("welt") or {}).get(art)
        if w and w[1] > 0:
            return {"quelle": "Welt", "gebaeude": w[0], "stufen": w[1], "je_stufe": round(w[2] / w[1], 4)}
        return None

    # eigene ausbaufähige Gebäude (unter der Höchststufe): Werte des Mods je Stufe (GetProfitPerLevel = GetProfit ÷ GetLevel,
    # Prüfung 25.10. – ein Durchschnitt, kein Zuwachs), je Art das beste
    eigen_mod = {}
    typ_von = {str(b.get("id")): b.get("typ") for b in last.get("gebaeude") or []}
    for bid, w in (geb_werte or {}).items():
        art = typ_von.get(str(bid))
        if not art or not _num(w.get("GetProfitPerLevel")):
            continue
        if _num(w.get("GetLevel")) and _num(w.get("GetMaxLevel")) and w["GetLevel"] >= w["GetMaxLevel"]:
            continue
        e = eigen_mod.get(art)
        if not e or w["GetProfitPerLevel"] > e["gewinn_je_stufe"]:
            eigen_mod[art] = {"gewinn_je_stufe": round(w["GetProfitPerLevel"], 4),
                              "steuer_je_stufe": round(w["GetTaxBaseValuePerLevel"], 4) if _num(w.get("GetTaxBaseValuePerLevel")) else None,
                              "stufe": w.get("GetLevel"), "max": w.get("GetMaxLevel")}

    # ---------------------------------------------------------------- Stufe 1: Gewichte je Schwerpunkt
    einheiten_frei = _freigeschaltet(voll_get, last, "unlock_unit")

    def einheiten(prefix, art):
        """Einheiten, die das Land über erforschte Fortschritte freigeschaltet hat (unlock_unit) – je Einheit Bau und
        Unterhalt gleich gewichtet. Holland 1348: Bogenschützen, Fußknechte, Reiter, gepanzerte Reiter, Kogge, Galeere."""
        z = {}
        for k in sorted(einheiten_frei):
            cat = _einheit(ut, k, "category")
            if not isinstance(cat, str) or not cat.startswith(prefix):
                continue
            for feld in ("construction_demand", "maintenance_demand"):
                key = _einheit(ut, k, feld)
                if isinstance(key, str) and ((gd.get(key) or {}).get("def") or {}).get("category", "").startswith(art):
                    _addiere(z, _mengen(gd, key), je_eintrag=True)
        return z

    def kategorie(cats=None, ausser=(), nur=None):
        z = {}
        for k, e in gd.items():
            d = e.get("def") or {}
            if (cats is None or d.get("category") in cats) and k not in ausser and (nur is None or k in nur):
                _addiere(z, _mengen(gd, k), je_eintrag=True)
        return z

    def hersteller(g, nur_baubar=True):
        return sorted({x["gebaeude"] for x in (goods.get(g) or {}).get("produziert_von") or []
                       if not nur_baubar or baubar(x["gebaeude"])})

    def bester_gewinn(g):
        """(Gewinn je Stufe, Gebäudeart, Quelle) der besten baubaren Gebäudeart – Heimatmarkt vor Reichweite vor Welt."""
        rang = {"Heimatmarkt": 0, "Märkte in Reichweite": 1, "Welt": 2}
        werte = [(w, a) for a in hersteller(g) if (w := gewinn(a))]
        if not werte:
            return None
        beste_quelle = min(rang[w["quelle"]] for w, _ in werte)
        w, a = max(((w, a) for w, a in werte if rang[w["quelle"]] == beste_quelle), key=lambda t: t[0]["je_stufe"])
        return w["je_stufe"], a, w["quelle"]

    def export_w():
        z = {}
        for g in goods:
            ph = G[g]["preis"] or G[g]["grundpreis"]
            if not ph:
                continue
            v = sum(max(0, y["preis"] - ph) * (y.get("nachfrage") or 0)
                    for m2 in fremd for y in m2.get("gueter") or [] if y.get("gut") == g and _num(y.get("preis")))
            if v > 0:
                z[g] = v
        return z

    def import_w():
        z = {}
        for g in goods:
            if not G[g]["preis"]:                     # das fertige Gut muss sich im Heimatmarkt verkaufen lassen
                continue
            best = 0
            for a in hersteller(g):
                for pm in (wis["gebaeude"].get(a) or {}).get("pms") or []:
                    if pm.get("produced") != g:
                        continue
                    v = 0
                    for i, amt in (pm.get("inputs") or {}).items():
                        ph, fm = G.get(i, {}).get("preis") or G.get(i, {}).get("grundpreis"), G.get(i, {}).get("fremd_min")
                        if ph and fm:
                            v += amt * max(0, ph - fm[1])
                    best = max(best, v / (pm.get("output") or 1))
            if best > 0:
                z[g] = best
        return z

    def bau_w():
        z = {}
        for a, e in bt.items():                       # Baugüter der Gebäudearten, die wir bauen können
            key = (e.get("def") or {}).get("construction_demand")
            if isinstance(key, str) and baubar(a):
                _addiere(z, _mengen(gd, key), je_eintrag=True)
        _addiere(z, kategorie(nur=REGIERUNG_BAU + STRASSEN))
        return z

    gewinn_quelle = {}
    gewinn_w = {}
    for g in goods:
        b = bester_gewinn(g)
        if b and b[0] > 0:
            gewinn_w[g], gewinn_quelle[g] = b[0], {"gebaeude": b[1], "quelle": b[2]}
    gewichte = {
        "grundwirtschaft": {g: G[g]["preis"] * (G[g]["nachfrage"] or 0) for g in goods if G[g]["preis"] and G[g]["nachfrage"]},
        "gewinn": gewinn_w,
        "bevoelkerung": {g: G[g]["nahrung"] for g in goods if _num(G[g]["nahrung"]) and G[g]["nahrung"] > 0},
        "landheer": einheiten("army_", "regiment_"),
        "marine": einheiten("navy_", "ship_"),
        "expansion": kategorie(nur=EXPANSION),
        "export": export_w(),
        "import": import_w(),
        "bau": bau_w(),
        "verwaltung": kategorie(nur=tuple(k for k, e in gd.items()
                                          if ((e.get("def") or {}).get("category") == "government_activities"
                                              and k not in REGIERUNG_BAU + ("market_create_demand", "market_destroy_demand")))
                                + ("bureaucracy_maintenance",)),
        "lebensstandard": {g: (hm.get(g, {}).get("verbrauch") or {}).get("Pops", 0) * (G[g]["preis"] or 0) for g in goods
                           if (hm.get(g, {}).get("verbrauch") or {}).get("Pops")},
    }

    # ---------------------------------------------------------------- Stufe 2: Gebäudearten
    meine_raenge = collections.defaultdict(list)
    for o in orte:
        meine_raenge[o.get("rang")].append(o["name"])
    pop_gesamt = collections.Counter()
    for o in orte:
        for t, v in (o.get("pops_typen") or {}).items():
            pop_gesamt[t] += (v or {}).get("groesse") or 0

    def geb_info(art):
        d = (bt.get(art) or {}).get("def") or {}
        arten = [r for r in ORTSARTEN if d.get(r) == "yes"]
        bau_key = d.get("construction_demand")
        pt = d.get("pop_type")
        return {"name": bn.get(art) or (bt.get(art) or {}).get("name") or art, "status": gs.get(art) or {},
                "baubar": baubar(art), "ortsart": [nm(r) for r in arten],
                "orte": sorted({n for r in arten for n in meine_raenge.get(r, [])}),
                "ortsbedingung": "location_potential" in d, "pop_typ": pt, "pop_name": nm(pt) if pt else None,
                "pops_bei_uns": round(pop_gesamt.get(pt, 0), 3) if pt else None,
                "pms": [{"name": pm.get("name"), "produziert": pm.get("produced"), "menge": pm.get("output"),
                         "eingang": pm.get("inputs") or {}}
                        for pm in (wis["gebaeude"].get(art) or {}).get("pms") or [] if pm.get("produced")],
                "gewinn": gewinn(art), "eigen": eigen_mod.get(art), "bei_uns": eigene_geb.get(art, 0),
                "baugueter": _mengen(gd, bau_key) if isinstance(bau_key, str) else {},
                "wirkung": {}, "wirkung_hauptstadt": {}}

    # Rohstoff-Ausbau der eigenen Orte je Rohstoff (Mod: GetRGOProfitPerLevel, Kosten aus GetUpgradeRGOBuildCostAndTime)
    rgo = collections.defaultdict(list)
    for o in orte:
        w = (ort_werte or {}).get(str(o["id"])) or (ort_werte or {}).get(o["id"]) or {}
        if o.get("rohstoff"):
            gold, tage = rgo_kosten(o["id"]) if rgo_kosten else (None, None)
            rgo[o["rohstoff"]].append({"ort": o["name"], "steuer_je_stufe": w.get("GetRGOProfitPerLevel"), "kosten": gold, "tage": tage})

    GEB = {}
    mt = voll_get("_modifikator_typen") or {}

    # ---------------------------------------------------------------- Stufe 4: Bauplan (eu5ratgeber/bauplan.py)
    eigene = []
    for b in last.get("gebaeude") or []:
        w = (geb_werte or {}).get(str(b.get("id"))) or {}
        stufe, mx = w.get("GetLevel", b.get("stufe")), w.get("GetMaxLevel")
        laufend = {pm_gut.get((b.get("typ"), pm)) for pm in ((last.get("gebaeude_pm") or {}).get(str(b.get("id"))) or {}).get("pms") or []}
        eigene.append({"typ": b.get("typ"), "ort": b.get("ort"), "ort_id": b.get("ort_id"), "stufe": stufe or 0,
                       # Güter der laufenden Produktionsmethode bei Belegschaft (Ausbau nur dafür, Prüfung 25.10.)
                       "produziert": sorted(g for g in laufend if g) if (b.get("beschaeftigt") or 0) > 0 else [],
                       "ausbaufaehig": _num(stufe) and _num(mx) and stufe < mx and not w.get("GetLevelsUnderConstruction")
                                       and not w.get("GetLevelsUnderUpgrade"),
                       "gewinn_je_stufe": w.get("GetProfitPerLevel") or 0, "steuer_je_stufe": w.get("GetTaxBaseValuePerLevel"),
                       "unterhalt_je_stufe": w.get("GetUpkeepPerLevel"),
                       "unterhalt_save": (b.get("unterhalt") or 0) / (b.get("stufe") or 1) if b.get("unterhalt") else None})
    eigene.sort(key=lambda e: -(e["gewinn_je_stufe"] or 0))

    def unterhalt_roh(art):
        return sum(m * (G.get(g, {}).get("preis") or G.get(g, {}).get("grundpreis") or 0)
                   for pm in (wis["gebaeude"].get(art) or {}).get("pms") or [] if not pm.get("produced")
                   for g, m in (pm.get("inputs") or {}).items())

    def unterhalt_ist(art):
        ist = [e["unterhalt_je_stufe"] or e["unterhalt_save"] for e in eigene if e["typ"] == art
               and (e["unterhalt_je_stufe"] or e["unterhalt_save"])]
        return max(ist) if ist else None
    # Unterhaltsgüter × Marktpreis liegt beim Spielwert nicht richtig (Burg 0,484 gegen 0,102, Kai 0,722 gegen 0,152 – Faktor
    # 0,21, Prüfung 25.10.): Faktor aus den eigenen Gebäuden mit Spielwert ableiten (Median), ohne solche nur die Güter nennen
    quoten = sorted(ist / roh for a in {e["typ"] for e in eigene} if (ist := unterhalt_ist(a)) and (roh := unterhalt_roh(a)))
    faktor = quoten[len(quoten) // 2] if quoten else None

    def unterhalt(art):
        """Unterhalt je Stufe: eigene Gebäude dieser Art (Mod GetUpkeepPerLevel bzw. Spielstand upkeep ÷ Stufe, Spielwert),
        sonst Schätzung über die Unterhaltsgüter, geeicht an unseren Gebäuden mit Spielwert."""
        ist = unterhalt_ist(art)
        if ist:
            return f"{bauplan._fmt(ist, 3)} Gold/Monat je Stufe (Spielwert)"
        roh = unterhalt_roh(art)
        if roh and faktor:
            return (f"≈ {bauplan._fmt(roh * faktor, 3)} Gold/Monat je Stufe (Schätzung: Unterhaltsgüter × Marktpreis × "
                    f"{bauplan._fmt(faktor, 2)}, geeicht an {len(quoten)} eigenen Gebäudearten)")
        g = {x: m for pm in (wis["gebaeude"].get(art) or {}).get("pms") or [] if not pm.get("produced")
             for x, m in (pm.get("inputs") or {}).items()}
        return ("Unterhaltsgüter je Stufe: " + ", ".join(f"{G.get(x, {}).get('name') or x} {bauplan._fmt(m)}" for x, m in g.items())) if g else None

    def modtxt(m, v):
        t = mt.get(m) or {}
        n = t.get("name") or m
        if v == "yes":
            return n
        if not _num(v):
            return f"{n} {v}"
        if t.get("percent") == "yes":
            v = v * 100
            return f"{n} {bauplan._sgn(v, 0 if float(v).is_integer() else 1)} %"
        # Mannstärke/Garnison/Seeleute (FormatManPower) und Bevölkerungsgrenze (FormatPopCaps) zählen in Tausend wie Pops
        tsd = " Tsd." if ((t.get("game_data") or {}).get("format") in ("FormatManPower", "FormatPopCaps")) else ""
        return f"{n} {bauplan._sgn(v, 0 if abs(v) >= 10 else 2 if abs(v) >= 0.1 else 3)}{tsd}"

    plan_ctx = {"G": G, "GEB": GEB, "gs": gs, "nm": nm, "bt": bt, "wis": wis, "orte": bauplan.ortsfakten(last, wis, ort_werte),
                "land": land_werte or {},
                "eigene": eigene, "rgo": rgo, "min_anteil": MIN_ANTEIL, "baubar": baubar,
                "hersteller": lambda g: hersteller(g), "geb_info": lambda a: geb_info(a), "unterhalt": unterhalt,
                "modtxt": modtxt, "mengen": lambda k: _mengen(gd, k) if isinstance(k, str) else {},
                "rt": voll_get("road_types") or {}, "preise": voll_get("prices") or {}}
    out = {"gueter": G, "gebaeude": GEB, "rgo": dict(rgo), "fokusse": {}, "heimat": heimat.get("zentrum"),
           "fremde_maerkte": [m2.get("zentrum") for m2 in fremd], "einheiten": sorted(einheiten_frei),
           "modnamen": {m: {"name": (mt.get(m) or {}).get("name") or m, "prozent": (mt.get(m) or {}).get("percent") == "yes"}
                        for f in FOKUS.values() for m in f[3]}}
    for key, (name, erkl, reihung, fmods) in FOKUS.items():
        w = gewichte.get(key) or {}
        summe = sum(w.values()) or 1
        rows = []
        for g, v in w.items():
            anteil = v / summe
            verh = G[g]["verh"]
            rows.append({"gut": g, "anteil": round(anteil, 4), "wert": round(v, 4),
                         "rang": round(anteil * (verh if reihung == "knapp" and verh else 1), 5),
                         # knapp nur mit Nachfrage: ohne Angebot und Nachfrage steht der Preis auf dem Grundpreis (Oliven 1,00)
                         "im_markt": G[g]["preis"] is not None, "knapp": (verh or 0) >= 1 and (G[g]["nachfrage"] or 0) > 0,
                         **(gewinn_quelle.get(g, {}) if key == "gewinn" else {})})

        # knapp: erst knappe Güter (Preis ≥ Grundpreis) mit mindestens MIN_ANTEIL, nach Anteil × Preis/Grundpreis, dann die übrigen
        # – mehr von einem Gut unter Grundpreis drückt den Preis weiter; wert: nur nach dem Anteil
        def ordnung(r):
            vorne = reihung == "wert" or (r["knapp"] and r["anteil"] >= MIN_ANTEIL)
            return (0 if vorne else 1, -r["rang"])
        im = sorted([r for r in rows if r["im_markt"] or reihung == "wert"], key=ordnung)[:TOP]
        fehlt = sorted([r for r in rows if not r["im_markt"] and reihung != "wert"], key=lambda r: -r["anteil"])[:TOP]
        for r in fehlt:                               # nur als Rohstoff ohne eigenen Ort: keine Kette möglich
            r["nur_rohstoff"] = not hersteller(r["gut"], False) and not G[r["gut"]]["eigene_rgo"]
        kandidaten = [r for r in (im + fehlt if reihung == "wert" else im[:KETTEN - min(2, len(fehlt))] + fehlt + im)
                      if not r.get("nur_rohstoff")]
        ketten, eingang = {}, {}
        for r in kandidaten:
            if len(ketten) >= KETTEN or r["gut"] in ketten:
                continue
            arten = hersteller(r["gut"], False)
            if not arten and G[r["gut"]]["kategorie"] != "raw_material":
                continue
            for a in arten:
                if a not in GEB:
                    GEB[a] = geb_info(a)
            ketten[r["gut"]] = arten
            for a in arten:                                   # Eingangsgüter: deren baubare Hersteller (eine Stufe tiefer)
                for pm in GEB[a]["pms"]:
                    for i in pm["eingang"]:
                        eingang[i] = hersteller(i)
        wirkung = []
        if fmods:
            for a, e in bt.items():
                d = e.get("def") or {}
                s = gs.get(a) or {}
                if s.get("sonder") and not s.get("freischaltung") and not s.get("bei_uns"):
                    continue                                  # Denkmäler/Ereignisgebäude: nicht frei baubar
                if s.get("erreichbar") is False and not s.get("bei_uns"):
                    continue                                  # Fortschritt mit Bedingung, die wir nicht erfüllen (andere Kultur)
                m = d.get("modifier") if isinstance(d.get("modifier"), dict) else {}
                c = d.get("capital_modifier") if isinstance(d.get("capital_modifier"), dict) else {}
                if not any(x in m or x in c for x in fmods):
                    continue
                if a not in GEB:
                    GEB[a] = geb_info(a)
                GEB[a]["wirkung"].update({x: v for x, v in m.items() if x in fmods})
                GEB[a]["wirkung_hauptstadt"].update({x: v for x, v in c.items() if x in fmods})
                wirkung.append(a)
        out["fokusse"][key] = {
            "name": name, "erklaerung": erkl, "reihung": reihung, "gueter": im, "fehlen": fehlt, "ketten": ketten,
            "eingang": eingang, "modifikatoren": list(fmods),
            "wirkung": sorted(wirkung, key=lambda a: (-(GEB[a]["bei_uns"] or 0), not GEB[a]["baubar"],
                                                      bool((gs.get(a) or {}).get("fortschritt")), GEB[a]["name"]))}
        out["fokusse"][key]["plan"] = bauplan.plane(key, out["fokusse"][key], plan_ctx)
    return out
