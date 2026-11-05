"use strict";
// EU5 Ratgeber – gemeinsame Gestaltung der Kacheln: einheitlicher Kopf (Hauptwerte mit Trend und Mini-Verlauf,
// kleine Werte, Warnungen), Themen (Symbol, Farbe, Gruppe), Aufschlüsselungen als aufklappbare Liste,
// deutsche Bezeichnungen für Code-Namen der Live-Werte. Nutzt esc/fmt/sgn/pct aus app.js.

// ---------------------------------------------------------------- Themen und Anordnung
// Bereich „Handel“ mit Handel, Heimatmarkt und den anderen Märkten unter „Wirtschaft“ (Nutzerwunsch 29.09.);
// „Land und Leute“ heißt „Staat und Regierung“ und steht vor Wirtschaft; „Staat und Außenpolitik“ wird „Diplomatie und Militär“
// mit Diplomatie und Militär direkt darunter (Nutzerwunsch 30.09.)
// „Ratgeber“ mit den Empfehlungen ganz oben; „Fremde Märkte in Reichweite“ (zuschaltbar) unter Handel (Nutzerwunsch 02.10.)
const GROUPS = [["ratgeber", "Ratgeber"], ["leute", "Staat und Regierung"], ["staat", "Diplomatie und Militär"], ["wirtschaft", "Wirtschaft"],
                ["handel", "Handel"], ["fremdmaerkte", "Fremde Märkte in Reichweite"], ["einzelorte", "Einzelne Orte"], ["auswertung", "Auswertung"]];
const THEME = {
  empfehlungen: { icon: "🧭", color: "--c3", group: "ratgeber" },
  wirtschaftsplan: { icon: "🏗️", color: "--c2", group: "ratgeber" },
  startstrategie: { icon: "🎯", color: "--c4", group: "ratgeber" },   // nach dem Wirtschaftsplan (31.10., startstrategie.js)
  finanzen: { icon: "💰", color: "--c7", group: "wirtschaft" }, handel: { icon: "🚢", color: "--c2", group: "handel" },
  markt: { icon: "🏪", color: "--c6", group: "handel" }, produktion: { icon: "🏭", color: "--c1", group: "wirtschaft" },
  gueter: { icon: "📦", color: "--c4", group: "wirtschaft" },
  land: { icon: "🗺️", color: "--c3", group: "leute" }, forschung: { icon: "🔬", color: "--c4", group: "leute" },
  orte: { icon: "📍", color: "--c5", group: "leute" }, staende: { icon: "🏛️", color: "--c1", group: "leute" },
  religion: { icon: "⛪", color: "--c7", group: "leute" },
  // Regierung im Bereich „Staat und Regierung“, Diplomatie mit Militär im Bereich „Diplomatie und Militär“ (Nutzerwunsch 30.09.)
  regierung: { icon: "👑", color: "--c7", group: "leute" }, diplomatie: { icon: "🤝", color: "--c6", group: "staat" },
  krankheiten: { icon: "🦠", color: "--c5", group: "leute" },   // zwischen Regierung und Forschung (04.10.)
  mehr: { icon: "⚔️", color: "--c5", group: "staat" },
  nachbarn: { icon: "🗺️", color: "--c6", group: "staat" },   // Nachbarn und Kriegsgelegenheiten (25.10.)
  verlauf: { icon: "📈", color: "--c2", group: "auswertung" }, entscheidungen: { icon: "📝", color: "--c8", group: "auswertung" },
  modifikatoren: { icon: "🧮", color: "--c8", group: "auswertung" },
};

// ---------------------------------------------------------------- Kopf
const num = v => typeof v === "number" && !Number.isNaN(v);
// Mini-Verlauf (Zahlenreihe) als kleine Linie
function spark(vals, { w = 90, h = 26, color = "--accent" } = {}) {
  const v = (vals || []).filter(x => typeof x === "number");
  if (v.length < 2) return "";
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const pts = v.map((x, i) => `${(i / (v.length - 1) * (w - 2) + 1).toFixed(1)},${(h - 2 - (x - lo) / span * (h - 4)).toFixed(1)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><polyline points="${pts}" fill="none" stroke="var(${color})" stroke-width="1.6"/></svg>`;
}
// Reihe aus den monatlichen Live-Werten (d.live), letzte n Monate
const liveSeries = (d, key, n = 24) => (d.live || []).map(r => r[key]).filter(x => typeof x === "number").slice(-n);
// Werte wie im Wirtschaftsfenster des Spiels (Daten-Mod, Stand Monatserster; Nutzerwunsch 29.09.):
// Einnahmen = GetIncomeValue, Saldo = monthly_balance (= Einnahmen − Reglerkosten, geprüft 29 Monate), Ausgaben = Differenz,
// Handelseinnahmen = Gewinn der Routen × Modifikator trade_income (Oberfläche: market_tooltips.gui). Ohne Mod-Daten: null.
function spielWerte(d) {
  const L = (d.live || []).filter(r => typeof r.einkommen_spiel === "number" && typeof r.saldo_spiel === "number");
  if (!L.length) return null;
  const r = L.at(-1), n = 24, sl = L.slice(-n);
  const hRows = (d.live || []).filter(x => typeof x.handel_gewinn === "number" && typeof x.handel_mod === "number").slice(-n);
  const hLast = (d.live || []).filter(x => typeof x.handel_gewinn === "number").at(-1);
  const mod = (d.live || []).filter(x => typeof x.handel_mod === "number").at(-1)?.handel_mod;
  // Modifikator liegt nicht in jedem Monat vor: Trend nur, wenn die letzten zwei Werte aufeinanderfolgende Monate sind
  const mIdx = x => { const [j, m] = String(x.datum).split(".").map(Number); return j * 12 + m; };
  const hVorm = hRows.length > 1 && mIdx(hRows.at(-1)) - mIdx(hRows.at(-2)) === 1
    ? hRows.at(-1).handel_gewinn * hRows.at(-1).handel_mod - hRows.at(-2).handel_gewinn * hRows.at(-2).handel_mod : null;
  return {
    datum: r.datum, ein: r.einkommen_spiel, saldo: r.saldo_spiel, aus: r.einkommen_spiel - r.saldo_spiel,
    handel: hLast && typeof mod === "number" ? hLast.handel_gewinn * mod : null, handelVorm: hVorm,
    ser: { ein: sl.map(x => x.einkommen_spiel), saldo: sl.map(x => x.saldo_spiel), aus: sl.map(x => x.einkommen_spiel - x.saldo_spiel),
           handel: hRows.map(x => x.handel_gewinn * x.handel_mod) },
  };
}
const vorm = s => s && s.length > 1 ? s.at(-1) - s.at(-2) : null;      // Veränderung zum Vormonat einer Reihe
// Trend-Pfeil: Veränderung gegenüber dem Vormonat; good = +1 (mehr ist besser), -1 (weniger ist besser), 0 (neutral)
function trend(delta, d = 1, good = 1) {
  if (typeof delta !== "number" || Math.abs(delta) < 0.5 * 10 ** -d) return "";     // gerundet 0 -> kein Pfeil
  const cls = good === 0 ? "" : delta * good > 0 ? "pos" : "neg";
  return `<i class="tr ${cls}">${delta > 0 ? "▲" : "▼"} ${sgn(delta, d)}</i>`;
}
// Kopf: big/small = [{l, v, t (Trend-HTML), s (Spark-HTML), cls, title}], warn = [Text …]
// "<!--klein-->" markiert das Ende der kleinen Werte: live.js hängt dort weitere Kopfwerte an.
// cols = feste Spaltenzahl für die kleinen Werte (gleiche Stelle in jeder Kachel, z. B. Ortskacheln);
// bar = Anteil 0..1 -> kleiner Balken unter dem Wert; u = kleiner Zusatz unter dem Wert (HTML, z. B. „Spielstand 6,80“)
// stack = [Wert, Wert …] -> Werte untereinander in einer Spalte (bleiben auch in der aufgeklappten, breiten Kachel untereinander);
// klein = in der großen Reihe trotzdem kleine Schrift; neben = Spalte steht zugeklappt am Ende der Reihe, aufgeklappt direkt
// neben der vorigen Spalte (CSS .hd-big > .neben); mw = Höchstbreite in px (lange Listen brechen in der Spalte um, statt die
// Spalte in eine neue Zeile zu schieben – aufgeklappt bleibt der Kopf so in einer Reihe)
function hd({ big = [], small = [], warn = [], cols = 0 } = {}) {
  const bar = x => num(x.bar) ? `<span class="mbar"><i style="width:${Math.max(0, Math.min(1, x.bar)) * 100}%"></i></span>` : "";
  const one = (x, isBig) => x.umbruch ? `<span class="hdbr"></span>`           // { umbruch: true } = neue Zeile im Kopf
    : x.stack ?`<span class="hkstack${x.neben ? " neben" : ""}">${x.stack.filter(Boolean).map(y => one(y, isBig && !x.klein)).join("")}</span>`
    : `<span class="hk${isBig ? " big" : ""}"${x.title ? ` title="${esc(x.title)}"` : ""}${x.mw ? ` style="max-width:${x.mw}px"` : ""}><small>${esc(x.l)}</small>
    <b class="${x.cls || ""}">${x.v}${x.t || ""}</b>${x.u ? `<span class="hku">${x.u}</span>` : ""}${bar(x)}${x.s || ""}</span>`;
  return `<div class="hd"><div class="hd-big">${big.filter(Boolean).map(x => one(x, true)).join("")}</div>
    <div class="hd-small${cols ? " hd-grid" : ""}"${cols ? ` style="--cols:${cols}"` : ""}>${small.filter(Boolean).map(x => one(x, false)).join("")}<!--klein--></div>
    ${warn.filter(Boolean).length ? `<div class="hd-warn">${warn.filter(Boolean).map(w => `<span class="warn">⚠ ${w}</span>`).join("")}</div>` : ""}</div>`;
}
// Geschlossene Kacheln gleich hoch: höchste geschlossene Kachel messen, als --tileh setzen (CSS: min-height)
function equalizeTiles() {
  const root = document.documentElement;
  root.style.setProperty("--tileh", "0px");
  const closed = [...document.querySelectorAll("details.sec:not([open])")];
  const h = Math.max(0, ...closed.map(el => el.offsetHeight));
  root.style.setProperty("--tileh", h + "px");
}
let _eqT = null;
window.addEventListener("resize", () => { clearTimeout(_eqT); _eqT = setTimeout(equalizeTiles, 150); });

// Abschnitt im aufgeklappten Inhalt
const sect = (title, html, sub = "") => html ? `<section class="ab"><h4>${esc(title)}${sub ? ` <span class="hint">${sub}</span>` : ""}</h4>${html}</section>` : "";

// ---------------------------------------------------------------- Aufschlüsselungen
// Dekodierter Oberflächentext (Zeilen, Unterpunkte mit 2 Leerzeichen eingerückt) -> Liste: Bezeichnung links, Wert
// rechts; Unterpunkte klappen unter der Zeile auf, an der sie hängen.
function breakdown(text) {
  // Platzhalter des Spiels ohne Inhalt („Sprachmacht: :BREAKDOWN_TAG 7.41%“, Regler Unterhalt) entfernen
  const lines = String(text || "").replace(/[\x00-\x08\x0b-\x1f]/g, "").replace(/:BREAKDOWN_TAG\s*/g, "").split("\n").filter(l => l.trim())
    .map(l => { const m = l.match(/^( *)(.*)$/); return { depth: Math.floor(m[1].length / 2), text: m[2] }; });
  if (!lines.length) return `<div class="empty">kein Text</div>`;
  const row = t => {
    // "Name: +1.23", "Name: 45%", "Name: x0.90", "Name: 0.00/2.16", "Den Haag: +7.12 (0.00)"
    const m = t.match(/^(.*?):\s*((?:[-+−]?|x)[\d.,]+\s*%?(?:\s*\/\s*[\d.,]+\s*%?)?(?:\s*\([^)]*\))?)\s*$/);
    return m ? `<span class="bl">${esc(m[1])}</span><span class="bv ${/^[-−]/.test(m[2]) ? "neg" : /^\+/.test(m[2]) ? "pos" : ""}">${esc(m[2])}</span>`
             : `<span class="bl bt">${esc(t)}</span><span></span>`;
  };
  // Baum: jede Zeile nimmt die folgenden tieferen Zeilen als Kinder
  const build = (i, depth) => {
    const out = [];
    while (i < lines.length && lines[i].depth >= depth) {
      if (lines[i].depth > depth) { const [kids, j] = build(i, lines[i].depth); out.push({ kids }); i = j; continue; }
      const node = { text: lines[i].text, kids: [] }; i++;
      if (i < lines.length && lines[i].depth > depth) { const [kids, j] = build(i, lines[i].depth); node.kids = kids; i = j; }
      out.push(node);
    }
    return [out, i];
  };
  const render = nodes => nodes.map(n => n.text === undefined ? render(n.kids)
    : n.kids.length ? `<details class="bk"><summary>${row(n.text)}</summary><div class="bsub">${render(n.kids)}</div></details>`
                    : `<div class="bk">${row(n.text)}</div>`).join("");
  return `<div class="brk">${render(build(0, 0)[0])}</div>`;
}

// ---------------------------------------------------------------- deutsche Bezeichnungen
// Feste Bezeichnungen für häufige Werte; sonst Wortbausteine (GLOSSAR) - der Code-Name steht klein daneben.
const LABELS = {
  total_population: "Bevölkerung gesamt", monthly_population_change: "Bevölkerung – Veränderung / Monat",
  GetLastMonthsPopulationChange: "Bevölkerung – Veränderung letzter Monat", average_country_literacy: "Ø Bildung",
  GetAverageLiteracy: "Ø Bildung", cultural_unity: "Kulturelle Einheit", religious_unity: "Glaubenseinigkeit",
  total_primary_culture_population: "Bevölkerung Hauptkultur", total_accepted_culture_population: "Bevölkerung akzeptierte Kulturen",
  total_tolerated_culture_population: "Bevölkerung tolerierte Kulturen", total_not_tolerated_culture_population: "Bevölkerung nicht tolerierte Kulturen",
  total_true_faith_population: "Bevölkerung Staatsreligion", total_heretic_population: "Bevölkerung Ketzer", total_heathen_population: "Bevölkerung Heiden",
  heretic_population_fraction: "Anteil Ketzer", heathen_population_fraction: "Anteil Heiden",
  used_cultures_capacity: "Kulturkapazität genutzt", GetCulturalCapacity: "Kulturkapazität", GetTotalCultureCapacityUsed: "Kulturkapazität genutzt",
  gold: "Gold", stability: "Stabilität", prestige: "Prestige", inflation: "Inflation", legitimacy: "Legitimität",
  government_power: "Regierungsmacht", war_exhaustion: "Kriegsmüdigkeit", manpower: "Manpower", max_manpower: "Manpower max.",
  sailors: "Seeleute", max_sailors: "Seeleute max.", monthly_manpower: "Manpower / Monat", monthly_sailors: "Seeleute / Monat",
  monthly_balance: "Saldo / Monat", monthly_income_total: "Einkommen / Monat", monthly_trade_income: "Handelseinkommen / Monat",
  monthly_income_trade_and_tax: "Einkommen Handel + Steuer / Monat", yearly_gold: "Gold / Jahr", country_tax_base: "Steuerbasis",
  country_economical_base: "Wirtschaftsbasis", creditworthiness: "Kreditwürdigkeit", total_debt: "Schulden gesamt",
  country_loan_capacity: "Kreditrahmen", bond_capacity: "Anleihenrahmen", capital_wealth: "Vermögen der Hauptstadt",
  army_maintenance: "Regler Heer", navy_maintenance: "Regler Flotte", fort_maintenance: "Regler Festungen", court_maintenance: "Regler Hof",
  cultural_maintenance: "Regler Kultur", diplomatic_maintenance: "Regler Diplomatie", colonial_maintenance: "Regler Kolonien",
  exploration_maintenance: "Regler Erkundung", food_maintenance: "Regler Nahrung", upkeep_maintenance: "Regler Unterhalt",
  army_size: "Heer", navy_size: "Flotte", regular_army_size: "stehendes Heer", expected_army_size: "Heer erwartet",
  potential_army_size: "Heer möglich", military_strength: "Militärstärke", country_strength: "Landesstärke",
  great_power_score: "Großmacht-Punkte", great_power_ranking: "Großmacht-Rang", power_projection: "Machtprojektion",
  average_control: "Ø Kontrolle", average_control_in_home_region: "Ø Kontrolle Kernregion", total_development: "Entwicklung gesamt",
  num_locations: "Orte", num_provinces: "Provinzen", num_subjects: "Untertanen", num_rivals: "Rivalen", num_loans: "Kredite",
  num_privileges: "Privilegien", num_possible_privileges: "Privilegien möglich", num_reforms: "Reformen", num_open_reform_slots: "freie Reformplätze",
  average_estate_satisfaction: "Ø Zufriedenheit der Stände", research_progress: "Forschungsfortschritt",
  num_embraced_institutions: "Institutionen angenommen", num_known_institutions: "Institutionen bekannt",
  population: "Bevölkerung", location_max_population: "Bevölkerungskapazität", migration_attraction: "Wanderungsanziehung",
  monthly_conversion: "Bekehrung / Monat", employment_percentage: "Beschäftigung", food_production: "Nahrung Produktion",
  food_consumption: "Nahrung Verbrauch", average_satisfaction: "Ø Zufriedenheit", development: "Entwicklung", prosperity: "Wohlstand",
  control: "Kontrolle", local_control: "Kontrolle", max_control: "Kontrolle max.", market_access: "Marktzugriff", proximity: "Nähe",
  GetPopGrowth: "Bevölkerungswachstum", GetCapacityPercentage: "Kapazität genutzt (%)", IsOverPopulationCapacity: "überbevölkert",
  pop_size: "Größe", pop_satisfaction: "Zufriedenheit", pop_literacy: "Bildung", power: "Macht", satisfaction: "Zufriedenheit",
  target_satisfaction: "Zielzufriedenheit", estate_tax_rate: "Steuersatz", estate_gold: "Gold des Standes",
  trade_profit: "Gewinn", trade_volume: "Menge", trade_buy: "Einkauf", trade_sell: "Verkauf",
  GetActiveEmploymentSystemInfo: "Beschäftigungssystem", GetStarvingProvinces: "Hungernde Provinzen",
  GetTotalPopulation: "Bevölkerung gesamt", GetTotalPopulationNoLink: "Bevölkerung gesamt", GetLastMonthsPopulationText: "Bevölkerung letzter Monat",
  GetHistoricalMaxPopulation: "Bevölkerung historisch max.", GetHistoricalMinPopulation: "Bevölkerung historisch min.",
};
const GLOSSAR = {
  average: "Ø", avg: "Ø", total: "gesamt", num: "Anzahl", number: "Anzahl", max: "max.", maximum: "max.", min: "min.", minimum: "min.",
  monthly: "monatlich", yearly: "jährlich", last: "letzte", months: "Monate", month: "Monat", days: "Tage", years: "Jahre",
  percentage: "Anteil", percent: "Anteil", pct: "Anteil", fraction: "Anteil", change: "Veränderung", growth: "Wachstum",
  population: "Bevölkerung", pop: "Pop", pops: "Pops", country: "Land", countries: "Länder", location: "Ort", locations: "Orte",
  province: "Provinz", provinces: "Provinzen", area: "Gebiet", region: "Region", market: "Markt", markets: "Märkte",
  estate: "Stand", estates: "Stände", army: "Heer", navy: "Flotte", maintenance: "Unterhalt", cost: "Kosten", costs: "Kosten",
  gold: "Gold", income: "Einkommen", expense: "Ausgaben", expenses: "Ausgaben", balance: "Saldo", tax: "Steuer", taxable: "steuerpfl.",
  base: "Basis", trade: "Handel", trades: "Handel", merchant: "Händler", merchants: "Händler", capacity: "Kapazität", power: "Macht",
  strength: "Stärke", military: "Militär", manpower: "Manpower", sailors: "Seeleute", levy: "Aufgebot", levies: "Aufgebote",
  regiment: "Regiment", regiments: "Regimenter", fort: "Festung", forts: "Festungen", control: "Kontrolle", development: "Entwicklung",
  prosperity: "Wohlstand", literacy: "Bildung", satisfaction: "Zufriedenheit", target: "Ziel", culture: "Kultur", cultures: "Kulturen",
  cultural: "kulturell", religion: "Religion", religious: "religiös", unity: "Einheit", influence: "Einfluss", tradition: "Tradition",
  legitimacy: "Legitimität", prestige: "Prestige", stability: "Stabilität", inflation: "Inflation", war: "Krieg", wars: "Kriege",
  exhaustion: "Müdigkeit", debt: "Schulden", loan: "Kredit", loans: "Kredite", bond: "Anleihe", bonds: "Anleihen",
  creditworthiness: "Kreditwürdigkeit", credit: "Kredit", interest: "Zins", food: "Nahrung", consumption: "Verbrauch",
  production: "Produktion", produced: "produziert", output: "Ausstoß", building: "Gebäude", buildings: "Gebäude", level: "Stufe",
  levels: "Stufen", employment: "Beschäftigung", employed: "beschäftigt", workers: "Arbeiter", rgo: "Rohstoff", raw: "Roh",
  material: "stoff", materials: "stoffe", goods: "Güter", price: "Preis", value: "Wert", score: "Punkte", rank: "Rang", great: "Groß",
  subject: "Untertan", subjects: "Untertanen", overlord: "Oberherr", rival: "Rivale", rivals: "Rivalen", diplomatic: "diplomatisch",
  diplomats: "Diplomaten", diplomat: "Diplomat", relations: "Beziehungen", relation: "Beziehung", alliance: "Allianz",
  character: "Person", characters: "Personen", ruler: "Herrscher", heir: "Erbe", cabinet: "Kabinett", reform: "Reform",
  reforms: "Reformen", law: "Gesetz", laws: "Gesetze", privilege: "Privileg", privileges: "Privilegien", parliament: "Parlament",
  government: "Regierung", institution: "Institution", institutions: "Institutionen", advance: "Fortschritt", advances: "Fortschritte",
  research: "Forschung", progress: "Fortschritt", integration: "Integration", proximity: "Nähe", capital: "Hauptstadt",
  migration: "Wanderung", attraction: "Anziehung", conversion: "Bekehrung", assimilation: "Assimilation", heathen: "Heiden",
  heretic: "Ketzer", faith: "Glaube", primary: "Haupt", accepted: "akzeptiert", tolerated: "toleriert", not: "nicht",
  rebel: "Rebell", rebels: "Rebellen", unit: "Einheit", units: "Einheiten", ship: "Schiff", ships: "Schiffe", morale: "Moral",
  experience: "Erfahrung", attrition: "Zermürbung", garrison: "Garnison", supply: "Versorgung", size: "Größe", count: "Anzahl",
  amount: "Menge", age: "Alter", of: "von", per: "je", with: "mit", in: "in", and: "und", or: "oder", to: "zu", from: "aus",
  estimated: "geschätzt", historical: "historisch", potential: "möglich", possible: "möglich", current: "aktuell", used: "genutzt",
  available: "verfügbar", open: "frei", slots: "Plätze", effective: "effektiv", raised: "ausgehoben", regular: "stehend",
  expected: "erwartet", wealth: "Vermögen", economical: "Wirtschafts", gdp: "BIP", minting: "Münzprägung", coin: "Münz",
  bankruptcy: "Bankrott", owned: "eigene", home: "Heimat", coastal: "Küsten", port: "Hafen", ports: "Häfen", naval: "See",
  land: "Land", range: "Reichweite", colonial: "Kolonial", exploration: "Erkundung", explorations: "Erkundungen", upkeep: "Unterhalt",
  court: "Hof", bureaucracy: "Bürokratie", slider: "Regler", art: "Kunst", works: "Werke", quality: "Qualität", dynasty: "Dynastie",
  dynastic: "dynastisch", union: "Union", annex: "Annexion", liberty: "Freiheit", desire: "streben", loyalty: "Loyalität",
  antagonism: "Antagonismus", spy: "Spion", network: "Netz", devotion: "Hingabe", complacency: "Selbstgefälligkeit",
  horde: "Horde", tribal: "Stammes", cohesion: "Zusammenhalt", republican: "republikanisch", societal: "Gesellschafts",
  ports_: "Häfen", nobles: "Adel", clergy: "Klerus", burghers: "Bürger", peasants: "Bauern", laborers: "Arbeiter",
  soldiers: "Soldaten", slaves: "Sklaven", tribesmen: "Stammesleute", crown: "Krone", tithe: "Zehnt", reign: "Regierungszeit",
  elector: "Kurfürst", emperor: "Kaiser", hre: "HRR", imperial: "Reichs", authority: "Autorität", papal: "päpstlich",
  percentage_: "Anteil", enfranchisment: "Emanzipation", peasant: "Bauern", demand: "Nachfrage", stockpile: "Vorrat",
  profit: "Gewinn", buy: "Einkauf", sell: "Verkauf", volume: "Menge", efficiency: "Effizienz", speed: "Tempo", time: "Zeit",
  construction: "Bau", constructions: "Bauten", roads: "Straßen", road: "Straße", river: "Fluss", winter: "Winter", siege: "Belagerung",
  // Namen der Text-Funktionen (…Info, …Tooltip, …Breakdown)
  tooltip: "", tt: "", info: "", information: "", text: "", breakdown: "Aufschlüsselung", desc: "Beschreibung",
  description: "Beschreibung", effect: "Wirkung", effects: "Wirkungen", impact: "Wirkung", details: "Details",
  modifier: "Modifikator", modifiers: "Modifikatoren", on: "bei", activated: "Aktivierung", deactivated: "Deaktivierung",
  fully: "voller", support: "Unterstützung", debate: "Debatte", passed: "angenommen", failed: "abgelehnt", fail: "Ablehnung",
  start: "Beginn", sources: "Quellen", embraced: "angenommen", affected: "betroffen", points: "Punkte", enough: "genug",
  moving: "wird verlegt", researched: "erforscht", below: "darunter", by: "durch", rural: "ländlich", settlement: "Siedlung",
  town: "Stadt", city: "Großstadt", megalopolis: "Metropole", self: "Selbst", active: "aktiv", system: "System", starving: "hungernde", link: "", demands: "Nachfrage", upkeep_: "Unterhalt", spending: "Ausgaben", owned: "eigene",
};
const PREFIX = { Get: "", Is: "ist", Has: "hat", Can: "kann", Are: "sind", Was: "war", Calc: "", Contains: "enthält", Auto: "automatisch" };
function de(key) {
  if (LABELS[key]) return LABELS[key];
  let k = String(key), pre = "";
  const m = k.match(/^(eco_|dip_|cur_|curmax_|curbal_|abil_|disease_|popnum_|poppct_|estsat_|esttsat_|esttax_|estmaxtax_|estpriv_|estprivmax_|sv_|world_|bltot_|bleff_|sutype_|sucount_|sufrac_|sustr_|sucat_|prod_|traded_|rank_|inst_|produced_)(.*)$/);
  const SUB = { cur_: "Wert", curmax_: "Maximum", curbal_: "Bilanz", abil_: "Fähigkeit", disease_: "Krankheit", popnum_: "Pops",
                poppct_: "Anteil", estsat_: "Zufriedenheit", esttsat_: "Zielzufriedenheit", esttax_: "Steueranteil", estmaxtax_: "Höchststeuer",
                estpriv_: "Privilegien", estprivmax_: "Privilegien möglich", sv_: "Gesellschaftswert", world_: "Weltproduktion",
                bltot_: "Gebäudestufen inkl. Bau", bleff_: "Gebäudestufen wirksam", sutype_: "Untereinheiten", sucount_: "Anzahl",
                sufrac_: "Anteil", sustr_: "Stärke", sucat_: "Kategorie", prod_: "Produktion", traded_: "Handel", rank_: "Orte mit Rang",
                inst_: "Institution", produced_: "Produktion" };
  if (m && m[1] !== "eco_" && m[1] !== "dip_") {
    const rest = m[2], name = DE_NAMES[rest] || DE_NAMES[rest.replace(/_estate$/, "")];
    return `${SUB[m[1]]}: ${name || rest.replace(/_estate$/, "").split("_").map(w => GLOSSAR[w] ?? w).filter(Boolean).join(" ")}`;
  }
  if (m) k = m[2];
  const p = k.match(/^(Get|Is|Has|Can|Are|Was|Calc|Contains|Auto)(?=[A-Z])/);
  if (p) { pre = PREFIX[p[1]]; k = k.slice(p[1].length); }
  const words = k.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/_/g, " ").toLowerCase().split(/\s+/).filter(Boolean);
  const out = words.map(w => GLOSSAR[w] ?? w);
  if (out[0] === "gesamt" && out.length > 1) out.push(out.shift());          // "Bevölkerung gesamt" statt "gesamt Bevölkerung"
  return [pre, ...out].filter(Boolean).join(" ").replace(/^./, c => c.toUpperCase());
}
// Deutsche Spielnamen (Güter, Gebäude, Pop-Typen, Stände) - füllt app.js render() aus den Spieldaten
const DE_NAMES = {};
// Bezeichnung mit Code-Namen (klein)
const deL = key => `${esc(de(key))} <span class="code">${esc(key)}</span>`;
