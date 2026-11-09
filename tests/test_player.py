"""Player: Kapitel, Untertitel (eingebettet + Datei daneben), Weiterschauen pro Person. Start: python tests/test_player.py
Braucht ffmpeg/ffprobe im PATH."""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

SRT = "1\n00:00:00,500 --> 00:00:01,500\n{}\n"

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS["download_dir"] = str(d)
    server.LIBRARY_FILE, server.USERS_FILE, server.THUMB_DIR = d / "library.json", d / "users.json", d / "thumbs"
    server.USERS.clear(); server.LIB.clear()
    a = server.new_user("Mama", role="admin", folder="")
    k = server.new_user("Kind")
    o = server.new_user("Opa")

    # Testvideo: 6 s, 2 Kapitel, 1 eingebettete Untertitel-Spur (eng) + „film.de.srt“ daneben
    (d / "in.srt").write_text(SRT.format("Hello inside"), "utf-8")
    (d / "meta.txt").write_text(";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1\nSTART=0\nEND=3\ntitle=Anfang\n"
                                "[CHAPTER]\nTIMEBASE=1/1\nSTART=3\nEND=6\ntitle=Schluss\n", "utf-8")
    film = d / "film.mkv"
    r = subprocess.run([server.ffmpeg_bin("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=d=6:s=160x120:r=10",
                        "-i", str(d / "in.srt"), "-i", str(d / "meta.txt"), "-map", "0:v", "-map", "1:s", "-map_metadata", "2",
                        "-map_chapters", "2", "-c:v", "libx264", "-preset", "ultrafast", "-c:s", "srt",
                        "-metadata:s:s:0", "language=eng", str(film)], capture_output=True)
    assert film.exists(), r.stderr.decode("utf-8", "replace")
    (d / "film.de.srt").write_text(SRT.format("Hallo daneben"), "utf-8")
    (d / "filmriss.srt").write_text(SRT.format("gehört zu einer anderen Datei"), "utf-8")
    plain = d / "plain.mp4"
    subprocess.run([server.ffmpeg_bin("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=d=1:s=160x120:r=10",
                    "-c:v", "libx264", "-preset", "ultrafast", str(plain)], capture_output=True)

    def entry(eid, path, owner, shared=False):
        server.LIB[eid] = {"id": eid, "path": str(path), "name": path.name, "title": eid, "owner": owner, "shared": shared,
                           "added": 1, "size": 1, "kind": "video"}
    entry("film", film, k["id"]); entry("plain", plain, k["id"]); entry("fam", plain, a["id"], shared=True)
    entry("priv", plain, o["id"])
    c = server.app.test_client()
    kid, opa = {"X-Token": k["token"]}, {"X-Token": o["token"]}

    # Kapitel + Untertitel
    x = c.get("/api/library/film/extras", headers=kid).get_json()
    assert [(ch["title"], ch["start"]) for ch in x["chapters"]] == [("Anfang", 0), ("Schluss", 3)], x
    assert [s["lang"] for s in x["subs"]] == ["eng", "de"], x
    assert all("src" not in s for s in x["subs"]), x                     # keine Dateinamen nach außen
    x = c.get("/api/library/plain/extras", headers=kid).get_json()
    assert x == {"chapters": [], "subs": []}, x

    r = c.get("/api/library/film/subs/0", headers=kid)
    assert r.status_code == 200 and r.mimetype == "text/vtt" and r.data.startswith(b"WEBVTT") and b"Hello inside" in r.data, r.data
    r = c.get("/api/library/film/subs/1", headers=kid)
    assert r.status_code == 200 and "Hallo daneben" in r.data.decode("utf-8"), r.data
    assert c.get("/api/library/film/subs/2", headers=kid).status_code == 404
    assert c.get("/api/library/plain/subs/0", headers=kid).status_code == 404

    # Fremde private Datei: nichts sichtbar
    assert c.get("/api/library/film/extras", headers=opa).status_code == 404
    assert c.get("/api/library/film/subs/0", headers=opa).status_code == 404

    # Weiterschauen: pro Person, auch für geteilte Dateien, nicht für fremde private
    assert c.post("/api/library/pos", json={"id": "film", "pos": 42.7}, headers=kid).status_code == 200
    assert c.post("/api/library/pos", json={"id": "fam", "pos": 7}, headers=kid).status_code == 200
    assert c.post("/api/library/pos", json={"id": "priv", "pos": 7}, headers=kid).status_code == 404
    assert c.post("/api/library/pos", json={"id": "nix", "pos": 7}, headers=kid).status_code == 404
    for bad in ({"id": "film", "pos": "9"}, {"id": "film", "pos": -1}, {"id": "film", "pos": True}, {"id": 5, "pos": 1},
                {"id": "film"}, {"id": "film", "pos": 1e9}, [1]):
        assert c.post("/api/library/pos", json=bad, headers=kid).status_code == 400, bad
    assert c.post("/api/library/pos", data='{"id": "film", "pos": NaN}', content_type="application/json",
                  headers=kid).status_code == 400
    assert c.get("/api/library", headers=kid).get_json()["pos"] == {"film": 42, "fam": 7}
    assert c.get("/api/library", headers=opa).get_json()["pos"] == {}          # andere Person: eigener Stand
    assert c.post("/api/library/pos", json={"id": "film", "pos": 0}, headers=kid).status_code == 200
    assert c.get("/api/library", headers=kid).get_json()["pos"] == {"fam": 7}
    assert "pos" not in c.get("/api/me", headers=kid).get_json()

    # Obergrenze: älteste fallen raus, zuletzt Gesehenes bleibt
    with server.USERS_LOCK:
        server.USERS[k["id"]]["pos"] = {f"alt{i}": 1 for i in range(server.POS_MAX)}
    c.post("/api/library/pos", json={"id": "fam", "pos": 9}, headers=kid)
    p = server.USERS[k["id"]]["pos"]
    assert len(p) == server.POS_MAX and "alt0" not in p and p["fam"] == 9 and list(p)[-1] == "fam", len(p)

print("test_player ok")
