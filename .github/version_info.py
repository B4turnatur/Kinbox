"""Schreibt version.txt (Windows-Dateiinfos für Kinbox.exe) aus dem Git-Tag, z. B. `python version_info.py v3.5.1`.
Eine exe ohne Hersteller/Beschreibung wirkt auf Virenscanner verdächtiger."""
import sys

v = sys.argv[1].lstrip("v")
n = tuple(([int(x) for x in v.split(".")] + [0, 0, 0, 0])[:4])
info = {"CompanyName": "Kinbox", "FileDescription": "Kinbox - home video downloader and library",
        "FileVersion": v, "InternalName": "Kinbox", "LegalCopyright": "MIT License",
        "OriginalFilename": "Kinbox.exe", "ProductName": "Kinbox", "ProductVersion": v}
strings = ", ".join(f"StringStruct({k!r}, {val!r})" for k, val in info.items())
open("version.txt", "w", encoding="utf-8").write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={n}, prodvers={n}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [{strings}])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
""")
