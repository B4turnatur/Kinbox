# Auto-Sammlungen (Teil 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kinbox merkt sich Hashtags/Kategorie/Beschreibung, die Suche findet darüber, und Sammlungen mit Stichwörtern füllen sich automatisch (z. B. „GTA“).

**Architecture:** Alles in `server/server.py` (neuer Abschnitt `# ---- Auto-Sammlungen` direkt nach „Favoriten & Sammlungen“) + `server/static/library.html`. Daten: Eintrag in library.json bekommt `tags`, `desc`, `meta_ok`; Sammlung in users.json bekommt `words`, `skip`. Kein neues Paket.

**Tech Stack:** Python 3.12, Flask, yt-dlp (Unterprozess), Vanilla-JS.

**Spec:** `docs/superpowers/specs/2026-11-23-auto-sammlungen-bildersuche-design.md` (nur Teil 1; Teil 2 bekommt einen eigenen Plan nach Release 3.22.0)

## Global Constraints
- Windows ist Zielsystem, Linux muss laufen. Keine neuen Abhängigkeiten.
- `tags`: klein, ohne `#`, ohne Doppelte, max. 50 Stück × 60 Zeichen. `desc`: max. 2000 Zeichen gespeichert, `lib_public()` liefert max. 300.
- `words`: max. 20 Stück, je 2–40 Zeichen, klein, ohne führendes `#`.
- Treffer nur am Wortanfang (Regex `(?<!\w)` + escaptes Wort), Groß/klein egal.
- Auto-Sammlung nimmt nur Einträge, deren `owner` die Person ist oder die `shared` sind – auch beim Admin.
- Nachladen: eins nach dem anderen, `REFRESH_WAIT = 2.5` s Pause, Timeout 60 s, nur Admin.
- Alte library.json/users.json ohne neue Felder bleiben gültig. `POST /api/collections/<cid>` ohne `words` antwortet weiter genau `{id, name, items}` (test_organize prüft das) – `words`/`skip` nur im Objekt, wenn gesetzt.
- UI-Texte DE + `extension/lib/i18n.js` (EN, PAT) → nach `server/static/i18n.js` kopieren; prompt/confirm/toast-Texte in `t()`.
- Versionen: `APP_VERSION` 3.22.0, `extension/manifest.json` +0.0.1 (nur i18n).

## Review Focus
- Nutzer nimmt ein Video aus einer Auto-Sammlung → beim nächsten Download/Stichwort-Speichern kommt es **nicht** zurück (Task 2, Test `skip`).
- Kind-Video (privat) und Admin-Sammlung „GTA“ → landet nicht beim Admin; wird es geteilt, landet es drin (Task 2, Test Rechte + Share).
- Video und MP3 vom selben Link → Nachladen fragt den Link nur einmal ab und füllt beide (Task 3, Test zählt Aufrufe).
- Gelöschtes/privates Video beim Nachladen → `meta_ok=-1`, zweiter Lauf fragt es nicht erneut (Task 3).
- Beschreibung mit Zeilenumbrüchen/Emoji/sehr lang in der `@@I`-Zeile → JSON bleibt lesbar, Eintrag hat `desc` ≤ 2000 (Task 1).

---

### Task 1: Hashtags, Kategorie, Beschreibung speichern

**Files:**
- Modify: `server/server.py` – `_build_args()` (Print-Vorlage Zeile ~243), `_read_ytdlp()` (@@I ~841, nichts entfernen außer wie bisher), `lib_add()` (~1464), `lib_public()` (~1526), `_photo_meta()` (~1218, liefert zusätzlich `tags`/`description` aus gallery-dl-Metadaten, falls Felder `tags`/`hashtags`/`description`/`desc` da sind)
- Test: `tests/test_autocoll.py` (neu, Aufbau wie `tests/test_organize.py`)

**Interfaces:**
- Produces: `meta_tags(meta: dict) -> list[str]` (aus `meta["tags"]`, `meta["categories"]`, `#hashtags` in `meta["description"]`; Regeln aus Global Constraints). `lib_add()` setzt bei neuem **und** vorhandenem Eintrag `tags = meta_tags(meta)` und `desc = (meta.get("description") or "")[:2000]` – vorhandene Werte nur überschreiben, wenn meta etwas liefert.

- [ ] **Step 1: Test schreiben** – `meta_tags({"tags": ["GTA 5", "gta 5"], "categories": ["Gaming"], "description": "Stunt #GTA5 #LosSantos\n#gta5"})` == `["gta 5", "gaming", "gta5", "lossantos"]`; 80 Tags → 50; Tag mit 100 Zeichen → 60. `lib_add(path, {"title": "x", "tags": ["a"], "description": "y" * 5000}, job)` → Eintrag `tags == ["a"]`, `len(desc) == 2000`; `lib_public(e)["desc"]` hat 300 Zeichen, `["tags"] == ["a"]`. Zweites `lib_add` mit gleichem Pfad und `{"description": ""}` lässt `desc` stehen. `_build_args({...Einzelvideo...})` enthält in der `before_dl:@@I`-Vorlage `tags,categories,description`.
- [ ] **Step 2:** `python tests/test_autocoll.py` → FAIL (`meta_tags` fehlt).
- [ ] **Step 3:** Implementieren (Funktionen oben; Reihenfolge der Tags: tags, categories, Hashtags; Hashtag-Regex `#(\w+)`).
- [ ] **Step 4:** `python tests/test_autocoll.py` → PASS; `python tests/test_retry.py`, `python tests/test_quality.py`, `python tests/test_photos.py` → grün (sie prüfen die Print-Vorlage/Meta).
- [ ] **Step 5:** Commit `Auto-Sammlungen: Hashtags und Beschreibung speichern`.

### Task 2: Sammlungen mit Stichwörtern

**Files:**
- Modify: `server/server.py` – neuer Abschnitt nach `collection_delete()`; `collection_new()`, `collection_update()`, `lib_add()` (am Ende `coll_auto(entry)`), `library_share()` (nach dem Setzen `coll_auto(e)`)
- Test: `tests/test_autocoll.py`

**Interfaces:**
- Consumes: `tags`, `desc` aus Task 1.
- Produces:
  - `coll_words(raw) -> list[str]` – nimmt Liste oder String (Komma/Zeilenumbruch getrennt), Regeln aus Global Constraints.
  - `coll_match(e: dict, words: list[str]) -> bool` – Text = Titel, `uploader`, `tags`, `desc`, Unterordner (`lib_public(e)["folder"]`), klein.
  - `coll_eligible(e: dict, u: dict) -> bool` – `e["owner"] == u["id"] or e.get("shared")`.
  - `coll_fill(u: dict, c: dict) -> int` – geht alle LIB-Einträge durch, hängt Treffer an (außer `skip`), gibt Zahl neu hinzugefügter zurück. Aufrufer hält `USERS_LOCK`.
  - `coll_auto(e: dict) -> None` – für alle Personen/Sammlungen mit `words`; speichert per `users_save()` nur bei Änderung.
  - API: `POST /api/collections` nimmt `words`; `POST /api/collections/<cid>` nimmt `words` (leere Liste/leerer String = Automatik aus, Feld `words` + `skip` weg), Antwort enthält dann zusätzlich `added: int`. `remove` in einer Sammlung mit `words` → ids nach `skip`; `add` → ids aus `skip` raus.

- [ ] **Step 1: Tests schreiben** (Einträge wie in test_organize, mit `tags`/`desc`):
  - `coll_words(" GTA, #gta5 ,x, gta\nLos Santos")` == `["gta", "gta5", "los santos"]` (x zu kurz, Doppeltes weg); 30 Wörter → 20.
  - `coll_match({"title": "Stunt", "tags": ["gta5"]}, ["gta"])` True; Titel „agta“ False; desc „in Los Santos“ + `["los santos"]` True; Titel „GTA V“ True.
  - Kind legt Sammlung `{"name": "GTA", "words": "gta"}` an → Antwort `items` enthält eigenes GTA-Video + geteiltes Admin-GTA-Video, nicht privates Admin-GTA-Video, nicht Nicht-GTA-Video.
  - Admin legt Sammlung mit `words: "gta"` an → privates Kind-GTA-Video fehlt; `POST /api/library/<kid-eid>/share` (als Kind) → Video jetzt in Admin-Sammlung.
  - Kind entfernt Video (`remove`) → in `skip`; neues `lib_add` (gleicher Pfad) und erneutes Speichern der `words` → bleibt draußen; `add` → wieder drin, nicht mehr in `skip`.
  - Neues `lib_add()` mit Tag „gta“ für Kind → sofort in Kind-Sammlung.
  - `words: ""` → Antwort ohne `words`/`skip`, items bleiben.
  - Sammlung ohne `words`: Antwort genau `{id, name, items}`.
- [ ] **Step 2:** `python tests/test_autocoll.py` → FAIL.
- [ ] **Step 3:** Implementieren. Locks: `coll_auto()` nach dem LIB_LOCK-Block in `lib_add()` aufrufen, nie verschachtelt LIB_LOCK→USERS_LOCK umgekehrt zu bestehendem Code (vorher prüfen, welche Reihenfolge `library_list()`/`collection_update()` nutzt, und gleich halten).
- [ ] **Step 4:** `python tests/test_autocoll.py` + `python tests/test_organize.py` → PASS.
- [ ] **Step 5:** Commit `Auto-Sammlungen: Stichwörter füllen Sammlungen automatisch`.

### Task 3: Alte Einträge nachladen

**Files:**
- Modify: `server/server.py` – im Abschnitt Auto-Sammlungen
- Test: `tests/test_autocoll.py`

**Interfaces:**
- Consumes: `meta_tags()`, `coll_auto()`.
- Produces:
  - `REFRESH = {"running": False, "done": 0, "total": 0, "failed": 0, "stop": False}`, `REFRESH_WAIT = 2.5`.
  - `refresh_meta_url(url: str, owner: dict | None) -> dict | None` – `ytdlp_base() + ["--skip-download", "--no-warnings", "--ignore-config", "--no-playlist", "--print", "%(.{tags,categories,description})j"] + cookie_args(tmp, url, owner) + list(SETTINGS.get("extra_args") or []) + site_args(url) + ["--", url]` über `run_tool(..., timeout=60)`; Fehler/kein JSON → None.
  - `refresh_meta_all() -> None` – Kandidaten: Einträge ohne `meta_ok`, mit `url` (http/https), ohne `album`; nach URL gruppiert (ein Aufruf pro URL), Pause `REFRESH_WAIT` zwischen Aufrufen, `REFRESH["stop"]` bricht ab. Erfolg → `tags`, `desc`, `meta_ok = 1`, `coll_auto(e)`; Fehler → `meta_ok = -1`. `lib_save_soon()` nach jedem Link.
  - Routen (alle `need_admin()`): `GET /api/library/refresh-meta` → `REFRESH` + `todo` (Zahl Kandidaten); `POST` startet `refresh_meta_all` in Daemon-Thread (läuft schon → 409); `DELETE` setzt `stop`.

- [ ] **Step 1: Tests schreiben** – `server.run_tool` durch Fake ersetzen (zählt Aufrufe, liefert für URL A `{"tags": ["gta"], "categories": [], "description": ""}` mit returncode 0, für URL B returncode 1), `REFRESH_WAIT = 0`. Zwei Einträge mit URL A (mp4 + mp3), einer mit B, einer mit `album`. `refresh_meta_all()` → Fake 2× aufgerufen; beide A-Einträge `tags == ["gta"]`, `meta_ok == 1`, und in Kind-Sammlung „GTA“; B `meta_ok == -1`; Album unberührt. Zweiter Lauf → 0 Aufrufe. Kind-Token: GET/POST/DELETE `/api/library/refresh-meta` → 403; Admin GET → `todo == 0`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** `python tests/test_autocoll.py` → PASS.
- [ ] **Step 5:** Commit `Auto-Sammlungen: Hashtags alter Videos nachladen`.

### Task 4: Mediathek-Oberfläche

**Files:**
- Modify: `server/static/library.html` – Suchfilter (~827), `drawColls()` + Klick-Handler (~1417), Server-Reiter (~638 neuer Abschnitt nach „Downloads“, Lade-Code ~1685)
- Modify: `server/static/icons.svg` **und** `extension/icons.svg` – neues Icon `wand` (Lucide „wand-sparkles“, gleich in beiden Dateien)
- Modify: `extension/lib/i18n.js` → kopieren nach `server/static/i18n.js`

**Interfaces:**
- Consumes: Routen aus Task 2 + 3; `e.tags`, `e.desc`, `c.words` aus `/api/library`.

- [ ] **Step 1:** Suche: Heuhaufen in Zeile ~827 um `...(e.tags || [])` und `e.desc` erweitern.
- [ ] **Step 2:** Sammlungs-Leiste: Chip-Icon `wand` statt `folder`, wenn `c.words?.length`. Bei aktiver eigener Sammlung zusätzlicher Chip `data-c="words"` (Icon `wand`, Titel „Automatisch füllen“) → `prompt(t("Stichwörter, mit Komma getrennt (leer = aus):"), cur.words?.join(", ") || "")`; `null` = abbrechen; sonst POST `{words}` → `toast(t(\`${r.added} Videos hinzugefügt\`))` bzw. „Automatik aus“ → `load()`.
- [ ] **Step 3:** Server-Reiter (nur Admin sichtbar wie die anderen Abschnitte): Überschrift „Hashtags alter Videos“, Hinweis „Fragt bei YouTube/TikTok einmal die Hashtags der schon geladenen Videos ab, damit Suche und automatische Sammlungen sie finden. Läuft langsam im Hintergrund.“, Zeile `#refInfo` („N Videos ohne Hashtags“ / „Läuft: done / total“ / „Alle erledigt“) + Knopf `#refBtn` „Jetzt nachladen“ ⇄ „Anhalten“. Beim Öffnen GET; läuft es, alle 3 s neu fragen, solange der Dialog offen ist.
- [ ] **Step 4:** Alle neuen Texte in `extension/lib/i18n.js` (EN + PAT), kopieren, `node tests/test_i18n.mjs` + `node tests/test_i18n_literals.mjs` → grün.
- [ ] **Step 5: Browser-Test** gegen lokalen Testserver im Scratchpad (Demo-Daten mit `tags`): Suche „gta“ findet Video ohne GTA im Titel; Sammlung anlegen → Stichwörter → Toast-Zahl stimmt, Chip zeigt Zauberstab; Video aus Sammlung entfernen → nach erneutem Speichern weiter weg; Server-Reiter zeigt Zahl, Knopf startet/stoppt (Fake-URLs); Handy-Breite 375 px; keine Konsolenfehler.
- [ ] **Step 6:** Commit `Auto-Sammlungen: Mediathek-Oberfläche`.

### Task 5: Abschluss 3.22.0

**Files:**
- Modify: `server/server.py` (`APP_VERSION = "3.22.0"`), `extension/manifest.json` (+0.0.1), `README.md` + `README.de.md` (Abschnitt „Automatische Sammlungen“: Stichwörter setzen, Hashtags nachladen), `PROGRESS.md`

- [ ] **Step 1:** Versionen + READMEs.
- [ ] **Step 2:** Alle Tests: jedes `tests/*.py` mit `python`, jedes `tests/*.mjs` mit `node` → alle grün.
- [ ] **Step 3:** PROGRESS.md (Stand, Nächste Schritte: Plan Teil 2, Changelog).
- [ ] **Step 4:** Commit `Kinbox 3.22.0 – automatische Sammlungen nach Hashtags`. Pushen + Tag `v3.22.0` erst nach Rückfrage beim Nutzer.
