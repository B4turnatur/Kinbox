// Kinbox – Übersetzung. Die Oberfläche ist auf Deutsch geschrieben; ist der Browser
// nicht auf Deutsch eingestellt, übersetzt diese Datei alle sichtbaren Texte ins Englische.
// Liegt identisch in extension/lib/i18n.js und server/static/i18n.js – beide gleich halten!
// Neue Texte: unten in EN (feste Texte) bzw. PAT (Texte mit Platzhaltern {0}, {1} …) ergänzen.
// Führende/abschließende Symbole (⬇ ✓ … : ?) werden automatisch beibehalten.
(() => {
  const EN = {
    // ---- allgemein
    "Einstellungen": "Settings", "Einstellungen öffnen": "Open settings", "Mediathek": "Library", "Mediathek öffnen": "Open library",
    "Speichern": "Save", "Abbrechen": "Cancel", "Löschen": "Delete", "Schließen": "Close", "Übernehmen": "Apply", "Ändern": "Change",
    "Entfernen": "Remove", "Kopieren": "Copy", "Kopiert": "Copied", "Gespeichert": "Saved", "Gelöscht": "Deleted", "Umbenennen": "Rename",
    "Exportieren": "Export", "Importieren": "Import", "Zurücksetzen": "Reset", "Fehler": "Error", "Unbekannter Fehler": "Unknown error",
    "Ja": "Yes", "Nein": "No", "Aus": "Off", "aus": "off", "An": "On", "Alle": "All", "alle": "all", "Keine": "None", "Auswahl": "Selection",
    "Name": "Name", "Bild": "Image", "Datei": "File", "Dateien": "Files", "Ordner": "Folder", "Farbe": "Color", "Link": "Link", "Hilfe": "Help",
    "Video": "Video", "Videos": "Videos", "Audio": "Audio", "Bilder": "Images", "Download": "Download", "Herunterladen": "Download",
    "Warteschlange": "Queue", "Qualität": "Quality", "Format": "Format", "Original": "Original", "Codec": "Codec", "Automatisch": "Automatic",
    "Breite": "Width", "Bitrate": "Bitrate", "Start": "Start", "Ende": "End", "Sprachen": "Languages", "Vorschau": "Preview",
    "Vorschaubild": "Thumbnail", "Von": "From", "von": "of", "Bis": "To", "Tagen": "days", "Beste": "Best", "Wartet": "Waiting",
    "Fertig": "Done", "Abgebrochen": "Cancelled", "Lädt": "Loading", "Lädt herunter": "Downloading", "Lädt Infos": "Fetching info",
    "Verarbeitet": "Processing", "Unterbrochen": "Interrupted", "Hallo": "Hello", "Meine": "Mine", "Neueste": "Newest", "Älteste": "Oldest",
    "Größte": "Largest", "Cookies": "Cookies", "Admin": "Admin", "Token": "Token", "Profil": "Profile", "gerade eben": "just now",
    "heute": "today", "gestern": "yesterday", "Server nicht erreichbar.": "Server not reachable.", "Verbinde …": "Connecting …",
    "Verbunden!": "Connected!", "Server": "Server", "server": "server",

    // ---- Popup
    "Noch kein Server eingerichtet.": "No server set up yet.", "Link einfügen oder Seite öffnen …": "Paste a link or open a page …",
    "Infos laden": "Load info", "MP4 (empfohlen)": "MP4 (recommended)", "H.264 (kompatibel)": "H.264 (compatible)", "AV1 (klein)": "AV1 (small)",
    "60 fps bevorzugen": "Prefer 60 fps", "Danach umwandeln": "Convert afterwards", "Verkleinern": "Shrink", "Bilder pro Sekunde": "Frames per second",
    "25 (flüssig)": "25 (smooth)", "Tipp: vorher zuschneiden – GIFs gehen bis 90 Sekunden.": "Tip: trim first – GIFs can be up to 90 seconds.",
    "25 MB · E-Mail": "25 MB · Email", "Original zusätzlich behalten": "Also keep the original", "VBR beste": "VBR best",
    "Musik-Modus: Interpret & Titel sauber, quadratisches Cover": "Music mode: clean artist & title, square cover",
    "Lautstärke angleichen (loudnorm)": "Normalize volume (loudnorm)", "TikTok: nur die Musik (ohne Stimme)": "TikTok: music only (no voice)", "nur Musik": "music only",
    "Auf einer Profilseite (Instagram, TikTok) wird das Profilbild gespeichert.": "On a profile page (Instagram, TikTok) the profile picture is saved.", "Vorschaubild speichern als": "Save thumbnail as", "Zuschneiden": "Trim",
    "ganzes Video": "whole video", "Aktuelle Position im Video übernehmen": "Use the current position in the video", "jetzt": "now",
    "Framegenau schneiden (etwas langsamer)": "Frame-accurate cut (a bit slower)", "Beim Ziehen im Video mitspringen": "Seek the video while dragging",
    "Kapitel": "Chapters", "Jedes Kapitel als eigene Datei": "Each chapter as its own file", "Playlist": "Playlist", "nur dieses Video": "only this video",
    "Nur dieses": "Only this one", "Ganze Playlist": "Whole playlist", "ganze Playlist": "whole playlist", "Untertitel": "Subtitles",
    "Untertitel herunterladen": "Download subtitles", "(Komma-getrennt, z. B. de,en oder en.*)": "(comma-separated, e.g. en,de or en.*)",
    "Automatische Untertitel verwenden": "Use automatic subtitles", "In Video einbetten (sonst als Datei)": "Embed in video (otherwise as a file)",
    "Als Kapitel markieren": "Mark as chapters", "Herausschneiden": "Cut out", "Sponsor": "Sponsor", "Eigenwerbung": "Self-promotion",
    "Intro": "Intro", "Abspann": "Outro", "Füller": "Filler", "Musik: Nicht-Musik": "Music: non-music", "Erweitert": "Advanced",
    "Vorschaubild einbetten": "Embed thumbnail", "Metadaten einbetten (Titel, Kanal …)": "Embed metadata (title, channel …)",
    "Kapitelmarken einbetten": "Embed chapter markers", "Vorschaubild zusätzlich als Datei": "Also save thumbnail as a file",
    "Beschreibung als .txt": "Description as .txt", "Info-JSON speichern": "Save info JSON", "Ordnerstruktur": "Folder structure",
    "Alles in einen Ordner": "Everything in one folder", "Nach Kanal / Account": "By channel / account",
    "Plex / Jellyfin (Kanal › Jahr › Folge)": "Plex / Jellyfin (channel › year › episode)", "Musik (Interpret › Titel)": "Music (artist › title)",
    "Unterordner auf dem Server": "Subfolder on the server", "z. B. Musik/Playlists": "e.g. Music/Playlists", "Dateiname": "File name",
    "Tempolimit": "Speed limit", "Parallele Teile": "Parallel fragments",
    "Schon geladene Videos überspringen (Archiv)": "Skip videos already downloaded (archive)", "Auf diesen PC": "To this PC", "Auf PC": "To PC",
    "Download startet erst im Nachtfenster (Einstellungen)": "Download only starts in the night window (settings)", "Nachts": "At night",
    "nachts": "at night", "Preset": "Preset", "Als Preset": "As preset", "Erledigte entfernen": "Remove finished", "Noch keine Downloads.": "No downloads yet.",
    "Öffne ein Video und klick auf „Herunterladen\".": "Open a video and click \"Download\".", "Kein Video auf dieser Seite": "No video on this page",
    "Öffne ein Video oder füge oben einen Link ein.": "Open a video or paste a link above.", "eingebettet": "embedded", "Beste Qualität": "Best quality",
    "beste Qualität": "best quality", "Standard": "Default", "Aktuelle Einstellungen speichern": "Save current settings",
    "Auch als Standard verwenden": "Also use as default", "Als Standard gespeichert": "Saved as default", "Ungültiger Link": "Invalid link",
    "Der Link muss mit http:// oder https:// beginnen.": "The link must start with http:// or https://", "Lade Infos …": "Loading info …",
    "Livestream – wird ab jetzt aufgenommen, bis er endet.": "Livestream – will be recorded from now until it ends.",
    "In Mediathek ansehen": "View in library", "Verfügbar": "Available", "Keine manuellen Untertitel": "No manual subtitles",
    "automatische Sprachen": "automatic languages", "Kein laufendes Video im Tab gefunden.": "No playing video found in the tab.",
    "Lade Playlist …": "Loading playlist …", "Bitte zuerst einen Link eingeben.": "Please enter a link first.",
    "Mindestens ein Kapitel auswählen.": "Select at least one chapter.", "Welche Playlist-Einträge? z. B. 1-5,8": "Which playlist items? e.g. 1-5,8",
    "Wird gesendet …": "Sending …", "Zur Warteschlange hinzugefügt": "Added to queue", "Kein Server eingestellt": "No server configured",
    "Auf dem Server fehlt ffmpeg – MP3, Zuschneiden und Zusammenführen funktionieren nicht.": "ffmpeg is missing on the server – MP3, trimming and merging won't work.",
    "Auf dem Server fehlt deno – YouTube funktioniert evtl. nicht zuverlässig.": "deno is missing on the server – YouTube may not work reliably.",
    "Geplant für die Nacht": "Scheduled for the night", "Datei gelöscht": "File deleted", "Jetzt starten": "Start now", "Nochmal": "Retry",
    "Datei löschen": "Delete file", "Wirklich löschen?": "Really delete?", "Log ausblenden": "Hide log", "Log": "Log",
    "Datei auf dem Server gelöscht": "File deleted on the server", "Herunterladen …": "Download …",

    // ---- Einstellungen der Erweiterung
    "Kinbox – Einstellungen": "Kinbox – Settings", "1. Mit deinem Server verbinden": "1. Connect to your server",
    "Die Adresse und den Token zeigt": "The address and token are shown by", "beim Start auf dem Server an (Token steht auch in": "when it starts on the server (the token is also in",
    "Server-Adresse": "Server address", "aus settings.json": "from settings.json", "Speichern & testen": "Save & test",
    "Unterwegs-Adresse (optional)": "Away address (optional)", "(über die Unterwegs-Adresse)": "(via the away address)",
    "Z. B. die Tailscale-Adresse. Antwortet die Server-Adresse nicht, nimmt Kinbox automatisch diese.": "E.g. the Tailscale address. If the server address doesn't respond, Kinbox uses this one automatically.", "2. Server": "2. Server",
    "(nur Admin)": "(admin only)", "Profile für die Familie verwaltest du in der": "You manage family profiles in the", "Mediathek → ⚙ → Familie": "library → ⚙ → Family",
    "Download-Ordner auf dem Server": "Download folder on the server", "Gleichzeitige Downloads": "Simultaneous downloads", "yt-dlp aktualisieren": "Update yt-dlp",
    "YouTube ändert oft etwas – wenn Downloads plötzlich scheitern, hilft meist ein Update.": "YouTube changes things often – if downloads suddenly fail, an update usually helps.",
    "Automatisch aufräumen": "Automatic clean-up", "Gilt nur für": "Applies only to", "deine": "your",
    "Dateien. Jederzeit umschaltbar und frei kombinierbar. Gelöscht werden nur Dateien, die Kinbox selbst geladen hat – und nie welche, die du in der Mediathek mit „Behalten“ markiert hast.": "files. Can be switched any time and combined freely. Only files Kinbox downloaded itself are deleted – never ones you marked \"Keep\" in the library.",
    "Löschen, sobald ich die Datei auf PC oder Handy geladen habe": "Delete once I've downloaded the file to my PC or phone",
    "Nach so vielen Tagen löschen": "Delete after this many days", "(0 = aus)": "(0 = off)", "Speicherlimit in GB": "Storage limit in GB",
    "(0 = aus, älteste zuerst)": "(0 = off, oldest first)", "Nachts laden": "Download at night",
    "Downloads mit „Nachts\" starten erst in diesem Zeitfenster (gilt für die ganze Familie).": "Downloads marked \"At night\" only start in this time window (applies to the whole family).",
    "Jetzt aufräumen": "Clean up now", "3. Verhalten": "3. Behavior", "4. Aussehen": "4. Appearance", "Aussehen": "Appearance", "5. Presets": "5. Presets", "Stil": "Style", "Klassisch": "Classic", "Schlicht": "Clean", "Papier": "Paper", "Terminal": "Terminal",
    "Violett": "Violet", "Blau": "Blue", "Petrol": "Teal", "Grün": "Green", "Orange": "Orange", "Rot": "Red", "Pink": "Pink", "Graphit": "Graphite", "„Kinbox\"-Button unter YouTube-Videos anzeigen": "Show the \"Kinbox\" button below YouTube videos",
    "„Kinbox\"-Button über Videos auf TikTok, Instagram, X und Reddit": "\"Kinbox\" button on videos on TikTok, Instagram, X and Reddit",
    "Benachrichtigung, wenn ein Download fertig ist": "Notify me when a download is finished", "Tastenkürzel": "Keyboard shortcuts",
    "Popup ·": "popup ·", "sofort laden ·": "download now ·", "als MP3.": "as MP3.", "4. Presets": "4. Presets",
    "Eigene Presets legst du im Popup über „★ Als Preset\" an. Dort kannst du sie auch als Standard festlegen.": "Create your own presets in the popup via \"★ As preset\". You can also set one as default there.",
    "Standard-Einstellungen zurücksetzen": "Reset default settings",
    "Nur im Heimnetz nutzen – den Port nicht im Router freigeben. Für unterwegs lieber VPN (z. B. WireGuard/Tailscale).": "Use only on your home network – don't forward the port on your router. For on the go, use a VPN (e.g. WireGuard/Tailscale).",
    "Zurückgesetzt": "Reset", "Bitte die Adresse des Servers eintragen.": "Please enter the server's address.", "fehlt": "missing", "vorhanden": "available",
    "Angemeldet als": "Signed in as", "Der Token stimmt nicht. Kopiere ihn aus dem Server-Fenster oder aus settings.json.": "The token is wrong. Copy it from the server window or from settings.json.",
    "Prüfe: Läuft start.bat auf dem Server? Stimmt die IP? Ist Port 8765 in der Windows-Firewall freigegeben (install.bat als Admin)?": "Check: is start.bat running on the server? Is the IP right? Is port 8765 open in the Windows firewall (install.bat as admin)?",
    "nach dem Laden aufs Gerät": "after downloading to a device", "Gespeichert. Automatisches Aufräumen ist aus.": "Saved. Automatic clean-up is off.",
    "Nichts zu löschen – alles innerhalb deiner Regeln.": "Nothing to delete – everything is within your rules.", "Aktualisiere … (kann dauern)": "Updating … (may take a while)",
    "Video → GIF": "Video → GIF", "Eingebaut ·": "Built-in ·", "Als Standard": "As default", "Neuer Name:": "New name:",
    "Die Datei konnte nicht gelesen werden.": "The file could not be read.",

    // ---- Hintergrund & Seiten-Buttons
    "Mit Kinbox herunterladen": "Download with Kinbox", "Standard-Einstellungen": "Default settings", "Mit Optionen…": "With options…",
    "Mit Optionen …": "With options …", "Mit Optionen … (zuschneiden, Kapitel …)": "With options … (trim, chapters …)", "Mehr Optionen": "More options",
    "Download fehlgeschlagen": "Download failed", "Download fertig": "Download finished", "Auf diesen PC speichern": "Save to this PC",
    "Speichern fehlgeschlagen": "Saving failed", "Unbekannte Nachricht": "Unknown message", "1080p MP4 (überall abspielbar)": "1080p MP4 (plays everywhere)",
    "720p klein": "720p small", "Musik mit Tags & Cover": "Music with tags & cover", "Musik verlustfrei (FLAC)": "Lossless music (FLAC)",
    "WhatsApp-tauglich (≤ 15 MB)": "WhatsApp-ready (≤ 15 MB)", "Podcast (MP3, ohne Sponsoren)": "Podcast (MP3, no sponsors)",
    "Kein Server eingestellt – öffne die Einstellungen.": "No server configured – open the settings.", "Zeitüberschreitung – Server antwortet nicht.": "Timeout – server isn't responding.",
    "Server nicht erreichbar. Läuft er und stimmt die Adresse?": "Server not reachable. Is it running and is the address right?",
    "Kinbox: Erweiterung wurde neu geladen – bitte Seite aktualisieren.": "Kinbox: the extension was reloaded – please refresh the page.",
    "Adresse nicht gefunden": "Address not found", "Video-Adresse nicht gefunden – öffne das Video einzeln": "Video address not found – open the video on its own",
    "Seite neu laden": "Reload page",

    // ---- Mediathek
    "Mediathek · Kinbox": "Library · Kinbox", "Wer schaut": "Who's watching", "PIN eingeben": "Enter PIN", "Anderes Profil": "Other profile",
    "Profil & Einstellungen": "Profile & settings", "Familie": "Family", "Alle Personen": "Everyone", "Suchen": "Search", "Auf dieses Gerät": "To this device",
    "Link herunterladen": "Download a link", "Was": "What", "Video – beste Qualität": "Video – best quality", "Video – 1080p (überall abspielbar)": "Video – 1080p (plays everywhere)",
    "Video – 720p klein": "Video – 720p small", "FLAC verlustfrei": "FLAC lossless", "Podcast (ohne Sponsoren)": "Podcast (no sponsors)",
    "Erst nachts laden": "Download at night", "Direkt aus der Teilen-Funktion am Handy": "Straight from your phone's share menu",
    "Diese Adresse ruft der Kurzbefehl auf –": "The shortcut calls this address –", "wird durch den geteilten Link ersetzt. Sie enthält": "is replaced by the shared link. It contains",
    "persönlichen Schlüssel, Downloads landen also in deinem Bereich.": "personal key, so downloads land in your area.", "Android": "Android", "iPhone": "iPhone",
    "App „HTTP Shortcuts\" → ＋ → Create from scratch → Methode GET, obige Adresse, [LINK] durch eine globale „Static Variable\" mit „Allow Receiving Value from Share Dialog\" ersetzen.": "App \"HTTP Shortcuts\" → ＋ → Create from scratch → method GET, the address above, replace [LINK] with a global \"Static Variable\" with \"Allow Receiving Value from Share Dialog\".",
    "App „Kurzbefehle\" → neuer Kurzbefehl → „Im Share-Sheet anzeigen\" (URLs) → Aktion „URL\" mit obiger Adresse, [LINK] durch „Kurzbefehleingabe\" ersetzen → „Inhalte von URL abrufen\".": "App \"Shortcuts\" → new shortcut → \"Show in Share Sheet\" (URLs) → action \"URL\" with the address above, replace [LINK] with \"Shortcut Input\" → \"Get Contents of URL\".",
    "Mein Profil": "My profile", "Aufräumen": "Clean-up", "PIN (4–8 Ziffern, leer = ohne PIN)": "PIN (4–8 digits, empty = no PIN)", "unverändert": "unchanged",
    "PIN entfernen": "Remove PIN", "Browser-Erweiterung einrichten": "Set up the browser extension",
    "In den Einstellungen der Erweiterung diese beiden Werte eintragen:": "Enter these two values in the extension's settings:", "Profil wechseln": "Switch profile",
    "Dateien. Jederzeit umschaltbar und kombinierbar. Dateien mit „Behalten“ werden nie automatisch gelöscht.": "files. Can be switched any time and combined. Files marked \"Keep\" are never deleted automatically.",
    "Löschen, nachdem ich die Datei auf PC/Handy geladen habe": "Delete after I've downloaded the file to my PC/phone", "Nach Tagen löschen (0 = aus)": "Delete after days (0 = off)",
    "Speicherlimit in GB (0 = aus)": "Storage limit in GB (0 = off)", "Zuletzt aufgeräumt": "Recently cleaned up",
    "Jede Person hat einen eigenen Bereich, eine eigene Warteschlange und eigene Aufräum-Regeln. Über „Einladen\" bekommt jemand einen Link, der ihn direkt anmeldet.": "Everyone has their own area, their own queue and their own clean-up rules. \"Invite\" gives someone a link that signs them in directly.",
    "Person hinzufügen": "Add person", "PIN (optional)": "PIN (optional)", "Speicher-Kontingent in GB (0 = unbegrenzt)": "Storage quota in GB (0 = unlimited)",
    "Auch Admin (darf Familie & Server verwalten)": "Also admin (may manage family & server)", "Hinzufügen": "Add", "Bei allen aufräumen": "Clean up for everyone",
    "Bitte Profil wählen": "Please choose a profile", "Weitere Personen legt der Admin unter ⚙ → Familie an.": "The admin adds more people under ⚙ → Family.",
    "Deine Dateien werden automatisch gelöscht": "Your files are deleted automatically", "ändern": "change", "einschalten": "turn on",
    "Automatisches Aufräumen ist": "Automatic clean-up is", "– deine Dateien bleiben, bis du sie löschst.": "– your files stay until you delete them.",
    "Nichts gefunden.": "Nothing found.", "Noch nichts geteilt.": "Nothing shared yet.",
    "Öffne eine deiner Dateien und tippe auf „Mit Familie teilen“.": "Open one of your files and tap \"Share with family\".",
    "Noch nichts heruntergeladen.": "Nothing downloaded yet.", "Tippe auf „＋ Link“ oder nutze die Browser-Erweiterung.": "Tap \"＋ Link\" or use the browser extension.",
    "Wird gleich gelöscht": "Will be deleted soon", "Wird nie automatisch gelöscht": "Never deleted automatically", "Mit der Familie geteilt": "Shared with the family",
    "Keine Vorschau": "No preview", "Dieses Format kann der Browser nicht abspielen – lade die Datei herunter.": "The browser can't play this format – download the file.",
    "Geteilt": "Shared", "Mit Familie teilen": "Share with family", "Behalten (an)": "Keep (on)", "Behalten": "Keep",
    "Die ganze Familie sieht das jetzt": "The whole family can see this now", "Nur noch für dich sichtbar": "Now only visible to you",
    "Normal – darf aufgeräumt werden": "Normal – may be cleaned up", "Wird nachts geladen": "Will be downloaded at night", "Wird heruntergeladen …": "Downloading …",
    "keine PIN": "no PIN", "(Hauptordner)": "(main folder)", "Nichts zu löschen": "Nothing to delete", "Nichts zu löschen – alle halten ihre Regeln ein": "Nothing to delete – everyone is within their rules",
    "Einladen": "Invite", "Bearbeiten": "Edit", "Neuer Schlüssel": "New key", "Wirklich? Dateien behalten": "Really? Keep files", "und Dateien löschen": "and delete files",
    "Einladung kopiert – per WhatsApp o. ä. schicken": "Invitation copied – send it via WhatsApp or similar", "Einladung kopieren:": "Copy invitation:",
    "Neuer Schlüssel – bitte neu einladen": "New key – please invite again", "Wirklich?": "Really?", "keine (optional)": "none (optional)", "entfernen": "remove", "markieren": "mark", "Eingebaut": "Built-in", "Original-Audio": "Original audio", "Musik-Tags": "Music tags", "(du)": "(you)", "Alter Link & Erweiterung hören auf zu funktionieren": "The old link & extension stop working", "(Admin)": "(admin)",

    // ---- Server-Meldungen
    "Ungültige URL": "Invalid URL", "Ungültige Playlist-Auswahl (Beispiel: 1-5,8,10)": "Invalid playlist selection (example: 1-5,8,10)",
    "Dateinamen-Vorlage darf keine absoluten Pfade oder '..' enthalten": "The file name template must not contain absolute paths or '..'",
    "Unbekanntes Audioformat": "Unknown audio format", "Ungültige Audio-Bitrate": "Invalid audio bitrate", "Unbekanntes Bildformat": "Unknown image format",
    "Unbekannter Video-Codec": "Unknown video codec", "Unbekannter Container": "Unknown container", "Ungültige Qualität": "Invalid quality", "Unbekannter Modus": "Unknown mode",
    "Das Ende muss nach dem Start liegen": "The end must be after the start", "Ungültige Untertitel-Sprachen": "Invalid subtitle languages",
    "Unbekannte Umwandlung": "Unknown conversion", "GIF und Verkleinern gehen nur im Video-Modus": "GIF and shrinking only work in video mode",
    "Ungültiger Zeitpunkt": "Invalid time", "Ungültiges Tempolimit (z. B. 5M oder 500K)": "Invalid speed limit (e.g. 5M or 500K)",
    "Server wurde neu gestartet": "Server was restarted", "Video und Ton zusammenführen": "Merging video and audio", "Audio umwandeln": "Converting audio",
    "Metadaten schreiben": "Writing metadata", "Untertitel einbetten": "Embedding subtitles", "Abschnitte entfernen": "Removing segments",
    "Kapitel aufteilen": "Splitting chapters", "Container umwandeln": "Converting container", "Bild umwandeln": "Converting image",
    "Untertitel umwandeln": "Converting subtitles", "Kein Vorschaubild gefunden": "No thumbnail found", "Lädt Fotos": "Downloading photos", "Keine Fotos gefunden": "No photos found",
    "gallery-dl fehlt – bitte „pip install gallery-dl“ ausführen": "gallery-dl is missing – please run “pip install gallery-dl”",
    "Zu viele falsche Versuche – bitte 5 Minuten warten.": "Too many wrong attempts – please wait 5 minutes.",
    "Die PIN muss aus 4–8 Ziffern bestehen.": "The PIN must have 4–8 digits.", "auf Gerät geladen": "downloaded to device", "GIF erstellen": "Creating GIF",
    "Videolänge unbekannt – Verkleinern nicht möglich": "Video length unknown – can't shrink", "Verkleinern (1/2)": "Shrinking (1/2)", "Verkleinern (2/2)": "Shrinking (2/2)",
    "Falscher oder fehlender Token": "Wrong or missing token", "Nur für den Admin": "Admin only", "nicht gefunden": "not found", "eigene Einstellung": "own setting",
    "Profil nicht gefunden": "Profile not found", "Falsche PIN": "Wrong PIN", "Bitte einen Namen angeben": "Please enter a name", "Diesen Namen gibt es schon": "This name already exists",
    "Ungültiges Kontingent": "Invalid quota", "Es muss mindestens einen Admin geben": "There must be at least one admin",
    "Du kannst dein eigenes Profil nicht löschen": "You can't delete your own profile", "Zeitüberschreitung beim Abrufen der Infos": "Timeout while fetching info",
    "Kein Link gefunden": "No link found", "Auftrag läuft noch": "Job is still running", "Erst abbrechen, dann löschen": "Cancel first, then delete",
    "Das gehört jemand anderem": "That belongs to someone else", "Datei konnte nicht gelöscht werden (wird sie gerade benutzt?)": "File could not be deleted (is it in use?)",
    "Uhrzeit bitte als HH:MM angeben": "Please enter the time as HH:MM", "Update läuft bereits": "Update already running",
    "Für Instagram, altersbeschränkte Videos und den YouTube-Bot-Check: im Browser einloggen, mit der Erweiterung „Get cookies.txt LOCALLY“ exportieren und hier hochladen. Mehrere Seiten nacheinander hochladen geht.": "For Instagram, age-restricted videos and YouTube's bot check: log in in your browser, export with the \"Get cookies.txt LOCALLY\" extension and upload here. You can upload several sites one after another.",
    "cookies.txt hochladen": "Upload cookies.txt", "Keine Cookies eingerichtet": "No cookies set up", "Cookies gespeichert": "Cookies saved",
    "Alle Cookies entfernen?": "Remove all cookies?", "Datei zu groß": "File too large",
    "Das ist keine cookies.txt – bitte mit „Get cookies.txt LOCALLY“ exportieren": "This isn't a cookies.txt – please export it with \"Get cookies.txt LOCALLY\"",
    "Kinbox-Update": "Kinbox update", "Jetzt aktualisieren": "Update now", "Suche nach Updates …": "Checking for updates …",
    "Lade Update …": "Downloading update …", "Kinbox startet neu …": "Kinbox is restarting …",
    "Kinbox jetzt aktualisieren? Der Server startet dafür kurz neu.": "Update Kinbox now? The server will restart briefly.",
    "Kinbox antwortet nicht – bitte Seite neu laden": "Kinbox isn't responding – please reload the page",
    "Erst laufende Downloads abwarten, dann aktualisieren": "Wait for running downloads to finish, then update",
    "Kinbox ist schon aktuell": "Kinbox is already up to date",
    // ---- Android-App
    "Aufs Handy": "To phone", "Willkommen bei Kinbox": "Welcome to Kinbox",
    "Verbinde die App einmal mit deiner Kinbox zu Hause – danach kannst du Videos aus jeder App über „Teilen“ laden.": "Connect the app to your Kinbox at home once – then you can download videos from any app via \"Share\".",
    "Lass dir einen Einladungslink schicken – der Admin erstellt ihn in der Mediathek unter ⚙ → Familie → Einladen.": "Ask for an invite link – the admin creates it in the library under ⚙ → Family → Invite.",
    "Tippe in WhatsApp & Co. lange auf den Link → Teilen → Kinbox.": "In WhatsApp & co., long-press the link → Share → Kinbox.",
    "Oder kopiere den Link und tippe hier:": "Or copy the link and tap here:", "Link aus der Zwischenablage einfügen": "Paste link from clipboard",
    "Link von Hand eingeben": "Enter link manually", "Verbinden": "Connect", "Oder Adresse und Token einzeln:": "Or address and token separately:",
    "Funktioniert nur im WLAN zu Hause.": "Only works on the home Wi-Fi.", "Android-App einrichten": "Set up Android app",
    "1. „Kinbox.apk“ aus dem": "1. Get \"Kinbox.apk\" from the", "neuesten Release": "latest release", "aufs Handy laden und installieren.": "onto your phone and install it.",
    "2. Hier am Handy auf „Mit der App verbinden“ tippen.": "2. On your phone, tap \"Connect with the app\" here.", "Mit der App verbinden": "Connect with the app",

    // ---- Bearbeiten (Mediathek), Video + Audio, schwebender Knopf
    "Als Audio speichern": "Save as audio", "In MP4 umwandeln": "Convert to MP4", "Ton entfernen": "Remove sound", "Drehen": "Rotate",
    "Lautstärke angleichen": "Normalize volume", "Format ändern": "Change format", "Zielgröße": "Target size", "Richtung": "Direction",
    "90° nach rechts": "90° clockwise", "90° nach links": "90° counter-clockwise", "Original behalten": "Keep the original", "Starten": "Start", "Jetzt": "Now",
    "Regler ziehen oder abspielen und an der richtigen Stelle auf „Jetzt“ tippen.": "Drag the slider, or play it and tap \"Now\" at the right moment.",
    "Speichert nur den Ton – z. B. als MP3 für Voicemod, OBS oder Soundboards.": "Saves only the sound – e.g. as MP3 for Voicemod, OBS or soundboards.",
    "MP4 (H.264) spielt überall – OBS, Handy, Fernseher.": "MP4 (H.264) plays everywhere – OBS, phone, TV.",
    "GIFs gehen bis 90 Sekunden – vorher zuschneiden.": "GIFs can be up to 90 seconds – trim first.", "Für WhatsApp, Discord oder E-Mail.": "For WhatsApp, Discord or email.",
    "Macht zu leise oder zu laute Dateien gleichmäßig laut.": "Makes files that are too quiet or too loud evenly loud.",
    "Wird bearbeitet – erscheint gleich in der Mediathek": "Editing – it will show up in the library shortly",
    "Unbekannte Bearbeitung": "Unknown edit", "Das geht mit dieser Datei nicht": "That doesn't work with this file", "Bitte Start oder Ende angeben": "Please enter a start or end",
    "Ungültiger Winkel": "Invalid angle", "Diese Datei hat keinen Ton": "This file has no sound", "Die Datei gibt es nicht mehr": "The file no longer exists",
    "Bearbeitet": "Editing", "Audio-Datei erstellen": "Creating audio file", "Video + MP3 (beides)": "Video + MP3 (both)",
    "Zusätzlich als Audio-Datei (MP3 – Format wie unter „Audio“)": "Also save as audio file (MP3 – format as under \"Audio\")",
    "Knopf in andere Ecke": "Move button to another corner", "Auf dieser Seite ausblenden": "Hide on this site", "Position über dem Video": "Position on the video",
    "Oben links": "Top left", "Oben rechts": "Top right", "Unten links": "Bottom left", "Unten rechts": "Bottom right", "Anzeigen auf": "Show on",
  };
  // Texte mit Platzhaltern – {0}, {1} … werden selbst wieder übersetzt (z. B. „heute“).
  const PAT = [
    ["Audio-Datei: {0}", "Audio file: {0}"], ["Profilbild {0}", "Profile picture {0}"],
    ["{0} – Instagram-Profilbilder gehen nur mit Instagram-Cookies", "{0} – Instagram profile pictures only work with Instagram cookies"],
    ["Eingerichtet für: {0}", "Set up for: {0}"],
    ["Aufs Handy ({0})", "To phone ({0})"], ["Lädt herunter ({0})", "Downloading ({0})"], ["Lädt Fotos ({0})", "Downloading photos ({0})"], ["gallery-dl nicht gefunden: {0}", "gallery-dl not found: {0}"],
    ["Kein Video gefunden – Foto-Beitrag? Einfach „Herunterladen“ drücken, Kinbox lädt dann die Bilder. ({0})", "No video found – a photo post? Just press “Download”, Kinbox will fetch the images. ({0})"], ["Interner Fehler: {0}", "Internal error: {0}"], ["yt-dlp beendet mit Code {0}", "yt-dlp exited with code {0}"],
    ["Ungültige Zeitangabe: {0} (Format z. B. 1:23 oder 01:02:03)", "Invalid time: {0} (format e.g. 1:23 or 01:02:03)"],
    ["Ungültiger Wert für {0}", "Invalid value for {0}"], ["{0} muss zwischen {1} und {2} liegen", "{0} must be between {1} and {2}"],
    ["Dein Speicher ist voll ({0} GB). Lösche etwas in der Mediathek oder frag den Admin.", "Your storage is full ({0} GB). Delete something in the library or ask the admin."],
    ["älter als {0} Tage", "older than {0} days"], ["Speicherlimit {0} GB", "storage limit {0} GB"], ["ffmpeg-Fehler: {0}", "ffmpeg error: {0}"],
    ["Für ein GIF ist das Video zu lang ({0} s). Bitte vorher auf max. 90 s zuschneiden.", "The video is too long for a GIF ({0} s). Please trim it to max. 90 s first."],
    ["Zu lang für {0} MB – bei dieser Größe gehen etwa {1} Minuten. Bitte zuschneiden.", "Too long for {0} MB – that size fits about {1} minutes. Please trim."],
    ["Ordner nicht nutzbar: {0}", "Folder not usable: {0}"],
    ["Neue Version {0} verfügbar (installiert: {1})", "New version {0} available (installed: {1})"], ["Kinbox {0} ist aktuell", "Kinbox {0} is up to date"],
    ["Kinbox {0} ist installiert", "Kinbox {0} is installed"], ["Update fehlgeschlagen: {0}", "Update failed: {0}"], ["GitHub nicht erreichbar: {0}", "GitHub unreachable: {0}"],
    ["Preset „{0}\" gespeichert", "Preset \"{0}\" saved"], ["Playlist · {0} Videos · {1}", "Playlist · {0} videos · {1}"], ["Playlist · {0} Videos", "Playlist · {0} videos"],
    ["Schon in der Kinbox ({0})", "Already in Kinbox ({0})"], ["vor {0} Tagen", "{0} days ago"], ["vor {0} Min.", "{0} min ago"], ["vor {0} Std.", "{0} h ago"],
    ["+ {0} weitere", "+ {0} more"], ["{0} · Verbunden · {1}", "{0} · Connected · {1}"], ["Verbunden · {0}", "Connected · {0}"], ["Ziel: {0}", "Destination: {0}"],
    ["noch {0}", "{0} left"], ["{0} Dateien", "{0} files"], ["Alle aufs Gerät ({0})", "All to this device ({0})"], ["{0} Dateien werden geladen …", "Downloading {0} files …"], ["Auf PC ({0})", "To PC ({0})"], ["Videos in „{0}\"", "Videos in \"{0}\""],
    ["✓ Zur Warteschlange hinzugefügt: {0}", "✓ Added to queue: {0}"],
    ["{0} Dateien · {1}", "{0} files · {1}"], ["Gespeichert. Automatisch löschen: {0}", "Saved. Delete automatically: {0}"], ["{0} Dateien gelöscht.", "{0} files deleted."],
    ["{0} Dateien gelöscht", "{0} files deleted"], ["Gespeichert. Ordner: {0} · parallel: {1}", "Saved. Folder: {0} · parallel: {1}"],
    ["Audio · {0}", "Audio · {0}"], ["Video → max. {0} MB", "Video → max. {0} MB"], ["Video · {0} · {1}", "Video · {0} · {1}"],
    ["nach {0} Tagen", "after {0} days"], ["ab {0} GB (älteste zuerst)", "above {0} GB (oldest first)"], ["ab {0} GB", "above {0} GB"],
    ["{0} von {1} GB genutzt", "{0} of {1} GB used"], ["{0} genutzt von {1} GB · Ordner:", "{0} used of {1} GB · Folder:"], ["{0} genutzt · Ordner:", "{0} used · Folder:"],
    ["{0} · Ordner", "{0} · Folder"], ["{0} Downloads aktiv", "{0} downloads active"], ["{0} entfernt – Dateien gehören jetzt dir", "{0} removed – the files are yours now"],
    ["{0} entfernt, {1} Dateien gelöscht", "{0} removed, {1} files deleted"], ["{0} angelegt – jetzt auf „✉ Einladen“ tippen", "{0} added – now tap \"✉ Invite\""],
  ];
  const lang = /^de\b/i.test((navigator.languages && navigator.languages[0]) || navigator.language || "") ? "de" : "en";
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pats = PAT.map(([de, en]) => [new RegExp("^" + esc(de).replace(/\\\{(\d)\\\}/g, "([\\s\\S]+?)") + "$"), en]);
  const SPLIT = /^([^\p{L}\p{N}(]*)([\s\S]*?)([^\p{L}\p{N})]*)$/u;
  const cache = new Map();

  function lookup(t) {
    if (EN[t] !== undefined) return EN[t];
    const [, a, c, z] = t.match(SPLIT);
    if (c !== t && EN[c] !== undefined) return a + EN[c] + z;
    for (const [re, en] of pats) {
      const m = t.match(re) || (c !== t && c.match(re));
      if (m) return (m[0] === t ? "" : a) + en.replace(/\{(\d)\}/g, (_, i) => tr(m[+i + 1])) + (m[0] === t ? "" : z);
    }
    return null;
  }
  // Übersetzt einen Text (Leerzeichen am Rand bleiben erhalten). Unbekanntes bleibt unverändert.
  function tr(s) {
    if (lang === "de" || typeof s !== "string") return s;
    const t = s.trim();
    if (!t || !/\p{L}/u.test(t)) return s;
    if (!cache.has(t)) cache.set(t, lookup(t));
    const r = cache.get(t);
    return r == null ? s : s.replace(t, r);
  }

  const ATTRS = ["title", "placeholder", "aria-label", "alt"];
  const SKIP = /^(SCRIPT|STYLE|TEXTAREA|CODE|PRE)$/;
  function attrs(el) {
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (v) { const n = tr(v); if (n !== v) el.setAttribute(a, n); }
    }
  }
  // Übersetzt ein Element samt Inhalt (für Seiten-Buttons der Content-Skripte).
  function walk(n) {
    if (n.nodeType === 3) {
      if (SKIP.test(n.parentNode?.nodeName || "") || n.nodeValue.length > 600) return;   // nie Code anfassen
      const v = tr(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; return;
    }
    if (n.nodeType !== 1 || SKIP.test(n.tagName) || n.getAttribute("translate") === "no") return;
    attrs(n);
    for (const c of n.childNodes) walk(c);
  }

  globalThis.t = tr;
  globalThis.translateEl = walk;
  globalThis.LANG = lang;

  // Seiten mit <script src="…i18n.js" data-auto> werden komplett und laufend übersetzt.
  const me = typeof document !== "undefined" && document.currentScript;
  if (lang === "en" && me && me.hasAttribute("data-auto")) {
    const start = () => {
      document.documentElement.lang = "en";
      document.title = tr(document.title);
      walk(document.body);
      new MutationObserver((ms) => {
        for (const m of ms) {
          if (m.type === "childList") m.addedNodes.forEach(walk);
          else if (m.type === "characterData") walk(m.target);
          else attrs(m.target);
        }
      }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    };
    document.body ? start() : document.addEventListener("DOMContentLoaded", start);
  }
})();
