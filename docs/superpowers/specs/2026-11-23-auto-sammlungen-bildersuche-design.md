# Automatische Sammlungen + KI-Bildersuche – Design

Stand: 2026-11-23 · Ziel-Versionen: Teil 1 = 3.22.0, Teil 2 = 3.23.0

> **Teil 1 umgesetzt (3.22.0). Teil 2 (KI-Bildersuche) am 2026-11-23 vom Nutzer verworfen – nicht bauen.** Gründe: Modell ~606 MB + ~1 GB RAM fürs NAS, versteht vor allem Englisch; Hashtags + Auto-Sammlungen reichen.

## Warum
Der Nutzer hat z. B. viele GTA-Videos. Er möchte sie wiederfinden („gta“ suchen) und gesammelt an einem Ort sehen („wie ein Unterordner GTA“), **ohne dass „GTA“ im Titel stehen muss**. Bei seinen Videos steht „GTA“ meist in Hashtags/Beschreibung/Kanal – das wertet Kinbox heute nicht aus (yt-dlp liefert es, Kinbox wirft es weg). Für Videos ganz ohne passenden Text: Bildersuche wie Immich („Smart Search“ mit CLIP).

## Ziele
- **Teil 1 – Hashtags + automatische Sammlungen** (zuerst, eigenes Release)
  - Beim Download Hashtags, Kategorien, Beschreibung speichern; Mediathek-Suche findet darüber.
  - Eine Sammlung kann Stichwörter haben („gta, gta5, gtav, gtaonline, los santos“). Passende Videos landen automatisch darin – neue sofort, vorhandene beim Speichern der Stichwörter.
  - Alte Einträge: Admin-Knopf lädt die fehlenden Infos einmal nach (yt-dlp ohne Download).
- **Teil 2 – KI-Bildersuche (optional, Admin-Schalter, aus als Standard)**
  - Lokales CLIP-Modell (wie Immich) rechnet pro Video/Bild Fingerabdrücke aus mehreren Standbildern.
  - Suche „gta“ zeigt zusätzlich Videos, die *so aussehen*, auch ohne passenden Text.
  - Läuft komplett lokal, ohne Internet (außer einmaligem Modell-Download) und ohne Kosten.

## Nicht-Ziele
- Dateien auf der Platte wirklich in Ordner verschieben (Sammlung = virtueller Ordner; Dateien bleiben, wo sie sind).
- Automatische Sammlungen per KI-Bild (CLIP liefert nur „ähnlich“, keine saubere Ja/Nein-Grenze).
- Sprach-KI (Claude/Ollama), Gesichtserkennung, Musik-Einordnung.
- Eigene Änderungen an der Android-App (sie zeigt library.html, bekommt alles automatisch).

## Anti-Ziele (wäre ein Fehlschlag, auch wenn es „funktioniert“)
- Ein manuell aus einer Auto-Sammlung entferntes Video taucht wieder auf.
- Kinder sehen über eine Auto-Sammlung fremde, nicht geteilte Videos.
- KI-Bildersuche macht Kinbox für alle langsamer/größer, auch wenn sie aus ist; NAS hängt beim Indexieren.
- Nachladen alter Infos löst eine YouTube-Sperre aus (zu viele Anfragen auf einmal).

## Ansätze (besprochen, gewählt: B + D)
- A – nur Hashtags speichern + mitsuchen: einfach, aber kein „Ordner“.
- **B – A + Auto-Sammlungen nach Stichwörtern (gewählt, Teil 1)**: genau, kostenlos, offline; Stichwörter einmal pro Sammlung eintragen.
- C – Sprach-KI ordnet ein: Kosten/Internet (Claude) oder zu langsam auf dem NAS (Ollama), kann irren → verworfen.
- **D – Bildersuche mit CLIP wie Immich (gewählt, Teil 2)**: findet auch ohne Text, aber nur „ähnlich sortiert“, groß (Modell ~ einige 100 MB, RAM ~1 GB).

## Teil 1 – Details

### Infos speichern
- `_build_args()`: Print-Vorlage `@@I` um `tags,categories,description` ergänzen.
- `_read_ytdlp()` → `lib_add()`: neue Felder im Eintrag:
  - `tags`: Liste aus yt-dlp-`tags` + `categories` + `#hashtags` aus der Beschreibung, klein geschrieben, ohne `#`, ohne Doppelte, max. 50 × 60 Zeichen.
  - `desc`: Beschreibung, max. 2000 Zeichen.
  - Bei vorhandenem Eintrag (Neu-Laden) Felder aktualisieren.
- `lib_public()`: `tags` mitliefern, `desc` gekürzt auf 300 Zeichen (Mediathek-Liste soll nicht MB-groß werden).
- Foto-Beiträge (gallery-dl, `_photo_meta()`): Beschreibung/Hashtags ebenso übernehmen, soweit vorhanden.

### Suche
- library.html (Filter ~Zeile 827): Heuhaufen um `tags` + `desc` erweitern. Player-Infos (`#pMeta`) optional Hashtags als kleine Chips (Klick = danach suchen) – Builder-Entscheidung, nice to have.

### Auto-Sammlungen
- Sammlung in users.json bekommt optional `words: [..]` (max. 20, je max. 40 Zeichen, klein) und `skip: [ids]` (manuell entfernte).
- Treffer-Regel (`coll_match(entry, words)`): Wort/Phrase trifft, wenn es am **Wortanfang** im Text aus Titel + Kanal + tags + desc + Ordnername vorkommt (Groß/klein egal). „gta“ trifft „#gta5“ und „GTA V“, nicht „agta“.
- Wer: nur Einträge, die die Person lesen darf **und** die ihr gehören oder geteilt sind – auch beim Admin (sonst landen Kinder-Videos in der Admin-Sammlung). Rechteprüfung wie `_readable()`.
- Wann:
  - `lib_add()` (neuer/aktualisierter Eintrag) → alle Personen mit Stichwort-Sammlungen prüfen, Treffer anhängen (außer in `skip`).
  - Stichwörter speichern (`POST /api/collections/<cid>` mit `words`) → ganze Mediathek der Person durchgehen.
  - Nach dem Nachladen alter Infos → wie oben.
- Manuell entfernen (`remove`) aus einer Stichwort-Sammlung → id in `skip`. Manuell hinzufügen → aus `skip` raus.
- Eintrag gelöscht → verschwindet wie heute (items werden beim Ausliefern gefiltert).
- UI: Sammlungs-Dialog/Leiste bekommt Feld „Automatisch füllen mit Stichwörtern“ (kommagetrennt) + Hinweis „N Videos gefunden“. Sammlungen mit Stichwörtern bekommen ein kleines Icon (z. B. ✨/Zauberstab-Linienicon in icons.svg, beide Kopien).
- Neue Sammlung direkt mit Stichwörtern anlegen: `POST /api/collections` nimmt `words`.

### Alte Einträge nachladen
- Admin → ⚙ → Server: Knopf „Hashtags für alte Videos nachladen“ + Fortschritt („120 / 800“).
- `POST /api/library/refresh-meta` (need_admin) startet Hintergrund-Thread; `GET` liefert Stand. Pro Eintrag ohne `meta_ok` mit `url`: `yt-dlp --skip-download -J`-artig (nur die nötigen Felder per `--print`), mit `cookie_args()` + `site_args`, Timeout 60 s, **2–3 s Pause** zwischen Einträgen, eins nach dem anderen. Erfolg → `tags/desc` setzen, `meta_ok=1`; Fehler (gelöscht/privat) → `meta_ok=-1`, nicht erneut versuchen. Abbrechbar, übersteht Neustart nicht (einfach erneut drücken).
- Foto-Alben/Edit-Ergebnisse/hochgeladene Dateien ohne Link überspringen.

### Migration
- Alte library.json ohne `tags/desc` bleibt gültig (Felder fehlen = leer). Alte Sammlungen ohne `words` = normale Sammlung.

## Teil 2 – Details (KI-Bildersuche)

### Einschalten
- Einstellung `smart_search` (bool, Standard aus), Admin → Server → „KI-Bildersuche (wie Immich)“ mit Erklärung („läuft lokal, braucht ~1 GB RAM, erstes Durchsuchen dauert“).
- Beim Einschalten: Abhängigkeiten prüfen/holen, Modell laden, Indexieren starten. Ausschalten: Indexieren stoppt, Modell aus dem Speicher; Fingerabdrücke bleiben liegen (Knopf „Daten löschen“).

### Abhängigkeiten (pro Installationsart)
- Nur `onnxruntime` + `numpy`. Kein torch, kein Pillow nötig (ffmpeg liefert fertige 224×224-RGB-Pixel als rawvideo), Tokenizer in reinem Python (CLIP-BPE aus der Tokenizer-Datei des Modells).
- Python-Installation (install.bat/Linux): beim Einschalten per pip nachinstallieren wie `ensure_gallerydl()`.
- Docker: im Image mitinstallieren (amd64 + arm64 Wheels vorhanden – Builder prüft).
- exe: in release.yml mit in die exe packen (exe wird größer) – Builder misst die Größe; wenn deutlich > 60 MB extra, Nutzer fragen.
- Modell: einmalig von Hugging Face nach `DATA_DIR/models/<modell>/` laden, mit Fortschritt. Vorschlag: Immichs ONNX-Export `immich-app/ViT-B-32__openai` (getrennte Bild-/Text-Teile, MIT-Lizenz). **Builder prüft Dateiaufbau, Größe und Lizenz**, bevor er es fest einträgt.

### Indexieren
- Hintergrund-Thread, immer nur ein Eintrag zur Zeit, niedrige Priorität (wie `STRIP_LOCK`), pausiert während Downloads laufen.
- Video: 8 Standbilder gleichmäßig verteilt (ffmpeg, kurze Seite 224 + Mitte zuschneiden). Bild/GIF: 1 Bild. Audio: Cover falls vorhanden, sonst überspringen.
- Speicher: Fingerabdrücke pro Eintrag (8 × 512 Zahlen, float16 ≈ 8 KB) in `DATA_DIR/smart/<modell>.npy` + ID-Liste, gespeichert gebündelt (wie `lib_save_soon()`). Modellwechsel = neuer Index.
- Neue Downloads nach `lib_add()` einreihen; `lib_delete()`/`lib_prune_missing()` räumen mit weg.
- Fortschritt in Admin → Server („Bildersuche: 340 / 1200“), in `/api/ping` oder eigener Route.

### Suchen
- `GET /api/library/smart?q=…` → Text-Fingerabdruck → Kosinus-Ähnlichkeit, Wert pro Eintrag = bestes Standbild. Nur Einträge, die die Person lesen darf (wie `library_list()`), Top 60 über Mindestwert (Builder stimmt den Wert mit echten GTA-/Nicht-GTA-Videos ab).
- library.html: bei Suche ≥ 2 Zeichen und `smart_search` an, entprellt (~400 ms), unter den normalen Treffern ein Abschnitt „Sieht so aus (KI)“ mit Treffern, die nicht schon oben stehen.
- Hinweis in der Oberfläche: englische Suchwörter funktionieren am besten (das Modell versteht vor allem Englisch; Spielnamen wie „GTA“, „Minecraft“ gehen in jeder Sprache).
- Text-Modell bleibt geladen, solange eingeschaltet; Bild-Modell nach 10 min ohne Indexier-Arbeit freigeben.

## Allgemein (beide Teile)
- Rechte: jede neue Route prüft `me()`/`is_admin()`/`need_admin()` wie bestehende.
- UI-Texte Deutsch + `extension/lib/i18n.js` (EN, PAT) → nach `server/static/i18n.js` kopieren → `node tests/test_i18n.mjs`; alert/prompt in `t()`.
- Versionen: `APP_VERSION`; Erweiterung `manifest.json` nur wegen i18n erhöhen.
- README.md + README.de.md: Abschnitt „Automatische Sammlungen“ / „KI-Bildersuche“.
- Tests (neu): `tests/test_autocoll.py` (Treffer-Regel Wortanfang, skip, Rechte Kind/Admin/geteilt, Migration, Nachladen mit nachgebautem yt-dlp), `tests/test_smart.py` (Tokenizer gegen Referenz-IDs, Indexieren mit echtem ffmpeg, Rechte bei Suche, Aufräumen; Modell-Test nur wenn Modell vorhanden). Alle bestehenden Tests grün. Browser-Test gegen Demo-Server.

## Dem Builder überlassen
- Genaues Layout von Stichwort-Feld und KI-Abschnitt (im Stil der bestehenden Dialoge, Handy-Breite 375 px prüfen).
- Mindestwert der Ähnlichkeit, Zahl der Standbilder (8 ist Startwert).
- Wie Hashtag-Chips im Player aussehen (oder ob sie entfallen).
- Speicherformat der Fingerabdrücke, solange es abwärtskompatibel ist und Löschen sauber klappt.
