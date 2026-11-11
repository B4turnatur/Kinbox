"""Windows-Skripte (server/*.bat): CRLF, nur ASCII, keine Store-Python-Falle, Autostart ohne Admin/Limits.
Start: python tests/test_bat.py"""
import re
from pathlib import Path

BATS = sorted((Path(__file__).resolve().parent.parent / "server").glob("*.bat"))
assert {b.name for b in BATS} >= {"install.bat", "start.bat", "autostart.bat"}, BATS

for bat in BATS:
    raw = bat.read_bytes()
    # cmd.exe liest Sprungmarken bei reinen LF-Zeilen falsch („Das Sprungziel wurde nicht gefunden“)
    assert raw.endswith(b"\r\n"), f"{bat.name}: letzte Zeile ohne CRLF"
    assert raw.count(b"\n") == raw.count(b"\r\n"), f"{bat.name}: LF ohne CR"
    assert b"\r\r" not in raw, f"{bat.name}: doppeltes CR"
    assert all(c < 128 for c in raw), f"{bat.name}: Nicht-ASCII-Zeichen (Umlaute) – Codepage-Probleme"
    text = raw.decode("ascii")
    # Store-Platzhalter python.exe existiert immer → Python wirklich starten statt „where python“
    assert not re.search(r"where\s+(python|py)\b", text, re.I), f"{bat.name}: 'where python' erkennt den Store-Platzhalter nicht"
    if re.search(r"%PY%", text):
        assert 'py -3 -c "import sys"' in text and 'python -c "import sys"' in text, f"{bat.name}: Python-Prüfung fehlt"
    labels = set(re.findall(r"^:(\w+)", text, re.M))
    for target in re.findall(r"\b(?:goto|call)\s+:(\w+)", text, re.I):
        assert target == "eof" or target in labels, f"{bat.name}: Sprungziel :{target} fehlt"

auto = (BATS[0].parent / "autostart.bat").read_text("ascii")
assert "/RL HIGHEST" not in auto and "LeastPrivilege" in auto, "Autostart ohne Admin-Rechte"
assert "<ExecutionTimeLimit^>PT0S" in auto, "kein 72-h-Limit"
assert "<StopIfGoingOnBatteries^>false" in auto and "<DisallowStartIfOnBatteries^>false" in auto, "läuft auch im Akkubetrieb"
assert "/XML" in auto and "powershell" not in auto.lower(), "Aufgabe per XML, ohne PowerShell"
assert "netsh" not in auto, "Firewall-Regel bleibt in install.bat"
inst = (BATS[0].parent / "install.bat").read_text("ascii")
assert "netsh advfirewall firewall add rule" in inst
assert inst.count("if errorlevel 1 goto :setupfail") == 2, "Fehler von server.py --setup erkannt"
assert "where winget" in inst
print(f"bat ok ({len(BATS)} Dateien)")
