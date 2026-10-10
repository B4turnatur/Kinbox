"""
Kinbox Server – eine kleine HTTP-API um yt-dlp.

Läuft auf einem Windows- oder Linux-PC im Heimnetz, nimmt Aufträge von der Browser-Erweiterung an,
lädt mit yt-dlp herunter und meldet den Fortschritt zurück.

Start:  python server.py         (oder start.bat)
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from flask import Flask, Response, abort, g, jsonify, request, send_file

APP_VERSION = "3.4.2"
FROZEN = getattr(sys, "frozen", False)   # Kinbox.exe (PyInstaller)
BASE_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR / "tools"            # nur Kinbox.exe: yt-dlp, ffmpeg, deno
SETTINGS_FILE = BASE_DIR / "settings.json"
JOBS_FILE = BASE_DIR / "jobs.json"
LIBRARY_FILE = BASE_DIR / "library.json"
STATIC_DIR = (Path(getattr(sys, "_MEIPASS", BASE_DIR))) / "static"
IS_WINDOWS = os.name == "nt"

DEFAULT_SETTINGS = {
    "host": "0.0.0.0",
    "port": 8765,
    "token": "",                      # wird beim ersten Start erzeugt
    "download_dir": str(Path.home() / "Downloads" / "Kinbox"),
    "max_parallel": 2,
    "cookies_file": "",               # optional: Pfad zu cookies.txt (Netscape-Format)
    "ffmpeg_location": "",            # optional: Ordner mit ffmpeg.exe, falls nicht im PATH
    "ytdlp_command": [],              # leer = "python -m yt_dlp" mit diesem Python
    "extra_args": [],                 # wird an jeden Aufruf angehängt
    "site_args": {                    # Zusatz-Argumente nur für bestimmte Seiten
        "tiktok.com": [
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
            "--referer", "https://www.tiktok.com/",
        ],
    },
    "keep_history": 200,
    "cleanup": {                      # automatisches Aufräumen (in der Erweiterung umschaltbar)
        "after_pc_download": False,   # nach dem Laden auf PC/Handy vom Server löschen
        "max_age_days": 0,            # 0 = aus, sonst nach X Tagen löschen
        "max_size_gb": 0,             # 0 = aus, sonst älteste löschen, wenn größer
    },
    "night": {"start": "01:00", "end": "07:00"},   # Zeitfenster für „nachts laden"
}
NESTED_DEFAULTS = ("cleanup", "night")

# --------------------------------------------------------------------------- #
# Einstellungen
# --------------------------------------------------------------------------- #

def load_settings() -> dict:
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))  # -sig: Windows-Editor speichert mit BOM
        except Exception as e:  # kaputte Datei nicht still überschreiben
            print(f"[!] settings.json konnte nicht gelesen werden: {e}")
            sys.exit(1)
    settings = {**DEFAULT_SETTINGS, **data}
    for k in NESTED_DEFAULTS:
        settings[k] = {**DEFAULT_SETTINGS[k], **(data.get(k) or {})}
    changed = data != settings
    if not settings["token"]:
        settings["token"] = secrets.token_urlsafe(18)
        changed = True
    if changed:
        save_settings(settings)
    return settings


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


FIRST_RUN = not SETTINGS_FILE.exists()
SETTINGS = load_settings()
SETTINGS_LOCK = threading.Lock()


def ytdlp_base() -> list[str]:
    cmd = SETTINGS.get("ytdlp_command") or []
    if cmd:
        return list(cmd)
    return [str(TOOLS_DIR / "yt-dlp.exe")] if FROZEN else [sys.executable, "-m", "yt_dlp"]


def download_root() -> Path:
    p = Path(SETTINGS["download_dir"]).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------- #
# Validierung & Übersetzung der Optionen in yt-dlp-Argumente
# --------------------------------------------------------------------------- #

TIME_RE = re.compile(r"^\d{1,3}(:\d{1,2}){0,2}(\.\d+)?$")
ITEMS_RE = re.compile(r"^[\d:,\-\s]+$")
LANGS_RE = re.compile(r"^[\w.*,\-]+$")
RATE_RE = re.compile(r"^\d+(\.\d+)?[KMG]?$", re.I)
SB_CATS = {"sponsor", "intro", "outro", "selfpromo", "preview", "filler",
           "interaction", "music_offtopic", "poi_highlight", "chapter"}
AUDIO_FORMATS = {"best", "mp3", "m4a", "opus", "flac", "wav", "aac", "vorbis", "alac"}
CONTAINERS = {"auto", "mp4", "mkv", "webm", "mov"}
VCODECS = {"any": None, "h264": "vcodec:h264", "h265": "vcodec:h265", "vp9": "vcodec:vp9", "av1": "vcodec:av01"}
THUMB_FORMATS = {"jpg", "png", "webp"}


def site_args(url: str) -> list[str]:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    out: list[str] = []
    for domain, args in (SETTINGS.get("site_args") or {}).items():
        d = domain.lower().lstrip(".")
        if host == d or host.endswith("." + d):
            out += [str(x) for x in args]
    return out


class OptionError(ValueError):
    pass


def to_seconds(t: str) -> float:
    parts = [float(x) for x in t.split(":")]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def safe_subfolder(sub: str) -> str:
    sub = (sub or "").strip().replace("\\", "/")
    parts = [p for p in sub.split("/") if p not in ("", ".", "..")]
    cleaned = [re.sub(r'[<>:"|?*\x00-\x1f]', "_", p).strip(" .") for p in parts]
    return "/".join(p for p in cleaned if p)


def build_args(opts: dict, job_dir: Path, temp_dir: Path | None = None, archive_dir: Path | None = None) -> list[str]:
    url = (opts.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        raise OptionError("Ungültige URL")

    mode = opts.get("mode", "video")
    a: list[str] = [
        "--newline", "--progress", "--no-colors", "--no-simulate", "--ignore-config",
        "--windows-filenames", "--no-part" if opts.get("noPart") else "--part",
        "-P", f"home:{job_dir}",
        "-P", f"temp:{temp_dir or download_root() / '.tmp'}",
        "--progress-template", "download:@@P%(progress)j",
        "--progress-template", "postprocess:@@Q%(progress.status)s|%(progress.postprocessor)s",
        "--print", "before_dl:@@I%(.{title,thumbnail,id,playlist_index,n_entries,extractor_key,uploader,duration,webpage_url})j",
        "--print", "after_move:@@F%(filepath|)j",
        "--no-mtime",
    ]

    # ---- Playlist ----------------------------------------------------------
    pl = opts.get("playlist", "single")
    if pl == "all":
        a += ["--yes-playlist"]
    elif pl == "items":
        items = (opts.get("playlistItems") or "").replace(" ", "")
        if not items or not ITEMS_RE.match(items):
            raise OptionError("Ungültige Playlist-Auswahl (Beispiel: 1-5,8,10)")
        a += ["--yes-playlist", "--playlist-items", items]
    else:
        a += ["--no-playlist"]

    # ---- Dateiname ---------------------------------------------------------
    tpl = (opts.get("filenameTemplate") or "").strip()
    organize = opts.get("organize", "flat")
    music = bool(opts.get("musicTags")) and mode != "thumbnail"
    if not tpl:
        if organize == "channel":
            tpl = "%(uploader,channel,extractor)s/%(title)s [%(id)s].%(ext)s"
        elif organize == "plex":
            tpl = ("%(uploader,channel,extractor)s/Season %(upload_date>%Y|0000)s/"
                   "%(uploader,channel,extractor)s - S%(upload_date>%Y|0000)sE%(upload_date>%m%d|0000)s - %(title)s [%(id)s].%(ext)s")
        elif organize == "music" or (music and mode == "audio"):
            tpl = ("%(meta_artist,artist,uploader|Unbekannt)s/%(meta_title,track,title)s.%(ext)s" if organize == "music"
                   else "%(meta_artist,artist,uploader|Unbekannt)s - %(meta_title,track,title)s.%(ext)s")
        elif pl != "single":
            tpl = "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
        else:
            tpl = "%(title)s [%(id)s].%(ext)s"
    if ".." in tpl or tpl.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", tpl):
        raise OptionError("Dateinamen-Vorlage darf keine absoluten Pfade oder '..' enthalten")
    a += ["-o", tpl]

    # ---- Modus -------------------------------------------------------------
    if mode == "audio":
        fmt = opts.get("audioFormat", "mp3")
        if fmt not in AUDIO_FORMATS:
            raise OptionError("Unbekanntes Audioformat")
        a += ["-f", "ba/b", "-x", "--audio-format", fmt]
        br = str(opts.get("audioBitrate", "best"))
        if fmt not in ("flac", "wav", "alac", "best"):
            if br == "best":
                a += ["--audio-quality", "0"]
            elif br.isdigit() and 32 <= int(br) <= 512:
                a += ["--audio-quality", f"{br}K"]
            else:
                raise OptionError("Ungültige Audio-Bitrate")
    elif mode == "thumbnail":
        tf = opts.get("thumbnailFormat", "jpg")
        if tf not in THUMB_FORMATS:
            raise OptionError("Unbekanntes Bildformat")
        a += ["--skip-download", "--write-thumbnail", "--convert-thumbnails", tf]
    elif mode == "video":
        q = str(opts.get("quality", "best"))
        vcodec = opts.get("vcodec", "any")
        container = opts.get("container", "mp4")
        if vcodec not in VCODECS:
            raise OptionError("Unbekannter Video-Codec")
        if container not in CONTAINERS:
            raise OptionError("Unbekannter Container")
        sort: list[str] = []
        if q != "best":
            if not q.isdigit():
                raise OptionError("Ungültige Qualität")
            sort.append(f"res:{int(q)}")
        if opts.get("prefer60fps", True):
            sort.append("fps")
        if VCODECS[vcodec]:
            sort.append(VCODECS[vcodec])
        if container == "mp4":
            sort.append("acodec:m4a")  # AAC-Ton, spielt überall
        a += ["-f", "bv*+ba/b"]
        if sort:
            a += ["-S", ",".join(sort)]
        if container != "auto":
            a += ["--merge-output-format", container, "--remux-video", container]
    else:
        raise OptionError("Unbekannter Modus")

    if mode != "thumbnail":
        # ---- Zuschneiden ---------------------------------------------------
        trim = opts.get("trim") or {}
        start, end = (trim.get("start") or "").strip(), (trim.get("end") or "").strip()
        if start or end:
            for t in (start, end):
                if t and not TIME_RE.match(t):
                    raise OptionError(f"Ungültige Zeitangabe: {t} (Format z. B. 1:23 oder 01:02:03)")
            if start and end and to_seconds(end) <= to_seconds(start):
                raise OptionError("Das Ende muss nach dem Start liegen")
            a += ["--download-sections", f"*{start or '0'}-{end or 'inf'}"]
            if trim.get("precise", True):
                a += ["--force-keyframes-at-cuts"]

        # ---- Kapitel -------------------------------------------------------
        chapters = [c for c in (opts.get("chapters") or []) if isinstance(c, str) and c]
        if chapters:
            rx = "^(?:" + "|".join(re.escape(c) for c in chapters) + ")$"
            a += ["--download-sections", rx]
        if opts.get("splitChapters"):
            a += ["--split-chapters", "-o",
                  "chapter:%(title)s - Kapitel/%(section_number)02d - %(section_title)s.%(ext)s"]

        # ---- Untertitel ----------------------------------------------------
        subs = opts.get("subs") or {}
        if subs.get("enabled"):
            langs = (subs.get("langs") or "de,en").replace(" ", "")
            if not LANGS_RE.match(langs):
                raise OptionError("Ungültige Untertitel-Sprachen")
            a += ["--write-subs", "--sub-langs", langs]
            if subs.get("auto"):
                a += ["--write-auto-subs"]
            if subs.get("embed") and mode == "video":
                a += ["--embed-subs"]
            else:
                a += ["--convert-subs", subs.get("format", "srt") if subs.get("format") in ("srt", "vtt", "ass") else "srt"]

        # ---- Metadaten -----------------------------------------------------
        if opts.get("embedThumbnail", True):
            a += ["--embed-thumbnail"]
        if opts.get("embedMetadata", True):
            a += ["--embed-metadata"]
        if opts.get("embedChapters", True):
            a += ["--embed-chapters"]
        if opts.get("writeThumbnail"):
            a += ["--write-thumbnail"]
        if opts.get("writeDescription"):
            a += ["--write-description"]
        if opts.get("writeInfoJson"):
            a += ["--write-info-json"]

        # ---- SponsorBlock --------------------------------------------------
        sb = opts.get("sponsorblock") or {}
        sb_mode = sb.get("mode", "off")
        cats = [c for c in (sb.get("categories") or []) if c in SB_CATS]
        if sb_mode in ("mark", "remove") and cats:
            a += [f"--sponsorblock-{sb_mode}", ",".join(cats)]

        # ---- Musik-Tags: Interpret/Titel sauber, quadratisches Cover --------
        if music:
            a += [
                "--parse-metadata", "%(artist,creator,uploader,channel|)s:(?P<meta_artist>.+)",
                "--parse-metadata", "%(track,title)s:%(meta_title)s",
                "--parse-metadata", "title:(?P<meta_artist>.+?)\\s+[-–—]\\s+(?P<meta_title>.+)",
                "--replace-in-metadata", "meta_artist", r"\s*-\s*Topic$", "",
                "--replace-in-metadata", "meta_title",
                r"(?i)\s*[\(\[](official|offizielles?|lyrics?|audio|video|music video|musikvideo|hd|hq|4k|visuali[sz]er|clip)[^\)\]]*[\)\]]", "",
            ]
            if mode == "audio" and opts.get("embedThumbnail", True):
                crop = "-c:v mjpeg -qmin 1 -qscale:v 1 -vf crop=\"'if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'\""
                a += ["--convert-thumbnails", "jpg",
                      "--postprocessor-args", f"ThumbnailsConvertor+ffmpeg_o:{crop}",
                      "--postprocessor-args", f"EmbedThumbnail+ffmpeg_o:{crop}"]

        # ---- Audio normalisieren (nur Audio-Modus) -------------------------
        if mode == "audio" and opts.get("normalize"):
            a += ["--postprocessor-args", "ExtractAudio:-af loudnorm=I=-16:TP=-1.5:LRA=11"]

    # ---- Nachbearbeitung (GIF / verkleinern) wird nach yt-dlp erledigt -------
    conv = opts.get("convert") or {}
    if conv.get("type", "none") not in ("none", "gif", "small"):
        raise OptionError("Unbekannte Umwandlung")
    if conv.get("type") in ("gif", "small") and mode != "video":
        raise OptionError("GIF und Verkleinern gehen nur im Video-Modus")
    for key, lo, hi in (("gifFps", 5, 30), ("gifWidth", 120, 1280), ("targetMB", 1, 4000)):
        if key in conv:
            try:
                v = float(conv[key])
            except (TypeError, ValueError):
                raise OptionError(f"Ungültiger Wert für {key}")
            if not lo <= v <= hi:
                raise OptionError(f"{key} muss zwischen {lo} und {hi} liegen")
    if opts.get("when", "now") not in ("now", "night"):
        raise OptionError("Ungültiger Zeitpunkt")

    # ---- Netzwerk ----------------------------------------------------------
    rate = (opts.get("rateLimit") or "").strip()
    if rate:
        if not RATE_RE.match(rate):
            raise OptionError("Ungültiges Tempolimit (z. B. 5M oder 500K)")
        a += ["-r", rate]
    frag = int(opts.get("concurrentFragments") or 4)
    a += ["-N", str(max(1, min(frag, 16)))]
    if opts.get("skipArchive"):
        a += ["--download-archive", str((archive_dir or download_root()) / "archive.txt")]

    if SETTINGS.get("ffmpeg_location"):
        a += ["--ffmpeg-location", SETTINGS["ffmpeg_location"]]
    a += list(SETTINGS.get("extra_args") or []) + site_args(url)
    a += ["--", url]
    return a


def cookie_args(work: Path) -> list[str]:
    """Kopiert cookies_file nach work/ – yt-dlp schreibt Cookies am Ende zurück; bei schreibgeschützter
    oder gleichzeitig genutzter Originaldatei gab das „Errno 13 Permission denied“."""
    src = Path(SETTINGS.get("cookies_file") or "")
    if not str(src).strip() or str(src) == ".":
        return []
    if src.is_dir():
        src = src / "cookies.txt"
    if not src.is_file():
        print(f"[Kinbox] cookies_file nicht gefunden: {src}", flush=True)
        return []
    work.mkdir(parents=True, exist_ok=True)
    dst = work / "cookies.txt"
    try:
        shutil.copyfile(src, dst)
    except OSError as e:
        raise OptionError(f"Cookie-Datei nicht lesbar: {e}")
    return ["--cookies", str(dst)]


# --------------------------------------------------------------------------- #
# Aufträge
# --------------------------------------------------------------------------- #

class Job:
    PUBLIC = ("id", "url", "title", "thumbnail", "status", "stage", "percent", "speed",
              "eta", "downloaded", "total", "files", "error", "created", "finished",
              "options", "item", "subfolder", "playlist_pos", "when", "owner")

    def __init__(self, options: dict, owner: str = ""):
        self.id = uuid.uuid4().hex[:12]
        self.owner = owner
        self.url = options.get("url", "")
        self.options = options
        self.title = options.get("title") or self.url
        self.thumbnail = options.get("thumbnail") or ""
        self.subfolder = safe_subfolder(options.get("subfolder", ""))
        self.when = options.get("when", "now")
        self.status = "scheduled" if self.when == "night" else "queued"   # + running, finished, error, cancelled
        self.stage = "Geplant" if self.status == "scheduled" else "Wartet"
        self.percent = 0.0
        self.speed = None
        self.eta = None
        self.downloaded = 0
        self.total = 0
        self.files: list[str] = []
        self.error = ""
        self.created = time.time()
        self.finished = None
        self.item = 0                   # laufende Nummer der Teil-Datei / Playlist-Eintrag
        self.playlist_pos = ""          # z. B. "3/12" bei Playlists
        self.log: deque[str] = deque(maxlen=300)
        self.proc: subprocess.Popen | None = None
        self.cancel_requested = False
        self.meta: dict = {}                       # zuletzt gemeldete Video-Infos von yt-dlp
        self.file_meta: dict[str, dict] = {}       # Datei -> Video-Infos (für die Mediathek)

    def public(self, with_log=False) -> dict:
        d = {k: getattr(self, k) for k in self.PUBLIC}
        d["files"] = [{"name": Path(f).name, "size": _size(f), "exists": Path(f).exists()} for f in self.files]
        if with_log:
            d["log"] = list(self.log)
        return d

    def to_disk(self) -> dict:
        d = self.public()
        d["files"] = self.files
        return d

    @classmethod
    def from_disk(cls, d: dict) -> "Job":
        j = cls(d.get("options") or {"url": d.get("url", "")})
        for k in cls.PUBLIC:
            if k in d:
                setattr(j, k, d[k])
        if j.status == "running":
            j.status, j.stage, j.error = "error", "Unterbrochen", "Server wurde neu gestartet"
        elif j.status in ("queued", "scheduled"):
            j.stage = "Wartet" if j.status == "queued" else "Geplant"
        return j


def _size(f: str) -> int:
    try:
        return os.path.getsize(f)
    except OSError:
        return 0


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()
QUEUE: deque[str] = deque()
QUEUE_COND = threading.Condition(JOBS_LOCK)
_save_pending = threading.Event()


def load_jobs():
    if JOBS_FILE.exists():
        try:
            for d in json.loads(JOBS_FILE.read_text(encoding="utf-8")):
                j = Job.from_disk(d)
                JOBS[j.id] = j
                if j.status in ("queued", "scheduled"):
                    QUEUE.append(j.id)
        except Exception as e:
            print(f"[!] jobs.json ignoriert: {e}")


def save_jobs_soon():
    _save_pending.set()


def _saver():
    while True:
        _save_pending.wait()
        time.sleep(1.5)
        _save_pending.clear()
        with JOBS_LOCK:
            jobs = sorted(JOBS.values(), key=lambda j: j.created)[-SETTINGS["keep_history"]:]
            data = [j.to_disk() for j in jobs]
        tmp = JOBS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, JOBS_FILE)


def _running_count() -> int:
    return sum(1 for j in JOBS.values() if j.status == "running")


def in_night_window() -> bool:
    n = SETTINGS.get("night") or {}
    def mins(t):
        h, _, m = str(t).partition(":")
        return int(h) * 60 + int(m or 0)
    try:
        start, end = mins(n.get("start", "01:00")), mins(n.get("end", "07:00"))
    except ValueError:
        return True
    lt = time.localtime()
    now = lt.tm_hour * 60 + lt.tm_min
    return start <= now < end if start < end else (now >= start or now < end)


def _pick_job() -> str | None:
    night = None
    for jid in list(QUEUE):
        j = JOBS.get(jid)
        if not j or j.status not in ("queued", "scheduled"):
            QUEUE.remove(jid)
            continue
        if j.status == "queued":
            return jid
        if night is None:
            night = in_night_window()
        if night:
            return jid
    return None


def _worker():
    while True:
        with QUEUE_COND:
            while True:
                if _running_count() < int(SETTINGS["max_parallel"]):
                    jid = _pick_job()
                    if jid:
                        break
                QUEUE_COND.wait(timeout=30)   # regelmäßig prüfen, ob das Nachtfenster begonnen hat
            QUEUE.remove(jid)
            job = JOBS[jid]
            job.status, job.stage = "running", "Startet"
        try:
            run_job(job)
        except Exception as e:  # letzte Absicherung
            job.status, job.error = "error", f"Interner Fehler: {e}"
        finally:
            job.finished = time.time()
            job.proc = None
            save_jobs_soon()
            JANITOR_WAKE.set()
            with QUEUE_COND:
                QUEUE_COND.notify_all()


PP_NAMES = {
    "Merger": "Video und Ton zusammenführen", "ExtractAudio": "Audio umwandeln",
    "FFmpegExtractAudio": "Audio umwandeln", "EmbedThumbnail": "Vorschaubild einbetten",
    "FFmpegMetadata": "Metadaten schreiben", "Metadata": "Metadaten schreiben", "EmbedSubtitle": "Untertitel einbetten",
    "FFmpegEmbedSubtitle": "Untertitel einbetten", "SponsorBlock": "SponsorBlock",
    "ModifyChapters": "Abschnitte entfernen", "SplitChapters": "Kapitel aufteilen",
    "FFmpegSplitChapters": "Kapitel aufteilen", "VideoRemuxer": "Container umwandeln",
    "FFmpegVideoRemuxer": "Container umwandeln", "MoveFiles": "Verschieben",
    "FFmpegThumbnailsConvertor": "Bild umwandeln", "FFmpegSubtitlesConvertor": "Untertitel umwandeln",
}


def run_job(job: Job):
    try:
        _run_job(job)
    finally:
        shutil.rmtree(download_root() / ".tmp" / job.id, ignore_errors=True)


def _run_job(job: Job):
    root = user_root(USERS.get(job.owner) or admin_user())
    job_dir = root / job.subfolder if job.subfolder else root
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        temp_dir = download_root() / ".tmp" / job.id
        conv_type = (job.options.get("convert") or {}).get("type", "none")
        # Bei GIF/Verkleinern landet das Original erst im Arbeitsordner, damit sich Aufträge nicht in die Quere kommen
        work_dir = temp_dir / "out" if conv_type in ("gif", "small") else job_dir
        args = cookie_args(temp_dir) + build_args(job.options, work_dir, temp_dir, archive_dir=root)
    except OptionError as e:
        job.status, job.error, job.stage = "error", str(e), "Fehler"
        return
    cmd = ytdlp_base() + args
    job.log.append("$ " + " ".join(cmd))

    kw = {}
    if IS_WINDOWS:
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000  # CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    job.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=env, **kw)
    job.stage = "Lädt Infos"
    last_error = ""
    for raw in job.proc.stdout:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            continue
        if line.startswith("@@P"):
            _progress(job, line[3:])
            continue
        if line.startswith("@@Q"):
            status, _, pp = line[3:].partition("|")
            if status == "started":
                job.stage = PP_NAMES.get(pp, pp)
            continue
        if line.startswith("@@I"):
            try:
                meta = json.loads(line[3:])
                job.meta = meta
                if meta.get("title") and job.title == job.url:
                    job.title = meta["title"]
                if meta.get("thumbnail") and not job.thumbnail:
                    job.thumbnail = meta["thumbnail"]
                if meta.get("n_entries"):
                    job.playlist_pos = f"{meta.get('playlist_index') or '?'}/{meta['n_entries']}"
                job.stage = f"Lädt herunter ({job.playlist_pos})" if job.playlist_pos else "Lädt herunter"
                job.percent = 0.0
            except Exception:
                pass
            job.item += 1
            continue
        if line.startswith("@@F"):
            try:
                fp = json.loads(line[3:])
                if fp and fp not in job.files:
                    job.files.append(fp)
                    job.file_meta[fp] = dict(job.meta)
            except Exception:
                pass
            continue
        job.log.append(line)
        if line.startswith("ERROR:"):
            last_error = line[6:].strip()
    rc = job.proc.wait()
    if job.cancel_requested:
        job.status, job.stage = "cancelled", "Abgebrochen"
    elif rc == 0:
        if job.options.get("mode") == "thumbnail":
            job.files = _find_recent(job_dir, job.created, (".jpg", ".png", ".webp"))
            for f in job.files:
                job.file_meta[f] = dict(job.meta)
            if not job.files:
                job.status, job.stage, job.error = "error", "Fehler", "Kein Vorschaubild gefunden"
                return
        conv = (job.options.get("convert") or {}).get("type", "none")
        if conv in ("gif", "small"):
            try:
                convert_job_files(job, conv, job_dir)
            except OptionError as e:
                if job.cancel_requested:
                    job.status, job.stage = "cancelled", "Abgebrochen"
                else:
                    job.status, job.stage, job.error = "error", "Fehler", str(e)
                return
        job.status, job.stage, job.percent = "finished", "Fertig", 100.0
        for f in job.files:
            if Path(f).exists():
                lib_add(f, job.file_meta.get(f) or job.meta, job)
    else:
        job.status, job.stage = "error", "Fehler"
        job.error = last_error or f"yt-dlp beendet mit Code {rc}"


def _find_recent(folder: Path, since: float, exts) -> list[str]:
    out = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts and p.stat().st_mtime >= since - 2:
            out.append(str(p))
    return out


def _progress(job: Job, payload: str):
    try:
        p = json.loads(payload)
    except Exception:
        return
    st = p.get("status")
    if st == "downloading":
        done = p.get("downloaded_bytes") or 0
        total = p.get("total_bytes") or p.get("total_bytes_estimate") or 0
        job.downloaded, job.total = done, total
        if total:
            job.percent = round(min(done / total * 100, 100), 1)
        elif p.get("fragment_count"):
            job.percent = round((p.get("fragment_index") or 0) / p["fragment_count"] * 100, 1)
        job.speed, job.eta = p.get("speed"), p.get("eta")
        job.stage = f"Lädt herunter ({job.playlist_pos})" if job.playlist_pos else "Lädt herunter"
    elif st == "finished":
        job.percent = 100.0
        job.speed = job.eta = None
        job.stage = "Verarbeitet"


def kill_job(job: Job):
    job.cancel_requested = True
    p = job.proc
    if not p or p.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)],
                           capture_output=True, creationflags=0x08000000)
        else:
            os.killpg(p.pid, signal.SIGTERM)
    except Exception:
        p.kill()


# --------------------------------------------------------------------------- #
# Mediathek: Register aller heruntergeladenen Dateien
# --------------------------------------------------------------------------- #

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".ts"}
AUDIO_EXT = {".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav", ".aac", ".alac", ".weba"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

LIB: dict[str, dict] = {}
LIB_LOCK = threading.RLock()
CLEANUP_LOG: deque[dict] = deque(maxlen=50)
JANITOR_WAKE = threading.Event()


def kind_of(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".gif":
        return "gif"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in IMAGE_EXT:
        return "image"
    return "other"


def lib_load():
    if not LIBRARY_FILE.exists():
        return
    try:
        data = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] library.json ignoriert: {e}")
        return
    for e in data.get("entries", []):
        if Path(e.get("path", "")).exists():
            LIB[e["id"]] = e
    CLEANUP_LOG.extend(data.get("cleanup_log", []))


def lib_save():
    with LIB_LOCK:
        data = {"entries": list(LIB.values()), "cleanup_log": list(CLEANUP_LOG)}
        tmp = LIBRARY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, LIBRARY_FILE)


def lib_by_path(path: str) -> dict | None:
    rp = str(Path(path).resolve())
    with LIB_LOCK:
        return next((e for e in LIB.values() if str(Path(e["path"]).resolve()) == rp), None)


def lib_add(path: str, meta: dict, job: "Job") -> dict:
    existing = lib_by_path(path)
    size = _size(path)
    with LIB_LOCK:
        if existing:
            existing.update(size=size, added=time.time(), job_id=job.id)
            entry = existing
        else:
            entry = {
                "id": uuid.uuid4().hex[:12], "path": str(path), "name": Path(path).name,
                "title": meta.get("title") or job.title or Path(path).stem,
                "url": meta.get("webpage_url") or job.url,
                "thumbnail": meta.get("thumbnail") or job.thumbnail or "",
                "vid": meta.get("id") or "", "extractor": meta.get("extractor_key") or "",
                "uploader": meta.get("uploader") or "", "duration": meta.get("duration") or 0,
                "added": time.time(), "size": size, "kind": kind_of(path), "pinned": False,
                "job_id": job.id, "pc_downloaded": None, "delete_at": None,
                "owner": job.owner, "shared": False,
            }
            LIB[entry["id"]] = entry
    lib_save()
    return entry


def _remove_empty_dirs(p: Path):
    root = download_root().resolve()
    d = p.parent.resolve()
    while d != root and root in d.parents:
        try:
            d.rmdir()          # klappt nur, wenn leer
        except OSError:
            break
        d = d.parent


def lib_delete(eid: str, reason: str = "") -> bool:
    with LIB_LOCK:
        e = LIB.get(eid)
        if not e:
            return False
        p = Path(e["path"])
        try:
            if p.exists():
                p.unlink()
        except OSError:
            return False       # z. B. unter Windows noch geöffnet – später erneut versuchen
        _remove_empty_dirs(p)
        LIB.pop(eid, None)
        if reason:
            CLEANUP_LOG.appendleft({"time": time.time(), "name": e["name"], "size": e.get("size", 0),
                                    "reason": reason, "owner": e.get("owner")})
    lib_save()
    return True


def lib_public(e: dict) -> dict:
    d = {k: e.get(k) for k in ("id", "name", "title", "url", "thumbnail", "uploader", "duration",
                               "added", "size", "kind", "pinned", "extractor", "pc_downloaded", "delete_at",
                               "owner", "shared")}
    owner = USERS.get(e.get("owner") or "")
    d["owner_name"] = owner["name"] if owner else "?"
    d["owner_avatar"] = owner["avatar"] if owner else "❔"
    try:
        root = user_root(owner) if owner else download_root()
        d["folder"] = str(Path(e["path"]).parent.relative_to(root))
    except ValueError:
        d["folder"] = ""
    if d["folder"] == ".":
        d["folder"] = ""
    return d


def lib_stats(owner: str | None = None) -> dict:
    with LIB_LOCK:
        alive = [e for e in LIB.values() if Path(e["path"]).exists() and (owner is None or e.get("owner") == owner)]
        return {"count": len(alive), "size": sum(_size(e["path"]) for e in alive)}


# --------------------------------------------------------------------------- #
# Benutzer & Profile (Familie)
# --------------------------------------------------------------------------- #

import hashlib
import hmac

USERS_FILE = BASE_DIR / "users.json"
USERS: dict[str, dict] = {}
USERS_LOCK = threading.RLock()
AVATARS = ["😀", "😎", "🦊", "🐼", "🐯", "🦄", "🐸", "🐙", "🦁", "🐶", "🐱", "🐻", "🚀", "⚽", "🎮", "🎧", "🌸", "👑"]
COLORS = ["#7c5cff", "#ff6b6b", "#3ecf8e", "#f5a524", "#2fb7ff", "#ff5cc8", "#9aa0a6", "#00c2a8"]
DEFAULT_USER_CLEANUP = {"after_pc_download": False, "max_age_days": 0, "max_size_gb": 0}
_pin_fails: dict[str, list[float]] = {}


def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 120_000).hex()


def users_save():
    with USERS_LOCK:
        tmp = USERS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(list(USERS.values()), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, USERS_FILE)


def folder_name(name: str) -> str:
    f = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "Profil"
    return f[:40]


def new_user(name: str, role: str = "member", avatar: str = "", color: str = "", folder: str | None = None) -> dict:
    with USERS_LOCK:
        taken = {u["folder"].lower() for u in USERS.values()}
        base = folder if folder is not None else folder_name(name)
        f = base
        i = 2
        while folder is None and f.lower() in taken:
            f = f"{base} {i}"
            i += 1
        u = {
            "id": uuid.uuid4().hex[:10], "name": name.strip()[:30] or "Profil", "role": role,
            "avatar": avatar or AVATARS[len(USERS) % len(AVATARS)], "color": color or COLORS[len(USERS) % len(COLORS)],
            "token": secrets.token_urlsafe(18), "pin_hash": "", "pin_salt": "", "folder": f,
            "quota_gb": 0, "cleanup": dict(DEFAULT_USER_CLEANUP), "created": time.time(),
        }
        USERS[u["id"]] = u
    users_save()
    return u


def users_load():
    """Lädt users.json – beim ersten Start wird der bisherige Token zum Admin-Profil."""
    if USERS_FILE.exists():
        for u in json.loads(USERS_FILE.read_text(encoding="utf-8")):
            u.setdefault("cleanup", dict(DEFAULT_USER_CLEANUP))
            u.setdefault("quota_gb", 0)
            USERS[u["id"]] = u
    if not USERS:
        admin = new_user("Admin", role="admin", avatar="👑", folder="")
        admin["token"] = SETTINGS["token"]
        admin["cleanup"] = {**DEFAULT_USER_CLEANUP, **(SETTINGS.get("cleanup") or {})}
        users_save()
        print(" [i] Profile eingerichtet – dein bisheriger Token gehört jetzt zum Admin-Profil.")


def admin_user() -> dict:
    with USERS_LOCK:
        return next((u for u in USERS.values() if u["role"] == "admin"), next(iter(USERS.values())))


def user_by_token(token: str) -> dict | None:
    if not token:
        return None
    with USERS_LOCK:
        for u in USERS.values():
            if hmac.compare_digest(token, u["token"]):
                return u
    return None


def user_root(u: dict) -> Path:
    p = download_root() / safe_subfolder(u.get("folder", "")) if u.get("folder") else download_root()
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_public(u: dict, private=False) -> dict:
    d = {k: u.get(k) for k in ("id", "name", "avatar", "color", "role")}
    d["has_pin"] = bool(u.get("pin_hash"))
    if private:
        d.update(folder=u.get("folder"), quota_gb=u.get("quota_gb", 0), cleanup=u.get("cleanup"), created=u.get("created"))
    return d


def user_usage(uid: str) -> int:
    with LIB_LOCK:
        return sum(_size(e["path"]) for e in LIB.values() if e.get("owner") == uid and Path(e["path"]).exists())


def check_quota(u: dict):
    q = float(u.get("quota_gb") or 0)
    if q and user_usage(u["id"]) >= q * 1024 ** 3:
        raise OptionError(f"Dein Speicher ist voll ({q:g} GB). Lösche etwas in der Mediathek oder frag den Admin.")


def check_pin(u: dict, pin: str) -> bool:
    now = time.time()
    fails = [t for t in _pin_fails.get(u["id"], []) if now - t < 300]
    if len(fails) >= 8:
        raise OptionError("Zu viele falsche Versuche – bitte 5 Minuten warten.")
    ok = not u.get("pin_hash") or hmac.compare_digest(_hash_pin(pin or "", u.get("pin_salt", "")), u["pin_hash"])
    if not ok:
        fails.append(now)
        _pin_fails[u["id"]] = fails
        time.sleep(0.8)
    else:
        _pin_fails.pop(u["id"], None)
    return ok


def set_pin(u: dict, pin: str):
    pin = (pin or "").strip()
    if pin and not re.fullmatch(r"\d{4,8}", pin):
        raise OptionError("Die PIN muss aus 4–8 Ziffern bestehen.")
    with USERS_LOCK:
        if pin:
            u["pin_salt"] = secrets.token_hex(8)
            u["pin_hash"] = _hash_pin(pin, u["pin_salt"])
        else:
            u["pin_salt"] = u["pin_hash"] = ""
    users_save()


# --------------------------------------------------------------------------- #
# Aufräumen (umschaltbar: nach PC-Download, nach X Tagen, ab Speicherlimit)
# --------------------------------------------------------------------------- #

def janitor_once(only_user: str | None = None) -> int:
    """Jede Person hat eigene Regeln – sie gelten nur für ihre eigenen Dateien."""
    now = time.time()
    removed = 0
    with LIB_LOCK:
        for eid, e in list(LIB.items()):
            if not Path(e["path"]).exists():
                LIB.pop(eid, None)
        for uid, u in list(USERS.items()):
            if only_user and uid != only_user:
                continue
            c = u.get("cleanup") or {}
            mine = sorted((e for e in LIB.values() if e.get("owner") == uid), key=lambda e: e["added"])
            for e in mine:
                if e.get("pinned"):
                    continue
                if e.get("delete_at") and e["delete_at"] <= now:
                    removed += lib_delete(e["id"], "auf Gerät geladen")
                elif c.get("max_age_days") and now - e["added"] > float(c["max_age_days"]) * 86400:
                    removed += lib_delete(e["id"], f"älter als {c['max_age_days']} Tage")
            if c.get("max_size_gb"):
                limit = float(c["max_size_gb"]) * 1024 ** 3
                alive = [e for e in LIB.values() if e.get("owner") == uid and Path(e["path"]).exists()]
                alive.sort(key=lambda e: e["added"])
                total = sum(_size(e["path"]) for e in alive)
                for e in alive:
                    if total <= limit:
                        break
                    if e.get("pinned"):
                        continue
                    size = _size(e["path"])
                    if lib_delete(e["id"], f"Speicherlimit {c['max_size_gb']} GB"):
                        total -= size
                        removed += 1
    if removed:
        lib_save()
    return removed


def _janitor():
    while True:
        JANITOR_WAKE.wait(timeout=300)
        JANITOR_WAKE.clear()
        time.sleep(2)
        try:
            janitor_once()
        except Exception as e:  # darf den Server nie stoppen
            print(f"[!] Aufräumen fehlgeschlagen: {e}")


def mark_pc_downloaded(path: str, by_user: str | None = None):
    e = lib_by_path(path)
    if not e:
        return
    owner = USERS.get(e.get("owner") or "") or {}
    if by_user and by_user != e.get("owner"):
        return          # Laden durch andere Familienmitglieder (geteilte Datei) löscht nichts
    with LIB_LOCK:
        e["pc_downloaded"] = time.time()
        if (owner.get("cleanup") or {}).get("after_pc_download") and not e.get("pinned"):
            e["delete_at"] = time.time() + 60   # kurze Gnadenfrist, falls der Download wiederholt wird
            threading.Timer(65, JANITOR_WAKE.set).start()
    lib_save()


def stream_download(path: Path, on_complete=None) -> Response:
    """Datei als Download senden; on_complete wird nur bei vollständiger Übertragung aufgerufen."""
    from urllib.parse import quote
    size = path.stat().st_size

    def gen():
        sent = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                sent += len(chunk)
                yield chunk
        if on_complete and sent >= size:
            on_complete()

    ascii_name = re.sub(r'[^\x20-\x7e]|["\\]', "_", path.name)
    headers = {
        "Content-Length": str(size),
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(path.name)}",
    }
    return Response(gen(), mimetype="application/octet-stream", headers=headers, direct_passthrough=True)


# --------------------------------------------------------------------------- #
# Nachbearbeitung mit ffmpeg: GIF und „klein" (für WhatsApp, Discord …)
# --------------------------------------------------------------------------- #

def ffmpeg_bin(name: str) -> str:
    loc = SETTINGS.get("ffmpeg_location")
    if loc:
        p = Path(loc)
        if p.is_file():
            p = p.parent
        for cand in (p / f"{name}.exe", p / name):
            if cand.exists():
                return str(cand)
    return shutil.which(name) or name


def probe(path: str) -> dict:
    r = subprocess.run([ffmpeg_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                        "-of", "json", path], capture_output=True, timeout=60,
                       **({"creationflags": 0x08000000} if IS_WINDOWS else {}))
    try:
        d = json.loads(r.stdout.decode("utf-8", "replace"))
    except Exception:
        d = {}
    return {"duration": float((d.get("format") or {}).get("duration") or 0),
            "audio": any(s.get("codec_type") == "audio" for s in d.get("streams", []))}


def run_ffmpeg(job: "Job", args: list[str], duration: float, stage: str, lo: float, hi: float):
    cmd = [ffmpeg_bin("ffmpeg"), "-hide_banner", "-nostats", "-loglevel", "error", "-progress", "pipe:1", "-y"] + args
    job.log.append("$ " + " ".join(cmd))
    job.stage, job.percent = stage, lo
    kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000} if IS_WINDOWS else {"start_new_session": True}
    job.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, **kw)
    for raw in job.proc.stdout:
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith(("out_time_us=", "out_time_ms=")) and duration:
            try:
                t = int(line.split("=", 1)[1]) / 1e6
                job.percent = round(lo + (hi - lo) * min(t / duration, 1), 1)
            except ValueError:
                pass
    err_out = job.proc.stderr.read().decode("utf-8", "replace").strip()
    rc = job.proc.wait()
    job.proc = None
    if err_out:
        job.log.extend(err_out.splitlines()[-10:])
    if job.cancel_requested:
        raise OptionError("Abgebrochen")
    if rc != 0:
        raise OptionError(f"ffmpeg-Fehler: {err_out.splitlines()[-1] if err_out else rc}")


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(2, 1000):
        cand = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not cand.exists():
            return cand
    return p.with_name(f"{p.stem} {uuid.uuid4().hex[:6]}{p.suffix}")


def convert_job_files(job: "Job", kind: str, final_dir: Path):
    conv = job.options.get("convert") or {}
    new_files = []
    for f in job.files:
        src = Path(f)
        if not src.exists() or kind_of(f) != "video":
            new_files.append(f)
            continue
        info = probe(f)
        dur = info["duration"]
        if kind == "gif":
            if dur > 90:
                raise OptionError(f"Für ein GIF ist das Video zu lang ({int(dur)} s). Bitte vorher auf max. 90 s zuschneiden.")
            fps, width = int(conv.get("gifFps", 12)), int(conv.get("gifWidth", 480))
            out = unique_path(final_dir / (src.stem + ".gif"))
            vf = (f"fps={fps},scale={width}:-2:flags=lanczos,split[a][b];"
                  f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5")
            run_ffmpeg(job, ["-i", str(src), "-vf", vf, "-loop", "0", str(out)], dur, "GIF erstellen", 0, 100)
        else:
            target = float(conv.get("targetMB", 16))
            if not dur:
                raise OptionError("Videolänge unbekannt – Verkleinern nicht möglich")
            total_k = target * 8000 * 0.92 / dur            # verfügbare kbit/s insgesamt
            audio_k = (96 if total_k > 400 else 64) if info["audio"] else 0
            video_k = int(total_k - audio_k)
            if video_k < 90:
                mins = target * 8000 * 0.92 / (90 + audio_k) / 60
                raise OptionError(f"Zu lang für {target:g} MB – bei dieser Größe gehen etwa {mins:.1f} Minuten. Bitte zuschneiden.")
            h = 480 if video_k < 600 else 720 if video_k < 1800 else 1080
            out = unique_path(final_dir / f"{src.stem} (klein).mp4")
            tmp = download_root() / ".tmp" / job.id / "pass"
            tmp.mkdir(parents=True, exist_ok=True)
            log = str(tmp / "pass")
            vf = f"scale=-2:'min(ih,{h})'"
            common = ["-i", str(src), "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-b:v", f"{video_k}k",
                      "-maxrate", f"{int(video_k * 1.4)}k", "-bufsize", f"{video_k * 2}k", "-passlogfile", log]
            try:
                run_ffmpeg(job, common + ["-pass", "1", "-an", "-f", "null", os.devnull], dur, "Verkleinern (1/2)", 0, 45)
                audio = ["-c:a", "aac", "-b:a", f"{audio_k}k"] if audio_k else ["-an"]
                run_ffmpeg(job, common + ["-pass", "2"] + audio + ["-movflags", "+faststart", str(out)],
                           dur, "Verkleinern (2/2)", 45, 100)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        job.file_meta[str(out)] = job.file_meta.get(f) or dict(job.meta)
        new_files.append(str(out))
        if conv.get("keepOriginal"):
            dest = unique_path(final_dir / src.name)
            shutil.move(str(src), dest)
            job.file_meta[str(dest)] = job.file_meta.get(f) or dict(job.meta)
            new_files.append(str(dest))
    # Nicht umgewandelte Nebendateien (Untertitel usw.) aus dem Arbeitsordner mitnehmen
    for i, f in enumerate(new_files):
        p = Path(f)
        if p.exists() and final_dir.resolve() not in p.resolve().parents and p.parent.resolve() != final_dir.resolve():
            dest = unique_path(final_dir / p.name)
            shutil.move(str(p), dest)
            job.file_meta[str(dest)] = job.file_meta.get(f) or dict(job.meta)
            new_files[i] = str(dest)
    job.files = new_files


# --------------------------------------------------------------------------- #
# Presets für Handy-Kurzbefehle (/api/add?preset=…)
# --------------------------------------------------------------------------- #

SERVER_PRESETS = {
    "best": {"mode": "video", "quality": "best", "container": "mp4"},
    "1080": {"mode": "video", "quality": "1080", "container": "mp4", "vcodec": "h264"},
    "720": {"mode": "video", "quality": "720", "container": "mp4", "vcodec": "h264"},
    "mp3": {"mode": "audio", "audioFormat": "mp3", "audioBitrate": "320"},
    "music": {"mode": "audio", "audioFormat": "mp3", "audioBitrate": "320", "musicTags": True},
    "flac": {"mode": "audio", "audioFormat": "flac"},
    "podcast": {"mode": "audio", "audioFormat": "mp3", "audioBitrate": "128", "normalize": True,
                "sponsorblock": {"mode": "remove", "categories": ["sponsor", "selfpromo", "interaction", "intro", "outro"]}},
    "whatsapp": {"mode": "video", "quality": "720", "container": "mp4", "vcodec": "h264",
                 "convert": {"type": "small", "targetMB": 15}},
    "gif": {"mode": "video", "quality": "720", "container": "mp4", "convert": {"type": "gif"}},
}
BASE_OPTIONS = {"embedThumbnail": True, "embedMetadata": True, "embedChapters": True, "concurrentFragments": 4}


# --------------------------------------------------------------------------- #
# Info-Abfrage (mit kleinem Cache)
# --------------------------------------------------------------------------- #

INFO_CACHE: dict[str, tuple[float, dict]] = {}


def fetch_info(url: str, playlist: bool) -> dict:
    key = f"{playlist}|{url}"
    hit = INFO_CACHE.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    cmd = ytdlp_base() + ["-J", "--no-warnings", "--ignore-config", "--flat-playlist",
                          "--yes-playlist" if playlist else "--no-playlist"]
    kw = {"creationflags": 0x08000000} if IS_WINDOWS else {}
    with tempfile.TemporaryDirectory() as tmp:
        cmd += cookie_args(Path(tmp)) + list(SETTINGS.get("extra_args") or []) + site_args(url) + ["--", url]
        r = subprocess.run(cmd, capture_output=True, timeout=90,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **kw)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip().splitlines()
        msg = next((l[6:].strip() for l in reversed(err) if l.startswith("ERROR:")), err[-1] if err else "Unbekannter Fehler")
        raise OptionError(msg)
    info = json.loads(r.stdout.decode("utf-8", "replace"))
    out = summarize_info(info)
    INFO_CACHE[key] = (time.time(), out)
    return out


def summarize_info(info: dict) -> dict:
    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        return {
            "type": "playlist", "title": info.get("title"), "uploader": info.get("uploader") or info.get("channel"),
            "count": info.get("playlist_count") or len(entries),
            "thumbnail": (info.get("thumbnails") or [{}])[-1].get("url"),
            "entries": [{"title": e.get("title"), "duration": e.get("duration")} for e in entries[:500]],
        }
    formats = info.get("formats") or []
    duration = info.get("duration") or 0
    audio = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    best_audio = max((f.get("filesize") or f.get("filesize_approx") or 0 for f in audio), default=0)
    heights: dict[int, dict] = {}
    for f in formats:
        h = f.get("height")
        if not h or f.get("vcodec") in (None, "none"):
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        if not size and f.get("tbr") and duration:
            size = f["tbr"] * 1000 / 8 * duration
        cur = heights.setdefault(h, {"height": h, "fps": 0, "size": 0, "codecs": set()})
        cur["fps"] = max(cur["fps"], int(f.get("fps") or 0))
        cur["size"] = max(cur["size"], size)
        cur["codecs"].add((f.get("vcodec") or "").split(".")[0])
    qualities = []
    for h in sorted(heights, reverse=True):
        q = heights[h]
        qualities.append({"height": h, "fps": q["fps"],
                          "size": int(q["size"] + best_audio) if q["size"] else 0,
                          "codecs": sorted(c for c in q["codecs"] if c)})
    subs = sorted((info.get("subtitles") or {}).keys())
    auto = sorted((info.get("automatic_captions") or {}).keys())
    return {
        "type": "video", "id": info.get("id"), "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"), "duration": duration,
        "thumbnail": info.get("thumbnail"), "extractor": info.get("extractor_key"),
        "webpage_url": info.get("webpage_url"), "is_live": bool(info.get("is_live")),
        "qualities": qualities, "audio_size": int(best_audio),
        "chapters": [{"title": c.get("title"), "start": c.get("start_time"), "end": c.get("end_time")}
                     for c in (info.get("chapters") or [])],
        "subtitles": subs, "auto_subtitles": [l for l in auto if "-" not in l or l.endswith("-orig")][:80],
    }


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

app = Flask(__name__)
app.json.ensure_ascii = False


@app.after_request
def cors(resp: Response):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Token"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Private-Network"] = "true"
    return resp


PUBLIC_PATHS = ("/", "/favicon.ico", "/library", "/manifest.webmanifest", "/api/profiles", "/api/login")


@app.before_request
def auth():
    if request.method == "OPTIONS":
        return Response(status=204)
    if request.path in PUBLIC_PATHS or request.path.startswith("/static/"):
        return None
    u = user_by_token(request.headers.get("X-Token") or request.args.get("token") or "")
    if not u:
        return jsonify(error="Falscher oder fehlender Token"), 401
    g.user = u


def me() -> dict:
    return g.user


def is_admin() -> bool:
    return g.user.get("role") == "admin"


def need_admin():
    if not is_admin():
        abort(Response(json.dumps({"error": "Nur für den Admin"}), 403, mimetype="application/json"))


def err(msg, code=400):
    return jsonify(error=msg), code


@app.get("/")
def index():
    from flask import redirect
    return redirect("/library")


@app.get("/library")
def library_page():
    p = STATIC_DIR / "library.html"
    if not p.exists():
        return Response(f"Kinbox {APP_VERSION} läuft.", mimetype="text/plain; charset=utf-8")
    return send_file(p, mimetype="text/html", max_age=0)


@app.get("/static/<path:name>")
def static_file(name):
    p = (STATIC_DIR / name).resolve()
    if STATIC_DIR.resolve() not in p.parents or not p.is_file():
        abort(404)
    return send_file(p, max_age=0)


@app.get("/manifest.webmanifest")
def manifest():
    return jsonify(name="Kinbox", short_name="Kinbox", start_url="/library", display="standalone",
                   background_color="#121216", theme_color="#7c5cff",
                   icons=[{"src": "/static/icon.png", "sizes": "192x192", "type": "image/png"}])


def has_ffmpeg() -> bool:
    loc = SETTINGS.get("ffmpeg_location")
    if loc:
        return any((Path(loc) / n).exists() for n in ("ffmpeg.exe", "ffmpeg")) or Path(loc).is_file()
    return bool(shutil.which("ffmpeg"))


_version_cache = {}


def ytdlp_version() -> str:
    if "v" not in _version_cache or time.time() - _version_cache.get("t", 0) > 3600:
        try:
            r = subprocess.run(ytdlp_base() + ["--version"], capture_output=True, timeout=30,
                               **({"creationflags": 0x08000000} if IS_WINDOWS else {}))
            _version_cache["v"] = r.stdout.decode().strip() or "?"
        except Exception:
            _version_cache["v"] = "nicht gefunden"
        _version_cache["t"] = time.time()
    return _version_cache["v"]


def js_runtime():
    for r in ("deno", "node", "bun", "qjs"):
        if shutil.which(r):
            return r
    extra = " ".join(str(x) for x in SETTINGS.get("extra_args") or [])
    if "--js-runtimes" in extra:
        return "eigene Einstellung"
    home_deno = Path.home() / ".deno" / "bin" / ("deno.exe" if IS_WINDOWS else "deno")
    return "deno" if home_deno.exists() else None


def _my_log(limit: int) -> list:
    uid = me()["id"]
    return [l for l in CLEANUP_LOG if is_admin() or l.get("owner") == uid][:limit]


@app.get("/api/ping")
def ping():
    u = me()
    return jsonify(ok=True, version=APP_VERSION, ytdlp=ytdlp_version(),
                   ffmpeg=has_ffmpeg(), js_runtime=js_runtime(),
                   download_dir=str(user_root(u)) if not is_admin() else str(download_root()),
                   max_parallel=SETTINGS["max_parallel"],
                   cookies=bool(SETTINGS.get("cookies_file")),
                   user=user_public(u, private=True), is_admin=is_admin(),
                   cleanup=u.get("cleanup"), night=SETTINGS.get("night"), night_active=in_night_window(),
                   library=lib_stats(u["id"]), usage=user_usage(u["id"]), quota_gb=u.get("quota_gb", 0),
                   cleanup_log=_my_log(8))


# ---- Profile & Anmeldung ----------------------------------------------------

@app.get("/api/profiles")
def profiles():
    with USERS_LOCK:
        users = sorted(USERS.values(), key=lambda u: (u["role"] != "admin", u["created"]))
        return jsonify([user_public(u) for u in users])


@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    u = USERS.get(str(body.get("id", "")))
    if not u:
        return err("Profil nicht gefunden", 404)
    try:
        if not check_pin(u, str(body.get("pin", ""))):
            return err("Falsche PIN", 403)
    except OptionError as e:
        return err(str(e), 429)
    return jsonify(token=u["token"], user=user_public(u, private=True))


@app.get("/api/me")
def get_me():
    u = me()
    return jsonify(user=user_public(u, private=True), token=u["token"], usage=user_usage(u["id"]))


@app.post("/api/me")
def update_me():
    u = me()
    body = request.get_json(silent=True) or {}
    try:
        _apply_profile(u, body, admin_fields=False)
        if "pin" in body:
            set_pin(u, str(body.get("pin") or ""))
    except OptionError as e:
        return err(str(e))
    users_save()
    return jsonify(user=user_public(u, private=True))


def _apply_profile(u: dict, body: dict, admin_fields: bool):
    with USERS_LOCK:
        if "name" in body:
            name = str(body["name"]).strip()[:30]
            if not name:
                raise OptionError("Bitte einen Namen angeben")
            if any(x["name"].lower() == name.lower() and x["id"] != u["id"] for x in USERS.values()):
                raise OptionError("Diesen Namen gibt es schon")
            u["name"] = name
        if "avatar" in body and 0 < len(str(body["avatar"])) <= 8:
            u["avatar"] = str(body["avatar"])
        if "color" in body and re.fullmatch(r"#[0-9a-fA-F]{6}", str(body["color"])):
            u["color"] = str(body["color"])
        if admin_fields:
            if "quota_gb" in body:
                try:
                    u["quota_gb"] = max(0, float(body["quota_gb"] or 0))
                except (TypeError, ValueError):
                    raise OptionError("Ungültiges Kontingent")
            if body.get("role") in ("admin", "member"):
                if u["role"] == "admin" and body["role"] == "member" and \
                        sum(1 for x in USERS.values() if x["role"] == "admin") <= 1:
                    raise OptionError("Es muss mindestens einen Admin geben")
                u["role"] = body["role"]


# ---- Familie verwalten (nur Admin) --------------------------------------------

@app.get("/api/users")
def list_users():
    need_admin()
    with USERS_LOCK:
        out = []
        for u in sorted(USERS.values(), key=lambda u: (u["role"] != "admin", u["created"])):
            d = user_public(u, private=True)
            d["token"] = u["token"]
            d["usage"] = user_usage(u["id"])
            d["files"] = lib_stats(u["id"])["count"]
            d["active_jobs"] = sum(1 for j in JOBS.values() if j.owner == u["id"] and j.status in ("queued", "running", "scheduled"))
            out.append(d)
    return jsonify(out)


@app.post("/api/users")
def create_user():
    need_admin()
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return err("Bitte einen Namen angeben")
    if any(u["name"].lower() == name.lower() for u in USERS.values()):
        return err("Diesen Namen gibt es schon")
    u = new_user(name, role="admin" if body.get("role") == "admin" else "member",
                 avatar=str(body.get("avatar") or ""), color=str(body.get("color") or ""))
    try:
        _apply_profile(u, {k: v for k, v in body.items() if k in ("quota_gb",)}, admin_fields=True)
        if body.get("pin"):
            set_pin(u, str(body["pin"]))
    except OptionError as e:
        with USERS_LOCK:
            USERS.pop(u["id"], None)
        users_save()
        return err(str(e))
    users_save()
    d = user_public(u, private=True)
    d["token"] = u["token"]
    return jsonify(d), 201


@app.patch("/api/users/<uid>")
def patch_user(uid):
    need_admin()
    u = USERS.get(uid) or abort(404)
    body = request.get_json(silent=True) or {}
    try:
        _apply_profile(u, body, admin_fields=True)
        if "pin" in body:
            set_pin(u, str(body.get("pin") or ""))
    except OptionError as e:
        return err(str(e))
    users_save()
    return jsonify(user_public(u, private=True))


@app.post("/api/users/<uid>/token")
def reset_token(uid):
    need_admin()
    u = USERS.get(uid) or abort(404)
    with USERS_LOCK:
        u["token"] = secrets.token_urlsafe(18)
        if u["role"] == "admin" and u["id"] == admin_user()["id"]:
            SETTINGS["token"] = u["token"]
            save_settings(SETTINGS)
    users_save()
    return jsonify(token=u["token"])


@app.delete("/api/users/<uid>")
def delete_user(uid):
    need_admin()
    u = USERS.get(uid) or abort(404)
    if u["id"] == me()["id"]:
        return err("Du kannst dein eigenes Profil nicht löschen")
    if u["role"] == "admin" and sum(1 for x in USERS.values() if x["role"] == "admin") <= 1:
        return err("Es muss mindestens einen Admin geben")
    with QUEUE_COND:
        for j in JOBS.values():
            if j.owner == uid and j.status in ("queued", "scheduled", "running"):
                j.status, j.stage = "cancelled", "Abgebrochen"
                kill_job(j)
    removed = 0
    if request.args.get("files") == "1":
        for e in [e for e in LIB.values() if e.get("owner") == uid]:
            removed += lib_delete(e["id"])
    else:   # Dateien bleiben – sie gehören dann dir
        with LIB_LOCK:
            for e in LIB.values():
                if e.get("owner") == uid:
                    e["owner"] = me()["id"]
        lib_save()
    with JOBS_LOCK:
        for jid in [j.id for j in JOBS.values() if j.owner == uid]:
            JOBS.pop(jid, None)
    with USERS_LOCK:
        USERS.pop(uid, None)
    users_save()
    save_jobs_soon()
    return jsonify(ok=True, removed_files=removed)


# ---- Aufträge -----------------------------------------------------------------

def _visible(entry_owner: str, shared: bool = False) -> bool:
    return entry_owner == me()["id"] or shared or is_admin()


@app.post("/api/info")
def info():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        return err("Ungültige URL")
    try:
        data = dict(fetch_info(url, bool(body.get("playlist"))))
        if data.get("type") == "video" and data.get("id"):
            uid = me()["id"]
            with LIB_LOCK:
                data["already"] = [lib_public(e) for e in sorted(LIB.values(), key=lambda e: e["added"], reverse=True)
                                   if e.get("vid") == data["id"] and (e.get("extractor") or "") == (data.get("extractor") or "")
                                   and Path(e["path"]).exists() and (e.get("owner") == uid or e.get("shared"))]
        return jsonify(data)
    except OptionError as e:
        return err(str(e), 422)
    except subprocess.TimeoutExpired:
        return err("Zeitüberschreitung beim Abrufen der Infos", 504)


@app.post("/api/jobs")
def create_job():
    opts = request.get_json(silent=True) or {}
    try:
        check_quota(me())
        build_args(opts, download_root())  # vorab prüfen, damit Fehler sofort sichtbar sind
    except OptionError as e:
        return err(str(e))
    return jsonify(enqueue(opts).public()), 201


def enqueue(opts: dict) -> Job:
    job = Job(opts, owner=me()["id"])
    with QUEUE_COND:
        JOBS[job.id] = job
        QUEUE.append(job.id)
        QUEUE_COND.notify_all()
    save_jobs_soon()
    return job


@app.get("/api/add")
def add_via_get():
    """Für Handy-Kurzbefehle: /api/add?url=…&preset=mp3&token=…"""
    url = (request.args.get("url") or "").strip()
    m = re.search(r"https?://\S+", url)          # geteilter Text enthält oft mehr als nur den Link
    if not m:
        return err("Kein Link gefunden")
    preset = request.args.get("preset", "best")
    opts = {**BASE_OPTIONS, **SERVER_PRESETS.get(preset, SERVER_PRESETS["best"]), "url": m.group(0).rstrip(").,;")}
    if request.args.get("when") == "night":
        opts["when"] = "night"
    try:
        check_quota(me())
        build_args(opts, download_root())
    except OptionError as e:
        return err(str(e))
    job = enqueue(opts)
    if "text/html" in (request.headers.get("Accept") or ""):
        return Response(f"""<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<body style="font:18px system-ui;background:#121216;color:#eee;display:grid;place-items:center;height:90vh;text-align:center">
<div><div style="font-size:48px">✓</div>Zur Warteschlange hinzugefügt<br><small style="color:#999">{preset}</small>
<p><a style="color:#a48bff" href="/library">Zur Mediathek</a></p></div>""", mimetype="text/html")
    return jsonify(job.public()), 201


@app.get("/api/jobs")
def list_jobs():
    show_all = is_admin() and request.args.get("all") == "1"
    uid = me()["id"]
    with JOBS_LOCK:
        jobs = sorted((j for j in JOBS.values() if show_all or j.owner == uid), key=lambda j: j.created, reverse=True)
        return jsonify([j.public() for j in jobs])


def _get(jid) -> Job:
    job = JOBS.get(jid)
    if not job or not (job.owner == me()["id"] or is_admin()):
        abort(404)
    return job


@app.get("/api/jobs/<jid>")
def get_job(jid):
    return jsonify(_get(jid).public(with_log=True))


@app.post("/api/jobs/<jid>/cancel")
def cancel_job(jid):
    job = _get(jid)
    with QUEUE_COND:
        if job.status in ("queued", "scheduled"):
            job.status, job.stage = "cancelled", "Abgebrochen"
            if jid in QUEUE:
                QUEUE.remove(jid)
    if job.status == "running":
        kill_job(job)
    save_jobs_soon()
    return jsonify(job.public())


@app.post("/api/jobs/<jid>/start")
def start_now(jid):
    job = _get(jid)
    with QUEUE_COND:
        if job.status == "scheduled":
            job.status, job.stage, job.when = "queued", "Wartet", "now"
            job.options["when"] = "now"
            QUEUE_COND.notify_all()
    save_jobs_soon()
    return jsonify(job.public())


@app.post("/api/jobs/<jid>/retry")
def retry_job(jid):
    old = _get(jid)
    if old.status in ("queued", "running", "scheduled"):
        return err("Auftrag läuft noch")
    job = Job({**old.options, "title": old.title, "thumbnail": old.thumbnail}, owner=old.owner)
    with QUEUE_COND:
        JOBS.pop(jid, None)
        JOBS[job.id] = job
        QUEUE.append(job.id)
        QUEUE_COND.notify_all()
    save_jobs_soon()
    return jsonify(job.public()), 201


@app.delete("/api/jobs/<jid>")
def delete_job(jid):
    job = _get(jid)
    if job.status in ("queued", "running", "scheduled"):
        return err("Erst abbrechen, dann löschen")
    removed = 0
    if request.args.get("files") == "1":
        root = download_root().resolve()
        for f in job.files:
            e = lib_by_path(f)
            if e:
                removed += lib_delete(e["id"])
                continue
            p = Path(f).resolve()
            if root in p.parents and p.exists():
                p.unlink()
                _remove_empty_dirs(p)
                removed += 1
    with JOBS_LOCK:
        JOBS.pop(jid, None)
    save_jobs_soon()
    return jsonify(ok=True, removed_files=removed)


@app.post("/api/jobs/clear")
def clear_jobs():
    uid = me()["id"]
    with JOBS_LOCK:
        for jid in [j.id for j in JOBS.values() if j.status in ("finished", "error", "cancelled") and j.owner == uid]:
            JOBS.pop(jid)
    save_jobs_soon()
    return jsonify(ok=True)


@app.get("/api/jobs/<jid>/files/<int:idx>")
def get_file(jid, idx):
    job = _get(jid)
    if idx < 0 or idx >= len(job.files):
        abort(404)
    p = Path(job.files[idx]).resolve()
    if download_root().resolve() not in p.parents or not p.exists():
        abort(404)
    uid = me()["id"]
    return stream_download(p, lambda: mark_pc_downloaded(str(p), uid))


# ---- Mediathek -------------------------------------------------------------

def _entry(eid, write=False) -> dict:
    e = LIB.get(eid)
    if not e or not Path(e["path"]).exists():
        abort(404)
    mine = e.get("owner") == me()["id"]
    if write and not (mine or is_admin()):
        abort(Response(json.dumps({"error": "Das gehört jemand anderem"}), 403, mimetype="application/json"))
    if not write and not (mine or e.get("shared") or is_admin()):
        abort(404)
    return e


@app.get("/api/library")
def library_list():
    """scope: mine (Standard) · family (geteilte von allen) · all (nur Admin)"""
    scope = request.args.get("scope", "mine")
    uid = me()["id"]
    with LIB_LOCK:
        items = [e for e in LIB.values() if Path(e["path"]).exists()]
        if scope == "family":
            items = [e for e in items if e.get("shared")]
        elif scope == "all" and is_admin():
            owner = request.args.get("owner")
            items = [e for e in items if not owner or e.get("owner") == owner]
        else:
            items = [e for e in items if e.get("owner") == uid]
        items.sort(key=lambda e: e["added"], reverse=True)
        u = me()
        return jsonify(items=[lib_public(e) for e in items], stats=lib_stats(uid), user=user_public(u, private=True),
                       is_admin=is_admin(), usage=user_usage(uid), quota_gb=u.get("quota_gb", 0),
                       cleanup=u.get("cleanup"), cleanup_log=_my_log(20),
                       family_count=sum(1 for e in LIB.values() if e.get("shared") and Path(e["path"]).exists()))


@app.get("/api/library/<eid>/stream")
def library_stream(eid):
    import mimetypes
    e = _entry(eid)
    mt = mimetypes.guess_type(e["path"])[0] or "application/octet-stream"
    if e["path"].lower().endswith(".mkv"):
        mt = "video/webm"   # Chrome spielt die meisten MKV so ab
    return send_file(e["path"], mimetype=mt, conditional=True, max_age=0)


@app.get("/api/library/<eid>/download")
def library_download(eid):
    e = _entry(eid)
    uid = me()["id"]
    return stream_download(Path(e["path"]), lambda: mark_pc_downloaded(e["path"], uid))


@app.post("/api/library/<eid>/pin")
def library_pin(eid):
    e = _entry(eid, write=True)
    body = request.get_json(silent=True) or {}
    with LIB_LOCK:
        e["pinned"] = bool(body.get("pinned", not e.get("pinned")))
        if e["pinned"]:
            e["delete_at"] = None
    lib_save()
    return jsonify(lib_public(e))


@app.post("/api/library/<eid>/share")
def library_share(eid):
    e = _entry(eid, write=True)
    body = request.get_json(silent=True) or {}
    with LIB_LOCK:
        e["shared"] = bool(body.get("shared", not e.get("shared")))
    lib_save()
    return jsonify(lib_public(e))


@app.delete("/api/library/<eid>")
def library_delete(eid):
    _entry(eid, write=True)
    if not lib_delete(eid):
        return err("Datei konnte nicht gelöscht werden (wird sie gerade benutzt?)", 409)
    return jsonify(ok=True)


@app.post("/api/cleanup/run")
def cleanup_run():
    uid = me()["id"]
    removed = janitor_once(only_user=None if is_admin() and request.args.get("all") == "1" else uid)
    return jsonify(removed=removed, library=lib_stats(uid), cleanup_log=_my_log(8))


@app.post("/api/settings")
def update_settings():
    body = request.get_json(silent=True) or {}
    u = me()
    # Eigene Aufräum-Regeln darf jede Person selbst einstellen
    if isinstance(body.get("cleanup"), dict):
        c = dict(u.get("cleanup") or DEFAULT_USER_CLEANUP)
        b = body["cleanup"]
        if "after_pc_download" in b:
            c["after_pc_download"] = bool(b["after_pc_download"])
        for k, hi in (("max_age_days", 3650), ("max_size_gb", 100000)):
            if k in b:
                try:
                    c[k] = max(0, min(float(b[k] or 0), hi))
                except (TypeError, ValueError):
                    return err(f"Ungültiger Wert für {k}")
                if c[k] == int(c[k]):
                    c[k] = int(c[k])
        with USERS_LOCK:
            u["cleanup"] = c
        users_save()
    server_keys = {"max_parallel", "download_dir", "night"} & set(body)
    if server_keys:
        need_admin()
        with SETTINGS_LOCK:
            if "max_parallel" in body:
                SETTINGS["max_parallel"] = max(1, min(int(body["max_parallel"]), 8))
            if "download_dir" in body and body["download_dir"]:
                p = Path(body["download_dir"]).expanduser()
                try:
                    p.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    return err(f"Ordner nicht nutzbar: {e}")
                SETTINGS["download_dir"] = str(p)
            if isinstance(body.get("night"), dict):
                n = dict(SETTINGS.get("night") or {})
                for k in ("start", "end"):
                    v = str(body["night"].get(k, n.get(k, ""))).strip()
                    if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", v):
                        return err("Uhrzeit bitte als HH:MM angeben")
                    n[k] = v
                SETTINGS["night"] = n
            save_settings(SETTINGS)
    JANITOR_WAKE.set()
    with QUEUE_COND:
        QUEUE_COND.notify_all()
    return ping()


_update_lock = threading.Lock()


@app.post("/api/update")
def update_ytdlp():
    need_admin()
    if not _update_lock.acquire(blocking=False):
        return err("Update läuft bereits")
    try:
        if SETTINGS.get("ytdlp_command") or FROZEN:
            cmd = ytdlp_base() + ["-U"]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]"]
        r = subprocess.run(cmd, capture_output=True, timeout=300,
                           **({"creationflags": 0x08000000} if IS_WINDOWS else {}))
        _version_cache.clear()
        out = (r.stdout + r.stderr).decode("utf-8", "replace").strip().splitlines()[-6:]
        return jsonify(ok=r.returncode == 0, ytdlp=ytdlp_version(), output="\n".join(out))
    finally:
        _update_lock.release()


def migrate_owners():
    """Alte Aufträge/Dateien ohne Besitzer gehören dem Admin."""
    aid = admin_user()["id"]
    changed = False
    with LIB_LOCK:
        for e in LIB.values():
            if not e.get("owner") or e["owner"] not in USERS:
                e["owner"] = aid
                changed = True
            e.setdefault("shared", False)
    if changed:
        lib_save()
    for j in JOBS.values():
        if not j.owner or j.owner not in USERS:
            j.owner = aid
    save_jobs_soon()


def main():
    users_load()
    lib_load()
    load_jobs()
    migrate_owners()
    threading.Thread(target=_janitor, daemon=True).start()
    JANITOR_WAKE.set()
    for _ in range(8):
        threading.Thread(target=_worker, daemon=True).start()
    threading.Thread(target=_saver, daemon=True).start()
    host, port = SETTINGS["host"], int(SETTINGS["port"])
    print("=" * 60)
    print(f" Kinbox {APP_VERSION}")
    print(f" Adresse : http://<IP-dieses-PCs>:{port}")
    print(f" Mediathek: http://<IP-dieses-PCs>:{port}/library")
    print(f" Admin-Token: {admin_user()['token']}")
    print(f" Profile : {', '.join(u['avatar'] + ' ' + u['name'] for u in USERS.values())}")
    print(f" Ordner  : {download_root()}")
    print(f" yt-dlp  : {ytdlp_version()}")
    if not has_ffmpeg():
        print(" [!] ffmpeg nicht gefunden – Zusammenführen, MP3 und Zuschneiden gehen dann nicht.")
    if not js_runtime():
        print(" [!] Keine JavaScript-Laufzeit (deno) gefunden – YouTube braucht sie.")
    print("=" * 60)
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=16)
    except ImportError:
        app.run(host=host, port=port, threaded=True)


def setup(mode: str) -> None:
    """Vom Installer aufgerufen: „local“ = nur dieser PC (Standalone), „lan“ = Server fürs Heimnetz."""
    local = mode == "local"
    SETTINGS["host"] = "127.0.0.1" if local else "0.0.0.0"
    save_settings(SETTINGS)
    users_load()
    token, port = admin_user()["token"], int(SETTINGS["port"])
    if IS_WINDOWS:
        # Desktop-Link zur Mediathek; bei „local“ zusätzlich Autostart bei der Anmeldung (ohne Admin/Passwort)
        ps = r"""
$lnk = [Environment]::GetFolderPath('Startup') + '\Kinbox.lnk'
Set-Content -Path ([Environment]::GetFolderPath('Desktop') + '\Kinbox.url') -Value "[InternetShortcut]`r`nURL=$env:KB_URL"
if ($env:KB_LOCAL -eq '1') {
  $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
  $s.TargetPath = $env:KB_PYW; $s.Arguments = $(if ($env:KB_PY) { '"' + $env:KB_PY + '"' } else { '' }); $s.WorkingDirectory = $env:KB_DIR; $s.Save()
} else { Remove-Item $lnk -ErrorAction SilentlyContinue }
"""
        # Kinbox.exe: Autostart in beiden Modi (Heimnetz mit sichtbarem Fenster), sonst pythonw + server.py
        pyw = Path(sys.executable) if FROZEN else Path(sys.executable).with_name("pythonw.exe")
        arg = "" if FROZEN else str(BASE_DIR / "server.py")
        env = {**os.environ, "KB_LOCAL": "1" if local or FROZEN else "0", "KB_PYW": str(pyw), "KB_DIR": str(BASE_DIR),
               "KB_PY": arg,
               "KB_URL": f"http://127.0.0.1:{port}/library" + (f"?token={token}" if local else "")}
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], env=env,
                       creationflags=0x08000000)  # CREATE_NO_WINDOW
        if local and pyw.exists() and not FROZEN:
            subprocess.Popen([str(pyw), str(BASE_DIR / "server.py")], cwd=BASE_DIR,
                             creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    print()
    print(" Browser-Erweiterung -> Einstellungen:")
    print(f"   Adresse: http://{'127.0.0.1' if local else '<IP-dieses-PCs>'}:{port}")
    print(f"   Token  : {token}")
    if local:
        print(" Kinbox laeuft jetzt unsichtbar im Hintergrund und startet bei jeder Anmeldung mit.")
        print(" Mediathek: Desktop-Verknuepfung \"Kinbox\".")


TOOL_DOWNLOADS = {  # offizielle Quellen, jeweils neueste Version
    "yt-dlp.exe": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
    "ffmpeg.exe": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "deno.exe": "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip",
}


def ensure_tools(progress=None) -> None:
    """Kinbox.exe: fehlende Programme beim ersten Start nach tools/ laden."""
    import ssl
    import urllib.request
    import zipfile
    try:  # eigene Zertifikatsliste: frisches Windows (Server) hat die GitHub-Stammzertifikate noch nicht
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = None
    TOOLS_DIR.mkdir(exist_ok=True)
    os.environ["PATH"] = str(TOOLS_DIR) + os.pathsep + os.environ.get("PATH", "")
    for name, url in TOOL_DOWNLOADS.items():
        if (TOOLS_DIR / name).exists():
            continue
        print(f" Lade {name} herunter ...", flush=True)
        tmp = TOOLS_DIR / (name + ".part")
        with urllib.request.urlopen(url, context=ctx, timeout=60) as r, open(tmp, "wb") as f:
            total, done = int(r.headers.get("Content-Length") or 0), 0
            while chunk := r.read(1 << 16):
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(name, done, total)
        if url.endswith(".zip"):
            with zipfile.ZipFile(tmp) as z:
                for m in z.namelist():
                    base = m.rsplit("/", 1)[-1]
                    if base in ("ffmpeg.exe", "ffprobe.exe", "deno.exe"):
                        (TOOLS_DIR / base).write_bytes(z.read(m))
            tmp.unlink()
        else:
            tmp.replace(TOOLS_DIR / name)


def lan_ip() -> str:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))  # schickt nichts, wählt nur die Netzwerkkarte
            return s.getsockname()[0]
    except OSError:
        return "<IP-dieses-PCs>"


def setup_gui() -> None:
    """Kinbox.exe, erster Start: Einrichtungsfenster – Modus wählen, Programme laden, Adresse + Token anzeigen."""
    import ctypes
    import tkinter as tk
    import webbrowser
    from tkinter import ttk
    de = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x07
    L = lambda d, e: d if de else e  # noqa: E731
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # scharf statt verwaschen bei 125 %/150 %
    except Exception:
        pass
    BG, BG2, BG3, LINE, TEXT, MUTED, ACC, ACC2 = ("#121216", "#1b1b21", "#24242c", "#2e2e38", "#ececf1", "#9a9aa8",
                                                  "#7c5cff", "#8f73ff")
    root = tk.Tk()
    root.title(L("Kinbox einrichten", "Kinbox setup"))
    root.configure(bg=BG)
    root.resizable(False, False)
    logo = tk.PhotoImage(file=str(STATIC_DIR / "icon.png"))
    small = logo.subsample(2)
    root.iconphoto(True, logo)
    root.update()
    try:  # dunkle Titelleiste (Windows 10 20H1+/11)
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass
    font = lambda size, bold=False: ("Segoe UI Semibold" if bold else "Segoe UI", size)  # noqa: E731
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("K.Horizontal.TProgressbar", troughcolor=BG3, background=ACC, bordercolor=BG3,
                    lightcolor=ACC, darkcolor=ACC, thickness=10)
    body = tk.Frame(root, bg=BG, padx=40, pady=30)
    body.pack(fill="both", expand=True)
    st = {"mode": "local", "file": "", "done_b": 0, "total_b": 0, "error": None, "ready": False}

    def clear():
        for w in body.winfo_children():
            w.destroy()

    def button(parent, text, cmd, primary=True):
        bg, hover = (ACC, ACC2) if primary else (BG3, LINE)
        b = tk.Label(parent, text=text, font=font(11, True), bg=bg, fg="white" if primary else TEXT,
                     padx=22, pady=9, cursor="hand2")
        b.bind("<Enter>", lambda e: b.config(bg=hover))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        b.bind("<Button-1>", lambda e: cmd())
        return b

    def header(title, sub):
        tk.Label(body, image=small, bg=BG).pack()
        tk.Label(body, text=title, font=font(18, True), bg=BG, fg=TEXT).pack(pady=(10, 2))
        tk.Label(body, text=sub, font=font(10), bg=BG, fg=MUTED, wraplength=460).pack(pady=(0, 18))

    def center():
        root.update_idletasks()
        w, h = root.winfo_reqwidth(), root.winfo_reqheight()
        root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 3}")

    def page_choose():
        clear()
        header(L("Willkommen bei Kinbox", "Welcome to Kinbox"), L("Wie willst du Kinbox nutzen?", "How do you want to use Kinbox?"))
        cards = {}

        def pick(mode):
            st["mode"] = mode
            for m, c in cards.items():
                bg = BG3 if m == mode else BG2
                c.config(bg=bg, highlightbackground=ACC if m == mode else LINE)
                for w in c.winfo_children():
                    w.config(bg=bg)

        for mode, title, text in (
            ("local", L("Nur auf diesem PC", "Just this PC"),
             L("Kinbox läuft unsichtbar im Hintergrund und startet bei jeder Anmeldung mit. Kein Zugriff aus dem Netzwerk.",
               "Kinbox runs invisibly in the background and starts when you sign in. No network access.")),
            ("lan", L("Server fürs Heimnetz", "Server for your home network"),
             L("Handys, Tablets und andere PCs im WLAN können Kinbox nutzen. Die Windows-Firewall fragt einmal nach.",
               "Phones, tablets and other PCs on your Wi-Fi can use Kinbox. Windows Firewall will ask once.")),
        ):
            c = tk.Frame(body, bg=BG2, highlightthickness=2, highlightbackground=LINE, padx=18, pady=14, cursor="hand2")
            c.pack(fill="x", pady=5)
            tk.Label(c, text=title, font=font(12, True), bg=BG2, fg=TEXT, anchor="w").pack(fill="x")
            tk.Label(c, text=text, font=font(10), bg=BG2, fg=MUTED, anchor="w", justify="left",
                     wraplength=430).pack(fill="x", pady=(2, 0))
            for w in (c, *c.winfo_children()):
                w.bind("<Button-1>", lambda e, m=mode: pick(m))
            cards[mode] = c
        pick(st["mode"])
        bar = tk.Frame(body, bg=BG)
        bar.pack(fill="x", pady=(22, 0))
        button(bar, L("Einrichten", "Set up"), page_install).pack(side="right")
        center()

    def work():
        try:
            ensure_tools(lambda name, done, total: st.update(file=name, done_b=done, total_b=total))
            setup(st["mode"])
            # eigener Entpack-Ordner: sonst nutzt der Server den des Fensters, der beim Schließen gelöscht wird
            # (dann fehlt library.html → nur „Kinbox läuft.“)
            env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
            subprocess.Popen([sys.executable], cwd=BASE_DIR, env=env,
                             creationflags=0x00000008 | 0x00000200)  # Server unsichtbar
            st["ready"] = True
        except Exception as e:
            st["error"] = str(e)

    def page_install():
        clear()
        header(L("Kinbox wird eingerichtet …", "Setting up Kinbox …"),
               L("yt-dlp, ffmpeg und deno werden heruntergeladen (ca. 150 MB). Das dauert einen Moment.",
                 "Downloading yt-dlp, ffmpeg and deno (about 150 MB). This takes a moment."))
        info = tk.Label(body, text="", font=font(10), bg=BG, fg=TEXT, anchor="w")
        info.pack(fill="x")
        pb = ttk.Progressbar(body, style="K.Horizontal.TProgressbar", length=460, maximum=100)
        pb.pack(fill="x", pady=(6, 10))
        st.update(error=None, file="")
        threading.Thread(target=work, daemon=True).start()

        def poll():
            if st["error"]:
                return page_error()
            if st["ready"]:
                return page_done()
            if st["file"]:
                mb = lambda n: f"{n / 1e6:.0f} MB"  # noqa: E731
                info.config(text=f"{st['file']}  ·  {mb(st['done_b'])}" + (f" / {mb(st['total_b'])}" if st["total_b"] else ""))
                pb.config(value=st["done_b"] * 100 / st["total_b"] if st["total_b"] else 0)
            else:
                info.config(text=L("Richte ein …", "Configuring …"))
            root.after(100, poll)
        poll()
        center()

    def page_error():
        clear()
        header(L("Das hat nicht geklappt", "That didn't work"),
               L("Prüfe die Internetverbindung und versuch es nochmal.", "Check your internet connection and try again."))
        tk.Label(body, text=st["error"], font=font(9), bg=BG2, fg="#ff6b6b", wraplength=440, justify="left",
                 padx=12, pady=10).pack(fill="x")
        bar = tk.Frame(body, bg=BG)
        bar.pack(fill="x", pady=(22, 0))
        button(bar, L("Nochmal versuchen", "Try again"), page_install).pack(side="right")
        button(bar, L("Zurück", "Back"), page_choose, primary=False).pack(side="right", padx=8)
        center()

    def field(label, value):
        tk.Label(body, text=label, font=font(9, True), bg=BG, fg=MUTED, anchor="w").pack(fill="x", pady=(8, 2))
        row = tk.Frame(body, bg=BG2, highlightthickness=1, highlightbackground=LINE)
        row.pack(fill="x")
        e = tk.Entry(row, font=("Consolas", 11), bg=BG2, fg=TEXT, readonlybackground=BG2, relief="flat", bd=0)
        e.insert(0, value)
        e.config(state="readonly")
        e.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        copy = tk.Label(row, text=L("Kopieren", "Copy"), font=font(9, True), bg=BG3, fg=TEXT, padx=10, pady=4, cursor="hand2")

        def do_copy(_):
            root.clipboard_clear()
            root.clipboard_append(value)
            copy.config(text=L("Kopiert ✓", "Copied ✓"))
            root.after(1500, lambda: copy.winfo_exists() and copy.config(text=L("Kopieren", "Copy")))
        copy.bind("<Button-1>", do_copy)
        copy.pack(side="right", padx=6)

    def page_done():
        clear()
        users_load()
        local, port, token = st["mode"] == "local", int(SETTINGS["port"]), admin_user()["token"]
        header(L("Fertig! Kinbox läuft.", "Done! Kinbox is running."),
               L("Trag Adresse und Token in der Browser-Erweiterung unter Einstellungen ein. "
                 "Kinbox startet ab jetzt automatisch – ein Doppelklick auf Kinbox.exe öffnet die Mediathek.",
                 "Enter the address and token in the browser extension's settings. "
                 "Kinbox now starts automatically – double-click Kinbox.exe to open the library."))
        field(L("Adresse", "Address"), f"http://{'127.0.0.1' if local else lan_ip()}:{port}")
        field("Token", token)
        bar = tk.Frame(body, bg=BG)
        bar.pack(fill="x", pady=(24, 0))
        button(bar, L("Mediathek öffnen", "Open library"),
               lambda: webbrowser.open(f"http://127.0.0.1:{port}/library?token={token}")).pack(side="right")
        button(bar, L("Schließen", "Close"), root.destroy, primary=False).pack(side="right", padx=8)
        center()

    page_choose()
    root.mainloop()
    if not st["ready"]:
        SETTINGS_FILE.unlink(missing_ok=True)  # abgebrochen → beim nächsten Start erneut fragen


def exe_start() -> None:
    """Doppelklick auf Kinbox.exe (ohne Konsole gebaut): läuft schon → Mediathek öffnen; erster Start →
    Einrichtungsfenster; sonst Server unsichtbar starten (Ausgaben in kinbox.log)."""
    import socket
    import webbrowser
    port = int(SETTINGS["port"])
    with socket.socket() as sock:
        running = sock.connect_ex(("127.0.0.1", port)) == 0
    if running:
        users_load()
        webbrowser.open(f"http://127.0.0.1:{port}/library?token={admin_user()['token']}")
        return
    sys.stdout = sys.stderr = open(BASE_DIR / "kinbox.log", "w", encoding="utf-8", buffering=1)
    if FIRST_RUN:
        return setup_gui()
    try:
        ensure_tools()
    except Exception as e:
        print(f" [!] Download fehlgeschlagen: {e}")
        return
    main()


if __name__ == "__main__":
    if sys.argv[1:2] == ["--setup"] and len(sys.argv) > 2:
        setup(sys.argv[2])
    elif FROZEN:
        exe_start()
    else:
        main()
