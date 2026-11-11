// Gemeinsame Helfer für Popup, Einstellungen und Hintergrund-Skript.

export const DEFAULT_OPTIONS = {
  mode: "video",            // video | audio | thumbnail
  quality: "best",          // best | 2160 | 1440 | 1080 | 720 | 480 | 360 | 240 | 144
  container: "mp4",         // mp4 | mkv | webm | mov | auto
  vcodec: "any",            // any | h264 | h265 | vp9 | av1
  prefer60fps: true,
  audioFormat: "mp3",       // mp3 | m4a | opus | flac | wav | aac | best
  audioBitrate: "320",      // best | 320 | 256 | 192 | 160 | 128 | 96 | 64
  thumbnailFormat: "jpg",
  normalize: false,
  subs: { enabled: false, langs: "de,en", auto: false, embed: true, format: "srt" },
  embedThumbnail: true,
  embedMetadata: true,
  embedChapters: true,
  writeThumbnail: false,
  writeDescription: false,
  writeInfoJson: false,
  sponsorblock: { mode: "off", categories: ["sponsor", "selfpromo", "interaction"] },
  rateLimit: "",
  concurrentFragments: 4,
  skipArchive: false,
  filenameTemplate: "",
  subfolder: "",
  saveToPc: false,
  musicTags: false,         // Interpret/Titel sauber + quadratisches Cover
  musicOnly: false,         // TikTok: reine Musikspur statt Originalton
  organize: "flat",         // flat | channel | plex | music
  alsoAudio: false,         // Video-Modus: zusätzlich Audiodatei (audioFormat) daneben legen
  convert: { type: "none", gifFps: 12, gifWidth: 480, targetMB: 15, keepOriginal: false },
  when: "now",              // now | night
};

export const BUILTIN_PRESETS = [
  { id: "best", name: "Beste Qualität", icon: "★", options: { mode: "video", quality: "best", container: "mp4", vcodec: "any" } },
  { id: "1080", name: "1080p MP4 (überall abspielbar)", icon: "▶", options: { mode: "video", quality: "1080", container: "mp4", vcodec: "h264" } },
  { id: "720", name: "720p klein", icon: "▶", options: { mode: "video", quality: "720", container: "mp4", vcodec: "h264" } },
  { id: "both", name: "Video + MP3 (beides)", icon: "▶", options: { mode: "video", quality: "best", container: "mp4", vcodec: "h264", alsoAudio: true, audioFormat: "mp3", audioBitrate: "320" } },
  { id: "mp3", name: "MP3 320 kbps", icon: "♪", options: { mode: "audio", audioFormat: "mp3", audioBitrate: "320" } },
  { id: "music", name: "Musik mit Tags & Cover", icon: "♫", options: { mode: "audio", audioFormat: "mp3", audioBitrate: "320", musicTags: true } },
  { id: "flac", name: "Musik verlustfrei (FLAC)", icon: "♫", options: { mode: "audio", audioFormat: "flac" } },
  { id: "whatsapp", name: "WhatsApp-tauglich (≤ 15 MB)", icon: "💬", options: { mode: "video", quality: "720", container: "mp4", vcodec: "h264", convert: { type: "small", targetMB: 15 } } },
  { id: "gif", name: "GIF", icon: "🖼", options: { mode: "video", quality: "720", container: "mp4", convert: { type: "gif", gifFps: 12, gifWidth: 480 } } },
  { id: "podcast", name: "Podcast (MP3, ohne Sponsoren)", icon: "🎙", options: { mode: "audio", audioFormat: "mp3", audioBitrate: "128", normalize: true, sponsorblock: { mode: "remove", categories: ["sponsor", "selfpromo", "interaction", "intro", "outro"] } } },
];

// Linien-Icon aus icons.svg; bekannte Preset-Symbole werden auf Icons abgebildet.
const ICON_OF = { "★": "star", "▶": "play", "♪": "music", "♫": "music", "💬": "chat", "🖼": "image", "🎙": "mic", "⟲": "reset" };
export const icon = (name) => `<svg class="i"><use href="icons.svg#${ICON_OF[name] || name}"/></svg>`;
export const presetIcon = (ch) => ICON_OF[ch] ? icon(ch) : escapeHtml(ch || "•");

export const DEFAULT_SETTINGS = {
  serverUrl: "",
  serverUrl2: "",       // optional: Unterwegs-Adresse (z. B. Tailscale), wenn die Heim-Adresse nicht antwortet
  token: "",
  showYoutubeButton: true,
  showSocialButtons: true,
  socialPos: "tl",      // Ecke des schwebenden Knopfs: tl | tr | bl | br
  socialOff: [],        // Seiten ohne Knopf: tiktok | instagram | x | reddit
  notify: true,
  style: "classic",     // classic | clean | paper | mono
  accent: "#7c5cff",
  defaults: { ...DEFAULT_OPTIONS },
  presets: [],          // eigene Presets: {id, name, icon, options}
  hiddenBuiltins: [],   // ausgeblendete eingebaute Presets
};

// Token liegt in storage.sync (wie bis 3.9) und zusätzlich als Kopie in storage.local.
// 3.10.0 hatte ihn aus sync gelöscht – Chrome hat das Löschen auf alle PCs mit demselben Google-Konto
// übertragen („Falscher oder fehlender Token“ dort). Jetzt: sync gewinnt; fehlt er dort, aber lokal ist
// noch einer (von 3.10.0 umgezogen), wird er nach sync zurückgeschrieben und heilt die anderen PCs.
// In der Android-App sind sync und local derselbe Speicher.
async function syncedToken(syncToken) {
  const { sync, local } = chrome.storage;
  if (!local || sync === local) return syncToken || "";
  const { token: localTok = "" } = await local.get("token");
  if (syncToken) {
    if (localTok !== syncToken) await local.set({ token: syncToken });
    return syncToken;
  }
  if (localTok) await sync.set({ token: localTok });
  return localTok || "";
}

export async function getSettings() {
  const s = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  s.token = await syncedToken(s.token);
  s.defaults = deepMerge(structuredClone(DEFAULT_OPTIONS), s.defaults || {});
  return s;
}

export async function saveSettings(patch) {
  const { token, ...rest } = patch;
  if (token !== undefined && chrome.storage.local && chrome.storage.local !== chrome.storage.sync) await chrome.storage.local.set({ token });
  await chrome.storage.sync.set(token !== undefined ? { ...rest, token } : rest);
}

export async function allPresets() {
  const s = await getSettings();
  return [
    ...BUILTIN_PRESETS.filter((p) => !s.hiddenBuiltins.includes(p.id)),
    ...s.presets,
  ];
}

// ---- Presets: welche Optionen gelten? ------------------------------------
// Eingebaute Presets legen fest, WAS entsteht (Format/Qualität). Sie bauen auf den eigenen Standards auf
// (Ordner, „Auf PC speichern“, Dateinamen, SponsorBlock …), setzen aber alles, was das Ergebnis verändert
// (Umwandeln, zusätzliche MP3, Nachtplan, nur Musik, Musik-Tags, Lautstärke, Untertitel), neutral –
// sonst würde „Beste Qualität“ verkleinern, nur weil „WhatsApp“ als Standard gespeichert ist.
export const PRESET_NEUTRAL = {
  convert: { type: "none" }, alsoAudio: false, when: "now", musicOnly: false, musicTags: false,
  normalize: false, subs: { enabled: false },
};
export const isBuiltinPreset = (p) => !!p && BUILTIN_PRESETS.some((b) => b.id === p.id);

// Eigene Presets sind als Unterschied zu DEFAULT_OPTIONS gespeichert (alte, vollständige bleiben lesbar)
// und werden genau so wiederhergestellt – unabhängig vom aktuellen Standard.
export function presetOptions(defaults, preset) {
  const base = structuredClone(DEFAULT_OPTIONS);
  if (!preset) return deepMerge(base, structuredClone(defaults || {}));
  if (isBuiltinPreset(preset)) deepMerge(deepMerge(base, structuredClone(defaults || {})), structuredClone(PRESET_NEUTRAL));
  return deepMerge(base, structuredClone(preset.options || {}));
}

// Nur was vom Grundwert abweicht (storage.sync erlaubt höchstens 8 KB pro Eintrag).
export function diffOptions(opts, base = DEFAULT_OPTIONS) {
  const out = {};
  for (const [k, v] of Object.entries(opts || {})) {
    const b = base?.[k];
    if (v && typeof v === "object" && !Array.isArray(v) && b && typeof b === "object" && !Array.isArray(b)) {
      const d = diffOptions(v, b);
      if (Object.keys(d).length) out[k] = d;
    } else if (JSON.stringify(v) !== JSON.stringify(b)) out[k] = structuredClone(v);
  }
  return out;
}

// Import aus Datei: nur bekannte Schlüssel mit passendem Typ übernehmen (nie den Token).
export function sanitizeImport(data) {
  const out = {};
  const isObj = (v) => !!v && typeof v === "object" && !Array.isArray(v);
  if (!isObj(data)) return out;
  for (const [k, def] of Object.entries(DEFAULT_SETTINGS)) {
    if (k === "token" || !(k in data)) continue;
    const v = data[k];
    if (Array.isArray(def)) {
      if (!Array.isArray(v)) continue;
      out[k] = k === "presets"
        ? v.filter((p) => isObj(p) && typeof p.id === "string" && typeof p.name === "string" && isObj(p.options))
          .map((p) => ({ id: p.id.slice(0, 40), name: p.name.slice(0, 80), icon: typeof p.icon === "string" ? p.icon.slice(0, 8) : "•", options: diffOptions(p.options) }))
        : v.filter((x) => typeof x === "string");
    } else if (isObj(def)) {
      if (isObj(v)) out[k] = v;
    } else if (typeof v === typeof def) out[k] = v;
  }
  if ("socialPos" in out && !/^[tb][lr]$/.test(out.socialPos)) delete out.socialPos;
  return out;
}

export function deepMerge(target, src) {
  for (const [k, v] of Object.entries(src || {})) {
    if (v && typeof v === "object" && !Array.isArray(v) && target[k] && typeof target[k] === "object" && !Array.isArray(target[k])) {
      deepMerge(target[k], v);
    } else {
      target[k] = v;
    }
  }
  return target;
}

export function normalizeUrl(u) {
  u = (u || "").trim().replace(/\/+$/, "");
  if (u && !/^https?:\/\//i.test(u)) u = "http://" + u;
  return u;
}

export class ApiError extends Error {
  constructor(msg, status) { super(msg); this.status = status; }
}

// Heim- oder Unterwegs-Adresse: beide parallel prüfen, Heim bevorzugt. Ergebnis 1 Minute gemerkt – auch in
// storage.session, damit Popup, Einstellungen und Hintergrund nicht jedes Mal neu prüfen.
// Gleichzeitige Aufrufe teilen sich eine laufende Prüfung.
const BASE_TTL = 60000;
let _base = { key: "", base: "", at: 0 }, _probe = null, _probeKey = "";
const sessionArea = () => globalThis.chrome?.storage?.session;
async function reachable(base) {
  try {
    await fetch(base + "/api/ping", { signal: AbortSignal.timeout(2000) });
    return true;
  } catch { return false; }
}
export async function serverBase(s, fresh = false) {
  const urls = [s.serverUrl, s.serverUrl2].map(normalizeUrl).filter(Boolean);
  if (urls.length < 2) return urls[0] || "";
  const key = urls.join(" ");
  const valid = (c) => !!c && c.key === key && urls.includes(c.base) && Date.now() - c.at < BASE_TTL;
  if (!fresh) {
    if (valid(_base)) return _base.base;
    if (_probe && _probeKey === key) return _probe;
    try {
      const { kbBase } = (await sessionArea()?.get("kbBase")) || {};
      if (valid(kbBase)) { _base = kbBase; return kbBase.base; }
    } catch { /* kein storage.session (Android-App, Tests) */ }
    if (_probe && _probeKey === key) return _probe;
  }
  _probeKey = key;
  const probe = (async () => {
    const [home, away] = urls.map(reachable);
    const base = (await home) ? urls[0] : (await away) ? urls[1] : urls[0];
    _base = { key, base, at: Date.now() };
    try { await sessionArea()?.set({ kbBase: _base }); } catch { /* egal */ }
    return base;
  })();
  _probe = probe;
  try { return await probe; } finally { if (_probe === probe) _probe = null; }
}

export async function api(path, { method = "GET", body, timeout = 20000, settings, retry = true } = {}) {
  const s = settings || (await getSettings());
  const base = await serverBase(s);
  if (!base) throw new ApiError("Kein Server eingestellt – öffne die Einstellungen.", 0);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  let res;
  try {
    res = await fetch(base + path, {
      method,
      headers: { "X-Token": s.token || "", ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
  } catch (e) {
    // Netz gewechselt? Nur bei echtem Netzwerkfehler (nicht bei Zeitüberschreitung) neu prüfen und nur
    // wiederholen, wenn jetzt die ANDERE Adresse gilt – die erste war nicht erreichbar, ein POST kam also nicht an.
    if (retry && e.name === "TypeError" && normalizeUrl(s.serverUrl2) && (await serverBase(s, true)) !== base) {
      return api(path, { method, body, timeout, settings: s, retry: false });
    }
    throw new ApiError(e.name === "AbortError" ? "Zeitüberschreitung – Server antwortet nicht." : "Server nicht erreichbar. Läuft er und stimmt die Adresse?", 0);
  } finally {
    clearTimeout(timer);
  }
  let data = null;
  try { data = await res.json(); } catch { /* leer */ }
  if (!res.ok) throw new ApiError((data && data.error) || `HTTP ${res.status}`, res.status);
  return data;
}

export async function libraryUrl() {
  const s = await getSettings();
  return `${await serverBase(s)}/library?token=${encodeURIComponent(s.token)}`;
}

export const SOCIAL_HOSTS = /(^|\.)(tiktok\.com|instagram\.com|x\.com|twitter\.com|reddit\.com)$/i;
export function isSocial(url) {
  try { return SOCIAL_HOSTS.test(new URL(url).hostname); } catch { return false; }
}

// Content-Skript samt i18n/Icons in einen Tab nachladen, der vor der Erweiterung (oder vor einem Update) offen war.
export async function injectContent(tabId, script) {
  const cs = chrome.runtime.getManifest().content_scripts.find((c) => c.js.includes(script));
  await chrome.scripting.insertCSS({ target: { tabId }, files: cs.css });
  await chrome.scripting.executeScript({ target: { tabId }, files: cs.js });
}

// Auf TikTok/Instagram/X/Reddit ist die Adresse im Browser oft nicht die des Videos –
// das Seiten-Skript kennt das Video, das gerade zu sehen ist.
export async function mediaUrlForTab(tab, kind = "currentMediaUrl") {
  if (!tab?.id || !isSocial(tab.url)) return tab?.url;
  const ask = () => chrome.tabs.sendMessage(tab.id, { type: kind });
  try {
    const r = await ask();
    if (r?.url) return r.url;
  } catch {
    try {   // Tab war schon offen, bevor die Erweiterung (neu) geladen wurde
      await injectContent(tab.id, "content/social.js");
      const r = await ask();
      if (r?.url) return r.url;
    } catch { /* egal (z. B. Android-App: kein chrome.scripting) */ }
  }
  return tab.url;
}

export async function fileUrl(jobId, idx) {
  const s = await getSettings();
  return `${await serverBase(s)}/api/jobs/${jobId}/files/${idx}?token=${encodeURIComponent(s.token)}`;
}

// ---- Formatierung -------------------------------------------------------

export function fmtBytes(n) {
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 && i > 1 ? 1 : 0)} ${u[i]}`;
}

export function fmtTime(sec, forceHours = false) {
  if (sec == null || isNaN(sec)) return "";
  sec = Math.max(0, Math.round(sec * 10) / 10);
  const whole = Math.floor(sec);
  const tenth = Math.round((sec - whole) * 10);
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  const frac = tenth ? "." + tenth : "";
  const mm = String(m).padStart(h || forceHours ? 2 : 1, "0");
  return (h || forceHours ? `${h}:` : "") + `${mm}:${String(s).padStart(2, "0")}` + frac;
}

export function parseTime(str) {
  str = (str || "").trim();
  if (!str) return null;
  if (!/^\d+(:\d{1,2}){0,2}(\.\d+)?$/.test(str)) return NaN;
  return str.split(":").reduce((acc, p) => acc * 60 + parseFloat(p), 0);
}

export function qualityLabel(h) {
  return { 4320: "8K", 2160: "4K", 1440: "2K" }[h] || `${h}p`;
}

export function youtubeId(url) {
  try {
    const u = new URL(url);
    if (u.hostname === "youtu.be") return u.pathname.slice(1);
    if (/youtube\.com$/.test(u.hostname)) {
      if (u.searchParams.get("v")) return u.searchParams.get("v");
      const m = u.pathname.match(/^\/(shorts|live|embed)\/([\w-]{6,})/);
      if (m) return m[2];
    }
  } catch { /* egal */ }
  return null;
}

export function playlistId(url) {
  try { return new URL(url).searchParams.get("list"); } catch { return null; }
}

// Für url('…') in style-Attributen: Zeichen, die aus dem CSS-String ausbrechen könnten, kodieren.
export const cssUrl = (u) => String(u ?? "").replace(/['"()\\\s]/g, (c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"));

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
