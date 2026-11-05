"use strict";
// Mechaniken (Wiki, Nutzerwunsch 30.10.): eigene Ansicht #wiki, #wiki/<id> – Rahmen siehe ansichten.js.
// Daten: /api/wiki (eu5ratgeber/wiki.py, einmal je Spielversion gebaut): Spielbegriffe der Europedia, die 6 Zeitalter und
// weitere Mechaniken mit Namen und Beschreibung (Gesetze, Reformen, Privilegien …), je Eintrag Erklärung, Wirkung,
// Zeitalter-Bezug, Verweise, „Wird verändert durch“ und Ratgeber-Wissen (analysis/MECHANIK.md).
// Id = Adresse: Spielbegriff = Schlüssel (#wiki/control), sonst <ordner>/<schlüssel> (#wiki/laws/press_law,
// #wiki/age/age_3_discovery); eine Politik (#wiki/policies/<k> oder #wiki/laws/<politik>) öffnet ihr Gesetz.
// Aufbau: links Suche, Zeitalter, Arten, Typen und Trefferliste, rechts der Eintrag (schmal untereinander).
// Nutzt Helfer aus app.js ($, esc, store).
const WK = { d: null, laden: null, el: null, id: "", alle: false,
             q: store.get("wk_q") || "", art: store.get("wk_art") || "", za: store.get("wk_za") || "",
             typ: store.get("wk_typ") || "", quellen: null, namen: {} };
const WK_LISTE = 400;                     // so viele Treffer zeigt die Liste, Rest über „alle zeigen“
const WK_ZA_ART = { zeitalter: "vom Zeitalter geändert", frei: "durch Fortschritt freigeschaltet",
                    voraussetzung: "setzt Fortschritt voraus", feld: "Feld age der Spieldatei" };
const WK_OFFEN = "Wert, den nur das laufende Spiel kennt (Datenfunktion der Lokalisierung) – aus den Spieldateien nicht berechenbar";

// Suchform: klein, Umlaute ausgeschrieben (ä = ae …), sonstige Akzente weg – gleiche Regel wie wiki._fold
const wkFold = s => String(s ?? "").toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue")
  .replace(/ß/g, "ss").normalize("NFD").replace(/[̀-ͯ]/g, "");
const wkPlain = x => String(x || "").replace(/\[\[([^|\]]*)\|(.*?)\]\]/g, (m, id, t) => id === "?" ? "" : t);
const wkWorte = () => wkFold(WK.q).split(/\s+/).filter(Boolean);

// Hervorhebung: Suchwort in Such- und Schreibform (ae trifft ä, ss trifft ß)
function wkMuster(worte) {
  if (!worte.length) return null;
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
function wkMarkiere(el, re) {
  if (!re || !el) return;
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), nodes = [];
  while (w.nextNode()) nodes.push(w.currentNode);
  for (const n of nodes) {
    re.lastIndex = 0;
    if (!re.test(n.data)) continue;
    const frag = document.createDocumentFragment();
    let last = 0;
    n.data.replace(re, (m, off) => {
      frag.append(n.data.slice(last, off));
      const mk = document.createElement("mark");
      mk.textContent = m;
      frag.append(mk);
      last = off + m.length;
      return m;
    });
    frag.append(n.data.slice(last));
    n.replaceWith(frag);
  }
}

// ---------------------------------------------------------------- Daten
async function wkLaden() {
  const r = await fetch("/api/wiki");
  if (!r.ok) throw new Error(`/api/wiki: ${r.status}`);
  const d = await r.json();
  d.rein = {};                            // eingehende Verweise (Erwähnt bei)
  d.vd = {};                              // Begriff -> Modifikatoren, deren Erklärung ihn verlinkt: [m, zuerst genannt]
  d.zaName = Object.fromEntries(d.zeitalter.map(z => [z.k, z]));
  d.artName = Object.fromEntries(d.arten);
  d.typReihe = Object.keys(d.typen);
  for (const [m, v] of Object.entries(d.mods)) (v[2] || []).forEach((b, n) => (d.vd[b] ||= []).push([m, n === 0]));
  for (const [i, e] of Object.entries(d.e)) {
    e.id = i;
    for (const z of e.l || []) (d.rein[z] ||= []).push(i);
    e._n = wkFold([e.n, ...(e.an || [])].join(" \u0001 "));
    e._k = wkFold([i, ...(e.ak || []), ...(e.pol || []).map(p => p.k)].join(" "));
    e._s = [e._n, e._k, wkFold(wkPlain(e.x)), ...(e.pol || []).map(p => wkFold(p.n + " " + wkPlain(p.x)))].join(" \u0001 ");
  }
  return d;
}

// Id aus der Adresse -> [eintrag, politik]; Politiken stehen in ihrem Gesetz
function wkFinde(id) {
  const d = WK.d;
  if (d.e[id]) return [d.e[id], null];
  const k = id.split("/").pop();
  if (/^(policies|laws)\//.test(id) && d.politik[k]) return [d.e[d.politik[k]], k];
  return [null, null];
}

const wkZaPasst = (e, za) => za === "ohne" ? !(e.za || []).length : (e.za || []).some(z => z[0] === za);

// Treffer nach Suche und Zeitalter; Arten und Typen zählen jeweils ohne ihren eigenen Filter
function wkTreffer() {
  const d = WK.d, worte = wkWorte();
  const basis = Object.values(d.e).filter(e => (!WK.za || wkZaPasst(e, WK.za)) && worte.every(w => e._s.includes(w)));
  const artZahl = {}, typZahl = {};
  for (const e of basis) {
    if (!WK.typ || e.t === WK.typ) artZahl[e.art] = (artZahl[e.art] || 0) + 1;
    if (!WK.art || e.art === WK.art) typZahl[e.t] = (typZahl[e.t] || 0) + 1;
  }
  const liste = basis.filter(e => (!WK.art || e.art === WK.art) && (!WK.typ || e.t === WK.typ));
  // Reihenfolge mit Suche: Name oder Alias gleich der Suche, Name beginnt mit dem Suchwort, Name enthält alle Wörter,
  // Schlüssel/Alias, nur im Text; dann nach Typ (Spielbegriffe zuerst) und Name
  const ganz = worte.join(" ");
  const rang = e => !worte.length ? 0 : e._n.split(" \u0001 ").includes(ganz) || e._k.split(" ").includes(ganz) ? 0
    : e._n.startsWith(worte[0]) ? 1 : worte.every(w => e._n.includes(w)) ? 2
    : worte.every(w => e._k.includes(w) || e._n.includes(w)) ? 3 : 4;
  for (const e of liste) e._r = rang(e);
  liste.sort((a, b) => a._r - b._r || d.typReihe.indexOf(a.t) - d.typReihe.indexOf(b.t) || a.n.localeCompare(b.n, "de"));
  return { liste, artZahl, typZahl, gesamt: basis.length };
}

// ---------------------------------------------------------------- Text mit Verweisen
function wkText(x) {
  return esc(x || "").replace(/\[\[([^|\]]*)\|(.*?)\]\]/g, (m, id, t) => {
    if (id === "?") return `<span class="wk_off" title="${esc(WK_OFFEN)}">‹${t}›</span>`;
    return WK.d.e[id] || WK.d.politik[id] ? `<a href="#wiki/${id}">${t}</a>` : t;
  }).replace(/\n/g, "<br>");
}
const wkLink = (id, text) => WK.d.e[id] ? `<a href="#wiki/${esc(id)}">${esc(text ?? WK.d.e[id].n)}</a>` : esc(text ?? id);
const wkZaText = k => { const z = WK.d.zaName[k]; return z ? `${esc(z.n)} (ab ${z.jahr})` : esc(k); };

// Modifikator: deutscher Name (Erklärung als Hinweis), Begriff dazu verlinkt
function wkMod(m) {
  const v = WK.d.mods[m];
  if (!v) return `<code>${esc(m)}</code> <span class="qu">(ohne deutschen Namen)</span>`;
  const b = v[2]?.[0];
  return `<span title="${esc(wkPlain(v[1]) + "\n" + m)}">${esc(v[0])}</span>`
    + (b && WK.d.e[b] ? ` <span class="qu">→ ${wkLink(b)}</span>` : "");
}
function wkBlockName(b) {
  const de = (WK.d.bloecke || {})[b.split("/").pop()];
  return (de ? esc(de) + " " : "") + `<code>${esc(b)}</code>`;
}
function wkWirkung(w) {
  if (!w?.length) return "";
  return w.map(([b, mm]) => `<table class="wk_tab"><thead><tr><th class="l">${wkBlockName(b)}</th><th>Wert</th></tr></thead>`
    + `<tbody>${mm.map(([m, x]) => `<tr><td class="l">${wkMod(m)}</td><td>${esc(x)}</td></tr>`).join("")}</tbody></table>`).join("");
}
// Wert einer Modifikator-Quelle im Format des Modifikators (wiki._modformat)
function wkWert(m, x) {
  if (typeof x !== "number") return esc(x === "yes" ? "ja" : x === "no" ? "nein" : x);
  const f = WK.d.mods[m]?.[4] || "", d0 = /\d/.test(f) ? +f.match(/\d/)[0] : null;
  if (f[0] === "b") return x ? "ja" : "nein";
  const v = f[0] === "p" ? x * 100 : x;
  let d = d0 ?? (Math.abs(v) < 0.1 ? 3 : 2);
  while (d < 6 && v && Math.abs(v) < 0.5 * 10 ** -d) d++;          // sehr kleine Werte nicht als 0 zeigen
  return (v > 0 ? "+" : "") + v.toLocaleString("de-DE", { maximumFractionDigits: d }).replace("-", "−")
    + (f[0] === "p" || f[0] === "a" ? " %" : "");
}

// analysis/MECHANIK.md: nur das Nötigste (Tabellen, Stichpunkte, **fett**, `code`)
function wkMd(t) {
  const zeile = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const out = [];
  let tab = null;
  for (const z of String(t || "").split("\n")) {
    if (/^\s*\|/.test(z)) {
      if (/^\s*\|[\s|:-]+\|\s*$/.test(z)) continue;
      const c = z.trim().replace(/^\||\|$/g, "").split("|").map(s => s.trim());
      if (!tab) { tab = []; out.push(`<table class="wk_tab"><tr>${c.map(x => `<th class="l">${zeile(x)}</th>`).join("")}</tr>`); }
      else out.push(`<tr>${c.map(x => `<td class="l">${zeile(x)}</td>`).join("")}</tr>`);
      continue;
    }
    if (tab) { out.push("</table>"); tab = null; }
    out.push(`<div class="wk_md${/^\s+/.test(z) ? " ein" : ""}">${zeile(z.trim()) || "&nbsp;"}</div>`);
  }
  if (tab) out.push("</table>");
  return out.join("");
}

// ---------------------------------------------------------------- Seite
function wkGeruest(el) {
  el.innerHTML = `<div class="wk">
  <div class="wk_links">
    <aside class="wk_filter">
      <input type="search" id="wk_q" placeholder="Mechanik suchen – Name, Schlüssel, Text" autocomplete="off">
      <div class="wk_zahl" id="wk_zahl"></div>
      <div class="wk_t">Zeitalter</div><div class="wk_chips" id="wk_za"></div>
      <div class="wk_t">Art</div><div class="wk_arten" id="wk_arten"></div>
      <div class="wk_t">Typ</div><select id="wk_typ"></select>
    </aside>
    <aside class="wk_liste" id="wk_liste"></aside>
  </div>
  <article class="wk_eintrag card" id="wk_eintrag"><div class="empty">Lade Mechaniken …</div></article>
</div>`;
  const q = $("#wk_q", el);
  q.value = WK.q;
  let t = null;
  q.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(() => { WK.q = q.value; WK.alle = false; store.set("wk_q", WK.q); wkFilter(); wkEintrag(); }, 120);
  });
  q.addEventListener("keydown", ev => {               // Enter öffnet den ersten Treffer
    if (ev.key !== "Enter") return;
    clearTimeout(t);
    WK.q = q.value; store.set("wk_q", WK.q);
    const r = wkTreffer().liste;
    if (r.length) location.hash = "#wiki/" + r[0].id; else wkFilter();
  });
  $("#wk_typ", el).addEventListener("change", ev => { WK.typ = ev.target.value; store.set("wk_typ", WK.typ); wkFilter(); });
  el.addEventListener("click", ev => {
    const a = ev.target.closest("[data-wk-art],[data-wk-za],[data-wk-alle],[data-wk-filter],[data-wk-typ]");
    if (!a) return;
    ev.preventDefault();
    if (a.dataset.wkArt !== undefined) { WK.art = WK.art === a.dataset.wkArt ? "" : a.dataset.wkArt; store.set("wk_art", WK.art); }
    if (a.dataset.wkZa !== undefined) { WK.za = a.dataset.wkZa; store.set("wk_za", WK.za); }
    if (a.dataset.wkFilter !== undefined || a.dataset.wkTyp !== undefined) {   // aus Übersicht/Eintrag: Filter setzen, Suche leeren
      const [art, za] = (a.dataset.wkFilter || "|").split("|");
      Object.assign(WK, { art, za, typ: a.dataset.wkTyp || "", q: "" });
      q.value = "";
      for (const k of ["art", "za", "typ", "q"]) store.set("wk_" + k, WK[k]);
    }
    wkFilter();
    if (a.dataset.wkAlle !== undefined) { WK.alle = true; wkFilter(); wkEintrag(); }
  });
  // Herkunft eines Modifikators erst beim Aufklappen laden (Spielwissen _modifikator_quellen, 1,6 MB)
  el.addEventListener("toggle", ev => {
    const x = ev.target;
    if (x.tagName === "DETAILS" && x.dataset.wkMod && x.open && !x.dataset.done) {
      x.dataset.done = "1";
      wkHerkunft(x.dataset.wkMod, $(".wk_her", x));
    }
  }, true);
}

function wkFilter() {
  const el = WK.el, d = WK.d;
  if (!d) return;
  const r = wkTreffer(), worte = wkWorte();
  $("#wk_zahl", el).textContent = `${r.liste.length.toLocaleString("de-DE")} von ${Object.keys(d.e).length.toLocaleString("de-DE")} Einträgen`
    + (worte.length ? ` für „${WK.q.trim()}“` : "");
  const chip = (wert, text, titel) => `<a href="#" class="${WK.za === wert ? "on" : ""}" data-wk-za="${wert}" title="${esc(titel || "")}">${text}</a>`;
  $("#wk_za", el).innerHTML = chip("", "alle")
    + d.zeitalter.map((z, n) => chip(z.k, `${"I II III IV V VI".split(" ")[n] || n + 1} ${esc(z.n)}`, `ab ${z.jahr}`)).join("")
    + chip("ohne", "ohne Bezug", "ohne belegten Zeitalter-Bezug – von Beginn an oder unbekannt");
  $("#wk_arten", el).innerHTML = [["", "Alle Arten"], ...d.arten].map(([k, n]) => {
    const z = k ? r.artZahl[k] || 0 : Object.values(r.artZahl).reduce((s, v) => s + v, 0);
    return `<a href="#" class="${WK.art === k ? "on" : ""}${z ? "" : " leer"}" data-wk-art="${k}"><span>${esc(n)}</span><b>${z}</b></a>`;
  }).join("");
  $("#wk_typ", el).innerHTML = `<option value="">alle Typen</option>` + d.typReihe.map(t =>
    `<option value="${t}"${WK.typ === t ? " selected" : ""}>${esc(d.typen[t].m)} (${r.typZahl[t] || 0})</option>`).join("");
  const zeig = WK.alle ? r.liste : r.liste.slice(0, WK_LISTE);
  let html = "", gruppe = null;
  for (const e of zeig) {
    if (!worte.length && e.t !== gruppe) { gruppe = e.t; html += `<div class="wk_t">${esc(d.typen[e.t].m)}</div>`; }
    const za = WK.za && WK.za !== "ohne" ? [...new Set((e.za || []).filter(z => z[0] === WK.za).map(z => WK_ZA_ART[z[1]]))] : [];
    html += `<a href="#wiki/${esc(e.id)}" class="wk_li${e.id === WK.id ? " on" : ""}"><span>${esc(e.n)}</span>`
      + `<small>${esc(worte.length ? d.typen[e.t].n : d.artName[e.art])}${za.length ? " · " + esc(za.join(", ")) : ""}`
      + `${e.ency === false ? " · nicht in der Europedia" : ""}</small></a>`;
  }
  if (r.liste.length > zeig.length)
    html += `<div class="hint">… ${r.liste.length - zeig.length} weitere – Suche oder Filter eingrenzen <a href="#" data-wk-alle>alle zeigen</a></div>`;
  const li = $("#wk_liste", el);
  li.innerHTML = html || `<div class="empty">Keine Treffer.</div>`;
  wkMarkiere(li, wkMuster(worte));
}

// Übersicht (#wiki ohne Eintrag): Quellen, Zeitalter, Arten
function wkUebersicht() {
  const d = WK.d, E = Object.values(d.e);
  const proZa = k => E.filter(e => e.t !== "zeitalter" && (e.za || []).some(z => z[0] === k)).length;
  const proArt = k => E.filter(e => e.art === k).length;
  const ohne = E.filter(e => !(e.za || []).length).length;
  return `<h2>Mechaniken – Spielregeln von EU5 ${esc(d.version || "")}</h2>
<p>${E.length.toLocaleString("de-DE")} Einträge: alle Spielbegriffe der Europedia des Spiels, die Zeitalter und weitere Mechaniken, die das
Spiel mit Namen und Beschreibung führt. Texte und Zahlen stammen aus den Spieldateien; was der Ratgeber selbst zuordnet oder
nachgerechnet hat, steht als <b>Regel des Ratgebers</b> dabei. ‹Wert im Spiel› markiert Stellen, die nur das laufende Spiel füllt.</p>
<p>Je Eintrag: <b>Erklärung</b> (Text des Spiels), <b>Wirkung</b> (Modifikatoren der Spieldatei), <b>Wird verändert durch</b>
(Ursachen: Modifikatoren, deren Erklärung im Spiel den Begriff nennt, mit ihrer Herkunft), <b>Wirkt automatisch</b> (Wirkungen:
automatische Modifikatoren des Spiels, die mit dem Begriff wachsen), <b>Zeitalter</b>, <b>Im Text erwähnt</b> / <b>Erwähnt bei</b>
(nur Verweise, ohne Richtung) und <b>Im Ratgeber nachgerechnet</b> (geprüfte Formeln aus analysis/MECHANIK.md).</p>
<div class="wk_t">Zeitalter</div>
<div class="wk_zeit">${d.zeitalter.map((z, n) => `<div class="card"><a href="#wiki/age/${esc(z.k)}"><b>${"I II III IV V VI".split(" ")[n] || ""} ${esc(z.n)}</b></a>
  <div class="qu">ab ${z.jahr}</div><a href="#" data-wk-filter="|${esc(z.k)}">${proZa(z.k)} Einträge mit Bezug</a></div>`).join("")}</div>
<p class="hint">Zeitalter-Bezug nur, wenn belegt: ein Fortschritt dieses Zeitalters schaltet den Eintrag frei oder setzt ihn voraus,
das Zeitalter ändert ihn (Spieldatei age) oder der Eintrag nennt sein Zeitalter selbst (Feld age). ${ohne.toLocaleString("de-DE")} Einträge
ohne belegten Bezug: <a href="#" data-wk-filter="|ohne">zeigen</a>.</p>
<div class="wk_t">Arten</div>
<div class="wk_artgrid">${d.arten.map(([k, n]) => `<a href="#" class="card" data-wk-filter="${k}|"><b>${esc(n)}</b><span class="qu">${proArt(k)}</span></a>`).join("")}</div>
<p class="hint">Einordnung der Spielbegriffe (Regel des Ratgebers, eu5ratgeber/wiki.py): Feld family des Spiels, sonst Stichwort im
Schlüssel, sonst Symbol-Ordner (texture), sonst Mehrheit der verlinkten Begriffe, sonst Sonstiges. Andere Typen nach ihrer Art
(Gesetze → Regierung …). Der Grund steht in jedem Eintrag.</p>
<div class="wk_t">Typen</div>
<div class="wk_artgrid">${d.typReihe.map(t => `<a href="#" class="card" data-wk-typ="${t}"><b>${esc(d.typen[t].m)}</b><span class="qu">${E.filter(e => e.t === t).length}</span></a>`).join("")}</div>`;
}

// Liste von Verweisen, lange Listen eingeklappt
function wkVerweise(ids, max = 40) {
  const a = ids.map(i => wkLink(i));
  if (a.length <= max) return `<div class="wk_vw">${a.join("")}</div>`;
  return `<div class="wk_vw">${a.slice(0, max).join("")}</div><details class="more"><summary>${a.length - max} weitere</summary><div class="wk_vw">${a.slice(max).join("")}</div></details>`;
}

function wkAbschnitt(titel, quelle, html) {
  return html ? `<section class="wk_ab"><h3>${titel}${quelle ? ` <span class="qu">${quelle}</span>` : ""}</h3>${html}</section>` : "";
}

// Zeitalter: Felder, Modifikatoren und die Einträge mit Bezug zu diesem Zeitalter
function wkZeitalter(e, k) {
  const d = WK.d;
  const felder = (e.felder || []).map(f => {
    const [lab, wert, feld, bg, hinweis] = f;
    const name = lab ? wkText(lab) : `<code>${esc(feld)}</code> <span class="qu">ohne deutschen Spieltext</span>`
      + ((bg || []).length ? ` <span class="qu">(Begriff aus dem Feldnamen: ${bg.map(b => wkLink(b)).join(", ")})</span>` : "");
    return `<tr><td class="l">${name}${hinweis ? `<div class="qu">${esc(hinweis)}</div>` : ""}</td><td>${esc(wert)}</td>`
      + `<td class="l"><code>${esc(feld)}</code></td></tr>`;
  }).join("");
  const mitBezug = {};
  for (const x of Object.values(d.e)) {
    if (x === e) continue;
    for (const z of x.za || []) if (z[0] === k) (mitBezug[z[1]] ||= new Set()).add(x.id);
  }
  return wkAbschnitt("Was sich in diesem Zeitalter ändert", "Spieldatei in_game/common/age",
      `<p>Beginn: Jahr ${esc(e.jahr)}</p>`
      + (felder ? `<table class="wk_tab"><thead><tr><th class="l">Feld</th><th>Wert</th><th class="l">Schlüssel</th></tr></thead><tbody>${felder}</tbody></table>` : "")
      + wkWirkung(e.w)
      + `<p class="hint">Werte wie in der Spieldatei; Felder mit deutschem Spieltext (AGE_… in interfaces_l_german.yml) heißen wie im Spiel,
         die übrigen stehen mit Schlüssel. Ob ein Wert gegenüber dem vorigen Zeitalter neu ist, zeigen die Einträge darunter.</p>`)
    + wkAbschnitt("Einträge mit Bezug zu diesem Zeitalter", "Regel des Ratgebers (Belege je Eintrag)",
      Object.entries(WK_ZA_ART).filter(([a]) => mitBezug[a]).map(([a, t]) =>
        `<div class="wk_t">${esc(t)} (${mitBezug[a].size})</div>${wkVerweise([...mitBezug[a]].sort((x, y) => d.e[x].n.localeCompare(d.e[y].n, "de")), 30)}`).join(""));
}

function wkEintrag() {
  const el = WK.el, d = WK.d, box = $("#wk_eintrag", el);
  if (!d || !box) return;
  if (!WK.id) { box.innerHTML = wkUebersicht(); return; }
  const [e, pol] = wkFinde(WK.id);
  if (!e) {
    const o = WK.id.includes("/") ? WK.id.split("/")[0] : "";
    const fremd = o && !Object.values(d.typen).some(t => t.o === o);
    box.innerHTML = `<h2>Kein Eintrag</h2><p>Zu <code>${esc(WK.id)}</code> gibt es im Wiki keinen Eintrag (Spielversion ${esc(d.version)}).`
      + (fremd ? ` Der Ordner <code>${esc(o)}</code> des Spiels gehört nicht zu den Mechaniken des Wikis – Inhalte wie Gebäude,
         Einheiten oder Güter stehen im Datenbrowser des Ratgebers (Begründung in eu5ratgeber/wiki.py, TYPEN).` : "")
      + ` <a href="#wiki">Zur Übersicht</a></p>`;
    return;
  }
  const ty = d.typen[e.t], id = e.id;
  const kopf = `<div class="wk_kopf"><h2>${esc(e.n)}</h2>
    <span class="tag">${esc(ty.n)}</span><a href="#" class="tag" data-wk-filter="${e.art}|" title="${esc("Einordnung: " + e.ag + " (Regel des Ratgebers)")}">${esc(d.artName[e.art])}</a>
    <code>${esc(id)}</code>${e.ency === false ? ` <span class="tag" title="shown_in_encyclopedia = no">nicht in der Europedia des Spiels</span>` : ""}</div>`
    + ((e.an || []).length || (e.ak || []).length ? `<div class="qu">Auch: ${esc((e.an || []).join(", "))}${(e.ak || []).length ? ` (Schlüssel ${esc(e.ak.join(", "))})` : ""}</div>` : "")
    + (ty.b && ty.b !== id && d.e[ty.b] ? `<div class="qu">Spielbegriff dazu: ${wkLink(ty.b)}</div>` : "");
  const quelle = e.t === "begriff" ? `Europedia des Spiels (game_concept_${esc(id)}_desc)` : esc(ty.q);
  let html = kopf + wkAbschnitt("Erklärung", quelle,
    e.x ? `<div class="wk_text">${wkText(e.x)}</div>` : `<p class="qu">Das Spiel führt zu diesem Eintrag keine Erklärung.</p>`);
  if (e.t === "zeitalter") html += wkZeitalter(e, id.split("/").pop());
  if (e.pol?.length)
    html += wkAbschnitt(`Politiken (${e.pol.length})`, esc(ty.q), e.pol.map(p =>
      `<div class="wk_pol${p.k === pol ? " on" : ""}" id="wk_pol_${esc(p.k)}"><b>${esc(p.n)}</b> <code>${esc(p.k)}</code>
       ${p.x ? `<div class="wk_text">${wkText(p.x)}</div>` : ""}${wkWirkung(p.w) || `<div class="qu">ohne Modifikatoren</div>`}</div>`).join(""));
  if (e.t !== "zeitalter" && e.w?.length) html += wkAbschnitt("Wirkung", "Modifikatoren der Spieldatei, Werte wie im Spiel", wkWirkung(e.w));
  if (e.aw?.length)
    html += wkAbschnitt("Wirkt automatisch", "Spieldatei in_game/common/auto_modifiers (scales_with = dieser Begriff)",
      e.aw.map(([k, faktor, mm, bed]) => `<div class="wk_t"><code>${esc(k)}</code> × ${esc(e.n)}${faktor ? ` (${esc(faktor)})` : ""}${bed ? " – nur unter Bedingung (potential_trigger)" : ""}</div>${wkWirkung([["je Einheit", mm]])}`).join(""));
  if (e.t !== "zeitalter")
    html += wkAbschnitt("Zeitalter", "Regel des Ratgebers: nur belegte Bezüge", (e.za || []).length
      ? `<ul class="wk_ul">${e.za.map(z => `<li><b>${wkZaText(z[0])}</b> – ${esc(WK_ZA_ART[z[1]] || z[1])}: ${esc(z[2])}`
        + (z[3] ? ` <a href="#techbaum/${esc(z[3])}" class="qu">im Fortschrittsbaum</a>` : "") + `</li>`).join("")}</ul>`
      : `<p class="qu">Kein belegter Zeitalter-Bezug – von Beginn an verfügbar oder nicht aus den Spieldateien ablesbar.</p>`);
  const vdRang = ([m, erst]) => d.mods[m][3] === "s" ? 2 : erst ? 0 : 1;    // zuerst genannt, auch genannt, aus dem Schlüssel
  const vd = (d.vd[id] || []).slice().sort((a, b) => vdRang(a) - vdRang(b) || d.mods[a[0]][0].localeCompare(d.mods[b[0]][0], "de"));
  if (vd.length)
    html += wkAbschnitt(`Wird verändert durch (${vd.length} Modifikatoren)`, "Regel des Ratgebers",
      `<p class="hint">Modifikatoren, deren Erklärung im Spiel (MODIFIER_TYPE_DESC_…) diesen Begriff verlinkt; „zuerst genannt“ = erster
       verlinkter Begriff außer Land/Ort/Provinz. „aus dem Schlüssel“ = Erklärung ohne Verweis, Begriff steht im Schlüssel des
       Modifikators. Aufklappen zeigt, wo der Modifikator im Spiel vorkommt.</p>`
      + vd.slice(0, WK.alle ? vd.length : 60).map(([m, erst]) => {
        const v = d.mods[m];
        return `<details class="wk_mod" data-wk-mod="${esc(m)}"><summary>${esc(v[0])} <code>${esc(m)}</code>`
          + ` <span class="qu">${v[3] === "s" ? "aus dem Schlüssel" : erst ? "zuerst genannt" : "auch genannt"}</span></summary>`
          + `<div class="wk_text">${wkText(v[1]) || "<span class='qu'>ohne Erklärung im Spiel</span>"}</div><div class="wk_her"></div></details>`;
      }).join("") + (vd.length > 60 && !WK.alle ? `<a href="#" data-wk-alle>alle ${vd.length} zeigen</a>` : ""));
  if (e.rg?.length)
    html += wkAbschnitt("Im Ratgeber nachgerechnet", "Wissen des Ratgebers (analysis/MECHANIK.md, im Spiel geprüft) – kein Spieltext",
      e.rg.map(s => d.ratgeber[s] ? `<details class="wk_rg"${e.rg.length === 1 ? " open" : ""}><summary>${esc(d.ratgeber[s].titel)}</summary>${wkMd(d.ratgeber[s].text)}</details>` : "").join(""));
  if (e.l?.length) html += wkAbschnitt("Im Text erwähnt", "Verweise der Erklärung", wkVerweise(e.l));
  const rein = d.rein[id] || [];
  if (rein.length) html += wkAbschnitt(`Erwähnt bei (${rein.length})`, "Einträge, deren Erklärung hierher verweist",
    wkVerweise(rein.slice().sort((a, b) => d.e[a].n.localeCompare(d.e[b].n, "de"))));
  html += `<p class="hint">Einordnung „${esc(d.artName[e.art])}“: ${esc(e.ag)} (Regel des Ratgebers). Der Linkgraph trennt Ursache und
    Wirkung nicht – „Im Text erwähnt“ und „Erwähnt bei“ sind nur Verweise.</p>`;
  box.innerHTML = html;
  wkMarkiere(box, wkMuster(wkWorte()));
  if (pol) $("#wk_pol_" + CSS.escape(pol), box)?.scrollIntoView({ block: "start" });
}

// Herkunft eines Modifikators: Spielwissen _modifikator_quellen {m: [[ordner, schlüssel, block, (konstante), wert]]}
async function wkHerkunft(m, box) {
  box.innerHTML = `<div class="qu">Lade Herkunft …</div>`;
  if (!WK.quellen) {
    const r = await fetch("/api/wissen?ordner=_modifikator_quellen");
    WK.quellen = r.ok ? await r.json() : {};
  }
  const q = WK.quellen[m] || [];
  if (!q.length) { box.innerHTML = `<div class="qu">Keine Quelle in den Definitionsordnern (wirkt nur über Skripte, Ereignisse oder das Spiel selbst).</div>`; return; }
  const d = WK.d, gruppen = {};
  for (const x of q) (gruppen[x[0]] ||= []).push(x);
  // Namen über /api/namen (Lokalisierung); statische Modifikatoren heißen STATIC_MODIFIER_NAME_<k>; ohne Übersetzung
  // liefert der Server den Schlüssel zurück -> Schlüssel anzeigen. Schlüssel ohne INJECT:/REPLACE:; bei Gesetzen steht die
  // Politik im Block (<politik>/country_modifier) – sie ist die eigentliche Quelle.
  const schl = x => x[1].replace(/^[A-Z_]+:/, "");
  const pol = x => x[0] === "laws" && x[2].includes("/") ? x[2].split("/")[0] : null;
  const lk = x => x[0] === "static_modifiers" ? "STATIC_MODIFIER_NAME_" + schl(x) : schl(x);
  const fehlt = [...new Set(q.flatMap(x => [lk(x), pol(x)]).filter(k => k && !(k in WK.namen)))].slice(0, 400);
  if (fehlt.length) {
    try { Object.assign(WK.namen, await (await fetch("/api/namen?k=" + encodeURIComponent(fehlt.join(",")))).json()); } catch (e) {}
  }
  const nm = k => WK.namen[k] && WK.namen[k] !== k ? WK.namen[k] : null;
  const ordnerName = o => Object.values(d.typen).find(t => t.o === o)?.m || (o === "advances" ? "Fortschritte" : o);
  box.innerHTML = `<div class="qu">Herkunft (Spielwissen _modifikator_quellen, Definitionsordner des Spiels):</div>`
    + Object.entries(gruppen).sort((a, b) => b[1].length - a[1].length).map(([o, xs]) => {
      const zeilen = xs.slice(0, 25).map(x => {
        const id = `${o}/${schl(x)}`, name = d.e[id]?.n || nm(lk(x)) || schl(x), p = pol(x);
        const ziel = p && d.politik[p] ? `<a href="#wiki/policies/${esc(p)}">${esc(nm(p) || p)}</a> <span class="qu">(${esc(name)})</span>`
          : d.e[id] ? `<a href="#wiki/${esc(id)}">${esc(name)}</a>`
          : o === "advances" ? `<a href="#techbaum/${esc(schl(x))}">${esc(name)}</a>` : esc(name);
        return `<tr><td class="l">${ziel}</td><td>${wkWert(m, x[x.length - 1])}</td></tr>`;
      }).join("");
      return `<table class="wk_tab"><thead><tr><th class="l">${esc(ordnerName(o))} (${xs.length}) <code>${esc(o)}</code></th><th>Wert</th></tr></thead>`
        + `<tbody>${zeilen}</tbody></table>${xs.length > 25 ? `<div class="qu">… ${xs.length - 25} weitere</div>` : ""}`;
    }).join("");
}

// Höhe der Kopfzeile für die mitlaufende linke Spalte (--wk_top); sie ändert sich mit Breite und Kopfwerten (render())
const wkOben = () => WK.el?.style.setProperty("--wk_top", ($("header")?.offsetHeight || 60) + "px");
if (window.ResizeObserver && $("header")) new ResizeObserver(wkOben).observe($("header"));

ansicht("wiki", "Mechaniken", async (rest, el) => {
  WK.el = el;
  wkOben();
  if (!el.dataset.built) {
    el.dataset.built = "1";
    wkGeruest(el);
    WK.laden = wkLaden().then(d => {
      WK.d = d;                                      // gemerkte Filter einer anderen Spielversion verwerfen
      if (!d.typen[WK.typ]) WK.typ = "";
      if (!d.artName[WK.art]) WK.art = "";
      if (WK.za !== "ohne" && !d.zaName[WK.za]) WK.za = "";
    }).catch(err => {
      $("#wk_eintrag", el).innerHTML = `<div class="empty">Mechaniken nicht geladen: ${esc(err.message)}</div>`;
    });
  }
  await WK.laden;
  if (!WK.d) return;
  if (WK.id !== rest) WK.alle = false;
  WK.id = rest;
  wkFilter();
  if (rest && matchMedia("(max-width: 760px)").matches) $("#wk_eintrag", el).scrollIntoView({ block: "start" });
  else scrollTo({ top: 0 });
  wkEintrag();                                         // springt bei einer Politik zu ihr
  const li = $("#wk_liste", el), on = $(".wk_li.on", li);   // gewählten Eintrag in der Liste sichtbar (nur die Liste scrollt)
  if (on && (on.offsetTop < li.scrollTop || on.offsetTop > li.scrollTop + li.clientHeight - 30))
    li.scrollTop = on.offsetTop - li.clientHeight / 3;
});
