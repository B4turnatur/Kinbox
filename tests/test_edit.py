"""Nachträglich bearbeiten + „Video + Audio“ mit echtem ffmpeg an einem 6-s-Testvideo.
Start: python tests/test_edit.py   (braucht ffmpeg/ffprobe im PATH)"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import server  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    server.SETTINGS["download_dir"] = str(d)
    server.LIBRARY_FILE = d / "library.json"          # echte library.json nicht anfassen
    src = d / "clip.mp4"
    subprocess.run([server.ffmpeg_bin("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=6",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)], check=True)
    job = server.Job({"url": "https://example.com/v"}, owner="u1")
    out_dir = d / "out"
    out_dir.mkdir()

    def run(kind, body, path=src):
        ed = server.edit_check(kind, body)
        out = server.edit_file(job, path, kind, ed, out_dir)
        return out, server.probe(str(out))

    out, info = run("video", {"op": "cut", "start": "1", "end": "0:03.5"})
    assert out.suffix == ".mp4" and abs(info["duration"] - 2.5) < 0.2 and info["audio"], (out, info)
    out, info = run("video", {"op": "audio", "format": "mp3", "bitrate": "192"})
    assert out.suffix == ".mp3" and info["audio"] and abs(info["duration"] - 6) < 0.3, (out, info)
    mp3 = out
    out, info = run("audio", {"op": "cut", "start": "2"}, mp3)
    assert out.suffix == ".mp3" and abs(info["duration"] - 4) < 0.3, info
    out, info = run("audio", {"op": "audio", "format": "wav"}, mp3)
    assert out.suffix == ".wav", out
    out, info = run("video", {"op": "mute"})
    assert not info["audio"], info
    out, info = run("video", {"op": "rotate", "angle": 90})
    wh = subprocess.run([server.ffmpeg_bin("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                         "stream=width,height", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert wh == "240,320", wh
    out, info = run("video", {"op": "loudnorm"})
    assert info["audio"] and out.suffix == ".mp4", info
    out, info = run("video", {"op": "gif", "gifFps": 8, "gifWidth": 160})
    assert out.suffix == ".gif", out

    for kind, body in (("video", {"op": "rm -rf"}), ("audio", {"op": "gif"}), ("video", {"op": "cut"}),
                       ("video", {"op": "cut", "start": "5", "end": "2"}), ("video", {"op": "cut", "start": "1;ls"}),
                       ("video", {"op": "audio", "format": "exe"}), ("video", {"op": "rotate", "angle": 45})):
        try:
            server.edit_check(kind, body)
            raise AssertionError(f"nicht abgelehnt: {body}")
        except server.OptionError:
            pass

    # Video + Audio beim Download
    job.files, job.options = [str(src)], {"mode": "video", "alsoAudio": True, "audioFormat": "mp3"}
    server.also_audio(job)
    assert len(job.files) == 2 and job.files[1].endswith("clip.mp3") and Path(job.files[1]).exists(), job.files

    # run_edit: fremde Datei wird abgelehnt, eigene landet als neuer Eintrag in der Mediathek
    entry = {"id": "e1", "path": str(src), "name": src.name, "title": "Clip", "kind": "video", "owner": "u1", "url": ""}
    server.LIB["e1"] = entry
    stranger = server.Job({"url": "", "edit": {"eid": "e1", "op": "mp4"}}, owner="u2")
    server.run_edit(stranger)
    assert stranger.status == "error", stranger.status
    ok = server.Job({"url": "", "edit": {"eid": "e1", "op": "cut", "start": "0", "end": "2", "keep": True}}, owner="u1")
    server.run_edit(ok)
    assert ok.status == "finished", (ok.status, ok.error)
    new = server.lib_by_path(ok.files[0])
    assert new and new["title"] == "Clip (0:00–0:02)" and new["owner"] == "u1" and src.exists(), new

print("edit ok")
