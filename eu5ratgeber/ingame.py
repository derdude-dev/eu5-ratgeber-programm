"""Seitenleiste im Spiel (Mod 0.26; Nutzerwunsch 02.11.: „das datenfenster als eigenen menüpunkt im spiel … ohne Browser“).

Ein zehnter Reiter „Ratgeber“ in der Symbolleiste unter dem Landesnamen öffnet eine Seitenleiste im Stil des Spiels
(tools/mod_ingame.py). Ihre Texte stehen in einer Übersetzungsdatei des Mods, die der Ratgeber hier schreibt (LIVE_DATEI) – für
alle Schwerpunkte zugleich, damit die Auswahl im Spiel sofort umschaltet (Nutzer 02.11.: „die auswahl sollte ohne ratgeber
rechnung erfolgen“). Die Oberfläche setzt den Schlüssel aus dem gewählten Schwerpunkt zusammen
(Localize(Concatenate('RG_RATGEBER_S1_', GetVariableSystem.Get('rg_fokus')))); die Schlüssel ohne Schwerpunkt („…_S1_“) tragen
den ersten Schwerpunkt, falls noch nichts gewählt ist. Das Spiel lädt die Datei nicht von selbst neu (Test 0.26: -filewatcher
überwacht nur gfx/skins); der Reiter und „Aktualisieren“ rufen dafür „switchlanguage l_german“ auf.

Nach Test 0.26.1 (Nutzer: „der text ist auf jeden fall zu viel“): eine Karte = Symbol, eine Zeile, Kostenmarke; Begründung und
Einzelheiten im Tooltip. Reiter Übersicht (Kennzahlen, „Jetzt tun“, Warnungen, Gründung), Strategie (Schritte und Tabelle
jetzt → Vorschlag), Empfehlungen.

Mod 0.27 (03.11., Nutzer: „kannst du das design anpassen ans spiel … was ist mit den restlichen kacheln aus dem ratgeber?“): 18
Kacheln der Seite mit Kopfwerten, Warnungen und Einzelheiten (eu5ratgeber/ingame_kacheln.py), Hauptreiter Ratgeber, Wirtschaft,
Staat, Außen & Militär. Das Symbol einer Karte ist jetzt nur der Bereichsschlüssel (z. B. „government“) – die Oberfläche wählt
damit Symbol und Farbe (Test 0.26.2: texture aus Localize zeigte nichts). Zuordnung Bereich -> Banner/Farbe/Symbol: BEREICHE.

Mod 0.28 (03.11., Nutzer: „kannst du diese [symbole] benutzen in allen fenstern“ – „bitte die kacheln nicht transparent“ – „sind
links und öffnen der entsprechenden fenster möglich?“ – „ja, so bauen“):
- Text-Symbole: loc() setzt die Platzhalter aus ingame_kacheln (FARBE -> „#“, SYM_A name SYM_E -> „@name!“) am Ende um; welche
  eigenen Symbole erlaubt sind, sagt der installierte Mod (ingame_symbole.namen).
- Links je Karte (Schritte, Empfehlungen, Warnungen, Gründung) und Tabellenzeile: Schlüssel …L (Typ), …Z (Ziel), …O (Ort beim
  Baumodus) – nur öffnen, nie ausführen; der Tooltip nennt den Klick.
- Warnungen der Prüfung Spiel/Mod (pruef, z. B. Spiel-Update – bisher nur im Konsolenfenster, das künftig entfällt) zuerst in den
  Warnungen der Übersicht, rot bei „hoch“.
- Hintergrund je Bereich (Karten, Zeilen): BEREICHE, vierter Eintrag bg_card_header_01_<x> (backgrounds.gui)."""
import os
import re
import time
from pathlib import Path

from . import ingame_kacheln, ingame_symbole, ingame_tips as tips, livelog, pfade, sprache, wirtschaftsplan
from .sprache import ue

MOD_DIR = "eu5_ratgeber_daten"


def live_datei(ordner=None):
    """Übersetzungsdatei der Live-Texte; die Sprache des Spiels bestimmt, welche Datei es liest."""
    o = ordner or sprache.ORDNER
    return Path(f"main_menu/localization/{o}/rg_ratgeber_live_l_{o}.yml")


LIVE_DATEI = live_datei()
GUI_DATEI = Path("in_game/gui/rg_ratgeber.gui")       # ab Mod 0.26 – ohne sie schreibt der Ratgeber nichts
SCHRITTE, EMPFEHLUNGEN, ZEILEN, KENNZAHLEN, WARNUNGEN = 5, 8, 12, 3, 3   # Felder in der Oberfläche
JETZT = 3                                             # Schritte auf der Übersicht
PRIO = {"hoch": 0, "mittel": 1, "niedrig": 2}
PRIO_FARBE = {"hoch": f"#R {ue('hoch')}#!", "mittel": f"#Y {ue('mittel')}#!", "niedrig": ue("niedrig")}
# Bereich -> (Banner button_banner_01_anim_<x>.dds, Farbe color_<x>_texture, Symbol tabicons/<x>.dds, Hintergrund der Karten und
# Zeilen) – Banner und Farben wie im Entscheidungsfenster des Spiels (decisions_lateralview.gui: Kategorien country, expansion,
# government, society, economy, other, production), Symbole der Reiter der Symbolleiste, Hintergrund wie die Kategorie-Liste des
# Diplomatiefensters (bg_card_header_01_<x>, backgrounds.gui; Mod 0.28). Die einzige Stelle für Farbe/Banner/Symbol (03.11.)
BEREICHE = {"government": ("government", "color_government_texture", "government", "bg_card_header_01_government"),
            "economy": ("economy", "color_economy_texture", "economy", "bg_card_header_01_economy"),
            "production": ("production", "color_production_texture", "production", "bg_card_header_01_production"),
            "society": ("society", "color_society_texture", "demography", "bg_card_header_01_society"),
            "country": ("country", "color_diplomacy_texture", "diplomacy", "bg_card_header_01_diplomacy"),
            "expansion": ("expansion", "color_geopolitics_texture", "military", "bg_card_header_01_geopolitics"),
            "other": ("other", "color_advances_texture", "advances", "bg_card_header_01_advances")}
# Bereich der Schritte, Empfehlungen und Warnungen -> Bereichsschlüssel (Auftrag 03.11.: Regierung -> government, Wirtschaft/
# Finanzen/Handel -> economy, Produktion/Bau -> production, Stände/Gesellschaft/Bevölkerung/Kultur/Religion/Krankheiten -> society,
# Diplomatie/Bündnis/Nachbarn -> country, Militär/Krieg/Gründung -> expansion, Forschung -> other)
SYMBOL = {"kabinett": "government", "minister": "government", "politlinie": "government", "reform": "government",
          "privileg": "society", "forschung": "other", "bau": "production", "buendnis": "country", "rivale": "country",
          "Krankheiten": "society", "Stände": "society", "Bevölkerung": "society", "Gesellschaft": "society", "Regierung": "government",
          "Wirtschaft": "economy", "Produktion": "production", "Finanzen": "economy", "Handel": "economy", "Forschung": "other",
          "Militär": "expansion", "Krieg": "expansion", "Diplomatie": "country", "Nachbarn": "country", "Gründung": "expansion",
          "Kultur": "society", "Religion": "society"}
BEREICH = {"kabinett": "Kabinett", "forschung": "Forschung", "politlinie": "Politlinie", "privileg": "Privileg", "bau": "Bau",
           "buendnis": "Bündnis", "reform": "Reform", "rivale": "Rivale", "minister": "Minister"}
FOKUSSE = list(wirtschaftsplan.FOKUS)
# Karte: Zeile, Kostenmarke, Tooltip, Bereich (Symbol); ab 0.28 Link: Typ, Ziel, Ort (Baumodus)
TEILE = ("", "K", "T", "I", "L", "Z", "O")
# Bereich eines ersten Schritts -> Seitenleiste des Spiels (Bau, Bündnis und Rivale haben eigene Ziele)
SCHRITT_ANSICHT = {"kabinett": "government", "minister": "government", "politlinie": "laws", "privileg": "government",
                   "reform": "government_reforms", "forschung": "advances"}


def symbol(bereich):
    """Bereichsschlüssel (BEREICHE) – die Oberfläche zeigt damit Symbol und Farbe (EqualTo_string)."""
    return SYMBOL.get(bereich, "other")


def schluessel_fokus(fk):
    """Schlüssel je Schwerpunkt (fk = "" für „noch nichts gewählt“): Karten der Schritte (S) und Empfehlungen (E) je mit Teilen,
    Tabellenzeilen (T: A Bereich, B jetzt, C Vorschlag, T Tooltip), Hinweise, Kacheln des Hauptreiters Ratgeber (Mod 0.27).
    „Abweichungen“ steht seit 0.27 im Kopf der Kachel Startstrategie (vorher Hinweis ABW)."""
    out = [f"RG_RATGEBER_{f}{i}{t}_{fk}" for f, n in (("S", SCHRITTE), ("E", EMPFEHLUNGEN)) for i in range(1, n + 1) for t in TEILE]
    out += [f"RG_RATGEBER_T{i}{t}_{fk}" for i in range(1, ZEILEN + 1) for t in "ABCTLZ"]
    out += [f"RG_RATGEBER_{h}_{fk}" for h in ("LEER", "MEHR")]
    return out + [k for kid in ingame_kacheln.JE_FOKUS for k in ingame_kacheln.schluessel(kid, fk)]


def schluessel_allgemein():
    """Schlüssel ohne Schwerpunkt: Kennzahlen (L Bezeichnung, W Wert, T Tooltip), Warnungen (Karten), Gründung, Stand."""
    return ([f"RG_RATGEBER_KZ{i}{t}" for i in range(1, KENNZAHLEN + 1) for t in "LWT"]
            + [f"RG_RATGEBER_W{i}{t}" for i in range(1, WARNUNGEN + 1) for t in TEILE]
            + [f"RG_RATGEBER_GR{t}" for t in TEILE] + ["RG_RATGEBER_STAND"]
            + [k for kid in ingame_kacheln.FEST for k in ingame_kacheln.schluessel(kid)])


def alle_schluessel():
    return [k for fk in FOKUSSE + [""] for k in schluessel_fokus(fk)] + schluessel_allgemein()


def leer():
    """Alle Schlüssel mit Platzhaltern – bis zur ersten Rechnung des Ratgebers (Mod-Bau)."""
    t = {k: "" for k in alle_schluessel()}
    for fk in FOKUSSE + [""]:
        # seit 03.11. startet der Wächter den Ratgeber mit dem Spiel (tools/waechter.py); die .bat nur noch von Hand
        t[f"RG_RATGEBER_LEER_{fk}"] = ("Noch keine Daten. Das Programm EU5 Ratgeber muss laufen und braucht einen Spielstand "
                                       "(Startoption -force_text_save). Danach „Aktualisieren“.")
    t["RG_RATGEBER_STAND"] = "EU5 Ratgeber – Daten-Mod"
    return t


def mod_ordner():
    """Ordner des Daten-Mods: lokal oder aus dem Workshop (pfade.mod_ordner)."""
    return Path(pfade.mod_ordner())


def loc(s):
    """Text für einen Wert der Übersetzungsdatei: nichts, was das Spiel deutet ([ ] Datenfunktion, $ Variable, # Format, @ Symbol,
    " Ende des Werts), Zeilenumbruch als \\n. Danach die Platzhalter der Kacheln: FARBE -> „#“ (Farbcode), SYM_A name SYM_E ->
    „@name!“ (Text-Symbol, Mod 0.28); ein halber Platzhalter (gekürzt) fällt weg."""
    s = str(s if s is not None else "")
    for a, b in (("\\", "/"), ('"', "“"), ("[", "("), ("]", ")"), ("$", "S"), ("#", ue("Nr.")), ("@", "(at)"), ("\r", "")):
        s = s.replace(a, b)
    ik = ingame_kacheln
    s = re.sub(ik.SYM_A + r"(\w+)" + ik.SYM_E, r"@\1!", s).replace(ik.SYM_A, "").replace(ik.SYM_E, "")
    s = re.sub(ik.ORT_A + r"(\w+)" + ik.ORT_E, r"[GetLocationByKey('\1').GetName]", s)        # Textlink eines Orts (nur fester Schlüssel)
    return s.replace(ik.FARBE, "#").replace("\n", "\\n")


def _de(v, d=1):
    s = sprache.ziffern(f"{v:,.{d}f}")
    return s.rstrip("0").rstrip(sprache.KOMMA) if sprache.KOMMA in s else s


def _setze(t, prefix, fk, zeile, marke, tooltip, bereich, link=None):
    """Karte <prefix> (z. B. „S1“) für Schwerpunkt fk: Zeile, Kostenmarke, Tooltip (Rohtext aus ingame_tips), Symbol; Link (Mod 0.28: Typ,
    Ziel, Ort – ingame_kacheln.ansicht/ort_link/bau_link/land_link), der Tooltip nennt dann den Klick."""
    link = link if zeile else None
    t[f"RG_RATGEBER_{prefix}_{fk}"] = zeile
    t[f"RG_RATGEBER_{prefix}K_{fk}"] = marke
    t[f"RG_RATGEBER_{prefix}T_{fk}"] = loc(tips.mit_klick(tooltip, link and link["text"]))
    t[f"RG_RATGEBER_{prefix}I_{fk}"] = symbol(bereich) if zeile else ""
    for s, f in (("L", "typ"), ("Z", "z"), ("O", "o")):
        t[f"RG_RATGEBER_{prefix}{s}_{fk}"] = loc(link[f]) if link else ""


def _ortkeys(d):
    """Name -> Spielschlüssel der eigenen Orte (nur eindeutige Namen) – für Links."""
    orte = [o for o in (d.get("aktuell") or {}).get("orte") or [] if o.get("key")]
    namen = [o.get("name") for o in orte]
    return {o.get("name"): o["key"] for o in orte if namen.count(o.get("name")) == 1}


def _schritt_link(e, fk, S, d):
    """Link eines ersten Schritts: Seitenleiste je Bereich; Bau -> Baumodus und Karte (erster Schritt des Bauplans = Quelle des
    Schritts, startstrategie.py), Bündnis/Rivale -> Diplomatie mit dem Land."""
    b, ik = e.get("bereich"), ingame_kacheln
    if b in SCHRITT_ANSICHT:
        return ik.ansicht(SCHRITT_ANSICHT[b])
    D = S.get("diplomatie") or {}
    if b == "bau":
        plan = (((d.get("wirtschaftsplan") or {}).get("fokusse") or {}).get(fk or FOKUSSE[0]) or {}).get("plan") or []
        p = plan[0] if plan and str(plan[0].get("was") or "") in str(e.get("text") or "") else {}
        geb, ok = p.get("gebaeude"), _ortkeys(d).get(p.get("ort"))
        gn = ((d.get("wissen") or {}).get("namen") or {}).get("gebaeude") or {}
        return ((ik.bau_link(geb, gn.get(geb), ok, p.get("ort")) if geb in gn else None) or ik.ort_link(ok, p.get("ort"))
                or ik.ansicht("production"))
    if b == "buendnis":
        bv = D.get("buendnis_vorschlag") or {}
        return ik.land_link(bv.get("tag"), bv.get("name"))
    if b == "rivale":
        rk = (D.get("rivalen_kandidaten") or [{}])[0] or {}
        return ik.land_link(rk.get("tag"), rk.get("name"))
    return None


def _marke(kosten, sparen):
    """Kurze Kostenmarke aus dem Kostentext der ersten Schritte („20 Politischer Einfluss – danach 80 übrig“ -> „20 Einfluss“)."""
    if not kosten:
        return ""
    m = loc(kosten.split(" – ")[0].split(";")[0].replace("Politischer Einfluss", "Einfluss"))
    return f"#R {m}#!" if sparen else m


def _schritte(t, fk, S, F, d=None):
    xs = (F.get("erste_schritte") or [])[:SCHRITTE]
    for i in range(1, SCHRITTE + 1):
        e = xs[i - 1] if i <= len(xs) else None
        if not e:
            _setze(t, f"S{i}", fk, "", "", "", "")
            continue
        b = BEREICH.get(e.get("bereich"), e.get("bereich"))
        link = _schritt_link(e, fk, S, d or {})
        sy = ingame_kacheln.geb_sym(link["z"]) if link and link["typ"] == "bau" else ""
        _setze(t, f"S{i}", fk, f"#bold {loc(b)}:#! {loc(sy + str(e.get('text') or ''))}", _marke(e.get("kosten"), e.get("sparen")),
               tips.schritt(f"{b}: {e.get('text')}", e.get("warum"), e.get("kosten")), e.get("bereich"), link)
    t[f"RG_RATGEBER_LEER_{fk}"] = (f"Startstrategie: {loc(S['fehler'])}" if S.get("fehler") else
                                   "" if xs else "Nichts zu ändern – alle Einstellungen passen zum Schwerpunkt.")


def _empfehlung_texte(r, fk=None):
    """(Zeile, Marke, Tooltip als Rohtext) einer Empfehlung: Titel, Priorität, Handlung, Gründe, Wirkung; mit fk der Grund, warum sie zu
    diesem Schwerpunkt passt (empfehlungen.py fokus_wert)."""
    gruende = r.get("gruende") if isinstance(r.get("gruende"), list) else []
    wirkung = (r.get("wirkung") or {}).get("text") if isinstance(r.get("wirkung"), dict) else None
    # Symbol aus der Kennung (geb:/stand:/krank:, Mod 0.28)
    return (loc(ingame_kacheln.empf_sym(r) + str(r.get("titel") or "")), PRIO_FARBE.get(r.get("prio"), loc(r.get("prio") or "")),
            tips.empfehlung(r.get("titel"), r.get("handlung"), gruende, wirkung, ((r.get("fokus_wert") or {}).get(fk) or (0, ""))[1]))


def _empfehlungen(t, fk, d):
    E = sorted((r for r in d.get("empfehlungen") or [] if not r.get("fokus") or r.get("fokus") == fk),
               key=lambda r: ((r.get("rang") or {}).get(fk, 999), PRIO.get(r.get("prio"), 3)))    # rang: empfehlungen.reihe
    for i in range(1, EMPFEHLUNGEN + 1):
        r = E[i - 1] if i <= len(E) else None
        if not r:
            _setze(t, f"E{i}", fk, "", "", "", "")
            continue
        z, m, tip = _empfehlung_texte(r, fk)
        _setze(t, f"E{i}", fk, z, m, tip, r.get("bereich"), ingame_kacheln.empf_link(r))
    t[f"RG_RATGEBER_MEHR_{fk}"] = (f"… {len(E) - EMPFEHLUNGEN} weitere auf der Seite des Ratgebers" if len(E) > EMPFEHLUNGEN
                                   else "" if E else "Keine Empfehlungen für diesen Schwerpunkt.")


def _tabelle(S, F):
    """Zeilen „Bereich | jetzt | Vorschlag | Tooltip“ der Startstrategie: Kabinettsplätze, abweichende Politlinien, Privilegien,
    Reform, Rivale, Bündnis."""
    K = (S.get("kabinett") or {}).get("aktionen") or {}
    G = S.get("gesetze") or {}
    PK = (S.get("privilegien") or {}).get("katalog") or {}
    ST = {s["stand"]: s for s in (S.get("privilegien") or {}).get("staende") or []}
    RK = (S.get("reformen") or {}).get("katalog") or {}
    D = S.get("diplomatie") or {}
    ik = ingame_kacheln                      # Symbole und Links (Mod 0.28)
    z = []
    for s in F.get("kabinett") or []:
        j = s.get("jetzt") or {}
        jetzt = ik.kab_sym(j.get("aktion")) + (j.get("aktion_name") or (K.get(j.get("aktion")) or {}).get("n") or "frei")
        vor = ("behalten" if not s.get("abweichung") else
               ik.kab_sym(s.get("vorschlag")) + str((K.get(s.get("vorschlag")) or {}).get("n"))
               if s.get("vorschlag") != j.get("aktion") else "Aktion behalten")
        if s.get("minister"):
            vor = f"{vor}, Minister {s['minister']['name']}"
        z.append((f"Kabinett {s['platz'] + 1 if isinstance(s.get('platz'), int) else 'neu'}", jetzt, vor,
                  "; ".join((s.get("gruende") or [])[:2] + (s.get("warnungen") or [])[:1]) or s.get("grund") or "",
                  ik.ansicht("government")))
    for g in F.get("gesetze") or []:
        if g.get("abweichung"):
            L = G.get(g["gesetz"]) or {}
            pol = L.get("pol") or {}
            z.append((ik.gesetz_sym(g["gesetz"]) + (L.get("n") or g["gesetz"]), (pol.get(g["jetzt"]) or {}).get("n") or g["jetzt"],
                      (pol.get(g["vorschlag"]) or {}).get("n") or g["vorschlag"], "; ".join(g.get("gruende", [])[:2] + g.get("warnungen", [])[:1]),
                      ik.ansicht("laws")))
    for p in F.get("privilegien") or []:
        if p.get("vorschlag"):
            z.append((f"{ik.stand_sym(p['stand'])}Privileg {(ST.get(p['stand']) or {}).get('name') or p['stand']}",
                      f"{len((ST.get(p['stand']) or {}).get('gewaehrt') or [])} gewährt",
                      f"+ {(PK.get(p['vorschlag']) or {}).get('n') or p['vorschlag']}",
                      "; ".join(p.get("gruende", [])[:2] + p.get("warnungen", [])[:1]), ik.ansicht("government")))
    R = F.get("reform") or {}
    if R.get("abweichung"):
        z.append(("Reform", f"{R.get('offen')} Platz frei", (RK.get(R.get("vorschlag")) or {}).get("n") or R.get("vorschlag"),
                  "; ".join(R.get("gruende", [])[:2]), ik.ansicht("government_reforms")))
    rv = D.get("rivale_vorschlag")
    if rv:
        rk = (D.get("rivalen_kandidaten") or [{}])[0] or {}
        z.append(("Rivale", f"{D.get('rivalen_zahl')} von {D.get('rivalen_moeglich')}", rv.get("text"), rv.get("warum") or "",
                  ik.land_link(rk.get("tag"), rk.get("name"))))
    bv = D.get("buendnis_vorschlag")
    if bv:
        z.append(("Bündnis", ", ".join(D.get("verbuendete_namen") or []) or "keins", bv.get("text"), bv.get("warum") or "",
                  ik.land_link(bv.get("tag"))))
    return z[:ZEILEN]


def _kennzahlen(t, d):
    """Startkachel: Gold mit Änderung zum Vormonat (Daten-Mod), schwächster Stand, Forschung je Monat (vorläufig – Nutzer passt an)."""
    lv = d.get("live") or []
    g = lv[-1].get("gold") if lv else None
    gv = lv[-2].get("gold") if len(lv) > 1 else None
    dg = g - gv if isinstance(g, (int, float)) and isinstance(gv, (int, float)) else None
    ST = ((d.get("startstrategie") or {}).get("privilegien") or {}).get("staende") or []
    sw = min((s for s in ST if isinstance(s.get("zufriedenheit"), (int, float))), key=lambda s: s["zufriedenheit"], default=None)
    lf = (d.get("techbaum_vorschlag") or {}).get("laufend") or {}
    kz = [("Gold", "–" if g is None else f"{_de(g, 0)}" + ("" if dg is None else f" ({'#G' if dg >= 0 else '#R'} {'+' if dg >= 0 else ''}{_de(dg, 1)}#!)"),
           "Gold laut Daten-Mod, in Klammern die Änderung zum Vormonat"),
          ("Schwächster Stand", "–" if not sw else f"{'#R' if sw['zufriedenheit'] < 0.5 else '#G'} "
                                                   f"{loc(ingame_kacheln.stand_sym(sw.get('stand')) + str(sw['name']))} {_de(sw['zufriedenheit'] * 100, 0)} %#!",
           "Zufriedenheit des am wenigsten zufriedenen Stands; unter 50 % rot (Kachel Stände)"),
          ("Forschung", "–" if not isinstance(lf.get("je_monat"), (int, float)) else f"{_de(lf['je_monat'], 2)} je Monat",
           f"Laufend: {loc(lf.get('name') or '–')}" + (f", {_de(lf['fortschritt'], 1)} von {_de(lf['kosten'], 2)}"
                                                      if isinstance(lf.get("fortschritt"), (int, float)) and isinstance(lf.get("kosten"), (int, float)) else ""))]
    for i, (l, w, tt) in enumerate(kz, 1):
        t[f"RG_RATGEBER_KZ{i}L"], t[f"RG_RATGEBER_KZ{i}W"], t[f"RG_RATGEBER_KZ{i}T"] = l, w, tt


def _warnungen(t, d, pruef=None):
    """Warnungen der Übersicht: zuerst die der Prüfung Spiel/Mod (pruef = [{stufe, text, tun}], z. B. Spiel-Update; rot bei
    „hoch“ – Mod 0.28, bisher nur im Konsolenfenster), dann die Empfehlungen „hoch“ ohne Schwerpunkt."""
    P = [p for p in pruef or [] if isinstance(p, dict) and p.get("text")]
    W = [("p", p) for p in P] + [("e", r) for r in d.get("empfehlungen") or [] if r.get("prio") == "hoch" and not r.get("fokus")]
    W = W[:WARNUNGEN]
    for i in range(1, WARNUNGEN + 1):
        art, r = W[i - 1] if i <= len(W) else (None, None)
        link = None
        if art == "p":
            hoch = r.get("stufe") == "hoch"
            z = f"#R {loc(r['text'])}#!" if hoch else loc(r["text"])
            m = PRIO_FARBE.get(r.get("stufe"), loc(r.get("stufe") or ""))
            tip = tips.pruefung(r["text"], r.get("tun"))
        elif art == "e":
            z, m, tip = _empfehlung_texte(r)
            link = ingame_kacheln.empf_link(r)
        else:
            z, m, tip = "", "", ""
        t[f"RG_RATGEBER_W{i}"], t[f"RG_RATGEBER_W{i}K"] = z, m
        t[f"RG_RATGEBER_W{i}T"] = loc(tips.mit_klick(tip, link and link["text"]))
        t[f"RG_RATGEBER_W{i}I"] = (symbol(r.get("bereich")) if art == "e" else "other") if r else ""
        for s, f in (("L", "typ"), ("Z", "z"), ("O", "o")):
            t[f"RG_RATGEBER_W{i}{s}"] = loc(link[f]) if link else ""


def _gruendung(t, d):
    g = d.get("gruendung") or {}
    o = next((x for x in g.get("optionen") or [] if x.get("key") == g.get("standard")), None)
    for s in ("L", "Z", "O"):
        t[f"RG_RATGEBER_GR{s}"] = ""
    if not o:
        t["RG_RATGEBER_GR"], t["RG_RATGEBER_GRK"], t["RG_RATGEBER_GRT"], t["RG_RATGEBER_GRI"] = "", "", "", ""
        return
    gb = o.get("gebiet") or {}
    t["RG_RATGEBER_GR"] = (f"#bold Gründung {loc(o.get('name'))}:#! {gb.get('unsere')} von {gb.get('noetig')} Orten"
                           + (f" – {gb.get('fehlt')} fehlen" if gb.get("fehlt") else " – erfüllt"))
    t["RG_RATGEBER_GRK"] = "#G gründbar#!" if o.get("gruendbar") else f"{_de(100 * gb['unsere'] / gb['noetig'], 0)} %" if gb.get("noetig") else ""
    link = ingame_kacheln.ansicht("form_new_country")              # Mod 0.28: Klick öffnet die Ländergründung des Spiels
    t["RG_RATGEBER_GRT"] = loc(tips.mit_klick(tips.mit_titel(f"{o.get('name')} (Grad {o.get('grad') or '–'})", [
        f"Bedingungen: {o.get('bedingungen_erfuellt')} von {o.get('bedingungen_alle')} erfüllt",
        f"Neuer Rang: {o.get('rang_neu_name') or '–'}", "Einzelheiten: Kachel Ländergründung"]), link["text"]))
    t["RG_RATGEBER_GRI"] = symbol("Gründung")
    t["RG_RATGEBER_GRL"], t["RG_RATGEBER_GRZ"] = link["typ"], link["z"]


def texte(d, jetzt=None, pruef=None, symbole=None):
    """{Schlüssel: Text} für alle Schwerpunkte (und „noch nichts gewählt“ = erster Schwerpunkt) aus den Daten der Seite.
    pruef: Warnungen der Prüfung Spiel/Mod ([{stufe, text, tun}], spielversion.pruefen) – zuerst in die Warnungen der Übersicht.
    symbole: eigene Text-Symbole, die benutzt werden dürfen (Vorgabe: die der installierten font_icons.gui des Mods)."""
    ingame_kacheln.symbole_setzen(ingame_symbole.namen(mod_ordner()) if symbole is None else symbole, _spiel_symbole())
    ingame_kacheln.ort_ids_setzen(d)
    S = d.get("startstrategie") or {}
    t = {}
    for fk in FOKUSSE + [""]:
        F = (S.get("fokusse") or {}).get(fk or FOKUSSE[0]) or {}
        _schritte(t, fk, S, F, d)
        if fk:
            _empfehlungen(t, fk, d)
        zeilen = _tabelle(S, F)
        for i in range(1, ZEILEN + 1):
            a, b, c, tt, ln = zeilen[i - 1] if i <= len(zeilen) else ("", "", "", "", None)
            ln = ln if a else None
            t[f"RG_RATGEBER_T{i}A_{fk}"], t[f"RG_RATGEBER_T{i}B_{fk}"] = loc(a), loc(b)
            t[f"RG_RATGEBER_T{i}C_{fk}"] = loc(c)
            t[f"RG_RATGEBER_T{i}T_{fk}"] = loc(tips.mit_klick(tips.zeile(tt), ln and ln["text"]))
            t[f"RG_RATGEBER_T{i}L_{fk}"], t[f"RG_RATGEBER_T{i}Z_{fk}"] = (loc(ln["typ"]), loc(ln["z"])) if ln else ("", "")
    for k in [k for k in t if k.endswith("_" + FOKUSSE[0]) and k.startswith(("RG_RATGEBER_E", "RG_RATGEBER_MEHR"))]:
        t[k[:-len(FOKUSSE[0])]] = t[k]                           # Empfehlungen „nichts gewählt“ = erster Schwerpunkt
    _kennzahlen(t, d)
    _warnungen(t, d, pruef)
    _gruendung(t, d)
    t.update(ingame_kacheln.texte(d, FOKUSSE + [""], loc))     # Kacheln der Seite (Mod 0.27)
    meta = d.get("meta") or {}
    t["RG_RATGEBER_STAND"] = (f"{loc(meta.get('land'))} · Spielstand {loc(meta.get('datum'))}"
                              + (f" · Mod {loc(S.get('mod_datum'))}" if S.get("mod_datum") else " · ohne Daten-Mod")
                              + f" · Ratgeber {time.strftime('%H:%M', jetzt or time.localtime())}")
    return {k: t.get(k, "") for k in alle_schluessel()}


_SPIEL = {}


def _spiel_symbole():
    """Text-Symbole des Spiels (font_icons.gui) – einmal je Lauf gelesen."""
    if "n" not in _SPIEL:
        _SPIEL["n"] = ingame_symbole.spiel_namen()
    return _SPIEL["n"]


def yml(t, ordner=None):
    """Übersetzungsdatei wie die Spieldateien (Kopf l_german:, je Zeile ein Schlüssel mit Text in Anführungszeichen)."""
    return f"l_{ordner or sprache.ORDNER}:\n" + "".join(f' {k}: "{v}"\n' for k, v in t.items())


def schreiben(t, ordner=None):
    """Übersetzungsdatei schreiben – UTF-8 mit BOM wie die Spieldateien, nur wenn der Mod mit Seitenleiste installiert ist und
    sich der Inhalt geändert hat; erst in eine Hilfsdatei, dann umbenennen, damit das Spiel nie eine halbe Datei liest."""
    ordner = Path(ordner) if ordner else mod_ordner()
    if not (ordner / GUI_DATEI).exists():
        return None
    p = ordner / LIVE_DATEI
    neu = yml(t).encode("utf-8-sig")
    try:
        if p.read_bytes() == neu:
            return None
    except OSError:
        pass
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(neu)
    os.replace(tmp, p)
    return p


def daten(db, pid, names, wis, voll):
    """Daten für die Seitenleiste wie die Seite sie bekommt: history.series + /api/alles + /api/bevoelkerung (Nutzer 04.11.: die
    Kacheln Religion, Militär, Diplomatie … blieben sonst dünn). ~1 s zusätzlich je Rechnung."""
    from . import bevoelkerung, history
    d = history.series(db, pid, names, wis, voll=voll)
    if d:
        d["alles"] = history.live_alles(db, (d.get("meta") or {}).get("tag"))
        d["bev"] = bevoelkerung.build(db, pid, names)
    return d


def aktuelle_partie(db):
    """Partie der laufenden Sitzung: das Land der zuletzt gespeicherten Monatszeile des Daten-Mods, davon die Partie mit dem
    neuesten Spielstand (wie history.live_gehoert). Test 0.26: „neuester Spielstand überhaupt“ nahm einen Brandenburg-Stand aus
    einer anderen Sitzung. Ohne Mod-Daten der neueste Spielstand überhaupt."""
    row = db.execute("SELECT tag FROM monatswerte ORDER BY erfasst DESC LIMIT 1").fetchone()
    q = ("SELECT m.partie_id FROM momentaufnahmen m JOIN dateien d ON d.pfad LIKE '%' || m.datei "
         + ("WHERE m.tag=? " if row else "") + "ORDER BY d.mtime DESC LIMIT 1")
    r = db.execute(q, (row[0],) if row else ()).fetchone()
    return r[0] if r else None
