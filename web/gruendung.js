"use strict";
// Kachel Ländergründung (Nutzerwunsch 30.10.): welche größeren Länder wir gründen können und wie wir am besten vorgehen – Wirtschaft,
// Militär, Diplomatie, Staat; Auswahl, wenn es mehrere Gründungen gibt (bleibt in diesem Browser). Daten: d.gruendung aus
// eu5ratgeber/gruendung.py (Spieldateien formable_countries, Spielstand ab Format 17, Daten-Mod). Begriffe verweisen ins Wiki
// (#wiki/<schlüssel>, #wiki/<ordner>/<schlüssel>), Fortschritte in den Techbaum (#techbaum/<schlüssel>) – nur Schlüssel, die der Server
// in den Spieldaten gefunden hat. Nutzt esc/fmt/pct/table/store/hd aus app.js und design.js.
THEME.gruendung = { icon: "👑", color: "--c3", group: "staat" };      // nach Nachbarn im Bereich „Diplomatie und Militär“
if (typeof EMPF_KACHEL !== "undefined") EMPF_KACHEL.gruendung = "Ländergründung";

const GR_STATUS = s => s === true ? `<span class="pos" title="erfüllt">✓</span>` : s === false ? `<span class="neg" title="nicht erfüllt">✗</span>`
  : `<span class="hint" title="unbekannt – vom Ratgeber nicht auswertbar">?</span>`;
const GR_AMPEL = { gruen: ["pos", "aussichtsreich"], gelb: ["", "knapp"], rot: ["neg", "nicht ratsam"], grau: ["hint", "unbekannt"] };
const grAmpel = s => { const [c, t] = GR_AMPEL[s] || ["hint", "keine Mod-Werte"];
  return `<span class="${c}" style="${s === "gelb" ? "color:var(--c7);" : ""}font-size:16px" title="${t}">●</span>`; };
// Verweis ins Wiki bzw. in den Techbaum (Hash-Pfad vom Server, z. B. "wiki/estate_power", "techbaum/teutonic_legacy")
const grLink = (pfad, text = "ⓘ", titel = "") => pfad ? `<a class="grlink" href="#${esc(pfad)}" title="${esc(titel || (pfad.startsWith("techbaum/")
  ? "im Techbaum zeigen" : "in den Mechaniken nachlesen"))}">${text}</a>` : "";
const grBegriff = (G, k, text) => G.wiki?.[k] ? `<a class="grlink" href="#${esc(G.wiki[k])}" title="in den Mechaniken nachlesen">${esc(text)}</a>` : esc(text);
const grWahl = () => store.get("rg_gruendung_wahl") || "";

// Bedingungen als Baum: Status, Text, Ist-Wert, Hinweis, Wiki-Verweis; Kinder eingerückt
function grBaum(liste) {
  if (!liste?.length) return `<p class="hint">keine</p>`;
  return `<ul class="grbaum">${liste.map(x => `<li>${GR_STATUS(x.ok)} ${esc(x.text)}${x.ist ? ` <span class="hint">(jetzt: ${esc(x.ist)})</span>` : ""}
    ${grLink(x.wiki)}${grLink(x.techbaum, "🔬")}${x.hinweis ? `<div class="hint">${esc(x.hinweis)}</div>` : ""}${x.kinder?.length ? grBaum(x.kinder) : ""}</li>`).join("")}</ul>`;
}

function gruendungKachel(d) {
  const G = d.gruendung;
  if (!G) return { head: hd({ big: [{ l: "Gründungen", v: "–" }] }), body: '<p class="hint">Noch keine Daten.</p>' };
  if (G.fehler) return { head: hd({ big: [{ l: "Gründungen", v: "?" }], warn: [esc(G.fehler)] }), body: `<p class="hint">Fehler beim Auswerten: ${esc(G.fehler)}</p>` };
  const S = G.stand || {}, O = G.optionen || [];
  // Grad 0 = kein gegründetes Land (Daten-Mod formable_level; ROEMISCH kennt nur I–VI)
  const gradTxt = S.grad || (S.stufe === 0 ? "0" : "?");
  const wahl = O.find(o => o.key === grWahl()) || O.find(o => o.key === G.standard) || O[0];
  const regel = S.regel_name ? esc(S.regel_name) : `<span class="hint">unbekannt</span>`;
  const anteilTxt = o => `${fmt(o.gebiet.unsere, 0)} / ${fmt(o.gebiet.noetig, 0)}`;
  const bedTxt = o => o.bedingungen_alle ? `${o.bedingungen_erfuellt}/${o.bedingungen_alle}${o.bedingungen_offen ? ` (${o.bedingungen_offen} ?)` : ""}` : "keine";
  const head = hd({
    big: [{ l: "Gründungen", v: String(O.length), title: O.map(o => o.name).join(", ") || "keine infrage" },
          wahl && { l: "Gewählt", v: esc(wahl.name), cls: wahl.gruendbar ? "pos" : "", title: `Grad ${wahl.grad || "?"}` },
          wahl && { l: "Orte", v: anteilTxt(wahl), u: "eigene / nötig", bar: wahl.gebiet.noetig ? wahl.gebiet.unsere / wahl.gebiet.noetig : null,
                    cls: wahl.gebiet.ok ? "pos" : "" },
          wahl && { l: "Bedingungen", v: bedTxt(wahl), cls: wahl.bedingungen_ok === true ? "pos" : wahl.bedingungen_ok === false ? "neg" : "" }],
    small: [{ l: "Unser Grad", v: `${esc(gradTxt)}${S.stufe === 0 ? ` <span class="hint">kein gegründetes Land</span>` : ""}`, title: S.stufe_quelle || "" },
            { l: "Spielregel", v: regel, title: "Spielregel „Gründbare Länder“ laut Spielstand" },
            { l: "Kultur", v: esc(S.kultur || "–"), title: (S.kulturgruppen || []).join(", ") }],
    warn: [O.some(o => o.gruendbar) && `Jetzt gründbar: ${esc(O.filter(o => o.gruendbar).map(o => o.name).join(", "))}`,
           G.spiel_extra?.length && `Laut Spiel sichtbar, vom Ratgeber nicht als Option erkannt: ${esc(G.spiel_extra.map(x => x.name).join(", "))}`,
           G.fehler_spielstand && "Spielstand-Auszug fehlerhaft: " + esc(G.fehler_spielstand)],
  });
  if (!O.length) return { head, body: `<p class="hint">Keine Gründung kommt infrage (Grad über unserem ${esc(gradTxt)}, Spielregel, potential,
    eigener Ort im geforderten Gebiet). ${grQuellen(G)}</p>` };
  // Übersicht und Auswahl
  const uebersicht = table([
    { t: "", f: o => `<input type="radio" name="gr-wahl" data-gr-wahl="${esc(o.key)}"${o === wahl ? " checked" : ""} title="diese Gründung zeigen">` },
    { t: "Gründung", l: true, f: o => `<b>${esc(o.name)}</b> <span class="hint">${esc(o.tag || "")}</span>${grLink(o.wiki)}${o.potential_ok === null
      ? ` <span class="hint" title="Sichtbarkeit (potential) nicht sicher auswertbar">sichtbar?</span>` : ""}` },
    { t: "Grad", f: o => esc(o.grad || "?") },
    { t: "Gebiet erfüllt", f: o => pct(o.gebiet.noetig ? Math.min(1, o.gebiet.unsere / o.gebiet.noetig) : 0, 0),
      cls: o => o.gebiet.ok ? "pos" : "", title: "eigene Orte ÷ nötige Orte" },
    { t: "Orte (eigene / nötig / alle)", f: o => `${fmt(o.gebiet.unsere, 0)} / ${fmt(o.gebiet.noetig, 0)} / ${fmt(o.gebiet.alle, 0)}` },
    { t: "Bedingungen", f: bedTxt, cls: o => o.bedingungen_ok === true ? "pos" : o.bedingungen_ok === false ? "neg" : "" },
    { t: "Regel", f: o => esc(o.regel_name || o.regel) },
    { t: "Stand", l: true, f: o => o.gruendbar ? `<b class="pos">jetzt gründbar</b>` : o.fast ? `<span style="color:var(--c7)">fast – ${o.gebiet.fehlt} Orte fehlen</span>`
      : `${o.gebiet.fehlt ? `${o.gebiet.fehlt} Orte fehlen` : "Gebiet erfüllt"}${o.bedingungen_ok === false ? ", Bedingungen offen" : ""}` }], O, { scroll: false });
  const auswahl = O.length > 1 ? `<label class="grauswahl">Gründung <select data-gr-select>${O.map(o => `<option value="${esc(o.key)}"${o === wahl ? " selected" : ""}>${esc(o.name)} (Grad ${esc(o.grad || "?")})</option>`).join("")}</select></label>
      <span class="hint">Standard: die am weitesten erfüllte (gründbar zuerst, dann Gebiet und Bedingungen). Die Wahl bleibt in diesem Browser.</span>` : "";
  const karte = (titel, html, breit = false) => `<div class="card${breit ? " grbreit" : ""}"><h3>${titel}</h3>${html}</div>`;
  const o = wahl;
  return { head, body: `<div class="grid2">${karte(`Optionen – ${O.length}`, auswahl + uebersicht, true)}
    ${karte(`${esc(o.name)} <span class="hint">Grad ${esc(o.grad || "?")} · ${esc(o.regel_name || "")}</span> ${grLink(o.wiki)}`, grUeberblick(G, o), true)}
    ${karte("Empfehlungen je Bereich", grEmpfehlungen(G, o), true)}
    ${karte(`Bedingungen (${bedTxt(o)})`, grBaum(o.bedingungen) + `<h5>Sichtbarkeit im Spiel (potential)</h5>` + grBaum(o.potential)
      + `<p class="hint">✓ erfüllt · ✗ nicht erfüllt · ? vom Ratgeber nicht auswertbar – im Spiel prüfen. Texte nach der Spieldatei formable_countries
         (allow, potential) mit deutschen Namen aus der Lokalisierung.</p>`)}
    ${karte(`Gebiet – ${fmt(o.gebiet.unsere, 0)} von ${fmt(o.gebiet.alle, 0)} Orten`, grGebiet(G, o))}
    ${karte(`Wer besitzt die fehlenden Orte?`, grBesitzer(G, o), true)}
    ${karte("Wirkung der Gründung", grWirkung(G, o))}
    ${karte("Danach möglich", grKette(G, o))}
    </div>${grQuellen(G)}` };
}

function grUeberblick(G, o) {
  const g = o.gebiet;
  const zeilen = [
    ["Stand", o.gruendbar ? `<b class="pos">Jetzt gründbar</b> – Weg im Spiel: ${G.weg?.fenster ? `Fenster „${esc(G.weg.fenster)}“, ` : ""}Reiter „${esc(G.weg?.reiter || "Gründbare")}“
       (neben „Entscheidungen“), Knopf „„${esc(o.name)}“ gründen“; auch über den Hinweis „${esc(G.weg?.hinweis || "")}“`
      : o.fast ? `<span style="color:var(--c7)">Fast gründbar</span> – es fehlen ${g.fehlt} Orte` : "noch nicht gründbar"],
    ["Gebiet", `${fmt(g.unsere, 0)} von ${fmt(g.alle, 0)} Orten (${pct(g.anteil, 0)}), gefordert ${pct(g.gefordert, 0)} = ${fmt(g.noetig, 0)} Orte`
      + (g.fehlt ? ` – <b>${fmt(g.fehlt, 0)} fehlen</b>` : ` – <span class="pos">erfüllt</span>`)],
    g.hauptstadt_noetig && ["Hauptstadt", `muss im geforderten Gebiet liegen: ${GR_STATUS(g.hauptstadt_ok)}`],
    ["Bedingungen", `${o.bedingungen_erfuellt} von ${o.bedingungen_alle} erfüllt${o.bedingungen_offen ? `, ${o.bedingungen_offen} offen (?)` : ""}`],
    ["Sichtbar im Spiel", o.sichtbar ? `ja (eigener Ort im geforderten Gebiet${o.potential_ok === null ? "; potential nicht sicher auswertbar" : ""})` : "nein"],
    // ab Daten-Mod 0.25: Urteil des Spiels (is_formable_visible, location_progress_for_formable = Anteil an den nötigen Orten)
    ["Laut Spiel", !o.spiel ? `<span class="hint">noch keine Werte – kommen mit Daten-Mod 0.25</span>`
      : !o.spiel.sichtbar ? `<span class="neg">nicht sichtbar</span> <span class="hint">(is_formable_visible)</span>`
      : `sichtbar ✓ · ${num(o.spiel.fortschritt) ? `${pct(o.spiel.fortschritt, 1)} der nötigen Orte${num(o.spiel.orte) ? ` (≈ ${fmt(o.spiel.orte, 0)} von ${fmt(g.noetig, 0)})` : ""}` : "Gebietsfortschritt –"}
         ${o.spiel.gleich === true ? `<span class="pos">– gleich wie der Ratgeber ✓</span>`
           : o.spiel.gleich === false ? `<span class="neg">– Ratgeber zählt ${fmt(g.unsere, 0)} von ${fmt(g.noetig, 0)}</span> <span class="hint">(andere Zählung, etwa Orte von Untertanen)</span>` : ""}
         <span class="hint">(location_progress_for_formable; im Spiel die Zahl x/y am Eintrag im Reiter „${esc(G.weg?.reiter || "")}“)</span>`],
    o.rang_neu_name && ["Neuer Rang", `${esc(o.rang_neu_name)} ${grLink(o.rang_neu_wiki)}`],
  ];
  return kv(zeilen.filter(Boolean)) + (o.beschreibung ? `<p class="hint">${esc(o.beschreibung)}</p>` : "");
}

function grEmpfehlungen(G, o) {
  const E = o.empfehlungen || {};
  const liste = (xs, leer) => xs?.length ? `<ul class="grempf">${xs.map(x => `<li${x.offen ? ' class="hint"' : ""}>${x.ampel !== undefined ? grAmpel(x.ampel) + " " : ""}${esc(x.text)}
    ${x.grund ? `<div class="hint">${esc(x.grund)}</div>` : ""}</li>`).join("")}</ul>` : `<p class="hint">${leer}</p>`;
  const P = E.plan;
  const plan = P ? `<p><b>Vorschlag für die ${fmt(P.fehlt, 0)} fehlenden Orte</b> (Regel des Ratgebers: Klientelländer zuerst, dann nach Ampel grün, gelb,
      ohne Mod-Werte, rot und nach Zahl der Orte): ${P.schritte.map(s => `${esc(s.name)} ${s.orte < s.von ? `${s.orte} von ${s.von}` : s.orte} (${s.weg})`).join(" + ")}
      = ${fmt(P.summe, 0)}${P.summe < P.fehlt ? ` – <span class="neg">reicht nicht, ${fmt(P.fehlt - P.summe, 0)} fehlen weiter</span>` : ""}.</p>` : "";
  return `<div class="grid2 grbereiche">
    <div><h5>Wirtschaft</h5>${liste(E.wirtschaft, "–")}</div>
    <div><h5>Militär <span class="hint">${grBegriff(G, "casus_belli", "Kriegsgrund")} · ${grBegriff(G, "truce", "Waffenstillstand")}</span></h5>${plan}${liste(E.militaer, "Kein fehlender Ort in fremder Hand.")}</div>
    <div><h5>Diplomatie <span class="hint">${grBegriff(G, "subject", "Klientelland")} · ${grBegriff(G, "alliance", "Bündnis")} · ${grBegriff(G, "annexation", "Annexion")}</span></h5>${liste(E.diplomatie, "Nichts zu tun – keine Klientelländer, Verbündeten oder starken Bündnisse unter den Besitzern.")}</div>
    <div><h5>Staat <span class="hint">${grBegriff(G, "estate_privilege", "Privileg")} · ${grBegriff(G, "estate_power", "Standes-Macht")} · ${grBegriff(G, "government_reform", "Reform")}</span></h5>${liste(E.staat, "Alle Bedingungen erfüllt.")}</div>
  </div><p class="hint">Regeln des Ratgebers mit Begründung aus Spieldateien, Spielstand und Daten-Mod (Ampel wie in der Kachel Nachbarn und
    Kriegsgelegenheiten). Was eine Eroberung oder Eingliederung kostet, rechnet der Ratgeber nicht.</p>`;
}

function grGebiet(G, o) {
  const g = o.gebiet;
  const t = table([
    { t: "Art", l: true, f: u => u.wiki ? `<a class="grlink" href="#${esc(u.wiki)}">${esc(u.art)}</a>` : esc(u.art) },
    { t: "Name", l: true, f: u => esc(u.name) },
    { t: "eigene Orte", f: u => fmt(u.unsere, 0), cls: u => u.unsere === u.alle && u.alle ? "pos" : "" },
    { t: "alle Orte", f: u => fmt(u.alle, 0) }], g.einheiten || [], { scroll: false });
  return t + kv([
    ["Gefordert", `${pct(g.gefordert, 0)} aller geforderten Orte zusammen = ${fmt(g.noetig, 0)} von ${fmt(g.alle, 0)}`],
    ["Eigene", `${fmt(g.unsere, 0)} (${pct(g.anteil, 0)})`],
    ["Fehlen", g.fehlt ? `<b>${fmt(g.fehlt, 0)}</b>` : `<span class="pos">0</span>`],
    ["Hauptstadt", g.hauptstadt_noetig ? `muss im Gebiet liegen ${GR_STATUS(g.hauptstadt_ok)}` : "keine Bedingung (capital_required nein)"],
    g.besitz_bekannt && ["Ohne Besitzer", fmt(g.ohne_besitzer, 0)]].filter(Boolean))
    + `<p class="hint">Spieldatei formable_countries (Gebiete, required_locations_fraction), Karte in_game/map_data/definitions.txt. Annahmen: nur besitzbare
      Orte zählen (ohne Meereszonen, Seen, unpassierbare Berge und non_ownable laut default.map); der Anteil gilt für alle geforderten Orte zusammen;
      Orte unserer Klientelländer zählen nicht mit.</p>`;
}

function grBesitzer(G, o) {
  if (!o.gebiet.besitz_bekannt) return o.gebiet.besitz_fehlt === "kandidat"
    ? `<p class="hint">Die Besitzer dieser Orte hat der Ratgeber beim Einlesen nicht gesammelt: nach dem Rang im Spielstand war die Gründung
      noch keine Option (die Stufe kommt jetzt aus dem Daten-Mod). Ein neuer Spielstand mit dem höheren Rang bringt sie.</p>`
    : `<p class="hint">Die Besitzer der fehlenden Orte stehen erst in Momentaufnahmen ab Format 17 – der Ratgeber liest
    den letzten Spielstand neu ein, spätestens mit dem nächsten Autosave.</p>`;
  if (!o.besitzer?.length) return `<p class="hint">Alle geforderten Orte sind unsere oder ohne Besitzer.</p>`;
  const bez = b => [b.untertan && "unser Klientelland", b.verbuendet && "verbündet", b.oberherr && "unser Oberherr",
    ...(b.beziehungen || []).map(x => (typeof BEZIEHUNG !== "undefined" && BEZIEHUNG[x]) || x)].filter(Boolean).join(", ") || "–";
  const ja = v => v === 1 ? "ja" : v === 0 ? "nein" : "–";
  return table([
    { t: "", f: b => grAmpel(b.ampel) },
    { t: "Land", l: true, f: b => `<b>${esc(b.name)}</b> <span class="hint">${esc(b.tag)}</span><div class="hint">${esc(bez(b))}</div>` },
    { t: "benötigte Orte", f: b => fmt(b.orte, 0) },
    { t: "Beispiele", l: true, f: b => esc(b.beispiele.join(", ")) + (b.orte > b.beispiele.length ? " …" : "") },
    { t: "Bündnis wir : sie", f: b => b.unendlich ? "∞ : 1" : typeof b.verhaeltnis === "number" ? `${fmt(b.verhaeltnis, 2)} : 1` : "–" },
    { t: "Bündnis ÷ Land", f: b => typeof b.buendnis_faktor === "number" ? fmt(b.buendnis_faktor, 1) : "–",
      title: "ihr Verteidigungsbündnis ÷ ihre eigene Stärke (Daten-Mod)" },
    { t: "Kriegsgrund", f: b => b.kriegsgrund ? '<span class="pos">ja</span>' : b.mod ? "nein" : "–" },
    { t: "Waffenstillstand", f: b => ja(b.waffenstillstand) },
    { t: "Militär-Rang", f: b => fmt(b.mil_rang, 0) },
    { t: "Begründung", l: true, f: b => esc((b.gruende || []).join("; ") || (b.mod ? "" : "keine Mod-Werte – keine Beziehung zu uns"))
      + (b.hinweise?.length ? `<div class="hint">${esc(b.hinweise.join("; "))}</div>` : "") }], o.besitzer)
    + `<p class="hint">Besitzer: Spielstand ${esc(G.datum || "")}. Ampel, Bündnisstärken, Kriegsgrund und Waffenstillstand: Daten-Mod (Kachel Nachbarn und
      Kriegsgelegenheiten); Militär-Rang: Spielstand.</p>`;
}

function grWirkung(G, o) {
  const w = (o.wirkung || []).map(x => `<li>${x.ok === false ? `<span class="hint">` : ""}${esc(x.text)}${x.bedingung ? ` <span class="hint">(falls: ${esc(x.bedingung)}${x.ok === false
    ? " – trifft nicht zu" : x.ok === null ? " – unbekannt" : ""})</span>` : ""}${grLink(x.wiki)}${grLink(x.techbaum, "🔬")}${x.ok === false ? "</span>" : ""}</li>`).join("");
  const wert = (v, m) => v === null || v === undefined ? "–" : m.ja_nein || typeof v === "string" ? ({ yes: "ja", no: "nein" }[v] || esc(v))
    : m.prozent ? pct(v, 0) : fmt(v, v % 1 ? 2 : 0);
  const mods = o.rang_modifikatoren?.length ? `<h5>Neuer Rang ${esc(o.rang_neu_name || "")} gegenüber heute (${esc(G.stand?.rang_name || "")})</h5>`
    + table([{ t: "Wert", l: true, f: m => esc(m.name) }, { t: "heute", f: m => wert(m.alt, m) }, { t: "danach", f: m => wert(m.neu, m), cls: () => "pos" }],
      o.rang_modifikatoren, { scroll: false }) + `<p class="hint">Spieldatei country_ranks (rank_modifier), deutsche Namen der Modifikatoren.</p>` : "";
  const fs = o.fortschritte?.length ? `<h5>Fortschritte nur für ${esc(o.name)} (${o.fortschritte.length})</h5><p>${o.fortschritte.map(f =>
    `<a class="grlink" href="#${esc(f.techbaum)}" title="im Techbaum zeigen">${esc(f.name)}</a>`).join(" · ")}</p>
    <p class="hint">Spieldatei advances: ihr potential nennt das Kürzel ${esc(o.tag || "")} (ist oder war). Laut readme der Spieldatei
    werden Fortschritte nicht rückwirkend sichtbar – die vergangener Zeitalter gibt es nach einer späten Gründung möglicherweise nicht mehr.</p>` : "";
  return `<ul class="grempf">${w || "<li>laut Spieldatei keine besondere Wirkung</li>"}<li>Name, Flagge und Farbe des Landes wechseln
    <span class="hint">(Europedia „${grBegriff(G, "formable_country", "Gründbares Land")}“)</span></li></ul>${mods}${fs}`;
}

function grKette(G, o) {
  if (!o.danach?.length) return `<p class="hint">Keine weitere Gründung mit höherem Grad, deren Gebiet an dieses oder an unsere Orte grenzt und deren
    Bedingungen (potential) nach der Gründung nicht sicher verfehlt sind.</p>`;
  return `<ul class="grempf">${o.danach.map(x => `<li>${x.option ? `<a href="#" data-gr-wahl-link="${esc(x.key)}">${esc(x.name)}</a>` : esc(x.name)}
    <span class="hint">Grad ${esc(x.grad || "?")}${x.option ? " – auch jetzt schon in der Auswahl" : ""}</span></li>`).join("")}</ul>
    <p class="hint">Regel des Ratgebers: Gründungen mit höherem Grad als diese und als der Rang danach, deren potential mit Kürzel, Rang und Regierungsform nach
      der Gründung nicht sicher falsch ist und deren Gebiet das dieser Gründung oder unsere Orte berührt; die Spielregel gilt weiter.</p>`;
}

function grQuellen(G) {
  const S = G.stand || {}, A = G.ausgeschlossen || {};
  const macht = Object.entries(S.stand_macht || {}).map(([k, v]) => `${esc(S.stand_namen?.[k] || k)} ${pct(v, 1)}`).join(", ");
  return `<p class="hint">Quellen: Spieldateien in_game/common/formable_countries (mit DLC), country_ranks, advances; Spielstand ${esc(G.datum || "")}
    ${G.format17 ? "" : "(vor Format 17: ohne Besitzer, Spielregel, Verbündete und geduldete Kulturen)"}; Daten-Mod (neuester Monat) vor Spielstand
    für Stände-Macht, Grad und Krieg. Stände-Macht laut ${esc(S.stand_macht_quelle || "–")}: ${macht || "–"}. Unser ${grBegriff(G, "tier", "Grad")}:
    ${esc(S.grad || (S.stufe === 0 ? "0" : "?"))} (${esc(S.stufe_quelle || "")}) – nicht der ${grBegriff(G, "country_rank", "Rang")} (Walachei: Grad 0 bei Rang
    Herzogtum); ohne Daten-Mod die Stufe der Gründung mit unserem Kürzel, sonst 0 (passt bei 14 von 16 Ländern mit Mod-Wert). Eine Gründung muss einen
    höheren Grad haben („nur Länder eines höheren Grads“, Europedia). Nicht infrage: ${A.stufe || 0} mit zu niedrigem Grad, ${A.regel || 0} durch die Spielregel,
    ${A.potential || 0} wegen potential, ${A.gebiet || 0} ohne eigenen Ort im Gebiet. NICHT mit mehreren Bedingungen: stimmen „keins davon“ und
    „nicht alle zugleich“ überein, gilt das Ergebnis, sonst „?“.</p>`;
}

function grSetzen(key) {
  store.set("rg_gruendung_wahl", key);
  if (!LAST_D) return;
  const y = window.scrollY;
  render(LAST_D);
  if (typeof equalizeTiles === "function") equalizeTiles();
  window.scrollTo(0, y);
}
document.addEventListener("change", e => {
  if (e.target.matches?.("[data-gr-select]")) grSetzen(e.target.value);
  else if (e.target.matches?.("input[data-gr-wahl]")) grSetzen(e.target.dataset.grWahl);
});
document.addEventListener("click", e => {
  const a = e.target.closest?.("a[data-gr-wahl-link]");
  if (!a) return;
  e.preventDefault();
  grSetzen(a.dataset.grWahlLink);
});
