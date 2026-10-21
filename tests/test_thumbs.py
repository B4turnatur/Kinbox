"""Vorschaubilder der Mediathek lokal: Bild der Seite, sonst Videobild bzw. Cover aus der Datei.
Start: python tests/test_thumbs.py   (braucht ffmpeg im PATH)"""
import functools
import http.server
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.THUMB_DIR = d / "thumbs"
    ff = server.ffmpeg_bin("ffmpeg")
    run = lambda *a: subprocess.run([ff, "-v", "error", "-y", *a], check=True)
    run("-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=3", "-c:v", "libx264", str(d / "v.mp4"))
    run("-f", "lavfi", "-i", "color=red:size=300x300", "-frames:v", "1", str(d / "cover.png"))
    run("-f", "lavfi", "-i", "sine=duration=2", "-i", str(d / "cover.png"), "-map", "0", "-map", "1",
        "-c:a", "libmp3lame", "-c:v", "mjpeg", "-disposition:v", "attached_pic", str(d / "a.mp3"))
    run("-f", "lavfi", "-i", "color=blue:size=1280x720", "-frames:v", "1", str(d / "web.webp"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}/"

    def w(p):
        r = subprocess.run([server.ffmpeg_bin("ffprobe"), "-v", "error", "-show_entries", "stream=width", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True)
        return int(r.stdout.strip())

    assert w(server.thumb_file({"id": "web", "kind": "video", "path": str(d / "v.mp4"), "thumbnail": base + "web.webp"})) == 480
    expired = server.thumb_file({"id": "exp", "kind": "video", "path": str(d / "v.mp4"), "duration": 3, "thumbnail": base + "weg.jpg"})
    assert expired and w(expired) == 480                          # abgelaufener Link → Bild aus dem Video
    assert w(server.thumb_file({"id": "mp3", "kind": "audio", "path": str(d / "a.mp3"), "thumbnail": base + "weg.jpg"})) == 300
    assert server.thumb_file({"id": "x", "kind": "other", "path": str(d / "a.mp3")}) is None
    assert (server.THUMB_DIR / "x.none").exists()
    srv.shutdown()

print("thumbs ok")
