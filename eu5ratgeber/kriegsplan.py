"""Kriegsplan (0.31 Teil 2, Nutzer 08.11.: „konkrete kriegsempfehlungen, wer wann angegriffen werden kann, ob man noch kriegsgründe
erzeugen muss und welche armeestärke man haben sollte“): je Land mit Mod-Werten (Kachel Nachbarn) der Stand auf dem Weg zum Krieg.

Quellen:
- Kachel Nachbarn (nachbarn.build): Beziehungen (kb_ziel = wir haben einen Kriegsgrund), Waffenstillstand jetzt (has_truce_with), im
  Krieg, Bündnisstärken (offensive_/defensive_alliance_strength) mit der Ampel, Militärstärke je Land; ab Mod 0.31 die Kriegsgründe, die
  wir schaffen könnten (can_create_casus_belli_of_type_on, je Nachbar und Rivale).
- Spielstand (snapshot.kriegsgruende, neue Spielstände ab 08.11.): Kriegsgründe mit Art und seit wann, laufendes Schaffen mit
  Fortschritt in Prozent, letzter Krieg je Land mit Datum und Kriegspunkten.
- Spieldateien (Spielwissen): Namen und Kriegsziele der Kriegsgründe (casus_belli), Kosten des Schaffens (diplomatic_costs:
  casus_belli_creation), Dauer des Waffenstillstands (defines NDiplomacy TRUCE_YEARS, SCALED_TRUCE_YEARS).

Regeln des Ratgebers (Zahlen sind Spielwerte):
- Waffenstillstand: Ende = letzter Krieg + TRUCE_YEARS + SCALED_TRUCE_YEARS × Kriegspunkte/100 Jahre. Geprüft 08.11.: Walachei – Sizilien,
  Frieden 1343.2.11 mit 73 Punkten -> 5 + 7,3 = 12,3 Jahre bis Ende Mai 1355; der Daten-Mod meldete den Waffenstillstand bis 1355.5 und ab
  1355.6 nicht mehr. Ob es einen gibt, sagt immer der Daten-Mod; die Rechnung liefert nur das Ende.
- Militärstärke (Spielwert military_strength) = Aufgebote + Heer + größte Mannstärke, alles in Tausend Mann (geprüft 08.11. an 11 von 12
  Ländern auf 0,01 genau). „Es fehlen X Tsd. Mann“ = Ziel 1,5 × ihre − unsere, gegen das Land allein. Mit Verbündeten geschätzt: die
  Bündnisstärken (Spielwerte) rechnen in Landesstärke (country_strength), nicht in Mann – darum je Seite Militärstärke × Bündnis ÷
  Landesstärke (Annahme: die Verbündeten haben dasselbe Verhältnis von Militär zu Landesstärke wie das Land selbst).
- Stufe: „jetzt“ = Kriegsgrund, kein Waffenstillstand, unser Angriffsbündnis mindestens nachbarn.GRUEN : 1 gegen ihr Verteidigungsbündnis;
  „bald“ = Kriegsgrund mit Waffenstillstand oder zu wenig Stärke, oder ein Kriegsgrund wird gerade geschaffen; „schaffen“ = kein
  Kriegsgrund, aber das Spiel erlaubt einen zu schaffen; „unmoeglich“ = nichts davon. Länder, mit denen wir im Krieg oder verbündet im Krieg
  sind, fehlen.
- Reichweite (Test 08.11., Walachei 2,8 Tsd. Mann: Empfehlung „Kriegsgrund gegen Ungarn schaffen“ bei 0,11 : 1 und im Armeebuilder
  „+82.828 Mann“): erreichbar ist ein Land, wenn unser Angriffsbündnis mindestens REICHWEITE : 1 gegen ihr Verteidigungsbündnis steht –
  wer mehr als doppelt so stark ist, lässt sich mit Heer und Bündnissen nicht bald einholen. Unerreichbare Länder bleiben im Plan, aber
  ohne Kriegsempfehlung und nicht als Ziel des Armeebuilders.
"""
from . import nachbarn
from .sprache import ue

STUFEN = ("jetzt", "bald", "schaffen", "unmoeglich")
# Reihenfolge der schaffbaren Kriegsgründe nach ihrem Kriegsziel (Regel des Ratgebers: Gebiet zuerst – dafür führt man Krieg)
ZIEL_RANG = (("conquer", 0), ("take_province", 0), ("take_border", 0), ("take_capital", 1), ("superiority", 2), ("humiliate", 3))
BUENDNIS_FAKTOR = 2.0       # ab so viel Bündnis je eigener Landesstärke: erst isolieren (wie gruendung.BUENDNIS_FAKTOR)
REICHWEITE = 0.5            # Regel des Ratgebers: darunter (Bündnis gegen Bündnis) gilt ein Land als außer Reichweite


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _monat(datum):
    """„1356.12.1“ -> Monate seit Jahr 0 (mit Tagesbruchteil)."""
    try:
        j, m, t = (int(x) for x in str(datum).split(".")[:3])
    except ValueError:
        return None
    return j * 12 + (m - 1) + (t - 1) / 30


def _datum(monate):
    """Monate -> „1357.6“ (Monatsgenauigkeit reicht für eine Schätzung)."""
    m = int(monate)
    return f"{m // 12}.{m % 12 + 1}"


def _define(defines, name, vorgabe):
    v = ((defines or {}).get("NDiplomacy") or {}).get("def", {}).get(name)
    return v if _num(v) else vorgabe


def kb_name(kbw, nm, typ):
    return ((kbw or {}).get(typ) or {}).get("name") or nm(typ)


def _ziel_rang(kbw, typ):
    ziel = str((((kbw or {}).get(typ) or {}).get("def") or {}).get("war_goal_type") or "")
    return next((r for w, r in ZIEL_RANG if w in ziel), 4)


def _verhaeltnis(a, b):
    return a / b if _num(a) and _num(b) and b > 0 else None


def waffenstillstand_ende(letzter, defines):
    """Ende des Waffenstillstands nach dem letzten Krieg (Regel oben) als Monate; ohne Datum None."""
    a = _monat((letzter or {}).get("datum"))
    if a is None:
        return None
    p = abs(letzter.get("kriegspunkte") or 0)
    return a + 12 * (_define(defines, "TRUCE_YEARS", 5) + _define(defines, "SCALED_TRUCE_YEARS", 10) * p / 100)


def build(last, nb, names=None, kbw=None, defines=None, kosten=None):
    """Kriegsplan je Land der Kachel Nachbarn. kbw: Spielwissen casus_belli; defines; kosten: diplomatic_costs."""
    nm = names or (lambda k: k)
    if not nb or nb.get("veraltet"):
        return {"laender": [], "veraltet": (nb or {}).get("veraltet")}
    kg = (last or {}).get("kriegsgruende") if isinstance((last or {}).get("kriegsgruende"), dict) else {}
    jetzt = _monat(nb.get("datum_live") or (last or {}).get("meta", {}).get("datum"))
    stand = _monat((last or {}).get("meta", {}).get("datum"))
    spion = ((kosten or {}).get("casus_belli_creation") or {}).get("def", {}).get("spy_network")
    wir = nb.get("wir") or {}
    out = []
    for r in nb.get("laender") or []:
        bz = r.get("beziehungen") or []
        if "krieg" in bz or "kriegsverbuendet" in bz:
            continue
        b, w, d = r.get("bewertung") or {}, r.get("werte") or {}, r.get("diplomatie") or {}
        kb = [{"typ": x.get("typ"), "name": kb_name(kbw, nm, x.get("typ")), "seit": x.get("seit")}
              for x in kg.get("wir_gegen") or [] if x.get("tag") == r["tag"]]
        if not kb and "kb_ziel" in bz:
            kb = [{"typ": None, "name": None, "seit": None}]          # nur Daten-Mod (kb_ziel): Art erst im nächsten Spielstand
        sch = next((x for x in kg.get("schaffen") or [] if x.get("tag") == r["tag"]), None)
        if sch:
            p, seit = sch.get("fortschritt"), _monat(sch.get("seit"))
            fertig = None
            if _num(p) and 0 < p < 100 and seit is not None and stand is not None and stand > seit:
                fertig = _datum(stand + (100 - p) / (p / (stand - seit)))
            sch = {"typ": sch.get("typ"), "name": kb_name(kbw, nm, sch.get("typ")), "fortschritt": p, "seit": sch.get("seit"),
                   "fertig": fertig}
        schaffbar = [{"typ": t, "name": kb_name(kbw, nm, t)} for t in sorted(r.get("kb_schaffbar") or [], key=lambda t: (_ziel_rang(kbw, t), t))]
        lk = (kg.get("letzter_krieg") or {}).get(r["tag"])
        ws = None
        if d.get("truce") == 1:
            ende = waffenstillstand_ende(lk, defines)
            ws = {"bis": _datum(ende) if ende is not None and (jetzt is None or ende > jetzt) else None,
                  "frieden": (lk or {}).get("datum"), "kriegspunkte": (lk or {}).get("kriegspunkte")}
        verh = b.get("verhaeltnis")
        ok = b.get("unendlich") or (_num(verh) and verh >= nachbarn.GRUEN)
        wm, sm = wir.get("military_strength"), w.get("military_strength")
        fw = _verhaeltnis(wir.get("offensive_alliance_strength"), wir.get("country_strength"))
        fs = _verhaeltnis(w.get("defensive_alliance_strength"), w.get("country_strength"))
        staerke = {"wir": wm, "sie": sm, "ziel": nachbarn.GRUEN,
                   "fehlt": max(0.0, nachbarn.GRUEN * sm - wm) if _num(wm) and _num(sm) else None,
                   "fehlt_buendnis": max(0.0, nachbarn.GRUEN * sm * fs - wm * fw) if _num(wm) and _num(sm) and fw and fs else None,
                   "buendnis": verh, "unendlich": bool(b.get("unendlich")),
                   "buendnis_faktor": (w["defensive_alliance_strength"] / w["country_strength"])
                   if _num(w.get("defensive_alliance_strength")) and _num(w.get("country_strength")) and w["country_strength"] > 0 else None}
        if kb:
            stufe = "jetzt" if ok and not ws else "bald"
        elif sch:
            stufe = "bald"
        elif schaffbar:
            stufe = "schaffen"
        else:
            stufe = "unmoeglich"
        out.append({"tag": r["tag"], "name": r.get("name") or nm(r["tag"]), "stufe": stufe, "kb": kb, "schaffen": sch,
                    "schaffbar": schaffbar, "waffenstillstand": ws, "staerke": staerke, "im_krieg": d.get("at_war") == 1,
                    "nachbar": "nachbar" in bz, "rivale": "rivale" in bz, "ohne_kb": d.get("ohne_kb"), "ampel": b.get("stufe"),
                    # ohne Verhältnis (Mod-Werte fehlen) bleibt das Land erreichbar – die Ampel sagt dann ohnehin nichts
                    "erreichbar": bool(b.get("unendlich")) or not _num(verh) or verh >= REICHWEITE})
    out.sort(key=lambda x: (STUFEN.index(x["stufe"]), not x["nachbar"],
                            -(1e9 if x["staerke"]["unendlich"] else x["staerke"]["buendnis"] or 0), x["name"]))
    return {"laender": out, "datum": nb.get("datum_live"), "spionagenetz": spion if _num(spion) else None,
            "spielstand_kb": bool(kg), "waffenstillstand_jahre": [_define(defines, "TRUCE_YEARS", 5), _define(defines, "SCALED_TRUCE_YEARS", 10)]}
