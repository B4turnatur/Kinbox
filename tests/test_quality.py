"""Formatwahl: Auflösung hat Vorrang vor 60 fps und Codec (sonst schlägt 720p60 ein 1440p30).
Prüft die echten -f/-S-Argumente aus build_args() mit yt-dlp gegen nachgebaute Formate (kein Netz).
Start: python tests/test_quality.py   (braucht yt-dlp im PATH, sonst wird nur die Reihenfolge geprüft)"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402


def args(**o):
    return server.build_args({"url": "https://example.com/v/1", "mode": "video", **o}, Path("."))


def after(a, flag):
    return a[a.index(flag) + 1]


def fmt(i, h, fps, vc, ac="none"):
    d = {"format_id": i, "url": "https://example.invalid/" + i, "ext": "mp4", "protocol": "https", "vcodec": vc, "acodec": ac}
    d.update({"height": h, "width": h * 16 // 9, "fps": fps, "tbr": h / 10} if h else {"tbr": 128})
    return d


# Reihenfolge der Sortierfelder
assert after(args(quality="best"), "-S").startswith("res,fps"), args(quality="best")
assert after(args(quality="best", vcodec="h264"), "-S").startswith("res,vcodec:h264,fps")
assert after(args(quality="1080", vcodec="h264"), "-S").startswith("res:1080,vcodec:h264,fps")
assert after(args(quality="best", prefer60fps=False), "-S") == "res,acodec:m4a"
# Einzelvideo nochmal laden ersetzt die alte Datei, Playlists überspringen Vorhandenes
assert "--force-overwrites" in args(quality="best")
assert "--force-overwrites" not in args(playlist="all") and "--force-overwrites" not in args(playlist="items", playlistItems="1-3")
try:
    args(quality="hoch")
    raise AssertionError("ungültige Qualität angenommen")
except server.OptionError:
    pass

# JavaScript-Laufzeit für YouTube: yt-dlp nimmt von sich aus nur deno aus dem PATH
real_which, real_home = shutil.which, Path.home
try:
    for found, home_deno, want in ((["deno", "node"], False, []), (["node"], False, ["--js-runtimes", "node"]),
                                   (["qjs"], False, ["--js-runtimes", "quickjs"]), ([], False, []),
                                   (["node"], True, "deno")):
        shutil.which = lambda exe, found=found: exe if exe in found else None
        with tempfile.TemporaryDirectory() as h:
            if home_deno:
                exe = Path(h) / ".deno" / "bin" / ("deno.exe" if server.IS_WINDOWS else "deno")
                exe.parent.mkdir(parents=True); exe.write_text("")
            Path.home = staticmethod(lambda h=h: Path(h))
            got = server.js_runtime_args()
        if want == "deno":
            assert got[0] == "--js-runtimes" and got[1].startswith("deno:"), got
        else:
            assert got == want, (found, got)
    server.SETTINGS["extra_args"] = ["--js-runtimes", "bun"]
    assert server.js_runtime_args() == []                                   # eigene Einstellung gewinnt
finally:
    shutil.which, Path.home = real_which, real_home
    server.SETTINGS["extra_args"] = []

ytdlp = shutil.which("yt-dlp")
if not ytdlp:
    print("yt-dlp fehlt – nur Reihenfolge geprüft")
    sys.exit(0)

FORMATS = [fmt("v720p60", 720, 60, "avc1"), fmt("v1080p30", 1080, 30, "avc1"), fmt("v1080p60", 1080, 60, "vp9"),
           fmt("v1440p30", 1440, 30, "vp9"), fmt("a", None, None, "none", "mp4a.40.2")]


def pick(**o):
    a = args(**o)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "x.info.json"
        f.write_text(json.dumps({"id": "x", "title": "t", "extractor": "generic", "extractor_key": "Generic",
                                 "webpage_url": "https://example.invalid/x", "formats": FORMATS}), "utf-8")
        r = subprocess.run([ytdlp, "-q", "--no-warnings", "--load-info-json", str(f), "-f", after(a, "-f"),
                            "-S", after(a, "-S"), "--print", "%(format_id)s"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


assert pick(quality="best") == "v1440p30+a", pick(quality="best")                    # höchste Auflösung, nicht 720p60
assert pick(quality="best", vcodec="h264") == "v1440p30+a"                           # Codec nur bei gleicher Auflösung
assert pick(quality="1080") == "v1080p60+a", pick(quality="1080")                    # bei gleicher Auflösung 60 fps
assert pick(quality="1080", vcodec="h264") == "v1080p30+a", pick(quality="1080", vcodec="h264")
assert pick(quality="720") == "v720p60+a"
print("Formatwahl ok")
