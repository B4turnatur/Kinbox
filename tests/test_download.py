"""Downloads aufs Handy: abgebrochene Übertragungen müssen fortgesetzt werden können.
Androids DownloadManager macht nach einem Netzwechsel/Funkloch mit „Range“ + „If-Match“ weiter –
ohne ETag/206 bricht er mit „can't resume“ ab. Start: python tests/test_download.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

DATA = bytes(range(256)) * 40   # 10240 Bytes


def get(p, headers=None):
    done = []
    with server.app.test_request_context(headers=headers or {}):
        r = server.stream_download(p, lambda: done.append(1))
        body = b"".join(r.response) if r.status_code in (200, 206) else b""
    return r, body, bool(done)


with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "Katze #shorts 100%.mp4"
    p.write_bytes(DATA)

    # ganz
    r, body, done = get(p)
    assert r.status_code == 200 and body == DATA and done
    assert "Accept-Ranges" not in r.headers and r.headers["Content-Length"] == str(len(DATA))
    etag = r.headers["ETag"]
    assert etag.startswith('"') and r.headers["Content-Type"] == "video/mp4"
    assert "filename*=UTF-8''Katze%20%23shorts%20100%25.mp4" in r.headers["Content-Disposition"]

    # Fortsetzen ab Byte 4000 (so fragt der DownloadManager nach einem Abbruch)
    r, body, done = get(p, {"Range": "bytes=4000-", "If-Match": etag})
    assert r.status_code == 206 and body == DATA[4000:] and done, r.status_code
    assert r.headers["Content-Range"] == f"bytes 4000-{len(DATA) - 1}/{len(DATA)}"
    assert r.headers["Content-Length"] == str(len(DATA) - 4000) and r.headers["ETag"] == etag

    # Teilstück in der Mitte: noch nicht fertig → keine „vollständig geladen“-Meldung (Aufräumen nach Download)
    r, body, done = get(p, {"Range": "bytes=0-99", "If-Match": etag})
    assert r.status_code == 206 and body == DATA[:100] and not done
    r, body, done = get(p, {"Range": "bytes=-100", "If-Match": etag})
    assert r.status_code == 206 and body == DATA[-100:] and done

    # Samsung: Teilstücke ohne If-Match (Laden in mehreren Teilen) → wie früher die ganze Datei
    for h in ({"Range": "bytes=0-"}, {"Range": "bytes=4000-"}, {"Range": "bytes=0-99", "If-Range": etag}):
        r, body, done = get(p, h)
        assert r.status_code == 200 and body == DATA and done, h

    # Datei hat sich geändert: If-Match passt nicht → 412
    r, _, done = get(p, {"Range": "bytes=4000-", "If-Match": '"alt"'})
    assert r.status_code == 412 and not done

    # außerhalb der Datei → 416; kaputter Range-Kopf → einfach ganz
    r, _, _ = get(p, {"Range": f"bytes={len(DATA)}-", "If-Match": etag})
    assert r.status_code == 416 and r.headers["Content-Range"] == f"bytes */{len(DATA)}"
    r, body, _ = get(p, {"Range": "bytes=abc", "If-Match": etag})
    assert r.status_code == 200 and body == DATA

print("test_download ok")
