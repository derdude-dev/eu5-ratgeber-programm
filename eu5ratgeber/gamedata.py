"""Spieldateien: Lokalisierung (Anzeigenamen) und Definitionen aus in_game/common."""
import glob
import os
import re

from . import pdx, pfade, sprache

GAME_DIR = pfade.spiel()
LOC_LINE = re.compile(r'^\s*([\w.\-]+):\d*\s*"(.*)"\s*(?:#.*)?$')


def load_loc(lang=None, game_dir=GAME_DIR):
    """Alle Lokalisierungsdateien einer Sprache (Hauptspiel und DLC) -> {schlüssel: text}; ohne Angabe die Sprache des Spiels."""
    lang = lang or sprache.ORDNER
    loc = {}
    pattern = os.path.join(glob.escape(game_dir), "**", "localization", lang, "**", "*.yml")      # escape: [ ] im Pfad (D:\Spiele [SSD])
    for fn in sorted(glob.glob(pattern, recursive=True)):
        with open(fn, encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                m = LOC_LINE.match(line)
                if m:
                    loc[m.group(1)] = m.group(2)
    return loc


def modifikatoren(game_dir=GAME_DIR):
    """Namen aller Modifikatoren aus den Spieldateien – dieselbe Liste wie docs/modifiers.log (2.750 von 2.750, geprüft 05.11.), die es nur
    nach dem Konsolenbefehl script_docs gibt."""
    fs = glob.glob(os.path.join(glob.escape(game_dir), "main_menu", "common", "modifier_type_definitions", "*.txt"))
    fs += glob.glob(os.path.join(glob.escape(game_dir), "dlc", "*", "main_menu", "common", "modifier_type_definitions", "*.txt"))
    out = set()
    for f in fs:
        with open(f, encoding="utf-8-sig", errors="replace") as d:
            out.update(m[1] for m in (re.match(r"(\w+)\s*=\s*\{", z) for z in d) if m)
    return sorted(out)


def load_defs(folder, game_dir=GAME_DIR):
    """Alle .txt eines common-Ordners (Hauptspiel und DLC) zusammengeführt -> {name: definition}."""
    defs = {}
    pattern = os.path.join(glob.escape(game_dir), "**", "in_game", "common", folder, "*.txt")
    for fn in sorted(glob.glob(pattern, recursive=True)):
        with open(fn, "rb") as f:
            parsed = pdx.parse(f.read().lstrip(b"\xef\xbb\xbf"))
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                if not k.startswith("@") and k != "_items":
                    defs[k] = v
    return defs


REF = re.compile(r"\$([\w.]+)(?:\|[^$]*)?\$")                     # $SCHLÜSSEL$ -> anderer Text
FUNC = re.compile(r"\[\w+\('(\w+)'\)(?:\.\w+)*(?:\|(\w*))?\]")       # [ShowGoodsNameWithNoTooltip('x')], [ShowTownRightsName('x')|l]
# [Concept('wars', 'Kriegserlaubnis')|e] -> der angezeigte Text (1.4.5: 10 Modifikator-Namen blieben sonst Codes, 29.10.)
CONCEPT_TEXT = re.compile(r"\[Concept\('\w+',\s*'([^'\]]*)'\)(?:\|\w*)?\]")
CONCEPT = re.compile(r"\[(\w+)(?:\|\w*)?\]")                       # [trust|e], [towns_and_cities]
ICON = re.compile(r"@\w+!\s*|#\w+\s|#!")                           # Symbole und Formatierung


def clean_loc(text, loc, depth=0):
    """Verweise in einem Lokalisierungstext auflösen. None, wenn ein Laufzeitausdruck übrig bleibt."""
    if text is None or depth > 4:
        return text

    def ref(key):
        t = loc.get(key)
        return clean_loc(t, loc, depth + 1) if t else None

    def fall(t, fmt):
        """Format hinter dem Verweis wie im Spiel: l = erster Buchstabe klein, U = groß."""
        if not t or not fmt:
            return t
        return t[:1].lower() + t[1:] if "l" in fmt else t[:1].upper() + t[1:] if "U" in fmt else t

    text = CONCEPT_TEXT.sub(lambda m: m.group(1), text)
    text = REF.sub(lambda m: ref(m.group(1)) or m.group(1), text)
    text = FUNC.sub(lambda m: fall(ref(m.group(1)), m.group(2)) or m.group(1), text)
    text = CONCEPT.sub(lambda m: ref("game_concept_" + m.group(1)) or ref(m.group(1)) or m.group(1), text)
    text = ICON.sub("", text).strip()
    return None if "[" in text or "$" in text else text


class Names:
    """Anzeigenamen mit Rückfall auf den Schlüssel, wenn keine Übersetzung existiert."""

    def __init__(self, lang=None):
        self.loc = load_loc(lang)

    def __call__(self, key):
        if key is None:
            return None
        text = self.loc.get(str(key))
        if text and ("$" in text or "[" in text or "@" in text or "#" in text):
            text = clean_loc(text, self.loc)
        return text or str(key)
