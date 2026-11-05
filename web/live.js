"use strict";
// EU5 Ratgeber – Live-Daten des Mods (ab 0.12, /api/alles) in den Kacheln.
// Jede Kachel bekommt: weitere Kopfwerte, die wichtigsten Aufschlüsselungen des Spiels direkt sichtbar und
// "alle Live-Daten zum Thema" (Landeswerte und Land-Modifikatoren nach Stichwort, zugehörige Bereiche, alle Texte).
// Nutzt Helfer aus app.js (esc, fmt, pct, sgn, mk, kv, table, rawText, openAttr, posneg).

// Stichworte je Thema für die Landeswerte (RG2 land) und Land-Modifikatoren (Schlüssel sind Code-Namen des Spiels).
// Ein Wert kann in mehreren Kacheln stehen; was nirgends passt, zeigt die Kachel "Land" unter "übrige".
const TOPIC_RX = {
  finanzen: /gold|income|balance|maintenance|debt|loan|bond|credit|bankrupt|inflation|mint|coin|^eco_|tax_base|wealth|economical|gdp|upkeep|expense|slider|interest/i,
  handel: /trade|merchant|market|caravan|sound_toll/i,
  staende: /estate|esttax|estsat|esttsat|estpriv|privilege|crown_power|enfranch/i,
  land: /control|development|location|province|^rank_|capital|great_power|power_projection|country_rank|country_strength|historical|^climate|^topography|^vegetation|coastal|proximity|integration|prosperity/i,
  forschung: /institution|advance|research|innovat/i,          // eigene Kachel seit 30.09.
  regierung: /legitim|government|reform|law|parliament|cabinet|bureaucra|societal|^sv_|ruler|complacency|republican|horde|tribal|stability|prestige|dynast|heir|character/i,
  diplomatie: /^dip_|subject|rival|alliance|ally|union|casus|annex|antagon|relation|diplomat|liberty|loyal|overlord|hegemon|neutral|releasable|spy|favor|trust|opinion/i,
  religion: /religi|devotion|doom|karma|purity|righteous|harmony|yanantin|rite_power|honor|self_control|cardinal|holy_site|avatar|gods?_|omen|heathen|heretic|faith|liturgical|tolerance|papal|missionar|tithe|cultur|assimil|accepted_culture|language|artist|work_of_art|works_of_art|art_quality|art_start/i,
  mehr: /army|navy|manpower|sailor|regiment|levy|levies|fort|military|morale|war|^sucount|^sustrength|^sutype|mercenar|ship|siege|fleet|experience|tradition|attrition|garrison|rebel|disaster|explor|colon|privateer/i,
  gueter: /^world_|^produced_|goods|food/i,
  produktion: /^bleff_|^bltot_|building|rgo|raw_material|production|construction/i,
};
// Nicht in „Alle Live-Daten zum Thema“: Zähler je Einheiten-/Gebäudetyp; beim Militär außerdem nur Werte ≠ 0 (Nutzerwunsch 01.10.)
const TOPIC_SKIP = { mehr: /^(sutype_|sucount_|sustrength_|sufrac_|sustr_|sucat_|bltot_|bleff_)/ };
const TOPIC_NONZERO = new Set(["mehr"]);
// Bereiche (RG2-Arten) und Texte (RG1I-Bereiche) je Kachel
const TILE_LIVE = {
  finanzen: { arts: [], texte: ["eco", "regler"], landText: /Income|Tax|Credit|Wealth|Economical|Cost|Upkeep|Loan|Bond|Debt|Spending/ },
  handel: { arts: ["handel"], texte: ["handel"], landText: /Trade/ },
  staende: { arts: ["stand", "privileg"], texte: ["stand", "privileg"], landText: /Crown|Estate/ },
  land: { arts: ["gebiet", "provinz", "provinzmod", "landgeo"], texte: ["gebiet", "provinz"],
          landText: /Control|Capital|GreatPower|Regional|Owned|Objectives|History|Description|Type|Flavor|Area|Towns|Power/ },
  forschung: { arts: ["institution"], texte: ["institution"], landText: /Institution|Advance|Age|Research|Liturgical/ },
  regierung: { arts: ["kabinett", "kabinettsaktion", "gesetz", "reform", "politik", "parlament", "buerokratie", "person", "personmod",
                      "dynastie", "dynastiemod"],
               texte: ["kabinett", "kabinettsaktion", "gesetz", "reform", "politik", "parlament", "buerokratie", "person", "dynastie"],
               landText: /Character|Bureaucrac|Court|Employment|Regency/ },
  diplomatie: { arts: ["fremd", "io", "iomod", "reichskreis"], texte: ["dip", "io", "reichskreis"], landText: /Relation|Subject|Diplomatic/ },
  religion: { arts: ["religion", "religionmod", "glaubensaspekt", "glaubensfokus", "heiligtum", "gott", "avatar", "omen", "kardinal", "kultur", "kunstwerk"],
              texte: ["religion", "glaubensaspekt", "glaubensfokus", "heiligtum", "gott", "avatar", "omen", "kardinal", "kultur", "kunstwerk"],
              landText: /Religi|Liturgical|Cultur|Art/ },
  markt: { arts: ["markt"], texte: ["markt"] },
  gueter: { arts: ["gut"], texte: ["gut"] },
  produktion: { arts: ["gebaeude", "gebaeudetyp"], texte: ["gebaeude"] },
  mehr: { arts: ["einheit", "einheitmod", "untereinheit", "krieg", "soeldner", "katastrophe", "freibeuter", "erkundung",
                 "kolonie", "bewegung", "stadtrecht", "rebell"],
          texte: ["einheit", "untereinheit", "krieg", "kredit", "soeldner", "katastrophe", "freibeuter", "erkundung", "kolonie",
                  "bewegung", "stadtrecht", "rebell"],
          landText: /Army|Navy|Manpower|Sailor|Levy|Fort|Morale|Military|Blockade|Starving|Winter|Units|Strength/ },
};
const ART_TITLE = { handel: "Handelsrouten", stand: "Stände", privileg: "Privilegien", gebiet: "Gebiete", provinz: "Provinzen",
  provinzmod: "Provinz-Modifikatoren", landgeo: "Geografie (Anzahl Orte)", institution: "Institutionen", kabinett: "Kabinett",
  kabinettsaktion: "Kabinettsaktionen", gesetz: "Gesetze", reform: "Reformen", politik: "Politik", parlament: "Parlamentsthemen",
  buerokratie: "Bürokratie", person: "Personen", personmod: "Personen-Modifikatoren", dynastie: "Dynastie",
  dynastiemod: "Dynastie-Modifikatoren", fremd: "Länder mit Beziehung", io: "Organisationen", iomod: "Organisations-Modifikatoren",
  reichskreis: "Reichskreis", religion: "Religion", religionmod: "Religions-Modifikatoren", glaubensaspekt: "Glaubensaspekte",
  glaubensfokus: "Glaubensfokus", heiligtum: "Heilige Stätten", gott: "Götter", avatar: "Avatare", omen: "Omen",
  kardinal: "Kardinäle", markt: "Märkte", gut: "Güter", gebaeude: "Gebäude", gebaeudetyp: "Baubare Gebäudetypen",
  einheit: "Einheiten", einheitmod: "Einheiten-Modifikatoren", untereinheit: "Untereinheiten", krieg: "Kriege", kredit: "Kredite",
  soeldner: "Söldner", katastrophe: "Katastrophen", freibeuter: "Freibeuter", erkundung: "Erkundungen", kolonie: "Kolonien",
  bewegung: "Bewegungen", kunstwerk: "Kunstwerke", stadtrecht: "Stadtrechte", rebell: "Rebellen", eco: "Wirtschaft",
  regler: "Regler", dip: "Diplomatie", land: "Land", ort: "Ort", pop: "Pops", kultur: "Kultur" };
// Aufschlüsselungen, die direkt (ohne Aufklappen der Live-Daten) in der Kachel stehen: [Bereich, Feld, Titel, dazu]
// dazu (optional) = weitere [Bereich, Feld, Titel], die in derselben Karte darunter stehen;
// part.vor = { Feld: HTML } aus der Kachel steht in der Karte über der Aufschlüsselung (Finanzen: Kreditbezug)
const TILE_TEXTS = {
  // Einkommens-Tooltip steckt in der Einnahmen-Karte (app.js); GetTaxBaseInfo = Orte + Spitzenwaren -> getrennt
  finanzen: [["land", "GetTaxBaseLocationInfo", "Steuerbasis – Orte"], ["land", "GetTaxBaseGoodsInfo", "Spitzenwaren nach Steuergrundlage"],
             ["land", "GetCreditworthinessInfo", "Kreditwürdigkeit", [["eco", "GetTotalDebtImpactDesc", "Schulden – Wirkung"]]]],
  handel: [],        // Handelsverbindungen stehen in der Karte Handelsrouten (app.js)
  staende: [],       // Macht und Ausgewogenheit stehen aufklappbar in den Stand-Karten (app.js, 01.10.)
  land: [],          // Kontrolle, Großmacht, Hauptstadt-Bonus in den Karten von „Land und Leute“; Institutionen in „Forschung“ (30.09.)
  forschung: [],
  regierung: [],     // Wirkungen von Kabinett, Gesetzen und Reformen stehen aufklappbar in deren Zeilen (app.js, 30.09.)
  diplomatie: [],    // Diplomaten und Kapazität mit Aufschlüsselung in der Karte „Diplomatiekapazität und Diplomaten“ (app.js, 01.10.)
  religion: [],      // Reformwunsch und Wirkung der Religion stehen aufklappbar in der Karte des Glaubens (app.js, 01.10.)
  markt: [],         // Nahrung – Produktion/Einfuhr/Ausfuhr/Preis stehen in der Karte „Nahrung“ (app.js, 30.09.)
  mehr: [],          // Aufgebote, Mannstärke und Festungen stehen aufklappbar in den Karten (app.js, 01.10.)
};
// Text vor der Anzeige bereinigen (Feld -> Funktion). Spitzenwaren: Überschrift „• Spitzen-Waren …“ und die
// Zwischenüberschriften „Spitzenorte in Sachen … für Steuergrundlage“ raus (Zeilen ohne Wert, Nutzerwunsch 29.09.)
const TEXT_CLEAN = {
  GetTaxBaseGoodsInfo: x => String(x).split("\n").filter(z => z.includes(":")).join("\n"),
};
// weitere Kopfwerte je Kachel: [Titel, Wert-Funktion(Land-Werte, alle Werte)]
const TILE_HEAD = {
  finanzen: [],                                         // Einkommen/Jahr, Kreditwürdigkeit, Schulden: fester Kopf in app.js
  handel: [],        // Handelsbilanz = Gewinn der Routen, Händlerkapazität gesamt = Händlerkapazität (doppelt, entfernt 29.09.)
  staende: [],       // „Ø Zufriedenheit der Stände“ steht im festen Kopf (app.js, 01.10.)
  land: [],          // Institutionen stehen groß in der Kachel „Forschung“ (30.09.)
  forschung: [],
  regierung: [],     // Legitimität und Stabilität stehen in der Kopfzeile, Regierungsmacht = Legitimität (entfernt 30.09.)
  diplomatie: [],    // Diplomaten (1,6 / 1,0 – vorher auf ganze Zahlen gerundet „2 / 1“) und Kapazität im festen Kopf (app.js, 01.10.)
  religion: [],      // „Gläubige weltweit … in x Ländern“ steht im festen Kopf (app.js, 01.10.)
  markt: [],         // Nahrungsvorrat und Saldo stehen groß im Kopf (app.js, 30.09.)
  mehr: [],          // Militärstärke, Mannstärke und Seeleute im festen Kopf (app.js, 01.10.)
};

// ---------------------------------------------------------------- Bausteine
const LAZY = new Map();          // id -> Funktion, die den Inhalt baut (erst beim Aufklappen)
let lazyN = 0;
function lazy(key, summary, build) {
  const id = "lz" + (++lazyN);
  LAZY.set(id, build);
  return `<details class="more" data-lazy="${id}" ${openAttr(key, false)}><summary>${summary}</summary><div class="lazyc"></div></details>`;
}
function fillLazy(root = document) {
  root.querySelectorAll("details[data-lazy]").forEach(el => {
    const fill = () => { const c = el.querySelector(":scope > .lazyc"); if (el.open && c && !c.dataset.done) { c.innerHTML = LAZY.get(el.dataset.lazy)?.() || ""; c.dataset.done = "1"; fillLazy(c); } };
    el.addEventListener("toggle", fill);
    fill();
  });
}
const isFlag = k => /^(Has|Is|Can|Are|Was|Contains|Should|Will|Auto|Benefits|Meets|Requires|Needs|Build|Converts|Lift|Only|In|Character|Uses)[A-Z]/.test(k);
function val(k, v, M) {
  if (M && M[k]) {                         // Modifikator: Anzeige wie im Spiel (Prozent/schon Prozent)
    if (M[k].percent) return pct(v, 1);
    if (M[k].already_percent) return fmt(v, 2) + " %";
    return sgn(v, Math.abs(v) < 1 ? 3 : 2);
  }
  if (typeof v !== "number") return esc(String(v ?? "–"));
  if (isFlag(k) && (v === 0 || v === 1)) return v ? "ja" : "nein";
  return fmt(v, Math.abs(v) >= 100 ? 1 : 3);
}
const label = (k, M) => M && M[k]?.name ? `${esc(M[k].name)} <span class="code">${esc(k)}</span>` : deL(k);
// Titel eines Aufschlüsselungs-Feldes (Funktionsname des Spiels) -> deutsch
const tl = f => (typeof POP_TEXT !== "undefined" && POP_TEXT[f]) || de(f);
// Werte eines Objekts als Liste; Modifikatoren mit Namen, nur ≠ 0
function valueList(obj, { M = null, nonzero = false, rx = null } = {}) {
  const rows = Object.entries(obj || {}).filter(([k, v]) => k !== "name" && (!rx || rx.test(k)) && (!nonzero || (v !== 0 && v != null)))
    .sort(([a], [b]) => a.localeCompare(b));
  return rows.length ? `<div class="kv">${rows.map(([k, v]) => `<span>${label(k, M)}</span><span>${val(k, v, M)}</span>`).join("")}</div>`
    : `<div class="empty">keine Werte</div>`;
}
// Name eines Objekts (Ort, Gebäude, Stand … über die Kennung)
function objName(art, id, obj, N) {
  if (obj?.name) return obj.name;
  return (N[art] && N[art][id]) || String(id);
}
// Ein Bereich: bis 6 Objekte als Karten, mehr als Tabelle (Zeilen = Objekte, Spalten = Felder)
function artBlock(art, objs, M, N) {
  const ids = Object.keys(objs || {});
  if (!ids.length) return "";
  const isMod = art.endsWith("mod");
  const title = `${esc(ART_TITLE[art] || art)} (${ids.length})`;
  if (isMod || ids.length <= 6) {
    return `<div class="card"><h3>${title}</h3>${ids.map(id => `${ids.length > 1 ? `<div class="sect">${esc(objName(art, id, objs[id], N))}</div>` : ""}
      ${valueList(objs[id], { M: isMod ? M : null, nonzero: isMod })}`).join("")}</div>`;
  }
  const fields = [...new Set(ids.flatMap(id => Object.keys(objs[id])))].filter(k => k !== "name").sort();
  const cols = [{ t: "", l: true, f: id => esc(objName(art, id, objs[id], N)) }, ...fields.map(k => ({ t: de(k), f: id => val(k, objs[id][k]) }))];
  return `<div class="card"><h3>${title}</h3>${table(cols, ids)}</div>`;
}
// Texte eines Bereichs: je Objekt aufklappbar, darin je Feld der Text
function textBlock(bereich, objs, N, keyPrefix) {
  const ids = Object.keys(objs || {});
  if (!ids.length) return "";
  return `<div class="card"><h3>Aufschlüsselungen – ${esc(ART_TITLE[bereich] || bereich)} (${ids.length})</h3>${ids.map(id =>
    lazy(`${keyPrefix}:${bereich}:${id}`, `${esc(objName(bereich, id, null, N))} <span class="hint">${Object.keys(objs[id]).length} Texte</span>`,
      () => Object.entries(objs[id]).map(([f, t]) => lazy(`${keyPrefix}:${bereich}:${id}:${f}`, `${esc(tl(f))} <span class="code">${esc(f)}</span>`,
        () => breakdown(t))).join(""))).join("")}</div>`;
}

// ---------------------------------------------------------------- je Kachel
// Namen für Objekte ohne eigenes Namensfeld
function liveNames(d, P) {
  const N = { ort: {}, gebaeude: {}, stand: {}, handel: {}, provinz: {}, markt: {}, gut: {} };
  for (const o of P.orte || []) N.ort[o.id] = o.name;
  for (const b of P.LD.gebaeude || []) N.gebaeude[b.id] = `${b.name} (${b.ort || b.ort_id})`;
  for (const e of P.A.staende || []) N.stand[e.stand] = e.name;
  const gn = (P.W.namen || {}).gueter || {};
  for (const t of P.LD.handel || []) N.handel[t.id] = `${gn[t.gut] || t.gut_name || t.gut}`;
  for (const [k, v] of Object.entries(gn)) N.gut[k] = v;
  for (const [id, o] of Object.entries(d.alles?.werte?.provinz || {})) N.provinz[id] = o.name;
  for (const [id, o] of Object.entries(d.alles?.werte?.markt || {})) N.markt[id] = o.name;
  N.land = { [d.meta.tag]: d.meta.land };
  return N;
}

// nur = { art: id } schränkt Bereiche auf ein Objekt ein (Kachel je Markt: { markt: <Markt-ID> })
function withLive(id, part, d, P, nur = {}) {
  const A = d.alles;
  // ohne Mod-Daten: vor-Blöcke als eigene Karten unter den Inhalt
  // part.nach = weitere Abschnitte zwischen Übersicht und „Alle Live-Daten“ (Land und Leute: die Bevölkerungs-Abschnitte)
  const ohne = () => { const p0 = part?.vor ? { ...part, body: (part.body || "") + `<div class="grid2">${Object.entries(part.vor).map(([f, h]) =>
    `<div class="card"><h3>${esc((TILE_TEXTS[id] || []).find(e => e[1] === f)?.[2] || f)}</h3>${h}</div>`).join("")}</div>` } : part;
    return p0?.nach ? { ...p0, body: (p0.body || "") + p0.nach } : p0; };
  if (!A || !A.werte || !(id in TILE_LIVE || id in TOPIC_RX)) return ohne();
  const p = typeof part === "string" ? { body: part } : { ...(part || {}) };
  if (!p.body && !p.head && !Object.keys(A.werte).length) return ohne();
  const vor = p.vor || {};
  const only = (src, a) => a in nur ? Object.fromEntries(Object.entries(src[a] || {}).filter(([k]) => String(k) === String(nur[a]))) : src[a];
  const W = Object.fromEntries(Object.keys(A.werte).map(a => [a, only(A.werte, a)]));
  const T = Object.fromEntries(Object.keys(A.texte || {}).map(a => [a, only(A.texte, a)]));
  const M = A.modnamen || {}, N = P.liveNames;
  const land = Object.values(W.land || {})[0] || {}, lmod = Object.values(W.landmod || {})[0] || {};
  const cfg = TILE_LIVE[id] || { arts: [], texte: [] }, rx = TOPIC_RX[id];
  // Kopf
  const hdx = (TILE_HEAD[id] || []).map(([t, f]) => { const v = f(land, W); return v && v !== "–" && !/^–/.test(v)
    ? `<span class="hk" title="live aus dem Daten-Mod"><small>${esc(t)}</small><b>${v}</b></span>` : ""; }).join("");
  // direkt sichtbare Aufschlüsselungen
  const teil = ([b, f, t]) => Object.entries(T[b] || {}).filter(([, o]) => o[f])
    .map(([oid, o]) => ({ t: `${esc(t)}${Object.keys(T[b]).length > 1 ? ` – ${esc(objName(b, oid, null, N))}` : ""}`, x: TEXT_CLEAN[f] ? TEXT_CLEAN[f](o[f]) : o[f] }));
  const card = (c, dazu = [], oben = "") => `<div class="card"><h3>${c.t}</h3>${oben}${c.x != null ? breakdown(c.x) : ""}${dazu.map(e =>
    `<h3 style="margin-top:10px">${e.t}</h3>${breakdown(e.x)}`).join("")}</div>`;
  const shown = (TILE_TEXTS[id] || []).flatMap(([b, f, t, dazu = []]) => {
    let main = teil([b, f, t]);
    const extra = dazu.flatMap(teil);
    if (!main.length && vor[f]) main = [{ t: esc(t), x: null }];          // Aufschlüsselung fehlt, Kachel-Werte trotzdem zeigen
    return main.length ? main.map((c, i) => card(c, i ? [] : extra, i ? "" : vor[f] || "")) : extra.map(e => card(e));
  });
  // alle Live-Daten zum Thema
  const unmatched = id === "land" ? Object.fromEntries(Object.entries(land).filter(([k]) => !Object.values(TOPIC_RX).some(r => r.test(k)))) : null;
  const skip = TOPIC_SKIP[id], nz = TOPIC_NONZERO.has(id);
  const landSel = rx ? Object.fromEntries(Object.entries(land).filter(([k, v]) => rx.test(k) && !(skip && skip.test(k)) && (!nz || (v !== 0 && v != null)))) : {};
  const nLand = Object.keys(landSel).length;
  const nMod = rx ? Object.entries(lmod).filter(([k, v]) => v && rx.test(k) && !(skip && skip.test(k))).length : 0;
  const arts = cfg.arts.filter(a => Object.keys(W[a] || {}).length);
  const landTexts = cfg.landText ? Object.keys((Object.values(T.land || {})[0]) || {}).filter(f => cfg.landText.test(f)) : [];
  const texte = cfg.texte.filter(b => Object.keys(T[b] || {}).length);
  const nTexte = texte.reduce((s, b) => s + Object.keys(T[b]).length, 0) + landTexts.length;
  const key = "live:" + id + Object.values(nur).join(":");
  const inner = () => `<div class="grid2">
      ${rx ? `<div class="card"><h3>Landeswerte zum Thema (${nLand})</h3>${valueList(landSel)}</div>` : ""}
      ${unmatched ? `<div class="card"><h3>übrige Landeswerte (${Object.keys(unmatched).length})</h3>${valueList(unmatched)}</div>` : ""}
      ${rx ? `<div class="card"><h3>Land-Modifikatoren ≠ 0 (${nMod})</h3>${valueList(skip ? Object.fromEntries(Object.entries(lmod).filter(([k]) => !skip.test(k))) : lmod, { M, nonzero: true, rx })}</div>` : ""}
      ${arts.map(a => artBlock(a, W[a], M, N)).join("")}
      ${landTexts.length ? `<div class="card"><h3>Aufschlüsselungen – Land (${landTexts.length})</h3>${landTexts.map(f =>
        lazy(`${key}:land:${f}`, `${esc(tl(f))} <span class="code">${esc(f)}</span>`, () => breakdown(Object.values(T.land)[0][f]))).join("")}</div>` : ""}
      ${texte.map(b => textBlock(b, T[b], N, key)).join("")}</div>`;
  const sum1 = `Alle Live-Daten zum Thema <span class="hint">${nLand} Landeswerte · ${nMod} Modifikatoren · ${arts.length} Bereiche · ${nTexte} Texte · Mod ${esc(A.datum?.land || "")}</span>`;
  // Gliederung: Übersicht (die Kachel selbst, darunter ohne eigene Überschrift die Aufschlüsselungen aus dem Spiel;
  // Nutzerwunsch 29.09., alle Kacheln) · alle Live-Daten zum Thema
  const grid = shown.length ? `<div class="grid2">${shown.join("")}</div>` : "";
  const extra = sect("Alle Live-Daten zum Thema", lazy(key, sum1, inner));
  const head = (p.head || "").includes("<!--klein-->") ? p.head.replace("<!--klein-->", hdx + "<!--klein-->") : (p.head || "") + hdx;
  const ueb = (p.body || "") + grid;
  return { head, body: (ueb ? sect("Übersicht", ueb) : "") + (p.nach || "") + extra };
}

// Orte: alle Live-Werte, Modifikatoren und Texte je Ort (in der Orts-Kachel)
function ortLive(d, o) {
  const A = d.alles; if (!A?.werte) return "";
  const w = A.werte.ort?.[o.id], m = A.werte.ortmod?.[o.id], t = A.texte?.ort?.[o.id];
  if (!w && !m && !t) return "";
  const M = A.modnamen || {};
  return lazy(`ort:${o.id}:live`, `Alle Live-Daten des Ortes <span class="hint">${Object.keys(w || {}).length} Werte · ${Object.values(m || {}).filter(v => v).length} Modifikatoren · ${Object.keys(t || {}).length} Texte</span>`,
    () => `${w ? `<div class="sect">Werte</div>${valueList(w)}` : ""}${m ? `<div class="sect">Modifikatoren ≠ 0</div>${valueList(m, { M, nonzero: true })}` : ""}
      ${t ? `<div class="sect">Aufschlüsselungen</div>${Object.entries(t).map(([f, x]) => lazy(`ort:${o.id}:t:${f}`, `${esc(tl(f))} <span class="code">${esc(f)}</span>`, () => breakdown(x))).join("")}` : ""}`);
}
