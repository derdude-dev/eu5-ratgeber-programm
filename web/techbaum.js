"use strict";
// Fortschritte (Techbaum, Nutzerwunsch 30.10.): eigene Ansicht #techbaum, #techbaum/<schlüssel> – Rahmen siehe ansichten.js.
// „ingame ist die suche nicht sinnvoll und die darstellung auch nicht so übersichtlich“: alle Fortschritte des Spiels je Zeitalter,
// gruppiert nach Thema (Spieldatei) und Stufe im Baum, Status farbig, Suche über Name, Schlüssel, Beschreibung, Wirkungen und
// Freischaltungen; Detail mit Wirkungen, Freischaltungen, Bedingungen, Vorgängern bis zur Wurzel, Nachfolgern und dem Weg dorthin.
// Oben der Vorschlag zum Schwerpunkt des Wirtschaftsplans (localStorage rg_wp_fokus, in beide Richtungen synchron).
// Daten: /api/techbaum?partie=… (eu5ratgeber/techbaum.py: Spieldateien + Stand der Partie), Vorschlag aus /api/daten
// (LAST_D.techbaum_vorschlag, history.series). Nutzt Helfer aus app.js ($, esc, fmt, store, wpFokus, render) und design.js (num).
const TB = { d: null, pid: null, sig: null, laedt: null, el: null, sel: "", idx: {}, vokabel: null, fokusNeu: false,
             f: (() => { try { return JSON.parse(store.get("rg_tb_filter") || "{}"); } catch (e) { return {}; } })() };
const TB_LISTE = 250;                     // so viele Suchtreffer zeigt die Liste
const TB_ST = { e: "erforscht", j: "jetzt erforschbar", v: "Voraussetzungen fehlen", s: "späteres Zeitalter",
                n: "nicht für uns", u: "unklar" };
const TB_ST_LANG = { e: "laut Spielstand erforscht", j: "alle Voraussetzungen erforscht, Zeitalter erreicht, Bedingungen erfüllt",
                     v: "Vorgänger fehlen oder Bedingung „allow“ (z. B. Institution) noch nicht erfüllt",
                     s: "gehört zu einem Zeitalter, das noch nicht begonnen hat",
                     n: "Bedingung (potential, Regierungsform, Landestyp oder Konzentration) für unser Land nicht erfüllt",
                     u: "Bedingung mit Teilen, die der Ratgeber aus dem Spielstand nicht prüfen kann" };

// Suchform wie im Wiki: klein, Umlaute ausgeschrieben (ä = ae …), sonstige Akzente weg
const tbFold = s => String(s ?? "").toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue")
  .replace(/ß/g, "ss").normalize("NFD").replace(/[̀-ͯ]/g, "");
const tbStatus = k => TB.d?.status?.[k] || "u";
const tbA = k => TB.d?.fortschritte?.[k];
const tbAlter = i => TB.d?.zeitalter?.[i] || {};
const tbFilterSpeichern = () => store.set("rg_tb_filter", JSON.stringify(TB.f));

// Zurück zum Ratgeber nach einem Schwerpunktwechsel hier: Kacheln (Wirtschaftsplan, Empfehlungen, Forschung) neu zeichnen
addEventListener("hashchange", () => {
  if (!TB.fokusNeu || aktuelleAnsicht() || typeof LAST_D === "undefined" || !LAST_D) return;
  TB.fokusNeu = false;
  const y = window.scrollY;
  render(LAST_D);
  if (typeof equalizeTiles === "function") equalizeTiles();
  window.scrollTo(0, y);
});

// app.js load() nach jedem Neuladen der Daten (alle 60 s): neuer Spielstand oder andere Partie -> neu holen. Ein neuer Mod-Monat
// ändert nur die laufende Forschung; sie kommt mit /api/daten (techbaum_vorschlag.laufend) – sonst lud die offene Ansicht bei
// laufendem Spiel fast jede Minute ~3 MB neu und klappte die Zeitalter zu (Prüfer 30.10.)
function techbaumNeu(d) {
  if (!TB.el?.dataset.built) return;
  const sig = `${d.meta.partie_id}|${d.meta.datum}`, alt = TB.sig;
  TB.sig = sig;
  // erstes Laden der Seite: die Ansicht hat schon selbst geholt – nur bei anderer Partie neu
  if ((alt && alt !== sig) || (TB.pid && TB.pid !== d.meta.partie_id)) {
    TB.d = null;
    if (aktuelleAnsicht()?.id === "techbaum") tbLaden().then(() => { tbDetail(); tbMarkiere(); });
  } else if (TB.d && TB.pid === d.meta.partie_id && d.techbaum_vorschlag?.laufend) {
    TB.d.laufend = { ...TB.d.laufend, ...d.techbaum_vorschlag.laufend };
  }
  if (aktuelleAnsicht()?.id === "techbaum") tbVorschlag();
}

async function tbLaden() {
  const pid = $("#partie")?.value || store.get("partie");
  if (!pid) {                                   // Partienliste kommt noch (app.js loadPartien)
    await new Promise(r => setTimeout(r, 400));
    return tbLaden();
  }
  if (TB.d && TB.pid === pid) return;
  if (TB.laedt) return TB.laedt;
  TB.laedt = (async () => {
    $("#tb-liste").innerHTML = `<div class="empty">Lade Fortschritte …</div>`;
    try {
      const r = await fetch("/api/techbaum?partie=" + encodeURIComponent(pid));
      if (!r.ok) throw new Error(r.status === 404 ? "Partie unbekannt oder Server ohne /api/techbaum (Ratgeber neu starten)" : "HTTP " + r.status);
      TB.d = await r.json();
      TB.pid = pid;
      tbVorbereiten();
      tbListe();
    } catch (e) {
      $("#tb-liste").innerHTML = `<div class="empty">Fortschritte nicht geladen: ${esc(e.message)}</div>`;
    }
  })().finally(() => { TB.laedt = null; });
  return TB.laedt;
}

// Suchtext je Fortschritt (Name, Schlüssel, Beschreibung, Namen der Wirkungen, Schalter, Freischaltungen, Hinweise)
function tbVorbereiten() {
  const D = TB.d, idx = {};
  for (const [k, a] of Object.entries(D.fortschritte)) {
    idx[k] = tbFold([a.n, k, a.b, ...(a.w || []).map(w => w[1]), ...(a.s || []).map(s => s[1]),
                     ...(a.u || []).map(u => `${u[1]} ${u[3]} ${u[2]}`), ...(a.tt || [])].join("   "));
  }
  TB.idx = idx;
  TB.vokabel = null;
  const z = $("#tb-z"), t = $("#tb-t");
  z.innerHTML = `<option value="">alle</option>` + D.zeitalter.map((x, i) =>
    `<option value="${i}">${esc(x.name)}${i === D.zeitalter_idx ? " (jetzt)" : ""}</option>`).join("");
  t.innerHTML = `<option value="">alle</option>` + D.themen.map((x, i) => `<option value="${i}">${esc(x)}</option>`).join("");
  z.value = TB.f.z ?? ""; t.value = TB.f.t ?? ""; $("#tb-s").value = TB.f.s ?? "";
  $("#tb-alle-t").textContent = `alle ${fmt(Object.keys(D.fortschritte).length, 0)} anzeigen`;
}

// tolerante Suche: alle Wörter müssen vorkommen; ein Wort ohne Treffer darf um einen Buchstaben abweichen (ab 8 Zeichen zwei)
function tbAbstand(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let best = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      best = Math.min(best, cur[j]);
    }
    if (best > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}
function tbSuche(q) {
  const worte = tbFold(q).split(/\s+/).filter(Boolean);
  if (!worte.length) return null;
  const alle = Object.keys(TB.idx), varianten = [];
  for (const w of worte) {
    if (w.length < 4 || alle.some(k => TB.idx[k].includes(w))) { varianten.push([w]); continue; }
    if (!TB.vokabel) TB.vokabel = [...new Set(Object.values(TB.idx).join(" ").split(/[^a-z0-9_]+/).filter(x => x.length >= 3))];
    const max = w.length >= 8 ? 2 : 1;
    // ähnliches Wort oder ähnlicher Wortanfang („Weberi“ findet „Weberei“, „Weberein“ findet „Weberei“)
    const nah = TB.vokabel.filter(t => tbAbstand(w, t, max) <= max || (t.length > w.length && tbAbstand(w, t.slice(0, w.length), max) <= max));
    varianten.push(nah.length ? nah : [w]);
  }
  const treffer = alle.filter(k => varianten.every(vs => vs.some(v => TB.idx[k].includes(v))));
  const nf = worte.join(" ");
  // Rang: Name beginnt mit / enthält die Suche, dann Schlüssel, dann alles andere
  const rang = k => { const n = tbFold(tbA(k).n); return n.startsWith(nf) ? 0 : n.includes(nf) ? 1 : k.includes(nf) ? 2 : 3; };
  treffer.sort((a, b) => rang(a) - rang(b) || tbA(a).n.localeCompare(tbA(b).n, "de"));
  return { treffer, worte: varianten.flat() };
}

// Hervorhebung: Suchwort in Such- und Schreibform (ae trifft ä, ss trifft ß)
function tbMuster(worte) {
  if (!worte?.length) return null;
  const teil = w => {
    let r = "";
    for (let i = 0; i < w.length; i++) {
      const zw = w.slice(i, i + 2), u = { ae: "ä", oe: "ö", ue: "ü", ss: "ß" }[zw];
      if (u) { r += `(?:${zw}|${u})`; i++; } else r += w[i].replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }
    return r;
  };
  return new RegExp(worte.map(teil).sort((a, b) => b.length - a.length).join("|"), "gi");
}
function tbHell(text, re) {
  const s = String(text ?? "");
  if (!re) return esc(s);
  let out = "", last = 0;
  for (const m of s.matchAll(re)) {
    if (!m[0]) continue;
    out += esc(s.slice(last, m.index)) + `<mark>${esc(m[0])}</mark>`;
    last = m.index + m[0].length;
  }
  return out + esc(s.slice(last));
}

// gilt für uns: Standard ohne „nicht für uns“ und „unklar“ (Schalter „alle anzeigen“ oder Statusfilter zeigen sie)
function tbSichtbar(k) {
  const a = tbA(k), s = tbStatus(k), f = TB.f;
  if (f.z !== undefined && f.z !== "" && String(a.z) !== String(f.z)) return false;
  if (f.t !== undefined && f.t !== "" && String(a.th) !== String(f.t)) return false;
  if (f.s) return s === f.s;
  return f.alle || (s !== "n" && s !== "u");
}

const tbChip = (k, re = null) => {
  const a = tbA(k);
  if (!a) return `<span class="code">${esc(k)}</span>`;
  const s = tbStatus(k);
  return `<a class="tbc st-${s}${k === TB.sel ? " sel" : ""}" href="#techbaum/${encodeURIComponent(k)}" data-tb="${esc(k)}"
    title="${esc(TB_ST[s])}${num(TB.d.kosten?.[k]) ? ` · Kosten ${fmt(TB.d.kosten[k], 2)}` : ""} · ${esc(TB.d.themen[a.th] || "")}">${tbHell(a.n, re)}</a>`;
};

function tbListe() {
  const D = TB.d, box = $("#tb-liste");
  if (!D || !box) return;
  const S = tbSuche(TB.f.q || "");
  if (S) {
    const re = tbMuster(S.worte), rows = S.treffer.filter(tbSichtbar);
    const ausgeblendet = S.treffer.length - rows.length;
    $("#tb-n").textContent = `${fmt(rows.length, 0)} Treffer` + (ausgeblendet ? ` (${fmt(ausgeblendet, 0)} durch Filter ausgeblendet)` : "");
    const trifft = x => { if (!re) return false; re.lastIndex = 0; const t = re.test(x); re.lastIndex = 0; return t; };
    const wo = k => {                                          // wo die Suche trifft, wenn nicht im Namen
      const a = tbA(k), fs = [...(a.w || []).map(w => `Wirkung ${w[1]} ${w[2]}`), ...(a.s || []).map(s => `Schalter ${s[1]}`),
                               ...(a.u || []).map(u => `${u[1]}: ${u[3]}`), ...(a.tt || [])];
      const f = fs.find(trifft);
      if (f) return tbHell(f, re);
      const b = String(a.b || "");
      if (!re) return "";
      re.lastIndex = 0;
      const m = b.search(re);
      return m >= 0 ? "… " + tbHell(b.slice(Math.max(0, m - 60), m + 100), re) + " …" : "";
    };
    box.innerHTML = rows.length ? `<div class="card scroll tb-trefferbox"><table class="tb-treffer"><tr><th>Fortschritt</th><th class="l">Status</th>
        <th class="l">Zeitalter · Thema</th><th class="l">Fundstelle</th></tr>
      ${rows.slice(0, TB_LISTE).map(k => { const a = tbA(k); return `<tr><td class="l">${tbChip(k, re)}<div class="code">${tbHell(k, re)}</div></td>
        <td class="l">${esc(TB_ST[tbStatus(k)])}</td><td class="l">${esc(tbAlter(a.z).name || "–")} · ${esc(D.themen[a.th] || "")}</td>
        <td class="l tb-fund">${wo(k)}</td></tr>`; }).join("")}</table>
      ${rows.length > TB_LISTE ? `<p class="hint">Die ersten ${TB_LISTE} von ${fmt(rows.length, 0)} – Suche genauer fassen.</p>` : ""}</div>`
      : `<div class="empty">Keine Treffer${ausgeblendet ? ` – ${fmt(ausgeblendet, 0)} durch Filter ausgeblendet („alle anzeigen“ oder Filter lösen)` : ""}.</div>`;
    return;
  }
  const n = Object.keys(D.fortschritte).filter(tbSichtbar).length;
  $("#tb-n").textContent = `${fmt(n, 0)} Fortschritte`;
  const z0 = D.zeitalter_idx ?? 0;
  box.innerHTML = D.zeitalter.map((z, i) => {
    const ks = Object.keys(D.fortschritte).filter(k => D.fortschritte[k].z === i && tbSichtbar(k));
    if (!ks.length) return "";
    const zahl = Object.fromEntries(Object.keys(TB_ST).map(s => [s, ks.filter(k => tbStatus(k) === s).length]));
    const offen = i === z0 || (TB.f.z !== undefined && TB.f.z !== "") || (TB.sel && tbA(TB.sel)?.z === i);
    return `<details class="card tb-alter" data-z="${i}"${offen ? " open" : ""}><summary><b>${esc(z.name)}</b>
        <span class="hint">${z.jahr > 1 ? `ab ${z.jahr}` : "ab Spielbeginn"}${i === z0 ? " · jetzt" : ""} · ${fmt(ks.length, 0)} Fortschritte:
        ${Object.entries(zahl).filter(([, v]) => v).map(([s, v]) => `${v} ${TB_ST[s]}`).join(" · ")}</span>
        <a class="tb-wiki" href="#wiki/age/${encodeURIComponent(z.key)}" title="Zeitalter im Wiki (Mechaniken)">Wiki</a></summary>
      <div class="tb-inhalt"></div></details>`;
  }).join("") || `<div class="empty">Kein Fortschritt passt zum Filter.</div>`;
  box.querySelectorAll("details.tb-alter[open]").forEach(tbAbschnitt);
}

// ein Zeitalter: je Thema die Fortschritte nach Stufe im Baum (0 = ohne Vorgänger)
function tbAbschnitt(det) {
  const D = TB.d, i = +det.dataset.z, box = det.querySelector(".tb-inhalt");
  if (!D || box.dataset.fertig) return;
  const ks = Object.keys(D.fortschritte).filter(k => D.fortschritte[k].z === i && tbSichtbar(k));
  const je = {};
  for (const k of ks) (je[D.fortschritte[k].th] ??= []).push(k);
  box.innerHTML = Object.keys(je).sort((a, b) => a - b).map(th => {
    const st = {};
    for (const k of je[th]) (st[D.fortschritte[k].t || 0] ??= []).push(k);
    return `<div class="tb-thema"><h4>${esc(D.themen[th])} <small>${je[th].length}</small></h4>
      ${Object.keys(st).sort((a, b) => a - b).map(t => `<div class="tb-stufe"><span class="tb-sn">Stufe ${t}</span><div>${st[t]
        .sort((a, b) => D.fortschritte[a].n.localeCompare(D.fortschritte[b].n, "de")).map(k => tbChip(k)).join("")}</div></div>`).join("")}</div>`;
  }).join("");
  box.dataset.fertig = "1";
}

function tbMarkiere() {
  document.querySelectorAll("#tb-liste a.tbc.sel").forEach(a => a.classList.remove("sel"));
  if (!TB.sel) return;
  document.querySelectorAll(`#tb-liste a.tbc[data-tb="${CSS.escape(TB.sel)}"]`).forEach(a => a.classList.add("sel"));
}

// fehlende Vorgänger in Forschungsreihenfolge (wie techbaum.weg: erst niedrige Stufe, dann Name)
function tbWeg(k) {
  const out = [], seen = new Set();
  const sammle = x => { for (const r of tbA(x)?.r || []) if (tbA(r) && !seen.has(r) && tbStatus(r) !== "e") { seen.add(r); sammle(r); out.push(r); } };
  sammle(k);
  return out.sort((a, b) => (tbA(a).t || 0) - (tbA(b).t || 0) || tbA(a).n.localeCompare(tbA(b).n, "de"));
}

// Bedingungsbaum [Text, ok, Kinder] mit ✓ / ✗ / ?
const tbBed = knoten => `<ul>${knoten.map(([t, ok, kids]) => `<li><span class="${ok === true ? "ok" : ok === false ? "no" : "q"}">${ok === true ? "✓" : ok === false ? "✗" : "?"}</span>
  ${esc(t)}${kids?.length ? tbBed(kids) : ""}</li>`).join("")}</ul>`;

function tbKosten(k) {
  const D = TB.d, c = D.kosten?.[k], a = tbA(k), je = D.laufend?.je_monat;
  if (num(c)) return `${fmt(c, 2)} Forschungsfortschritt${num(je) ? ` · ≈ ${fmt(c / je, 1)} Monate bei ${fmt(je, 2)} je Monat (Ableitung)` : ""}`;
  return `zeigt das Spiel${num(a?.rc) ? ` (Feld research_cost ${fmt(a.rc, 2)} – Wirkung nicht belegt)` : ""}`;
}

// Selbstprüfung der Kosten (30.10., techbaum.kostenbelege): jede laufende Forschung, die der Daten-Mod geschrieben hat, gegen die
// Formel; was die Aufschlüsselungen über die offenen Teile verraten (Zuschlag ab Zeitalter 3, research_cost, einzigartige)
function tbKostenpruefung(K) {
  if (!K?.belege?.length) return `<h5>Kostenprüfung</h5><p class="hint">Noch keine laufende Forschung mit Aufschlüsselung im Daten-Mod (ab 0.16).</p>`;
  const n = v => K.belege.filter(b => b.vergleich === v).length, G = K.gelernt || {};
  const zeile = z => `${esc(z.text)} ${z.prozent ? `${sgn(z.wert, 2)} %` : fmt(z.wert, 2)}`;
  const zusatz = G.zusatz?.length ? G.zusatz.map(x => `${esc(x.name)}: research_cost ${esc(x.research_cost ?? "–")} → ${sgn(x.prozent, 2)} %${x.passt ? " ✓" : " ≠"}`).join("; ")
    : "noch kein Beleg";
  return `<h5>Kostenprüfung – ${n("gleich")} von ${K.belege.length} gleich${n("abweichung") ? `, <span class="neg">${n("abweichung")} abweichend</span>` : ""}${n("offen") ? `, ${n("offen")} offen` : ""}</h5>
    <div class="scroll"><table><tr><th class="l">Fortschritt</th><th class="l">Land, Monat</th><th>Spiel</th><th>Ratgeber</th><th class="l">Aufschlüsselung des Spiels</th></tr>
    ${K.belege.map(b => `<tr><td class="l">${b.key ? tbChip(b.key) : esc(b.name)}</td><td class="l">${esc(b.tag)} ${b.quelle === "tooltip" ? "Tooltip" : esc(b.von) + (b.bis !== b.von ? "–" + esc(b.bis) : "")}</td>
      <td>${fmt(b.spiel, 2)}</td><td class="${b.vergleich === "gleich" ? "pos" : b.vergleich === "abweichung" ? "neg" : ""}">${num(b.formel) ? `${fmt(b.formel, 2)} ${b.vergleich === "gleich" ? "✓" : "≠"}` : "offen"}</td>
      <td class="l hint">${b.quelle === "tooltip" ? `Forschungsfenster, „Zu Forschungsreihe hinzufügen“ – nur die Summe${b.einzig ? " (nur für ein Land)" : ""}` : b.zeilen.map(zeile).join(" · ")}</td></tr>`).join("")}</table></div>
    <p class="hint">Daten-Mod: Name, „Benötigt x von y“ und Aufschlüsselung der laufenden Forschung, alle Länder und Partien der Datenbank; dazu Kosten aus
      Tooltips des Forschungsfensters (Screenshots 31.10.). Ein belegter Fall (Zeitalter, gleiches/früheres Zeitalter, research_cost, einzigartig) gilt für alle
      Fortschritte mit demselben Fall (Regel des Ratgebers).
      Zuschlag ab Zeitalter 3: ${K.modus ? `<b>${esc(K.modus)}</b> (belegt)` : G.modus_belege?.length > 1 ? `<span class="neg">Belege widersprechen sich (${esc(G.modus_belege.join(", "))})</span>` : "kein Beleg"};
      noch offen – Feld research_cost: ${zusatz}; Aufschlüsselung einzigartiger Fortschritte: ${G.einzig?.length ? G.einzig.map(v => fmt(v, 2)).join(", ") : "noch kein Beleg"}${G.andere?.length
      ? `; unbekannte Zeilen: ${esc(G.andere.join(", "))}` : ""}.</p>`;
}

function tbDetail() {
  const D = TB.d, box = $("#tb-detail");
  if (!box) return;
  if (!D) { box.innerHTML = ""; return; }
  const k = TB.sel, a = tbA(k);
  if (!a) {
    const lf = D.laufend || {}, kd = D.kosten_defines || {}, zj = D.zeitalter[D.zeitalter_idx] || {};
    box.innerHTML = `<h3>Fortschritte von ${esc(D.land || D.tag || "")}</h3>
      <div class="kv"><span>Zeitalter (Spielstand)</span><span><a href="#wiki/age/${encodeURIComponent(zj.key || "")}">${esc(zj.name || "–")}</a></span>
        <span>erforscht</span><span>${fmt(D.erforscht, 0)} von ${fmt(Object.keys(D.fortschritte).length, 0)}</span>
        <span>jetzt erforschbar</span><span>${fmt(Object.values(D.status).filter(s => s === "j").length, 0)}</span>
        ${lf.name ? `<span>laufende Forschung</span><span>${lf.key ? tbChip(lf.key) : esc(lf.name)}</span>
          <span>Fortschritt</span><span>${num(lf.fortschritt) ? `${fmt(lf.fortschritt, 2)} von ${fmt(lf.kosten, 2)}` : "–"}${lf.dauer ? ` · fertig ${esc(lf.dauer)}` : ""}</span>` : ""}
        ${num(lf.je_monat) ? `<span>Forschung je Monat</span><span>${fmt(lf.je_monat, 2)}</span>` : ""}</div>
      ${k ? `<p class="neg">Fortschritt „${esc(k)}“ gibt es in den Spieldaten nicht.</p>` : `<p class="hint">Fortschritt anklicken – Wirkungen, Freischaltungen,
        Bedingungen, Vorgänger bis zur Wurzel, Nachfolger und der Weg dorthin erscheinen hier.</p>`}
      <h5>Quellen und Regeln</h5><ul class="tb-q">
        <li>Fortschritte, Wirkungen, Freischaltungen: Spieldateien in_game/common/advances (mit Erweiterungen), Namen deutsch laut Lokalisierung, Werte wie im Spiel (Modifikator-Typen).</li>
        <li>Status: Spielstand ${esc(D.datum)} (erforschte Fortschritte, Zeitalter, Land, Kultur, Religion, Hauptstadt, Regierungsform); Erweiterungen: ${esc(D.fakten?.dlcs_quelle || "–")}.</li>
        <li>Voraussetzungen: <b>Annahme</b> – alle genannten Vorgänger sind nötig (das Spiel listet sie einzeln mit ✓/✗ unter „Voraussetzungen:“; die Regel selbst steht in keiner Datei).</li>
        <li>Kosten nur, wo Defines und Spielwerte übereinstimmen (Kostenprüfung unten): Grundwert ${esc(kd.BASE_RESEARCH_COST)} (nur für ein Land: ${esc(kd.BASE_UNIQUE_RESEARCH_COST)}),
          +${fmt((kd.AGE_RESEARCH_MODIFIER || 0) * 100, 0)} % je Zeitalter nach dem ersten, addiert – für Fortschritte des laufenden und späterer Zeitalter;
          vorheriges Zeitalter ${esc(kd.PREVIOUS_AGE_REDUCTION)} (belegt im 2. Zeitalter). Sonst „zeigt das Spiel“, etwa beim Feld research_cost.
          Monate = Kosten ÷ Forschung je Monat (Ableitung des Ratgebers).</li>
        <li>Thema: Einordnung des Ratgebers nach der Spieldatei; Stufe = längste Kette der Vorgänger im Zeitalter.</li></ul>
      ${lf.kosten_text ? `<p class="hint">Laufende Forschung laut Daten-Mod (${esc(lf.datum || "")}): ${esc(lf.info || "")} ${esc(lf.kosten_text).replace(/\n/g, ", ")}${lf.key && num(D.kosten?.[lf.key])
        ? ` – Formel ${fmt(D.kosten[lf.key], 2)} ${Math.abs(D.kosten[lf.key] - lf.kosten) < 0.01 ? "✓ gleich" : "≠ Spielwert"}` : ""}</p>` : ""}
      ${tbKostenpruefung(D.kostenpruefung)}`;
    return;
  }
  const s = tbStatus(k), z = tbAlter(a.z), datei = D.dateien?.[a.dt];
  const weg = s === "e" ? [] : tbWeg(k);
  // laufende Forschung zählt nur mit dem Rest (Kosten − schon erforscht laut Daten-Mod, Prüfer 30.10.)
  const tbRest = x => x === D.laufend?.key && num(D.kosten?.[x]) && num(D.laufend.fortschritt)
    ? Math.max(0, D.kosten[x] - D.laufend.fortschritt) : D.kosten?.[x];
  const wegK = [...weg, k].map(tbRest);
  const summe = weg.length && wegK.every(num) ? wegK.reduce((x, y) => x + y, 0) : null;
  const gesperrt = weg.filter(x => ["n", "u", "s"].includes(tbStatus(x)));
  const nachAlle = new Set();
  (function nach(x) { for (const n of tbA(x)?.nf || []) if (!nachAlle.has(n)) { nachAlle.add(n); nach(n); } })(k);
  const gesehen = new Set([k]);
  const kette = x => (tbA(x)?.r || []).map(r => {
    const neu = !gesehen.has(r); gesehen.add(r);
    return `<li>${tbChip(r)}${!neu ? ` <span class="hint">(oben schon)</span>` : tbA(r)?.r?.length ? `<ul>${kette(r)}</ul>` : ` <span class="hint">Wurzel</span>`}</li>`;
  }).join("");
  const wirk = a.w || [];
  box.innerHTML = `<div class="tb-det-kopf"><span class="tbc st-${s}" title="${esc(TB_ST_LANG[s])}">${esc(TB_ST[s])}</span>
      ${k === D.laufend?.key ? `<span class="tbc st-j" title="laut Daten-Mod">wird gerade erforscht</span>` : ""}</div>
    <h3>${esc(a.n)}</h3><div class="code">${esc(k)}</div>
    <p class="hint">Zeitalter <a href="#wiki/age/${encodeURIComponent(z.key || "")}">${esc(z.name || "–")}</a> · Thema ${esc(D.themen[a.th] || "")} ·
      Stufe ${a.t || 0} im Baum${num(a.dp) ? ` (Feld depth ${a.dp})` : ""}${a.i ? ` · Symbol ${esc(a.i)}` : ""}<br>Spieldatei ${esc(datei || "–")}${a.itb ? ` · im Baum von ${tbChip(a.itb)}` : ""}</p>
    ${a.b ? `<p>${esc(a.b)}</p>` : ""}
    ${D.grund?.[k] ? `<p class="warn">${esc(D.grund[k])}</p>` : ""}
    <h5>Kosten</h5><p>${s === "e" ? "erforscht" : tbKosten(k)}</p>
    ${wirk.length ? `<h5>Wirkungen</h5><table>${wirk.map(([m, n, t, r]) => `<tr><td class="l" title="${esc(m)}">${esc(n)}</td>
      <td class="${r > 0 ? "pos" : r < 0 ? "neg" : ""}">${esc(t)}</td></tr>`).join("")}</table>` : ""}
    ${(a.s || []).length ? `<h5>Schalter</h5><div>${a.s.map(([m, n]) => `<span class="tag" title="${esc(m)}">${esc(n)}</span>`).join("")}</div>` : ""}
    ${(a.u || []).length ? `<h5>Freischaltungen</h5><ul class="tb-frei">${a.u.map(([f, l, x, n, link]) => `<li>${esc(l)}: ${link
      ? `<a href="${esc(link)}" title="im Wiki (Mechaniken)">${esc(n)}</a>` : esc(n)} <span class="code">${esc(x)}</span></li>`).join("")}</ul>` : ""}
    ${(a.tt || []).length ? `<h5>Hinweis des Spiels</h5>${a.tt.map(t => `<p>${esc(t)}</p>`).join("")}` : ""}
    ${D.bed?.[k] ? `<h5>Bedingungen <span class="hint">✓ erfüllt · ✗ nicht · ? nicht prüfbar</span></h5><div class="tb-bed">${tbBed(D.bed[k])}</div>` : ""}
    ${s !== "e" ? `<h5>Weg dorthin</h5>${weg.length ? `<ol class="tb-weg">${[...weg, k].map(x => `<li>${tbChip(x)} <span class="hint">${num(D.kosten?.[x])
      ? fmt(D.kosten[x], 2) + (tbRest(x) !== D.kosten[x] ? ` (läuft, Rest ${fmt(tbRest(x), 2)})` : "") : "Kosten im Spiel"}${D.grund?.[x] ? ` · ${esc(D.grund[x])}` : ""}</span></li>`).join("")}</ol>
      <p class="hint">${weg.length + 1} Schritte${num(summe) ? `, zusammen ${fmt(summe, 2)} Forschungsfortschritt${num(D.laufend?.je_monat)
        ? ` ≈ ${fmt(summe / D.laufend.je_monat, 1)} Monate` : ""}` : " – Kosten nicht für alle Schritte belegt"}.
        ${gesperrt.length ? `<span class="neg">Gesperrt: ${gesperrt.map(x => `${esc(tbA(x).n)} (${esc(TB_ST[tbStatus(x)])})`).join(", ")}.</span>` : ""}
        ${s === "s" ? `<span class="neg">Erforschbar erst im Zeitalter ${esc(z.name || "")}.</span>` : ""}</p>`
      : `<p>${s === "j" ? "Keine Voraussetzung offen – jetzt erforschbar." : s === "v" ? "Alle Vorgänger erforscht." : "–"}</p>`}` : ""}
    <h5>Vorgänger${(a.r || []).length > 1 ? ` <span class="hint">– alle nötig (Annahme)</span>` : ""}</h5>
    ${(a.r || []).length ? `<ul class="tb-baum">${kette(k)}</ul>` : `<p class="hint">keine – Wurzel im Zeitalter ${esc(z.name || "")}</p>`}
    <h5>Nachfolger</h5>${(a.nf || []).length ? `<div>${a.nf.slice().sort((x, y) => tbA(x).n.localeCompare(tbA(y).n, "de")).map(x => tbChip(x)).join("")}</div>
      <p class="hint">${a.nf.length} direkt, ${nachAlle.size} insgesamt (auch Fortschritte anderer Länder und Kulturen).</p>` : `<p class="hint">keine</p>`}
    <p class="hint">Quellen: Spieldatei ${esc(datei || "advances")}; Status laut Spielstand ${esc(D.datum)}; Bedingungen geprüft gegen
      Spielstand (Land ${esc(D.fakten?.tag || "")}, Kultur ${esc(D.fakten?.kultur || "–")}, Religion ${esc(D.fakten?.religion || "–")}).</p>`;
  if (innerWidth <= 1100 && TB.sel) box.scrollIntoView({ block: "start" });
}

// Vorschlag zum Schwerpunkt (oben): aus /api/daten (LAST_D.techbaum_vorschlag), Auswahl synchron mit dem Wirtschaftsplan
function tbVorschlag() {
  const box = $("#tb-vor");
  if (!box) return;
  const L = typeof LAST_D !== "undefined" ? LAST_D : null, V = L?.techbaum_vorschlag;
  if (!V) { box.innerHTML = `<div class="empty">Vorschlag lädt mit den Ratgeber-Daten …</div>`; return; }
  if (V.fehler) { box.innerHTML = `<p class="neg">Vorschlag fehlgeschlagen: ${esc(V.fehler)}</p>`; return; }
  const fk = wpFokus(L), F = (V.fokusse || {})[fk];
  if (!F) { box.innerHTML = `<p class="hint">Kein Wirtschaftsplan für diesen Spielstand – ohne Schwerpunkt kein Vorschlag.</p>`; return; }
  const lnk = (k, n) => `<a href="#techbaum/${encodeURIComponent(k)}">${esc(n)}</a>`;
  const kost = e => num(e.kosten) ? `${fmt(e.kosten, 2)}${num(e.monate) ? ` <span class="hint">≈ ${fmt(e.monate, 1)} Mon.</span>` : ""}` : `<span class="hint">im Spiel</span>`;
  const gr = e => `<ul class="tb-gr">${e.gruende.map(g => `<li>${esc(g)}</li>`).join("")}</ul>`;
  const lf = V.laufend || {};
  box.innerHTML = `<div class="wpwahl"><label><b>Vorschlag für den Schwerpunkt</b> <select id="tb-fokus">${Object.entries(V.fokusse).map(([k, f]) =>
      `<option value="${esc(k)}"${k === fk ? " selected" : ""}>${esc(f.name)}</option>`).join("")}</select></label>
    <span class="hint">gleiche Auswahl wie in der Kachel Wirtschaftsplan · Spielstand ${esc(V.datum || "")} · Zeitalter ${esc(V.zeitalter || "–")}
      ${lf.name ? ` · läuft: ${lf.key ? lnk(lf.key, lf.name) : esc(lf.name)}${lf.dauer ? ` (fertig ${esc(lf.dauer)})` : ""}` : ""}</span></div>
    <div class="grid2">
      <div><h5>Jetzt erforschbar – ${F.anzahl ? `${F.eintraege.length} von ${F.anzahl} mit Bezug zum Schwerpunkt` : "keiner mit Bezug zum Schwerpunkt"}</h5>
        ${F.eintraege.length ? `<div class="scroll"><table><tr><th>#</th><th class="l">Fortschritt</th><th>Punkte</th><th class="l">Gründe</th><th>Kosten</th></tr>
        ${F.eintraege.map((e, i) => `<tr><td>${i + 1}</td><td class="l">${lnk(e.key, e.name)}${e.laeuft ? ` <span class="tag">läuft</span>` : ""}
          <div class="hint">${esc(e.thema)}</div></td><td>${e.punkte}</td><td class="l">${gr(e)}</td><td>${kost(e)}</td></tr>`).join("")}</table></div>`
        : `<p class="hint">Kein jetzt erforschbarer Fortschritt bringt etwas für „${esc(F.name)}“ nach den Regeln unten.</p>`}</div>
      <div><h5>Ziele mit kurzem Weg</h5>
        ${F.ziele.length ? `<div class="scroll"><table><tr><th class="l">Ziel</th><th>Punkte</th><th class="l">Weg und Gründe</th><th>Kosten Weg</th></tr>
        ${F.ziele.map(e => `<tr><td class="l">${lnk(e.key, e.name)}<div class="hint">${esc(e.thema)}</div></td><td>${e.punkte}</td>
          <td class="l"><div>${e.weg.map(w => `${lnk(w.key, w.name)}${w.gesperrt ? ` <span class="warn" title="${esc(w.gesperrt)}">gesperrt</span>` : ""}`).join(" → ")}</div>${gr(e)}</td>
          <td>${num(e.weg_kosten) ? `${fmt(e.weg_kosten, 2)}${num(e.weg_monate) ? ` <span class="hint">≈ ${fmt(e.weg_monate, 1)} Mon.</span>` : ""}` : `<span class="hint">im Spiel</span>`}</td></tr>`).join("")}</table></div>`
        : `<p class="hint">Kein Ziel mit höchstens 3 fehlenden Voraussetzungen.</p>`}</div></div>
    <details class="more"><summary>Wie bewertet und gereiht wird (Regel des Ratgebers)</summary>
      <ul class="tb-q">${Object.values(V.punkte || {}).map(p => `<li>${esc(p)}</li>`).join("")}</ul>
      <p class="hint">${esc(V.regel || "")} Themenliste für „${esc(F.name)}“: ${esc(F.thema || "–")}.</p></details>`;
}

// Ansicht eintragen (am Ende: läuft die Seite schon mit #techbaum, ruft ansicht() die Funktion sofort auf – alle Helfer müssen stehen)
ansicht("techbaum", "Fortschritte", (rest, el) => {
  TB.el = el;
  if (!el.dataset.built) {
    el.innerHTML = `<div class="card tb-vor" id="tb-vor"><div class="empty">Vorschlag lädt mit den Ratgeber-Daten …</div></div>
      <div class="tb-leiste">
        <input type="search" id="tb-q" placeholder="Suche: Name, Schlüssel, Beschreibung, Wirkung, Freischaltung …" autocomplete="off">
        <label>Zeitalter <select id="tb-z"><option value="">alle</option></select></label>
        <label>Status <select id="tb-s"><option value="">alle</option>${Object.entries(TB_ST).map(([k, v]) =>
          `<option value="${k}">${esc(v)}</option>`).join("")}</select></label>
        <label>Thema <select id="tb-t"><option value="">alle</option></select></label>
        <label title="Standard: nur Fortschritte, deren Bedingungen unser Land erfüllt oder die keine haben"><input type="checkbox" id="tb-alle">
          <span id="tb-alle-t">alle anzeigen</span></label>
        <span class="hint" id="tb-n"></span>
      </div>
      <div class="tb-legende">${Object.entries(TB_ST).map(([k, v]) => `<span class="tbc st-${k}" title="${esc(TB_ST_LANG[k])}">${esc(v)}</span>`).join("")}</div>
      <div class="tb-grid"><div class="tb-liste" id="tb-liste"><div class="empty">Lade Fortschritte …</div></div>
        <aside class="card tb-detail" id="tb-detail"></aside></div>`;
    el.dataset.built = "1";
    const q = $("#tb-q", el);
    q.value = TB.f.q || "";
    let timer = null;
    q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { TB.f.q = q.value; tbFilterSpeichern(); tbListe(); }, 180); });
    for (const [id, f] of [["tb-z", "z"], ["tb-s", "s"], ["tb-t", "t"]])
      $("#" + id, el).addEventListener("change", e => { TB.f[f] = e.target.value; tbFilterSpeichern(); tbListe(); });
    $("#tb-alle", el).addEventListener("change", e => { TB.f.alle = e.target.checked; tbFilterSpeichern(); tbListe(); });
    $("#tb-alle", el).checked = !!TB.f.alle;
    // Abschnitt eines Zeitalters erst beim Aufklappen füllen (bis zu 700 Fortschritte je Zeitalter)
    el.addEventListener("toggle", e => { if (e.target.classList?.contains("tb-alter") && e.target.open) tbAbschnitt(e.target); }, true);
    el.addEventListener("change", e => {
      if (e.target.id !== "tb-fokus") return;
      store.set("rg_wp_fokus", e.target.value);     // gleicher Schlüssel wie die Kachel Wirtschaftsplan
      TB.fokusNeu = true;                           // Ratgeber-Seite beim Zurückwechseln neu zeichnen
      tbVorschlag();
    });
  }
  TB.sel = rest || "";
  tbVorschlag();
  tbLaden().then(() => { tbDetail(); tbMarkiere(); });
});
