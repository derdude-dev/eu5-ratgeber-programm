"use strict";
// Kachel Startstrategie (Nutzerwunsch 31.10.): alles, was man am Anfang einstellt – Kabinett, Gesetze mit Politlinien, Privilegien,
// Regierungsreformen, Gesellschaftswerte, erste Gebäude, erste Forschung, Diplomatie und Bündnisvorschläge –, je mit Bezug zum
// Schwerpunkt des Wirtschaftsplans. Daten: d.startstrategie aus eu5ratgeber/startstrategie.py (alle Schwerpunkte); gezeigt wird der
// gewählte (store rg_wp_fokus wie Wirtschaftsplan und Techbaum – eine Auswahl hier setzt denselben Schlüssel). Bau, Forschung und
// Nachbarn sind nur übernommen und verlinkt. Nutzt esc/fmt/pct/sgn/table/kv/store/wpFokus aus app.js, hd aus design.js und
// grBaum/grLink aus gruendung.js (Skript davor).

const SS_STATUS = { a: ["pos", "jetzt eingestellt"], m: ["pos", "möglich – alle Bedingungen erfüllt"],
  v: ["", "sichtbar – ob jetzt wählbar, im Spiel prüfen"], u: ["hint", "unklar – Sichtbarkeit nicht auswertbar"], g: ["neg", "gesperrt"] };
const ssSt = s => { const [c, t] = SS_STATUS[s] || ["hint", "?"]; return `<span class="${c}" title="${esc(t)}">${s === "a" ? "●" : s === "g" ? "✗" : s === "m" ? "✓" : "?"}</span>`; };
const SS_FAEH = { adm: "Verwaltung", dip: "Diplomatie", mil: "Militär" };
const SS_BEREICH = { kabinett: "Kabinett", forschung: "Forschung", politlinie: "Politlinie", privileg: "Privileg", bau: "Bau",
  buendnis: "Bündnis", reform: "Reform", rivale: "Rivale" };
// Verweise und Haken wie in der Ländergründung (gruendung.js); ohne sie nur Text
const ssGL = (pfad, text = "ⓘ") => typeof grLink === "function" ? grLink(pfad, text) : "";
const ssOk = ok => typeof GR_STATUS === "function" ? GR_STATUS(ok) : ok === true ? "✓" : ok === false ? "✗" : "?";
const ssLink = (S, k, text) => S.wiki?.[k] ? `<a class="grlink" href="#${esc(S.wiki[k])}" title="in den Mechaniken nachlesen">${esc(text)}</a>` : esc(text);

// Wirkungen wie im Spiel: [schlüssel, name, anzeige, richtung, ebene, zahl, bedingt]
function ssWirk(w, max = 8) {
  if (!w?.length) return `<span class="hint">keine Modifikatoren – Wirkung über Effekte (Text im Spiel)</span>`;
  const z = w.slice(0, max).map(([m, n, t, ri, eb, , b]) => `${esc(n)} <b class="${ri > 0 ? "pos" : ri < 0 ? "neg" : ""}">${esc(t)}</b>`
    + `${eb !== "land" ? ` <span class="hint">(${eb === "ort" ? "im Ort" : "in der Provinz"})</span>` : ""}${b ? ` <span class="hint">(unter Bedingung)</span>` : ""}`);
  return z.join("<br>") + (w.length > max ? `<br><span class="hint">… ${w.length - max} weitere</span>` : "");
}
function ssBezug(p, gr, na) {
  return `${p ? `<b>${fmt(p, 0)} Punkte</b>` : `<span class="hint">0 Punkte</span>`}${gr?.length ? `<ul class="ssliste">${gr.map(g => `<li>${esc(g)}</li>`).join("")}</ul>` : ""}`
    + (na?.length ? `<div class="neg">Nachteil: ${na.map(esc).join("; ")}</div>` : "");
}
// Bedingungen (gruendung.js grBaum) nur, wo etwas offen oder gesperrt ist
function ssBed(x) {
  if (!x) return "";
  if (x.status === "g" && x.grund && !x.bed) return `<div class="neg">gesperrt: ${esc(x.grund)}</div>`;
  if (!x.bed?.length) return x.status === "m" || x.status === "a" ? `<span class="hint">✓ alle Bedingungen erfüllt</span>` : "";
  return `<details class="ssbed"><summary>${ssSt(x.status)} ${esc((SS_STATUS[x.status] || [])[1] || "")}${x.grund ? ` – ${esc(x.grund)}` : ""}</summary>${typeof grBaum === "function" ? grBaum(x.bed) : ""}</details>`;
}
const ssKarte = (titel, html, quelle = "", breit = true) => `<div class="card${breit ? " ssbreit" : ""}"><h3>${titel}</h3>${html}${quelle ? `<p class="hint">${quelle}</p>` : ""}</div>`;

function startstrategieKachel(d) {
  const S = d.startstrategie;
  if (!S) return { head: hd({ big: [{ l: "Abweichungen", v: "–" }] }), body: '<p class="hint">Noch keine Daten (Spielwissen fehlt).</p>' };
  if (S.fehler) return { head: hd({ big: [{ l: "Abweichungen", v: "?" }], warn: [esc(S.fehler)] }), body: `<p class="hint">Fehler beim Auswerten: ${esc(S.fehler)}</p>` };
  SS_NAMEN = S.stand_namen || {};
  const fk0 = typeof wpFokus === "function" ? wpFokus(d) : "grundwirtschaft";
  const fk = S.fokusse[fk0] ? fk0 : Object.keys(S.fokusse)[0];
  const F = S.fokusse[fk], A = F.abweichungen || {}, D = S.diplomatie || {};
  const head = hd({
    big: [{ l: "Abweichungen", v: String(A.summe ?? "–"), cls: A.summe ? "neg" : "pos",
            title: `Einstellungen, die vom Vorschlag abweichen: Kabinett ${A.kabinett}, Politlinien ${A.gesetze}, Privilegien ${A.privilegien}, Reform ${A.reformen}, Rivale ${A.rivalen}, Bündnis ${A.buendnis}` },
          { l: "Schwerpunkt", v: esc(F.name), cls: "wort" }],
    small: [F.erste_schritte?.length && { l: "1. Schritt", v: `${esc(SS_BEREICH[F.erste_schritte[0].bereich] || "")}: ${esc(F.erste_schritte[0].text)}`, mw: 520 },
            { l: "Politischer Einfluss", v: num(S.einfluss) ? `${fmt(S.einfluss, 1)}${num(S.einfluss_monat) ? ` <span class="hint">${sgn(S.einfluss_monat, 2)}/Monat</span>` : ""}` : "–" },
            { l: "Kabinett", v: `${(S.kabinett?.plaetze || []).length} Plätze${num(S.kabinett?.offen) && S.kabinett.offen ? `, ${S.kabinett.offen} frei` : ""}` },
            { l: "Rivalen", v: num(D.rivalen_zahl) ? `${fmt(D.rivalen_zahl, 0)} von ${fmt(D.rivalen_moeglich, 0)}` : "–" },
            { l: "Stand", v: `Spielstand ${esc(S.datum || "")}${S.mod_datum ? ` · Mod ${esc(S.mod_datum)}` : " · ohne Daten-Mod"}` }],
    warn: [!S.mit_mod && "Ohne Werte des Daten-Mods: keine freien Plätze, Personen, Stände-Ziele, Bündnisstärken"],
  });
  const wahl = `<div class="wpwahl"><label>Schwerpunkt <select id="ss-fokus">${Object.entries(S.fokusse).map(([k, f]) =>
      `<option value="${k}"${k === fk ? " selected" : ""}>${esc(f.name)}</option>`).join("")}</select></label>
    <span class="hint">derselbe Schwerpunkt wie im Wirtschaftsplan und im Techbaum. ${esc(S.regeln.bewertung)}</span></div>`;
  const body = `${wahl}<div class="grid2">
    ${ssErste(S, F)}${ssKabinett(S, F)}${ssGesetze(S, F)}${ssPrivilegien(S, F)}${ssReformen(S, F)}${ssGesellschaft(S, F)}
    ${ssBau(S, F)}${ssForschung(S, F)}${ssDiplomatie(S)}${ssBuendnis(S)}</div>${ssPunkte(S, F)}`;
  return { head, body };
}

function ssErste(S, F) {
  const xs = F.erste_schritte || [];
  const li = xs.map(x => `<li><b>${esc(SS_BEREICH[x.bereich] || x.bereich)}:</b> ${x.link ? `<a href="${esc(x.link)}">${esc(x.text)}</a>` : esc(x.text)}
    ${x.warum ? `<div class="hint">${esc(x.warum)}</div>` : ""}${x.kosten ? `<div class="${x.sparen ? "neg" : "hint"}">Kosten: ${esc(x.kosten)}</div>` : ""}</li>`).join("");
  return ssKarte(`Erste Schritte – ${esc(F.name)}`, xs.length ? `<ol class="sserste">${li}</ol>` : `<p class="hint">Nichts zu ändern – alle Einstellungen passen zum Schwerpunkt.</p>`,
    `${esc(S.regeln.erste_schritte)} ${esc(S.regeln.abweichung)}`);
}

function ssKabinett(S, F) {
  const K = S.kabinett || {}, AK = K.aktionen || {};
  const name = a => AK[a]?.n || a || "–";
  const zeile = s => {
    const j = s.jetzt || {}, a = AK[s.vorschlag] || {}, f = s.faehigkeit;
    const jetzt = j.aktion ? `<b>${esc(j.aktion_name || name(j.aktion))}</b>${ssGL(AK[j.aktion]?.wiki)}<br>${esc(j.person || "–")} <span class="hint">(V ${j.adm ?? "–"} / D ${j.dip ?? "–"} / M ${j.mil ?? "–"}${j.stand ? `, ${esc(j.stand)}` : ""})</span>
        <div class="hint">seit ${esc(j.seit || "–")}${num(j.wirksam) ? ` · Gesamtsteigerung ${pct(j.wirksam, 1)} (Spiel)` : ""}${num(j.fortschritt) ? ` · Fortschritt ${pct(j.fortschritt, 0)}` : ""}</div>
        ${j.mod_andere_aktion ? `<div class="hint">Daten-Mod zeigt noch „${esc(j.mod_andere_aktion)}“ (älterer Monat) – Werte nicht übernommen</div>` : ""}`
      : `<span class="hint">freier Platz</span>`;
    const min = s.minister ? `<div>Minister: <b>${esc(s.minister.name)}</b> (${esc(SS_FAEH[f] || f)} ${fmt(s.minister.wert, 0)}${num(s.minister.jetzt) ? ` statt ${fmt(s.minister.jetzt, 0)}` : ""}, ${sgn(s.minister.mehr * 100, 1)} %-Pkt. Steigerung)</div>` : "";
    const vor = !s.abweichung ? `<span class="pos">behalten</span> <span class="hint">${esc(s.grund || "")}</span>${min}`
      : `${s.vorschlag !== j.aktion ? `<b>${esc(name(s.vorschlag))}</b>${ssGL(a.wiki)} ${ssSt(a.status)}<div class="hint">${esc(s.grund || "")}</div>` : `<span class="pos">Aktion behalten</span>`}${min}`;
    const warum = s.vorschlag ? `${ssWirk(a.w)}${ssWarn(s.warnungen)}<div class="hint">Fähigkeit: ${esc(SS_FAEH[a.f] || a.f || "–")}${a.dauer ? ` · voll wirksam nach ${esc(a.dauer)}` : ""}${a.ziel?.length ? ` · Ziel: ${esc(a.ziel.join(", "))}` : ""}${a.mehrfach ? " · mehrfach möglich" : ""}${a.ende ? " · endet, wenn erfüllt" : ""}</div>${ssBed(a)}` : "–";
    return [num(s.platz) ? String(s.platz + 1) : "neu", jetzt, vor, warum, ssBezug(s.punkte, s.gruende, s.nachteile)
      + (s.abweichung && s.vorschlag !== j.aktion && j.aktion ? `<div class="hint">jetzt: ${fmt(s.punkte_jetzt || 0, 0)} Punkte</div>` : "")];
  };
  const pers = (K.personen || []).map(p => `${esc(p.name)} <span class="hint">V ${fmt(p.adm, 0)} / D ${fmt(p.dip, 0)} / M ${fmt(p.mil, 0)}${p.im_kabinett ? ", im Kabinett" : ""}</span>`).join(" · ");
  const top = Object.entries(F.kabinett_punkte || {}).filter(([k]) => ["m", "v", "a"].includes(AK[k]?.status)).sort((a, b) => b[1] - a[1]).slice(0, 8)
    .map(([k, p]) => `${ssSt(AK[k].status)} ${esc(AK[k].n)} <span class="hint">${fmt(p, 0)} P.</span>`).join(" · ");
  const P = S.preise || {}, def = S.defines || {};
  return ssKarte(`${ssLink(S, "cabinet", "Kabinett")} <span class="hint">${fmt((K.plaetze || []).length, 0)} Plätze${num(K.offen) ? `, ${fmt(K.offen, 0)} frei` : ""}</span>`,
    ssTabelle(["Platz", "Jetzt eingestellt", "Vorschlag", "Warum (Spielwerte)", "Bezug zum Schwerpunkt"], (F.kabinett || []).map(zeile))
    + (top ? `<p><b>Beste Aktionen für den Schwerpunkt:</b> ${top}</p>` : "")
    + (pers ? `<p><b>Personen (Daten-Mod):</b> ${pers}</p>` : ""),
    `Wirkung = Grundwert × (1 + Gesamtsteigerung). Gesamtsteigerung laut Spiel = Fähigkeit des Ministers × ${fmt(def.CABINET_ACTION_SKILL_MODIFIER ?? 0.005, 3)}
     (CABINET_ACTION_SKILL_MODIFIER) + Fähigkeit des Herrschers × ${fmt(def.CABINET_ACTION_SKILL_MODIFIER ?? 0.005, 3)} + weitere Posten (Tooltip „Gesamtsteigerung“, z. B. Kronmacht).
     Aktion zuweisen: ${esc(P.set_cabine_action?.text || "–")}; Minister ersetzen: ${esc(P.replace_cabinet_member?.text || "–")} (prices).
     Ob eine Person ins Kabinett darf (Stand, Kabinettsausschluss), prüft das Spiel. ${esc(S.regeln.kabinett)} Quellen: cabinet_actions, Spielstand, Daten-Mod.`);
}

function ssTabelle(kopf, zeilen) {
  return `<div class="ssscroll"><table class="sstab"><thead><tr>${kopf.map(k => `<th class="l">${esc(k)}</th>`).join("")}</tr></thead><tbody>${zeilen.length
    ? zeilen.map(z => `<tr>${z.map(x => `<td class="l">${x}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${kopf.length}" class="empty">keine Einträge</td></tr>`}</tbody></table></div>`;
}

function ssPolitlinien(G, g) {
  const ps = Object.entries(G.pol || {}).sort((a, b) => ((g.alle || {})[b[0]] ?? -1) - ((g.alle || {})[a[0]] ?? -1));
  return `<details class="ssbed"><summary>alle ${ps.length} Politlinien${G.nicht_fuer_uns ? ` <span class="hint">(+${G.nicht_fuer_uns} nicht für uns)</span>` : ""}</summary>
    <ul class="ssliste">${ps.map(([k, p]) => `<li>${ssSt(p.status)} <b>${esc(p.n)}</b>${ssGL(p.wiki)} <span class="hint">${fmt((g.alle || {})[k] ?? 0, 0)} P.${p.dauer ? ` · ${esc(p.dauer)}` : ""}${p.staende?.length ? ` · gutgeheißen von ${esc(p.staende.map(SS_STAND).join(", "))}` : ""}</span>
      <div>${ssWirk(p.w, 5)}</div>${p.status !== "a" ? ssBed(p) : ""}</li>`).join("")}</ul></details>`;
}
// Standesnamen aus der Lokalisierung (Server: stand_namen), gesetzt beim Zeichnen der Kachel
let SS_NAMEN = {};
const SS_STAND = s => SS_NAMEN[s] || s;
const ssWarn = xs => (xs || []).map(w => `<div class="neg">⚠ ${esc(w)}</div>`).join("");

function ssGesetze(S, F) {
  const GS = S.gesetze || {};
  const zeile = g => {
    const G = GS[g.gesetz] || {}, j = G.pol?.[g.jetzt] || {}, v = G.pol?.[g.vorschlag] || {};
    return [`<b>${esc(G.n || g.gesetz)}</b>${ssGL(G.wiki)}`,
      `${esc(j.n || g.jetzt)}${ssGL(j.wiki)}<div class="hint">${fmt(g.punkte_jetzt, 0)} Punkte</div>`,
      (g.abweichung ? `<b>${esc(v.n || g.vorschlag)}</b>${ssGL(v.wiki)} ${ssSt(v.status)}` : `<span class="pos">behalten</span>`) + ssPolitlinien(G, g),
      g.abweichung ? `${ssWirk(v.w)}${ssWarn(g.warnungen)}<div class="hint">${v.dauer ? `voll wirksam nach ${esc(v.dauer)}` : ""}${v.staende?.length ? ` · gutgeheißen von ${esc(v.staende.map(SS_STAND).join(", "))}` : ""}${v.preis ? ` · Preis ${esc(v.preis)}` : ""}</div>${ssBed(v)}` : ssWirk(j.w, 4),
      ssBezug(g.punkte, g.gruende, g.nachteile)];
  };
  const ab = (F.gesetze || []).filter(g => g.abweichung), rest = (F.gesetze || []).filter(g => !g.abweichung);
  const P = S.preise || {};
  return ssKarte(`${ssLink(S, "laws", "Gesetze")} und ${ssLink(S, "policies", "Politlinien")} <span class="hint">${ab.length} Vorschläge</span>`,
    ssTabelle(["Gesetz", "Jetzt eingestellt", "Vorschlag", "Warum (Spielwerte)", "Bezug zum Schwerpunkt"], ab.map(zeile))
    + (rest.length ? `<details class="ssbed"><summary>unverändert – ${rest.length} Gesetze</summary>${ssTabelle(["Gesetz", "Jetzt eingestellt", "Vorschlag", "Wirkung jetzt", "Bezug zum Schwerpunkt"], rest.map(zeile))}</details>` : ""),
    `Kosten laut prices: „${esc(P.set_policy?.name || "")}“ ${esc(P.set_policy?.text || "–")}, „${esc(P.change_policy?.name || "")}“ ${esc(P.change_policy?.text || "–")}
     – welcher Preis beim Wechsel gilt, zeigt das Spiel. „gutgeheißen von“ = estate_preferences der Spieldatei (Wirkung im Spiel nicht beschrieben).
     ${esc(S.regeln.gesetze)} Quellen: laws (Politlinien mit country_modifier, years, potential, allow), advances (unlock_policy), Spielstand.`);
}

function ssPrivilegien(S, F) {
  const PR = S.privilegien || {}, KAT = PR.katalog || {}, ST = Object.fromEntries((PR.staende || []).map(s => [s.stand, s]));
  const zeile = p => {
    const s = ST[p.stand] || {}, v = KAT[p.vorschlag] || {};
    const stand = `<b>${esc(s.name || p.stand)}</b><div class="hint">Zufriedenheit ${pct(s.zufriedenheit, 1)}${num(s.ziel) ? `, Ziel ${pct(s.ziel, 1)}` : ""}${num(s.macht) ? ` · Macht ${pct(s.macht, 1)}` : ""}${num(s.privilegien) ? ` · Privilegien ${fmt(s.privilegien, 0)} von ${fmt(s.moeglich, 0)}` : ""}</div>`
      + (num(s.zufriedenheit) && s.zufriedenheit < 0.5 ? `<div class="neg">unter 50 %</div>` : "");
    const gew = (s.gewaehrt || []).map(k => `${esc(KAT[k]?.n || k)}${ssGL(KAT[k]?.wiki)} <span class="hint">${fmt(p.gewaehrt_punkte?.[k] ?? 0, 0)} P.</span>`).join("<br>") || `<span class="hint">keine</span>`;
    const alle = Object.entries(p.alle || {}).filter(([k]) => k !== p.vorschlag).sort((a, b) => b[1] - a[1]).slice(0, 5)
      .map(([k, n]) => `${ssSt(KAT[k]?.status)} ${esc(KAT[k]?.n || k)} <span class="hint">${fmt(n, 0)} P.</span>`).join(" · ");
    return [stand, gew, (p.vorschlag ? `<b>${esc(v.n)}</b>${ssGL(v.wiki)} ${ssSt(v.status)} gewähren` : `<span class="hint">kein Vorschlag</span>`)
      + (alle ? `<div class="hint">weitere: ${alle}</div>` : ""),
      p.vorschlag ? `${ssWirk(v.w)}${ssWarn(p.warnungen)}${ssBed(v)}` : "–",
      ssBezug(p.punkte, p.gruende, p.nachteile)];
  };
  const P = S.preise || {}, def = S.defines || {};
  const zeilen = (F.privilegien || []).filter(p => p.vorschlag || (ST[p.stand]?.gewaehrt || []).length);
  return ssKarte(`${ssLink(S, "estate_privileges", "Privilegien")} <span class="hint">${(F.privilegien || []).filter(p => p.vorschlag).length} Vorschläge</span>`,
    ssTabelle(["Stand (Werte wie Kachel Stände)", "Jetzt gewährt", "Vorschlag", "Warum (Spielwerte)", "Bezug zum Schwerpunkt"], zeilen.map(zeile)),
    `Gewähren: ${esc(P.grant_privilege?.text || "–")}, entziehen: ${esc(P.revoke_privilege?.text || "–")} (prices). Ein Privileg hebt Macht und Zielzufriedenheit seines Stands
     (Modifikatoren der Spieldatei); weniger Kronmacht folgt aus mehr Standesmacht (Spielhinweis zur Kronmacht). Defines: GRANT_PRIVILEGE_SATISFACTION_IMPACT ${fmt(def.GRANT_PRIVILEGE_SATISFACTION_IMPACT, 2)},
     GRANT_PRIVILEGE_PENALTY_FOR_OTHERS_SCALE ${fmt(def.GRANT_PRIVILEGE_PENALTY_FOR_OTHERS_SCALE, 2)} – Rechenweg im Spielprogramm, nicht nachgerechnet.
     ${esc(S.regeln.privilegien)} Quellen: estate_privileges, Spielstand, Daten-Mod (Zufriedenheit, Ziel, Macht).`);
}

function ssReformen(S, F) {
  const R = S.reformen || {}, KAT = R.katalog || {}, r = F.reform || {}, v = KAT[r.vorschlag] || {};
  const jetzt = (R.jetzt || []).map(k => `${esc(KAT[k]?.n || k)}${ssGL(KAT[k]?.wiki)} <span class="hint">${fmt(r.jetzt_punkte?.[k] ?? 0, 0)} P.</span>`).join("<br>") || "keine";
  const frei = num(R.offen) ? (R.offen ? `<b class="pos">${fmt(R.offen, 0)} frei</b>` : "kein Platz frei") : `<span class="hint">unbekannt (Daten-Mod)</span>`;
  const vor = r.vorschlag ? `${r.abweichung ? "" : `<span class="hint">für den nächsten freien Platz:</span> `}<b>${esc(v.n)}</b>${ssGL(v.wiki)} ${ssSt(v.status)}` : `<span class="hint">kein Vorschlag</span>`;
  const weitere = (r.weitere || []).map(k => `${ssSt(KAT[k]?.status)} ${esc(KAT[k]?.n || k)} <span class="hint">${fmt(r.alle?.[k] ?? 0, 0)} P.</span>`).join(" · ");
  const gesperrt = Object.values(KAT).filter(x => x.status === "g").length;
  return ssKarte(`${ssLink(S, "government_reforms", "Regierungsreformen")} <span class="hint">${frei}</span>`,
    ssTabelle(["Jetzt eingeführt", "Freie Plätze", "Vorschlag", "Warum (Spielwerte)", "Bezug zum Schwerpunkt"],
      [[jetzt, frei, vor + (weitere ? `<div class="hint">weitere: ${weitere}</div>` : ""), r.vorschlag ? `${ssWirk(v.w)}${ssWarn(r.warnungen)}${v.dauer ? `<div class="hint">voll wirksam nach ${esc(v.dauer)}</div>` : ""}${ssBed(v)}` : "–",
        ssBezug(r.punkte, r.gruende, r.nachteile)]]),
    `Freie Plätze: Daten-Mod num_open_reform_slots. Gesellschaftswert-Bedingungen: mindestens ${fmt(S.defines?.SOCIAL_VALUE_REQUIREMENT_FOR_REFORM, 0)} zum Pol
     (SOCIAL_VALUE_REQUIREMENT_FOR_REFORM; Spielhinweis „wird entfernt, weil … unter … gefallen ist“). ${gesperrt} Reformen gesperrt (meist späteres Zeitalter).
     ${esc(S.regeln.reformen)} Quellen: government_reforms (government, age, major, societal_values, potential, allow), advances (unlock_government_reform).`);
}

function ssGesellschaft(S, F) {
  const AX = Object.fromEntries((S.gesellschaft?.achsen || []).map(a => [a.key, a]));
  const liste = xs => xs?.length ? xs.map(x => `${x.status ? ssSt(x.status) + " " : ""}${esc(x.art)} „${esc(x.name)}“ <span class="hint">${esc(x.wert || "")}</span>`).join("<br>") : `<span class="hint">–</span>`;
  const zeile = g => {
    const a = AX[g.achse] || {}, poln = p => p === a.l ? a.ln : p === a.r ? a.rn : p;
    const jetzt = `${fmt(g.wert, 0)} <span class="hint">(${g.pol_jetzt ? `${esc(poln(g.pol_jetzt))} ${fmt(Math.abs(g.wert), 0)}` : "Mitte"})</span>`
      + (num(g.drift) ? `<div class="hint">${sgn(g.drift, 2)}/Monat${g.richtung ? ` → ${esc(poln(g.richtung))}, Grenze ${fmt(g.grenze, 1)}` : ""}</div>` : "")
      + (g.zieht_hin === true ? `<div class="pos">zieht schon dorthin</div>` : g.zieht_hin === false ? `<div class="neg">zieht weg</div>` : "");
    return [`<b>${esc(a.n || g.achse)}</b>${ssGL(a.wiki)}`, jetzt, `<b>${esc(g.pol_name)}</b><div class="hint">${fmt(g.punkte?.l, 0)} : ${fmt(g.punkte?.r, 0)} Punkte (links : rechts)</div>`,
      `${ssWirk(g.seite === "l" ? a.wl : a.wr, 6)}`,                     // Wirkung des günstigen Pols (seite), nicht des jetzigen
      `<div><b>wirkt schon:</b><br>${liste(g.wirkt)}</div><div><b>möglich:</b><br>${liste(g.moeglich)}</div>${g.gegen?.length ? `<div class="neg"><b>zieht weg:</b><br>${liste(g.gegen)}</div>` : ""}`
      + (g.kabinett?.length ? `<div><b>Kabinett:</b> ${g.kabinett.map(k => `„${esc(k.name)}“ (societal_values ${esc(k.wert)})`).join(", ")}</div>` : "")];
  };
  return ssKarte(`${ssLink(S, "societal_values", "Gesellschaftswerte")} <span class="hint">die ${(F.gesellschaft || []).length} wichtigsten für den Schwerpunkt</span>`,
    ssTabelle(["Achse", "Jetzt", "Günstig", "Wirkung des Pols (Spieldatei)", "Was schiebt dorthin"], (F.gesellschaft || []).map(zeile)),
    `Wert −100 (linker Pol) bis +100 (rechter Pol); Verschiebung je Monat = monthly_towards rechts − links (Daten-Mod), Grenze = 100 × Verschiebung (MECHANIK.md).
     Wie stark ein Pol bei Werten unter 100 wirkt, steht nicht in den Dateien – das zeigt das Spiel. ${esc(S.regeln.gesellschaft)} Quellen: societal_values (left/right_modifier),
     Politlinien, Privilegien und Reformen mit monthly_towards_…, Kabinettsaktion „Gesellschaftswerte ändern“.`);
}

function ssBau(S, F) {
  const xs = F.bau || [];
  return ssKarte(`Erste Gebäude <span class="hint">aus dem Bauplan</span>`, xs.length ? ssTabelle(["Nr.", "Was", "Wo", "Warum"],
    xs.map(s => [fmt(s.nr, 0), esc(s.was), esc(s.ort || "–"), esc(s.warum || "")])) + `<p><a href="#wirtschaftsplan">Ganzer Bauplan in der Kachel Wirtschaftsplan</a></p>`
    : `<p class="hint">Kein Bauplan für diesen Schwerpunkt.</p>`, "Übernommen aus dem Bauplan (Wirtschaftsplan) – nicht neu gerechnet; Voraussetzung und Kosten stehen dort.", false);
}

function ssForschung(S, F) {
  const xs = F.forschung || [];
  return ssKarte(`Erste Forschung <span class="hint">aus dem Techbaum-Vorschlag</span>`, F.forschung_fehler ? `<p class="hint">Techbaum: ${esc(F.forschung_fehler)}</p>`
    : xs.length ? ssTabelle(["Fortschritt", "Punkte", "Kosten (Forschung)", "Monate", "Grund"], xs.map(e => [`<a href="#techbaum/${esc(e.key)}">${esc(e.name)}</a>${e.laeuft ? ` <span class="pos">läuft</span>` : ""}`
      + (e.ziel ? `<div class="hint">Ziel – Weg: ${(e.weg || []).map(w => `${esc(w.name)}${w.gesperrt ? ` <span class="neg">(${esc(w.gesperrt)})</span>` : ""}`).join(" → ")}</div>` : ""),
      fmt(e.punkte, 0), num(e.kosten) ? fmt(e.kosten, 2) : "–", num(e.monate) ? fmt(e.monate, 1) : "–", esc(e.grund || "")]))
    : `<p class="hint">Kein Vorschlag (keine jetzt erforschbaren Fortschritte mit Punkten).</p>`,
    "Übernommen aus der Ansicht Fortschritte (gleiche Punkte-Regeln): erst jetzt erforschbare, dann Ziele mit kurzem Weg (Kosten des ganzen Wegs). Monate = Kosten ÷ Forschung je Monat.", false);
}

function ssDiplomatie(S) {
  const D = S.diplomatie || {}, def = S.defines || {}, P = S.preise || {};
  const riv = (D.rivalen || []).map(r => `${esc(r.name)} <span class="hint">(ihre Meinung ${fmt(r.meinung_sie, 0)})</span>`).join(", ") || "keine";
  const rk = (D.rivalen_kandidaten || []).map(r => `${esc(r.name)} <span class="hint">${r.kb_gegen_uns ? "Kriegsgrund gegen uns, " : ""}ihre Meinung ${fmt(r.meinung_sie, 0)}</span>`).join(", ");
  const rr = Object.entries(D.rivalen_regeln || {}).map(([t, r]) => `${esc(r.n)}: ${r.enabled ? "eigene Bedingung, wer es als Rivalen wählen darf" : ""}${r.enabled && r.ai_rule ? "; " : ""}${r.ai_rule ? "Regel nur für die KI" : ""}`).join(" · ");
  const hf = D.heirat_faktoren || {};
  const HF = { opinion: "Meinung", heir: "Erbe", trust_in_actor: "Vertrauen in uns", same_culture: "gleiche Kultur", different_culture: "andere Kultur",
    different_religion: "andere Religion", different_religion_group: "andere Religionsgruppe", same_court_language: "gleiche Hofsprache",
    actor_is_rival: "Anfragender ist Rivale", recipient_is_rival: "Angefragter ist Rivale", actor_overlord_is_rival: "Oberherr des Anfragenden ist Rivale",
    recipient_overlord_is_rival: "Oberherr des Angefragten ist Rivale", rank_difference: "Rangunterschied", border_distance: "Grenzabstand",
    age_female: "Alter (Frau)", marriage_desirability: "Heiratswert", culture_view: "Kulturansicht", religion_view: "Religionsansicht", union_size: "Größe der Union" };
  const heirat = (D.heirat || []).map(h => `${esc(h.name)} <span class="hint">(ihre Meinung ${fmt(h.meinung_sie, 0)}${num(h.vertrauen) ? `, Vertrauen ${fmt(h.vertrauen, 0)}` : ""}${h.rivale ? ", Rivale" : ""})</span>`).join(", ");
  const rows = [
    ["Rivalen", `${num(D.rivalen_zahl) ? `${fmt(D.rivalen_zahl, 0)} von ${fmt(D.rivalen_moeglich, 0)}: ` : ""}${riv}`],
    D.rivale_vorschlag && ["Vorschlag", `<b>${esc(D.rivale_vorschlag.text)}</b> <span class="hint">${esc(D.rivale_vorschlag.warum)}</span>`],
    rk && ["Kandidaten", rk],
    ["Regeln des Spiels", `unsere Meinung von ihnen unter ${fmt(def.RIVAL_OPINION_THRESHOLD, 0)} (RIVAL_OPINION_THRESHOLD), in Diplomatiereichweite, ähnlicher Großmachtwert (Spielbegriff Rivale);
      ersetzen ${esc(P.replace_rival?.text || "–")}; entfernen frühestens nach ${fmt(def.REMOVE_RIVAL_COOLDOWN, 0)} Monaten (REMOVE_RIVAL_COOLDOWN)${rr ? `. Sonderregeln (rival_criteria): ${rr}` : ""}`],
    ["Diplomaten", num(D.diplomaten?.jetzt) ? `${fmt(D.diplomaten.jetzt, 2)} von ${fmt(D.diplomaten.max, 0)} <span class="hint">(Daten-Mod)</span>` : "–"],
    ["Diplomatiekapazität", num(D.kapazitaet?.max) ? `${fmt(D.kapazitaet.benutzt, 2)} von ${fmt(D.kapazitaet.max, 2)} benutzt` : "–"],
    [`Beziehungen verbessern`, (D.beziehungen_laufend || []).length ? `${D.beziehungen_laufend.length} laufen (seit ${D.beziehungen_laufend.map(b => esc(b.seit)).join(", ")}${D.beziehungen_laufend.some(b => b.automatisch) ? "; automatisch gestartet" : ""})` : "keine laufen"],
    ["Heirat", `${heirat ? `Kandidaten wie Bündnis: ${heirat}<br>` : ""}<span class="hint">Faktoren der KI laut ai_diplochance (royal_marriage): ${Object.entries(hf).map(([k, v]) => `${esc(HF[k] || k)} ${sgn(v, Math.abs(v) < 1 ? 3 : 0)}`).join(", ")}.
      Bedeutung nach dem Schlüsselnamen; Schwelle und Grundwert stehen dort nicht – die Annahmechance zeigt das Spiel.</span>`],
  ];
  return ssKarte(`Diplomatie <span class="hint">${ssLink(S, "rivals", "Rivalen")} · ${ssLink(S, "diplomats", "Diplomaten")} · ${ssLink(S, "royal_marriage", "Staatsehe")}</span>`,
    kv(rows.filter(Boolean)), `Unabhängig vom Schwerpunkt. ${esc(S.regeln.rivalen)} Quellen: Daten-Mod (Rivalen, Meinungen, Diplomaten), Spielstand (Beziehungsverbesserungen), defines, prices, rival_criteria, ai_diplochance.`, false);
}

function ssBuendnis(S) {
  const D = S.diplomatie || {}, K = D.kandidaten || [], W = D.wir || {};
  const KI = { base: "Grundwert", actor_is_rival: "Anfragender ist Rivale", actor_overlord_is_rival: "Oberherr des Anfragenden ist Rivale",
    trust_in_actor: "Vertrauen in uns", positive_opinion: "positive Meinung", negative_opinion: "negative Meinung", border_distance: "Grenzabstand",
    few_relations: "wenige Beziehungen", same_court_language: "gleiche Hofsprache", royal_ties: "königliche Bande", strategic_interest: "strategisches Interesse",
    common_threat: "gemeinsame Bedrohung", relative_strength: "Stärkeverhältnis", threatening_rivals: "bedrohliche Rivalen" };
  const ki = Object.entries(D.ki_faktoren || {}).map(([k, v]) => `${esc(KI[k] || k)} ${sgn(v, Math.abs(v) < 1 ? 2 : 0)}`).join(", ");
  const bed = k => k.bedingungen.map(b => `${ssOk(b.ok)} ${esc(b.text)}${b.ist ? ` <span class="hint">(${esc(b.ist)})</span>` : ""}`).join("<br>");
  const zeile = k => [`<b>${esc(k.name)}</b><div class="hint">${esc(k.beziehungen.join(", "))}</div>`, bed(k),
    `${num(k.staerke) ? fmt(k.staerke, 2) : "–"}${num(k.gewinn) ? `<div class="hint">${pct(k.gewinn, 0)} unseres Verteidigungsbündnisses</div>` : ""}${k.schutz ? `<div class="pos">Schutz: sie haben einen Kriegsgrund gegen uns</div>` : ""}`,
    num(k.unterhalt) ? `${fmt(k.unterhalt, 2)}<div class="hint">${k.unterhalt_teile.map(esc).join("; ")}</div>` : `<span class="hint">${esc((k.unterhalt_teile || []).join("; ") || "–")}</span>`,
    k.besser_nicht.length ? `<div class="neg">${k.besser_nicht.map(esc).join("<br>")}</div>` : (D.vorschlaege || []).includes(k.tag) ? `<span class="pos">Kandidat</span>` : ""];
  const gut = K.filter(k => !k.besser_nicht.length), nicht = K.filter(k => k.besser_nicht.length);
  const bv = D.buendnis_vorschlag;
  return ssKarte(`${ssLink(S, "alliance", "Bündnisvorschläge")} <span class="hint">${D.verbuendete_namen?.length ? `verbündet: ${esc(D.verbuendete_namen.join(", "))}` : "keine Verbündeten"}</span>`,
    (bv ? `<p><b>Vorschlag:</b> ${esc(bv.text)} <span class="hint">${esc(bv.warum)}${bv.kosten ? ` · ${esc(bv.kosten)}` : ""}</span></p>` : `<p class="hint">Kein Bündnisvorschlag.</p>`)
    + `<p class="hint">Unser Verteidigungsbündnis ${fmt(W.verteidigung, 2)}, Offensivbündnis ${fmt(W.angriff, 2)}, Landesstärke ${fmt(W.staerke, 2)} (Daten-Mod); freie Diplomatiekapazität ${fmt(D.kapazitaet?.frei, 2)}.</p>`
    + ssTabelle(["Land", "Bedingungen (alliance_can_exist)", "Stärke", "Unterhalt (Diplomatiekapazität)", "Hinweis"], gut.map(zeile))
    + (nicht.length ? `<h5>Besser nicht</h5>${ssTabelle(["Land", "Bedingungen", "Stärke", "Unterhalt", "Warum nicht"], nicht.map(zeile))}` : "")
    + ((D.fern || []).length ? `<p class="hint">Ferne Großmächte (nur Beziehung „Großmacht“, Diplomatiereichweite unbekannt – nicht bewertet): ${D.fern.map(f => esc(f.name)).join(", ")}</p>` : ""),
    `Bedingungen laut scripted_triggers alliance_can_exist: ${(D.regeln || []).map(r => esc(r[1])).join("; ")}. Geprüft werden die Meinungen und die Rivalität (Daten-Mod); den Rest prüft das Spiel.
     Ein Bündnis verbietet den Krieg miteinander (disallow_war = ${esc(D.felder?.disallow_war || "?")}), beide können sich in Kriege rufen und zahlen Diplomatiekapazität
     (alliance_upkeep_cost, script_values). Im Krieg kein Bündnis anbieten (block_when_at_war = ${esc(D.felder?.block_when_at_war || "?")}).
     Ob die KI annimmt – Faktoren laut scripted_relations alliance (wants_to_give_diplo_chance): ${ki || "–"}; dazu weitere Posten (wants_to_give).
     Grenzabstand, Stärkeverhältnis, Bedrohungen und diese Posten kennt der Ratgeber nicht – die Annahmechance zeigt das Diplomatiefenster.
     Gemeinsame Gegner: Rivalen anderer Länder liefern Spielstand-Auszug und Daten-Mod nicht – nicht bewertet.
     Die Reihung ist eine ${esc(S.regeln.buendnis)} Siehe auch <a href="#nachbarn">Nachbarn und Kriegsgelegenheiten</a> und <a href="#gruendung">Ländergründung</a>.`);
}

function ssPunkte(S, F) {
  return `<p class="hint">Punkte (Regel des Ratgebers) für „${esc(F.name)}“${F.thema ? `, Themenliste „${esc(F.thema)}“` : ""}: ${Object.values(S.punkte || {}).map(esc).join("; ")}.
    Status: ● jetzt eingestellt · ✓ alle Bedingungen erfüllt · ? Bedingung offen (im Spiel prüfen) · ✗ gesperrt. Vorgeschlagen wird nur, was sichtbar ist
    (Bedingung „potential“ erfüllt) und eine direkte Wirkung hat – allein für das Verschieben eines Gesellschaftswerts nicht.</p>`;
}

function ssSetzen(fk) {
  store.set("rg_wp_fokus", fk);                 // gleicher Schlüssel wie Wirtschaftsplan und Techbaum
  if (!LAST_D) return;
  const y = window.scrollY;
  render(LAST_D);
  if (typeof equalizeTiles === "function") equalizeTiles();
  window.scrollTo(0, y);
}
document.addEventListener("change", e => { if (e.target.id === "ss-fokus") ssSetzen(e.target.value); });
