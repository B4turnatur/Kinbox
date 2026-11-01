"""Abos: Kanal prüfen (yt-dlp hier ein Ersatzskript, kein Netz), „ab jetzt“, Kontingent, Rechte, alte Daten.
Start: python tests/test_subs.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

# Kanal-Startseite → Reiter „Videos“, alles andere bleibt
assert server.sub_url("https://www.youtube.com/@NASA") == "https://www.youtube.com/@NASA/videos"
assert server.sub_url(" https://youtube.com/channel/UC123/?x=1 ") == "https://youtube.com/channel/UC123/videos"
assert server.sub_url("https://www.youtube.com/@NASA/shorts") == "https://www.youtube.com/@NASA/shorts"
assert server.sub_url("https://www.tiktok.com/@nasa") == "https://www.tiktok.com/@nasa"

# Ersatz-yt-dlp: liest die Einträge aus feed.json (neueste zuerst), merkt sich die Argumente
FAKE = r'''
import json, pathlib, sys
d = pathlib.Path(__file__).parent
(d / "args.json").write_text(json.dumps(sys.argv[1:]))
feed = json.loads((d / "feed.json").read_text())
if feed == "fail":
    print("ERROR: [youtube:tab] Kanal gibt es nicht", file=sys.stderr); sys.exit(1)
for e in feed:
    print(json.dumps(e))
'''

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS["download_dir"] = str(d)
    server.SETTINGS["cookies_file"] = ""
    server.SETTINGS["ytdlp_command"] = [sys.executable, str(d / "fake.py")]
    server.LIBRARY_FILE, server.USERS_FILE, server.SUBS_FILE = d / "library.json", d / "users.json", d / "subs.json"
    server.JOBS_FILE = d / "jobs.json"
    server.USERS.clear(); server.LIB.clear(); server.SUBS.clear(); server.JOBS.clear(); server.QUEUE.clear()
    server.sub_check_soon = lambda sid: None       # im Test von Hand prüfen
    (d / "fake.py").write_text(FAKE)
    feed = lambda *ids, **kw: (d / "feed.json").write_text(json.dumps(
        [{"id": i, "url": f"https://www.youtube.com/watch?v={i}", "title": f"Video {i}",
          "playlist_uploader": "Kanal", **kw.get(i, {})} for i in ids]))

    # alte Installation ohne subs.json: lädt leer
    server.subs_load()
    assert server.SUBS == {}
    a = server.new_user("Mama", role="admin", folder="")
    k = server.new_user("Kind")
    o = server.new_user("Oma")
    c = server.app.test_client()
    kid, oma, adm = ({"X-Token": u["token"]} for u in (k, o, a))
    assert c.get("/api/subs", headers=kid).get_json() == []

    # Anlegen: Prüfung über build_args, ungültiges wird abgelehnt
    assert c.post("/api/subs", json={"url": "ftp://x"}, headers=kid).status_code == 400
    assert c.post("/api/subs", json={"url": "https://youtube.com/@x", "preset": "quatsch"}, headers=kid).status_code == 400
    assert c.post("/api/subs", json={"url": "https://youtube.com/@x", "interval_h": 0.1}, headers=kid).status_code == 400
    assert c.post("/api/subs", json={"url": "https://youtube.com/@x", "max_items": 99}, headers=kid).status_code == 400
    r = c.post("/api/subs", json={"url": "https://www.youtube.com/@kanal", "preset": "mp3", "max_items": 2}, headers=kid)
    assert r.status_code == 201, r.get_json()
    s = r.get_json()
    assert s["url"] == "https://www.youtube.com/@kanal/videos" and s["from_now"] and s["seen_count"] == 0
    assert c.post("/api/subs", json={"url": "https://www.youtube.com/@kanal"}, headers=kid).status_code == 400  # doppelt
    sid = s["id"]

    # erste Prüfung „ab jetzt“: nichts laden, alles merken, Name vom Kanal
    feed("c", "b", "a")
    server.sub_check(sid)
    sub = server.SUBS[sid]
    assert sub["seen"] == ["c", "b", "a"] and sub["name"] == "Kanal" and sub["error"] == "" and not server.JOBS, sub
    args = json.loads((d / "args.json").read_text())
    assert "--flat-playlist" in args and args[args.index("--playlist-end") + 1] == "50" and args[-2:] == ["--", sub["url"]]

    # neue Videos → normale Aufträge des Besitzers; mehr als max_items: Rest überspringen; Livestream warten lassen
    feed("f", "live", "e", "d", "c", "b", "a", live={"live_status": "is_upcoming"})
    server.sub_check(sid)
    jobs = sorted(server.JOBS.values(), key=lambda j: j.created)
    assert [j.url[-1] for j in jobs] == ["e", "f"], [j.url for j in jobs]      # älteste zuerst
    j = jobs[0]
    assert j.owner == k["id"] and j.subfolder == "Kanal" and j.options["mode"] == "audio" and j.title == "Video e"
    assert j.options["sub"] == sid and j.status == "queued"
    assert set(sub["seen"]) == {"a", "b", "c", "d", "e", "f"} and sub["last_new"] == 2
    server.build_args(j.options, d)       # Auftrag ist gültig

    # Kontingent voll → Fehler im Abo, Video bleibt offen für später
    server.JOBS.clear()
    feed("g", "f")
    k["quota_gb"] = 0.000001
    p = d / "Kind" / "x.mp4"; p.parent.mkdir(exist_ok=True); p.write_bytes(b"x" * 5000)
    server.LIB["x"] = {"id": "x", "path": str(p), "owner": k["id"], "added": 1}
    server.sub_check(sid)
    assert "Speicher ist voll" in sub["error"] and "g" not in sub["seen"] and not server.JOBS
    k["quota_gb"] = 0
    server.sub_check(sid)
    assert sub["error"] == "" and [j.url[-1] for j in server.JOBS.values()] == ["g"]

    # yt-dlp-Fehler: im Abo gespeichert, kein Absturz, „gesehen“ bleibt
    feed_ok = (d / "feed.json").read_text()
    (d / "feed.json").write_text('"fail"')
    server.sub_check(sid)
    assert sub["error"] == "[youtube:tab] Kanal gibt es nicht" and "g" in sub["seen"] and not sub["checking"]
    (d / "feed.json").write_text(feed_ok)

    # „alles laden“ statt „ab jetzt“: erste Prüfung holt max_items; Playlist (list=) ohne Limit, umgedreht
    server.JOBS.clear()
    r = c.post("/api/subs", json={"url": "https://www.youtube.com/playlist?list=PL1", "from_now": False, "max_items": 2,
                                  "name": "Lieder", "night": True}, headers=oma).get_json()
    feed("1", "2", "3")
    server.sub_check(r["id"])
    assert "--playlist-end" not in json.loads((d / "args.json").read_text())
    jobs = sorted(server.JOBS.values(), key=lambda j: j.created)
    assert [j.url[-1] for j in jobs] == ["2", "3"] and all(j.status == "scheduled" for j in jobs), [j.url for j in jobs]
    assert jobs[0].owner == o["id"] and jobs[0].subfolder == "Lieder"

    # Rechte: fremde Abos gibt es nicht (404), Admin sieht und darf alle
    assert [x["id"] for x in c.get("/api/subs", headers=kid).get_json()] == [sid]
    assert c.delete(f"/api/subs/{r['id']}", headers=kid).status_code == 404
    assert c.post(f"/api/subs/{r['id']}/check", headers=kid).status_code == 404
    assert c.post(f"/api/subs/{sid}/check", headers=kid).status_code == 202
    assert c.get("/api/subs", headers={"X-Token": "falsch"}).status_code == 401
    lst = c.get("/api/subs", headers=adm).get_json()
    assert {x["id"] for x in lst} == {sid, r["id"]} and {x["owner_name"] for x in lst} == {"Kind", "Oma"}
    assert "seen" not in lst[0] and lst[0]["seen_count"]
    assert c.delete(f"/api/subs/{r['id']}", headers=adm).status_code == 200

    # gespeichert und wieder geladen (ohne „läuft gerade“)
    sub["checking"] = True; server.subs_save()
    server.SUBS.clear(); server.subs_load()
    assert list(server.SUBS) == [sid] and server.SUBS[sid]["seen"] == sub["seen"] and not server.SUBS[sid]["checking"]

    # Profil gelöscht → Abo verschwindet bei der nächsten Prüfung
    server.USERS.pop(k["id"])
    server.sub_check(sid)
    assert server.SUBS == {} and json.loads(server.SUBS_FILE.read_text(encoding="utf-8")) == []

print("subs ok")
