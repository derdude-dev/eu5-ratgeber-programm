"""Mechanik-Wiki (Nutzerwunsch 30.10.): alle Mechaniken, die das Spiel erklärt, als eigene Ansicht des Ratgebers (#wiki).

Quellen - nur Spieldateien, Spielwissen-Cache und geprüftes Ratgeber-Wissen, nichts erfunden:
- Spielbegriffe der Europedia: main_menu/common/game_concepts (alias, family, texture, shown_in_encyclopedia) mit den deutschen
  Texten game_concept_<x> (Name) und game_concept_<x>_desc (Erklärung). game_concepts.json des Spielwissens hat
  beschreibung = null (wissen_voll sucht <x>_desc) - die Lokalisierung wird hier direkt gelesen, wissen_voll bleibt unverändert.
- Zeitalter: in_game/common/age; Felder mit eigenem Spieltext (AGE_* in interfaces_l_german.yml) heißen wie im Spiel.
- weitere Mechaniken mit Namen und Beschreibung (TYPEN): Gesetze mit Politiken, Reformen, Privilegien, Institutionen …
- Modifikatoren: Name MODIFIER_TYPE_NAME_<m>, Erklärung MODIFIER_TYPE_DESC_<m>. Die Begriffe, die diese Erklärung des Spiels
  verlinkt, sind die belegte Zuordnung Modifikator -> Mechanik (erster Begriff außer dem Geltungsbereich = Hauptbegriff).
  Verlinkt die Erklärung keinen Begriff: Begriff-Schlüssel (oder Alias) als ganze Wortfolge im Modifikator-Schlüssel
  (local_max_control -> control), als schwächerer Beleg gekennzeichnet (Quelle "s" statt "e").
- automatische Modifikatoren (auto_modifiers mit scales_with = Begriff): belegte Wirkung eines Begriffs.
- Fortschritte (advances, Feld age): Freischaltungen (unlock_*) und Ja/Nein-Modifikatoren -> Zeitalter-Bezug.
- analysis/MECHANIK.md: geprüfte Formeln des Ratgebers (Zuordnung Abschnitt/Stichwort -> Begriff unten).

build() -> {format, version, arten, typen, zeitalter, e: {id: eintrag},
mods: {m: [name, erklärung, [begriffe], quelle, format]},
politik: {politik: id des Gesetzes}, ratgeber}.
Id eines Eintrags = Adresse auf der Seite (#wiki/<id>, vereinbart 30.10. mit dem Fortschritte-Baum): Spielbegriff = Schlüssel
(control), sonst "<ordner>/<schlüssel>" mit dem Ordner des Spiels (laws/press_law, age/age_1_traditions).
Felder eines Eintrags (kurz, die Antwort ist groß): t Typ, n Name, an Alias-Namen, ak Alias-Schlüssel, x Erklärung, art Thema,
ag Grund der Einordnung, za Zeitalter-Bezug [[zeitalter, art, beleg]], w Wirkung [[block, [[modifikator, wert]]]],
pol Politiken eines Gesetzes, aw automatische Wirkungen eines Begriffs, rg Abschnitte aus MECHANIK.md, ency False = nicht in
der Europedia, l ausgehende Verweise.
Text-Auszeichnung: Verweis [[id|Text]], Laufzeitwert des Spiels [[?|Hinweis]] (nicht berechenbar, auf der Seite gekennzeichnet),
Zeilen mit \\n, Aufzählungen mit "• ".
"""
import collections
import gzip
import json
import os
import re
import threading

from . import pfade
from . import sprache

FORMAT = 1           # Aufbau der Antwort /api/wiki (Zwischenspeicher _wiki_f<FORMAT>.json; neu gebaut auch, wenn wiki.py jünger ist)
MECHANIK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis", "MECHANIK.md")

# ---------------------------------------------------------------- Themen ("Art") passend zu den Kacheln des Ratgebers
ARTEN = [
    ("wirtschaft", "Wirtschaft und Steuern"), ("handel", "Handel und Märkte"), ("produktion", "Produktion und Güter"),
    ("bevoelkerung", "Bevölkerung und Gesellschaft"), ("staende", "Stände"), ("regierung", "Regierung und Verwaltung"),
    ("diplomatie", "Diplomatie"), ("militaer", "Militär und Krieg"), ("seefahrt", "Seefahrt und Entdeckung"),
    ("religion", "Religion"), ("kultur", "Kultur und Sprache"), ("forschung", "Forschung und Zeitalter"),
    ("karte", "Karte und Orte"), ("charaktere", "Charaktere und Dynastien"), ("situationen", "Situationen und Ereignisse"),
    ("spielsystem", "Spielsystem (Modifikatoren, Auslöser)"), ("sonstiges", "Sonstiges"),
]

# Einordnung der Spielbegriffe (634 von 731 ohne family) - Regeln in dieser Reihenfolge, die erste greift:
# 1. FAMILIE: Feld family des Spiels.
# 2. STICHWORT: erstes Wort des Schlüssels (an "_" getrennt, von links), das in der Tabelle steht (estate_tax_base -> Stände).
# 3. TEXTUR: Symbol-Ordner des Feldes texture (längster passender Pfadanfang aus der Tabelle).
# 4. Mehrheit der verlinkten Begriffe: Themen der Begriffe, die der Text verlinkt und auf die er verlinkt wird (ohne die
#    allgemeinen Begriffe Land/Ort/Provinz) - mindestens 2 Stimmen und mindestens die Hälfte; bis zu 3 Durchläufe.
# 5. sonst Sonstiges.
FAMILIE = {
    "combat": "militaer", "war": "militaer", "dice": "militaer", "mercenary": "militaer", "trade": "handel",
    "market": "handel", "good": "produktion", "building": "produktion", "food": "produktion", "wealth": "wirtschaft",
    "tax_base": "wirtschaft", "culture": "kultur", "religion": "religion", "trait": "charaktere", "role": "charaktere",
    "ability": "charaktere", "cabinet": "regierung", "integration_status": "regierung", "estate": "staende",
    "location_rank": "karte",
}
_W = lambda art, woerter: {w: art for w in woerter.split()}       # noqa: E731
STICHWORT = {
    **_W("wirtschaft", "tax taxes taxable loan loans debt interest inflation budget treasury income expense maintenance gold "
                       "bond bank bankrupt creditworthiness lender borrower minting subsidy subsidization gdp profit economical "
                       "wealth"),
    **_W("handel", "trade trading market import export tariff tariffs subvention merchant embargo protectionism price prices "
                   "demand supply stockpile sound sell selling buying"),
    **_W("produktion", "production produced goods good raw rgo building buildings construction output food plantation employ "
                       "unemploy establishment industry common"),
    **_W("bevoelkerung", "pop pops population migration colonial_migration people literacy unrest disease separatism slavery "
                         "peasant upper lower promote demote starving rebel rebels revolter minor nationalist pretender "
                         "religious_rebels slave average"),
    **_W("staende", "estate estates privilege crown"),
    **_W("regierung", "government law laws policy reform major cabinet parliament legislative bureaucracy legitimacy stability "
                      "control max_control integration core societal regency election political entrenchment employment "
                      "leader leadership prestige republican horde tribal civil centralization head"),
    **_W("diplomatie", "diplomacy diplomatic diplomat alliance ally union subject overlord opinion rival threat antagonism "
                       "treaty guarantee royal betrothal trust favors friend hostile enemy international imperial hre holy_roman "
                       "circle great regional normal hegemony coalition annexation inheritance liberty loyal disloyal spy "
                       "counterespionage infiltrate relation bias member candidate resolution payment special elector free "
                       "country_rank tier power_projection improve divorce non_sovereign blocked economic war_ally "
                       "military_access fleet"),
    **_W("militaer", "army armies unit units regiment regular levy army_levy mercenary combat battle siege assault garrison "
                     "fort fortification fortifications war military morale discipline tactics attrition supply frontage "
                     "flank initiative artillery bombard damage strength strength_damage_taken morale_damage_taken retreat "
                     "general commander prisoner occupation loot peace truce casus cobelligerent recruit recruitment manpower "
                     "reinforce repair logistics engagement phase reserves broken section center crossing zone white "
                     "unconditional combined secure flanking private sub experience attacker defender total maximum "
                     "non_avoidable movement_speed exile victory_card score"),
    **_W("seefahrt", "navy naval ship ships sailors admiral blockade privateer pirate sea seazone maritime harbor natural port "
                     "hull crew embarking exploration explore explorer discover colonial colonized colony colonization "
                     "conquistador expedition terra known cannons transport anti mothballed regular_ship navy_levy"),
    **_W("religion", "religion religious faith heretic heathen holy papal pope curia tithe cardinal sect patriarch "
                     "autocephalous god avatar omen offered karma purity honor yanantin righteousness harmony self doom "
                     "devotion excommunication canonization zeal calling holding tolerance true heathenry reformation reform "
                     "katun pentarchy hindu dominant_religion state_religion imperial_religion"),
    **_W("kultur", "culture cultural language dialect liturgical court_language court_dialect market_language artist art "
                   "artistic work ethnicity graphical discriminated accepted tolerated foreign_culture primary assimilate "
                   "isolated common_language dominant_language dominant_dialect merged dominant_culture"),
    **_W("forschung", "advance research institution embrace age stored"),
    **_W("karte", "location province region area continent sub geography geographical topography vegetation climate winter "
                  "river lake strait corridor impassable frozen hemisphere road proximity capital town rural inland coastal "
                  "development prosperity weather fertility geographical_term historical_capital province_capital"),
    **_W("charaktere", "character characters ruler heir consort courtier dynasty dynastic trait child adult infant adolescent "
                       "lowborn legal role ability adm dip mil total_ability immortality courtier"),
    **_W("situationen", "situation disaster event events mission decision flashpoint dynamic historical revolutionary "
                        "ambition gc"),
    **_W("spielsystem", "modifier effect trigger action map_mode_slot fow hidden locked ai d100 d20 d10 dice title"),
}
# längerer Schlüsselteil vor einzelnen Wörtern: "court_language" vor "court"; Prüfung zuerst auf zwei Wörter
TEXTUR = {
    "character_roles": "charaktere", "unit_types": "militaer", "unit_view": "militaer", "unit_actions": "militaer",
    "unit_category": "militaer", "unit_type": "militaer", "military_army": "militaer", "combat_modifiers": "militaer",
    "military_navy": "seefahrt", "religious_doctrines": "religion", "religious_orders": "religion",
    "religious_aspects": "religion", "omens": "religion", "religion": "religion", "culture": "kultur",
    "situations": "situationen", "events": "situationen", "missions": "situationen", "decisions": "situationen",
    "international_organizations": "diplomatie", "diplomatic_status": "diplomatie", "diplomatic_actions": "diplomatie",
    "peace_treaty": "militaer", "laws": "regierung", "government_power": "regierung", "bureaucracy": "regierung",
    "integration_levels": "regierung", "rebels": "bevoelkerung", "country_ranks": "diplomatie", "hegemony": "diplomatie",
    "buildings": "produktion", "production_methods": "produktion", "trade_goods": "produktion",
    "building_categories": "produktion", "cabinet_actions": "regierung", "map_subdivisons": "karte",
    "flat_icons/trade_market": "handel", "flat_icons/balance": "wirtschaft", "flat_icons/declare_war": "militaer",
    "flat_icons/foreigncountry": "diplomatie", "flat_icons/building_panel": "produktion", "flat_icons/dynasty": "charaktere",
    "flat_icons/war_view": "militaer", "location_icons/new": "bevoelkerung", "outliner/categories/battles": "militaer",
    "outliner/categories/sieges": "militaer", "outliner/categories/armyrecruitment": "militaer",
    "outliner/categories/colonies": "seefahrt", "outliner/categories/parliament": "regierung",
    "outliner/categories/cabinet": "regierung", "outliner/categories/spynetworks": "diplomatie",
    "map_modes/culture": "kultur", "map_modes/language_family": "kultur", "map_modes/dialect": "kultur",
    "map_modes/great_powers": "diplomatie", "map_modes/opinion": "diplomatie", "map_modes/dynasty": "charaktere",
    "map_modes/winter": "karte", "map_modes/topography": "karte", "map_modes/vegetation": "karte",
    "map_modes/climate": "karte", "map_modes/continent": "karte", "map_modes/region": "karte", "map_modes/area": "karte",
    "map_modes/provinces": "karte", "treaty_type/become_subject": "diplomatie",
}
LINK_ALLGEMEIN = {"country", "location", "province"}      # zählen bei der Mehrheit der Verweise nicht

# Typen außer Spielbegriffen und Zeitaltern: (typ, Ordner des Spielwissens, Einzahl, Mehrzahl, Thema, Spielbegriff dazu).
# Aufgenommen: Ordner mit deutschem Namen und Beschreibung für (fast) jeden Eintrag, die Regeln des Spiels beschreiben.
# Weggelassen (Inhalte statt Mechaniken, eigene Kacheln/Ansichten): Güter, Gebäude, Einheiten, Religionen, Kulturen,
# Fortschritte (nächstes Paket „Fortschritte“), Produktionsmethoden; ohne Beschreibung: Kriegsziele, Entscheidungen, Merkmale,
# Aufgebote; generic_actions (530 Bedien-Aktionen, Kosten statt Regeln).
TYPEN = [
    ("gesetz", "laws", "Gesetz", "Gesetze", "regierung", "law"),
    ("reform", "government_reforms", "Regierungsreform", "Regierungsreformen", "regierung", "government_reform"),
    ("staatsform", "government_types", "Staatsform", "Staatsformen", "regierung", "government_type"),
    ("thronfolge", "heir_selections", "Thronfolge", "Thronfolgen", "regierung", "heir_selection"),
    ("regentschaft", "regencies", "Regentschaft", "Regentschaften", "regierung", "regency"),
    ("kabinettsaktion", "cabinet_actions", "Kabinettsaktion", "Kabinettsaktionen", "regierung", "cabinet_action"),
    ("buerokratie", "bureaucracies", "Bürokratie", "Bürokratien", "regierung", "bureaucracy"),
    ("parlament", "parliament_types", "Parlamentsart", "Parlamentsarten", "regierung", "parliament_type"),
    ("parlamentsthema", "parliament_issues", "Parlamentsthema", "Parlamentsthemen", "regierung", "parliament_issue"),
    ("parlamentsagenda", "parliament_agendas", "Parlamentsagenda", "Parlamentsagenden", "regierung", "parliament_agenda"),
    ("gesellschaftswert", "societal_values", "Gesellschaftswert", "Gesellschaftswerte", "regierung", "societal_value"),
    ("stand", "estates", "Stand", "Stände", "staende", "estate"),
    ("privileg", "estate_privileges", "Standesprivileg", "Standesprivilegien", "staende", "estate_privilege"),
    ("popart", "pop_types", "Pop-Art", "Pop-Arten", "bevoelkerung", "pop_type"),
    ("beschaeftigung", "employment_systems", "Beschäftigungssystem", "Beschäftigungssysteme", "bevoelkerung",
     "employment_system"),
    ("krankheit", "diseases", "Krankheit", "Krankheiten", "bevoelkerung", "disease"),
    ("institution", "institution", "Institution", "Institutionen", "forschung", "institution"),
    ("situation", "situations", "Situation", "Situationen", "situationen", "situation"),
    ("katastrophe", "disasters", "Katastrophe", "Katastrophen", "situationen", "disaster"),
    ("kriegsgrund", "casus_belli", "Kriegsgrund", "Kriegsgründe", "militaer", "casus_belli"),
    ("friedensvertrag", "peace_treaties", "Friedensbedingung", "Friedensbedingungen", "militaer", "peace_treaty"),
    ("einheitenfaehigkeit", "unit_abilities", "Einheitenfähigkeit", "Einheitenfähigkeiten", "militaer", "unit_ability"),
    ("rekrutierung", "recruitment_method", "Rekrutierungsart", "Rekrutierungsarten", "militaer", "recruitment_method"),
    ("ritterorden", "chivalric_orders", "Ritterorden", "Ritterorden", "militaer", "chivalric_order"),
    ("zusammenschluss", "international_organizations", "Zusammenschluss", "Zusammenschlüsse", "diplomatie",
     "international_organization"),
    ("sonderstatus", "international_organization_special_statuses", "Sonderstatus", "Sonderstatus", "diplomatie",
     "special_status"),
    ("resolution", "resolutions", "Resolution", "Resolutionen", "diplomatie", "resolution"),
    ("untertan", "subject_types", "Untertanentyp", "Untertanentypen", "diplomatie", "subject_type"),
    ("landesaktion", "country_interactions", "Landesinteraktion", "Landesinteraktionen", "diplomatie", "country_interaction"),
    ("landesrang", "country_ranks", "Landesrang", "Landesränge", "diplomatie", "country_rank"),
    ("hegemonie", "hegemons", "Hegemonie", "Hegemonien", "diplomatie", "hegemony"),
    ("charakteraktion", "character_interactions", "Charakterinteraktion", "Charakterinteraktionen", "charaktere",
     "character_interaction"),
    ("erziehung", "child_educations", "Erziehung", "Erziehungen", "charaktere", "child_education"),
    ("ortsrang", "location_ranks", "Ortsrang", "Ortsränge", "karte", "location_rank"),
    ("stadtrecht", "town_rights", "Stadtrecht", "Stadtrechte", "karte", "town_rights"),
    ("strasse", "road_types", "Straßenart", "Straßenarten", "karte", "road"),
    ("gelaende", "topography", "Gelände", "Gelände", "karte", "topography"),
    ("vegetation", "vegetation", "Vegetation", "Vegetationen", "karte", "vegetation"),
    ("klima", "climates", "Klima", "Klimata", "karte", "climate"),
    ("religionsaspekt", "religious_aspects", "Religionsaspekt", "Religionsaspekte", "religion", "religious_aspect"),
    ("religionsfokus", "religious_focuses", "Religionsfokus", "Religionsfokusse", "religion", "religious_focus"),
    ("religionsschule", "religious_schools", "Religionsschule", "Religionsschulen", "religion", "religious_school"),
    ("sakralstaette", "holy_site_types", "Art der Sakralstätte", "Arten der Sakralstätten", "religion", "holy_site_type"),
    ("expedition", "expedition_types", "Expedition", "Expeditionen", "seefahrt", "expedition"),
    ("kolonialziel", "colonial_charter_goals", "Ziel des Kolonialbriefs", "Ziele der Kolonialbriefe", "seefahrt",
     "colonial_charter_goal"),
]
ORDNER = {t[0]: t[1] for t in TYPEN}
ORDNER["zeitalter"] = "age"


def im_wiki(ordner):
    """Führt das Wiki Einträge dieses Ordners? Spielbegriffe, Zeitalter und TYPEN – Verweise aus Fortschritten und Ländergründung
    nur dorthin, sonst endet der Link in „Kein Eintrag“ (Prüfer 30.10.: Gebäude, Einheiten, Gründungen, Kulturgruppen)."""
    return ordner == "game_concepts" or ordner in ORDNER.values()
# Bedeutung des Feldes age je Ordner (readme.txt der Spieldatei, wo vorhanden)
AGE_FELD = {"government_reforms": "Feld age der Spieldatei government_reforms (readme: ab diesem Zeitalter nutzbar)",
            "institution": "Feld age der Spieldatei institution (Zeitalter der Institution)"}


def _id(typ, k):
    """Id eines Eintrags: Spielbegriff = Schlüssel, sonst <ordner>/<schlüssel> (siehe oben)."""
    return k if typ == "begriff" else f"{ORDNER[typ]}/{k}"


def _injekt(daten):
    """INJECT:<x> / TRY_INJECT:<x> (eine Spieldatei ergänzt eine bestehende Definition, z. B. ein DLC weitere Politiken eines
    Gesetzes) in <x> einmischen, REPLACE:<x> ersetzt <x>; ohne vorhandenes <x> wird der Eintrag zu <x>. Das Spielwissen
    führt diese Schlüssel unverändert (laws 4, government_reforms 5 in 1.4.6)."""
    out = {k: v for k, v in daten.items() if ":" not in str(k)}
    for k, v in daten.items():
        if ":" not in str(k):
            continue
        art, ziel = str(k).split(":", 1)
        alt = out.get(ziel)
        if alt and "INJECT" in art and isinstance(alt.get("def"), dict) and isinstance(v.get("def"), dict):
            out[ziel] = {**alt, "def": {**alt["def"], **v["def"]}}
        elif not alt or art == "REPLACE":
            out[ziel] = {**(alt or {}), **{f: x for f, x in v.items() if x is not None}}
    return out

# Fortschritt schaltet frei (Feld -> Typ); None = Spielbegriff (unlock_diplomacy = { supportrebels })
UNLOCK = {
    "unlock_law": "gesetz", "unlock_policy": "politik", "unlock_government_reform": "reform",
    "unlock_estate_privilege": "privileg", "unlock_cabinet_action": "kabinettsaktion", "unlock_casus_belli": "kriegsgrund",
    "unlock_subject_type": "untertan", "unlock_town_rights": "stadtrecht", "unlock_heir_selection": "thronfolge",
    "unlock_road_type": "strasse", "unlock_chivalric_order": "ritterorden", "unlock_ability": "einheitenfaehigkeit",
    "unlock_country_interaction": "landesaktion", "unlock_interaction": "charakteraktion", "unlock_diplomacy": None,
}
# Zusatz zu einem Beleg über einen Modifikator: Zuordnung Modifikator -> Begriff aus der Erklärung (e) oder dem Schlüssel (s)
MOD_ZU = {"e": "", "s": " (Begriff aus dem Schlüssel des Modifikators)", "": ""}
# Modifikator-Blöcke einer Definition (Wirkung); Beschriftung auf der Seite = Feld des Spiels, dazu deutsch nur, wo eindeutig
MOD_BLOCK = re.compile(r"(^|_)modifier$")
BLOCK_NAME = {"country_modifier": "Land", "location_modifier": "Ort", "province_modifier": "Provinz", "modifier": "",
              "rank_modifier": "", "unit_modifier": "Einheiten", "character_modifier": "Charakter",
              "subject_modifier": "Untertan", "overlord_modifier": "Oberherr", "capital_country_modifier": "Land (Hauptstadt)",
              "unique": "Bedeutung offen (im Spiel nicht beschriftet):"}
NICHT_MOD = re.compile(r"^(potential|allow|visible|enabled|can_|trigger|limit|on_|ai_|calc|select_trigger|gain|lose|"
                       r"create_|invite_|auto_|.*_trigger$|.*_effect$|effect$)")
# Geltungsbereich in den Modifikator-Erklärungen: kein „verändert“-Begriff (Dies passt … an einem [location|e] an)
SCOPE = {"country", "location", "province", "character", "unit", "international_organization"}

# Felder der Zeitalter mit eigenem Spieltext (interfaces_l_german.yml); Zuordnung über gleichen Namen (Regel des Ratgebers)
AGE_TEXT = {"mercenaries": "AGE_MERCENARIES_AMOUNT", "mercenary_starting_experience": "AGE_MERCENARY_STARTING_EXPERIENCE",
            "war_score_from_battles": "AGE_BATTLE_WAR_SCORE_IMPACT",
            "known_goods_demand_threshold": "AGE_KNOWN_GOODS_DEMAND_THRESHOLD",
            "burgher_max_trade_range": "AGE_BURGHER_MAX_TRADE_RANGE",
            "months_for_exploration_spread": "AGE_EXPLORATION_SPREAD"}
# ohne Spieltext: nur Schlüssel und Wert; Hinweise aus Kommentaren der Spieldatei age/00_default.txt
AGE_HINWEIS = {"max_ai_privilege_per_estate": "Kommentar der Spieldatei: Optimierung der KI (Privilegien je Stand)",
               "min_ai_privilege_per_estate": "Kommentar der Spieldatei: Optimierung der KI (Privilegien je Stand)",
               "efficiency": "Bedeutung im Spiel nicht beschriftet (offen)",
               "unique": "Block „unique“ – im Spiel nicht beschriftet, Bedeutung offen"}

# Show…('x') -> Typ des Wiki-Eintrags (Verweis); …WithNoTooltip verlinkt auch im Spiel nicht
FUNC_TYP = {"ShowLawName": "gesetz", "ShowSituationName": "situation", "ShowDisasterName": "katastrophe",
            "ShowCasusBelliName": "kriegsgrund", "ShowCabinetActionName": "kabinettsaktion",
            "ShowGovernmentReformName": "reform", "ShowAgeName": "zeitalter", "ShowSubjectTypeName": "untertan",
            "ShowCountryRankName": "landesrang", "ShowLocationRankName": "ortsrang", "ShowTownRightsName": "stadtrecht",
            "ShowGovernmentTypeName": "staatsform", "ShowEstateTypeName": "stand", "ShowPopTypeName": "popart",
            "ShowSpecialStatusName": "sonderstatus", "ShowUnitAbilityName": "einheitenfaehigkeit",
            "ShowCountryInteractionName": "landesaktion", "ShowCharacterInteractionName": "charakteraktion",
            "ShowBureaucracyTypeName": "buerokratie", "ShowTopographyName": "gelaende", "ShowPolicyName": "politik",
            "ShowEstatePrivilegeName": "privileg", "ShowInstitutionName": "institution", "ShowHegemonyName": "hegemonie",
            "ShowHeirSelectionName": "thronfolge", "ShowClimateName": "klima", "ShowVegetationName": "vegetation"}
# [ShowDatabase('x')] = Liste aller Einträge einer Spieldatenbank (Name der Datenbank -> Ordner des Spielwissens)
DATENBANK = {"age": "age", "ai_personality": "ai_personalities", "artist": "artist_types", "climate": "climates",
             "government_type": "government_types", "hegemony": "hegemons", "holy_site_type": "holy_site_types",
             "location_rank": "location_ranks", "pop_type": "pop_types", "religious_figures": "religious_figures",
             "societal_values": "societal_values", "unit_category": "unit_categories"}

# analysis/MECHANIK.md: Abschnitt (Überschrift "## …", Anfang) -> Begriffe. Stichpunkte "- **X**" zusätzlich zum Begriff,
# dessen deutscher Name oder Alias-Name gleich X ist (Klammerzusatz und Doppelpunkt weggelassen).
MECHANIK_BEGRIFFE = {
    "Wie das Spiel Werte bildet": ["modifier"], "Stände": ["estate", "estate_power", "estate_satisfaction"],
    "Religion, Kultur und Kunst": ["religion", "culture", "artist"],
    "Diplomatie und Annektierung": ["annexation", "diplomatic_capacity", "subject"],
    "Militär": ["army", "morale", "army_tradition", "levy"], "Krankheiten": ["disease", "disease_outbreak"],
    "Pops": ["pop"], "Gesellschaftswerte und Regierung": ["societal_value"],
    "Forschung und Institutionen": ["research", "institution", "advance"], "Markt und Handel": ["market", "trade"],
    "Zölle und Handelsbestellungen": ["tariffs", "trade_orders"], "Gebäude, Einheiten, Bedarf": ["building", "pop_needs"],
    "Krieg": ["war", "war_score"], "Wirtschaft": ["budget", "income", "inflation"],
    "Orte": ["location", "control", "development"], "Diplomatie und Untertanen": ["subject", "annexation"],
    "Gesellschaftswerte": ["societal_value"],
}


# ---------------------------------------------------------------- Hilfen
def _num(v, d=2):
    """Zahl in der Schreibweise der Ausgabe, höchstens d Nachkommastellen, ohne Nullen am Ende (1234.5 -> 1.234,5)."""
    s = sprache.ziffern(f"{abs(v):,.{d}f}")
    if sprache.KOMMA in s:
        s = s.rstrip("0").rstrip(sprache.KOMMA)
    return ("−" if v < 0 and s != "0" else "") + s


def _sign(v, d=2):
    return ("+" if v > 0 else "") + _num(v, d)


def _fold(s):
    """Suchform: klein, Umlaute ausgeschrieben (wie auf der Seite)."""
    s = str(s or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return s


def _liste(v):
    return v if isinstance(v, list) else [] if v is None else [v]


def _load(voll, ordner):
    p = os.path.join(voll, f"{ordner}.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


# ---------------------------------------------------------------- Lokalisierung -> lesbarer Text mit Verweisen
BRACKET = re.compile(r"\[([^\[\]]*)\]")
DOLLAR = re.compile(r"\$([^$\s]+)\$")
FORMAT_CODE = re.compile(r"#[A-Za-z_]+[ ]?|#!|@\w+!")       # #Y … #!, #T, Symbole @gold!
CONCEPT_CALL = re.compile(r"Concept\('(\w+)',\s*'(.*)'\)(?:\|(\w*))?$")
FUNC_CALL = re.compile(r"(\w+)\('([^']*)'(?:\s*,\s*'([^']*)')?\)((?:\.\w+)*)(?:\|(.*))?$")
# Verweise beim Zusammensetzen in eigenen Zeichen (⟦⟦id|Text⟧⟧), damit die Klammer-Suche eingesetzte Texte nicht noch einmal
# liest; erst das fertige Ergebnis bekommt [[id|Text]]
L0, L1 = "⟦⟦", "⟧⟧"
MARKE = re.compile("⟦⟦([^|⟧]*)\\|([^⟧]*)⟧⟧")
OFFEN = "?"


def _mk(ziel, text):
    return f"{L0}{ziel}|{str(text).replace('|', '/')}{L1}"


class Texte:
    """Lokalisierungstexte des Spiels in die Auszeichnung des Wikis wandeln.

    [key|e] / [key] / [Concept('key', 'Text')|e] -> Verweis auf den Spielbegriff (auch über Aliase), $KEY$ -> eingesetzter
    Text, Show…Name('x') -> Name (Verweis, wenn x ein Wiki-Eintrag ist), GetDefine -> Zahl aus den Defines, ShowDatabase /
    ShowModifierEffect / ShowCabinetTypeDatabase -> Liste aus den Spieldateien. Alles andere, was nur das laufende Spiel kennt
    (Country.GetName, $VAL$ …), wird als [[?|…]] gekennzeichnet - nie roher Code."""

    def __init__(self, loc, alias, voll, modtypes, const):
        self.loc, self.alias, self.voll, self.mt, self.const = loc, alias, voll, modtypes, const
        self.ids = set()                 # Ids aller Wiki-Einträge (für Verweise aus Show…Name)
        self.politik = {}                # Politik -> Gesetz
        self.offen = collections.Counter()    # nicht auflösbare Ausdrücke (Test/Bericht)
        self._db = {}

    def db(self, ordner):
        if ordner not in self._db:
            self._db[ordner] = _load(self.voll, ordner)
        return self._db[ordner]

    @staticmethod
    def _fall(t, fmt):
        """Format hinter dem Verweis wie im Spiel: l = erster Buchstabe klein, U/E = groß."""
        if not t or not fmt:
            return t
        if "l" in fmt:
            return t[:1].lower() + t[1:]
        if "U" in fmt or "E" in fmt:
            return t[:1].upper() + t[1:]
        return t

    def __call__(self, raw):
        """Fertige Auszeichnung ([[id|Text]], [[?|Hinweis]])."""
        t = self._text(raw, 0)
        return None if t is None else t.replace(L0, "[[").replace(L1, "]]")

    def flach(self, raw, depth=0):
        """Text ohne Verweise (Namen); Laufzeitwerte als „…“."""
        t = self._text(raw, depth)
        return None if t is None else MARKE.sub(lambda m: "…" if m.group(1) == OFFEN else m.group(2), t)

    def begriff_name(self, key):
        """Anzeigename eines Begriffs oder Alias (game_concept_<key>), ohne Verweise."""
        raw = self.loc.get(f"game_concept_{key}")
        return self.flach(raw) if raw else None

    def _zahl(self, v, fmt):
        """Zahl im Format der Lokalisierung: % = Prozent (× 100), + = mit Vorzeichen, Ziffer = Nachkommastellen."""
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return None
        fmt = fmt or ""
        pct = "%" in fmt
        d = re.search(r"\d", fmt)
        x = v * 100 if pct else v
        return (_sign if "+" in fmt else _num)(x, int(d.group()) if d else 2) + (" %" if pct else "")

    def _funktion(self, name, arg, arg2, kette, fmt, depth):
        """Datenfunktion der Lokalisierung -> Auszeichnung oder None (nicht auflösbar)."""
        loc = self.loc
        if name == "GetDefine":
            return self._zahl((self.db("defines").get(arg, {}).get("def") or {}).get(arg2), fmt)
        if name in ("GetCountry", "GetUniqueInternationalOrganization", "GetInternationalOrganizationType",
                    "GetInternationalOrganization") and kette in (".GetName", ".GetNameWithNoTooltip"):
            return self.flach(loc[arg], depth + 1) if loc.get(arg) else None
        if kette:                                       # weitere Methoden: nur zur Laufzeit
            return None
        if name == "ShowDatabase":
            ordner = DATENBANK.get(arg)
            if not ordner:
                return None
            typ = "zeitalter" if arg == "age" else next((t[0] for t in TYPEN if t[1] == ordner), None)
            zeilen = []
            for k, v in self.db(ordner).items():
                n = (self.flach(loc[k], depth + 1) if loc.get(k) else None) or v.get("name") or k
                i = _id(typ, k) if typ else None
                zeilen.append("• " + (_mk(i, n) if i in self.ids else n))
            return "\n" + "\n".join(zeilen) if zeilen else None
        if name == "ShowCabinetTypeDatabase":
            zeilen = ["• " + _mk(_id("kabinettsaktion", k), v.get("name") or k) for k, v in self.db("cabinet_actions").items()
                      if isinstance(v.get("def"), dict) and v["def"].get("ability") == arg]
            return "\n" + "\n".join(zeilen) if zeilen else None
        if name == "ShowModifierEffect":
            d = (self.db("static_modifiers").get(arg) or {}).get("def")
            if not isinstance(d, dict):
                return None
            zeilen = [f"• {(self.mt.get(m) or {}).get('name') or m}: {wert(m, v, self.mt, self.const)[0]}"
                      for m, v in d.items() if m in self.mt and not isinstance(v, (dict, list))]
            return "\n" + "\n".join(zeilen) if zeilen else None
        if not name.startswith("Show"):
            return None
        basis = re.sub(r"WithNoTooltip$", "", name)
        if basis == "ShowModifierTypeName":
            t = loc.get(f"MODIFIER_TYPE_NAME_{arg}")
        elif basis == "ShowModifier":
            t = loc.get(f"STATIC_MODIFIER_NAME_{arg}")
        elif "Adjective" in basis:
            t = loc.get(f"{arg}_adj") or loc.get(f"{arg}_adjective") or loc.get(f"{arg}_ADJ")
        elif basis.endswith("Plural"):
            t = loc.get(f"{arg}_plural") or loc.get(f"{arg}_name_plural")
        else:
            t = loc.get(arg) or loc.get(f"{arg}_name") or loc.get(f"game_concept_{arg}")
        if not t:
            return None
        t = self._fall(self.flach(t, depth + 1), fmt)
        typ = FUNC_TYP.get(basis) if basis == name else None          # …WithNoTooltip: auch im Spiel kein Verweis
        ziel = (self.politik.get(arg) if typ == "politik" else _id(typ, arg)) if typ else None
        return _mk(ziel, t) if ziel in self.ids else t

    def _klammer(self, inhalt, depth):
        m = re.fullmatch(r"(\w+)(?:\|(\w*))?", inhalt)
        if m:                                           # [country|e], [countries], [own|el]
            key, fmt = m.group(1), m.group(2) or ""
            ziel = self.alias.get(key)
            if ziel:
                return _mk(ziel, self._fall(self.begriff_name(key) or self.begriff_name(ziel) or key, fmt))
            if key in self.loc:
                return self._fall(self.flach(self.loc[key], depth + 1), fmt)
            return None
        m = CONCEPT_CALL.match(inhalt)
        if m:                                           # [Concept('location', 'Orte')|e]
            key, text, fmt = m.groups()
            t = self._fall(self.flach(text, depth + 1), fmt or "")
            ziel = self.alias.get(key)
            return _mk(ziel, t) if ziel else t
        m = FUNC_CALL.match(inhalt)
        if m:
            return self._funktion(m.group(1), m.group(2), m.group(3), m.group(4) or "", m.group(5) or "", depth)
        return None

    def _text(self, raw, depth):
        if raw is None:
            return None
        if depth > 6:
            return ""
        t = raw.replace("\\n", "\n")

        def dollar(m):
            key = m.group(1).split("|")[0]
            if key in self.loc:
                return self._text(self.loc[key], depth + 1)
            self.offen["$" + key + "$"] += 1
            return _mk(OFFEN, "Wert im Spiel")

        def klammer(m):
            r = self._klammer(m.group(1), depth)
            if r is None:
                self.offen[re.sub(r"'[^']*'", "'…'", m.group(1))[:60]] += 1
                return _mk(OFFEN, "Wert im Spiel")
            return r

        t = DOLLAR.sub(dollar, t)
        t = BRACKET.sub(klammer, t)
        t = FORMAT_CODE.sub("", t)
        t = re.sub(r"•[ \t]*", "• ", t)                 # $BULLET_WITH_TAB$: Tabulator -> ein Leerzeichen
        t = re.sub(r"[ \t]+\n", "\n", t)
        return re.sub(r"[ \t]{2,}", " ", t).strip()


def wert(mk, v, mt, const):
    """Anzeige eines Modifikator-Werts wie im Spiel: (Text, Zahl oder None). Prozent laut Modifikator-Typ, Ja/Nein,
    benannte Konstanten (small_tax_income_efficiency_bonus) aus den Skriptwerten aufgelöst."""
    t = mt.get(mk) or {}
    roh = v
    if isinstance(v, str):
        if v in ("yes", "no"):
            return ("ja" if v == "yes" else "nein"), None
        if v in const:
            v = const[v]
        else:
            return f"Skriptwert {roh} (nicht aufgelöst)", None
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return str(roh), None
    if t.get("boolean") == "yes":
        return ("ja" if v else "nein"), v
    d = int(t["decimals"]) if str(t.get("decimals", "")).isdigit() else None
    if t.get("percent") == "yes":
        return _sign(v * 100, _stellen(v * 100, d if d is not None else 2)) + " %", v
    if t.get("already_percent") == "yes":
        return _sign(v, _stellen(v, d if d is not None else 2)) + " %", v
    return _sign(v, _stellen(v, d if d is not None else (3 if abs(v) < 0.1 else 2))), v


def _stellen(x, d):
    """Nachkommastellen: d, bei Werten ungleich 0, die gerundet 0 ergäben, so viele wie nötig (höchstens 6) - sonst stünde
    „+0“ da (automatischer Modifikator je Pop, z. B. expected_army_size 0,0002)."""
    while d < 6 and x and round(abs(x), d) == 0:
        d += 1
    return d


# ---------------------------------------------------------------- Bausteine
def _modformat(t):
    """Anzeigeformat eines Modifikator-Typs für die Seite (Herkunft der Werte): b = ja/nein, p = Prozent (× 100),
    a = schon in Prozent, sonst Zahl; dahinter die Nachkommastellen des Spiels, wenn angegeben."""
    f = ("b" if t.get("boolean") == "yes" else "p" if t.get("percent") == "yes"
         else "a" if t.get("already_percent") == "yes" else "")
    return f + (str(t["decimals"]) if str(t.get("decimals", "")).isdigit() else "")


def _modbloecke(d, mt, pfad=()):
    """Modifikator-Blöcke einer Definition -> [(block, [(modifikator, wert)])]; Auslöser/Effekte (potential, allow, on_* …)
    werden übersprungen, damit Vergleiche dort nicht als Wirkung erscheinen."""
    out = []
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        k = str(k)
        if NICHT_MOD.match(k):
            continue
        if isinstance(v, dict) and MOD_BLOCK.search(k):
            mods = [(m, x) for m, x in v.items() if m in mt and not isinstance(x, (dict, list))]
            if mods:
                out.append(("/".join(pfad + (k,)), mods))
        elif isinstance(v, dict):
            out += _modbloecke(v, mt, pfad + (k,))
    return out


def _token_begriff(feld, alias):
    """Begriffe, deren Schlüssel oder Alias als ganze Wortfolge im Feldnamen steht (längste zuerst, keine Überlappung)."""
    tok = feld.split("_")
    gefunden, belegt = [], set()
    for n in range(len(tok), 0, -1):
        for i in range(len(tok) - n + 1):
            if belegt & set(range(i, i + n)):
                continue
            k = "_".join(tok[i:i + n])
            if k in alias:
                gefunden.append(alias[k])
                belegt |= set(range(i, i + n))
    return list(dict.fromkeys(gefunden))


def _links(markup):
    return list(dict.fromkeys(k for k in re.findall(r"\[\[([^|\]]+)\|", markup or "") if k != "?"))


def _art_begriff(key, d, fam_tex):
    """Regeln 1-3 der Einordnung (siehe oben) -> (art, grund) oder None."""
    fam, tex = fam_tex
    if fam in FAMILIE:
        return FAMILIE[fam], f"Familie „{fam}“ des Spiels"
    tok = key.split("_")
    for i in range(len(tok)):
        for n in (3, 2, 1):                        # mehrteilige Stichwörter (court_language) vor einzelnen
            w = "_".join(tok[i:i + n])
            if len(tok[i:i + n]) == n and w in STICHWORT:
                return STICHWORT[w], f"Stichwort „{w}“ im Schlüssel"
    tex = str(tex or "").replace("gfx/interface/icons/", "").strip("/")
    best = max((p for p in TEXTUR if tex == p or tex.startswith(p + "/")), key=len, default=None)
    if best:
        return TEXTUR[best], f"Symbol-Ordner „{best}“"
    return None


def _ratgeber(begriffe_name, alias):
    """MECHANIK.md in Abschnitte (## …) und Stichpunkte (- **X** …) zerlegen -> (abschnitte, begriff -> [ids])."""
    if not os.path.exists(MECHANIK):
        return {}, {}
    zeilen = open(MECHANIK, encoding="utf-8").read().splitlines()
    abschnitte, zu = {}, collections.defaultdict(list)
    titel, start = None, 0
    bloecke = []
    for i, z in enumerate(zeilen + ["## ENDE"]):
        if z.startswith("## "):
            if titel:
                bloecke.append((titel, zeilen[start:i]))
            titel, start = z[3:].strip(), i + 1
    for nr, (titel, body) in enumerate(bloecke, 1):
        sid = f"m{nr}"
        abschnitte[sid] = {"titel": titel, "text": "\n".join(body).strip()}
        kurz = re.sub(r"\s*\(.*$", "", titel).strip()
        for k in MECHANIK_BEGRIFFE.get(kurz, []):
            if k in alias:
                zu[alias[k]].append(sid)
        # Stichpunkte: "- **X**" bis zum nächsten Stichpunkt gleicher Tiefe
        j = 0
        while j < len(body):
            m = re.match(r"^- \*\*([^*]+)\*\*", body[j])
            if not m:
                j += 1
                continue
            ende = j + 1
            while ende < len(body) and not re.match(r"^(- |\S)", body[ende]):
                ende += 1
            wort = _fold(re.sub(r"\s*\(.*$", "", m.group(1)).rstrip(":").strip())
            ziel = begriffe_name.get(wort)
            if ziel:
                pid = f"{sid}.{j}"
                abschnitte[pid] = {"titel": f"{kurz} – {m.group(1).rstrip(':').strip()}", "text": "\n".join(body[j:ende])}
                if sid not in zu[ziel]:
                    zu[ziel].append(pid)
            j = ende
    return abschnitte, dict(zu)


# ---------------------------------------------------------------- Aufbau
def build(voll, loc, modtypes, const=None, version=""):
    """Alle Einträge des Wikis aus dem Spielwissen-Ordner voll (data/spielwissen/<version>), der deutschen Lokalisierung loc
    und den Modifikator-Typen (Name, Prozent …)."""
    if const is None:
        from .wissen import _constants
        const = _constants()
    gc = _load(voll, "game_concepts")
    alias = {}
    for k, v in gc.items():
        alias[k] = k
    for k, v in gc.items():
        d = v["def"] if isinstance(v["def"], dict) else {}
        for a in _liste(d.get("alias")):
            alias.setdefault(str(a), k)
    T = Texte(loc, alias, voll, modtypes, const)
    E = {}

    # Ids zuerst (Verweise aus Show…Name brauchen sie beim Rendern)
    ages = _load(voll, "age")
    T.ids |= set(gc) | {_id("zeitalter", k) for k in ages}
    typdaten = {}
    for typ, ordner, *_ in TYPEN:
        typdaten[typ] = _injekt(_load(voll, ordner))
        T.ids |= {_id(typ, k) for k in typdaten[typ] if not str(k).startswith(("_", "@"))}
    for lk, lv in typdaten["gesetz"].items():
        for pk, pv in (lv["def"] or {}).items() if isinstance(lv["def"], dict) else []:
            if isinstance(pv, dict) and loc.get(pk):
                T.politik[pk] = _id("gesetz", lk)

    # Modifikatoren: Name, Erklärung, verlinkte Begriffe (Hauptbegriff zuerst, ohne Geltungsbereich); Quelle e = Erklärung
    # des Spiels verlinkt den Begriff, s = nur Schlüssel-Muster (Erklärung ohne Begriff-Verweis)
    mods = {}
    for m, t in modtypes.items():
        x = T(loc.get(f"MODIFIER_TYPE_DESC_{m}")) or ""
        bg, q = [k for k in _links(x) if k in gc and k not in SCOPE], "e"
        if not bg:
            bg, q = [k for k in _token_begriff(m, alias) if k not in SCOPE], "s"
        mods[m] = [t.get("name") or m, x, bg, q if bg else "", _modformat(t)]

    # 1. Spielbegriffe
    for k, v in gc.items():
        d = v["def"] if isinstance(v["def"], dict) else {}
        al = [str(a) for a in _liste(d.get("alias"))]
        name = T.begriff_name(k) or k
        an = list(dict.fromkeys(n for n in (T.begriff_name(a) for a in al) if n and n != name))
        x = T(loc.get(f"game_concept_{k}_desc")) or ""
        e = {"t": "begriff", "n": name, "x": x}
        if an:
            e["an"] = an
        if al:
            e["ak"] = al
        if d.get("shown_in_encyclopedia") == "no":
            e["ency"] = False
        e["_ft"] = (d.get("family"), d.get("texture"))
        E[k] = e

    # 2. Zeitalter
    zeitalter = []
    for k, v in ages.items():
        d = v["def"] if isinstance(v["def"], dict) else {}
        zeitalter.append({"k": k, "n": T.flach(loc.get(k)) or v.get("name") or k, "jahr": d.get("year")})
    zeitalter.sort(key=lambda z: z["jahr"] or 0)
    za_name = {z["k"]: z["n"] for z in zeitalter}
    vorher = {}
    for z in zeitalter:
        k = z["k"]
        d = ages[k]["def"]
        felder, w = [], []
        for f, val in d.items():
            if f in ("year",) or isinstance(val, dict):
                continue
            lk = AGE_TEXT.get(f)
            if lk and loc.get(lk):
                lab = loc[lk].split(": $VAL")[0]
                fm = (re.search(r"\$VAL\|([^$]*)\$", loc[lk]) or [None, ""])[1]
                z_ = T._zahl(val, fm) if isinstance(val, (int, float)) else str(val)
                felder.append([T(lab), z_ + (" Monate" if f == "months_for_exploration_spread" else ""), f])
            else:
                anzeige = ("ja" if val == "yes" else "nein") if val in ("yes", "no") else \
                    _num(val, 3) if isinstance(val, (int, float)) else str(val)
                bg = _token_begriff(f, alias)
                felder.append([None, anzeige, f, bg[:2], AGE_HINWEIS.get(f)])
        for blk in ("modifier", "unique", "goods_demand"):
            mm = [(m, x) for m, x in (d.get(blk) or {}).items() if m in modtypes]
            if mm:
                w.append([blk, [[m, wert(m, x, modtypes, const)[0]] for m, x in mm]])
        for f in ("max_ai_privilege_per_estate", "min_ai_privilege_per_estate"):
            if isinstance(d.get(f), dict):
                felder.append([None, ", ".join(f"{T.flach(loc.get(s)) or s} {n}" for s, n in d[f].items()), f,
                               _token_begriff(f, alias)[:2], AGE_HINWEIS.get(f)])
        desc = loc.get(f"{k}_desc")
        e = {"t": "zeitalter", "n": z["n"], "jahr": z["jahr"], "x": T(desc) or "", "felder": felder, "w": w,
             "za": [[k, "zeitalter", "Zeitalter selbst"]]}
        E[_id("zeitalter", k)] = e
        vorher[k] = d

    # 3. weitere Typen
    for typ, ordner, ein, mehr, art, begriff in TYPEN:
        for k, v in typdaten[typ].items():
            if str(k).startswith(("_", "@")):
                continue
            d = v["def"] if isinstance(v["def"], dict) else {}
            name = T.flach(loc.get(k)) if loc.get(k) else (v.get("name") or k)
            e = {"t": typ, "n": name, "x": T(loc.get(f"{k}_desc")) or ""}
            if typ == "gesetz":
                pol = []
                for pk, pv in d.items():
                    if not (isinstance(pv, dict) and loc.get(pk)):
                        continue
                    pw = [[b, [[m, wert(m, x, modtypes, const)[0]] for m, x in mm]] for b, mm in _modbloecke(pv, modtypes)]
                    pol.append({"k": pk, "n": T.flach(loc[pk]), "x": T(loc.get(f"{pk}_desc")) or "", "w": pw})
                if pol:
                    e["pol"] = pol
            else:
                w = [[b, [[m, wert(m, x, modtypes, const)[0]] for m, x in mm]] for b, mm in _modbloecke(d, modtypes)]
                if w:
                    e["w"] = w
            if isinstance(d.get("age"), str) and d["age"] in za_name:
                e["za"] = [[d["age"], "feld", AGE_FELD.get(ordner, f"Feld age in der Spieldatei {ordner}")]]
            for fld in ("potential", "allow"):
                adv = d.get(fld, {}).get("has_advance") if isinstance(d.get(fld), dict) else None
                if isinstance(adv, str):
                    e.setdefault("_adv", []).append((adv, fld))
            E[_id(typ, k)] = e

    # Zeitalter-Bezug über Fortschritte (advances, Feld age): Freischaltungen und Ja/Nein-Modifikatoren
    adv = _load(voll, "advances")
    for ak, av in adv.items():
        d = av["def"] if isinstance(av["def"], dict) else {}
        age = d.get("age")
        if age not in za_name:
            continue
        an = av.get("name") or ak
        bed = " (nur unter Bedingungen des Fortschritts)" if d.get("potential") else ""
        for f, typ in UNLOCK.items():
            for x in _liste(d.get(f)):
                x = str(x)
                if typ == "politik":
                    ziel = T.politik.get(x)
                    beleg = f"Fortschritt „{an}“ schaltet die Politik „{T.flach(loc.get(x)) or x}“ frei{bed}"
                elif typ:
                    ziel = _id(typ, x)
                    beleg = f"Fortschritt „{an}“ schaltet frei ({f}){bed}"
                else:
                    ziel = alias.get(x)
                    beleg = f"Fortschritt „{an}“ schaltet frei ({f}){bed}"
                if ziel in E:
                    E[ziel].setdefault("za", []).append([age, "frei", beleg, ak])
        for m, x in d.items():
            if (modtypes.get(m) or {}).get("boolean") == "yes" and x == "yes" and mods.get(m) and mods[m][2]:
                # Ziel nur, wenn der Begriff auch im Schlüssel des Modifikators steht – der erste Begriff der Erklärung ist oft
                # nur Kontext (Prüfer 30.10.: can_promote_industry -> „Gebiet“, global_may_build_paik_units -> „Zeitalter“)
                imk = _token_begriff(m, alias)
                ziel = next((b for b in mods[m][2] if b in imk), None) if mods[m][3] == "e" else mods[m][2][0]
                zu = MOD_ZU[mods[m][3]]
                if not ziel and imk:
                    ziel, zu = imk[0], MOD_ZU["s"]
                if ziel in E:
                    E[ziel].setdefault("za", []).append([age, "frei", f"Fortschritt „{an}“: {mods[m][0]}{bed}{zu}", ak])
    for e in E.values():
        for a, fld in e.pop("_adv", []):
            if a in adv and (adv[a]["def"] or {}).get("age") in za_name:
                e.setdefault("za", []).append([adv[a]["def"]["age"], "voraussetzung",
                                               f"setzt den Fortschritt „{adv[a].get('name') or a}“ voraus ({fld})", a])

    # Zeitalter ändern Begriffe: Modifikatoren (über ihre Erklärung) und Felder mit Begriff; nur neu oder geändert gegenüber
    # dem vorigen Zeitalter
    alt = {}
    for z in zeitalter:
        k, d = z["k"], ages[z["k"]]["def"]
        jetzt = {}
        for blk in ("modifier", "unique", "goods_demand"):
            for m, x in (d.get(blk) or {}).items():
                if m in mods and mods[m][2]:
                    jetzt[(blk, m)] = (x, mods[m][2][0], f"„{mods[m][0]}“{MOD_ZU[mods[m][3]]}")
        for f, x in d.items():
            if f == "year" or isinstance(x, dict):
                continue
            lk = AGE_TEXT.get(f)
            bg = [b for b in _links(T(loc.get(lk))) if b not in SCOPE] if lk and loc.get(lk) else _token_begriff(f, alias)
            if bg:
                lab = (f"„{T.flach(loc[lk].split(': $VAL')[0])}“" if lk and loc.get(lk)
                       else f"das Feld {f} (Begriff aus dem Feldnamen)")
                jetzt[("feld", f)] = (x, bg[0], lab)
        for key, (x, ziel, lab) in jetzt.items():
            if alt.get(key, (None,))[0] != x and ziel in E:
                E[ziel].setdefault("za", []).append([k, "zeitalter", f"Zeitalter {z['n']} ändert {lab}"])
        alt = jetzt

    # automatische Modifikatoren: skaliert mit einem Begriff -> Wirkung dieses Begriffs
    for k, v in _load(voll, "auto_modifiers").items():
        d = v["def"] if isinstance(v["def"], dict) else {}
        sw = d.get("scales_with")
        quelle = sw.get("value") if isinstance(sw, dict) else sw
        ziel = alias.get(str(quelle)) if isinstance(quelle, str) else None
        if not ziel:
            continue
        faktor = []
        if isinstance(sw, dict):
            for op, z in (("subtract", "−"), ("multiply", "×"), ("divide", "÷"), ("add", "+")):
                for y in _liste(sw.get(op)):
                    faktor.append(f"{z} {_num(y, 4) if isinstance(y, (int, float)) else y}")
            for op, z in (("min", "mindestens"), ("max", "höchstens")):
                if op in sw:
                    faktor.append(f"{z} {_num(sw[op], 4) if isinstance(sw[op], (int, float)) else sw[op]}")
            if "abs" in sw:
                faktor.append("Betrag")
        mm = [[m, wert(m, x, modtypes, const)[0]] for m, x in d.items() if m in modtypes and not isinstance(x, (dict, list))]
        if mm:
            E[ziel].setdefault("aw", []).append([k, " ".join(faktor), mm, bool(d.get("potential_trigger"))])

    # Einordnung nach Thema: Typen fest, Begriffe nach Regeln 1-3, dann Mehrheit der Verweise
    for typ, ordner, ein, mehr, art, begriff in TYPEN:
        for i, e in E.items():
            if e["t"] == typ:
                e["art"], e["ag"] = art, f"Typ {mehr}"
    for i, e in E.items():
        if e["t"] == "zeitalter":
            e["art"], e["ag"] = "forschung", "Typ Zeitalter"
        e["l"] = _links(e.get("x"))
        for p in e.get("pol", []):
            e["l"] = list(dict.fromkeys(e["l"] + _links(p["x"])))
    rein = collections.defaultdict(list)
    for i, e in E.items():
        for z in e["l"]:
            rein[z].append(i)
    for k in gc:
        r = _art_begriff(k, gc[k], E[k].pop("_ft"))
        if r:
            E[k]["art"], E[k]["ag"] = r
    for _ in range(3):
        neu = {}
        for k in gc:
            if "art" in E[k]:
                continue
            stimmen = collections.Counter(E[z]["art"] for z in E[k]["l"] + rein.get(k, [])
                                          if z in E and z not in LINK_ALLGEMEIN and "art" in E[z] and z != k)
            if stimmen:
                art, n = stimmen.most_common(1)[0]
                if n >= 2 and n * 2 >= sum(stimmen.values()):
                    neu[k] = (art, f"Mehrheit der verlinkten Begriffe ({n} von {sum(stimmen.values())})")
        if not neu:
            break
        for k, (art, grund) in neu.items():
            E[k]["art"], E[k]["ag"] = art, grund
    for e in E.values():
        if "art" not in e:
            e["art"], e["ag"] = "sonstiges", "keine Regel greift"
        if not e["l"]:
            del e["l"]
        if "za" in e:                          # doppelte Belege weg, Reihenfolge der Zeitalter
            reihe = [z["k"] for z in zeitalter]
            e["za"] = sorted({json.dumps(z, ensure_ascii=False): z for z in e["za"]}.values(),
                             key=lambda z: (reihe.index(z[0]), z[1]))

    # MECHANIK.md (Ratgeber-Wissen)
    namen = {}
    for k in gc:
        for n in [E[k]["n"]] + E[k].get("an", []):
            namen.setdefault(_fold(n), k)
    abschnitte, zu = _ratgeber(namen, alias)
    for k, ids in zu.items():
        if k in E:
            E[k]["rg"] = ids

    # Typen mit Namen, Quelle und Spielbegriff dazu; Modifikatoren alle (Wirkungen und „Wird verändert durch“ auf der Seite)
    typen = {"begriff": {"n": "Spielbegriff", "m": "Spielbegriffe", "o": "game_concepts",
                         "q": "Europedia des Spiels (main_menu/common/game_concepts, game_concepts_l_german.yml)"},
             "zeitalter": {"n": "Zeitalter", "m": "Zeitalter", "o": "age", "b": "age" if "age" in gc else None,
                           "q": "Spieldatei in_game/common/age, Texte aus der Lokalisierung"}}
    for typ, ordner, ein, mehr, art, begriff in TYPEN:
        typen[typ] = {"n": ein, "m": mehr, "o": ordner, "b": begriff if begriff in gc else None,
                      "q": f"Spieldatei in_game/common/{ordner}, Texte aus der Lokalisierung"}
    return {"format": FORMAT, "version": version, "arten": ARTEN, "typen": typen, "zeitalter": zeitalter, "e": E,
            "mods": mods, "politik": T.politik, "bloecke": BLOCK_NAME, "ratgeber": abschnitte, "offen": dict(T.offen.most_common(40))}


# ---------------------------------------------------------------- Zwischenspeicher
_CACHE = {}
_LOCK = threading.Lock()


def laden(voll, loc, modtypes, version="", log=print, gz=False):
    """Wiki als JSON-Bytes (gz=True: gzip-gepackt, rund ein Fünftel): aus dem Speicher, aus
    data/spielwissen/<version>/_wiki_f<FORMAT>.json oder neu gebaut. Neu gebaut auch, wenn analysis/MECHANIK.md
    (Ratgeber-Wissen) oder dieses Modul jünger ist als die Datei."""
    p = os.path.join(voll, f"_wiki_f{FORMAT}.json")
    quellen = max(os.path.getmtime(f) for f in (MECHANIK, os.path.abspath(__file__)) if os.path.exists(f))
    with _LOCK:                          # zwei Seiten gleichzeitig: nur einmal bauen
        c = _CACHE.get(p)
        if not (c and c[0] >= quellen):
            if os.path.exists(p) and os.path.getmtime(p) >= quellen:
                data = open(p, "rb").read()
            else:
                log("Mechanik-Wiki wird gebaut …")
                w = build(voll, loc, modtypes, version=version)
                data = json.dumps(w, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                pfade.atomar_schreiben(p, data)
                log(f"Mechanik-Wiki: {len(w['e'])} Einträge, {len(data) / 1e6:.1f} MB")
            c = _CACHE[p] = (os.path.getmtime(p) if os.path.exists(p) else quellen, data, gzip.compress(data, 6))
    return c[2] if gz else c[1]
