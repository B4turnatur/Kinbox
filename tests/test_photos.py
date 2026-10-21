"""Foto-Beiträge per gallery-dl (hier ein Ersatzskript, kein Netz) + richtiger Dateityp beim Download.
Start: python tests/test_photos.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

assert server.mime_of("a.MP4") == "video/mp4" and server.mime_of("a.webp") == "image/webp"
assert server.mime_of("a.mp3") == "audio/mpeg" and server.mime_of("a.xyz") == "application/octet-stream"
assert server.photo_site("https://www.instagram.com/p/x/") and not server.photo_site("https://youtube.com/watch?v=1")
assert server.is_photo_post("https://www.tiktok.com/@a/photo/123") and not server.is_photo_post("https://www.tiktok.com/@a/video/1")
assert not server.is_photo_post("https://www.instagram.com/p/x/")    # Instagram: erst yt-dlp, dann Ersatz

FAKE = r'''
import json, sys, pathlib
out = pathlib.Path(sys.argv[sys.argv.index("-D") + 1]); out.mkdir(parents=True)
meta = {"desc": "Urlaub am Meer: Tag 1\nmehr Text", "author": {"nickname": "Oma"}}
for n in ("123.mp3", "123_02.jpg", "123_01.jpg"):
    (out / n).write_bytes(b"x"); (out / (n + ".json")).write_text(json.dumps(meta))
    print(out / n)
print("[tiktok][info] fertig")
'''

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS["download_dir"] = str(d)
    server.LIBRARY_FILE = d / "library.json"
    (d / "fake.py").write_text(FAKE)
    server.gallerydl_base = lambda: [sys.executable, str(d / "fake.py")]
    server.ensure_gallerydl = lambda: None
    job = server.Job({"url": "https://www.tiktok.com/@a/photo/123"}, owner="u1")
    server.run_photos(job, d / "ziel")
    names = [Path(f).name for f in job.files]
    assert job.status == "finished", (job.status, job.error)
    assert names == ["Urlaub am Meer_ Tag 1 01.jpg", "Urlaub am Meer_ Tag 1 02.jpg", "Urlaub am Meer_ Tag 1.mp3"], names
    assert all(Path(f).exists() for f in job.files) and not list((d / "ziel").glob("*.json"))
    kinds = sorted(e["kind"] for e in server.LIB.values())
    assert kinds == ["audio", "image", "image"], kinds
    e = next(e for e in server.LIB.values() if e["name"].endswith("01.jpg"))
    assert e["title"] == "Urlaub am Meer: Tag 1 (1/2)" and e["uploader"] == "Oma", e

    (d / "fake.py").write_text('print("[instagram][error] HTTP redirect to login page")')
    job = server.Job({"url": "https://www.instagram.com/p/x/"}, owner="u1")
    server.run_photos(job, d / "ziel", "yt-dlp: login nötig")
    assert job.status == "error" and job.error == "yt-dlp: login nötig", job.error
    json.loads(server.LIBRARY_FILE.read_text(encoding="utf-8"))

print("OK")
