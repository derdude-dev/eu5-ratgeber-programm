"use strict";
// Kachel Armee planen (0.31 Teil 3, Nutzer 08.11.: „armeebuilder, mit vorschlag zu armeegröße und zusammensetzung, äquivalent für
// marine“; auf der Seite seit 08.11. – bis dahin nur in der Seitenleiste im Spiel). Daten: d.armee aus eu5ratgeber/armee.py. Die
// Kopfwerte stehen genauso in der Seitenleiste (eu5ratgeber/ingame_kacheln.py armee, Vergleich in tests/test_ingame.py).
// Nutzt esc/fmt/pct/num/table/hd aus app.js und design.js, grLink aus gruendung.js.
THEME.armee = { icon: "🛡️", color: "--c5", group: "staat" };          // nach „Militär und Kriege“ im Bereich „Diplomatie und Militär“
if (typeof EMPF_KACHEL !== "undefined") EMPF_KACHEL.armee = "Armee planen";

// Was als Nächstes Mannstärke bringt (armee.naechste_quelle: [„bauen“ | „forschen“, Quelle]) – wie _quelle_wert in der Seitenleiste
function armeeQuelleWert(nq) {
  if (!nq) return "–";
  const [art, q] = nq;
  if (art === "bauen") return q.ort ? `${esc(q.name)} in ${esc(q.ort)} bauen` : `${esc(q.name)} bauen`;
  const a = (q.durch || [])[0] || {};
  return `Fortschritt „${esc(a.name || q.name)}“`;
}

// Vorschlag ohne Regimenter (armee.build vorschlag_leer) – wie _vorschlag_leer in der Seitenleiste
const armeeVorschlagLeer = g => ({ mannstaerke: "keins – Mannstärke fasst kein Regiment", zu_wenig: "keins – Mannstärke trägt zu wenig",
  traegt: "Mannstärke ausgeschöpft" })[g]
  || "Obergrenze erreicht";

function armeeKachel(d) {
  const A = d.armee || {}, h = A.heer || {}, m = A.marine || {};
  if (!A.heer) return { head: hd({ big: [{ l: "Regulärtruppen", v: "–" }] }),
                        body: '<p class="hint">Noch keine Werte – der Armeebuilder braucht die Monatswerte des Daten-Mods.</p>' };
  const vs = h.vorschlag || [], kr = h.krieg, au = h.ausser_reichweite, Q = h.quellen || [];
  const mischung = xs => xs.map(v => `${v.anzahl} × ${esc(v.einheit)}`).join(", ");
  const head = hd({
    big: [{ l: "Regulärtruppen", v: `${fmt(h.jetzt, 0)} <i>/ ${fmt(h.grenze, 0)}</i>`, bar: num(h.jetzt) && h.grenze ? h.jetzt / h.grenze : null,
            title: "stehendes Heer / Obergrenze laut Spiel (Mann), wie „Regulärtruppen ausheben“ im Militärfenster" },
          { l: "Vorschlag Heer", v: mischung(vs) || armeeVorschlagLeer(h.vorschlag_leer),
            title: `bis zur Obergrenze, höchstens so groß, wie die Mannstärke trägt (Zuwachs × ${fmt(h.erholung_monate, 0)} Monate, Spielwert der KI); Tross mindestens ${pct(A.tross_anteil, 0)} (Spielwert der KI), Kavallerie höchstens ein Drittel, je Kategorie die meiste Kampfkraft je Gold (Regel des Ratgebers)` },
          { l: "Für Krieg", v: kr ? `gegen ${esc(kr.name)}: +${fmt(kr.fehlt_mann, 0)} Mann` : au ? `${esc(au.name)}: außer Reichweite` : "kein Ziel mit fehlender Stärke",
            cls: au && !kr ? "neg" : "",
            title: kr ? (kr.mit_verbuendeten ? "mit Verbündeten geschätzt, Ziel 1,5 : 1 (Kriegsplan)" : "gegen das Land allein, Ziel 1,5 : 1")
              : au ? `Bündnis gegen Bündnis ${fmt(au.verhaeltnis, 2)} : 1 – mehr als doppelt so stark gilt als außer Reichweite (Regel des Ratgebers)` : "laut Kriegsplan" },
          { l: "Mannstärke-Quelle", v: armeeQuelleWert(h.naechste_quelle), title: "was als Nächstes Mannstärke bringt – Liste unten" }],
    small: [{ l: "Aufgebote", v: fmt(h.aufgebote, 0), title: "möglich (Mann); laut Spiel nur im Krieg oder bei Rebellen auszuheben" },
            { l: "Mannstärke", v: `${fmt(h.mannstaerke, 2)} <i>/ ${fmt(h.max_mannstaerke, 2)}</i>`, title: "in Tausend, wie in der Kopfzeile",
              cls: num(h.max_mannstaerke) && h.max_mannstaerke <= 0 ? "neg" : "" },
            { l: "Unterhalt Vorschlag", v: num(h.gold) ? `${fmt(h.gold, 2)} Gold / Monat` : "–", u: num(h.saldo) ? `Saldo ${fmt(h.saldo, 2)}` : "",
              title: "geschätzt: Unterhaltsgüter je Regiment × Preis im Heimatmarkt, ohne Regler und Modifikatoren" },
            { l: "Schiffe", v: `${fmt(m.jetzt, 0)} <i>/ ${fmt(m.erwartet, 0)}</i>`, title: "Schiffe / erwartete Marinegröße laut Spiel" }],
    warn: (h.grenzen || []).map(esc),
  });

  const vorschlag = `<div class="card"><h3>Vorschlag Heer</h3>
    ${vs.length ? table([{ t: "Einheit", l: true, f: v => esc(v.einheit) }, { t: "Kategorie", l: true, f: v => esc(v.kategorie || "–") },
        { t: "Anzahl", f: v => fmt(v.anzahl, 0) }, { t: "Mann", f: v => fmt(v.mann, 0) }, { t: "Gold / Monat", f: v => fmt(v.gold, 2) }], vs)
      : `<p class="hint">${esc(armeeVorschlagLeer(h.vorschlag_leer))}${h.vorschlag_leer === "obergrenze" ? " – oder keine Einheit freigeschaltet" : ""}.</p>`}
    <p class="hint">Regulärtruppen ${fmt(h.jetzt, 0)} von ${fmt(h.grenze, 0)} Mann (Obergrenze laut Spiel)${num(h.traegt) ? `; die Mannstärke trägt
      etwa ${fmt(h.traegt, 0)} Mann (Zuwachs ${fmt(h.zuwachs * (d.armee.regiment || 1000), 1)} Mann je Monat × ${fmt(h.erholung_monate, 0)} Monate: so viel
      Zuwachs will die KI des Spiels, um ihr ganzes Heer in dieser Zeit neu aufstellen zu können)` : ""}. Mischung: Tross mindestens
      ${pct(A.tross_anteil, 0)} wie die KI des Spiels, Kavallerie höchstens ein Drittel, je Kategorie die meiste Kampfkraft je Gold
      (Regel des Ratgebers). Unterhalt geschätzt aus den Preisen im Heimatmarkt.</p></div>`;

  const krieg = `<div class="card"><h3>Für den Krieg</h3>${kr
    ? `<p>Gegen <b>${esc(kr.name)}</b> fehlen etwa <b>${fmt(kr.fehlt_mann, 0)} Mann</b> für 1,5 : 1
        (${kr.mit_verbuendeten ? "mit ihren Verbündeten geschätzt" : "gegen das Land allein"}): etwa ${mischung(kr.mischung || []) || "–"}.</p>`
    : au ? `<p><b>${esc(au.name)}</b> ist außer Reichweite: Bündnis gegen Bündnis ${fmt(au.verhaeltnis, 2)} : 1, es fehlten
        ${fmt(au.fehlt_mann, 0)} Mann. Wer mehr als doppelt so stark ist, lässt sich mit Heer und Bündnissen nicht bald einholen (Regel des
        Ratgebers) – erst Wirtschaft, Mannstärke und Bündnisse.</p>`
    : `<p class="hint">Kein Ziel mit fehlender Stärke im Kriegsplan.</p>`}
    <p class="hint">Ziele aus dem Kriegsplan (Kachel Nachbarn und Kriegsgelegenheiten): Kriegsgrund vorhanden, bald oder schaffbar.</p></div>`;

  const stand = q => q.gebaut ? `${q.gebaut}× gebaut oder im Bau${num(q.belegt) ? `, ${fmt(q.belegt * 100, 0)} % besetzt` : ""}` : q.frei ? `<span class="pos">frei, nicht gebaut</span>`
    : (q.durch || []).length ? `Fortschritt ${q.durch.map(a => `„${esc(a.name)}“${typeof grLink === "function" ? grLink("techbaum/" + a.key, "🔬") : ""}`).join(" oder ")} nötig`
    : "nicht frei";
  const quellen = `<div class="card"><h3>Mannstärke</h3>
    <p class="hint">Laut Spiel kommt Mannstärke aus Mannstärke-Gebäuden oder bestimmten Fortschritten. Ohne Mannstärke lassen sich keine
      Regulärtruppen ausheben – im Krieg nur Aufgebote. Der Wert der Spieldatei gilt bei voller Belegschaft: ein neues Gebäude füllt sich nach
      und nach mit Arbeitern, die Mannstärke wächst mit.</p>
    ${table([{ t: "Gebäude", l: true, f: q => esc(q.name) }, { t: "Monatliche Mannstärke je Stufe (voll besetzt)", f: q => esc(q.wert_text || fmt(q.wert, 3)) },
      { t: "Ort", l: true, f: q => q.hauptstadt ? `nur Hauptstadt${q.ort ? ` (${esc(q.ort)})` : ""}` : "Orte mit unserer Kultur" },
      { t: "Stand", l: true, f: stand }], Q)}</div>`;

  const E = A.einheiten || [];
  const einheiten = `<div class="card"><h3>Freigeschaltete Einheiten</h3>
    ${table([{ t: "Einheit", l: true, f: e => esc(e.name) }, { t: "Kategorie", l: true, f: e => esc(e.kategorie_name || e.kategorie) },
      { t: "Kampfkraft", f: e => e.heer ? fmt(e.kampfkraft, 1) : "–" }, { t: "Mann", f: e => e.heer ? fmt(e.mann, 0) : "–" },
      { t: "Gold / Monat", f: e => fmt(e.gold, 2) }, { t: "Kampfkraft je Gold", f: e => fmt(e.je_gold, 2) },
      { t: "Unterhalt je Regiment bzw. Schiff", l: true, f: e => Object.entries(e.gueter || {}).map(([g, x]) => `${esc(g)} ${fmt(x, 2)}`).join(", ") || "–" }], E)}
    <p class="hint">Kampfkraft und Mann je Regiment aus den Spieldateien, Gold je Monat geschätzt aus den Preisen im Heimatmarkt.</p></div>`;

  const marine = `<div class="card"><h3>Marine</h3><div class="kv">
    <span>Schiffe / erwartete Marinegröße</span><span>${fmt(m.jetzt, 0)} / ${fmt(m.erwartet, 0)}</span>
    <span>Seeleute (Tsd.)</span><span>${fmt(m.seeleute, 2)} / ${fmt(m.max_seeleute, 2)}</span>
    <span>Schutz für Transporte</span><span>${pct(m.schutz_anteil, 0)} schwere Schiffe (Spielwert der KI)</span></div></div>`;

  return { head, body: `<p class="hint">Wie groß das Heer sein sollte und womit du es füllst: Regulärtruppen bis zur Obergrenze des Spiels,
    so weit die Mannstärke trägt, dazu der Bedarf für den Krieg mit dem besten Ziel in Reichweite (Kriegsplan). Der Vorschlag mischt Infanterie, Kavallerie und Tross nach
    einer Regel des Ratgebers; die Zahlen der Einheiten stehen so in den Spieldateien.</p>
    <div class="grid2">${vorschlag}${krieg}${quellen}${marine}</div>${einheiten}` };
}
