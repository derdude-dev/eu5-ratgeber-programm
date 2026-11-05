"""Karte „Handelsbestellungen und Zölle“ (Nutzerwunsch 27.10., Patch 1.4); Grundlage der Empfehlung „Zölle“
(empfehlungen.r_zoelle).

Im deutschen Spiel heißen Handelsaufträge „Handelsbestellungen“ (game_concept_trade_order), das Fenster der Zölle
„Handelsrichtlinien“ (TRADE_POLICIES_LATERALVIEW_TITLE).

Quellen:
- Daten-Mod, neuester Monat: RG2 handel je Route (Trade.GetTariffValue – negativ = wir zahlen, IsFromTradeOrder, IsLocked,
  IsExport, GetProfit, GetAssignedMerchantCapacity, GetProfitPerMerchantCapacity), RG1T je Route (Gut, Ausgangs- und
  Zielmarkt), Text Trade.GetTariffInfo je Route, RG2 landmod (max_tariff, max_trade_subventions, tariff_income, trade_income).
- Spielstand (Format 15, snapshot.zoelle/handelsbestellungen): Zollsätze je Land und Gut, Zolleinnahmen von Land und
  Ständen, Marktbesitzer, Meinungsabzug durch Ausfuhrzölle, Handelsbestellungen roh.
- Spieldateien (Spielwissen): Define NCountry.DEFAULT_TRADE_ORDER_MIN_PROFIT = 0,25 (Standard-Mindestgewinn einer
  Handelsbestellung je Händlerkapazität), Quellen der Modifikatoren max_tariff/max_trade_subventions/tariff_income.

Herkunft einer Route wie in der Handelsübersicht (panels/trade/trade_overview_possible_trades.gui): Zahnrad bei
IsFromTradeOrder („Dieser Handel wird durch eine Handelsbestellung geschaffen“), Automatik ohne Bestellung und ohne Sperre
(„wird von der Automatisierung übernommen“), Schloss bei IsLocked ohne Bestellung („durch eine Vereinbarung geschützt“).
Der Zoll ist im Gewinn der Route schon abgezogen (nachgerechnet 27.10.: Verkauf − Einkauf − Unterhalt passt bei Routen mit
Zoll nur nach Abzug des Zolls).

Empfehlungen für Handelsbestellungen (Nutzerwunsch 29.10.) – pruefung() und vorschlaege() unten:
- pruefung: je Bestellung und Ware die Routen (live und je Monat laut Daten-Mod), die Lage im Markt der Bestellung, Preise in
  den Märkten in Reichweite, unsere Händlerkapazität dort, Gewinn je Kapazität von Bestellung und Automatisierung.
- vorschlaege: je Schwerpunkt des Wirtschaftsplans (wirtschaftsplan.FOKUS) passende Ein- oder Ausfuhrbestellungen für den
  Heimatmarkt mit Vorlage aus dem Spiel (Modus, Eintrag „Beliebige …“). Gewinn je Händlerkapazität einer neuen Route ist nicht
  vorausberechenbar (Kapazität je Einheit hängt von Entfernung und Gut ab) – das zeigt nur das Spiel in der Bestellung.
"""
import json
import re

from . import sprache

HERKUNFT = {"automatik": "Automatisierung", "bestellung": "Handelsbestellung", "geschuetzt": "geschützt (Vereinbarung)"}
# Spieltexte (deutsch) TRADE_IMPORT/EXPORT_TARIFF_TT und TRADE_IMPORT/EXPORT_SUBSIDY_TT (trade_orders_l_german.yml), nach
# livelog.decode_text: „Bulgarien verlangt einen 20% Zoll auf Ausfuhren von: Schmuck (0.98).“
_ZOLL = re.compile(r"(?P<land>[^\n]+?) verlangt einen (?P<satz>-?\d+)% Zoll auf (?P<richtung>Einfuhren|Ausfuhren) von: "
                   r"(?P<gut>[^\n(]+?) \((?P<wert>-?[\d.,]+)\)")
_SUBV = re.compile(r"(?P<land>[^\n]+?) zahlt eine (?P<satz>-?\d+)% Subvention für (?P<richtung>Einfuhren|Ausfuhren) von:? "
                   r"(?P<gut>[^\n(:]+?):? \((?P<wert>-?[\d.,]+)\)")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _zahl(s):
    return float(s.replace(",", ".")) if s.count(",") == 1 and "." not in s else float(s.replace(",", ""))


def zolltexte(text):
    """Trade.GetTariffInfo -> [{land, art (zoll|subvention), richtung (einfuhr|ausfuhr), satz (0,2 = 20 %), gut, wert}];
    wert = Gold je Monat wie im Text (ohne Vorzeichen, 2 Stellen)."""
    out = []
    for art, rx in (("zoll", _ZOLL), ("subvention", _SUBV)):
        for m in rx.finditer(text or ""):
            out.append({"land": m.group("land").strip(), "art": art,
                        "richtung": "einfuhr" if m.group("richtung") == "Einfuhren" else "ausfuhr",
                        "satz": int(m.group("satz")) / 100, "gut": m.group("gut").strip(), "wert": _zahl(m.group("wert"))})
    return out


def herkunft(w):
    """Herkunft einer Route aus den RG2-Werten (1/0) – None ohne 1.4-Werte (GetTariffValue): in 1.3 gab es manuelle
    Handelskapazität (Market.GetManualTradeCapacity), die Regel der 1.4-Oberfläche passt dort nicht (Prüfer 27.10.)."""
    if "GetTariffValue" not in w:
        return None
    if w.get("IsFromTradeOrder") == 1:
        return "bestellung"
    if w.get("IsLocked") == 1:
        return "geschuetzt"
    if w.get("IsLocked") == 0:
        return "automatik"
    return None


def _monat(db, tag, art):
    r = db.execute("SELECT MAX(jahr*12+monat) FROM monat_extra WHERE tag=? AND art=?", (tag, art)).fetchone()
    return r[0] if r and r[0] else None


def _datum(ym):
    return f"{(ym - 1) // 12}.{(ym - 1) % 12 + 1}.1" if ym else None


def _strategie(names, wert):
    """automated_trade_policy_strategy (Balanced …) -> Name aus TRADE_POLICY_STRATEGY_<WERT> (Balanced → BALANCED belegt)."""
    if not wert:
        return None
    key = "TRADE_POLICY_STRATEGY_" + re.sub(r"(?<!^)(?=[A-Z])", "_", str(wert)).upper()
    n = names(key) if names else key
    return n if n and n != key else str(wert)


def quellen_liste(quellen, names, mod):
    """Quellen eines Modifikators laut Spielwissen (_modifikator_quellen: [ordner, definition, pfad, wert]); teil = Unterteil
    mit eigenem Namen (Gesetz: Politik „free_trade_policy/country_modifier“) bzw. Pol eines Gesellschaftswerts."""
    nm = names or (lambda k: k)

    def teil(p):
        if "/" in p:
            return nm(p.split("/")[0])
        return {"left_modifier": "linker Pol", "right_modifier": "rechter Pol"}.get(p, "")
    return [{"ordner": o, "name": nm(d) or d, "teil": teil(p or ""), "wert": w} for o, d, p, w in (quellen or {}).get(mod) or []
            if _num(w)]


def build(db, last, names=None, defines=None, quellen=None, wp=None):
    """Alles für die Karte und die Empfehlung (siehe Modulkopf); wp = wirtschaftsplan.build (für die Vorschläge je Schwerpunkt)."""
    nm = names or (lambda k: k)
    tag = last["meta"]["tag"]
    z = last.get("zoelle") or {}
    besitzer = z.get("markt_besitzer") or {}
    laender = z.get("laender") or {}
    mname = {str(k): v for k, v in (last.get("markt_namen") or {}).items()}
    ym = _monat(db, tag, "a.handel")
    werte = {k: json.loads(w) for k, w in db.execute(
        "SELECT schluessel, werte FROM monat_extra WHERE tag=? AND art='a.handel' AND jahr*12+monat=?", (tag, ym))} if ym else {}
    det = {}
    for k, w in db.execute("SELECT schluessel, werte FROM monat_extra WHERE tag=? AND art='handel' AND jahr*12+monat=?",
                           (tag, ym or -1)):
        e = json.loads(w)
        det[str(e.get("id", k.lstrip(":")))] = e
    texte = {}
    for k, w in db.execute("SELECT schluessel, werte FROM monat_extra WHERE tag=? AND art='text' AND jahr*12+monat=? "
                           "AND schluessel LIKE 'handel:%:GetTariffInfo'", (tag, ym or -1)):
        texte[k.split(":")[1]] = json.loads(w).get("text") or ""
    lm = {}
    r = db.execute("SELECT werte FROM monat_extra WHERE tag=? AND art='a.landmod' ORDER BY jahr DESC, monat DESC LIMIT 1",
                   (tag,)).fetchone()
    if r:
        lm = json.loads(r[0])

    routen = []
    for rid, w in werte.items():
        d = det.get(str(rid)) or {}
        von, nach, gut = d.get("von"), d.get("nach"), d.get("gut")
        export = {1: True, 0: False}.get(w.get("IsExport"))
        bv, bn = besitzer.get(str(von)), besitzer.get(str(nach))
        # Satz laut Spielstand: Ausfuhrzoll des Besitzers des Ausgangsmarkts (Spielbegriff Ausfuhrzoll: „Waren, die unsere
        # Märkte in Richtung fremdländischer Ziele verlassen“) – Einfuhrzölle haben im Spielstand noch kein belegtes Feld
        satz = ((laender.get(bv) or {}).get("goods_export_tariffs") or {}).get(gut) if export and bv and bv != tag else None
        routen.append({"id": int(rid) if str(rid).isdigit() else rid, "gut": gut, "gut_name": nm(gut) if gut else None,
                       "von": von, "nach": nach, "von_name": mname.get(str(von)), "nach_name": mname.get(str(nach)),
                       "besitzer_von": bv, "besitzer_nach": bn, "export": export, "herkunft": herkunft(w),
                       "zoll": w.get("GetTariffValue"), "gewinn": w.get("GetProfit"),
                       "kapazitaet": w.get("GetAssignedMerchantCapacity"), "genutzt": w.get("GetActuallyUsedOrAssignedMerchantCapacity"),
                       "je_kap": w.get("GetProfitPerMerchantCapacity"), "text": texte.get(str(rid), ""),
                       "texte": zolltexte(texte.get(str(rid), "")), "satz_spielstand": satz})
    routen.sort(key=lambda x: (x["zoll"] if _num(x["zoll"]) else 0, -(x["gewinn"] or 0)))

    # Zölle je Land: Land aus dem Spieltext, ohne lesbaren Text über den Marktbesitzer (Richtung der Route). Betrag bei genau
    # einem Texteintrag der genaue Wert der Route (GetTariffValue) – der Goldwert im Text ist auf 2 Stellen abgeschnitten
    # (0,369 → „0.36“, Prüfer 27.10.); nur bei mehreren Einträgen je Route die Textwerte (Zoll −, Subvention +)
    je_land = {}
    for x in routen:
        if not _num(x["zoll"]) or x["zoll"] == 0:
            continue
        if x["texte"]:
            for e in x["texte"]:
                g = je_land.setdefault(e["land"], {"land": e["land"], "quelle": "Spieltext", "routen": set(), "betrag": 0.0,
                                                   "eintraege": []})
                g["routen"].add(x["id"])
                g["betrag"] += (x["zoll"] if len(x["texte"]) == 1
                                else -abs(e["wert"]) if e["art"] == "zoll" else abs(e["wert"]))
                g["eintraege"].append({k: e[k] for k in ("art", "richtung", "satz", "gut")})
        else:
            t = x["besitzer_von"] if x["export"] else x["besitzer_nach"]
            name = nm(t) if t else "unbekannt"
            g = je_land.setdefault(name, {"land": name, "quelle": "Marktbesitzer (Spielstand)", "routen": set(), "betrag": 0.0,
                                          "eintraege": []})
            g["routen"].add(x["id"])
            g["betrag"] += x["zoll"]
    meinung = {(nm(m["tag"]) if m.get("tag") else None): m["wert"] for m in (z.get("meinung") or {}).get("gegen_uns") or []}
    je_land = sorted(({**g, "routen": len(g["routen"]), "betrag": round(g["betrag"], 3), "meinung": meinung.get(g["land"])}
                      for g in je_land.values()), key=lambda g: g["betrag"])

    hk = {}
    for x in routen:
        h = hk.setdefault(x["herkunft"] or "unbekannt", {"routen": 0, "kapazitaet": 0.0, "gewinn": 0.0, "zoll": 0.0})
        h["routen"] += 1
        h["kapazitaet"] += x["kapazitaet"] or 0
        h["gewinn"] += x["gewinn"] or 0
        h["zoll"] += x["zoll"] if _num(x["zoll"]) else 0
    mindest = ((defines or {}).get("NCountry") or {}).get("def", {}).get("DEFAULT_TRADE_ORDER_MIN_PROFIT")
    zoll = sum(x["zoll"] for x in routen if _num(x["zoll"]))
    gewinn = sum(x["gewinn"] for x in routen if _num(x["gewinn"]))

    land = z.get("land") or {}
    # Handelsaufträge in 1.3-Spielständen: am Land trade_orders = { { market goods trade_order_is_import trade_order_capacity } }
    # (MP_WAL_1479, 1.3.11: Eisen-Einfuhr Markt 131, Kapazität 2 – Prüfer 27.10.); Anhaltspunkt für das Format in 1.4
    alt = land.get("trade_orders")
    bestellungen_13 = [{**e, "markt_name": mname.get(str(e.get("market"))), "gut_name": nm(e["goods"]) if e.get("goods") else None}
                       for e in (alt if isinstance(alt, list) else [alt] if isinstance(alt, dict) else []) if isinstance(e, dict)]
    # Handelsbestellungen lesbar (Format belegt 29.10., snapshot.handelsbestellungen): Markt, Güter mit Richtung (ohne
    # trade_order_is_import = Ausfuhr), Kapazität (Anteil in % bei trade_order_is_percentage), Mindestgewinn (wenn genutzt);
    # Routen über trade_order_ref unserer Routen im Spielstand, Gewinn/Kapazität/Zoll live (Mod) über dieselbe Routen-Nr.
    live = {str(x["id"]): x for x in routen}
    ref = {}
    for t in last.get("handel_spielstand") or []:
        if t.get("trade_order_ref") is not None:
            ref.setdefault(str(t["trade_order_ref"]), []).append(str(t["id"]))
    bestellungen = []
    for e in ((last.get("handelsbestellungen") or {}).get("unsere") or []):
        ge = e.get("trade_order_goods_entry")
        ge = ge if isinstance(ge, list) else [ge] if isinstance(ge, dict) else []
        rids = ref.get(str(e.get("id")), [])
        lr = [live[r] for r in rids if r in live]
        bestellungen.append({
            "id": e.get("id"), "markt": e.get("market"), "markt_name": mname.get(str(e.get("market"))),
            "gueter": [{"gut": g.get("goods"), "gut_name": nm(g["goods"]) if g.get("goods") else None,
                        "richtung": "einfuhr" if g.get("trade_order_is_import") == "yes" else "ausfuhr"} for g in ge if isinstance(g, dict)],
            "kapazitaet": e.get("trade_order_capacity"), "anteil": e.get("trade_order_is_percentage") == "yes",
            "mindestgewinn": e.get("trade_order_min_profit") if e.get("trade_order_use_min_profit") == "yes" else None,
            "routen": len(rids), "routen_live": len(lr),
            "gewinn": round(sum(x["gewinn"] or 0 for x in lr), 3) if lr else None,
            "kap_genutzt": round(sum(x["kapazitaet"] or 0 for x in lr), 3) if lr else None,
            "zoll": round(sum(x["zoll"] for x in lr if _num(x["zoll"])), 3) if lr else None,
            "gueter_routen": sorted({x["gut_name"] or x["gut"] for x in lr if x["gut"]})})
    staende = {e["stand"]: (e.get("letzter_monat") or {}).get("tariff_income") for e in last.get("staende") or []}
    staende = {k: v for k, v in staende.items() if _num(v)}
    eigene = sorted(k for k, t in besitzer.items() if t == tag)
    heim = (last.get("markt") or {}).get("id")
    hb = besitzer.get(str(heim)) if heim is not None else None
    out = {
        "datum": _datum(ym), "routen": routen, "je_land": je_land,
        # Daten aus 1.4: Routen mit Zollwert (Mod) oder ein Spielstand mit trade_order_manager – sonst zeigt die Seite die Zoll-
        # und Herkunftskarten nicht (1.3 hatte keine Zölle)
        "ab14": any("GetTariffValue" in w for w in werte.values()) or last.get("handelsbestellungen") is not None,
        # Besitzer der Märkte unserer Bestellungen (Name) – seine Zölle zahlt jede Route der Bestellung (Prüfer 29.10.)
        "bestellmarkt_besitzer": {str(b["markt"]): nm(besitzer[str(b["markt"])]) for b in bestellungen
                                  if besitzer.get(str(b["markt"]))},
        "herkunft": {k: {kk: round(vv, 3) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in hk.items()},
        "herkunft_namen": HERKUNFT, "zoll": round(zoll, 3), "gewinn": round(gewinn, 3), "gewinn_vor_zoll": round(gewinn - zoll, 3),
        "mindestgewinn": mindest,
        "unter_mindest": [x["id"] for x in routen if _num(mindest) and _num(x["je_kap"]) and (x["kapazitaet"] or 0) > 0
                          and x["je_kap"] < mindest],
        "modifikatoren": {k: lm.get(k) for k in ("max_tariff", "max_trade_subventions", "tariff_income", "trade_income",
                                                 "tariff_impact_on_price")},
        "quellen": {m: quellen_liste(quellen, names, m) for m in ("max_tariff", "max_trade_subventions", "tariff_income")},
        "spielstand": {
            "datum": last["meta"]["datum"], "vorhanden": "zoelle" in last,
            # der Spielstand lässt Nullwerte weg (93 Länder mit Feld; die Walachei ohne Markt hat keins) -> ab Format 15 fehlend = 0
            "zolleinnahmen_land": land.get("last_months_tariff_income", 0.0 if "zoelle" in last else None),
            "zolleinnahmen_staende": staende,
            "buerger_feld": land.get("last_months_burgher_tariff_revenue"),
            "saetze": {k: v for k, v in land.items() if isinstance(v, dict)},
            "felder": {k: v for k, v in land.items() if not isinstance(v, dict)},
            "strategie": land.get("automated_trade_policy_strategy"),
            "strategie_name": _strategie(names, land.get("automated_trade_policy_strategy")),
            "eigene_maerkte": [{"id": int(k), "name": mname.get(k)} for k in eigene],
            "heimatmarkt": heim, "heimatmarkt_name": mname.get(str(heim)) if heim is not None else None,
            "heimatmarkt_besitzer": hb, "heimatmarkt_besitzer_name": nm(hb) if hb else None,
            # Zollfelder des fremden Besitzers unseres Heimatmarkts (seine Ausfuhrzölle treffen unsere Ausfuhren von dort)
            "heimatmarkt_besitzer_saetze": {k: v for k, v in (laender.get(hb) or {}).items() if isinstance(v, dict)}
                                           if hb and hb != tag else {},
            "meinung": z.get("meinung") or {}, "handelsbestellungen": last.get("handelsbestellungen"),
            "bestellungen_13": bestellungen_13, "bestellungen": bestellungen,
        },
    }
    # Empfehlungen für Handelsbestellungen (29.10.): Schwellen aus den Defines, Prüfung der Bestellungen, Vorschläge je Schwerpunkt –
    # nur für Spielstände ab 1.4 (Modi und Vorlagen der Bestellungen gibt es erst dort; die Mod-Daten hängen nur am Länderkürzel,
    # ab14 allein trennt eine 1.3-Partie mit gleichem Kürzel nicht)
    neu = ab_14(last, out["ab14"])
    out["defines_handel"] = defines_handel(defines)
    out["pruefung"] = pruefung(db, last, out, nm) if neu else {"kapazitaet": {}, "bestellungen": []}
    out["vorschlaege"] = vorschlaege(out, wp, last, nm, _markt_mod(db, tag, heim)) if wp and neu else {}
    return out


# ---------------------------------------------------------------- Handelsbestellungen prüfen und vorschlagen (29.10.)
# Spielregeln laut Lokalisierung (main_menu/localization/german/trade_orders_l_german.yml) und Defines
# (loading_screen/common/defines/00_defines.txt), geprüft 29.10. – Wortlaut siehe analysis/MECHANIK.md:
# - Modi: Gewinnschwerpunkt (TRADE_ORDER_MODE_PROFIT), Nahrungsschwerpunkt (…_FOOD), Knappheitsschwerpunkt (…_NEEDS).
# - Mindestgewinn je Händlerkapazität: darunter keine Routen; je näher der beste Gewinn an der Schwelle, desto weniger Kapazität
#   (TRADE_ORDER_MIN_PROFIT_TT); Standard 0,25 (NCountry.DEFAULT_TRADE_ORDER_MIN_PROFIT).
# - Kapazität als Anteil oder feste Menge, jeweils ein Maximum (TRADE_ORDER_TC_TOGGLE_TO_…_DESC); frühere Bestellungen bekommen
#   zuerst Kapazität (TRADE_ORDER_PRIORITY_INFO); ohne eigene Kapazität im Markt kann die Bestellung nichts zuordnen
#   (TRADE_ORDER_NO_TC_IN_MARKET_TT).
# - Ohne gewinnbringende Route sucht die KI jeden Tag weiter (TRADE_ORDER_NO_PROFITABLE_ROUTE, …_BELOW_PROFIT_CUTOFF – das Spiel
#   nennt dort die beste Route mit ihrem Gewinn je Händlerkapazität; der Ratgeber kennt diesen Wert nicht).
# Spielstand 1.4.5: Felder trade_order_mode, trade_order_import/export_markets, …_market_groups kennt das Spielprogramm (eu5.exe),
# die Bestellung des Nutzers (1338.4.7) hat keins davon -> Standardwerte, welche, ist nicht belegt.
MODI = {
    "profit": ("Gewinnschwerpunkt", "TRADE_ORDER_MODE_PROFIT",
               "nutzt die Händlerkapazität für die lohnenswertesten Handel bei den gewählten Waren und Märkten"),
    "food": ("Nahrungsschwerpunkt", "TRADE_ORDER_MODE_FOOD",
             "bringt möglichst viel Nahrung auf einen Markt, der ohne die Bestellung Nahrung verlieren würde und unter {food} "
             "Nahrungsbestand hat (Define TRADE_ORDER_FOOD_MAINTAIN_STOCKPILE_FRACTION)"),
    "needs": ("Knappheitsschwerpunkt", "TRADE_ORDER_MODE_NEEDS",
              "deckt Knappheiten des Zielmarkts, ein Eintrag nach dem anderen – nur Waren, die der Markt stärker verbraucht als er "
              "herstellt und deren Vorrat unter {needs} des Höchstvorrats liegt (Define "
              "TRADE_ORDER_NEEDS_STOCKPILE_EXCLUSION_FRACTION; den Höchstvorrat je Ware hat der Spielstand nicht)"),
}
EINTRAEGE = {
    "any_food": ("Beliebige Nahrung", "TRADE_ORDER_ANY_FOOD", "alle Waren, die Nahrung ergeben"),
    "any_pop_need": ("Beliebige Pop-Bedarfe", "TRADE_ORDER_ANY_POP_NEED",
                     "jede Ware, die unsere Pops auf diesem Markt derzeit brauchen; monatlich neu bewertet"),
    "any_government_need": ("Beliebige Regierungsbedarfe", "TRADE_ORDER_ANY_GOVERNMENT_NEED",
                            "jede Ware, die die Regierung auf diesem Markt derzeit braucht; monatlich neu bewertet"),
}
# Schwerpunkt -> (Richtung, Modus, Eintrag „Beliebige …“ oder None). Regel des Ratgebers: Einfuhr knapper Güter des Schwerpunkts
# (Knappheitsschwerpunkt), Ausfuhr von Überschüssen bei Export und Gewinn (Gewinnschwerpunkt), Veredelung: Einfuhr der
# Eingangsgüter (Einkaufsvorteil = Gewinn); Bevölkerung mit dem Nahrungsschwerpunkt des Spiels, Lebensstandard und Verwaltung
# mit den Einträgen des Spiels für Pop- und Regierungsbedarfe.
VORLAGEN = {"grundwirtschaft": ("einfuhr", "needs", None), "gewinn": ("ausfuhr", "profit", None),
            "bevoelkerung": ("einfuhr", "food", "any_food"), "landheer": ("einfuhr", "needs", None),
            "marine": ("einfuhr", "needs", None), "expansion": ("einfuhr", "needs", None), "export": ("ausfuhr", "profit", None),
            "import": ("einfuhr", "profit", None), "bau": ("einfuhr", "needs", None),
            "verwaltung": ("einfuhr", "needs", "any_government_need"), "lebensstandard": ("einfuhr", "needs", "any_pop_need")}
KNAPP_FAKTOR = 1.05        # knapp = Nachfrage > Angebot × 1,05 (wie Markt- und Güterkachel), Überschuss = Angebot > Nachfrage × 1,05
OHNE_ROUTE_MONATE = 3      # Ware einer Bestellung ohne Route ab 3 Monaten in Folge (Regel des Ratgebers)
MAX_VORSCHLAEGE = 5        # Vorschläge je Schwerpunkt
DEFINES_HANDEL = (("NCountry", "DEFAULT_TRADE_ORDER_MIN_PROFIT"), ("NCountry", "MERCHANT_MAINTENANCE_COST"),
                  ("NAI", "TRADE_ORDER_MIN_TRADE_CAPACITY"), ("NAI", "AI_MINIMUM_TRADE_SIZE"),
                  ("NAI", "AI_STEAL_MERCHANT_CAPACITY_PROFIT_MARGIN"), ("NAI", "AI_PERFORMANCE_TRADE_PROFIT_PER_WEIGHT_CUTOFF"),
                  ("NAI", "TRADE_ORDER_FOOD_MAINTAIN_STOCKPILE_FRACTION"), ("NAI", "TRADE_ORDER_NEEDS_STOCKPILE_EXCLUSION_FRACTION"))


def ab_14(last, sonst=False):
    """Spielstand ab Version 1.4 (meta.version „1.4.5“); ohne Versionsangabe der Rückfall (ab14 aus build)."""
    v = str((last.get("meta") or {}).get("version") or "")
    try:
        return tuple(int(x) for x in v.split(".")[:2]) >= (1, 4)
    except ValueError:
        return bool(sonst)


def defines_handel(defines):
    """Die Defines, die Prüfung, Vorschläge und Regeln nutzen: {NAME: Wert} (fehlt das Spielwissen: leer)."""
    out = {}
    for blk, k in DEFINES_HANDEL:
        v = (((defines or {}).get(blk) or {}).get("def") or {}).get(k)
        if _num(v):
            out[k] = v
    return out


def _mon(ym):
    return f"{(ym - 1) // 12}.{(ym - 1) % 12 + 1}"


def _r(v, d=3):
    return round(v, d) if _num(v) else None


def _je_kap(rs, genutzt, zugewiesen):
    """Gewinn je Händlerkapazität mehrerer Routen wie das Spiel (GetProfitPerMerchantCapacity = Gewinn ÷ genutzte Kapazität
    GetActuallyUsedOrAssignedMerchantCapacity: Feinstoff 0,433 ÷ 0,439 = 0,986, Urkorn 1337.8 laut Mod 0,307 bei zugewiesen 1,352)."""
    if len(rs) == 1 and _num(rs[0].get("je_kap")):
        return _r(rs[0]["je_kap"])
    k = sum((x.get(genutzt) if _num(x.get(genutzt)) else x.get(zugewiesen)) or 0 for x in rs)
    return _r(sum(x.get("gewinn") or 0 for x in rs) / k) if k > 0 else None


def routen_monate(db, tag):
    """Routen je Monat laut Daten-Mod (RG2 handel + RG1T handel): [(ym, [{id, gut, von, nach, bestellung, kap, gewinn, je_kap,
    zoll}])] für jeden Monat mit Monatszeile des Landes (a.land) – ein Monat ohne a.handel-Zeile hatte keine Route."""
    monate = sorted(r[0] for r in db.execute("SELECT DISTINCT jahr*12+monat FROM monat_extra WHERE tag=? AND art IN ('a.land', "
                                             "'a.handel')", (tag,)))
    det = {}
    for ym, w in db.execute("SELECT jahr*12+monat, werte FROM monat_extra WHERE tag=? AND art='handel'", (tag,)):
        e = json.loads(w)
        det[(ym, str(e.get("id")))] = e
    je = {}
    for ym, k, w in db.execute("SELECT jahr*12+monat, schluessel, werte FROM monat_extra WHERE tag=? AND art='a.handel'", (tag,)):
        e, d = json.loads(w), det.get((ym, str(k))) or {}
        je.setdefault(ym, []).append({"id": str(k), "gut": d.get("gut"), "von": d.get("von"), "nach": d.get("nach"),
                                      "bestellung": e.get("IsFromTradeOrder") == 1, "kap": e.get("GetAssignedMerchantCapacity"),
                                      "genutzt": e.get("GetActuallyUsedOrAssignedMerchantCapacity"),
                                      "gewinn": e.get("GetProfit"), "je_kap": e.get("GetProfitPerMerchantCapacity"),
                                      "zoll": e.get("GetTariffValue")})
    return [(ym, je.get(ym, [])) for ym in monate]


def _markt_mod(db, tag, markt_id):
    """Werte des Mods zum Markt (RG2 markt, neuester Monat): Nahrungsbestand usw. – {} ohne Daten."""
    if markt_id is None:
        return {}
    r = db.execute("SELECT werte FROM monat_extra WHERE tag=? AND art='a.markt' AND schluessel=? ORDER BY jahr DESC, monat DESC "
                   "LIMIT 1", (tag, str(markt_id))).fetchone()
    return json.loads(r[0]) if r else {}


def _views(last):
    """Alle Marktbilder der Momentaufnahme: {id als Text: Markt} – Heimatmarkt, Märkte mit eigenen Orten/Händlern, Reichweite."""
    out = {}
    for m in ([last["markt"]] if last.get("markt") else []) + list(last.get("maerkte") or []) + list(last.get("fremde_maerkte") or []):
        if m.get("id") is not None:
            out.setdefault(str(m["id"]), m)
    return out


def _gut(view, g):
    return next((x for x in (view or {}).get("gueter") or [] if x.get("gut") == g), None)


def kapazitaet(last):
    """Unsere Händlerkapazität je Markt laut Spielstand (Markt merchant: capacity, used): {id: {markt, kapazitaet, genutzt, frei}}."""
    me, tag = last["meta"].get("land_id"), last["meta"].get("tag")
    out = {}
    for mid, m in _views(last).items():
        h = next((x for x in m.get("haendler") or [] if (me is not None and x.get("land_id") == me) or x.get("tag") == tag), None)
        if h and _num(h.get("kapazitaet")):
            g = h.get("genutzt") if _num(h.get("genutzt")) else 0.0
            out[mid] = {"markt": m.get("zentrum") or mid, "kapazitaet": _r(h["kapazitaet"]), "genutzt": _r(g),
                        "frei": _r(max(0.0, h["kapazitaet"] - g))}
    return out


def _tarif(last, markt_id, gut):
    """Ausfuhrzoll des Besitzers eines Markts auf ein Gut laut Spielstand: (Land, Satz) – Ausfuhren aus diesem Markt zahlen ihn
    (Gegenprobe 27.10.). Eigener Markt oder kein Satz: (Land, None)."""
    z = last.get("zoelle") or {}
    b = (z.get("markt_besitzer") or {}).get(str(markt_id))
    if not b or b == last["meta"].get("tag"):
        return b, None
    return b, (((z.get("laender") or {}).get(b) or {}).get("goods_export_tariffs") or {}).get(gut)


def _lage(x):
    """Lage eines Guts im Markt: Preis, Angebot, Nachfrage, Vorrat, Saldo (Angebot − Nachfrage)."""
    if not x:
        return None
    a, n = x.get("angebot"), x.get("nachfrage")
    return {"preis": _r(x.get("preis")), "angebot": _r(a), "nachfrage": _r(n), "vorrat": _r(x.get("vorrat")),
            "saldo": _r((a or 0) - (n or 0)) if _num(a) or _num(n) else None}


def _vergleich(views, mid, g, preis):
    """Märkte in Reichweite (ohne den eigenen) mit Preis: billiger mit Angebot, teurer mit Nachfrage – je höchstens 3."""
    billig, teuer = [], []
    for k, m in views.items():
        y = _gut(m, g)
        if k == mid or not y or not _num(y.get("preis")) or y["preis"] <= 0 or not _num(preis):
            continue
        e = {"id": int(k) if k.isdigit() else k, "markt": m.get("zentrum") or k, "preis": _r(y["preis"]),
             "angebot": _r(y.get("angebot")), "nachfrage": _r(y.get("nachfrage"))}
        if y["preis"] < preis and (y.get("angebot") or 0) > 0:
            billig.append(e)
        elif y["preis"] > preis and (y.get("nachfrage") or 0) > 0:
            teuer.append(e)
    return sorted(billig, key=lambda e: e["preis"])[:3], sorted(teuer, key=lambda e: -e["preis"])[:3]


def _de(v, d=2):
    return sprache.ziffern(f"{v:,.{d}f}")


def pruefung(db, last, hz, nm):
    """Prüfung unserer Handelsbestellungen (Spielstand ab Format 16) mit Routen live und je Monat (Daten-Mod):
    {kapazitaet: {Markt: …}, bestellungen: [{id, markt, kap, bestellung/automatik (Gewinn je Kapazität), zoll_anteil, modus,
    gueter: [{gut, richtung, routen, je_kap, monate, ohne_seit, nie, letzte, lage, billiger, teurer, zoll_satz, befund}]}]}."""
    sp = hz.get("spielstand") or {}
    kap = kapazitaet(last)
    out = {"kapazitaet": kap, "bestellungen": []}
    if not sp.get("bestellungen"):
        return out
    tag = last["meta"]["tag"]
    views = _views(last)
    monate = routen_monate(db, tag)
    live = {str(x["id"]): x for x in hz.get("routen") or []}
    roh = {str(e.get("id")): e for e in ((last.get("handelsbestellungen") or {}).get("unsere") or [])}
    ref = {}
    for t in last.get("handel_spielstand") or []:
        if t.get("trade_order_ref") is not None:
            ref.setdefault(str(t["trade_order_ref"]), []).append(str(t["id"]))
    datum = last["meta"].get("datum")
    for b in sp["bestellungen"]:
        mid = str(b.get("markt"))
        mname = b.get("markt_name") or mid
        view = views.get(mid) or {}
        rb = [live[r] for r in ref.get(str(b["id"]), []) if r in live]
        auto = [x for x in hz.get("routen") or [] if x.get("herkunft") == "automatik" and mid in (str(x.get("von")), str(x.get("nach")))]

        def summe(rs):
            k, g = sum(x.get("kapazitaet") or 0 for x in rs), sum(x.get("gewinn") or 0 for x in rs)
            return {"routen": len(rs), "kapazitaet": _r(k), "gewinn": _r(g), "je_kap": _je_kap(rs, "genutzt", "kapazitaet")}
        bs = summe(rb)
        zoll = sum(x["zoll"] for x in rb if _num(x.get("zoll")))
        vor = (bs["gewinn"] or 0) - zoll
        r0 = roh.get(str(b["id"])) or {}
        gueter = []
        for g in b.get("gueter") or []:
            gut, ein = g.get("gut"), g.get("richtung") == "einfuhr"

            def passt(x):
                return x.get("gut") == gut and str(x.get("nach") if ein else x.get("von")) == mid
            rl = [x for x in rb if passt(x)]
            verlauf = [(ym, [x for x in rs if x["bestellung"] and passt(x)]) for ym, rs in monate]
            mit = [(ym, rs) for ym, rs in verlauf if rs]
            ohne = 0
            for ym, rs in reversed(verlauf):
                if rs:
                    break
                ohne += 1
            letzte = None
            if mit:
                ym, rs = mit[-1]
                # (Monat, Gewinn je Kapazität, genutzte Kapazität) – genutzt 0 = Route ohne Handel (Urkorn 1337.9)
                serie = [(_mon(y), _je_kap(r, "genutzt", "kap"),
                          _r(sum(x["genutzt"] for x in r if _num(x.get("genutzt")))) if any(_num(x.get("genutzt")) for x in r) else None)
                         for y, r in mit[-3:]]
                ziel = rs[0].get("von" if ein else "nach")
                letzte = {"monat": _mon(ym), "serie": serie, "markt": (last.get("markt_namen") or {}).get(str(ziel)) or ziel}
            lage = _lage(_gut(view, gut))
            billig, teuer = _vergleich(views, mid, gut, (lage or {}).get("preis"))
            land, satz = _tarif(last, mid, gut) if not ein else (None, None)
            e = {"gut": gut, "gut_name": g.get("gut_name") or gut, "richtung": g.get("richtung"),
                 "routen": [{"id": x["id"], "markt": x.get("von_name" if ein else "nach_name") or x.get("von" if ein else "nach"),
                             "gewinn": x.get("gewinn"), "kapazitaet": x.get("kapazitaet"), "je_kap": x.get("je_kap"),
                             "zoll": x.get("zoll")} for x in rl],
                 "je_kap": _je_kap(rl, "genutzt", "kapazitaet"),
                 "monate": len(verlauf), "von": _mon(verlauf[0][0]) if verlauf else None,
                 "bis": _mon(verlauf[-1][0]) if verlauf else None, "mit_route": len(mit), "ohne_seit": ohne,
                 "nie": bool(verlauf) and not mit, "letzte": letzte, "lage": lage, "billiger": billig, "teurer": teuer,
                 "zoll_land": land, "zoll_satz": satz}
            e["befund"] = _befund(e, mname, b.get("mindestgewinn"), datum, nm)
            gueter.append(e)
        out["bestellungen"].append({
            "id": b["id"], "markt": b.get("markt"), "markt_name": mname, "kap": kap.get(mid),
            "bestellung": bs, "automatik": summe(auto),
            "zoll": _r(zoll), "zoll_anteil": _r(-zoll / vor, 4) if vor > 0 and zoll < 0 else 0.0 if vor > 0 else None,
            "mindestgewinn": b.get("mindestgewinn"), "anteil": b.get("anteil"), "kapazitaet_bestellung": b.get("kapazitaet"),
            # Felder, die das Spielprogramm kennt (eu5.exe), die in der Bestellung des Nutzers (1338.4.7) aber fehlen – vermutlich
            # Standardwerte; welche, ist offen
            "modus": r0.get("trade_order_mode"),
            "maerkte_angepasst": any(k in r0 for k in ("trade_order_import_markets", "trade_order_export_markets",
                                                       "trade_order_import_market_groups", "trade_order_export_market_groups")),
            "gueter": gueter})
    return out


def _befund(e, mname, mindest, datum, nm):
    """Belegte Gründe zu einer Ware einer Bestellung (deutsch, mit Zahlen und Quelle) – Seite und Empfehlung."""
    out = []
    ein = e["richtung"] == "einfuhr"
    if e["routen"]:
        r = e["routen"][0]
        out.append(f"Route live {'aus' if ein else 'nach'} {r['markt']}: Gewinn je Händlerkapazität "
                   f"{_de(e['je_kap']) if _num(e['je_kap']) else '–'} (Daten-Mod).")
    elif e["nie"]:
        out.append(f"In keinem der {e['monate']} Monate mit Daten-Mod ({e['von']}–{e['bis']}) eine Route dieser Bestellung.")
    elif e["letzte"]:
        L = e["letzte"]
        werte = [(m, v) for m, v, gen in L["serie"] if _num(v) and gen != 0]
        leer = [m for m, v, gen in L["serie"] if gen == 0]
        t = f"Letzte Route im {L['monat']} {'aus' if ein else 'nach'} {L['markt']}"
        if werte:
            t += ", Gewinn je Händlerkapazität " + " → ".join(f"{_de(v)} ({m})" for m, v in werte)
        if leer:
            t += f"; im {', '.join(leer)} nichts gehandelt (genutzte Kapazität 0)"
        if _num(mindest) and werte and werte[-1][1] < mindest:
            t += f" – zuletzt unter dem Mindestgewinn {_de(mindest)} der Bestellung"
        out.append(t + f"; seit {e['ohne_seit']} Monat(en) keine Route (Daten-Mod).")
    lg = e["lage"]
    if lg and _num(lg.get("angebot")) and _num(lg.get("nachfrage")):
        a, n = lg["angebot"], lg["nachfrage"]
        if ein:
            out.append(f"{mname}: Angebot {_de(a)} ≥ Nachfrage {_de(n)} – kein Bedarf (Spielstand {datum})." if a >= n
                       else f"{mname}: Nachfrage {_de(n)} > Angebot {_de(a)} (Spielstand {datum}).")
        else:
            out.append(f"{mname}: Nachfrage {_de(n)} > Angebot {_de(a)} – eine Ausfuhr verschärft die Knappheit (Spielstand {datum})."
                       if n > a else f"{mname}: Überschuss {_de(a - n)} (Angebot {_de(a)}, Nachfrage {_de(n)}; Spielstand {datum}).")
    if lg and _num(lg.get("preis")):
        liste = e["billiger"] if ein else e["teurer"]
        if liste:
            out.append(f"{'Billiger' if ein else 'Teurer'} in Märkten in Reichweite: "
                       + ", ".join(f"{x['markt']} {_de(x['preis'])}" for x in liste) + f" (hier {_de(lg['preis'])}; Spielstand).")
        else:
            out.append(f"Kein Markt in Reichweite {'billiger mit Angebot' if ein else 'teurer mit Nachfrage'} "
                       f"(hier {_de(lg['preis'])}; Spielstand) – weitere Märkte erreicht das Spiel trotzdem.")
    if not ein and _num(e.get("zoll_satz")) and e["zoll_satz"] > 0:
        out.append(f"Ausfuhrzoll {nm(e['zoll_land'])} auf {e['gut_name']}: {_de(e['zoll_satz'] * 100, 1)} % (Spielstand).")
    return out


def vorschlaege(hz, wp, last, nm, markt_mod=None):
    """Vorschläge für Handelsbestellungen je Schwerpunkt des Wirtschaftsplans (Heimatmarkt; Märkte in Reichweite laut Spielstand):
    {markt_id, markt, kapazitaet, hinweise, fokusse: {fk: {name, richtung, modus, eintrag, hinweise, eintraege, ausgelassen}}}.
    Einfuhr: Gut des Schwerpunkts (Veredelung: Eingangsgut der Ketten) mit Nachfrage > Angebot × 1,05 und Fehlmenge ≥ 0,1 im
    Heimatmarkt; Quelle = Markt mit Angebot und Vorteil nach Zoll ≥ Händlerunterhalt, Märkte mit Überschuss zuerst, dann der größte
    Vorteil. Ausfuhr: Gut mit Angebot > Nachfrage × 1,05 und Überschuss ≥ 0,1; Ziel = teuerster Markt mit Nachfrage. Keine
    Vorschläge ohne Preis im Heimatmarkt; ausgelassene Güter mit Grund."""
    heim = last.get("markt") or {}
    if not wp or not wp.get("fokusse") or heim.get("id") is None:
        return {}
    df = hz.get("defines_handel") or {}
    G = wp.get("gueter") or {}
    hid = str(heim["id"])
    views = _views(last)
    hv = {x.get("gut"): x for x in heim.get("gueter") or []}
    kap = kapazitaet(last).get(hid)
    hname = heim.get("zentrum") or hid
    bestand = {}
    for b in (hz.get("spielstand") or {}).get("bestellungen") or []:
        if str(b.get("markt")) == hid:
            for g in b.get("gueter") or []:
                bestand.setdefault(g.get("gut"), []).append((b["id"], g.get("richtung")))
    pr = {str(p["id"]): p for p in (hz.get("pruefung") or {}).get("bestellungen") or []}

    def route_da(bid, gut):
        p = pr.get(str(bid)) or {}
        return any(e["gut"] == gut and e["routen"] for e in p.get("gueter") or [])

    hinweise = []
    min_tc = df.get("TRADE_ORDER_MIN_TRADE_CAPACITY", 0.1)
    # kleinste Fehl- bzw. Überschussmenge (Güter-Einheiten) für einen Vorschlag: so groß wie die kleinste Kapazität einer neuen
    # Bestellungsroute (Define TRADE_ORDER_MIN_TRADE_CAPACITY 0,1) – Regel des Ratgebers gegen Kleinstmengen (Oliven 0,0001)
    min_menge = min_tc
    # kleinster Vorteil je Einheit nach Zoll: der Händlerunterhalt je Kapazität (NCountry.MERCHANT_MAINTENANCE_COST 0,25; Unterhalt
    # einer Route = genutzte Kapazität × 0,25, nachgerechnet 29.10. an allen 27 Routen-Monaten der Walachei 1337.5–1338.4, z. B.
    # Wolle 5,86 → 1,465, Urkorn 1337.8 genutzt 0,857 (zugewiesen 1,352) → 0,214). Braucht eine Einheit mindestens 1 Kapazität
    # (Routen der Walachei 1338.4: Feinstoff nach Kraków 1,00, Wolle nach Brügge 2,73 je Einheit), deckt ein kleinerer Vorteil
    # nicht einmal den Unterhalt – Regel des Ratgebers
    min_netto = df.get("MERCHANT_MAINTENANCE_COST", 0.25)
    # Vorlagen mit „Min. Gewinn“ (Gewinnschwerpunkt): Gewinn je Kapazität ≈ Vorteil je Einheit ÷ Kapazität je Einheit − Unterhalt
    # (Unterhalt und Gewinn je Kapazität nachgerechnet, s. o.) – den Mindestgewinn 0,25 erreicht eine Route bei mindestens 1 Kapazität
    # je Einheit erst ab Vorteil ≥ Mindestgewinn + Unterhalt = 0,5 (Prüfer 29.10.; Regel des Ratgebers, „mindestens 1 Kapazität je
    # Einheit“ beobachtet, nicht belegt)
    min_profit = min_netto + (df.get("DEFAULT_TRADE_ORDER_MIN_PROFIT") or 0.25)

    def schwelle_txt(s):
        return (f"unter Mindestgewinn {_de(s - min_netto)} + Händlerunterhalt {_de(min_netto)} je Kapazität (bei mindestens 1 "
                "Kapazität je Einheit)" if s > min_netto else f"unter dem Händlerunterhalt {_de(min_netto)} je Kapazität")
    if not kap:
        hinweise.append(f"Wir haben keine Händlerkapazität im Markt {hname} – das Spiel kann einer Bestellung dort nichts zuordnen "
                        "(Spieltext TRADE_ORDER_NO_TC_IN_MARKET_TT).")
    elif (kap["frei"] or 0) < min_tc:
        teile = [f"Bestellung Nr. {p['id']} {_de(p['bestellung']['kapazitaet'])}" for p in pr.values()
                 if str(p.get("markt")) == hid and _num(p["bestellung"].get("kapazitaet"))]
        hinweise.append(f"Unsere Händlerkapazität in {hname} ist voll genutzt: {_de(kap['genutzt'])} von {_de(kap['kapazitaet'])} "
                        f"(Spielstand{'; davon ' + ', '.join(teile) if teile else ''}). Eine neue Bestellung bekommt Kapazität nach "
                        "Priorität – früher gelistete zuerst (Spieltext TRADE_ORDER_PRIORITY_INFO): vor die bestehende setzen oder "
                        "deren Kapazität senken.")
    hinweise.append("Gewinn je Händlerkapazität einer neuen Route rechnet der Ratgeber nicht vor: die Kapazität je Einheit hängt von "
                    "Entfernung und Gut ab. Das Spiel zeigt ihn in der Bestellung (beste Route mit Gewinn je Händlerkapazität).")
    # Märkte ohne Preisdaten (nicht in Reichweite laut Daten-Mod) erreicht das Spiel trotzdem – Beleg aus unseren Routen
    aussen = sorted({f"{x.get('gut_name') or x.get('gut')} → {x.get('nach_name') or x.get('nach')}" for x in hz.get("routen") or []
                     if str(x.get("von")) == hid and x.get("nach") is not None and str(x.get("nach")) not in views}
                    | {f"{x.get('gut_name') or x.get('gut')} aus {x.get('von_name') or x.get('von')}" for x in hz.get("routen") or []
                       if str(x.get("nach")) == hid and x.get("von") is not None and str(x.get("von")) not in views})
    if aussen:
        hinweise.append("Verglichen werden nur Märkte mit Preisen im Spielstand (Märkte in Reichweite laut Daten-Mod); das Spiel "
                        "handelt auch mit anderen – unsere Route(n) " + ", ".join(aussen) + " (Daten-Mod).")

    def zeile(gut, richtung, anteil, k, m, y, p, a, n, land, satz, netto, weitere, fuer=None):
        dort = y["preis"]
        return {"gut": gut, "gut_name": (G.get(gut) or {}).get("name") or nm(gut), "richtung": richtung, "anteil": _r(anteil, 4),
                "fuer": fuer, "fuer_name": ((G.get(fuer) or {}).get("name") or nm(fuer)) if fuer else None,
                "markt_id": int(k) if k.isdigit() else k, "markt": m.get("zentrum") or k, "preis_hier": _r(p), "preis_dort": _r(dort),
                "vorteil": _r(abs(p - dort)), "vorteil_anteil": _r(abs(p - dort) / p, 4), "netto": _r(netto),
                "angebot_hier": _r(a), "nachfrage_hier": _r(n), "angebot_dort": _r(y.get("angebot")),
                "nachfrage_dort": _r(y.get("nachfrage")), "zoll_land": land, "zoll_land_name": nm(land) if land else None,
                "zoll_satz": satz, "weitere": weitere}

    def preis_hier(gut):
        x = hv.get(gut)
        p = x.get("preis") if x and _num(x.get("preis")) and x["preis"] > 0 else None
        return x, p

    def einfuhr(gut, anteil, fuer=None, schwelle=min_netto):
        """Nachfrage > Angebot × 1,05 und Fehlmenge ≥ Mindestmenge im Heimatmarkt; Quelle: Markt mit Angebot und Preisvorteil
        nach dem Ausfuhrzoll ihres Besitzers (Satz × Einkaufswert, nachgerechnet 29.10.) – Märkte mit Überschuss zuerst."""
        x, p = preis_hier(gut)
        if not p:
            return None, "kein Preis im Heimatmarkt"
        a, n = x.get("angebot") or 0, x.get("nachfrage") or 0
        if a >= n:
            return None, "ausreichend (Angebot ≥ Nachfrage)"
        if n - a < min_menge:
            return None, f"Fehlmenge {_de(n - a)} unter {_de(min_menge, 1)}"
        if not n > a * KNAPP_FAKTOR:
            return None, "kaum knapp (Nachfrage unter Angebot × 1,05)"
        q = []
        for k, m in views.items():
            y = _gut(m, gut)
            if k == hid or not y or not _num(y.get("preis")) or not 0 < y["preis"] < p or not (y.get("angebot") or 0) > 0:
                continue
            land, satz = _tarif(last, k, gut)
            netto = p - y["preis"] - (satz or 0) * y["preis"]
            q.append((k, m, y, land, satz, netto))
        if not q:
            return None, "kein Markt in Reichweite mit Angebot billiger"
        pos = sorted((t for t in q if t[5] >= schwelle),
                     key=lambda t: ((t[2].get("angebot") or 0) <= (t[2].get("nachfrage") or 0), -t[5]))
        if not pos:
            best = max(q, key=lambda t: t[5])
            return None, (f"Vorteil nach Zoll höchstens {_de(best[5])} ({best[1].get('zentrum') or best[0]}) – "
                          + schwelle_txt(schwelle))
        k, m, y, land, satz, netto = pos[0]
        return zeile(gut, "einfuhr", anteil, k, m, y, p, a, n, land, satz, netto, len(pos) - 1, fuer), None

    def ausfuhr(gut, anteil, schwelle=min_netto):
        """Angebot > Nachfrage × 1,05 und Überschuss ≥ Mindestmenge im Heimatmarkt; Ziel: teuerster Markt mit Nachfrage, Vorteil
        nach dem Ausfuhrzoll des Besitzers unseres Markts (Satz × Einkaufswert)."""
        x, p = preis_hier(gut)
        if not p:
            return None, "kein Preis im Heimatmarkt"
        a, n = x.get("angebot") or 0, x.get("nachfrage") or 0
        if not (a > n * KNAPP_FAKTOR and a - n >= min_menge):
            return None, "kein Überschuss (Angebot ≤ Nachfrage × 1,05 oder unter " + _de(min_menge, 1) + ")"
        z = [(k, m, y) for k, m in views.items() if k != hid and (y := _gut(m, gut)) and _num(y.get("preis")) and y["preis"] > p
             and (y.get("nachfrage") or 0) > 0]
        if not z:
            return None, "kein Markt in Reichweite mit Nachfrage teurer"
        k, m, y = max(z, key=lambda t: t[2]["preis"])
        land, satz = _tarif(last, hid, gut)
        netto = y["preis"] - p - (satz or 0) * p
        if netto < schwelle:
            return None, (f"Vorteil nach Zoll {_de(netto)} ({m.get('zentrum') or k} {_de(y['preis'])}, hier {_de(p)}"
                          + (f", Ausfuhrzoll {nm(land)} {_de(satz * 100, 0)} %" if satz else "")
                          + ") – " + schwelle_txt(schwelle))
        return zeile(gut, "ausfuhr", anteil, k, m, y, p, a, n, land, satz, netto, len(z) - 1), None

    # Nahrungsschwerpunkt: wirkt nur, wenn der Markt ohne die Bestellung Nahrung verliert UND unter 60 % Bestand hat – liefert also
    # nichts, sobald eins davon nicht zutrifft (Prüfer 29.10.; ob unter 40 %, TRADE_ORDER_FOOD_GROWTH_STOCKPILE_FRACTION, auch ohne
    # Nahrungsverlust aufgefüllt wird, ist offen)
    mm = markt_mod or {}
    voll = mm.get("market_food_percentage") if _num(mm.get("market_food_percentage")) else (
        mm["GetFoodStockpilePercent"] / 100 if _num(mm.get("GetFoodStockpilePercent")) else None)
    bilanz = mm.get("GetMonthlyFoodBalance")
    food_frac = df.get("TRADE_ORDER_FOOD_MAINTAIN_STOCKPILE_FRACTION", 0.6)
    food_aus = _num(voll) and _num(bilanz) and (voll >= food_frac or bilanz >= 0)

    out = {"markt_id": heim["id"], "markt": hname, "kapazitaet": kap, "hinweise": hinweise, "fokusse": {}}
    for fk, F in wp["fokusse"].items():
        richtung, modus, eintrag = VORLAGEN.get(fk, ("einfuhr", "needs", None))
        fh = []
        if modus == "food" and food_aus:
            grund = (f"Nahrungsbestand {_de(voll * 100, 0)} % (ab {_de(food_frac * 100, 0)} % gilt ein Markt als versorgt, Define "
                     "TRADE_ORDER_FOOD_MAINTAIN_STOCKPILE_FRACTION)" if voll >= food_frac else
                     f"der Markt verliert keine Nahrung ({'+' if bilanz > 0 else ''}{_de(bilanz, 1)} je Monat, Daten-Mod)")
            fh.append(f"Der Nahrungsschwerpunkt liefert derzeit nichts nach {hname}: {grund}. Für einzelne knappe Nahrungsgüter den "
                      "Knappheitsschwerpunkt nehmen.")
            modus = "needs"
        rows, aus = [], []
        schwelle = min_profit if modus == "profit" else min_netto
        if fk == "import":                    # Veredelung: Eingangsgüter der Fertigwaren mit Einkaufsvorteil
            kand, gesehen = [], set()
            for r in F.get("gueter") or []:
                for a in (F.get("ketten") or {}).get(r["gut"]) or []:
                    for pm in ((wp.get("gebaeude") or {}).get(a) or {}).get("pms") or []:
                        if pm.get("produziert") != r["gut"]:
                            continue
                        for i in pm.get("eingang") or {}:
                            if i not in gesehen:
                                gesehen.add(i)
                                kand.append((i, r["anteil"], r["gut"]))
        else:
            kand = [(r["gut"], r["anteil"], None) for r in F.get("gueter") or []]
        for gut, anteil, fuer in kand:
            if len(rows) >= MAX_VORSCHLAEGE:
                break
            if richtung == "einfuhr":
                e, grund = einfuhr(gut, anteil, fuer, schwelle)
            else:
                e, grund = ausfuhr(gut, anteil, schwelle)
            if not e:
                gg = [(bid, rr) for bid, rr in bestand.get(gut, []) if rr != richtung]
                aus.append({"gut": gut, "gut_name": (G.get(gut) or {}).get("name") or nm(gut),
                            "grund": grund + (f"; Bestellung Nr. {gg[0][0]} führt es {'aus' if gg[0][1] == 'ausfuhr' else 'ein'}"
                                              if gg else "")})
                continue
            gleich = [bid for bid, rr in bestand.get(gut, []) if rr == richtung]
            gegen = [(bid, rr) for bid, rr in bestand.get(gut, []) if rr != richtung]
            if gleich:
                e["bestellung"] = {"art": "gleich", "id": gleich[0], "route": route_da(gleich[0], gut)}
            elif gegen:
                e["bestellung"] = {"art": "gegen", "id": gegen[0][0], "richtung": gegen[0][1], "route": route_da(gegen[0][0], gut)}
            rows.append(e)
        mtxt = MODI[modus]
        if fk == "import" and any(x["grund"] == "ausreichend (Angebot ≥ Nachfrage)" for x in aus):
            fh.append("Eingangsgüter, von denen der Heimatmarkt genug hat, erst einführen, wenn der Veredelungsbetrieb steht – vorher "
                      "gibt es keinen Bedarf.")
        out["fokusse"][fk] = {
            "name": F.get("name"), "richtung": richtung,
            "bestellart": "Einfuhrbestellung" if richtung == "einfuhr" else "Ausfuhrbestellung",
            "modus": {"key": modus, "name": mtxt[0], "loc": mtxt[1],
                      "text": mtxt[2].format(food=_de(food_frac * 100, 0) + " %",
                                             needs=_de(df.get("TRADE_ORDER_NEEDS_STOCKPILE_EXCLUSION_FRACTION", 0.1) * 100, 0) + " %")},
            "eintrag": ({"key": eintrag, "name": EINTRAEGE[eintrag][0], "loc": EINTRAEGE[eintrag][1], "text": EINTRAEGE[eintrag][2]}
                        if eintrag and not (eintrag == "any_food" and food_aus) else None),
            "mindestgewinn": df.get("DEFAULT_TRADE_ORDER_MIN_PROFIT") if modus == "profit" else None,
            "schwelle": schwelle, "food_aktiv": modus == "food",
            "nahrung": {"bestand": voll, "bilanz": bilanz, "grenze": food_frac} if fk == "bevoelkerung" else None,
            "hinweise": fh, "eintraege": rows, "ausgelassen": aus[:12]}
    return out
