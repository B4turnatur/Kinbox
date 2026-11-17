"""Selbstheilung: automatisch wiederholen, Fehler einordnen, Teil-Erfolg, Fortsetzen nach Neustart, Foto-Beitrag
in der Vorschau erkennen. yt-dlp/gallery-dl sind hier Ersatzskripte (kein Netz).
Start: python tests/test_retry.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

K = server.error_kind
assert K("[tiktok] 1: Unsupported URL: https://x") == "novideo" and K("There is no video in this post") == "novideo"
assert K("Sign in to confirm you're not a bot. Use --cookies") == "login" and K("Private video") == "login"
assert K("Video unavailable. This video has been removed") == "gone" and K("HTTP Error 404: Not Found") == "gone"
assert K("Unable to extract data; please report this issue on https://github.com/yt-dlp") == "extractor"
assert K("unable to download video data: HTTP Error 403: Forbidden") == "extractor"
assert K("HTTP Error 429: Too Many Requests") == "rate" and K("[Errno 28] No space left on device") == "disk"
assert K("Unable to download webpage: <urlopen error timed out>") == "network" and K("Read timed out.") == "network"
assert K("Postprocessing: ffmpeg not found") == "post" and K("irgendwas") == "unknown" and K("") == "unknown"
assert server.explain("Private video").startswith("Privat oder nur mit Anmeldung") and server.explain("x") == "x"
assert server.explain("") == ""

# Ersatz-yt-dlp: zählt seine Aufrufe und verhält sich je nach Plan in plan.json
FAKE = r'''
import json, sys, pathlib
here = pathlib.Path(__file__).parent
plan = json.loads((here / "plan.json").read_text())
n = int((here / "n").read_text()) + 1 if (here / "n").exists() else 1
(here / "n").write_text(str(n))
if "-U" in sys.argv or "--version" in sys.argv:
    print("1"); sys.exit(0)
home = next(a[5:] for a in sys.argv if a.startswith("home:"))
step = plan[min(n, len(plan)) - 1]
for name in step.get("files", []):
    f = pathlib.Path(home) / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b"x")
    print("@@I" + json.dumps({"title": name}))
    print("@@F" + json.dumps(str(f)))
if step.get("slideshow"):      # TikTok-Fotos hinter /video/-Link: nur Ton, der Server muss hier abbrechen
    import time
    print("@@I" + json.dumps({"title": "Urlaub", "vcodec": "none", "webpage_url": "https://www.tiktok.com/@a/video/123"}), flush=True)
    time.sleep(30)
for e in step.get("errors", []):
    print("ERROR: " + e)
sys.exit(step.get("rc", 0))
'''


def run(d: Path, plan: list, **opts):
    (d / "plan.json").write_text(json.dumps(plan))
    (d / "n").unlink(missing_ok=True)
    job = server.Job({"url": "https://example.com/v/1", "mode": "video", **opts}, owner="u1")
    job.status = "running"
    server.run_job(job)
    assert (d / "n").exists(), (job.status, job.error, list(job.log)[-3:])
    return job, int((d / "n").read_text())


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS.update(download_dir=str(d / "dl"), ytdlp_command=[sys.executable, str(d / "fake.py")],
                           auto_retry=2, auto_update_ytdlp=False, cookies_file="")
    server.LIBRARY_FILE, server.USERS_FILE, server.THUMB_DIR = d / "library.json", d / "users.json", d / "thumbs"
    server.USERS.clear(); server.LIB.clear()
    server.USERS["u1"] = {**server.new_user("Mama", role="admin", folder=""), "id": "u1"}
    server.RETRY_WAITS = (0.1,)
    server.thumb_file = lambda e: None
    (d / "fake.py").write_text(FAKE)

    # Netzfehler → zweiter Versuch klappt, kein Fehler bleibt stehen
    job, n = run(d, [{"rc": 1, "errors": ["Unable to download webpage: timed out"]}, {"files": ["a.mp4"]}])
    assert (job.status, job.error, n) == ("finished", "", 2), (job.status, job.error, n)
    assert any("Neuer Versuch (2/3)" in l for l in job.log) and len(server.LIB) == 1

    # endgültiger Fehler (privat) → kein zweiter Versuch, verständlicher Text
    job, n = run(d, [{"rc": 1, "errors": ["Private video. Sign in if you've been granted access"]}])
    assert (job.status, n) == ("error", 1) and job.error.startswith("Privat oder nur mit Anmeldung"), (job.error, n)

    # immer wieder Netzfehler → nach 3 Versuchen Schluss
    job, n = run(d, [{"rc": 1, "errors": ["Connection reset by peer"]}])
    assert (job.status, n) == ("error", 3) and job.error.startswith("Keine Verbindung zur Seite ("), (job.error, n)

    # auto_retry = 0 → wie früher genau ein Versuch
    server.SETTINGS["auto_retry"] = 0
    job, n = run(d, [{"rc": 1, "errors": ["Connection reset by peer"]}])
    assert (job.status, n) == ("error", 1), n
    server.SETTINGS["auto_retry"] = 2

    # Playlist: ein Video gelöscht, zwei geladen → fertig mit Hinweis, beide in der Mediathek (früher: Fehler, nichts)
    before = len(server.LIB)
    job, n = run(d, [{"rc": 1, "files": ["p/1.mp4", "p/2.mp4"], "errors": ["[youtube] x: Video unavailable"]}], playlist="all")
    assert (job.status, n) == ("finished", 1) and len(server.LIB) == before + 2, (job.status, job.error, n)
    assert job.error.startswith("Fertig, aber nicht alles hat geklappt (1×): Nicht (mehr) verfügbar"), job.error

    # „Seite geändert“ → yt-dlp wird einmal aktualisiert (hier: Ersatzskript mit -U), dann neuer Versuch
    server.SETTINGS["auto_update_ytdlp"] = True
    job, n = run(d, [{"rc": 1, "errors": ["Unable to extract x; please report this issue on https://github.com/yt-dlp"]},
                     {"rc": 0}, {"rc": 0}, {"rc": 0}, {"files": ["u.mp4"]}])
    assert job.status == "finished" and "--- yt-dlp aktualisiert ---" not in job.log, (job.status, job.error)
    assert n == 5 and server._auto_update_at > 0, n          # 1 Lauf + Version + -U + Version + 2. Lauf
    assert not server.ytdlp_autoupdate()                     # höchstens alle 12 Stunden
    server.SETTINGS["auto_update_ytdlp"] = False

    # Abbrechen während der Wartezeit
    server.RETRY_WAITS = (30,)
    (d / "plan.json").write_text(json.dumps([{"rc": 1, "errors": ["Connection reset by peer"]}]))
    job = server.Job({"url": "https://example.com/v/2", "mode": "video"}, owner="u1")
    import threading
    th = threading.Thread(target=server.run_job, args=(job,))
    th.start()
    for _ in range(200):
        if job.stage.startswith("Neuer Versuch"):
            break
        th.join(0.05)
    server.kill_job(job)
    th.join(5)
    assert not th.is_alive() and job.status == "cancelled", (job.status, job.stage)
    server.RETRY_WAITS = (0.1,)

    # TikTok-Slideshow im Audio-Modus → nur die Musik
    GDL = r'''
import json, sys, pathlib
if "-j" in sys.argv:
    meta = {"desc": "Urlaub", "author": {"nickname": "Oma"}}
    print(json.dumps([[2, meta], [3, "https://cdn.example/1.jpg", {**meta, "extension": "jpg"}],
                      [3, "https://cdn.example/2.jpg", {**meta, "extension": "jpg"}],
                      [3, "ytdl:https://x", {**meta, "extension": "mp3"}]]))
    sys.exit(0)
out = pathlib.Path(sys.argv[sys.argv.index("-D") + 1]); out.mkdir(parents=True)
(pathlib.Path(__file__).parent / "gdl_url").write_text(sys.argv[-1])
for name in ("1.jpg", "2.jpg", "1.mp3"):
    (out / name).write_bytes(b"x"); (out / (name + ".json")).write_text(json.dumps({"desc": "Urlaub"})); print(out / name)
'''
    (d / "gdl.py").write_text(GDL)
    server.gallerydl_base = lambda: [sys.executable, str(d / "gdl.py")]
    server.ensure_gallerydl = lambda: None
    job = server.Job({"url": "https://www.tiktok.com/@a/photo/123", "mode": "audio"}, owner="u1")
    server.run_job(job)
    assert job.status == "finished" and [Path(f).name for f in job.files] == ["Urlaub.mp3"], (job.status, job.error, job.files)

    # Slideshow hinter einem /video/-Link: yt-dlp sähe nur die Musik → abbrechen und die Bilder laden
    import time
    t0 = time.time()
    job, n = run(d, [{"slideshow": True}], url="https://www.tiktok.com/@a/video/123")
    assert job.status == "finished" and time.time() - t0 < 15, (job.status, job.error, time.time() - t0)
    assert sorted(Path(f).suffix for f in job.files) == [".jpg", ".jpg", ".mp3"] and n == 1, job.files
    assert (d / "gdl_url").read_text() == "https://www.tiktok.com/@a/photo/123"
    # … aber nicht, wenn ein ganzes Profil geladen wird (ein Beitrag darf nicht den ganzen Auftrag umlenken)
    job, n = run(d, [{"files": ["x.mp4"]}], url="https://www.tiktok.com/@a", playlist="all")
    assert job.status == "finished" and not job.slideshow

    # Vorschau: Foto-Beitrag wird als solcher erkannt (statt Fehlermeldung)
    ph = server.photo_info("https://www.tiktok.com/@a/photo/123")
    assert ph == {"type": "photos", "title": "Urlaub", "uploader": "Oma", "count": 2, "audio": True,
                  "webpage_url": "https://www.tiktok.com/@a/photo/123", "thumbnail": "https://cdn.example/1.jpg"}, ph
    (d / "gdl.py").write_text('print("[]")')
    assert server.photo_info("https://www.instagram.com/p/x/") is None

    # Neustart mitten im Download: einmal von selbst wieder einreihen, beim zweiten Mal Fehler
    j = server.Job.from_disk({"id": "abc", "url": "https://example.com/v/3", "status": "running", "options": {"url": "https://example.com/v/3"}})
    assert (j.status, j.resumed, j.stage) == ("queued", 1, "Wartet"), (j.status, j.resumed)
    j = server.Job.from_disk({**j.to_disk(), "status": "running"})
    assert (j.status, j.error) == ("error", "Server wurde neu gestartet"), j.status
    j = server.Job.from_disk({"id": "old", "url": "https://example.com/v/4", "status": "finished"})   # alte jobs.json ohne Feld
    assert j.resumed == 0 and j.status == "finished"

print("OK")
