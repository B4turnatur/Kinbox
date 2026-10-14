"""cookie_args(): Kopie pro Auftrag, Ordner → cookies.txt, fehlende Datei → keine Cookies.
Start: python tests/test_cookies.py"""
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    src = d / "cookies.txt"
    src.write_text("# Netscape HTTP Cookie File\n")
    os.chmod(src, stat.S_IREAD)  # schreibgeschützt wie beim Errno-13-Fall

    for setting in (str(src), str(d)):  # Datei oder Ordner
        server.SETTINGS["cookies_file"] = setting
        args = server.cookie_args(d / "job")
        assert args[0] == "--cookies" and Path(args[1]) != src and Path(args[1]).read_text() == src.read_text(), args

    server.SETTINGS["cookies_file"] = str(d / "fehlt.txt")
    assert server.cookie_args(d / "job2") == []
    server.SETTINGS["cookies_file"] = ""
    assert server.cookie_args(d / "job3") == []
    os.chmod(src, stat.S_IWRITE | stat.S_IREAD)

# merge_cookies(): neue Datei ergänzt/ersetzt, Müll wird abgelehnt
ig = ".instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\tALT\n"
yt = "# Netscape HTTP Cookie File\r\n#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tY\r\n"
m = server.merge_cookies(ig, yt + ig.replace("ALT", "NEU"))
assert "NEU" in m and "ALT" not in m and "#HttpOnly_.youtube.com" in m and "\r" not in m, m
try:
    server.merge_cookies("", "<html>kein Cookie</html>")
    raise AssertionError("Müll angenommen")
except server.OptionError:
    pass

print("cookies ok")
