"""Sprache des Ratgebers (Englischpaket, release/ENGLISCH.md).

Die Sprache des Spiels steht in pdx_settings.json. Deutsch bleibt die Quelle: ein Spiel auf Deutsch zeigt die Texte, wie sie im Code stehen, jede
andere Sprache die englischen aus dem Katalog texte_en.json. Namen von Gütern, Gebäuden, Orten … kommen immer in der Sprache des Spiels aus den
Spieldateien.

Texte stehen als t-String im Code, der Rest bleibt ein normaler Ausdruck:

    ue(t"Steuer um {punkte} Punkte senken")          Schlüssel im Katalog: "Steuer um {} Punkte senken"
    ue("Was tun")

Im Katalog stehen Platzhalter als {} oder, wenn sich die Reihenfolge ändert, als {0} {1}. Fehlt ein Eintrag, bleibt der deutsche Text. Das Werkzeug
tools/texte.py meldet fehlende Einträge und was in der Ausgabe noch deutsch ist.

Zum Prüfen überschreibbar: EU5_RATGEBER_SPRACHE (z. B. l_english).
"""
import functools
import json
import os
import re

from . import pfade

SPRACHEN = ("german", "english", "french", "spanish", "polish", "russian", "braz_por", "japanese", "korean", "simp_chinese", "turkish")
KATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "texte_en.json")


def spiel_sprache(nutzer_ordner=None):
    """Sprache des Spiels, z. B. l_german; ohne Einstellung (Spiel nie gestartet) l_english wie im Spiel selbst."""
    if os.environ.get("EU5_RATGEBER_SPRACHE"):
        return os.environ["EU5_RATGEBER_SPRACHE"]
    try:
        s = open(os.path.join(nutzer_ordner or pfade.nutzer(), "pdx_settings.json"), encoding="utf-8-sig", errors="replace").read()
    except OSError:
        return "l_english"
    m = re.search(r'"language"\s*:\s*"l_(\w+)"', s)
    return f"l_{m[1]}" if m and m[1] in SPRACHEN else "l_english"


AKTIV = spiel_sprache()
ORDNER = AKTIV[2:]                  # Ordner unter localization/, zugleich Sprache für gamedata.load_loc
DEUTSCH = AKTIV == "l_german"
KOMMA = "," if DEUTSCH else "."     # Dezimalzeichen der Ausgabe


@functools.lru_cache(maxsize=1)
def katalog():
    try:
        return json.load(open(KATALOG, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def schluessel(text):
    """Katalog-Schlüssel eines Texts oder t-Strings."""
    return text if isinstance(text, str) else "{}".join(text.strings)


def _wert(i):
    v = i.value
    if i.conversion:
        v = {"r": repr, "s": str, "a": ascii}[i.conversion](v)
    return format(v, i.format_spec)


def _einsetzen(vorlage, werte):
    reihe = iter(werte)
    return re.sub(r"\{(\d*)\}", lambda m: str(werte[int(m[1])] if m[1] else next(reihe)), vorlage)


def _deutsch(text, werte):
    return "".join(s + w for s, w in zip(text.strings, [*werte, ""]))


def ue(text):
    """Text in der Sprache der Ausgabe."""
    if isinstance(text, str):
        return text if DEUTSCH else katalog().get(text, text)
    werte = [_wert(i) for i in text.interpolations]
    vorlage = None if DEUTSCH else katalog().get(schluessel(text))
    return _deutsch(text, werte) if vorlage is None else _einsetzen(vorlage, werte)


def englisch(text):
    """Fester deutscher Text auf Englisch (Bau des Mods: alle Sprachen in einem Lauf). Fehlt er im Katalog, bleibt er deutsch."""
    return katalog().get(text, text)


def ziffern(s):
    """Zahl im englischen Format („1,234.50“, wie f"{v:,.2f}") in die Schreibweise der Ausgabe."""
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".") if DEUTSCH else s
