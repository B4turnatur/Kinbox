"""Befunde der Code-Prüfung (Server): CORS/Host, PIN-Sperre, Cookies, SSRF, Abbrechen, Bild-Modus, Speichern,
Prozess-Timeouts, Umbenennen, Einstellungen, Profil löschen, Leistung. Start: python tests/test_review_fixes.py
(braucht ffmpeg im PATH)"""
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

FAKE_IMG = r'''
import sys, pathlib
a = sys.argv[1:]
home = next(x[5:] for i, x in enumerate(a) if a[i - 1] == "-P" and x.startswith("home:"))
pathlib.Path(home).mkdir(parents=True, exist_ok=True)
(pathlib.Path(home) / "bild.jpg").write_bytes(b"\xff\xd8\xff bild")
(pathlib.Path(__file__).parent / "lief.txt").write_text("ja")
'''

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    dl = d / "dl"
    server.SETTINGS["download_dir"] = str(dl)
    server.SETTINGS["cookies_file"] = ""
    server.SETTINGS_FILE = d / "settings.json"
    server.LIBRARY_FILE, server.USERS_FILE, server.JOBS_FILE = d / "library.json", d / "users.json", d / "jobs.json"
    server.SUBS_FILE, server.THUMB_DIR = d / "subs.json", d / "thumbs"
    real_thumb = server.thumb_file
    server.thumb_file = lambda e: None
    server.USERS.clear(); server.LIB.clear(); server.JOBS.clear(); server.QUEUE.clear()
    a = server.new_user("Mama", role="admin", folder="")
    k = server.new_user("Kind")
    c = server.app.test_client()
    adm, kid = {"X-Token": a["token"]}, {"X-Token": k["token"]}

    # ---- 1. CORS: nur Erweiterung/Heimnetz, nie für Profile/Anmeldung; Host-Prüfung gegen DNS-Rebinding
    H = lambda origin, **kw: {**kw, "Origin": origin}     # noqa: E731
    r = c.get("/api/ping", headers=H("https://boese.example", **kid))
    assert r.status_code == 200 and "Access-Control-Allow-Origin" not in r.headers
    r = c.get("/api/ping", headers=H("chrome-extension://abc", **kid))
    assert r.headers["Access-Control-Allow-Origin"] == "chrome-extension://abc"
    assert c.get("/api/ping", headers=H("http://192.168.1.5:8765", **kid)).headers["Access-Control-Allow-Origin"] == "http://192.168.1.5:8765"
    assert c.get("/api/ping", headers=H("http://kinbox.invalid", **kid)).headers.get("Access-Control-Allow-Origin")   # Android-Einrichtung
    assert c.options("/api/jobs", headers=H("chrome-extension://abc")).status_code == 204
    r = c.get("/api/profiles", headers=H("chrome-extension://abc"))
    assert r.status_code == 200 and "Access-Control-Allow-Origin" not in r.headers
    assert "Access-Control-Allow-Origin" not in c.post("/api/login", json={"id": k["id"]}, headers=H("http://192.168.1.5")).headers
    for host in ("192.168.1.5:8765", "localhost:8765", "nas:8765", "kinbox.local", "pc.tail1234.ts.net", "[::1]:8765"):
        assert c.get("/api/profiles", headers={"Host": host}).status_code == 200, host
    assert c.get("/api/profiles", headers={"Host": "boese.example"}).status_code == 403
    assert c.post("/api/login", json={"id": k["id"]}, headers={"Host": "boese.example"}).status_code == 403
    assert "token" not in (c.post("/api/login", json={"id": k["id"]}, headers={"Host": "boese.example"}).get_json() or {})
    # Unterwegs-Adresse (DynDNS): mit Token benutzt → gelernt und gespeichert
    assert c.get("/api/profiles", headers={"Host": "heim.dyndns.example"}).status_code == 403
    assert c.get("/api/ping", headers={"Host": "heim.dyndns.example", **kid}).status_code == 200
    assert c.get("/api/profiles", headers={"Host": "heim.dyndns.example"}).status_code == 200
    assert "heim.dyndns.example" in json.loads(server.SETTINGS_FILE.read_text(encoding="utf-8"))["allowed_hosts"]
    server.SETTINGS["allowed_hosts"] = ["mein.example"]
    assert server.host_ok("mein.example:443") and not server.host_ok("dein.example")
    # sendBeacon (Token im Query) geht weiter
    assert c.post(f"/api/library/pos?token={k['token']}", json={"id": "x", "pos": 1}).status_code == 404

    # ---- 4. PIN: Sperre pro Gerät, nicht für alle; jede weitere Sperre länger
    server.set_pin(a, "4711")

    def burst(ip, n):
        out = []

        def guess():
            try:
                out.append(server.check_pin(a, "0000", ip))
            except server.OptionError:
                out.append("gesperrt")
        ts = [threading.Thread(target=guess) for _ in range(n)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        return out
    r = burst("10.0.0.66", 10)
    assert r.count(False) == 8 and r.count("gesperrt") == 2, r
    st = server._pin_fails["ip:10.0.0.66"]
    first = st["until"] - time.time()
    assert 250 < first <= 300, first
    assert server.check_pin(a, "4711", "10.0.0.2")            # Admin am eigenen Gerät kommt rein
    assert server.check_pin(k, "", "10.0.0.66")                # Profil ohne PIN bleibt erreichbar
    st["until"] = 0                                            # Sperre abgelaufen, Angreifer macht weiter
    burst("10.0.0.66", 8)
    assert server._pin_fails["ip:10.0.0.66"]["until"] - time.time() > 550   # doppelt so lang
    assert c.post("/api/login", json={"id": a["id"], "pin": "4711"},
                  environ_base={"REMOTE_ADDR": "10.0.0.66"}).status_code == 429
    assert c.post("/api/login", json={"id": a["id"], "pin": "4711"},
                  environ_base={"REMOTE_ADDR": "10.0.0.3"}).status_code == 200
    server._pin_fails.clear()
    server.set_pin(a, "")

    # ---- 5. Cookies: Admin-Einstellung, private YouTube-Listen nur für den Admin
    ck = d / "cookies.txt"
    ck.write_text("# Netscape HTTP Cookie File\n")
    server.SETTINGS["cookies_file"] = str(ck)
    assert server.cookie_args(d / "c1", "https://youtube.com/watch?v=1", k)[0] == "--cookies"      # Standard: an
    assert c.post("/api/settings", json={"cookies_all_profiles": False}, headers=kid).status_code == 403
    assert c.post("/api/settings", json={"cookies_all_profiles": False}, headers=adm).get_json()["cookies_all"] is False
    assert server.cookie_args(d / "c2", "https://youtube.com/watch?v=1", k) == []
    assert server.cookie_args(d / "c3", "https://youtube.com/watch?v=1", a)[0] == "--cookies"
    assert server.cookie_args(d / "c4", "https://youtube.com/watch?v=1")[0] == "--cookies"         # ohne Profil wie bisher
    for u in ("https://www.youtube.com/feed/history", "https://www.youtube.com/playlist?list=WL",
              "https://youtube.com/playlist?list=LL&x=1"):
        try:
            server.cookie_args(d / "c5", u, k)
            raise AssertionError(u)
        except server.OptionError:
            pass
        server.cookie_args(d / "c6", u, a)                     # Admin darf
        assert c.post("/api/jobs", json={"url": u}, headers=kid).status_code == 400
        assert c.post("/api/info", json={"url": u}, headers=kid).status_code == 403
        assert c.post("/api/subs", json={"url": u}, headers=kid).status_code == 400
    assert c.get("/api/add?url=https://www.youtube.com/feed/history", headers=kid).status_code == 400
    assert not server.PRIVATE_FEED_RE.search("https://www.youtube.com/playlist?list=PLx")
    server.SETTINGS["cookies_all_profiles"] = True
    server.SETTINGS["cookies_file"] = ""
    server.JOBS.clear(); server.QUEUE.clear()

    # ---- 6. SSRF: Vorschaubild nur von öffentlichen http(s)-Adressen, nur echte Bilder
    for u in ("http://127.0.0.1/x.jpg", "http://10.1.2.3/", "http://192.168.0.1/", "http://169.254.169.254/latest",
              "http://[::1]/", "http://[::ffff:127.0.0.1]/", "ftp://8.8.8.8/x", "file:///etc/passwd", "http://localhost/"):
        assert not server.public_http_url(u), u
    assert server.public_http_url("http://8.8.8.8/x.jpg")
    assert not server.fetch_image("http://127.0.0.1:1/x.jpg", d / "x.web")

    # ---- 12. Unterordner: Gerätenamen, Länge, Tiefe
    assert server.safe_subfolder("CON/aux.txt/x") == "_CON/_aux.txt/x"
    assert len(server.safe_subfolder("a" * 300)) == 80
    assert server.safe_subfolder("/".join("abcdefghijk")) == "a/b/c/d/e/f/g/h"
    assert server.safe_subfolder("../Musik/./Rock") == "Musik/Rock"

    # ---- 2./3. Bild-Modus im eigenen Arbeitsordner; Abbrechen ohne laufenden Prozess startet nichts mehr
    (d / "fake.py").write_text(FAKE_IMG)
    server.SETTINGS["ytdlp_command"] = [sys.executable, str(d / "fake.py")]
    dl.mkdir(parents=True, exist_ok=True)
    (dl / "fremd.jpg").write_bytes(b"\xff\xd8\xff fremd")        # Bild eines anderen Auftrags im Zielordner
    job = server.Job({"url": "https://example.com/v", "mode": "thumbnail"}, owner=a["id"])
    job.status = "running"
    server.run_job(job)
    assert job.status == "finished", (job.status, job.error, list(job.log))
    assert [Path(f).name for f in job.files] == ["bild.jpg"] and Path(job.files[0]).parent == dl, job.files
    assert not (dl / ".tmp" / job.id).exists()
    (d / "lief.txt").unlink()
    job = server.Job({"url": "https://example.com/v2"}, owner=a["id"])
    server.kill_job(job)                                        # Abbrechen, bevor ein Prozess lief
    job.status = "running"
    server.run_job(job)
    assert job.status == "cancelled" and not (d / "lief.txt").exists(), job.status
    try:
        server.start_proc(job, [sys.executable, "-c", "pass"])
        raise AssertionError("nach Abbrechen gestartet")
    except server.OptionError:
        pass
    # fertige Teildateien eines abgebrochenen Auftrags kommen in die Mediathek (auch aus dem Arbeitsordner)
    job = server.Job({"url": "https://example.com/pl"}, owner=a["id"])
    (dl / "teil1.mp4").write_bytes(b"1")
    work = dl / ".tmp" / job.id / "out"
    work.mkdir(parents=True)
    (work / "teil2.mp4").write_bytes(b"22")
    job.files = [str(dl / "teil1.mp4"), str(work / "teil2.mp4"), str(dl / "fehlt.mp4")]
    server._cancelled(job, dl)
    assert job.status == "cancelled" and sorted(Path(f).name for f in job.files) == ["teil1.mp4", "teil2.mp4"], job.files
    assert all(server.lib_by_path(f) for f in job.files) and (dl / "teil2.mp4").exists()

    # ---- 9. ffmpeg-Fehler kommen durch (stderr über Datei statt Pipe)
    job = server.Job({"url": "https://example.com/x"}, owner=a["id"])
    try:
        server.run_ffmpeg(job, ["-i", str(d / "gibtsnicht.mp4"), str(d / "o.mp4")], 1, "Test", 0, 100)
        raise AssertionError("ffmpeg-Fehler verschluckt")
    except server.OptionError as e:
        assert str(e).startswith("ffmpeg-Fehler") and any("gibtsnicht" in l for l in job.log), (e, list(job.log))

    # ---- 10. run_tool: Zeitüberschreitung beendet auch Enkelprozesse (hielten sonst die Pipes offen)
    t0 = time.time()
    try:
        server.run_tool([sys.executable, "-c", "import subprocess,sys,time;"
                         "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);time.sleep(60)"], timeout=1)
        raise AssertionError("keine Zeitüberschreitung")
    except subprocess.TimeoutExpired:
        pass
    assert time.time() - t0 < 20, time.time() - t0
    r = server.run_tool([sys.executable, "-c", "print('hallo')"], timeout=30)
    assert r.returncode == 0 and r.stdout.strip() == b"hallo"

    # ---- 20. /api/ping wartet nicht auf yt-dlp
    (d / "slow.py").write_text("import time; time.sleep(5); print('2099.01.01')")
    server.SETTINGS["ytdlp_command"] = [sys.executable, str(d / "slow.py")]
    server._version_cache.clear()
    t0 = time.time()
    assert c.get("/api/ping", headers=adm).get_json()["ytdlp"] == "…"
    assert time.time() - t0 < 3, time.time() - t0
    assert server.ytdlp_version(wait=True) == "2099.01.01"
    calls = []
    server._tool_cache.clear()
    real_js = server.js_runtime
    server.js_runtime = lambda: calls.append(1) or "deno"
    c.get("/api/ping", headers=adm); c.get("/api/ping", headers=adm)
    assert len(calls) == 1
    c.post("/api/settings", json={"max_parallel": 2}, headers=adm)          # Einstellung geändert → neu prüfen
    assert len(calls) == 2
    server.js_runtime = real_js

    # ---- 11. Umbenennen nimmt Untertitel, .info.json und .description mit
    vid = dl / "Video.mp4"
    vid.write_bytes(b"v")
    for n in ("Video.de.srt", "Video.en.vtt", "Video.info.json", "Video.description", "Video.2.mp4"):
        (dl / n).write_text(n)
    server.LIB["r1"] = {"id": "r1", "path": str(vid), "name": vid.name, "owner": a["id"], "added": 1, "kind": "video", "size": 1}
    r = c.post("/api/library/r1/rename", json={"title": "Neu", "file": True}, headers=adm).get_json()
    assert r["name"] == "Neu.mp4"
    names = {p.name for p in dl.iterdir()}
    assert {"Neu.mp4", "Neu.de.srt", "Neu.en.vtt", "Neu.info.json", "Neu.description", "Video.2.mp4"} <= names, names
    assert not {"Video.de.srt", "Video.info.json", "Video.mp4"} & names
    assert server.lib_by_path(str(dl / "Neu.mp4"))["id"] == "r1" and server.lib_by_path(str(vid)) is None   # 19. Index

    # ---- 13. Einstellungen/Abos: falsche Typen → 400 statt 500, leeres Nachtfenster abgelehnt
    assert c.post("/api/settings", json={"night": {"start": "02:00", "end": "02:00"}}, headers=adm).status_code == 400
    assert c.post("/api/settings", json={"download_dir": 5}, headers=adm).status_code == 400
    assert c.post("/api/settings", json={"download_dir": ["x"]}, headers=adm).status_code == 400
    assert c.post("/api/settings", json={"night": "nachts"}, headers=adm).status_code == 400
    assert c.post("/api/subs", json=["x"], headers=kid).status_code == 400
    assert c.post("/api/settings", json={"night": {"start": "23:00", "end": "05:00"}}, headers=adm).status_code == 200

    # ---- 7. subs.json: atomar, kaputte Datei bleibt als Kopie, kaputte Einträge einzeln übersprungen
    server.SUBS.clear()
    server.SUBS_FILE.write_text("[{kaputt", encoding="utf-8")
    server.subs_load()
    assert server.SUBS == {} and (d / "subs.json.kaputt").read_text(encoding="utf-8") == "[{kaputt"
    server.SUBS_FILE.write_text(json.dumps([{"id": "s1", "owner": k["id"], "url": "https://youtube.com/@x/videos",
                                             "preset": "best", "interval_h": 6, "max_items": 5, "created": 1},
                                            {"id": "s2", "url": 5}, "Müll", {"id": "s3", "url": "https://x", "preset": "quatsch"}]),
                               encoding="utf-8")
    server.subs_load()
    assert list(server.SUBS) == ["s1"] and server.SUBS["s1"]["checking"] is False
    server.subs_save()
    assert json.loads(server.SUBS_FILE.read_text(encoding="utf-8"))[0]["id"] == "s1" and not list(d.glob("*.tmp"))
    server.SUBS.clear()

    # ---- 8. jobs.json/JOBS: wartende nie kürzen, fertige auf keep_history
    server.JOBS.clear()
    keep = server.SETTINGS["keep_history"]
    server.SETTINGS["keep_history"] = 2
    for i, st in enumerate(["queued", "scheduled", "finished", "error", "cancelled", "finished"]):
        j = server.Job({"url": f"https://example.com/{i}"}, owner=a["id"])
        j.status, j.created = st, 100 + i
        server.JOBS[j.id] = j
    server.save_jobs()
    on_disk = json.loads(server.JOBS_FILE.read_text(encoding="utf-8"))
    assert sorted(j["status"] for j in on_disk) == ["cancelled", "finished", "queued", "scheduled"], on_disk
    assert len(server.JOBS) == 4
    server.SETTINGS["keep_history"] = keep
    server.JOBS.clear()

    # ---- 16. Auftragsliste: alte fertige Aufträge ohne stat bei jedem Abruf; to_disk ohne public()
    j = server.Job({"url": "https://example.com/alt"}, owner=a["id"])
    j.status, j.finished, j.files = "finished", time.time() - 3600, [str(dl / "Neu.mp4")]
    server.JOBS[j.id] = j
    stats = []
    real_size = server._size
    server._size = lambda f: stats.append(f) or real_size(f)
    c.get("/api/jobs", headers=adm); c.get("/api/jobs", headers=adm); j.to_disk()
    assert len(stats) == 1, stats
    j.status, j.finished = "running", None
    c.get("/api/jobs", headers=adm); c.get("/api/jobs", headers=adm)
    assert len(stats) == 3, stats                              # laufend: immer frisch
    server._size = real_size
    server.JOBS.clear()

    # ---- 14. Profil löschen: laufender Auftrag wird abgebrochen und darf noch fertig werden; Dateien → Admin
    o = server.new_user("Oma")
    oj = server.Job({"url": "https://example.com/oma"}, owner=o["id"])
    oj.status = "running"
    server.JOBS[oj.id] = oj
    late = dl / "Oma" / "spaet.mp4"
    late.parent.mkdir(parents=True, exist_ok=True)
    late.write_bytes(b"123")

    def worker():                  # tut so, als liefe yt-dlp und würde beim Abbrechen Fertiges übernehmen
        while not oj.cancel_requested:
            time.sleep(0.05)
        time.sleep(0.3)
        oj.files = [str(late)]
        server._cancelled(oj, late.parent)
    threading.Thread(target=worker).start()
    assert c.delete(f"/api/users/{o['id']}", headers=adm).status_code == 200
    e = server.lib_by_path(str(late))
    assert e and e["owner"] == a["id"], e
    ghost = server.Job({"url": "https://example.com/g"}, owner="gibtsnicht")
    late2 = dl / "spaet2.mp4"
    late2.write_bytes(b"1")
    assert server.lib_add(str(late2), {}, ghost)["owner"] == a["id"]     # Besitzer weg → Admin

    # ---- 17. /api/library und /api/users: gespeicherte Größe, kein Ordner anlegen pro Eintrag
    server.LIB.clear()
    z = server.new_user("Zoe")
    zroot = server.user_root(z, create=False)
    f1 = dl / "a.mp4"
    f1.write_bytes(b"x" * 10)
    server.LIB["l1"] = {"id": "l1", "path": str(f1), "name": "a.mp4", "owner": z["id"], "added": 1, "kind": "video", "size": 1000, "shared": True}
    server.LIB["l2"] = {"id": "l2", "path": str(dl / "weg.mp4"), "name": "weg.mp4", "owner": z["id"], "added": 2, "kind": "video", "size": 5}
    lst = c.get("/api/library?scope=all", headers=adm).get_json()
    assert [i["id"] for i in lst["items"]] == ["l1"] and lst["family_count"] == 1
    assert not zroot.exists(), "Mediathek-Liste hat einen Ordner angelegt"
    zl = c.get("/api/library", headers={"X-Token": z["token"]}).get_json()
    assert zl["stats"] == {"count": 1, "size": 1000} and zl["usage"] == 1000, zl["stats"]
    users = {u["id"]: u for u in c.get("/api/users", headers=adm).get_json()}
    assert users[z["id"]]["files"] == 2 and users[z["id"]]["usage"] == 1005

    # ---- 22. Aufräumer: Existenzprüfung abschaltbar; verwaiste Vorschaubilder werden mit gelöscht
    server.THUMB_DIR.mkdir(parents=True, exist_ok=True)
    (server.THUMB_DIR / "l2.jpg").write_bytes(b"x")
    server.janitor_once(prune=False)
    assert "l2" in server.LIB
    server.janitor_once()
    assert "l2" not in server.LIB and not (server.THUMB_DIR / "l2.jpg").exists()

    # ---- 18. library.json wird entprellt gespeichert, flush_all schreibt sofort
    server.LIBRARY_FILE.unlink(missing_ok=True)
    server.LIB["l3"] = {"id": "l3", "path": str(f1), "name": "a.mp4", "owner": z["id"], "added": 3, "kind": "video", "size": 1}
    server.lib_save_soon()
    assert not server.LIBRARY_FILE.exists()
    server.flush_all()
    assert "l3" in {e["id"] for e in json.loads(server.LIBRARY_FILE.read_text(encoding="utf-8"))["entries"]}
    server.LIB.pop("l3")
    server.lib_save_soon()
    for _ in range(50):
        if "l3" not in server.LIBRARY_FILE.read_text(encoding="utf-8"):
            break
        time.sleep(0.1)
    else:
        raise AssertionError("library.json nicht entprellt gespeichert")

    # ---- 21. Vorschaubild auch für Bilder und GIFs
    server.thumb_file = real_thumb
    ff = server.ffmpeg_bin("ffmpeg")
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "color=red:size=1200x600", "-frames:v", "1", str(d / "gross.png")], check=True)
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=5:duration=1", str(d / "anim.gif")], check=True)
    for eid, p, kind in (("img", d / "gross.png", "image"), ("gif", d / "anim.gif", "gif")):
        t = server.thumb_file({"id": eid, "kind": kind, "path": str(p), "thumbnail": ""})
        w = subprocess.run([server.ffmpeg_bin("ffprobe"), "-v", "error", "-show_entries", "stream=width", "-of", "csv=p=0", str(t)],
                           capture_output=True, text=True).stdout.strip()
        assert w == "480", (eid, w)
    # privates Vorschaubild wird nicht geladen, das Bild aus der Datei kommt trotzdem
    t = server.thumb_file({"id": "priv", "kind": "image", "path": str(d / "gross.png"), "thumbnail": "http://127.0.0.1:9/x.jpg"})
    assert t and not list(server.THUMB_DIR.glob("*.web"))
    # alte .none-Markierung von Bildern wird einmalig entfernt, die von Videos bleibt
    server.LIB["oldimg"] = {"id": "oldimg", "path": str(d / "gross.png"), "kind": "image", "owner": a["id"], "added": 1}
    server.LIB["oldvid"] = {"id": "oldvid", "path": str(f1), "kind": "video", "owner": a["id"], "added": 1}
    for n in ("oldimg", "oldvid"):
        (server.THUMB_DIR / f"{n}.none").touch()
    server.thumbs_migrate()
    assert not (server.THUMB_DIR / "oldimg.none").exists() and (server.THUMB_DIR / "oldvid.none").exists()
    (server.THUMB_DIR / "oldimg.none").touch()
    server.thumbs_migrate()                                    # nur einmal
    assert (server.THUMB_DIR / "oldimg.none").exists()
    server.LIB.pop("oldimg"); server.LIB.pop("oldvid")

    # ---- 15. Doppelter Start: belegter Port wird erkannt
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(16)
    port = srv.getsockname()[1]
    assert server.already_running("0.0.0.0", port) and server.already_running("127.0.0.1", port)
    srv.close()
    assert not server.already_running("0.0.0.0", port)

    server.lib_save()          # ausstehendes Speichern erledigen, bevor der Testordner gelöscht wird
    time.sleep(0.5)

print("review fixes ok")
