"""Text-Symbole (texticon) für die Seitenleiste im Spiel (Mod 0.28, 03.11.; Nutzer: „eigentlich haben doch alle eigenschaften und
modifikatoren symbole ingame, kannst du diese benutzen in allen fenstern wenn möglich, gerade güter.“ – „ja, so bauen“).

Das Spiel kennt Text-Symbole nur aus main_menu/gui/shared/font_icons.gui (381 texticon-Blöcke; keine andere .gui des Spiels
definiert texticon – Suche 03.11. in game/*/gui: sonst nur zwei auskommentierte Blockzeilen in in_game/gui/shared/windows.gui).
Ohne Beleg, dass das Spiel texticon-Blöcke aus anderen Dateien liest, übernimmt der Bau die Spieldatei und ergänzt sie hinten
(wie left_panel.gui): BOM und Zeilenenden wie das Original, Fingerabdruck in rg_basis.json, die Datei zählt zu den überdeckten
Dateien (eu5ratgeber/spielversion.py, tools/patch_pruefung.py melden ein Spiel-Update).

Eigene Symbole (Präfix rg_) nur für die Dinge, die unsere Texte nennen: Güter (rg_g_<gut>), Gebäude (rg_b_<gebäude>),
Institutionen (rg_i_<institution>), Krankheiten (rg_d_<krankheit>), Kabinettsaktionen (rg_c_<aktion>), Gesetze (rg_l_<gesetz>).
Stände haben schon Spielsymbole (nobles_estate …). Zuordnung Schlüssel -> Bild beim Bau aus den Spieldateien: Schlüssel = Blöcke
der obersten Ebene in in_game/common/<ordner>, Bild nach dem Namensmuster des Ordners gfx/interface/icons/<…>; Kabinettsaktionen
mit eigenem „icon = …“ nehmen dieses Bild. Gibt es die Textur nicht, gibt es kein Symbol (nichts raten).

Zur Laufzeit (Ratgeber) gelten nur die Symbole, die der installierte Mod wirklich definiert (namen()): ein älterer Mod ohne
ergänzte font_icons.gui bekommt keine eigenen Symbole – sonst stünde „@rg_g_wheat!“ unerklärt im Text."""
import os
import re
from pathlib import Path

from . import gamedata

FONT_ICONS = Path("main_menu/gui/shared/font_icons.gui")
MARKE = "# EU5 Ratgeber (Daten-Mod) - eigene Text-Symbole, eingefuegt von eu5ratgeber/ingame_symbole.py"
TEX_ORDNER = ("main_menu", "in_game")                 # dort liegen die Bilder (gfx/…); Mod-Test prüft dieselben Ordner
# Kürzel -> (Ordner der Schlüssel in in_game/common, Bild mit {} = Schlüssel bzw. eigenes icon)
ARTEN = {"g": ("goods", "gfx/interface/icons/trade_goods/icon_goods_{}.dds"),
         "b": ("building_types", "gfx/interface/icons/buildings/{}.dds"),
         "i": ("institution", "gfx/interface/icons/institutions/{}.dds"),
         "d": ("diseases", "gfx/interface/icons/disease/{}.dds"),
         "c": ("cabinet_actions", "gfx/interface/icons/cabinet_actions/{}.dds"),
         "l": ("laws", "gfx/interface/icons/laws/{}.dds")}
_ZEILE = re.compile(r"^﻿?([A-Za-z_][\w]*)\s*=\s*\{")


def name(art, key):
    return f"rg_{art}_{key}"


def _bloecke(text):
    """{Schlüssel: eigenes icon oder None} der Blöcke auf oberster Ebene (Kommentare entfernt, Tiefe über die Klammern)."""
    out, tiefe, aktuell = {}, 0, None
    for z in text.splitlines():
        z = z.split("#", 1)[0]
        if tiefe == 0:
            m = _ZEILE.match(z)
            if m:
                aktuell = m.group(1)
                out.setdefault(aktuell, None)
        elif tiefe == 1 and aktuell:
            m = re.match(r"^\s*icon\s*=\s*([\w]+)\s*$", z)
            if m:
                out[aktuell] = m.group(1)
        tiefe += z.count("{") - z.count("}")
        tiefe = max(tiefe, 0)
    return out


def _textur_da(game, tex):
    return any((Path(game) / o / tex).exists() for o in TEX_ORDNER)


def alle(game=None):
    """[(Name, Textur)] aller eigenen Symbole, deren Bild es im Spiel gibt – sortiert, je Name einmal."""
    game = Path(game or gamedata.GAME_DIR)
    out = {}
    for art, (ordner, muster) in ARTEN.items():
        d = game / "in_game" / "common" / ordner
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.txt")):
            for key, icon in _bloecke(f.read_text(encoding="utf-8-sig", errors="replace")).items():
                tex = muster.format(icon or key)
                if _textur_da(game, tex):
                    out.setdefault(name(art, key), tex)
    return sorted(out.items())


def bloecke(symbole):
    """texticon-Blöcke wie in der Spieldatei (Größe und Versatz wie die Stände-Symbole: @font_icon_default_…), je Block eine
    Zeile – 861 Symbole wären sonst ~235 KB."""
    return "".join(f'texticon = {{ icon = {n} iconsize = {{ texture = "{t}" size = {{ @font_icon_default_size '
                   f'@font_icon_default_size }} offset = {{ 0 @font_icon_default_offset }} fontsize = @font_icon_default_fontsize }} }}\n'
                   for n, t in symbole)


def font_icons(vanilla, symbole):
    """font_icons.gui des Spiels, hinten um die eigenen Symbole ergänzt (Zeilenenden wie das Original). Steht die Marke schon
    drin oder fehlt ein texticon-Block (Spiel-Update), bricht der Bau ab."""
    if MARKE in vanilla or "texticon = {" not in vanilla:
        raise ValueError("font_icons.gui: Marke schon vorhanden oder keine texticon-Blöcke – Spiel-Update? Datei prüfen")
    nl = "\r\n" if "\r\n" in vanilla else "\n"
    zusatz = f"\n\n{'#' * 36}\n{MARKE}\n{'#' * 36}\n" + bloecke(symbole)
    return vanilla.rstrip("\r\n") + nl + zusatz.replace("\n", nl)


def spiel_namen(game=None):
    """Namen der Text-Symbole des Spiels (font_icons.gui des Spiels)."""
    p = Path(game or gamedata.GAME_DIR) / FONT_ICONS
    try:
        return set(re.findall(r"^\s*icon\s*=\s*(\w+)", p.read_text(encoding="utf-8-sig", errors="replace"), re.M))
    except OSError:
        return set()


_CACHE = {}


def namen(mod=None, game=None):
    """Eigene Symbole (rg_…), die der Text benutzen darf: die der installierten font_icons.gui des Mods. Mod ohne ergänzte Datei
    (älter als 0.28) -> keine; kein Mod-Ordner (Test, Bau) -> alle aus den Spieldateien."""
    mod = Path(mod) if mod else None
    p = mod / FONT_ICONS if mod else None
    try:
        stempel = (str(p), p.stat().st_mtime) if p and p.exists() else (str(mod), bool(mod and mod.exists()), str(game))
    except OSError:
        stempel = (str(mod), False, str(game))
    if stempel in _CACHE:
        return _CACHE[stempel]
    if p and p.exists():
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        # ohne Zeilenanker: bloecke() schreibt je Block eine Zeile („texticon = { icon = rg_… “) – Prüfung 03.11.: mit ^ fand der
        # Ausdruck im gebauten Mod 0 statt 861 Namen, im Spiel wären keine eigenen Symbole angekommen
        ns = set(re.findall(r"\bicon\s*=\s*(rg_\w+)", text)) if MARKE in text else set()
    elif mod and mod.exists():
        ns = set()
    else:
        ns = {n for n, _ in alle(game)}
    _CACHE[stempel] = ns
    return ns


if __name__ == "__main__":
    xs = alle()
    print(len(xs), "Symbole;", {a: sum(1 for n, _ in xs if n.startswith(f"rg_{a}_")) for a in ARTEN})
    print(len(bloecke(xs).encode()), "Byte", os.linesep)
