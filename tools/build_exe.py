"""Exe des Ratgebers bauen: Ordner mit „EU5 Ratgeber.exe“ und Zip für den Download.

    python tools/build_exe.py

Braucht PyInstaller in ../Exe_bau/venv (python -m venv, pip install pyinstaller). Ergebnis in ../Mod_final:
  EU5 Ratgeber/                Programmordner
  EU5-Ratgeber-<Version>-windows.zip

Ordner statt Einzeldatei: startet schneller, entpackt sich nicht bei jedem Start, und genau dieses Entpacken lässt Virenscanner
öfter anschlagen. Kein Konsolenfenster (--windowed), Meldungen stehen in der Logdatei. Gebaut wird nur, was die Exe braucht: Python-Teile
findet PyInstaller über tools/programm.py, dazu web/ und die Mechanik-Notizen für das Wiki.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eu5ratgeber import pfade, version  # noqa: E402

BAU = ROOT.parent / "Exe_bau"
ZIEL = ROOT.parent / "Mod_final"
NAME = pfade.PROGRAMM
PYINSTALLER = BAU / "venv" / "Scripts" / "pyinstaller.exe"
# nur Standardbibliothek; was das Programm nicht nutzt, bleibt draußen (kleiner, weniger Angriffsfläche für Fehlalarme)
OHNE = ("tkinter", "unittest", "pydoc", "pdb", "doctest", "lib2to3", "test", "xmlrpc", "ftplib", "imaplib", "smtplib", "poplib")

VERSIONSDATEI = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}, 0), prodvers=({v}, 0), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [
      StringStruct('CompanyName', 'derdude-dev'),
      StringStruct('FileDescription', 'EU5 Ratgeber'),
      StringStruct('FileVersion', '{t}'),
      StringStruct('InternalName', 'EU5 Ratgeber'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'EU5 Ratgeber.exe'),
      StringStruct('ProductName', 'EU5 Ratgeber'),
      StringStruct('ProductVersion', '{t}')])]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ])
"""


def main():
    if not PYINSTALLER.exists():
        raise SystemExit(f"PyInstaller fehlt: {PYINSTALLER}")
    t = version.PROGRAMM_VERSION
    (BAU / "version.txt").write_text(VERSIONSDATEI.format(v=", ".join(t.split(".")), t=t), encoding="utf-8")
    befehl = [str(PYINSTALLER), "--noconfirm", "--clean", "--windowed", "--onedir", "--name", NAME,
              "--distpath", str(BAU / "dist"), "--workpath", str(BAU / "work"), "--specpath", str(BAU),
              "--paths", str(ROOT), "--paths", str(ROOT / "tools"), "--version-file", str(BAU / "version.txt"),
              "--icon", str(ROOT / "assets" / "ratgeber.ico"),
              "--add-data", f"{ROOT / 'web'};web", "--add-data", f"{ROOT / 'analysis' / 'MECHANIK.md'};analysis",
              "--add-data", f"{ROOT / 'eu5ratgeber' / 'texte_en.json'};eu5ratgeber"]
    befehl += [x for m in OHNE for x in ("--exclude-module", m)]
    subprocess.run(befehl + [str(ROOT / "tools" / "programm.py")], check=True)
    ordner = ZIEL / NAME
    if ordner.exists():
        shutil.rmtree(ordner)
    shutil.copytree(BAU / "dist" / NAME, ordner)
    shutil.copyfile(ROOT / "LICENSE", ordner / "LICENSE.txt")
    shutil.copyfile(ROOT / "NOTICE.md", ordner / "NOTICE.txt")
    shutil.copyfile(ROOT / "release" / "LIESMICH.txt", ordner / "LIESMICH.txt")
    shutil.copyfile(ROOT / "release" / "Ratgeber beenden.bat", ordner / "Ratgeber beenden.bat")
    z = ZIEL / f"EU5-Ratgeber-{t}-windows.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as a:
        for p in sorted(ordner.rglob("*")):
            if p.is_file():
                a.write(p, Path(NAME) / p.relative_to(ordner))
    groesse = sum(p.stat().st_size for p in ordner.rglob("*") if p.is_file())
    print(f"Ordner: {ordner} ({groesse / 1e6:.1f} MB)")
    print(f"Zip:    {z} ({z.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
