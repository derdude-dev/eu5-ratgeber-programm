"use strict";
// EU5 Ratgeber - Seite. Daten: /api/partien, /api/daten?partie=… (history.series), Markierungen per POST.

const $ = (s, el = document) => el.querySelector(s);
const nf = (d = 1) => new Intl.NumberFormat("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });
const fmt = (v, d = 1) => (v === null || v === undefined || typeof v !== "number" || Number.isNaN(v)) ? "–" : nf(d).format(v);
const pct = (v, d = 0) => (typeof v !== "number") ? "–" : nf(d).format(v * 100) + " %";
const sgn = (v, d = 1) => (typeof v !== "number") ? "–" : (v > 0 ? "+" : "") + nf(d).format(v);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
// Addiert mit Ausgleich der Rundungsfehler wie Pythons sum(): Spielwerte haben drei Nachkommastellen, einfach addiert wurde aus 3,685 sonst
// 3,6849999… und die Seite zeigte 3,68, die Seitenleiste 3,69 (Neumaier, Test 07.11.).
const sum = a => {
  let s = 0, c = 0;
  for (const v of a) {
    if (typeof v !== "number") continue;
    const t = s + v;
    c += Math.abs(s) >= Math.abs(v) ? (s - t) + v : (v - t) + s;
    s = t;
  }
  return s + c;
};
const avg = a => { const n = a.filter(v => typeof v === "number"); return n.length ? sum(n) / n.length : null; };
const ESTATE_COLOR = { crown_estate: "--c1", nobles_estate: "--c2", clergy_estate: "--c6", burghers_estate: "--c4",
                       peasants_estate: "--c3", dhimmi_estate: "--c7", tribes_estate: "--c5", cossacks_estate: "--c8" };
const PALETTE = ["--c2", "--c1", "--c3", "--c4", "--c6", "--c7"];     // --c5 = eigenes Land, --c8 = übrige
const monthX = k => { const [y, m] = k.split(".").map(Number); return y + (m - 1) / 12; };
const xLabel = x => { const y = Math.floor(x + 1e-6), m = Math.round((x - y) * 12) + 1; return m === 1 ? String(y) : `${String(m).padStart(2, "0")}/${y}`; };
const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
                set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };

// ---------------------------------------------------------------- Bausteine
function niceTicks(min, max, n = 5) {
  if (min === max) { min -= 1; max += 1; }
  const step = Math.pow(10, Math.floor(Math.log10((max - min) / n)));
  const err = (max - min) / n / step;
  const s = step * (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1);
  const out = [];
  for (let v = Math.ceil(min / s) * s; v <= max + s * 1e-9; v += s) out.push(+v.toFixed(10));
  return out;
}

function lineChart(series, { marks = [], yFmt = v => fmt(v, 0), xFmt = xLabel, zero = false } = {}) {
  const W = 640, H = 230, L = 52, R = 12, T = 10, B = 26;
  const pts = series.flatMap(s => s.points);
  if (!pts.length) return `<div class="empty">Noch keine Daten</div>`;
  let x0 = Math.min(...pts.map(p => p[0])), x1 = Math.max(...pts.map(p => p[0]));
  if (x0 === x1) { x0 -= 0.5; x1 += 0.5; }
  let y0 = Math.min(...pts.map(p => p[1])), y1 = Math.max(...pts.map(p => p[1]));
  if (zero) { y0 = Math.min(0, y0); y1 = Math.max(0, y1); }
  const yt = niceTicks(y0, y1); y0 = Math.min(y0, yt[0]); y1 = Math.max(y1, yt[yt.length - 1]);
  const sx = x => L + (x - x0) / (x1 - x0) * (W - L - R);
  const sy = y => T + (1 - (y - y0) / ((y1 - y0) || 1)) * (H - T - B);
  let g = yt.map(v => `<line class="grid" x1="${L}" x2="${W - R}" y1="${sy(v)}" y2="${sy(v)}"/><text x="${L - 6}" y="${sy(v) + 4}" text-anchor="end">${yFmt(v)}</text>`).join("");
  g += niceTicks(x0, x1, 6).filter(v => v >= x0 && v <= x1).map(v => `<text x="${sx(v)}" y="${H - 8}" text-anchor="middle">${esc(xFmt(v))}</text>`).join("");
  g += marks.filter(m => m.jahr >= x0 && m.jahr <= x1).map(m =>
    `<line x1="${sx(m.jahr)}" x2="${sx(m.jahr)}" y1="${T}" y2="${H - B}" stroke="${css("--accent")}" stroke-dasharray="4 3"><title>${esc(m.datum)}: ${esc(m.text)}</title></line>`).join("");
  for (const s of series) {
    const c = css(s.color), p = s.points.slice().sort((a, b) => a[0] - b[0]);
    if (p.length > 1) g += `<polyline fill="none" stroke="${c}" stroke-width="${s.dash ? 1.5 : 2}"${s.dash ? ' stroke-dasharray="5 4" opacity=".75"' : ""} points="${p.map(q => `${sx(q[0])},${sy(q[1])}`).join(" ")}"/>`;
    if (!s.dash) g += p.map(q => `<circle cx="${sx(q[0])}" cy="${sy(q[1])}" r="${p.length > 40 ? 1.5 : 3}" fill="${c}"><title>${esc(s.name)} ${esc(xFmt(q[0]))}: ${yFmt(q[1])}</title></circle>`).join("");
  }
  const legend = series.filter(s => s.points.length).map(s => `<span><i style="background:${s.dash ? `repeating-linear-gradient(90deg, ${css(s.color)} 0 3px, transparent 3px 5px)` : css(s.color)}"></i>${esc(s.name)}</span>`).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${g}</svg><div class="legend">${legend}</div>`;
}

function pieChart(items, { size = 180, fmtV = v => pct(v, 1), legend: showLegend = true } = {}) {
  const tot = sum(items.map(i => i.value)); if (!tot) return `<div class="empty">Keine Werte</div>`;
  const r = size / 2 - 4, c = size / 2, ri = r * 0.55;
  let a = -Math.PI / 2, g = "";
  for (const it of items) {
    const frac = it.value / tot; if (frac <= 0) continue;
    const a2 = a + frac * 2 * Math.PI, large = frac > 0.5 ? 1 : 0;
    const p = (ang, rad) => `${c + rad * Math.cos(ang)},${c + rad * Math.sin(ang)}`;
    const d = frac >= 0.9999 ? `M ${p(0, r)} A ${r} ${r} 0 1 1 ${p(Math.PI, r)} A ${r} ${r} 0 1 1 ${p(0, r)} Z`
      : `M ${p(a, r)} A ${r} ${r} 0 ${large} 1 ${p(a2, r)} L ${p(a2, ri)} A ${ri} ${ri} 0 ${large} 0 ${p(a, ri)} Z`;
    g += `<path d="${d}" fill="${css(it.color)}"><title>${esc(it.label)}: ${fmtV(it.value / tot)}</title></path>`;
    a = a2;
  }
  const svg = `<svg class="pie" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${g}</svg>`;
  if (!showLegend) return svg;
  const legend = items.filter(i => i.value > 0).map(i => `<span><i style="background:${css(i.color)}"></i>${esc(i.label)} ${fmtV(i.value / tot)}</span>`).join("");
  return `<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">${svg}<div class="legend" style="flex-direction:column">${legend}</div></div>`;
}

// Kennzahl im Kachelkopf (auch zugeklappt sichtbar)
const mk = (label, value, { big = false, cls = "", title = "" } = {}) =>
  `<span class="mk${big ? " big" : ""}"${title ? ` title="${esc(title)}"` : ""}><small>${esc(label)}</small><b class="${cls}">${value}</b></span>`;
const dlt = (cur, prev, d = 1, good = 1) => (typeof cur === "number" && typeof prev === "number")
  ? ` <i class="${(cur - prev) * good > 0 ? "pos" : (cur - prev) * good < 0 ? "neg" : ""}">${sgn(cur - prev, d)}</i>` : "";
const posneg = v => typeof v === "number" ? (v < 0 ? "neg" : v > 0 ? "pos" : "") : "";

// Zusammensetzung als Balken: [{l, v, sub?, c?, st?}], Anteil an total; st = Zusatz klein hinter dem Namen (HTML)
function compo(rows, total, d = 2) {
  const max = Math.max(...rows.map(r => Math.abs(r.v || 0)), 1e-9);
  return `<div class="compo">${rows.map(r => `<span class="${r.sub ? "subl" : ""}">${esc(r.l)}${r.st ? ` <span class="st">${r.st}</span>` : ""}</span>
    <div class="bar1"><i style="width:${(Math.abs(r.v || 0) / max * 100).toFixed(1)}%;background:var(${r.c || (r.sub ? "--line" : "--accent")})"></i></div>
    <span class="v ${r.v < 0 ? "neg" : ""}">${fmt(r.v, d)}</span><span class="v hint0">${total && !r.sub ? pct(r.v / total, 0) : ""}</span>`).join("")}</div>`;
}

// Rohtext einer Oberflächen-Aufschlüsselung (Mod 0.11, RG1I) - Steuerzeichen raus, sonst unverändert
const rawText = t => esc(String(t || "").replace(/[\x00-\x08\x0b-\x1f]/g, ""));

function table(cols, rows, { scroll = true } = {}) {
  const head = cols.map(c => `<th class="${c.l ? "l" : ""}">${esc(c.t)}</th>`).join("");
  const body = rows.map(r => `<tr>${cols.map(c => `<td class="${[c.l ? "l" : "", c.cls ? c.cls(r) : ""].join(" ")}">${c.f(r)}</td>`).join("")}</tr>`).join("");
  const t = `<table><thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${cols.length}" class="empty">keine Einträge</td></tr>`}</tbody></table>`;
  return scroll ? `<div class="scroll">${t}</div>` : t;
}
const kv = rows => `<div class="kv">${rows.filter(r => r).map(([k, v]) => `<span>${esc(k)}</span><span>${v}</span>`).join("")}</div>`;
// Mod 0.16: Aufschlüsselung eines Landes-Modifikators wie in den Fenstern des Spiels (Country.GetDescriptionFor('<mod>'),
// Text land <TAG> desc_<mod>) und sein Wert (Daten-Mod landmod)
const modDesc = (d, m) => (Object.values(d.alles?.texte?.land || {})[0] || {})["desc_" + m] || "";
const modWert = (d, m) => (Object.values(d.alles?.werte?.landmod || {})[0] || {})[m];
// Zeile mit Wert; mit Text klappt die Aufschlüsselung darunter auf (Darstellung wie breakdown)
const zeileAuf = (l, v, txt, code = "") => txt
  ? `<details class="bk"><summary${code ? ` title="Aufschlüsselung des Spiels: ${esc(code)}"` : ""}><span class="bl">${l}</span><span class="bv">${v}</span></summary><div class="bsub">${breakdown(txt)}</div></details>`
  : `<div class="bk"><span class="bl">${l}</span><span class="bv">${v}</span></div>`;
// Militärfenster (Mod 0.16): [Bezeichnung, Modifikator, Format] – Wert als Landeswert mod_<x>
const MIL_016 = [["Disziplin", "discipline", "%"], ["Kampf-Effizienz (Aufgebote)", "levy_combat_efficiency_modifier", "%"],
  ["Militärtaktiken", "military_tactics", 2], ["Belagerungsfähigkeit", "siege_ability", "%"]];
// Handel: Landes-Modifikatoren mit Aufschlüsselung (Mod 0.16)
function handelModKarte(d) {
  const rows = [["Handelskapazität", "global_merchant_capacity_modifier"], ["Handelsvorteil", "global_merchant_power"],
    ["Marktanziehung", "global_trade_center_power"], ["Handelseinnahmen", "trade_income"]].filter(([, m]) => num(modWert(d, m)) || modDesc(d, m));
  if (!rows.length) return "";
  return `<div class="card"><h3>Handel – Modifikatoren des Landes</h3><div class="brk">${rows.map(([l, m]) =>
      zeileAuf(l, num(modWert(d, m)) ? `${sgn(modWert(d, m) * 100, 1)} %` : "–", modDesc(d, m), `GetDescriptionFor('${m}')`)).join("")}</div>
    <p class="hint">Landes-Modifikatoren mit der Aufschlüsselung des Spiels (Daten-Mod ab 0.16). Die „Handelskapazität +7,90 %“ im Marktfenster
      ist ein anderer Wert als der Landes-Modifikator – noch offen.</p></div>`;
}

function kpi(label, cur, prev, d = 1, good = +1, extra = "") {
  let delta = "";
  if (typeof prev === "number" && typeof cur === "number") {
    const diff = cur - prev, cls = diff * good > 0 ? "pos" : diff * good < 0 ? "neg" : "";
    delta = `<div class="delta ${cls}">${diff >= 0 ? "+" : ""}${fmt(diff, d)} ${extra || "seit letztem Stand"}</div>`;
  }
  return `<div class="kpi"><div class="label">${label}</div><div class="value">${fmt(cur, d)}</div>${delta}</div>`;
}

// Auf-/Zugeklappt merken: Abschnitte dauerhaft (localStorage), alles andere bis zum Neuladen der Seite.
const OPEN = (() => { try { return JSON.parse(store.get("rg_offen") || "{}"); } catch (e) { return {}; } })();
const isOpen = (k, dflt) => k in OPEN ? OPEN[k] : dflt;
const openAttr = (k, dflt) => `data-k="${esc(k)}" ${isOpen(k, dflt) ? "open" : ""}`;
function rememberToggles(root) {
  root.querySelectorAll("details[data-k] > summary").forEach(s => s.addEventListener("click", ev => {
    if (ev.target.closest("button, input, a")) return;
    const el = s.parentElement;
    OPEN[el.dataset.k] = !el.open;              // Klick schaltet gleich um
    store.set("rg_offen", JSON.stringify(Object.fromEntries(Object.entries(OPEN).filter(([k]) => k.startsWith("sec:")))));
  }));
}

// Abschnitt = Kachel: Kopf mit den wichtigsten Werten ist immer sichtbar, Klick klappt die Details auf
// (aufgeklappt über die ganze Breite). part = {head, body} oder nur body; {head, lazy: () => body} baut den Inhalt
// erst beim Öffnen (Kacheln je Ort - bei großen Ländern Hunderte).
const SECTIONS = [];
function sec(id, title, part, { open = false, sub = "" } = {}) {
  let { head = "", body = "", lazy: lz } = typeof part === "string" ? { body: part } : (part || {});
  if (lz && typeof LAZY !== "undefined") { LAZY.set("sec:" + id, lz); body = `<div class="lazyc" data-lzsec="${esc(id)}"></div>`; }
  if (!body && !head) return "";
  SECTIONS.push([id, title]);
  const th = (typeof THEME !== "undefined" && THEME[id]) || {};       // design.js: Symbol und Farbe je Thema
  return `<details class="sec" id="${id}" style="--th: var(${th.color || "--line"})" ${openAttr("sec:" + id, open)}><summary><div class="st">${th.icon ? `<span class="ic">${th.icon}</span>` : ""}${esc(title)}${sub ? `<span class="sub">${sub}</span>` : ""}</div>${head ? `<div class="head">${head}</div>` : ""}</summary><div class="body">${body || `<div class="empty">keine Details</div>`}</div></details>`;
}

// ---------------------------------------------------------------- Daten zusammenführen
function prepare(d) {
  const LD = d.live_details || {}, W = d.wissen || {}, A = d.aktuell || {};
  const lv = (d.live || []).at(-1) || {};
  const liveOrt = Object.fromEntries((LD.orte || []).map(o => [o.id, o]));
  const livePops = Object.fromEntries((LD.pops || []).map(p => [p.id, p]));
  const liveGeb = LD.gebaeude || [], saveGeb = A.gebaeude || [];
  const useLiveGeb = liveGeb.length > 0;
  const gebNach = {};
  for (const b of (useLiveGeb ? liveGeb : saveGeb)) {
    const e = useLiveGeb ? { id: b.id, typ: b.typ, name: b.name, stufe: b.level, gewinn: b.profit, moeglich: b.potential_profit,
                             besch: b.employed, plaetze: b.employment_size, ort_id: b.ort_id, ort: b.ort }
                         : { id: b.id, typ: b.typ, name: b.name, stufe: b.stufe, gewinn: b.gewinn, ort_id: b.ort_id, ort: b.ort };
    (gebNach[e.ort_id] ??= []).push(e);
  }
  const pn = d.pop_namen || {};
  const orte = (A.orte || []).map(o => {
    const L = liveOrt[o.id] || {}, w = (W.orte || {})[o.id] || {};
    let pops;
    const P = livePops[o.id];
    if (P) pops = Object.keys(pn).filter(t => (P["size_" + t] ?? 0) > 0).map(t => ({ typ: pn[t] || t, groesse: P["size_" + t],
      zufr: P["satw_" + t] / P["size_" + t], bildung: P["litw_" + t] / P["size_" + t] }));
    else pops = Object.entries(o.pops_typen || {}).map(([t, v]) => ({ typ: pn[t] || t, groesse: v.groesse, zufr: v.zufriedenheit, bildung: v.bildung }));
    return { ...o, L, w, pops: pops.sort((a, b) => b.groesse - a.groesse), gebaeude: gebNach[o.id] || [],
             bev: L.population ?? sum(pops.map(p => p.groesse)) };
  });
  return { LD, W, A, lv, orte, useLiveGeb, allGeb: Object.values(gebNach).flat() };
}

// ---------------------------------------------------------------- Abschnitte
const RES = { gold: "Gold", stability: "Stabilität", prestige: "Prestige", inflation: "Inflation", war_exhaustion: "Kriegsmüdigkeit",
              manpower: "Manpower", sailors: "Seeleute", government_power: "Regierungsmacht", army_tradition: "Heerestradition",
              navy_tradition: "Marinetradition", religious_influence: "Religiöser Einfluss" };
function finanzen(d, P) {
  const pts = d.punkte, last = pts.at(-1), prev = pts.length > 1 ? pts.at(-2) : null;
  const w = P.A.wirtschaft || {}, lm = w.letzter_monat || {}, lv = P.lv;
  const liveNewer = lv.jahr && lv.jahr > last.jahr, L2 = (d.live || []).at(-2) || {};
  const gold = liveNewer ? lv.gold : last.gold, goldPrev = liveNewer ? (L2.gold ?? last.gold) : prev?.gold;
  const F = (P.LD.finanzen || [])[0];                                   // ab Mod 0.11
  const num = v => typeof v === "number";
  // Einnahmen: Steuern (aufgeteilt nach Ständen: estate.last_month.paid_taxes), Handel, Rest.
  // last_months_subject_tax fehlt bewusst: kein Einkommen (Frankreich 426,6 bei 32,8 Gesamt), ~ Steuerbasis der Untertanen.
  const estTax = (P.A.staende || []).filter(e => num(e.letzter_monat?.paid_taxes) && e.letzter_monat.paid_taxes > 0)
    .map(e => ({ l: e.name, v: e.letzter_monat.paid_taxes, sub: true, c: ESTATE_COLOR[e.stand] }));
  const withRest = (total, rows) => num(total) ? [...rows, { l: "übrige (Differenz zur Summe)", v: total - sum(rows.filter(r => !r.sub).map(r => r.v)), c: "--c8" }] : rows;
  const TL = Object.values(d.alles?.texte?.land || {})[0] || {}, TE = Object.values(d.alles?.texte?.eco || {})[0] || {};
  // weitere Einnahmen laut Spiel (Einkommens-Tooltip, Daten-Mod): oberste Zeilen außer Steuern und Handel (die aus dem Spielstand).
  // Holland 1341.7: Münzprägung 1,53 + Diplomatie 0,10 + Nahrung 0,03 = 1,66 bei 1,68 „übrige“ vorher (geprüft 29.09.)
  const einMod = String(TL.GetIncomeTooltip || "").split("\n").filter(z => !/^\s/.test(z))
    .map(z => z.match(/^(.+?):\s*([+-]?\d+(?:\.\d+)?)\s*$/)).filter(Boolean)
    .map(([, l, v]) => ({ l: l.trim(), v: parseFloat(v), c: "--c7" })).filter(r => r.v && !/steuer|tax|handel|trade/i.test(r.l))
    .sort((a, b) => b.v - a.v);
  // Mit Daten-Mod: Einnahmen wie im Wirtschaftsfenster (Nutzerwunsch 29.09.) – Steuern je Stand live (tax_<stand>),
  // Handelseinnahmen = Gewinn × Modifikator, übrige Posten aus dem Einkommens-Tooltip, Summe = GetIncomeValue; Spielstand klein daneben.
  const S = spielWerte(d);
  const stName = Object.fromEntries((P.A.staende || []).map(e => [e.stand, e.name]));
  const liveTax = Object.keys(lv).filter(k => /^tax_\w+_estate$/.test(k) && lv[k] > 0)
    .map(k => ({ l: stName[k.slice(4)] || k.slice(4), v: lv[k], sub: true, c: ESTATE_COLOR[k.slice(4)] }));
  const sp = v => num(v) ? `Spielstand ${fmt(v, 2)}` : "";
  const ein = S
    ? withRest(S.ein, [
        ...(liveTax.length ? [{ l: "Steuern", v: sum(liveTax.map(r => r.v)), c: "--c3", st: sp(lm.last_months_tax_income) }, ...liveTax] : []),
        ...(num(S.handel) ? [{ l: "Handelseinnahmen", v: S.handel, c: "--c2", st: sp(lm.monthly_trade_balance) }] : []), ...einMod])
    : withRest(w.einkommen, [
        ...(num(lm.last_months_tax_income) ? [{ l: "Steuern", v: lm.last_months_tax_income, c: "--c3" }, ...estTax] : []),
        ...(num(lm.monthly_trade_balance) ? [{ l: "Handel (Saldo)", v: lm.monthly_trade_balance, c: "--c2" }] : []), ...einMod]);
  const einT = S ? S.ein : w.einkommen, ausT = S ? S.aus : w.ausgaben, saldoT = S ? S.saldo : last.saldo;
  // Ausgaben je Posten: mit Daten-Mod die Kosten je Regler laut Spiel (ki_*), sonst die Felder des Spielstands.
  // Der Spielstand führt Flotte/Festungen ohne Reglerstellung (navy 0,717 × Regler 50 % ≈ Mod 0,357) und Hof, Diplomatie,
  // Nahrung gar nicht; Summe der Reglerkosten + Seeleute = 3,990 bei 3,9996 im Spielstand (geprüft 29.09., Holland 1341.7).
  const REG_AUS = [["army", "Heer"], ["navy", "Flotte"], ["fort", "Festungen"], ["court", "Hof"], ["diplomatic", "Diplomatie"],
    ["cultural", "Kultur"], ["colonial", "Kolonien"], ["exploration", "Erkundung"], ["food", "Nahrung"], ["upkeep", "Gebäude-Unterhalt"],
    ["bureaucracy", "Bürokratie"]];
  const aland = Object.values(d.alles?.werte?.land || {})[0] || {};
  // Regler und Ausgaben zusammen (Nutzerwunsch 29.09.): je Posten Kosten, Anteil und Reglerstellung
  const regSt = k => {
    if (F["p_" + k] == null) return "";
    const ki = F["ki_" + k], k0 = F["k_" + k];                       // Kosten mit / ohne Info-Funktion; nur zeigen, wenn verschieden
    return `Regler ${pct(F["p_" + k], 0)}${num(ki) && num(k0) && Math.abs(Math.abs(ki) - Math.abs(k0)) > 0.005 ? ` · ohne Info ${fmt(k0, 2)}` : ""}`;
  };
  const SAVE_REG = { Heer: "ArmyMaintenance", Flotte: "NavyMaintenance", Festungen: "FortMaintenance", Gebäude: "UpkeepMaintenance" };
  const ausRows = F
    ? [...REG_AUS.map(([k, l]) => ({ l, v: Math.abs(F["ki_" + k] ?? F["k_" + k] ?? 0), st: regSt(k) })),
       { l: "Söldner", v: lm.last_months_mercenary_maintenance }, { l: "Seeleute", v: lm.last_months_sailor_expense },
       { l: "Stabilitäts-Investition", v: aland.eco_GetStabilityInvestmentExpense }].filter(x => num(x.v)).sort((a, b) => b.v - a.v)   // alle Regler, auch bei 0
    : [["Heer", lm.last_months_army_maintenance], ["Söldner", lm.last_months_mercenary_maintenance], ["Flotte", lm.last_months_navy_maintenance],
       ["Seeleute", lm.last_months_sailor_expense], ["Festungen", lm.last_months_fort_maintenance],
       ["Gebäude", lm.last_months_building_maintenance]].filter(x => num(x[1]))
       .map(([l, v]) => ({ l, v, st: SAVE_REG[l] && num((w.unterhalt_regler || {})[SAVE_REG[l]]) ? `Regler ${pct(w.unterhalt_regler[SAVE_REG[l]], 0)}` : "" }));
  const aus = withRest(ausT, ausRows.map(r => ({ ...r, c: "--c5" })));
  // Aufschlüsselungen einzelner Posten laut Spiel (Daten-Mod), aufklappbar unter den Ausgaben
  const ausTexte = [["Hof – Kosten", TL.GetCourtSpendingCostDetails], ["Flotte – Kosten je Schiff", TL.GetNavyCostsByDefinition],
    ["Heer – Kosten je Einheit", TL.GetArmyCostsByDefinition], ["Gebäude-Unterhalt – Güterkosten", TL.GetBuildingUpkeepGoodsCostInfo],
    ["Stabilitäts-Investition", TE.GetStabilityInvestmentExpenseInfo]].filter(([, t]) => t);
  // ohne Daten-Mod: Stellung aller Regler aus dem Spielstand (Kosten führt er nur für Heer, Flotte, Festungen, Gebäude)
  const REG = Object.fromEntries(REG_AUS);
  const regler = F ? "" : kv(Object.entries(w.unterhalt_regler || {}).map(([k, v]) => [REG[k.replace("Maintenance", "").toLowerCase()] || k, pct(v)]));
  const steuer = Object.entries(w.steuersaetze || {}).map(([k, v]) => [(P.A.staende || []).find(e => e.stand === k)?.name || k, pct(v)]);
  const texte = (P.LD.text || []).filter(t => !String(t.schluessel).startsWith("handel_"));
  // Monatsreihen aus dem Spielstand (monthly_gold, recent_balance); Ausgaben = Einkommen − Saldo
  // (nachgerechnet 29.09.: 1341.07 10,797 − 6,797 = 3,9996 = economy.expense)
  const mon = (d.monate || []).slice(-24);
  const ser = f => mon.map(f).filter(num);
  const saldoSer = ser(m => m.saldo), einSer = ser(m => m.einkommen), ausSer = ser(m => num(m.einkommen) && num(m.saldo) ? m.einkommen - m.saldo : null);
  const inflSer = liveSeries(d, "inflation");                                     // Inflation nur live (Daten-Mod)
  const vm = (s, cur, alt) => s.length > 1 ? s.at(-1) - s.at(-2) : num(cur) && num(alt) ? cur - alt : null;   // Vormonat, sonst voriger Spielstand
  const tt = x => `Trend = Veränderung zum Vormonat; Linie = ${x} je Monat (bis 24 Monate)`;
  // mit Daten-Mod: wie im Wirtschaftsfenster (Stand Monatserster), Spielstand klein darunter; sonst Spielstand
  const tS = x => `wie im Wirtschaftsfenster (Daten-Mod ${S?.datum}); ${tt(x)}; klein: Spielstand ${last.datum}`;
  const kopfW = (l, key, cur, ser0, good, color) => S
    ? { l, v: fmt(S[key], 2), cls: key === "saldo" ? posneg(S.saldo) : "", u: sp(cur), t: trend(vorm(S.ser[key]), 2, good),
        s: spark(S.ser[key], { color }), title: tS(l.split(" ")[0]) }
    : { l, v: fmt(cur, 2), cls: key === "saldo" ? posneg(cur) : "", t: trend(vm(ser0, cur, prev?.[key === "ein" ? "einkommen" : key === "aus" ? "ausgaben" : "saldo"]), 2, good),
        s: spark(ser0, { color }), title: tt(l.split(" ")[0]) };
  const head = hd({
    big: [{ l: liveNewer ? `Gold (live ${lv.datum})` : "Gold", v: fmt(gold, 0), t: trend(num(goldPrev) ? gold - goldPrev : null, 0, 1),
            s: spark(liveSeries(d, "gold"), { color: "--c7" }), title: "Trend = Veränderung zum Vormonat; Linie = Verlauf live" },
          kopfW("Saldo / Monat", "saldo", last.saldo, saldoSer, 1, "--c3"),
          { umbruch: true },                                     // Einkommen in die zweite Zeile (Nutzerwunsch 29.09.)
          kopfW("Einkommen / Monat", "ein", last.einkommen, einSer, 1, "--c2"),
          kopfW("Ausgaben / Monat", "aus", last.ausgaben, ausSer, -1, "--c5"),
          { l: "Inflation", v: fmt(lv.inflation ?? last.inflation, 3), t: trend(vm(inflSer), 3, -1),
            s: spark(inflSer, { color: "--c4" }), title: "Trend = Veränderung zum Vormonat; Linie = Inflation je Monat live (bis 24 Monate)" }],
    small: [{ l: "Einkommen / Jahr", v: fmt(lv.yearly_gold, 0) }, { l: "Kreditwürdigkeit", v: fmt(lv.creditworthiness, 2) },
            { l: "Schulden", v: fmt(lv.debt_total ?? 0, 0), cls: (lv.debt_total ?? 0) > 0 ? "neg" : "" }],
    warn: [saldoT < 0 && "Saldo negativ", (lv.debt_total ?? 0) > 0 && `Schulden ${fmt(lv.debt_total, 0)}`,
           (lv.stability ?? last.stabilitaet) < 0 && "Stabilität negativ", (lv.inflation ?? 0) > 0 && `Inflation ${fmt(lv.inflation, 3)}`],
  });
  const body = `<div class="grid2">
      <div class="card"><h3>Einnahmen – ${fmt(einT, 2)} / Monat${S ? ` <span class="hint">Spielstand ${fmt(w.einkommen, 2)}</span>` : ""}</h3>${compo(ein, einT)}
        ${steuer.length ? `<h3 style="margin-top:10px">Steuersätze (tatsächlich)</h3>${kv(steuer)}` : ""}
        ${S ? `<p class="hint">Wie im Wirtschaftsfenster (Daten-Mod ${esc(S.datum)}): Steuern je Stand, Handelseinnahmen = Gewinn der Routen × Modifikator,
          ${esc(einMod.map(r => r.l).join(", ") || "–")} aus der Einkommens-Aufschlüsselung (${esc(d.alles?.datum?.land || "")}); klein: Spielstand ${esc(last.datum)}.</p>`
          : einMod.length ? `<p class="hint">Steuern, Handel, Summe und „übrige“: Spielstand ${esc(last.datum)}; ${esc(einMod.map(r => r.l).join(", "))}: Einkommens-Aufschlüsselung laut Spiel (Daten-Mod ${esc(d.alles?.datum?.land || "")}).</p>` : ""}
        <h3 style="margin-top:10px">Wachstum</h3>${kv([["Wachstum kurz / lang", `${fmt(lv.eco_growth_short, 2)} / ${fmt(lv.eco_growth_long, 2)}`], ["Einkommen / Jahr", fmt(lv.yearly_gold, 0)],
          ["Münzprägung", pct(w.muenzpraegung, 1)], ["Prestige", fmt(lv.prestige ?? last.prestige, 1)]])}</div>
      <div class="card"><h3>Ausgaben und Regler – ${fmt(ausT, 2)} / Monat${S ? ` <span class="hint">Spielstand ${fmt(w.ausgaben, 2)}</span>` : ""}</h3>${compo(aus, ausT)}
        ${regler ? `<h3 style="margin-top:10px">Regler (Stellung)</h3>${regler}` : ""}
        ${ausTexte.map(([t, x], i) => lazy(`fin:aus:${i}`, esc(t), () => breakdown(x))).join("")}
        <p class="hint">${F ? `Posten = Kosten je Regler laut Spiel, dahinter die Reglerstellung (Daten-Mod ${esc(P.LD.extra_datum || "")}); Summe: ${S ? `wie im Wirtschaftsfenster (Einnahmen − Saldo, ${esc(S.datum)})` : `Spielstand ${esc(last.datum)}`}.`
          : "„übrige“ = alles, was der Spielstand nicht einzeln führt (vermutlich die Regler Hof, Diplomatie usw.); Kosten je Regler kommen mit Mod 0.11."}</p></div>
    </div>
    ${texte.length ? `<details class="more" ${openAttr("fin:texte", false)}><summary>Aufschlüsselungen der Spieloberfläche (Rohtext, Mod 0.11)</summary>
      <div class="grid2">${texte.map(t => `<div class="card"><h3>${esc(t.schluessel)}</h3><pre class="raw">${rawText(t.text)}</pre></div>`).join("")}</div></details>` : ""}`;
  // Kreditbezug steht in der Karte Kreditwürdigkeit über deren Aufschlüsselung (live.js, TILE_TEXTS „vor“)
  const vor = { GetCreditworthinessInfo: kv([["Schulden", fmt(lv.debt_total, 1)], ["Kredite", fmt(lv.loans, 0)],
    ["Kreditrahmen", fmt(lv.loan_capacity ?? w.kreditrahmen, 0)], ["Kreditwürdigkeit", fmt(lv.creditworthiness, 2)]]) };
  return { head, body, vor };
}

// Verlauf (Nutzerwunsch 01.10., Punkte 1–8): Einkommen/Saldo wie im Wirtschaftsfenster (Daten-Mod einkommen_spiel/saldo_spiel,
// ab 1340), Spielstand-Werte gestrichelt; Zeitraum-Schalter für alle Diagramme (die Startmonate 1337 mit Einkommen 70 → 16
// stauchen sonst die Achse); Tabelle „Entwicklung seit Spielbeginn“; eigene Monatsdiagramme statt zweier Reihen auf einer Achse;
// Gesellschaftswerte über die Zeit. Begriff „Steuergrundlage“ wie im Spiel.
const ZEITRAUM = [["12", "12 Monate"], ["36", "3 Jahre"], ["alle", "alles"]];
let VERLAUF_BAU = null;                       // baut die Diagramme für einen Zeitraum neu (Schalter oben in der Kachel)
document.addEventListener("click", e => {
  const b = e.target.closest?.("button[data-zeitraum]");
  if (!b || !VERLAUF_BAU) return;
  store.set("rg_zeitraum", b.dataset.zeitraum);
  const box = document.getElementById("vlcharts");
  if (box) box.innerHTML = VERLAUF_BAU(b.dataset.zeitraum);
  document.querySelectorAll("button[data-zeitraum]").forEach(x => x.classList.toggle("an", x === b));
});
function verlauf(d, P) {
  const L = d.live || [], names = Object.fromEntries((P.A.staende || []).map(e => [e.stand, e.name]));
  const estates = [...new Set(d.punkte.flatMap(p => Object.keys(p.staende)))];
  const estatePts = (e, snapKey, liveKey) => {
    const m = new Map(d.punkte.filter(p => p.staende[e]?.[snapKey] != null).map(p => [p.jahr.toFixed(4), [p.jahr, p.staende[e][snapKey]]]));
    for (const r of L) if (r[`${liveKey}_${e}`] != null) m.set(r.jahr.toFixed(4), [r.jahr, r[`${liveKey}_${e}`]]);
    return [...m.values()].sort((a, b) => a[0] - b[0]);
  };
  const monthPts = key => d.monate.filter(m => m[key] != null).map(m => [monthX(m.monat), m[key]]);
  const pctF = v => nf(0).format(v * 100) + " %";
  const handelEin = r => num(r.handel_gewinn) && num(r.handel_mod) ? r.handel_gewinn * r.handel_mod : null;
  const reihe = f => L.filter(r => num(f(r))).map(r => [r.jahr, f(r)]);
  const ser = key => reihe(r => r[key]);
  // Wert am Anfang, vor 12 Monaten und jetzt (Live-Monate mit Wert)
  const stand = f => { const s = reihe(f); if (!s.length) return null; const jetzt = s.at(-1), start = s[0];
    const v12 = s.find(p => Math.abs(p[0] - (jetzt[0] - 1)) < 0.05);
    return { start, v12: v12 ? v12[1] : null, jetzt: jetzt[1], ser: s.map(p => p[1]) }; };
  const datumX = x => { const y = Math.floor(x + 1e-6), m = Math.round((x - y) * 12) + 1; return `${MONAT[m - 1]?.slice(0, 3) || m}. ${y}`; };

  // Kopf (Punkt 6): Einkommen und Saldo wie im Wirtschaftsfenster, Steuergrundlage; klein: seit Spielbeginn
  const ein = stand(r => r.einkommen_spiel), sal = stand(r => r.saldo_spiel), steu = stand(r => r.tax_base);
  const bev = stand(r => r.population_total), kon = stand(r => r.control_avg), pre = stand(r => r.prestige);
  const lm = d.monate.at(-1) || {};
  const d12 = x => x && num(x.v12) ? x.jetzt - x.v12 : null;
  const head = hd({
    big: [ein && { l: "Einkommen / Monat", v: fmt(ein.jetzt, 2), t: trend(d12(ein), 2, 1), s: spark(ein.ser.slice(-24), { color: "--c2" }), u: `Spielstand ${fmt(lm.einkommen, 2)}`,
                   title: "wie im Wirtschaftsfenster (Daten-Mod); Pfeil = Veränderung gegenüber vor 12 Monaten; klein: Spielstand" },
          sal && { l: "Saldo / Monat", v: fmt(sal.jetzt, 2), cls: posneg(sal.jetzt), t: trend(d12(sal), 2, 1), s: spark(sal.ser.slice(-24), { color: "--c3" }), u: `Spielstand ${fmt(lm.saldo, 2)}`,
                   title: "wie im Wirtschaftsfenster (Daten-Mod); Pfeil = Veränderung gegenüber vor 12 Monaten" },
          steu && { l: "Steuergrundlage", v: fmt(steu.jetzt, 2), t: trend(d12(steu), 2, 1), s: spark(steu.ser.slice(-24), { color: "--c1" }),
                    title: "Pfeil = Veränderung gegenüber vor 12 Monaten" }],
    small: [bev && { l: "Bevölkerung seit Start", v: `${sgn(bev.jetzt - bev.start[1], 1)} Tsd.`, cls: posneg(bev.jetzt - bev.start[1]), title: `seit ${datumX(bev.start[0])}` },
            kon && { l: "Ø Kontrolle seit Start", v: `${sgn((kon.jetzt - kon.start[1]) * 100, 1)} %-Pkt.`, cls: posneg(kon.jetzt - kon.start[1]), title: `seit ${datumX(kon.start[0])}` },
            pre && { l: "Prestige seit Start", v: sgn(pre.jetzt - pre.start[1], 1), cls: posneg(pre.jetzt - pre.start[1]), title: `seit ${datumX(pre.start[0])}` }],
  });

  // Entwicklung seit Spielbeginn (Punkt 3): erster Live-Monat mit Wert, vor 12 Monaten, jetzt; gut = +1 (mehr ist besser) / −1 (Rang)
  const KZ = [["Steuergrundlage", r => r.tax_base, 2, 1], ["Ø Kontrolle", r => r.control_avg, "%", 1], ["Bevölkerung (Tsd.)", r => r.population_total, 1, 1],
    ["Entwicklung", r => r.development_total, 1, 1], ["Prestige", r => r.prestige, 1, 1], ["Legitimität", r => r.legitimacy, 1, 1],
    ["Stabilität", r => r.stability, 1, 1], ["Gold", r => r.gold, 0, 1], ["Einkommen / Monat (Fenster)", r => r.einkommen_spiel, 2, 1],
    ["Saldo / Monat (Fenster)", r => r.saldo_spiel, 2, 1], ["Handelseinkommen / Monat", handelEin, 2, 1], ["Gewinn der Gebäude / Monat", r => r.gebaeude_gewinn, 2, 1],
    ["Militärstärke", r => r.military_strength, 2, 1], ["Glaubenseinfluss", r => r.religious_influence, 1, 1],
    ["Großmacht-Rang", r => r.great_power_rank, 0, -1]];
  const wf = (v, n) => n === "%" ? pct(v, 1) : fmt(v, n);
  const df = (v, n) => n === "%" ? `${sgn(v * 100, 1)} %-Pkt.` : sgn(v, n === 0 ? 0 : n);
  // Reihen, die durchgehend 0 sind, fehlen (Mod-Wert advances ist immer 0, obwohl 69 Fortschritte erforscht sind – geprüft 01.10.)
  const kz = KZ.map(([t, f, n, gut]) => ({ t, n, gut, s: stand(f) })).filter(x => x.s && x.s.ser.some(v => v !== 0));
  const entwicklung = `<div class="card" style="grid-column:1/-1"><h3>Entwicklung seit Spielbeginn</h3>${table([
      { t: "Kennzahl", f: x => esc(x.t) },
      { t: "Start", f: x => `${wf(x.s.start[1], x.n)} <span class="hint">${datumX(x.s.start[0])}</span>` },
      { t: "vor 12 Monaten", f: x => wf(x.s.v12, x.n) }, { t: "jetzt", f: x => wf(x.s.jetzt, x.n) },
      { t: "seit Start", f: x => df(x.s.jetzt - x.s.start[1], x.n), cls: x => posneg((x.s.jetzt - x.s.start[1]) * x.gut) },
      { t: "12 Monate", f: x => num(x.s.v12) ? df(x.s.jetzt - x.s.v12, x.n) : "–", cls: x => num(x.s.v12) ? posneg((x.s.jetzt - x.s.v12) * x.gut) : "" },
      { t: "Verlauf", f: x => spark(x.s.ser, { color: "--accent", w: 120 }) }], kz, { scroll: false })}
    <p class="hint">Start = erster Monat mit Daten-Mod-Wert (Live-Daten ab ${esc(L[0]?.datum || "–")}); Farbe grün = besser (beim Rang: kleiner ist besser).</p></div>`;

  // Gesellschaftswerte über die Zeit (Punkt 7): je Achse jetzt, vor 12 Monaten, Start, Veränderung, Verlauf (negativ = linker Pol)
  const gs = P.A.gesellschaft || {}, gn = (P.W.namen || {}).gesellschaft || {};
  const achsen = Object.keys(gs).map(k => { const [lft, rgt] = (gn[k] || k).split(/ vs\.? /); return { k, lft, rgt, s: stand(r => r["sv_" + k]) }; })
    .filter(a => a.s && a.s.ser.some(v => v !== 0));
  const gesellschaft = achsen.length ? `<div class="card" style="grid-column:1/-1"><h3>Gesellschaftswerte über die Zeit</h3>${table([
      { t: "links (−)", f: a => esc(a.lft) }, { t: "rechts (+)", l: true, f: a => esc(a.rgt || "") },
      { t: "Start", f: a => fmt(a.s.start[1], 1) }, { t: "vor 12 Monaten", f: a => fmt(a.s.v12, 1) }, { t: "jetzt", f: a => fmt(a.s.jetzt, 1) },
      { t: "seit Start", f: a => sgn(a.s.jetzt - a.s.start[1], 1) }, { t: "Verlauf", f: a => spark(a.s.ser, { color: "--c6", w: 120 }) }], achsen, { scroll: false })}
    <p class="hint">Wert −100 … +100: negativ = linker Pol, positiv = rechter Pol (wie in der Regierungskachel). Achsen ohne Bewegung (immer 0) fehlen.</p></div>` : "";

  // Diagramme je Zeitraum (Punkte 1, 2, 4, 5)
  VERLAUF_BAU = zr => {
    const xs = [...L.map(r => r.jahr), ...d.monate.map(m => monthX(m.monat))];
    const lastX = xs.length ? Math.max(...xs) : 0, ab = zr === "alle" ? -Infinity : lastX - (+zr) / 12 + 1e-6;
    const ch = (title, series, opt = {}) => `<div class="card"><h3>${title}</h3>${lineChart(series.map(s => ({ ...s, points: s.points.filter(p => p[0] >= ab) })), { marks: d.markierungen, ...opt })}</div>`;
    return `<div class="grid3">${[
      ch("Einkommen und Saldo je Monat", [{ name: "Einkommen (Wirtschaftsfenster)", color: "--c2", points: ser("einkommen_spiel") },
        { name: "Saldo (Wirtschaftsfenster)", color: "--c3", points: ser("saldo_spiel") },
        { name: "Einkommen (Spielstand)", color: "--c2", dash: true, points: monthPts("einkommen") },
        { name: "Saldo (Spielstand)", color: "--c3", dash: true, points: monthPts("saldo") }], { zero: true, yFmt: v => fmt(v, 0) }),
      ch("Steuergrundlage je Monat", [{ name: "Steuergrundlage", color: "--c1", points: ser("tax_base") }], { yFmt: v => fmt(v, 0) }),
      ch("Ø Kontrolle je Monat", [{ name: "Ø Kontrolle", color: "--c3", points: ser("control_avg") }], { yFmt: pctF }),
      ch("Bevölkerung je Monat (Tsd.)", [{ name: "Bevölkerung", color: "--c4", points: ser("population_total") }], { yFmt: v => fmt(v, 1) }),
      ch("Gold je Monat", [{ name: "Gold", color: "--c7", points: ser("gold") }]),
      ch("Stabilität je Monat", [{ name: "Stabilität", color: "--c2", points: ser("stability") }], { zero: true }),
      ch("Prestige und Legitimität", [{ name: "Prestige", color: "--c6", points: ser("prestige") }, { name: "Legitimität", color: "--c1", points: ser("legitimacy") }], { zero: true }),
      ch("Macht der Stände", estates.map(e => ({ name: names[e] || e, color: ESTATE_COLOR[e] || "--c8", points: estatePts(e, "macht", "power") })), { yFmt: pctF }),
      ch("Zufriedenheit der Stände", estates.map(e => ({ name: names[e] || e, color: ESTATE_COLOR[e] || "--c8", points: estatePts(e, "zufriedenheit", "sat") })), { yFmt: pctF }),
    ].join("")}</div>`;
  };
  const zr = ZEITRAUM.some(([k]) => k === store.get("rg_zeitraum")) ? store.get("rg_zeitraum") : "36";
  const schalter = `<div class="zr"><span class="hint">Zeitraum der Diagramme:</span>${ZEITRAUM.map(([k, t]) => `<button data-zeitraum="${k}" class="${k === zr ? "an" : ""}">${t}</button>`).join("")}</div>`;
  return { head, body: `${schalter}<div id="vlcharts">${VERLAUF_BAU(zr)}</div>
    <p class="hint">Einkommen und Saldo: durchgezogen wie im Wirtschaftsfenster (Daten-Mod, ab ${esc(L.find(r => num(r.einkommen_spiel))?.datum || "–")}),
      gestrichelt laut Spielstand (Schätzung des Spiels). Die ersten Monate 1337 (Einkommen 70 → 16) stauchen die Ansicht „alles“.</p>
    <div class="grid2" style="margin-top:14px">${entwicklung}${gesellschaft}</div>` };
}

// Entscheidungen (Nutzerwunsch 01.10., Punkte 1–6): Wirkung mit Werten wie im Spiel (Daten-Mod, Einkommen/Saldo wie im
// Wirtschaftsfenster), viele Kennzahlen je Entscheidung, Monate vorher/nachher sichtbar, Δ erst ab 3 Monaten danach;
// automatisch erkannte Änderungen (Server history.aenderungen) mit Knopf „übernehmen“.
function wirkungKennzahlen(P) {
  const st = (P.A.staende || []).filter(e => e.stand !== "crown_estate");
  return [["Einkommen / Monat (Fenster)", r => r.einkommen_spiel, 2, 1], ["Saldo / Monat (Fenster)", r => r.saldo_spiel, 2, 1],
    ["Steuergrundlage", r => r.tax_base, 2, 1], ["Ø Kontrolle", r => r.control_avg, "%", 1], ["Stabilität", r => r.stability, 1, 1],
    ["Prestige", r => r.prestige, 1, 1], ["Legitimität", r => r.legitimacy, 1, 1], ["Gewinn der Gebäude / Monat", r => r.gebaeude_gewinn, 2, 1],
    ["Handelseinkommen / Monat", r => num(r.handel_gewinn) && num(r.handel_mod) ? r.handel_gewinn * r.handel_mod : null, 2, 1],
    ["Bevölkerung – Veränderung / Monat (Tsd.)", r => r.population_change, 3, 1],
    ...st.map(e => [`Zufriedenheit ${e.name}`, r => r["sat_" + e.stand], "%", 1]),
    ...(P.A.staende || []).map(e => [`Macht ${e.name}`, r => r["power_" + e.stand], "%", 0])];
}
function wirkung(d, P) {
  if (!d.markierungen.length) return `<p class="hint">Noch keine Entscheidung markiert – selbst eintragen oder unten eine erkannte Änderung übernehmen.</p>`;
  const L = d.live || [], KZ = wirkungKennzahlen(P);
  // Fenster: 6 Monate vor dem Datum gegen 6 Monate danach (Monat der Entscheidung selbst zählt nicht)
  const fenster = (x, f) => { const v = L.filter(r => num(f(r)) && r.jahr < x - 1e-6 && r.jahr >= x - 0.5 - 1e-6).map(f);
    const n = L.filter(r => num(f(r)) && r.jahr > x + 1e-6 && r.jahr <= x + 0.5 + 1e-6).map(f);
    return { vor: avg(v), nach: avg(n), nv: v.length, nn: n.length }; };
  const wf = (v, n) => n === "%" ? pct(v, 1) : fmt(v, n);
  const df = (w, n, gut) => w.nn < 3 || !w.nv ? `<span class="hint">noch zu früh</span>`
    : `<span class="${posneg((w.nach - w.vor) * gut)}">${n === "%" ? `${sgn((w.nach - w.vor) * 100, 1)} %-Pkt.` : sgn(w.nach - w.vor, n)}</span>`;
  const rows = d.markierungen.map(mk => ({ mk, w: KZ.map(([t, f, n, gut]) => ({ t, n, gut, ...fenster(mk.jahr, f) })) }));
  const kurz = (r, t) => { const w = r.w.find(x => x.t.startsWith(t)); return w ? df(w, w.n, w.gut) : "–"; };
  return table([
    { t: "Datum", f: r => esc(r.mk.datum) },
    { t: "Entscheidung", l: true, f: r => `${esc(r.mk.text)} <button data-del="${r.mk.id}" title="löschen">✕</button>` },
    // Monate laut Einkommen (Fensterwert ab 1340), sonst Steuergrundlage
    { t: "Monate vorher / nachher", f: r => { const w = r.w[0].nv + r.w[0].nn ? r.w[0] : r.w[2]; return `${w.nv} / ${w.nn}`; } },
    { t: "Einkommen Δ", f: r => kurz(r, "Einkommen") }, { t: "Saldo Δ", f: r => kurz(r, "Saldo") },
    { t: "Steuergrundlage Δ", f: r => kurz(r, "Steuergrundlage") }, { t: "Stabilität Δ", f: r => kurz(r, "Stabilität") },
    { t: "alle Werte", l: true, f: r => `<details><summary>zeigen</summary>${table([{ t: "Kennzahl", f: w => esc(w.t) },
        { t: "vorher (Ø)", f: w => wf(w.vor, w.n) }, { t: "nachher (Ø)", f: w => wf(w.nach, w.n) }, { t: "Δ", f: w => df(w, w.n, w.gut) },
        { t: "Monate", f: w => `${w.nv} / ${w.nn}` }], r.w.filter(w => w.nv || w.nn), { scroll: false })}</details>` }], rows);
}

// Empfehlungen (Nutzerwunsch 02.10.): Regeln laufen im Server (eu5ratgeber/empfehlungen.py). Je Empfehlung die Handlung, die
// Begründung mit Zahlen und die Wirkung – berechnet (geprüfte Formel), Spielwert (Zahl so aus dem Spiel) oder messen (keine
// Formel: nach dem Umsetzen markieren, die Kachel Entscheidungen misst vorher/nachher). Die Kachelköpfe zeigen weiter den
// Zustand (Warnungen), hier steht nur die Handlung. „umgesetzt“ legt die Markierung mit dem Spieldatum des letzten Monats an.
const EMPF_PRIO = { hoch: "wichtig", mittel: "mittel", niedrig: "später" };
const EMPF_WIRK = { berechnet: "berechnet", Spielwert: "Spielwert", messen: "messen" };
const EMPF_KACHEL = { orte: "Orte", produktion: "Produktion", gueter: "Güter", staende: "Stände", diplomatie: "Diplomatie",
                      finanzen: "Finanzen", empfehlungen: "Empfehlungen", krankheiten: "Krankheiten",
                      nachbarn: "Nachbarn und Kriegsgelegenheiten", handel: "Handel", wirtschaftsplan: "Wirtschaftsplan",
                      forschung: "Forschung" };
// gewählter Schwerpunkt des Wirtschaftsplans (bleibt in diesem Browser) – auch für die Empfehlungen und die Kachel Handel (29.10.)
function wpFokus(d) {
  const fk = store.get("rg_wp_fokus") || "grundwirtschaft";
  return (d.wirtschaftsplan?.fokusse || {})[fk] ? fk : "grundwirtschaft";
}
// Wirtschaftsplan (Nutzerwunsch 25.10.): welche Güter und Produktionsketten aufbauen, Schwerpunkt wählbar. Stufen 1–3 aus
// eu5ratgeber/wirtschaftsplan.py: Bedarf (Gewicht des Schwerpunkts × Knappheit im Heimatmarkt), Ketten (Gebäudearten,
// Produktionsmethoden, Eingangsgüter mit Verfügbarkeit), Gewinn je Stufe derselben Gebäudeart laut Spielstand. Die Reihenfolge
// als Plan (Stufe 4) folgt.
const WP_STATUS_RANG = s => s.bei_uns ? 0 : s.sonder ? 4 : s.fortschritt ? 2 : s.landbedingung ? 3 : 1;
function wpStatus(s = {}) {
  const fehlt = s.fortschritt ? `<span class="neg">Fortschritt fehlt:</span> ${esc(s.fortschritt.join(" / "))}` : "";
  return s.bei_uns ? `<span class="pos">bei uns ×${s.bei_uns}</span>`
    : s.sonder ? (s.freischaltung ? `Sondergebäude${fehlt ? ` – ${fehlt}` : " – freigeschaltet"}${s.landbedingung ? ", mit Bedingung des Landes" : ""}` : "Sondergebäude")
    : fehlt || (s.landbedingung ? "mit Bedingung des Landes" : "freigeschaltet");
}
function wirtschaftsplanKachel(d, P) {
  const WP = d.wirtschaftsplan || {};
  if (!WP.fokusse) return "";
  const W = P.W || {}, gnm = (W.namen || {}).gueter || {}, bnm = (W.namen || {}).gebaeude || {}, pmn = (W.namen || {}).pms || {};
  const fk = wpFokus(d);
  const F = WP.fokusse[fk], G = WP.gueter || {}, B = WP.gebaeude || {};
  const gname = g => esc(G[g]?.name || gnm[g] || g), bname = a => esc(B[a]?.name || bnm[a] || a);
  const verh = g => num(G[g]?.verh) ? `<span class="${G[g].verh >= 1 ? "neg" : "pos"}">${fmt(G[g].verh, 2)}×</span>` : "–";
  const knappe = F.reihung === "knapp" ? F.gueter.filter(r => r.knapp) : [];
  const head = hd({
    big: [{ l: "Schwerpunkt", v: esc(F.name), cls: "wort" },
          !F.gueter.length ? { l: "Bedarf", v: "keine Daten", cls: "wort", title: "Für diesen Schwerpunkt fehlen im Spielstand die Werte (älterer Stand?)" }
          : F.reihung === "knapp"
            ? { l: "knapp im Heimatmarkt", cls: "wort", title: "Preis mindestens Grundpreis – Güter des Schwerpunkts mit dem größten Anteil × Preis/Grundpreis",
                v: knappe.slice(0, 3).map(r => `${gname(r.gut)} <i>${verh(r.gut)}</i>`).join(" · ") || "keins – alles gedeckt" }
            : { l: "vorne", v: F.gueter.slice(0, 3).map(r => gname(r.gut)).join(" · ") || "–", cls: "wort" },
          F.fehlen.length && { l: "im Markt nicht vorhanden", v: F.fehlen.slice(0, 3).map(r => gname(r.gut)).join(" · "), cls: "wort neg" }],
    small: [(F.plan || []).length && { l: "nächster Schritt", v: `${esc(F.plan[0].was)} – ${esc(F.plan[0].ort)}`, cls: "wort", mw: 520 },
            { l: "Heimatmarkt", v: esc(WP.heimat || "–"), cls: "wort" },
            { l: "Vergleich mit", v: esc((WP.fremde_maerkte || []).join(", ") || "–"), cls: "wort", mw: 420 }],
  });
  const wahl = `<div class="wpwahl"><label>Schwerpunkt <select id="wp-fokus">${Object.entries(WP.fokusse).map(([k, f]) =>
      `<option value="${k}"${k === fk ? " selected" : ""}>${esc(f.name)}</option>`).join("")}</select></label>
    <span class="hint">${esc(F.erklaerung)}</span></div>`;
  // Stufe 1: Bedarf
  const wertSp = { gewinn: ["Gewinn je Stufe (Gold/Monat)", 3], export: ["Preisvorteil × Nachfrage dort (Gold)", 2],
                   import: ["Einkaufsvorteil je Einheit (Gold)", 3] }[fk];
  const herkunft = g => [G[g].eigene_rgo?.length && `Rohstoff in ${esc(G[g].eigene_rgo.join(", "))}`,
                         G[g].eigene_gebaeude?.length && G[g].eigene_gebaeude.map(bname).join(", ")].filter(Boolean).join("<br>") || "–";
  const bedarf = table([
    { t: "Gut", l: true, f: r => `${gname(r.gut)}${F.reihung === "knapp" ? (r.knapp ? ` <span class="warn">knapp</span>` : ` <span class="hint">gedeckt</span>`) : ""}` },
    { t: "Anteil am Schwerpunkt", f: r => pct(r.anteil, r.anteil < 0.1 ? 1 : 0) },
    wertSp && { t: wertSp[0], f: r => fmt(r.wert, wertSp[1]) },
    fk === "gewinn" && { t: "beste baubare Gebäudeart", l: true, f: r => r.gebaeude ? `${bname(r.gebaeude)}<div class="hint">${esc(r.quelle || "")}</div>` : "–" },
    { t: "Preis (Gold)", f: r => num(G[r.gut].preis) ? `${fmt(G[r.gut].preis, 2)} <span class="hint">Grundpreis ${fmt(G[r.gut].grundpreis, 2)}</span>` : "–" },
    { t: "Preis ÷ Grundpreis", f: r => verh(r.gut) },
    { t: "Preisverlauf", f: r => (G[r.gut].verlauf || []).length > 1 ? spark(G[r.gut].verlauf, { w: 70, h: 18, color: "--c4" }) : "–" },
    { t: "Nachfrage / Angebot", f: r => num(G[r.gut].nachfrage) ? `${fmt(G[r.gut].nachfrage, 1)} / ${fmt(G[r.gut].angebot, 1)}` : "–" },
    { t: "Einfuhr", f: r => num(G[r.gut].einfuhr) ? pct(G[r.gut].einfuhr, 0) : "–" },
    { t: "bei uns", l: true, f: r => herkunft(r.gut) },
    { t: "billigster Markt in Reichweite (Gold)", l: true, f: r => G[r.gut].fremd_min ? `${esc(G[r.gut].fremd_min[0])} ${fmt(G[r.gut].fremd_min[1], 2)}` : "–" }].filter(Boolean),
    F.gueter, { scroll: true });
  const bedarfKarte = `<div class="card" style="grid-column:1/-1"><h3>Bedarf – ${esc(F.name)}</h3>${bedarf}
    ${F.fehlen.length ? `<p><b>Im Heimatmarkt nicht vorhanden</b> (Anteil am Schwerpunkt): ${F.fehlen.map(r => `${gname(r.gut)} ${pct(r.anteil, 0)}${r.nur_rohstoff ? " <i>(nur als Rohstoff, kein eigener Ort)</i>" : ""}`).join(", ")}</p>` : ""}
    <p class="hint">Spielstand ${esc(d.meta.datum)}, Heimatmarkt ${esc(WP.heimat || "")}. ${F.reihung === "knapp" ? "Erst knappe Güter (Preis ≥ Grundpreis) nach Anteil × Preis/Grundpreis, dann gedeckte – mehr von einem gedeckten Gut drückt seinen Preis weiter. " : ""}
      Einfuhr = Anteil des Angebots aus Handel (angebot_quellen Trade und BurgherTrades); Mengen wie im Marktfenster des Spiels; Preisverlauf aus dem Spielstand.</p></div>`;
  // Handelsbestellungen zum Schwerpunkt (Nutzerwunsch 29.10.) – Server eu5ratgeber/handel.vorschlaege: Einfuhr knapper Güter des
  // Schwerpunkts aus Märkten in Reichweite mit Angebot (Veredelung: Eingangsgüter), Ausfuhr von Überschüssen (Export, Gewinn);
  // Vorlage aus dem Spiel (Modus, Eintrag „Beliebige …“). Lage hier steht schon in der Bedarfstabelle – hier nur Fehlmenge/Überschuss.
  const HV = d.handel_zoelle?.vorschlaege || {}, HF = (HV.fokusse || {})[fk];
  const zollTxt = e => num(e.zoll_satz) && e.zoll_satz > 0 ? `${esc(e.zoll_land_name || e.zoll_land)} ${pct(e.zoll_satz, 0)}` : "–";
  const bestTxt = e => !e.bestellung ? "–" : e.bestellung.art === "gleich"
    ? `<span class="pos">schon in Nr. ${esc(e.bestellung.id)}</span>${e.bestellung.route ? "" : ` <span class="hint">(ohne Route)</span>`}`
    : `<span class="neg">Nr. ${esc(e.bestellung.id)} führt ${e.bestellung.richtung === "ausfuhr" ? "aus" : "ein"}</span>`;
  const bestellKarte = HF ? `<div class="card" style="grid-column:1/-1"><h3>Handelsbestellungen – ${esc(F.name)}</h3>
    <p><b>Im Spiel:</b> Markt ${esc(HV.markt)} → Handelsbestellung „Benutzerdefiniert“ → „${HF.richtung === "einfuhr" ? "Einfuhreintrag" : "Ausfuhreintrag"} hinzufügen“;
      Modus <b>${esc(HF.modus.name)}</b> – ${esc(HF.modus.text)}.${num(HF.mindestgewinn) ? ` „Min. Gewinn“ ${fmt(HF.mindestgewinn, 2)} je Händlerkapazität (Standard).`
        : " Ohne Mindestgewinn sind Verluste möglich (Spieltext)."}${HF.eintrag ? ` Statt einzelner Waren: Eintrag „${esc(HF.eintrag.name)}“ – ${esc(HF.eintrag.text)}.` : ""}</p>
    ${(HF.hinweise || []).map(h => `<p><span class="warn">Hinweis</span> ${esc(h)}</p>`).join("")}
    ${(HF.eintraege || []).length ? table([
      { t: "Gut", l: true, f: e => `<b>${esc(e.gut_name)}</b>${e.fuer_name ? `<div class="hint">für ${esc(e.fuer_name)}</div>` : ""}` },
      { t: HF.richtung === "einfuhr" ? "Einfuhr aus" : "Ausfuhr nach", l: true, f: e => `${esc(e.markt)}${e.weitere ? ` <span class="hint">+${e.weitere} weitere</span>` : ""}` },
      { t: "Preis hier → dort (Gold)", f: e => `${fmt(e.preis_hier, 2)} → ${fmt(e.preis_dort, 2)}` },
      { t: "Vorteil je Einheit nach Zoll (Gold)", f: e => `<span title="vor Zoll ${fmt(e.vorteil, 2)} (${pct(e.vorteil_anteil, 0)})">${fmt(e.netto, 2)}</span>` },
      { t: "Ausfuhrzoll (Spielstand)", l: true, f: zollTxt },
      { t: HF.richtung === "einfuhr" ? "Fehlmenge hier" : "Überschuss hier", f: e => fmt(Math.abs(e.nachfrage_hier - e.angebot_hier), 2) },
      { t: "dort Angebot / Nachfrage", f: e => `${fmt(e.angebot_dort, 2)} / ${fmt(e.nachfrage_dort, 2)}` },
      { t: "Bestellung", l: true, f: bestTxt }], HF.eintraege, { scroll: true })
      : `<p class="hint">Kein Vorschlag: kein Gut des Schwerpunkts erfüllt die Bedingungen (siehe „ausgelassen“).</p>`}
    ${(HF.ausgelassen || []).length ? `<details class="more"><summary>ausgelassen (${HF.ausgelassen.length})</summary><div class="hint">${HF.ausgelassen.map(a =>
      `${esc(a.gut_name)}: ${esc(a.grund)}`).join("<br>")}</div></details>` : ""}
    ${(HV.hinweise || []).map(h => `<p class="hint">${esc(h)}</p>`).join("")}
    <p class="hint">${HF.richtung === "einfuhr" ? "Einfuhr: Gut mit Nachfrage über Angebot × 1,05 und Fehlmenge ab 0,1 im Heimatmarkt; Quelle mit Angebot – Märkte mit Überschuss zuerst, dann der größte Vorteil"
        : "Ausfuhr: Gut mit Angebot über Nachfrage × 1,05 und Überschuss ab 0,1; Ziel = teuerster Markt mit Nachfrage"}.
      Vorteil nach Zoll = Preisunterschied − Ausfuhrzoll (Satz × Einkaufspreis, wie das Spiel ihn je Route abzieht); mindestens ${num(HF.schwelle) && HF.schwelle > 0.25
        ? `${fmt(HF.schwelle, 2)} je Einheit = „Min. Gewinn“ 0,25 + Händlerunterhalt 0,25 je Kapazität`
        : "der Händlerunterhalt von 0,25 je Kapazität"} (Define MERCHANT_MAINTENANCE_COST) – Regel des Ratgebers unter der Annahme von mindestens 1 Kapazität
      je Einheit (beobachtet 1,0–2,7). Einfuhrzölle stehen nicht im Spielstand. Höchstens 5 Vorschläge
      in der Reihenfolge des Schwerpunkts; Preise laut Spielstand ${esc(d.meta.datum)}.</p></div>` : "";
  // Stufe 2 und 3: Ketten mit Gewinn je Stufe
  const gew = b => b.gewinn ? `${fmt(b.gewinn.je_stufe, 3)}<div class="hint">${esc(b.gewinn.quelle)}: ${b.gewinn.gebaeude} Gebäude, ${fmt(b.gewinn.stufen, 0)} Stufen${b.gewinn.laender ? `, ${b.gewinn.laender} Länder` : ""}${b.gewinn.eigene ? `, davon ${b.gewinn.eigene} eigene` : ""}</div>` : "–";
  const eig = b => b.eigen ? `${sgn(b.eigen.gewinn_je_stufe, 2)}<div class="hint">${num(b.eigen.steuer_je_stufe) ? `Steuergrundlage ${sgn(b.eigen.steuer_je_stufe, 2)} · ` : ""}Stufe ${fmt(b.eigen.stufe, 0)}/${fmt(b.eigen.max, 0)}</div>` : "–";
  const eingang = pm => Object.entries(pm.eingang || {}).map(([g, m]) => { const x = G[g] || {}, da = x.eigene_rgo?.length || x.eigene_gebaeude?.length;
      return `${gname(g)} ${fmt(m, 2)}${da ? ` <span class="pos">bei uns</span>` : num(x.verh) ? ` <i>${verh(g)}</i>` : ` <span class="neg">fehlt im Markt</span>`}`; }).join(", ");
  const kette = g => {
    const arten = [...(F.ketten[g] || [])].sort((a, b) => WP_STATUS_RANG(B[a]?.status || {}) - WP_STATUS_RANG(B[b]?.status || {})
      || (B[b]?.gewinn?.je_stufe ?? -9) - (B[a]?.gewinn?.je_stufe ?? -9));
    const rg = (WP.rgo || {})[g] || [];
    const rohstoff = G[g]?.kategorie === "raw_material" ? `<p>Rohstoff – Förderung in Orten mit ${gname(g)}: ${rg.length ? rg.map(o => `${esc(o.ort)}${num(o.steuer_je_stufe)
        ? ` <span class="hint">Ausbau ${sgn(o.steuer_je_stufe, 2)} Steuergrundlage je Stufe${num(o.kosten) ? ` für ${fmt(o.kosten, 1)} Gold${o.tage ? `, ${o.tage} Tage` : ""}` : ""}</span>` : ""}`).join(", ") : "bei uns kein Ort"}</p>` : "";
    const knappEin = [...new Set(arten.flatMap(a => (B[a]?.pms || []).filter(pm => pm.produziert === g).flatMap(pm => Object.keys(pm.eingang || {}))))]
      .filter(i => !(G[i]?.eigene_rgo?.length || G[i]?.eigene_gebaeude?.length) && (!num(G[i]?.verh) || G[i].verh >= 1));
    const tabelle = arten.length ? table([
      { t: "Gebäudeart", l: true, f: a => `<b>${bname(a)}</b><div class="hint">${wpStatus(B[a]?.status)}</div>` },
      { t: "Ort", l: true, f: a => { const b = B[a] || {}; return `${esc((b.ortsart || []).join(", ") || "–")}${b.ortsbedingung ? " <i>+ Bedingung des Orts</i>" : ""}<div class="hint">${(b.orte || []).length ? esc(b.orte.join(", ")) : "kein passender eigener Ort"}</div>`; } },
      { t: "Arbeitskräfte", l: true, f: a => { const b = B[a] || {}; return b.pop_name ? `${esc(b.pop_name)}${num(b.pops_bei_uns) ? `<div class="hint">${fmt(b.pops_bei_uns, 1)} Tsd. bei uns</div>` : ""}` : "–"; } },
      { t: "Gewinn je Stufe (Gold/Monat)", f: a => gew(B[a] || {}) },
      { t: "eigene ausbaufähige: Gewinn je Stufe (Mod, Gold/Monat)", f: a => eig(B[a] || {}) },
      { t: "Produktionsmethode → Ausstoß: Eingang je Stufe", l: true, f: a => (B[a]?.pms || []).filter(pm => pm.produziert === g)
          .map(pm => `<div><i>${esc(pmn[pm.name] || pm.name)}</i> → ${fmt(pm.menge, 2)}: ${eingang(pm) || "ohne Eingang"}</div>`).join("") || "–" },
      { t: "Baugüter je Stufe", l: true, f: a => Object.entries(B[a]?.baugueter || {}).map(([x, m]) => `${gname(x)} ${fmt(m, 2)}`).join(", ") || "–" }],
      arten, { scroll: true }) : `<p class="hint">Kein Gebäude stellt ${gname(g)} her.</p>`;
    const vorstufe = knappEin.length ? `<p><b>Knappe oder fehlende Eingangsgüter</b> – hergestellt von: ${knappEin.map(i => `${gname(i)} ${verh(i)} ← ${
        (F.eingang?.[i] || []).map(bname).join(", ") || (G[i]?.kategorie === "raw_material" ? "Rohstoff" : "keine für uns baubare Gebäudeart")}`).join("; ")}</p>` : "";
    return `<details class="more wpkette" ${openAttr(`wp:${fk}:${g}`, false)}><summary><b>${gname(g)}</b> ${verh(g)}${F.fehlen.some(r => r.gut === g) ? ` <span class="neg">fehlt im Markt</span>` : ""}</summary>${rohstoff}${tabelle}${vorstufe}</details>`;
  };
  const ketten = Object.keys(F.ketten || {});
  const kettenKarte = ketten.length ? `<div class="card" style="grid-column:1/-1"><h3>Produktionsketten – ${ketten.length} Güter</h3>${ketten.map(kette).join("")}
    <p class="hint">Gebäudearten und Produktionsmethoden laut Spieldateien; Lage für uns wie in der Kachel Güter (Fortschritte gegen die erforschten,
      Bedingungen des Landes und des Orts nicht ausgewertet). Gewinn je Stufe = last_months_profit ÷ Stufen derselben Gebäudeart laut Spielstand –
      im Heimatmarkt, sonst in Märkten in Reichweite, sonst weltweit (ohne Gewinnangabe im Spielstand zählt ein Gebäude mit 0); ein Durchschnitt, kein Wert
      für einen bestimmten Ort. „eigene ausbaufähige“ = Daten-Mod (GetProfitPerLevel = Gewinn ÷ Stufe, GetTaxBaseValuePerLevel) unserer Gebäude unter der
      Höchststufe. „bei uns“ bei Eingangsgütern = eigener Rohstoff oder eigenes Gebäude mit laufender Produktionsmethode und Belegschaft. Baukosten in Gold
      zeigt das Spiel nur im Baumenü – hier die Baugüter laut Spieldatei.</p></div>` : "";
  // Gebäude mit Wirkung auf den Schwerpunkt (Bevölkerung, Heer, Marine)
  const MN = WP.modnamen || {};
  // Ja/Nein-Modifikatoren nur mit Namen; kleine Werte mit mehr Stellen (Monatliche Mannstärke +0,002 statt +0,00)
  const stellen = v => Math.abs(v) >= 1 || v === 0 ? 0 : Math.abs(v) >= 0.1 ? 2 : 3;
  const modTxtWP = (m, v) => v === "yes" ? esc(MN[m]?.name || m) : `${esc(MN[m]?.name || m)} ${num(v)
    ? (MN[m]?.prozent ? sgn(v * 100, stellen(v * 100)) + " %" : sgn(v, stellen(v))) : `<i>${esc(String(v))}</i>`}`;
  const wirkKarte = (F.wirkung || []).length ? `<div class="card" style="grid-column:1/-1"><h3>Gebäude mit Wirkung auf den Schwerpunkt</h3>${table([
      { t: "Gebäudeart", l: true, f: a => `<b>${bname(a)}</b><div class="hint">${wpStatus(B[a]?.status)}</div>` },
      { t: "Wirkung je Stufe", l: true, f: a => [...Object.entries(B[a]?.wirkung || {}).filter(([m]) => (F.modifikatoren || []).includes(m)).map(([m, v]) => modTxtWP(m, v)),
          ...Object.entries(B[a]?.wirkung_hauptstadt || {}).filter(([m]) => (F.modifikatoren || []).includes(m)).map(([m, v]) => `${modTxtWP(m, v)} <i>(in der Hauptstadt)</i>`)].join("<br>") || "–" },
      { t: "Ort", l: true, f: a => { const b = B[a] || {}; return `${esc((b.ortsart || []).join(", ") || "–")}${b.ortsbedingung ? " <i>+ Bedingung des Orts</i>" : ""}`; } },
      { t: "Gewinn je Stufe (Gold/Monat)", f: a => gew(B[a] || {}) }], F.wirkung, { scroll: true })}
    <p class="hint">Gebäudearten mit passenden Modifikatoren in der Spieldatei (building_types modifier und capital_modifier); Sondergebäude nur, wenn ein
      Fortschritt sie freischaltet (z. B. Polder) oder wir sie haben.</p></div>` : "";
  // Stufe 4: Bauplan – konkrete Schritte (eu5ratgeber/bauplan.py)
  const lvW = (d.live || []).at(-1) || {}, marks = d.markierungen || [];
  const datumW = lvW.datum || d.meta.datum;
  const GRUPPE = { 1: "Ausbau", 2: "Neubau", 3: "Wirkung", 4: "Straße" };
  const knopfW = st => { const t = `Bauplan: ${st.was} in ${st.ort}`, mk = marks.find(m => m.text === t);
    return mk ? `<span class="hint">markiert am ${esc(mk.datum)}</span>`
      : `<button data-ueb-datum="${esc(datumW)}" data-ueb-text="${esc(t)}" data-ueb-partie="${esc(d.meta.partie_id)}"
           title="Markierung zum ${esc(datumW)} anlegen – die Kachel Entscheidungen misst die Wirkung">umgesetzt – markieren</button>`; };
  const planKarte = `<div class="card" style="grid-column:1/-1"><h3>Bauplan – ${esc(F.name)}</h3>${(F.plan || []).length ? table([
      { t: "Nr", f: st => String(st.nr) },
      { t: "Was", l: true, f: st => `<b>${esc(st.was)}</b><div class="hint">${esc(GRUPPE[st.gruppe] || "")} · ${esc(st.kategorie)}${st.kategorie_spiel ? ` (${esc(st.kategorie_spiel)})` : ""}</div>` },
      { t: "Wo", l: true, f: st => esc(st.ort) },
      { t: "Warum", l: true, f: st => esc(st.warum) },
      { t: "Voraussetzung", l: true, f: st => st.voraussetzung === "–" ? "–" : esc(st.voraussetzung).replace(/; /g, "<br>") },
      { t: "Wirkung", l: true, f: st => `${esc(st.wirkung)}<div class="hint">${esc(st.quelle || "")}</div>` },
      { t: "Kosten", l: true, f: st => esc(st.kosten).replace(/; /g, "<br>") },
      { t: "", l: true, f: knopfW }], F.plan, { scroll: true }) : `<p class="hint">Kein Schritt – für diesen Schwerpunkt ist nichts knapp oder es fehlen Daten.</p>`}
    <p class="hint">Reihenfolge: 1. Ausbau mit bekannten Spielwerten (Rohstoff, eigene Gebäude unter der Höchststufe), 2. Neubau eines Herstellers
      (fehlendes Eingangsgut als Schritt davor), 3. Gebäude mit Wirkung auf den Schwerpunkt (Markt und Handel, Militär, Zivil – sofort baubare vor denen
      mit fehlendem Fortschritt), 4. Straßen zur Hauptstadt; innerhalb nach dem Rang des Guts. Ort: Ortsart, Ortsbedingung (Küste/Hafen über
      map_data/ports.csv, Fluss und See nicht prüfbar), Pops des Typs, Marktzugang. Gold-Baukosten neuer Gebäude und Straßen zeigt das Spiel im
      Baumenü bzw. beim Straßenbau – hier Baugüter und der Preis je Entfernungseinheit. Gold jetzt: ${fmt(lvW.gold, 2)}, Saldo ${sgn(lvW.saldo_spiel, 2)} je Monat (Wirtschaftsfenster, ${esc(datumW)}).</p></div>`;
  return { head, body: wahl + `<div class="stgrid">${planKarte}${bedarfKarte}${bestellKarte}${kettenKarte}${wirkKarte}</div>` };
}

function empfehlungen(d, P) {
  // Handelsbestellungen je Schwerpunkt (29.10.): der Server liefert eine Empfehlung je Schwerpunkt (Feld fokus) – gezeigt wird nur die
  // des in der Kachel Wirtschaftsplan gewählten
  // Reihenfolge je Schwerpunkt (05.11.): rechnet der Server (empfehlungen.reihe, Feld rang) – dieselbe wie in der Seitenleiste im Spiel
  const fkE = wpFokus(d), rangE = r => r.rang?.[fkE] ?? 9999;
  const E = (d.empfehlungen || []).filter(r => !r.fokus || r.fokus === fkE).sort((a, b) => rangE(a) - rangE(b)), marks = d.markierungen || [];
  const n = p => E.filter(r => r.prio === p).length;
  const head = hd({
    big: [{ l: "Empfehlungen", v: String(E.length) },
          { l: "wichtig", v: String(n("hoch")), cls: n("hoch") ? "neg" : "" }, { l: "mittel", v: String(n("mittel")) },
          { l: "später", v: String(n("niedrig")) }],
    // die drei wichtigsten im geschlossenen Kopf
    small: E.slice(0, 3).map(r => ({ l: EMPF_PRIO[r.prio] || r.prio, v: esc(r.titel), cls: "wort", mw: 560 })),
  });
  if (!E.length) return { head, body: `<p class="hint">Keine Empfehlung – keine Regel schlägt an.</p>` };
  const karte = r => {
    const mk = r.marker && marks.find(m => m.text === r.marker);
    const knopf = !r.marker ? "" : mk ? `<span class="hint">markiert am ${esc(mk.datum)}</span>`
      : `<button data-ueb-datum="${esc(r.datum)}" data-ueb-text="${esc(r.marker)}" data-ueb-partie="${esc(d.meta.partie_id)}"
           title="Markierung „${esc(r.marker)}“ zum ${esc(r.datum)} anlegen – die Kachel Entscheidungen misst die Wirkung">umgesetzt – markieren</button>`;
    return `<div class="card empf ${esc(r.prio)}"><h3><span class="tag ${esc(r.prio)}">${esc(EMPF_PRIO[r.prio] || r.prio)}</span> ${esc(r.titel)}</h3>
      ${r.fokus ? `<p class="hint">Zum gewählten Schwerpunkt „${esc(r.fokus_name || r.fokus)}“ (Kachel Wirtschaftsplan) – ein anderer Schwerpunkt zeigt andere Vorschläge.</p>` : ""}
      ${r.fokus_wert?.[fkE] ? `<p class="hint">Passt zum Schwerpunkt: ${esc(r.fokus_wert[fkE][1])}</p>` : ""}
      <h5>Was tun</h5><p>${esc(r.handlung)}</p>
      <h5>Warum</h5><ul>${r.gruende.map(g => `<li>${esc(g)}</li>`).join("")}</ul>
      <h5>Wirkung – ${esc(EMPF_WIRK[r.wirkung.art] || r.wirkung.art)}</h5><p>${esc(r.wirkung.text)}</p>
      <div class="empf-fuss">${r.kachel && r.kachel !== "empfehlungen" ? `<a href="#${esc(r.kachel)}" data-oeffne="${esc(r.kachel)}">→ Kachel ${esc(EMPF_KACHEL[r.kachel] || (r.kachel.startsWith("krieg_") ? "Krieg" : r.kachel))}</a>` : ""}${knopf}</div></div>`;
  };
  return { head, body: `<div class="stgrid">${E.map(karte).join("")}</div>
    <p class="hint">Regeln auf Spielstand ${esc(d.meta.datum)} und Daten-Mod ${esc(d.live?.at(-1)?.datum || "–")}. Wirkung: <b>berechnet</b> = geprüfte Formel
      (analysis/MECHANIK.md), <b>Spielwert</b> = Zahl so, wie das Spiel sie zeigt, <b>messen</b> = keine Formel – nach dem Umsetzen markieren, die Kachel
      Entscheidungen vergleicht 6 Monate vorher und nachher. Zustände (Warnungen) stehen weiter in den Kachelköpfen.</p>` };
}

function entscheidungen(d, P) {
  const L = d.live || [], marks = d.markierungen, aend = d.aenderungen || [];
  const lastX = L.length ? L.at(-1).jahr : (d.punkte.at(-1)?.jahr ?? 0);
  const schon = new Set(marks.map(m => `${m.datum}|${m.text}`));
  const offen = aend.filter(e => !schon.has(`${e.datum}|${e.text}`));
  const neu12 = aend.filter(e => e.jahr >= lastX - 1 + 1e-6);
  const m = marks.at(-1), e0 = aend[0];
  const head = hd({
    big: [{ l: "markierte Entscheidungen", v: String(marks.length) },
          { l: "erkannte Änderungen (12 Monate)", v: String(neu12.length), title: "Änderungen der letzten 12 Monate laut Spielständen und Monatswerten" }],
    small: [m ? { l: "zuletzt markiert", v: `${esc(m.datum)} – ${esc(m.text)}`, cls: "wort" } : { l: "zuletzt markiert", v: "–" },
            e0 && { l: "letzte erkannte Änderung", v: `${esc(e0.datum)} – ${esc(e0.text)}`, mw: 420 }],
  });
  const tag = esc(L.at(-1)?.datum || d.meta.datum);
  const zeit = e => e.von ? `<span class="hint">zwischen ${esc(e.von)} und</span> ${esc(e.datum)}` : esc(e.datum);
  const erkannt = offen.length ? `<div class="card" style="margin-top:14px"><h3>Erkannte Änderungen – ${offen.length}</h3>${table([
      { t: "Datum", f: zeit }, { t: "Art", f: e => esc(e.art) }, { t: "Was", l: true, f: e => esc(e.text) },
      { t: "", f: e => `<button data-ueb-datum="${esc(e.datum)}" data-ueb-text="${esc(e.text)}" data-ueb-partie="${esc(d.meta.partie_id)}" title="als Entscheidung markieren">übernehmen</button>` }], offen)}
    <p class="hint">Aus den Spielständen (Privilegien, Gesetze, Reformen, Gebäude, Orte – Datum = späterer Spielstand) und den Monatswerten des
      Daten-Mods (Herrscherwechsel, Regler ab 5 Prozentpunkten, Klientelländer, Rivalen; Privilegien auf den Monat genau, wenn erkennbar).
      Kabinettsaktionen mit ihrem Startdatum. Gebäude über ihre feste Nummer, Ort aus dem neuesten Spielstand – bei abgerissenen Gebäuden
      aus Spielständen vor Mai 1340 kann der Ortsname noch um einen Ort verschoben sein.</p></div>` : "";
  return { head, body: `<div class="marks"><form id="markform">
      <input name="datum" value="${tag}" size="10" pattern="\\d{3,4}\\.\\d{1,2}\\.\\d{1,2}" required title="Spieldatum JJJJ.M.T, z. B. ${tag}">
      <input name="text" placeholder="z. B. Steuern der Bürger erhöht, Straße nach X gebaut …" required>
      <button class="primary">Markieren</button></form>
    ${wirkung(d, P)}
    <p class="hint">Ø der 6 Monate vor dem Datum gegen Ø der 6 Monate danach (Daten-Mod, Einkommen und Saldo wie im Wirtschaftsfenster); Δ erst ab
      3 Monaten danach. Andere Einflüsse wirken mit – ein Hinweis, kein Beweis. Markierungen erscheinen als Linien in den Diagrammen der Kachel Verlauf.</p>
    ${erkannt}</div>` };
}
// Erkannte Änderung als Entscheidung übernehmen (ein Klick: Datum und Text)
document.addEventListener("click", async e => {
  const b = e.target.closest?.("button[data-ueb-datum]");
  if (!b) return;
  b.disabled = true;
  const r = await fetch("/api/markierung", { method: "POST", body: JSON.stringify({ partie: b.dataset.uebPartie, datum: b.dataset.uebDatum, text: b.dataset.uebText }) });
  if (!r.ok) { alert((await r.json()).fehler || "Fehler"); b.disabled = false; return; }
  load();
});

// Stände (Nutzerwunsch 01.10., Punkte 1–6): Werte wie im Ständefenster des Spiels (Macht, Bevölkerung, Zufriedenheit >
// Ausgewogenheit; Krone mit Ø Kontrolle, Gemeine mit Bauernbefreiung – government_lateralview.gui). Macht der Stände steht in der
// Kopfzeile: hier nur die kleine Torte im Kopf (Nutzerwunsch), keine eigene Karte. Je Stand eine Karte; Aufschlüsselungen des
// Spiels aufklappbar je Zeile. Zufriedenheit, Veränderung und Ausgewogenheit aus dem Spieltext GetSatisfactionTooltip (zwei
// Nachkommastellen wie im Spiel; die Mod-Werte sind auf 0,001 gerundet).
// Schwellen laut Spiel: unter 25 % keine Steuern und keine Aufgebote (GetCollectTaxesInfo/GetRaiseLevyInfo), 50 % = Nullpunkt
// der Zufriedenheits-Wirkung (LOW_SATISFACTION_THRESHOLD, analysis/MECHANIK.md).
function staende(d, P) {
  const lv = P.lv, S = (P.LD.staende || [])[0] || {}, A = P.A, W = P.W;
  const AW = d.alles?.werte || {}, AT = d.alles?.texte || {};
  const AS = AW.stand || {}, TS = AT.stand || {}, L = Object.values(AW.land || {})[0] || {}, LM = Object.values(AW.landmod || {})[0] || {};
  const TL = Object.values(AT.land || {})[0] || {};
  const estNames = Object.fromEntries((A.staende || []).map(e => [e.stand, e.name]));
  const REIHE = ["crown_estate", "nobles_estate", "clergy_estate", "burghers_estate", "peasants_estate"];   // Reihenfolge wie im Spiel
  let ests = Object.keys(AS).length ? Object.keys(AS).filter(e => AS[e].ExistsForCountry !== 0)
    : Object.keys(lv).filter(k => /^power_\w+_estate$/.test(k)).map(k => k.slice(6));
  if (!ests.length) ests = (A.staende || []).map(e => e.stand);
  ests.sort((a, b) => (REIHE.indexOf(a) + 1 || 99) - (REIHE.indexOf(b) + 1 || 99));
  const name = e => esc(estNames[e] || e);
  const sw = (e, k) => AS[e]?.[k];
  const power = e => sw(e, "power") ?? lv["power_" + e] ?? (A.staende || []).find(x => x.stand === e)?.mod?.power;
  // „Derzeit: 49.63% / Monatliche Veränderung: +0.32% / Ausgewogenheit: 54.48%“ -> Anteile; sonst Mod-Werte
  const tip = e => {
    const t = String(TS[e]?.GetSatisfactionTooltip || ""), z = rx => { const m = t.match(rx); return m ? +m[1] / 100 : null; };
    return { sat: z(/Derzeit:\s*([-+]?[\d.]+)%/) ?? sw(e, "satisfaction") ?? lv["sat_" + e],
             chg: z(/Monatliche Veränderung:\s*([-+]?[\d.]+)%/) ?? sw(e, "monthly_satisfaction_change") ?? S["sat_change_" + e],
             tgt: z(/Ausgewogenheit:\s*([-+]?[\d.]+)%/) ?? sw(e, "target_satisfaction") ?? S["sat_target_" + e] };
  };
  const pz = (v, n = 2) => num(v) ? `${fmt(v * 100, n)} %` : "–";
  // Zeile „Steuern für Adelsstand: -30.43%“ der Ausgewogenheit
  const steuerZeile = e => { const m = String(TS[e]?.GetTargetSatisfactionInfo || "").match(/Steuern für [^:\n]+:\s*([-+]?[\d.]+)%/); return m ? +m[1] / 100 : null; };
  // Spieltext-Zeilen „Name: Wert“ kurz in einer Zeile („Monatliches Prestige -0.00 · Monatliche Legitimität -0.00“)
  const kurz = t => String(t || "").split("\n").map(z => z.trim()).filter(z => z.includes(":")).map(z => esc(z.replace(/:\s*/, " "))).join(" · ");
  // Zeile mit Wert; mit Text klappt die Aufschlüsselung des Spiels darunter auf (gleiche Darstellung wie breakdown)
  const zl = (l, v, txt, code = "") => txt
    ? `<details class="bk"><summary${code ? ` title="Aufschlüsselung des Spiels: ${esc(code)}"` : ""}><span class="bl">${l}</span><span class="bv">${v}</span></summary><div class="bsub">${breakdown(txt)}</div></details>`
    : `<div class="bk"><span class="bl">${l}</span><span class="bv">${v}</span></div>`;

  // Privilegien je Stand: Macht und Ausgewogenheit live (Mod privileg: GetPower, GetSatisfaction), Wirkung als Spieltext
  const AP = AW.privileg || {}, TP = AT.privileg || {};
  const privOf = {};
  for (const k of A.privilegien || []) { const p = (W.privilegien || {})[k]; if (p) (privOf[p.stand] ??= []).push(p); }
  const privListe = e => { const L = (privOf[e] || []).slice().sort((a, b) => (AP[b.name]?.GetPower ?? 0) - (AP[a.name]?.GetPower ?? 0));
    return L.length ? table([
      { t: "Privileg", l: true, f: p => { const txt = TP[p.name]?.GetEffectText || p.wirkungen.map(x => `${x.name}: ${x.wert}`).join("\n");
          return `<details><summary>${esc(p.name)}</summary>${breakdown(txt)}</details>`; } },
      { t: "Macht", f: p => num(AP[p.name]?.GetPower) ? sgn(AP[p.name].GetPower * 100, 0) + " %" : "–" },
      { t: "Ausgew.", f: p => num(AP[p.name]?.GetSatisfaction) ? sgn(AP[p.name].GetSatisfaction * 100, 1) + " %" : "–" }], L, { scroll: false }) : ""; };

  const karte = e => {
    const { sat, chg, tgt } = tip(e), krone = e === "crown_estate", T = TS[e] || {};
    const monate = num(sat) && num(tgt) && num(chg) && Math.abs(chg) >= 0.00005 && Math.sign(tgt - sat) === Math.sign(chg) ? (tgt - sat) / chg : null;
    const pop = T.GetTotalPopulation || fmt(sw(e, "GetTotalPopulationNoFormat"), 1);
    const mt = String(T.GetMaxTax || "").match(/([-+]?[\d.]+)%/);
    const st = steuerZeile(e), maxT = mt ? +mt[1] / 100 : sw(e, "GetMaxTaxValue"), regler = sw(e, "estate_tax_rate") ?? lv["taxrate_" + e];
    const rows = [
      zl("Macht", pz(power(e), 1), [T.GetEstatePowerInfo, T.GetEstatePowerInfoBreakdown].filter(Boolean).join("\n"), "GetEstatePowerInfoBreakdown"),
      zl("Bevölkerung", esc(pop)),                       // GetRelativePowerDesc wiederholt nur die Macht-Aufschlüsselung
      krone && zl("Ø Kontrolle", pz(L.GetAverageControl ?? L.average_control), TL.GetAverageControlInfo, "GetAverageControlInfo"),
      krone && num(L.num_reforms) && zl("Reformen", `${fmt(L.num_reforms, 0)} / ${fmt(L.num_reforms + (L.num_open_reform_slots ?? 0), 0)}`),
      e === "peasants_estate" && num(sw(e, "GetAvgEnfranchisment")) && zl("Bauernbefreiung", pz(sw(e, "GetAvgEnfranchisment"), 1)
        + (num(LM.global_peasant_enfranchisment) ? ` <span class="hint">Landesmodifikator ${sgn(LM.global_peasant_enfranchisment * 100, 1)} %</span>` : ""),
        modDesc(d, "global_peasant_enfranchisment"), "GetDescriptionFor('global_peasant_enfranchisment')"),
      !krone && zl("Zufriedenheit", pz(sat), T.GetSatisfactionImpact ? `Wirkung:\n${String(T.GetSatisfactionImpact).split("\n").map(z => "  " + z).join("\n")}` : "", "GetSatisfactionImpact"),
      !krone && zl("Ausgewogenheit", pz(tgt), T.GetTargetSatisfactionInfo, "GetTargetSatisfactionInfo"),
      !krone && zl("Veränderung / Monat", `${num(chg) ? sgn(chg * 100, 2) + " %" : "–"}${num(monate) ? ` <span class="hint">· erreicht in ${fmt(monate, 0)} Mon.</span>` : ""}`,
        T.GetMonthlySatisfactionChangeInfo, "GetMonthlySatisfactionChangeInfo"),
      !krone && num(maxT) && maxT > 0 && zl("Steuer", `${pz(maxT)} <span class="hint">· Regler ${pct(regler, 0)}</span>`, T.GetTaxBaseInfo, "GetTaxBaseInfo"),
      !krone && num(st) && zl("Steuer kostet Ausgewogenheit", `<span class="neg">${sgn(st * 100, 2)} %</span>`),
      !krone && num(maxT) && maxT > 0 && num(sw(e, "GetLastMonthsTax")) && zl("Steuern letzter Monat", fmt(sw(e, "GetLastMonthsTax"), 2)),
      zl("Wirkung der Macht", "", T.GetPowerImpactInfo, "GetPowerImpactInfo"),
      !krone && zl("Gebäude", fmt(sw(e, "num_buildings_owned_by_estate") ?? S["buildings_" + e], 0)),
    ].filter(Boolean).join("");
    const nP = sw(e, "num_privileges") ?? S["privileges_" + e], nM = sw(e, "num_possible_privileges") ?? S["privileges_possible_" + e];
    return `<div class="card" style="border-top:3px solid var(${ESTATE_COLOR[e] || "--c8"})"><h3>${name(e)}</h3>
      <div class="brk">${rows}</div>
      ${!krone ? `<h5>Privilegien – ${fmt(nP, 0)} von ${fmt(nM, 0)} möglich</h5>${privListe(e) || `<div class="hint">keine</div>`}` : ""}</div>`;
  };

  // Wirtschaft der Stände wie im Spiel (live): steuerpflichtiges Einkommen − Steuern − Pops + Posten aus GetEconomyInfo = Saldo
  // (nachgerechnet 01.10. an allen vier Ständen, auf 0,01 genau; „Städte“ city_income gehört nicht dazu)
  const oek = ests.filter(e => e !== "crown_estate").map(e => {
    const posten = Object.fromEntries(String(TS[e]?.GetEconomyInfo || "").split("\n").map(z => z.match(/^\s*(.+?):\s*([-+]?[\d.]+)\s*$/)).filter(Boolean).map(m => [m[1], +m[2]]));
    const lm = (A.staende || []).find(x => x.stand === e)?.letzter_monat || {};
    const vor = sw(e, "GetLastMonthsIncomeBeforeTax") ?? lm.taxable_income, steuer = sw(e, "GetLastMonthsTax") ?? lm.paid_taxes ?? 0, pops = sw(e, "GetLastMonthsExpense") ?? lm.pop_expense;
    const saldo = sw(e, "GetBalance") ?? (A.staende || []).find(x => x.stand === e)?.balance;
    const summe = (vor ?? 0) - steuer - (pops ?? 0) + sum(Object.values(posten));
    // aktuelles Gold (Nutzerwunsch 01.10.): GetGold, sonst estate_gold; der Spielstand führt kein Gold-Feld der Stände (= 0)
    const gold = sw(e, "GetGold") ?? sw(e, "estate_gold") ?? S["gold_" + e];
    return { e, vor, steuer, pops, posten, saldo, gold, ok: num(saldo) && Object.keys(posten).length && Math.abs(summe - saldo) < 0.02 };
  });
  const postenNamen = [...new Set(oek.flatMap(x => Object.keys(x.posten)))];
  const oekKarte = oek.length ? `<div class="card"><h3>Wirtschaft der Stände – letzter Monat</h3>${table([
      { t: "Stand", f: x => name(x.e) }, { t: "steuerpfl. Einkommen", f: x => fmt(x.vor, 2) }, { t: "− Steuern", f: x => fmt(-x.steuer, 2) },
      { t: "− Pops", f: x => fmt(num(x.pops) ? -x.pops : null, 2) },
      ...postenNamen.map(n => ({ t: n, f: x => x.posten[n] != null ? sgn(x.posten[n], 2) : "–", cls: x => posneg(x.posten[n]) })),
      { t: "= Saldo", f: x => `${fmt(x.saldo, 2)}${x.ok ? ` <span class="hint" title="Summe der Posten = Saldo des Spiels">✓</span>` : ""}`, cls: x => posneg(x.saldo) },
      { t: "Gold aktuell", f: x => fmt(x.gold, 2) }], oek)}
    <p class="hint">Live ${esc(d.alles?.datum?.stand || "")}: steuerpflichtiges Einkommen, Steuern und Pops (GetLastMonthsIncomeBeforeTax, GetLastMonthsTax,
      GetLastMonthsExpense), übrige Posten aus der Wirtschafts-Aufschlüsselung des Spiels (GetEconomyInfo), Saldo = GetBalance;
      ✓ = Summe der Posten ergibt den Saldo. Gold aktuell = GetGold (Daten-Mod); im Spielstand steht bei 0 kein Gold-Feld.</p></div>` : "";

  // Kopf: groß je Stand Zufriedenheit mit Ausgewogenheit und Veränderung je Monat
  const ohneKrone = ests.filter(e => e !== "crown_estate");
  const steuernSumme = sum(ohneKrone.map(e => sw(e, "GetLastMonthsTax") ?? (A.staende || []).find(x => x.stand === e)?.letzter_monat?.paid_taxes));
  // Torte der Macht nur in der aufgeklappten Kachel, mit Beschriftung (Nutzerwunsch 01.10.: zugeklappt unbeschriftet nutzlos)
  const head = `<div style="display:flex;gap:16px;align-items:center;width:100%"><span class="hdpie">${pieChart(ests.map(e => ({ label: estNames[e] || e, value: power(e) ?? 0, color: ESTATE_COLOR[e] || "--c8" })), { size: 72, fmtV: v => pct(v, 0) })}</span>
    ${hd({
      big: ohneKrone.map(e => { const { sat, chg, tgt } = tip(e);
        return { l: estNames[e] || e, v: pz(sat), t: num(chg) ? trend(chg * 100, 2) : "", u: `Ausgewogenheit ${pz(tgt)}`, bar: sat,
                 title: "Zufriedenheit wie im Ständefenster; Pfeil = Veränderung je Monat (Prozentpunkte); darunter die Ausgewogenheit, der sich die Zufriedenheit annähert" }; }),
      small: [{ l: "Steuern der Stände / Monat", v: fmt(steuernSumme, 2), title: "Summe der Steuern aller Stände im letzten Monat (GetLastMonthsTax)" },
              { l: "Privilegien", v: `${fmt(sum(ohneKrone.map(e => sw(e, "num_privileges") ?? S["privileges_" + e])), 0)} <i>von ${fmt(sum(ohneKrone.map(e => sw(e, "num_possible_privileges") ?? S["privileges_possible_" + e])), 0)} möglich</i>` },
              { l: "Ø Zufriedenheit der Stände", v: pct(L.average_estate_satisfaction ?? lv.average_estate_satisfaction, 0),
                title: "Durchschnitt der Stände ohne Krone (average_estate_satisfaction) – nicht die Zufriedenheit der Pops aus „Land und Leute“" }],
      warn: ohneKrone.flatMap(e => {
        const { sat, tgt } = tip(e), n = esc(estNames[e] || e);
        if (num(sat) && sat < 0.25) return [`${n} unter 25 % (${pz(sat)}) – keine Steuern und keine Aufgebote mehr`];
        if (num(sat) && sat < 0.5) return [`${n} unter 50 % (${pz(sat)}) – Wirkung negativ${TS[e]?.GetSatisfactionImpact ? `: ${kurz(TS[e].GetSatisfactionImpact)}` : ""}`];
        return num(tgt) && tgt < 0.5 ? [`${n}: Ausgewogenheit ${pz(tgt)} unter 50 %`] : [];
      }),
    })}</div>`;
  return { head, body: `<div class="stgrid">${ests.map(karte).join("")}</div>${oekKarte}
    <p class="hint">Werte live ${esc(d.alles?.datum?.stand || "")} (Daten-Mod), Zufriedenheit/Ausgewogenheit aus dem Spieltext. Unter 25 % Zufriedenheit
      kann ein Stand keine Steuern und keine Aufgebote mehr leisten (Spieltext); unter 50 % kehrt sich die Wirkung der Zufriedenheit um.
      „erreicht in x Mon.“ bei gleichbleibender Veränderung. Bauernbefreiung: Die Pops der Gemeinen erhalten nur diesen Anteil ihres
      Reichtumsanteils, der Rest geht an den Adelsstand (Spieltext); Aufschlüsselung des Landesmodifikators aufklappbar (Daten-Mod ab 0.16).</p>` };
}

// Regierung und Gesellschaft (Nutzerwunsch 30.09., Punkte 1–6): Kopf ohne Legitimität/Stabilität (stehen in der Kopfzeile),
// Kabinett mit „läuft seit“ und Wirkung je Zeile, Gesetze und Reformen mit Wirkung aufklappbar, Karten Parlament und Hof und
// Dynastie, Gesellschaftswerte mit monatlicher Verschiebung je Achse.
function regierung(d, P) {
  const A = P.A, W = P.W, LD = P.LD, lv = P.lv;
  const AW = d.alles?.werte || {}, AT = d.alles?.texte || {};
  const L = Object.values(AW.land || {})[0] || {}, LM = Object.values(AW.landmod || {})[0] || {};
  const rolle = { herrscher: "Herrscher", erbe: "Erbe", gemahl: "Gemahl(in)", kabinett: "Kabinett" };
  // nur Herrscher, Erbe, Gemahl (ab Mod 0.19 gibt es auch Heerführer im Krieg, Rolle fuehrer)
  const ch = (LD.charakter || []).filter(c => ["herrscher", "erbe", "gemahl"].includes(c.rolle));
  const ruler = ch.find(c => c.rolle === "herrscher"), erbe = ch.find(c => c.rolle === "erbe");
  // Angaben des Spiels zum Herrscher (Person.GetDetailedInformation): Eigenschaften, seit wann, Personalunion, Ehe
  const rInfo = String((ruler && AT.person?.[ruler.id]?.GetDetailedInformation) || "");
  const zeile = rx => (rInfo.match(rx) || [])[1];
  const eigenschaften = zeile(/^Eigenschaften:\s*(.+)$/m);
  const seit = zeile(/\(seit ([^)]+)\)/);
  const union = zeile(/^(Anführer von .+)$/m);
  const ehe = zeile(/^Verheiratet mit (.+)$/m);
  const datum = s => { const [y, m, t] = String(s || "").split(".").map(Number); return y ? `${t}.${m}.${y}` : "–"; };
  const personen = ch.length ? table([
    { t: "Rolle", f: c => rolle[c.rolle] || esc(c.rolle) }, { t: "Name", l: true, f: c => esc(c.name) },
    { t: "Verw.", f: c => fmt(c.adm, 0) }, { t: "Dipl.", f: c => fmt(c.dip, 0) }, { t: "Mil.", f: c => fmt(c.mil, 0) },
    { t: "Alter", f: c => fmt(c.age, 0) },
    { t: "Eigenschaften", l: true, f: c => c === ruler && eigenschaften ? esc(eigenschaften) : fmt(c.traits, 0) }], ch, { scroll: false }) : "";
  // Kabinett: die Mod-Zahl „Tage“ ist negativ = Tage seit Beginn der Aktion (geprüft 30.09.: 3.7.1341 bis 1.1.1344 = 912 Tage,
  // GetDaysUntilFullyImplemented des Spiels liefert ebenso „-912 Tage“); Beginn aus dem Spielstand (seit)
  const kabLive = LD.kabinett || [], kabSave = A.kabinett || [];
  const ziele = k => Object.values(k?.ziele || {}).filter(v => !/^\w+:\d+$/.test(v)).join(", ") || "–";
  const laeuft = k => { const s = kabSave.find(x => x.platz === k.id), t = k.tage ?? k.werte?.tage;
    return num(t) && t < 0 ? `${datum(s?.seit)} <span class="hint">${fmt(-t, 0)} Tage</span>` : num(t) ? `noch ${fmt(t, 0)} Tage` : datum(s?.seit); };
  const wirkung = (txt, label = "zeigen") => txt ? `<details><summary>${label}</summary>${breakdown(txt)}</details>` : "";
  const kab = kabLive.length ? table([
    { t: "Person", l: true, f: k => esc(k.person) }, { t: "Aktion", l: true, f: k => esc(k.aktion) },
    { t: "Fortschritt", f: k => fmt(k.fortschritt ?? k.werte?.fortschritt, 1) + " %" },
    { t: "läuft seit", f: laeuft }, { t: "Fähigkeit", f: k => fmt(k.skill ?? k.werte?.skill, 3) },
    { t: "Ziel", l: true, f: k => esc(ziele(kabSave.find(s => s.platz === k.id))) },
    { t: "Wirkung", l: true, f: k => wirkung(AT.kabinett?.[k.id]?.GetEffectiveSkillImpactInfo) }], kabLive, { scroll: false })
    : table([{ t: "Person", l: true, f: k => esc(k.person) }, { t: "Aktion", l: true, f: k => esc(k.aktion_name || "–") },
      { t: "Ziel", l: true, f: k => esc(ziele(k)) }, { t: "seit", f: k => datum(k.seit) },
      { t: "Verw./Dipl./Mil.", f: k => `${k.adm ?? "–"} / ${k.dip ?? "–"} / ${k.mil ?? "–"}` }], kabSave, { scroll: false });
  const kabMit = (LD.charakter || []).filter(c => c.rolle === "kabinett");
  // Gesellschaftswerte: Stand live (sv_…), sonst Spielstand; Verschiebung je Monat = Land-Modifikator monthly_towards_<rechts> −
  // monthly_towards_<links> (alle Quellen zusammen). Nachgerechnet 30.09. an drei Achsen: Aristokratie–Plutokratie 0,2 − 0,441 =
  // −0,24/Monat, Spielstand 1.8.1343 → live 1.1.1344 −1,21 in 5 Monaten; Leibeigenschaft −0,05 und Individualismus +0,05 ebenso.
  const gs = A.gesellschaft || {}, gn = (W.namen || {}).gesellschaft || {};
  const bars = Object.keys(gs).map(k => {
    const v = L["sv_" + k] ?? gs[k];
    const [lft, rgt] = (gn[k] || k).split(/ vs\.? /), [pl, pr] = k.split("_vs_");
    const drift = num(LM["monthly_towards_" + pr]) && num(LM["monthly_towards_" + pl]) ? LM["monthly_towards_" + pr] - LM["monthly_towards_" + pl] : null;
    const x = Math.max(-100, Math.min(100, v)), left = x < 0 ? 50 + x / 2 : 50, width = Math.abs(x) / 2;
    // Grenze in Zugrichtung = 100 × monatliche Veränderung (netto). Tooltip des Spiels (Screenshot 30.09.): „monatliche Veränderung
    // +0.26 in Richtung Dezentralisierung … Kann nicht mehr als 26.66 in Richtung Dezentralisierung vorangetrieben werden“; netto hier
    // 0,575 − 0,308 = 0,267 (das Spiel schneidet nach 2 Stellen ab). Spielhinweis: „bis auf maximal das 100-fache des derzeitigen
    // Drucks“. Liegt der Wert schon darüber (Dezentralisierung 60), steht er still.
    const ser = liveSeries(d, "sv_" + k, 60);
    let still = 0; for (let i = ser.length - 1; i > 0 && ser[i] === ser[i - 1]; i--) still++;
    const zu = num(drift) && Math.abs(drift) >= 0.005 ? (drift > 0 ? pr : pl) : null;
    const grenze = zu ? 100 * Math.abs(drift) : null, weit = zu ? (drift > 0 ? v : -v) : null;
    const dr = zu ? `${Math.abs(drift) < 0.01 ? sgn(drift, 3) : sgn(Math.trunc(drift * 100) / 100, 2)} <span class="hint">→ ${esc(drift > 0 ? rgt || pr : lft)} · ${weit >= grenze
      ? `<b>Grenze ${fmt(grenze, 1)} erreicht</b>${still >= 2 ? `, steht seit ${still} Monaten` : ""}` : `Grenze ${fmt(grenze, 1)}`}</span>` : "–";
    return `<span class="r">${esc(lft)}</span><div class="bar"><b></b><i style="left:${left}%;width:${width}%"></i></div><span>${esc(rgt || "")}</span><span class="v">${fmt(v, 0)}</span><span class="v">${dr}</span>`;
  }).join("");
  // Gesetze und Reformen mit Wirkung (Spieltexte Politik/Reform; Zuordnung über den deutschen Namen)
  const law = A.gesetze || {}, ln = (W.namen || {}).gesetze || {}, lc = (W.namen || {}).gesetz_kategorien || {};
  const gesetze = table([{ t: "Bereich", l: true, f: x => esc(lc[x[0]] || x[0]) }, { t: "Gesetz", l: true, f: x => esc(ln[x[1]] || x[1]) },
    { t: "Wirkung", l: true, f: x => wirkung(AT.politik?.[ln[x[1]]]?.GetEffectText) }], Object.entries(law), { scroll: false });
  const rn = (W.namen || {}).reformen || {};
  const reformen = (A.reformen || []).length ? table([{ t: "Reform", l: true, f: r => esc(rn[r] || r) },
    { t: "Wirkung", l: true, f: r => wirkung(AT.reform?.[rn[r]]?.GetEffectText || AT.reform?.[rn[r]]?.GetModifiersText) }], A.reformen, { scroll: false }) : "–";
  // Parlament: wieder einberufbar, wenn mehr als 59 Monate seit der letzten Einberufung vergangen sind (generic_actions/parliament.txt
  // call_parliament: months_since_last_parliament_called > define:NCountry|PARLIAMENT_COOLDOWN_MONTHS = 59)
  const hatParl = L.HasParliament === 1, mParl = L.months_since_last_parliament_called, tagt = L.remaining_parliament_days;
  const PARL_COOLDOWN = 59;
  const parlWann = num(tagt) && tagt > 0 ? `tagt noch ${fmt(tagt, 0)} Tage`
    : num(mParl) ? (mParl > PARL_COOLDOWN ? "jetzt einberufbar" : `einberufbar in ${fmt(PARL_COOLDOWN + 1 - mParl, 0)} Monaten`) : "–";
  const themen = Object.entries(AW.parlament || {}).map(([k, o]) => {
    const t = AT.parlament?.[k] || {}, sup = (String(t.GetCurrentSupport || "").match(/([-\d.]+)\s*%/) || [])[1];
    return { name: o.name || k, sup: sup != null ? +sup / 100 : null, eff: t.GetPassedEffect || t.GetModifierEffectCondensed || t.GetModifierEffect };
  });
  const parlament = hatParl ? `<div class="card"><h3>Parlament</h3>${kv([["aktive Vorhaben", fmt(L.num_of_active_parliament_agendas, 0)],
      ["nächste Einberufung", parlWann], ["letzte Einberufung", num(mParl) ? `vor ${fmt(mParl, 0)} Monaten` : "–"]])}
      ${themen.length ? table([{ t: "Thema", l: true, f: x => esc(x.name) }, { t: "Unterstützung", f: x => pct(x.sup, 0) },
        { t: "Wirkung bei Annahme", l: true, f: x => wirkung(x.eff) }], themen, { scroll: false }) : ""}
      <p class="hint">Einberufbar nach mehr als 59 Monaten seit der letzten Einberufung (Spieldatei call_parliament); Themen und Unterstützung laut Spiel.</p></div>` : "";
  // Hof und Dynastie
  const DY = Object.values(AW.dynastie || {})[0] || {}, DT = Object.values(AT.dynastie || {})[0] || {};
  const hof = Object.values(AW.person || {}).filter(p => p.name);
  // Hof und Dynastie – steht in derselben Karte wie die Reformen (Nutzerwunsch 30.09.)
  const hofInhalt = `${kv([
      ["Erbe", erbe ? esc(erbe.name) : `<span class="neg">keiner</span> <span class="hint">laut Daten-Mod</span>`],
      seit && ["Herrscher seit", esc(seit)], union && ["Personalunion", esc(union.replace(/^Anführer von /, "Anführer: "))], ehe && ["verheiratet mit", esc(ehe)],
      DY.name && ["Dynastie", `${esc(DY.name)} <span class="hint">${fmt(DY.GetNumOfLivingCharacters, 0)} lebende, ${fmt(DY.num_adult_available_dynasty_members, 0)} erwachsene verfügbare Mitglieder</span>`]])}
      ${rInfo ? `<details class="more"><summary>Herrscher – Angaben des Spiels</summary>${breakdown(rInfo)}</details>` : ""}
      ${DT.GetLivingMembersInfo ? `<details class="more"><summary>lebende Mitglieder der Dynastie</summary>${breakdown(DT.GetLivingMembersInfo)}</details>` : ""}
      ${DT.GetRulerHistoryInfo ? `<details class="more"><summary>Herrschergeschichte</summary>${breakdown(DT.GetRulerHistoryInfo)}</details>` : ""}
      ${hof.length ? `<details class="more"><summary>Personen des Landes – ${hof.length}</summary>${table([{ t: "Name", l: true, f: p => esc(p.name) },
        { t: "Alter", f: p => fmt(p.GetAgeInYears, 0) }, { t: "im Kabinett", f: p => p.HoldsCabinetPosition ? "ja" : "" }],
        hof.slice().sort((a, b) => (b.HoldsCabinetPosition || 0) - (a.HoldsCabinetPosition || 0)), { scroll: false })}</details>` : ""}`;
  // Politischer Einfluss (1.4): Stand, Veränderung je Monat und Tooltip der Kopfleiste (Mod ab 0.24), Preise der Aktionen (Spieldateien)
  const TL = Object.values(AT.land || {})[0] || {};
  const peWert = lv.political_influence ?? L.political_influence ?? L.cur_political_influence, peMon = L.monthly_political_influence;
  const peAnteil = L.political_influence_percentage, peMax = L.curmax_political_influence;
  const peTeuer = (d.einfluss_preise || []).filter(p => !num(peWert) || p.einfluss > peWert).length;
  // Bürokratien (29.10., Patch 1.4.5): eingeführte laut Daten-Mod (buerokratie, Name) und jede mit Auswirkung ≠ 0 – Modifikator
  // <schlüssel>_impact_modifier („Auswirkung (Consejo de Castilla)“, landmod) mit seinen Quellen laut Spieldateien
  const BW = d.buerokratien || {};
  const bAktiv = Object.values(AW.buerokratie || {}).map(b => b.name).filter(Boolean);
  const bListe = Object.entries(BW).map(([k, b]) => ({ k, ...b, imp: b.wirkung ? LM[b.wirkung] : null, aktiv: bAktiv.includes(b.name) }))
    .filter(b => b.aktiv || (num(b.imp) && b.imp !== 0))
    .concat(bAktiv.filter(n => !Object.values(BW).some(b => b.name === n)).map(n => ({ k: n, name: n, aktiv: true, quellen: [] })));
  const bQuellen = b => (b.quellen || []).map(q => `${esc(q.name)}${q.teil ? ` (${esc(q.teil)})` : ""}: ${sgn(q.wert * 100, 0)} %`).join("<br>");
  const buero = bListe.length ? `<div class="card"><h3>Bürokratien</h3>${table([
      { t: "Bürokratie", l: true, f: b => `<span title="${esc(b.beschreibung || "")}">${esc(b.name)}</span>` },
      { t: "eingeführt", f: b => b.aktiv ? "ja" : "–" },
      { t: "Auswirkung", f: b => num(b.imp) ? `${sgn(b.imp * 100, 0)} %` : "–", cls: b => posneg(b.imp) },
      { t: "Quellen der Auswirkung (Spieldateien)", l: true, f: b => bQuellen(b) || "–" }], bListe, { scroll: false })}
    <p class="hint">Auswirkung = Modifikator „Auswirkung (…)“ der Bürokratie (&lt;Schlüssel&gt;_impact_modifier, Daten-Mod landmod). Wie stark er die
      Bürokratie verändert, zeigt das Spiel im Tooltip der Bürokratie – hier nicht nachgerechnet. Beschreibung beim Zeigen auf den Namen.</p></div>` : "";
  const einfluss = num(peWert) ? `<div class="card"><h3>Politischer Einfluss</h3><div class="brk">
      ${zeileAuf("Stand", `${fmt(peWert, 1)}${num(peMax) ? ` <span class="hint">von ${fmt(peMax, 0)}</span>` : ""}${num(peAnteil) ? ` <span class="hint">${pct(peAnteil, 0)}</span>` : ""}`,
                 TL.pe_beschreibung, "GetCurrencyTooltipDescription('political_influence')")}
      ${zeileAuf("Veränderung je Monat", num(peMon) ? sgn(peMon, 2) : "–", TL.pe_aufschluesselung, "GetMonthlyCurrencyChangeBreakdown('political_influence')")}</div>
      ${(d.einfluss_preise || []).length ? `<details class="more"><summary>Preise in Politischem Einfluss – ${d.einfluss_preise.length} Aktionen${peTeuer ? `, ${peTeuer} teurer als der Stand` : ""}</summary>
        ${table([{ t: "Aktion", l: true, f: p => esc(p.name) }, { t: "Einfluss", f: p => `<span class="${p.einfluss > peWert ? "neg" : ""}">${fmt(p.einfluss, 0)}</span>` },
          { t: "weitere Kosten", l: true, f: p => (p.weitere || []).map(esc).join(", ") || "–" }],
          d.einfluss_preise, { scroll: false })}</details>` : ""}
      <p class="hint">Politischer Einfluss ersetzt in 1.4 die Selbstgefälligkeit. Preise = Grundpreise der Spieldateien (prices) ohne Modifikatoren;
        rot = mehr als der Stand. Aufschlüsselungen wie im Tooltip der Kopfleiste (Daten-Mod ab 0.24).</p></div>` : "";
  const head = hd({
    big: [ruler && { l: "Herrscher (Verw./Dipl./Mil.)", v: `${esc(ruler.name)} <i>${fmt(ruler.adm, 0)} / ${fmt(ruler.dip, 0)} / ${fmt(ruler.mil, 0)} · ${fmt(ruler.age, 0)} J.</i>`, cls: "wort" },
          // Kabinettsaktionen untereinander (bis zu 5 möglich, Nutzerwunsch 30.09.)
          kabLive.length ? { l: "Kabinett", v: kabLive.map(k => `${esc(k.aktion)} <i>${fmt(k.fortschritt, 0)} %</i>`).join("<br>"), cls: "wort" }
                         : kabSave.length ? { l: "Kabinett", v: kabSave.map(k => esc(k.aktion_name || "–")).join("<br>"), cls: "wort" } : null],
    small: [num(lv.ruler_reign) && { l: "Regierungszeit", v: `${fmt(lv.ruler_reign, 0)} Jahre` },
            ruler && { l: "Erbe", v: erbe ? esc(erbe.name) : "keiner", cls: erbe ? "" : "neg" },
            num(lv.complacency) && { l: "Selbstgefälligkeit", v: fmt(lv.complacency, 2), title: "complacency laut Daten-Mod (bis 1.3)" },
            num(peWert) && { l: "Politischer Einfluss", v: `${fmt(peWert, 1)}${num(peMon) ? ` <i>${sgn(peMon, 2)} / Monat</i>` : ""}`,
                             title: "political_influence laut Daten-Mod (ab 1.4)" },
            // Gesetze/Reformen und Parlament in der Zeile darunter (Nutzerwunsch 30.09.)
            { umbruch: true },
            { l: "Gesetze / Reformen", v: `${Object.keys(law).length} / ${(A.reformen || []).length}${num(lv.reform_slots_open) ? ` <i>${fmt(lv.reform_slots_open, 0)} frei</i>` : ""}` },
            hatParl && { l: "Parlament", v: `${fmt(L.num_of_active_parliament_agendas, 0)} Vorhaben`, u: parlWann }],   // Einberufung darunter
  });
  return { head, body: `<div class="grid2">
      <div class="card"><h3>Herrscherhaus</h3>${personen || `<div class="empty">Live-Daten ab Mod 0.9</div>`}</div>
      <div class="card"><h3>Kabinett</h3>${kab}${kabMit.length ? `<p class="hint">Kabinettsmitglieder: ${kabMit.map(c => `${esc(c.name)} (${fmt(c.adm, 0)}/${fmt(c.dip, 0)}/${fmt(c.mil, 0)})`).join(", ")}</p>` : ""}</div>
    </div>
    <div class="grid2">
      <div class="card"><h3>Gesellschaftswerte</h3><div class="sv sv5">${bars || `<span>–</span>`}</div>
      <p class="hint">Wert von −100 (links) bis +100 (rechts), live ${esc(lv.datum || "")}; letzte Spalte = Verschiebung je Monat aus allen Quellen
      (Land-Modifikatoren „monatlich Richtung …“, rechts − links) und Grenze in Zugrichtung = 100 × monatliche Veränderung, wie im Tooltip
      des Spiels („kann nicht mehr als … vorangetrieben werden“); darüber bewegt sich der Wert nicht weiter. Nicht aktive Achsen ausgeblendet.</p></div>
      ${parlament}
    </div>
    <div class="grid2"><div class="card"><h3>Gesetze</h3>${gesetze}</div>
      <div class="card"><h3>Reformen</h3>${reformen}<h3 style="margin-top:16px">Hof und Dynastie</h3>${hofInhalt}</div></div>
    ${einfluss || buero ? `<div class="grid2">${einfluss}${buero}</div>` : ""}` };
}

// Religion, Kultur und Kunst (Nutzerwunsch 01.10., Punkte 1, 2, 4–6 + Kultur und Kunst wie im Kulturfenster des Spiels):
// Glaubenseinigkeit und Glaubenseinfluss stehen in der Kopfzeile („Glaube“) und fehlen deshalb im Kachelkopf. Reformwunsch aus dem
// Spieltext GetReformDesireInfo (der Modifikator reform_desire 0,03 ist der Monatszuwachs +0,03 %, nicht der Stand). Die Liste aller
// Landes-Modifikatoren steht in der eigenen Kachel „Modifikatoren“ (Punkt 3a).
function religion(d, P) {
  const AW = d.alles?.werte || {}, AT = d.alles?.texte || {}, lv = P.lv;
  const L = Object.values(AW.land || {})[0] || {}, LM = Object.values(AW.landmod || {})[0] || {}, TL = Object.values(AT.land || {})[0] || {};
  const relId = Object.keys(AW.religion || {})[0], R = (AW.religion || {})[relId] || {}, TR = (AT.religion || {})[relId] || {};
  if (!relId && !num(lv.religious_unity)) return "";
  const relName = R.name || (d.bev?.religionen || []).find(r => r.staatsreligion)?.name || "Staatsreligion";
  const zl = (l, v, txt, code = "") => txt
    ? `<details class="bk"><summary${code ? ` title="Aufschlüsselung des Spiels: ${esc(code)}"` : ""}><span class="bl">${l}</span><span class="bv">${v}</span></summary><div class="bsub">${breakdown(txt)}</div></details>`
    : `<div class="bk"><span class="bl">${l}</span><span class="bv">${v}</span></div>`;
  const p1 = (v, n = 1) => num(v) ? `${sgn(v * 100, n)} %` : "–";
  // Kulturfenster zeigt abgerundet auf zwei Stellen (Mod 292,925 / +0,985 / 123,959 / −0,208 -> Spiel 292.92 / +0.98 / 123.95 / −0.21)
  const ab = v => num(v) ? Math.floor(v * 100 + 1e-6) / 100 : v;
  // „60.749M“ / „1.488M“ / „194K“ (Spieltext) -> Mio./Tsd.
  const menge = t => { const m = String(t || "").match(/([\d.,]+)\s*([MK])?/); if (!m) return "–"; const x = +m[1].replace(/,/g, "");
    return m[2] === "M" ? `${fmt(x, 2)} Mio.` : m[2] === "K" ? `${fmt(x, 0)} Tsd.` : fmt(x, 0); };

  // Reformwunsch wie im Spiel: „… liegt bei 0.00%. Der Reformwunsch ändert sich derzeit monatlich um +0.03%.“
  const rdTxt = String(TR.GetReformDesireInfo || "").replace(/der _ADJ\w* Religion/, `des ${relName}`);
  const rdM = rdTxt.match(/liegt bei\s*([-+]?[\d.]+)%/), rdC = rdTxt.match(/monatlich um\s*([-+]?[\d.]+)%/);
  const rd = rdM ? +rdM[1] / 100 : null, rdChg = rdC ? +rdC[1] / 100 : null;
  // Zehnt: Posten „Zehnt“ in der Wirtschafts-Aufschlüsselung jedes Standes (geht an das Papsttum, Spielbegriff „Zehnt“)
  const zehntJe = Object.entries(AT.stand || {}).map(([e, t]) => { const m = String(t.GetEconomyInfo || "").match(/Zehnt:\s*([-+]?[\d.]+)/);
    return m ? [e, +m[1]] : null; }).filter(Boolean);
  const zehnt = zehntJe.length ? -sum(zehntJe.map(x => x[1])) : null;
  const estName = Object.fromEntries((P.A.staende || []).map(e => [e.stand, e.name]));
  const heilBeiUns = sum(Object.values(AW.ort || {}).map(o => o.location_num_holy_sites));
  const glE = L.religious_influence ?? lv.religious_influence, glMax = LM.maximum_religious_influence, glMon = LM.monthly_religious_influence;

  // Kultur: Primärkultur = Pop-Status „Primary“ (Spielstand), Werte je Kultur aus dem Mod (kultur: Tradition, Einfluss, je Monat)
  const kulturen = d.bev?.kulturen || [];
  const primId = kulturen.find(k => k.status.includes("Primary"))?.id ?? Object.keys(AW.kultur || {})[0];
  const K = (AW.kultur || {})[primId] || {}, TK = (AT.kultur || {})[primId] || {};
  const kapUsed = L.used_cultures_capacity ?? L.GetTotalCultureCapacityUsed, kapMax = L.GetCulturalCapacity ?? LM.cultures_capacity;
  // Kosten je akzeptierter Kultur: Zeile „Friesisch (Akzeptiert): 0.15“ in GetAcceptedCulturesInfo
  const kosten = Object.fromEntries([...String(TL.GetAcceptedCulturesInfo || "").matchAll(/^(\S[^:\n]*?) \(Akzeptiert\):\s*([\d.]+)/gm)].map(m => [m[1], +m[2]]));
  const ST = { Primary: "Primärkultur", Accepted: "akzeptiert", Tolerated: "toleriert" };

  // Kopf: groß Reformwunsch · Toleranz · Kulturtradition · Kultureinfluss; klein Religion weltweit, Kardinäle, Sakralstätten, Zehnt, Kultur, Kunst
  const head = hd({
    big: [{ l: "Reformwunsch", v: num(rd) ? `${fmt(rd * 100, 2)} %` : "–", t: num(rdChg) ? trend(rdChg * 100, 2, 0) : "",
            u: num(rdChg) ? `${sgn(rdChg * 100, 2)} % je Monat` : "", title: "Reformwunsch des Glaubens laut Spiel (GetReformDesireInfo); Pfeil = Veränderung je Monat" },
          { l: "Toleranz", v: `${sgn(LM.tolerance_own, 1)} <i>/ ${sgn(LM.tolerance_heretic, 1)} / ${sgn(LM.tolerance_heathen, 1)}</i>`,
            u: "Wahrer Glaube / Ketzer / Ungläubige" },
          K.name && { l: `Kulturtradition (${K.name})`, v: fmt(ab(K.GetTradition ?? K.cultural_tradition), 2), t: trend(ab(K.GetTraditionChange), 2, 1),
            title: "Kulturtradition der Primärkultur wie im Kulturfenster; Pfeil = Veränderung je Monat" },
          K.name && { l: "Kultureinfluss", v: fmt(ab(K.GetInfluence ?? K.cultural_influence), 2), t: trend(ab(K.GetInfluenceChange), 2, 1) }],
    small: [{ l: "Gläubige weltweit", v: `${menge(TR.GetTotalPopulation)} <i>in ${fmt(R.GetNumCountries ?? R.num_countries_in_religion, 0)} Ländern</i>` },
            R.HasCardinals === 1 && { l: "Kardinäle", v: `${fmt(L.num_cardinals, 0)} <i>von ${fmt(R.total_cardinals, 0)}</i>` },
            R.HasHolySites === 1 && { l: "Sakralstätten", v: `${fmt(R.GetNumHolySites, 0)} <i>bei uns ${fmt(heilBeiUns, 0)}</i>` },
            num(zehnt) && { l: "Zehnt / Monat", v: fmt(zehnt, 2), title: "Summe des Postens „Zehnt“ der Stände (geht an das Papsttum)" },
            num(glMon) && { l: "Glaubenseinfluss / Monat", v: sgn(glMon, 2) },
            num(kapUsed) && { l: "Akzeptierte Kulturen", v: `${fmt(kapUsed, 2)} <i>/ ${fmt(kapMax, 2)}</i>`, bar: kapMax ? kapUsed / kapMax : null },
            num(LM.global_pop_assimilation_speed_modifier) && { l: "Angleichungsrate", v: p1(LM.global_pop_assimilation_speed_modifier, 0) },
            { l: "Kunstwerke / Künstler", v: `${fmt(L.num_works_of_art ?? L.GetNumWorksOfArt, 0)} <i>/ ${fmt(L.num_artists, 0)}</i>` }],
    warn: [num(L.religious_unity ?? lv.religious_unity) && (L.religious_unity ?? lv.religious_unity) < 1 && `Glaubenseinigkeit ${pct(L.religious_unity ?? lv.religious_unity, 0)}`,
           L.HasTooManyCultures === 1 && "zu viele akzeptierte Kulturen (Kulturkapazität überschritten)"],
  });

  // Karte 1: der Glaube weltweit
  const glaube = `<div class="card"><h3>${esc(relName)}</h3><div class="brk">
    ${zl("Länder", fmt(R.GetNumCountries ?? R.num_countries_in_religion, 0), TR.GetCountriesInfo, "GetCountriesInfo")}
    ${zl("Gläubige", menge(TR.GetTotalPopulation))}
    ${R.HasHolySites === 1 ? zl("Sakralstätten", fmt(R.GetNumHolySites, 0)) : ""}
    ${R.HasCardinals === 1 ? zl("Kardinäle", fmt(R.total_cardinals, 0)) : ""}
    ${R.HasReligiousHead === 1 ? zl("Religionsoberhaupt", "ja") : ""}
    ${zl("Reformwunsch", num(rd) ? `${fmt(rd * 100, 2)} % <span class="hint">${num(rdChg) ? sgn(rdChg * 100, 2) + " % / Monat" : ""}</span>` : "–", rdTxt, "GetReformDesireInfo")}
    ${zl("Wirkung der Religion", "", TR.GetEffect, "GetEffect")}</div>
    ${R.HasCardinals === 1 ? `<p class="hint">Kardinäle bekommt ein Land über das Gebäude „Kardinalssitz“ (Spielbeschreibung „Kardinal“, auch in 1.4).</p>` : ""}</div>`;
  // 1.4: Kardinäle sind Personen (Daten-Mod ab 0.23: Bereich kardinal mit den Werten der Person)
  const kardinaele = Object.values(AW.kardinal || {}).filter(k => k.name);

  // Karte 2: bei uns
  const gS = liveSeries(d, "religious_influence");
  const religionen = d.bev?.religionen || [];
  const relTab = religionen.length ? `<h5>Religionen im Land</h5><div class="mvz"><div>${pieChart(religionen.map((r, i) => ({ label: r.name + (r.staatsreligion ? " ★" : ""), value: r.groesse, color: PALETTE[i % PALETTE.length] })), { size: 90, fmtV: v => pct(v, 1) })}</div>
    <div>${table([{ t: "Religion", f: r => esc(r.name) + (r.staatsreligion ? " ★" : "") }, { t: "Größe (Tsd.)", f: r => fmt(r.groesse, 2) },
      { t: "Anteil (%)", f: r => fmt(r.anteil * 100, 2) }, { t: "Veränd. (Tsd.)", f: r => sgn(r.veraenderung, 3), cls: r => posneg(r.veraenderung) }], religionen, { scroll: false })}</div></div>` : "";
  const beiUns = `<div class="card thw"><h3>Bei uns</h3><div class="brk">
    ${zl("Bevölkerung Staatsreligion / Ketzer / Heiden (Tsd.)", `${fmt(L.total_true_faith_population ?? lv.pop_true_faith, 1)} / ${fmt(L.total_heretic_population ?? lv.pop_heretic, 1)} / ${fmt(L.total_heathen_population ?? lv.pop_heathen, 1)}`)}
    ${num(L.GetTotalStateReligionClergy) ? zl("Klerus der Staatsreligion (Tsd.)", `${fmt(L.GetTotalStateReligionClergy, 2)} <span class="hint">${pct(L.state_religion_clergy, 1)} der Bevölkerung</span>`) : ""}
    ${zl("Toleranz (Wahrer Glaube)", sgn(LM.tolerance_own, 2))}${zl("Toleranz (Ketzer)", sgn(LM.tolerance_heretic, 2))}${zl("Toleranz (Ungläubige)", sgn(LM.tolerance_heathen, 2))}
    ${zl("Pop-Bekehrungstempo", p1(LM.global_pop_conversion_speed_modifier, 0))}
    ${zl("Glaubenseinfluss", `${fmt(glE, 1)}${num(glMax) ? ` <span class="hint">von ${fmt(glMax, 0)}</span>` : ""} ${spark(gS, { color: "--c7", w: 70, h: 18 })}`)}
    ${num(glMon) ? zl("Glaubenseinfluss / Monat", sgn(glMon, 2)) : ""}
    ${num(L.devotion) ? zl("Hingabe", fmt(L.devotion, 0)) : ""}
    ${num(zehnt) ? zl("Zehnt der Stände / Monat", fmt(zehnt, 2), zehntJe.map(([e, v]) => `${estName[e] || e}: ${v.toFixed(2)}`).join("\n")) : ""}
    ${R.HasCardinals === 1 ? zl("Kardinäle", `${fmt(L.num_cardinals, 0)}${num(LM.cardinal_price_cost_modifier) ? ` <span class="hint">Kardinalspreis ${p1(LM.cardinal_price_cost_modifier, 0)}</span>` : ""}`,
        kardinaele.map(k => `${k.name}${num(k.GetAgeInYears) ? ` (${fmt(k.GetAgeInYears, 0)} J.)` : ""}`).join("\n")) : ""}
    ${R.HasHolySites === 1 ? zl("Sakralstätten in unseren Orten", fmt(heilBeiUns, 0)) : ""}</div>${relTab}
    <p class="hint">Hingabe zählt laut Spiel für Theokratien. Zehnt = Posten „Zehnt“ der Stände, er geht an das Papsttum.</p></div>`;

  // Karte 3: Kultur wie im Kulturfenster (Primärkultur, Tradition, Einfluss, akzeptierte Kulturen, Angleichungsrate, Kulturen im Land)
  const kultur = K.name ? `<div class="card thw"><h3>Kultur – ${esc(K.name)}</h3><div class="brk">
    ${zl("Kulturtradition", `${fmt(ab(K.GetTradition), 2)} <span class="hint">${sgn(ab(K.GetTraditionChange), 2)} / Monat</span>`, TK.GetTraditionTooltip, "GetTraditionTooltip")}
    ${zl("Kultureinfluss", `${fmt(ab(K.GetInfluence), 2)} <span class="hint">${sgn(ab(K.GetInfluenceChange), 2)} / Monat</span>`, TK.GetInfluenceTooltip, "GetInfluenceTooltip")}
    ${TK.GetCultureGroupsString ? zl("Kulturgruppen", esc(TK.GetCultureGroupsString), TK.GetCultureGroupsTooltip, "GetCultureGroupsTooltip") : ""}
    ${TK.GetTotalPopulation ? zl("Angehörige weltweit", menge(TK.GetTotalPopulation)) : ""}
    ${num(kapUsed) ? zl("Akzeptierte Kulturen", `${fmt(kapUsed, 2)} / ${fmt(kapMax, 2)}`, TL.GetAcceptedCulturesInfo, "GetAcceptedCulturesInfo") : ""}
    ${modDesc(d, "cultures_capacity") ? zl("Kulturkapazität", fmt(kapMax, 2), modDesc(d, "cultures_capacity"), "GetDescriptionFor('cultures_capacity')") : ""}
    ${zl("Angleichungsrate", p1(LM.global_pop_assimilation_speed_modifier, 2), modDesc(d, "global_pop_assimilation_speed_modifier"), "GetDescriptionFor('global_pop_assimilation_speed_modifier')")}
    ${TL.dialekt_gemein || TL.sprache_gemein ? zl("Gemeinsprache", esc(TL.dialekt_gemein || TL.sprache_gemein), TL.sprache_gemein_macht, "GetCommonLanguage.GetPowerInfo") : ""}
    ${TL.dialekt_hof || TL.sprache_hof ? zl("Hofsprache", esc(TL.dialekt_hof || TL.sprache_hof)) : ""}
    ${TL.GetLiturgicalLanguagePower ? zl("Glaubenssprache", (String(TL.GetLiturgicalLanguagePower).match(/beträgt\s*([\d.]+)%/) || [])[1] ? `Macht ${fmt(+String(TL.GetLiturgicalLanguagePower).match(/beträgt\s*([\d.]+)%/)[1], 2)} %` : "",
        [TL.GetLiturgicalLanguagePower, TL.GetLiturgicalLanguageInfo].filter(Boolean).join("\n"), "GetLiturgicalLanguagePower") : ""}</div>
    ${kulturen.length ? `<h5>Kulturen im Land</h5>${pieChart(kulturen.map((k, i) => ({ label: `${k.name}${k.status.length ? ` (${k.status.map(s => ST[s] || s).join(", ")})` : ""}`, value: k.groesse, color: PALETTE[i % PALETTE.length] })), { size: 90, fmtV: v => pct(v, 1) })}
      ${table([{ t: "Kultur", f: k => esc(k.name) }, { t: "Status", l: true, f: k => esc(k.status.map(s => ST[s] || s).join(", ") || "–") },
        { t: "Größe (Tsd.)", f: k => fmt(k.groesse, 2) }, { t: "Anteil (%)", f: k => fmt(k.anteil * 100, 2) }, { t: "Tradition", f: k => fmt((AW.kultur || {})[k.id]?.GetTradition, 1) },
        { t: "Angleichung / Monat (Tsd.)", f: k => sgn(k.ursachen?.Assimilation, 3), cls: k => posneg(k.ursachen?.Assimilation) },
        { t: "Kosten akzeptiert", f: k => kosten[k.name] != null ? fmt(kosten[k.name], 2) : "–" }], kulturen)}` : ""}
    <p class="hint">Werte wie im Kulturfenster (Daten-Mod ${esc(d.alles?.datum?.kultur || "")}); Kulturen im Land und Angleichung aus dem Spielstand ${esc(d.bev?.datum || "")}.</p></div>` : "";

  // Karte 4: Kunst (Kunstwerke, Künstler, Kunstfertigkeit wie im Kulturfenster)
  const werke = Object.values(AW.kunstwerk || {});
  const kunst = `<div class="card"><h3>Kunst</h3><div class="brk">
    ${zl("Kunstwerke", fmt(L.num_works_of_art ?? L.GetNumWorksOfArt, 0))}
    ${zl("Künstler am Hof", fmt(L.num_artists, 0))}
    ${num(LM.skill_of_new_artists) ? zl("Kunstfertigkeit", p1(LM.skill_of_new_artists, 1), modDesc(d, "skill_of_new_artists"), "GetDescriptionFor('skill_of_new_artists')") : ""}
    ${num(LM.artist_salary_modifier) ? zl("Künstlergehalt", p1(LM.artist_salary_modifier, 2), modDesc(d, "artist_salary_modifier"), "GetDescriptionFor('artist_salary_modifier')") : ""}
    ${num(LM.hire_artist_cost_modifier) ? zl("Künstler-Anwerbekosten", p1(LM.hire_artist_cost_modifier, 1)) : ""}
    ${num(LM.global_monthly_art_start_chance) ? zl("Monatliche Werkauftakt-Chance", p1(LM.global_monthly_art_start_chance, 1)) : ""}
    ${num(L.country_art_quality) ? zl("Kunstgüte", fmt(L.country_art_quality, 2)) : ""}</div>
    ${werke.length ? `<h5>Kunstwerke</h5>${werke.map(w => `<div>${esc(w.name || "–")}</div>`).join("")}` : `<p class="hint">Es gibt keine Kunstwerke in unserem Land.</p>`}</div>`;

  return { head, body: `<div class="grid2">${glaube}${beiUns}${kultur}${kunst}</div>` };
}

// Modifikatoren (Nutzerwunsch 01.10., Punkt 3a): alle wirksamen Landes-Modifikatoren (≠ 0, Daten-Mod landmod) nach Thema,
// Format wie im Spiel (Prozent laut Modifikator-Typ), Name aus der Lokalisierung, Codename im Tooltip.
const MOD_GRUPPEN = [
  ["erlaubt", "Erlaubnisse und Sperren", /^(allow_|can_|cannot_|block_|has_|may_|enable_|is_)|_allowed|_can_participate|_cannot_|silver_|goods_gold_|care_about|heir_of_same/],
  ["ki", "KI-Gewichte", /^ai_|^bias_for|importance_modifier$|aggressiveness|carefulness|^win_war_chance|preference_modifier$/],
  ["gesellschaft", "Gesellschaftswerte", /^monthly_towards_/],
  ["staende", "Stände", /estate|crown_power|enfranch|privilege/],
  ["forschung", "Forschung und Bildung", /institution|advance|research|innovat|literacy/],
  ["religion", "Religion, Kultur und Kunst", /religi|devotion|doom|karma|righteous|cardinal|holy_site|heathen|heretic|faith|liturgical|tolerance_(own|heretic|heathen)|papal|missionar|tithe|canoniz|monaster|calvin|luther|cultur|assimil|conversion|artist|art_|language/],
  ["regierung", "Regierung und Hof", /legitim|government|reform|law|legislat|parliament|cabinet|bureaucra|policy|ruler|complacency|political_influence|republican|horde|tribal|stability|prestige|dynast|heir|character|advisor|bailiff|governor|spouse|child_education|life_expectancy|court_/],
  ["diplomatie", "Diplomatie", /^dip_|diplomat|subject|rival|alliance|ally|union|casus|annex|antagon|relation|liberty|loyal|overlord|peace_offer|shared_border|subjugat|spy|opinion|sovereignty|influence_over/],
  ["handel", "Handel", /trade|merchant|market|caravan|selling|tariff/],
  ["militaer", "Militär", /army|navy|naval|manpower|sailor|regiment|levy|fort|military|morale|war|mercenar|ship|siege|fleet|attrition|garrison|rebel|explor|colon|privateer|general|admiral|supply|defensive|slave_raid|maritime_presence/],
  ["produktion", "Produktion und Bau", /building|rgo|raw_material|production|construction|output/],
  ["gueter", "Güter und Nahrung", /goods|food/],
  ["finanzen", "Finanzen", /gold|income|maintenance|debt|loan|bond|credit|inflation|mint|tax|interest|upkeep/],
  ["land", "Land und Leute", /control|development|location|province|capital|power_projection|proximity|integration|prosperity|devastation|disease|pop_|migration|population|desired_pop|land_cost|port_cost|sea_cost|wetlands|town_|promotion|slave/],
  // 1.4.5 (DLC „Across the Pillars“): Kosten der Situations-Aktionen und Preise ohne anderes Thema (vorher „Übrige“)
  ["kosten", "Aktionskosten und Preise", /actions_cost|price_cost_modifier|_cost_modifier$/],
];
function modifikatoren(d, P) {
  const LM = Object.values(d.alles?.werte?.landmod || {})[0], MN = d.alles?.modnamen || {}, mn = (P.W.namen || {}).modifikatoren || {};
  if (!LM) return "";
  const rows = Object.entries(LM).filter(([, v]) => typeof v === "number" && v !== 0);
  // „Erlaubnisse“ nur für Ja/Nein-Modifikatoren: Zahlen wie num_thagr_fort_allowed (erlaubte Gebäudestufen) nach Thema (29.10.)
  const gruppe = k => (MOD_GRUPPEN.find(([g, , rx]) => rx.test(k) && (g !== "erlaubt" || MN[k]?.boolean !== false)) || ["sonst", "Übrige"]);
  const name = k => MN[k]?.name || mn[k] || de(k);
  const wert = (k, v) => MN[k]?.percent ? `${sgn(v * 100, Math.abs(v) < 0.1 ? 2 : 1)} %` : MN[k]?.already_percent ? `${sgn(v, 2)} %`
    : sgn(v, Math.abs(v) < 1 ? 3 : Math.abs(v) < 100 ? 2 : 0);
  const G = {};
  for (const [k, v] of rows) (G[gruppe(k)[0]] ??= []).push([k, v]);
  const reihe = [...MOD_GRUPPEN.map(g => g[0]).filter(g => g !== "erlaubt"), "sonst", "erlaubt"];
  const titel = Object.fromEntries([...MOD_GRUPPEN.map(([g, t]) => [g, t]), ["sonst", "Übrige"]]);
  const karte = g => { const list = (G[g] || []).sort((a, b) => name(a[0]).localeCompare(name(b[0])));
    if (!list.length) return "";
    if (g === "erlaubt") return `<div class="card" style="grid-column:1/-1"><h3>${esc(titel[g])} – ${list.length}</h3>
      <div class="hint" style="font-size:12.5px;line-height:1.6">${list.map(([k, v]) => `<span title="${esc(k)} = ${v}">${esc(name(k))}${v !== 1 ? ` (${fmt(v, 0)})` : ""}</span>`).join(" · ")}</div></div>`;
    return `<div class="card"><h3>${esc(titel[g])} – ${list.length}</h3><div class="brk">${list.map(([k, v]) =>
      `<div class="bk" title="${esc(k)}"><span class="bl">${esc(name(k))}</span><span class="bv ${v < 0 ? "neg" : "pos"}">${wert(k, v)}</span></div>`).join("")}</div></div>`; };
  const head = hd({
    big: [{ l: "wirksame Modifikatoren", v: fmt(rows.length, 0), title: "Landes-Modifikatoren ungleich 0 (Daten-Mod landmod)" }],
    small: reihe.filter(g => G[g]?.length).slice(0, 8).map(g => ({ l: titel[g], v: fmt(G[g].length, 0) })),
  });
  return { head, body: `<div class="grid3">${reihe.map(karte).join("")}</div>
    <p class="hint">Alle Landes-Modifikatoren ≠ 0 (Daten-Mod ${esc(d.alles?.datum?.landmod || "")}), Format wie im Spiel (Prozent laut Modifikator-Typ);
      Thema nach Stichworten im Codenamen (Tooltip). Woher ein Modifikator kommt, zeigt die Aufschlüsselung in der jeweiligen Kachel.</p>` };
}

// Land und Leute (Nutzerwunsch 30.09.): frühere Kacheln Land und Bevölkerung zusammen. Aus der Landkachel bleiben nur die Werte,
// die sonst nirgends stehen: Entwicklung, Kontrolle (mit Auswirkungen laut Spiel), Rang, Hauptstadt, Orte/Provinzen, Großmacht.
// Forschung und Institutionen haben eine eigene Kachel; Regierungs-, Militär- und Diplomatie-Werte stehen in deren Kacheln.
function landUndLeute(d, P) {
  const lv = P.lv, A = d.alles || {};
  const L = Object.values(A.werte?.land || {})[0] || {}, T = Object.values(A.texte?.land || {})[0] || {};
  const bev = bevoelkerung(d, P);
  if (!bev && lv.population_total === undefined) return "";
  const K = bev?.kopf || {};
  const L2 = (d.live || []).at(-2) || {};
  // Hauptstadt: Ort mit IsCapital (Daten-Mod, Orte); Rang: GetFlavorRank („Grafentum“)
  const capId = Object.entries(A.werte?.ort || {}).find(([, o]) => o.IsCapital === 1)?.[0];
  const cap = P.orte.find(o => String(o.id) === capId);
  const rang = String(T.GetFlavorRank || "").trim();
  // Großmacht wie im Tooltip am Rang (Screenshot 30.09.: „Mittelmacht“, Platz #1317, 0 Punkte, „Holland 8 von 13 nötigen“ ✗)
  const gp = L.IsGreatPower === 1 ? "Großmacht" : "Mittelmacht";
  const gpRang = L.GetGreatPowerRank ?? lv.great_power_rank, gpPunkte = L.GetGreatPowerScore ?? lv.great_power_score;
  const ortRang = [["rank_megalopolis", "Metropolen"], ["rank_city", "Großstädte"], ["rank_town", "Städte"], ["rank_rural_settlement", "ländliche Siedlungen"]]
    .filter(([k]) => L[k] > 0).map(([k, n]) => `${fmt(L[k], 0)} ${n}`).join(" · ");
  // Kopf (Nutzerwunsch 30.09.): Reihe 1 groß Bevölkerung · Bevölkerungskapazität genutzt; Reihe 2 groß Orte/Provinzen · Ø Kontrolle ·
  // Entwicklung; Reihe 3 klein Großmacht · Rang · Hauptstadt; Reihe 4 klein wie in der Bevölkerungskachel. Aufgeklappt eine Reihe.
  const head = hd({
    big: [K.bev || { l: "Bevölkerung (Tsd.)", v: fmt(lv.population_total, 1) },
          K.kap && { ...K.kap, l: "Bevölkerungskapazität genutzt" },
          { umbruch: true },
          { l: "Orte / Provinzen", v: `${fmt(lv.locations, 0)} / ${fmt(lv.provinces, 0)}` },
          { l: "Ø Kontrolle", v: pct(lv.control_avg, 0), t: trend(num(L2.control_avg) ? (lv.control_avg - L2.control_avg) * 100 : null, 1, 1),
            s: spark(liveSeries(d, "control_avg"), { color: "--c3" }) },
          { l: "Entwicklung", v: fmt(lv.development_total, 0), t: trend(num(L2.development_total) ? lv.development_total - L2.development_total : null, 2, 1),
            s: spark(liveSeries(d, "development_total"), { color: "--c3" }) }],
    small: [num(gpRang) && { l: "Großmacht", v: `${gp} <i>Platz ${fmt(gpRang, 0)} · ${fmt(gpPunkte, 0)} Punkte</i>`,
              title: "wie im Tooltip am Rang: Platz unter den Großmächten der Welt und Großmachtpunkte" },
            rang && { l: "Rang", v: esc(rang), cls: "wort" }, cap && { l: "Hauptstadt", v: esc(cap.name), cls: "wort" },
            { umbruch: true },
            ...(K.small || [])],
    warn: K.warn || [],
  });
  const land = `<div class="grid3">
      <div class="card"><h3>Land</h3>${kv([rang && ["Rang", esc(rang)], cap && ["Hauptstadt", esc(cap.name)],
        ["Orte / Provinzen", `${fmt(lv.locations, 0)} / ${fmt(lv.provinces, 0)}`], ortRang && ["Orte nach Rang", ortRang],
        ["Entwicklung", fmt(lv.development_total, 1)], num(L.capital_wealth) && ["Vermögen der Hauptstadt", fmt(L.capital_wealth, 2)]])}
        ${T.GetCapitalBonusInfo ? `<div class="sect">Hauptstadt-Bonus</div>${breakdown(T.GetCapitalBonusInfo)}` : ""}</div>
      <div class="card"><h3>Kontrolle</h3>${kv([["Ø Kontrolle", pct(lv.control_avg, 1)], ["Ø Kontrolle Kernregion", pct(lv.control_avg_home, 1)],
        ["kontrollgewichtete Bevölkerung (Tsd.)", fmt(lv.control_pop, 1)]])}
        ${T.GetAverageControlInfo ? `<div class="sect">Auswirkungen der Ø Kontrolle laut Spiel</div>${breakdown(T.GetAverageControlInfo)}` : ""}</div>
      <div class="card"><h3>Großmacht</h3>${kv([["Stellung", gp], ["Platz", fmt(gpRang, 0)], ["Großmachtpunkte", fmt(gpPunkte, 2)]])}
        ${T.GetGreatPowerScoreInfo ? `<div class="sect">Die Großmachtpunkte beruhen auf (laut Spiel)</div>${breakdown(T.GetGreatPowerScoreInfo)}` : ""}
        <p class="hint">Wie im Tooltip am Rang des Landes; „8 von 13 nötigen“ ist im Spiel mit ✗ markiert und zählt dann nicht.</p></div>
    </div>`;
  return { head, body: land, nach: bev?.body || "" };
}

// Forschung (eigene Kachel, Nutzerwunsch 30.09., Punkte 1–4): Kopf mit Forschung je Monat (nachgerechnet), Institutionen als
// Tabelle (Spielstand institution_manager + Spieltext), Fortschritte nach Zeitalter (Spieldateien), Zeitalter-Vorlieben ganz
// ---------------------------------------------------------------- Krankheiten (Nutzerwunsch 04.10., Screenshots Weltpolitik →
// Krankheiten, Ort-Tooltip im Kartenmodus, Situation Schwarzer Tod). Quellen:
// - Spielstand (aktuell.krankheiten, ab Format 10): Ausbrüche der Welt (disease_outbreak_manager: Ursprung, Start, Tote je Land in
//   Tausend – Anzeige ×1000 abgeschnitten wie im Spiel: 1.68724 → 1.687), Widerstand/Ausbreitung je eigenem Ort (Festkomma ÷ 2^30),
//   Situation Schwarzer Tod. Fremde Ausbrüche gibt es nur hier (kein Iterator im Spiel-Skript).
// - Daten-Mod ab 0.18 (monatlich): seucheland (Tote je Krankheit, ausgebrochen ja/nein, Schwarzer Tod), seucheort (Widerstand,
//   Ausbreitung, Anzeige des Spiels GetDiseaseResistance, Malaria-Grundrate), Texte des Ausbruchs; Seuchenwiderstand landmod.
// - Spieldateien (krankheiten_wissen): Grundwerte je Krankheit, Aktionen des Schwarzen Tods, Pesthaus/Krankenhaus.
// Widerstand im Ort wie im Tooltip: gespeicherter Wert + Seuchenwiderstand des Landes, auf ganze Prozent abgeschnitten
// (Den Haag 1.1.1347: 7,66 % + 3 % → 10 %, 6,60 → 9, 41,81 → 44 – Screenshot des Nutzers); mit Mod 0.18 der Wert des Spiels.
const KRANK_GRUPPE = { food_and_trade_actions: "Nahrungs- & Handelsaktionen", bd_disease_control_actions: "Krankheitsbekämpfung",
                       bd_social_actions: "Soziale Aktionen" };
const KRANK_FELDER = [["monthly_spawn_chance", "Ausbruchschance je Monat", "%"], ["r0", "Ansteckung (R0)", 2],
  ["mortality_rate", "Sterblichkeit", "%"], ["monthly_resistance_reduction", "Widerstandsverlust je Monat", "%"],
  ["location_spread_threshold", "Übergreifen ab", "%"], ["calc_interval_days", "Intervall (Tage)", 0]];
const toteAnz = x => num(x) ? fmt(Math.trunc(x * 1000 + 1e-6), 0) : "–";      // Tausend → Menschen, abgeschnitten wie im Spiel
const pzAb = (x, d = 0) => num(x) ? `${nf(d).format(Math.trunc(x * 100 * 10 ** d + 1e-6) / 10 ** d)} %` : "–";
function krankheiten(d, P) {
  const K = P.A.krankheiten, KW = d.krankheiten_wissen || {};
  const W = d.alles?.werte || {}, TX = d.alles?.texte || {};
  const SL = Object.values(W.seucheland || {})[0] || {}, SO = W.seucheort || {}, ORTW = W.ort || {};
  const STX = TX.situation?.black_death || {}, SIT = W.situation?.black_death || {};
  if (!K && !Object.keys(SL).length) return "";
  const KR = (K || {}).krankheiten || {};
  const name = k => KR[k]?.name || KW.krankheiten?.[k]?.name || k;
  const reihe = Object.keys(KR).length ? Object.keys(KR) : Object.keys(KW.krankheiten || {});
  const nachName = [...reihe].sort((a, b) => name(a).localeCompare(name(b), "de"));     // wie die Liste im Spiel
  const gdr = modWert(d, "global_disease_resistance");
  // Mod-Texte zum Schwarzen Tod (ab 0.18): GetDeaths in Tausend mit deutschem Komma („49,588“ = 49.588 Tote, Test 0.18),
  // Tooltip „… hat sich bislang auf 175 Orte ausgebreitet“
  const deZahl = s => /^[\d.]+(,\d+)?$/.test(String(s ?? "").trim()) ? +String(s).trim().replace(/\./g, "").replace(",", ".") : null;
  const bdToteLive = deZahl(STX.tote), bdOrteWelt = deZahl((String(STX.tooltip || "").match(/auf\s+([\d.]+)\s+Orte/) || [])[1]);
  const live = Object.keys(SO).length > 0;
  // Ausbreitung je eigenem Ort: Mod 0.18 (pres_<k>), sonst GetDiseaseInfectionPercentage (disease_<k>, seit 0.12), sonst Spielstand
  const ausbr = (o, k) => {
    const v = SO[o.id]?.["pres_" + k] ?? ORTW[o.id]?.["disease_" + k];
    return num(v) ? v : (K?.orte?.[o.id]?.[k]?.ausbreitung ?? 0);
  };
  const befallen = P.orte.filter(o => reihe.some(k => ausbr(o, k) > 0));
  const toteLive = reihe.map(k => SL["tote_" + k]).filter(num);
  const tote = toteLive.length ? sum(toteLive) : K?.tote_uns;
  const ab = (K?.ausbrueche || []).slice().sort((a, b) => name(a.krankheit).localeCompare(name(b.krankheit), "de"));
  const bd = K?.schwarzer_tod, bdAb = ab.find(a => a.id === bd?.ausbruch);
  const markt = P.A.markt?.zentrum || "Heimatmarkt";
  const pop = liveSeries(d, "population_total");
  const head = hd({
    big: [{ l: "Seuchenwiderstand", v: num(gdr) ? sgn(gdr * 100, 0) + " %" : "–", title: "Landes-Modifikator global_disease_resistance (Daten-Mod) – „Seuchenwiderstand +3%“ im Spiel unter Gesellschaft → Aufruhr → Krankheiten (bis 1.3 Weltpolitik → Krankheiten)" },
          { l: "Tote durch Krankheiten", v: toteAnz(tote), cls: (tote ?? 0) > 0 ? "neg" : "",
            title: toteLive.length ? "Daten-Mod: disease_country_deaths je Krankheit, Summe (in Tausend gespeichert, ×1000 abgeschnitten)" : `Spielstand ${esc(d.meta.datum)}: Tote unseres Landes je Ausbruch, Summe` },
          { l: "befallene eigene Orte", v: `${befallen.length} <i>/ ${P.orte.length}</i>`, cls: befallen.length ? "neg" : "" },
          { l: "laufende Ausbrüche (Welt)", v: String(ab.length), title: `Spielstand ${esc(d.meta.datum)}; ohne endemische Malaria (zählt im Spiel nicht)` },
          { l: "Bevölkerung (Tsd.)", v: fmt(pop.at(-1), 1), s: spark(pop, { color: "--c4" }), t: trend(vorm(pop), 1, 0) }],
    small: [bd && { l: "Schwarzer Tod", cls: "wort", mw: 520,
                    v: bd.status === "active" ? `aktiv seit ${esc(bd.start || "")}${bdAb ? ` · Ursprung ${esc(bdAb.ursprung || "?")} · ${toteAnz(bdToteLive ?? bdAb.tote)} Tote` : ""}` : "nicht aktiv" },
            { l: "in unserem Land", v: befallen.length ? reihe.filter(k => befallen.some(o => ausbr(o, k) > 0)).map(name).join(", ") : "keine Krankheit ausgebrochen", cls: "wort" }],
    warn: [...reihe.filter(k => befallen.some(o => ausbr(o, k) > 0)).map(k => `${esc(name(k))} in ${befallen.filter(o => ausbr(o, k) > 0).length} eigenen Orten`),
           ...ab.filter(a => a.orte_markt_anzahl).map(a => `${esc(name(a.krankheit))} im Markt ${esc(markt)} (${a.orte_markt_anzahl} Orte)`)],
  });
  // Karte 1: Derzeitige Ausbrüche wie Weltpolitik → Krankheiten
  const ohne = nachName.filter(k => !ab.some(a => a.krankheit === k));
  const ausbrKarte = K ? `<div class="card" style="grid-column:1/-1"><h3>Derzeitige Ausbrüche – ${ab.length}</h3>${ab.length ? table([
      { t: "Krankheit", l: true, f: a => esc(name(a.krankheit)) },
      { t: "Ausbruch", l: true, f: a => `in ${esc(a.ursprung || "?")}${a.ursprung_land_name ? `<div class="hint">${esc(a.ursprung_land_name)}</div>` : ""}` },
      { t: "Start", f: a => esc(a.start || "–") },
      { t: "Länder", f: a => fmt(a.laender, 0), title: "Länder mit Toten (Flagge im Spiel)" },
      { t: "Tote", f: a => toteAnz(a.tote) },
      { t: "befallene Orte", f: a => fmt(a.orte, 0) },
      { t: "bei uns", l: true, f: a => a.orte_uns.length ? `<span class="neg">${a.orte_uns.map(o => `${esc(o.name)} ${pzAb(o.ausbreitung)}`).join(", ")}</span>` : "nicht in unserem Land" },
      { t: `im Markt ${esc(markt)}`, l: true, f: a => a.orte_markt_anzahl ? `<span class="neg">${a.orte_markt_anzahl} Orte</span><div class="hint">${a.orte_markt.slice(0, 4).map(o => esc(o.name)).join(", ")}</div>` : "–" },
      { t: "Tote je Land", l: true, f: a => a.laender_tote.slice(0, 3).map(x => `${esc(x.name || x.tag)} ${toteAnz(x.tote)}`).join(" · ") || "–" }], ab) : `<p class="hint">Keine laufenden Ausbrüche.</p>`}
    ${ohne.length ? `<p class="hint">Ohne Ausbruch: ${ohne.map(k => esc(name(k)) + (KR[k]?.endemisch ? ` (endemisch in ${fmt(KR[k].endemisch, 0)} Orten – zählt im Spiel nicht als Ausbruch)` : "")).join(", ")}.</p>` : ""}
    <p class="hint">Im Spiel ab 1.4 unter Gesellschaft → Aufruhr → Krankheiten (zusammen mit Rebellen und Bewegungen), bis 1.3 Weltpolitik → Krankheiten.
      Spielstand ${esc(d.meta.datum)} (disease_outbreak_manager). Tote = gespeicherter Wert in Tausend × 1000, abgeschnitten wie im Spiel
      (Kalmyk 1,68724 → 1.687). Länder = Länder mit Toten (Flagge im Spiel). Fremde Ausbrüche kennt nur der Spielstand – der Mod hat keinen Zugriff darauf.</p></div>` : "";
  // Karte 2: Unsere Orte – Ausbreitung, Widerstand je Krankheit wie im Ort-Tooltip, Malaria-Grundrate
  // Widerstand wie im Ort-Tooltip = Wert des Orts + Seuchenwiderstand des Landes, auf ganze Prozent abgeschnitten (geprüft
  // 1.1.1347 an den 4 Werten des Tooltips von Den Haag). Wert des Orts live aus dem Mod (ab 0.18: disease_resistance je Krankheit),
  // sonst aus dem Spielstand. Die Anzeige-Funktion des Spiels (GetDiseaseResistance) ist im Mod nicht nutzbar (Test 0.18).
  const resOrt = (o, k) => { const v = SO[o.id]?.["res_" + k]; return num(v) ? v : K?.orte?.[o.id]?.[k]?.widerstand; };
  const widK = [...reihe].sort().filter(k => P.orte.some(o => (resOrt(o, k) ?? 0) > 0));   // Reihenfolge wie im Ort-Tooltip
  const widerstand = (o, k) => { const r = resOrt(o, k); return num(r) ? { v: Math.min(1, r + (gdr ?? 0)), roh: r } : null; };
  const orteKarte = `<div class="card" style="grid-column:1/-1"><h3>Unsere Orte</h3>${table([
      { t: "Ort", l: true, f: o => `<a href="#ort_${o.id}" data-oeffne="ort_${o.id}">${esc(o.name)}</a>` },
      { t: "Ausbreitung", l: true, f: o => { const x = reihe.filter(k => ausbr(o, k) > 0); return x.length ? `<span class="neg">${x.map(k => `${esc(name(k))} ${pzAb(ausbr(o, k), 2)}`).join(", ")}</span>` : "keine"; } },
      ...widK.map(k => ({ t: `Widerstand ${esc(name(k))}`, f: o => { const w = widerstand(o, k); return w ? `${pzAb(w.v)}<div class="hint">Ort ${pzAb(w.roh, 2)}</div>` : "–"; } })),
      { t: "Malaria-Grundrate", f: o => num(SO[o.id]?.mal) ? pzAb(SO[o.id].mal, 2) : "–", title: "„Ansteckungsgebiet – Grund-Infektionsrate pro Intervall“ (Formel environmental_infection aus malaria.txt, Daten-Mod ab 0.18)" }],
    P.orte, { scroll: true })}
    <p class="hint">${live ? `Daten-Mod ${esc(d.alles?.datum?.seucheort || "")}` : `Spielstand ${esc(d.meta.datum)}`}. Widerstand wie im Ort-Tooltip:
      Wert des Orts („Ort“) + Seuchenwiderstand des Landes ${num(gdr) ? sgn(gdr * 100, 0) + " % " : ""}(Alchemie), auf ganze Prozent abgeschnitten
      (Den Haag 1.1.1347: 7,66 % + 3 % → 10 % wie im Spiel).
      Typhus und Malaria fehlen, solange es dafür keinen Widerstand gibt (Spiel zeigt dann kein Symbol). Große Seuche 100 %: die Alte Welt ist
      immun, sie wirkt nur in Amerika.</p></div>`;
  // Karte 3: Schwarzer Tod – Situation, Endbedingung, Aktionen und Gebäude laut Spieldateien
  const preis = p => Object.entries(p || {}).map(([k, v]) => k === "stability" ? `${fmt(v, 0)} Stabilität` : k === "scaled_gold" ? "Gold (mit dem Einkommen skaliert)" : `${esc(k)} ${fmt(v, 2)}`).join(", ") || "–";
  const modTxt = x => num(x.wert) ? `${esc(x.name)} ${x.prozent ? sgn(x.wert * 100, 1) + " %" : sgn(x.wert, 2)}${x.skal ? ` <i title="Größe laut Spieldatei (size)">× ${esc(x.skal)}</i>` : ""}`
    : x.roh === "yes" ? esc(x.name) : `${esc(x.name)} <i>${esc(String(x.roh ?? ""))}</i>`;
  const landW = Object.values(W.land || {})[0] || {};
  const bdOrte = P.orte.filter(o => (SO[o.id]?.bd ?? 0) > 0).length;
  const bdKarte = bd ? `<div class="card"><h3>Schwarzer Tod</h3>${kv([
      ["Status", bd.status === "active" ? `aktiv seit ${esc(bd.start || "")}${num(SIT.tage) ? ` <span class="hint">(${fmt(SIT.tage, 0)} Tage)</span>` : ""}` : esc(bd.status || "–")],
      STX.ausbruch && ["Ausbruch", esc(STX.ausbruch)],
      bdAb && ["Ursprung", `${esc(bdAb.ursprung || "?")}${bdAb.ursprung_land_name ? ` <span class="hint">${esc(bdAb.ursprung_land_name)}</span>` : ""}`],
      (bdAb || num(bdToteLive)) && ["Tote insgesamt", num(bdToteLive) ? `${toteAnz(bdToteLive)} <span class="hint">live</span>`
        : `${toteAnz(bdAb.tote)} <span class="hint">Spielstand</span>`],
      bdAb && ["Länder mit Toten", `${fmt(bdAb.laender, 0)} <span class="hint">Spielstand ${esc(d.meta.datum)}</span>`],
      (bdAb || num(bdOrteWelt)) && ["befallene Orte (Welt)", num(bdOrteWelt) ? `${fmt(bdOrteWelt, 0)} <span class="hint">live</span>`
        : `${fmt(bdAb.orte, 0)} <span class="hint">Spielstand</span>`],
      ["Tote im Land", num(SL.bd_tote) ? toteAnz(SL.bd_tote) : toteAnz(bdAb?.tote_uns)],
      ["betroffene Orte bei uns", live ? fmt(bdOrte, 0) : fmt(bdAb?.orte_uns?.length ?? 0, 0)],
      ["Pesthäuser", num(landW.bltot_pest_house) ? fmt(landW.bltot_pest_house, 0) : "–"]].filter(Boolean))}
    <p class="hint">Endet, wenn der ursprüngliche Ausbruch an keinem Ort mehr aktiv ist (situations/black_death.txt: can_end = NOT
      disease_outbreak_is_active; Spieltext „Diese Krankheit ist an keinem Ort ausgebrochen“ – der Haken im Fenster ist fest, kein Status).</p></div>` : "";
  const akt = KW.aktionen || [];
  const aktKarte = akt.length ? `<div class="card" style="grid-column:1/-1"><h3>Aktionen und Gebäude gegen die Pest</h3>${table([
      { t: "Gruppe", l: true, f: a => esc(KRANK_GRUPPE[a.gruppe] || "Hof und Städte") },
      { t: "Aktion", l: true, f: a => `<span title="${esc(a.beschreibung || "")}">${esc(a.name)}</span>` },
      { t: "Preis", l: true, f: a => preis(a.preis) },
      { t: "Wirkung", l: true, f: a => { const w = a.wirkung.flatMap(x => x.werte.map(modTxt));
          return w.length > 4 ? `<span title="${esc(w.join(", ").replace(/<[^>]+>/g, ""))}">${w.slice(0, 4).join("<br>")}<br><i>+${w.length - 4} weitere</i></span>` : w.join("<br>") || "–"; } }],
      akt, { scroll: false })}
    ${(KW.gebaeude || []).length ? `<h5>Gebäude</h5><div class="kv">${KW.gebaeude.map(g => `<span title="${esc(g.beschreibung || "")}">${esc(g.name)}</span>
      <span>${g.wirkung.map(modTxt).join(", ") || "–"}${g.bedingung ? `<div class="hint">${esc(g.bedingung)}</div>` : ""}</span>`).join("")}</div>` : ""}
    <p class="hint">Laut Spieldateien (generic_actions, prices, static_modifiers, building_types). Je Gruppe läuft eine Aktion; welche gerade erlaubt
      ist, entscheidet das Spiel (z. B. „Die Erkrankten absondern“ nur mit Pest im Land, „Städte abschotten“ nur bei zufriedenen Bürgern).</p></div>` : "";
  // Karte 4: Krankheiten im Spiel – Grundwerte laut Spieldateien
  const kw = KW.krankheiten || {};
  const kurz = (x, f) => {
    if (!x) return "–";
    const one = v => f === "%" ? pct(v, v < 0.01 ? 2 : v < 0.1 ? 1 : 0) : fmt(v, f);
    if (num(x.grund) && (!num(x.min) || x.min === x.max)) return one(x.grund);
    if (num(x.min) && num(x.max)) return `${one(x.min)}–${one(x.max)}${x.zufall ? "" : `<i title="Spanne über die Bedingungen der Spieldatei">*</i>`}`;
    return "–";
  };
  const spielKarte = Object.keys(kw).length ? `<div class="card" style="grid-column:1/-1"><h3>Krankheiten im Spiel</h3>${table([
      { t: "Krankheit", l: true, f: k => `<span title="${esc(kw[k].beschreibung || "")}">${esc(kw[k].name || k)}</span>` },
      ...KRANK_FELDER.map(([f, t, fm]) => ({ t, f: k => kurz(kw[k].werte?.[f], fm) })),
      { t: "Wirkung im befallenen Ort", l: true, f: k => (kw[k].ort_wirkung || []).map(modTxt).join(", ") || "–" }],
    Object.keys(kw).sort((a, b) => (kw[a].name || a).localeCompare(kw[b].name || b, "de")), { scroll: true })}
    <p class="hint">Laut in_game/common/diseases (Felder siehe readme.txt). Spannen ohne * = Zufall je Ausbruch; * = abhängig von Bedingungen
      (Spielregel, Klima, Markt, Gelände …). Übergreifen ab = Ausbreitung im Ort, ab der die Krankheit auf Nachbarorte, das Marktzentrum, dessen
      Handelspartner und die Hauptstadt springt.</p></div>` : "";
  // Karte 5: Einheiten (Spieltext GetDiseaseTooltip, Daten-Mod)
  const ET = Object.entries(TX.einheit || {}).filter(([, t]) => String(t.GetDiseaseTooltip || "").trim());
  const einhKarte = ET.length ? `<div class="card"><h3>Einheiten</h3>${ET.map(([, t]) => breakdown(t.GetDiseaseTooltip)).join("")}
    <p class="hint">Spieltext je Armee/Flotte (Daten-Mod ${esc(d.alles?.datum?.einheit || "")}); Einheiten haben eigenen Widerstand, ohne Landeszuschlag.</p></div>` : "";
  return { head, body: `<div class="stgrid">${ausbrKarte}${orteKarte}${bdKarte}${einhKarte}${aktKarte}${spielKarte}</div>` };
}

function forschung(d, P) {
  const lv = P.lv, fo = P.A.forschung, A = d.alles || {}, FI = d.forschung_info || {};
  const L = Object.values(A.werte?.land || {})[0] || {}, LM = Object.values(A.werte?.landmod || {})[0] || {};
  const T = Object.values(A.texte?.land || {})[0] || {};
  if (!fo && !num(lv.research_progress)) return "";
  const rSer = liveSeries(d, "research_progress");
  // Forschung je Monat = research_speed × (1 + research_speed_modifier); geprüft 30.09.: 1,053 × 1,322 = 1,392 = Zuwachs von
  // research_progress im letzten Monat (+1,39)
  const rs = LM.research_speed, rsm = LM.research_speed_modifier ?? 0;
  const jeMonat = num(rs) ? rs * (1 + rsm) : null;
  // Stand je Institution laut Spieltext GetInstitutionInfo („Feudalismus: Eingeführt“, „Meritokratie: 0.00%“, „Renaissance: Unbekannt“)
  const stand = Object.fromEntries(String(T.GetInstitutionInfo || "").split("\n").filter(l => l.includes(":"))
    .map(l => { const i = l.lastIndexOf(":"); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; }));
  const inst = FI.institutionen || [];
  const nInst = inst.length || Object.keys(stand).length || L.GetInstitutionActiveCount;
  const nEin = L.num_embraced_institutions ?? lv.institutions_embraced;
  // Zeitalter: Spielstand (current_age, über techbaum_vorschlag, 30.10.) – der Spieltext GetAgePreferenceInfo ist im 1. Zeitalter leer
  const zeitalter = d.techbaum_vorschlag?.zeitalter || String(T.GetAgePreferenceInfo || "").split("\n")[0].split(":")[0].trim();
  const beiUns = x => { const s = stand[x.name];
    if (x.eingefuehrt || /^Eingeführt/i.test(s || "")) return `<span class="pos">eingeführt</span>`;
    if (/%/.test(s || "")) return `${fmt(parseFloat(s), 1)} % verbreitet`;
    return s ? esc(s.toLowerCase()) : "–"; };
  // Mod 0.16: „Benötigt 7.32 von 17.00 Forschungsfortschritt“ (CurrentResearch.GetProgressInfo)
  const fz = String(T.forsch_fortschritt_info || "").match(/Benötigt\s*([\d.]+)\s*von\s*([\d.]+)/);
  const forschKarte = T.forsch_fortschritt_name || modDesc(d, "research_speed_modifier") ? `<div class="card"><h3>Laufende Forschung und Tempo</h3><div class="brk">
    ${T.forsch_fortschritt_name ? zeileAuf("laufende Forschung", esc(T.forsch_fortschritt_name)) : ""}
    ${fz ? zeileAuf("Fortschritt", `${fmt(+fz[1], 2)} von ${fmt(+fz[2], 2)} <span class="hint">${pct(L.forsch_fortschritt, 0)}</span>`, T.forsch_kosten ? `Kosten ${fz[2]}:\n${String(T.forsch_kosten).split("\n").map(z => "  " + z).join("\n")}` : "", "GetResearchCost") : ""}
    ${T.forsch_dauer ? zeileAuf("voraussichtlich fertig", esc(T.forsch_dauer)) : ""}
    ${num(jeMonat) ? zeileAuf("Forschung je Monat", fmt(jeMonat, 2)) : ""}
    ${zeileAuf("Grundwert", fmt(rs, 3), modDesc(d, "research_speed"), "GetDescriptionFor('research_speed')")}
    ${zeileAuf("Forschungstempo (Modifikator)", `${sgn(rsm * 100, 1)} %`, modDesc(d, "research_speed_modifier"), "GetDescriptionFor('research_speed_modifier')")}</div>
    <p class="hint">Forschung je Monat = Grundwert × (1 + Forschungstempo); laufende Forschung, Kosten und Fertigdatum wie im Forschungsfenster (Daten-Mod ab 0.16).</p></div>` : "";
  const head = hd({
    big: [fo && { l: "Fortschritte erforscht", v: String(fo.erforscht), title: "Spielstand" },
          T.forsch_fortschritt_name ? { l: "laufende Forschung", v: esc(T.forsch_fortschritt_name), cls: "wort", bar: L.forsch_fortschritt,
              u: `${fz ? `${fmt(+fz[1], 2)} von ${fmt(+fz[2], 2)} · ` : ""}${T.forsch_dauer ? `fertig ${esc(T.forsch_dauer)}` : ""}`,
              title: "laufende Forschung wie im Forschungsfenster (Daten-Mod ab 0.16): Fortschritt / Kosten, voraussichtlich fertig" }
          : num(lv.research_progress) && { l: "laufende Forschung", v: fmt(lv.research_progress, 1), t: trend(vorm(rSer), 2, 1), s: spark(rSer, { color: "--c4" }),
            title: "research_progress laut Daten-Mod (Fortschrittspunkte); Trend = Zuwachs im letzten Monat, Linie = je Monat" },
          num(jeMonat) && { l: "Forschung je Monat", v: fmt(jeMonat, 2), u: `${fmt(rs, 3)} × (1 + ${pct(rsm, 1)})`,
            title: "Grundwert research_speed × (1 + Modifikator Forschungstempo), Land-Modifikatoren laut Daten-Mod; nachgerechnet = Zuwachs der laufenden Forschung" },
          { l: "Institutionen eingeführt", v: `${fmt(nEin, 0)} <i>von ${fmt(nInst, 0)}</i>`, title: "eingeführt / Institutionen, die es in der Welt gibt" }],
    small: [zeitalter && { l: "Zeitalter", v: esc(zeitalter), cls: "wort" },
            num(LM.embrace_institution_cost_modifier) && { l: "Einführungskosten Institutionen", v: sgn(LM.embrace_institution_cost_modifier * 100, 0) + " %",
              cls: LM.embrace_institution_cost_modifier > 0 ? "neg" : "pos", title: "Land-Modifikator embrace_institution_cost_modifier" },
            num(LM.global_institution_growth_modifier) && { l: "Verbreitung Institutionen", v: sgn(LM.global_institution_growth_modifier * 100, 0) + " %",
              cls: LM.global_institution_growth_modifier < 0 ? "neg" : "pos", title: "Land-Modifikator global_institution_growth_modifier" }],
  });
  const instKarte = inst.length || Object.keys(stand).length ? `<div class="card"><h3>Institutionen</h3>${inst.length ? table([
      { t: "Institution", l: true, f: x => esc(x.name) }, { t: "bei uns", l: true, f: beiUns },
      { t: "entstanden in", l: true, f: x => x.entstanden ? esc(x.ursprung || "–") : `<span class="hint">noch nicht</span>` },
      { t: "nach Monaten im Zeitalter", f: x => num(x.monate) ? fmt(x.monate, 0) : "–" }], inst, { scroll: false }) : breakdown(T.GetInstitutionInfo)}
      <p class="hint">Welt und Ursprungsort: Spielstand (institution_manager); „bei uns“: Spieltext. „nach Monaten im Zeitalter“ zählt, bis die
      Institution entsteht, und bleibt dann stehen; bei den Institutionen des ersten Zeitalters leer.</p></div>` : "";
  // Fortschritte nach Zeitalter (Zeitalter aus den Spieldateien); einzigartige Fortschritte laut Spieltext, erforschte markiert
  const zeit = FI.zeitalter || [];
  const alleNamen = new Set(zeit.flatMap(z => z.fortschritte));
  const einzig = String(T.GetUniqueAdvancesInfo || "").split("\n").map(s => s.trim()).filter(s => s && !/^Einzigartige Fortschritte/.test(s));
  const fortKarte = fo?.fortschritte?.length ? `<div class="card"><h3>Fortschritte – ${fo.erforscht} erforscht</h3>
      ${zeit.length ? zeit.map(z => `<details class="more"><summary>${esc(z.name)} <span class="hint">${z.fortschritte.length}</span></summary>
        <div class="hint">${z.fortschritte.map(esc).join(" · ")}</div></details>`).join("")
        : `<details class="more"><summary>alle ${fo.fortschritte.length} Fortschritte</summary><div class="hint">${fo.fortschritte.map(a => esc(a.name)).join(" · ")}</div></details>`}
      ${einzig.length ? `<div class="sect" style="margin-top:10px">Einzigartige Fortschritte – ${einzig.length}</div>
        <div>${einzig.map(n => alleNamen.has(n) ? `<span class="tag">${esc(n)} ✓</span>` : `<span class="tag" style="opacity:.6">${esc(n)}</span>`).join(" ")}</div>
        <p class="hint">✓ = erforscht; blasser = noch nicht erforscht.</p>` : ""}</div>` : "";
  // Zeitalter-Vorlieben: alle Zeilen sichtbar (vorher nur die erste)
  const vorlieben = T.GetAgePreferenceInfo ? `<div class="card"><h3>Zeitalter – Vorlieben <span class="code">GetAgePreferenceInfo</span></h3>
      ${breakdown(T.GetAgePreferenceInfo).replace(/<details class="bk">/g, '<details class="bk" open>')}</div>` : "";
  // Vorschlag zum Schwerpunkt des Wirtschaftsplans (Ansicht Fortschritte, 30.10.): techbaum.fuer_series liefert alle Schwerpunkte,
  // gezeigt wird der gewählte (wie die Empfehlungen); Gründe, Regeln und der ganze Baum in der Ansicht #techbaum
  const TV = d.techbaum_vorschlag || {}, TF = (TV.fokusse || {})[wpFokus(d)];
  const tbL = (k, n) => `<a href="#techbaum/${encodeURIComponent(k)}">${esc(n)}</a>`;
  const tbKarte = TF ? `<div class="card"><h3>Vorschlag für den Schwerpunkt „${esc(TF.name)}“</h3>
      ${TF.eintraege.length ? `<ol class="tb-gr">${TF.eintraege.slice(0, 5).map(e => `<li>${tbL(e.key, e.name)}${e.laeuft ? ` <span class="tag">läuft</span>` : ""}
        <span class="hint">${e.punkte} Punkte · ${num(e.kosten) ? `${fmt(e.kosten, 2)}${num(e.monate) ? ` ≈ ${fmt(e.monate, 1)} Monate` : ""}` : "Kosten im Spiel"}</span>
        <div class="hint">${esc(e.gruende[0] || "")}</div></li>`).join("")}</ol>` : `<p class="hint">Jetzt erforschbar ist keiner mit Bezug zum Schwerpunkt.</p>`}
      ${TF.ziele.length ? `<h5>Ziele mit kurzem Weg</h5><ul class="tb-gr">${TF.ziele.slice(0, 3).map(e => `<li>${e.weg.map(w => tbL(w.key, w.name)
          + (w.gesperrt ? ` <span class="warn" title="${esc(w.gesperrt)}">gesperrt</span>` : "")).join(" → ")}
        <span class="hint">${e.punkte} Punkte${num(e.weg_kosten) ? ` · ${fmt(e.weg_kosten, 2)} Forschung` : ""}</span><div class="hint">${esc(e.gruende[0] || "")}</div></li>`).join("")}</ul>` : ""}
      <p class="hint">Schwerpunkt wie in der Kachel Wirtschaftsplan; Gründe, Reihung und alle Fortschritte: <a href="#techbaum">Ansicht Fortschritte</a>.
        Kosten laut Defines (am Spielwert geprüft), Monate = Kosten ÷ Forschung je Monat.</p></div>`
    : TV.fehler ? `<div class="card"><h3>Vorschlag zum Schwerpunkt</h3><p class="neg">${esc(TV.fehler)}</p></div>` : "";
  return { head, body: `<div class="grid3">${forschKarte}${tbKarte}${instKarte}${fortKarte}${vorlieben}</div>` };
}

// Orte (Nutzerwunsch 01.10.): Vergleichstabelle aller eigenen Orte mit Summen je Provinz statt der alten Mini-Kacheln
// (dieselben Inhalte stehen in den Ortskacheln unter „Einzelne Orte“), fehlende Steuergrundlage durch Kontrolle,
// Hafen/Fluss/Straßen/Festung und Wanderung/Bekehrung als eigene Karten.
// Gebäudeunterhalt = GetTotalUpkeep des Ortes (= − location_net_building_profit, der frühere „Gebäude netto“-Wert): Unterhalt der
// Landesgebäude (Tempel, Marktplatz, Getreidespeicher, Kai, Burg), geprüft 01.10. gegen den Spielstand (Σ unterhalt je Ort:
// Den Haag 0,705, Amsterdam 0,604, Dordrecht 0,445) – kein Gebäudegewinn (der steht in der Produktionskachel)
const ortUnterhalt = (o, lw = {}) => num(lw.GetTotalUpkeep) ? lw.GetTotalUpkeep : num(o.L?.building_profit) ? -o.L.building_profit : null;

function orte(d, P) {
  if (!P.orte.length) return "";
  const A = d.alles?.werte?.ort || {}, T = d.alles?.texte?.ort || {}, gn = (P.W.namen || {}).gueter || {};
  const lw = o => A[o.id] || {}, tx = o => T[o.id] || {};
  const all = P.orte;
  const pop = o => o.L.population ?? o.bev, ctrl = o => o.L.control ?? o.kontrolle, maxc = o => o.L.max_control;
  const prox = o => o.L.proximity ?? o.naehe, mkt = o => o.L.market_access ?? o.marktzugang;
  const ent = o => o.L.development ?? o.entwicklung, wst = o => o.L.prosperity ?? o.wohlstand;
  // Steuergrundlage / möglich = GetTotalTaxBase / GetTotalPossibleTaxBase des Ortes (Spielstand steuer / moegliche_steuer)
  const fehlt = o => num(o.moegliche_steuer) && num(o.steuer) ? o.moegliche_steuer - o.steuer : null;
  const uh = o => ortUnterhalt(o, lw(o));
  const stadt = o => num(lw(o).HasCityStatus) ? lw(o).HasCityStatus === 1 : ["town", "city"].includes(o.rang);
  // Beitrag der Nähe zur max. Kontrolle laut Aufschlüsselung des Spiels (Zeile „Nähe zu Hauptsitz: +33.85%“)
  const ausNaehe = o => { const m = String(tx(o).GetMaxControlInfo || "").match(/Nähe zu Hauptsitz:\s*([+-]?[\d.]+)%/); return m ? +m[1] / 100 : null; };
  const pz = v => num(v) ? fmt(v * 100, 0) : "–";
  // Name öffnet die Ortskachel (Klick-Handler für a[data-oeffne] unten bei den Kachel-Handlern)
  const ortN = o => `<a href="#ort_${o.id}" data-oeffne="ort_${o.id}">${esc(o.name)}</a>`;
  const ort = o => `${ortN(o)} <span class="hint">${esc(o.w.rang_name || "")}</span>`;      // mit Rang nur in der Vergleichstabelle

  // Kopf (Nutzerwunsch 01.10.): Ø Kontrolle steht in „Land und Leute“ und fällt hier weg
  const st = sum(all.map(o => o.steuer)), sm = sum(all.map(o => o.moegliche_steuer)), fs = sm - st;
  const pAvg = avg(all.map(prox)), mAvg = avg(all.map(mkt));
  const head = hd({
    big: [{ l: "Steuergrundlage / möglich", v: `${fmt(st, 1)} <i>/ ${fmt(sm, 1)}</i>`, bar: sm ? st / sm : null,
            title: "Summe der Orte: Steuergrundlage gegen mögliche Steuergrundlage (Spielstand). Balken = Anteil an der möglichen." },
          { l: "fehlt durch Kontrolle", v: fmt(fs, 1), cls: fs >= 0.05 ? "neg" : "", u: sm ? `${pct(fs / sm, 0)} der möglichen` : "",
            title: "mögliche Steuergrundlage − Steuergrundlage, Summe der Orte" }],
    small: [{ l: "Orte", v: String(all.length) },
            { l: "Städte", v: `${all.filter(stadt).length} <i>von ${all.length}</i>`, title: "Orte mit Stadtstatus (Spielwert HasCityStatus)" },
            { l: "Ø Nähe", v: fmt(pAvg, 0), bar: num(pAvg) ? pAvg / 100 : null, title: "ungewichteter Durchschnitt der Orte" },
            { l: "Ø Marktzugriff", v: pct(mAvg, 0), bar: mAvg, title: "ungewichteter Durchschnitt der Orte" },
            { l: "Gebäudeunterhalt", v: fmt(sum(all.map(uh)), 2),
              title: "Unterhalt der Landesgebäude (Tempel, Marktplatz, Getreidespeicher, Kai, Burg …) aller Orte, Spielwert GetTotalUpkeep je Ort" }],
  });

  // Orte im Vergleich: eine Zeile je Ort, Summenzeile je Provinz (Region › Gebiet nur, wenn es mehrere gibt) und gesamt
  const cols = [
    { t: "Ort", f: ort },
    { t: "Bevölkerung (Tsd.)", f: o => fmt(pop(o), 2), g: L => fmt(sum(L.map(pop)), 2) },
    { t: "Kontrolle / max. (%)", f: o => `${pz(ctrl(o))} / ${pz(maxc(o))}`, g: L => `Ø ${pz(avg(L.map(ctrl)))}` },
    { t: "Nähe", f: o => fmt(prox(o), 0), g: L => `Ø ${fmt(avg(L.map(prox)), 0)}` },
    { t: "Steuergrundlage / möglich", f: o => `${fmt(o.steuer, 2)} / ${fmt(o.moegliche_steuer, 2)}`,
      g: L => `${fmt(sum(L.map(o => o.steuer)), 2)} / ${fmt(sum(L.map(o => o.moegliche_steuer)), 2)}` },
    { t: "fehlt", f: o => fmt(fehlt(o), 2), cls: o => fehlt(o) >= 0.005 ? "neg" : "", g: L => fmt(sum(L.map(fehlt)), 2) },
    { t: "Entwicklung", f: o => fmt(ent(o), 1), g: L => fmt(sum(L.map(ent)), 1) },
    { t: "Wohlstand", f: o => fmt(wst(o), 2), g: L => `Ø ${fmt(avg(L.map(wst)), 2)}` },
    { t: "Marktzugriff (%)", f: o => pz(mkt(o)), g: L => `Ø ${pz(avg(L.map(mkt)))}` },
    { t: "Zufriedenheit (%)", f: o => pz(o.L.satisfaction), g: L => `Ø ${pz(avg(L.map(o => o.L.satisfaction)))}` },
    { t: "Rohstoff", l: true, f: o => esc(gn[o.rohstoff] || o.rohstoff || "–"), g: () => "" },
    { t: "Gebäudeunterhalt", f: o => fmt(uh(o), 2), g: L => fmt(sum(L.map(uh)), 2) },
  ];
  const zeile = o => `<tr>${cols.map(c => `<td class="${[c.l ? "l" : "", c.cls ? c.cls(o) : ""].join(" ")}">${c.f(o)}</td>`).join("")}</tr>`;
  const summe = (cls, titel, L) => `<tr class="${cls}"><td class="l">${titel}</td>${cols.slice(1).map(c => `<td class="${c.l ? "l" : ""}">${c.g(L)}</td>`).join("")}</tr>`;
  const prov = {};
  for (const o of all) (prov[o.w.provinz_name || "?"] ??= []).push(o);
  const provs = Object.entries(prov).sort(([a], [b]) => a.localeCompare(b));
  const rg = [...new Set(all.map(o => [o.w.region_name, o.w.gebiet_name].filter(Boolean).join(" › ")))];
  const rows = provs.map(([p, L]) => (provs.length > 1 ? summe("grp", `${esc(p)}${rg.length > 1 ? ` <span class="hint">${esc([L[0].w.region_name, L[0].w.gebiet_name].filter(Boolean).join(" › "))}</span>` : ""} <span class="hint">${L.length} Orte</span>`, L) : "")
    + L.slice().sort((a, b) => (pop(b) ?? 0) - (pop(a) ?? 0)).map(zeile).join("")).join("") + summe("ges", `Gesamt <span class="hint">${all.length} Orte</span>`, all);
  const vergleich = `<div class="card"><h3>Orte im Vergleich</h3><div style="overflow-x:auto"><table><thead><tr>${cols.map(c => `<th class="${c.l ? "l" : ""}">${esc(c.t)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>
    <p class="hint">${rg.length === 1 ? `Region › Gebiet: ${esc(rg[0])}. ` : ""}Steuergrundlage / möglich laut Spielstand ${esc(d.meta.datum)} (Spielwerte GetTotalTaxBase / GetTotalPossibleTaxBase),
    fehlt = möglich − Steuergrundlage; übrige Werte live ${esc(P.LD.datum || "")}. Gebäudeunterhalt = Unterhalt der Landesgebäude (GetTotalUpkeep).
    Ø = ungewichteter Durchschnitt. Ortsname anklicken öffnet die Ortskachel.</p></div>`;

  // Wo Steuergrundlage fehlt: Steuergrundlage ≈ möglich × Kontrolle; Kontrolle am Deckel → nur höhere max. Kontrolle hilft
  const fl = all.filter(o => fehlt(o) >= 0.005).sort((a, b) => fehlt(b) - fehlt(a));
  const amDeckel = all.filter(o => num(ctrl(o)) && num(maxc(o)) && maxc(o) - ctrl(o) < 0.01).length;
  const bsp = fl[0];
  const naeheFaktor = all.every(o => num(ausNaehe(o)) && num(prox(o)) && Math.abs(ausNaehe(o) - 0.0075 * prox(o)) < 0.001);
  const fehltKarte = fl.length ? `<div class="card thw"><h3>Wo Steuergrundlage fehlt – ${fmt(sum(fl.map(fehlt)), 2)}</h3>${table([
      { t: "Ort", f: ortN }, { t: "fehlt", f: o => fmt(fehlt(o), 2), cls: () => "neg" },
      { t: "Kontrolle (%)", f: o => pz(ctrl(o)) }, { t: "max. Kontrolle (%)", f: o => pz(maxc(o)) },
      { t: "Nähe", f: o => fmt(prox(o), 0) }, { t: "davon Nähe (%)", f: o => pz(ausNaehe(o)) }], fl)}
    ${fl.map(o => lazy(`orte:fehlt:${o.id}`, `${esc(o.name)} – max. Kontrolle ${pz(maxc(o))} %, Nähe ${fmt(prox(o), 0)}`, () => `<h5>Max. Kontrolle <span class="code">GetMaxControlInfo</span></h5>${breakdown(tx(o).GetMaxControlInfo)}
      <h5>Nähe <span class="code">GetProximityInfo</span></h5>${breakdown(tx(o).GetProximityInfo)}`)).join("")}
    <p class="hint">Steuergrundlage ≈ möglich × Kontrolle (z. B. ${esc(bsp.name)}: ${fmt(bsp.moegliche_steuer, 2)} × ${pz(ctrl(bsp))} % = ${fmt(bsp.moegliche_steuer * ctrl(bsp), 2)},
      laut Spiel ${fmt(bsp.steuer, 2)}). ${amDeckel} von ${all.length} Orten haben die max. Kontrolle erreicht – dort steigt die Steuergrundlage nur mit der max. Kontrolle.
      „davon Nähe“ = Zeile „Nähe zu Hauptsitz“ der Aufschlüsselung${naeheFaktor ? " (bei allen Orten 0,75 × Nähe)" : ""}.</p></div>` : "";

  // Hafen, Fluss, Straßen, Festung (Mod-Werte je Ort; Naturhafen aus den Kartendaten)
  const ja = v => v === 1 ? "ja" : v === 0 ? "nein" : "–";
  const fluss = x => { const n = [1, 2, 3, 4, 5].find(i => x[`HasRiverSize${i}`] === 1); return x.HasRiver === 1 && n ? `ja <span class="hint">Größe ${n}</span>` : ja(x.HasRiver); };
  const lageKarte = `<div class="card thw"><h3>Hafen, Fluss, Straßen, Festung</h3>${table([
      { t: "Ort", f: ortN }, { t: "Küste", f: o => ja(lw(o).IsCoastal) }, { t: "Hafen", f: o => ja(lw(o).HasPort) },
      { t: "Naturhafen (Eignung)", f: o => fmt(o.w.natural_harbor_suitability, 2) }, { t: "Fluss", f: o => fluss(lw(o)) },
      { t: "Straßen (Anzahl)", f: o => fmt(lw(o).num_roads, 0) }, { t: "Festung (Stufe)", f: o => fmt(lw(o).GetFortLevel, 0) }],
      all.slice().sort((a, b) => (pop(b) ?? 0) - (pop(a) ?? 0)))}
    <p class="hint">Spielwerte IsCoastal, HasPort, HasRiver/HasRiverSize1–5, num_roads, GetFortLevel (live ${esc(d.alles?.datum?.ort || "")}); Naturhafen aus den Kartendaten.</p></div>`;

  // Wanderung und Bekehrung: Anziehung (migration_attraction = Spieltext GetLocalMigrationAttraction), Wanderung letzter Monat
  // (Spieltext GetMigrationChange, z. B. „+6“), Bekehrung / Monat (monthly_conversion); Aufschlüsselungen des Spiels je Ort aufklappbar
  const migr = o => { const m = String(tx(o).GetMigrationChange ?? "").match(/[-+−]?\d+/); return m ? +m[0].replace("−", "-") : null; };
  const wanderKarte = `<div class="card thw"><h3>Wanderung und Bekehrung</h3>${table([
      { t: "Ort", f: ortN }, { t: "Wanderungsanziehung", f: o => sgn(lw(o).migration_attraction, 2), cls: o => posneg(lw(o).migration_attraction) },
      { t: "Wanderung letzter Monat (Anzahl)", f: o => sgn(migr(o), 0), cls: o => posneg(migr(o)) },
      { t: "Bekehrung / Monat", f: o => fmt(lw(o).monthly_conversion, 3) }],
      all.slice().sort((a, b) => (lw(b).migration_attraction ?? 0) - (lw(a).migration_attraction ?? 0)))}
    ${lazy("orte:wander", "Aufschlüsselungen je Ort", () => `<div>${all.map(o => `<div><h5>${esc(o.name)}</h5>
      ${tx(o).GetLocalMigrationAttractionInfo ? `<div class="hint">Wanderungsanziehung <span class="code">GetLocalMigrationAttractionInfo</span></div>${breakdown(tx(o).GetLocalMigrationAttractionInfo)}` : ""}
      ${tx(o).GetMigrationInfo ? `<div class="hint">Wanderung letzter Monat <span class="code">GetMigrationInfo</span></div>${breakdown(tx(o).GetMigrationInfo)}` : ""}
      ${tx(o).GetConvertInfo ? `<div class="hint">Bekehrung <span class="code">GetConvertInfo</span></div>${breakdown(tx(o).GetConvertInfo)}` : ""}</div>`).join("")}</div>`)}
    <p class="hint">Spielwerte migration_attraction, GetMigrationChange, monthly_conversion (live ${esc(d.alles?.datum?.ort || "")}).</p></div>`;

  return { head, body: `${vergleich}<div class="grid3" style="margin-top:14px">${fehltKarte}${lageKarte}${wanderKarte}</div>` };
}

function produktion(d, P) {
  const W = P.W, gb = W.gebaeude || {}, gn = (W.namen || {}).gueter || {}, pmn = (W.namen || {}).pms || {};
  const kat = (W.namen || {}).kategorien || {}, pn = d.pop_namen || {};
  if (!P.allGeb.length) return "";
  // laufende Produktionsmethoden je Gebäude aus dem Spielstand (aktuell.gebaeude_pm, ab Format 7 vollständig)
  const PMA = P.A.gebaeude_pm || {}, hatPM = Object.keys(PMA).length > 0;
  const own = new Set([...P.orte.map(o => o.rohstoff).filter(Boolean)]);
  const byType = {};
  for (const b of P.allGeb) {
    const t = byType[b.typ] ??= { typ: b.typ, name: b.name, n: 0, stufen: 0, gewinn: 0, moeglich: 0, besch: 0, plaetze: 0, pms: {} };
    t.n++; t.stufen += b.stufe ?? 0; t.gewinn += b.gewinn ?? 0;
    t.moeglich += b.moeglich ?? 0; t.besch += b.besch ?? 0; t.plaetze += b.plaetze ?? 0;
    for (const pm of PMA[b.id]?.pms || []) t.pms[pm] = (t.pms[pm] || 0) + 1;
  }
  // „im eigenen Land hergestellt“ = Rohstoffe der Orte + Ausgaben der laufenden Methoden
  const pmDef = (typ, name) => (gb[typ]?.pms || []).find(p => p.name === name);
  for (const t of Object.values(byType)) for (const pm of hatPM ? Object.keys(t.pms).map(n => pmDef(t.typ, n)).filter(Boolean) : gb[t.typ]?.pms || [])
    if (pm.produced) own.add(pm.produced);
  const g = x => `<span class="${own.has(x) ? "pos" : ""}" title="${own.has(x) ? "im eigenen Land hergestellt/gefördert" : "aus dem Markt"}">${esc(gn[x] || x)}</span>`;
  const pmZeile = (pm, n) => `<div>${n ? `<span class="tag">${n}×</span> ` : ""}<span class="hint">${esc(pmn[pm.name] || pm.name)}:</span> ${Object.entries(pm.inputs).map(([k, v]) => `${fmt(v, 2)} ${g(k)}`).join(" + ") || "–"} → ${pm.produced ? `${fmt(pm.output, 2)} ${g(pm.produced)}` : "–"}</div>`;
  const pmName = (typ, name) => esc(pmn[name] || pmDef(typ, name)?.name || name);
  const rows = Object.values(byType).sort((a, b) => b.gewinn - a.gewinn);
  const worst = rows.at(-1), best = rows[0], tot = sum(rows.map(t => t.gewinn));
  const minus = P.allGeb.filter(b => (b.gewinn ?? 0) < 0).length;
  const bau = P.A.bau || [], bn = (W.namen || {}).gebaeude || {};
  // Kopf: alle Werte groß in einer Reihe (Nutzerwunsch 29.09.); Verlauf = Summe Gewinn aller Gebäude je Monat (Mod-Gebäudezeilen)
  const gSer = liveSeries(d, "gebaeude_gewinn");
  const head = hd({
    big: [{ l: "Gewinn der Gebäude / Monat", v: fmt(tot, 2), cls: posneg(tot), t: trend(vorm(gSer), 2, 1), s: spark(gSer, { color: "--c1" }),
            title: "Summe Gewinn aller Gebäude live; Trend = Veränderung zum Vormonat; Linie = je Monat (bis 24 Monate)" },
          { l: "Gebäude / Typen", v: `${P.allGeb.length} <i>/ ${rows.length}</i>` },
          { l: "im Bau", v: String(bau.length), title: "Bauprojekte laut Spielstand (Neubau und Ausbau)" }],
    // Zeile zwei: bester und schwächster Typ (Nutzerwunsch 29.09.)
    // Schrift wie „Stoff · Fisch · Salz“ in der Güterkachel (cls wort, Nutzerwunsch 29.09.)
    small: [best && { l: "bester Typ", v: `${esc(best.name)} <i>${fmt(best.gewinn, 2)}</i>`, cls: "wort" },
            worst && { l: "schwächster Typ", v: `${esc(worst.name)} <i class="${posneg(worst.gewinn)}">${fmt(worst.gewinn, 2)}</i>`, cls: "wort" }],
    warn: [minus && `${minus} Gebäude mit Verlust`],
  });
  // Bauprojekte (Spielstand roh.bauprojekte): Fortschritt = progress von total, „Güter angefordert“ = has_active_demand
  const bauKarte = bau.length ? `<div class="card"><h3>Im Bau – ${bau.length}</h3>${table([
    { t: "Gebäude", l: true, f: x => `${esc(bn[x.typ] || x.name || x.typ || x.bedarf)}<div class="hint">${esc(x.ort || "")}</div>` },
    { t: "Stufe jetzt", f: x => x.stufe != null ? fmt(x.stufe, 0) : "Neubau" },
    { t: "Fortschritt", f: x => num(x.fortschritt) && x.gesamt ? `${pct(x.fortschritt / x.gesamt, 0)}<span class="mbar"><i style="width:${Math.min(100, x.fortschritt / x.gesamt * 100)}%"></i></span>` : "nicht begonnen" },
    { t: "Güter angefordert", f: x => x.aktiv ? "ja" : "nein" },
    { t: "fehlende Güter", l: true, f: x => Object.entries(x.fehlt || {}).map(([k, v]) => `${esc(gn[k] || k)} ${fmt(v, 2)}`).join(", ") || "–" },
    { t: "bisher bezahlt", f: x => fmt(x.gold, 1) }], bau, { scroll: false })}
    <p class="hint">Laut Spielstand ${esc(d.meta.datum)}; Fortschritt = progress von total im Bauprojekt.</p></div>` : "";
  // Gebäude mit Verlust einzeln (Nutzerwunsch 29.09.): Einnahmen/Kosten/Gewinn und Texte aus dem Daten-Mod (gleiche IDs wie im
  // Spielstand; GetIncome − GetExpense = GetProfit, z. B. Fischerdorf Alkmaar 0,466 − 0,276 = 0,19), Methode und Status aus dem Spielstand
  // Achtung: der Mod schreibt die Gebäude-Details nur im Januar (Jahresblock) - Einnahmen/Kosten/Hinweise nur zeigen,
  // wenn sie vom selben Tag sind wie der Gewinn (sonst passen sie nicht zusammen; geprüft 29.09.: Gerberei Den Haag
  // Januar +0,116, Juli −0,027); die Aufschlüsselungen tragen ihr Datum
  const mwDat = d.alles?.datum?.gebaeude, gleich = !!mwDat && mwDat === P.LD.extra_datum;
  const MW = gleich ? d.alles?.werte?.gebaeude || {} : {}, MT = d.alles?.texte?.gebaeude || {};
  const STATUS = { LayingOff: "entlässt Arbeiter (LayingOff)" };
  const verl = P.allGeb.filter(b => (b.gewinn ?? 0) < 0).sort((a, b) => a.gewinn - b.gewinn);
  const hinweis = b => { const m = MW[b.id] || {}, st = PMA[b.id]?.status;
    return [st && (STATUS[st] || st), m.HasMissingGoods === 1 && "Güter fehlen", num(m.GetInputGoodsAccess) && m.GetInputGoodsAccess < 1 && `Zufuhrwaren ${pct(m.GetInputGoodsAccess, 0)}`,
            m.IsSubsidized === 1 && "bezuschusst"].filter(Boolean).join(" · ") || "–"; };
  const texte = b => [["Markt", MT[b.id]?.GetMarketInfo], ["Zufuhrwaren", MT[b.id]?.GetInputGoodsInformation], ["Produktion", MT[b.id]?.GetIncomeBreakdown]]
    .filter(([, x]) => x).map(([t, x]) => `<div class="sect">${t}</div>${breakdown(x)}`).join("");
  const verlustKarte = verl.length ? `<div class="card"><h3>Gebäude mit Verlust – ${verl.length}</h3>${table([
    { t: "Gebäude", l: true, f: b => `${esc(b.name)}<div class="hint">${esc(b.ort || "")}</div>` }, { t: "Stufe", f: b => fmt(b.stufe, 0) },
    ...(gleich ? [{ t: "Einnahmen", f: b => fmt(MW[b.id]?.GetIncome, 2) }, { t: "Kosten", f: b => fmt(MW[b.id]?.GetExpense, 2) }] : []),
    { t: "Gewinn", f: b => fmt(b.gewinn, 2), cls: () => "neg" }, { t: "möglich", f: b => fmt(b.moeglich, 2), cls: b => posneg(b.moeglich) },
    { t: "Beschäftigt", f: b => b.besch != null ? `${fmt(b.besch, 2)} / ${fmt(b.plaetze, 2)}` : "–" },
    { t: "Laufende Methode", l: true, f: b => (PMA[b.id]?.pms || []).map(n => pmName(b.typ, n)).join(", ") || "–" },
    { t: "Hinweis", l: true, f: hinweis },
    { t: "Aufschlüsselung", l: true, f: b => { const x = texte(b); return x ? `<details><summary>zeigen${gleich ? "" : ` <span class="hint">(Stand ${esc(mwDat || "")})</span>`}</summary>${x}</details>` : ""; } }], verl, { scroll: false })}
    <p class="hint">Gewinn und möglicher Gewinn live (Daten-Mod ${esc(P.LD.extra_datum || "")}); Methode und Status laut Spielstand ${esc(d.meta.datum)}.
      ${gleich ? "Einnahmen, Kosten und Aufschlüsselung laut Spiel vom selben Tag." : `Einnahmen, Kosten und Aufschlüsselung liefert der Mod nur im Januar (zuletzt ${esc(mwDat || "–")}) – deshalb keine Spalten dafür, die Aufschlüsselung ist älter.`}</p></div>` : "";
  return { head, body: `${verlustKarte}${bauKarte}<div class="card"><h3>Produktionsketten der eigenen Gebäude</h3>
    ${table([{ t: "Gebäude", l: true, f: t => { const b = gb[t.typ] || {}; return `${esc(t.name)}<div class="hint">${esc(kat[b.category] || b.category || "")}${b.pop_type ? " · " + esc(pn[b.pop_type] || b.pop_type) : ""}</div>`; } },
             { t: "Anzahl", f: t => t.n }, { t: "Stufen", f: t => fmt(t.stufen, 0) }, { t: "Gewinn", f: t => fmt(t.gewinn, 2), cls: t => t.gewinn < 0 ? "neg" : "" },
             ...(P.useLiveGeb ? [{ t: "möglich", f: t => fmt(t.moeglich, 2), cls: t => posneg(t.moeglich) },
               { t: "Beschäftigt", f: t => t.plaetze ? `${fmt(t.besch, 2)} / ${fmt(t.plaetze, 2)}<span class="mbar"><i style="width:${Math.min(100, t.besch / t.plaetze * 100)}%"></i></span>` : "–" }] : []),
             { t: hatPM ? "Laufende Methode: Eingänge → Ausgabe" : "Produktionsmethoden: Eingänge → Ausgabe", l: true, f: t => {
                 if (hatPM) {                                             // nur die laufenden Methoden (Nutzerwunsch 29.09.), Anzahl der Gebäude davor
                   const e = Object.entries(t.pms);
                   return e.map(([n, c]) => { const pm = pmDef(t.typ, n); return pm ? pmZeile(pm, t.n > 1 ? c : 0) : `<div>${t.n > 1 ? `<span class="tag">${c}×</span> ` : ""}${esc(pmn[n] || n)}</div>`; }).join("")
                     || `<span class="hint">keine Produktion</span>`;
                 }
                 const pms = gb[t.typ]?.pms || [], groups = new Set(pms.map(p => p.gruppe)).size;
                 return pms.map(pm => `<div>${groups > 1 ? `<span class="tag">Gruppe ${pm.gruppe}</span>` : ""}<span class="hint">${esc(pmn[pm.name] || pm.name)}:</span> ${Object.entries(pm.inputs).map(([k, v]) => `${fmt(v, 2)} ${g(k)}`).join(" + ") || "–"} → ${pm.produced ? `${fmt(pm.output, 2)} ${g(pm.produced)}` : "–"}</div>`).join("") || "–"; } }], rows)}
    <p class="hint">${hatPM ? `Laufende Methode je Gebäude laut Spielstand ${esc(d.meta.datum)} (Zahl davor = wie viele Gebäude des Typs sie nutzen; bei zwei Gruppen laufen zwei Methoden).`
      : "Je Gruppe läuft eine Methode; welche gerade läuft, steht erst in neueren Spielständen."} Grün = Gut wird im eigenen Land gefördert oder hergestellt; sonst muss es aus dem Markt kommen.
      ${P.useLiveGeb ? `Gewinn, „möglich“ (potential_profit des Spiels) und Beschäftigt (belegte / verfügbare Stellen) live, Daten-Mod ${esc(P.LD.extra_datum || "")}.` : ""}</p></div>` };
}

// ---- eigene Güterbilanz (Güter- und Handelskachel, 29.09.): Förderung der Orte (live rgo_output), Herstellung und Verbrauch
// der eigenen Gebäude nominal = laufende Methode (Spielstand) × Stufe, ohne Zu-/Abschläge (Arbeiter, Marktzugriff, Zufuhr).
// Fehlend = eigener Saldo < 0 (muss gekauft werden); knapp = im ganzen Heimatmarkt Nachfrage > Angebot × 1,05;
// Engpass = beides zugleich (nur dann Warnung, Nutzerwunsch 29.09.).
// markt (optional): nur Orte und Gebäude in diesem Markt, knapp in diesem Markt (Marktkacheln); sonst das ganze Land.
// Knapp (30.09.): Nachfrage > Angebot × 1,05 UND der Preis steigt (letzter Schritt im Preisverlauf des Spielstands) –
// sonst behandelt das Spiel das Gut nicht als knapp (Lübeck 1342: Zucker ohne Angebot, 1,0 auf Vorrat, Preis fällt 6,36 → 3,21).
// Gleiche Regel wie history.ist_knapp (Zähler „knapp“ je Spielstand).
const preisSchritt = x => { const pv = (x.preisverlauf || []).filter(num); return pv.length > 1 ? pv.at(-1) - pv.at(-2) : null; };
const istKnapp = x => (x.nachfrage ?? 0) > (x.angebot ?? 0) * 1.05 && (preisSchritt(x) ?? 1) > 0;
// Ortssaldo wie im Marktfenster (Market.GetBalanceWithoutTrades): Angebot aus Produktion − Verbrauch ohne Handel (Trade,
// BurgherTrades). Geprüft 1.2.1342 an allen 10 Gütern im Fenster (Stoff +54,88, Wolle −24,13, Seide −9,33 …; das Spiel schneidet
// nach 2 Stellen ab). Das Spielstandfeld possible ist es nicht (Wolle +10,65).
const ortssaldo = x => (x.angebot_quellen?.Production ?? 0)
  - sum(Object.entries(x.verbrauch || {}).filter(([k]) => k !== "Trade" && k !== "BurgherTrades").map(([, v]) => v));
function gueterBilanz(P, markt = null) {
  const PMA = P.A.gebaeude_pm || {}, GB = P.W.gebaeude || {}, home = P.A.markt?.id;
  const orte = markt ? P.orte.filter(o => (o.markt ?? home) === markt.id) : P.orte;
  const ortIds = new Set(orte.map(o => o.id));
  const geb = markt ? P.allGeb.filter(b => ortIds.has(b.ort_id)) : P.allGeb;
  const foerd = {}, herst = {}, verbr = {}, gebH = {}, gebV = {}, orteF = {};
  for (const o of orte) if (o.rohstoff && num(o.L.rgo_output)) {
    foerd[o.rohstoff] = (foerd[o.rohstoff] || 0) + o.L.rgo_output; (orteF[o.rohstoff] ??= []).push(o.name);
  }
  // Gebäude ohne Arbeiter erzeugen und verbrauchen nichts (Spieltext: „Erzeugte … mit x % der benötigten Arbeiter“) -> nicht
  // zählen; geprüft 29.09.: 3 Schneiderzünfte auf Seidenweberei, 0 Arbeiter, entlassen -> sonst Fehlalarm „Seide fehlt“
  const ohneArbeit = new Set(P.useLiveGeb ? geb.filter(b => num(b.besch) && b.besch <= 0).map(b => b.id) : []);
  for (const b of geb) for (const n of ohneArbeit.has(b.id) ? [] : PMA[b.id]?.pms || []) {
    const pm = (GB[b.typ]?.pms || []).find(p => p.name === n), lv = b.stufe ?? 0;
    if (!pm || !lv) continue;
    if (pm.produced) { herst[pm.produced] = (herst[pm.produced] || 0) + pm.output * lv; (gebH[pm.produced] ??= new Set()).add(b.typ); }
    for (const [k, v] of Object.entries(pm.inputs || {})) { verbr[k] = (verbr[k] || 0) + v * lv; (gebV[k] ??= new Set()).add(b.typ); }
  }
  const eigen = new Set([...Object.keys(foerd), ...Object.keys(herst), ...Object.keys(verbr)]);
  const saldo = k => (foerd[k] || 0) + (herst[k] || 0) - (verbr[k] || 0);
  const knapp = (((markt || P.A.markt) || {}).gueter || []).filter(istKnapp)
    .sort((a, b) => (b.nachfrage - b.angebot) - (a.nachfrage - a.angebot));
  const fehlend = [...eigen].filter(k => saldo(k) < 0).sort((a, b) => saldo(a) - saldo(b));
  const knappSet = new Set(knapp.map(x => x.gut));
  return { foerd, herst, verbr, gebH, gebV, orteF, eigen, saldo, knapp, fehlend, engpass: fehlend.filter(k => knappSet.has(k)),
           ohneArbeit: ohneArbeit.size };
}
const engpassWarn = (B, gn, wo = "im Heimatmarkt") => B.engpass.map(k => `${esc(gn[k] || k)} fehlt dir (${fmt(B.saldo(k), 2)}) und ist ${wo} knapp`);

function gueter(d, P) {
  const W = P.W, goods = W.gueter || {}, gn = (W.namen || {}).gueter || {}, bn = (W.namen || {}).gebaeude || {}, pn = d.pop_namen || {};
  if (!Object.keys(goods).length) return "";
  const m = P.A.markt || {}, mg = Object.fromEntries((m.gueter || []).map(x => [x.gut, x]));
  const pr = ((P.LD.preise || [])[0]) || {};
  const pop = x => Object.entries(x.demand_add || {}).map(([k, v]) => `${esc(pn[k] || (k === "all" ? "alle" : k))} ${fmt(v * 1000, 1)}`).join(", ");
  const mult = x => Object.entries(x.demand_multiply || {}).filter(([, v]) => v !== 1).map(([k, v]) => `${esc(pn[k] || (k === "upper" ? "Oberschicht" : k))} ×${fmt(v, 1)}`).join(", ");
  const rows = Object.entries(goods).map(([k, x]) => ({ k, x, mk: mg[k] || {} })).sort((a, b) => (gn[a.k] || a.k).localeCompare(gn[b.k] || b.k));
  const B = gueterBilanz(P);
  const { foerd, herst, verbr, gebH, gebV, orteF, eigen } = B;
  const menge = k => (foerd[k] || 0) + (herst[k] || 0) + (verbr[k] || 0);
  // Preise je Monat im Heimatmarkt (Mod, letzte 24 Monate)
  const PV = d.preis_verlauf || { monate: [], gueter: {} };
  // Preis 0 = Gut wird im Markt nicht angeboten (24 von 74 Gütern, geprüft 29.09.) -> kein Preis, nicht im Preisniveau
  const pos = v => num(v) && v > 0;
  const pser = k => (PV.gueter[k] || []).filter(pos);
  const preis = k => [pr["price_" + k], mg[k]?.preis].find(pos);
  const preisZelle = k => { const s = pser(k); return pos(preis(k)) ? `${fmt(preis(k), 2)} ${trend(vorm(s), 2, 0)}${spark(s, { w: 70, h: 18, color: "--c4" })}` : "–"; };
  // Preisniveau: Ø Preis ÷ Grundpreis über alle Güter mit Preis > 0 im Heimatmarkt, je Monat
  const niveau = PV.monate.map((_, i) => { const r = Object.entries(PV.gueter).map(([k, s]) => pos(s[i]) && goods[k]?.default_market_price ? s[i] / goods[k].default_market_price : null).filter(num);
    return r.length ? sum(r) / r.length : null; }).filter(num);
  // „hergestellt/verbraucht von“: eigene Gebäudetypen mit Namen, übrige nur als Anzahl
  const gebListe = (eig, alle) => { const e = [...(eig || [])], rest = new Set((alle || []).map(x => x.gebaeude).filter(t => !e.includes(t))).size;
    return `${e.map(t => esc(bn[t] || t)).join(", ") || "–"}${rest ? ` <span class="hint">+${rest} weitere</span>` : ""}`; };
  const GT = d.alles?.texte?.gut || {};
  // Spieltexte je Gut (Daten-Mod). Quellen und Nachfrage durch Gebäude nicht mehr als Spieltext: ohne Land ausgewertet fehlten
  // 86 von 126 Quellen und 1.552 von 1.713 Gebäuden (Test 0.18, 24.10.) – stattdessen vollständig aus den Spieldateien
  const GTXT = [["GetDemandsInfo", "Nachfrage"], ["GetPopsDemandInfo", "Nachfrage durch Pops"], ["GetRawMaterialMethodInfo", "Rohstoff-Förderung"]];
  const GS = d.gebaeude_status || {};
  const gebGruppen = liste => {
    const ks = [...new Set((liste || []).map(x => x.gebaeude))].sort((a, b) => (bn[a] || a).localeCompare(bn[b] || b, "de"));
    if (!ks.length) return `<div class="hint">keine Gebäudeart</div>`;
    const g = { bei: [], frei: [], adv: [], land: [], sonder: [] };
    for (const k of ks) { const s = GS[k] || {};
      (s.bei_uns ? g.bei : s.sonder ? g.sonder : s.fortschritt ? g.adv : s.landbedingung ? g.land : g.frei).push(k); }
    const n = k => esc(bn[k] || k);
    const zeile = (l, ks, f = n, title = "") => ks.length ? `<div${title ? ` title="${esc(title)}"` : ""}><b>${l}</b> <span class="hint">${ks.length}</span>: ${ks.map(f).join(", ")}</div>` : "";
    return `<div class="brk">${zeile("bei uns", g.bei, k => `${n(k)} <i>×${GS[k].bei_uns}</i>`)}${zeile("freigeschaltet", g.frei, n, "kein Fortschritt nötig bzw. erforscht, keine Bedingung des Landes; Bedingungen des Orts (Fluss, Küste, Entwicklung …) nicht geprüft")}`
      + zeile("Fortschritt fehlt", g.adv, k => `${n(k)} <i>(${esc(GS[k].fortschritt.join(" / "))})</i>`)
      + zeile("mit Bedingung des Landes", g.land, n, "country_potential in der Spieldatei (Religion, Kultur, Regierung …) – nicht ausgewertet")
      + (g.sonder.length ? `<details class="more"><summary>Sondergebäude <span class="hint">${g.sonder.length}</span></summary><div class="hint">${g.sonder.map(n).join(", ")}</div></details>` : "")
      + `</div>`;
  };
  const aufschl = r => { const t = GT[r.k] || {}, f = GTXT.filter(([x]) => t[x]);
    return lazy(`gut:${r.k}`, "zeigen", () =>
      `<div class="sect">Hergestellt von (laut Spieldateien)</div>`
      + (r.x.category === "raw_material" ? `<div class="hint">Förderung in Orten mit diesem Rohstoff${orteF[r.k] ? ` – bei uns: ${esc(orteF[r.k].join(", "))}` : ""}</div>` : "")
      + gebGruppen(r.x.produziert_von)
      + `<div class="sect">Verbraucht von Gebäuden (laut Spieldateien)</div>${gebGruppen(r.x.verbraucht_von)}`
      + f.map(([x, l]) => `<div class="sect">${l}</div>${breakdown(t[x])}`).join("")
      + `<div class="sect">Pop-Nachfrage (Definition, ‰ je Pop)</div><div class="hint">${pop(r.x) || "–"}${mult(r.x) ? `<br>${mult(r.x)}` : ""}</div>`); };
  const gutZelle = r => `${esc(gn[r.k] || r.k)}<div class="hint">${esc(((W.namen || {}).kategorien || {})[r.x.category] || r.x.category || "")}${r.x.food ? " · Nahrung " + fmt(r.x.food, 1) : ""}</div>`;
  const eigRows = rows.filter(r => eigen.has(r.k)).sort((a, b) => menge(b.k) - menge(a.k));
  const restRows = rows.filter(r => !eigen.has(r.k));
  // Kopf (Nutzerwunsch 29.09.): groß die 3 Güter, die am meisten fehlen (Saldo am stärksten negativ) und die 3 am meisten
  // produzierten (Förderung + Herstellung), eigene Güter, Güter; klein darunter teuerste und günstigste ggü. Grundpreis
  const saldo = B.saldo;
  const erz = k => (foerd[k] || 0) + (herst[k] || 0);
  const fehlt3 = B.fehlend.slice(0, 3);
  const prod3 = [...eigen].filter(k => erz(k) > 0).sort((a, b) => erz(b) - erz(a)).slice(0, 3);
  const liste = (ks, f, cls) => ks.map(k => `${esc(gn[k] || k)} <i class="${cls}">${f(k)}</i>`).join(" · ") || "–";
  // teuerste und günstigste im Vergleich zum Grundpreis: angebotene Güter (Preis > 0), Preis live im Heimatmarkt
  const verh = k => preis(k) / goods[k].default_market_price;
  const angeboten = Object.keys(goods).filter(k => pos(preis(k)) && goods[k].default_market_price).sort((a, b) => verh(b) - verh(a));
  const teuer3 = angeboten.slice(0, 3), guenstig3 = angeboten.slice(-3).reverse();
  // Reihenfolge und Anordnung (Nutzerwunsch 29.09.): „am meisten produziert“ über „fehlen am meisten“, „günstigste“ über
  // „teuerste“ – je als Spalte (stack). Zugeklappt steht die Preis-Spalte in der zweiten Zeile, aufgeklappt beide Spalten
  // nebeneinander in einer Reihe (neben). Knappe Güter und die Engpass-Warnung stehen in der jeweiligen Marktkachel.
  const head = hd({
    big: [{ stack: [
            { l: "am meisten produziert", v: liste(prod3, k => fmt(erz(k), 2), "pos"), cls: "wort",
              title: "Förderung deiner Orte (live) + Herstellung deiner Gebäude (Nennwert: laufende Methode × Stufe)" },
            { l: "fehlen am meisten", v: liste(fehlt3, k => fmt(saldo(k), 2), "neg"), cls: "wort",
              title: "Saldo = Förderung + Herstellung − Verbrauch deiner Gebäude (Nennwerte); negativ = muss aus dem Markt kommen" }] },
          { stack: [
            { l: "günstigste ggü. Grundpreis", v: liste(guenstig3, k => `×${fmt(verh(k), 2)}`, "pos"), cls: "wort", title: "Preis live im Heimatmarkt ÷ Grundpreis, angebotene Güter" },
            { l: "teuerste ggü. Grundpreis", v: liste(teuer3, k => `×${fmt(verh(k), 2)}`, "neg"), cls: "wort", title: "Preis live im Heimatmarkt ÷ Grundpreis, angebotene Güter" }],
            neben: true },                                       // gleiche Schrift wie „am meisten produziert“ (Nutzerwunsch 29.09.)
          { l: "eigene Güter", v: String(eigen.size), title: "Güter, die deine Orte fördern oder deine Gebäude herstellen oder verbrauchen" },
          { l: "Güter", v: String(Object.keys(goods).length) }],
  });
  // Preisniveau oben in der Übersicht (Nutzerwunsch 29.09.)
  const niveauKarte = niveau.length ? `<div class="card"><h3>Preisniveau Heimatmarkt</h3>
    <div class="hk big"><b>×${fmt(niveau.at(-1), 2)}${trend(vorm(niveau), 3, 0)}</b>${spark(niveau, { w: 320, h: 44, color: "--c4" })}</div>
    <p class="hint">Ø Preis ÷ Grundpreis über alle ${angeboten.length} Güter, die im Heimatmarkt angeboten werden (Preis > 0), je Monat laut Daten-Mod
      (${esc(PV.monate[0] || "")} bis ${esc(PV.monate.at(-1) || "")}); unter 1 = im Schnitt billiger als der Grundpreis. Trend zum Vormonat.</p></div>` : "";
  // Aufstellung je 10 (Nutzerwunsch 29.09.), angeordnet wie im Kopf: links produziert über fehlend, rechts günstigste über teuerste
  const top10 = (ks, v, c) => ks.length ? compo(ks.slice(0, 10).map(k => ({ l: gn[k] || k, v: v(k), c })), null) : `<div class="empty">keine</div>`;
  const prodAlle = [...eigen].filter(k => erz(k) > 0).sort((a, b) => erz(b) - erz(a));
  const zehnKarten = `<div class="grid2">
      <div class="card"><h3>Produktion und Bedarf</h3>
        <div class="sect">am meisten produziert – ${Math.min(10, prodAlle.length)} von ${prodAlle.length}</div>${top10(prodAlle, erz, "--c3")}
        <div class="sect" style="margin-top:10px">fehlen am meisten – ${Math.min(10, B.fehlend.length)} von ${B.fehlend.length}</div>${top10(B.fehlend, saldo, "--c5")}
        <p class="hint">Produziert = Förderung deiner Orte + Herstellung deiner Gebäude; fehlend = Saldo mit dem Verbrauch deiner Gebäude (Nennwerte, Gebäude ohne Arbeiter nicht gezählt).</p></div>
      <div class="card"><h3>Preise im Vergleich zum Grundpreis</h3>
        <div class="sect">günstigste – 10 von ${angeboten.length}</div>${top10(angeboten.slice().reverse(), verh, "--c3")}
        <div class="sect" style="margin-top:10px">teuerste – 10 von ${angeboten.length}</div>${top10(angeboten, verh, "--c5")}
        <p class="hint">Preis live im Heimatmarkt ÷ Grundpreis, nur angebotene Güter (Preis > 0).</p></div>
    </div>`;
  const eigenKarte =`<div class="card"><h3>Eigene Güter – ${eigRows.length}</h3>${table([
    { t: "Gut", l: true, f: gutZelle }, { t: "Preis", f: r => preisZelle(r.k) }, { t: "Grundpreis", f: r => fmt(r.x.default_market_price, 1) },
    { t: "Förderung", f: r => foerd[r.k] ? fmt(foerd[r.k], 2) : "" }, { t: "Herstellung", f: r => herst[r.k] ? fmt(herst[r.k], 2) : "" },
    { t: "Verbrauch Gebäude", f: r => verbr[r.k] ? fmt(verbr[r.k], 2) : "" },
    { t: "Saldo", f: r => fmt((foerd[r.k] || 0) + (herst[r.k] || 0) - (verbr[r.k] || 0), 2), cls: r => posneg((foerd[r.k] || 0) + (herst[r.k] || 0) - (verbr[r.k] || 0)) },
    { t: "Angebot / Nachfrage (Markt)", f: r => `${fmt(r.mk.angebot, 1)} / ${fmt(r.mk.nachfrage, 1)}` },
    { t: "hergestellt von", l: true, f: r => `${orteF[r.k] ? `<div>Förderung in ${esc(orteF[r.k].join(", "))}</div>` : ""}${gebH[r.k] || !orteF[r.k] ? gebListe(gebH[r.k], r.x.produziert_von) : ""}` },
    { t: "verbraucht von", l: true, f: r => gebListe(gebV[r.k], r.x.verbraucht_von) },
    { t: "Aufschlüsselung", l: true, f: aufschl }], eigRows, { scroll: false })}
    <p class="hint">Förderung = Rohstoff-Ausstoß deiner Orte (live); Herstellung und Verbrauch Gebäude = laufende Methode × Stufe (nominal, ohne Zu- und
      Abschläge für Arbeiter, Marktzugriff und Zufuhr; Methode laut Spielstand ${esc(d.meta.datum)})${B.ohneArbeit ? `; ${B.ohneArbeit} Gebäude ohne Arbeiter nicht gezählt` : ""}. Pops verbrauchen zusätzlich – siehe Aufschlüsselung.
      Preis live im Heimatmarkt mit Veränderung zum Vormonat und Verlauf; Angebot/Nachfrage = ganzer Markt (Spielstand). „hergestellt/verbraucht von“:
      deine Gebäudetypen, die übrigen des Spiels nur als Anzahl.</p></div>`;
  const restKarte = lazy("gueter:rest", `Übrige Güter <span class="hint">${restRows.length}, ohne eigene Förderung, Herstellung oder Verbrauch</span>`, () => table([
    { t: "Gut", l: true, f: gutZelle }, { t: "Preis", f: r => preisZelle(r.k) }, { t: "Grundpreis", f: r => fmt(r.x.default_market_price, 1) },
    { t: "Angebot / Nachfrage (Markt)", f: r => `${fmt(r.mk.angebot, 1)} / ${fmt(r.mk.nachfrage, 1)}` },
    { t: "hergestellt von", l: true, f: r => gebListe(null, r.x.produziert_von) }, { t: "verbraucht von", l: true, f: r => gebListe(null, r.x.verbraucht_von) },
    { t: "Aufschlüsselung", l: true, f: aufschl }], restRows, { scroll: false }));
  return { head, body: `${niveauKarte}${zehnKarten}${eigenKarte}<div class="card">${restKarte}</div>` };
}

// Ein Markt (Spielstand: aktuell.maerkte ab Format 5, sonst nur aktuell.markt = Heimatmarkt); Live-Werte je Markt-ID
function markt(d, P, m = P.A.markt) {
  if (!m) return "";
  const gn = (P.W.namen || {}).gueter || {};
  const tot = sum((m.haendler || []).map(h => h.macht));
  const h = (m.haendler || []).slice().sort((a, b) => b.macht - a.macht);
  const top = h.slice(0, 7), rest = sum(h.slice(7).map(x => x.macht));
  let ci = 0;
  const pie = pieChart([...top.map(x => ({ label: x.land, value: x.macht, color: x.tag === d.meta.tag ? "--c5" : PALETTE[ci++ % PALETTE.length] })),
                       ...(rest ? [{ label: "übrige", value: rest, color: "--c8" }] : [])]);
  // Schlüssel wie im Spielstand (Market goods: supplied/taken/production_supplied)
  const SRC = { Production: "Produktion", Trade: "Handel", BurgherTrades: "Bürgerhandel", Pops: "Pops", Building: "Gebäude", Buildings: "Gebäude",
                Units: "Einheiten", RawMaterials: "Rohstoffe", Base: "Basis", Roads: "Straßen", Construction: "Bau", Consumption: "Verbrauch" };
  const src = x => Object.entries(x || {}).map(([k, v]) => `${esc(SRC[k] || k)} ${fmt(v, 1)}`).join(", ");
  const goods = (m.gueter || []).filter(x => (x.angebot ?? 0) > 0 || (x.nachfrage ?? 0) > 0).sort((a, b) => (b.angebot ?? 0) - (a.angebot ?? 0));
  const inM = P.orte.filter(o => o.markt == null || o.markt === m.id);      // unsere Orte in diesem Markt
  // unsere Orte: Marktzugriff (live, sonst Spielstand) und die Markt-Modifikatoren des Ortes (live ortmod)
  const OM = d.alles?.werte?.ortmod || {}, OT = d.alles?.texte?.ort || {};
  const access = inM.map(o => ({ id: o.id, name: o.name, z: o.L.market_access ?? o.marktzugang, om: OM[o.id] || {} })).sort((a, b) => (a.z ?? 0) - (b.z ?? 0));
  const ownIdx = h.findIndex(x => x.tag === d.meta.tag), own = h[ownIdx];
  const LM = d.alles?.werte?.markt?.[m.id] || (m.heimat !== false ? Object.values(d.alles?.werte?.markt || {})[0] : null) || {};
  // Marktanziehung dieses Markts auf unsere Hauptstadt (Spieltext Location.GetMarketAttractionInfo; der Daten-Mod schreibt ihn nur
  // für die Hauptstadt, dort stehen alle Märkte absteigend: „Brugge: 149.84%“ = Marktzugriff + Marktanziehung + Verträge …)
  const capT = Object.entries(OT).find(([, v]) => v.GetMarketAttractionInfo);
  let anz = null;
  if (capT && LM.name) {
    const mname = String(LM.name).replace(/^Markt von /, ""), lines = capT[1].GetMarketAttractionInfo.split("\n");
    const tops = lines.map((l, i) => [i, l]).filter(([, l]) => l && !l.startsWith(" "));
    const k = tops.findIndex(([, l]) => l.startsWith(mname + ":"));
    if (k >= 0) anz = { ort: P.orte.find(o => String(o.id) === capT[0])?.name || "Hauptstadt", wert: tops[k][1].slice(mname.length + 1).trim(),
      platz: k + 1, von: tops.length, text: lines.slice(tops[k][0] + 1, tops[k + 1]?.[0] ?? lines.length)
        .filter(l => !l.includes(":BREAKDOWN_TAG") && l.trim() !== "Derzeitige Marktanziehung").map(l => l.slice(2)).join("\n") };
  }
  const nOrte = sum((m.mitglieder || []).map(x => x.orte));
  // fehlende Güter der eigenen Orte und Gebäude in diesem Markt (Nutzerwunsch 29.09.: in der Marktkachel), Warnung nur bei Engpass
  const B = inM.length ? gueterBilanz(P, m) : null;
  // knappe Güter in diesem Markt (istKnapp: Nachfrage > Angebot × 1,05 und Preis steigt); Trend nur im Heimatmarkt (je Spielstand)
  const knapp = (m.gueter || []).filter(istKnapp).sort((a, b) => (b.nachfrage - b.angebot) - (a.nachfrage - a.angebot));
  const kSer = m.heimat !== false && m.id === P.A.markt?.id ? d.punkte.map(p => p.knapp).filter(num) : [];
  // Monatswerte des Mods je Markt (history.markt_verlauf: Orte, Bevölkerung, Nahrung, unser Handelsvorteil im Heimatmarkt)
  // und Werte je Spielstand (punkte.marktwert/produktionswert)
  const MV = (d.markt_verlauf || {})[String(m.id)] || {};
  const ser = k => (MV[k] || []).filter(num);
  // Marktwert wie im Marktfenster: „Waren im Wert von … gehandelt“ = Σ Preis × Nachfrage (Spielstand; geprüft 1.2.1342: 800,03
  // zu 799,98 im Spiel). Der Mod-Wert GetTotalValueTraded (587,7) weicht ab und wird nicht genutzt.
  const mw = sum((m.gueter || []).map(x => (x.preis ?? 0) * (x.nachfrage ?? 0)));
  const pw = sum((m.gueter || []).map(x => (x.preis ?? 0) * sum(Object.values(x.produktion || {}))));
  const mwSer = d.punkte.map(p => p.marktwert?.[m.id]).filter(num), pwSer = d.punkte.map(p => p.produktionswert?.[m.id]).filter(num);
  // Markt gewachsen/geschrumpft (Orte je Monat, letzte 12 Monate) – erklärt einen fallenden Anteil (Nutzerwunsch 30.09.)
  let wachs = "";
  const oS = MV.orte || [], mon = MV.monate || [];
  for (let i = oS.length - 1; i > 0 && i >= oS.length - 12; i--) {
    if (num(oS[i]) && num(oS[i - 1]) && oS[i] !== oS[i - 1]) {
      const [jj, mm] = String(mon[i]).split(".");
      wachs = `Markt ${fmt(oS[i - 1], 0)} → ${fmt(oS[i], 0)} Orte seit 1.${mm}.${jj}`;
      break;
    }
  }
  // Handelsvorteil wie im Tooltip des Spiels (Screenshot 30.09.: 19,09 = „Im Besitz Orte“ 8,91 + „Marinepräsenz“ 10,15 + „Gebäude
  // in fremdländischen Orten“ 0,00). Orte = Σ Orts-Modifikator local_merchant_power × (1 + global_merchant_power) = 7,45 × 1,196 =
  // 8,91 (live 1343.1, genau). Marinepräsenz ≈ Σ Seepräsenz (Spielstand) × merchant_power_from_maritime: 201,0 × 0,05 = 10,05 bei
  // 5 Monate älterem Spielstand; welche Seezonen zu welchem Markt zählen, zeigt das Spiel nicht -> nur im Heimatmarkt gerechnet.
  const LMOD = Object.values(d.alles?.werte?.landmod || {})[0] || {};
  const heimat = m.id === P.A.markt?.id;
  // live nur im Heimatmarkt (Mod-Zeile „preise“). Test 0.17 (02.10.): Market.GetMerchantPower mit gespeichertem Land lieferte
  // überall 0 (auch Brügge, richtig ≈ 17) – nicht anzeigen; 0.17.1 prüft andere Schreibweisen (marktvorteil hv_a/hv_b)
  const hvFremd = (d.reichweite || []).find(x => x.id === m.id)?.handelsvorteil;     // Mod ab 0.18 (Märkte in Reichweite)
  const hvLive = heimat ? ser("wir").at(-1) : num(hvFremd) && hvFremd > 0 ? hvFremd : null;
  const hvGes = hvLive ?? own?.macht;
  const ortMP = sum(access.map(x => x.om.local_merchant_power)), globMP = LMOD.global_merchant_power ?? 0;
  const hvOrte = ortMP * (1 + globMP);
  const see = P.A.seepraesenz || [], seeSum = sum(see.map(x => x.macht));
  const hvSee = heimat && see.length && num(LMOD.merchant_power_from_maritime) ? seeSum * LMOD.merchant_power_from_maritime : null;
  const food = LM.market_food ?? m.nahrung, fmax = LM.market_max_food, fsal = LM.market_monthly_food_balance;
  const unsereBev = inM.length ? sum(inM.map(o => o.bev)) : null;
  // fremder Markt: Preisvergleich zum Heimatmarkt (Güter mit Angebot in beiden Märkten; ohne Handelskosten; Nutzerwunsch 30.09.)
  const H = P.A.markt, liste = xs => xs.map(x => `${esc(gn[x.gut] || x.gut)} <i class="${x.r < 0 ? "pos" : "neg"}">${sgn(x.r * 100, 0)} %</i>`).join(" · ") || "–";
  let vergleich = null;
  if (H && H.id !== m.id) {
    const hp = Object.fromEntries((H.gueter || []).filter(x => (x.angebot ?? 0) > 0 && x.preis > 0).map(x => [x.gut, x.preis]));
    const rel = (m.gueter || []).filter(x => (x.angebot ?? 0) > 0 && x.preis > 0 && hp[x.gut]).map(x => ({ gut: x.gut, r: x.preis / hp[x.gut] - 1 }));
    const tt = `Preis in ${m.zentrum} ÷ Preis in ${H.zentrum} − 1 (Spielstand), nur Güter mit Angebot in beiden Märkten; ohne Handelskosten`;
    vergleich = { stack: [
      { l: `hier günstiger als in ${H.zentrum}`, v: liste(rel.filter(x => x.r < 0).sort((a, b) => a.r - b.r).slice(0, 3)), cls: "wort", title: tt, mw: 330 },
      { l: `hier teurer als in ${H.zentrum}`, v: liste(rel.filter(x => x.r > 0).sort((a, b) => b.r - a.r).slice(0, 3)), cls: "wort", title: tt, mw: 330 }], neben: true };
  }
  const head = hd({
    // Reihe 1 groß (Nutzerwunsch 30.09.): Handelsvorteil (wie im Marktfenster: Wert und Rang), Marktwert, Produktionswert,
    // Bevölkerung, Nahrungsvorrat – je mit Verlauf; bei fremden Märkten dazu der Preisvergleich zum Heimatmarkt
    big: [{ l: "Handelsvorteil", v: num(hvLive) ? fmt(hvLive, 2) : own ? fmt(own.macht, 2) : "keiner", t: own ? `<i>Platz ${ownIdx + 1} von ${h.length}</i>` : "",
            u: [own && tot ? `Anteil ${pct(own.macht / tot, 1)}` : "", wachs].filter(Boolean).join("<br>"),
            s: spark(ser("wir"), { color: "--c6" }),
            title: `wie im Spiel (Tooltip über dem Rang in Wirtschaft → Märkte); Wert ${num(hvLive) ? "live (Daten-Mod)" : "Spielstand"}, Rang und Anteil aus dem Spielstand ${d.meta.datum} (Anteil = unser Handelsvorteil ÷ Summe aller Händler, das Spiel zeigt keinen Anteil); Linie = je Monat (Daten-Mod, nur Heimatmarkt)` },
          { l: "Marktwert", v: fmt(mw, 2), t: trend(vorm(mwSer), 1, 1), s: spark(mwSer, { color: "--c7" }),
            title: "wie im Marktfenster: Wert der Waren, die letzten Monat auf dem Markt gehandelt wurden = Σ Preis × Nachfrage (Spielstand); Trend und Linie je Spielstand" },
          { l: "Produktionswert", v: fmt(pw, 2), t: trend(vorm(pwSer), 1, 1), s: spark(pwSer, { color: "--c1" }),
            title: "Σ Preis × Produktion aller Güter im Markt (Spielstand); das Spiel zeigt dafür keinen Gesamtwert; Trend und Linie je Spielstand" },
          { l: "Bevölkerung (Tsd.)", v: fmt(m.bevoelkerung ?? ser("bev").at(-1), 1), t: trend(vorm(ser("bev")), 1, 0), s: spark(ser("bev"), { color: "--c4" }),
            u: num(unsereBev) ? `davon unsere ${fmt(unsereBev, 1)}` : "", title: "alle Orte des Markts (Spielstand = Daten-Mod); Linie = je Monat" },
          num(food) && { l: "Nahrungsvorrat", v: `${fmt(food, 0)}${num(fmax) ? ` <i>/ ${fmt(fmax, 0)}</i>` : ""}`, bar: num(fmax) && fmax ? food / fmax : null,
            u: num(fsal) ? `<span class="${posneg(fsal)}">${sgn(fsal, 1)} / Monat</span>` : "", s: spark(ser("nahrung"), { color: "--c3" }),
            title: "wie im Marktfenster: Nahrungsbestand / Maximum (Saldo im Monat); Linie = Bestand je Monat (Daten-Mod)" },
          vergleich],
    // Reihe 2: eigene Orte, stärkster Händler, Handelskapazität, Marktzugriff, knappe und fehlende Güter
    small: [{ l: "eigene Orte", v: `${m.eigene_orte ?? inM.length} <i>von ${nOrte || "–"}</i>` },
            h[0] && h[0] !== own && { l: "stärkster Händler", v: `${esc(h[0].land)} ${fmt(h[0].macht, 2)} <i>${pct(h[0].macht / tot, 0)}</i>` },
            own && own.kapazitaet > 0 && { l: "Handelskapazität", v: `${fmt(own.kapazitaet, 2)} <i>${fmt(own.kapazitaet - (own.genutzt ?? 0), 2)} frei</i>`,
              bar: (own.genutzt ?? 0) / own.kapazitaet, title: "wie im Marktfenster (frei / gesamt); Balken = genutzt" },
            // Marktzugriff und Anziehung untereinander (eine Spalte, damit der aufgeklappte Kopf in einer Reihe bleibt)
            (access.length || anz) && { stack: [
              access.length && { l: "schlechtester Marktzugriff", v: `${esc(access[0].name)} ${pct(access[0].z, 0)}` },
              anz && { l: `Anziehung auf ${anz.ort}`, v: `${esc(anz.wert.replace(".", ","))} <i>Platz ${anz.platz} von ${anz.von}</i>`,
                title: `Marktanziehung dieses Markts auf unsere Hauptstadt laut Spiel (Marktzugriff + Marktanziehung + Verträge …); Platz unter allen ${anz.von} Märkten der Liste. Laut Spiel = Zugkraft des Marktzentrums, den Ort zum Teil des eigenen Markts zu machen` }] },
            (m.gueter || []).length && { l: `knappe Güter – ${knapp.length}`, cls: knapp.length ? "neg" : "", t: trend(vorm(kSer), 0, -1), mw: 230,
              v: knapp.length ? knapp.slice(0, 5).map(x => `${esc(gn[x.gut] || x.name)} <i>${fmt(x.nachfrage, x.nachfrage < 1 ? 2 : 1)} / ${num(x.angebot) ? fmt(x.angebot, x.angebot < 1 ? 2 : 1) : "kein Angebot"}</i>`).join(" · ") + (knapp.length > 5 ? ` <i>+${knapp.length - 5}</i>` : "") : "keine",
              title: "Knapp = in diesem ganzen Markt ist die Nachfrage mehr als 5 % höher als das Angebot und der Preis steigt (Spielstand; Zahlen = Nachfrage / Angebot)" },
            B?.fehlend.length && { l: `fehlende Güter – ${B.fehlend.length}, musst du kaufen`, mw: 230,
              v: B.fehlend.slice(0, 3).map(k => `${esc(gn[k] || k)} <i class="neg">${fmt(B.saldo(k), 2)}</i>`).join(" · ") + (B.fehlend.length > 3 ? ` <i>+${B.fehlend.length - 3}</i>` : ""),
              title: "Eigener Saldo in diesem Markt negativ: Förderung deiner Orte + Herstellung deiner Gebäude − Verbrauch deiner Gebäude (Nennwerte, Gebäude ohne Arbeiter nicht gezählt; siehe Güterkachel)" }],
    warn: [(fsal ?? 0) < 0 && `Nahrung im Markt sinkt (${sgn(fsal, 1)}/M.)`,
           LM.HasStarvingProvinces === 1 && "Provinzen hungern", LM.HasRiskStarvingProvinces === 1 && "Provinzen droht Hunger",
           ...(B ? engpassWarn(B, gn, `im Markt ${esc(m.zentrum || "")}`) : [])],
  });
  // Nahrung als eine Karte (Nutzerwunsch 30.09.): Bestand, Saldo, darunter die Aufschlüsselungen des Spiels
  const T = d.alles?.texte?.markt?.[m.id] || {};
  const nahrung = num(food) ? `<div class="card"><h3>Nahrung im Markt ${esc(m.zentrum)}</h3>${kv([
      ["Bestand / Maximum", `${fmt(food, 0)} / ${fmt(fmax, 0)}${num(fmax) && fmax ? ` <span class="hint">${pct(food / fmax, 0)}</span>` : ""}`],
      ["Saldo / Monat", `<span class="${posneg(fsal)}">${sgn(fsal, 1)}</span>`]])}
      ${[["GetFoodProductionInfo", "Produktion"], ["GetFoodImportsInfo", "Einfuhr"], ["GetFoodExportsInfo", "Ausfuhr"], ["GetFoodPriceStepInfo", "Nahrungspreis"],
         ["GetRiskStarvingProvincesInfo", "Provinzen, denen Hunger droht"], ["GetStarvingProvincesInfo", "Hungernde Provinzen"]]
        .filter(([k]) => String(T[k] || "").trim())
        // eingeklappt: im großen Markt (Lübeck, 240 Orte) sind die Listen sehr lang; erste Zeile = Summe laut Spiel
        .map(([k, t]) => `<details class="more"><summary>${t} <span class="hint">${esc(String(T[k]).split("\n")[0].slice(0, 90))}</span></summary>${breakdown(T[k])}</details>`).join("")}
      <p class="hint">Daten-Mod ${esc(d.alles?.datum?.markt || "")}; Aufschlüsselungen wie im Spiel.</p></div>` : "";
  const eig = B ? B.eigen : new Set();
  const os2 = x => Math.trunc(ortssaldo(x) * 100) / 100;               // abgeschnitten wie im Spiel
  // Handelsvorteil und Marktzugriff in einer Karte (Nutzerwunsch 30.09.): Torte, unsere Orte mit Marktzugriff (Aufschlüsselung des
  // Spiels) und ihren Markt-Modifikatoren (live ortmod), darunter die Anziehung dieses Markts auf unsere Hauptstadt
  const ortTab = access.length ? `${table([
      { t: "Ort", l: true, f: x => esc(x.name) }, { t: "Marktzugriff", f: x => pct(x.z, 1) },
      { t: "Handelsvorteil", f: x => fmt(x.om.local_merchant_power, 2) }, { t: "Handelskapazität", f: x => fmt(x.om.local_merchant_capacity, 2) },
      { t: "Marktanziehung", f: x => num(x.om.local_trade_center_power) ? pct(x.om.local_trade_center_power, 1) : "–" },
      { t: "Aufschlüsselung", l: true, f: x => OT[x.id]?.GetMarketAccessBreakdown
          ? `<details><summary>Marktzugriff</summary>${breakdown(OT[x.id].GetMarketAccessBreakdown)}</details>` : "" }], access, { scroll: false })}
      <p class="hint">Je Ort laut Spiel (Daten-Mod ${esc(d.alles?.datum?.ort || "")}): Marktzugriff und die Modifikatoren des Ortes für Handelsvorteil,
      Handelskapazität und Marktanziehung.</p>` : "";
  const anzHtml = anz ? `<div class="sect" style="margin-top:10px">Anziehung auf ${esc(anz.ort)} – ${esc(anz.wert.replace(".", ","))}, Platz ${anz.platz} von ${anz.von} Märkten</div>
      ${breakdown(anz.text)}` : "";
  const hvKv = num(hvGes) ? `<div class="sect">Unser Handelsvorteil – wie im Tooltip des Spiels</div>${kv([
      ["Handelsvorteil", `<b>${fmt(hvGes, 2)}</b> <span class="hint">${num(hvLive) ? `live ${esc(MV.monate?.at(-1) || "")}` : `Spielstand ${esc(d.meta.datum)}`}</span>`],
      ["im Besitz Orte", `${fmt(hvOrte, 2)} <span class="hint">= Orte ${fmt(ortMP, 2)} × (1 + Handelsvorteil ${pct(globMP, 1)})</span>`],
      num(hvSee) ? ["Marinepräsenz", `${fmt(hvSee, 2)} <span class="hint">≈ Präsenz ${fmt(seeSum, 1)} in ${see.length} Seezonen × ${fmt(LMOD.merchant_power_from_maritime, 2)} (Spielstand ${esc(d.meta.datum)})</span>`]
                 : ["übrige", `${fmt(hvGes - hvOrte, 2)} <span class="hint">Marinepräsenz, Gebäude in fremdländischen Orten</span>`]])}
      ${num(hvSee) ? `<details class="more"><summary>Seezonen</summary>${table([{ t: "Seezone", l: true, f: x => esc(x.name || String(x.id)) },
        { t: "Präsenz", f: x => fmt(x.macht, 2) }], see.slice().sort((a, b) => b.macht - a.macht), { scroll: false })}</details>` : ""}
      <p class="hint">Orte = Orts-Modifikator Handelsvorteil (Marktzentrum +20, Marktplatz, Händlergilde …) laut Daten-Mod; Handelsvorteil
      in % = Land-Modifikator (Wirtschaft → Märkte). Nachgerechnet 30.09.: 7,45 × 1,196 = 8,91 wie im Spiel.</p>` : "";
  const vorteilKarte = `<div class="card"><h3>Handelsvorteil${access.length ? " und Marktzugriff" : ""} im Markt ${esc(m.zentrum)}</h3>
      <div class="mvz"><div>${pie}</div>${ortTab ? `<div>${ortTab}</div>` : ""}</div>${hvKv}${anzHtml}</div>`;
  // fremde Märkte: Aufstellung der Güter wie in der Güterkachel, bezogen auf diesen Markt (Nutzerwunsch 30.09.; der Heimatmarkt
  // steht in der Güterkachel). Produziert = Produktion im Markt, Mängel = Ortssaldo negativ („Größte örtliche Mängel“ im Spiel)
  let zehn = "";
  if (H && H.id !== m.id) {
    const GD = P.W.gueter || {}, alle = m.gueter || [];
    const prodM = x => sum(Object.values(x.produktion || {}));
    const prod = alle.filter(x => prodM(x) > 0).sort((a, b) => prodM(b) - prodM(a));
    const mangel = alle.filter(x => ortssaldo(x) < 0).sort((a, b) => ortssaldo(a) - ortssaldo(b));
    const verh = x => x.preis / GD[x.gut].default_market_price;
    const ang = alle.filter(x => (x.angebot ?? 0) > 0 && x.preis > 0 && GD[x.gut]?.default_market_price).sort((a, b) => verh(b) - verh(a));
    const top10 = (xs, v, c) => xs.length ? compo(xs.slice(0, 10).map(x => ({ l: gn[x.gut] || x.name, v: v(x), c })), null) : `<div class="empty">keine</div>`;
    zehn = `<div class="grid2">
      <div class="card"><h3>Produktion und Mängel im Markt ${esc(m.zentrum)}</h3>
        <div class="sect">am meisten produziert – ${Math.min(10, prod.length)} von ${prod.length}</div>${top10(prod, prodM, "--c3")}
        <div class="sect" style="margin-top:10px">größte Mängel – ${Math.min(10, mangel.length)} von ${mangel.length}</div>${top10(mangel, os2, "--c5")}
        <p class="hint">Produziert = Produktion aller Orte des Markts; Mängel = Ortssaldo negativ wie „Größte örtliche Mängel“ im Marktfenster (Spielstand ${esc(d.meta.datum)}).</p></div>
      <div class="card"><h3>Preise im Vergleich zum Grundpreis</h3>
        <div class="sect">günstigste – ${Math.min(10, ang.length)} von ${ang.length}</div>${top10(ang.slice().reverse(), verh, "--c3")}
        <div class="sect" style="margin-top:10px">teuerste – ${Math.min(10, ang.length)} von ${ang.length}</div>${top10(ang, verh, "--c5")}
        <p class="hint">Preis im Markt ${esc(m.zentrum)} ÷ Grundpreis (Spielstand), nur Güter mit Angebot.</p></div></div>`;
  }
  return { head, body: `<div class="grid2">
      ${vorteilKarte}
      <div class="card"><h3>Händler</h3>${table([{ t: "Land", l: true, f: x => `${esc(x.land)} <span class="hint">${esc(x.tag)}</span>` },
        { t: "Handelsvorteil", f: x => fmt(x.macht, 2) }, { t: "Anteil", f: x => pct(tot ? x.macht / tot : null, 1) },
        { t: "Kapazität", f: x => fmt(x.kapazitaet, 2) }, { t: "genutzt", f: x => fmt(x.genutzt, 2) }], h)}</div>
    </div>
    ${zehn}
    <div class="grid2">
      <div class="card"><h3>Wer im Markt sitzt (Mitgliedsorte je Land)</h3>${table([{ t: "Land", l: true, f: x => esc(x.land) },
        { t: "Orte", f: x => x.orte }, { t: "Entwicklung", f: x => fmt(x.entwicklung, 0) }, { t: "Steuer", f: x => fmt(x.steuer, 1) },
        { t: "Rohstoffe", l: true, f: x => Object.entries(x.rohstoffe).map(([k, v]) => `${esc(gn[k] || k)}${v > 1 ? " ×" + v : ""}`).join(", ") }], m.mitglieder || [])}
        <p class="hint">Annäherung für „wer produziert wieviel“: der Spielstand hat keine Produktion je Land und Markt, nur Orte mit Rohstoff je Besitzer.</p></div>
      ${nahrung}
    </div>
    <div class="card"><h3>Angebot nach Quelle und Verbrauch nach Abnehmer – Spielstand ${esc(d.meta.datum)}</h3>${table([
      { t: "Gut", l: true, f: x => `${esc(gn[x.gut] || x.name)}${eig.has(x.gut) ? ` <span class="hint">eigen</span>` : ""}` },
      { t: "Preis", f: x => `${fmt(x.preis, 2)}${trend(preisSchritt(x), 2, 0)}` },
      { t: "Angebot", f: x => fmt(x.angebot, 1) }, { t: "Nachfrage", f: x => fmt(x.nachfrage, 1) },
      { t: "Ortssaldo", f: x => sgn(os2(x), 2), cls: x => posneg(ortssaldo(x)) },
      { t: "Angebot aus", l: true, f: x => src(x.angebot_quellen) }, { t: "Verbrauch durch", l: true, f: x => src(x.verbrauch) },
      { t: "Produktion", l: true, f: x => src(x.produktion) }], goods)}
      <p class="hint">Ortssaldo wie im Marktfenster: Angebot aus Produktion − Verbrauch ohne Handel, also Überschuss oder Mangel der Orte des Markts.
      „eigen“ = deine Orte fördern oder deine Gebäude stellen her oder verbrauchen das Gut. Pfeil = letzte Preisänderung.</p></div>` };
}

// Diplomatie und Untertanen (Nutzerwunsch 01.10., Punkte 1–8). Begriffe wie im Spiel (Lokalisierung game_concept_…):
// Befreundet, Feindlich, Staatsehe, Kriegsgrund, Personalunion, Klienteltreue, Freiheitsdrang, Annektierung.
const BEZIEHUNG = { nachbar: "Nachbar", rivale: "Rivale", krieg: "Krieg", untertan: "Klientelland", oberherr: "Oberherr",
  freund: "Befreundet", feind: "Feindlich", kb_ziel: "Kriegsgrund gegen sie", kb_gegen_uns: "Kriegsgrund gegen uns",
  kriegsverbuendet: "Kriegsverbündeter",   // ab Mod 0.19
  koalition: "Koalition gegen uns", union: "Personalunion", heirat: "Staatsehe", grossmacht: "Großmacht",
  annektiert_uns: "annektiert uns", wir_annektieren: "wird annektiert", spion_bei_uns: "Spionagenetz bei uns", hist_rivale: "historischer Rivale" };
const MONAT = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
function diplomatie(d, P) {
  const dipAll = P.LD.diplomatie || [], unter = P.A.untertanen || [];
  if (!dipAll.length && !unter.length) return "";
  const AW = d.alles?.werte || {}, AT = d.alles?.texte || {};
  const L = Object.values(AW.land || {})[0] || {}, TD = (AT.dip || {})[d.meta.tag] || Object.values(AT.dip || {})[0] || {};
  const v = (x, k) => x[k] ?? x[k + "_a"] ?? x[k + "_b"];
  // eigenes Land raus: die Personalunion (every_union_partner) zählt uns selbst mit (Punkt 3)
  const dip = dipAll.filter(x => x.tag !== d.meta.tag);
  const bez = x => x.beziehungen.map(b => BEZIEHUNG[b] || b).join(", ");
  const liveU = Object.fromEntries((P.LD.untertan || []).map(u => [u.anderes, u]));
  const zl = (l, val, txt, code = "") => txt
    ? `<details class="bk"><summary${code ? ` title="Aufschlüsselung des Spiels: ${esc(code)}"` : ""}><span class="bl">${l}</span><span class="bv">${val}</span></summary><div class="bsub">${breakdown(txt)}</div></details>`
    : `<div class="bk"><span class="bl">${l}</span><span class="bv">${val}</span></div>`;

  // Diplomaten (Punkt 1): Bestand ist eine Kommazahl (1,6) und kann über dem Maximum liegen; Zuwachs laut Spieltext
  const dGain = String(TD.GetDiplomaticActionsInfo || "").match(/gewinnen\s*([-+]?[\d.]+)\s*Diplomaten/);
  const diplomaten = L.dip_GetNumOfDiplomats ?? L.num_of_diplomats, dMax = L.dip_GetMaxNumOfDiplomats;
  const capUsed = L.dip_GetUsedDiplomaticCapacity ?? L.used_diplomatic_capacity, capMax = L.dip_GetMaxCapacity ?? L.diplomatic_capacity_without_maintenance;

  // Annektierung (Punkt 2): Spielstand progress = Punkte; Kosten laut Tooltip des Spiels = 200 Grundkosten + je Ort
  // (Stadt 13,33 laut Screenshot des Nutzers 01.10.; ländlicher Ort 10 = ANNEX_COST_PER_LOCATION, nicht im Spiel geprüft).
  // Zeeland: 114,0 ÷ 213,33 = 53 %, Rest 99,3 ÷ 1,35 = 74 Monate -> März 1350 (Spiel: 1. März 1350). Genau ab Mod 0.16.
  const datumPlus = (mon, ab = d.meta.datum) => { const [y, m] = String(ab).split(".").map(Number), t = y * 12 + (m - 1) + mon;
    return `${MONAT[t % 12]} ${Math.floor(t / 12)}`; };
  const annex = u => { const a = u.angliederung; if (!a) return null;
    // Mod 0.16: Fortschritt in % und Kosten laut Spiel (Trigger annexation_progress/annexation_cost, Test 02.10.: Zeeland 61,08 %
    // von 213,33 - Kosten wie im Tooltip); Restzeit mit dem Fortschritt je Monat aus dem Spielstand (Punkte)
    const G = (AW.annex || {})[u.tag];
    if (num(G?.fortschritt) && num(G?.kosten) && G.kosten > 0) {
      const anteil = G.fortschritt / 100, punkte = anteil * G.kosten;
      const rest = a.monatlich > 0 ? Math.max(0, Math.ceil((G.kosten - punkte) / a.monatlich)) : null;
      return { ...a, fortschritt: punkte, kosten: G.kosten, anteil, rest, fertig: rest != null ? datumPlus(rest, d.alles?.datum?.annex || d.meta.datum) : null, spiel: true };
    }
    const F = (AW.fremd || {})[u.tag] || {}, n = F.num_locations ?? F.GetOwnedLocationCount, st = F.num_of_non_rural ?? 0;
    const kosten = num(n) ? 200 + st * 40 / 3 + Math.max(0, n - st) * 10 : null;
    const anteil = kosten ? a.fortschritt / kosten : null;
    const rest = kosten && a.monatlich > 0 ? Math.max(0, Math.ceil((kosten - a.fortschritt) / a.monatlich)) : null;
    return { ...a, kosten, anteil, rest, fertig: rest != null ? datumPlus(rest) : null, geschaetzt: num(n) && n > st }; };
  // Kosten an Diplomatiekapazität je Beziehung: „„ Zeeland“ ist „Lehnsgut“: +0.46“ (GetActiveRelationsList)
  const capJe = Object.fromEntries([...String(TD.GetActiveRelationsList || "").matchAll(/^„\s*([^“]+)“ ist „[^“]+“:\s*([-+]?[\d.]+)/gm)].map(m => [m[1].trim(), +m[2]]));
  const capTeile = [...String(TD.GetActiveRelationsList || "").matchAll(/^\S.*:\s*([-+]?[\d.]+)\s*$/gm)].map(m => +m[1]);
  const capMod = capUsed, capFenster = capTeile.length ? sum(capTeile) : null;
  const capZeigen = capFenster ?? capMod;
  const ruf = Object.values(AW.landmod || {})[0]?.diplomatic_reputation;

  // Kopf (Punkt 4)
  const rivals = dip.filter(x => x.beziehungen.includes("rivale")), wars = dip.filter(x => x.beziehungen.includes("krieg"));
  const union = dip.filter(x => x.beziehungen.includes("union")), kbZiel = dip.filter(x => x.beziehungen.includes("kb_ziel"));
  const kbUns = dip.filter(x => x.beziehungen.includes("kb_gegen_uns"));
  const ann = unter.map(u => ({ u, a: annex(u) })).filter(x => x.a);
  const antag = L.dip_GetNumberOfCountriesWithAntagonismTowardsUs, antagZ = L.dip_GetNumberOfCountriesWithTimedAntagonismTowardsUs;
  const head = hd({
    big: [{ l: "Rivalen (ihre Meinung von uns)", v: rivals.length ? rivals.map(x => `${esc(x.name)} <i>${fmt(v(x, "op_them"), 0)}</i>`).join(", ") : "keine", cls: "wort" },
          ann.length ? { l: "Annektierung", v: ann.map(({ u, a }) => `${esc(u.name)} ${num(a.anteil) ? pct(a.anteil, 0) : "–"}`).join(", "), cls: "wort",
                         u: ann.map(({ a }) => a.fertig ? `fertig ca. ${a.fertig} (${a.rest} Mon.)` : "").join(" · "), bar: ann.length === 1 ? ann[0].a.anteil : null,
                         title: "Annektierungsfortschritt = Punkte ÷ Kosten (200 + je Ort); fertig bei gleichbleibendem Fortschritt je Monat" }
                     : { l: "Klientelländer", v: unter.length ? unter.map(u => esc(u.name)).join(", ") : "keine", cls: "wort" },
          { l: "Diplomaten", v: `${fmt(diplomaten, 1)} <i>/ ${fmt(dMax, 1)}</i>`,
            u: dGain ? `${sgn(+dGain[1], 2)} je Monat${num(diplomaten) && num(dMax) && diplomaten >= dMax ? " (über dem Maximum)" : ""}` : "",
            title: "Diplomaten wie im Spiel (Kommazahl); laut Spiel kein Zuwachs, solange der Bestand am oder über dem Maximum liegt" },
          { l: "Diplomatiekapazität", v: `${fmt(capZeigen, 2)} <i>/ ${fmt(capMax, 2)}</i>`, bar: num(capZeigen) && capMax ? capZeigen / capMax : null,
            u: num(capFenster) && num(capMod) && Math.abs(capFenster - capMod) >= 0.005 ? `Mod ${fmt(capMod, 3)}` : "",
            title: "Wie im Diplomatiefenster: Summe der Kosten je Beziehung (GetActiveRelationsList); klein der abweichende Mod-Wert GetUsedDiplomaticCapacity" }],
    small: [num(ruf) && { l: "Diplomatieruf", v: sgn(ruf, 2) },
            { l: "Kriegsgegner", v: wars.length ? wars.map(x => esc(x.name)).join(", ") : "keine", cls: wars.length ? "neg" : "" },
            union.length && { l: "Personalunion", v: union.map(x => esc(x.name)).join(", ") },
            (kbZiel.length || kbUns.length) && { l: "Kriegsgründe", v: `${kbZiel.length ? `gegen ${kbZiel.map(x => esc(x.name)).join(", ")}` : ""}${kbZiel.length && kbUns.length ? " · " : ""}${kbUns.length ? `gegen uns: ${kbUns.map(x => esc(x.name)).join(", ")}` : ""}` },
            (num(antag) || num(antagZ)) && { l: "Antagonismus gegen uns", v: `${fmt(antag, 0)} <i>Länder · zeitweilig ${fmt(antagZ, 0)}</i>` }],
    warn: [wars.length && `Krieg mit ${wars.map(x => esc(x.name)).join(", ")}`, L.dip_IsOverCapacityLimit === 1 && "Diplomatiekapazität überschritten",
           ...unter.filter(u => (AW.fremd || {})[u.tag]?.dip_IsBeingAnnexedStalled === 1).map(u => `Annektierung von ${esc(u.name)} stockt`)],
  });

  // Klientelländer (Punkt 8): Annektierung in Prozent mit Restzeit, Kosten an Diplomatiekapazität, Steuergrundlage, Treue, Zahlung
  const untertanen = unter.length ? `<div class="card" style="grid-column:1/-1"><h3>Klientelländer</h3>${table([
    { t: "Land", f: u => `${esc(u.name)} <span class="hint">${esc(u.tag)}</span>` }, { t: "Art", l: true, f: u => esc(u.typ_name || u.typ || "–") },
    { t: "Annektierung", f: u => { const a = annex(u); return a && num(a.anteil) ? `${pct(a.anteil, 1)} <span class="hint">${fmt(a.fortschritt, 1)} / ${fmt(a.kosten, 2)}${a.spiel ? " laut Spiel" : " geschätzt"}</span>` : "–"; } },
    { t: "+ / Monat", f: u => u.angliederung ? fmt(u.angliederung.monatlich, 2) : "–" },
    { t: "fertig ca.", f: u => { const a = annex(u); return a?.fertig ? `${a.fertig} <span class="hint">${a.rest} Mon.</span>` : "–"; } },
    { t: "Diplomatiekapazität", f: u => fmt(capJe[u.name], 2) },
    { t: "Steuergrundlage", f: u => fmt((AW.fremd || {})[u.tag]?.country_tax_base, 2) },
    { t: "Klienteltreue (%)", f: u => fmt(liveU[u.tag]?.loyalitaet ?? (AW.fremd || {})[u.tag]?.subject_loyalty, 2) },
    // „Vasall bezahlt Suzerän“ (Spiel-Tooltip 01.10.): 2 % der Grundwirtschaft, für uns eine Einnahme; der Mod liefert den Wert
    // aus Sicht des Vasallen negativ (−0,089) -> Vorzeichen gedreht, abgerundet wie im Spiel (0.08)
    { t: "zahlt uns / Monat", f: u => { const z = liveU[u.tag]?.zahlt ?? (AW.fremd || {})[u.tag]?.dip_GetSubjectPays;
        return num(z) ? fmt(Math.floor(-z * 100 + 1e-6) / 100, 2) : "–"; }, cls: u => posneg(-(liveU[u.tag]?.zahlt ?? 0)) },
    { t: "Grundwirtschaft", f: u => fmt((AW.fremd || {})[u.tag]?.country_economical_base, 2) },
    { t: "Mannstärke (Anzahl)", f: u => { const m = (AW.fremd || {})[u.tag]?.max_manpower; return num(m) ? fmt(m * 1000, 0) : "–"; } },
    // Mod 0.16: Aufgebote wie im Fenster „Klientelländer verwalten“ (GetArmyLevyPotentialStrength, Spiel 710 / Mod 716 ein Jahr später)
    { t: "Aufgebote (Mann)", f: u => { const t = (AT.fremd || {})[u.tag] || {}, z = String(t.GetArmyLevyPotentialStrength || "").replace(/[^\d]/g, "");
        return z ? `<span title="${esc(t.GetPotentialArmyLevyPowerTooltip || "")}">${fmt(+z, 0)}</span>` : "–"; } },
    { t: "Freiheitsdrang", f: u => fmt((AW.fremd || {})[u.tag]?.liberty_desire ?? dip.find(x => x.tag === u.tag)?.liberty_desire, 0) }], unter)}
    <p class="hint">Annektierung seit ${esc(unter.find(u => u.angliederung)?.angliederung.seit || "–")}: Fortschritt und Kosten laut Spiel (Daten-Mod ab 0.16,
      annexation_progress/annexation_cost); ohne diese Werte geschätzt (Spielstand-Punkte ÷ 200 + je Ort, Stadt 13,33${ann.some(x => x.a.geschaetzt) ? ", ländlicher Ort 10" : ""}).
      „fertig ca.“ bei gleichbleibendem Fortschritt je Monat (Spielstand).</p></div>` : "";

  // Diplomatiekapazität (Punkt 7): genutzt / max mit Aufschlüsselung je Beziehung, Diplomaten, Antagonismus
  const kapazitaet = `<div class="card"><h3>Diplomatiekapazität und Diplomaten</h3><div class="brk">
    ${zl("Diplomatiekapazität genutzt / max.", `${fmt(capZeigen, 2)} / ${fmt(capMax, 2)}`, TD.GetActiveRelationsList, "GetActiveRelationsList")}
    ${num(ruf) ? zl("Diplomatieruf", sgn(ruf, 2), modDesc(d, "diplomatic_reputation"), "GetDescriptionFor('diplomatic_reputation')") : ""}
    ${modDesc(d, "diplomatic_capacity_modifier") ? zl("Diplomatiekapazität (Modifikator)", `${sgn((modWert(d, "diplomatic_capacity_modifier") ?? 0) * 100, 0)} %`,
      modDesc(d, "diplomatic_capacity_modifier"), "GetDescriptionFor('diplomatic_capacity_modifier')") : ""}
    ${num(L.dip_GetDiplomaticRange) ? zl("Diplomatiereichweite", fmt(L.dip_GetDiplomaticRange, 0)) : ""}
    ${zl("Diplomaten", `${fmt(diplomaten, 1)} / ${fmt(dMax, 1)}`, TD.GetDiplomaticActionsInfo, "GetDiplomaticActionsInfo")}
    ${num(L.num_relations_above_limit) ? zl("Beziehungen über dem Limit", fmt(L.num_relations_above_limit, 0)) : ""}
    ${num(L.power_projection) ? zl("Machtprojektion", fmt(L.power_projection, 1)) : ""}
    ${num(antagZ) ? zl("Länder mit zeitweiligem Antagonismus", fmt(antagZ, 0), TD.GetAllCountriesTimedAntagonismDescription, "GetAllCountriesTimedAntagonismDescription") : ""}
    ${num(L.num_possible_rivals) ? zl("Rivalen / möglich", `${fmt(L.num_rivals, 0)} / ${fmt(L.num_possible_rivals, 0)}`) : ""}</div></div>`;

  // Bündnisse und Organisationen (Punkt 6): Allianzstärke, Zusammenschlüsse mit Politiken und Wirkung (Spieltexte)
  const ios = Object.entries(AW.io || {});
  const io = ios.map(([id, w]) => { const t = (AT.io || {})[id] || {};
    const jahre = num(w.international_organization_lifetime_in_days) ? w.international_organization_lifetime_in_days / 365.25 : null;
    return `<h5>${esc(w.name || id)}</h5><div class="brk">
      ${zl("Mitglieder", fmt(w.GetMembersAmount ?? w.total_members, 0))}
      ${w.HasElectors === 1 ? zl("Kurfürsten", fmt(w.num_of_electors, 0)) : ""}
      ${num(jahre) ? zl("besteht seit", `${fmt(jahre, 0)} Jahren`) : ""}
      ${t.GetImplementedPolicies ? zl("Politiken", "", t.GetImplementedPolicies, "GetImplementedPolicies") : ""}
      ${t.GetAllMembersEffects ? zl("Wirkung für Mitglieder", "", t.GetAllMembersEffects, "GetAllMembersEffects") : ""}
      ${t.GetInternationalOrganizationEffects ? zl("Wirkung des Zusammenschlusses", "", t.GetInternationalOrganizationEffects, "GetInternationalOrganizationEffects") : ""}
      ${t.GetJoinWarsText ? zl("Kriegsbeitritt", "", t.GetJoinWarsText.replace(/:\d+ :\d+ /g, ""), "GetJoinWarsText") : ""}
      ${t.GetOtherEffects ? zl("Weiteres", "", t.GetOtherEffects, "GetOtherEffects") : ""}</div>`; }).join("");
  const buendnisse = `<div class="card"><h3>Bündnisse und Organisationen</h3><div class="brk">
    ${zl("Stärke Defensivallianz", fmt(L.defensive_alliance_strength ?? P.lv.alliance_defensive, 2))}
    ${num(L.offensive_alliance_strength) ? zl("Stärke Offensivallianz", fmt(L.offensive_alliance_strength, 2)) : ""}</div>${io}
    <p class="hint">Allianzstärke = Land mit allen, die es im Krieg unterstützen oder gerufen werden können (Spieldoku). Zusammenschlüsse aus dem Daten-Mod (io).</p></div>`;

  // Beziehungen (Punkt 5): Nachbarn und Beziehungen; Länder, die nur als ferne Großmacht auftauchen, aufklappbar
  const nurGross = x => x.beziehungen.every(b => b === "grossmacht");
  const rang = x => (AW.fremd || {})[x.tag]?.great_power_ranking;
  const cols = [
    { t: "Rang", f: x => fmt(rang(x), 0) },
    { t: "Land", f: x => `${esc(x.name)} <span class="hint">${esc(x.tag)}</span>` }, { t: "Beziehung", l: true, f: x => esc(bez(x)) },
    { t: "Meinung sie→wir", f: x => sgn(v(x, "op_them"), 2), cls: x => posneg(v(x, "op_them")) },
    { t: "wir→sie", f: x => sgn(v(x, "op_us"), 2), cls: x => posneg(v(x, "op_us")) },
    { t: "Vertrauen sie→wir", f: x => fmt(v(x, "trust_them"), 2) }, { t: "wir→sie", f: x => fmt(v(x, "trust_us"), 2) },
    { t: "Antagonismus", f: x => fmt(v(x, "antagonism"), 1) }, { t: "rel. Stärke", f: x => fmt(v(x, "rel_strength"), 2) },
    { t: "Entwicklung", f: x => fmt(x.development, 0) }, { t: "Stabilität", f: x => fmt(x.stability, 0) }];
  const nachRang = (a, b) => (rang(a) ?? 1e9) - (rang(b) ?? 1e9);
  const nah = dip.filter(x => !nurGross(x)).sort(nachRang), fern = dip.filter(nurGross).sort(nachRang);
  const beziehungen = dip.length ? `<div class="card" style="grid-column:1/-1"><h3>Nachbarn und Beziehungen – ${nah.length}</h3>${table(cols, nah)}
    ${fern.length ? lazy("dip:fern", `Ferne Großmächte – ${fern.length}`, () => table(cols, fern)) : ""}</div>` : "";

  return { head, body: `<div class="grid2">${untertanen}${kapazitaet}${buendnisse}${beziehungen}</div>` };
}

function handel(d, P) {
  const LD = P.LD, A = P.A, gn = (P.W.namen || {}).gueter || {}, lm = (A.wirtschaft || {}).letzter_monat || {}, lv = P.lv;
  const mName = { ...(A.markt_namen || {}), ...Object.fromEntries((LD.maerkte || []).map(m => [m.id, m.name])) };
  const kosten = Object.fromEntries((LD.handel_kosten || []).map(k => [k.id, k]));
  const tip = Object.fromEntries((LD.text || []).filter(t => String(t.schluessel).startsWith("handel_")).map(t => [t.schluessel.slice(7), t.text]));
  const tr = (LD.handel || []).slice().sort((a, b) => (b.profit ?? 0) - (a.profit ?? 0));
  const home = A.markt?.id;
  const richtung = x => x.nach === home ? "Einfuhr" : x.von === home ? "Ausfuhr" : "Durchhandel";
  const gew = sum(tr.map(x => x.profit)), kost = sum(tr.map(x => kosten[x.id]?.kosten));
  const estTrade = (A.staende || []).filter(e => (e.letzter_monat?.trade_income ?? 0) > 0)
    .map(e => ({ l: e.name, v: e.letzter_monat.trade_income, c: ESTATE_COLOR[e.stand] }));
  const ownH = (A.markt?.haendler || []).find(x => x.tag === d.meta.tag), totH = sum((A.markt?.haendler || []).map(x => x.macht));
  const pr = (LD.preise || []).find(p => p.id === home) || {};
  if (!tr.length && !estTrade.length && lm.monthly_trade_balance == null) return "";
  const lossR = tr.filter(x => (x.profit ?? 0) < 0).length;
  // 1.4: Zoll je Route (Trade.GetTariffValue, negativ = wir zahlen) mit Spieltext GetTariffInfo; Route aus einem Handelsauftrag
  // (IsFromTradeOrder). Zoll offenbar im Gewinn enthalten (Walachei 1337.7): Verkauf − Einkauf − Unterhalt trifft den Gewinn bei
  // Routen ohne Zoll auf ±7 %, bei Routen mit Zoll nur nach Abzug des Zolls (Gewinn 3,855: ohne Zoll 5,118, mit Zoll 4,103)
  const HW = d.alles?.werte?.handel || {}, HT = d.alles?.texte?.handel || {};
  const zoll = x => HW[x.id]?.GetTariffValue, zollSum = sum(tr.map(zoll).filter(num));
  const mitZoll = tr.some(x => num(zoll(x)) && zoll(x) !== 0), mitAuftrag = tr.some(x => HW[x.id]?.IsFromTradeOrder === 1);
  // Kopf: alle Werte groß in einer Reihe (Nutzerwunsch 29.09.), Verlauf wo es Monatswerte gibt, Balken für die Auslastung
  const tiSer = liveSeries(d, "trade_income"), rSer = liveSeries(d, "trades"), gSer = liveSeries(d, "handel_gewinn");
  const hwSer = d.punkte.map(p => p.handelswert).filter(num).slice(-24);
  const d1 = s => s.length > 1 ? s.at(-1) - s.at(-2) : null;
  const S = spielWerte(d);                                  // Handelseinnahmen wie im Wirtschaftsfenster (Gewinn × Modifikator)
  const head = hd({
    big: [S && num(S.handel)
          ? { l: "Handelseinkommen / Monat", v: fmt(S.handel, 2), cls: posneg(S.handel), u: `Spielstand ${fmt(lm.monthly_trade_balance, 2)}`,
              t: trend(S.handelVorm, 2, 1), s: spark(S.ser.handel, { color: "--c2" }),
              title: `wie im Wirtschaftsfenster: Gewinn der Routen × Modifikator Handelseinnahmen (Daten-Mod ${S.datum}); Trend zum Vormonat; Linie = Monate, in denen der Mod den Modifikator geliefert hat; klein: Spielstand` }
          : { l: "Handelseinkommen / Monat", v: fmt(lm.monthly_trade_balance ?? lv.trade_income, 2), cls: posneg(lm.monthly_trade_balance),
              t: trend(d1(tiSer), 2, 1), s: spark(tiSer, { color: "--c2" }), title: "Spielstand; Trend = Veränderung zum Vormonat; Linie = Handelseinkommen je Monat live" },
          // Reihenfolge (Nutzerwunsch 29.09.): Handelseinkommen, Handelswert, Gewinn der Routen, Händlerkapazität, Routen
          { l: "Handelswert", v: fmt(lm.monthly_trade_value, 1), t: trend(d1(hwSer), 1, 1), s: spark(hwSer, { color: "--c7" }),
            title: "Spielstand monthly_trade_value; Trend und Linie je Spielstand" },
          { l: "Gewinn der Routen", v: fmt(gew, 2), cls: posneg(gew), t: trend(d1(gSer), 2, 1), s: spark(gSer, { color: "--c3" }),
            title: "Summe trade_profit (= EconomyView.GetTradeBalance); Linie = je Monat live" },
          { l: "Händlerkapazität", v: `${fmt(lv.merchant_capacity, 1)}${ownH ? ` <i>${fmt(ownH.genutzt, 1)} genutzt</i>` : ""}`,
            bar: ownH && ownH.kapazitaet ? ownH.genutzt / ownH.kapazitaet : null, title: "Balken = genutzte Kapazität im Heimatmarkt (Spielstand)" },
          { l: "Routen", v: String(tr.length), t: trend(d1(rSer), 0, 1), s: spark(rSer, { color: "--c6" }), title: "Linie = Anzahl Handelsrouten je Monat live" }],
    small: [mitZoll && { l: "Zölle / Monat", v: sgn(zollSum, 2), cls: posneg(zollSum),
                         title: "Summe Trade.GetTariffValue aller Routen (ab 1.4); negativ = wir zahlen fremden Märkten Zoll; nachgerechnet im Gewinn schon enthalten" }],
    warn: [lossR && `${lossR} Route(n) mit Verlust`],
  });
  const routen = tr.length ? table([
    { t: "Gut", l: true, f: x => esc(gn[x.gut] || x.gut_name || x.gut) }, { t: "Richtung", f: x => richtung(x) },
    { t: "von", l: true, f: x => esc(mName[x.von] ?? x.von) }, { t: "nach", l: true, f: x => esc(mName[x.nach] ?? x.nach) },
    { t: "Menge", f: x => fmt(x.volume, 2) }, { t: "Einkauf", f: x => fmt(x.buy, 2) }, { t: "Verkauf", f: x => fmt(x.sell, 2) },
    { t: "Gewinn", f: x => fmt(x.profit, 2), cls: x => posneg(x.profit) },
    ...(Object.keys(kosten).length ? [{ t: "Kosten", f: x => fmt(kosten[x.id]?.kosten, 2) }] : []),   // „Gewinn (Spiel)“ = Gewinn, entfernt
    ...(mitZoll ? [{ t: "Zoll", f: x => num(zoll(x)) && zoll(x) !== 0 ? `<span class="${posneg(zoll(x))}" title="${esc(HT[x.id]?.GetTariffInfo || "")}">${fmt(zoll(x), 2)}</span>` : "–" }] : []),
    ...(mitAuftrag ? [{ t: "Bestellung", f: x => HW[x.id]?.IsFromTradeOrder === 1 ? "ja" : "" }] : []),
    { t: "Auslastung", f: x => pct(x.capacity_usage, 0) },
    ...(Object.keys(tip).length ? [{ t: "Aufschlüsselung", l: true, f: x => tip[x.id] ? `<details><summary>zeigen</summary><pre class="raw">${rawText(tip[x.id])}</pre></details>` : "" }] : [])],
    tr) : `<div class="empty">keine Routen im letzten Monat</div>`;
  const lmTrade = [{ l: "Land (Handelssaldo)", v: lm.monthly_trade_balance, c: "--c5" }, ...estTrade].filter(r => typeof r.v === "number");
  // Anteil der Staatskasse laut Spiel-Oberfläche: Gewinn der Routen × Modifikator trade_income
  // (market_tooltips.gui: Multiply(Merchant.GetTotalTradeProfit, GetModifier('trade_income'))). Holland 1341.7: 5,677 × 0,304 = 1,73 =
  // Einkommens-Tooltip „Handelseinnahmen +1,72“; 0,304 = Grundwert 0,1 (auto_modifiers/country.txt) + Kronmacht 0,204 × 1,0
  // (estates/00_default.txt, crown_estate power trade_income = 1.0). Geprüft 29.09.
  const tiMod = (Object.values(d.alles?.werte?.landmod || {})[0] || {}).trade_income, crownP = lv.power_crown_estate;
  const kasse = num(tiMod) ? gew * tiMod : null;
  // Handelsverbindungen laut Spiel (Einnahmen der Staatskasse je Route) als eigene Karte neben „Wer am Handel verdient“
  // und „Händler im Heimatmarkt“ (Nutzerwunsch 29.09.)
  const verb = (Object.values(d.alles?.texte?.land || {})[0] || {}).GetTradeConnectionsTooltip;
  const verbCard = verb ? `<div class="card"><h3>Handelsverbindungen</h3>${breakdown(verb)}
      <p class="hint">Einnahmen der Staatskasse je Route laut Spiel (Daten-Mod ${esc(d.alles?.datum?.land || "")}), = Gewinn der Route × Modifikator Handelseinnahmen.</p></div>` : "";
  return { head, body: `<div class="card"><h3>Handelsrouten – live ${esc(LD.extra_datum || "")}</h3>${routen}
      <p class="hint">Einkauf/Verkauf = Wert je Route (trade_buy/trade_sell), Gewinn = trade_profit. Summe der Gewinne ${fmt(gew, 2)}${kost ? `, Kosten ${fmt(kost, 2)}` : ""}.${mitZoll
        ? ` Zoll (ab 1.4) = Trade.GetTariffValue, negativ = wir zahlen; nachgerechnet ist er im Gewinn schon enthalten (Verkauf − Einkauf − Unterhalt passt nur mit Zoll). Text des Spiels beim Zeigen auf den Wert.` : ""}${mitAuftrag
        ? " Bestellung = Route aus einer Handelsbestellung (Spiel: „Dieser Handel wird durch eine Handelsbestellung geschaffen“), sonst Automatisierung." : ""}</p></div>
    ${handelZollKarte(d)}
    <div class="${verbCard ? "grid3" : "grid2"}">
      <div class="card"><h3>Wer am Handel verdient</h3>
        ${num(kasse) ? `<div class="sect">Anteil der Staatskasse laut Spiel (live)</div>${kv([["Gewinn der Routen", fmt(gew, 2)],
          ["× Handelseinnahmen-Modifikator", `${pct(tiMod, 1)}${num(crownP) ? ` <span class="hint">(Kronmacht ${pct(crownP, 1)} + übrige ${pct(tiMod - crownP, 1)})</span>` : ""}`],
          ["= Handelseinkommen der Staatskasse", `<b>${fmt(kasse, 2)}</b>`]])}` : ""}
        <div class="sect">Vormonat laut Spielstand</div>${compo(lmTrade, sum(lmTrade.map(r => r.v)))}
        <p class="hint">Laut Spiel wird das Handelseinkommen nach Standesmacht zwischen Krone und Ständen geteilt; nur der Kronanteil geht in die Staatskasse.
        Die Oberfläche rechnet dafür Gewinn × Modifikator „Handelseinnahmen“ (Grundwert 10 % + Kronmacht × 1,0); so zeigt es auch das Wirtschaftsfenster.
        Der Spielstand führt für das Land ${fmt(lm.monthly_trade_balance, 2)}${num(kasse) ? ` (${sgn(lm.monthly_trade_balance - kasse, 2)} gegenüber der Rechnung)` : ""} – diesen Wert zeigt das Spiel nirgends.
        Die Stände-Werte zeigt das Spiel so im Stände-Tooltip („Handel“); woraus sie entstehen, zeigt es nicht – sie sind höher als ihr Machtanteil am Gewinn der Routen.</p></div>
      <div class="card"><h3>Händler im Heimatmarkt ${esc(A.markt?.zentrum || "")}</h3>${kv([
        ["unsere Marktmacht", ownH ? `${fmt(ownH.macht, 1)} (${pct(ownH.macht / totH, 1)})` : "–"],
        ["Kapazität / genutzt", ownH ? `${fmt(ownH.kapazitaet, 1)} / ${fmt(ownH.genutzt, 1)}` : "–"],
        ["Händlermacht live / gesamt", `${fmt(pr.merchant_power, 1)} / ${fmt(pr.merchant_power_total, 1)}`],
        ["Märkte mit eigenen Händlern", fmt(lv.markets_with_merchants, 0)], ["Handelsrouten (Zähler)", fmt(lv.trades, 0)],
        ["Handelseffizienz See / Land", `${sgn(((P.LD.modifikatoren || [])[0] || {}).trade_sea_efficiency, 2)} / ${sgn(((P.LD.modifikatoren || [])[0] || {}).trade_land_efficiency, 2)}`],
        ["Verkaufseffizienz", sgn(((P.LD.modifikatoren || [])[0] || {}).selling_efficiency, 3)]])}</div>
      ${verbCard}
      ${handelModKarte(d)}
    </div>` };
}

// Handelsbestellungen und Zölle (Nutzerwunsch 27.10., Patch 1.4) – Server eu5ratgeber/handel.py (d.handel_zoelle). Im deutschen
// Spiel heißen Handelsaufträge „Handelsbestellungen“ (game_concept_trade_order), das Zollfenster „Handelsrichtlinien“.
// Live (Daten-Mod): Zoll je Route (Trade.GetTariffValue, negativ = wir zahlen; Spieltext GetTariffInfo mit Land, Satz, Gut),
// Herkunft wie in der Handelsübersicht (Zahnrad = IsFromTradeOrder, Automatik, Schloss = IsLocked ohne Bestellung), Höchstsätze
// (landmod max_tariff/max_trade_subventions, Aufschlüsselung ab Mod 0.24.1). Spielstand (Format 15): Zollsätze je Gut, Zoll-
// einnahmen von Land und Ständen, Marktbesitzer, Meinungsabzug durch Ausfuhrzölle, Handelsbestellungen roh.
const ZOLL_ORDNER = { advances: "Fortschritt", laws: "Gesetz", government_reforms: "Reform", societal_values: "Gesellschaftswert",
  auto_modifiers: "Grundwert", static_modifiers: "Modifikator", subject_types: "Klientelland-Art", estate_privileges: "Privileg",
  estates: "Stand", parliament_issues: "Parlamentsthema" };
const ZOLL_SATZ = { goods_export_tariffs: "Ausfuhrzoll" };          // weitere Satz-Felder (Einfuhr) zeigt die Karte unter ihrem Feldnamen
function handelZollKarte(d) {
  const H = d.handel_zoelle;
  // nur mit Daten aus 1.4 (1.3 hatte keine Zölle); 1.3-Spielstände zeigen allein ihre Handelsaufträge (Prüfer 27.10.)
  if (!H || (!H.ab14 && !(H.spielstand?.bestellungen_13 || []).length)) return "";
  const S = H.spielstand || {}, M = H.modifikatoren || {}, gn = ((d.wissen || {}).namen || {}).gueter || {};
  const ent = s => String(s ?? "").replace(/&amp;/g, "&");
  const gut = g => esc(gn[g] || g);
  const hn = H.herkunft_namen || {};
  // 1 Zölle auf unseren Routen (live)
  const anteil = num(H.gewinn_vor_zoll) && H.gewinn_vor_zoll > 0 ? (H.zoll < 0 ? -H.zoll / H.gewinn_vor_zoll : 0) : null;   // nie „-0,0 %“
  const saetze = g => [...new Set((g.eintraege || []).map(e =>
    `${e.richtung === "ausfuhr" ? "Ausfuhr" : "Einfuhr"}${e.art === "zoll" ? "zoll" : "-Subvention"} ${pct(e.satz, 0)}: ${esc(e.gut)}`))].join("; ");
  const zoelle = `<div class="card"><h3>Zölle auf unseren Routen – live ${esc(H.datum || "")}</h3>${kv([
      ["Zölle / Monat", `<span class="${posneg(H.zoll)}">${sgn(H.zoll, 2)}</span>`],
      ["Gewinn der Routen (nach Zoll)", fmt(H.gewinn, 2)], ["Gewinn vor Zoll", fmt(H.gewinn_vor_zoll, 2)],
      ["Anteil der Zölle am Gewinn vor Zoll", pct(anteil, 1)]])}
    ${(H.je_land || []).length ? table([
      { t: "Land", l: true, f: g => esc(g.land) }, { t: "Routen", f: g => String(g.routen) },
      { t: "Gold / Monat", f: g => sgn(g.betrag, 2), cls: g => posneg(g.betrag) },
      { t: "Satz laut Spieltext", l: true, f: g => saetze(g) || `<span class="hint">${esc(g.quelle)}</span>` },
      { t: "Meinung", f: g => num(g.meinung) ? sgn(g.meinung, 2) : "–" }], H.je_land, { scroll: false })
      : `<div class="empty">keine Zölle auf unseren Routen</div>`}
    <p class="hint">Zölle / Monat = Σ Trade.GetTariffValue (negativ = wir zahlen); im Gewinn der Route schon abgezogen (nachgerechnet).
      Je Land: Werte aus dem Text des Spiels je Route („… verlangt einen 20% Zoll auf Ausfuhren von: …“, 2 Stellen). Einen Ausfuhrzoll
      erhebt der Besitzer des Ausgangsmarkts, einen Einfuhrzoll der des Zielmarkts (Spielbegriffe). Meinung = Feld
      export_tariff_opinion_penalty im Spielstand ${esc(S.datum || "")}; laut Spiel „verabscheuen“ Zielländer Ausfuhrzölle.</p></div>`;
  // 2 Handelsbestellungen: Herkunft der Routen (live) und Bestellungen im Spielstand
  const hk = Object.entries(H.herkunft || {});
  const hb = S.handelsbestellungen, mind = H.mindestgewinn, unter = new Set(H.unter_mindest || []), b13 = S.bestellungen_13 || [];
  const unterR = (H.routen || []).filter(x => unter.has(x.id));
  const feld = v => v !== null && typeof v === "object" ? `<code>${esc(JSON.stringify(v))}</code>` : esc(v);
  const roh = e => Object.entries(e).filter(([k]) => k !== "id" && k !== "zuordnung").map(([k, v]) => `${esc(k)} = ${feld(v)}`).join("<br>");
  const bestellungen = `<div class="card"><h3>Handelsbestellungen</h3>
    ${hk.length && H.ab14 ? `<div class="sect">Herkunft unserer Routen – live ${esc(H.datum || "")}</div>${table([
      { t: "Herkunft", l: true, f: ([k]) => esc(hn[k] || k) }, { t: "Routen", f: ([, v]) => String(v.routen) },
      { t: "Händlerkapazität", f: ([, v]) => fmt(v.kapazitaet, 2) }, { t: "Gewinn", f: ([, v]) => fmt(v.gewinn, 2), cls: ([, v]) => posneg(v.gewinn) },
      { t: "Gewinn je Kapazität", f: ([, v]) => v.kapazitaet ? fmt(v.gewinn / v.kapazitaet, 2) : "–" },
      { t: "Zoll", f: ([, v]) => v.zoll ? sgn(v.zoll, 2) : "–", cls: ([, v]) => posneg(v.zoll) }], hk, { scroll: false })}` : ""}
    ${num(mind) ? `<p class="hint">Standard-Mindestgewinn einer Handelsbestellung: ${fmt(mind, 2)} je Händlerkapazität (Define
      DEFAULT_TRADE_ORDER_MIN_PROFIT). ${unterR.length ? `Darunter liegen ${unterR.length} Route(n): ${unterR.map(x =>
        `${esc(x.gut_name || x.gut)} ${fmt(x.je_kap, 2)}`).join(", ")}.` : "Keine unserer Routen liegt darunter."}</p>` : ""}
    <div class="sect">Handelsbestellungen im Spielstand ${esc(S.datum || "")}</div>
    ${hb == null ? (b13.length ? `${table([{ t: "Markt", l: true, f: e => esc(e.markt_name || e.market) },
          { t: "Gut", l: true, f: e => esc(e.gut_name || e.goods || "–") }, { t: "Richtung", f: e => e.trade_order_is_import === "yes" ? "Einfuhr" : "Ausfuhr" },
          { t: "Kapazität", f: e => fmt(e.trade_order_capacity, 2) }], b13, { scroll: false })}
          <p class="hint">Handelsaufträge eines Spielstands vor 1.4 (am Land: trade_orders mit market, goods, trade_order_is_import,
            trade_order_capacity).</p>` : `<div class="empty">Spielstand ohne Handelsbestellungen (vor 1.4 oder nicht eingelesen)</div>`)
      : (S.bestellungen || []).length ? `${table([{ t: "Nr.", f: e => esc(e.id) }, { t: "Markt", l: true, f: e => esc(e.markt_name || e.markt) },
          { t: "Güter", l: true, f: e => e.gueter.map(g => `${esc(g.gut_name || g.gut)} <span class="hint">${g.richtung === "einfuhr" ? "Einfuhr" : "Ausfuhr"}</span>`).join(", ") || "–" },
          { t: "Kapazität", f: e => num(e.kapazitaet) ? (e.anteil ? `${fmt(e.kapazitaet, 0)} %` : fmt(e.kapazitaet, 2)) : "–" },
          { t: "Mindestgewinn", f: e => num(e.mindestgewinn) ? fmt(e.mindestgewinn, 2) : "–" },
          { t: "Routen", f: e => String(e.routen) },
          { t: "Gewinn (live)", f: e => num(e.gewinn) ? fmt(e.gewinn, 2) : "–", cls: e => posneg(e.gewinn) },
          { t: "Kapazität genutzt", f: e => num(e.kap_genutzt) ? fmt(e.kap_genutzt, 2) : "–" },
          { t: "Zoll", f: e => num(e.zoll) && e.zoll ? sgn(e.zoll, 2) : "–", cls: e => posneg(e.zoll) },
          { t: "gehandelt", l: true, f: e => esc((e.gueter_routen || []).join(", ")) || "–" }], S.bestellungen, { scroll: false })}
          <p class="hint">Spielstand: trade_order_manager, unserem Land über trade_order_refs zugeordnet. Kapazität in % = Anteil
            (trade_order_is_percentage); Mindestgewinn je Händlerkapazität, wenn eingeschaltet. Routen = Routen mit trade_order_ref im
            Spielstand; Gewinn, genutzte Kapazität und Zoll live (Daten-Mod) über dieselbe Routen-Nummer.</p>`
      : `<div class="empty">keine Handelsbestellungen im Spielstand${hb.anzahl_gesamt ? ` (${hb.anzahl_gesamt} anderer Länder)` : ""}</div>`}
    ${pruefKarte(d, H)}
    ${hb && hb.beispiel ? `<details><summary>Eintrag eines anderen Landes (Format noch unbelegt)</summary><div class="hint">${roh(hb.beispiel)}</div></details>` : ""}
    ${hb && hb.roh ? `<details><summary>Rohtext des Spielstands</summary><pre class="raw">${rawText(hb.roh)}</pre></details>` : ""}
    <p class="hint">Herkunft wie in der Handelsübersicht des Spiels: Handelsbestellung (IsFromTradeOrder), Automatisierung (weder
      Bestellung noch gesperrt), geschützt (durch Vereinbarung, IsLocked). Eine Bestellung verteilt Händlerkapazität nach Priorität;
      was übrig bleibt, nutzt die Automatisierung (Spieltexte TRADE_ORDER_PRIORITY_INFO, TRADE_ORDER_CAPACITY_TOTAL).</p></div>`;
  // 3 Unsere Zölle (Spielstand): Sätze, Einnahmen, Automatisierung, Besitzer des Heimatmarkts
  const st = Object.entries(S.zolleinnahmen_staende || {}), stSum = sum(st.map(([, v]) => v));
  const stName = Object.fromEntries(((d.aktuell || {}).staende || []).map(e => [e.stand, e.name]));
  const satzFelder = Object.entries(S.saetze || {});
  const gueter = [...new Set(satzFelder.flatMap(([, v]) => Object.keys(v || {})))].sort((a, b) => String(gn[a] || a).localeCompare(String(gn[b] || b)));
  const fremd = Object.entries(S.heimatmarkt_besitzer_saetze || {});
  const unsere = `<div class="card"><h3>Unsere Zölle – Spielstand ${esc(S.datum || "")}</h3>
    ${(S.eigene_maerkte || []).length ? `<p>Märkte in unserem Besitz: ${S.eigene_maerkte.map(m => esc(m.name || m.id)).join(", ")}</p>`
      : `<p class="hint">Wir besitzen keinen Markt – Zölle legt nur der Marktbesitzer fest (Spiel: „Wir können Zölle nur auf Märkten
        verhandeln, in denen wir auch Marktbesitzer sind.“).${S.heimatmarkt_besitzer_name ? ` Heimatmarkt ${esc(S.heimatmarkt_name || "")}:
        Besitzer ${esc(S.heimatmarkt_besitzer_name)}.` : ""}</p>`}
    ${kv([["Zölle des Landes, Vormonat", num(S.zolleinnahmen_land) ? fmt(S.zolleinnahmen_land, 2) : "–"],
          ["Anteil der Zölle für die Stände", st.length ? `${fmt(stSum, 2)} <span class="hint">(${st.map(([k, v]) => `${esc(stName[k] || k)} ${fmt(v, 2)}`).join(", ")})</span>` : "–"],
          ["Summe", num(S.zolleinnahmen_land) || st.length ? fmt((S.zolleinnahmen_land || 0) + stSum, 2) : "–"],
          num(S.buerger_feld) && ["Feld last_months_burgher_tariff_revenue", `${fmt(S.buerger_feld, 2)} <span class="hint">(Bedeutung offen)</span>`],
          S.strategie && ["Automatisierung der Handelsrichtlinien", esc(S.strategie_name || S.strategie)]])}
    ${gueter.length ? table([{ t: "Gut", l: true, f: g => gut(g) },
      ...satzFelder.map(([k, v]) => ({ t: ZOLL_SATZ[k] || k, f: g => num((v || {})[g]) ? `${v[g] < 0 ? "Subvention " : ""}${pct(Math.abs(v[g]), 1)}` : "–" }))],
      gueter, { scroll: true }) : ""}
    ${(S.meinung?.von_uns || []).length ? `<p class="hint">Meinungsabzug durch unsere Ausfuhrzölle: ${S.meinung.von_uns.map(m =>
      `${esc(m.tag)} ${sgn(m.wert, 2)}`).join(", ")}.</p>` : ""}
    ${fremd.length ? `<details><summary>Zölle des Besitzers ${esc(S.heimatmarkt_besitzer_name || "")} (treffen unsere Ausfuhren aus
      ${esc(S.heimatmarkt_name || "dem Heimatmarkt")})</summary>${fremd.map(([k, v]) => table([{ t: "Gut", l: true, f: ([g]) => gut(g) },
        { t: ZOLL_SATZ[k] || k, f: ([, s]) => pct(s, 1) }], Object.entries(v || {}).sort((a, b) => b[1] - a[1]), { scroll: true })).join("")}</details>` : ""}
    <p class="hint">Spielstand: Land last_months_tariff_income, je Stand last_month.tariff_income (Spiel: „Anteil der Zölle für die
      Stände“), Sätze goods_export_tariffs (0,2 = 20 %; negativ = Subvention). Ein Feld für Einfuhrzölle ist im Spielstand noch nicht
      belegt – erscheint eins, zeigt die Tabelle es unter seinem Feldnamen.</p></div>`;
  // 4 Höchstsätze (live, Aufschlüsselung ab Mod 0.24.1) und ihre Quellen laut Spieldateien
  const quellen = m => ((H.quellen || {})[m] || []).map(q => `${esc(ZOLL_ORDNER[q.ordner] || q.ordner)}${q.ordner === "auto_modifiers" ? "" : " " + esc(ent(q.name))}${q.teil
    ? ` <span class="hint">(${esc(q.teil)})</span>` : ""}: ${sgn(q.wert * 100, 0)} %`).join("<br>");
  const hoechst = `<div class="card"><h3>Höchstsätze der Zölle – live</h3><div class="brk">
      ${zeileAuf("Max. Einfuhr- und Ausfuhrzoll", num(M.max_tariff) ? pct(M.max_tariff, 0) : "–", modDesc(d, "max_tariff"), "GetDescriptionFor('max_tariff')")}
      ${zeileAuf("Max. Einfuhr- und Ausfuhr-Subvention", num(M.max_trade_subventions) ? pct(M.max_trade_subventions, 0) : "–", modDesc(d, "max_trade_subventions"), "GetDescriptionFor('max_trade_subventions')")}
      ${zeileAuf("Modifikator Zolleinnahmen", num(M.tariff_income) ? pct(M.tariff_income, 1) : "–", modDesc(d, "tariff_income"), "GetDescriptionFor('tariff_income')")}</div>
    ${quellen("max_tariff") ? `<details><summary>Woher höhere Höchstzölle kommen (Spieldateien)</summary><div class="hint">${quellen("max_tariff")}</div></details>` : ""}
    ${quellen("max_trade_subventions") ? `<details><summary>Woher höhere Subventionen kommen (Spieldateien)</summary><div class="hint">${quellen("max_trade_subventions")}</div></details>` : ""}
    <p class="hint">Wie „Maximale Zölle“ im Fenster Handelsrichtlinien: max_tariff gilt für Ein- und Ausfuhrzoll, max_trade_subventions für
      Subventionen (Grundwerte je 20 %, auto_modifiers/country.txt). Zolleinnahmen: Grundwert 10 % + Kronmacht × 1,0 – vermutlich der Anteil
      des Landes an den Zöllen (wie bei den Handelseinnahmen; nicht nachgerechnet). Gesellschaftswert Merkantilismus: +50 % am linken Pol
      (Wirkung je Stellung ungeprüft). Aufschlüsselung des Spiels ab Daten-Mod 0.24.1.</p></div>`;
  return H.ab14 ? sect("Handelsbestellungen und Zölle", `<div class="grid2">${zoelle}${bestellungen}${unsere}${hoechst}</div>`,
                      "ab Patch 1.4 – im Spiel: Handelsbestellungen, Fenster Handelsrichtlinien")
    : sect("Handelsaufträge", `<div class="grid2">${bestellungen}</div>`, "Spielstand vor 1.4");
}

// Prüfung der Handelsbestellungen je Ware (Nutzerwunsch 29.10.) – Server eu5ratgeber/handel.pruefung: Route live, Monate mit Route
// (Daten-Mod je Monat), Gewinn je Händlerkapazität zuletzt, Lage im Markt der Bestellung, Preise in Reichweite, Ausfuhrzoll.
// Die Gründe als Text und die Handlung stehen in der Empfehlung (Kachel Empfehlungen), hier die Zahlen.
function pruefKarte(d, H) {
  const PR = (H.pruefung || {}).bestellungen || [];
  if (!PR.length) return "";
  const HV = H.vorschlaege || {}, fk = wpFokus(d), VF = (HV.fokusse || {})[fk];
  const lage = g => { const l = g.lage || {}; return num(l.saldo) ? `<span class="${g.richtung === "einfuhr" ? (l.saldo >= 0 ? "neg" : "pos") : (l.saldo < 0 ? "neg" : "pos")}">${sgn(l.saldo, 2)}</span>
      <div class="hint">Angebot ${fmt(l.angebot, 2)}, Nachfrage ${fmt(l.nachfrage, 2)}</div>` : "–"; };
  const vgl = g => { const L = g.richtung === "einfuhr" ? g.billiger : g.teurer;
    return (L || []).length ? L.map(x => `${esc(x.markt)} ${fmt(x.preis, 2)}`).join(", ") + `<div class="hint">hier ${fmt(g.lage?.preis, 2)}</div>` : `<span class="hint">keiner (hier ${fmt(g.lage?.preis, 2)})</span>`; };
  const html = PR.map(p => `<div class="sect">Prüfung je Ware – Bestellung Nr. ${esc(p.id)} (${esc(p.markt_name)})</div>${table([
      { t: "Ware", l: true, f: g => `<b>${esc(g.gut_name)}</b> <span class="hint">${g.richtung === "einfuhr" ? "Einfuhr" : "Ausfuhr"}</span>` },
      { t: "Route live", l: true, f: g => g.routen.length ? `${g.routen.map(r => esc(r.markt)).join(", ")}<div class="hint">${fmt(g.je_kap, 2)} je Händlerkapazität</div>` : `<span class="neg">keine</span>` },
      { t: "Monate mit Route", f: g => `${g.mit_route} von ${g.monate}${!g.routen.length && g.ohne_seit ? `<div class="hint">seit ${g.ohne_seit} ohne</div>` : ""}` },
      { t: "Gewinn je Kapazität zuletzt", l: true, f: g => g.letzte ? `${g.letzte.serie.map(([m, v, gen]) => gen === 0
          ? `<span class="hint">${esc(m)}: nichts gehandelt</span>` : `${fmt(v, 2)} <span class="hint">${esc(m)}</span>`).join(" → ")}` : "–" },
      { t: "Saldo im Markt (Angebot − Nachfrage)", f: lage },
      { t: "Preise in Reichweite (Gold)", l: true, f: g => `<span class="hint">${g.richtung === "einfuhr" ? "billiger:" : "teurer:"}</span> ${vgl(g)}` },
      { t: "Ausfuhrzoll", f: g => g.richtung === "ausfuhr" && num(g.zoll_satz) ? pct(g.zoll_satz, 1) : "–" }], p.gueter, { scroll: true })}
    <p class="hint">${p.kap ? `Unsere Händlerkapazität in ${esc(p.kap.markt)}: ${fmt(p.kap.kapazitaet, 2)}, genutzt ${fmt(p.kap.genutzt, 2)}, frei ${fmt(p.kap.frei, 2)} (Spielstand). ` : ""}
      Modus und erlaubte Märkte: ${p.modus ? esc(p.modus) : "kein Feld im Spielstand (Standardwerte – welche, ist nicht belegt)"}${p.maerkte_angepasst ? ", Märkte angepasst" : ""}.
      Monate mit Route = Monate mit Daten-Mod, in denen eine Route aus einer Bestellung diese Ware aus dem bzw. in den Markt der Bestellung handelte.
      Gewinn je Kapazität = GetProfitPerMerchantCapacity (Gewinn ÷ genutzte Kapazität).</p>`).join("");
  const vor = VF && (VF.eintraege || []).length ? `<p>Vorschläge zum gewählten Schwerpunkt „${esc(VF.name)}“: ${VF.eintraege.map(e =>
      `${esc(e.gut_name)} (${e.richtung === "einfuhr" ? "Einfuhr aus" : "Ausfuhr nach"} ${esc(e.markt)})`).join(", ")} – <a href="#wirtschaftsplan" data-oeffne="wirtschaftsplan">→ Kachel Wirtschaftsplan</a></p>` : "";
  return html + vor;
}

// Nachbarn und Kriegsgelegenheiten (Nutzerwunsch 25.10.): Stärke der Nachbarn und selbst gewählter Länder, Ampel „Krieg möglich?“ –
// Server eu5ratgeber/nachbarn.py. Daten-Mod: Bündnisstärken (offensive/defensive_alliance_strength), Kriegsgrund (Beziehung kb_ziel),
// Heer, Mannstärke …, ab 0.20 Waffenstillstand, im Krieg, Krieg ohne Kriegsgrund; Spielstand (Format 14): alle lebenden Länder.
const NB_AMPEL = { gruen: ["pos", "aussichtsreich"], gelb: ["", "knapp"], rot: ["neg", "nicht ratsam"], grau: ["hint", "unbekannt"] };
const nbWahl = () => { try { return JSON.parse(store.get("rg_nachbarn_wahl") || "[]") || []; } catch (e) { return []; } };
function nachbarnKachel(d) {
  const nb = d.nachbarn;
  if (!nb) return { head: hd({ big: [{ l: "Nachbarn", v: "–" }] }), body: '<p class="hint">Noch keine Daten.</p>' };
  const wir = nb.wir || {}, alle = store.get("rg_nachbarn_alle") === "1";
  const SP = nb.spielstand || { spalten: [], zeilen: [] };
  const spRow = z => Object.fromEntries(SP.spalten.map((s, i) => [s, z[i]]));
  const spByTag = Object.fromEntries(SP.zeilen.map(z => [z[0], spRow(z)]));
  const serverTags = new Set(nb.laender.map(r => r.tag));
  // gespeicherte Auswahl nur mit Ländern dieser Partie, die es noch gibt, ohne uns selbst (Prüfung 25.10.)
  const wahlRoh = nbWahl(), wahl = wahlRoh.filter(t => t !== d.meta.tag && (spByTag[t] || serverTags.has(t)));
  // gezeigt: Nachbarn, Kriegsgrund-Ziele, Rivalen, Kriegsgrund gegen uns (standard), gewählte Länder, auf Wunsch alle mit Beziehung
  const rows = nb.laender.filter(r => r.standard || alle || wahl.includes(r.tag))
    .concat(wahl.filter(t => !serverTags.has(t) && spByTag[t]).map(t => ({ tag: t, name: spByTag[t].name, beziehungen: [], werte: {},
      diplomatie: {}, sp: spByTag[t], nurSpielstand: true,
      bewertung: { stufe: "grau", verhaeltnis: null, gruende: ["keine Beziehung zu uns – nur Spielstand, Bündnisstärke unbekannt"], hinweise: [] } })));
  const ampel = r => { const [c, t] = NB_AMPEL[r.bewertung.stufe];
    return `<span class="${c}" style="${r.bewertung.stufe === "gelb" ? "color:var(--c7);" : ""}font-size:18px" title="${t}">●</span>`; };
  const ja = v => v === 1 ? "ja" : v === 0 ? "nein" : "–";
  const kb = r => r.beziehungen.includes("kb_ziel") ? '<span class="pos">ja</span>' : r.diplomatie.ohne_kb === 1 ? "ohne KG möglich"
    : r.diplomatie.ohne_kb === 0 ? '<span class="neg">nein</span>' : r.nurSpielstand ? "–" : "nein";
  const heer = r => num(r.werte.army_size) ? fmt(r.werte.army_size, 2) : r.sp ? `${fmt((r.sp.mann || 0) / 1000, 2)} <span class="hint">Sp.</span>` : "–";
  const mp = r => num(r.werte.manpower) ? `${fmt(r.werte.manpower, 2)} / ${fmt(r.werte.max_manpower, 2)}`
    : r.sp && num(r.sp.mannstaerke) ? `${fmt(r.sp.mannstaerke, 2)} / ${fmt(r.sp.max_mannstaerke, 2)} <span class="hint">Sp.</span>` : "–";
  const gruen = nb.laender.filter(r => r.bewertung.stufe === "gruen");
  const head = hd({
    big: [{ l: "Kriegsgelegenheiten", v: String(gruen.length), cls: gruen.length ? "pos" : "",
            title: gruen.map(r => r.name).join(", ") || "keine Ampel auf Grün" },
          { l: "Unser Offensivbündnis", v: fmt(wir.offensive_alliance_strength, 2),
            title: "Spielwert offensive_alliance_strength: wir samt allen, die wir in einen Angriffskrieg rufen können" },
          { l: "Heer", v: fmt(wir.army_size, 2), u: "Tsd. Mann" },
          { l: "Mannstärke", v: `${fmt(wir.manpower, 2)} <i>/ ${fmt(wir.max_manpower, 2)}</i>`, u: "Tsd." }],
    small: [{ l: "Verteidigungsbündnis", v: fmt(wir.defensive_alliance_strength, 2) },
            { l: "Stabilität", v: fmt(wir.stability, 1), cls: posneg(wir.stability) },
            { l: "Kriegsmüdigkeit", v: fmt(wir.war_exhaustion, 2) },
            { l: "Gold / Saldo", v: `${fmt(wir.gold, 0)} / ${sgn(wir.saldo, 2)}` },
            { l: "Laufende Kriege", v: String(wir.kriege || 0), cls: wir.kriege ? "neg" : "" }],
    warn: [nb.veraltet && esc(nb.veraltet) + " – Ampel grau",
           wir.kriege && `Wir sind schon in ${wir.kriege} Krieg(en)`,
           num(wir.manpower) && num(wir.max_manpower) && wir.max_manpower > 0 && wir.manpower < 0.5 * wir.max_manpower && "Unsere Mannstärke liegt unter der Hälfte"],
  });
  const tabelle = table([
    { t: "", f: ampel },
    { t: "Land", l: true, f: r => `<b>${esc(r.name)}</b> <span class="hint">${esc(r.tag)}</span>${wahl.includes(r.tag)
      ? ` <button class="nbweg" data-nb-weg="${esc(r.tag)}" title="aus der Auswahl nehmen">×</button>` : ""}<div class="hint">${esc(r.beziehungen.map(b => BEZIEHUNG[b] || b).join(", ") || "gewählt")}</div>` },
    { t: "Bündnis wir : sie", f: r => r.bewertung.unendlich ? "∞ : 1" : num(r.bewertung.verhaeltnis) ? `${fmt(r.bewertung.verhaeltnis, 2)} : 1` : "–",
      cls: r => ({ gruen: "pos", rot: "neg" })[r.bewertung.stufe] || "" },
    { t: "Ihr Verteidigungsbündnis", f: r => fmt(r.werte.defensive_alliance_strength, 2) },
    { t: "Heer (Tsd. Mann)", f: heer }, { t: "Regimenter", f: r => fmt(r.werte.num_regiments ?? r.sp?.regimenter, 0) },
    { t: "Schiffe", f: r => fmt(r.werte.navy_size ?? r.sp?.schiffe, 0) },
    { t: "Mannstärke (Tsd.)", f: mp },
    { t: "Militärstärke", f: r => fmt(r.werte.military_strength, 2) },
    { t: "Stabilität", f: r => fmt(r.werte.stability, 1), cls: r => posneg(r.werte.stability) },
    { t: "Kriegsgrund", f: kb }, { t: "Waffenstillstand", f: r => ja(r.diplomatie.truce) }, { t: "im Krieg", f: r => ja(r.diplomatie.at_war ?? (r.sp ? (r.sp.kriege ? 1 : 0) : null)) },
    { t: "Militär-Rang", f: r => fmt(r.sp?.mil_rang, 0), title: "Militärwertung des Spiels (score_rank MIL), Spielstand" },
    { t: "Fortschritte", f: r => fmt(r.sp?.fortschritte, 0) },
    { t: "Begründung", l: true, f: r => esc(r.bewertung.gruende.join("; ")) + (r.bewertung.hinweise.length ? `<div class="hint">${esc(r.bewertung.hinweise.join("; "))}</div>` : "") }],
    rows);
  const liste = SP.zeilen.map(z => `<option value="${esc(z[1])} (${esc(z[0])})"></option>`).join("");
  const auswahl = `<div class="nbwahl"><input list="nb-liste" id="nb-neu" placeholder="Land suchen (Name oder Kürzel) …" style="min-width:280px">
      <datalist id="nb-liste">${liste}</datalist> <button data-nb-add>hinzufügen</button>
      <label style="margin-left:16px"><input type="checkbox" id="nb-alle"${alle ? " checked" : ""}> alle Länder mit Beziehung zu uns zeigen</label>
      ${wahl.length ? `<span class="hint" style="margin-left:16px">gewählt: ${wahl.length}</span>` : ""}
      ${wahlRoh.length ? ` <button data-nb-leer title="alle selbst gewählten Länder entfernen">Auswahl leeren</button>` : ""}</div>`;
  const body = `<div class="card" style="grid-column:1/-1"><h3>Länder – ${rows.length}</h3>${auswahl}${tabelle}
    <p class="hint">Ampel (Regel des Ratgebers, Zahlen sind Spielwerte): unser Offensivbündnis (offensive_alliance_strength) gegen ihr
      Verteidigungsbündnis (defensive_alliance_strength: sie samt allen, die sie verteidigen). Grün ab ${fmt(nb.schwellen.gruen, 1)} : 1 mit Kriegsgrund
      und ohne Waffenstillstand; gelb ab ${fmt(nb.schwellen.gelb, 1)} : 1 oder nur Krieg ohne Kriegsgrund; rot bei Waffenstillstand, ohne möglichen
      Kriegsgrund oder unter ${fmt(nb.schwellen.gelb, 1)} : 1; grau ohne Mod-Werte. Mod-Werte ${esc(nb.fremd_datum || "–")} (Länder mit Beziehung zu uns),
      „Sp.“ und Rang/Fortschritte: Spielstand ${esc(nb.datum_spielstand || "–")}. Waffenstillstand, im Krieg und „Krieg ohne Kriegsgrund“ ab Mod 0.20.
      Die gewählten Länder bleiben in diesem Browser.</p></div>`;
  return { head, body: `<div class="grid2">${body}</div>` };
}
function nbSetzen(tags) {
  store.set("rg_nachbarn_wahl", JSON.stringify(tags));
  if (!LAST_D) return;
  const y = window.scrollY;
  render(LAST_D);
  if (typeof equalizeTiles === "function") equalizeTiles();
  window.scrollTo(0, y);
}
document.addEventListener("click", e => {
  const add = e.target.closest?.("button[data-nb-add]"), weg = e.target.closest?.("button[data-nb-weg]");
  const leer = e.target.closest?.("button[data-nb-leer]");
  if (add) {
    // „Name (TAG)“ aus der Liste, Kürzel oder Name – groß/klein egal; nur Länder dieser Partie, nicht wir selbst
    const v = String(document.getElementById("nb-neu")?.value || "").trim();
    const zeilen = LAST_D?.nachbarn?.spielstand?.zeilen || [];
    const m = v.match(/\(([A-Za-z0-9_]{3,})\)\s*$/) || v.match(/^([A-Za-z0-9_]{3})$/);
    const tag = m ? m[1].toUpperCase() : zeilen.find(z => String(z[1]).toLowerCase() === v.toLowerCase())?.[0];
    const gibt = tag && (zeilen.some(z => z[0] === tag) || (LAST_D?.nachbarn?.laender || []).some(r => r.tag === tag));
    if (gibt && tag !== LAST_D?.meta?.tag && !nbWahl().includes(tag)) nbSetzen([...nbWahl(), tag]);
  } else if (weg) nbSetzen(nbWahl().filter(t => t !== weg.dataset.nbWeg));
  else if (leer) nbSetzen([]);
});
document.addEventListener("change", e => {
  if (e.target.id !== "nb-alle") return;
  store.set("rg_nachbarn_alle", e.target.checked ? "1" : "0");
  nbSetzen(nbWahl());
});

// Kachel je Krieg (Nutzerwunsch 25.10.): Seiten, Kräfte, Armeen mit Heerführern, Einheitentypen, Lage – Server eu5ratgeber/krieg.py.
// Mod (neuester Monat): Kriegspunkte, Dauer, Kräfte je Land (RG2 fremd/land), ab 0.19 Armeen mit Heerführern (RG1F, RG1C);
// Spielstand (Format 13): Seiten mit Beitrittsgrund, Schlachten, Verluste, Besetzung, Einheitentypen, Eigenschaften der Heerführer.
const KRIEG_KRAFT = [["Heer (Tsd. Mann)", "army_size", 2], ["Regimenter", "num_regiments", 0], ["Schiffe", "navy_size", 0],
  ["Mannstärke (Tsd.)", "manpower", 2, "max_manpower"], ["Seeleute (Tsd.)", "sailors", 2, "max_sailors"],
  ["Aufgebote möglich (Tsd. Mann)", "country_total_army_levy_size", 2], ["Regulärtruppen (Tsd. Mann)", "regular_army_size", 2],
  ["Militärstärke", "military_strength", 1]];
const KRIEG_GRUND = { Instigator: "Kriegserklärer", Target: "Kriegsziel", Overlord: "Oberherr", Subject: "Untertan",
  InternationalOrganization: "Organisation" };
const KRIEG_VERLUST = [["Battle", "Schlacht"], ["Attrition", "Zermürbung"], ["Capture", "Gefangen"]];
const ZEITALTER_REIHE = ["age_1_traditions", "age_2_renaissance", "age_3_discovery", "age_4_reformation", "age_5_absolutism", "age_6_revolutions"];
function kriegKachel(d, w) {
  const N = w.namen || {}, nm = k => N[k] || k;
  const wir = w.wir_seite, geg = w.gegen_seite, S = w.seiten || {}, sw = S[wir] || {}, sg = S[geg] || {};
  const T = Object.fromEntries(w.teilnehmer.map(t => [t.tag, t]));
  const land = tag => esc(T[tag]?.name || tag || "?");
  const verh = (a, b) => num(a) && num(b) && b > 0 ? a / b : null;
  const heerV = verh(sg.army_size, sw.army_size), schiffV = verh(sg.navy_size, sw.navy_size);
  const ich = w.teilnehmer.find(t => t.wir) || {};
  const ziel = w.kriegsziel?.orte || [];
  // Zielorte aus dem Spielstand, die die Gegner besetzen – das Kriegsziel kann eine ganze Provinz sein; ob das Kriegsziel beim
  // Gegner liegt, sagt nur der Spieltext (ziel_kontrolle, erste Zeile der Punkte-Aufschlüsselung). Prüfung 25.10.
  const zielGegner = ziel.filter(o => o.kontrolleur && T[o.kontrolleur]?.seite === geg);
  const zk = w.ziel_kontrolle, zkUns = zk && zk === wir;
  // Kriegspunkte: Spielwert GetWarScore aus unserer Sicht (die Aufschlüsselung des Spiels ergibt ihn); RG1W war_score_in_war klein
  const pw = num(w.punkte_spiel) ? w.punkte_spiel : w.punkte_wir;
  const ohneHeer = sw.army_size === 0 && sg.army_size > 0;
  const head = hd({
    big: [{ l: "Kriegspunkte", v: sgn(pw, 1), cls: posneg(pw),
            title: num(w.punkte_spiel) ? "Spielwert GetWarScore aus unserer Sicht – die Aufschlüsselung in der Karte Lage ergibt ihn" : "Daten-Mod: war_score_in_war" },
          { l: "Dauer", v: fmt(w.dauer, 0), u: "Monate" },
          { l: "Heer unsere Seite / Gegner", v: `${fmt(sw.army_size, 1)} <i>/ ${fmt(sg.army_size, 1)}</i>`, u: "Tsd. Mann",
            cls: heerV >= 1.2 ? "neg" : heerV && heerV <= 0.83 ? "pos" : "", title: "Summe army_size der Länder je Seite (Daten-Mod)" },
          { l: "Schiffe unsere Seite / Gegner", v: `${fmt(sw.navy_size, 0)} <i>/ ${fmt(sg.navy_size, 0)}</i>`,
            cls: schiffV >= 1.2 ? "neg" : schiffV && schiffV <= 0.83 ? "pos" : "" }],
    small: [{ l: "Wir sind", v: `${esc(wir || "?")} · ${fmt(sw.laender, 0)} gegen ${fmt(sg.laender, 0)} Länder` },
            (w.kriegsziel_text || ziel.length) && { l: "Kriegsziel", v: esc(w.kriegsziel_text || ziel.map(o => o.name).join(", ")) },
            zk && { l: "Kriegsziel hält", v: `<span class="${zkUns ? "pos" : zk === geg ? "neg" : ""}">${esc(zk)}${zkUns ? " (wir)" : ""}</span>`,
              title: "Spieltext (erste Zeile der Punkte-Aufschlüsselung, Daten-Mod)" },
            !zk && zielGegner.length && { l: "Zielort besetzt", v: `<span class="neg">${esc(zielGegner.map(o => o.name).join(", "))} – ${land(zielGegner[0].kontrolleur)}</span> <span class="hint">Spielstand</span>` },
            num(w.punkte_spiel) && num(w.punkte_wir) && { l: "war_score_in_war (Mod)", v: sgn(w.punkte_wir, 1),
              title: "Daten-Mod RG1W: Wert des Spiel-Triggers war_score_in_war – weicht von den Kriegspunkten des Spiels ab" },
            num(w.stillstand) && { l: "Stillstand", v: `${fmt(w.stillstand, 0)} Monate` },
            num(ich.kraefte?.war_exhaustion) && { l: "Kriegsmüdigkeit (wir)", v: fmt(ich.kraefte.war_exhaustion, 2) },
            w.beginn && { l: "Beginn", v: esc(w.beginn) }],
    warn: [ohneHeer && `Unsere Seite hat kein Heer, die Gegner ${fmt(sg.army_size, 1)} Tsd. Mann`,
           heerV >= 1.5 && `Heer der Gegner ${fmt(heerV, 1)}× so groß wie das unserer Seite`,
           schiffV >= 1.5 && `Flotte der Gegner ${fmt(schiffV, 1)}× so groß`,
           zk && zk === geg && `Kriegsziel in Hand der Gegner (${esc(zk)}, Spieltext)`],
  });

  // Seiten im Vergleich (Summen der Mod-Werte je Land)
  const vergleich = `<div class="card" style="grid-column:1/-1"><h3>Seiten im Vergleich</h3>${table([
    { t: "Wert", l: true, f: r => esc(r[0]) },
    { t: `Unsere Seite (${esc(wir || "?")})`, f: r => r[3] ? `${fmt(sw[r[1]], r[2])} / ${fmt(sw[r[3]], r[2])}` : fmt(sw[r[1]], r[2]) },
    { t: `Gegner (${esc(geg || "?")})`, f: r => r[3] ? `${fmt(sg[r[1]], r[2])} / ${fmt(sg[r[3]], r[2])}` : fmt(sg[r[1]], r[2]) },
    { t: "Gegner : wir", f: r => fmt(verh(sg[r[1]], sw[r[1]]), 2), cls: r => (verh(sg[r[1]], sw[r[1]]) ?? 1) > 1 ? "neg" : "pos" }], KRIEG_KRAFT)}
    <p class="hint">Summe der Spielwerte je Land (Daten-Mod ${esc(w.fremd_datum || "")}: RG2 fremd, für uns RG2 land). Ohne Werte:
      ${fmt(sw.ohne_werte, 0)} Länder unserer Seite, ${fmt(sg.ohne_werte, 0)} der Gegner – Verbündete bekommen die Werte ab Mod 0.19.
      Mannstärke und Seeleute: aktuell / Höchstwert.</p></div>`;

  // Teilnehmer
  const beitrag = t => { const p = t.punkte || {}; const s = (p.Combat || 0) + (p.Siege || 0); return s || null; };
  const teil = `<div class="card" style="grid-column:1/-1"><h3>Teilnehmer – ${w.teilnehmer.length}</h3>${table([
    { t: "Land", l: true, f: t => `${t.wir ? "<b>" : ""}${esc(t.name)}${t.wir ? "</b>" : ""} <span class="hint">${esc(t.tag)}</span>${t.im_krieg_live === false ? ' <span class="neg">nicht mehr im Krieg (Mod)</span>' : ""}` },
    { t: "Seite", l: true, f: t => esc(t.seite === wir ? `${t.seite} (unsere Seite)` : t.seite || "?") },
    { t: "Grund", l: true, f: t => esc([KRIEG_GRUND[t.grund] || t.grund, t.gerufen_von && `gerufen von ${T[t.gerufen_von]?.name || t.gerufen_von}`].filter(Boolean).join(", ") || "–") },
    { t: "Heer (Tsd.)", f: t => fmt(t.kraefte.army_size, 2) }, { t: "Regimenter", f: t => fmt(t.kraefte.num_regiments, 0) },
    { t: "Schiffe", f: t => fmt(t.kraefte.navy_size, 0) },
    { t: "Mannstärke (Tsd.)", f: t => num(t.kraefte.manpower) ? `${fmt(t.kraefte.manpower, 2)} / ${fmt(t.kraefte.max_manpower, 2)}` : "–" },
    { t: "Seeleute (Tsd.)", f: t => num(t.kraefte.sailors) ? `${fmt(t.kraefte.sailors, 2)} / ${fmt(t.kraefte.max_sailors, 2)}` : "–" },
    { t: "Armeetradition", f: t => num(t.kraefte.army_tradition) ? `${fmt(t.kraefte.army_tradition, 1)} %` : "–" },
    { t: "Kriegsmüdigkeit", f: t => fmt(t.kraefte.war_exhaustion ?? t.diplomatie.war_exhaustion, 2) },
    { t: "Fortschritte", f: t => fmt(t.technik?.fortschritte, 0) },
    { t: "Kriegspunkte Kampf + Belagerung", f: t => fmt(beitrag(t), 1) }], w.teilnehmer)}
    <p class="hint">Seite, Grund und Kriegspunkte je Teilnehmer: Spielstand ${esc(w.datum_spielstand || "–")}; Kräfte: Daten-Mod ${esc(w.fremd_datum || "–")};
      Fortschritte: erforschte Fortschritte laut Spielstand (der Mod-Wert num_of_advances_researched ist immer 0).</p></div>`;

  // Armeen und Flotten: Gegner zuerst, dann unsere Seite; je Seite nach Stärke
  const zus = e => e.kategorien && Object.keys(e.kategorien).length
    ? Object.entries(e.kategorien).map(([k, n]) => `${n} ${esc(nm(k))}`).join(", ")
    : Object.entries(e.typen || {}).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${n} ${esc(nm(k))}`).join(", ");
  // je Seite erst Heere (nach Mann), dann Flotten (nach Schiffen)
  const groesse = e => e.art === "flotte" ? e.schiffe ?? 0 : e.mann ?? 0;
  const einh = (w.einheiten || []).slice().sort((a, b) => (a.seite === geg ? 0 : 1) - (b.seite === geg ? 0 : 1)
    || (a.art === "flotte") - (b.art === "flotte") || groesse(b) - groesse(a));
  const quelleE = einh[0]?.quelle === "Mod" ? `Daten-Mod ${esc(w.datum_live || "")}` : `Spielstand ${esc(w.datum_spielstand || "")}`;
  const armeen = `<div class="card" style="grid-column:1/-1"><h3>Armeen und Flotten – ${einh.length}</h3>${table([
    { t: "Seite", l: true, f: e => e.seite === geg ? '<span class="neg">Gegner</span>' : "wir/Verbündete" },
    { t: "Land", l: true, f: e => land(e.land) },
    { t: "Art", l: true, f: e => e.art === "flotte" ? "Flotte" : "Heer" },
    { t: "Ort", l: true, f: e => esc(e.ort || "–") },
    { t: "Stärke", f: e => e.art === "flotte" ? `${fmt(e.schiffe, 0)} Schiffe` : `${fmt(e.mann, 0)} Mann` },
    { t: "Zusammensetzung", l: true, f: e => zus(e) || "–" },
    { t: "Moral", f: e => num(e.moral_pct) ? pct(e.moral_pct, 0) : fmt(e.moral, 2) },
    { t: "Heerführer", l: true, f: e => e.fuehrer ? `${esc(e.fuehrer.name || "?")}${num(e.fuehrer.mil) ? ` <span class="hint">Militär ${fmt(e.fuehrer.mil, 0)}</span>` : ""}${e.fuehrer.eigenschaft ? ` · ${esc(e.fuehrer.eigenschaft)}` : ""}` : "–" }], einh)}
    <p class="hint">Quelle: ${quelleE}. Stärke wie im Spiel angezeigt (Mod: GetVisualStrength) bzw. Summe der Regimentsstärke × 1.000 Mann
      (Spielstand, REGIMENT_SIZE); Moral: Mod in % des Höchstwerts, Spielstand als Spielwert. Militär, Eigenschaft: Spielstand/Mod.</p></div>`;

  // Einheitentypen (statt „Techlevel“, das es in EU5 nicht gibt): neueste freigeschaltete Einheit je Kategorie
  const neueste = es => { const m = Math.max(...es.map(e => ZEITALTER_REIHE.indexOf(e.zeitalter))); return es.filter(e => ZEITALTER_REIHE.indexOf(e.zeitalter) === m); };
  const gegner = w.teilnehmer.filter(t => t.seite === geg && t.technik).sort((a, b) => (b.kraefte.army_size || 0) - (a.kraefte.army_size || 0)).slice(0, 4);
  const spalten = [ich, ...gegner].filter(t => t.technik);
  const kats = [...new Set(spalten.flatMap(t => Object.keys(t.technik.einheiten || {})))].sort();
  const alterWir = k => Math.max(-1, ...((ich.technik?.einheiten || {})[k] || []).map(e => ZEITALTER_REIHE.indexOf(e.zeitalter)));
  const technik = spalten.length ? `<div class="card" style="grid-column:1/-1"><h3>Einheitentypen</h3>${table([
    { t: "Kategorie", l: true, f: k => k === "_n" ? "Erforschte Fortschritte" : esc(nm(k)) },
    ...spalten.map(t => ({ t: t.name + (t.wir ? " (wir)" : ""), l: true,
      f: k => k === "_n" ? fmt(t.technik.fortschritte, 0) : (() => { const es = (t.technik.einheiten || {})[k];
        if (!es) return "–";
        const nn = neueste(es), a = ZEITALTER_REIHE.indexOf(nn[0].zeitalter), vor = !t.wir && a > alterWir(k);
        return `<span class="${vor ? "neg" : ""}">${nn.map(e => esc(e.name)).join(", ")}</span> <span class="hint">${esc(nm(nn[0].zeitalter))}${es.length > nn.length ? ` · ${es.length} Typen` : ""}</span>`; })() }))],
    ["_n", ...kats])}
    <p class="hint">EU5 hat kein Techlevel: verglichen werden die erforschten Fortschritte und die Einheiten, die sie freischalten (unlock_unit,
      Spieldateien), je Kategorie die des spätesten Zeitalters. Rot: Gegner hat in der Kategorie eine Einheit eines späteren Zeitalters als wir.
      Spielstand ${esc(w.datum_spielstand || "–")}; Gegner: die vier größten Heere.</p></div>` : "";

  // Lage: Beschreibung, Punkte-Aufschlüsselung, Verluste, besetzte Orte
  const vsum = v => KRIEG_VERLUST.map(([k]) => Object.values(v || {}).reduce((s, x) => s + (x[k] || 0), 0));
  const vw = vsum((w.verluste || {})[wir]), vg = vsum((w.verluste || {})[geg]);
  const vl = w.verluste_live || {}, ab = wir === "Angreifer" ? "a" : "v", gb = ab === "a" ? "v" : "a";
  const lage = `<div class="card"><h3>Lage</h3>
    ${w.texte?.beschreibung ? `<p>${esc(w.texte.beschreibung)}</p>` : ""}
    ${w.texte?.aufschluesselung ? zeileAuf(`Kriegspunkte laut Spiel${num(w.punkte_spiel) ? "" : " (Mod war_score_in_war)"}`, sgn(pw, 1), w.texte.aufschluesselung, "GetWarScoreBreakdown") : ""}
    ${num(w.punkte_spiel) ? `<p class="hint">Die Aufschlüsselung gilt aus Sicht des Angreifers (Spiel: ${sgn(w.kriegspunkte, 2)}); oben aus unserer Sicht.</p>` : ""}
    ${w.verluste ? table([{ t: "Verluste (Mann)", l: true, f: r => r[0] }, ...KRIEG_VERLUST.map(([, l], i) => ({ t: l, f: r => fmt(r[1][i], 0) }))],
      [["Unsere Seite", vw], ["Gegner", vg]], { scroll: false }) : ""}
    ${num(vl[`verl_${ab}_mann`]) ? `<p>Verluste laut Spiel (Mod): wir ${fmt(vl[`verl_${ab}_mann`], 0)} Mann, ${fmt(vl[`verl_${ab}_schiffe`], 0)} Schiffe ·
      Gegner ${fmt(vl[`verl_${gb}_mann`], 0)} Mann, ${fmt(vl[`verl_${gb}_schiffe`], 0)} Schiffe</p>` : ""}
    ${(w.besetzt || []).length ? `<h5>Besetzte Orte – ${w.besetzt.length}</h5>${table([{ t: "Ort", l: true, f: b => esc(b.ort) },
      { t: "Besitzer", l: true, f: b => land(b.besitzer) }, { t: "besetzt von", l: true, f: b => land(b.kontrolleur),
        cls: b => T[b.kontrolleur]?.seite === geg ? "neg" : "pos" }], w.besetzt, { scroll: false })}` : ""}
    <p class="hint">Verluste je Seite und Kategorie summiert: Spielstand ${esc(w.datum_spielstand || "–")} (attacker_losses/defender_losses);
      Text und Kriegspunkte: Daten-Mod ${esc(w.datum_live || "–")}.</p></div>`;

  // Schlachten (Spielstand, neueste zuerst; Kriegspunkte aus unserer Sicht)
  const sl = (w.schlachten || []).slice().reverse();
  const unser = b => b[b.unsere], ihr = b => b[b.unsere === "angreifer" ? "verteidiger" : "angreifer"];
  const schlachten = sl.length ? `<div class="card"><h3>Schlachten – ${fmt(w.schlachten_gesamt, 0)}</h3>${table([
    { t: "Datum", l: true, f: b => esc(b.datum) }, { t: "Ort", l: true, f: b => esc(b.ort || "–") },
    { t: "Ergebnis", l: true, f: b => b.unsere_seite_siegt ? '<span class="pos">Sieg</span>' : '<span class="neg">Niederlage</span>' },
    // Länder der Schlachtseite beim Darüberfahren (die Spalte allein brach in der halben Breite je Land um)
    { t: "wir (Tsd.)", f: b => `<span title="${unser(b).laender.map(land).join(", ")}">${fmt(unser(b).groesse, 2)} <span class="hint">−${fmt(unser(b).verluste, 2)}</span></span>` },
    { t: "Gegner (Tsd.)", f: b => `<span title="${ihr(b).laender.map(land).join(", ")}">${fmt(ihr(b).groesse, 2)} <span class="hint">−${fmt(ihr(b).verluste, 2)}</span></span>` },
    { t: "Kriegspunkte", f: b => sgn(b.punkte_wir, 2), cls: b => posneg(b.punkte_wir) }], sl)}
    <p class="hint">Spielstand ${esc(w.datum_spielstand || "–")}, die letzten ${sl.length}; Größe und Verluste in Tausend Mann, beteiligte Länder beim
      Darüberfahren. Kriegspunkte aus unserer Sicht
      (der Spielstand führt sie aus Sicht des Angreifers der Schlacht).</p></div>` : "";

  return { head, body: `<div class="grid2">${vergleich}${lage}${schlachten}${armeen}${technik}${teil}</div>` };
}

// Militär und Kriege (Nutzerwunsch 01.10., Punkte 1, 3–9; Kredite stehen in den Finanzen). Werte wie im Militärfenster
// (Screenshots des Nutzers): Aufgebote 0 / 3.802, Regulärtruppen 0 / 807 (= expected_army_size in Tsd.), Schiffe 2 / 3
// (= expected_navy_size), Armeetradition in %, Moral abgerundet (1,643 -> 1.64, 1,636 -> 1.63), Festungsschwelle 1,00 / 2,16.
// Mannstärke und Seeleute bleiben im Kopf, obwohl sie auch in der Kopfzeile stehen (Nutzerwunsch).
function militaer(d, P) {
  const LD = P.LD, lv = P.lv, AW = d.alles?.werte || {}, AT = d.alles?.texte || {};
  const L = Object.values(AW.land || {})[0] || {}, LM = Object.values(AW.landmod || {})[0] || {}, TL = Object.values(AT.land || {})[0] || {};
  const zl = (l, val, txt, code = "") => txt
    ? `<details class="bk"><summary${code ? ` title="Aufschlüsselung des Spiels: ${esc(code)}"` : ""}><span class="bl">${l}</span><span class="bv">${val}</span></summary><div class="bsub">${breakdown(txt)}</div></details>`
    : `<div class="bk"><span class="bl">${l}</span><span class="bv">${val}</span></div>`;
  const ab = (v, n = 2) => num(v) ? Math.floor(v * 10 ** n + 1e-6) / 10 ** n : v;          // Spiel rundet ab
  const zahl = t => { const m = String(t ?? "").match(/[\d,.]+/); return m ? +m[0].replace(/,/g, "") : null; };   // „3,793“ -> 3793
  const krieg = LD.krieg || [], kat = LD.katastrophe || [];
  const seitStart = d.punkte.length && num(lv.jahr ?? d.punkte.at(-1).jahr) ? Math.round(((lv.jahr ?? d.punkte.at(-1).jahr) - d.punkte[0].jahr) * 12) : null;
  const mw = L.months_since_war ?? lv.months_since_war;
  const nieKrieg = num(seitStart) && num(mw) && mw > seitStart;

  // Aufgebote (Spieltexte, ganze Zahlen wie im Fenster), Regulärtruppen und Schiffe
  const aufPot = zahl(TL.GetArmyLevyPotentialStrength ?? TL.GetPotentialAndBeingRaisedArmyLevyBreakdown), aufJetzt = zahl(TL.GetRaisedLevyStrength);
  const marAuf = zahl(TL.GetNavyLevyPower), marJetzt = zahl((String(TL.GetNavyLevyPowerTooltip || "").match(/Derzeit gibt es\s*([\d,.]+)/) || [])[1]);
  const regMax = num(L.expected_army_size) ? L.expected_army_size * 1000 : null, regJetzt = num(L.regular_army_size) ? L.regular_army_size * 1000 : null;
  const schiffe = L.navy_size ?? lv.navy_size, schiffeMax = L.expected_navy_size ?? L.GetExpectedNavySize;
  // Moral: Unterhalt multipliziert die Grundmoral (Spieltext „Der derzeitige Unterhalt multipliziert dies mit 0.50“)
  const moralFaktor = +((String(TL.GetDefaultLandMoraleTooltip || "").match(/multipliziert dies mit\s*([\d.]+)/) || [])[1] ?? NaN);
  const regler = [["Heer", L.army_maintenance], ["Flotte", L.navy_maintenance], ["Festungen", L.fort_maintenance]].filter(([, x]) => num(x));

  const head = hd({
    big: [{ l: "Aufgebote", v: `${fmt(aufJetzt, 0)} <i>/ ${fmt(aufPot, 0)}</i>`, u: num(L.potential_army_size) ? `Kampfkraft ${fmt(L.potential_army_size, 2)}` : "",
            title: "ausgehoben / potenziell (Mann) wie im Militärfenster; Aufgebote können laut Spiel nur im Krieg oder bei Rebellen ausgehoben werden" },
          { l: "Regulärtruppen", v: `${fmt(regJetzt, 0)} <i>/ ${fmt(regMax, 0)}</i>`, title: "stehendes Heer / Obergrenze (Mann) wie „Regulärtruppen ausheben“ im Militärfenster (Spielwert expected_army_size)" },
          { l: "Schiffe", v: `${fmt(schiffe, 0)} <i>/ ${fmt(schiffeMax, 0)}</i>`, bar: num(schiffe) && schiffeMax ? schiffe / schiffeMax : null, title: "Schiffe / erwartete Marinegröße wie „Schiffe bauen“ im Militärfenster" },
          { l: "Militärstärke", v: fmt(L.military_strength ?? lv.military_strength, 2), s: spark(liveSeries(d, "military_strength"), { color: "--c5" }) }],
    small: [{ l: "Kriege", v: krieg.length ? String(krieg.length) : nieKrieg ? "seit Spielbeginn keiner" : "keine", cls: krieg.length ? "neg" : "" },
            { l: "Mannstärke", v: `${fmt(L.manpower ?? lv.manpower, 2)} <i>/ ${fmt(L.max_manpower ?? lv.manpower_max, 2)}</i>`, title: "in Tausend, wie in der Kopfzeile" },
            { l: "Seeleute", v: `${fmt(L.sailors ?? lv.sailors, 2)} <i>/ ${fmt(L.max_sailors ?? lv.sailors_max, 2)}</i>`, title: "in Tausend, wie in der Kopfzeile" },
            { l: "Armeetradition", v: `${fmt(ab(L.army_tradition), 2)} %`, t: trend(L.curbal_army_tradition, 2, 1), title: "Pfeil = Veränderung je Monat (Zuwachs − Verfall)" },
            { l: "Marinetradition", v: `${fmt(ab(L.navy_tradition), 2)} %`, t: trend(L.curbal_navy_tradition, 2, 1) },
            { l: "Moral Heer / Flotte", v: `${fmt(ab(L.GetDefaultLandMorale), 2)} <i>/ ${fmt(ab(L.GetDefaultNavalMorale), 2)}</i>` },
            { l: "Festungsschwelle", v: `${fmt(L.used_fort_limit, 2)} <i>/ ${fmt(L.GetFortLimit, 2)}</i>`, bar: num(L.used_fort_limit) && L.GetFortLimit ? L.used_fort_limit / L.GetFortLimit : null },
            ...MIL_016.filter(([, m]) => num(L["mod_" + m])).map(([l, m, n]) => ({ l, v: n === "%" ? `${sgn(L["mod_" + m] * 100, 1)} %` : fmt(L["mod_" + m], n),
              title: "wie im Militärfenster (Daten-Mod ab 0.16); Aufschlüsselung in der Karte Armeen" }))],
    warn: [krieg.length && `${krieg.length} Krieg(e)`, kat.length && "Katastrophe aktiv",
           num(moralFaktor) && moralFaktor < 1 && `Moral × ${fmt(moralFaktor, 2)} durch Unterhalt (Regler ${regler.map(([n, x]) => `${n} ${pct(x, 0)}`).join(", ")})`],
  });

  // Karte Armeen: Aufgebote je Gebiet, Regulärtruppen, Mannstärke, beste Einheiten, Heerführer, Moral, Erfahrung, Festungsverteidigung
  const armeen = `<div class="card"><h3>Armeen</h3><div class="brk">
    ${zl("Aufgebote ausgehoben / potenziell", `${fmt(aufJetzt, 0)} / ${fmt(aufPot, 0)}`, TL.GetArmyLevyPowerInfo, "GetArmyLevyPowerInfo")}
    ${num(L.potential_army_size) ? zl("Kampfkraft der Aufgebote", fmt(L.potential_army_size, 2), TL.GetMilitaryStrengthForRelativePowerTooltip, "GetMilitaryStrengthForRelativePowerTooltip") : ""}
    ${TL.GetLevyRecoveryInfo ? zl("Erholung der Aufgebote", "", TL.GetLevyRecoveryInfo, "GetLevyRecoveryInfo") : ""}
    ${zl("Regulärtruppen / Obergrenze", `${fmt(regJetzt, 0)} / ${fmt(regMax, 0)}`)}
    ${zl("Mannstärke (Tsd.)", `${fmt(L.manpower, 2)} / ${fmt(L.max_manpower, 2)}`, TL.GetMaxManpowerTT, "GetMaxManpowerTT")}
    ${zl("Armeemoral", fmt(ab(L.GetDefaultLandMorale), 2), TL.GetDefaultLandMoraleTooltip, "GetDefaultLandMoraleTooltip")}
    ${zl("Armeeerfahrung", "", TL.GetAverageArmyExperienceInfo, "GetAverageArmyExperienceInfo")}
    ${MIL_016.filter(([, m]) => num(L["mod_" + m])).map(([l, m, n]) => zl(l, n === "%" ? `${sgn(L["mod_" + m] * 100, 1)} %` : fmt(L["mod_" + m], n),
      modDesc(d, m), `GetDescriptionFor('${m}')`)).join("")}
    ${num(LM.global_defensive) ? zl("Festungsverteidigung", `${sgn(LM.global_defensive * 100, 0)} %`, modDesc(d, "global_defensive"), "GetDescriptionFor('global_defensive')") : ""}
    ${num(L.possible_military_leaders) ? zl("mögliche Heerführer", fmt(L.possible_military_leaders, 0)) : ""}
    ${TL.GetBestArmyUnits ? zl("beste Einheiten", "", TL.GetBestArmyUnits, "GetBestArmyUnits") : ""}</div></div>`;

  // Karte Marineflotten: je Schiff (Untereinheiten mit IsShip), Flotten mit Admiral, Proviant, Krankheiten; Marineaufgebote
  const flotten = Object.entries(AW.einheit || {}).filter(([, e]) => e.IsNavy === 1);
  const schiffListe = Object.entries(AW.untereinheit || {}).filter(([, s]) => s.IsShip === 1).map(([id, s]) => {
    const t = (AT.untereinheit || {})[id] || {};
    return { name: String(t.GetDescription || "").split("\n")[0], typ: t.GetTypeDescription, staerke: t.GetStrength, moral: s.GetMorale,
             unterhalt: zahl(t.GetMaintenanceCost) != null ? +String(t.GetMaintenanceCost).replace(",", "") : null, info: t.GetMaintenanceCostTooltip };
  });
  const flotte = flotten.map(([id, e]) => { const t = (AT.einheit || {})[id] || {};
    const admiral = (String(t.GetMaxMoraleInfo || "").match(/des Admirals \(([^,)]+)/) || [])[1];
    const proviant = String(t.GetFoodSupplyInformation || "").match(/führt derzeit\s*(\d+(?:\.\d+)?)\s*Proviant mit von einem Höchstwert von\s*(\d+(?:\.\d+)?)/);
    return `<h5>${esc(e.name || id)}</h5><div class="brk">
      ${admiral ? zl("Admiral", esc(admiral)) : ""}
      ${zl("Moral", `${fmt(ab(e.GetMorale), 2)} / ${fmt(ab(e.GetMaxMorale), 2)}`, t.GetMaxMoraleInfo, "GetMaxMoraleInfo")}
      ${proviant ? zl("Proviant", `${fmt(+proviant[1], 2)} / ${fmt(+proviant[2], 2)}`, t.GetFoodSupplyInformation, "GetFoodSupplyInformation") : ""}
      ${t.GetStatus ? zl("Status", esc(t.GetStatus)) : ""}
      ${t.GetDiseaseTooltip ? zl("Krankheiten", "", t.GetDiseaseTooltip, "GetDiseaseTooltip") : ""}</div>`; }).join("");
  const marine = `<div class="card"><h3>Marineflotten</h3>${flotte}
    ${schiffListe.length ? table([{ t: "Schiff", f: s => esc(s.name) }, { t: "Typ", l: true, f: s => esc(s.typ || "–") },
        { t: "Stärke", f: s => esc(s.staerke || "–") }, { t: "Moral", f: s => fmt(ab(s.moral), 2) },
        { t: "Unterhalt / Monat", f: s => s.info ? `<details><summary>${fmt(s.unterhalt, 2)}</summary>${breakdown(s.info)}</details>` : fmt(s.unterhalt, 2), cls: s => posneg(s.unterhalt) }], schiffListe) : ""}
    <div class="brk">
    ${zl("Marineaufgebote ausgehoben / potenziell", `${fmt(marJetzt, 0)} / ${fmt(marAuf, 0)}`, TL.GetNavyLevyPowerInfo, "GetNavyLevyPowerInfo")}
    ${zl("Schiffe / erwartete Marinegröße", `${fmt(schiffe, 0)} / ${fmt(schiffeMax, 0)}`)}
    ${zl("Seeleute (Tsd.)", `${fmt(L.sailors, 3)} / ${fmt(L.max_sailors, 3)}`, TL.GetMaxSailorsTT, "GetMaxSailorsTT")}
    ${zl("Marinemoral", fmt(ab(L.GetDefaultNavalMorale), 2), TL.GetDefaultNavalMoraleTooltip, "GetDefaultNavalMoraleTooltip")}
    ${num(L.naval_range) ? zl("Marinereichweite", fmt(L.naval_range, 0)) : ""}
    ${TL.GetBestNavyUnits ? zl("beste Schiffe", "", TL.GetBestNavyUnits, "GetBestNavyUnits") : ""}</div></div>`;

  // Karte Festungen und Unterhalt. Festungen je Ort aus GetFortLevel (Mod, Ortswerte) als eigene Zeile – die Stufe ist nicht die
  // Nutzung der Schwelle (Den Haag Stufe 2, Nutzung 1,00). Der Spieltext GetCurrentFortsAmountInfo warf ohne Landeskontext einen
  // Datenfehler und ist ab Mod 0.21 gestrichen (Test 0.20)
  const festungOrte = (P.orte || []).map(o => [o.name, (AW.ort || {})[o.id]?.GetFortLevel]).filter(([, l]) => num(l) && l > 0)
    .map(([n, l]) => `${n}: Festungsstufe ${fmt(l, 0)}`).join("\n");
  const festung = `<div class="card"><h3>Festungen und Unterhalt</h3><div class="brk">
    ${zl("Festungsschwelle genutzt / max.", `${fmt(L.used_fort_limit, 2)} / ${fmt(L.GetFortLimit, 2)}`, TL.GetFortsLimitInfo, "GetFortsLimitInfo")}
    ${festungOrte ? zl("Festungen (Stufe je Ort)", "", festungOrte, "GetFortLevel") : ""}
    ${regler.map(([n, x]) => zl(`Regler ${n}`, pct(x, 0))).join("")}
    ${num(moralFaktor) ? zl("Wirkung des Unterhalts auf die Moral", `× ${fmt(moralFaktor, 2)}`) : ""}
    ${zl("Kriegsmüdigkeit / max.", `${fmt(L.war_exhaustion ?? lv.war_exhaustion, 2)} / ${fmt(L.curmax_war_exhaustion ?? LM.max_war_exhaustion, 0)}`)}
    ${num(mw) ? zl("Monate seit Krieg", nieKrieg ? "seit Spielbeginn kein Krieg" : fmt(mw, 0)) : ""}</div>
    <p class="hint">Der Spieltext GetFortsLimitInfo nennt „0.00/2.16“, das Militärfenster 1.00/2.16 (= used_fort_limit, wie hier).</p></div>`;

  // Kriege und Katastrophen nur, wenn es welche gibt (Punkt 7)
  // Spieltext „1.. Englisch-Holländischer Krieg“ -> „1. …“ (wie die Kriegskachel, eu5ratgeber/krieg.py)
  const kriege = krieg.length ? `<div class="card"><h3>Kriege</h3>${table([{ t: "Krieg", l: true, f: x => esc(String(x.name || "").replace(/(\d)\.\./, "$1.")) },
    { t: "Dauer", f: x => fmt(x.length, 0) }, { t: "Stillstand", f: x => fmt(x.stalling, 0) }, { t: "Punkte wir", f: x => fmt(x.score, 1) },
    { t: "Punkte Seite", f: x => fmt(x.score_side, 1) }], krieg)}<p class="hint">Je Krieg eine eigene Kachel in dieser Gruppe (Seiten, Armeen, Heerführer,
    Einheitentypen, Schlachten).</p></div>` : "";
  const katast = kat.length ? `<div class="card"><h3>Katastrophen</h3>${table([{ t: "Katastrophe", l: true, f: x => esc(x.name) }, { t: "Tage", f: x => fmt(x.days, 0) }], kat)}</div>` : "";

  return { head, body: `<div class="grid3">${kriege}${katast}${armeen}${marine}${festung}</div>
    <p class="hint">Disziplin, Kampf-Effizienz, Taktiken und Belagerung wie im Militärfenster (Daten-Mod ab 0.16). Rekrutierungskosten je Einheitentyp
      zeigt das Spiel nur in seiner Oberfläche – später aus den Spieldateien (Güterkosten) × Marktpreisen.</p>` };
}

// Bevölkerung (/api/bevoelkerung): Pops und Veränderung je Ursache aus dem Spielstand, Werte/Modifikatoren/Texte live
const CHANGE_ORDER = ["Reproduction", "PromotionIn", "PromotionOut", "DemotionIn", "DemotionOut", "MigrationIn", "MigrationOut",
                      "Assimilation", "Conversion"];
const POP_TEXT = { GetPopGrowthInfo: "Wachstum", GetPopulationCapacityInfo: "Kapazität", GetMigrationInfo: "Wanderung",
  GetLocalMigrationAttractionInfo: "Wanderungsanziehung", GetLiteracyInfo: "Bildung", GetAverageSatisfactionInfo: "Zufriedenheit",
  GetSatisfactionInfo: "Zufriedenheit", GetTotalPopulationInfo: "Bevölkerung", GetPrimaryCulturePercentageInfo: "Anteil Hauptkultur",
  GetPrimaryReligionPercentageInfo: "Anteil Staatsreligion", GetAcceptedCulturesInfo: "Akzeptierte Kulturen", GetCulturalInfo: "Kultur",
  GetReligionInfo: "Religion", GetPopulationInfo: "Bevölkerung", GetLiteracyChangeInfo: "Bildung – Veränderung",
  GetMaxLiteracyInfo: "Bildung – Maximum", GetPopLiteracyInfo: "Bildung der Pop", GetMissingGoodsInfo: "Fehlende Güter",
  GetGoodsInformation: "Güterbedarf", GetFoodsOutputModifiersTooltip: "Nahrung – Ausstoß" };
function bevoelkerung(d, P) {
  const B = d.bev; if (!B || !B.typen) return "";
  const total = B.gesamt_live ?? B.gesamt, ch = B.veraenderung_live ?? B.veraenderung, cn = B.ursachen_namen || {};
  const kinds = [...new Set([...CHANGE_ORDER, ...Object.keys(B.ursachen || {})])].filter(k => k in (B.ursachen || {}));
  const kn = k => cn[k] || k;
  const primary = sum(B.kulturen.filter(k => k.status.includes("Primary")).map(k => k.anteil));
  const staat = sum(B.religionen.filter(r => r.staatsreligion).map(r => r.anteil));
  const voll = B.orte.filter(o => o.ueberbevoelkert);
  // Kopfwerte getrennt zurückgeben: die Kachel „Land und Leute“ setzt ihren Kopf daraus zusammen (Nutzerwunsch 30.09.)
  const kopf = {
    bev: { l: "Bevölkerung (Tsd.)", v: fmt(total, 2), t: trend(ch, 3, 1), s: spark(liveSeries(d, "population_total")),
           title: "Summe der Pops in Tausend (das Spiel zeigt z. B. 188K); Trend = Veränderung im letzten Monat, Linie = Verlauf live" },
    kap: B.kapazitaet ? { l: "Kapazität genutzt", v: `${pct(total / B.kapazitaet, 0)} <i>von ${fmt(B.kapazitaet, 0)}</i>`, bar: total / B.kapazitaet,
           title: "Bevölkerung ÷ Bevölkerungskapazität aller Orte" } : null,
    small: [{ l: "Ø Zufriedenheit", v: pct(B.zufriedenheit, 0) }, { l: "Ø Bildung", v: `${fmt(B.bildung, 1)} %` },
            { l: "Hauptkultur", v: pct(primary, 0) }, { l: "Staatsreligion", v: pct(staat, 0) },
            B.typen[0] && { l: "größter Pop-Typ", v: `${esc(B.typen[0].name)} ${pct(B.typen[0].anteil, 0)}` }],
    warn: [ch < 0 && "Bevölkerung schrumpft", ...voll.map(o => `${esc(o.name)} überbevölkert`)],
  };
  const head = hd({ big: [kopf.bev], small: [kopf.kap, ...kopf.small], warn: kopf.warn });
  const POPC = { peasants: "--c3", laborers: "--c1", burghers: "--c4", clergy: "--c6", soldiers: "--c5", nobles: "--c2", slaves: "--c8", tribesmen: "--c7" };
  const pie = (items, title) => `<div class="card"><h3>${esc(title)}</h3>${pieChart(items, { size: 150 })}</div>`;
  const ST = { Primary: "Hauptkultur", Accepted: "akzeptiert", Tolerated: "toleriert" };   // Pop-Status im Spielstand
  const zus = `<div class="pies">
      ${pie(B.typen.map(t => ({ label: t.name, value: t.groesse, color: POPC[t.typ] || "--c8" })), "Pop-Typen")}
      ${pie(B.kulturen.map((k, i) => ({ label: `${k.name}${k.status.length ? ` (${k.status.map(s => ST[s] || s).join(", ")})` : ""}`, value: k.groesse, color: PALETTE[i % PALETTE.length] })), "Kulturen")}
      ${pie(B.religionen.map((r, i) => ({ label: r.name + (r.staatsreligion ? " ★" : ""), value: r.groesse, color: PALETTE[i % PALETTE.length] })), "Religionen")}
    </div>`;
  const causes = r => kinds.filter(k => r.ursachen?.[k]).map(k => `${kn(k)} ${sgn(r.ursachen[k], 3)}`).join(" · ");
  const veraend = `<div class="grid2"><div class="card"><h3>Veränderung nach Ursache in Tsd. (Spielstand ${esc(B.datum)})</h3>${compo(kinds.map(k => ({ l: kn(k), v: B.ursachen[k] })), 0, 3)}
      ${kv([["Summe (Spielstand, Tsd.)", sgn(B.veraenderung, 3)], ["live (Mod, Tsd.)", sgn(B.veraenderung_live, 3)]])}
      <p class="hint">Auf-/Abstieg und Wanderung innerhalb des Landes heben sich teilweise auf.</p></div>
    <div class="card"><h3>Kulturen und Religionen</h3>${table([{ t: "Kultur", l: true, f: k => esc(k.name) }, { t: "Status", l: true, f: k => esc(k.status.map(s => ST[s] || s).join(", ")) },
      { t: "Größe (Tsd.)", f: k => fmt(k.groesse, 2) }, { t: "Anteil", f: k => pct(k.anteil, 1) },
      { t: "Veränd. (Tsd.)", f: k => sgn(k.veraenderung, 3), cls: k => posneg(k.veraenderung) }], B.kulturen, { scroll: false })}
      ${table([{ t: "Religion", l: true, f: r => esc(r.name) + (r.staatsreligion ? " ★" : "") },
      { t: "Größe (Tsd.)", f: r => fmt(r.groesse, 2) }, { t: "Anteil", f: r => pct(r.anteil, 1) },
      { t: "Veränd. (Tsd.)", f: r => sgn(r.veraenderung, 3), cls: r => posneg(r.veraenderung) }], B.religionen, { scroll: false })}</div></div>`;
  const typCols = [{ t: "Typ", l: true, f: t => esc(t.name) }, { t: "Größe (Tsd.)", f: t => fmt(t.groesse, 2) }, { t: "Anteil", f: t => pct(t.anteil, 1) },
    { t: "Pops (Anzahl)", f: t => String(t.pops) }, { t: "Zufr.", f: t => pct(t.zufriedenheit, 0) }, { t: "Bildung (%)", f: t => fmt(t.bildung, 1) },
    { t: "ohne Anstellung (Tsd.)", f: t => fmt(t.arbeitslos, 2) }, { t: "Veränd. (Tsd.)", f: t => sgn(t.veraenderung, 3), cls: t => posneg(t.veraenderung) },
    ...kinds.map(k => ({ t: `${kn(k)} (Tsd.)`, f: t => t.ursachen?.[k] ? sgn(t.ursachen[k], 3) : "", cls: t => posneg(t.ursachen?.[k]) }))];
  const ortCols = [{ t: "Ort", l: true, f: o => esc(o.name) + (o.ueberbevoelkert ? ` <span class="warn">überbevölkert</span>` : "") },
    { t: "Bev. (Tsd.)", f: o => fmt(o.groesse, 2) }, { t: "Kapazität (Tsd.)", f: o => fmt(o.kapazitaet, 1) },
    { t: "genutzt", f: o => o.auslastung != null ? fmt(o.auslastung, 1) + " %" : "–" },
    { t: "Veränd. (Tsd.)", f: o => sgn(o.veraenderung, 3), cls: o => posneg(o.veraenderung) }, { t: "Wachstum live (%)", f: o => pct(o.wachstum_live, 2) },
    { t: "Anziehung", f: o => fmt(o.anziehung, 2) }, { t: "Beschäft.", f: o => pct(o.beschaeftigung, 0) },
    { t: "Zufr.", f: o => pct(o.zufriedenheit, 0) }, { t: "Bildung (%)", f: o => fmt(o.bildung, 1) },
    { t: "Nahrung +/−", f: o => `${fmt(o.nahrung_prod, 1)} / ${fmt(o.nahrung_verbr, 1)}` }, { t: "Bekehrung / Monat", f: o => fmt(o.bekehrung, 3) },
    { t: "Ursachen", l: true, f: o => `<span class="hint">${esc(causes(o))}</span>` }];
  const M = B.parameter?.modifikatoren || [];
  const landRows = Object.entries(B.parameter?.land || {});
  const provs = Object.entries(B.parameter?.provinzen || {});
  const fv = v => typeof v === "number" ? fmt(v, 3) : esc(String(v));
  const werte = typeof lazy === "function" ? lazy("bev:werte", `${landRows.length} Landeswerte · ${M.length} Modifikatoren ≠ 0 · ${provs.length} Provinzen`, () =>
    `<div class="grid2"><div class="card"><h3>Land</h3><div class="kv">${landRows.map(([k, v]) => `<span>${deL(k)}</span><span>${fv(v)}</span>`).join("")}</div></div>
      <div class="card"><h3>Modifikatoren</h3><div class="kv">${M.map(m => `<span>${esc(m.name)} <span class="code">${esc(m.key)}</span></span><span>${m.prozent ? pct(m.wert, 1) : fmt(m.wert, 3)}</span>`).join("")}</div></div>
      ${provs.map(([p, f]) => `<div class="card"><h3>${esc(p)}</h3><div class="kv">${Object.entries(f).map(([k, v]) => `<span>${deL(k)}</span><span>${fv(v)}</span>`).join("")}</div></div>`).join("")}</div>`) : "";
  const texte = Object.entries(B.texte || {}).flatMap(([bereich, objs]) => Object.entries(objs).map(([o, felder]) =>
    lazy(`bev:t:${bereich}:${o}`, `${esc(ART_TITLE[bereich] || bereich)} ${esc(o)} <span class="hint">${Object.keys(felder).map(f => esc(POP_TEXT[f] || de(f))).join(", ")}</span>`,
      () => Object.entries(felder).map(([f, t]) => `<div class="card" style="margin:6px 0"><h3>${esc(POP_TEXT[f] || de(f))} <span class="code">${esc(f)}</span></h3>${breakdown(t)}</div>`).join(""))));
  const body = sect("Zusammensetzung", zus)
    + sect("Veränderung letzter Monat", veraend + `<div class="card"><h3>je Pop-Typ</h3>${table(typCols, B.typen)}</div>`)
    + sect("Orte", `<div class="card">${table(ortCols, B.orte)}</div>`)
    + (B.wanderung.length ? sect("Wanderungen letzter Monat", table([{ t: "von", l: true, f: w => esc(w.von) },
      { t: "nach", l: true, f: w => esc(w.nach) }, { t: "Typ", l: true, f: w => esc(w.typ) }, { t: "Menge (Tsd.)", f: w => fmt(w.menge, 3) }], B.wanderung)) : "")
    // Aufschlüsselungen ohne eigene Überschrift (Nutzerwunsch 29.09., alle Kacheln) - im Abschnitt der Live-Werte
    + sect("Alle Bevölkerungs-Werte live", werte + (texte.length ? `<div class="card" style="margin-top:14px">${texte.join("")}</div>` : ""))
    + `<p class="hint">Größen in Tausend. Pops, Veränderung und Wanderungen: Spielstand ${esc(B.datum)}. Kapazität, Wachstum live, Anziehung, Beschäftigung, Nahrung,
      Bekehrung, Werte, Modifikatoren und Aufschlüsselungen: Daten-Mod ${esc(B.live_datum || "–")}.</p>`;
  return { head, body, kopf };
}

// Kopfzeile: grundlegende Werte, immer sichtbar (Nutzerwunsch 29.09.). Live-Werte (Mod) wo vorhanden, Saldo aus dem
// neuesten Spielstand (live gibt es nur geschätztes Einkommen und Reglerkosten, deren Differenz nicht genau passt).
const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
const KURZ_STAND = { crown_estate: "Krone", nobles_estate: "Adel", clergy_estate: "Klerus", burghers_estate: "Bürger",
                     peasants_estate: "Gemeine", dhimmi_estate: "Dhimmi", tribes_estate: "Stämme", cossacks_estate: "Kosaken" };
const monatJahr = datum => { const [y, m] = String(datum || "").split(".").map(Number); return y && m ? `${MONATE[m - 1]} ${y}` : "–"; };
function kopfzeile(d, P) {
  const lv = P.lv, last = d.punkte.at(-1) || {}, L = d.live || [];
  const datum = lv.jahr && lv.jahr > (last.jahr ?? 0) ? lv.datum : last.datum;
  const kz = (label, value, { title = "", cls = "", bar = "" } = {}) => `<div class="kz ${cls}"${title ? ` title="${esc(title)}"` : ""}><small>${esc(label)}</small><b>${value}</b>${bar}</div>`;
  // kleiner Balken unter dem Wert: Anteil 0..1; mitte = Bereich −1..+1 mit Null in der Mitte (Stabilität, Prestige)
  const kbar = (x, mitte = false) => {
    if (!num(x)) return "";
    const v = Math.max(mitte ? -1 : 0, Math.min(1, x));
    const st = !mitte ? `width:${v * 100}%` : v >= 0 ? `left:50%;width:${v * 50}%` : `left:${50 + v * 50}%;width:${-v * 50}%`;
    return `<span class="mbar kbar${mitte ? " mitte" : ""}"><i class="${v < 0 ? "neg" : ""}" style="${st}"></i></span>`;
  };
  // Bevölkerung: Wachstum letzter Monat, Veränderung gegenüber vor 12 Monaten (live-Reihe)
  const pop = lv.population_total, popNow = L.at(-1);
  const [py, pm] = String(popNow?.datum || "").split(".").map(Number);
  const vor12 = L.find(r => String(r.datum || "").startsWith(`${py - 1}.${pm}.`)) || null;
  const d12 = vor12 && num(vor12.population_total) && num(pop) ? pop - vor12.population_total : null;
  const t12 = d12 == null ? "" : `<i class="${d12 >= 0 ? "pos" : "neg"}">12 M. ${d12 >= 0 ? "▲" : "▼"} ${sgn(d12, 2)}</i>`;
  // Macht der Stände als gestapelter Balken
  const names = Object.fromEntries((P.A.staende || []).map(e => [e.stand, e.name]));
  const ests = Object.keys(lv).filter(k => /^power_\w+_estate$/.test(k) && lv[k] > 0).map(k => [k.slice(6), lv[k]]).sort((a, b) => b[1] - a[1]);
  // Balken mit fetten Zahlen, darunter alle Namen in einer Reihe (Reihenfolge wie im Balken), mittig unter dem Balken
  const w = v => `${(v * 100).toFixed(1)}%`;
  const stbar = ests.length ? `<div title="${esc(ests.map(([e, v]) => `${names[e] || e} ${pct(v, 1)}`).join(" · "))}">
    <div class="stbar">${ests.map(([e, v]) => `<i style="width:${w(v)};background:var(${ESTATE_COLOR[e] || "--c8"})">${v >= 0.06 ? pct(v, 0) : ""}</i>`).join("")}</div>
    <div class="stnamen">${ests.map(([e]) => `<span style="color:var(${ESTATE_COLOR[e] || "--c8"})">${esc(KURZ_STAND[e] || names[e] || e)}</span>`).join(`<i>·</i>`)}</div></div>` : "–";
  // Glaube: Staatsreligion (Spielstand-Pops, sonst Mod)
  const rel = (d.bev?.religionen || []).find(r => r.staatsreligion)?.name || Object.values(d.alles?.werte?.religion || {})[0]?.name || "–";
  // Heimatmarkt: unser Anteil an der Händlermacht, Handelseinkommen (beides Spielstand, wie in den Kacheln)
  const m = P.A.markt || {}, hs = m.haendler || [], totH = sum(hs.map(x => x.macht)), own = hs.find(x => x.tag === d.meta.tag);
  const lm = (P.A.wirtschaft || {}).letzter_monat || {}, aland = Object.values(d.alles?.werte?.land || {})[0] || {};
  const legit = lv.legitimacy ?? aland.legitimacy;
  // Maxima laut Spiel (curmax_legitimacy / curmax_prestige = 100; stability_percentage = stability ÷ 100, geprüft 29.09.)
  const stab = lv.stability ?? aland.stability, prest = lv.prestige ?? aland.prestige;
  const S = spielWerte(d);                                        // Werte wie im Wirtschaftsfenster (Mod), sonst null
  const legMax = aland.curmax_legitimacy || 100, prMax = aland.curmax_prestige || 100;
  // 1.4: Politischer Einfluss (Kopfleiste des Spiels); Balken = Anteil am Höchstwert laut Spiel (political_influence_percentage)
  const pe = lv.political_influence ?? aland.political_influence ?? aland.cur_political_influence;
  const peAnteil = aland.political_influence_percentage ?? (num(pe) && aland.curmax_political_influence ? pe / aland.curmax_political_influence : null);
  const peMon = aland.monthly_political_influence;
  return [
    kz("Datum", monatJahr(datum), { title: `Spieldatum ${datum}` }),
    kz("Land", `${esc(d.meta.land)} <span class="u">${esc(d.meta.tag)}</span>`, { cls: "land" }),
    kz("Stabilität", `<span class="${stab < 0 ? "neg" : ""}">${fmt(stab, 1)}</span>`, { bar: kbar(num(stab) ? stab / 100 : null, true),
       title: "live; Balken: Mitte = 0, rechts bis +100, links negativ (Unruhe)" }),
    kz("Kontrolle", pct(lv.control_avg ?? aland.average_control, 0), { bar: kbar(lv.control_avg ?? aland.average_control),
       title: "Ø Kontrolle der Orte (live)" }),
    kz("Legitimität", fmt(legit, 0), { bar: kbar(num(legit) ? legit / legMax : null), title: `live; Balken = Anteil am Maximum ${fmt(legMax, 0)}` }),
    kz("Prestige", `<span class="${prest < 0 ? "neg" : ""}">${fmt(prest, 1)}</span>`, { bar: kbar(num(prest) ? prest / prMax : null, true),
       title: `live; Balken: Mitte = 0, rechts bis Maximum ${fmt(prMax, 0)}, links negativ` }),
    num(pe) ? kz("Politischer Einfluss", `${fmt(pe, 1)}${num(peMon) ? ` <i class="${posneg(peMon)}">${sgn(peMon, 2)}/M.</i>` : ""}`,
       { bar: kbar(peAnteil), title: `live (ab 1.4)${num(peAnteil) ? `; Balken = ${pct(peAnteil, 0)} des Höchstwerts` : ""}; /M. = Veränderung je Monat` }) : "",
    kz("Gold", fmt(lv.gold ?? last.gold, 0), { title: "live" }),
    S ? kz("Saldo / Monat", `<span class="${posneg(S.saldo)}">${sgn(S.saldo, 2)}</span>`,
           { bar: `<span class="hku">Spielstand ${sgn(last.saldo, 2)}</span>`, title: `wie im Wirtschaftsfenster (Daten-Mod ${S.datum}); klein: Spielstand ${last.datum}` })
      : kz("Saldo / Monat", `<span class="${posneg(last.saldo)}">${sgn(last.saldo, 2)}</span>`, { title: `Spielstand ${last.datum}` }),
    kz("Marktmacht Heimatmarkt", own && totH ? `${pct(own.macht / totH, 1)} <span class="u">${esc(m.zentrum || "")}</span>` : "keine Händler",
       { title: `Anteil an der Händlermacht im Markt ${m.zentrum || ""} (Spielstand ${last.datum})` }),
    S && num(S.handel) ? kz("Handelseinkommen / Monat", `<span class="${posneg(S.handel)}">${fmt(S.handel, 2)}</span>`,
           { bar: `<span class="hku">Spielstand ${fmt(lm.monthly_trade_balance, 2)}</span>`,
             title: `wie im Wirtschaftsfenster: Gewinn der Routen × Modifikator Handelseinnahmen (Daten-Mod ${S.datum}); klein: Spielstand ${last.datum}` })
      : kz("Handelseinkommen / Monat", `<span class="${posneg(lm.monthly_trade_balance)}">${fmt(lm.monthly_trade_balance ?? lv.trade_income, 2)}</span>`,
           { title: `Spielstand ${last.datum} (monthly_trade_balance)` }),
    kz("Orte / Entwicklung", `${fmt(lv.locations, 0)} · ${fmt(lv.development_total, 0)}`),
    kz("Bevölkerung (Tsd.)", `${fmt(pop, 1)} <i class="${posneg(lv.population_change)}">${sgn(lv.population_change, 3)}/M.</i>${t12}`,
       { title: "Wachstum letzter Monat; Veränderung gegenüber vor 12 Monaten (live)" }),
    kz("Mannstärke", `${fmt(lv.manpower, 2)} <span class="u">/ ${fmt(lv.manpower_max, 2)}</span>`, { title: "verfügbar / Maximum (live)" }),
    kz("Seeleute", `${fmt(lv.sailors, 2)} <span class="u">/ ${fmt(lv.sailors_max, 2)}</span>`, { title: "verfügbar / Maximum (live)" }),
    kz("Macht der Stände", stbar),
    kz("Glaube", `${esc(rel)} · ${pct(lv.religious_unity, 0)} <span class="u">Einigkeit</span> · ${fmt(lv.religious_influence, 1)} <span class="u">Einfluss</span>`),
  ].join("");
}

// Seitenleiste: Links geöffneter Kacheln hervorheben (toggle bubbelt nicht -> einmal in der Capture-Phase am Dokument)
const markOpen = () => document.querySelectorAll("#toc a[data-open]").forEach(a => a.classList.toggle("auf", !!document.getElementById(a.dataset.open)?.open));
// Inhalt einer Kachel mit lazy-Inhalt beim ersten Öffnen bauen
function fillSec(el) {
  const c = el.open && el.querySelector(":scope > .body > .lazyc[data-lzsec]");
  if (!c || c.dataset.done) return;
  c.innerHTML = (typeof LAZY !== "undefined" && LAZY.get("sec:" + c.dataset.lzsec)?.()) || "";
  c.dataset.done = "1";
  if (typeof fillLazy === "function") fillLazy(c);
  rememberToggles(c);
}
document.addEventListener("toggle", e => {
  if (!e.target.matches?.("details.sec")) return;
  const el = e.target;
  fillSec(el);
  markOpen();
  if (typeof equalizeTiles === "function") equalizeTiles();
  // Geöffnete Kachel springt an Position 1 ihres Bereichs (CSS order, Nutzerwunsch 30.09.). Nach einem Klick auf den Kachelkopf
  // dorthin scrollen, wenn sie aus dem Sichtfeld gerutscht ist – erst nach equalizeTiles (ändert die Höhe der übrigen Kacheln);
  // nicht beim Wiederherstellen offener Kacheln nach dem Neuladen (kein Klick)
  if (el.dataset.klick) {
    delete el.dataset.klick;
    if (el.open) setTimeout(() => {
      const hh = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--hh")) || 120;
      const top = el.getBoundingClientRect().top;
      if (top < hh || top > innerHeight - 80) el.scrollIntoView({ block: "start" });
    }, 0);
  }
}, true);
document.addEventListener("click", e => {
  const el = e.target.closest?.("details.sec > summary")?.parentElement;
  if (el) el.dataset.klick = "1";
});
// Verweis auf eine Kachel (z. B. Ortsname in der Orte-Kachel, Nutzerwunsch 01.10.): Kachel öffnen, Zustand merken, hinspringen
document.addEventListener("click", e => {
  const a = e.target.closest?.("a[data-oeffne]");
  const el = a && document.getElementById(a.dataset.oeffne);
  if (!el) return;
  e.preventDefault();
  if (el.open) el.scrollIntoView({ block: "start" });
  else { el.dataset.klick = "1"; el.open = true; }
  OPEN["sec:" + el.id] = true;
  store.set("rg_offen", JSON.stringify(Object.fromEntries(Object.entries(OPEN).filter(([k]) => k.startsWith("sec:")))));
});

// ---------------------------------------------------------------- Seite
function render(d) {
  SECTIONS.length = 0;
  const P = prepare(d), L = d.live || [], lv = L.at(-1);
  $("#stand").textContent = `${d.meta.land} (${d.meta.tag}) · Spielstand ${d.meta.datum} · ${d.punkte.length} Momentaufnahme(n)` + (lv ? ` · live bis ${lv.datum}` : "");
  $("#kopf").innerHTML = kopfzeile(d, P);
  const liveDt = P.LD.extra_datum || P.LD.datum || "";
  const sub = liveDt ? "live " + liveDt : "";
  // live.js (Mod ab 0.12): weitere Kopfwerte, Aufschlüsselungen und alle Live-Daten je Kachel
  const L2 = typeof withLive === "function" ? withLive : (id, part) => part;
  if (typeof LAZY !== "undefined") LAZY.clear();
  P.liveNames = typeof liveNames === "function" ? liveNames(d, P) : {};
  if (typeof DE_NAMES !== "undefined") Object.assign(DE_NAMES, (P.W.namen || {}).gueter || {}, (P.W.namen || {}).gebaeude || {},
    d.pop_namen || {}, Object.fromEntries((P.A.staende || []).map(e => [e.stand, e.name])));
  // Kacheln je Gruppe (design.js GROUPS/THEME): Staat und Regierung, Diplomatie und Militär, Wirtschaft, Handel, Einzelne Orte, Auswertung
  // Märkte: je Markt mit eigenen Orten oder Händlern eine Kachel (Spielstand ab Format 5), sonst nur der Heimatmarkt
  const maerkte = (P.A.maerkte || []).length ? P.A.maerkte : (P.A.markt ? [{ ...P.A.markt, heimat: true }] : []);
  for (const m of maerkte) if (!m.heimat) THEME[`markt_${m.id}`] = { ...THEME.markt, icon: "⚓" };
  // Fremde Märkte in Reichweite (Nutzerwunsch 02.10.): Liste aus dem Daten-Mod (ab 0.17, Spieltrigger in_trade_range_of), Marktbild aus
  // dem Spielstand (aktuell.fremde_maerkte); welche als normale Marktkachel erscheinen, wählt der Nutzer (localStorage). Märkte mit
  // eigenen Orten oder Händlern bleiben unter Handel und fehlen in der Auswahl.
  const eigeneM = new Set(maerkte.map(m => m.id));
  const fmListe = (d.reichweite || []).filter(x => !eigeneM.has(x.id));
  const fmView = Object.fromEntries((P.A.fremde_maerkte || []).map(m => [m.id, m]));
  const fmWahl = fremdeWahl().filter(id => fmListe.some(x => x.id === id));
  for (const id of fmWahl) THEME[`markt_${id}`] = { ...THEME.markt, icon: "🌐", group: "fremdmaerkte" };
  // Orte: je Ort eine Kachel (Gruppe "Einzelne Orte"), sortiert nach Provinz, dann Bevölkerung
  const orteSort = typeof ortTile === "function" ? P.orte.slice().sort((a, b) => String(a.w?.provinz_name || "").localeCompare(String(b.w?.provinz_name || ""))
    || (b.bev ?? 0) - (a.bev ?? 0)) : [];
  for (const o of orteSort) THEME[`ort_${o.id}`] = { icon: "📍", color: "--c5", group: "einzelorte" };
  // je laufendem Krieg eine Kachel nach „Militär und Kriege“ (Nutzerwunsch 25.10.)
  for (const w of d.kriege || []) THEME[`krieg_${w.id}`] = { icon: "⚔️", color: "--c5", group: "staat" };
  const tiles = {
    empfehlungen: () => sec("empfehlungen", "Empfehlungen", empfehlungen(d, P), { sub }),     // ganz oben (Nutzerwunsch 02.10.)
    wirtschaftsplan: () => sec("wirtschaftsplan", "Wirtschaftsplan", wirtschaftsplanKachel(d, P), { sub: "Spielstand " + d.meta.datum }),
    // nach dem Wirtschaftsplan, immer sichtbar (Nutzerwunsch 31.10.): Einstellungen am Anfang je Schwerpunkt – startstrategie.js
    startstrategie: () => typeof startstrategieKachel === "function" ? sec("startstrategie", "Startstrategie", startstrategieKachel(d),
      { sub: ["Spielstand " + d.meta.datum, d.startstrategie?.mod_datum && "Mod " + d.startstrategie.mod_datum].filter(Boolean).join(" · ") }) : "",
    finanzen: () => sec("finanzen", "Finanzen", L2("finanzen", finanzen(d, P), d, P), { sub: "Spielstand " + d.meta.datum }),
    produktion: () => sec("produktion", "Produktion", L2("produktion", produktion(d, P), d, P)),   // neben Finanzen (Nutzerwunsch 29.09.)
    handel: () => sec("handel", "Handel", L2("handel", handel(d, P), d, P), { sub }),
    ...Object.fromEntries(maerkte.map(m => [m.heimat ? "markt" : `markt_${m.id}`, () => sec(m.heimat ? "markt" : `markt_${m.id}`,
      `${m.heimat ? "Heimatmarkt" : "Markt"} ${m.zentrum || m.id}`, L2("markt", markt(d, P, m), d, P, { markt: m.id }),
      { sub: `Spielstand ${d.meta.datum}${m.eigene_orte ? ` · ${m.eigene_orte} eigene Orte` : " · nur Händler"}` })])),
    ...Object.fromEntries(fmWahl.map(id => {
      const m = fmView[id], x = fmListe.find(y => y.id === id), nm = String(m?.zentrum || x.name).replace(/^Markt von /, "");
      return [`markt_${id}`, () => m ? sec(`markt_${id}`, `Markt ${nm}`, L2("markt", markt(d, P, m), d, P, { markt: id }),
        { sub: `Spielstand ${d.meta.datum} · in Handelsreichweite` })
        : sec(`markt_${id}`, `Markt ${nm}`, { head: hd({ big: [{ l: "Marktbild", v: "folgt" }] }),
          body: `<p class="hint">In Handelsreichweite laut Daten-Mod; das Marktbild (Güter, Händler, Mitglieder) kommt aus dem Spielstand. Der Ratgeber
            liest den letzten Spielstand dafür neu ein, sobald die Liste da ist – sonst mit dem nächsten Autosave.</p>` },
          { sub: "in Handelsreichweite" })];
    })),
    gueter: () => sec("gueter", "Güter", L2("gueter", gueter(d, P), d, P)),
    // Land und Bevölkerung zusammen als „Land und Leute“, Forschung als eigene Kachel (Nutzerwunsch 30.09.)
    land: () => sec("land", "Land und Leute", L2("land", landUndLeute(d, P), d, P),
      { sub: [d.bev && "Spielstand " + d.bev.datum, lv && "live " + lv.datum].filter(Boolean).join(" · ") }),
    regierung: () => sec("regierung", "Regierung und Gesellschaft", L2("regierung", regierung(d, P), d, P), { sub }),   // Position 2 (30.09.)
    // zwischen Regierung und Forschung (Nutzerwunsch 04.10.)
    krankheiten: () => sec("krankheiten", "Krankheiten", krankheiten(d, P), { sub: ["Spielstand " + d.meta.datum, sub].filter(Boolean).join(" · ") }),
    forschung: () => sec("forschung", "Forschung", L2("forschung", forschung(d, P), d, P), { sub }),
    orte: () => sec("orte", "Orte", orte(d, P), { sub: ["Spielstand " + d.meta.datum, sub].filter(Boolean).join(" · ") }),
    staende: () => sec("staende", "Stände und Privilegien", L2("staende", staende(d, P), d, P), { sub }),
    religion: () => sec("religion", "Religion, Kultur und Kunst", L2("religion", religion(d, P), d, P), { sub }),   // Kultur und Kunst seit 01.10.
    diplomatie: () => sec("diplomatie", "Diplomatie und Untertanen", L2("diplomatie", diplomatie(d, P), d, P), { sub }),
    // nach der Diplomatie (Nutzerwunsch 25.10.): wann lohnt ein Krieg?
    nachbarn: () => sec("nachbarn", "Nachbarn und Kriegsgelegenheiten", nachbarnKachel(d),
      { sub: [d.nachbarn?.fremd_datum && "Mod " + d.nachbarn.fremd_datum, d.nachbarn?.datum_spielstand && "Spielstand " + d.nachbarn.datum_spielstand].filter(Boolean).join(" · ") }),
    // nach den Nachbarn (Nutzerwunsch 30.10.): welche größeren Länder gründen und wie – gruendung.js
    gruendung: () => typeof gruendungKachel === "function" ? sec("gruendung", "Ländergründung", gruendungKachel(d),
      { sub: ["Spielstand " + d.meta.datum, sub].filter(Boolean).join(" · ") }) : "",
    mehr: () => sec("mehr", "Militär und Kriege", L2("mehr", militaer(d, P), d, P), { sub }),   // Kredite in den Finanzen (01.10.)
    ...Object.fromEntries((d.kriege || []).map(w => [`krieg_${w.id}`, () => sec(`krieg_${w.id}`, `Krieg: ${w.name}`, kriegKachel(d, w),
      { sub: [w.datum_live && "Mod " + w.datum_live, w.datum_spielstand && "Spielstand " + w.datum_spielstand].filter(Boolean).join(" · ") })])),
    verlauf: () => sec("verlauf", "Verlauf", verlauf(d, P), { sub: `${d.punkte.length} Momentaufnahmen · ${(d.live || []).length} Live-Monate` }),
    entscheidungen: () => sec("entscheidungen", "Entscheidungen und ihre Wirkung", entscheidungen(d, P)),
    modifikatoren: () => sec("modifikatoren", "Modifikatoren", modifikatoren(d, P), { sub }),            // aus der Religionskachel (01.10.)
    ...Object.fromEntries(orteSort.map(o => [`ort_${o.id}`, () => sec(`ort_${o.id}`, o.name, ortTile(d, P, o),
      { sub: [o.w?.provinz_name, o.w?.rang_name].filter(Boolean).map(esc).join(" · ") })])),
  };
  const groups = typeof GROUPS !== "undefined" ? GROUPS : [["", ""]];
  const tocGroups = [];
  $("#main").innerHTML = groups.map(([g, gt]) => {
    const ids = Object.keys(tiles).filter(id => !g || (THEME[id] || {}).group === g);
    const n0 = SECTIONS.length, html = ids.map(id => tiles[id]()).join("");
    tocGroups.push([gt, SECTIONS.slice(n0)]);
    const extra = g === "fremdmaerkte" ? fremdeAuswahl(fmListe, fmWahl, fmView) : "";
    return html || extra ? (gt ? `<h2 class="grp">${esc(gt)}</h2>` : "") + extra + (html ? `<div class="gridT">${html}</div>` : "") : "";
  }).join("");
  if (typeof fillLazy === "function") fillLazy($("#main"));
  document.querySelectorAll("details.sec[open]").forEach(fillSec);
  // Seitenleiste: Gruppen untereinander, geöffnete Kacheln hervorgehoben; "Alle Daten" (browser.js) am Ende
  const link = (id, t) => `<a href="#${id}" data-open="${id}" style="--th: var(${(THEME[id] || {}).color || "--accent"})">${(THEME[id] || {}).icon || "🗂️"} ${esc(t.split(" und ")[0])}</a>`;
  $("#toc").innerHTML = tocGroups.filter(([, s]) => s.length).map(([gt, s]) => (gt ? `<span class="tg">${esc(gt)}</span>` : "")
    + s.map(([id, t]) => link(id, t)).join("")).join("") + `<span class="tg">Daten</span>${link("alle", "Alle Daten")}`;
  rememberToggles(document);
  // Klick in der Leiste: geschlossene Kachel öffnen und hinspringen, offene Kachel wieder schließen (Zustand merken)
  document.querySelectorAll("#toc a[data-open]").forEach(a => a.addEventListener("click", ev => {
    const el = document.getElementById(a.dataset.open);
    if (!el) return;
    if (el.open) { ev.preventDefault(); el.open = false; } else el.open = true;
    OPEN["sec:" + el.id] = el.open;
    store.set("rg_offen", JSON.stringify(Object.fromEntries(Object.entries(OPEN).filter(([k]) => k.startsWith("sec:")))));
    markOpen();
  }));
  markOpen();
  // Sprungziel unter der (festen) Kopfzeile
  document.documentElement.style.setProperty("--hh", ($("header")?.offsetHeight || 120) + "px");
  if (typeof equalizeTiles === "function") equalizeTiles();
  $("#markform")?.addEventListener("submit", async ev => {
    ev.preventDefault();
    const f = new FormData(ev.target);
    const r = await fetch("/api/markierung", { method: "POST", body: JSON.stringify({ partie: d.meta.partie_id, datum: f.get("datum"), text: f.get("text") }) });
    if (!r.ok) alert((await r.json()).fehler || "Fehler");
    load();
  });
  document.querySelectorAll("[data-del]").forEach(b => b.addEventListener("click", async () => {
    if (!confirm("Markierung löschen?")) return;
    await fetch("/api/markierung/loeschen", { method: "POST", body: JSON.stringify({ id: b.dataset.del }) });
    load();
  }));
}

// ---------------------------------------------------------------- Fremde Märkte in Reichweite: Auswahl (Nutzerwunsch 02.10.)
let LAST_D = null;
const fremdeWahl = () => { try { return (JSON.parse(store.get("rg_fremde_maerkte") || "[]") || []).map(Number); } catch (e) { return []; } };
function fremdeAuswahl(liste, wahl, view) {
  if (!liste.length) return `<p class="hint fmwahl">Welche Märkte in Handelsreichweite liegen, meldet erst der Daten-Mod ab 0.17 (Spieltrigger
    in_trade_range_of) – danach stehen sie hier zum Zuschalten als normale Marktkachel.</p>`;
  const offen = store.get("rg_fmwahl_offen") === "1";
  return `<details class="fmwahl"${offen ? " open" : ""}><summary>Märkte wählen – ${wahl.length} von ${liste.length} gezeigt</summary>
    <div class="fmliste">${liste.map(x => `<label><input type="checkbox" data-fm="${x.id}"${wahl.includes(x.id) ? " checked" : ""}>
      ${esc(String(x.name).replace(/^Markt von /, ""))}${num(x.handelsvorteil) && x.handelsvorteil > 0 ? ` <i>Handelsvorteil ${fmt(x.handelsvorteil, 2)}</i>` : ""}${view[x.id] ? "" : " <i>Marktbild folgt</i>"}</label>`).join("")}</div>
    <button data-fm-alle>alle</button> <button data-fm-keine>keine</button>
    <p class="hint">Liste laut Daten-Mod (Märkte in Handelsreichweite, ohne die eigenen Marktkacheln unter Handel); Auswahl bleibt in diesem Browser.</p></details>`;
}
// Wirtschaftsplan: Schwerpunkt wählen (bleibt in diesem Browser), Kachel neu zeichnen
document.addEventListener("change", e => {
  if (e.target.id !== "wp-fokus" || !LAST_D) return;
  store.set("rg_wp_fokus", e.target.value);
  const y = window.scrollY;
  render(LAST_D);
  if (typeof equalizeTiles === "function") equalizeTiles();
  window.scrollTo(0, y);
});
function fremdeSetzen(ids) {
  store.set("rg_fremde_maerkte", JSON.stringify(ids));
  if (!LAST_D) return;
  const y = window.scrollY;
  render(LAST_D);
  if (typeof equalizeTiles === "function") equalizeTiles();
  window.scrollTo(0, y);
}
document.addEventListener("change", e => {
  const c = e.target.closest?.("input[data-fm]");
  if (!c) return;
  const w = new Set(fremdeWahl());
  if (c.checked) w.add(+c.dataset.fm); else w.delete(+c.dataset.fm);
  fremdeSetzen([...w]);
});
document.addEventListener("click", e => {
  const b = e.target.closest?.("button[data-fm-alle], button[data-fm-keine]");
  if (!b) return;
  fremdeSetzen(b.hasAttribute("data-fm-alle") ? [...document.querySelectorAll("input[data-fm]")].map(c => +c.dataset.fm) : []);
});
document.addEventListener("toggle", e => {
  if (e.target.classList?.contains("fmwahl")) store.set("rg_fmwahl_offen", e.target.open ? "1" : "0");
}, true);

async function loadPartien() {
  const ps = await (await fetch("/api/partien")).json();
  const sel = $("#partie"), keep = sel.value || store.get("partie");
  sel.innerHTML = ps.map(p => `<option value="${esc(p.id)}">${esc(p.name)} – ${esc(p.land)} (bis ${esc(p.bis)}, ${p.anzahl})</option>`).join("");
  if (ps.some(p => p.id === keep)) sel.value = keep;
  if (!ps.length) $("#main").innerHTML = `<div class="empty">Noch keine Spielstände eingelesen. Startoption <code>-force_text_save</code> setzen und speichern.</div>`;
  return ps.length;
}

// Spiel-Update erkannt (24.10.): Server vergleicht Steam-Build und die vom Mod überdeckte Spieldatei mit dem Stand beim Bau
async function pruefung() {
  try {
    const p = await (await fetch("/api/pruefung")).json(), el = $("#pruefung");
    const w = p.warnungen || [];
    el.hidden = !w.length;
    el.innerHTML = w.map(x => `<div class="${esc(x.stufe)}"><b>⚠ ${x.stufe === "hoch" ? "Spiel-Update – Daten-Mod veraltet" : "Spiel und Mod prüfen"}:</b>
      ${esc(x.text)}${x.tun ? `<br>${esc(x.tun).replace(/python tools\/[\w.]+(?: --\w+)?/g, m => `<code>${m}</code>`)}` : ""}</div>`).join("");
  } catch (e) { /* Server älter oder kurz weg */ }
}

async function load() {
  const pid = $("#partie").value; if (!pid) return;
  store.set("partie", pid);
  const y = window.scrollY;
  const q = "?partie=" + encodeURIComponent(pid);
  const [r, rb, ra] = await Promise.all([fetch("/api/daten" + q), fetch("/api/bevoelkerung" + q), fetch("/api/alles" + q)]);
  if (r.ok) {
    const d = await r.json();
    d.bev = rb.ok ? await rb.json() : null;
    d.alles = ra.ok ? await ra.json() : null;
    LAST_D = d;
    render(d);
    if (typeof renderBrowser === "function") renderBrowser(d.meta.partie_id);   // browser.js: alle Daten
    if (typeof techbaumNeu === "function") techbaumNeu(d);                      // techbaum.js: neuer Stand -> Ansicht Fortschritte
    if (typeof equalizeTiles === "function") equalizeTiles();
    window.scrollTo(0, y);
  }
}

$("#partie").addEventListener("change", load);
$("#reload").addEventListener("click", async () => { await loadPartien(); load(); });
(async () => { pruefung(); if (await loadPartien()) load(); })();
setInterval(async () => {
  hallo();
  pruefung();                                                  // Steam kann bei offenem Ratgeber aktualisieren                                                     // auch wenn neu gezeichnet wird: nach einem Server-Neustart wieder angemeldet
  if (document.activeElement?.name === "text") return;        // nicht beim Tippen einer Markierung neu aufbauen
  await loadPartien(); load();
}, 60000);
// Server endet mit dem Tab (Nutzerwunsch 02.10.): anmelden beim Öffnen und jede Minute, abmelden beim Schließen/Neuladen
// (pagehide + sendBeacon kommt auch beim Schließen an). Der Server wartet nach einer Abmeldung 15 s auf eine neue Anmeldung.
const TAB_ID = Math.random().toString(36).slice(2) + Date.now().toString(36);
function hallo() { fetch("/api/hallo", { method: "POST", body: JSON.stringify({ id: TAB_ID }) }).catch(() => {}); }
hallo();
addEventListener("pagehide", () => navigator.sendBeacon("/api/tschuess", JSON.stringify({ id: TAB_ID })));
