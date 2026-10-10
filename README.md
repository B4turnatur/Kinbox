# Kinbox

🇬🇧 English · 🇩🇪 [Deutsch](README.de.md)

**The family media box:** a self-hosted [yt-dlp](https://github.com/yt-dlp/yt-dlp) server for any PC on your home network. You use it through a browser extension, a web library and your phone's share menu, with no terminal needed. Everyone in the family gets their own profile.

```
 Browser (Chrome/Edge/Brave/Opera …)            PC/server at home
 ┌────────────────────────────┐ home network ┌──────────────────────────┐
 │ "Kinbox" extension          │ ───────────► │ server.py (port 8765)    │
 │  • popup with every option  │  HTTP+token  │  └─ yt-dlp + ffmpeg + deno│
 │  • "Kinbox" button on       │ ◄─────────── │  → saves to local disk   │
 │    YouTube, TikTok …        │   progress   │  → web library /library  │
 └────────────────────────────┘              └──────────────────────────┘
```

The UI is shown in German or English, depending on your browser language.

## Features

- **Video:** best quality up to 8K, MP4/MKV/WebM/MOV, H.264/H.265/VP9/AV1, prefer 60 fps, size estimate per quality
- **Audio:** MP3, M4A, Opus, FLAC, WAV, 96–320 kbps, loudness normalization, **music mode** (clean artist/title tags, square cover)
- **Trim** with sliders or "⏱ now" (takes the position of the video playing in your tab), **chapters**, **playlists** (`1-5,8,10-`), **subtitles**, **SponsorBlock**
- **Convert** to GIF or shrink to 8 MB (Discord), 15 MB (WhatsApp), 25 MB (email) …
- **Folder layouts:** flat, by channel, **Plex/Jellyfin** (channel › season year › episode) or music (artist › title)
- **Download at night** (scheduled window), duplicate warning, 9 built-in presets plus your own
- **One-click buttons** on YouTube, TikTok, Instagram, X and Reddit, right-click menu, keyboard shortcuts, notifications with "Save to this PC"
- **Web library** (works great on phones, installable as a PWA): search, filter, play, download to the device, 📌 keep
- **Family profiles:** "Who's watching?" with optional PIN, a folder, library, queue and clean-up rules for each person, sharing with the family, storage quotas, invite links, multiple admins
- **Automatic clean-up** per person: after downloading to a device, after X days, or above a size limit
- **Share from your phone** via the iOS Shortcuts app or Android's "HTTP Shortcuts"

yt-dlp supports 1,000+ sites, and the popup and right-click menu work on all of them.

## 1. Install the server (once)

### Windows

1. Copy the `server` folder anywhere, e.g. `C:\Kinbox`.
2. **Right-click `install.bat` → "Run as administrator".**
   It installs Python (if needed), yt-dlp, Flask, Waitress, ffmpeg and deno, and opens port 8765 in the firewall (private networks only).
   If Python was just installed, run `install.bat` a second time.
3. Sign out and back in once, so Windows finds ffmpeg/deno.
4. Double-click `start.bat`. The window shows the **token** and the download folder.
5. Find the PC's IP address: `ipconfig` → "IPv4 Address", e.g. `192.168.178.20`.

**Start automatically at boot:** right-click `autostart.bat` → "Run as administrator". The server then runs invisibly in the background, even when nobody is signed in. The token is in `settings.json`.

> The installer scripts are in German. They only show a few short status messages.

### Linux / macOS

```bash
pip install "yt-dlp[default]" flask waitress   # plus ffmpeg and deno from your package manager
python3 server/server.py
```

## 2. Install the browser extension

1. Open `chrome://extensions` (Edge: `edge://extensions`).
2. Turn on **Developer mode** (top right).
3. **"Load unpacked"** → select the `extension` folder.
4. The settings page opens. Enter the address (`http://192.168.178.20:8765`) and the token, then click **Save & test**.
5. Tip: pin the extension via the puzzle icon.

Shortcuts: **Alt+Shift+D** popup · **Alt+Shift+Q** download the current page · **Alt+Shift+M** as MP3 (change them at `chrome://extensions/shortcuts`).

## 👨‍👩‍👧 Family & profiles

**Add a person (admin):** library → your profile (top right) → **Family** → name, picture, optional PIN and quota → **＋ Add** → **✉ Invite**. The invitation contains a link that signs the person in directly, plus the address and token for the extension.

- *Mine* = your own files · *Family* = files others shared · *All* = admins only
- Each person gets their own subfolder (`Downloads/Kinbox/<name>`); the admin keeps the main folder
- **New key** invalidates a person's old links and extension access (e.g. a lost phone)
- **Privacy:** admins can see everyone's files under *All*. Let your family know.

## Server settings (`server/settings.json`)

This file is created on first start. Restart the server after editing it.

| Key | Meaning |
|---|---|
| `port` | default 8765 |
| `token` | admin profile key (all profiles live in `users.json`) |
| `download_dir` | target folder, e.g. `"D:\\Media\\Downloads"` |
| `max_parallel` | simultaneous downloads |
| `cookies_file` | path to a `cookies.txt` for age-restricted/members-only videos, Instagram, or YouTube's bot check |
| `ffmpeg_location` | folder containing ffmpeg if it isn't on the PATH |
| `extra_args` | extra yt-dlp arguments for every download |
| `site_args` | extra arguments for specific sites (includes a TikTok fix) |
| `night` | night window, e.g. `{"start": "01:00", "end": "07:00"}` |

**Cookies:** export a `cookies.txt` with an extension like "Get cookies.txt LOCALLY", put it on the server, set `cookies_file` – that's it. Kinbox then uses them automatically for every download (phone shortcuts included). You may also point it at the folder containing `cookies.txt`.

## Troubleshooting

- **"Server not reachable":** is `start.bat` running? Is the IP right? Did you run `install.bat` as admin (firewall)? Open `http://IP:8765` in a browser. On Windows the network must be set to **private**.
- **YouTube downloads suddenly fail:** Settings → "Update yt-dlp".
- **"Sign in to confirm you're not a bot" / Instagram "login required":** set up cookies (see above).
- **No "Kinbox" button on TikTok etc.:** reload the page. The right-click menu and the popup always work.
- **A video won't play in the library:** the browser can't play that format (e.g. MKV/H.265). Download it to the device instead, or choose MP4.
- **Error details:** queue → "Log" on the job.

## Security & legal

Kinbox is meant for your home network. **Do not** forward port 8765 on your router. To use it on the go, use a VPN such as Tailscale or WireGuard.
Only download content you're allowed to download, and respect the sites' terms of service and copyright law.

## Development

No build step. `server/server.py` is a single-file Flask app. `server/static/library.html` is the web library. `extension/` is a plain Manifest V3 extension.
Translations live in `extension/lib/i18n.js`. `server/static/i18n.js` must be an identical copy. Run `node tests/test_i18n.mjs` to check both.

## License

[MIT](LICENSE). Kinbox uses [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org) and [deno](https://deno.com). They are installed separately and come with their own licenses.
