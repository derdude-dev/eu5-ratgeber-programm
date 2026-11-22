"use strict";
// Kachel Besonderheiten des Landes (0.31 Teil 4, Nutzer 08.11.: „in der übersicht sollte noch alles individuelle eines landes aufgelistet
// sein, was sie von anderen unterscheidet: besondere mechaniken, gesetze, einheiten, technologien, staatsformen usw.“). Im Spiel stehen
// sie in der Übersicht (Karten B1–B7, höchstens 22 Einträge je Tooltip), hier vollständig. Daten: d.besonderheiten aus
// eu5ratgeber/besonderheiten.py. Fortschritte verweisen in den Techbaum, andere Einträge ins Wiki, wo es sie führt.
// Nutzt esc/fmt/num/table/hd/store aus app.js und design.js, grLink aus gruendung.js.
THEME.besonderheiten = { icon: "✨", color: "--c3", group: "ratgeber" };   // nach der Startstrategie im Bereich „Ratgeber“
if (typeof EMPF_KACHEL !== "undefined") EMPF_KACHEL.besonderheiten = "Besonderheiten des Landes";

const BES_STATUS = { researched: ["pos", "erforscht"], active: ["pos", "aktiv"], unlocked: ["pos", "freigeschaltet"] };
const BES_ZEITALTER = z => { const m = String(z || "").match(/^age_(\d+)_/); return m ? `Zeitalter ${m[1]}` : ""; };

function besonderheitenKachel(d) {
  const B = d.besonderheiten;
  if (!B || !B.grundlagen) return { head: hd({ big: [{ l: "Besonderheiten", v: B?.fehler ? "?" : "–" }], warn: [B?.fehler && esc(B.fehler)] }),
    body: `<p class="hint">${B?.fehler ? "Fehler beim Auswerten: " + esc(B.fehler) : "Noch keine Daten – der Ratgeber braucht einen Spielstand."}</p>` };
  const g = B.grundlagen, arten = B.arten || [];
  const kultur = (g.kultur || "–") + ((g.kulturgruppen || []).length ? ` (${g.kulturgruppen.join(", ")})` : "");
  const religion = (g.religion || "–") + (g.religionsgruppe ? ` (${g.religionsgruppe})` : "");
  const n = arten.reduce((s, a) => s + a.anzahl, 0);
  const head = hd({
    big: [{ l: "Land", v: `${esc(g.land || "–")} <i>${esc(g.tag || "")}</i>`, title: g.hauptstadt ? `Hauptstadt ${g.hauptstadt}` : "" },
          { l: "Kultur", v: esc(kultur) }, { l: "Religion", v: esc(religion) },
          { l: "Regierungsform", v: esc(g.regierungsform || "–") }],
    small: [{ l: "Besonderheiten", v: String(n), title: "alles, was die Spieldateien an Land, Kultur, Religion oder Lage der Hauptstadt binden und für uns zutrifft" },
            ...arten.map(a => ({ l: a.name, v: a.aktiv ? `${a.aktiv} <i>/ ${a.anzahl}</i>` : String(a.anzahl),
                                 title: a.aktiv ? "erforscht, aktiv oder freigeschaltet / alle" : "Anzahl" }))],
    warn: [],
  });
  const link = x => typeof grLink !== "function" ? "" : x.techbaum ? grLink(x.techbaum, "🔬") : x.wiki ? grLink(x.wiki) : "";
  const stand = x => { const s = BES_STATUS[x.status]; return s ? `<span class="${s[0]}">${s[1]}</span>` : ""; };
  const karten = arten.map(a => `<div class="card"><h3>${esc(a.name)} <span class="hint">${a.anzahl}${a.aktiv ? `, davon ${a.aktiv} erforscht, aktiv oder freigeschaltet` : ""}</span></h3>
    ${table([{ t: "Name", l: true, f: x => `${esc(x.name)}${link(x)}` }, { t: "Art", l: true, f: x => esc(x.typ || "") },
      { t: "Grund", l: true, f: x => (x.gruende || []).map(r => esc(r.text)).join("<br>") }, { t: "Stand", l: true, f: stand },
      ...(a.key === "fortschritte" ? [{ t: "Zeitalter", l: true, f: x => BES_ZEITALTER(x.zeitalter) }] : [])], a.eintraege)}</div>`).join("");
  return { head, body: `<p class="hint">Was dein Land von anderen unterscheidet: Einträge der Spieldateien, deren Sichtbarkeit an das Land, seine
    Kultur, seine Religion oder die Region der Hauptstadt gebunden ist und für uns zutrifft – dazu, was diese Fortschritte freischalten.
    Regierungsform, Rang, Zeitalter und Kontinent allein zählen nicht, die teilen viele Länder.${B.offen ? ` ${B.offen} weitere hängen
    zusätzlich an Bedingungen, die der Ratgeber nicht prüfen kann.` : ""}</p>${karten || '<p class="hint">Keine Besonderheiten gefunden.</p>'}` };
}
