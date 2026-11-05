"use strict";
// Eigene Ansichten neben dem Ratgeber (Nutzerwunsch 30.10.): Mechaniken (#wiki, wiki.js) und Fortschritte (#techbaum, techbaum.js).
// Umschalter in der Kopfzeile; Adresse über location.hash: #<ansicht> oder #<ansicht>/<schlüssel>, dazu die Pfade /wiki und
// /techbaum (der Server liefert dort index.html, hier wird daraus #wiki bzw. #techbaum). Die Zurück-Taste des Browsers
// funktioniert, weil jeder Wechsel ein Hash-Wechsel ist. Andere Sprungmarken (#ort_…, Kacheln) bleiben beim Ratgeber.
// Eine Ansicht trägt sich mit ansicht(id, titel, zeige) ein. zeige(rest, el) läuft bei jedem Hash-Wechsel auf diese Ansicht
// (rest = Teil nach dem ersten „/“, sonst ""); sie baut ihren Bereich el (<main id="ansicht_<id>">) beim ersten Mal und danach
// nur noch die Teile, die sich ändern. render() (app.js) fasst diese Bereiche nicht an – Suche und Auswahl bleiben stehen.
const ANSICHTEN = {};

function ansicht(id, titel, zeige) {
  const el = document.createElement("main");
  el.id = "ansicht_" + id;
  el.className = "ansicht";
  el.style.display = "none";
  $("#browser").after(el);
  const a = document.createElement("a");
  a.href = "#" + id;
  a.textContent = titel;
  a.dataset.ansicht = id;
  $("#ansichten").append(a);
  ANSICHTEN[id] = { titel, zeige, el };
  zeigeAnsicht();
}

function aktuelleAnsicht() {
  const [id, ...rest] = decodeURIComponent(location.hash.slice(1)).split("/");
  return ANSICHTEN[id] ? { id, rest: rest.join("/") } : null;
}

function zeigeAnsicht() {
  const a = aktuelleAnsicht();
  for (const [id, v] of Object.entries(ANSICHTEN)) v.el.style.display = a?.id === id ? "" : "none";
  for (const s of ["#main", "#toc", "#browser"]) $(s).style.display = a ? "none" : "";
  document.body.classList.toggle("in_ansicht", !!a);
  document.querySelectorAll("#ansichten a").forEach(x => x.classList.toggle("on", (x.dataset.ansicht || "") === (a?.id || "")));
  if (a) {
    document.title = `${ANSICHTEN[a.id].titel} – EU5 Ratgeber`;
    ANSICHTEN[a.id].zeige(a.rest, ANSICHTEN[a.id].el);
  } else {
    document.title = "EU5 Ratgeber";
    // load() glich die Kacheln alle 60 s auch bei verstecktem #main an – alle Höhen 0 (Prüfer 30.10.): beim Zurückkommen neu
    if (typeof equalizeTiles === "function") equalizeTiles();
  }
}

// Pfad /wiki bzw. /techbaum -> Hash (Seite bleibt dieselbe, Adresse wird /#wiki)
if (location.pathname.length > 1 && !location.hash) history.replaceState(null, "", "/#" + location.pathname.slice(1));
addEventListener("hashchange", zeigeAnsicht);
