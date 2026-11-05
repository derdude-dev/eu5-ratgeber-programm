"""Momentaufnahme des Spieler-Landes aus einem Spielstand - Wirtschaft zuerst.

Feldbedeutungen, die am Spielstand geprüft sind (Walachei 1479):
  economy.monthly_gold    Einkommen der letzten 12 Monate (letzter Wert = economy.income)
  economy.recent_balance  Saldo der letzten 12 Monate (letzter Wert = income - expense)
  historical_population / historical_tax_base   ein Wert je Jahr seit 1337
  government.estates      Stand -> ID in estate_manager/database
  economy.tax_rates       tatsächlicher Steuersatz = estate_tax / estate_taxable_income (Mod-Test Holland 1337.7)
  monthly_trade_balance   = monthly_trade_income (Mod-Test)
"""
import json
import re
from collections import defaultdict

from . import gruendung, pdx

COUNTRY_LAST_MONTH = (
    "last_month_gold_income", "last_months_tax_income", "last_months_subject_tax",
    "last_months_foreign_building_income", "monthly_trade_value", "monthly_trade_balance",
    "last_months_army_maintenance", "last_months_navy_maintenance", "last_months_fort_maintenance",
    "last_months_building_maintenance", "last_months_mercenary_maintenance", "last_months_sailor_expense",
    "last_months_population",
)
# last_months_subject_tax ist KEIN Einkommen: Frankreich 426,6 bei 32,8 Gesamteinkommen; Holland 11,06 ~ Steuerbasis
# des Untertanen Zeeland (10,7). Wird deshalb nur als "Steuerbasis der Untertanen (vermutlich)" gezeigt.
CURRENCY = ("gold", "stability", "prestige", "inflation", "war_exhaustion", "manpower", "sailors",
            "government_power", "army_tradition", "navy_tradition", "religious_influence")
ESTATE_FIELDS = ("satisfaction", "gold", "balance", "wealth_impact")


def played_countries(save):
    out = []
    for key, s, e in save.children.get("", []):
        if key == "played_country":
            out.append(pdx.parse_block(save.data[s:e]))
    return out


def find_player_country(save, names, player=None):
    """Land-ID des Spielers: über den Spielernamen, sonst eindeutig, sonst über metadata."""
    pcs = played_countries(save)
    if player:
        hits = {p["country"] for p in pcs if p.get("name") == player}
        if len(hits) == 1:
            return hits.pop()
        raise ValueError(f"Spieler {player!r} nicht eindeutig gefunden: {hits}")
    ids = {p["country"] for p in pcs}
    if len(ids) == 1:
        return ids.pop()
    tags = save.block("countries/tags")
    want = save.meta.get("player_country_name")
    hits = [i for i in ids if names(tags.get(i)) == want]
    if len(hits) == 1:
        return hits[0]
    raise ValueError(f"Spieler-Land nicht eindeutig: Kandidaten {sorted(ids)} - Spielername angeben")


def _num(v):
    return v if isinstance(v, (int, float)) else None


# Werte-Variablen stehen als ganze Zahl in data.identity. Skalierung vermutlich 100000
# (num_of_explorations = 800000). Probe: der Daten-Mod setzt rg_mod_version = 1.
VAR_SCALE = 100000


def mod_variables(country):
    """rg_*-Variablen des Daten-Mods -> {name: wert}; leer, wenn der Mod nicht lief."""
    out = {}
    for v in (country.get("variables") or {}).get("data") or []:
        name = v.get("flag", "") if isinstance(v, dict) else ""
        d = v.get("data") if isinstance(v, dict) else None
        if name.startswith("rg_") and isinstance(d, dict) and d.get("type") == "value":
            out[name] = d.get("identity", 0) / VAR_SCALE
    if out and out.get("rg_mod_version") != 1:
        raise ValueError(f"Skalierung der Variablen stimmt nicht: rg_mod_version = {out.get('rg_mod_version')} "
                         f"(erwartet 1 bei Faktor {VAR_SCALE})")
    return out


# Ortsliste im Spielstand (meta compatibility.locations): Orts-ID n steht an Index n-1 (die Liste beginnt bei ID 1).
# Geprüft 29.09. an Spieltexten: ID 804 = „Steuergrundlage von Amsterdam“, Liste[803] = amsterdam; 8 von 8 Orten.
# Vorher Index = ID -> alle Ortsnamen und Marktzentren um eins verschoben (Brugge hieß „Cassel“).
def loc_key(locnames, lid):
    return locnames[lid - 1] if isinstance(lid, int) and 0 < lid <= len(locnames) else None


def build(save, names, player=None, fremde=None):
    """fremde: Funktion tag -> Markt-IDs in Handelsreichweite (Daten-Mod ab 0.17); diese Märkte kommen mit vollem
    Marktbild nach fremde_maerkte (Kacheln „Fremde Märkte in Reichweite“, zuschaltbar)."""
    cid = find_player_country(save, names, player)
    c = save.entry("countries/database", cid)
    tag = save.block("countries/tags").get(cid)
    locnames = save.meta["compatibility"]["locations"]
    eco = c.get("economy", {})
    cur = c.get("currency_data", {})

    snap = {
        "meta": {
            # Datum kann eine Stunde tragen ("1338.3.9.4", Autosave beim Beenden) -> auf J.M.T kürzen
            "datum": ".".join(str(save.meta.get("date")).split(".")[:3]),
            "datum_roh": save.meta.get("date"), "version": save.meta.get("version"),
            "partie_id": save.meta.get("playthrough_id"), "partie": save.meta.get("playthrough_name"),
            "land_id": cid, "tag": tag, "land": names(tag),
            "spielstand": save.path.replace("\\", "/").rsplit("/", 1)[-1],
            "zeitalter": save.top_scalar("current_age"),          # ab Format 11 (Wirtschaftsplan: Einheiten des Zeitalters)
            # ab Format 12 (Bauplan): Regierungsform – Fortschritte mit government = … (z. B. steppe_horde) nur dafür
            "regierungsform": ((c.get("government") or {}).get("type") if isinstance(c.get("government"), dict) else None),
        },
        "wirtschaft": {
            "einkommen": _num(eco.get("income")),
            "ausgaben": _num(eco.get("expense")),
            "saldo": (eco["income"] - eco["expense"]) if _num(eco.get("income")) is not None
                     and _num(eco.get("expense")) is not None else None,
            "einkommen_12_monate": eco.get("monthly_gold"),
            "saldo_12_monate": eco.get("recent_balance"),
            "kreditrahmen": eco.get("loan_capacity"),
            "muenzpraegung": eco.get("coin_minting"),
            "stabilitaets_investition": eco.get("stability_investment"),
            "unterhalt_regler": eco.get("maintenances"),
            "steuersaetze": eco.get("tax_rates"),
            "schulden": {k: eco[k] for k in ("total_debt", "estate_debt", "foreign_debt") if k in eco},
            "letzter_monat": {k: c[k] for k in COUNTRY_LAST_MONTH if k in c},
            "produziert_letzter_monat": c.get("last_month_produced"),
        },
        "ressourcen": {k: cur[k] for k in CURRENCY if k in cur},
        "verlauf_jahre": {
            "bevoelkerung": c.get("historical_population"),
            "steuerbasis": c.get("historical_tax_base"),
        },
    }

    mv = mod_variables(c)
    snap["mod_daten"] = mv
    if mv:
        snap["wirtschaft"]["mod"] = {k[3:]: mv.get(k) for k in
                                     ("rg_income", "rg_balance", "rg_trade_income", "rg_trade_and_tax", "rg_tax_base")}

    # Stände
    staende = []
    for etype, eid in (c.get("government", {}).get("estates") or {}).items():
        e = save.entry("estate_manager/database", eid) or {}
        if e.get("existence") != "yes":
            continue
        row = {"stand": etype, "name": names(etype), "id": eid}
        row.update({k: e.get(k) for k in ESTATE_FIELDS})
        row["steuersatz"] = (eco.get("tax_rates") or {}).get(etype)
        row["letzter_monat"] = e.get("last_month")
        if mv:
            row["mod"] = {k: mv.get(f"rg_{k}_{etype}") for k in ("power", "tax", "taxrate", "taxable")}
        staende.append(row)
    snap["staende"] = staende

    # Regierung: Gesellschaftswerte (-999 = nicht aktiv), Privilegien, Gesetze, Reformen, Kabinett
    gov = c.get("government", {})
    snap["gesellschaft"] = {k: v for k, v in (gov.get("societal_values") or {}).items()
                            if isinstance(v, (int, float)) and v > -999}
    snap["privilegien"] = [p.get("object") for p in _items(gov.get("implemented_privileges")) if isinstance(p, dict)]
    snap["gesetze"] = _objects(gov.get("implemented_laws"))
    snap["reformen"] = _objects(gov.get("implemented_reforms"))
    snap["kabinett"] = [_cabinet(save, names, cid) for cid in gov.get("cabinet_entries") or []]

    # Orte
    # ab Format 12 (Bauplan 25.10.): Straßen je Ort aus road_network/roads ({from to type}, 1.348: 1.926 Straßen weltweit,
    # Holland keine), Straße zur Hauptstadt (Feld road_to_capital), Hauptstadt
    strassen = defaultdict(list)
    if "road_network/roads" in save.blocks:
        a, b = save.blocks["road_network/roads"]
        for von, zu, typ in re.findall(rb"from=(\d+)\s+to=(\d+)\s+type=(\w+)", save.data[a:b]):
            strassen[int(von)].append([int(zu), typ.decode()])
            strassen[int(zu)].append([int(von), typ.decode()])
    orte = []
    for lid in c.get("owned_locations") or []:
        L = save.entry("locations/locations", lid) or {}
        orte.append({
            "id": lid, "key": loc_key(locnames, lid), "name": names(loc_key(locnames, lid)), "rang": L.get("rank"),
            "steuer_staende": L.get("estate_tax"), "pops_typen": _pop_types(save, L),
            "kultur": L.get("culture"), "religion": L.get("religion"),
            "kontrolle": L.get("control"), "naehe": L.get("proximity"),
            "entwicklung": L.get("development"), "wohlstand": L.get("prosperity"),
            "steuer": L.get("tax"), "moegliche_steuer": L.get("possible_tax"),
            "rohstoff": L.get("raw_material"), "markt": L.get("market"),
            "marktzugang": L.get("market_access"),
            "pops": len((L.get("population") or {}).get("pops") or []),
            "hauptstadt": lid == c.get("capital"), "strasse_zur_hauptstadt": L.get("road_to_capital") == "yes",
            "strassen": strassen.get(lid, []),
        })
    snap["orte"] = orte

    # Gebäude (Vorfilter über Rohbytes: Besitzer)
    owner = re.compile(rb"\n\towner=%d\n" % cid)
    geb = []
    for bid, raw in save.raw_entries("building_manager/database"):
        if owner.search(raw):
            b = pdx.parse_block(raw)
            geb.append({
                "id": bid, "typ": b.get("type"), "name": names(b.get("type")),
                "stufe": b.get("level"), "ort": names(loc_key(locnames, b["location"])) if "location" in b else None,
                "ort_id": b.get("location"),
                "gewinn": b.get("last_months_profit"), "unterhalt": b.get("upkeep"),
                "beschaeftigt": b.get("employed"), "subventioniert": b.get("subsidized") == "yes",
            })
    snap["gebaeude"] = geb

    # Forschung: der Mod-Wert num_of_advances_researched war 0, der Spielstand listet 25 (Holland 1339.2)
    adv = c.get("researched_advances")
    adv = list(adv) if isinstance(adv, (dict, list)) else []
    snap["forschung"] = {"erforscht": len(adv), "fortschritte": [{"key": a, "name": names(a)} for a in adv],
                         "fortschritt": (c.get("current_research") or {}).get("progress"),
                         "institutionen": list((c.get("institutions") or {}).keys())}

    # Untertanen (diplomacy_manager: dependency first=Oberherr second=Untertan) und laufende Angliederung
    tags = save.block("countries/tags")
    dip = save.raw("diplomacy_manager") if "diplomacy_manager" in save.blocks else b""
    unter = {}
    for m in re.finditer(rb"dependency=\{\s*first=%d\s*second=(\d+)(.*?)\n\t\}" % cid, dip, re.S):
        typ = re.search(rb"object=(\w+)", m.group(2))
        sid = int(m.group(1))
        unter[sid] = {"id": sid, "tag": tags.get(sid), "name": names(tags.get(sid)),
                      "typ": typ.group(1).decode() if typ else None, "typ_name": names(typ.group(1).decode()) if typ else None}
    for m in re.finditer(rb"annex=\{\s*first=%d\s*second=(\d+)\s*start_date=(\S+)\s*monthly=([-\d.]+)\s*progress=([-\d.]+)"
                         % cid, dip):
        u = unter.setdefault(int(m.group(1)), {"id": int(m.group(1)), "tag": tags.get(int(m.group(1)))})
        u["angliederung"] = {"seit": m.group(2).decode(), "monatlich": float(m.group(3)), "fortschritt": float(m.group(4))}
    snap["untertanen"] = list(unter.values())

    # Namen aller Märkte (Zentrum) - für Handelsrouten zwischen fremden Märkten
    snap["markt_namen"] = {}
    for mid_, raw in save.raw_entries("market_manager/database"):
        cm = re.search(rb"\bcenter=(\d+)", raw)
        if cm and loc_key(locnames, int(cm.group(1))):
            snap["markt_namen"][mid_] = names(loc_key(locnames, int(cm.group(1))))

    # Markt der Hauptstadt
    cap = save.entry("locations/locations", c["capital"]) or {}
    mid = cap.get("market")
    m = save.entry("market_manager/database", mid) if mid is not None else None
    if m:
        snap["markt"] = _market_view(save, names, tags, locnames, mid, m)
    # ab Format 5: alle Märkte mit eigenen Orten oder eigenen Händlern (je eine Kachel auf der Seite)
    eigene = {}
    for o in orte:
        if o.get("markt") is not None:
            eigene[o["markt"]] = eigene.get(o["markt"], 0) + 1
    ids = set(eigene)
    has_cid = re.compile(rb"country=%d\b" % cid)
    for mid_, raw in save.raw_entries("market_manager/database"):
        if has_cid.search(raw):              # Vorfilter; genau geprüft unten (Händler mit Macht oder Kapazität)
            ids.add(int(mid_))
    snap["maerkte"] = []
    for mid_ in ids:
        mm = snap["markt"] if mid_ == mid and m else None
        if mm is None:
            e = save.entry("market_manager/database", mid_)
            if not e:
                continue
            mm = _market_view(save, names, tags, locnames, mid_, e)
        ours = next((h for h in mm["haendler"] if h["land_id"] == cid), None)
        if not eigene.get(mid_) and not (ours and ((ours["macht"] or 0) > 0 or (ours["kapazitaet"] or 0) > 0)):
            continue
        snap["maerkte"].append({**mm, "heimat": mid_ == mid, "eigene_orte": eigene.get(mid_, 0)})
    snap["maerkte"].sort(key=lambda x: (not x["heimat"], -x["eigene_orte"], x["zentrum"] or ""))
    # ab 02.10.: fremde Märkte in Handelsreichweite (ohne die eigenen Marktkacheln oben); fremde_ids = angefragte Liste,
    # daran erkennt der Wächter, ob die Momentaufnahme zur aktuellen Reichweite passt
    eigene_ids = {x["id"] for x in snap["maerkte"]}
    snap["fremde_ids"] = sorted(fremde(tag) if fremde else [])
    snap["fremde_maerkte"] = []
    for mid_ in snap["fremde_ids"]:
        if mid_ in eigene_ids:
            continue
        e = save.entry("market_manager/database", mid_)
        if e:
            snap["fremde_maerkte"].append({**_market_view(save, names, tags, locnames, mid_, e), "heimat": False,
                                           "eigene_orte": 0, "fremd": True})
    # ab Format 9: Marinepräsenz des Landes je Seezone (maritime_manager/objects, presences = { {power country} … }). Teil des
    # Handelsvorteils: Tooltip des Spiels „Marinepräsenz +10,15“ ≈ Summe 201,0 × merchant_power_from_maritime 0,05 (30.09.)
    snap["seepraesenz"] = []
    pres = re.compile(rb"power=([-\d.]+)\s*country=%d\b" % cid)
    for sid, raw in save.raw_entries("maritime_manager/objects"):
        pm = pres.search(raw)
        if pm:
            key = loc_key(locnames, sid)
            snap["seepraesenz"].append({"id": sid, "name": names(key) if key else None, "macht": float(pm.group(1))})
    snap["gebaeude_pm"] = _active_pms(save, cid)
    # ab Format 11 (Kachel Wirtschaftsplan, 25.10.): Gewinn je Gebäudeart im Heimatmarkt, in den Märkten mit eigenen Orten/
    # Händlern und in Reichweite sowie weltweit – Spielwert last_months_profit aller Gebäude (auch fremder Länder)
    snap["gebaeude_gewinne"] = gebaeude_gewinne(save, cid, [mid] + [x["id"] for x in snap["maerkte"]] + snap["fremde_ids"])
    # ab Format 10: Krankheiten (Ausbrüche der Welt, Widerstand/Ausbreitung je eigenem Ort, Tote, Schwarzer Tod)
    snap["krankheiten"] = krankheiten(save, names, tags, locnames, cid, c.get("owned_locations") or [],
                                      (m or {}).get("members") if m else None)
    # ab Format 13 (Kriegskachel 25.10.): laufende Kriege mit Seiten, Verlusten, Schlachten, Besetzung, Militär je Teilnehmer
    snap["kriege"] = kriege(save, names, tags, locnames, cid)
    # ab Format 14 (Kachel Nachbarn und Kriegsgelegenheiten 25.10.): Militärauszug aller lebenden Länder (wählbare Länder)
    snap["laender_militaer"] = laender_militaer(save, names, tags)
    # ab Format 15 (Patch 1.4, 27.10.): Zölle (Sätze je Gut, Einnahmen, Marktbesitzer, Meinung), Handelsbestellungen roh,
    # unsere Handelsrouten aus trade_manager roh
    snap["zoelle"] = zoelle(save, tags, cid, [x["id"] for x in snap["maerkte"]])
    snap["handelsbestellungen"] = handelsbestellungen(save, cid)
    snap["handel_spielstand"] = handel_spielstand(save, cid)
    snap["roh"] = roh(save, c, cid)
    # ab Format 17 (Kachel Ländergründung 30.10.): Fakten für die Bedingungen der Gründungen (Spielregel, geduldete Kulturen,
    # Verbündete …) und Besitzer der Orte in ihren geforderten Gebieten – nur Gründungen, die für uns infrage kommen, samt Kette
    # (eu5ratgeber/gruendung.py). Ein Fehler darin soll das Einlesen nicht verhindern.
    try:
        snap["gruendung"] = gruendung.spielstand(save, c, cid, tags, locnames, snap)
    except Exception as e:                       # noqa: BLE001
        snap["gruendung"] = {"fehler": f"{type(e).__name__}: {e}"}
    return snap

# ---------------------------------------------------------------- Zölle und Handelsbestellungen (ab Format 15, 27.10.)
# Geprüft am Spielstand 1.4.4 (Walachei 1337.8.1, 27.10.):
# - Land: goods_export_tariffs = { gut=satz } (Ausfuhrzoll je Gut, 0.2 = 20 %; 100 Länder, kein negativer Satz = Subvention),
#   last_months_tariff_income (93 Länder), last_months_burgher_tariff_revenue (72 Länder, Bedeutung offen),
#   automated_trade_policy_strategy (Balanced = „Ausgewogene Strategie“). Ein Feld für Einfuhrzölle kommt nicht vor – deshalb
#   werden alle Landesfelder mit tariff/trade_polic/trade_order unverändert übernommen (auch künftige).
# - Stand: last_month.tariff_income (Spieltext TARIFF_INCOME_TO_ESTATES „Anteil der Zölle für die Stände“) – steht schon in
#   staende[].letzter_monat.
# - Die Sätze sind die der Routen-Texte: Bulgarien jewelry=0.2 / copper=0.12614 ↔ Trade.GetTariffInfo „Bulgarien verlangt einen
#   20% Zoll auf Ausfuhren von: Schmuck“ / „12% … Kupfer“ (debug.log 1337.8).
# - Marktbesitzer = Besitzer des Marktzentrums (Spielbegriff market_owner); nur er legt Zölle fest (TRADE_POLICIES_TAB_REQUIRES_
#   MARKET). Walachei: Heimatmarkt 10, Zentrum 5795 = Hauptstadt Bulgariens.
# - diplomacy_manager/<A>/relations/<B>.export_tariff_opinion_penalty (932×; Bulgarien, Eintrag Walachei: −2,2935).
# - trade_order_manager/database: Format belegt mit Test 1.4.5 (29.10., Walachei 1338.4.7, eine Bestellung):
#   0={ market=10 trade_order_goods_entry={ { goods=fruit trade_order_is_import=yes } { goods=wool } { goods=millet } }
#   trade_order_min_profit=0.25 trade_order_capacity=100 trade_order_is_percentage=yes trade_order_use_min_profit=yes
#   trade_order_last_edit_month=1 trade_order_last_restructure_month=2 } – ohne Land; das Land verweist mit
#   trade_order_refs={ 0 } darauf. Ohne trade_order_is_import = Ausfuhr (der Spielstand lässt „no“ weg).
#   Routen einer Bestellung in trade_manager: from_trade_order=yes, trade_order_ref=<Nr.>, locked=yes.
# - trade_manager/database = Handelsrouten aller Länder: trade_owner, which (Gut), size = GetAssignedMerchantCapacity,
#   cached = GetActuallyUsedOrAssignedMerchantCapacity, effect = GetDesiredGoodsShipped (Route 16777442: 1,42133 / 0,43806 /
#   1,56826 ↔ Mod 1337.8: 1,421 / 0,438 / 1,568), power, capacity, trade_path …; kein Zoll- oder Auftragsfeld.
ZOLL_FELD = rb"\w*(?:tariff|trade_polic|trade_order)\w*"
_Z_ZENTRUM = re.compile(rb"\bcenter=(\d+)")
_Z_STRAFE = re.compile(rb"export_tariff_opinion_penalty=(-?[\d.]+)")
_Z_KLAMMER = re.compile(rb"[{}]")


def _klammer_ende(raw, auf):
    """Index hinter der Klammer, die die Klammer an Position auf schließt (Blöcke ohne Zeichenketten)."""
    tiefe = 0
    for m in _Z_KLAMMER.finditer(raw, auf):
        tiefe += 1 if m.group() == b"{" else -1
        if tiefe == 0:
            return m.end()
    return len(raw)


def zollfelder(raw, muster=ZOLL_FELD):
    """Felder der obersten Ebene eines Eintrags (Zeile „\\t<feld>=“), deren Name zum Muster passt – unverändert: Blöcke zerlegt
    (goods_export_tariffs → {gut: satz}), sonst der Wert."""
    out = {}
    for m in re.finditer(rb"\n\t(" + muster + rb")=", raw):
        k, i = m.group(1).decode(), m.end()
        if raw[i:i + 1] == b"{":
            v = pdx.parse_block(raw[i:_klammer_ende(raw, i)])
            out[k] = v if v != [] else {}
        else:
            w = re.match(rb"[^\s{}]+", raw[i:])
            out[k] = pdx._atom(w.group()) if w else None
    return out


def _zoll_meinung(save, tags, cid):
    """export_tariff_opinion_penalty im Beziehungsblock: gegen_uns = bei Land A unter unserer Kennung (Bulgarien → Walachei
    −2,29 bei Bulgariens Ausfuhrzöllen auf unsere Routen), von_uns = in unserem Block unter Land B. Laut Spielbegriff Ausfuhrzoll
    „verabscheuen“ Zielländer ihn; wessen Meinung der Wert genau senkt, steht nicht im Spielstand."""
    gegen, von = [], []
    if "diplomacy_manager" not in save.children:
        return {"gegen_uns": gegen, "von_uns": von}
    wir = re.compile(rb"\n\t+%d=\{" % cid)
    for aid, raw in save.raw_entries("diplomacy_manager"):
        if b"export_tariff_opinion_penalty" not in raw:
            continue
        i = raw.find(b"relations={")
        if i < 0:
            continue
        j = _klammer_ende(raw, i + len(b"relations="))
        if aid == cid:
            for bm in re.finditer(rb"\n\t+(\d+)=\{", raw[i:j]):
                a = i + bm.end() - 1
                s = _Z_STRAFE.search(raw[a:_klammer_ende(raw, a)])
                if s:
                    von.append({"tag": tags.get(int(bm.group(1))), "wert": float(s.group(1))})
            continue
        m = wir.search(raw, i, j)
        if m:
            s = _Z_STRAFE.search(raw[m.end() - 1:_klammer_ende(raw, m.end() - 1)])
            if s:
                gegen.append({"tag": tags.get(aid), "wert": float(s.group(1))})
    return {"gegen_uns": sorted(gegen, key=lambda x: x["wert"]), "von_uns": sorted(von, key=lambda x: x["wert"])}


def zoelle(save, tags, cid, unsere_maerkte=()):
    """Zölle laut Spielstand: unsere Landesfelder (Sätze, Einnahmen, Automatisierung), Besitzer aller Märkte ({Markt: Land}),
    Zollfelder jedes Marktbesitzers ({Tag: Felder}), Zollfelder unserer Märkte, Meinungsabzug durch Ausfuhrzölle."""
    eigen = save.raw_entry("countries/database", cid) or b""
    besitzer, besitzer_id = {}, {}
    for mid, raw in save.raw_entries("market_manager/database"):
        z = _Z_ZENTRUM.search(raw)
        o = (save.entry("locations/locations", int(z.group(1))) or {}).get("owner") if z else None
        if isinstance(o, int):
            besitzer[str(mid)] = tags.get(o)
            besitzer_id[str(mid)] = o
    # Zollfelder nach Land-ID: Tags sind im Spielstand nicht eindeutig (1.3.11 MP_WAL_1479: „YUA“ zweimal – Prüfer 27.10.)
    laender = {}
    for o in sorted(set(besitzer_id.values())):
        f = zollfelder(save.raw_entry("countries/database", o) or b"")
        if f and tags.get(o):
            laender[tags[o]] = f
    markt_felder = {}
    for mid in unsere_maerkte:
        f = zollfelder(save.raw_entry("market_manager/database", mid) or b"")
        if f:
            markt_felder[str(mid)] = f
    return {"land": zollfelder(eigen, rb"\w*(?:tariff|trade_polic|trade_order|foreign_export)\w*"),
            "markt_besitzer": besitzer, "laender": laender, "markt_felder": markt_felder,
            "meinung": _zoll_meinung(save, tags, cid)}


def handelsbestellungen(save, cid):
    """Handelsbestellungen aus trade_order_manager/database (1.4), Felder unverändert. Uns zugeordnet über trade_order_refs
    unseres Landes (Format belegt 29.10., siehe oben); der erste fremde Eintrag steht als Beispiel da. None = kein
    trade_order_manager (vor 1.4)."""
    if "trade_order_manager" not in save.blocks:
        return None
    out = {"anzahl_gesamt": 0, "unsere": [], "beispiel": None, "roh": None}
    refs = re.search(rb"\n\ttrade_order_refs=\{([^}]*)\}", save.raw_entry("countries/database", cid) or b"")
    unsere = {int(x) for x in re.findall(rb"\d+", refs.group(1))} if refs else set()
    for oid, raw in save.raw_entries("trade_order_manager/database"):
        out["anzahl_gesamt"] += 1
        e = pdx.parse_block(raw)
        e = e if isinstance(e, dict) else {"werte": e}
        if oid in unsere:
            out["unsere"].append({"id": oid, "zuordnung": "trade_order_refs", **e})
        elif out["beispiel"] is None:
            out["beispiel"] = {"id": oid, **e}
    if "trade_order_manager/database" in save.blocks and not out["anzahl_gesamt"]:
        r = save.raw("trade_order_manager/database")
        if re.search(rb"[^\s{}]", r):                       # nicht leer, aber keine Einträge mit Kennung: Rohtext
            out["roh"] = r[:4000].decode("utf-8", "replace")
    return out


def handel_spielstand(save, cid):
    """Unsere Handelsrouten aus trade_manager/database (Feld trade_owner), alle Felder unverändert."""
    if "trade_manager/database" not in save.blocks:
        return []
    own = re.compile(rb"\n\ttrade_owner=%d\s" % cid)
    out = []
    for tid, raw in save.raw_entries("trade_manager/database"):
        if own.search(raw):
            e = pdx.parse_block(raw)
            out.append({"id": tid, **(e if isinstance(e, dict) else {})})
    return out

# ---------------------------------------------------------------- Militär aller Länder (ab Format 14, Kachel Nachbarn 25.10.)
_U_OWN, _U_TYP, _U_STR = re.compile(rb"\n\towner=(\d+)"), re.compile(rb"\n\ttype=(\w+)"), re.compile(rb"\n\tstrength=([\d.]+)")


def laender_militaer(save, names, tags):
    """Kurzer Militärauszug je lebendem Land (mit Orten) – für die wählbaren Länder der Kachel Nachbarn und Kriegsgelegenheiten.
    Regimenter/Schiffe und Mann (strength × 1.000, REGIMENT_SIZE) aus subunit_manager; Regimenter ohne strength-Feld (z. B.
    Bauernaufgebote, 53 von 1.446 am 1.1.1351) zählen gesondert, ihre Stärke steht nicht im Spielstand. Rang und
    Militärwertung des Spiels (score_rating/score_rank MIL), Mannstärke, Seeleute, Armeetradition, erforschte Fortschritte,
    Zahl der laufenden Kriege. Holland 1351.1: 1.348 Länder in rund 3 s."""
    sub = defaultdict(lambda: {"regimenter": 0, "schiffe": 0, "mann": 0.0, "ohne_staerke": 0})
    for _, raw in save.raw_entries("subunit_manager/database"):
        o, ty = _U_OWN.search(raw), _U_TYP.search(raw)
        if not o or not ty:
            continue
        d, st = sub[int(o.group(1))], _U_STR.search(raw)
        if ty.group(1).startswith(b"a_"):
            d["regimenter"] += 1
            if st:
                d["mann"] += float(st.group(1)) * 1000
            else:
                d["ohne_staerke"] += 1
        elif ty.group(1).startswith(b"n_"):
            d["schiffe"] += 1
    kriege = defaultdict(int)
    for _, raw in save.raw_entries("war_manager/database"):
        w = pdx.parse_block(raw)
        for t in (w.get("all") or []) if isinstance(w, dict) else []:
            if t.get("status") == "Active":
                kriege[t.get("country")] += 1
    out = []
    for cid, raw in save.raw_entries("countries/database"):
        if b"owned_locations={" not in raw:
            continue
        c = pdx.parse_block(raw)
        if not isinstance(c, dict) or not c.get("owned_locations") or not tags.get(cid):
            continue
        cur, sc = c.get("currency_data") or {}, c.get("score") or {}
        adv = c.get("researched_advances") or {}
        s = sub.get(cid) or {}
        # Der Spielstand lässt Nullwerte weg (Prüfung 25.10.: Utrecht, Geldern … laut Mod Mannstärke 0,0, im Spielstand ohne Feld;
        # 1.143 von 1.348 Ländern ohne manpower) – bei lebenden Ländern 0 statt unbekannt
        r3 = lambda v: round(v, 3) if isinstance(v, float) else 0 if v is None else v  # noqa: E731  (Namen holt der Server)
        out.append({"tag": tags[cid], "rang": c.get("great_power_rank"),
                    "mil_wertung": r3((sc.get("score_rating") or {}).get("MIL")), "mil_rang": (sc.get("score_rank") or {}).get("MIL"),
                    "mannstaerke": r3(cur.get("manpower")), "max_mannstaerke": r3(c.get("max_manpower")),
                    "seeleute": r3(cur.get("sailors")), "max_seeleute": r3(c.get("max_sailors")),
                    "armeetradition": r3(cur.get("army_tradition")),
                    "fortschritte": sum(1 for v in adv.values() if v == "yes") if isinstance(adv, dict) else None,
                    "orte": len(c.get("owned_locations") or []), "kriege": kriege.get(cid, 0),
                    "regimenter": s.get("regimenter", 0), "schiffe": s.get("schiffe", 0), "mann": round(s.get("mann", 0.0)),
                    "ohne_staerke": s.get("ohne_staerke", 0)})
    return out

# ---------------------------------------------------------------- Kriege (ab Format 13, Kriegskachel 25.10.)
# Reihenfolge der Einheitenkategorien in den Schlachtlisten (losses/total/imprisoned je 10 Werte) = Dateireihenfolge in
# in_game/common/unit_categories (00_army_light_infantry … 14_navy_transport); geprüft an Krieg 83886081 (1345): die
# Kategorien mit Werten passen zu attacker_losses. Größen in Tausend Mann (Schlachtgröße = Σ total), REGIMENT_SIZE = 1000.
KATEGORIEN = ("army_light_infantry", "army_heavy_infantry", "army_light_cavalry", "army_heavy_cavalry", "army_artillery",
              "army_auxiliary", "navy_galley", "navy_light_ship", "navy_heavy_ship", "navy_transport")
SCHLACHTEN_MAX = 12
_K_LAND = re.compile(rb"\bcountry=(\d+)\b")


def _verluste(v):
    """{"losses": {kategorie: {Battle, Attrition, Capture}}} -> {kategorie: {...}} (leer: [] im Spielstand)."""
    v = (v or {}).get("losses") if isinstance(v, dict) else None
    return {k: x for k, x in v.items() if isinstance(x, dict)} if isinstance(v, dict) else {}


def _kriegsziel(w, names, locnames):
    """Der Kriegsziel-Block ist der Eintrag mit casus_belli (take_province, independence …)."""
    for k, v in w.items():
        if isinstance(v, dict) and "casus_belli" in v:
            t = v.get("target") or {}
            locs = t.get("target_locations")
            locs = locs if isinstance(locs, list) else [locs] if locs is not None else []
            return {"block": k, "typ": v.get("type"), "casus_belli": v.get("casus_belli"),
                    "provinz": t.get("target_province"),
                    "orte": [{"id": i, "name": names(loc_key(locnames, i)) if loc_key(locnames, i) else str(i)}
                             for i in locs if isinstance(i, int)]}
    return None


def _land_militaer(save, names, locnames, pid):
    """Militärwerte eines Kriegsteilnehmers aus dem Spielstand: Mannstärke, Seeleute (Tsd.), Tradition, Armeen und Flotten
    mit Regimentern/Schiffen nach Typ, Stärke (Tsd. Mann, strength 1,0 = 1.000), Heerführer, erforschte Fortschritte."""
    c = save.entry("countries/database", pid) or {}
    cur = c.get("currency_data") or {}
    adv = c.get("researched_advances") or {}
    einheiten = {}
    for uid in c.get("units") or []:
        u = save.entry("unit_manager/database", uid)
        if not isinstance(u, dict):
            continue
        key = loc_key(locnames, u.get("location"))
        einheiten[uid] = {"id": uid, "art": "heer" if u.get("is_army") == "yes" else "flotte", "ort_id": u.get("location"),
                          "ort": names(key) if key else None, "fuehrer_id": u.get("leader"),
                          "taetigkeit": (u.get("activity") or {}).get("activity_type") if isinstance(u.get("activity"), dict) else None,
                          "typen": {}, "staerke": 0.0, "moral": [], "untereinheiten": 0}
    for sid in c.get("owned_subunits") or []:
        s = save.entry("subunit_manager/database", sid)
        if not isinstance(s, dict) or s.get("unit") not in einheiten:
            continue
        e = einheiten[s["unit"]]
        e["untereinheiten"] += 1
        e["typen"][s.get("type")] = e["typen"].get(s.get("type"), 0) + 1
        if isinstance(s.get("strength"), (int, float)):
            e["staerke"] += s["strength"]
        if isinstance(s.get("morale"), (int, float)):
            e["moral"].append(s["morale"])
    fuehrer = {}
    for e in einheiten.values():
        m = e.pop("moral")
        e["moral"] = round(sum(m) / len(m), 3) if m else None
        e["staerke"] = round(e["staerke"], 3)
        ch = save.entry("character_db/database", e["fuehrer_id"]) if e["fuehrer_id"] is not None else None
        if isinstance(ch, dict):
            fuehrer[e["fuehrer_id"]] = {"id": e["fuehrer_id"], "name": _char_name(names, ch), "mil": ch.get("mil"),
                                        "adm": ch.get("adm"), "dip": ch.get("dip"), "eigenschaft": ch.get("general_trait"),
                                        "eigenschaft_name": names(ch["general_trait"]) if ch.get("general_trait") else None,
                                        "merkmale": [names(t) for t in _items(ch.get("traits"))]}
    typen = {}
    for e in einheiten.values():
        for t, n in e["typen"].items():
            typen[t] = typen.get(t, 0) + n
    return {"mannstaerke": cur.get("manpower"), "max_mannstaerke": c.get("max_manpower"),
            "mannstaerke_monat": c.get("monthly_manpower"), "seeleute": cur.get("sailors"), "max_seeleute": c.get("max_sailors"),
            "seeleute_monat": c.get("monthly_sailors"), "armeetradition": cur.get("army_tradition"),
            "marinetradition": cur.get("navy_tradition"), "heer_erwartet": c.get("expected_army_size"),
            "flotte_erwartet": c.get("expected_navy_size"), "heer_unterhalt": c.get("last_months_army_maintenance"),
            "flotte_unterhalt": c.get("last_months_navy_maintenance"),
            "fortschritte": sorted(k for k, v in adv.items() if v == "yes") if isinstance(adv, dict) else [],
            "einheiten": list(einheiten.values()), "fuehrer": list(fuehrer.values()),
            "typen": typen, "typ_namen": {t: names(t) for t in typen}}


def _schlacht(b, names, tags, locnames):
    def seite(x):
        x = x or {}
        # mehrere Länder auf einer Seite: who steht wiederholt (je Land Größe, Aufgebot, Kriegsmüdigkeit …)
        who = [y for y in _items(x.get("who")) if isinstance(y, dict)]
        return {"laender": [tags.get(y.get("country")) for y in who],
                "groesse": round(sum(y.get("size") or 0 for y in who), 3),
                "verluste": round(sum(v for v in x.get("losses") or [] if isinstance(v, (int, float))), 3),
                "gefangen": round(sum(v for v in x.get("imprisoned") or [] if isinstance(v, (int, float))), 3),
                "fuehrer_id": x.get("character")}
    key = loc_key(locnames, b.get("location"))
    return {"ort_id": b.get("location"), "ort": names(key) if key else None, "datum": b.get("date"),
            "angreiferseite_siegt": b.get("war_attacker_win") == "yes", "kriegspunkte": b.get("war_score"),
            "angreifer": seite(b.get("attacker")), "verteidiger": seite(b.get("defender"))}


def kriege(save, names, tags, locnames, cid):
    """Unsere laufenden Kriege (war_manager/database, wir als aktiver Teilnehmer): Seiten mit Beitrittsgrund, Kriegspunkte und
    Verluste je Teilnehmer, Kriegsziel, besetzte Orte der Teilnehmer, Schlachten, Militär je Teilnehmer."""
    out = []
    for wid, raw in save.raw_entries("war_manager/database"):
        if cid not in {int(x) for x in _K_LAND.findall(raw)}:
            continue
        w = pdx.parse_block(raw)
        if not isinstance(w, dict):
            continue
        teil = []
        for t in w.get("all") or []:
            h = [x for x in t.get("all_history") or [] if isinstance(x, dict)]
            if not h:
                continue
            req, joined = h[-1].get("request") or {}, h[-1].get("joined") or {}
            pid = t.get("country")
            teil.append({"id": pid, "tag": tags.get(pid), "name": names(tags.get(pid)) if tags.get(pid) else str(pid),
                         "seite": {"Attacker": "Angreifer", "Defender": "Verteidiger"}.get(req.get("side"), req.get("side")),
                         "grund": req.get("reason"), "gerufen_von": tags.get(req.get("called_ally")),
                         "status": t.get("status"), "beitritt": joined.get("date"),
                         "punkte": joined.get("score") if isinstance(joined.get("score"), dict) else {},
                         "verluste": _verluste(joined.get("losses"))})
        wir = next((t for t in teil if t["id"] == cid), None)
        if not wir or wir["status"] != "Active":
            continue
        aktiv = {t["id"] for t in teil if t["status"] == "Active"}
        for t in teil:
            if t["id"] in aktiv:
                t["militaer"] = _land_militaer(save, names, locnames, t["id"])
        # besetzte Orte: Orte der aktiven Teilnehmer, die ein anderer aktiver Teilnehmer kontrolliert
        besetzt = []
        for pid in aktiv:
            for lid in (save.entry("countries/database", pid) or {}).get("owned_locations") or []:
                L = save.entry("locations/locations", lid) or {}
                if L.get("controller") is not None and L.get("controller") != L.get("owner") and L.get("controller") in aktiv:
                    key = loc_key(locnames, lid)
                    besetzt.append({"ort_id": lid, "ort": names(key) if key else str(lid), "besitzer": tags.get(L.get("owner")),
                                    "kontrolleur": tags.get(L.get("controller"))})
        schlachten = [_schlacht(b, names, tags, locnames) for b in (w.get("battle") or [])[-SCHLACHTEN_MAX:] if isinstance(b, dict)]
        oa, ziel = w.get("original_attacker"), w.get("original_attacker_target")
        out.append({
            "id": wid, "name": f"{names(tags.get(oa)) if tags.get(oa) else oa} gegen {names(tags.get(ziel)) if tags.get(ziel) else ziel}",
            "beginn": w.get("start_date"), "angreifer_ursprung": tags.get(oa), "ziel": tags.get(ziel),
            "verteidiger_ursprung": [tags.get(x) for x in _items(w.get("original_defenders"))],
            "kriegsziel": _kriegsziel(w, names, locnames), "angreifer_punkte": w.get("attacker_score"),
            "kriegsziel_gehalten": w.get("war_goal_held"), "stillstand_jahre": w.get("stalled_years"),
            "verluste": {"Angreifer": _verluste(w.get("attacker_losses")), "Verteidiger": _verluste(w.get("defender_losses"))},
            "pop_verluste": {k: w.get(k) for k in ("defender_siege_pop_losses", "attacker_siege_pop_losses",
                                                   "attacker_levy_pop_losses", "defender_levy_pop_losses") if k in w},
            "schlachten": schlachten, "schlachten_gesamt": len(w.get("battle") or []),
            "besetzt": besetzt, "teilnehmer": teil, "wir": wir["seite"]})
    return out


# ---------------------------------------------------------------- Gebäudegewinne (ab Format 11, Kachel Wirtschaftsplan 25.10.)
_G_TYP = re.compile(rb"\n\ttype=(\w+)")
_G_LVL = re.compile(rb"\n\tlevel=([\d.]+)")
_G_LOC = re.compile(rb"\n\tlocation=(\d+)")
_G_OWN = re.compile(rb"\n\towner=(\d+)")
_G_PRO = re.compile(rb"\n\tlast_months_profit=(-?[\d.]+)")


def gebaeude_gewinne(save, cid, markt_ids):
    """Gewinn je Gebäudeart laut Spielstand (building_manager: last_months_profit = Gewinn des ganzen Gebäudes, Spielwert):
    {"maerkte": {markt: {art: [gebäude, stufen, gewinn, eigene, länder]}}, "welt": {art: [gebäude, stufen, gewinn]}}. Gewinn je
    Stufe = Gewinn ÷ Stufen – passt zum Mod-Wert GetProfitPerLevel (Steinmetz Leiden 0,4228 / 2 = 0,211 gegen 0,206, Prüfung
    25.10.). Der Gewinn hängt am Ort (Produktivität, Marktzugang) – der Marktdurchschnitt ist ein Richtwert."""
    ort_markt = {}
    for m in dict.fromkeys(x for x in markt_ids if x is not None):
        for lid in (save.entry("market_manager/database", m) or {}).get("members") or []:
            ort_markt.setdefault(lid, m)
    # Der Spielstand schreibt Gewinn 0 nicht (unter 18.855 Werten kein einziger 0; Brauereien/Juwelierszünfte Hollands ohne Feld
    # haben laut Mod GetProfit 0, Prüfung 25.10.) -> fehlt das Feld bei einer Gebäudeart, die sonst Gewinn kennt, zählt 0.
    # Arten ganz ohne Feld (Staatsgebäude mit Unterhalt) bleiben weg. Ohne level = im Bau (establishment_progress 0).
    zeilen, mit_gewinn = [], set()
    for _, raw in save.raw_entries("building_manager/database"):
        lv = _G_LVL.search(raw)
        if not lv or float(lv.group(1)) <= 0:
            continue
        art, p = _G_TYP.search(raw).group(1).decode(), _G_PRO.search(raw)
        if p:
            mit_gewinn.add(art)
        loc, own = _G_LOC.search(raw), _G_OWN.search(raw)
        zeilen.append((art, float(lv.group(1)), float(p.group(1)) if p else 0.0, int(loc.group(1)) if loc else None,
                       own.group(1) if own else None))
    maerkte, welt, laender = {}, {}, {}
    for art, stufen, gewinn, loc, own in zeilen:
        if art not in mit_gewinn:
            continue
        w = welt.setdefault(art, [0, 0.0, 0.0])
        w[0] += 1; w[1] += stufen; w[2] += gewinn
        m = ort_markt.get(loc)
        if m is None:
            continue
        e = maerkte.setdefault(str(m), {}).setdefault(art, [0, 0.0, 0.0, 0, 0])
        e[0] += 1; e[1] += stufen; e[2] += gewinn
        if own is not None and int(own) == cid:
            e[3] += 1
        laender.setdefault((str(m), art), set()).add(own)
    for (m, art), s in laender.items():
        maerkte[m][art][4] = len(s)
    rund = lambda v: [round(x, 5) if isinstance(x, float) else x for x in v]     # noqa: E731
    return {"maerkte": {m: {a: rund(v) for a, v in d.items()} for m, d in maerkte.items()},
            "welt": {a: rund(v) for a, v in welt.items()}}


# ---------------------------------------------------------------- Krankheiten (ab Format 10, Kachel Krankheiten 04.10.)
FIX = 2 ** 30          # Festkomma im Spielstand: resistance/percent = Wert / 2^30 (Kulagin 904543458 → 84,24 % wie im Spiel)
_POPS = re.compile(rb"pops=\{(?:\s*\{[^{}]*\})*\s*\}")
_ITEM = re.compile(rb"\{([^{}]*)\}")
_KV = re.compile(rb"(\w+)=([\w.\-]+)")
_LAND_TOTE = re.compile(rb"county=(\d+)\s+deaths=\{((?:\s*\{[^{}]*\})*)\s*\}")
_TOTE = re.compile(rb"disease_outbreak=(\d+)\s+deaths=([\d.]+)")


def _eintraege(b):
    """Oberste { … }-Einträge eines Listenblocks (data={ {…} {…} })."""
    out, depth, start = [], 0, None
    for m in re.finditer(rb"[{}]", b):
        if m.group() == b"{":
            depth += 1
            if depth == 2:
                start = m.start()
        else:
            if depth == 2:
                out.append(b[start:m.end()])
            depth -= 1
    return out


def _abschnitt(b, key, folgende):
    """Teilblock key={ … } eines Eintrags bis zum nächsten bekannten Schlüssel."""
    i = b.find(key + b"={")
    if i < 0:
        return b""
    ends = [j for j in (b.find(k + b"={", i + 1) for k in folgende) if j > 0]
    return b[i:min(ends) if ends else len(b)]


def krankheiten(save, names, tags, locnames, cid, eigene_orte, markt_orte):
    """Krankheiten laut Spielstand (disease_outbreak_manager, situation_manager/black_death):
    - data = je Krankheit ein Eintrag: current (laufende Ausbrüche), locations (je Ort resistance, bei Befall origin =
      Ausbruch und percent = Ausbreitung), countries (je Land Tote je Ausbruch, in Tausend: 1.68724 → „1,687“ im Spiel).
    - database/<id> = Ausbruch: parameter (type, origin = Ursprungsort), outbreak_date, died_out_date.
    Malaria steht mit 2417 endemischen Einträgen in current; das Spiel zählt sie nicht als Ausbruch (Weltpolitik → 0)."""
    if "disease_outbreak_manager/data" not in save.blocks:
        return None
    eigene = set(eigene_orte)
    markt = set(markt_orte or [])
    out = {"krankheiten": {}, "ausbrueche": [], "orte": {}, "tote_uns": 0.0}
    ausbruch = {}                      # id -> Zähler
    for it in _eintraege(save.raw("disease_outbreak_manager/data")):
        mt = re.search(rb"type=(\w+)", it)
        if not mt:
            continue
        k = mt.group(1).decode()
        cur = re.search(rb"current=\{([^}]*)\}", it)
        aktuell = [int(x) for x in cur.group(1).split()] if cur else []
        info = out["krankheiten"][k] = {"name": names(k), "aktuell": [] if k == "malaria" else aktuell,
                                        "endemisch": len(aktuell) if k == "malaria" else 0, "tote_uns": 0.0, "orte_uns": 0}
        for a in info["aktuell"]:
            ausbruch[a] = {"krankheit": k, "orte": 0, "orte_uns": [], "orte_markt": [], "laender": {}}
        orte = _POPS.sub(b"", _abschnitt(it, b"locations", (b"sub_units", b"countries")))
        for m in _ITEM.finditer(orte):
            f = dict(_KV.findall(m.group(1)))
            if b"location" not in f:
                continue
            lid = int(f[b"location"])
            anteil = int(f[b"percent"]) / FIX if b"percent" in f else 0.0
            if lid in eigene:
                out["orte"].setdefault(str(lid), {})[k] = {"widerstand": int(f.get(b"resistance", b"0")) / FIX,
                                                         "ausbreitung": anteil}
                if anteil > 0:
                    info["orte_uns"] += 1
            if anteil > 0 and b"origin" in f and int(f[b"origin"]) in ausbruch:
                a = ausbruch[int(f[b"origin"])]
                a["orte"] += 1
                key = loc_key(locnames, lid)
                if lid in eigene:
                    a["orte_uns"].append({"id": lid, "name": names(key) if key else str(lid), "ausbreitung": anteil})
                elif lid in markt:
                    a["orte_markt"].append({"id": lid, "name": names(key) if key else str(lid), "ausbreitung": anteil})
        for m in _LAND_TOTE.finditer(_abschnitt(it, b"countries", ())):
            land = int(m.group(1))
            for t in _TOTE.finditer(m.group(2)):
                oid, tote = int(t.group(1)), float(t.group(2))
                if land == cid:
                    info["tote_uns"] += tote
                if oid in ausbruch:
                    ausbruch[oid]["laender"][land] = ausbruch[oid]["laender"].get(land, 0.0) + tote
        out["tote_uns"] += info["tote_uns"]
    for oid, a in ausbruch.items():
        e = save.entry("disease_outbreak_manager/database", oid) or {}
        par = e.get("parameter") or {}
        org = par.get("origin")
        okey = loc_key(locnames, org) if org is not None else None
        oloc = save.entry("locations/locations", org) or {} if org is not None else {}
        otag = tags.get(oloc.get("owner"))
        laender = sorted(a["laender"].items(), key=lambda x: -x[1])
        out["ausbrueche"].append({
            "id": oid, "krankheit": a["krankheit"], "krankheit_name": names(a["krankheit"]),
            "ursprung_id": org, "ursprung": names(okey) if okey else None, "ursprung_land": otag,
            "ursprung_land_name": names(otag) if otag else None,
            "start": e.get("outbreak_date"), "ende": e.get("died_out_date"),
            "tote": sum(a["laender"].values()), "laender": len(a["laender"]), "tote_uns": a["laender"].get(cid, 0.0),
            "laender_tote": [{"tag": tags.get(l), "name": names(tags.get(l)), "tote": t} for l, t in laender[:8]],
            "orte": a["orte"], "orte_uns": a["orte_uns"], "orte_markt": sorted(a["orte_markt"], key=lambda x: -x["ausbreitung"])[:12],
            "orte_markt_anzahl": len(a["orte_markt"]),
        })
    out["ausbrueche"].sort(key=lambda x: (x["krankheit"], str(x["start"])))
    # Situation Schwarzer Tod: status, start, Variable original_outbreak (identity = Ausbruch-ID)
    if "situation_manager/black_death" in save.blocks:
        r = save.raw("situation_manager/black_death")
        st = re.search(rb"status=(\w+)", r)
        sd = re.search(rb"start=([\d.]+)", r)
        ob = re.search(rb"flag=original_outbreak\s*data=\{[^}]*identity=(\d+)", r)
        out["schwarzer_tod"] = {"status": st.group(1).decode() if st else None, "start": sd.group(1).decode() if sd else None,
                                "ausbruch": int(ob.group(1)) if ob else None}
    return out


# ---------------------------------------------------------------- alle Rohdaten des Spielerlandes (ab Format 4)
def _entries_with(save, parent, needles, check=None):
    """Einträge eines database-Blocks, deren Rohtext eines der Muster enthält (schneller Vorfilter), zerlegt;
    check(eintrag) filtert genau."""
    out = {}
    for eid, raw in save.raw_entries(parent):
        if any(n.search(raw) for n in needles):
            e = pdx.parse_block(raw)
            if isinstance(e, dict) and (check is None or check(e)):
                out[eid] = e
    return out


def _relations(dip, cid):
    """Alle Beziehungsblöcke im diplomacy_manager mit first/second = cid -> [{art, …}]."""
    out = []
    for m in re.finditer(rb"\n\t\t(first|second)=%d\n" % cid, dip):
        start = dip.rfind(b"\n\t", 0, m.start())
        while start > 0 and dip[start + 2:start + 3] == b"\t":      # bis zur Blockzeile mit genau einem Tab
            start = dip.rfind(b"\n\t", 0, start)
        end = dip.find(b"\n\t}", m.end())
        head = dip[start + 2:dip.find(b"\n", start + 2)]
        if not head.endswith(b"={") or end < 0:
            continue
        name = head[:-2].decode("utf-8", "replace")
        # parse_block erwartet den Block samt Klammern (ohne liest es nur den ersten Unterblock)
        body = pdx.parse_block(b"{" + dip[start:end + 3].split(b"={", 1)[1].rsplit(b"}", 1)[0] + b"}")
        if isinstance(body, dict):
            out.append({"art": name, **body})
    # ein Block kann first und second zugleich treffen (nie bei uns selbst) - doppelte entfernen
    seen, uniq = set(), []
    for r in out:
        k = (r["art"], r.get("first"), r.get("second"), str(r.get("start_date")))
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


def roh(save, c, cid):
    """Alle Einträge des Spielstands, die das Spielerland betreffen - vollständig, ungekürzt (Ziel des Nutzers:
    alle Informationen, die das Spiel hat). Schlüssel = Bereich des Spielstands."""
    num = lambda n: re.compile(rb"(?<![\d.])%d(?![\d.])" % n)                      # noqa: E731
    field = lambda k, n: re.compile(rb"\n\t%s=%d\n" % (k.encode(), n))            # noqa: E731
    gov = c.get("government") or {}
    locs = [l for l in c.get("owned_locations") or [] if isinstance(l, int)]
    r = {"land": c}
    r["staende"] = {k: save.entry("estate_manager/database", v) for k, v in (gov.get("estates") or {}).items()}
    r["orte"] = {l: save.entry("locations/locations", l) for l in locs}
    r["provinzen"] = {p: save.entry("provinces/database", p) for p in c.get("provinces") or []}
    pops = [p for L in r["orte"].values() if L for p in (L.get("population") or {}).get("pops") or []]
    r["pops"] = {p: save.entry("population/database", p) for p in pops}
    r["gebaeude"] = _entries_with(save, "building_manager/database", [field("owner", cid)])
    maerkte = {L.get("market") for L in r["orte"].values() if L and L.get("market") is not None}
    r["maerkte"] = {m: save.entry("market_manager/database", m) for m in maerkte}
    r["charaktere"] = _entries_with(save, "character_db/database", [field("country", cid)],
                                    lambda e: e.get("country") == cid)
    dyn = {e.get("dynasty") for e in r["charaktere"].values() if e.get("dynasty") is not None}
    r["dynastien"] = {d: save.entry("dynasty_manager/database", d) for d in dyn}
    r["kabinett"] = {k: save.entry("cabinet_manager/database", k) for k in gov.get("cabinet_entries") or []}
    r["einheiten"] = _entries_with(save, "unit_manager/database", [field("country", cid)])
    r["untereinheiten"] = _entries_with(save, "subunit_manager/database", [field("owner", cid)])
    r["kredite"] = _entries_with(save, "loan_manager/database", [field("borrower", cid)])
    r["kriege"] = _entries_with(save, "war_manager/database", [num(cid)],
                                lambda e: re.search(r"(?<![\d.])%d(?![\d.])" % cid, json.dumps(e)) is not None)
    r["herrscherzeiten"] = _entries_with(save, "rulerterm_manager/database", [field("ruled", cid)],
                                         lambda e: e.get("ruled_type") == "Country")
    r["rebellen"] = _entries_with(save, "rebel_manager/database", [field("country", cid)])
    r["bauprojekte"] = _entries_with(save, "construction_manager/database", [field("country", cid)])
    r["organisationen"] = _entries_with(save, "international_organization_manager/database", [num(cid)],
                                        lambda e: cid in [x for x in (e.get("all_members") or []) if isinstance(x, int)])
    rel = save.entry("religion_manager/database", c.get("primary_religion")) if c.get("primary_religion") is not None else None
    r["religion"] = rel
    cults = [c.get("primary_culture"), *[x for x in c.get("accepted_cultures") or [] if isinstance(x, int)]]
    r["kulturen"] = {k: save.entry("culture_manager/database", k) for k in cults if k is not None}
    r["katastrophen"] = _entries_with(save, "disaster_manager/database", [field("owner", cid)])
    r["kunstwerke"] = _entries_with(save, "work_of_art_manager/database",
                                    [re.compile(rb"\n\tlocation=%d\n" % l) for l in locs])
    dip = save.raw("diplomacy_manager") if "diplomacy_manager" in save.blocks else b""
    r["beziehungen"] = _relations(dip, cid)
    # weltweite, kleine Blöcke
    for k in ("great_power_manager", "institution_manager", "situation_manager", "current_age"):
        if k in save.blocks:
            r[k] = save.block(k)
    return r


def _active_pms(save, cid):
    """Aktive Produktionsmethoden je Gebäude: im Spielstand steht je aktiver Methode ein Block unter ihrem Namen,
    darin missing.demand = derselbe Name (z. B. wheat_brewery_maintenance = { missing = { demand = wheat_brewery_maintenance } },
    clay_bricks = { missing = { demand = clay_bricks } }). Vorher nur Namen auf _maintenance -> Maurer, Marktdorf,
    Juwelier fehlten (geprüft 29.09. an allen 78 Gebäuden: jeder Block mit eigenem Namen als demand ist eine Methode)."""
    out = {}
    own = re.compile(rb"\n\towner=%d\n" % cid)
    for bid, raw in save.raw_entries("building_manager/database"):
        if own.search(raw):
            b = pdx.parse_block(raw)
            pms = {k: v for k, v in b.items() if isinstance(v, dict) and (v.get("missing") or {}).get("demand") == k}
            out[bid] = {"typ": b.get("type"), "pms": list(pms), "fehlt": {k: {g: x for g, x in (v.get("missing") or {}).items()
                                                                            if g != "demand"} for k, v in pms.items()},
                        "status": b.get("employment_requirement_status")}
    return out


def _items(v):
    """Liste von Blöcken - egal ob als { {…} {…} } (list) oder als wiederholter Schlüssel (_Multi) gespeichert."""
    if isinstance(v, list):
        return list(v)
    return [] if v is None else [v]


def _objects(v):
    """implemented_laws/_reforms -> {kategorie: objekt} bzw. Liste der Objekte."""
    if isinstance(v, dict):
        return {k: (x.get("object") if isinstance(x, dict) else x) for k, x in v.items()}
    if isinstance(v, list):
        return [x.get("object") if isinstance(x, dict) else x for x in v]
    return v


def _char_name(names, ch):
    # Annäherung: das Spiel lokalisiert Vornamen je Kultur (name_john -> "Jan" statt "Johan"); genaue
    # Namen liefern die Live-Zeilen RG1C/RG1G des Daten-Mods
    first = " ".join(names(p) for p in str(ch.get("first_name", "")).split(".") if p) if ch.get("first_name") else ""
    last = names(ch.get("last_name")) if ch.get("last_name") else ""
    return " ".join(x for x in (first, last) if x)


def _cabinet(save, names, cid):
    e = save.entry("cabinet_manager/database", cid) or {}
    ch = save.entry("character_db/database", e.get("character")) if e.get("character") is not None else None
    act = e.get("implemented_government_action") or {}
    ziele = {}
    for x in _items((e.get("params") or {}).get("named_targets")):
        if isinstance(x, dict) and isinstance(x.get("target"), dict):
            typ, ident = x["target"].get("type"), x["target"].get("identity")
            if typ == "prov":
                p = save.entry("provinces/database", ident) or {}
                ziele[x.get("flag")] = names(p.get("province_definition"))
            elif typ == "reli":
                r = save.entry("religion_manager/database", ident) or {}
                ziele[x.get("flag")] = names(r.get("name"))
            else:
                ziele[x.get("flag")] = f"{typ}:{ident}"
    return {"id": cid, "platz": e.get("index"), "aktion": act.get("object"), "aktion_name": names(act.get("object")),
            "seit": act.get("date"), "ziele": ziele,
            "person": _char_name(names, ch) if ch else None,
            "adm": ch.get("adm") if ch else None, "dip": ch.get("dip") if ch else None,
            "mil": ch.get("mil") if ch else None, "stand": names(ch.get("estate")) if ch and ch.get("estate") else None}


def _pop_types(save, L):
    """Pops eines Ortes je Typ: Größe, gewichtete Zufriedenheit und Bildung."""
    agg = {}
    for pid in (L.get("population") or {}).get("pops") or []:
        p = save.entry("population/database", pid)
        if not isinstance(p, dict):
            continue
        a = agg.setdefault(p.get("type"), {"groesse": 0.0, "_sat": 0.0, "_lit": 0.0, "pops": 0})
        size = p.get("size") or 0
        a["groesse"] += size
        a["_sat"] += size * (p.get("satisfaction") or 0)
        a["_lit"] += size * (p.get("literacy") or 0)
        a["pops"] += 1
    for a in agg.values():
        a["zufriedenheit"] = a.pop("_sat") / a["groesse"] if a["groesse"] else None
        a["bildung"] = a.pop("_lit") / a["groesse"] if a["groesse"] else None
    return agg


def _market_view(save, names, tags, locnames, mid, m):
    """Ein Markt aus market_manager/database: Güter (Preis, Angebot/Nachfrage nach Quelle), Händler, Mitglieder."""
    goods = []
    for g, gv in (m.get("goods") or {}).items():
        if isinstance(gv, dict):
            goods.append({"gut": g, "name": names(g), "preis": gv.get("price"),
                          "angebot": gv.get("supply"), "nachfrage": gv.get("demand"),
                          "vorrat": gv.get("stockpile"),
                          # Angebot nach Quelle (Production, Trade, BurgherTrades …), Verbrauch nach
                          # Abnehmer (Pops, Building, Trade, Units …), Produktion nach Art (RawMaterials, Buildings)
                          "angebot_quellen": gv.get("supplied"), "verbrauch": gv.get("taken"),
                          "produktion": gv.get("production_supplied"),
                          "preisverlauf": gv.get("history")})
    haendler = [{"land_id": x.get("country"), "tag": tags.get(x.get("country")), "land": names(tags.get(x.get("country"))),
                 "macht": x.get("power"), "kapazitaet": x.get("capacity"), "genutzt": x.get("used")}
                for x in _items(m.get("merchant")) if isinstance(x, dict)]
    return {"id": mid, "zentrum": names(loc_key(locnames, m["center"])) if "center" in m else None, "zentrum_id": m.get("center"),
            "nahrung": m.get("food"), "kapazitaet": m.get("capacity"),
            "bevoelkerung": m.get("population"), "gueter": goods, "haendler": haendler,
            "mitglieder": _market_members(save, names, tags, locnames, m.get("members") or [])}


def _market_members(save, names, tags, locnames, members):
    """Mitgliedsorte des Marktes je Besitzerland: Anzahl, Entwicklung, Steuer, Rohstoffe (Annäherung für
    'wer produziert wieviel' - der Spielstand hat keine Produktion je Land und Markt)."""
    by = {}
    for lid in members:
        L = save.entry("locations/locations", lid) or {}
        o = L.get("owner")
        r = by.setdefault(o, {"land_id": o, "tag": tags.get(o), "land": names(tags.get(o)) if o is not None else "ohne Besitzer",
                              "orte": 0, "entwicklung": 0.0, "steuer": 0.0, "rohstoffe": {}})
        r["orte"] += 1
        r["entwicklung"] += L.get("development") or 0
        r["steuer"] += L.get("tax") or 0
        rm = L.get("raw_material")
        if rm:
            r["rohstoffe"][rm] = r["rohstoffe"].get(rm, 0) + 1
    return sorted(by.values(), key=lambda r: -r["entwicklung"])


def summarize_buildings(geb):
    by = defaultdict(lambda: {"anzahl": 0, "stufen": 0, "gewinn": 0.0, "mit_gewinn": 0, "unterhalt": 0.0})
    for b in geb:
        r = by[b["name"]]
        r["anzahl"] += 1
        r["stufen"] += b["stufe"] or 0
        if isinstance(b["gewinn"], (int, float)):
            r["gewinn"] += b["gewinn"]
            r["mit_gewinn"] += 1
        if isinstance(b["unterhalt"], (int, float)):
            r["unterhalt"] += b["unterhalt"]
    return dict(by)
