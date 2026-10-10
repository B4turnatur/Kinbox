# Kinbox

🇬🇧 [English](README.md) · 🇩🇪 Deutsch

**Die Medienkiste für die Familie:** yt-dlp auf einem PC oder Server bei dir zu Hause, bedient über eine Browser-Erweiterung, eine Web-Mediathek und die Teilen-Funktion am Handy – ganz ohne Terminal. Jede Person bekommt ein eigenes Profil.

```
 Browser (Chrome/Edge/Brave/Opera …)            PC/Server im Heimnetz
 ┌────────────────────────────┐   Heimnetz   ┌──────────────────────────┐
 │ Erweiterung „Kinbox"        │ ───────────► │ server.py (Port 8765)    │
 │  • Popup mit allen Optionen │   HTTP+Token │  └─ yt-dlp + ffmpeg + deno│
 │  • „Kinbox"-Button auf      │ ◄─────────── │  → speichert lokal       │
 │    YouTube, TikTok …        │  Fortschritt │  → Mediathek /library    │
 └────────────────────────────┘              └──────────────────────────┘
```

Die Oberfläche ist zweisprachig: Deutsch bei deutschem Browser, sonst Englisch.

## 1. Server einrichten (einmalig)

### Am einfachsten: Kinbox.exe (Windows, ohne Python)

1. Im [neuesten Release](https://github.com/B4turnatur/Kinbox/releases/latest) **`Kinbox.exe`** und **`Kinbox-Extension.zip`** herunterladen.
2. `Kinbox.exe` in einen eigenen Ordner legen, z. B. `C:\Kinbox`, und doppelklicken. Windows warnt eventuell „Der Computer wurde durch Windows geschützt“. Dann auf **Weitere Informationen → Trotzdem ausführen** klicken. Die exe ist nicht signiert.
3. Ein Einrichtungsfenster öffnet sich. **Nur auf diesem PC** oder **Server fürs Heimnetz** wählen und auf **Einrichten** klicken. Kinbox lädt yt-dlp, ffmpeg und deno herunter (ca. 150 MB) und legt sie in `tools\` ab. Beim Heimnetz die Nachfrage der Windows-Firewall mit „Zugriff zulassen“ bestätigen.
4. Das Fenster zeigt **Adresse** und **Token** für die Erweiterung an (mit Kopieren-Knopf). Kinbox startet ab jetzt bei der Anmeldung automatisch. Ein erneuter Doppelklick auf `Kinbox.exe` öffnet die Mediathek.

yt-dlp aktualisierst du in den Einstellungen der Erweiterung mit „yt-dlp aktualisieren“.

### Windows mit Python (install.bat)

1. Den Ordner `server` irgendwohin kopieren, z. B. `C:\Kinbox`.
2. **Rechtsklick auf `install.bat` → „Als Administrator ausführen"**.
   Installiert Python (falls nötig), yt-dlp, Flask, Waitress, ffmpeg und deno.
   Falls Python neu installiert wurde, `install.bat` danach ein zweites Mal starten.
3. Auswählen, wie du Kinbox nutzen willst:
   - **1 = Nur auf diesem PC (Standalone)** – für alle mit nur einem Computer. Kinbox läuft unsichtbar im Hintergrund, startet bei der Anmeldung und ist aus dem Netzwerk nicht erreichbar. Keine Admin-Rechte nötig. Der Installer zeigt den **Token** an. In der Erweiterung als Adresse `http://127.0.0.1:8765` eintragen. Die Desktop-Verknüpfung „Kinbox“ öffnet die Mediathek.
   - **2 = Server fürs Heimnetz** – für Handy und andere PCs. Gibt Port 8765 in der Firewall frei (nur privates Netzwerk) und richtet auf Wunsch den Autostart beim Hochfahren ein (auch ohne Anmeldung). Danach `start.bat` starten. Im Fenster stehen **Token** und Download-Ordner. Die IP des Rechners findest du mit `ipconfig` → „IPv4-Adresse", z. B. `192.168.178.20`.
4. Einmal ab- und wieder anmelden (damit Windows ffmpeg/deno findet).

Umstellen geht jederzeit, indem du `install.bat` erneut startest. Autostart nachträglich: Rechtsklick auf `autostart.bat` → „Als Administrator ausführen". Den Token findest du auch in `settings.json`.

### Linux / macOS

```bash
pip install "yt-dlp[default]" flask waitress   # dazu ffmpeg und deno über den Paketmanager
python3 server/server.py
```

## 2. Erweiterung im Browser installieren

1. `chrome://extensions` öffnen (Edge: `edge://extensions`).
2. Oben rechts **Entwicklermodus** einschalten.
3. **„Entpackte Erweiterung laden"** → den Ordner `extension` auswählen (oder die entpackte `Kinbox-Extension.zip`).
4. Die Einstellungsseite öffnet sich: Adresse `http://192.168.178.20:8765` und Token eintragen → **Speichern & testen**.
5. Tipp: Erweiterung über das Puzzle-Symbol anheften.

## 👨‍👩‍👧 Familie & Profile

Jede Person hat ihren **eigenen Bereich**: eigener Ordner, eigene Mediathek, eigene Warteschlange, eigene Aufräum-Regeln und ein eigener Schlüssel (Token) für Erweiterung und Handy.

**Person hinzufügen (Admin):** Mediathek → dein Profil oben rechts → **👨‍👩‍👧 Familie** → Name, Bild, optional PIN und Speicher-Kontingent → **＋ Hinzufügen** → **✉ Einladen**. Die Einladung enthält einen Link, der die Person direkt anmeldet, plus Adresse und Token für die Browser-Erweiterung – einfach per Messenger schicken.

| | |
|---|---|
| **Profil-Auswahl** | Wie bei Netflix: „Wer schaut?" – mit optionaler PIN (4–8 Ziffern). Nach 8 falschen Versuchen 5 Minuten Pause. |
| **Meine / Familie / Alle** | *Meine* = nur eigene Dateien. *Familie* = was andere mit „👨‍👩‍👧 Mit Familie teilen" freigegeben haben (ansehen & herunterladen, nicht löschen). *Alle* = nur für Admins, mit Filter nach Person. |
| **Eigene Ordner** | `Downloads\Kinbox\Mama\…`, `…\Lena\…` – der Admin behält den Hauptordner |
| **Speicher-Kontingent** | Pro Person einstellbar (z. B. 20 GB). Ist es voll, startet kein neuer Download, bis etwas gelöscht wird. |
| **Aufräumen pro Person** | Jede Person stellt selbst ein, ob und wann *ihre* Dateien gelöscht werden. |
| **Admin-Rechte** | Familie verwalten, Nachtfenster, Server-Einstellungen, yt-dlp aktualisieren. Es können mehrere Admins sein. |
| **Neuer Schlüssel** | Macht alte Einladungslinks und Erweiterungs-Zugänge einer Person ungültig – z. B. wenn ein Handy verloren ging. |

**Datenschutz in der Familie:** Admins können im Bereich *Alle* sämtliche Dateien sehen. Sag das der Familie.

## Was sie kann

| | |
|---|---|
| **Qualität** | Beste, 8K … 144p – mit Größenschätzung pro Stufe, 60 fps bevorzugen |
| **Format** | MP4 / MKV / WebM / MOV, Codec H.264 (läuft überall), H.265, VP9, AV1 |
| **Nur Audio** | MP3, M4A, Opus, FLAC, WAV, Original · Bitrate 96–320 kbps · Lautstärke angleichen |
| **Zuschneiden** | Start/Ende per Regler, Eingabe oder „⏱ jetzt" (übernimmt die Position im laufenden Video). Framegenau oder schnell. |
| **Kapitel** | Einzelne Kapitel auswählen oder jedes Kapitel als eigene Datei |
| **Playlists** | Nur dieses Video, ganze Playlist oder Auswahl wie `1-5,8,10-` |
| **Untertitel** | Sprachen wählen, automatische Untertitel, einbetten oder als .srt |
| **SponsorBlock** | Sponsoren, Intros, Abo-Aufrufe … herausschneiden oder als Kapitel markieren |
| **Umwandeln** | Als **GIF** oder **verkleinern** auf 8 MB (Discord), 15 MB (WhatsApp), 25 MB (E-Mail) … |
| **Musik-Modus** | Interpret und Titel werden sauber aus „Interpret – Titel" gelesen, Cover quadratisch zugeschnitten |
| **Ordnerstruktur** | Alles in einen Ordner, nach Kanal, **Plex/Jellyfin** (Kanal › Season Jahr › Folge) oder Musik (Interpret › Titel) |
| **Nachts laden** | 🌙-Schalter: Download startet erst im Nachtfenster (Standard 01:00–07:00) |
| **Doppelt-Warnung** | Das Popup zeigt „Schon in der Kinbox", wenn das Video schon geladen wurde |
| **Presets** | 9 eingebaute (u. a. WhatsApp, GIF, Musik mit Tags) + beliebig viele eigene |
| **Schnellzugriff** | „Kinbox"-Button unter YouTube-Videos, schwebender Button auf TikTok, Instagram, X und Reddit, Rechtsklick, Tastenkürzel |
| **Benachrichtigung** | wenn fertig – mit Knopf „Auf diesen PC speichern" |

Tastenkürzel: **Alt+Shift+D** Popup · **Alt+Shift+Q** aktuelle Seite sofort laden · **Alt+Shift+M** als MP3. Unter `chrome://extensions/shortcuts` änderbar.

yt-dlp kann über 1.000 Seiten – Popup und Rechtsklick-Menü funktionieren überall.

## 📚 Mediathek – auch am Handy

Im Browser `http://<IP-des-Servers>:8765` öffnen (oder in der Erweiterung auf 📚).

- Alle Downloads mit Vorschaubild, Suche, Filter und Sortierung; direkt abspielen
- **⬇ Auf dieses Gerät** lädt die Datei aufs Handy/den PC · **📌 Behalten** schützt vor dem Aufräumen
- **＋ Link**: Link einfügen, Art wählen, fertig
- Am Handy: „Zum Startbildschirm hinzufügen" – dann wirkt sie wie eine App

**Direkt aus „Teilen" am Handy:** In der Mediathek unter „＋ Link" → „📱 Direkt aus der Teilen-Funktion" stehen Adresse und Anleitung für die iPhone-App „Kurzbefehle" bzw. die Android-App „HTTP Shortcuts".

## 🧹 Automatisch aufräumen

| Option | Was passiert |
|---|---|
| Nach dem Laden aufs Gerät löschen | Sobald eine Datei komplett auf PC/Handy geladen wurde, wird sie nach einer Minute vom Server gelöscht. |
| Nach X Tagen löschen | Dateien, die älter als X Tage sind, werden entfernt |
| Speicherlimit in GB | Wird der Ordner größer, werden die ältesten Dateien zuerst gelöscht |

Gelöscht werden **nur Dateien, die Kinbox selbst geladen hat** – und nie welche mit 📌.

## Server-Einstellungen (`server/settings.json`)

Wird beim ersten Start angelegt. Nach Änderungen den Server neu starten.

| Schlüssel | Bedeutung |
|---|---|
| `port` | Standard 8765 |
| `token` | Schlüssel des Admin-Profils (alle Profile stehen in `users.json`) |
| `download_dir` | Zielordner, z. B. `"D:\\Medien\\Downloads"` (doppelte Backslashes!) |
| `max_parallel` | Wie viele Downloads gleichzeitig laufen |
| `cookies_file` | Pfad zu einer `cookies.txt` für altersbeschränkte oder Mitglieder-Videos |
| `ffmpeg_location` | Ordner mit `ffmpeg.exe`, falls ffmpeg nicht gefunden wird |
| `extra_args` | Zusätzliche yt-dlp-Argumente für jeden Download |
| `site_args` | Zusätzliche Argumente nur für bestimmte Seiten (enthält schon einen TikTok-Fix) |
| `night` | Nachtfenster, z. B. `{"start": "01:00", "end": "07:00"}` |

**Cookies (für Instagram und den YouTube-Bot-Check):** Mit einer Erweiterung wie „Get cookies.txt LOCALLY" eine `cookies.txt` exportieren, auf den Server legen, Pfad in `cookies_file` eintragen – fertig. Kinbox nutzt sie dann automatisch für alle Downloads (auch vom Handy). Statt der Datei darf auch ihr Ordner angegeben werden.

## Wenn etwas nicht geht

- **„Server nicht erreichbar"** – Läuft `start.bat`? Stimmt die IP? `install.bat` als Admin ausgeführt (Firewall)? Im Browser `http://IP:8765` öffnen. Das Netzwerk muss in Windows als **privat** eingestuft sein.
- **„Falscher Token"** – Token aus dem Server-Fenster bzw. `settings.json` kopieren.
- **YouTube-Downloads scheitern plötzlich** – Einstellungen → „yt-dlp aktualisieren".
- **„Sign in to confirm you're not a bot" / Instagram „login required"** – Cookies einrichten (siehe oben).
- **Kein „Kinbox"-Button auf TikTok & Co.** – Seite neu laden. Rechtsklick → „Mit Kinbox herunterladen" und das Popup funktionieren immer.
- **Video spielt in der Mediathek nicht** – Format (z. B. MKV/H.265) kann der Browser nicht; „Auf dieses Gerät" laden oder MP4 wählen.
- **Fehlerdetails** – in der Warteschlange beim Auftrag auf „Log" klicken.

## Umstieg vom alten „NAS-Downloader"

Kinbox hieß früher NAS-Downloader. `server.py`, `static/` und die `.bat`-Dateien ersetzen, `settings.json`, `users.json`, `jobs.json` und `library.json` behalten. Der Download-Ordner bleibt, wo er war. Danach `install.bat` und ggf. `autostart.bat` einmal neu ausführen (alte Firewall-Regel und Aufgabe werden automatisch entfernt) und in `chrome://extensions` die alte Erweiterung entfernen und den neuen `extension`-Ordner laden.

## Sicherheit & Rechtliches

Der Server ist für dein Heimnetz gedacht. Gib Port 8765 **nicht** im Router frei – für unterwegs besser ein VPN wie Tailscale oder WireGuard.
Lade nur Inhalte herunter, die du herunterladen darfst; beachte die Nutzungsbedingungen der jeweiligen Seiten und das Urheberrecht.

## Lizenz

[MIT](LICENSE). Kinbox nutzt [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ffmpeg](https://ffmpeg.org) und [deno](https://deno.com) – diese werden getrennt installiert und haben eigene Lizenzen.
