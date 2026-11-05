"""Tooltips der Seitenleiste im Spiel – ein Aufbau für alle (Nutzer 04.11.: „der tooltip text ist meist sehr unübersichtlich und
schlecht zu lesen bei vielen zeilen“).

Titel (#T wie ALERT_AT_WAR_WITH), Abschnitte „Was tun“, „Warum“, „Wirkung“ (Bezeichnung #Y), Listen mit hängendem Einzug
(#indent_newline wie MAPMODE_DISEASE_LOCATION_TT_LINE), Klick-Hinweis abgesetzt als Nebentext (#L). Fließtext wird an Sätzen und Semikolons
in Zeilen geteilt; Quellenangaben („(Spielstand)“, „(Daten-Mod)“ …) und Hinweise nur für die Seite entfallen hier – auf der Seite im
Browser stehen sie weiter. Die Breite bleibt die des Spiels (420 px, rund 60 Zeichen).

Alle Funktionen liefern Rohtext mit dem Platzhalter FARBE statt „#“; der Aufrufer schickt das Ergebnis einmal durch ingame.loc().
"""
import re

from . import sprache
from .sprache import ue

FARBE = "\x01"              # Platzhalter für „#“ der Farbcodes (#G … #!): übersteht ingame.loc, wird danach zu „#“

ZEICHEN = 58                # Zeichen je Zeile im Tooltip (420 px, Schrift des Spiels) – nur für die Schätzung der Zeilenzahl
WARUM_ZEILEN = 14           # geschätzte Zeilen für „Warum“; was nicht passt, nennt ein Hinweis auf die Seite im Browser
TITEL_MAX = 120             # längere Titel: Kopf als Titel, die Aufzählung dahinter als Liste
EINZUG = (3, 7)             # #indent_newline je Listenebene

AUF, ZU, ANFUEHRUNG = ("([„", ")]“", "„") if sprache.DEUTSCH else ("([“", ")]”", "“")
ABKUERZUNG = re.compile(r"(?:\b(?:Nr|Min|max|ca|bzw|vgl|inkl|ggf|usw|etc)|\bz\. ?B|\bd\. ?h|\bu\. ?a)$" if sprache.DEUTSCH
                        else r"(?:\b(?:No|Min|max|approx|vs|etc)|\be\.g|\bi\.e)$")
ETIKETTEN = ("Was tun", "Warum", "Wirkung", "Kosten", "Voraussetzung", "Bedingungen", "Neuer Rang", "Einzelheiten", "Weitere Werte")
ETIKETT = re.compile("^(" + "|".join(re.escape(ue(x)) for x in ETIKETTEN) + r"):(?: |$)")
# Quellen und Seiten-Hinweise: im Spiel ohne Nutzen, in fast jedem Satz (Spielstand: 12× in einem Tooltip)
# Die Wörter kommen aus dem Katalog: dieselben Muster greifen die englischen Texte
_SPIELSTAND, _DATEN_MOD = ue("Spielstand"), ue("Daten-Mod")
QUELLEN = ((re.compile(rf"\s*\((?:{_DATEN_MOD}|{_SPIELSTAND}(?: [\d.]+)?|{ue('Spielmechanik')}|{ue('Spieldatei')}|{ue('Spielwert')}|Defines[^()]*|Test [\d./ ]+"
                       r"|(?:Location|Country|Market)\.[^()]*)\)"), ""),
           (re.compile(rf"[;,]\s*(?:{_SPIELSTAND}(?: [\d.]+)?|{_DATEN_MOD})(?=\))"), ""),
           (re.compile(rf"\({_SPIELSTAND}(?: [a-z_]+)?; "), "("),
           (re.compile(rf"\({ue('Schätzung')}:[^()]*\)"), f"({ue('Schätzung')})"),
           (re.compile(r"\s*[–-]?\s*[Nn]ach dem (?:Umsetzen|Erforschen) markieren\.?" if sprache.DEUTSCH
                       else r"\s*[–-]?\s*[Mm]ark (?:it )?after (?:implementing|researching)\.?"), ""),
           (re.compile(rf"{ue('Bedingung nicht prüfbar')}: [^;\n]*"), ue("Weitere Bedingungen nicht prüfbar")),    # sonst Schlüssel der Spieldatei
           (re.compile(rf" {re.escape(ue('Nr.'))} \d{{5,}}"), ""))    # Nummer einer Handelsbestellung: im Spiel nirgends zu sehen


def _f(code, text):
    return f"{FARBE}{code} {text}{FARBE}!"


def titel(s):
    return _f("T", s)


def kopf(s):
    return _f("Y", s)


def neben(s):
    return _f("L", s)


def quellen_weg(s):
    s = str(s if s is not None else "")
    for muster, ersatz in QUELLEN:
        s = muster.sub(ersatz, s)
    return s.strip()


def trennen(s, zeichen):
    """Text an „<zeichen> “ teilen, nicht innerhalb von Klammern und Anführungszeichen; Punkt nur am Satzende vor einem Großbuchstaben."""
    teile, tiefe, start = [], 0, 0
    for i, c in enumerate(s):
        tiefe += (c in AUF) - (c in ZU and tiefe > 0)
        if tiefe or c != zeichen or s[i + 1:i + 2] != " ":
            continue
        danach = s[i + 2:i + 3]
        if zeichen == "." and (ABKUERZUNG.search(s[start:i]) or not (danach.isupper() or danach == ANFUEHRUNG)):
            continue
        teile.append(s[start:i])
        start = i + 2
    teile.append(s[start:])
    return [t.strip() for t in teile if t.strip()]


def _gross(s):
    return s[:1].upper() + s[1:]


def _gruppieren(teile):
    """„Vieh: im Spiel prüfen“, „Wolle: im Spiel prüfen“ -> „Vieh, Wolle: im Spiel prüfen“ (Reihenfolge bleibt)."""
    gruppen = {}
    for t in teile:
        a = trennen(t, ":")
        name, rest = (a[0], ": ".join(a[1:])) if len(a) > 1 else ("", t)
        gruppen.setdefault(rest, []).append(name)
    return [f"{', '.join(n for n in namen if n)}: {rest}" if any(namen) else rest for rest, namen in gruppen.items()]


def punkte(text, folge=0):
    """Fließtext -> [(Ebene, Zeile)]: je Satz und je Teil einer Semikolon-Liste eine Zeile. Hat der erste Teil einen Kopf („Kopf: a: 1; b: 2“),
    steht der Kopf für sich und die Teile eine Ebene tiefer. folge = Ebene der Sätze nach dem ersten."""
    out = []
    for n, satz in enumerate(trennen(quellen_weg(text), ".")):
        ebene = folge if n else 0
        teile = trennen(satz.rstrip(" .;"), ";")
        doppel = [len(trennen(t, ":")) - 1 for t in teile]
        if len(teile) > 1 and doppel[0] > 0 and all(x == doppel[0] - 1 for x in doppel[1:]):
            a = trennen(teile[0], ":")
            out.append((ebene, a[0] + ":"))
            teile[0] = ": ".join(a[1:])
            out += [(1, _gross(t)) for t in _gruppieren(teile)]
        else:
            out += [(ebene, t) for t in _gruppieren(teile)]
    return [(e, z if i == 0 else _gross(z)) for i, (e, z) in enumerate(out)]


def _liste(ebene, zeile_):
    return _f(f"indent_newline:{EINZUG[ebene]}", ("    – " if ebene else "• ") + zeile_)


def abschnitt(name, zeilen):
    """Ein Punkt: „Name: Text“ in einer Zeile; Kopfsatz mit Liste: Kopfsatz hinter dem Namen; sonst Überschrift und Liste."""
    if not zeilen:
        return ""
    name = ue(name)
    if len(zeilen) == 1:
        return f"{kopf(name + ':')} {zeilen[0][1]}"
    if zeilen[0][1].endswith(":") and all(e == 1 for e, _ in zeilen[1:]):
        return "\n".join([f"{kopf(name + ':')} {zeilen[0][1]}"] + [_liste(0, z) for _, z in zeilen[1:]])
    return "\n".join([kopf(name)] + [_liste(e, z) for e, z in zeilen])


def _kopfzeilen(s):
    """Titel; ein überlanger mit Aufzählung („Handelsbestellung …: Vieh …, Wolle …“) als kurzer Titel mit Liste."""
    s = quellen_weg(s)
    a = trennen(s, ":")
    if len(s) > TITEL_MAX and len(a) == 2:
        return "\n".join([titel(a[0])] + [_liste(0, x) for x in trennen(a[1], ",")])
    return titel(s)


def _warum(gruende):
    zeilen, platz, rest = [], WARUM_ZEILEN, 0
    for i, g in enumerate(gruende):
        p = punkte(g, folge=1)
        n = sum(1 + len(z) // ZEICHEN for _, z in p)
        if zeilen and n > platz:
            rest = len(gruende) - i
            break
        platz -= n
        zeilen += p
    text = abschnitt("Warum", zeilen)
    mehr = ue("1 weiterer Grund") if rest == 1 else ue(t"{rest} weitere Gründe")
    return text + "\n" + neben(ue(t"… {mehr} auf der Seite im Browser")) if rest else text


def _bloecke(*teile):
    """Blöcke mit Leerzeile dazwischen; zwei einzeilige stehen direkt untereinander (der Tooltip soll nicht unnötig hoch werden)."""
    out, davor = "", ""
    for b in teile:
        if b:
            out += b if not out else ("\n" if "\n" not in b + davor else "\n\n") + b
            davor = b
    return out


def empfehlung(name, handlung, gruende, wirkung, schwerpunkt=None):
    return _bloecke(_kopfzeilen(name), abschnitt("Schwerpunkt", [(0, schwerpunkt)]) if schwerpunkt else "",
                    abschnitt("Was tun", punkte(handlung)) if handlung else "", _warum(gruende or []),
                    abschnitt("Wirkung", punkte(wirkung)) if wirkung else "")


def schritt(name, warum, kosten):
    return _bloecke(_kopfzeilen(name), abschnitt("Warum", punkte(warum)) if warum else "", abschnitt("Kosten", punkte(kosten)) if kosten else "")


def zeile(text):
    """Tooltip einer Zelle oder Tabellenzeile: je Zeile und Semikolon-Teil eine Zeile, Quellen weg. Zeilen mit bekannter Bezeichnung
    („Kosten: …“) beginnen einen Abschnitt, Zeilen ohne Bezeichnung dahinter gehören zu ihm."""
    vorn, teile = [], []
    for z in str(text if text is not None else "").split("\n"):
        z = quellen_weg(z)
        m = ETIKETT.match(z)
        if m:
            teile.append((m[1], []))
            z = z[m.end():]
        (teile[-1][1] if teile else vorn).extend(trennen(z, ";"))
    return _bloecke("\n".join(x if i == 0 else _gross(x) for i, x in enumerate(vorn)),
                    *(abschnitt(n, [(0, x if i == 0 else _gross(x)) for i, x in enumerate(zs)]) for n, zs in teile))


def pruefung(text, tun):
    return _bloecke(titel(ue("Prüfung Spiel und Daten-Mod")), zeile(text), abschnitt("Was tun", punkte(tun)) if tun else "")


def mit_titel(name, zeilen):
    return _bloecke(titel(name), zeile("\n".join(zeilen)))


def mit_klick(text, klick):
    """Klick-Hinweis abgesetzt ans Ende – er gehört nicht zum Inhalt."""
    return "\n\n".join(x for x in (text, neben(klick) if klick else "") if x)
