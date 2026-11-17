"""Tempolimit des Admins (Obergrenze für alle Downloads) und Speicherplatz-Wächter.
Start: python tests/test_limits.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

GB = 1024 ** 3


def args(**o):
    return server.build_args({"url": "https://example.com/v/1", "mode": "video", **o}, Path("."))


def after(a, flag):
    return a[a.index(flag) + 1]


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS.update(download_dir=str(d / "dl"), rate_limit_mb=0, min_free_gb=1)
    server.SETTINGS_FILE, server.USERS_FILE = d / "settings.json", d / "users.json"
    server.LIBRARY_FILE, server.JOBS_FILE, server.THUMB_DIR = d / "library.json", d / "jobs.json", d / "thumbs"
    server.USERS.clear(); server.LIB.clear()
    admin = server.new_user("Mama", role="admin", folder="")
    kid = server.new_user("Kind")

    # ---- Tempolimit
    assert server.rate_bytes("5M") == 5 * 1024 ** 2 and server.rate_bytes("500k") == 512000 and server.rate_bytes("1000") == 1000
    a = args()
    assert "-r" not in a and after(a, "-N") == "4", a                       # ohne Limit wie bisher
    a = args(rateLimit="5M")
    assert after(a, "-r") == "5M" and after(a, "-N") == "1", a              # Limit gilt pro Verbindung → nur eine
    server.SETTINGS["rate_limit_mb"] = 2
    assert after(args(), "-r") == str(2 * 1024 ** 2)                        # Admin-Limit für alle
    assert after(args(rateLimit="500K"), "-r") == "500K"                    # wer selbst weniger will, darf
    assert after(args(rateLimit="50M"), "-r") == str(2 * 1024 ** 2)         # mehr als der Admin erlaubt geht nicht
    server.SETTINGS["rate_limit_mb"] = "kaputt"
    assert "-r" not in args()                                               # kaputte settings.json bremst nicht aus
    server.SETTINGS["rate_limit_mb"] = 0

    # ---- Speicherplatz-Wächter
    assert server.free_space() > 0
    server.free_space = lambda: int(0.5 * GB)
    try:
        server.check_quota(kid)
        raise AssertionError("zu wenig Platz muss abgelehnt werden")
    except server.OptionError as e:
        assert str(e).startswith("Zu wenig Speicherplatz frei (0.5 GB)"), e
    job = server.Job({"url": "https://example.com/v/1"}, owner=admin["id"])     # z. B. nachts geplant, Platte inzwischen voll
    server.run_job(job)
    assert job.status == "error" and job.error.startswith("Zu wenig Speicherplatz"), (job.status, job.error)
    server.SETTINGS["min_free_gb"] = 0
    server.check_quota(kid)                                                 # 0 = Wächter aus
    server.SETTINGS["min_free_gb"] = 1
    server.free_space = lambda: -1
    server.check_quota(kid)                                                 # Platz unbekannt → nicht blockieren
    server.free_space = lambda: 50 * GB

    # ---- Einstellungen: nur Admin, Werte geprüft, /api/ping zeigt sie
    c = server.app.test_client()
    H = lambda u: {"X-Token": u["token"], "Host": "localhost"}
    r = c.post("/api/settings", json={"rate_limit_mb": 3}, headers=H(kid))
    assert r.status_code == 403, r.status_code
    r = c.post("/api/settings", json={"rate_limit_mb": "x"}, headers=H(admin))
    assert r.status_code == 400, r.status_code
    r = c.post("/api/settings", json={"rate_limit_mb": 2.5, "min_free_gb": 5}, headers=H(admin))
    assert r.status_code == 200 and server.SETTINGS["rate_limit_mb"] == 2.5 and server.SETTINGS["min_free_gb"] == 5
    r = c.post("/api/settings", json={"rate_limit_mb": -4, "min_free_gb": 10 ** 9}, headers=H(admin))
    assert server.SETTINGS["rate_limit_mb"] == 0 and server.SETTINGS["min_free_gb"] == 100000      # Grenzen
    server._tool_cache.clear()
    p = c.get("/api/ping", headers=H(kid)).get_json()
    assert p["free"] == 50 * GB and p["rate_limit_mb"] == 0 and p["min_free_gb"] == 100000, p
    r = c.post("/api/jobs", json={"url": "https://example.com/v/1"}, headers=H(kid))               # 50 GB < 100000 GB
    assert r.status_code == 400 and "Speicherplatz" in r.get_json()["error"], r.get_json()

print("limits ok")
