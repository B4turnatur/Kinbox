"""Härtung: Pfade, Eingabeprüfung, PIN-Sperre, kaputte JSON-Dateien. Start: python tests/test_hardening.py"""
import json
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402


def rejected(opts):
    try:
        server.build_args(opts, Path("."))
    except server.OptionError:
        return True
    return False


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS["download_dir"] = str(d / "dl")
    server.SETTINGS_FILE = d / "settings.json"
    server.LIBRARY_FILE, server.USERS_FILE, server.JOBS_FILE = d / "library.json", d / "users.json", d / "jobs.json"
    server.THUMB_DIR = d / "thumbs"
    server.thumb_file = lambda e: None
    U = "https://example.com/v"

    # ---- Dateinamen-Vorlage: nichts darf aus dem Download-Ordner heraus (yt-dlp: Typ-Präfix, ~, $VAR, %VAR%)
    for t in ("thumbnail:/tmp/x.%(ext)s", "default:C:/x/%(title)s", "~/x.%(ext)s", "$HOME/x.%(ext)s",
              "%USERPROFILE%/x.%(ext)s", "%(title)s/%APPDATA%/x", "C:/x.%(ext)s", "/x.%(ext)s", "../x.%(ext)s"):
        assert rejected({"url": U, "filenameTemplate": t}), t
    for t in ("%(title)s [%(id)s].%(ext)s", "%(upload_date>%Y%m%d)s %(title)s.%(ext)s", "Musik/%(title)s.%(ext)s"):
        assert not rejected({"url": U, "filenameTemplate": t}), t
    assert not rejected({"url": U, "organize": "plex"})          # eigene Vorlage mit %m%d bleibt erlaubt

    # ---- falsche Typen → OptionError statt Absturz
    for o in ({"url": U, "trim": 5}, {"url": U, "mode": "audio", "audioFormat": ["mp3"]}, {"url": U, "subs": "x"},
              {"url": U, "concurrentFragments": "viele"}, {"url": U, "subfolder": 5}, {"url": ["x"]}, [1, 2]):
        assert rejected(o), o

    # ---- Dateinamen: Windows-Gerätenamen
    assert server.safe_name("CON", 60, "x") == "_CON" and server.safe_name("nul.txt", 60, "x") == "_nul.txt"
    assert server.safe_name(" ../a:b. ", 60, "x") == "_a_b" and server.safe_name("...", 60, "Foto") == "Foto"
    assert server.folder_name("Lpt1") == "_Lpt1"

    # ---- users.json: fehlende Felder ergänzen, Müll überspringen, kaputte Datei nicht überschreiben
    server.USERS.clear()
    server.USERS_FILE.write_text(json.dumps([{"id": "a1", "name": "Mama", "role": "admin", "token": "tok-a"},
                                             {"id": "k1", "name": "Kind"}, "Müll", {"name": "ohne id"}]),
                                 encoding="utf-8")
    server.users_load()
    assert set(server.USERS) == {"a1", "k1"}
    k = server.USERS["k1"]
    assert k["token"] and k["role"] == "member" and k["folder"] == "k1" and server.USERS["a1"]["folder"] == ""
    server.USERS_FILE.write_text("[{kaputt", encoding="utf-8")
    try:
        server.users_load()
        raise AssertionError("kaputte users.json muss den Start abbrechen")
    except SystemExit:
        pass
    assert server.USERS_FILE.read_text(encoding="utf-8") == "[{kaputt"
    server.users_save()
    assert json.loads(server.USERS_FILE.read_text(encoding="utf-8"))[0]["id"] == "a1"
    assert not list(d.glob("*.tmp")), "tmp-Datei liegen geblieben"

    c = server.app.test_client()
    adm, kid = {"X-Token": "tok-a"}, {"X-Token": k["token"]}

    # ---- Token mit Umlaut: 401 statt 500
    assert c.get("/api/me", headers={"X-Token": "tök"}).status_code == 401

    # ---- kaputte Anfragen: 400 statt 500
    assert c.post("/api/jobs", json=[1, 2], headers=kid).status_code == 400
    assert c.post("/api/jobs", json={"url": U, "subfolder": {"a": 1}}, headers=kid).status_code == 400
    assert c.post("/api/login", json=["a1"]).status_code == 404
    assert c.post("/api/info", json={"url": 5}, headers=kid).status_code == 400
    assert c.post("/api/settings", json={"max_parallel": "x"}, headers=adm).status_code == 400

    # ---- /api/add: Preset wird in der HTML-Antwort maskiert
    r = c.get(f"/api/add?url={U}&preset=<script>alert(1)</script>", headers={**kid, "Accept": "text/html"})
    assert r.status_code == 200 and b"<script>" not in r.data and b"&lt;script&gt;" in r.data

    # ---- PIN: parallele Fehlversuche umgehen die Sperre nicht
    server.set_pin(k, "4711")
    tries = []

    def guess():
        try:
            tries.append(server.check_pin(k, "0000"))
        except server.OptionError:
            pass
    ts = [threading.Thread(target=guess) for _ in range(24)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(tries) == 8 and not any(tries), len(tries)
    server._pin_fails.clear()

    # ---- Wiederholen respektiert das Kontingent
    (d / "dl").mkdir(exist_ok=True)
    big = d / "dl" / "gross.mp4"
    big.write_bytes(b"x" * 2048)
    server.LIB.clear()
    server.LIB["e1"] = {"id": "e1", "path": str(big), "name": big.name, "owner": "k1", "added": 1, "kind": "video"}
    old = server.Job({"url": U}, owner="k1")
    old.status = "error"
    server.JOBS[old.id] = old
    k["quota_gb"] = 1 / 1024 ** 3      # 1 Byte
    assert c.post(f"/api/jobs/{old.id}/retry", headers=kid).status_code == 400
    k["quota_gb"] = 0
    assert c.post(f"/api/jobs/{old.id}/retry", headers=kid).status_code == 201

    # ---- Bearbeiten mit falschem Typ: 400
    assert c.post("/api/library/e1/edit", json={"op": ["cut"]}, headers=kid).status_code == 400

    # ---- Umbenennen zu Gerätenamen bleibt eine echte Datei im selben Ordner
    r = c.post("/api/library/e1/rename", json={"title": "NUL", "file": True}, headers=kid).get_json()
    assert r["name"] == "_NUL.mp4" and (d / "dl" / "_NUL.mp4").exists(), r

    # ---- library.json: Platte weg → Einträge behalten; kaputte Datei → Sicherungskopie
    server.LIB.clear()
    server.LIBRARY_FILE.write_text(json.dumps({"entries": [
        {"id": "x1", "path": str(d / "offline" / "a.mp4"), "owner": "k1"},
        {"id": "x2", "path": str(d / "offline" / "b.mp4"), "owner": "k1", "added": "kaputt"},
        {"path": "ohne id"}, 7], "cleanup_log": ["Müll"]}), encoding="utf-8")
    server.lib_load()
    assert set(server.LIB) == {"x1", "x2"} and server.LIB["x2"]["added"] == 0 and server.LIB["x1"]["name"] == "a.mp4"
    assert server.janitor_once() == 0 and set(server.LIB) == {"x1", "x2"}
    keep = d / "dl" / "da.mp4"
    keep.write_bytes(b"x")
    server.LIB["x3"] = {"id": "x3", "path": str(keep), "owner": "k1", "added": 1}
    server.janitor_once()
    assert set(server.LIB) == {"x3"}                   # ist der Speicher da, werden fehlende entfernt
    server.LIB.clear()
    server.LIBRARY_FILE.write_text("{kaputt", encoding="utf-8")
    server.lib_load()
    assert (d / "library.json.kaputt").read_text(encoding="utf-8") == "{kaputt"

    # ---- jobs.json: ein kaputter Eintrag nimmt die anderen nicht mit
    server.JOBS.clear()
    server.QUEUE.clear()
    server.JOBS_FILE.write_text(json.dumps([{"id": "j1", "url": U, "status": "finished", "created": 5},
                                            {"id": "j2", "options": "kaputt"}, 3]), encoding="utf-8")
    server.load_jobs()
    assert list(server.JOBS) == ["j1"], list(server.JOBS)

    # ---- settings.json wird atomar geschrieben
    server.save_settings({"a": 1})
    assert json.loads(server.SETTINGS_FILE.read_text(encoding="utf-8")) == {"a": 1} and not list(d.glob("*.tmp"))
    print("hardening ok")
