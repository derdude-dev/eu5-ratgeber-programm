"use strict";
// Datenbrowser: alle Informationen (Live-Werte RG2, Aufschlüsselungen RG1I, Spielstand roh, Spielwissen).
// Eigener Bereich (#browser), wird nicht von render() neu gebaut - Auswahl und Suche bleiben stehen.
// Nutzt Helfer aus app.js ($, esc, fmt, nf, store, openAttr, rememberToggles, rawText).
const DB = { tab: store.get("db_tab") || "live", cache: {}, partie: null };

async function dget(url, frisch = false) {
  if (frisch || !(url in DB.cache)) {
    const r = await fetch(url);
    DB.cache[url] = r.ok ? await r.json() : null;
  }
  return DB.cache[url];
}

// Baum für beliebige JSON-Werte; Unterknoten erst beim Aufklappen (große Spielstand-Blöcke)
const TREE = {};
let treeId = 0;
function treeNode(key, v) {
  if (v === null || typeof v !== "object") return `<div class="leaf"><span class="k">${esc(key)}</span> = ${esc(v)}</div>`;
  const n = Array.isArray(v) ? v.length : Object.keys(v).length;
  const id = "t" + (++treeId);
  TREE[id] = v;
  return `<details data-tree="${id}"><summary><span class="k">${esc(key)}</span> <span class="t">${Array.isArray(v) ? "[" + n + "]" : "{" + n + "}"}</span></summary></details>`;
}
function treeChildren(v) {
  const ent = Array.isArray(v) ? v.map((x, i) => [i, x]) : Object.entries(v);
  return ent.slice(0, 500).map(([k, x]) => treeNode(k, x)).join("")
    + (ent.length > 500 ? `<div class="hint">… ${ent.length - 500} weitere</div>` : "");
}
function wireTree(root) {
  root.addEventListener("toggle", ev => {
    const el = ev.target;
    if (el.tagName === "DETAILS" && el.dataset.tree && el.open && !el.dataset.done) {
      el.insertAdjacentHTML("beforeend", treeChildren(TREE[el.dataset.tree]));
      el.dataset.done = "1";
    }
  }, true);
}

function fmtVal(v, typ) {
  if (typeof v !== "number") return esc(v);
  if (typ && typ.boolean) return v ? "ja" : "nein";
  if (typ && (typ.percent || typ.already_percent)) return (v > 0 ? "+" : "") + nf(1).format(typ.already_percent ? v : v * 100) + " %";
  return fmt(v, Math.abs(v) < 1 && v !== 0 ? 3 : 2);
}
const isZero = v => typeof v === "number" ? v === 0 : (v === "no" || v === "nein" || v === "" || v === null);

async function browserLive(q, nonzero) {
  const al = await dget("/api/alles?partie=" + encodeURIComponent(DB.partie));
  if (!al || !Object.keys(al.werte || {}).length) return `<div class="empty">Noch keine Live-Werte (ab Daten-Mod 0.12).</div>`;
  const arts = Object.keys(al.werte).sort();
  const sel = arts.includes(store.get("db_art")) ? store.get("db_art") : arts[0];
  const ismod = /mod$/.test(sel);
  const typen = ismod ? (await dget("/api/wissen?ordner=_modifikator_typen")) || {} : {};
  const rows = Object.entries(al.werte[sel]);
  const ql = q.toLowerCase();
  const body = rows.map(([id, w]) => {
    const f = Object.entries(w).filter(([k, v]) => k !== "name" && (!nonzero || !isZero(v))
      && (!ql || k.toLowerCase().includes(ql) || String((typen[k] || {}).name || "").toLowerCase().includes(ql)
          || String(w.name || "").toLowerCase().includes(ql)));
    if (!f.length && ql) return "";
    const lines = f.map(([k, v]) => [ismod ? `${esc((typen[k] || {}).name || k)} <span class="qu" data-quelle="${esc(k)}" title="woher kann das kommen?">ⓘ</span>` : esc(k),
                                   fmtVal(v, typen[k])]);
    return `<details ${rows.length === 1 ? "open" : ""}><summary><b>${esc(w.name || id)}</b> <span class="hint">${esc(id)} · ${f.length} Werte</span></summary>
      <div class="kv">${lines.map(([k, v]) => `<span>${k}</span><span>${v}</span>`).join("")}</div></details>`;
  }).join("");
  return `<div class="dbar"><select id="dart">${arts.map(a => `<option ${a === sel ? "selected" : ""} value="${a}">${a} (${Object.keys(al.werte[a]).length}) – ${al.datum[a]}</option>`).join("")}</select></div>
    <div class="dlist">${body || `<div class="empty">nichts gefunden</div>`}</div>`;
}

async function browserTexte(q) {
  const al = await dget("/api/alles?partie=" + encodeURIComponent(DB.partie));
  const T = (al && al.texte) || {};
  if (!Object.keys(T).length) return `<div class="empty">Noch keine Aufschlüsselungen (ab Daten-Mod 0.12).</div>`;
  const ql = q.toLowerCase();
  return `<div class="dlist">${Object.entries(T).map(([b, ids]) => {
    const inner = Object.entries(ids).map(([id, fs]) => {
      const f = Object.entries(fs).filter(([k, t]) => !ql || k.toLowerCase().includes(ql) || String(t).toLowerCase().includes(ql));
      return f.length ? `<details><summary>${esc(b)} ${esc(id)} <span class="hint">${f.length}</span></summary>
        ${f.map(([k, t]) => `<div class="card" style="margin:6px 0"><h3>${esc(k)}</h3><pre class="raw">${rawText(t)}</pre></div>`).join("")}</details>` : "";
    }).join("");
    return inner ? `<details><summary><b>${esc(b)}</b> <span class="hint">${Object.keys(ids).length}</span></summary>${inner}</details>` : "";
  }).join("")}</div>`;
}

async function browserRoh(q) {
  const r = await dget("/api/roh?partie=" + encodeURIComponent(DB.partie));
  if (!r || !Object.keys(r.roh || {}).length) return `<div class="empty">Noch keine Rohdaten (der Spielstand wird im Format 4 neu eingelesen).</div>`;
  const ql = q.toLowerCase();
  const keys = Object.keys(r.roh).filter(k => !ql || k.toLowerCase().includes(ql) || JSON.stringify(r.roh[k]).toLowerCase().includes(ql));
  return `<p class="hint">Alle Einträge des Spielstands ${esc(r.datum)} zum Spielerland, ungekürzt.</p>
    <div class="tree">${keys.map(k => treeNode(k, r.roh[k])).join("")}</div>`;
}

async function browserWissen(q) {
  const idx = await dget("/api/wissen?ordner=_index");
  if (!idx) return `<div class="empty">Spielwissen nicht gebaut.</div>`;
  const folders = Object.keys(idx).sort();
  const sel = folders.includes(store.get("db_ordner")) ? store.get("db_ordner") : "estate_privileges";
  const data = (await dget("/api/wissen?ordner=" + encodeURIComponent(sel))) || {};
  const ql = q.toLowerCase();
  const ent = Object.entries(data).filter(([k, v]) => !ql || k.toLowerCase().includes(ql) || String(v.name || "").toLowerCase().includes(ql)
    || JSON.stringify(v.def).toLowerCase().includes(ql));
  return `<div class="dbar"><select id="dordner">${folders.map(f => `<option ${f === sel ? "selected" : ""} value="${f}">${f} (${idx[f].anzahl})</option>`).join("")}</select>
      <span class="hint">${ent.length} von ${Object.keys(data).length}</span></div>
    <div class="tree">${ent.slice(0, 400).map(([k, v]) => treeNode(`${v.name ? v.name + " – " : ""}${k}`,
      Object.assign(v.beschreibung ? { beschreibung: v.beschreibung } : {}, typeof v.def === "object" && v.def !== null ? v.def : { wert: v.def }))).join("")}
    ${ent.length > 400 ? `<div class="hint">… ${ent.length - 400} weitere – Suche eingrenzen</div>` : ""}</div>`;
}

function renderBrowser(partie) {
  const root = $("#browser");
  // Die Seite baut sich jede Minute neu - der Browser nur bei Partiewechsel (sonst per ↻), damit
  // aufgeklappte Äste und die Suche stehen bleiben.
  const changed = partie !== DB.partie;
  if (changed) { DB.partie = partie; DB.cache = {}; }
  if (!root.dataset.built) {
    root.innerHTML = `<details class="sec" id="alle" ${openAttr("sec:alle", false)}><summary><div class="st">Alle Daten</div>
        <div class="head"><span class="mk"><small>Inhalt</small><b>Live-Werte · Aufschlüsselungen · Spielstand · Spielwissen</b></span></div></summary>
      <div class="body"><div class="tabs">${[["live", "Live-Werte"], ["texte", "Aufschlüsselungen"], ["roh", "Spielstand (roh)"], ["wissen", "Spielwissen"]]
        .map(([k, t]) => `<button data-tab="${k}">${t}</button>`).join("")}
        <label><input type="checkbox" id="dnz" checked> nur ≠ 0</label> <button id="dneu" title="neu laden">↻</button></div>
        <div class="dbar"><input type="search" id="dq" placeholder="Suchen (Schlüssel, Name, Text) …"></div>
        <div id="dinhalt" class="card"></div></div></details>`;
    root.dataset.built = "1";
    rememberToggles(root);
    root.querySelectorAll("[data-tab]").forEach(b => b.addEventListener("click", () => { DB.tab = b.dataset.tab; store.set("db_tab", DB.tab); fillBrowser(); }));
    let t;
    $("#dq").addEventListener("input", () => { clearTimeout(t); t = setTimeout(fillBrowser, 250); });
    $("#dnz").addEventListener("change", fillBrowser);
    $("#dneu").addEventListener("click", () => { DB.cache = {}; fillBrowser(); });
    $("#alle").addEventListener("toggle", () => { if ($("#alle").open) fillBrowser(); });
    wireTree($("#dinhalt"));
    $("#dinhalt").addEventListener("change", ev => {
      if (ev.target.id === "dart") { store.set("db_art", ev.target.value); fillBrowser(); }
      if (ev.target.id === "dordner") { store.set("db_ordner", ev.target.value); fillBrowser(); }
    });
    $("#dinhalt").addEventListener("click", async ev => {       // Modifikator: woher kann er kommen?
      const k = ev.target.dataset && ev.target.dataset.quelle;
      if (!k) return;
      const qs = (await dget("/api/wissen?ordner=_modifikator_quellen")) || {};
      const all = qs[k] || [];
      const list = all.slice(0, 60).map(x => `${x[0]} · ${x[1]}${x[2] ? " (" + x[2] + ")" : ""}: ${x.length > 4 ? x[4] : x[3]}`);
      ev.target.insertAdjacentHTML("afterend", `<div class="qu">${list.length ? list.map(esc).join("<br>") : "keine Quelle in den Spieldateien"}${all.length > 60 ? "<br>… " + (all.length - 60) + " weitere" : ""}</div>`);
      ev.target.removeAttribute("data-quelle");
    });
  }
  if (changed && $("#alle").open) fillBrowser();
}

async function fillBrowser() {
  if (!DB.partie || !$("#alle") || !$("#alle").open) return;
  document.querySelectorAll("#browser [data-tab]").forEach(b => b.classList.toggle("on", b.dataset.tab === DB.tab));
  const q = $("#dq").value.trim(), nz = $("#dnz").checked;
  $("#dinhalt").innerHTML = `<div class="empty">Lade …</div>`;
  const html = DB.tab === "live" ? await browserLive(q, nz) : DB.tab === "texte" ? await browserTexte(q)
    : DB.tab === "roh" ? await browserRoh(q) : await browserWissen(q);
  $("#dinhalt").innerHTML = html;
}
