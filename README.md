# EU5 Ratgeber

Strategieberater für Europa Universalis V. Das Programm liest deine laufende Partie und schreibt Empfehlungen in eine Seitenleiste im Spiel. Dazu gibt es eine Seite im Browser mit allen Daten.

Dieses Repo enthält das Programm. Die Seitenleiste kommt aus dem Mod EU5 Ratgeber im Steam Workshop. Ohne den Mod zeigt das Programm nur die Seite im Browser.

**Stand:** in Entwicklung, noch nicht veröffentlicht. Seitenleiste auf Deutsch und Englisch, die Seite im Browser vorerst nur auf Deutsch.

## Wie es arbeitet

Der Mod schreibt jeden Spielmonat Werte ins Log des Spiels. Das Programm liest dieses Log und die Spielstände, rechnet und schreibt die Texte für die Seitenleiste. Es läuft nur auf deinem Rechner und schickt nichts ins Internet. Es enthält keine Spieldateien, sondern liest sie aus deiner Installation.

Voraussetzungen: Windows, Europa Universalis V über Steam, Startoption `-force_text_save`.

## Starten

Fertiges Programm: Zip von der Seite [Releases](https://github.com/derdude-dev/eu5-ratgeber-programm/releases) laden, `release/LIESMICH.txt` lesen.

Aus dem Quelltext (Python 3.14, nur Standardbibliothek):

```
python tools/ratgeber.py start --browser
```

Exe bauen: PyInstaller in einem venv unter `../Exe_bau/venv` installieren, dann `python tools/build_exe.py`.

## Aufbau

| Ordner | Inhalt |
|---|---|
| `eu5ratgeber/` | Einlesen, Regeln, Empfehlungen, Texte für die Seitenleiste; `pfade.py` findet Spiel, Nutzerdaten und Mod |
| `web/` | Seite im Browser |
| `tools/` | `ratgeber.py` (Server), `waechter.py` (Start mit dem Spiel), `programm.py` (Einstieg der Exe), `build_exe.py` |
| `analysis/MECHANIK.md` | Geprüfte Formeln, Quelle für das Wiki im Programm |

## Lizenz

MIT, siehe [LICENSE](LICENSE). Das Programmsymbol stammt aus einem Foto unter CC BY 2.0, Angaben in [NOTICE.md](NOTICE.md).

Kein offizielles Produkt von Paradox Interactive. Europa Universalis V ist eine Marke von Paradox Interactive.

## English

A strategy advisor for Europa Universalis V. This repository holds the companion program for the EU5 Ratgeber mod. The in-game panel is available in German and English, the browser page is in German for now. MIT license.
