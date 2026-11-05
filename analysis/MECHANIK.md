# EU5 – Mechanik aus den Spieldateien (Stand 1.3.11, 28.09.)

Nur Belegtes, mit Fundstelle (Pfade relativ zu `game/`). Vollständige Definitionen liegen im Spielwissen-Cache
(`data/spielwissen/<version>/…`, im Datenbrowser unter „Spielwissen“). Die tatsächlich wirkenden Beiträge je Land/Ort
liefern ab Mod 0.12 die Aufschlüsselungs-Texte der Spieloberfläche (…Info/…Breakdown).

## Wie das Spiel Werte bildet

1. **Modifikatoren** (2436, `docs/modifiers.log`): Summe aller Quellen. Quellen stehen in den Definitionsordnern
   (Privilegien, Gesetze, Reformen, Fortschritte, Gebäude, Kabinettsaktionen …) – Rückwärtsindex
   `_modifikator_quellen.json` (1406 Modifikatoren mit mindestens einer Quelle).
2. **Statische Modifikatoren** (`main_menu/common/static_modifiers`, 2671): Das Spiel wendet sie selbst an, oft
   **skaliert mit einem Zustand** (Kommentare in den Dateien), z. B.
   - `location.txt` `control` × Kontrolle, `inverse_control` × (1 − Kontrolle): −100 % lokale Kronmacht, Levy-,
     Manpower- und Seeleutegröße; `control_50` × (Kontrolle − 0,5).
   - `location.txt` `prosperity`: +0,004 Entwicklung/Monat, +0,002 Bevölkerungswachstum, +0,1 Migrationsanziehung.
   - `location.txt` `development` (× Entwicklung 0–100): +2,5 % Bevölkerungskapazität je Punkt.
   - `location.txt` `location_base_values`: Kontrolle +0,0005/Monat, Wohlstand +0,0025/Monat, Nahrungskapazität 50,
     max. RGO-Größe 2, Beförderung 0,001, Degradierung 0,10.
   - `country.txt` `is_bankrupt`: Kronmacht −90 %, Moral −90 %, Forschung −90 %, Bau −90 %, Kreditrahmen −50 %.
   - `country.txt` `inflation_impact` (× Inflation): Hof-, Festungs-, Gebäude-, Nahrungs- und Stabilitätskosten.
   - `country.txt` `average_control_50`: Forschung +50 %, Kronmacht aus Bevölkerung +0,5, Selbstgefälligkeit −0,2/Monat.
3. **Automatische Modifikatoren** (`in_game/common/auto_modifiers`, 151, 61 mit `scales_with`): ausdrücklich
   Modifikator × Wert, z. B. × Legitimität (7), × Stabilität, × Machtprojektion, × Anteil Soldaten/Bauern/Bürger,
   × `num_of_advances_researched` (`num_advances_impact`: Machtprojektion 0,05 je Fortschritt).
4. **Skriptwerte** (`script_values`, 1137): benannte Formeln und Konstanten (z. B. `small_tax_income_efficiency_bonus`).
5. **Defines** (`loading_screen/common/defines/00_defines.txt`): feste Zahlen der Spielmechanik (Auswahl unten).

## Stände (`in_game/common/estates/00_default.txt`, `NEstate`, `NCountry`)

| Stand | Macht je Pop | Steuer je Pop |
|---|---|---|
| Krone | 0 | 0 |
| Adel | 25 | 100 |
| Klerus | 10 | 25 |
| Bürger | 4 | 40 |
| Gemeine (Bauern) | 0,025 | 1 |
| Dhimmi | 0,02 | 1 |
| Stämme | 0,01 | 0,01 |
| Kosaken | 0,5 | 0,02 |

- Zufriedenheits-Wirkung je Stand (`satisfaction = { … }`) wird mit **(Zufriedenheit − 0,5)** multipliziert
  (`LOW_SATISFACTION_THRESHOLD = 0.5`); Adel z. B. +0,2 Prestige/Monat und +0,5 Legitimität/Monat bei voller Zufriedenheit.
- `high_power` wirkt × (relative Macht − 0,25), wenn über 0,25 (`LOW_POWER_THRESHOLD`); Adel: −100 % Adels-Höchststeuer,
  +100 % Levy-Kampfkraft, +100 % Festungsunterhalts-Effizienz. `low_power` × −(Macht − 0,25) darunter (Adel +50 % Höchststeuer).
- Kabinett/Kommando geben je 0,25 Standesmacht (`BASE_ESTATE_POWER_FROM_CABINET/COMMAND`).
- Privilegien (Defines, Bedeutung der Einheit nicht belegt): `GRANT_PRIVILEGE_SATISFACTION_IMPACT = 3`,
  `GRANT_PRIVILEGE_PENALTY_FOR_OTHERS_SCALE = -0.5`, `REVOKE_PRIVILEGE_SATISFACTION_BASE = -0.25`,
  `REVOKE_PRIVILEGE_SATISFACTION_IMPACT = -3`.
- Kultur/Religion: Stände anderer (akzeptierter/tolerierter/diskriminierter) Kultur −5/−10/−20 % Macht und Zufriedenheit.
- Macht → Zufriedenheit: `POWER_TO_SATISFACTION_PENALTY = -0.5`. Vermögen → Macht: `COMPARATIVE_WEALTH_POWER_FACTOR = 0.01` (Deckel 1).
- Stände mit Verlust schränken den Pop-Bedarf ein: `POP_DEMAND_DEFICIT_SCALE = 0.5`.

**Ständefenster und Tooltips (geprüft 01.10., Screenshots des Nutzers, Holland 1344.1.1):**
- Fenster (`in_game/gui/government_lateralview.gui`): je Stand Macht (`Estate.GetRelativePower`), Bevölkerung, Zufriedenheit
  „Derzeit > Ausgewogenheit“; bei der Krone `Player.GetAverageControl` (65 %, Tooltip = `GetAverageControlInfo`: Zentralisierung,
  Kronmacht durch Bevölkerung, Selbstgefälligkeit, Forschung) und Reformen x/y; bei den Gemeinen `Estate.GetAvgEnfranchisment`
  = **Bauernbefreiung** (58,7 %): Pops erhalten nur diesen Anteil ihres Reichtumsanteils, der Rest geht an den Adelsstand
  (Lokalisierung `PEASANT_ENFRANCHISMENT_TT_TEXT`); Landesmodifikator `global_peasant_enfranchisment` 0,352 (Tooltip +35,26 %:
  Grundwert 25 %, Selbstbestimmtheit, Privilegien) – dessen Aufschlüsselung liefert der Mod nicht.
- **Ausgewogenheit** = Spielbegriff für die Zielzufriedenheit (`GetTargetSatisfactionInfo`); die Zufriedenheit nähert sich ihr
  um „Monatliche Veränderung“ (`GetSatisfactionTooltip`, zwei Nachkommastellen; Mod-Wert `monthly_satisfaction_change` nur auf
  0,001 gerundet). Größter Minuspunkt: „Steuern für <Stand>“ ≈ tatsächlicher Steuersatz (Adel −30,43 % bei Höchststeuer
  30,42 % × Regler 100 %, Bürger −37,03 % / 36,92 %, Gemeine −47,05 % / 48,17 % × 97,6 %) – nicht exakt.
- Schwellen: unter 25 % Zufriedenheit keine Steuern und keine Aufgebote (`GetCollectTaxesInfo`, `GetRaiseLevyInfo`); Wirkung
  der Zufriedenheit (`GetSatisfactionImpact`) kehrt sich unter 50 % um (Adel bei 49,63 %: Prestige −0,00, Legitimität −0,00).
- **Saldo eines Standes** (`GetBalance`) = steuerpflichtiges Einkommen (`GetLastMonthsIncomeBeforeTax`) − Steuern
  (`GetLastMonthsTax`) − Pops (`GetLastMonthsExpense`) + Posten aus `GetEconomyInfo` (Einnahmen durch mangelnde Kontrolle,
  Handel, Nahrung, Standesgebäude-Unterhalt, Zehnt) – nachgerechnet an allen vier Ständen auf 0,01; Spielstand-Felder
  entsprechend (taxable/uncontrolled/trade/food_income − paid_taxes − pop/building/io_expense), `city_income` zählt nicht.
  Alle Stände: Gold 0, Saldo negativ (Adel −5,36, Bürger −6,79, Gemeine −7,92, Klerus −3,66).
- **Steuern und Zufriedenheit (geprüft 1.1.1345):** Posten „Steuern für <Stand>“ in der Ausgewogenheit = Steuer ÷ steuerpflichtiges
  Einkommen (Adel 1,867 ÷ 5,24 = 35,63 %, Bürger 2,091 ÷ 4,78 = 43,74 % zu 43,75 % im Spiel) – genau, nicht der Regler.
  Wirkung der Zufriedenheit = voller Wert aus `satisfaction = { … }` × (Zufriedenheit − 0,5): Bürger bei 45,49 % Handelsvorteil
  0,5 × −0,045 = −2,25 %, Produktionseffizienz 0,05 × −0,045 = −0,22 % (Spieltext `GetSatisfactionImpact`, abgeschnitten).
- Privilegien (Mod `privileg`): `GetPower` = Machtbonus (Adelsmarine 0,33 = +33 %), `GetSatisfaction` = Ausgewogenheit (+0,05).
  Möglich je Stand nur als Anzahl (`num_possible_privileges`), ohne Namen.
- `GetRelativePowerDesc` wiederholt die Macht-Aufschlüsselung (`GetEstatePowerInfoBreakdown`) plus `GetPowerImpactInfo`.

## Religion, Kultur und Kunst (geprüft 01.10., Screenshots des Kulturfensters, Holland 1344.1.1)

- **Reformwunsch:** Spieltext `GetReformDesireInfo` „liegt bei 0.00% … ändert sich monatlich um +0.03%“. Der Wert
  `reform_desire` 0,03 (Religion und Land-Modifikator) ist der Monatszuwachs (+0,03 %, „Monatlicher Reformwunsch“ in
  `GetEffect`), nicht der Stand. Der Spieltext enthält den kaputten Platzhalter „der _ADJen Religion“.
- Katholizismus: 484 Länder, 60,749 Mio. Gläubige (`GetTotalPopulation`), 7 Sakralstätten, 17 Kardinäle (wir 0;
  Kardinäle über das Gebäude „Kardinalssitz“, Lokalisierung `game_concept_cardinal_desc`), Kardinalspreis +340 %.
- **Zehnt** (`game_concept_tithe`): geht an das Papsttum; bei uns der Posten „Zehnt“ der Stände (`GetEconomyInfo`,
  Spielstand `io_expense`): 0,12 + 0,04 + 0,14 + 0,08 = 0,38 / Monat. Hingabe (`devotion`) zählt laut Spiel für Theokratien.
- Glaubenseinfluss 24,4 von 1.000 (`maximum_religious_influence`), +0,30 / Monat (`monthly_religious_influence`, Verlauf passt).
- **Kulturfenster** = Mod `kultur` der Primärkultur: Kulturtradition `GetTradition` / `GetTraditionChange`, Kultureinfluss
  `GetInfluence` / `GetInfluenceChange`. Das Spiel zeigt **abgerundet** auf zwei Stellen (292,925 → 292.92, +0,985 → +0.98,
  123,959 → 123.95, −0,208 → −0.21). Angleichungsrate = `global_pop_assimilation_speed_modifier` (−25 %), Akzeptierte
  Kulturen = `used_cultures_capacity` / `GetCulturalCapacity` (0,15 / 1,00; Kosten je Kultur in `GetAcceptedCulturesInfo`),
  Kulturanteile = Pop-Kulturen des Spielstands (87,20 % / 12,79 %). Kunstfertigkeit = `skill_of_new_artists` (Mod 0,116,
  Spiel +11,62 %); „Künstlergehalt +0.00%“ des Fensters nicht zugeordnet. Gemeinsprache („Deutsch, Niederländisch als
  Dialekt“) liefert der Mod nicht; Glaubenssprache Latein mit Macht 26,71 % (`GetLiturgicalLanguagePower`).

## Diplomatie und Annektierung (geprüft 01.10., Screenshot des Nutzers)

- **Annektierung:** Spielstand `diplomacy_manager` `annex={ first second start_date monthly progress }` zählt **Punkte**, keinen
  Prozentwert. Kosten laut Tooltip des Spiels: Grundkosten 200 (`ANNEX_BASE_COST`) + je Ort; „1 Stadt“ kostet 13,33 (nicht die
  10 aus `ANNEX_COST_PER_LOCATION`, Herkunft des Faktors nicht gefunden – nicht in `location_ranks`). Zeeland: 114,0 ÷ 213,33 =
  53 %, Rest 99,3 ÷ 1,35 je Monat = 74 Monate → Spiel „1. März 1350“ (stimmt). Fortschritt je Monat laut Tooltip: Grundwert 0,50,
  Dezentralisierung −19,80 %, „deutlich kleiner“ +69,92 %, gleiche Hauptkultur +100 %, Klienteltreue +19,16 %.
  Andere laufende Annektierungen im Spielstand stehen bei 125 und 160 Punkten (also nicht fertig bei 100).
  Mod meldet für Zeeland `IsBeingAnnexed = 0`, die Schleife `every_country_we_are_annexing` aber Zeeland – Widerspruch ungeklärt.
  Datenfunktionen des Spiels: `Diplomacy.GetBeingAnnexedProgress`, `GetBeingAnnexedDate`, `GetBeingAnnexedCostInfo`,
  `GetBeingAnnexedInfo` (Scope des annektierten Landes) – bisher nicht im Mod.
- **Diplomaten:** `dip_GetNumOfDiplomats` 1,6 bei Maximum 1,0 (Kommazahl, kann über dem Maximum liegen); Spieltext
  „Wir gewinnen +0.00 Diplomaten pro Monat … Maximum +1.00“.
- **Diplomatiekapazität** genutzt 0,725 = Lehnsgut Zeeland 0,46 + Personalunion 0,25 (`GetActiveRelationsList`).
- Die Schleife `every_union_partner` liefert das eigene Land mit (Holland in der eigenen Beziehungsliste).
- **Klientelländer verwalten** (Screenshots 01.10.): „Vasall bezahlt Suzerän“ = 2 % der Grundwirtschaft (Zeeland 4,47 → 0,08);
  Mod `dip_GetSubjectPays` = −0,089 (Sicht des Vasallen). Territoriumsanbindung 93,04 % (Ø Kontrolle durch direkte Grenze
  65,23 %, Beitrag durch Treue +18,60) – nicht in den Daten. Armeegröße: potenzielle Aufgebote 710, Mannstärke 1.089
  (= `max_manpower` 1,089 Tsd.); die 710 liefert der Mod nicht (`GetPotentialArmyLevyPowerValue` 0,497 ist eine Stärke).
- Begriffe (Lokalisierung): Befreundet, Feindlich, Staatsehe, Kriegsgrund, Personalunion, Klienteltreue, Freiheitsdrang,
  Annektieren, Koalition.

## Militär (geprüft 01.10., Screenshots des Militärfensters)

- Fenster „Armeen“: Aufgebote „0 +0 / 3,802“ = ausgehoben / potenziell (Spieltexte `GetRaisedLevyStrength`,
  `GetArmyLevyPotentialStrength`, Mann; Kampfkraft 3,01 = `potential_army_size`); „Regulärtruppen ausheben 0 / 807“ =
  `regular_army_size` / `expected_army_size` (0,806 Tsd.); Armeetradition 2,33 % = `army_tradition` 2,333 (als Prozent);
  Armee-/Marinemoral 1.64 / 1.63 = `GetDefaultLandMorale` 1,643 / `GetDefaultNavalMorale` 1,636 (abgerundet);
  Festungsschwelle 1.00/2.16 = `used_fort_limit` / `GetFortLimit` (der Text `GetFortsLimitInfo` nennt fälschlich 0.00/2.16);
  Festungsverteidigung −103,07 % = `global_defensive`. „Schiffe bauen 2 / 3“ = `navy_size` / `expected_navy_size`.
- Aufgebote nur im Krieg oder bei Rebellen aushebbar; Erholung nach Niederlage ≥ 240 Monate (Spieltexte).
- Moral: „Der derzeitige Unterhalt multipliziert dies mit 0.50“ (Regler Heer/Flotte/Festungen 50 %).
- Tradition je Monat = `curbal_army_tradition` (+0,038 = 0,05 − 0,005 × 2,333 Verfall), Marine −0,104.
- Schiffsunterhalt je Schiff (`GetMaintenanceCost` −0,18 / −0,15) = Regler Flotte −0,33.
- Nicht im Mod: Disziplin, Kampf-Effizienz (Aufgebote), Belagerungsfähigkeit, Militärtaktiken, Rekrutierungskosten.

## Krankheiten (geprüft 04.10., Screenshots des Nutzers 1.1.1347, Spielstand, Spieldateien)

- 7 Krankheiten (`in_game/common/diseases`, Felder in `readme.txt`): Beulenpest, Große Seuche, Grippe, Malaria, Masern, Pocken,
  Typhus. Malaria bricht nie aus (Chance 0, R0 0) und wirkt nur über `environmental_infection` = 0,05 × Klima × Vegetation ×
  Gelände × 0,10 an der Küste – Den Haag 0,05 × 0,1 (ozeanisch) × 0,8 (Wald) × 3 (Feuchtgebiet) × 0,1 = **0,12 %** wie im
  Ort-Tooltip („Ansteckungsgebiet – Grund-Infektionsrate pro Intervall“), Kulagin 0,1875 % → Spiel 0,18 %.
- Übergreifen (readme): auf Nachbarorte, zum Marktzentrum, über die Handelspartner des Marktzentrums und zur Hauptstadt des
  Besitzers; nicht in unbewohnte Orte, bei Embargo, ab 50 % Befall im Ziel oder wenn die Krankheit dort stagniert.
- **Spielstand** `disease_outbreak_manager`: `data` = Liste je Krankheit mit `current` (laufende Ausbrüche), `locations` (je Ort
  `resistance`, bei Befall `origin` = Ausbruch und `percent` = Ausbreitung; Festkomma ÷ 2^30: Kulagin 904543458 → 84,24 %),
  `sub_units`, `countries` (je Land `deaths` je Ausbruch in Tausend). `database/<id>` = Ausbruch: `parameter` (type, origin),
  `outbreak_date`, `died_out_date`. Weltpolitik → Krankheiten zeigt Tote = Summe × 1000 **abgeschnitten** (Kalmyk 1,68724 →
  1,687; Gwa 51,61497 → 51,614) und als Flagge die Zahl der Länder mit Toten (Typhus Gwa 8). Malaria hat 2.417 endemische
  Einträge in `current`, das Spiel zählt 0 Ausbrüche.
- **Widerstand im Ort-Tooltip** = gespeicherter Wert + Seuchenwiderstand des Landes (`global_disease_resistance`, Holland +3 %),
  auf ganze Prozent abgeschnitten: Den Haag 7,66 → 10 %, 6,60 → 9 %, 41,81 → 44 %, Große Seuche 100 % (alle 4 Werte des
  Screenshots). Symbole (alphabetisch nach Schlüssel): Ratte Beulenpest, Tropfen Große Seuche, Lunge Grippe, Auge Masern,
  Hand Pocken (Lunge/Auge nur über die Reihenfolge – beide 6,60 %). Typhus/Malaria ohne Eintrag → kein Symbol. Große Seuche:
  Alte Welt zu Spielbeginn 1,0 (immun), wirkt nur in Amerika.
- Situation Schwarzer Tod (`situation_manager/black_death`: status, start, Variable `original_outbreak` = Ausbruch 2470).
- **Gütertexte ohne Land unbrauchbar** (Test 0.18 + Gegenprobe ohne Mod, 24.10.): `Goods.GetSources` und
  `Goods.GetDemandsForBuildings` werten die Bedingungen der Gebäude ohne Land aus („Scoped object of type 'country' is not
  valid (Land (---))“, im Debug-Modus ~1.750 Skriptfehler je Monat) – es bleiben nur Gebäude ohne Fortschritt und ohne
  `country_potential` (Quellen 40 von 126, Nachfrage 161 von 1.713). `GetGameConceptFromCategory` scheitert bei den 22 Gütern
  der Kategorie produced („Could not find data system function 'produced'“). Vollständig: Produktionsmethoden der Gebäude.
- **Rohstoff-Ausbaukosten** (`Location.GetUpgradeRGOBuildCostAndTime`, Test 0.18 an allen 8 Orten): „Standardmäßige Bauzeit:
  225Tage / Baukosten: 84.3“ – **Dezimalpunkt**; Holland 1347.5: 168 / 140 / 98,3 / 84,3 / 70,2 Gold je nach Ort, je 225 Tage
  (`GetRGOCost` schlüsselt die Kosten über die Preise der für den Ausbau nötigen Güter auf).
  Endet, wenn der Ausbruch nicht mehr aktiv ist (`can_end = NOT disease_outbreak_is_active = var:original_outbreak`); der grüne
  Haken im Fenster ist eine feste Textur. Aktionen (generic_actions, je `exclusive_group` eine): z. B. „Das Land abschotten“
  (10 Stabilität; Ein- und Ausfuhrverbot, Bürger −10 % Ausgewogenheit), „Die Erkrankten absondern“ (10 Stabilität;
  Seuchenwiderstand +15 %), „Städte abschotten“ (40 Stabilität; Beulenpest-Auswirkungen −80 %), „Heilmittel beschaffen“ (Gold,
  skaliert). Alle Aktionen nur bei laufender Situation (`visible situation_is_active`), die meisten zusätzlich nur mit dem
  ursprünglichen Ausbruch im eigenen Land (`country_has_disease_outbreak`); „Das Land abschotten“, „Heilmittel beschaffen“, „Die
  Erkrankten absondern“ sind ohne diese Bedingung sichtbar. Größe (`size`): „Städte abschotten“ × Kontrolle × 0,85 (bei mehr als 4 Städten × 4/Anzahl),
  „Heilmittel beschaffen“ Gold = Monatseinkommen × 0,05–0,1 (mind. 1), „Massenvergebung“ × 0,1. **Pesthaus** (+30 %) nur während
  des Schwarzen Tods und nach „Die Kranken in Pesthäusern unterbringen“ (strict_quarantines → `enable_pest_house`), wird danach
  entfernt (`remove_if`); **Krankenhaus** (+10 %) mit Fortschritt Hospitäler in Orten ab Entwicklung 20.
- **Mod:** kein Iterator über Ausbrüche – fremde Ausbrüche nur im Spielstand. Eigenes Land/eigene Orte über Script Values mit
  Triggern (`"disease_resistance(disease:<k>)"`, `"disease_presence(disease:<k>)"`, `"disease_country_deaths(disease:<k>)"`,
  `"disease_outbreak_country_deaths(situation:black_death.var:original_outbreak)"`; Schreibweise wie Vanilla
  events/situations/black_death.txt) – **Test 0.18 (24.10., 1347.2–5): alle gehen.** Den Haag Widerstand 7,58 / 100 / 5,80 /
  5,80 / 41,53 % (sinkt monatlich, `monthly_resistance_reduction`), Malaria-Grundrate 0,12 % (Leiden 1,12 %).
- **Gescheitert:** `Location.GetDiseaseResistance('<k>')` mit Krankheitsname als Text („Data error in loc string“, FetchData
  failed) – die Funktion braucht ein Disease-Objekt (Oberfläche: `Disease.Self`); `GetDiseaseInfo('<k>')` hat dieselbe Form.
- **Seuchenwiderstand des Landes +3 %** kommt vom Fortschritt **Alchemie** (Zeitalter I) – `Country.GetDescriptionFor(
  'global_disease_resistance')`.
- **Schwarzer Tod live:** `days_since_situation_start` 92 → 181 (1.2.–1.5.1347, Beginn 1.11.1346); `DiseaseOutbreak.GetDeaths`
  liefert Tausend mit deutschem Komma („24,428“ → „49,588“ = 49.588 Tote, Kalmyk-Ausbruch; Spielstand 1.1.1347: 1,687);
  `GetTooltip` nennt die befallenen Orte („bislang auf 175 Orte ausgebreitet“).

## Pops (`NPop`)

- Zufriedenheit: Grund 0,2; Hauptkultur +0,25, akzeptiert +0,10, toleriert +0,05; Kultur-/Religionsmeinung je ±0,05;
  andere Religion −0,05; `GOODS_PRICE_SATISFACTION_SCALE = -0.05`, `LACK_OF_GOODS_SATISFACTION_SCALE = -0.5`,
  `ESTATE_SATISFACTION_OFFSET = 0.5`, `ESTATE_SATISFACTION_SCALE = 2.0` (Verrechnung nicht belegt).
- Rebellion: unter 0,05 sicher (sonst `pop_join_rebel_threshold` 0,2), Austritt über 0,1 (sonst 0,35).
- Bedarf wächst mit Entwicklung (`DEVELOPMENT_SCALE_ON_DEMAND = 0.05`), Einkommensbedarf × 1,33.

## Gesellschaftswerte und Regierung (geprüft 30.09., Tooltip-Screenshot des Nutzers)

- Monatliche Veränderung einer Achse = Land-Modifikator `monthly_towards_<rechter Pol>` − `monthly_towards_<linker Pol>`
  (alle Quellen: Gesetze, Privilegien, Kabinett, Kontrolle, Entwicklung …). Zentralisierung–Dezentralisierung 0,575 − 0,308
  = +0,267, Tooltip „+0.26“ (abgeschnitten). Nachgerechnet an Aristokratie–Plutokratie (−0,24/Monat, Spielstand → live −1,21
  in 5 Monaten), Leibeigenschaft (−0,05), Individualismus (+0,05).
- **Grenze = 100 × monatliche Veränderung (netto)** in Zugrichtung: Tooltip „Kann nicht mehr als 26.66 in Richtung
  Dezentralisierung vorangetrieben werden“; Spielhinweis „bis auf maximal das 100-fache des derzeitigen Drucks“. Liegt der Wert
  darüber, steht er still (Holland: Dezentralisierung 60, Traditionalismus 30, Spiritualismus 50 seit Spielbeginn unverändert).
- Parlament wieder einberufbar, wenn `months_since_last_parliament_called` > 59 (`generic_actions/parliament.txt`,
  `NCountry.PARLIAMENT_COOLDOWN_MONTHS = 59`) und kein Parlament tagt.
- Kabinett: `GetDaysUntilFullyImplemented` ist bei laufenden Aktionen negativ = Tage seit Beginn (3.7.1341 → 1.1.1344 = 912).
- Herrscher-Eigenschaften, „seit“, Personalunion und Ehe stehen in `Person.GetDetailedInformation`.

## Forschung und Institutionen (geprüft 30.09.)

- Forschung je Monat = Land-Modifikator `research_speed` × (1 + `research_speed_modifier`): 1,053 × 1,322 = 1,392 = Zuwachs von
  `research_progress` im letzten Monat (21,945 − 20,552). Die Kosten des laufenden Fortschritts stehen nicht in den Daten
  (`Country.GetCurrentResearch` → `CurrentResearch.GetResearchCost` bräuchte Mod 0.16); der Spielstand hat `current_research`
  mit 5 IDs, die sich nicht über die Reihenfolge der Spieldateien zuordnen lassen.
- Tooltip „Monatlicher Forschungsfortschritt“ (Walachei 1339, Screenshot 31.10.): +1,21 aus Siedlungsland +1,00, Macht der
  Glaubenssprache +0,00, Alphabetisierung +15,21 %, Kontrolle −3,80 %, eingeführte Institutionen +10,00 %:
  1,00 × (1 + 0,1521 − 0,038 + 0,10) = 1,214 – dieselbe Regel (Grundwert × (1 + Summe der Prozente)); der Ratgeber zeigt 1,21.
- Spielstand `institution_manager.institutions`: `active` = im laufenden Zeitalter gültig, `origin` = Ursprungsort (ab dem
  Entstehen), `months` zählt bis zum Entstehen und bleibt dann stehen (Bankwesen 1342.8 origin gesetzt, months bleibt 6).
  Chance je Monat laut `Institution.GetPossibility` (Renaissance 16 %, Bankwesen 6 %). `GetSpawnReasons` ist unbrauchbar
  (gegen „Stockholm“ ausgewertet, Steuerzeichen).
- Holland 1.8.1343: alle 69 Fortschritte aus dem Zeitalter der Traditionen (Zeitalter je Fortschritt aus `advances/*.def.age`).

## Markt und Handel (`NMarket`, `NEconomy`)

- Preis nähert sich monatlich um 5 % dem Zielpreis (`MONTHLY_PRICE_CHANGE`); Preiseinfluss −33 % bis +300 %.
- Nachfrage-Elastizität: −40 % je 100 % über Grundpreis, mindestens 35 % der Grundnachfrage.
- Skalen für Handel in Angebot/Nachfrage: `TRADE_IMPACT_ON_SUPPLY_SCALE = 0.75`, `TRADE_IMPACT_ON_DEMAND_SCALE = 0.75`,
  `BURGHER_TRADE_IMPACT_ON_SUPPLY_SCALE = 0.1`, `BURGHER_TRADE_IMPACT_ON_DEMAND_SCALE = 0.25`.
- Marktzugang: 100 % Basis, −0,5 % je Pixel Entfernung; See ×0,75, offene See ×1,5, flussabwärts ×0,5, flussaufwärts ×0,9;
  ohne Hafen +0,1 Aufschlag. Anziehung: gleiche Provinz +0,2, gleiches Gebiet +0,1, gemeinsame Sprache +0,05.
- Märkte mit ≤ 5 Orten „verdorren“ nach 24 Monaten, wenn zur Hälfte überflügelt.
- Händlerunterhalt 0,25 (`MERCHANT_MAINTENANCE_COST`); Bürger-Handelsgewinn-Skala 0,1 (`TRADE_BURGHER_PROFIT_SCALE`).
- **Marktfenster (geprüft 1.2.1342, Screenshot des Nutzers, Markt von Brugge; `shared/market_tooltips.gui`):**
  - „Marktwert“ = `Market.GetTotalValueTraded` („letzten Monat Waren im Wert von 799,98 gehandelt“) = Σ Preis × Nachfrage
    (`total_taken`) aller Güter im Spielstand: 800,03. Der gleichnamige Mod-Wert (RG2 a.markt) liefert 587,7 und liegt in
    allen verglichenen Monaten 20–30 % darunter (1339.7–1342.2) – nicht genutzt. `GetTotalProductionValue` zeigt das Spiel nirgends.
  - „Ortssaldo“ (Größte örtliche Überschüsse/Mängel) = `Market.GetBalanceWithoutTrades(gut)` = Angebot aus `Production`
    − Verbrauch (`taken`) ohne `Trade` und `BurgherTrades`; alle 10 Güter im Fenster gleich (Stoff +54,88, Wolle −24,13,
    Seide −9,33 …), das Spiel schneidet nach 2 Stellen ab. Das Spielstandfeld `possible` ist es nicht (Wolle +10,65).
  - „Mächtigste Händler“: Handelsvorteil = `merchant.power` (Holland 18,73), Handelskapazität frei/gesamt, Handelsgewinn;
    einen Anteil in % zeigt das Spiel nicht. Summe aller Händler im Spielstand 135,0, Mod `total_merchant_power` 125,0.
  - Nahrungsbestand 28597/38031 (+132) = Mod `market_food`/`market_max_food`/`market_monthly_food_balance` = Spielstand.
  - Liste der Märkte: Handelseinkommen des Landes +1,82 = Handelsgewinn 6,18 × Handelseinnahmen-Anteil 29,53 %.
- **Wirtschaft → Märkte (oben) = Land-Modifikatoren** (1.2.1342): Handelsvorteil +15,43 % = `global_merchant_power` 0,154,
  Marktanziehung +1,62 % = `global_trade_center_power` 0,016, Verkaufseffizienz +5,12 % = `selling_efficiency` 0,051.
  Handelskapazität +7,90 % passt nicht zu `global_merchant_capacity_modifier` 0,071 (ungeklärt).
- **Handelsvorteil eines Landes im Markt** (Tooltip über dem Rang in Wirtschaft → Märkte, `Market.GetMerchantPowerInfo`;
  Screenshot des Nutzers 30.09., Holland in Brugge 19,09, Nummer 2 von 32):
  - „Im Besitz Orte“ +8,91 = Σ Orts-Modifikator `local_merchant_power` der eigenen Orte im Markt (Marktzentrum +20, Marktplatz,
    Händlergilde …) × (1 + Land-Modifikator `global_merchant_power`): 7,45 × 1,196 = 8,91 (live 1343.1) – **genau**.
  - „Marinepräsenz“ +10,15 ≈ Σ Präsenz des Landes in den Seezonen (Spielstand `maritime_manager/objects`, presences
    {power, country}) × `merchant_power_from_maritime` 0,05: 1.8.1342 201,0 → 10,05; 1.2.1343 197,1 → 9,86 – der Tooltip lag
    dazwischen, genau prüfen ließ es sich nicht. Welche Seezonen zu welchem Markt zählen, ist offen (Holland: 7 Zonen, 5 mit
    ~36–43, Schelde-Mündung und Ostfriesische Inseln je ~1).
  - „Gebäude in fremdländischen Orten“ 0,00.
  - Summe der Teile 19,06 zu 19,09 angezeigt (Rundung/Zeitpunkt).
- **Marktanziehung:** `Location.GetMarketAttractionInfo` (Mod: nur Hauptstadt) listet alle Märkte absteigend, z. B. Den Haag
  1343.1: „Brugge: 149.84%“ = Marktzugriff 89,70 % + Marktanziehung +40,14 % (Marktzentrum: Ortsrang, Entwicklung,
  Stadtmauern, Gebäude, Hafen; Besitzer: Prestige, Handelseinnahmen gegen Steuergrundlage, Handelszentrenunterstützung;
  Handelssprache) + Diplomatische Verträge +20 %; Köln 64,53 %, London 44,41 %, Lübeck 40,53 % (Platz 4 von 45).
  Laut Spielbegriff die Zugkraft eines Marktzentrums, einen Ort in den eigenen Markt zu holen; Marktschutz wirkt dagegen.
- Knapp (Seite): Nachfrage > Angebot × 1,05 **und** Preis steigt (letzter Schritt im Preisverlauf). Lübeck 1342: Zucker mit
  Nachfrage 0,001, ohne Angebot, 1,0 auf Vorrat, Preis fällt stetig 6,36 → 3,21 – nach der reinen Mengenregel „knapp“.
- Märkte ändern ihre Größe: Brügge am 1.2.1342 von 55 auf 80 Orte (Bevölkerung 1.405 → 1.757 Tsd., Händlermacht gesamt
  101 → 125) – unser Anteil fiel dadurch, unser Handelsvorteil blieb (18,77 → 18,73).

## Zölle und Handelsbestellungen (Patch 1.4, geprüft 27.10., Spielstand 1.4.4 Walachei 1337.8.1)

- **Begriffe** (Lokalisierung deutsch): Handelsbestellung (`game_concept_trade_order`), Handelsrichtlinien
  (`TRADE_POLICIES_LATERALVIEW_TITLE`), Einfuhrzoll, Ausfuhrzoll, Subvention, Zollbefreiung, Marktbesitzer.
- **Wer Zölle setzt:**
  - Nur der Marktbesitzer (`TRADE_POLICIES_TAB_REQUIRES_MARKET`). Marktbesitzer ist das Land, dem das Marktzentrum gehört
    (`game_concept_market_owner_desc`).
  - Der Satz gilt je Gut für alle eigenen Märkte (`TRADE_POLICIES_TARIFF_SLIDER_FILTER_LOCKED_TT`), Bereich −1 bis +1; negativ ist
    eine Subvention (effects.log `set_goods_export/import_trade_policy`).
  - Einen Ausfuhrzoll erhebt der Besitzer des Ausgangsmarkts, einen Einfuhrzoll der des Zielmarkts (Spielbegriffe).
  - Beleg: Die Ausfuhren der Walachei aus Tarnowo (Markt Bulgariens) zahlen genau für die Güter in Bulgariens
    `goods_export_tariffs` Zoll (Schmuck 20 %, Kupfer 12,6 %), für Pelze, Faserpflanzen und Baumwolle nicht.
- **Höchstsätze** (Fenster Handelsrichtlinien, „Maximale Zölle“, `TRADE_POLICIES_MAX_TARIFFS_TT`):
  - `max_tariff` gilt für Ein- und Ausfuhrzoll, `max_trade_subventions` für Subventionen. Grundwerte je 0,20
    (`auto_modifiers/country.txt`); Walachei 1337: 20 % / 20 % (Mod landmod).
  - Quellen (Spielwissen `_modifikator_quellen`): Fortschritte (+5 bis +10 %), Gesetz Wirtschaftspolitik (Kriegswirtschaft +15 %,
    Freihandel −10 %, Kameralismus +10 %), Reformen (Statut der Monopole +15 %), Klientelland-Arten Hanse/Handelshaus (+5 %).
  - Gesellschaftswert `mercantilism_vs_free_trade` (ab Zeitalter Reformation): `left_modifier` max_tariff/max_trade_subventions
    +0,5. Die Wirkung je Stellung ist ungeprüft.
- **Zolleinnahmen:**
  - Das Land erhält einen Anteil, die Stände den Rest (`TARIFF_INCOME_TO_ESTATES` „Anteil der Zölle für die Stände“;
    `TARIFF_INCOME_TRADE_BREAKDOWN` „Und der Anteil für das Land in Höhe von … beruht auf“).
  - Modifikator `tariff_income`: Grundwert 0,1 (`auto_modifiers/country.txt`) + Kronmacht × 1,0 (`estates/00_default.txt`), wie bei
    `trade_income`. Dass er der Anteil des Landes ist, ist nicht nachgerechnet.
  - Spielstand: Land `last_months_tariff_income`, Stand `last_month.tariff_income`. Schweden 1337.8: Land 0,325, Stände 0,935.
    Der Anteil des Landes lag in 15 Ländern bei 17,6–43,4 %, meist über seinem Anteil am Handel (Ausnahme Ragusa 37 % zu 41 %).
  - `last_months_burgher_tariff_revenue` (72 Länder): Bedeutung offen.
- **Route:**
  - `Trade.GetTariffValue` ist negativ, wenn wir zahlen. Der Zoll ist im Gewinn der Route schon abgezogen (nachgerechnet 27.10.).
  - Die Zeile „Zölle“ im Gewinn-Tooltip der Route (`TRADE_TOOLTIP_PROFIT`) ist `GetSoundTollFee`, also der Sundzoll und nicht
    dieser Zoll (Prüfer 27.10.). Mit Sundzoll passt Verkauf − Einkauf − Unterhalt − Sundzoll − Zoll bei allen Routen
    einheitlich: Gewinn ≈ 1,07 × dieser Wert.
  - Text `Trade.GetTariffInfo` (`TRADE_EXPORT_TARIFF_TT`): „Bulgarien verlangt einen 20% Zoll auf Ausfuhren von: Schmuck
    (1.01)“. Der Goldwert ist |GetTariffValue| auf 2 Stellen (1,01 zu −1,015).
- **Herkunft einer Route** (`panels/trade/trade_overview_possible_trades.gui`, `shared/trade_details.gui`):
  - Zahnrad bei `IsFromTradeOrder` („wird durch eine Handelsbestellung geschaffen“).
  - Automatik ohne Bestellung und ohne Sperre („wird von der Automatisierung übernommen“).
  - Schloss bei `IsLocked` ohne Bestellung („durch eine Vereinbarung geschützt“).
- **Handelsbestellungen** (`trade_orders_l_german.yml`):
  - Sie bilden eine Prioritätsliste; frühere bekommen zuerst Händlerkapazität (`TRADE_ORDER_PRIORITY_INFO`).
  - Modi: Gewinn-, Nahrungs- und Knappheitsschwerpunkt. Dazu ein Mindestgewinn je Kapazität und erlaubte Märkte (beliebig,
    angepasst, eigene, Kolonial-, Landes-, Klientelmärkte). Die KI wählt die Routen täglich.
  - Defines: `NCountry.DEFAULT_TRADE_ORDER_MIN_PROFIT = 0.25`; `NAI.TRADE_ORDER_MAX_TRADES_PER_MONTH = 8`,
    `TRADE_ORDER_MIN_TRADE_CAPACITY = 0.1`, Kapazitätsstufen je Gewinnspanne (`TRADE_ORDER_GOOD_MARGIN_BAND_*`).
  - Spielstand: `trade_order_manager/database`, 1337.8.1 leer. Format unbekannt.
  - In 1.3 standen Handelsaufträge am Land: `trade_orders = { { market=131 goods=iron trade_order_is_import=yes
    trade_order_capacity=2 } }` (MP_WAL_1479, 1.3.11).
  - **1.4.5 (Test 29.10., Walachei 1338.4.7):**
    - Eintrag `market`, `trade_order_goods_entry = { { goods=… [trade_order_is_import=yes] } … }`, `trade_order_min_profit`,
      `trade_order_capacity` mit `trade_order_is_percentage`, `trade_order_use_min_profit`, `trade_order_last_edit_month`,
      `trade_order_last_restructure_month`. Ohne `trade_order_is_import` ist es eine Ausfuhr.
    - Der Eintrag nennt kein Land; das Land führt `trade_order_refs={ <Nr.> }`.
    - Die Routen der Bestellung stehen in `trade_manager` mit `from_trade_order=yes`, `trade_order_ref=<Nr.>` und `locked=yes`.
      Live (Mod) liefern sie `IsFromTradeOrder=1`.
- **Handelsbestellungen – Regeln des Spiels** (geprüft 29.10., `trade_orders_l_german.yml`, Defines
  `loading_screen/common/defines/00_defines.txt`):
  - Modi:
    - Gewinnschwerpunkt (`TRADE_ORDER_MODE_PROFIT_TT`): die lohnenswertesten Handel bei den gewählten Waren und Märkten.
    - Nahrungsschwerpunkt (`…_FOOD_INFO`): bringt Nahrung nur auf einen Markt, der ohne die Bestellung Nahrung verlieren würde
      und unter 60 % Nahrungsbestand hat (`NAI.TRADE_ORDER_FOOD_MAINTAIN_STOCKPILE_FRACTION`); unter 40 % füllt sie den Bestand um
      5 % des Höchstwerts je Monat auf (`…_GROWTH_…` 0,4, `…_MONTHLY_STOCKPILE_GAIN` 0,05). Ausfuhren der eigenen Nahrung pausieren
      unter 50 % Bestand im eigenen Markt und enden unter 25 % (`…_EXPORT_SELF_STOP/CANCEL_FRACTION`).
    - Knappheitsschwerpunkt (`…_NEEDS_INFO`): die Waren der Liste der Reihe nach, nur solange der Zielmarkt mehr verbraucht, als
      er herstellt, und der Vorrat unter 10 % des Höchstvorrats liegt (`…_NEEDS_STOCKPILE_EXCLUSION_FRACTION`); unter 5 % füllt
      sie den Vorrat um 0,5 % des Höchstwerts je Monat auf. Den Höchstvorrat je Ware hat der Spielstand nicht.
  - Mindestgewinn je Händlerkapazität (`TRADE_ORDER_MIN_PROFIT_TT`): darunter keine Handel. Je näher der beste Gewinn einer Ware
    an der Schwelle liegt, desto langsamer und kleiner bekommt sie Kapazität – die Bestellung kann Kapazität ungenutzt lassen.
    Ohne Haken oder negativ sind Verluste möglich. Standard 0,25 (`NCountry.DEFAULT_TRADE_ORDER_MIN_PROFIT`).
  - Kapazität als Prozentsatz unserer Händlerkapazität oder als feste Menge, jeweils ein Maximum; die Bestellung setzt sie nicht
    zwingend ein (`TRADE_ORDER_TC_TOGGLE_TO_…_DESC`). Frühere Bestellungen bekommen zuerst Kapazität (`TRADE_ORDER_PRIORITY_INFO`).
    Ohne eigene Kapazität im Markt kann eine Bestellung nichts zuordnen (`TRADE_ORDER_NO_TC_IN_MARKET_TT`). Die Oberfläche zeigt
    „Bestellungen nutzen [GetTradeOrderTotalCapacity] / [GetAutomatedCapacity] Händlerkapazität“.
  - Ohne gewinnbringende Route versucht die KI es jeden Tag erneut; liegt die beste Route unter dem Mindestgewinn, nennt das
    Spiel sie mit ihrem Gewinn je Händlerkapazität (`TRADE_ORDER_BELOW_PROFIT_CUTOFF`). Dieser Wert ist für den Mod nicht
    erreichbar (`TradeOrderItem.*` sind Oberflächen-Objekte).
  - Einträge: bestimmte Ware (Einfuhr/Ausfuhr), „Beliebige Einfuhr/Ausfuhr“, „Beliebige Nahrung“, „Beliebige Regierungs-/
    Gebäude-/Pop-Bedarfe“ (monatlich neu bewertet; Routen für nicht mehr gebrauchte Waren werden abgebrochen). Voreinstellung
    „Beliebiger Bedarf auf meinen Märkten“ = Knappheitsschwerpunkt, beliebige Ware, ohne Mindestgewinn, eigene Märkte.
  - Erlaubte Märkte: „Beliebig“ oder „Angepasste Auswahl“; Gruppen Märkte im Besitz, Kolonial-, Landes-, Klientelmärkte,
    Institutions-Quellen.
  - KI je Ware (`NAI`): Kapazitätsstufen nach Gewinnspanne = bester Gewinn je Kapazität − Mindestgewinn (`…_GOOD_MARGIN_BAND_1/2/3`
    0,1/0,4/0,6), Zuwachs je Monat 10/20/30/40 (`…_MONTHLY_TC_BAND_0–3`), Obergrenze max(30/80/120; 20/70/90 % unserer
    Kapazität im Markt), ab 0,6 und ohne Mindestgewinn keine Obergrenze. Eine Route wächst erst ab 85 % Auslastung, nach dem Schrumpfen 6 Monate nicht (`…_REGROW_…`); neue
    Routen ab 0,1 Kapazität (`TRADE_ORDER_MIN_TRADE_CAPACITY`), höchstens 8 je Monat (`TRADE_ORDER_MAX_TRADES_PER_MONTH`).
  - KI allgemein: verschiebt Kapazität zur besseren Route ab dem 1,25-fachen Gewinn (`AI_STEAL_MERCHANT_CAPACITY_PROFIT_MARGIN`),
    meidet Routen unter 0,5 Kapazität (`AI_MINIMUM_TRADE_SIZE`), überspringt Routen unter 0,25 Gewinn je Kapazität
    (`AI_PERFORMANCE_TRADE_PROFIT_PER_WEIGHT_CUTOFF`).
  - Spielstand: Die Feldnamen `trade_order_mode`, `trade_order_import/export_markets`, `…_market_groups`,
    `trade_order_goods_entry_is_any`, `trade_order_goods_need_category` kennt das Spielprogramm (Zeichenketten in `eu5.exe`). Die
    Bestellung der Walachei (1338.4.7) hat keins davon – vermutlich Standardwerte, welche, ist offen.
- **Nachgerechnet 29.10.** (Walachei 1337.5–1338.4, alle 27 Routen-Monate, Daten-Mod):
  - Unterhalt einer Route = genutzte Kapazität × 0,25 (`NCountry.MERCHANT_MAINTENANCE_COST`): Wolle 5,86 → 1,465;
    Urkorn 1337.8 genutzt 0,857 (zugewiesen 1,352) → 0,214.
  - `GetProfitPerMerchantCapacity` = Gewinn ÷ genutzte Kapazität (`GetActuallyUsedOrAssignedMerchantCapacity`):
    Urkorn 1337.8 0,263 ÷ 0,857 = 0,307 (÷ zugewiesen wären es 0,195).
  - Ausfuhrzoll einer Route = Satz × Einkaufswert (`GetBuy`): Wolle 1338.4 1,948 × 9,599 % = 0,187; Feinstoff 1338.3
    2,728 × 2,242 % = 0,061 und 1338.4 2,451 × 2,242 % = 0,055 zu 0,054; Urkorn 1337.7/8 0,181 ÷ 0,908 und 0,117 ÷ 0,589 = 19,9 %
    (Satz 20 %).
  - Kapazität je gehandelter Einheit: Wolle nach Brügge 5,86 ÷ 2,143 = 2,73, Feinstoff nach Kraków 0,439 ÷ 0,441 = 1,00. Die
    Formel (Entfernung, `transport_cost` der Ware: Obst 2, Wolle und Urkorn 1) ist offen. Den Gewinn je Kapazität einer neuen
    Route rechnet der Ratgeber deshalb nicht vor.
  - Die Wolle-Route der Bestellung geht nach Brügge, das nicht unter den Märkten in Handelsreichweite des Mods
    (`in_trade_range_of`) steht. Bestellungen erreichen also mehr Märkte als diese Liste. (Stand 1.3; seit 1.4.7 sind
    Reichweite und Transportkosten gleich gerechnet – neu prüfen.)
- **Bestellung der Walachei (1338.4.7, Tarnowo, Obst Einfuhr, Wolle und Urkorn Ausfuhr, 100 %, Mindestgewinn 0,25) – belegte
  Gründe für fehlende Routen:**
  - Händlerkapazität in Tarnowo 6,30, genutzt 6,30: Wolle (Bestellung) 5,86, Feinstoff (Automatisierung) 0,44.
  - Obst: in keinem der 12 Monate eine Route. Tarnowo hat Angebot 7,41 ≥ Nachfrage 4,35, billiger sind Kaffa 0,89,
    Dubrovnik 0,90, Pest 0,91 (Tarnowo 1,39). Warum keine Route entsteht, zeigt nur das Spiel: Der Gewinn je Kapazität der
    besten Route ist für den Ratgeber nicht lesbar.
  - Urkorn: Route nach Konstantinopel 1337.7–1337.9 mit 0,32 → 0,31 Gewinn je Kapazität, im 1337.9 nichts gehandelt (genutzte
    Kapazität 0), seit 1337.10 keine. Tarnowo ist knapp (Nachfrage 14,46 > Angebot 13,06). Bulgarien erhebt 20 % Ausfuhrzoll
    auf Urkorn.
- **Weitere Defines:** `NCountry.TRADE_POLICY_TARIFF_LIGHT/MODERATE/HEAVY` 0,10/0,25/0,50 und `…_SUBSIDY_…` −0,10/−0,20/−0,35
  (Verwendung offen); `TRADE_POLICY_AUTO_*` (Automatisierung); `NMarket.TARIFF_PRICE_IMPACT = 0.25`;
  `NEconomy.ECONOMICAL_BASE_FROM_TARIFF = 0.2`.
- **Automatisierung der Handelsrichtlinien:** Spielstand `automated_trade_policy_strategy`, mit Merkantilismus-, Ausgewogener und
  Freihandelsstrategie (`TRADE_POLICY_STRATEGY_*`). 1337.8.1 stehen alle 2.370 Einträge auf Balanced.
- **Zollbefreiung** (`scripted_relations/tariff_exemption.txt`, Aktionen „Zollbefreiung anbieten/erbitten/widerrufen“):
  - Einseitig, endet bei Krieg, `is_exempt_from_import_tariff = yes`. Ob sie Ausfuhrzölle erlässt, ist ungeprüft; das
    Spielkonzept nennt Ein- und Ausfuhr.
  - Bereitschaft der KI, sie zu geben (`wants_to_give`): −75 + ihr Vertrauen in uns + ihre Meinung von uns (positive Meinung ÷ 5);
    Rivale −100, eigenes Klientelland 1.000. Ab welchem Wert sie zustimmt, steht nicht in der Datei.
    Erbeten werden kann sie nur von Ländern mit Märkten.
- **Meinung:** `diplomacy_manager/<A>/relations/<B>.export_tariff_opinion_penalty` steht bei Ausfuhrzöllen von A auf den Handel
  von B (Bulgarien → Walachei −2,29, Schweden → Norwegen −1,45). Laut Spielkonzept „verabscheuen“ Zielländer Ausfuhrzölle.
- **Spielstand `trade_manager/database`** (Routen aller Länder): `size` = GetAssignedMerchantCapacity, `cached` =
  GetActuallyUsedOrAssignedMerchantCapacity, `effect` = GetDesiredGoodsShipped (Route 16777442: 1,42133 / 0,43806 / 1,56826 zu
  Mod 1,421 / 0,438 / 1,568), `which` = Gut, `trade_owner`. `capacity` = 10 ist vermutlich die Markt-ID; `power` und `trade_path`
  sind ungeprüft.

## Gebäude, Einheiten, Bedarf (geprüft 25.10., Kachel Wirtschaftsplan)

- **Gebäudegewinn im Spielstand:** `building_manager/database/<id>.last_months_profit` = Gewinn des ganzen Gebäudes je Monat.
  ÷ `level` passt zum Mod-Wert `Building.GetProfitPerLevel` (Steinmetz Leiden 0,4228 / 2 = 0,211 gegen 0,206, Weinkelterei
  0,2818 / 2 = 0,141 gegen 0,141). `GetProfitPerLevel` ist also ein Durchschnitt (GetProfit ÷ GetLevel), kein Zuwachs der
  nächsten Stufe. **Gewinn 0 schreibt der Spielstand nicht:** Unter 18.855 Werten (1348.3) ist kein einziger 0, und Hollands
  Brauereien und Juwelierszünfte ohne Feld haben laut Mod GetProfit 0. Arten ganz ohne Feld sind Staatsgebäude mit Unterhalt.
  Gebäude ohne `level` sind im Bau (`establishment_progress` 0). Von 37.883 Gebäuden der Welt haben 44 Arten ein Gewinnfeld.
- **Einheiten:** Welche ein Land bauen kann, bestimmt `unlock_unit` der erforschten Fortschritte. Holland 1348:
  a_archers, a_footmen, a_horsemen, a_armored_horsemen, n_cog, n_traditional_galley.
  - `buildable` ist bei fast allen Zeitalter-Einheiten „no“, `hide = yes` steht auch bei freigeschalteten Einheiten – beides
    taugt nicht als Filter.
  - `age` heißt „ab diesem Zeitalter freigeschaltet“, nicht „gilt nur dann“.
  - Bedarf: `construction_demand`/`maintenance_demand` → goods_demand (`regiment_*`, `ship_*`).
  - Das laufende Zeitalter steht im Spielstand als `current_age` (1348: age_2_renaissance).
- **goods_demand-Kategorien** (355 Einträge):
  - special_demands 116, building_construction 109, ship_construction/-maintenance je 29, regiment_construction/
    -maintenance je 23, government_activities 12, pop_needs 9, building_maintenance 5.
  - Papier für Privilegien, Kabinett, Institutionen und Reformen (je 1), Stadtrechte (Glas, Mauerwerk, Nutzholz).
  - Kolonien: colony_construction, simple_colony_construction, colonial_charter_maintenance. Erkundung: create_land/
    sea_exploration, create_conquistador.
  - Bürokratie: bureaucracy_maintenance (Papier 2, Möbel 1, Bücher 1).
  - Stahl nur bei Eisenbahn, Feuerwaffen beim Bauen nur in korean_gunnery_construction.
- **Rohstoff-Ausbaukosten** sind nicht aus den Spieldateien nachzurechnen: prices `expand_rgo_farming` = 100 Gold, dazu
  Faktoren aus dem Preis des Rohstoffs und weitere; Den Haag kostet laut Spiel 168. Gold-Baukosten neuer Gebäude zeigt das
  Spiel nur im Baumenü.
- **Ortsart der Gebäude:** `rural_settlement`/`town`/`city`/`megalopolis` = yes erlaubt den Bau, ein fehlendes Flag verbietet
  ihn. Die Spielnamen sind Landsiedlung, Stadt, Großstadt, Megalopolis.
- **Gebäudekategorien** (`category`, Spielnamen in buildings_l_german):
  - village = Dörfer, estate = Standesgebäude, trade = Handelsgebäude, government = Regierungsgebäude,
    defense = Verteidigungsgebäude, military = Militärgebäude, naval = Seefahrtsgebäude.
  - Das Marktdorf zählt zu den Dörfern, der Ortsmarkt zu den Standesgebäuden – beide wirken über Händlermacht und Marktzugang.
- **Ortsflags der Mod** (a.ort): HasRiver, IsCoastal, HasPort, IsMarketCenter, IsCapital, location_population_percentage,
  rank_index, num_roads, GetFortLevel. Damit prüft der Bauplan `location_potential`.
- **Ablöseketten:** `obsolete` in building_types (castle löst stockade ab). In einem Ort mit dem Nachfolger wird der Vorgänger
  nicht empfohlen.
- **Fortschritt erreichbar:**
  - Eine `potential`, die genauso bei einem erforschten Fortschritt steht, gilt als erfüllt (Polder wie flämische Tuchmacherei).
  - Das Feld `government` muss zur Regierungsform passen (Holland: monarchy; steppe_horde: Kurultai, Karawanserei).
- **Straßen:**
  - Spielstand `road_network/roads` ist eine Liste {from, to, type}; der Ort trägt `road_to_capital = yes`.
  - Holland 1348: keine Straße, Den Haag (Hauptstadt) mit road_to_capital.
  - Schotterstraße: prices `build_gravel_road` = 10 Gold je Entfernungseinheit (`price_per_unit_distance`), Baugüter aus
    `construction_demand`.
- **Festungsgrenze:** Mod a.land GetFortLimit 2,16, used_fort_limit 1,0 (Holland 1348).
- **Unterhalt je Stufe:** Mod `GetUpkeepPerLevel` je eigenem Gebäude. Unterhaltsgüter × Marktpreis liegt rund 4,7× zu hoch
  (Burg 0,484 gegen 0,102, Kai 0,722 gegen 0,152, Faktor 0,21).
- **Modifikatorformat:** FormatManPower (Mannstärke, Garnison, Seeleute) und FormatPopCaps zählen in Tausend.

## Krieg (geprüft 25.10., Kriegskachel, 1. Englisch-Holländischer Krieg 1348–1351)

- **Spielstand `war_manager/database/<id>`** (dieselbe ID wie die Mod-Datenfunktion `War.GetID`):
  - `all` = Teilnehmer: `country`, `status` (Active, Left, Declined) und `all_history`. Darin `request` mit `side`
    (Attacker/Defender), `reason` (Instigator, Target, Overlord, Subject, Scripted, InternationalOrganization) und
    `called_ally`, außerdem `joined` mit `date`, `score` (Combat, Siege, JoiningWar) und `losses`.
  - Verluste: `losses = { <kategorie> = { Battle Attrition Capture } }` in Mann, je Teilnehmer und als
    `attacker_losses`/`defender_losses` je Seite. Ohne Verluste steht `losses = { }`.
  - Kriegsziel: der Block mit `casus_belli` (z. B. `take_province`, `independence`) mit `target_province` und
    `target_locations` (Zahl oder Liste).
  - `battle` = Liste der Schlachten: `location`, `date`, `war_attacker_win` (siegt die Angreiferseite des Kriegs) und
    `war_score`. **`war_score` gilt aus Sicht des Schlacht-Angreifers** (5 Schlachten geprüft: Mechelen +9,70, Holland
    greift an und siegt; Antwerpen −2,04, Aquitanien greift an und verliert).
  - Je Schlachtseite `losses`/`total`/`imprisoned` mit 10 Werten in Tausend Mann. Die Reihenfolge entspricht den Dateien in
    `unit_categories`: 00 leichte Infanterie … 14 Transport. `who` steht je beteiligtem Land einmal (size, levy,
    war_exhaustion …), dazu `character` (Heerführer).
  - `war.locations` hat Ganzzahl-Schlüssel. Besetzung erkennt man am Ort selbst: `controller` ≠ `owner`.
- **Je Land:**
  - `currency_data`: manpower, sailors, army_tradition. Im Land: max_manpower, monthly_manpower, max_sailors,
    expected_army_size/navy_size, `units`, `owned_subunits`, `researched_advances`.
  - Einheit (`unit_manager`): is_army, location, leader, activity.
  - Regiment/Schiff (`subunit_manager`): type, strength, morale, experience, fehlende Unterhaltsgüter. **strength 1,0 =
    1.000 Mann** (`REGIMENT_SIZE = 1000` in 00_defines).
  - Heerführer (`character_db`): mil, general_trait, traits.
- **Daten-Mod:**
  - `army_size` ist in Tausend Mann (England 24,06 bei 58 Regimentern), `navy_size` die Zahl der Schiffe (England 37 = 37
    Schiffe im Spielstand).
  - `unit_strength` und `strength_percentage` je Einheit sind **Anteile** (beide 0,083 bei 9 Regimentern mit 753 Mann).
  - Die Anzeige je Einheit liefert `Unit.GetVisualStrength`: Mann bzw. Schiffe, „821“, „12,345“, ab 100.000 „123K“
    (VALUE_LIMIT_SHOW_K).
  - `num_of_advances_researched` liefert als Wert immer 0 (Holland 0,000) – die Zahl der Fortschritte kommt aus dem
    Spielstand.
  - RG2 fremd führt für jedes Land, mit dem wir im Krieg sind, alle Landeswerte (Mannstärke, Seeleute, Regimenter …).
  - `GetWarScore` (RG2 krieg) gilt aus Sicht des Angreifers. Die Punkte-Aufschlüsselung `GetWarScoreBreakdown` ergibt ihn
    genau (1351.2: −23,00 tickend − 4,74 aus 16 Schlachten + 2,10 Besetzung = −25,64).
  - Der Trigger `war_score_in_war(root)` (RG1W score, gleich `war_score_in_war_whole_side`) ist eine andere Größe: 1350.12
    +44,63 = −GetWarScore, aber 1351.1 +21,04 gegen 43,52 und 1351.2 +3,16 gegen 25,64. Seine Bedeutung ist ungeklärt; im
    Kriegsfenster des Spiels vergleichen.
  - Die erste Zeile von `GetWarScoreBreakdown` lautet „Kriegsziel: Verteidiger kontrolliert „…““. Der Kriegsname des
    Spiels lautet „1.. Englisch-Holländischer Krieg“ (doppelter Punkt).
  - Die Namenslisten `War.GetAttackerNames` usw. schreibt die Mod nicht: Texte mit „Name“ im Funktionsnamen schließt
    `mod_alles.TEXT_SKIP` aus, Conquest und WhitePeace gelten als zustandsabhängig.
- **Bündnisstärken (Spiel-Trigger, Scope country):**
  - `defensive_alliance_strength` = das Land samt allen, die es verteidigen oder in Verteidigungskriege gerufen werden können.
  - `offensive_alliance_strength` = dasselbe für Angriffskriege.
  - `relative_defensive_alliance_strength(<Land>)` = Stärke samt Verteidigungsbündnis im Verhältnis zum anderen Land.
  - Holland 1351.1: Offensivbündnis 2,20, Verteidigungsbündnis 3,61; Utrecht verteidigt mit 2,41, Brabant mit 23,82.
- **1.4 (Beta 1.4.3, 27.10.):**
  - `complacency`, `add/set_complacency` und `monthly_complacency` sind entfernt.
  - Politischer Einfluss: Trigger `political_influence`, `monthly_political_influence` und `political_influence_percentage`;
    Effekte `add/set_political_influence`.
  - `Scope.GetTownRights` → `TownRightsType`.
  - `every_cardinal_in_country` liefert Charaktere; der Datentyp `Cardinal` ist entfernt.
  - `code_revisions.log` nennt auf der Beta den Zweig `release/next` statt einer Versionsnummer. Die Version steht im
    debug.log (wenn ein Mod nicht passt) und im Spielstand (`metadata version`).
- **1.4 (Beta 1.4.4, Test 0.23, 27.10.):**
  - **Logeinträge:** höchstens 1.024 Byte ab „<Datei>:<Zeile>: “. Das Spiel schreibt 1.023 Byte und dann NUL, auch in
    mehrzeiligen Texten. Unter 1.3 gingen ~5 KB durch. Ab Mod 0.24 kommen Zahlenzeilen in Stücken.
    - Test 0.24: `error_log` kürzt in error.log ebenso, `test_log` schreibt in keine Logdatei. Für lange Texte gibt es keinen
      anderen Weg.
    - `curmax_political_influence` = 100.
  - **Zoll je Handelsroute:** `Trade.GetTariffValue` ist negativ, wenn wir zahlen. `Trade.GetTariffInfo` liefert den Text,
    z. B. „Bulgarien verlangt einen 17% Zoll auf Ausfuhren von: Kupfer (0.32)“.
    - `GetProfit` enthält den Zoll offenbar schon. Walachei 1337.7: Verkauf − Einkauf − Unterhalt trifft den Gewinn bei
      Routen ohne Zoll auf ±7 %, bei Routen mit Zoll nur nach Abzug des Zolls (Gewinn 3,855: ohne Zoll 5,118, mit 4,103).
    - Neu ist `Trade.IsFromTradeOrder`.
    - Entfallen sind die manuellen Handelsfunktionen des Markts (`GetManualTradeCapacity`, `GetMaxAutomatedTradeCapacity` …).
  - **Politischer Einfluss als Preis:**
    - `prices` mit `political_influence`, z. B. Privileg gewähren 20, Politlinie 20, Höfling 10, Hauptsitz verlegen 50
      und Primärkultur 75.
    - Die Kopfleiste nutzt `Country.GetCurrencyTooltipDescription('political_influence')` und
      `GetMonthlyCurrencyChangeBreakdown('political_influence')` (topbar_tooltips.gui).
  - **Krankheiten im Spiel:**
    - Gesellschaft → Aufruhr (`TURMOILS_TAB`) → Krankheiten, zusammen mit Rebellen und Bewegungen.
    - Malaria: `mortality_rate` 0,1–0,5 statt 0,85–0,95, dazu neue Klimazonen (`subpolar` ohne, `hot/cold_semi_arid` mit
      verringerter Ansteckung).
  - **Kardinäle:** Laut Spielbegriff bekommt ein Land sie weiter über das Gebäude Kardinalssitz.
- **Werte aus Mod 0.20 (Test 25.10.):**
  - `relative_strength` und `relative_defensive_alliance_strength` liefern Werte zwischen 0 und 1. Für Holland gegen sich
    selbst (Zeile der Personalunion) ergibt `relative_strength` 0,499. Vermutlich ist es ein Anteil: sie / (sie + wir).
  - `has_truce_with`: 1 bei England nach dem Krieg.
  - `can_declare_no_cb_war_on`: 0 bei allen HRE-Nachbarn, 1 bei Ländern außerhalb des Reichs.
- **Mod-Texte mit Fehlern im Debug-Modus (Test 0.20, 25.10.):** Datenfunktionen werten im Log-Text ohne Oberflächen-Kontext
  aus. Fundstellen und Folgen:
  - `Policy.MeetsPotential`/`HasPotential` und die Politik-Texte `GetPotentialTriggerDesc`/`GetImplementableTooltip` prüfen
    `potential` ohne Land.
  - `Goods.GetNumSources` zählt die Hersteller und prüft dabei `country_potential` jedes herstellenden Gebäudes ohne Land:
    ein Fehler je hergestelltem Gut (Test 0.21: shoen 5, tatara 2). `GetRawMaterialMethodInfo` ist unschuldig.
  - `InternationalOrganization.GetAllMembersEffects` (HRE) wertet den `potential_trigger` des Mitglieder-Modifikators ohne Land
    aus (1 Fehler je Monat).
  - `CabinetAction.GetEffects…` prüft das `limit` in `on_activate` ohne Land.
  - Ohne Kontext und deshalb unvollständig: `Estate.GetExpensesInfo` (Gütersymbol fehlt), `Market.GetFoodExports/ImportsInfo`
    (Marktnamen fehlen), `Country.GetCurrentFortsAmountInfo` (Landesname fehlt).
  - `unlock_bergregal_rights_tt` ist im Spiel selbst fehlerhaft (`ShowTownRightsName('upper_bergregal')` bei einer Funktion
    ohne Argument).
  - Das error.log wird ab 1 MB in `error.1.log` … geteilt.
- **Krieg ohne Kriegsgrund ist möglich:** `cb_none` mit `declare_enabled = can_declare_no_cb_war_on` (casus_belli/
  00_hardcoded.txt). Was es kostet, steht dort nicht. `NO_CASUS_BELLI_CONQUEST_FACTOR` (0,8) steht bei den KI-Werten.
- **Spielstand je Land:** `great_power_rank` sowie `score.score_rating` und `score.score_rank` je ADM/DIP/MIL, also die
  Militärwertung des Spiels (England MIL 5,93, Rang 4).
  - Regimenter ohne `strength`-Feld: 53 von 1.446 am 1.1.1351, alles Bauernaufgebote mit `levies = { … }`. Ihre Stärke steht
    nicht im Spielstand.
- **Techlevel gibt es in EU5 nicht.** Vergleichbar sind die erforschten Fortschritte und die Einheiten, die sie über
  `unlock_unit` freischalten (je Kategorie die des spätesten Zeitalters).

## Wirtschaft (`NEconomy`)

- Wirtschaftsbasis – Gewichte (`ECONOMICAL_BASE_FROM_*`, Verrechnung nicht belegt): Steuerbasis 0,5, Pop 0,015,
  Handelswert 0,2, Handelsgewinn 0,2, fremde Gebäude 1,0, Untertan 0,05, je Institution ×0,066, Zins 0,25.
- `COURT_SPENDING_FRACTON = 0.1`, `DIPLOMATIC_SPENDING_FRACTION = 0.1`, `STABILITY_INVEST_FACTOR = 0.5`,
  `STABILIY_EXPENSE_FACTOR = 0.1` (Bezugsgröße nicht belegt; die Regler-Kosten liefert Mod 0.12 je Regler).
- Unrentable, nicht bezuschusste Gebäude entlassen 10 % der Arbeiter pro Monat, rentable stellen 10 % wieder ein.
- Produktionseffizienz +1 % je Gebäudestufe.
- **Gebäudegewinn vorhersagen (geprüft 02.10., verworfen):** Methode × Stufe × Marktpreis (Ausgabe − Eingänge) trifft den Gewinn
  des Spiels nicht (Maurer Den Haag 0,19 gegen 0,25, Gerberei 0,03 gegen 0,06–0,22, Glaserzunft −0,58 gegen 0,00): Zu-/Abschläge
  (Effizienz, Marktzugriff, Zufuhr) fehlen. Das Spiel liefert selbst: `Building.GetProfitPerLevel` (Ausbau-Ansicht „+x Reichtum“),
  `GetTaxBaseValuePerLevel`, `GetIncomeToOwnerPerLevel`, `Location.GetRGOProfitPerLevel` (Ort-Tooltip mit Symbol der
  Steuergrundlage – keine Einnahme der Krone, deshalb keine Amortisation in Monaten); für neue Gebäudetypen nur die globalen
  Funktionen `GetBuildingTypeProfitInLocation(BuildingType, Location)` (+ Potential/IncomeToOwner/…Info) mit Objekt-Argumenten –
  Baumodus-Objekte (`ConstructScoreRanking`) sind nur in der Oberfläche. Kein Skript-Trigger für den Gewinn eines Gebäudetyps.
- **Handelsreichweite:** Landes-Modifikator `trade_range` (Holland 300, `trade_range_modifier` +10 %); welche Märkte darin liegen,
  rechnet nur das Spiel (Trigger `in_trade_range_of`, Scope Markt, Ziel Land). Laut Spielbegriff kosten Routen innerhalb der
  Reichweite keinen Transportaufschlag, darüber steigt er mit der Entfernung. Patch 1.4.7 (03.11.2026, Patchnotes Economy):
  die Reichweitenprüfung nutzt jetzt dieselben Routenkosten wie die Transportkosten – ein als „in Reichweite“ gezeigter Markt
  zahlt nie einen Entfernungsaufschlag (vorher konnten beide auseinanderliegen). Die Mod-Liste kommt aus dem Trigger und folgt
  der neuen Regel ohne Änderung bei uns.
- Kredite 1–25 % Zins, 12–360 Monate, ab 10 Gold; Standeskredit = 50 % (mind. 2), 60 Monate; Anleihen ×2 (mind. 10).
- Kreditwürdigkeit: nähert sich monatlich um 10 % dem Ziel; +0,02 je pünktlich getilgtem Kredit, −0,03 je Verlängerung,
  −0,15 für Krieg gegen Gläubiger; Bankrott −0,5 (Erholung 0,005/Jahr).
- Bankrott: −50 Stabilität, Inflation −25 %, Kontrolle −33 %, 60 Monate; 25 % Chance je Untereinheit auf Verlust,
  10 % je Gebäude auf Rückbau.
- Inflation: Münzprägung 0,005, Rohstoff 0,01 (Deckel 0,5).
- Spielstand-Ausgaben (nachgerechnet 29.09., Holland 1341.7): `last_months_navy_maintenance`/`last_months_fort_maintenance`
  sind die Kosten ohne Regler (0,717 bzw. 0,585; Regler 50 % → Mod-Reglerkosten 0,357 bzw. 0,291); `economy.expense`
  (3,9996) = Summe der Reglerkosten laut Spiel (Heer, Flotte, Festungen, Hof, Diplomatie, Nahrung, Unterhalt …) + Seeleute
  (3,990, Rest 0,01 bei 6 Tagen Abstand). `last_months_building_maintenance` = Regler „Unterhalt“ (1,794 / 1,793).
- Spielstand-Einnahmen: `economy.income` (10,797) = Steuern (6,682) + Handel (2,439) + Münzprägung, Diplomatie, Nahrung
  laut Einkommens-Tooltip (1,53 + 0,10 + 0,03; Rest 0,02). Der Tooltip selbst summiert zu `GetIncomeValue` (9,997) und
  weicht bei Steuern/Handel vom Spielstand ab (6,58 / 1,72) – Bezugszeitpunkt nicht belegt.
- Handelseinkommen: laut `game_concept_trade_income_desc` nach Standesmacht zwischen Krone und Ständen geteilt, nur der
  Kronanteil geht in die Staatskasse. Die Oberfläche rechnet Gewinn × Modifikator `trade_income`
  (`market_tooltips.gui`: `Multiply(Merchant.GetTotalTradeProfit, GetModifier('trade_income'))`); `trade_income` =
  0,1 Grundwert (`auto_modifiers/country.txt`) + Kronmacht × 1,0 (`estates/00_default.txt`, crown_estate `power`).
  Nachgerechnet 29.09. (Holland 1341.7): 5,677 × (0,1 + 0,204) = 1,73 = Tooltip „Handelseinnahmen +1,72“; je Route
  ebenso (Lübeck 2,13 × 0,304 = 0,65 ≈ 0,64). Stand 1.4.7: Die `Multiply(…GetTotalTradeProfit…)`-Zeile steht nicht mehr in
  `market_tooltips.gui` (nur noch auskommentiert); die Oberfläche zeigt `Merchant.GetProjectedTradeProfit` und
  `Merchant.GetProjectedTradeIncome` (beide in data_types 1.4.6 vorhanden) – Formel unter 1.4 nicht neu belegt. Ungeklärt: Spielstand `monthly_trade_balance` 2,44 (+0,71) und
  `estate.last_month.trade_income` zusammen 8,21 (Adel 3,92 bei Macht 0,34 – mehr als 0,34 × 5,68).
- Spiel-Anzeige gegen Spielstand, gleicher Zeitpunkt 7. Juli 1341 (Screenshots des Nutzers, 29.09.): Wirtschaftsfenster
  Einnahmen 9,74, Ausgaben 3,98, Saldo +5,75, Handelseinnahmen +1,66 (Stoff 9,20 Einheiten +1,43, Obst +0,18),
  Steuern Adel 1,64 / Bürger 2,78 / Gemeine 1,97, Münzprägung 1,53, Nahrung 0,03, Diplomatie 0,10; Händler-Tooltip Brügge
  Gesamt-Handelsgewinn +5,67 (+1,62 Einnahmen). Spielstand zur selben Zeit: `economy.income` 10,797, Saldo 6,797,
  `monthly_trade_balance` 2,439, `last_months_tax_income` 6,682. `economy.income` = Mod `GetEstimatedMonthlyIncome`
  (10,798 am 1.7.); die Anzeige entspricht `GetIncomeValue` / Einkommens-Tooltip (9,997 am 1.7.). Ausgaben stimmen überein.
  Über 29 Monate liegt `monthly_trade_income` im Mittel 7–10 % über Gewinn × Modifikator, mal darüber, mal darunter
  (kein fester Aufschlag, kein Vormonatswert). Was genau `GetEstimatedMonthlyIncome` enthält, ist nicht belegt.
- Stände-Tooltip im Spiel = `estate.last_month` im Spielstand (Bürger 7.7.1341, Screenshot): Einnahmen nach Steuern 5,01,
  mangelnde Kontrolle 1,43 (`uncontrolled_income`), Handel 2,84 (`trade_income`), Nahrung 0,05 (`food_income`),
  Standesgebäude-Unterhalt −9,00 (`building_expense`), Zehnt −0,18 (`io_expense`), Ausgaben von Pops −4,04
  (`pop_expense`). Die Handelseinnahmen der Stände sind also echte Spielwerte; woraus sie entstehen, zeigt das Spiel
  nicht (0,27 Macht × 5,68 Gewinn der Routen wären 1,53, nicht 2,84).

## Orte (`NLocation`)

- **Gebäudeunterhalt (geprüft 01.10., Holland 1344.1.1):** Ortswert `location_net_building_profit` = −`GetTotalUpkeep`
  (`GetTotalIncome` 0) = Σ Spielstand-Feld `unterhalt` der Landesgebäude im Ort (Tempel, Marktplatz, Getreidespeicher, Kai,
  Burg): Den Haag 0,705 / Amsterdam 0,604 / Dordrecht 0,445. Kein Gewinn der Gebäude (Produktion: +3,82 zur selben Zeit).
  Reglerposten „Unterhalt“ (`upkeep`) zeigt 1,63 (Marktplatz 0,74 + Getreidespeicher 0,40 + Kai 0,31 + Tempel 0,18), die
  Burg (0,10) fehlt in dieser Liste – Rest der Differenz 1,75 − 1,63 nicht weiter geprüft.
- **Steuergrundlage:** Spielstand `steuer` / `moegliche_steuer` = live `GetTotalTaxBase` / `GetTotalPossibleTaxBase`
  (Land: „Steuergrundlage: 16.61“). Steuergrundlage ≈ möglich × Kontrolle (Hoorn 5,41 × 46,6 % = 2,52, Spiel 2,49 – nicht exakt).
- **Max. Kontrolle:** Aufschlüsselung `GetMaxControlInfo` (Kern +20 %, Ortsrang „Stadt“ +5 %, Hauptsitz +20 %, Nähe zu
  Hauptsitz, Ø Zufriedenheit, Adelshof −2,5 %). „Nähe zu Hauptsitz“ = 0,75 × Nähe bei allen 8 Orten (Hoorn 45,14 → +33,85 %).
  Alle 8 Orte stehen am Deckel (Kontrolle = max. Kontrolle) – mehr Steuergrundlage nur über höhere max. Kontrolle.
- **Nähe:** `GetProximityInfo` zeigt den Weg von der nächsten Nähequelle; Ein-/Ausschiffung in eine Seezone ohne
  Marinepräsenz kostet je +30 („Nähekosten ohne Marinepräsenz“, Grundwert je Land), z. B. Den Haag → Küste von Holland → Hoorn.
- **Wanderung:** `migration_attraction` = Spieltext `GetLocalMigrationAttraction` (Den Haag +0,25), Aufschlüsselung
  `GetLocalMigrationAttractionInfo`; `GetMigrationChange` = Wanderung letzter Monat („+6“, Einzelzeilen in `GetMigrationInfo`:
  „1 Adlige migrierten aus …“).
- **Fluss:** `HasRiverSize1`–`5` schließen sich aus (Dordrecht nur Größe 3, Geertruidenberg nur Größe 1).
- Kontrolle verfällt 0,01/Monat (`MONTHLY_CONTROL_DECAY`); Wohlstand −1 … +1.
- Eroberte, nicht integrierte Orte: −0,1 Integration/Monat, bei Rebellion −10.
- Subsistenzlandwirtschaft 0,8.

## Forschung und Institutionen (`NCountry`)

- `BASE_RESEARCH_COST = 25`, `BASE_UNIQUE_RESEARCH_COST = 5`, `AGE_RESEARCH_MODIFIER = 0.15` („multiplied per age“),
  `PREVIOUS_AGE_REDUCTION = -8`.
- **Regel (belegt):** Kosten = Grundwert × (1 + 0,15 × Index des Zeitalters), der Zuschlag wird **addiert**, nicht vervielfacht.
  Grundwert 25, für Fortschritte nur eines Landes 5. Gilt schon vor dem Zeitalter (Tooltip im 1. Zeitalter).
- **Belege** (Selbstprüfung `techbaum.kostenbelege`, 31.10.: 11 von 11 gleich):
  - Aufschlüsselungen des Daten-Mods: laufendes Zeitalter 1: 25; laufendes Zeitalter 2: 25 × 1,15 = 28,75 („Fortschritt aus dem
    Zeitalter der Renaissance: +15.00%“); vorheriges Zeitalter im Zeitalter 2: 25 − 8 = 17 („Vorheriges Zeitalter: -8.00“).
  - Tooltips des Forschungsfensters („Zu Forschungsreihe hinzufügen – x Forschungsfortschritt“, Walachei im 1. Zeitalter,
    Screenshots 31.10.): „Operation“ (Entdeckungen, Zeitalter 3) **32,50** = 25 × 1,30 (vervielfacht wären 33,06);
    „Gründung der Kanzlei“ (Renaissance, nur Walachei) **5,75** = 5 × 1,15. Als `TOOLTIP_BELEGE` in techbaum.py.
- **Offen:**
  - Feld `research_cost` (Spieltext „Zusatzkosten für …: x %“; Werte −0,75 … 2,5) – Tooltip „Stoffmanufaktur“
    (`cloth_manufactory_advance`, −0,5) fehlt noch.
  - Ältere Zeitalter außer „vorheriges im Zeitalter 2“; einzigartige älterer Zeitalter.
- Nur die laufende Forschung ist für Skripte erreichbar (`CurrentResearch.GetAdvance` → `Advance.GetResearchCost`). Andere
  `Advance`-Objekte gibt es nur in der Oberfläche; `Scope.AdvanceType` liefert die Definition ohne Kosten.

## Ländergründung (geprüft 30.10.)

- **Grad des Landes = Trigger `formable_level`** („gründbarer Grad“), nicht die Stufe des Rangs. Der Daten-Mod schreibt ihn seit
  0.12 (land, fremd).
  - Walachei 0 bei Rang Herzogtum, Bulgarien 1 bei Großreich, Ungarn 3, England 2, Kastilien 2.
  - Bei 14 von 16 Ländern ist er die Stufe der Gründung mit dem eigenen Kürzel, sonst 0. Ashikaga und Yuan haben 4 bei
    Gründung 3; das setzt das Spielprogramm, in keiner Spieldatei.
- Eine Gründung muss einen höheren Grad haben (readme: „Players can only form countries of higher level“).
- **Keine Gründungskosten:** `FormableCountry` hat nur Anforderungen, Wirkungen und mögliche Fortschritte. Der Knopf `FORM_COUNTRY`
  nennt keinen Preis; `formable_countries` hat kein Kostenfeld.
- Skript-Abfragen des Spiels: `is_formable_visible` (Land → Gründung), `location_progress_for_formable`, `is_required_for_formable`
  (Ort). Ab Mod 0.25 ausgelesen.
- **Test 0.25 (31.10., Walachei 1338.4–1339.11):** `location_progress_for_formable` ist der **Anteil an den nötigen Orten** (0–1):
  0,687 = 44 von 64, genau wie der Eintrag „Gründen Rumänien – 44/64“ im Reiter „Gründbare“. Nötig = aufgerundet
  `required_locations_fraction` × besitzbare Orte der Gebiete (0,5 × 127 = 63,5 → 64); Ratgeber 44 von 64 bei 127 – gleich.
  - Untertanen: offen (Walachei und Holland 1352 haben keine; das 1479-Spiel hätte einen mit 7 Orten im Rumänien-Gebiet).
    Die Kachel zeigt gleich/≠ automatisch, sobald ein Spiel mit Untertan im Gebiet läuft.
  - `FormableCountry.GetRequirements`/`GetEffects` im Scope der Gründung brauchen ein Land: nur die Überschrift bzw. leer, je
    Monat Fehler „Scoped object of type 'country' is not valid“ an `allow` und `form_effect`. `GetLocationRequirementsTooltip`
    liefert nur den festen Text („Benötigt 50% der Orte in die Gebiete …“). Seit Mod 0.25.1 gestrichen.
  - Der Spielstand speichert keinen Gründungsfortschritt (nur Liste `formable_countries`).
- Institutionen: mindestens 20 % Verbreitung; Verbreitung über Handel mit Halbwertskosten 50, ab Marktdurchsatz 10.
- Kabinettsaktion: +0,5 % je Fähigkeitspunkt (`CABINET_ACTION_SKILL_MODIFIER = 0.005`).

## Startstrategie: Kabinett, Politlinien, Privilegien, Bündnisse (geprüft 31.10., Kachel Startstrategie)

- **Kabinett** – Gesamtsteigerung (Daten-Mod Walachei 1339.11, Texte `GetEffectiveSkillTooltip` und
  `GetEffectiveSkillImpactInfo`): „54 durch Regentin …: +27.00% · Herrscherrecht: +5.00% · Kronmacht: +7.89% · 72 durch Serban
  Caradja: +36.00%“ = 75,89 % = `GetEffectiveSkill` 0,7589. Minister und Herrscher/Regentin zählen je Fähigkeit × 0,005
  (`CABINET_ACTION_SKILL_MODIFIER`), jeweils in der Fähigkeit der Aktion (`ability`).
  - Wirkung = Grundwert × (1 + Gesamtsteigerung): `increase_control_province` `local_max_control = 0.1` → „Kontrollmaximum:
    +17.58%“, `local_monthly_control = 0.01` → „+1.75%“ (abgeschnitten).
  - Die readme der Kabinettsaktionen nennt „*0.05“ – das Define 0,005 passt zum Tooltip, nicht die readme.
  - Kosten (`prices/00_hardcoded.txt`): Aktion zuweisen `set_cabine_action` leer („#free“), Minister ersetzen
    `replace_cabinet_member` 20 Politischer Einfluss.
- **Politlinien** (`laws/readme.txt`): ein Gesetz enthält mehrere Politlinien, eine gilt; `years` = Zeit bis zur vollen Wirkung
  („Modifiers will be scaled by how much of this time is completed“); `INJECT:<gesetz>` fügt Politlinien hinzu. Preise:
  `set_policy` „Politlinie festlegen“ 20 Politischer Einfluss, `change_policy` „Politlinie annehmen“ Stabilität 100 und
  Rechtschaffenheit 10 – welcher beim Wechsel gilt, steht nicht in den Dateien. `estate_preferences`: Wirkung nicht beschrieben.
- **Freischaltung:** `unlock_cabinet_action`, `unlock_policy`, `unlock_law`, `unlock_estate_privilege`,
  `unlock_government_reform` stehen nur in `advances` (14/24/44/18/23 Einträge in 1.4.6); Bedingungen fragen sie mit
  `has_unlocked_<art>_trigger = { type = … }` ab. Was kein Fortschritt freischaltet, kommt aus Ereignissen oder Effekten.
- **Privilegien:** gewähren `grant_privilege` 20 Politischer Einfluss, entziehen `revoke_privilege` Stabilität 400 und
  Rechtschaffenheit 10. Zielzufriedenheit-Stufen (`script_values`): tiny 0,01, small 0,025, medium 0,05, large 0,1. Live-Werte je
  Privileg (`GetPower`, `GetSatisfaction`) = `global_<stand>_power` bzw. `<stand>_target_satisfaction` der Spieldatei
  (Alphabetisierungsrechte: 0,25 / 0,05).
- **Reformen:** Gesellschaftswert-Bedingung (`societal_values = { humanist_focus }`) mit `SOCIAL_VALUE_REQUIREMENT_FOR_REFORM =
  50`; Spielhinweis „Die Reform … wird in … Monaten entfernt werden, weil unser Gesellschaftswert … unter … gefallen ist“.
  `INJECT:<reform>` ergänzt Modifikatoren mit eigener Bedingung (DLC). Entfernen `remove_government_reform` Stabilität 20.
- **Bündnis** (`scripted_relations/alliance.txt`): `disallow_war = yes`, `called_in_defensively/offensively = mutual`,
  `diplomatic_capacity_cost = alliance_upkeep_cost`. Bedingung `alliance_can_exist` (`scripted_triggers`): Meinung beider Seiten
  voneinander ≥ 0, keine Rivalität, kein Klientelland des anderen, keine gesperrten Verträge, `modifier:allowed_alliance`, keine
  Personalunion, keine Koalition gegeneinander, keine Aufständischen, `can_create_subject_alliance`, nicht beide Hegemon.
  - Unterhalt `alliance_upkeep_cost` (`script_values`): 0,5 + (Wirtschaftsgrundlage des anderen ÷ eigene, mind. 1) × 2
    (begrenzt 0,1–3) + (0,5 − Meinung des anderen von uns ÷ 200) + max(0, (powerful_ally_weight − 1) × 0,3) + 1 Großmacht bzw.
    0,5 Regionalmacht.
  - Annahme durch die KI: Faktoren in `scripted_relations/alliance.txt` `wants_to_give_diplo_chance` (Grundwert −40,
    Anfragender ist Rivale −100, Vertrauen 1, positive Meinung 0,3, negative Meinung −1, Grenzabstand −0,05, Hofsprache 15,
    Stärkeverhältnis 25, bedrohliche Rivalen 20 …) und weitere Posten in `wants_to_give`/`wants_to_keep` (Prüfer 31.10.; vorher
    stand hier fälschlich „nur in der Oberfläche“). `ai_diplochance` hat keinen Eintrag für Bündnisse. `block_when_at_war = yes`:
    im Krieg nicht nutzbar. `royal_marriage` (ai_diplochance) nennt nur Faktoren (Meinung 0,1, Erbe 10, andere Religionsgruppe
    −200 …), keine Schwelle und keinen Grundwert.
- **Rivalen** (Lokalisierung `RIVALS_*`, Spielbegriff Rivale, `NDiplomacy`): unsere Meinung von ihnen unter
  `RIVAL_OPINION_THRESHOLD = 100`, Diplomatiereichweite, ähnlicher Großmachtwert; Rivalen nehmen keine freundschaftlichen
  Verträge an. Ersetzen `replace_rival` 20 Politischer Einfluss, entfernen frühestens nach `REMOVE_RIVAL_COOLDOWN = 60` Monaten.
  `rival_criteria`: Rom nur bei anderer Religion oder Exkommunikation wählbar, sonst KI-Regeln (Kastilien, Portugal …).

## Diplomatie und Untertanen

- Annexion: Grundkosten 200 + 10 je Ort (`ANNEX_BASE_COST`, `ANNEX_COST_PER_LOCATION`).
- Lehnsgut/Vasall zahlt `subject_pays_vassal = { scaled_gold = 0.2 }` (`in_game/common/prices/03_diplomacy.txt`).

## Gesellschaftswerte

- −100 … +100, Trägheit 100; Reformen verlangen 50 (`SOCIAL_VALUE_REQUIREMENT_FOR_REFORM`).
- Bewegungen kommen aus Modifikatoren `monthly_towards_<wert>` (z. B. Privilegien: Aristokratie +0,1/Monat).
