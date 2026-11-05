"""Kacheln der Ratgeber-Seite in der Seitenleiste im Spiel (Mod 0.27, 03.11.; Nutzer: „es stehen mir noch zu wenig infos drin,
was ist mit den restlichen kacheln aus dem ratgeber?“ – freigegeben „ja, so bauen“).

18 der 21 Kacheln der Seite kommen ins Spiel (Verlauf, Entscheidungen und Modifikatoren bleiben im Browser). Je Kachel:
- Kopfwerte wie im Kopf der Kachel auf der Seite (web/app.js, startstrategie.js, gruendung.js, live.js) – hier nach Python
  übertragen, gleiche Datenquelle (d aus history.series), gleiche Rundung (fmt/pct/sgn wie Intl de-DE: kaufmännisch auf die
  kürzeste Dezimaldarstellung), Veränderung zum Vormonat in Klammern wie bei der Kennzahl Gold (#G/#R).
  Seit 04.11. bekommt die Seitenleiste wie die Seite auch /api/alles und /api/bevoelkerung (d["alles"], d["bev"], ingame.daten).
  Was fehlt, bleibt leer; die Oberfläche blendet leere Felder aus (StringIsEmpty).
- Warnungen (bis 3), ein Segmentbalken aus 10 Teilen für einen Anteil des Ratgebers (Spielwerte zeigt die Oberfläche selbst als
  Balken aus den Datenfunktionen), Einzelheiten als kleine Tabelle (bis 8 Zeilen, 3 Spalten, Begründung im Tooltip).
- Keine doppelten Angaben: was die Seitenleiste schon zeigt (Schwerpunkt in der Auswahl, Stand im Fuß, Zufriedenheit der Stände
  als Spielwert), steht nicht noch einmal im Kopf; Einzelheiten wiederholen den Kopf nicht.

Schlüssel (alle über ingame.loc() entschärft): RG_K_<ID>_K<r><A|B><L|W|T> Kopf (Zeile r, Zelle A/B: Bezeichnung, Wert, Tooltip),
RG_K_<ID>_W<i> Warnungen, RG_K_<ID>_BL / _B1…_B10 Segmentbalken, RG_K_<ID>_D<r><A|B|C|T> Einzelheiten, RG_K_<ID>_DH Hinweis.
Kacheln des Hauptreiters Ratgeber hängen am Schwerpunkt (Endung _<schwerpunkt>, „_“ = noch nichts gewählt = erster).

Mod 0.28 (03.11., Nutzer: „eigentlich haben doch alle eigenschaften und modifikatoren symbole ingame, kannst du diese benutzen in
allen fenstern wenn möglich, gerade güter.“ – „sind links und öffnen der entsprechenden fenster möglich?“ – „ja, so bauen“):
- Symbole: Kopfwerte bekommen das passende Text-Symbol des Spiels (KOPF_SYMBOL, Namen aus font_icons.gui des Spiels), Zeilen mit
  Gütern, Gebäuden, Ständen, Krankheiten, Institutionen, Kabinettsaktionen und Gesetzen ihr eigenes (eu5ratgeber/ingame_symbole.py).
  Im Text als Platzhalter SYM_A name SYM_E – übersteht ingame.loc() und wird dort am Ende zu „@name!“ (wie FARBE zu „#“).
- Links (nur öffnen, nie ausführen): je Zeile der Einzelheiten RG_K_<ID>_D<r>L (Link-Typ aus LINK_TYPEN), _D<r>Z (Ziel: Name einer
  Seitenleiste des Spiels, Ort, Gebäudetyp oder Land) und bei Kacheln mit Baumodus _D<r>O (Ort zum Bauen). Ziel-Schlüssel nur
  aus den Daten (Spielschlüssel); fehlt einer, kein Link. Der Tooltip der Zeile nennt den Klick („Klick: …“). Welche Link-Typen
  eine Kachel hat, steht in LINKS – die Oberfläche baut nur dafür Knöpfe."""
import json
import math
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from . import ingame_tips as tips
from . import sprache
from .sprache import ue

STRICH = "–"
LANG = 30                   # Zeichen: längere Kopfwerte bekommen eine eigene Zeile über die ganze Breite
MAX_WERT = 70               # Zeichen: längere Kopfwerte gekürzt (voller Text im Tooltip) – eine Zeile in der Seitenleiste
SEGMENTE = 10
FARBE = tips.FARBE          # Platzhalter für „#“ der Farbcodes (#G … #!): übersteht ingame.loc, wird danach zu „#“
SYM_A, SYM_E = "\x02", "\x03"   # Platzhalter für ein Text-Symbol „@name!“ (Mod 0.28): übersteht ingame.loc, wird dort umgesetzt
# Spieltexte, aus denen die Kacheln Zahlen lesen, deutsch und englisch: RELIGION_REFORM_DESIRE, ESTATE_ECO_INFO_io_expense, MORALE_IMPACT_MAINTENANCE;
# der Name des Erben trägt den Titel (game_concept_heir)
REFORM_WERT = re.compile(r"(?:liegt bei| is)\s*([-+]?[\d.]+)%")
REFORM_AENDERUNG = re.compile(r"(?:monatlich um|changing by)\s*([-+]?[\d.]+)%")
ZEHNT = re.compile(r"(?:Zehnt|Tithe):\s*([-+]?[\d.]+)")
MORAL_FAKTOR = re.compile(r"(?:multipliziert dies mit|multiplies it by)\s*([\d.]+)")
ERBE_TITEL = re.compile(r"^(?:Erbe|Heir)\s+")

# ---------------------------------------------------------------- Symbole (Mod 0.28)
_ERLAUBT = {"rg": set(), "spiel": set()}       # eigene Symbole des installierten Mods, Symbole des Spiels (symbole_setzen)


def symbole_setzen(eigene, spiel):
    """Welche Text-Symbole die Texte benutzen dürfen: eigene (rg_…, die der installierte Mod definiert) und die des Spiels."""
    _ERLAUBT["rg"], _ERLAUBT["spiel"] = set(eigene or ()), set(spiel or ())


def sym(n):
    """Platzhalter für das Text-Symbol n (mit Leerzeichen danach) – nur, wenn es definiert ist; sonst nichts."""
    return f"{SYM_A}{n}{SYM_E} " if n and (n in _ERLAUBT["rg"] or n in _ERLAUBT["spiel"]) else ""


def gut_sym(k):
    return sym(f"rg_g_{k}") if k else ""


def geb_sym(k):
    return sym(f"rg_b_{k}") if k else ""


def inst_sym(k):
    return sym(f"rg_i_{k}") if k else ""


def krank_sym(k):
    return sym(f"rg_d_{k}") if k else ""


def kab_sym(k):
    return sym(f"rg_c_{k}") if k else ""


def gesetz_sym(k):
    return sym(f"rg_l_{k}") if k else ""


def stand_sym(k):
    """Stände: Symbole des Spiels (nobles_estate …, font_icons.gui)."""
    return sym(k) if k else ""


def ohne_symbole(s):
    """Text ohne Symbol-Platzhalter und ohne fertige „@name! “ (Vergleich, Länge)."""
    return re.sub(r"@\w+!\s?", "", re.sub(SYM_A + r"\w+" + SYM_E + r"\s?", "", str(s)))


def _sichtbar(s):
    """Länge wie in der Seitenleiste: ein Symbol zählt wie zwei Zeichen."""
    return re.sub(SYM_A + r"\w+" + SYM_E, "··", str(s))


# Kopfwert-Bezeichnung -> Text-Symbol des Spiels (main_menu/gui/shared/font_icons.gui; der Test prüft jeden Namen)
KOPF_SYMBOL = {
    "Empfehlungen": "agenda", "wichtig": "warning_icon", "mittel": "hint", "später": "time",
    "Bedarf": "goods", "knapp im Heimatmarkt": "shortage", "vorne": "goods", "im Markt nicht vorhanden": "market_needs",
    "nächster Schritt": "construction", "Heimatmarkt": "market", "Vergleich mit": "market",
    "Abweichungen": "policy", "Politischer Einfluss": "political_influence", "Kabinett": "cabinet_action", "Rivalen": "rival",
    "Gold": "gold", "Saldo / Monat": "gold_balance", "Einkommen / Monat": "income", "Ausgaben / Monat": "expense",
    "Inflation": "inflation", "Einkommen / Jahr": "income", "Kreditwürdigkeit": "creditworthiness", "Schulden": "expense",
    "Gewinn der Gebäude / Monat": "building", "Gebäude / Typen": "building_levels", "im Bau": "construction",
    "bester Typ": "arrow_up", "schwächster Typ": "arrow_down",
    "Handelseinkommen / Monat": "profit_trade", "Handelswert": "trade", "Gewinn der Routen": "profit_trade",
    "Händlerkapazität": "trade_capacity", "Routen": "trade",
    "am meisten produziert": "output", "fehlen am meisten": "shortage", "günstigste ggü. Grundpreis": "price_decrease",
    "teuerste ggü. Grundpreis": "price_increase", "eigene Güter": "goods", "Güter": "goods",
    "Steuergrundlage / möglich": "tax_base", "fehlt durch Kontrolle": "control", "Orte": "location", "Ø Nähe": "proximity_cost",
    "Ø Marktzugriff": "market",
    "Bevölkerung (Tsd.)": "population", "Bevölkerungskapazität genutzt": "population", "Orte / Provinzen": "province",
    "Ø Kontrolle": "control", "Entwicklung": "development", "Ø Bildung": "literacy",
    "Herrscher (Verw./Dipl./Mil.)": "ruler", "Regierungszeit": "time", "Erbe": "heir", "Gesetze / Reformen": "law",
    "Steuern der Stände / Monat": "gold", "Privilegien": "privilege", "Ø Zufriedenheit der Stände": "satisfaction",
    "Glaubenseinigkeit": "religious_unity", "Glaubenseinfluss": "religious_influence",
    "Fortschritte erforscht": "advance", "Forschung je Monat": "advance", "Institutionen eingeführt": "advance",
    "Zeitalter": "time",
    "laufende Ausbrüche (Welt)": "death", "Tote laut Spielstand": "death", "Schwarzer Tod": "death",
    "Rivalen (ihre Meinung von uns)": "rival", "Klientelländer": "subject", "Kriegsgegner": "army_strength",
    "Personalunion": "country", "Kriegsgründe": "casus_belli",
    "Kriegsgelegenheiten": "casus_belli", "Unser Offensivbündnis": "alliance", "Heer (Tsd. Mann)": "army_strength",
    "Mannstärke (Tsd.)": "manpower", "Verteidigungsbündnis": "alliance", "Stabilität": "stability",
    "Kriegsmüdigkeit": "war_exhaustion", "Gold / Saldo": "gold", "Laufende Kriege": "army_strength",
    "Gründungen": "country", "Gewählt": "country", "Orte (eigene / nötig)": "location", "Bedingungen": "trigger_yes",
    "Unser Grad": "country", "Spielregel": "hint", "Kultur": "culture",
    "Militärstärke": "army_strength", "Kriege": "army_strength", "Mannstärke": "manpower", "Seeleute": "sailors",
    # Werte aus /api/alles und /api/bevoelkerung (04.11.)
    "Zölle / Monat": "expense", "Städte": "city", "Gebäudeunterhalt": "expense", "Großmacht": "power", "Rang": "country",
    "Hauptstadt": "city_capital", "Ø Zufriedenheit": "satisfaction", "Hauptkultur": "primary_culture", "Staatsreligion": "religion",
    "größter Pop-Typ": "population", "Parlament": "parliament", "Reformwunsch": "religion", "Toleranz": "tolerated_culture",
    "Kulturtradition": "cultural_tradition", "Kultureinfluss": "cultural_influence", "Gläubige weltweit": "religion",
    "Kardinäle": "clergy", "Sakralstätten": "holy_site", "Zehnt / Monat": "expense", "Glaubenseinfluss / Monat": "religious_influence",
    "Akzeptierte Kulturen": "accepted_culture", "Angleichungsrate": "pop_assimilation_speed", "Kunstwerke / Künstler": "art_work",
    "Einführungskosten Institutionen": "advance", "Verbreitung Institutionen": "advance", "Seuchenwiderstand": "disease_resistance",
    "Tote durch Krankheiten": "death", "befallene eigene Orte": "location", "in unserem Land": "death",
    "Bündnisse": "alliance", "Diplomaten": "diplomacy", "Diplomatiekapazität": "diplomatic_capacity",
    "Diplomatieruf": "diplomatic_reputation", "Antagonismus gegen uns": "antagonism", "Aufgebote": "levy", "Regulärtruppen": "regular",
    "Schiffe": "ship", "Armeetradition": "army_tradition", "Marinetradition": "navy_tradition", "Moral Heer / Flotte": "morale",
    "Festungsschwelle": "control", "Disziplin": "army_strength", "Kampf-Effizienz (Aufgebote)": "levy", "Militärtaktiken": "army_strength",
    "Belagerungsfähigkeit": "army_strength"}


def kopf_text(l):
    """Bezeichnung eines Kopfwerts in der Sprache der Ausgabe. Im Code bleibt sie deutsch, sie ist Schlüssel von KOPF_SYMBOL; Zusätze in
    Klammern („Gold (live 1356.10.1)“, „Kulturtradition (Bayerisch)“) bleiben stehen."""
    kurz = re.sub(r" \(.*\)$", "", str(l))
    return ue(str(l)) if kurz == l or l in sprache.katalog() else ue(kurz) + str(l)[len(kurz):]


def kopf_symbol(l):
    """Symbol einer Kopfwert-Bezeichnung („Gold (live 1356.10.1)“ wie „Gold“)."""
    return sym(KOPF_SYMBOL.get(l) or KOPF_SYMBOL.get(re.sub(r" \(.*\)$", "", str(l))))


# Orte in Tabellen als Textlink des Spiels: in der Übersetzung nimmt GetLocationByKey den festen Schlüssel an, den die Oberfläche nicht
# annimmt (Test 0.28: GetLocationByKey(Localize(…)) -> Fehler); der Name trägt dann die Verknüpfung des Spiels (GetName, „format link“).
# ingame.loc macht aus dem Platzhalter [GetLocationByKey('<key>').GetName]; die Zelle ist dafür nicht durchlässig (mod_ingame.details)
ORT_A, ORT_E = "\x04", "\x05"
ORT_SPALTE = {"ORTE": "A", "PROD": "B", "WPLAN": "C"}


# Location.GetKey der Oberfläche ist die Nummer des Orts, nicht sein Name (Test 0.28.3: „3574“ = targoviste) – die Ort-Suche vergleicht mit ihr
_ORT_ID = {}


def ort_ids_setzen(d):
    """Spielschlüssel -> Nummer der eigenen Orte aus dem Spielstand, vor dem Bau der Links."""
    _ORT_ID.clear()
    _ORT_ID.update({o["key"]: str(o["id"]) for o in (d.get("aktuell") or {}).get("orte") or [] if o.get("key") and o.get("id") is not None})


def ort_text(key, name=None):
    return f"{ORT_A}{key}{ORT_E}" if key and _KEY.fullmatch(str(key)) else (name or STRICH)


# ---------------------------------------------------------------- Links (Mod 0.28: nur öffnen, nie ausführen)
LINK_TYPEN = ("ansicht", "bau", "ort", "land")
# Seitenleisten des Spiels für OpenLateralView – nur Namen, die das Spiel selbst so aufruft (Test: grep in game/*/gui)
ANSICHTEN = {"government": ue("Regierung"), "laws": ue("Gesetze"), "government_reforms": ue("Regierungsreformen"), "advances": ue("Fortschritte"),
             "economy": ue("Wirtschaft"), "production": ue("Produktion"), "goods_overview": ue("Güter"), "markets_overview": ue("Märkte"),
             "diplomacy": ue("Diplomatie"), "form_new_country": ue("Ländergründung"), "locations_list": ue("Orte"),
             "military_ledger": ue("Militär"), "wars_ledger": ue("Kriege"), "societal_values": ue("Gesellschaftswerte")}
# Link-Typen je Kachel (Zeilen der Einzelheiten); fehlt eine Kachel, haben ihre Zeilen keinen Link
LINKS = {"WPLAN": ("bau", "ort"), "SSTRAT": ("ansicht",), "FIN": ("ansicht",), "PROD": ("ort",), "HANDEL": ("ansicht",),
         "GUETER": ("ansicht",), "ORTE": ("ort",), "REG": ("ansicht",), "STAENDE": ("ansicht",), "FORSCH": ("ansicht",),
         "DIPL": ("land",), "NACHB": ("land",), "GRUEND": ("ansicht",), "MIL": ("ansicht",)}
# Link-Typen je Kartengruppe der Oberfläche (Schritte S, Empfehlungen E, Warnungen W, Gründung GR, Tabelle jetzt/Vorschlag T) –
# Empfehlungen, Warnungen und Gründung öffnen nur Seitenleisten, die Tabelle auch die Diplomatie
KARTEN_LINKS = {"S": LINK_TYPEN, "E": ("ansicht", "ort"), "W": ("ansicht",), "GR": ("ansicht",), "T": ("ansicht", "land")}
# Kachel einer Empfehlung (empfehlungen.py „kachel“) -> Seitenleiste des Spiels
EMPF_ANSICHT = {"finanzen": "economy", "handel": "markets_overview", "gueter": "goods_overview", "produktion": "production",
                "wirtschaftsplan": "production", "staende": "government", "diplomatie": "diplomacy", "nachbarn": "diplomacy",
                "gruendung": "form_new_country", "orte": "locations_list", "forschung": "advances"}
_KEY = re.compile(r"[a-z][a-z0-9_]*")
_TAG = re.compile(r"[A-Z][A-Z0-9]{2,5}")


def ansicht(v):
    return {"typ": "ansicht", "z": v, "o": "", "text": ue(t"Klick: Fenster {ANSICHTEN[v]} öffnen")} if v in ANSICHTEN else None


def ort_link(key, name=None):
    return ({"typ": "ort", "z": _ORT_ID[key], "o": "", "text": ue(t"Klick: {name or key} auswählen, Karte dorthin")}
            if key in _ORT_ID else None)


def bau_link(geb, geb_name, ort_key, ort_name=None):
    """Bau-Schritt: öffnet den Ort, dort lässt sich bauen (den Baumodus eines Gebäudetyps erreicht die Seitenleiste nicht, Test 0.28.1)."""
    if not (geb and _KEY.fullmatch(str(geb)) and ort_key in _ORT_ID):
        return None
    return {"typ": "bau", "z": geb, "o": _ORT_ID[ort_key], "text": ue(t"Klick: {ort_name or ort_key} öffnen, dort {geb_name or geb} bauen")}


def land_link(tag, name=None):
    return ({"typ": "land", "z": tag, "o": "", "text": ue(t"Klick: Diplomatie mit {name or tag}")}
            if tag and _TAG.fullmatch(str(tag)) else None)


def empf_link(r):
    """Link einer Empfehlung: mit Ort (Ausbau) der Ort, sonst über ihre Kachel; Krieg -> Kriege."""
    i = str(r.get("ort_id")) if r.get("ort_id") is not None else None
    if i in _ORT_ID.values():
        return {"typ": "ort", "z": i, "o": "", "text": ue(t"Klick: {r.get('ort') or ue('Ort')} öffnen")}
    k = str(r.get("kachel") or "")
    return ansicht("wars_ledger" if k.startswith("krieg") else EMPF_ANSICHT.get(k))


def empf_sym(r):
    """Symbol einer Empfehlung aus ihrer Kennung (geb:<gebäude>, stand:<stand>, krank:<krankheit>)."""
    art, _, key = str(r.get("id") or "").partition(":")
    return {"geb": geb_sym, "stand": stand_sym, "krank": krank_sym}.get(art, lambda _k: "")(key)

# Kachel: (ID, Titel, Hauptreiter, Reiter-Text, Bereich, je Schwerpunkt, Kopfzeilen, Einzelheiten-Zeilen, Segmentbalken,
#          Spalten der Einzelheiten (Kopf A, B, C), Einzelheiten zu Beginn offen – seit Test 0.28 alle: „können in allen reitern
#          ausgeklappt bleiben … es ist genug platz da“)
# Bereich -> Banner, Farbe und Symbol (ingame.BEREICHE); Hauptreiter/Unterreiter wie im Auftrag 03.11.
KACHELN = (
    ("EMPF", "Empfehlungen", "ratgeber", "Empfehlungen", "other", True, 2, 0, False, ("", "", ""), True),
    ("WPLAN", "Wirtschaftsplan", "ratgeber", "Wirtschaftsplan", "production", True, 5, 6, False, ("Nr.", "Bau", "Ort"), True),
    ("SSTRAT", "Startstrategie", "ratgeber", "Startstrategie", "government", True, 3, 6, False, ("Bereich", "Jetzt", "Vorschlag"),
     True),
    ("FIN", "Finanzen", "wirtschaft", "Finanzen", "economy", False, 4, 8, False, ("Posten", "Gold / Monat", "Regler"), True),
    ("PROD", "Produktion", "wirtschaft", "Produktion", "production", False, 3, 8, False, ("Gebäude", "Ort", "Gewinn / Monat"),
     True),
    ("HANDEL", "Handel", "wirtschaft", "Handel", "economy", False, 4, 8, True, ("Gut", "Richtung", "Gewinn / Monat"), True),
    ("GUETER", "Güter", "wirtschaft", "Güter", "production", False, 5, 8, False, ("Gut", "Saldo / Monat", "Preis : Grundpreis"),
     True),
    ("ORTE", "Orte", "wirtschaft", "Orte", "economy", False, 4, 8, True, ("Ort", "Steuer / möglich", "Kontrolle"), True),
    # Land: 4 Kopfzeilen, seit das Symbol vor der Bezeichnung mitzählt (Prüfung 03.11.: „Bevölkerungskapazität genutzt“ allein)
    ("LAND", "Land und Leute", "staat", "Land", "society", False, 8, 6, True, ("Wert", "Stand", ""), True),
    ("REG", "Regierung und Gesellschaft", "staat", "Regierung", "government", False, 6, 18, False, ("Bereich", "Gesetz / Reform", ""),
     True),
    ("STAENDE", "Stände und Privilegien", "staat", "Stände", "society", False, 2, 7, True,
     ("Stand", "Steuern (Spielstand)", "Privilegien"), True),
    ("REL", "Religion, Kultur und Kunst", "staat", "Religion", "society", False, 8, 0, False, ("", "", ""), True),
    ("FORSCH", "Forschung", "staat", "Forschung", "other", False, 4, 8, True, ("Institution", "bei uns", "Ursprung"), True),
    ("KRANK", "Krankheiten", "staat", "Krankheiten", "society", False, 5, 8, False, ("Krankheit", "Ausbruch", "befallene Orte"),
     True),
    ("DIPL", "Diplomatie und Untertanen", "aussen", "Diplomatie", "country", False, 7, 8, False,
     ("Land", "Beziehung", "ihre Meinung"), True),
    ("NACHB", "Nachbarn und Kriegsgelegenheiten", "aussen", "Nachbarn", "country", False, 5, 8, False,
     ("Land", "Bewertung", "Stärke uns : sie"), True),
    ("GRUEND", "Ländergründung", "aussen", "Gründung", "expansion", False, 4, 6, True, ("Land", "Orte", "Bedingungen"), True),
    ("MIL", "Militär und Kriege", "aussen", "Militär", "expansion", False, 9, 6, True, ("Wert", "Stand", ""), True),
)
# Was die Kachel zeigt – fester Text unter dem Banner (Test 0.28: „die einzelheiten müssen noch besser erklärt werden, was genau
# angezeigt wird“); was die Tabelle zeigt, steht direkt darüber (hinweis, mit den Zahlen des Stands)
ERKLAERUNG = {
    "EMPF": "Was der Ratgeber jetzt vorschlägt, Wichtigstes zuerst (hoch, mittel, niedrig). Innerhalb einer Stufe steht vorn, was zum "
            "gewählten Schwerpunkt passt. Die Begründung steht im Tooltip, ein Klick öffnet das passende Fenster.",
    "WPLAN": "Bauplan zum gewählten Schwerpunkt: welche Güter dafür im Heimatmarkt knapp sind (Preis über dem Grundpreis) und was "
             "als Nächstes gebaut werden sollte. „Vergleich mit“ nennt die Märkte, mit denen die Preise verglichen werden.",
    "SSTRAT": "Welche Einstellungen zum gewählten Schwerpunkt passen. Abweichungen = so viele deiner Einstellungen weichen vom "
              "Vorschlag ab. Erste Schritte und die Tabelle jetzt/Vorschlag stehen weiter unten.",
    "FIN": "Deine Kasse wie im Wirtschaftsfenster, Beträge in Gold je Monat. Klammer = Veränderung zum Vormonat: grün besser, rot "
           "schlechter. Inflation und Schulden stehen rot, sobald sie über 0 liegen.",
    "PROD": "Was deine Gebäude im Monat abwerfen (Gewinn laut Spiel, live). Bester und schwächster Typ: alle Gebäude einer Art "
            "zusammengerechnet.",
    "HANDEL": "Was dein Land am Handel verdient. Gewinn der Routen = was deine Händler verdienen; Handelseinkommen = der Teil davon "
              "für die Staatskasse. Händlerkapazität: was deine Händler bewegen können, in Klammern der genutzte Teil.",
    "GUETER": "Deine Güterbilanz: was deine Orte fördern und deine Gebäude herstellen, gegen das, was deine Gebäude verbrauchen "
              "(Nennwerte je Monat). ×-Werte = Preis im Heimatmarkt geteilt durch den Grundpreis: ×1,00 ist normal, darunter billig, "
              "darüber teuer.",
    "ORTE": "Steuergrundlage deiner Orte. „Möglich“ ist der Wert bei voller Kontrolle – die Differenz geht durch zu wenig Kontrolle "
            "verloren. Nähe und Marktzugriff sind Durchschnitte aller Orte. Gebäudeunterhalt = Landesgebäude aller Orte, Gold je Monat.",
    "LAND": "Eckdaten deines Landes. Bevölkerung in Tausend; Kapazität = wie viele Menschen deine Orte tragen können. Hauptkultur "
            "und Staatsreligion = Anteil der Bevölkerung.",
    "REG": "Herrscher (Verwaltung / Diplomatie / Militär, Alter), Kabinett mit dem Fortschritt der Aktionen, Politischer Einfluss, "
           "Zahl der Gesetze und Reformen.",
    "STAENDE": "Je Stand direkt aus dem Spiel: Balken = Zufriedenheit, Macht = Anteil an der Macht im Land, Ausgewogenheit = Wert, "
               "dem die Zufriedenheit zustrebt.",
    "REL": "Religion, Kultur und Kunst laut Spiel. Toleranz: eigener Glaube / Ketzer / Heiden. Kulturtradition und Kultureinfluss "
           "gelten für deine Hauptkultur, Klammer = Veränderung je Monat. Akzeptierte Kulturen: genutzt / Kapazität.",
    "FORSCH": "Laufende Forschung und Tempo. Institutionen: eingeführt = bei uns angenommen, entstanden = in der Welt vorhanden, bei "
              "uns noch nicht.",
    "KRANK": "Krankheiten: oben unser Land (live), die Tabelle zeigt die Ausbrüche der Welt laut Spielstand. Seuchenwiderstand = "
             "Modifikator des Landes, befallene eigene Orte = Orte mit Ausbreitung über 0.",
    "DIPL": "Deine Beziehungen zu anderen Ländern. Die Zahl ist die Meinung des Landes von uns (−200 bis +200). Großmacht = eines "
            "der mächtigsten Länder der Welt laut Spiel. Diplomaten und Diplomatiekapazität: jetzt / Höchstwert.",
    "NACHB": "Lohnt ein Krieg? Oben unsere Stärke, unten die Bewertung des Ratgebers je Land. Stärke uns : sie über 1 heißt: wir sind "
             "stärker.",
    "GRUEND": "Länder, die du gründen könntest. Orte und Bedingungen zeigen, was noch fehlt. Unser Grad = Rang unseres Landes unter "
              "den Gründungen; Spielregel = Einstellung „Gründbare Länder“.",
    "MIL": "Deine Streitkräfte wie im Militärfenster. Aufgebote und Regulärtruppen in Mann: aufgestellt / möglich – 0 heißt: zurzeit "
           "keine aufgestellt, Aufgebote lassen sich nur im Krieg oder gegen Rebellen ausheben. Mannstärke und Seeleute in Tausend, "
           "jetzt / Höchstwert. Festungsschwelle: genutzt / Grenze.",
}
IDS = [k[0] for k in KACHELN]
K = {k[0]: k for k in KACHELN}


def schluessel(kid, fk=None):
    """Alle Schlüssel einer Kachel (fk = Schwerpunkt bei Ratgeber-Kacheln, "" = noch nichts gewählt)."""
    _, _, _, _, _, je_fk, zeilen, dz, balken, spalten, _ = K[kid]
    e = f"_{fk}" if je_fk else ""
    out = [f"RG_K_{kid}_K{r}{z}{t}{e}" for r in range(1, zeilen + 1) for z in "AB" for t in "LWT"]
    out += [f"RG_K_{kid}_W{i}{e}" for i in range(1, 4)]
    if balken:
        out += [f"RG_K_{kid}_BL{e}"] + [f"RG_K_{kid}_B{i}{e}" for i in range(1, SEGMENTE + 1)]
    # Spalte C nur bei dreispaltigen Einzelheiten – die Oberfläche hat sonst keine (Prüfung 03.11.: 20 tote Schlüssel)
    out += [f"RG_K_{kid}_D{r}{t}{e}" for r in range(1, dz + 1) for t in ("ABCT" if spalten[2] else "ABT") + link_teile(kid)]
    return out + ([f"RG_K_{kid}_DH{e}"] if dz else [])


def link_teile(kid):
    """Link-Schlüssel einer Zeile (Mod 0.28): L Typ, Z Ziel, O Ort (nur mit Baumodus) – leer ohne Links."""
    lt = LINKS.get(kid) or ()
    return ("LZ" + ("O" if "bau" in lt else "")) if lt else ""


# ---------------------------------------------------------------- Zahlen wie auf der Seite (app.js: fmt, pct, sgn, trend)
def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(v)


def fmt(v, n=1):
    """Wie Intl.NumberFormat("de-DE") mit n Nachkommastellen: kürzeste Dezimaldarstellung, kaufmännisch gerundet, Tausenderpunkt."""
    if not num(v):
        return STRICH
    q = Decimal(repr(float(v))).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP)
    return sprache.ziffern(f"{q:,.{n}f}")


def pct(v, n=0):
    return ue(t"{fmt(v * 100, n)} %") if num(v) else STRICH


def sgn(v, n=1):
    return ("+" if v > 0 else "") + fmt(v, n) if num(v) else STRICH


def trend(delta, n=1, gut=1):
    """Veränderung zum Vormonat wie design.js trend(): unter einer halben Einheit der letzten Stelle nichts; grün/rot wie die
    Kennzahl Gold („73 (#G +2,7#!)“), neutral (gut = 0) ohne Farbe."""
    if not num(delta) or abs(delta) < 0.5 * 10 ** -n:
        return ""
    f = "" if gut == 0 else f"{FARBE}G " if delta * gut > 0 else f"{FARBE}R "
    return f" ({f}{sgn(delta, n)}{FARBE + '!' if f else ''})"


def rot(s, ja):
    """Kopfwert rot (#R … #!) statt einer Warnung mit demselben Inhalt."""
    return f"{FARBE}R {s}{FARBE}!" if ja and s != STRICH else s


def _erste(x):
    """Wie Object.values(x)[0] || {}: die Mod-Werte des Spielerlandes stehen unter einem Schlüssel."""
    return next(iter((x or {}).values()), None) or {}


def erst(*xs):
    """Erster Wert, der nicht None ist (?? in app.js)."""
    return next((x for x in xs if x is not None), None)


def ab(v, n=2):
    """Abgerundet wie die Fenster des Spiels (app.js ab: Moral 1,643 -> 1.64)."""
    return math.floor(v * 10 ** n + 1e-6) / 10 ** n if num(v) else v


def zahl(t):
    """Zahl aus einem Spieltext („3,793“ -> 3793; app.js zahl)."""
    m = re.search(r"[\d,.]+", str(t if t is not None else ""))
    try:
        return float(m.group(0).replace(",", "")) if m else None
    except ValueError:
        return None


def menge(t):
    """„60.749M“ / „194K“ (Spieltext) -> Mio./Tsd.; ohne Zahl None (app.js menge zeigt dann einen Strich)."""
    m = re.search(r"([\d.,]+)\s*([MK])?", str(t or ""))
    if not m:
        return None
    x = float(m.group(1).replace(",", ""))
    return ue(t"{fmt(x, 2)} Mio.") if m.group(2) == "M" else ue(t"{fmt(x, 0)} Tsd.") if m.group(2) == "K" else fmt(x, 0)


def saldo_farbe(v, n=2):
    """Saldo mit Vorzeichen, grün über 0, rot unter 0 (Tabelle Güter)."""
    if not num(v):
        return STRICH
    return f"{FARBE}{'G' if v > 0 else 'R'} {sgn(v, n)}{FARBE}!" if v else fmt(v, n)


def vorm(s):
    return s[-1] - s[-2] if len(s) > 1 else None


def summe(xs):
    return sum(x for x in xs if num(x))


def mittel(xs):
    n = [x for x in xs if num(x)]
    return sum(n) / len(n) if n else None


def live_reihe(d, key, n=24):
    return [r.get(key) for r in d.get("live") or [] if num(r.get(key))][-n:]


def _js_ordnung(keys):
    """Reihenfolge von Object.keys in JavaScript: ganzzahlige Schlüssel aufsteigend, dann die übrigen in Einfügereihenfolge."""
    keys = list(keys)
    zahl = [k for k in keys if re.fullmatch(r"0|[1-9]\d{0,9}", str(k)) and int(k) < 2 ** 32 - 1]
    return sorted(zahl, key=int) + [k for k in keys if k not in zahl]


def _de_sort(s):
    """Sortierschlüssel wie localeCompare(…, "de"): ohne Akzente/Umlaute, Groß-/Kleinschreibung egal."""
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().casefold()


# ---------------------------------------------------------------- Daten zusammenführen (app.js prepare)
def _prep(d):
    LD, W, A = d.get("live_details") or {}, d.get("wissen") or {}, d.get("aktuell") or {}
    lvs = d.get("live") or []
    lv = lvs[-1] if lvs else {}
    live_ort = {o.get("id"): o for o in LD.get("orte") or []}
    live_geb, save_geb = LD.get("gebaeude") or [], A.get("gebaeude") or []
    use = len(live_geb) > 0
    nach = {}
    for b in (live_geb if use else save_geb):
        e = ({"id": b.get("id"), "typ": b.get("typ"), "name": b.get("name"), "stufe": b.get("level"), "gewinn": b.get("profit"),
              "moeglich": b.get("potential_profit"), "besch": b.get("employed"), "plaetze": b.get("employment_size"),
              "ort_id": b.get("ort_id"), "ort": b.get("ort")} if use else
             {"id": b.get("id"), "typ": b.get("typ"), "name": b.get("name"), "stufe": b.get("stufe"), "gewinn": b.get("gewinn"),
              "ort_id": b.get("ort_id"), "ort": b.get("ort")})
        nach.setdefault(e["ort_id"], []).append(e)
    wo = W.get("orte") or {}
    orte = []
    for o in A.get("orte") or []:
        L = live_ort.get(o.get("id")) or {}
        w = wo.get(o.get("id")) or wo.get(str(o.get("id"))) or {}
        pops = o.get("pops_typen") or {}
        bev = L.get("population") if L.get("population") is not None else summe(v.get("groesse") for v in pops.values())
        orte.append({**o, "L": L, "w": w, "gebaeude": nach.get(o.get("id")) or [], "bev": bev})
    all_geb = [g for k in _js_ordnung(nach) for g in nach[k]]
    # Ortsschlüssel für Links (Mod 0.28): je Ort-ID und je Name (nur eindeutige Namen der eigenen Orte)
    key_id = {str(o.get("id")): o.get("key") for o in A.get("orte") or [] if o.get("key")}
    namen = [o.get("name") for o in A.get("orte") or [] if o.get("key")]
    key_name = {o.get("name"): o.get("key") for o in A.get("orte") or [] if o.get("key") and namen.count(o.get("name")) == 1}
    # /api/alles und /api/bevoelkerung wie die Seite (04.11.; d["alles"], d["bev"] aus ingame.daten) – ohne sie bleiben die Felder leer
    AW, AT = (d.get("alles") or {}).get("werte") or {}, (d.get("alles") or {}).get("texte") or {}
    return {"AW": AW, "AT": AT, "L": _erste(AW.get("land")), "LM": _erste(AW.get("landmod")), "TL": _erste(AT.get("land")),
            "B": d.get("bev") or {},
            "LD": LD, "W": W, "A": A, "lv": lv, "orte": orte, "useLiveGeb": use, "allGeb": all_geb, "ortKeyId": key_id,
            "ortKeyName": key_name}


def ort_key(P, ort_id=None, name=None):
    """Spielschlüssel eines eigenen Orts (über die ID, sonst über den Namen) – None, wenn unbekannt."""
    return ((P.get("ortKeyId") or {}).get(str(ort_id)) if ort_id is not None else None) or (P.get("ortKeyName") or {}).get(name)


def _kz(l, v, t="", u=""):
    """Kopfwert: Bezeichnung, Wert, Tooltip (u = Zusatz unter dem Wert auf der Seite -> Tooltip)."""
    return (l, v, " – ".join(x for x in (u, t) if x))


def _spiel_werte(d):
    """design.js spielWerte: wie im Wirtschaftsfenster (Daten-Mod) – Einnahmen, Saldo, Ausgaben, Handelseinnahmen."""
    L = [r for r in d.get("live") or [] if num(r.get("einkommen_spiel")) and num(r.get("saldo_spiel"))]
    if not L:
        return None
    r, sl = L[-1], L[-24:]
    live = d.get("live") or []
    h_rows = [x for x in live if num(x.get("handel_gewinn")) and num(x.get("handel_mod"))][-24:]
    h_last = ([x for x in live if num(x.get("handel_gewinn"))] or [None])[-1]
    mods = [x for x in live if num(x.get("handel_mod"))]
    mod = mods[-1]["handel_mod"] if mods else None

    def m_idx(x):
        j, m = (str(x.get("datum")).split(".") + ["0", "0"])[:2]
        return int(j) * 12 + int(m)
    h_vorm = (h_rows[-1]["handel_gewinn"] * h_rows[-1]["handel_mod"] - h_rows[-2]["handel_gewinn"] * h_rows[-2]["handel_mod"]
              if len(h_rows) > 1 and m_idx(h_rows[-1]) - m_idx(h_rows[-2]) == 1 else None)
    return {"datum": r.get("datum"), "ein": r["einkommen_spiel"], "saldo": r["saldo_spiel"], "aus": r["einkommen_spiel"] - r["saldo_spiel"],
            "handel": h_last["handel_gewinn"] * mod if h_last and num(mod) else None, "handelVorm": h_vorm,
            "ser": {"ein": [x["einkommen_spiel"] for x in sl], "saldo": [x["saldo_spiel"] for x in sl],
                    "aus": [x["einkommen_spiel"] - x["saldo_spiel"] for x in sl],
                    "handel": [x["handel_gewinn"] * x["handel_mod"] for x in h_rows]}}


def _leer():
    return {"kopf": [], "warn": [], "balken": None, "details": [], "hinweis": ""}


# ---------------------------------------------------------------- Ratgeber (je Schwerpunkt)
def empfehlungen(d, P, fk):
    E = [r for r in d.get("empfehlungen") or [] if not r.get("fokus") or r.get("fokus") == fk]

    def n(p):
        return len([r for r in E if r.get("prio") == p])
    k = _leer()
    # die drei wichtigsten (small) stehen als Karten darunter – nicht doppelt
    k["kopf"] = [_kz("Empfehlungen", str(len(E))), _kz("wichtig", str(n("hoch"))), _kz("mittel", str(n("mittel"))),
                 _kz("später", str(n("niedrig")))]
    return k


def wirtschaftsplan(d, P, fk):
    WP = d.get("wirtschaftsplan") or {}
    F = (WP.get("fokusse") or {}).get(fk)
    k = _leer()
    if not F:
        return k
    gnm = ((P["W"].get("namen") or {}).get("gueter") or {})
    G = WP.get("gueter") or {}

    def gname(g):
        return gut_sym(g) + ((G.get(g) or {}).get("name") or gnm.get(g) or g)

    def verh(g):
        v = (G.get(g) or {}).get("verh")
        return f"{fmt(v, 2)}×" if num(v) else STRICH
    gueter, fehlen, plan = F.get("gueter") or [], F.get("fehlen") or [], F.get("plan") or []
    # „Schwerpunkt“ steht in der Auswahl über den Reitern – nicht doppelt
    if not gueter:
        k["kopf"].append(_kz("Bedarf", ue("keine Daten"), ue("Für diesen Schwerpunkt fehlen im Spielstand die Werte (älterer Stand?)")))
    elif F.get("reihung") == "knapp":
        kn = [r for r in gueter if r.get("knapp")][:3]
        k["kopf"].append(_kz("knapp im Heimatmarkt", " · ".join(f"{gname(r['gut'])} {verh(r['gut'])}" for r in kn) or ue("keins – alles gedeckt"),
                             ue("Preis mindestens Grundpreis – Güter des Schwerpunkts mit dem größten Anteil × Preis/Grundpreis")))
    else:
        k["kopf"].append(_kz("vorne", " · ".join(gname(r["gut"]) for r in gueter[:3]) or STRICH))
    if fehlen:
        k["kopf"].append(_kz("im Markt nicht vorhanden", " · ".join(gname(r["gut"]) for r in fehlen[:3])))
    if plan:
        p = plan[0]
        k["kopf"].append(_kz("nächster Schritt", f"{geb_sym(p.get('gebaeude'))}{p.get('was')} – {p.get('ort')}", _plan_tip(p)))
    k["kopf"] += [_kz("Heimatmarkt", WP.get("heimat") or STRICH), _kz("Vergleich mit", ", ".join(WP.get("fremde_maerkte") or []) or STRICH)]

    # Einzelheiten: die weiteren Schritte des Bauplans (der erste steht im Kopf); Klick: Baumodus und Karte zum Ort (Mod 0.28)
    def link(p):
        ok, geb = ort_key(P, name=p.get("ort")), p.get("gebaeude")
        gn = (P["W"].get("namen") or {}).get("gebaeude") or {}            # alle Gebäudetypen des Spiels (Spielwissen)
        return (bau_link(geb, gn.get(geb), ok, p.get("ort")) if geb in gn else None) or ort_link(ok, p.get("ort"))
    k["details"] = [(str(p.get("nr")), geb_sym(p.get("gebaeude")) + (p.get("was") or STRICH), ort_text(ort_key(P, name=p.get("ort")), p.get("ort")),
                     _plan_tip(p), link(p))
                    for p in plan[1:]]
    k["hinweis"] = (ue(t"Weitere Schritte des Bauplans in dieser Reihenfolge ({len(plan) - 1}). Tooltip: Begründung, Wirkung, Kosten. Klick: "
                    t"Ort öffnen.") if len(plan) > 1
                    else ue("Keine weiteren Schritte im Bauplan.") if plan else "")
    return k


def _plan_tip(p):
    return "\n".join(x for x in (p.get("warum"), ue(t"Wirkung: {p['wirkung']}") if p.get("wirkung") else "",
                                 ue(t"Voraussetzung: {p['voraussetzung']}") if p.get("voraussetzung") not in (None, "", "–") else "",
                                 ue(t"Kosten: {p['kosten']}") if p.get("kosten") else "") if x)


def startstrategie(d, P, fk):
    S = d.get("startstrategie") or {}
    k = _leer()
    fokusse = S.get("fokusse") or {}
    if not fokusse:
        return k
    F = fokusse.get(fk) or fokusse[next(iter(fokusse))]
    A, D = F.get("abweichungen") or {}, S.get("diplomatie") or {}
    kab = S.get("kabinett") or {}
    # „Schwerpunkt“ (Auswahl), „1. Schritt“ (Erste Schritte unter dieser Kachel) und „Stand“ (Fuß) stehen schon in der Seitenleiste
    k["kopf"] = [
        _kz("Abweichungen", str(A["summe"]) if A.get("summe") is not None else STRICH,
            ue(t"Einstellungen, die vom Vorschlag abweichen: Kabinett {A.get('kabinett')}, Politlinien {A.get('gesetze')}, Privilegien "
            t"{A.get('privilegien')}, Reform {A.get('reformen')}, Rivale {A.get('rivalen')}, Bündnis {A.get('buendnis')}")),
        _kz("Politischer Einfluss", (fmt(S.get("einfluss"), 1) + (ue(t" {sgn(S.get('einfluss_monat'), 2)}/Monat") if num(S.get("einfluss_monat")) else ""))
            if num(S.get("einfluss")) else STRICH),
        _kz("Kabinett", ue(t"{len(kab.get('plaetze') or [])} Plätze") + (ue(t", {kab['offen']} frei") if num(kab.get("offen")) and kab["offen"] else "")),
        _kz("Rivalen", ue(t"{fmt(D.get('rivalen_zahl'), 0)} von {fmt(D.get('rivalen_moeglich'), 0)}") if num(D.get("rivalen_zahl")) else STRICH)]
    if not S.get("mit_mod"):
        k["warn"].append(ue("Ohne Werte des Daten-Mods: keine freien Plätze, Personen, Stände-Ziele, Bündnisstärken"))
    # Einzelheiten: Gesellschaftswerte und erste Forschung (Kabinett, Politlinien, Privilegien, Reform, Rivale und Bündnis stehen
    # in der Tabelle „jetzt -> Vorschlag“ unter dieser Kachel – wie auf der Seite, startstrategie.js; Prüfung 03.11.)
    AX = {a.get("key"): a for a in (S.get("gesellschaft") or {}).get("achsen") or []}
    for g in (F.get("gesellschaft") or [])[:3]:
        a = AX.get(g.get("achse")) or {}

        def poln(p, a=a):
            return a.get("ln") if p == a.get("l") else a.get("rn") if p == a.get("r") else p
        jetzt = f"{fmt(g.get('wert'), 0)} ({poln(g['pol_jetzt'])} {fmt(abs(g['wert']), 0)})" if g.get("pol_jetzt") and num(g.get("wert")) \
            else ue(t"{fmt(g.get('wert'), 0)} (Mitte)")
        tip = [ue(t"{sgn(g['drift'], 2)}/Monat") + (ue(t" -> {poln(g['richtung'])}, Grenze {fmt(g.get('grenze'), 1)}") if g.get("richtung") else "")
               if num(g.get("drift")) else "", ue("zieht schon dorthin") if g.get("zieht_hin") is True else ue("zieht weg") if g.get("zieht_hin") is False else ""]
        tip += list(g.get("gruende") or [])[:2]
        k["details"].append((a.get("n") or g.get("achse") or STRICH, jetzt, g.get("pol_name") or STRICH, "\n".join(x for x in tip if x),
                             ansicht("societal_values")))
    for e in (F.get("forschung") or [])[:3]:
        k["details"].append((ue("Forschung"), ue("läuft") if e.get("laeuft") else STRICH,
                             ue(t"{e.get('name')} · Kosten {fmt(e.get('kosten'), 2) if num(e.get('kosten')) else STRICH} · "
                             t"{fmt(e.get('monate'), 1) if num(e.get('monate')) else STRICH} Monate"), e.get("grund") or "",
                             ansicht("advances")))
    k["hinweis"] = (ue("Gesellschaftswerte: die wichtigsten für den Schwerpunkt – Jetzt = Stand auf der Achse, Vorschlag = Richtung. "
                    "Forschung: nächste Fortschritte mit Kosten und Dauer.") if k["details"] else "")
    return k


# ---------------------------------------------------------------- Wirtschaft
REG_AUS = (("army", ue("Heer")), ("navy", ue("Flotte")), ("fort", ue("Festungen")), ("court", ue("Hof")), ("diplomatic", ue("Diplomatie")),
           ("cultural", ue("Kultur")), ("colonial", ue("Kolonien")), ("exploration", ue("Erkundung")), ("food", ue("Nahrung")),
           ("upkeep", ue("Gebäude-Unterhalt")), ("bureaucracy", ue("Bürokratie")))


def finanzen(d, P):
    k = _leer()
    pts = d.get("punkte") or []
    if not pts:
        return k
    last, prev = pts[-1], (pts[-2] if len(pts) > 1 else None)
    w = P["A"].get("wirtschaft") or {}
    lm, lv = w.get("letzter_monat") or {}, P["lv"]
    live = d.get("live") or []
    live_neuer = bool(lv.get("jahr")) and num(last.get("jahr")) and lv["jahr"] > last["jahr"]
    L2 = live[-2] if len(live) > 1 else {}
    gold = lv.get("gold") if live_neuer else last.get("gold")
    gold_v = (L2.get("gold") if L2.get("gold") is not None else last.get("gold")) if live_neuer else (prev or {}).get("gold")
    S = _spiel_werte(d)
    mon = (d.get("monate") or [])[-24:]

    def ser(f):
        return [x for x in (f(m) for m in mon) if num(x)]

    def vm(s, cur=None, alt=None):
        return s[-1] - s[-2] if len(s) > 1 else cur - alt if num(cur) and num(alt) else None
    reihe = {"saldo": ser(lambda m: m.get("saldo")), "ein": ser(lambda m: m.get("einkommen")),
             "aus": ser(lambda m: m["einkommen"] - m["saldo"] if num(m.get("einkommen")) and num(m.get("saldo")) else None)}
    feld = {"saldo": "saldo", "ein": "einkommen", "aus": "ausgaben"}

    def kopf_w(l, key, cur, gut):
        if S:
            return _kz(l, fmt(S[key], 2) + trend(vorm(S["ser"][key]), 2, gut),
                       ue(t"wie im Wirtschaftsfenster (Daten-Mod {S['datum']}); Klammer = Veränderung zum Vormonat"),
                       ue(t"Spielstand {fmt(cur, 2)}") if num(cur) else "")
        return _kz(l, fmt(cur, 2) + trend(vm(reihe[key], cur, (prev or {}).get(feld[key])), 2, gut), ue("Spielstand"))
    infl = live_reihe(d, "inflation")
    inf = lv.get("inflation") if lv.get("inflation") is not None else last.get("inflation")
    schuld = lv.get("debt_total")                 # ohne Daten-Mod unbekannt – nicht „0“ (Prüfung 03.11.)
    # Klammer beim Gold immer gegen den Vormonat, wenn es Monatszeilen gibt – wie die Kennzahl der Übersicht (Test 0.28: „+6“ gegen
    # den vorigen Spielstand neben „+1,5“ in der Übersicht); nur ohne Mod gegen den vorigen Spielstand
    gold_d = (lv["gold"] - L2["gold"] if num(lv.get("gold")) and num(L2.get("gold"))
              else gold - gold_v if num(gold) and num(gold_v) else None)
    gold_tip = (ue("Klammer = Veränderung zum Vormonat") if num(lv.get("gold")) and num(L2.get("gold"))
                else ue(t"Klammer = Veränderung zum vorigen Spielstand {prev.get('datum') or ''}").rstrip() if prev else "")
    # Warnung der Seite zu Inflation und Schulden hier als roter Kopfwert – nicht dieselbe Angabe doppelt (Prüfung 03.11.)
    k["kopf"] = [
        _kz(f"Gold (live {lv.get('datum')})" if live_neuer else "Gold", fmt(gold, 0) + trend(gold_d, 1, 1), gold_tip),
        kopf_w("Saldo / Monat", "saldo", last.get("saldo"), 1),
        kopf_w("Einkommen / Monat", "ein", last.get("einkommen"), 1),
        kopf_w("Ausgaben / Monat", "aus", last.get("ausgaben"), -1),
        _kz("Inflation", rot(fmt(inf, 3), num(lv.get("inflation")) and lv["inflation"] > 0) + trend(vm(infl), 3, -1)),
        _kz("Einkommen / Jahr", fmt(lv.get("yearly_gold"), 0)), _kz("Kreditwürdigkeit", fmt(lv.get("creditworthiness"), 2)),
        _kz("Schulden", rot(fmt(schuld, 0), num(schuld) and schuld > 0))]
    saldo_t = S["saldo"] if S else last.get("saldo")
    stab = lv.get("stability") if lv.get("stability") is not None else last.get("stabilitaet")
    k["warn"] = [x for x in (ue("Saldo negativ") if num(saldo_t) and saldo_t < 0 else "",
                             ue("Stabilität negativ") if num(stab) and stab < 0 else "") if x]
    # Einzelheiten: Ausgaben je Posten wie die Karte „Ausgaben und Regler“ (Kosten je Regler laut Spiel, Daten-Mod)
    F = (P["LD"].get("finanzen") or [None])[0]
    if F:
        def kosten(key):
            v = F.get("ki_" + key) if F.get("ki_" + key) is not None else F.get("k_" + key)
            return abs(v) if num(v) else 0
        zeilen = [(l, kosten(key), pct(F["p_" + key], 0) if F.get("p_" + key) is not None else "") for key, l in REG_AUS]
        zeilen += [(l, v, "") for l, v in ((ue("Söldner"), lm.get("last_months_mercenary_maintenance")),
                                           (ue("Seeleute"), lm.get("last_months_sailor_expense"))) if num(v)]
        zeilen.sort(key=lambda z: -z[1])
        k["details"] = [(l, fmt(v, 2), r, "", ansicht("economy")) for l, v, r in zeilen if v][:8]
        k["hinweis"] = (ue(t"Ausgaben je Posten laut Spiel (Stand {P['LD'].get('extra_datum') or ''}), größter zuerst. Regler = Stellung des "
                        t"Reglers im Wirtschaftsfenster. Klick: Wirtschaftsfenster."))
    return k


def produktion(d, P):
    k = _leer()
    geb = P["allGeb"]
    if not geb:
        return k
    typen = {}
    for b in geb:
        t = typen.setdefault(b["typ"], {"typ": b["typ"], "name": b.get("name"), "n": 0, "gewinn": 0.0})
        t["n"] += 1
        t["gewinn"] += b.get("gewinn") if num(b.get("gewinn")) else 0
    rows = sorted(typen.values(), key=lambda t: -t["gewinn"])
    tot = summe(t["gewinn"] for t in rows)
    minus = len([b for b in geb if (b.get("gewinn") or 0) < 0])
    g_ser = live_reihe(d, "gebaeude_gewinn")
    k["kopf"] = [_kz("Gewinn der Gebäude / Monat", fmt(tot, 2) + trend(vorm(g_ser), 2, 1), ue("Summe Gewinn aller Gebäude live")),
                 _kz("Gebäude / Typen", f"{len(geb)} / {len(rows)}"),
                 _kz("im Bau", str(len(P["A"].get("bau") or [])), ue("Bauprojekte laut Spielstand (Neubau und Ausbau)")),
                 _kz("bester Typ", f"{geb_sym(rows[0]['typ'])}{rows[0]['name']} {fmt(rows[0]['gewinn'], 2)}"),
                 _kz("schwächster Typ", f"{geb_sym(rows[-1]['typ'])}{rows[-1]['name']} {fmt(rows[-1]['gewinn'], 2)}")]
    if minus:
        k["warn"] = [ue(t"{minus} Gebäude mit Verlust")]
    # Einzelheiten (Test 0.28: „details sollten besser dargestellt werden“): wo Geld verloren geht – Gebäude mit Verlust, größter
    # zuerst; gibt es keine, die mit dem geringsten Gewinn. Kleine Beträge mit drei Stellen (sonst „-0,00“), Verlust rot
    alle_g = sorted((b for b in geb if num(b.get("gewinn"))), key=lambda b: b["gewinn"])
    verlust = [b for b in alle_g if b["gewinn"] < 0]
    schwach = (verlust or alle_g)[:8]

    def gw(v):
        return rot(fmt(v, 3 if abs(v) < 0.01 else 2), v < 0)
    k["details"] = [(geb_sym(b.get("typ")) + (b.get("name") or b.get("typ") or STRICH),
                     ort_text(ort_key(P, b.get("ort_id"), b.get("ort")), b.get("ort")), gw(b["gewinn"]),
                     ue(t"Stufe {fmt(b.get('stufe'), 0)}") + (ue(t", möglich {fmt(b['moeglich'], 2)}") if num(b.get("moeglich")) else "")
                     + (ue(t", Beschäftigte {fmt(b['besch'], 2)} von {fmt(b.get('plaetze'), 2)}") if num(b.get("besch")) else ""),
                     ort_link(ort_key(P, b.get("ort_id"), b.get("ort")), b.get("ort")))
                    for b in schwach]
    k["hinweis"] = ((ue(t"Gebäude mit Verlust ({len(schwach)} von {len(verlust)}), größter Verlust zuerst") if verlust
                     else ue("Gebäude mit dem geringsten Gewinn")) + ue(": Gold je Monat, live. Tooltip: Stufe, möglicher Gewinn, Beschäftigte. "
                    "Klick: Ort öffnen.") if schwach else "")
    return k


def handel(d, P):
    k = _leer()
    LD, A, lv = P["LD"], P["A"], P["lv"]
    lm = (A.get("wirtschaft") or {}).get("letzter_monat") or {}
    tr = sorted(LD.get("handel") or [], key=lambda x: -(x.get("profit") or 0))
    est = [e for e in A.get("staende") or [] if ((e.get("letzter_monat") or {}).get("trade_income") or 0) > 0]
    if not tr and not est and lm.get("monthly_trade_balance") is None:
        return k
    markt = A.get("markt") or {}
    home = markt.get("id")
    gew = summe(x.get("profit") for x in tr)
    own_h = next((x for x in markt.get("haendler") or [] if x.get("tag") == (d.get("meta") or {}).get("tag")), None)
    ti_ser, r_ser, g_ser = live_reihe(d, "trade_income"), live_reihe(d, "trades"), live_reihe(d, "handel_gewinn")
    hw_ser = [p.get("handelswert") for p in d.get("punkte") or [] if num(p.get("handelswert"))][-24:]
    S = _spiel_werte(d)
    if S and num(S["handel"]):
        k["kopf"].append(_kz("Handelseinkommen / Monat", fmt(S["handel"], 2) + trend(S["handelVorm"], 2, 1),
                             ue(t"wie im Wirtschaftsfenster: Gewinn der Routen × Modifikator Handelseinnahmen (Daten-Mod {S['datum']})"),
                             ue(t"Spielstand {fmt(lm.get('monthly_trade_balance'), 2)}")))
    else:
        v = lm.get("monthly_trade_balance") if lm.get("monthly_trade_balance") is not None else lv.get("trade_income")
        k["kopf"].append(_kz("Handelseinkommen / Monat", fmt(v, 2) + trend(vorm(ti_ser), 2, 1), ue("Spielstand")))
    # Routen live nur mit Handelsdaten des Daten-Mods – sonst nicht „0“ behaupten (Prüfung 03.11.: „Routen 0“ neben Einkommen 1,64)
    hat = "handel" in LD
    kap = lv.get("merchant_capacity")
    genutzt = ue(t"({fmt(own_h.get('genutzt'), 1)} genutzt)") if own_h and num(own_h.get("genutzt")) else ""
    k["kopf"] += [_kz("Handelswert", fmt(lm.get("monthly_trade_value"), 1) + trend(vorm(hw_ser), 1, 1), ue("Spielstand monthly_trade_value")),
                  _kz("Gewinn der Routen", fmt(gew, 2) + trend(vorm(g_ser), 2, 1) if hat else STRICH,
                      ue("Summe trade_profit (= EconomyView.GetTradeBalance)")),
                  _kz("Händlerkapazität", " ".join(x for x in (fmt(kap, 1) if num(kap) else "", genutzt) if x) or STRICH),
                  _kz("Routen", str(len(tr)) + trend(vorm(r_ser), 0, 1) if hat else STRICH)]
    HW = P["AW"].get("handel") or {}
    zoelle = [(HW.get(str(x.get("id"))) or {}).get("GetTariffValue") for x in tr]
    if any(num(z) and z != 0 for z in zoelle):
        k["kopf"].append(_kz("Zölle / Monat", sgn(summe(zoelle), 2),
                             ue("Summe der Zölle aller Routen (ab 1.4); negativ = wir zahlen fremden Märkten Zoll; im Gewinn schon enthalten")))
    loss = len([x for x in tr if (x.get("profit") or 0) < 0])
    if loss:
        k["warn"] = [ue(t"{loss} Route(n) mit Verlust")]
    if own_h and own_h.get("kapazitaet"):
        k["balken"] = (ue(t"Händlerkapazität im Heimatmarkt genutzt: {fmt(own_h.get('genutzt'), 1)} von {fmt(own_h['kapazitaet'], 1)}"),
                       (own_h.get("genutzt") or 0) / own_h["kapazitaet"])
    gn = ((P["W"].get("namen") or {}).get("gueter") or {})
    m_name = {**{str(a): b for a, b in (A.get("markt_namen") or {}).items()}, **{str(m.get("id")): m.get("name") for m in LD.get("maerkte") or []}}

    def richtung(x):
        return ue("Einfuhr") if x.get("nach") == home else ue("Ausfuhr") if x.get("von") == home else ue("Durchhandel")
    k["details"] = [(gut_sym(x.get("gut")) + (gn.get(x.get("gut")) or x.get("gut_name") or x.get("gut") or STRICH), richtung(x),
                     fmt(x.get("profit"), 2),
                     ue(t"von {m_name.get(str(x.get('von')), x.get('von'))} nach {m_name.get(str(x.get('nach')), x.get('nach'))}; Menge "
                     t"{fmt(x.get('volume'), 2)}, Einkauf {fmt(x.get('buy'), 2)}, Verkauf {fmt(x.get('sell'), 2)}"),
                     ansicht("markets_overview")) for x in tr[:8]]
    k["hinweis"] = (ue(t"Deine Handelsrouten nach Gewinn (Stand {LD.get('extra_datum') or ''}). Richtung aus Sicht deines Heimatmarkts: "
                    t"Einfuhr = das Gut kommt herein, Ausfuhr = es geht hinaus. Tooltip: Märkte, Menge, Preise. Klick: Marktübersicht.")
                    if tr else "")
    return k


def _gueter_bilanz(P):
    PMA, GB = P["A"].get("gebaeude_pm") or {}, P["W"].get("gebaeude") or {}
    foerd, herst, verbr = {}, {}, {}
    for o in P["orte"]:
        if o.get("rohstoff") and num(o["L"].get("rgo_output")):
            foerd[o["rohstoff"]] = foerd.get(o["rohstoff"], 0) + o["L"]["rgo_output"]
    ohne = {b["id"] for b in P["allGeb"] if num(b.get("besch")) and b["besch"] <= 0} if P["useLiveGeb"] else set()
    for b in P["allGeb"]:
        for n in [] if b["id"] in ohne else ((PMA.get(b["id"]) or PMA.get(str(b["id"])) or {}).get("pms") or []):
            pm = next((p for p in (GB.get(b["typ"]) or {}).get("pms") or [] if p.get("name") == n), None)
            lv = b.get("stufe") or 0
            if not pm or not lv:
                continue
            if pm.get("produced"):
                herst[pm["produced"]] = herst.get(pm["produced"], 0) + pm["output"] * lv
            for g, v in (pm.get("inputs") or {}).items():
                verbr[g] = verbr.get(g, 0) + v * lv
    eigen = list(dict.fromkeys([*foerd, *herst, *verbr]))

    def saldo(g):
        return foerd.get(g, 0) + herst.get(g, 0) - verbr.get(g, 0)
    fehlend = sorted([g for g in eigen if saldo(g) < 0], key=saldo)
    return foerd, herst, eigen, saldo, fehlend


def gueter(d, P):
    k = _leer()
    goods = P["W"].get("gueter") or {}
    if not goods:
        return k
    gn = ((P["W"].get("namen") or {}).get("gueter") or {})
    mg = {x.get("gut"): x for x in (P["A"].get("markt") or {}).get("gueter") or []}
    pr = (P["LD"].get("preise") or [{}])[0] or {}
    foerd, herst, eigen, saldo, fehlend = _gueter_bilanz(P)

    def pos(v):
        return num(v) and v > 0

    def preis(g):
        return next((v for v in (pr.get("price_" + g), (mg.get(g) or {}).get("preis")) if pos(v)), None)

    def erz(g):
        return foerd.get(g, 0) + herst.get(g, 0)

    def liste(ks, f):
        return " · ".join(f"{gut_sym(g)}{gn.get(g) or g} {f(g)}" for g in ks) or STRICH

    def verh(g):
        return preis(g) / goods[g]["default_market_price"]
    prod3 = sorted([g for g in eigen if erz(g) > 0], key=lambda g: -erz(g))[:3]
    angeboten = sorted([g for g in goods if pos(preis(g)) and goods[g].get("default_market_price")], key=lambda g: -verh(g))
    k["kopf"] = [_kz("am meisten produziert", liste(prod3, lambda g: fmt(erz(g), 2)),
                     ue("Förderung deiner Orte (live) + Herstellung deiner Gebäude (Nennwert: laufende Methode × Stufe)")),
                 _kz("fehlen am meisten", liste(fehlend[:3], lambda g: fmt(saldo(g), 2)),
                     ue("Saldo = Förderung + Herstellung − Verbrauch deiner Gebäude (Nennwerte); negativ = muss aus dem Markt kommen")),
                 _kz("günstigste ggü. Grundpreis", liste(angeboten[-3:][::-1], lambda g: f"×{fmt(verh(g), 2)}"),
                     ue("Preis live im Heimatmarkt ÷ Grundpreis, angebotene Güter")),
                 _kz("teuerste ggü. Grundpreis", liste(angeboten[:3], lambda g: f"×{fmt(verh(g), 2)}"),
                     ue("Preis live im Heimatmarkt ÷ Grundpreis, angebotene Güter")),
                 _kz("eigene Güter", str(len(eigen)), ue("Güter, die deine Orte fördern oder deine Gebäude herstellen oder verbrauchen")),
                 _kz("Güter", str(len(goods)))]
    # Einzelheiten: weitere fehlende Güter (die ersten drei stehen im Kopf), dann die größten eigenen Mengen
    rest = fehlend[3:] + [g for g in sorted(eigen, key=lambda g: -erz(g)) if g not in fehlend and g not in prod3]
    k["details"] = [(gut_sym(g) + (gn.get(g) or g), saldo_farbe(saldo(g)),
                     f"×{fmt(verh(g), 2)}" if pos(preis(g)) and goods.get(g, {}).get("default_market_price") else STRICH,
                     ue(t"Förderung {fmt(foerd.get(g, 0), 2)}, Herstellung {fmt(herst.get(g, 0), 2)}"), ansicht("goods_overview"))
                    for g in rest[:8]]
    k["hinweis"] = (ue("Weitere eigene Güter: zuerst, was fehlt, dann deine größten Mengen. Saldo = Förderung + Herstellung − Verbrauch je "
                    "Monat: rot = du verbrauchst mehr, als du erzeugst (es kommt aus dem Markt), grün = Überschuss. Preis : Grundpreis wie "
                    "oben. Tooltip: Förderung und Herstellung. Klick: Güterübersicht.") if k["details"] else "")
    return k


def orte(d, P):
    k = _leer()
    alle = P["orte"]
    if not alle:
        return k

    def prox(o):
        return o["L"].get("proximity") if o["L"].get("proximity") is not None else o.get("naehe")

    def mkt(o):
        return o["L"].get("market_access") if o["L"].get("market_access") is not None else o.get("marktzugang")
    st, sm = summe(o.get("steuer") for o in alle), summe(o.get("moegliche_steuer") for o in alle)
    fs = sm - st
    p_avg, m_avg = mittel([prox(o) for o in alle]), mittel([mkt(o) for o in alle])
    AO = P["AW"].get("ort") or {}

    def lw(o):
        return AO.get(str(o.get("id"))) or {}

    def stadt(o):
        return lw(o)["HasCityStatus"] == 1 if num(lw(o).get("HasCityStatus")) else o.get("rang") in ("town", "city")

    def unterhalt(o):
        return lw(o)["GetTotalUpkeep"] if num(lw(o).get("GetTotalUpkeep")) else -o["L"]["building_profit"] if num(o["L"].get("building_profit")) else None
    k["kopf"] = [_kz("Steuergrundlage / möglich", f"{fmt(st, 1)} / {fmt(sm, 1)}",
                     ue("Summe der Orte: Steuergrundlage gegen mögliche Steuergrundlage (Spielstand)")),
                 _kz("fehlt durch Kontrolle", fmt(fs, 1), ue("mögliche Steuergrundlage − Steuergrundlage, Summe der Orte"),
                     ue(t"{pct(fs / sm, 0)} der möglichen") if sm else ""),
                 _kz("Orte", str(len(alle))),
                 _kz("Städte", ue(t"{len([o for o in alle if stadt(o)])} von {len(alle)}"), ue("Orte mit Stadtstatus (Spielwert HasCityStatus)")),
                 _kz("Ø Nähe", fmt(p_avg, 0), ue("ungewichteter Durchschnitt der Orte")),
                 _kz("Ø Marktzugriff", pct(m_avg, 0), ue("ungewichteter Durchschnitt der Orte")),
                 _kz("Gebäudeunterhalt", fmt(summe(unterhalt(o) for o in alle), 2) if AO or any(num(o["L"].get("building_profit")) for o in alle) else STRICH,
                     ue("Unterhalt der Landesgebäude (Tempel, Marktplatz, Getreidespeicher, Kai, Burg …) aller Orte, Spielwert GetTotalUpkeep je Ort"))]
    if sm:
        k["balken"] = (ue(t"Steuergrundlage: {pct(st / sm, 0)} der möglichen"), st / sm)

    def fehlt(o):
        return o["moegliche_steuer"] - o["steuer"] if num(o.get("moegliche_steuer")) and num(o.get("steuer")) else None
    top = sorted([o for o in alle if num(fehlt(o))], key=lambda o: -fehlt(o))[:8]
    k["details"] = [(ort_text(o.get("key"), o.get("name")), f"{fmt(o.get('steuer'), 2)} / {fmt(o.get('moegliche_steuer'), 2)}",
                     pct(o["L"].get("control") if o["L"].get("control") is not None else o.get("kontrolle"), 0),
                     ue(t"fehlt {fmt(fehlt(o), 2)}; Nähe {fmt(prox(o), 0)}; Marktzugriff {pct(mkt(o), 0)}"),
                     ort_link(o.get("key"), o.get("name"))) for o in top]
    k["hinweis"] = (ue("Orte mit der größten Lücke: Steuergrundlage jetzt / möglich und Kontrolle in Prozent. Tooltip: fehlender Betrag, "
                    "Nähe, Marktzugriff. Klick: Ort öffnen.") if top else "")
    return k


# ---------------------------------------------------------------- Staat
def land(d, P):
    k = _leer()
    lv = P["lv"]
    if lv.get("population_total") is None:
        return k
    live = d.get("live") or []
    L2 = live[-2] if len(live) > 1 else {}
    # Bevölkerung wie die Seite mit /api/bevoelkerung: gesamt_live = total_population, Veränderung = monthly_population_change –
    # dieselben Spielwerte stehen in der Monatszeile (population_total, population_change)
    # Kapazität wie die Seite: Summe location_max_population der eigenen Orte – dieselben Spielwerte in live_details.orte
    kap = summe(o.get("max_population") for o in P["LD"].get("orte") or [])
    tot = lv.get("population_total")
    k["kopf"] = [_kz("Bevölkerung (Tsd.)", fmt(tot, 2) + trend(lv.get("population_change"), 3, 1),
                     ue("Summe der Pops in Tausend; Klammer = Veränderung im letzten Monat")),
                 _kz("Bevölkerungskapazität genutzt", ue(t"{pct(tot / kap, 0)} von {fmt(kap, 0)}") if kap and num(tot) else STRICH,
                     ue("Bevölkerung ÷ Bevölkerungskapazität aller Orte")),
                 _kz("Orte / Provinzen", f"{fmt(lv.get('locations'), 0)} / {fmt(lv.get('provinces'), 0)}"),
                 _kz("Ø Kontrolle", pct(lv.get("control_avg"), 0)
                     + trend((lv["control_avg"] - L2["control_avg"]) * 100 if num(lv.get("control_avg")) and num(L2.get("control_avg")) else None, 1, 1)),
                 _kz("Entwicklung", fmt(lv.get("development_total"), 0)
                     + trend(lv["development_total"] - L2["development_total"] if num(lv.get("development_total")) and num(L2.get("development_total")) else None, 2, 1)),
                 _kz("Ø Bildung", ue(t"{fmt(lv.get('literacy_avg'), 1)} %") if num(lv.get("literacy_avg")) else STRICH)]
    # Großmacht, Rang, Hauptstadt (/api/alles); Zufriedenheit, Kultur, Religion, Pop-Typ (/api/bevoelkerung)
    L, T, B = P["L"], P["TL"], P["B"]
    gp_rang, gp_punkte = erst(L.get("GetGreatPowerRank"), lv.get("great_power_rank")), erst(L.get("GetGreatPowerScore"), lv.get("great_power_score"))
    if num(gp_rang):
        k["kopf"].append(_kz("Großmacht", ue(t"{ue('Großmacht') if L.get('IsGreatPower') == 1 else ue('Mittelmacht')} Platz {fmt(gp_rang, 0)} · {fmt(gp_punkte, 0)} Punkte")))
    cap_id = next((i for i, o in (P["AW"].get("ort") or {}).items() if o.get("IsCapital") == 1), None)
    cap = next((o for o in P["orte"] if str(o.get("id")) == cap_id), None)
    k["kopf"] += [_kz("Rang", str(T.get("GetFlavorRank") or "").strip() or STRICH), _kz("Hauptstadt", cap.get("name") if cap else STRICH)]
    if B.get("typen"):
        k["kopf"] += [_kz("Ø Zufriedenheit", pct(B.get("zufriedenheit"), 0)),
                      _kz("Hauptkultur", pct(summe(x.get("anteil") for x in B.get("kulturen") or [] if "Primary" in (x.get("status") or "")), 0)),
                      _kz("Staatsreligion", pct(summe(x.get("anteil") for x in B.get("religionen") or [] if x.get("staatsreligion")), 0)),
                      _kz("größter Pop-Typ", f"{B['typen'][0].get('name')} {pct(B['typen'][0].get('anteil'), 0)}")]
    if num(lv.get("population_change")) and lv["population_change"] < 0:
        k["warn"] = [ue("Bevölkerung schrumpft")]
    if kap and num(tot):
        k["balken"] = (ue(t"Bevölkerungskapazität genutzt: {pct(tot / kap, 0)}"), tot / kap)
    k["details"] = [(l, v, "", t) for l, v, t in (
        (ue("Ø Kontrolle Kernregion"), pct(lv.get("control_avg_home"), 1), "average_control_in_home_region"),
        (ue("kontrollgewichtete Bevölkerung (Tsd.)"), fmt(lv.get("control_pop"), 1), ""),
        (ue("Großmacht-Platz"), fmt(lv.get("great_power_rank"), 0), ue("Platz unter den Großmächten der Welt")),
        (ue("Hauptkultur-Pops (Tsd.)"), fmt(lv.get("pop_primary_culture"), 1), ue("Daten-Mod")),
        (ue("Pops wahren Glaubens (Tsd.)"), fmt(lv.get("pop_true_faith"), 1), ue("Daten-Mod"))) if v != STRICH]
    k["hinweis"] = ue(t"Weitere Landeswerte, Stand {lv.get('datum') or ''}; Pops in Tausend.") if k["details"] else ""
    return k


def regierung(d, P):
    k = _leer()
    A, W, LD, lv = P["A"], P["W"], P["LD"], P["lv"]
    ch = [c for c in LD.get("charakter") or [] if c.get("rolle") in ("herrscher", "erbe", "gemahl")]
    ruler = next((c for c in ch if c.get("rolle") == "herrscher"), None)
    erbe = next((c for c in ch if c.get("rolle") == "erbe"), None)
    kab_live, kab_save = LD.get("kabinett") or [], A.get("kabinett") or []
    if ruler:
        k["kopf"].append(_kz("Herrscher (Verw./Dipl./Mil.)",
                             ue(t"{ruler.get('name')} {fmt(ruler.get('adm'), 0)} / {fmt(ruler.get('dip'), 0)} / {fmt(ruler.get('mil'), 0)} · {fmt(ruler.get('age'), 0)} J.")))
    kab_key = {x.get("aktion_name"): x.get("aktion") for x in kab_save}      # Name -> Schlüssel (Symbol, Mod 0.28)
    if kab_live:
        # Fortschritt nur, wenn die Aktion einen hat (Test 0.28: „Gesellschaftswerte ändern – %“)
        k["kopf"].append(_kz("Kabinett", " · ".join(f"{kab_sym(kab_key.get(x.get('aktion')))}{x.get('aktion')}"
                                                    + (ue(t" {fmt(x['fortschritt'], 0)} %") if num(x.get("fortschritt")) else "")
                                                    for x in kab_live)))
    elif kab_save:
        k["kopf"].append(_kz("Kabinett", " · ".join(kab_sym(x.get("aktion")) + (x.get("aktion_name") or STRICH) for x in kab_save)))
    if num(lv.get("ruler_reign")):
        k["kopf"].append(_kz("Regierungszeit", f"{fmt(lv['ruler_reign'], 0)} {ue('Jahr') if lv['ruler_reign'] == 1 else ue('Jahre')}"))
    if ruler:
        # der Name des Spiels trägt den Titel („Erbe Valentin Basarab“) – unter der Bezeichnung „Erbe“ nicht doppelt
        k["kopf"].append(_kz("Erbe", ERBE_TITEL.sub("", str(erbe.get("name"))) if erbe else ue("keiner")))
    if num(lv.get("complacency")):
        k["kopf"].append(_kz("Selbstgefälligkeit", fmt(lv["complacency"], 2), ue("complacency laut Daten-Mod (bis 1.3)")))
    pe = lv.get("political_influence")
    pm = (d.get("startstrategie") or {}).get("einfluss_monat")      # = monthly_political_influence (Daten-Mod), wie die Seite
    if num(pe):
        k["kopf"].append(_kz("Politischer Einfluss", fmt(pe, 1) + (ue(t" {sgn(pm, 2)} / Monat") if num(pm) else ""),
                             ue("political_influence laut Daten-Mod (ab 1.4)")))
    law = A.get("gesetze") or {}
    k["kopf"].append(_kz("Gesetze / Reformen", f"{len(law)} / {len(A.get('reformen') or [])}"
                         + (ue(t" ({fmt(lv['reform_slots_open'], 0)} frei)") if num(lv.get("reform_slots_open")) else "")))
    L = P["L"]
    if L.get("HasParliament") == 1:
        m_parl, tagt = L.get("months_since_last_parliament_called"), L.get("remaining_parliament_days")
        wann = (ue(t"tagt noch {fmt(tagt, 0)} Tage") if num(tagt) and tagt > 0 else ue("jetzt einberufbar") if num(m_parl) and m_parl > 59
                else ue(t"einberufbar in {fmt(60 - m_parl, 0)} Monaten") if num(m_parl) else "")
        k["kopf"].append(_kz("Parlament", ue(t"{fmt(L.get('num_of_active_parliament_agendas'), 0)} Vorhaben"), wann))
    namen = W.get("namen") or {}
    lc, ln, rn = namen.get("gesetz_kategorien") or {}, namen.get("gesetze") or {}, namen.get("reformen") or {}
    k["details"] = ([(gesetz_sym(g) + (lc.get(g) or g), ln.get(p) or p, "", "", ansicht("laws")) for g, p in law.items()]
                    + [(ue("Reform"), rn.get(r) or r, "", "", ansicht("government_reforms")) for r in A.get("reformen") or []])[:18]
    k["hinweis"] = (ue(t"Deine Gesetze (Bereich und eingestellte Politlinie) und Reformen laut Spielstand; {len(law)} Gesetze, "
                    t"{len(A.get('reformen') or [])} Reformen. Klick: Gesetze bzw. Reformen.") if law or A.get("reformen") else "")
    return k


def staende(d, P):
    """Zufriedenheit, Ausgewogenheit und Macht je Stand zeigt die Oberfläche als Spielwert (Estate.GetSatisfaction …) – hier nur
    die übrigen Kopfwerte der Seite."""
    k = _leer()
    A, lv = P["A"], P["lv"]
    S = (P["LD"].get("staende") or [{}])[0] or {}
    names = {e.get("stand"): e.get("name") for e in A.get("staende") or []}
    ests = [x[6:] for x in lv if re.fullmatch(r"power_\w+_estate", x)] or [e.get("stand") for e in A.get("staende") or []]
    ohne = [e for e in ests if e != "crown_estate"]
    # Steuern wie die Seite mit /api/alles (Summe GetLastMonthsTax der Stände ohne Krone) – derselbe Spielwert steht live in
    # stand_einkommen (steuer; Namen dort je Kultur, z. B. „Boeren-Stand“, daher ohne Zuordnung zum Stand: Summe ohne die Krone);
    # ohne Mod-Zeilen die Steuern des Spielstands (paid_taxes) wie die Seite ohne Mod
    live = [x for x in P["LD"].get("stand_einkommen") or [] if num(x.get("steuer"))]

    def steuer(e):
        return (((next((x for x in A.get("staende") or [] if x.get("stand") == e), {}) or {}).get("letzter_monat") or {}).get("paid_taxes"))
    steuern = (summe(x["steuer"] for x in live if x.get("name") != names.get("crown_estate")) if live
               else summe(steuer(e) for e in ohne))
    # Privilegien nur mit Stände-Daten des Daten-Mods – sonst nicht „0 von 0“ (Prüfung 03.11.)
    priv, moegl = ((summe(S.get("privileges_" + e) for e in ohne), summe(S.get("privileges_possible_" + e) for e in ohne)) if S
                   else (None, None))
    k["kopf"] = [_kz("Steuern der Stände / Monat", fmt(steuern, 2), ue("Summe der Steuern aller Stände im letzten Monat")),
                 _kz("Privilegien", ue(t"{fmt(priv, 0)} von {fmt(moegl, 0)} möglich") if S else STRICH),
                 _kz("Ø Zufriedenheit der Stände", pct(lv.get("estate_satisfaction_avg"), 0),
                     ue("Durchschnitt der Stände ohne Krone (average_estate_satisfaction)"))]
    if moegl:
        k["balken"] = (ue(t"Privilegien: {fmt(priv, 0)} von {fmt(moegl, 0)} möglich"), priv / moegl)
    for e in ohne:
        st = next((x for x in A.get("staende") or [] if x.get("stand") == e), None)
        if not st and not num(S.get("privileges_possible_" + e)):
            continue
        if not (S.get("privileges_possible_" + e) or steuer(e)):
            continue                                   # Stand ohne Privilegien und Steuern (Dhimmi, Stämme … im Land nicht da)
        k["details"].append((stand_sym(e) + (names.get(e) or e), fmt(steuer(e), 2),
                             ue(t"{fmt(S.get('privileges_' + e), 0)} von {fmt(S.get('privileges_possible_' + e), 0)}"), "",
                             ansicht("government")))
    k["hinweis"] = (ue("Steuern, die der Stand im letzten Monat gezahlt hat (Spielstand), und gewährte von möglichen Privilegien. Klick: "
                    "Regierungsfenster.") if k["details"] else "")
    return k


def religion(d, P):
    """Köpfe wie die Seite (app.js religion, /api/alles und /api/bevoelkerung) und die Werte ihrer Kopfzeile (Einigkeit, Einfluss)."""
    k = _leer()
    lv = P["lv"]
    if not num(lv.get("religious_unity")):
        return k
    # Warnung der Seite (Einigkeit unter 100 %) als roter Kopfwert – nicht doppelt (Prüfung 03.11.); gerundet auf 100 % nicht rot
    # (Test 0.28: 0,996 stand als rote „100 %“ da)
    k["kopf"] = [_kz("Glaubenseinigkeit", rot(pct(lv["religious_unity"], 0), pct(lv["religious_unity"], 0) != pct(1, 0)),
                     ue("rot: unter 100 % (Warnung der Seite)")),
                 _kz("Glaubenseinfluss", fmt(lv.get("religious_influence"), 1))]
    AW, AT, L, LM, TL = P["AW"], P["AT"], P["L"], P["LM"], P["TL"]
    if not AW:
        return k
    rel = next(iter(AW.get("religion") or {}), None)
    R, TR = (AW.get("religion") or {}).get(rel) or {}, (AT.get("religion") or {}).get(rel) or {}
    # Reformwunsch wie im Spiel: „… liegt bei 0.00%. Der Reformwunsch ändert sich derzeit monatlich um +0.03%.“
    rd_txt = str(TR.get("GetReformDesireInfo") or "")
    rd_m, rd_c = REFORM_WERT.search(rd_txt), REFORM_AENDERUNG.search(rd_txt)
    k["kopf"].append(_kz("Reformwunsch", (ue(t"{fmt(float(rd_m.group(1)), 2)} %") + (trend(float(rd_c.group(1)), 2, 0) if rd_c else "")) if rd_m else STRICH))
    k["kopf"].append(_kz("Toleranz", f"{sgn(LM.get('tolerance_own'), 1)} / {sgn(LM.get('tolerance_heretic'), 1)} / {sgn(LM.get('tolerance_heathen'), 1)}",
                         ue("eigener Glaube / Ketzer / Heiden")))
    kulturen = (P["B"].get("kulturen") or [])
    prim = next((x.get("id") for x in kulturen if "Primary" in (x.get("status") or "")), None)
    prim = prim if prim is not None else next(iter(AW.get("kultur") or {}), None)
    K = (AW.get("kultur") or {}).get(str(prim)) or {}
    if K.get("name"):
        k["kopf"] += [_kz(f"Kulturtradition ({K['name']})", fmt(ab(erst(K.get("GetTradition"), K.get("cultural_tradition"))), 2) + trend(ab(K.get("GetTraditionChange")), 2, 1)),
                      _kz("Kultureinfluss", fmt(ab(erst(K.get("GetInfluence"), K.get("cultural_influence"))), 2) + trend(ab(K.get("GetInfluenceChange")), 2, 1))]
    laender = fmt(erst(R.get("GetNumCountries"), R.get("num_countries_in_religion")), 0)
    k["kopf"].append(_kz("Gläubige weltweit", " ".join(x for x in (menge(TR.get("GetTotalPopulation")), ue(t"in {laender} Ländern")) if x)))
    if R.get("HasCardinals") == 1:
        k["kopf"].append(_kz("Kardinäle", ue(t"{fmt(L.get('num_cardinals'), 0)} von {fmt(R.get('total_cardinals'), 0)}")))
    if R.get("HasHolySites") == 1:
        heil = summe(o.get("location_num_holy_sites") for o in (AW.get("ort") or {}).values())
        k["kopf"].append(_kz("Sakralstätten", ue(t"{fmt(R.get('GetNumHolySites'), 0)} bei uns {fmt(heil, 0)}")))
    zehnt = [float(m.group(1)) for t in (AT.get("stand") or {}).values() if (m := ZEHNT.search(str(t.get("GetEconomyInfo") or "")))]
    if zehnt:
        k["kopf"].append(_kz("Zehnt / Monat", fmt(-sum(zehnt), 2), ue("Summe des Postens „Zehnt“ der Stände (geht an das Papsttum)")))
    if num(LM.get("monthly_religious_influence")):
        k["kopf"].append(_kz("Glaubenseinfluss / Monat", sgn(LM["monthly_religious_influence"], 2)))
    kap, kmax = erst(L.get("used_cultures_capacity"), L.get("GetTotalCultureCapacityUsed")), erst(L.get("GetCulturalCapacity"), LM.get("cultures_capacity"))
    if num(kap):
        k["kopf"].append(_kz("Akzeptierte Kulturen", f"{fmt(kap, 2)} / {fmt(kmax, 2)}"))
    if num(LM.get("global_pop_assimilation_speed_modifier")):
        k["kopf"].append(_kz("Angleichungsrate", ue(t"{sgn(LM['global_pop_assimilation_speed_modifier'] * 100, 0)} %")))
    k["kopf"].append(_kz("Kunstwerke / Künstler", f"{fmt(erst(L.get('num_works_of_art'), L.get('GetNumWorksOfArt')), 0)} / {fmt(L.get('num_artists'), 0)}"))
    return k


def forschung(d, P):
    k = _leer()
    lv, fo, FI = P["lv"], P["A"].get("forschung"), d.get("forschung_info") or {}
    if not fo and not num(lv.get("research_progress")):
        return k
    inst = FI.get("institutionen") or []
    n_ein = lv.get("institutions_embraced")
    # laufende Forschung zeigt die Oberfläche als Spielwert (Name und Balken); „Forschung je Monat“ rechnet die Seite aus /api/alles,
    # derselbe Wert steht in d (techbaum_vorschlag.laufend.je_monat; Prüfung 03.11.: Walachei 1,15 = Seite)
    if fo:
        k["kopf"].append(_kz("Fortschritte erforscht", str(fo.get("erforscht")), ue("Spielstand")))
    jm = ((d.get("techbaum_vorschlag") or {}).get("laufend") or {}).get("je_monat")
    k["kopf"].append(_kz("Forschung je Monat", fmt(jm, 2)))
    # eingeführt: Monatszeile (institutions_embraced = num_embraced_institutions der Seite); fehlt sie, nichts zeigen
    k["kopf"].append(_kz("Institutionen eingeführt", ue(t"{fmt(n_ein, 0)} von {fmt(len(inst), 0)}") if inst and num(n_ein) else STRICH,
                         ue("eingeführt / Institutionen, die es in der Welt gibt")))
    z = (d.get("techbaum_vorschlag") or {}).get("zeitalter")
    if z:
        k["kopf"].append(_kz("Zeitalter", z))
    LM = P["LM"]
    for l, m, t in (("Einführungskosten Institutionen", "embrace_institution_cost_modifier", ue("Land-Modifikator; über 0 = teurer")),
                    ("Verbreitung Institutionen", "global_institution_growth_modifier", ue("Land-Modifikator; über 0 = schneller"))):
        if num(LM.get(m)):
            k["kopf"].append(_kz(l, ue(t"{sgn(LM[m] * 100, 0)} %"), t))
    if inst and num(n_ein):
        k["balken"] = (ue(t"Institutionen: {fmt(n_ein, 0)} von {len(inst)} eingeführt"), n_ein / len(inst))
    k["details"] = [(inst_sym(x.get("key")) + (x.get("name") or STRICH), ue("eingeführt") if x.get("eingefuehrt") else ue("entstanden")
                     if x.get("entstanden") else ue("noch nicht entstanden"), x.get("ursprung") or STRICH, "", ansicht("advances"))
                    for x in inst[:8]]
    k["hinweis"] = (ue("Institutionen der Welt laut Spielstand: bei uns eingeführt oder nur entstanden, Ursprung = Ort, an dem sie "
                    "entstand. Klick: Fortschritte.") if inst else "")
    return k


def _tote(x):
    return fmt(math.trunc(x * 1000 + 1e-6), 0) if num(x) else STRICH


def krankheiten(d, P):
    k = _leer()
    K, KW = P["A"].get("krankheiten"), d.get("krankheiten_wissen") or {}
    if not K:
        return k
    KR = K.get("krankheiten") or {}

    def name(x):
        return (KR.get(x) or {}).get("name") or ((KW.get("krankheiten") or {}).get(x) or {}).get("name") or x

    ab = sorted(K.get("ausbrueche") or [], key=lambda a: _de_sort(name(a.get("krankheit"))))
    bd = K.get("schwarzer_tod")
    bd_ab = next((a for a in ab if a.get("id") == (bd or {}).get("ausbruch")), None)
    markt = (P["A"].get("markt") or {}).get("zentrum") or ue("Heimatmarkt")
    pop = live_reihe(d, "population_total")
    # Seuchenwiderstand, Tote, befallene eigene Orte wie die Seite aus den Werten des Daten-Mods (/api/alles: seucheland, seucheort,
    # disease_<k>) – der Spielstand liegt dahinter (Prüfung 03.11.: Masern in 2 Orten live, 0 im Spielstand)
    AW, AT, SL = P["AW"], P["AT"], _erste(P["AW"].get("seucheland"))
    SO, ORTW = AW.get("seucheort") or {}, AW.get("ort") or {}
    reihe = list(KR) or list(KW.get("krankheiten") or {})

    def ausbr(o, x):
        i = str(o.get("id"))
        v = erst((SO.get(i) or {}).get("pres_" + x), (ORTW.get(i) or {}).get("disease_" + x))
        if num(v):
            return v
        return (((K.get("orte") or {}).get(i) or {}).get(x) or {}).get("ausbreitung") or 0
    befallen = [o for o in P["orte"] if any(ausbr(o, x) > 0 for x in reihe)]
    tote_live = [SL["tote_" + x] for x in reihe if num(SL.get("tote_" + x))]
    tote = sum(tote_live) if tote_live else K.get("tote_uns")
    gdr = P["LM"].get("global_disease_resistance")
    k["kopf"] = [_kz("Seuchenwiderstand", ue(t"{sgn(gdr * 100, 0)} %") if num(gdr) else STRICH, ue("Landes-Modifikator global_disease_resistance")),
                 _kz("Tote durch Krankheiten", rot(_tote(tote), num(tote) and tote > 0),
                     ue("Daten-Mod: Tote unseres Landes je Krankheit, Summe") if tote_live
                     else ue(t"Spielstand {(d.get('meta') or {}).get('datum') or ''}: Tote unseres Landes je Ausbruch, Summe")),
                 _kz("befallene eigene Orte", rot(f"{len(befallen)} / {len(P['orte'])}", bool(befallen))),
                 _kz("laufende Ausbrüche (Welt)", str(len(ab)), ue("ohne endemische Malaria (zählt im Spiel nicht)")),
                 _kz("Bevölkerung (Tsd.)", fmt(pop[-1] if pop else None, 1) + trend(vorm(pop), 1, 0))]
    if bd:
        k["kopf"].append(_kz("Schwarzer Tod", ue(t"aktiv seit {bd.get('start') or ''}") + (ue(t" · Ursprung {bd_ab.get('ursprung') or '?'} · {_tote(bd_ab.get('tote'))} Tote") if bd_ab else "")
                             if bd.get("status") == "active" else ue("nicht aktiv")))
    k["kopf"].append(_kz("in unserem Land", ", ".join(krank_sym(x) + name(x) for x in reihe if any(ausbr(o, x) > 0 for o in befallen))
                         or ue("keine Krankheit ausgebrochen")))
    k["warn"] = [ue(t"{krank_sym(a.get('krankheit'))}{name(a.get('krankheit'))} im Markt {markt} ({a['orte_markt_anzahl']} Orte)")
                 for a in ab if a.get("orte_markt_anzahl")]
    k["details"] = [(krank_sym(a.get("krankheit")) + name(a.get("krankheit")), f"{a.get('ursprung') or '?'}, {a.get('start') or STRICH}",
                     fmt(a.get("orte"), 0),
                     ue(t"Tote {_tote(a.get('tote'))} in {fmt(a.get('laender'), 0)} Ländern")
                     + (ue(t"; bei uns: {', '.join(o.get('name') for o in a.get('orte_uns') or [])}") if a.get("orte_uns") else ""))
                    for a in sorted(ab, key=lambda a: -(a.get("orte") or 0))[:8]]
    k["hinweis"] = (ue(t"Laufende Ausbrüche laut Spielstand {(d.get('meta') or {}).get('datum') or ''}, die mit den meisten Orten zuerst: "
                    t"Ursprung und Beginn, Zahl der befallenen Orte weltweit (0 = zurzeit keine). Tooltip: Tote, Länder, eigene Orte.")
                    if ab else "")
    return k


# ---------------------------------------------------------------- Außen und Militär
# Begriffe wie die Seite (app.js BEZIEHUNG, Spielbegriffe)
BEZIEHUNG = {"nachbar": ue("Nachbar"), "rivale": ue("Rivale"), "krieg": ue("Krieg"), "untertan": ue("Klientelland"), "oberherr": ue("Oberherr"),
             "freund": ue("Befreundet"), "feind": ue("Feindlich"), "kb_ziel": ue("Kriegsgrund gegen sie"), "kb_gegen_uns": ue("Kriegsgrund gegen uns"),
             "kriegsverbuendet": ue("Kriegsverbündeter"), "koalition": ue("Koalition gegen uns"), "union": ue("Personalunion"), "heirat": ue("Staatsehe"),
             "grossmacht": ue("Großmacht"), "annektiert_uns": ue("annektiert uns"), "wir_annektieren": ue("wird annektiert"),
             "spion_bei_uns": ue("Spionagenetz bei uns"), "hist_rivale": ue("historischer Rivale")}
# Reihenfolge in der Tabelle Diplomatie und in der Spalte Beziehung: was uns am meisten angeht, zuerst
BEZ_RANG = ("krieg", "rivale", "buendnis", "kriegsverbuendet", "union", "oberherr", "untertan", "koalition", "kb_gegen_uns", "kb_ziel",
            "heirat", "freund", "feind", "annektiert_uns", "wir_annektieren", "spion_bei_uns", "hist_rivale", "nachbar", "grossmacht")


def diplomatie(d, P):
    k = _leer()
    tag = (d.get("meta") or {}).get("tag")
    dip_all, unter = P["LD"].get("diplomatie") or [], P["A"].get("untertanen") or []
    if not dip_all and not unter:
        return k

    def v(x, key):
        return next((x[a] for a in (key, key + "_a", key + "_b") if x.get(a) is not None), None)
    dip = [x for x in dip_all if x.get("tag") != tag]

    def mit(b):
        return [x for x in dip if b in (x.get("beziehungen") or [])]
    rivals, wars, union, kb_ziel, kb_uns = mit("rivale"), mit("krieg"), mit("union"), mit("kb_ziel"), mit("kb_gegen_uns")
    # ohne Beziehungen des Daten-Mods (erster Monat, Partie ohne Mod) nicht „keine“ behaupten – Prüfung 03.11.: Brandenburg im Krieg
    # zeigte sonst „Kriegsgegner: keine“ neben „Laufende Kriege 1“ (Nachbarn)
    hat = "diplomatie" in P["LD"]
    k["kopf"].append(_kz("Rivalen (ihre Meinung von uns)",
                         (", ".join(f"{x.get('name')} {fmt(v(x, 'op_them'), 0)}" for x in rivals) or ue("keine")) if hat else STRICH))
    # Diplomaten, Kapazität, Ruf, Antagonismus (/api/alles) wie die Seite; Kapazität wie im Fenster aus der Liste der Beziehungen
    L, TD = P["L"], (P["AT"].get("dip") or {}).get(tag) or _erste(P["AT"].get("dip"))
    dipl, d_max = erst(L.get("dip_GetNumOfDiplomats"), L.get("num_of_diplomats")), L.get("dip_GetMaxNumOfDiplomats")
    if num(dipl):
        k["kopf"].append(_kz("Diplomaten", f"{fmt(dipl, 1)} / {fmt(d_max, 1)}"))
    teile = [float(m) for m in re.findall(r"^\S.*:\s*([-+]?[\d.]+)\s*$", str(TD.get("GetActiveRelationsList") or ""), re.M)]
    cap = sum(teile) if teile else erst(L.get("dip_GetUsedDiplomaticCapacity"), L.get("used_diplomatic_capacity"))
    cap_max = erst(L.get("dip_GetMaxCapacity"), L.get("diplomatic_capacity_without_maintenance"))
    if num(cap) or num(cap_max):
        k["kopf"].append(_kz("Diplomatiekapazität", f"{fmt(cap, 2)} / {fmt(cap_max, 2)}"))
    if num(P["LM"].get("diplomatic_reputation")):
        k["kopf"].append(_kz("Diplomatieruf", sgn(P["LM"]["diplomatic_reputation"], 2)))
    antag, antag_z = L.get("dip_GetNumberOfCountriesWithAntagonismTowardsUs"), L.get("dip_GetNumberOfCountriesWithTimedAntagonismTowardsUs")
    if num(antag) or num(antag_z):
        k["kopf"].append(_kz("Antagonismus gegen uns", ue(t"{fmt(antag, 0)} Länder · zeitweilig {fmt(antag_z, 0)}")))
    if not any(u.get("angliederung") for u in unter):
        k["kopf"].append(_kz("Klientelländer", ", ".join(u.get("name") or STRICH for u in unter) or ue("keine")))
    # Bündnisse: nicht unter den Beziehungen des Mods, sondern aus den Verbündeten der Startstrategie (Test 0.28: Bulgarien fehlte)
    D = (d.get("startstrategie") or {}).get("diplomatie") or {}
    verb = set(D.get("verbuendete") or [])
    if hat and "verbuendete" in D:
        k["kopf"].append(_kz("Bündnisse", ", ".join(D.get("verbuendete_namen") or []) or ue("keine")))
    k["kopf"].append(_kz("Kriegsgegner", (", ".join(x.get("name") for x in wars) or ue("keine")) if hat else STRICH))
    if union:
        k["kopf"].append(_kz("Personalunion", ", ".join(x.get("name") for x in union)))
    if kb_ziel or kb_uns:
        k["kopf"].append(_kz("Kriegsgründe", " · ".join(x for x in (ue(t"gegen {', '.join(y.get('name') for y in kb_ziel)}") if kb_ziel else "",
                                                                    ue(t"gegen uns: {', '.join(y.get('name') for y in kb_uns)}") if kb_uns else "") if x)))
    if wars:
        k["warn"] = [ue(t"Krieg mit {', '.join(x.get('name') for x in wars)}")]

    # Tabelle (Test 0.28: „marokko ist großmacht?“ – die Liste bestand aus fernen Großmächten, Nachbarn und Verbündete fehlten):
    # wie die Seite nur Länder mit echter Beziehung; „Großmacht“ allein ist keine Beziehung, solche Länder nennt der Hinweis
    def bez(x):
        b = list(x.get("beziehungen") or []) + (["buendnis"] if x.get("tag") in verb else [])
        if "freund" in b and "feind" in b:
            b.remove("feind")      # das Spiel listet Bulgarien (Meinung +111) in beiden (every_hostile_country) – nur das Eindeutige
        return sorted(b, key=lambda r: BEZ_RANG.index(r) if r in BEZ_RANG else len(BEZ_RANG))

    def rang(x):
        return min((BEZ_RANG.index(r) for r in bez(x) if r in BEZ_RANG), default=len(BEZ_RANG))
    nah = [x for x in dip if set(bez(x)) - {"grossmacht"}]
    fern = [x for x in dip if not set(bez(x)) - {"grossmacht"}]
    reihe = sorted(nah, key=lambda x: (rang(x), -(v(x, "op_them") or 0)))
    k["details"] = [(x.get("name") or x.get("tag") or STRICH, ", ".join(ue("Bündnis") if b == "buendnis" else BEZIEHUNG.get(b, b) for b in bez(x)),
                     fmt(v(x, "op_them"), 0), ue(t"unsere Meinung von ihnen {fmt(v(x, 'op_us'), 0)}; Stärke {fmt(x.get('country_strength'), 1)}"),
                     land_link(x.get("tag"), x.get("name"))) for x in reihe[:8]]
    k["hinweis"] = (ue(t"Länder mit Beziehung zu uns ({len(nah)}): Krieg, Rivalen und Bündnisse zuerst. Rechts ihre Meinung von uns. Tooltip: "
                    t"unsere Meinung von ihnen, Stärke. Klick: Diplomatie mit dem Land.")
                    + (ue(t" Ferne Großmächte ohne Beziehung zu uns: {', '.join(str(x.get('name')) for x in fern)}.") if fern else "")
                    if dip else "")
    return k


AMPEL = {"gruen": ue("aussichtsreich"), "gelb": ue("knapp"), "rot": ue("nicht ratsam"), "grau": ue("unbekannt")}


def nachbarn(d, P):
    k = _leer()
    nb = d.get("nachbarn")
    if not nb:
        return k
    wir = nb.get("wir") or {}
    gruen = [r for r in nb.get("laender") or [] if (r.get("bewertung") or {}).get("stufe") == "gruen"]
    k["kopf"] = [_kz("Kriegsgelegenheiten", str(len(gruen)), ", ".join(r.get("name") for r in gruen) or ue("keine Ampel auf Grün")),
                 _kz("Unser Offensivbündnis", fmt(wir.get("offensive_alliance_strength"), 2),
                     ue("Spielwert offensive_alliance_strength: wir samt allen, die wir in einen Angriffskrieg rufen können")),
                 _kz("Heer (Tsd. Mann)", fmt(wir.get("army_size"), 2)),
                 _kz("Mannstärke (Tsd.)", f"{fmt(wir.get('manpower'), 2)} / {fmt(wir.get('max_manpower'), 2)}"),
                 _kz("Verteidigungsbündnis", fmt(wir.get("defensive_alliance_strength"), 2)),
                 _kz("Stabilität", fmt(wir.get("stability"), 1)), _kz("Kriegsmüdigkeit", fmt(wir.get("war_exhaustion"), 2)),
                 _kz("Gold / Saldo", f"{fmt(wir.get('gold'), 0)} / {sgn(wir.get('saldo'), 2)}"),
                 _kz("Laufende Kriege", str(wir.get("kriege") or 0))]
    mp, mx = wir.get("manpower"), wir.get("max_manpower")
    k["warn"] = [x for x in (nb.get("veraltet") and ue(t"{nb['veraltet']} – Ampel grau"),
                             wir.get("kriege") and ue(t"Wir sind schon in {wir['kriege']} Krieg(en)"),
                             num(mp) and num(mx) and mx > 0 and mp < 0.5 * mx and ue("Unsere Mannstärke liegt unter der Hälfte")) if x]
    rows = [r for r in nb.get("laender") or [] if r.get("standard")]
    rang = {"gruen": 0, "gelb": 1, "rot": 2, "grau": 3}
    rows.sort(key=lambda r: rang.get((r.get("bewertung") or {}).get("stufe"), 4))
    k["details"] = [(r.get("name") or r.get("tag") or STRICH, AMPEL.get((r.get("bewertung") or {}).get("stufe"), STRICH),
                     fmt((r.get("bewertung") or {}).get("verhaeltnis"), 2),
                     "; ".join(((r.get("bewertung") or {}).get("gruende") or [])[:3]), land_link(r.get("tag"), r.get("name")))
                    for r in rows[:8]]
    k["hinweis"] = (ue("Nachbarn, Kriegsgrund-Ziele und Rivalen: Bewertung des Ratgebers (aussichtsreich, knapp, nicht ratsam) und "
                    "Stärke uns : sie. Tooltip: Gründe. Klick: Diplomatie mit dem Land.") if rows else "")
    return k


def gruendung(d, P):
    k = _leer()
    G = d.get("gruendung")
    if not G or G.get("fehler"):
        if G and G.get("fehler"):
            k["warn"] = [str(G["fehler"])]
        return k
    S, O = G.get("stand") or {}, G.get("optionen") or []
    grad = S.get("grad") or ("0" if S.get("stufe") == 0 else "?")
    wahl = next((o for o in O if o.get("key") == G.get("standard")), None) or (O[0] if O else None)

    def bed(o):
        return (f"{o.get('bedingungen_erfuellt')}/{o['bedingungen_alle']}" + (f" ({o['bedingungen_offen']} ?)" if o.get("bedingungen_offen") else "")
                if o.get("bedingungen_alle") else ue("keine"))
    k["kopf"].append(_kz("Gründungen", str(len(O)), ", ".join(o.get("name") for o in O) or ue("keine infrage")))
    if wahl:
        gb = wahl.get("gebiet") or {}
        k["kopf"] += [_kz("Gewählt", wahl.get("name") or STRICH, ue(t"Grad {wahl.get('grad') or '?'}")),
                      _kz("Orte (eigene / nötig)", f"{fmt(gb.get('unsere'), 0)} / {fmt(gb.get('noetig'), 0)}"),
                      _kz("Bedingungen", bed(wahl))]
        if gb.get("noetig"):
            k["balken"] = (ue(t"Orte {wahl.get('name')}: {fmt(gb.get('unsere'), 0)} von {fmt(gb['noetig'], 0)}"), (gb.get("unsere") or 0) / gb["noetig"])
    k["kopf"] += [_kz("Unser Grad", grad + (ue(" kein gegründetes Land") if S.get("stufe") == 0 else ""), S.get("stufe_quelle") or ""),
                  _kz("Spielregel", S.get("regel_name") or ue("unbekannt"), ue("Spielregel „Gründbare Länder“ laut Spielstand")),
                  _kz("Kultur", S.get("kultur") or STRICH, ", ".join(S.get("kulturgruppen") or []))]
    k["warn"] = [x for x in (any(o.get("gruendbar") for o in O) and ue(t"Jetzt gründbar: {', '.join(o.get('name') for o in O if o.get('gruendbar'))}"),
                             G.get("spiel_extra") and ue(t"Laut Spiel sichtbar, vom Ratgeber nicht als Option erkannt: {', '.join(x.get('name') for x in G['spiel_extra'])}"),
                             G.get("fehler_spielstand") and ue(t"Spielstand-Auszug fehlerhaft: {G['fehler_spielstand']}")) if x]
    k["details"] = [(o.get("name") or STRICH, f"{fmt((o.get('gebiet') or {}).get('unsere'), 0)} / {fmt((o.get('gebiet') or {}).get('noetig'), 0)}",
                     bed(o), ue(t"Grad {o.get('grad') or '?'}") + (ue(t", neuer Rang {o['rang_neu_name']}") if o.get("rang_neu_name") else "")
                     + (ue(" – jetzt gründbar") if o.get("gruendbar") else ""), ansicht("form_new_country")) for o in O[:6]]
    k["hinweis"] = (ue("Alle Gründungen, die infrage kommen: eigene / nötige Orte, erfüllte / alle Bedingungen. Tooltip: Grad, neuer Rang. "
                    "Klick: Fenster Gründung.") if O else "")
    return k


def militaer(d, P):
    k = _leer()
    LD, lv = P["LD"], P["lv"]
    krieg = LD.get("krieg") or []
    pts = d.get("punkte") or []
    jahr = lv.get("jahr") if lv.get("jahr") is not None else (pts[-1].get("jahr") if pts else None)
    seit = round((jahr - pts[0]["jahr"]) * 12) if pts and num(jahr) and num(pts[0].get("jahr")) else None
    mw = lv.get("months_since_war")
    nie = num(seit) and num(mw) and mw > seit
    L, TL = P["L"], P["TL"]
    # ohne Kriegsdaten des Daten-Mods die Kriege aus d (krieg.build, Spielstand) – nicht „keine“ behaupten (Prüfung 03.11.)
    if "krieg" in LD:
        kriege = str(len(krieg)) if krieg else ue("seit Spielbeginn keiner") if nie else ue("keine")
    else:
        kriege = str(len(d["kriege"])) if isinstance(d.get("kriege"), list) else STRICH
    k["kopf"] = [_kz("Militärstärke", fmt(lv.get("military_strength"), 2)),
                 _kz("Kriege", kriege, "" if "krieg" in LD else ue("laut Spielstand")),
                 _kz("Mannstärke", f"{fmt(erst(L.get('manpower'), lv.get('manpower')), 2)} / {fmt(erst(L.get('max_manpower'), lv.get('manpower_max')), 2)}",
                     ue("in Tausend, wie in der Kopfzeile")),
                 _kz("Seeleute", f"{fmt(erst(L.get('sailors'), lv.get('sailors')), 2)} / {fmt(erst(L.get('max_sailors'), lv.get('sailors_max')), 2)}",
                     ue("in Tausend, wie in der Kopfzeile"))]
    # wie das Militärfenster (app.js militaer, /api/alles): Aufgebote aus Spieltexten, Regulärtruppen und Schiffe, Traditionen, Moral
    if L:
        auf_pot = zahl(erst(TL.get("GetArmyLevyPotentialStrength"), TL.get("GetPotentialAndBeingRaisedArmyLevyBreakdown")))
        reg_max = L["expected_army_size"] * 1000 if num(L.get("expected_army_size")) else None
        reg = L["regular_army_size"] * 1000 if num(L.get("regular_army_size")) else None
        k["kopf"] += [_kz("Aufgebote", f"{fmt(zahl(TL.get('GetRaisedLevyStrength')), 0)} / {fmt(auf_pot, 0)}",
                          ue("ausgehoben / möglich (Mann); laut Spiel nur im Krieg oder bei Rebellen auszuheben"),
                          ue(t"Kampfkraft {fmt(L['potential_army_size'], 2)}") if num(L.get("potential_army_size")) else ""),
                      _kz("Regulärtruppen", f"{fmt(reg, 0)} / {fmt(reg_max, 0)}", ue("stehendes Heer / Obergrenze (Mann)")),
                      _kz("Schiffe", f"{fmt(erst(L.get('navy_size'), lv.get('navy_size')), 0)} / {fmt(erst(L.get('expected_navy_size'), L.get('GetExpectedNavySize')), 0)}",
                          ue("Schiffe / erwartete Marinegröße")),
                      _kz("Armeetradition", ue(t"{fmt(ab(L.get('army_tradition')), 2)} %") + trend(L.get("curbal_army_tradition"), 2, 1), ue("Klammer = Veränderung je Monat")),
                      _kz("Marinetradition", ue(t"{fmt(ab(L.get('navy_tradition')), 2)} %") + trend(L.get("curbal_navy_tradition"), 2, 1)),
                      _kz("Moral Heer / Flotte", f"{fmt(ab(L.get('GetDefaultLandMorale')), 2)} / {fmt(ab(L.get('GetDefaultNavalMorale')), 2)}"),
                      _kz("Festungsschwelle", f"{fmt(L.get('used_fort_limit'), 2)} / {fmt(L.get('GetFortLimit'), 2)}")]
        for l, m, n in (("Disziplin", "discipline", "%"), ("Kampf-Effizienz (Aufgebote)", "levy_combat_efficiency_modifier", "%"),
                        ("Militärtaktiken", "military_tactics", 2), ("Belagerungsfähigkeit", "siege_ability", "%")):
            if num(L.get("mod_" + m)):
                k["kopf"].append(_kz(l, ue(t"{sgn(L['mod_' + m] * 100, 1)} %") if n == "%" else fmt(L["mod_" + m], n), ue("wie im Militärfenster")))
    kat = LD.get("katastrophe") or []
    mf = MORAL_FAKTOR.search(str(TL.get("GetDefaultLandMoraleTooltip") or ""))
    regler = ", ".join(f"{n} {pct(L[x], 0)}" for n, x in ((ue("Heer"), "army_maintenance"), (ue("Flotte"), "navy_maintenance"), (ue("Festungen"), "fort_maintenance")) if num(L.get(x)))
    k["warn"] = [x for x in (krieg and ue(t"{len(krieg)} Krieg(e)"), kat and ue("Katastrophe aktiv"),
                             mf and float(mf.group(1)) < 1 and ue(t"Moral × {fmt(float(mf.group(1)), 2)} durch Unterhalt (Regler {regler})")) if x]
    if num(lv.get("manpower")) and lv.get("manpower_max"):
        k["balken"] = (ue(t"Mannstärke {pct(lv['manpower'] / lv['manpower_max'], 0)} des Höchstwerts"), lv["manpower"] / lv["manpower_max"])
    k["details"] = [(l, v, "", t) for l, v, t in (
        (ue("Heer (Tsd. Mann)"), fmt(lv.get("army_size"), 2), ue("army_size laut Daten-Mod")),
        (ue("Regimenter"), fmt(lv.get("regiments"), 0), ""),
        (ue("Festungen"), fmt(lv.get("forts"), 0), ""), (ue("Kriegsmüdigkeit"), fmt(lv.get("war_exhaustion"), 2), ""),
        (ue("Monate seit dem letzten Krieg"), fmt(mw, 0), "")) if v != STRICH]
    k["details"] = [z + (ansicht("military_ledger"),) for z in k["details"]]
    k["hinweis"] = ue(t"Weitere Militärwerte, Stand {lv.get('datum') or ''}. Klick: Militärübersicht.") if k["details"] else ""
    return k


FEST = {"FIN": finanzen, "PROD": produktion, "HANDEL": handel, "GUETER": gueter, "ORTE": orte, "LAND": land, "REG": regierung,
        "STAENDE": staende, "REL": religion, "FORSCH": forschung, "KRANK": krankheiten, "DIPL": diplomatie, "NACHB": nachbarn,
        "GRUEND": gruendung, "MIL": militaer}
JE_FOKUS = {"EMPF": empfehlungen, "WPLAN": wirtschaftsplan, "SSTRAT": startstrategie}


# ---------------------------------------------------------------- in Schlüssel
def _kurz(s):
    """Auf MAX_WERT sichtbare Zeichen kürzen; Symbole (Platzhalter) bleiben ganz oder fallen ganz weg (Mod 0.28)."""
    s = str(s)
    if len(_sichtbar(s)) <= MAX_WERT:
        return s
    out, n = "", 0
    for teil in re.split("(" + SYM_A + r"\w+" + SYM_E + ")", s):
        rest = MAX_WERT - 1 - n
        if rest <= 0:
            break
        if teil.startswith(SYM_A):
            if rest >= 2:
                out, n = out + teil, n + 2
            continue
        out, n = out + teil[:rest], n + len(teil[:rest])
    return out.rstrip() + "…"


def leerwert(v):
    """Wert ohne Inhalt („–“, „– / –“, „– von –“) – die Seite zeigt dann einen Strich, die Seitenleiste nichts."""
    return not re.sub(r"[–/\s%]|" + ue("von"), "", str(v or ""))


def packen(kopf, zeilen):
    """Kopfwerte auf Zeilen verteilen: kurze paarweise (Zelle A und B), lange allein über die ganze Breite (nur A).
    Was nicht mehr passt, meldet zuviel (setzen schreibt es in den Tooltip der letzten Zeile)."""
    out, offen = [], None
    for e in kopf:
        # Symbole zählen wie zwei Zeichen – auch das, das setzen() vor die Bezeichnung stellt (Prüfung 03.11.: 13 Bezeichnungen mit
        # 24–30 Zeichen plus Symbol passten sonst nicht in die halbe Zelle)
        lang = max(len(_sichtbar(kopf_symbol(e[0]) + kopf_text(e[0]))), len(_sichtbar(e[1]))) > LANG
        if lang:
            out.append([e, None])
        elif offen is not None:
            out[offen][1], offen = e, None
        else:
            out.append([e, None])
            offen = len(out) - 1
    return out[:zeilen], len(out) > zeilen


def setzen(t, kid, k, loc, fk=None):
    """Ergebnis einer Kachel in die Schlüssel (alle Werte durch loc)."""
    _, _, _, _, _, je_fk, zeilen, dz, balken, spalten, _ = K[kid]
    e = f"_{fk}" if je_fk else ""
    gefuellt = [x for x in k["kopf"] if not leerwert(x[1])]
    reihen, zuviel = packen(gefuellt, zeilen)
    # was nicht mehr in die Zeilen passt, im Tooltip der letzten Zelle statt still wegzufallen (Prüfung 03.11.)
    gezeigt = {id(x) for paar in reihen for x in paar if x}
    rest = "\n".join(f"{kopf_text(x[0])}: {x[1]}".replace(FARBE, "") for x in gefuellt if id(x) not in gezeigt) if zuviel else ""
    for r in range(1, zeilen + 1):
        paar = reihen[r - 1] if r <= len(reihen) else [None, None]
        for z, x in zip("AB", paar):
            l, w, tt = x if x else ("", "", "")
            voll = str(w) != _kurz(w)
            letzte = rest and x is not None and x is (paar[1] or paar[0]) and r == len(reihen)
            # Bezeichnung mit dem Symbol des Spiels (Mod 0.28: KOPF_SYMBOL); loc setzt Farbe („#“) und Symbole („@…!“) um
            t[f"RG_K_{kid}_K{r}{z}L{e}"] = loc(kopf_symbol(l) + kopf_text(l)) if x else ""
            t[f"RG_K_{kid}_K{r}{z}W{e}"] = loc(_kurz(w)) if x else ""
            t[f"RG_K_{kid}_K{r}{z}T{e}"] = loc(tips.zeile("\n".join(y for y in ((f"{kopf_text(l)}: {w}".replace(FARBE, "") if voll else ""), tt,
                                                                               ue(t"Weitere Werte:\n{rest}") if letzte else "") if y))) if x else ""
    # Warnungen wie auf der Seite; was ein Kopfwert schon sagt, färben die Kacheln rot statt zu warnen (rot())
    warn = [w for w in k["warn"] if w]
    for i in range(1, 4):
        t[f"RG_K_{kid}_W{i}{e}"] = loc(warn[i - 1]) if i <= len(warn) else ""
    if balken:
        b = k.get("balken")
        voll = max(0, min(SEGMENTE, round(b[1] * SEGMENTE))) if b and num(b[1]) else 0
        t[f"RG_K_{kid}_BL{e}"] = loc(b[0]) if b else ""
        for i in range(1, SEGMENTE + 1):
            t[f"RG_K_{kid}_B{i}{e}"] = "x" if b and i <= voll else ""
    teile = "ABCT" if spalten[2] else "ABT"                 # Spalte C nur bei dreispaltigen Einzelheiten (wie schluessel)
    lt = link_teile(kid)
    for r in range(1, dz + 1):
        z = k["details"][r - 1] if r <= len(k["details"]) else ("", "", "", "")
        # Link der Zeile (Mod 0.28): nur Link-Typen, für die die Oberfläche Knöpfe hat (LINKS); der Tooltip nennt den Klick
        ln = z[4] if len(z) > 4 and z[4] and z[0] and z[4]["typ"] in (LINKS.get(kid) or ()) else None
        tip = tips.mit_klick(tips.zeile(z[3] if len(z) > 3 else ""), ln and ln["text"])
        for s, v in zip("ABCT", (z[0], z[1], z[2] if len(z) > 2 else "", tip)):
            if s in teile:
                t[f"RG_K_{kid}_D{r}{s}{e}"] = loc(v) if z[0] else ""
        for s, f in (("L", "typ"), ("Z", "z"), ("O", "o")):
            if s in lt:
                t[f"RG_K_{kid}_D{r}{s}{e}"] = loc(ln[f]) if ln else ""
    if dz:
        t[f"RG_K_{kid}_DH{e}"] = loc(k.get("hinweis") or "")


def json_wie_seite(d):
    """d so, wie die Seite es bekommt (JSON): Schlüssel als Text, Reihenfolge wie im Browser – die Rechnungen sind von app.js."""
    return json.loads(json.dumps(d, ensure_ascii=False, default=str))


def texte(d, fokusse, loc):
    """{Schlüssel: Text} aller Kacheln; fokusse = Schwerpunkte (+ "" = erster). Fehler einer Kachel -> Kachel leer, Hinweis im Kopf."""
    d = json_wie_seite(d)
    ort_ids_setzen(d)
    try:
        P = _prep(d)
    except Exception:                              # noqa: BLE001 – sonst schriebe texte() gar nichts (Prüfung 03.11.)
        P = {"AW": {}, "AT": {}, "L": {}, "LM": {}, "TL": {}, "B": {}, "LD": {}, "W": {}, "A": {}, "lv": {}, "orte": [],
             "useLiveGeb": False, "allGeb": []}
    t = {}

    def sicher(f, *a):
        try:
            return f(d, P, *a)
        except Exception as ex:                    # noqa: BLE001 – eine Kachel darf die übrigen nicht verhindern
            k = _leer()
            k["warn"] = [ue(t"Fehler beim Auswerten: {type(ex).__name__}")]
            return k
    for kid, f in FEST.items():
        setzen(t, kid, sicher(f), loc)
    for kid, f in JE_FOKUS.items():
        for fk in fokusse:
            setzen(t, kid, sicher(f, fk or fokusse[0]), loc, fk)
    return t
