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
  organize: "flat",         // flat | channel | plex | music
  convert: { type: "none", gifFps: 12, gifWidth: 480, targetMB: 15, keepOriginal: false },
  when: "now",              // now | night
};

export const BUILTIN_PRESETS = [
  { id: "best", name: "Beste Qualität", icon: "★", options: { mode: "video", quality: "best", container: "mp4", vcodec: "any" } },
  { id: "1080", name: "1080p MP4 (überall abspielbar)", icon: "▶", options: { mode: "video", quality: "1080", container: "mp4", vcodec: "h264" } },
  { id: "720", name: "720p klein", icon: "▶", options: { mode: "video", quality: "720", container: "mp4", vcodec: "h264" } },
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
  notify: true,
  style: "classic",     // classic | clean | paper | mono
  accent: "#7c5cff",
  defaults: { ...DEFAULT_OPTIONS },
  presets: [],          // eigene Presets: {id, name, icon, options}
  hiddenBuiltins: [],   // ausgeblendete eingebaute Presets
};

export async function getSettings() {
  const s = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  s.defaults = deepMerge(structuredClone(DEFAULT_OPTIONS), s.defaults || {});
  return s;
}

export async function saveSettings(patch) {
  await chrome.storage.sync.set(patch);
}

export async function allPresets() {
  const s = await getSettings();
  return [
    ...BUILTIN_PRESETS.filter((p) => !s.hiddenBuiltins.includes(p.id)),
    ...s.presets,
  ];
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

// Heim- oder Unterwegs-Adresse: die erste, die antwortet (Ergebnis 1 Minute gemerkt).
let _base = "", _baseAt = 0;
async function reachable(base) {
  try {
    await fetch(base + "/api/ping", { signal: AbortSignal.timeout(2000) });
    return true;
  } catch { return false; }
}
export async function serverBase(s, fresh = false) {
  const urls = [s.serverUrl, s.serverUrl2].map(normalizeUrl).filter(Boolean);
  if (urls.length < 2) return urls[0] || "";
  if (!fresh && urls.includes(_base) && Date.now() - _baseAt < 60000) return _base;
  _base = urls[0];
  for (const u of urls) if (await reachable(u)) { _base = u; break; }
  _baseAt = Date.now();
  return _base;
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
    if (retry && normalizeUrl(s.serverUrl2) && Date.now() - _baseAt > 3000) {  // Netz gewechselt → andere Adresse probieren
      _baseAt = 0;
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

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
