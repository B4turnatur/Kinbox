"""Besondere Links: TikTok-Sound (→ Musik als Audio) und Profilseiten (→ Profilbild). Ohne Netz.
Start: python tests/test_links.py"""
import io
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

SID = "7706264754948098830"
PAGES = {}          # Adresse → (Zieladresse, Inhalt)


class Fake(io.BytesIO):
    def __init__(self, url, body=b""):
        super().__init__(body)
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_open(req, timeout=0):
    url = req.full_url if hasattr(req, "full_url") else req
    if url not in PAGES:
        raise OSError("kein Netz im Test: " + url)
    return Fake(*PAGES[url])


urllib.request.urlopen = fake_open


def embed(videos, artist="NASA"):
    state = {"source": {"data": {f"/embed/music/{SID}": {"videoList": videos, "embedInfo": {
        "artist": artist, "coverUrl": "https://example.com/cover.jpg", "id": SID}}}}}
    return ("", ('<html><script id="__FRONTITY_CONNECT_STATE__" type="application/json">' + json.dumps(state)
                 + "</script></html>").encode())


# ---- Sound-Links erkennen (auch Kurzlinks) --------------------------------------
assert server.sound_id(f"https://www.tiktok.com/music/original-sound-NASA-{SID}") == SID
assert server.sound_id(f"https://www.tiktok.com/music/{SID}?lang=de") == SID
assert server.sound_id(f"https://m.tiktok.com/music/Zwei-Wörter-ß-{SID}/") == SID
for no in ("https://www.tiktok.com/@nasa/video/7706264639297850637", "https://www.tiktok.com/music/ohne-nummer",
           f"https://evil.example/music/x-{SID}", f"https://nottiktok.com/music/x-{SID}", "https://www.tiktok.com/@nasa"):
    assert server.sound_id(no) == "", no
PAGES["https://vm.tiktok.com/ZSound/"] = (f"https://www.tiktok.com/music/x-{SID}?_r=1", b"")
PAGES["https://vm.tiktok.com/ZFoto/"] = ("https://www.tiktok.com/@nasa/photo/123", b"")
PAGES["https://vm.tiktok.com/ZFremd/"] = (f"https://evil.example/music/x-{SID}", b"")
assert server.sound_id("https://vm.tiktok.com/ZSound/") == SID
assert server.is_photo_post("https://vm.tiktok.com/ZFoto/") and not server.is_photo_post("https://vm.tiktok.com/ZSound/")
assert server.sound_id("https://vm.tiktok.com/ZFremd/") == ""           # Weiterleitung auf fremde Seite zählt nicht
assert server.sound_id("https://vm.tiktok.com/ZKaputt/") == ""          # nicht auflösbar → normaler Weg

# ---- Video zum Sound finden ----------------------------------------------------
URL = f"https://www.tiktok.com/embed/music/{SID}"
PAGES[URL] = embed([{"id": "111111", "privateItem": "True", "authorUniqueId": "x"},
                    {"id": "7706264639297850637", "privateItem": "False", "authorUniqueId": "nasa"}])
s = server.sound_lookup(SID)
assert s == {"video": "https://www.tiktok.com/@nasa/video/7706264639297850637", "artist": "NASA",
             "cover": "https://example.com/cover.jpg"}, s
for bad in (embed([]), embed([{"id": "../../etc", "authorUniqueId": "a"}]), ("", b"<html>nix</html>")):
    server.SOUND_CACHE.clear(); PAGES[URL] = bad
    try:
        server.sound_lookup(SID); raise SystemExit("kein Fehler bei " + repr(bad)[:60])
    except server.OptionError as e:
        assert "kein Video gefunden" in str(e)
server.SOUND_CACHE.clear()
PAGES[URL] = embed([{"id": "7706264639297850637", "authorUniqueId": "böse/../x"}], artist="")
assert server.sound_lookup(SID)["video"] == "https://www.tiktok.com/@_/video/7706264639297850637"   # Name nie ungeprüft in die Adresse

# ---- /api/info: Sound und Profil ------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS["download_dir"] = str(d)
    server.LIBRARY_FILE, server.USERS_FILE, server.THUMB_DIR = d / "library.json", d / "users.json", d / "thumbs"
    server.USERS.clear(); server.LIB.clear()
    u = server.new_user("Mama", role="admin", folder="")
    c, h = server.app.test_client(), {"X-Token": u["token"]}
    asked = []

    def fake_info(url, playlist):
        asked.append(url)
        if "instagram.com" in url:
            raise server.OptionError("Unable to extract data")
        if "/video/" in url:
            return {"type": "video", "id": "7706264639297850637", "title": "Beschreibung des Videos", "track": "original sound - NASA",
                    "uploader": "nasa", "thumbnail": "https://example.com/v.jpg", "qualities": [{"height": 720}], "duration": 86}
        return {"type": "playlist", "title": "nasa", "count": 3, "entries": []}
    server.fetch_info = fake_info

    server.SOUND_CACHE.clear(); PAGES[URL] = embed([{"id": "7706264639297850637", "authorUniqueId": "nasa"}])
    r = c.post("/api/info", json={"url": f"https://www.tiktok.com/music/x-{SID}"}, headers=h).get_json()
    assert r["sound"] and r["title"] == "original sound - NASA" and r["uploader"] == "NASA" and r["qualities"] == [], r
    assert r["thumbnail"] == "https://example.com/cover.jpg" and asked[-1].endswith("/video/7706264639297850637"), (r, asked)

    r = c.post("/api/info", json={"url": "https://www.tiktok.com/@nasa"}, headers=h).get_json()
    assert r["type"] == "playlist" and r["profile"] is True, r
    r = c.post("/api/info", json={"url": "https://www.tiktok.com/@nasa/video/7706264639297850637"}, headers=h).get_json()
    assert r["type"] == "video" and r["profile"] is False and "sound" not in r, r
    r = c.post("/api/info", json={"url": "https://www.instagram.com/nasa/"}, headers=h)
    assert r.status_code == 200 and r.get_json()["type"] == "profile" and r.get_json()["title"] == "nasa", r.get_json()
    assert c.post("/api/info", json={"url": "https://www.instagram.com/p/abc/"}, headers=h).status_code == 422

    # Preset „image“ (Mediathek „＋ Link“, Handy-Kurzbefehl) → Modus Bild
    server.enqueue = lambda opts: type("J", (), {"public": lambda self: opts})()
    r = c.get("/api/add?preset=image&url=https://www.tiktok.com/@nasa", headers=h)
    assert r.status_code == 201 and r.get_json()["mode"] == "thumbnail", r.get_json()

print("links ok")
