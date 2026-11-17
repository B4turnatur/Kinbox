"""Vorschau beim Spulen: Raster aus 60 Bildern pro Video (braucht ffmpeg).
Start: python tests/test_strip.py"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402


def ff(*args):
    subprocess.run([server.ffmpeg_bin("ffmpeg"), "-v", "error", "-y", *args], check=True)


def size(path):
    r = subprocess.run([server.ffmpeg_bin("ffprobe"), "-v", "error", "-show_entries", "stream=width,height", "-of", "json", str(path)],
                       capture_output=True, check=True)
    s = json.loads(r.stdout)["streams"][0]
    return s["width"], s["height"]


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS.update(download_dir=str(d / "dl"))
    server.LIBRARY_FILE, server.USERS_FILE, server.THUMB_DIR = d / "library.json", d / "users.json", d / "thumbs"
    server.USERS.clear(); server.LIB.clear()
    admin = server.new_user("Mama", role="admin", folder="")
    kid = server.new_user("Kind")
    (d / "dl").mkdir()

    def add(name, owner, *src, dur):
        f = d / "dl" / name
        ff(*src, str(f))
        return server.lib_add(str(f), {"title": name, "duration": dur}, server.Job({"url": "https://example.com/" + name}, owner=owner["id"]))

    wide = add("quer.mp4", admin, "-f", "lavfi", "-i", "testsrc=s=320x180:d=6", "-pix_fmt", "yuv420p", dur=6)
    tall = add("hoch.mp4", admin, "-f", "lavfi", "-i", "testsrc=s=180x320:d=4", "-pix_fmt", "yuv420p", dur=0)   # Länge unbekannt → ffprobe
    song = add("lied.mp3", admin, "-f", "lavfi", "-i", "sine=frequency=440:duration=2", dur=2)

    # Raster: 10 Spalten × 6 Zeilen, Einzelbild passt in 200×200 und behält das Seitenverhältnis
    p = server.strip_make(wide)
    assert p and p.name == wide["id"] + ".strip.jpg" and size(p) == (2000, 6 * 112), (p, p and size(p))
    assert size(server.strip_make(tall)) == (10 * 112, 6 * 200)
    assert server.strip_make(wide) == p                                    # zweites Mal: aus dem Speicher

    c = server.app.test_client()
    H = lambda u: {"X-Token": u["token"], "Host": "localhost"}
    r = c.get(f"/api/library/{wide['id']}/strip", headers=H(admin))
    assert r.status_code == 200 and r.mimetype == "image/jpeg" and r.data[:2] == b"\xff\xd8", r.status_code
    r.close()
    assert c.get(f"/api/library/{song['id']}/strip", headers=H(admin)).status_code == 404       # nur für Videos
    assert c.get(f"/api/library/{wide['id']}/strip", headers=H(kid)).status_code in (403, 404)  # fremde Datei
    assert c.get(f"/api/library/{wide['id']}/strip").status_code == 401

    # neues Video: erst 202 (wird im Hintergrund erzeugt), kurz darauf 200
    new = add("neu.mp4", admin, "-f", "lavfi", "-i", "testsrc=s=320x180:d=3", "-pix_fmt", "yuv420p", dur=3)
    assert c.get(f"/api/library/{new['id']}/strip", headers=H(admin)).status_code == 202
    for _ in range(100):
        r = c.get(f"/api/library/{new['id']}/strip", headers=H(admin))
        code = r.status_code
        r.close()
        if code == 200:
            break
        time.sleep(0.2)
    assert code == 200, code

    # kaputte Datei: einmal versuchen, dann merken (kein Dauerfeuer auf ffmpeg)
    bad = d / "dl" / "kaputt.mp4"
    bad.write_bytes(b"kein video")
    e = server.lib_add(str(bad), {"title": "kaputt", "duration": 5}, server.Job({"url": "https://example.com/k"}, owner=admin["id"]))
    assert server.strip_make(e) is None and (server.THUMB_DIR / f"{e['id']}.strip.none").exists()
    assert c.get(f"/api/library/{e['id']}/strip", headers=H(admin)).status_code == 404

    # Löschen räumt das Raster mit weg
    server.lib_delete(wide["id"])
    assert not p.exists()

print("strip ok")
