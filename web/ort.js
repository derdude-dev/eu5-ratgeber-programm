"use strict";
// EU5 Ratgeber – eine Kachel je eigenem Ort (Nutzerwunsch 29.09.): wichtige Werte im Kopf, darunter alle Faktoren.
// Quellen: Spielstand (aktuell.orte), Kartendaten (wissen.orte), Live-Zeile (live_details.orte), Mod (alles.werte.ort/
// ortmod, alles.texte.ort), Bevölkerung (/api/bevoelkerung). Der Inhalt wird erst beim Öffnen gebaut (sec lazy).
// Nutzt Helfer aus design.js, live.js und app.js.

const STATUS_GEB = { LayingOff: "entlässt Arbeiter (LayingOff)" };
// Aufschlüsselungen, die in der Orts-Kachel direkt stehen: [Feld, Titel]
// GetTaxBaseInformation fehlt bewusst: liefert nur die Überschrift „Steuergrundlage von „Hoorn““ (geprüft 01.10.)
const ORT_TEXTE = [["GetControlInfo", "Kontrolle"],
  ["GetMonthlyDevelopmentChangeInfo", "Entwicklung – Veränderung"], ["GetProsperityChangeInfo", "Wohlstand – Veränderung"],
  ["GetPopGrowthInfo", "Bevölkerungswachstum"], ["GetPopulationCapacityInfo", "Bevölkerungskapazität"],
  ["GetMarketAccessBreakdown", "Marktzugriff"], ["GetRawMaterialsOutputBreakdown", "Rohstoff-Ausstoß"]];

function ortTile(d, P, o) {
  const L = o.L || {}, w = o.w || {}, A = d.alles?.werte || {}, T = d.alles?.texte?.ort?.[o.id] || {};
  const lw = A.ort?.[o.id] || {}, lm = A.ortmod?.[o.id] || {}, M = d.alles?.modnamen || {};
  const b = (d.bev?.orte || []).find(x => x.id === o.id) || {};
  const gn = (P.W.namen || {}).gueter || {};
  const pop = L.population ?? b.groesse ?? o.bev, cap = L.max_population ?? b.kapazitaet;
  const ch = b.veraenderung;
  const minus = (o.gebaeude || []).filter(g => (g.gewinn ?? 0) < 0);
  const krank = Object.entries(lw).filter(([k, v]) => k.startsWith("disease_") && v > 0);
  // Kopf: festes Raster 4 × 3 (gleiche Stelle in jeder Ortskachel), Anteile mit kleinem Balken
  const ctrl = L.control ?? o.kontrolle, mkt = L.market_access ?? o.marktzugang, zuf = L.satisfaction ?? b.zufriedenheit;
  const head = hd({
    // Rang steht schon im Titel (Unterzeile); Reihenfolge nach Wunsch des Nutzers (29.09.)
    big: [{ l: "Bevölkerung (Tsd.)", v: fmt(pop, 2), t: trend(ch, 3, 1), title: "Trend = Veränderung im letzten Monat (Spielstand)" },
          { l: "Kontrolle", v: `${pct(ctrl, 0)} <i>max ${pct(L.max_control, 0)}</i>`, bar: ctrl },
          { l: "Steuergrundlage / möglich", v: `${fmt(o.steuer, 2)} <i>/ ${fmt(o.moegliche_steuer, 2)}</i>`,
            bar: num(o.steuer) && o.moegliche_steuer ? o.steuer / o.moegliche_steuer : null,
            title: "Steuergrundlage gegen mögliche Steuergrundlage (Spielwerte GetTotalTaxBase / GetTotalPossibleTaxBase, Spielstand). Balken = Anteil an der möglichen." }],
    cols: 4,
    small: [{ l: "Entwicklung", v: fmt(L.development ?? o.entwicklung, 1) },
            { l: "Wohlstand", v: fmt(L.prosperity ?? o.wohlstand, 2) },
            { l: "Nähe", v: fmt(L.proximity ?? o.naehe, 0), bar: num(L.proximity ?? o.naehe) ? (L.proximity ?? o.naehe) / 100 : null },
            { l: "Zufriedenheit", v: pct(zuf, 0), bar: zuf },
            { l: "Rohstoff (Ausstoß)", v: `${esc(gn[o.rohstoff] || o.rohstoff || "–")}${L.rgo_output != null ? ` <i>${fmt(L.rgo_output, 2)}</i>` : ""}` },
            { l: "Gebäudeunterhalt", v: fmt(ortUnterhalt(o, lw), 2),
              title: "Unterhalt der Landesgebäude im Ort (Tempel, Marktplatz, Getreidespeicher, Kai, Burg …), Spielwert GetTotalUpkeep – kein Gebäudegewinn" },
            { l: "Marktzugriff", v: pct(mkt, 0), bar: mkt },
            { l: "", v: "" },                                   // Zeile 2 endet hier; Kapazität beginnt Zeile 3
            { l: "Bev.-Kapazität", v: cap ? pct(pop / cap, 0) : "–", bar: cap ? pop / cap : null,
              title: "Bevölkerung im Verhältnis zur Bevölkerungskapazität des Ortes (gleich dem Spielwert GetCapacityPercentage). Wie sich die Kapazität zusammensetzt: Aufschlüsselung „Bevölkerungskapazität“ in der Kachel." },
            { l: "Bildung Ø", v: fmt(L.literacy ?? b.bildung, 1), bar: num(L.literacy ?? b.bildung) ? (L.literacy ?? b.bildung) / 100 : null },
            { l: "mit Anstellung", v: pct(L.employment, 0), bar: L.employment,
              title: "Anteil der Bevölkerung mit Anstellung in Gebäuden oder Rohstoff-Förderung (Spielwert employment_percentage = 1 − „ohne Anstellung“ ÷ Bevölkerung laut Spielstand). Bauern zählen im Spielstand als ohne Anstellung." }],
    warn: [b.ueberbevoelkert && "überbevölkert",
           minus.length && `${minus.length} Gebäude mit Verlust`,
           num(L.food_prod) && num(L.food_cons) && L.food_prod + L.food_cons < 0 && `Nahrung vor Ort: Produktion ${fmt(L.food_prod, 1)} < Verbrauch ${fmt(-L.food_cons, 1)}`,
           ...krank.map(([k, v]) => `Krankheit ${esc(de(k).replace(/^Krankheit: /, ""))} ${pct(v, 0)}`),
           lw.IsOccupied === 1 && "besetzt", lw.HasSiege === 1 && "wird belagert"],
  });
  const lazyBody = () => {
    const ST = { nobles_estate: "Adel", clergy_estate: "Klerus", burghers_estate: "Bürger", peasants_estate: "Gemeine", crown_estate: "Krone" };
    const steuerSt = Object.entries(o.steuer_staende || {}).map(([k, v]) => ({ label: ST[k] || k, value: v, color: ESTATE_COLOR[k] || "--c8" }));
    const POPC = { peasants: "--c3", laborers: "--c1", burghers: "--c4", clergy: "--c6", soldiers: "--c5", nobles: "--c2", slaves: "--c8", tribesmen: "--c7" };
    const pn = d.pop_namen || {};
    const typKey = Object.fromEntries(Object.entries(pn).map(([k, v]) => [v, k]));
    // laufende Methode je Gebäude (Spielstand gebaeude_pm) mit Eingängen → Ausgabe aus den Spieldateien; Bauprojekte des Ortes
    const PMA = P.A.gebaeude_pm || {}, GB = P.W.gebaeude || {}, pmn = (P.W.namen || {}).pms || {}, bn = (P.W.namen || {}).gebaeude || {};
    const pmText = (typ, n) => { const pm = (GB[typ]?.pms || []).find(p => p.name === n);
      return `<div>${esc(pmn[n] || n)}${pm ? `<div class="hint">${Object.entries(pm.inputs || {}).map(([k, v]) => `${fmt(v, 2)} ${esc(gn[k] || k)}`).join(" + ") || "–"} → ${pm.produced ? `${fmt(pm.output, 2)} ${esc(gn[pm.produced] || pm.produced)}` : "–"}</div>` : ""}</div>`; };
    const bauHier = (P.A.bau || []).filter(x => x.ort_id === o.id);
    const cards = [
      `<div class="card"><h3>Lage</h3>${kv([["Region › Gebiet › Provinz", esc([w.region_name, w.gebiet_name, w.provinz_name].filter(Boolean).join(" › "))],
        ["Klima · Gelände · Bewuchs", esc([w.climate_name, w.topography_name, w.vegetation_name].filter(Boolean).join(" · "))],
        ["Naturhafen", fmt(w.natural_harbor_suitability, 2)], ["Kultur / Religion", esc([w.culture_name, w.religion_name].filter(Boolean).join(" / "))],
        ["Markt", esc((P.A.markt_namen || {})[o.markt] || o.markt)], ["Integration", fmt(L.integration, 1)],
        ["Garnison", fmt(L.garrison, 2)], ["Kulturelle / religiöse Einheit", `${pct(L.cultural_unity, 0)} / ${pct(L.religious_unity, 0)}`]])}</div>`,
      `<div class="card"><h3>Steuergrundlage je Stand</h3>${steuerSt.length ? pieChart(steuerSt, { size: 120, fmtV: v => pct(v, 0) }) : "–"}</div>`,
      `<div class="card"><h3>Bevölkerung – ${fmt(pop, 2)} Tsd.${cap ? ` von ${fmt(cap, 1)}` : ""}</h3>
        ${o.pops?.length ? pieChart(o.pops.map(p => ({ label: p.typ, value: p.groesse, color: POPC[typKey[p.typ]] || "--c8" })), { size: 120 }) : ""}
        ${table([{ t: "Typ", l: true, f: p => esc(p.typ) }, { t: "Größe", f: p => fmt(p.groesse, 2) }, { t: "Zufr.", f: p => pct(p.zufr) },
                 { t: "Bildung", f: p => fmt(p.bildung, 0) }], o.pops || [], { scroll: false })}
        ${kv([["Veränderung letzter Monat", sgn(ch, 3)], ["Beschäftigung", pct(L.employment, 0)], ["Wanderung", fmt(L.migration, 3)],
              ["Bildung Ø", fmt(L.literacy, 1)],
              ...Object.entries(b.ursachen || {}).filter(([, v]) => v).map(([k, v]) => [(d.bev?.ursachen_namen || {})[k] || k, sgn(v, 3)])])}</div>`,
      `<div class="card"><h3>Produktion und Nahrung</h3>${kv([["Rohstoff", esc(gn[o.rohstoff] || o.rohstoff || "–")],
        ["Ausstoß", fmt(L.rgo_output, 2)], ["Stufe / Arbeiter", `${fmt(L.rgo_level, 0)} / ${fmt(L.rgo_workers, 1)} von ${fmt(L.max_rgo_workers, 1)}`],
        ["Nahrung Produktion", fmt(L.food_prod, 1)], ["Nahrung Verbrauch", fmt(L.food_cons, 1)],
        ["Gebäudestufen / Gebäude", `${fmt(L.building_levels, 0)} / ${fmt(L.buildings, 0)}`]])}</div>`,
      // Gebäude wie in der Produktionskachel (29.09.): laufende Methode (Spielstand), möglicher Gewinn, Status; Bauprojekte des Ortes
      `<div class="card" style="grid-column: 1 / -1"><h3>Gebäude – ${(o.gebaeude || []).length}</h3>${table([{ t: "Gebäude", l: true, f: g => esc(g.name) },
        { t: "Stufe", f: g => fmt(g.stufe, 0) }, { t: "Gewinn", f: g => fmt(g.gewinn, 2), cls: g => posneg(g.gewinn) },
        ...(P.useLiveGeb ? [{ t: "möglich", f: g => fmt(g.moeglich, 2), cls: g => posneg(g.moeglich) }] : []),
        { t: "Beschäftigt", f: g => g.besch != null ? `${fmt(g.besch, 2)} / ${fmt(g.plaetze, 2)}` : "–" },
        { t: "Laufende Methode", l: true, f: g => (PMA[g.id]?.pms || []).map(n => pmText(g.typ, n)).join("") || "–" },
        { t: "Hinweis", l: true, f: g => { const st = PMA[g.id]?.status; return st ? esc(STATUS_GEB[st] || st) : ""; } }],
        (o.gebaeude || []).slice().sort((a, b) => (b.gewinn ?? 0) - (a.gewinn ?? 0)), { scroll: false })}
        ${bauHier.length ? `<div class="sect">Im Bau – ${bauHier.length}</div>${table([
          { t: "Gebäude", l: true, f: x => esc(bn[x.typ] || x.name || x.typ || x.bedarf) }, { t: "Stufe jetzt", f: x => x.stufe != null ? fmt(x.stufe, 0) : "Neubau" },
          { t: "Fortschritt", f: x => num(x.fortschritt) && x.gesamt ? pct(x.fortschritt / x.gesamt, 0) : "nicht begonnen" },
          { t: "fehlende Güter", l: true, f: x => Object.entries(x.fehlt || {}).map(([k, v]) => `${esc(gn[k] || k)} ${fmt(v, 2)}`).join(", ") || "–" }], bauHier, { scroll: false })}` : ""}</div>`,
    ];
    const shown = ORT_TEXTE.filter(([f]) => T[f]).map(([f, t]) => `<div class="card"><h3>${esc(t)}</h3>${breakdown(T[f])}</div>`);
    const alle = lazy(`ort:${o.id}:alle`, `Alle Live-Daten des Ortes <span class="hint">${Object.keys(lw).length} Werte · ${Object.values(lm).filter(v => v).length} Modifikatoren · ${Object.keys(T).length} Texte · Mod ${esc(d.alles?.datum?.ort || "")}</span>`,
      () => `<div class="grid2"><div class="card"><h3>Werte</h3>${valueList(lw)}</div>
        <div class="card"><h3>Modifikatoren ≠ 0</h3>${valueList(lm, { M, nonzero: true })}</div>
        <div class="card"><h3>Aufschlüsselungen (${Object.keys(T).length})</h3>${Object.entries(T).map(([f, x]) =>
          lazy(`ort:${o.id}:t:${f}`, `${esc(tl(f))} <span class="code">${esc(f)}</span>`, () => breakdown(x))).join("")}</div></div>`);
    // Aufschlüsselungen ohne eigene Überschrift unter der Übersicht (Nutzerwunsch 29.09., alle Kacheln)
    return sect("Übersicht", `<div class="grid2">${cards.join("")}</div>${shown.length ? `<div class="grid2">${shown.join("")}</div>` : ""}`)
      + sect("Alle Live-Daten", alle);
  };
  return { head, lazy: lazyBody };
}
