import {
  api, getSettings, saveSettings, allPresets, deepMerge, fileUrl, libraryUrl, isSocial,
  fmtBytes, fmtTime, parseTime, qualityLabel, youtubeId, playlistId, escapeHtml,
} from "./lib/common.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const params = new URLSearchParams(location.search);
const isWindow = params.get("window") === "1";
if (isWindow) document.body.classList.add("window");

let settings;
let opts;                    // aktuelle Optionen (werden an den Server geschickt)
let info = null;             // Antwort von /api/info
let tabId = null;
let tabUrl = "";
let prefill = { title: "", thumbnail: "" };
let trim = { start: null, end: null };
let chapterSel = null;       // Set mit gewählten Kapiteltiteln, null = alle
let playlistMode = "single";
let activePreset = "default";

// ------------------------------------------------------------------------
// Start
// ------------------------------------------------------------------------

init();

async function init() {
  settings = await getSettings();
  opts = structuredClone(settings.defaults);
  $("#setupHint").hidden = !!settings.serverUrl;

  if (params.get("url")) {
    tabUrl = params.get("url");
    tabId = Number(params.get("tab")) || null;
    if (tabId) {
      try { prefill.title = (await chrome.tabs.get(tabId)).title; } catch { tabId = null; }
    }
  } else {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) { tabUrl = tab.url || ""; tabId = tab.id; prefill.title = tab.title || ""; }
  }
  prefill.title = prefill.title.replace(/^\(\d+\)\s*/, "").replace(/\s*[-–|]\s*YouTube( Music)?$/i, "");
  if (tabId && isSocial(tabUrl) && !params.get("url")) {
    // Auf TikTok & Co. zeigt die Adressleiste oft nicht das Video – das Seiten-Skript weiß es
    try {
      const r = await chrome.tabs.sendMessage(tabId, { type: "currentMediaUrl" });
      if (r?.url) { tabUrl = r.url; prefill.title = ""; }
    } catch { /* Seite wurde vor der Erweiterung geladen */ }
  }
  const yt = youtubeId(tabUrl);
  if (yt) prefill.thumbnail = `https://i.ytimg.com/vi/${yt}/hqdefault.jpg`;

  $("#url").value = /^https?:/.test(tabUrl) ? tabUrl : "";
  bindControls();
  bindTrim();
  bindChapters();
  bindPlaylist();
  bindQueue();
  await renderPresets();
  buildQualities();
  render();
  checkServer();
  if ($("#url").value) loadInfo();
  else showMedia({ title: "Kein Video auf dieser Seite", sub: "Öffne ein Video oder füge oben einen Link ein." });
  pollJobs();
}

// ------------------------------------------------------------------------
// Optionen <-> Bedienelemente
// ------------------------------------------------------------------------

const getPath = (o, p) => p.split(".").reduce((a, k) => a?.[k], o);
function setPath(o, p, v) {
  const ks = p.split(".");
  let a = o;
  for (const k of ks.slice(0, -1)) a = a[k] ??= {};
  a[ks.at(-1)] = v;
}

function bindControls() {
  for (const el of $$("[data-bind]")) {
    const path = el.dataset.bind;
    if (el.matches("input[type=checkbox]")) {
      el.addEventListener("change", () => { setPath(opts, path, el.checked); changed(); });
    } else if (el.matches("input, select")) {
      el.addEventListener("input", () => { setPath(opts, path, el.dataset.type === "number" ? Number(el.value) : el.value); changed(); });
    } else {
      el.addEventListener("click", (e) => {
        const b = e.target.closest("button[data-value]");
        if (!b) return;
        setPath(opts, path, b.dataset.value);
        changed();
      });
    }
  }
  for (const el of $$("[data-bind-multi]")) {
    el.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-value]");
      if (!b) return;
      const path = el.dataset.bindMulti;
      const set = new Set(getPath(opts, path) || []);
      set.has(b.dataset.value) ? set.delete(b.dataset.value) : set.add(b.dataset.value);
      setPath(opts, path, [...set]);
      if (set.size && opts.sponsorblock.mode === "off") opts.sponsorblock.mode = "remove";
      changed();
    });
  }
  $("#url").addEventListener("change", () => { tabUrl = $("#url").value.trim(); prefill = { title: "", thumbnail: "" }; resetPerVideo(); loadInfo(); });
  $("#reload").addEventListener("click", () => { tabUrl = $("#url").value.trim(); loadInfo(true); });
  $("#openSettings").addEventListener("click", () => chrome.runtime.openOptionsPage());
  $("#openLibrary").addEventListener("click", async () => {
    if (!settings.serverUrl) return chrome.runtime.openOptionsPage();
    chrome.tabs.create({ url: await libraryUrl() });
  });
  $("#night").addEventListener("change", () => { opts.when = $("#night").checked ? "night" : "now"; changed(); });
  $("#setupLink").addEventListener("click", (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); });
  $("#go").addEventListener("click", startDownload);
  $("#savePreset").addEventListener("click", savePresetDialog);
  for (const t of $$(".tab")) t.addEventListener("click", () => showView(t.dataset.view));
}

function changed() {
  activePreset = null;
  render();
}

function render() {
  for (const el of $$("[data-bind]")) {
    const v = getPath(opts, el.dataset.bind);
    if (el.matches("input[type=checkbox]")) el.checked = !!v;
    else if (el.matches("input, select")) { if (document.activeElement !== el) el.value = v ?? ""; }
    else for (const b of $$("button[data-value]", el)) b.classList.toggle("active", b.dataset.value === String(v));
  }
  for (const el of $$("[data-bind-multi]")) {
    const arr = getPath(opts, el.dataset.bindMulti) || [];
    for (const b of $$("button[data-value]", el)) b.classList.toggle("active", arr.includes(b.dataset.value));
  }
  for (const el of $$("[data-show-mode]")) el.hidden = el.dataset.showMode !== opts.mode;
  for (const el of $$("[data-hide-mode]")) el.hidden = el.dataset.hideMode === opts.mode || (el.id === "chapterCard" && !info?.chapters?.length);
  $("#bitrateBox").hidden = ["flac", "wav", "best"].includes(opts.audioFormat);
  const conv = opts.convert?.type || "none";
  $("#gifBox").hidden = conv !== "gif";
  $("#smallBox").hidden = conv !== "small";
  $("#keepOrigBox").hidden = conv === "none";
  $("#night").checked = opts.when === "night";
  for (const b of $$("#presets button")) b.classList.toggle("active", b.dataset.id === activePreset);
  summaries();
}

function summaries() {
  const on = (id, text, active) => { const e = $(id); e.textContent = text; e.classList.toggle("on", !!active); };
  const tr = trimRange();
  on("#trimSummary", tr ? `${fmtTime(tr.s)} – ${tr.e == null ? t("Ende") : fmtTime(tr.e)}${lenText(tr)}` : "ganzes Video", !!tr);
  on("#chapterSummary", chapterSel && info?.chapters ? `${chapterSel.size} ${t("von")} ${info.chapters.length}` : "alle", !!chapterSel);
  on("#subsSummary", opts.subs.enabled ? (opts.subs.langs || t("alle")) + (opts.subs.embed && opts.mode === "video" ? " · " + t("eingebettet") : "") : "aus", opts.subs.enabled);
  const sbCats = opts.sponsorblock.categories.length;
  on("#sbSummary", opts.sponsorblock.mode === "off" || !sbCats ? "aus" : `${t(opts.sponsorblock.mode === "remove" ? "entfernen" : "markieren")} · ${sbCats}`, opts.sponsorblock.mode !== "off" && sbCats);
  on("#playlistSummary", { single: "nur dieses Video", all: "ganze Playlist", items: "Auswahl" }[playlistMode], playlistMode !== "single");

  // Zusammenfassung unter dem Button
  const parts = [];
  if (opts.mode === "video") {
    parts.push(opts.quality === "best" ? "Beste Qualität" : qualityLabel(+opts.quality));
    parts.push(opts.container === "auto" ? "Original" : opts.container.toUpperCase());
    const q = info?.qualities?.find((x) => String(x.height) === opts.quality) || (opts.quality === "best" && info?.qualities?.[0]);
    let size = q?.size;
    if (size && tr && info.duration) size *= ((tr.e ?? info.duration) - tr.s) / info.duration;
    if (size && playlistMode === "single" && (opts.convert?.type || "none") === "none") parts.push("~" + fmtBytes(size));
  } else if (opts.mode === "audio") {
    parts.push(opts.audioFormat === "best" ? "Original-Audio" : opts.audioFormat.toUpperCase());
    if (!["flac", "wav", "best"].includes(opts.audioFormat)) parts.push(opts.audioBitrate === "best" ? "VBR" : opts.audioBitrate + " kbps");
  } else parts.push(t("Vorschaubild") + " " + opts.thumbnailFormat.toUpperCase());
  if (tr) parts.push("✂" + lenText(tr).replace(/[()\s]/g, ""));
  if (opts.mode === "video" && opts.convert?.type === "gif") parts.push("→ GIF");
  if (opts.mode === "video" && opts.convert?.type === "small") parts.push(`→ max. ${opts.convert.targetMB} MB`);
  if (opts.mode === "audio" && opts.musicTags) parts.push("Musik-Tags");
  if (opts.when === "night") parts.push("🌙 nachts");
  if (playlistMode !== "single") parts.push("Playlist");
  $("#goSummary").textContent = parts.map(t).join(" · ");
}

function lenText(tr) {
  const end = tr.e ?? info?.duration;
  return end ? ` (${fmtTime(end - tr.s)})` : "";
}

// ------------------------------------------------------------------------
// Presets
// ------------------------------------------------------------------------

async function renderPresets() {
  const box = $("#presets");
  const presets = await allPresets();
  box.innerHTML = `<button data-id="default">⟲ Standard</button>` +
    presets.map((p) => `<button data-id="${escapeHtml(p.id)}">${escapeHtml(p.icon || "•")} ${escapeHtml(p.name)}</button>`).join("");
  box.onclick = (e) => {
    const b = e.target.closest("button[data-id]");
    if (!b) return;
    const base = structuredClone(settings.defaults);
    const p = presets.find((x) => x.id === b.dataset.id);
    opts = p ? deepMerge(base, structuredClone(p.options)) : base;
    activePreset = b.dataset.id;
    render();
  };
}

function savePresetDialog() {
  const d = document.createElement("dialog");
  d.className = "card";
  d.style.cssText = "padding:14px;width:340px;border:1px solid var(--line);color:var(--text)";
  d.innerHTML = `
    <b>Aktuelle Einstellungen speichern</b>
    <label class="field" style="margin-top:10px">Name <input id="pName" placeholder="z. B. Musikvideos 4K"></label>
    <label class="switch"><input type="checkbox" id="pDefault"><span></span>Auch als Standard verwenden</label>
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:10px">
      <button class="link" value="cancel" id="pCancel">Abbrechen</button>
      <button class="primary" style="width:auto;padding:8px 16px" id="pSave">Speichern</button>
    </div>`;
  document.body.appendChild(d);
  d.showModal();
  $("#pName", d).focus();
  $("#pCancel", d).onclick = () => d.remove();
  $("#pSave", d).onclick = async () => {
    const name = $("#pName", d).value.trim();
    const makeDefault = $("#pDefault", d).checked;
    const clean = structuredClone(opts);
    if (name) {
      const icon = { video: "▶", audio: "♪", thumbnail: "🖼" }[opts.mode];
      const id = "u" + Date.now().toString(36);
      settings.presets = [...settings.presets, { id, name, icon, options: clean }];
      await saveSettings({ presets: settings.presets });
      activePreset = id;
    }
    if (makeDefault) {
      settings.defaults = clean;
      await saveSettings({ defaults: clean });
    }
    d.remove();
    if (name || makeDefault) {
      await renderPresets();
      render();
      toast(name ? `Preset „${name}" gespeichert` : "Als Standard gespeichert");
    }
  };
  d.addEventListener("close", () => d.remove());
}

// ------------------------------------------------------------------------
// Video-Infos
// ------------------------------------------------------------------------

function showMedia({ title, sub = "", thumb = "", duration = null, error = "", loading = false }) {
  $("#title").textContent = title || "—";
  $("#uploader").textContent = sub;
  $("#thumb").style.backgroundImage = thumb ? `url("${thumb.replace(/"/g, "%22")}")` : "";
  $("#duration").textContent = duration ? fmtTime(duration) : "";
  $("#infoError").textContent = error;
  $("#infoError").hidden = !error;
  $("#media").classList.toggle("loading", loading);
}

function resetPerVideo() {
  info = null;
  trim = { start: null, end: null };
  chapterSel = null;
  playlistMode = playlistId(tabUrl) && !youtubeId(tabUrl) ? "all" : "single";
}

let infoSeq = 0;
async function loadInfo() {
  const url = $("#url").value.trim();
  if (!/^https?:\/\//.test(url)) {
    showMedia({ title: "Ungültiger Link", error: "Der Link muss mit http:// oder https:// beginnen." });
    return;
  }
  resetPerVideo();
  showAlready([]);
  const seq = ++infoSeq;
  showMedia({ title: prefill.title || "Lade Infos …", sub: new URL(url).hostname, thumb: prefill.thumbnail, loading: true });
  updatePlaylistCard();
  buildQualities();
  updateTrimUi();
  render();
  try {
    const data = await api("/api/info", { method: "POST", body: { url }, timeout: 90000, settings });
    if (seq !== infoSeq) return;
    info = data;
    if (data.type === "playlist") {
      playlistMode = "all";
      showMedia({ title: data.title, sub: `Playlist · ${data.count} Videos${data.uploader ? " · " + data.uploader : ""}`, thumb: data.thumbnail || prefill.thumbnail });
    } else {
      const bits = [data.uploader, data.extractor].filter(Boolean);
      showMedia({ title: data.title, sub: bits.join(" · "), thumb: data.thumbnail || prefill.thumbnail, duration: data.duration });
      if (data.is_live) {
        $("#infoError").hidden = false;
        $("#infoError").textContent = "Livestream – wird ab jetzt aufgenommen, bis er endet.";
      }
    }
    showAlready(data.already || []);
    buildQualities();
    buildChapters();
    buildSubs();
    updateTrimUi();
    updatePlaylistCard();
    render();
  } catch (e) {
    if (seq !== infoSeq) return;
    showMedia({ title: prefill.title || url, sub: new URL(url).hostname, thumb: prefill.thumbnail, error: e.message });
  }
}

function showAlready(list) {
  const el = $("#already");
  el.hidden = !list.length;
  if (!list.length) return;
  const e = list[0];
  const days = Math.floor((Date.now() / 1000 - e.added) / 86400);
  const when = days < 1 ? "heute" : days === 1 ? "gestern" : `vor ${days} Tagen`;
  el.innerHTML = `<span>✓ Schon in der Kinbox (${escapeHtml(when)}): <b>${escapeHtml(e.name)}</b>${list.length > 1 ? ` + ${list.length - 1} weitere` : ""}</span>
    <button class="link" id="openLib">In Mediathek ansehen</button>`;
  $("#openLib").onclick = async () => chrome.tabs.create({ url: await libraryUrl() });
}

function buildQualities() {
  const box = $("#qualities");
  const qs = info?.qualities?.length ? info.qualities : [2160, 1440, 1080, 720, 480, 360].map((h) => ({ height: h }));
  const best = qs[0];
  const btn = (val, label, sub, tag) =>
    `<button data-value="${val}"><b>${label}${tag ? `<span class="tag">${tag}</span>` : ""}</b><small>${sub || "&nbsp;"}</small></button>`;
  let html = btn("best", "Beste", best?.size ? "~" + fmtBytes(best.size) : info ? qualityLabel(best.height) : "automatisch");
  for (const q of qs.slice(0, 8)) {
    html += btn(q.height, qualityLabel(q.height), q.size ? "~" + fmtBytes(q.size) : "", q.fps > 30 ? q.fps : "");
  }
  box.innerHTML = html;
}

function buildSubs() {
  const list = $("#subLangs");
  const subs = info?.subtitles || [];
  const auto = info?.auto_subtitles || [];
  list.innerHTML = [...new Set([...subs, ...auto])].map((l) => `<option value="${escapeHtml(l)}">`).join("");
  $("#subsAvail").textContent = info?.type === "video"
    ? (subs.length ? `Verfügbar: ${subs.slice(0, 12).join(", ")}${subs.length > 12 ? " …" : ""}` : "Keine manuellen Untertitel") +
      (auto.length ? ` · ${auto.length} automatische Sprachen` : "")
    : "";
}

// ------------------------------------------------------------------------
// Zuschneiden
// ------------------------------------------------------------------------

function trimRange() {
  const dur = info?.duration || null;
  let s = trim.start ?? 0, e = trim.end;
  if (dur && e != null && e >= dur - 0.05) e = null;
  if (s <= 0.05 && e == null) return null;
  return { s: Math.max(0, s), e };
}

function bindTrim() {
  const rs = $("#rStart"), re = $("#rEnd");
  rs.addEventListener("input", () => {
    if (+rs.value > +re.value - 1) rs.value = +re.value - 1;
    trim.start = +rs.value; syncTrimInputs(); seekPreview(+rs.value);
  });
  re.addEventListener("input", () => {
    if (+re.value < +rs.value + 1) re.value = +rs.value + 1;
    trim.end = +re.value; syncTrimInputs(); seekPreview(+re.value);
  });
  for (const [id, key] of [["#tStart", "start"], ["#tEnd", "end"]]) {
    $(id).addEventListener("change", () => {
      const v = parseTime($(id).value);
      const bad = Number.isNaN(v) || (v != null && info?.duration && v > info.duration);
      $(id).classList.toggle("invalid", bad);
      if (bad) return;
      trim[key] = v;
      updateTrimUi();
      render();
      if (v != null) seekPreview(v);
    });
  }
  $$("[data-now]").forEach((b) => b.addEventListener("click", async () => {
    const t = await videoTime();
    if (t == null) return toast("Kein laufendes Video im Tab gefunden.", true);
    trim[b.dataset.now] = Math.round(t * 10) / 10;
    updateTrimUi();
    render();
  }));
  $("#trimReset").addEventListener("click", () => { trim = { start: null, end: null }; updateTrimUi(); render(); });
  $("#trimPrecise").addEventListener("change", render);
}

function syncTrimInputs() {
  $("#tStart").value = trim.start ? fmtTime(trim.start) : "";
  $("#tEnd").value = trim.end != null && !(info?.duration && trim.end >= info.duration) ? fmtTime(trim.end) : "";
  $("#tStart").classList.remove("invalid"); $("#tEnd").classList.remove("invalid");
  const d = info?.duration;
  if (d) {
    const a = (trim.start || 0) / d * 100, b = (trim.end ?? d) / d * 100;
    $("#rangeFill").style.left = a + "%";
    $("#rangeFill").style.width = Math.max(0, b - a) + "%";
  }
  summaries();
}

function updateTrimUi() {
  const d = info?.duration;
  $("#range").hidden = !d;
  if (d) {
    for (const r of [$("#rStart"), $("#rEnd")]) { r.max = d; }
    $("#rStart").value = trim.start || 0;
    $("#rEnd").value = trim.end ?? d;
    $("#tEnd").placeholder = fmtTime(d);
  }
  syncTrimInputs();
}

function sameVideoInTab() {
  return tabId && (!youtubeId(tabUrl) || youtubeId(tabUrl) === youtubeId($("#url").value));
}

async function videoTime() {
  if (!sameVideoInTab()) return null;
  try {
    const [r] = await chrome.scripting.executeScript({
      target: { tabId, allFrames: false },
      func: () => {
        const vids = [...document.querySelectorAll("video")].filter((v) => v.duration);
        vids.sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight);
        return vids[0] ? vids[0].currentTime : null;
      },
    });
    return r?.result ?? null;
  } catch { return null; }
}

let seekTimer = null;
function seekPreview(t) {
  if (!$("#trimPreview").checked || !sameVideoInTab()) return;
  clearTimeout(seekTimer);
  seekTimer = setTimeout(() => {
    chrome.scripting.executeScript({
      target: { tabId },
      args: [t],
      func: (t) => {
        const vids = [...document.querySelectorAll("video")].filter((v) => v.duration);
        vids.sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight);
        if (vids[0]) { vids[0].pause(); vids[0].currentTime = t; }
      },
    }).catch(() => {});
  }, 120);
}

// ------------------------------------------------------------------------
// Kapitel
// ------------------------------------------------------------------------

function bindChapters() {
  $("#chapters").addEventListener("change", (e) => {
    const all = info.chapters.map((c) => c.title);
    const set = new Set($$("#chapters input:checked").map((i) => i.value));
    chapterSel = set.size === all.length ? null : set;
    if (e.target.checked === false && set.size === 0) chapterSel = new Set();
    render();
  });
  $("#chAll").addEventListener("click", () => { chapterSel = null; buildChapters(); render(); });
  $("#chNone").addEventListener("click", () => { chapterSel = new Set(); buildChapters(); render(); });
  $("#splitChapters").addEventListener("change", render);
}

function buildChapters() {
  const ch = info?.chapters || [];
  $("#chapterCard").hidden = !ch.length;
  $("#chapters").innerHTML = ch.map((c) => `
    <label><input type="checkbox" value="${escapeHtml(c.title)}" ${!chapterSel || chapterSel.has(c.title) ? "checked" : ""}>
    <span>${escapeHtml(c.title)}</span><span class="t">${fmtTime(c.start)}</span></label>`).join("");
}

// ------------------------------------------------------------------------
// Playlist
// ------------------------------------------------------------------------

function bindPlaylist() {
  $("#playlistMode").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-value]");
    if (!b) return;
    playlistMode = b.dataset.value;
    updatePlaylistCard();
    render();
    if (playlistMode !== "single") loadPlaylistInfo();
  });
}

function updatePlaylistCard() {
  const has = !!playlistId($("#url").value) || info?.type === "playlist";
  $("#playlistCard").hidden = !has;
  if (has && playlistMode !== "single") $("#playlistCard").open = true;
  for (const b of $$("#playlistMode button")) b.classList.toggle("active", b.dataset.value === playlistMode);
  $("#playlistItems").hidden = playlistMode !== "items";
  $("#playlistMode button[data-value=single]").hidden = info?.type === "playlist";
}

let plInfoFor = "";
async function loadPlaylistInfo() {
  const url = $("#url").value.trim();
  if (plInfoFor === url) return;
  plInfoFor = url;
  if (info?.type === "playlist") { $("#playlistInfo").textContent = `${info.count} Videos in „${info.title}"`; return; }
  $("#playlistInfo").textContent = "Lade Playlist …";
  try {
    const p = await api("/api/info", { method: "POST", body: { url, playlist: true }, timeout: 90000, settings });
    $("#playlistInfo").textContent = p.type === "playlist" ? `${p.count} Videos in „${p.title}"` : "";
  } catch (e) { $("#playlistInfo").textContent = e.message; plInfoFor = ""; }
}

// ------------------------------------------------------------------------
// Download starten
// ------------------------------------------------------------------------

function buildPayload() {
  const url = $("#url").value.trim();
  const p = structuredClone(opts);
  p.url = url;
  if (info?.type === "video" && playlistMode === "single") { p.title = info.title; p.thumbnail = info.thumbnail; }
  else if (info?.type === "playlist") { p.title = info.title; p.thumbnail = info.thumbnail; }
  else { p.title = prefill.title || ""; p.thumbnail = prefill.thumbnail || ""; }
  p.playlist = playlistMode;
  if (playlistMode === "items") p.playlistItems = $("#playlistItems").value.trim();
  if (opts.mode !== "thumbnail") {
    const tr = trimRange();
    if (tr) p.trim = { start: tr.s ? fmtTime(tr.s) : "", end: tr.e != null ? fmtTime(tr.e) : "", precise: $("#trimPrecise").checked };
    if (chapterSel) p.chapters = [...chapterSel];
    p.splitChapters = $("#splitChapters").checked && !!info?.chapters?.length;
  }
  return p;
}

async function startDownload() {
  if (!settings.serverUrl) return chrome.runtime.openOptionsPage();
  const url = $("#url").value.trim();
  if (!/^https?:\/\//.test(url)) return toast("Bitte zuerst einen Link eingeben.", true);
  if (chapterSel && chapterSel.size === 0) return toast("Mindestens ein Kapitel auswählen.", true);
  if (playlistMode === "items" && !$("#playlistItems").value.trim()) return toast("Welche Playlist-Einträge? z. B. 1-5,8", true);
  const btn = $("#go");
  btn.disabled = true;
  $("#go span").textContent = "Wird gesendet …";
  try {
    const res = await chrome.runtime.sendMessage({ type: "queue", options: buildPayload() });
    if (!res?.ok) throw new Error(res?.error || "Unbekannter Fehler");
    toast("✓ Zur Warteschlange hinzugefügt");
    showView("queue");
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
    $("#go span").textContent = "Herunterladen";
  }
}

// ------------------------------------------------------------------------
// Server-Status
// ------------------------------------------------------------------------

async function checkServer() {
  const st = $("#status");
  if (!settings.serverUrl) { st.className = "status bad"; st.title = "Kein Server eingestellt"; return; }
  try {
    const p = await api("/api/ping", { timeout: 6000, settings });
    st.className = "status ok";
    st.title = `Verbunden · yt-dlp ${p.ytdlp} · ffmpeg ${p.ffmpeg ? "✓" : "✗"} · JS ${p.js_runtime || "✗"}`;
    $("#serverInfo").textContent = `Ziel: ${p.download_dir} · yt-dlp ${p.ytdlp}`;
    if (p.user) {
      const w = $("#whoami");
      w.style.display = "inline-flex";
      w.innerHTML = `<span style="width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font-size:12px;background:${escapeHtml(p.user.color)}">${escapeHtml(p.user.avatar)}</span>${escapeHtml(p.user.name)}`;
      st.title = `${p.user.name} · ` + st.title;
    }
    if (!p.ffmpeg) toast("Auf dem Server fehlt ffmpeg – MP3, Zuschneiden und Zusammenführen funktionieren nicht.", true);
    else if (!p.js_runtime) toast("Auf dem Server fehlt deno – YouTube funktioniert evtl. nicht zuverlässig.", true);
  } catch (e) {
    st.className = "status bad";
    st.title = e.message;
    $("#serverInfo").textContent = e.message;
  }
}

// ------------------------------------------------------------------------
// Warteschlange
// ------------------------------------------------------------------------

let currentView = "download";
let lastJobsJson = "";
let pollTimer = null;
const openLogs = new Set();
const confirmDelete = new Set();

function showView(v) {
  currentView = v;
  for (const t of $$(".tab")) t.classList.toggle("active", t.dataset.view === v);
  $("#view-download").hidden = v !== "download";
  $("#actionbar").hidden = v !== "download";
  $("#view-queue").hidden = v !== "queue";
  pollJobs();
}

async function pollJobs() {
  clearTimeout(pollTimer);
  if (settings?.serverUrl) {
    try {
      const jobs = await api("/api/jobs", { timeout: 8000, settings });
      const active = jobs.filter((j) => ["running", "queued", "scheduled"].includes(j.status)).length;
      $("#queueCount").hidden = !active;
      $("#queueCount").textContent = active;
      if (currentView === "queue") renderJobs(jobs);
    } catch (e) {
      if (currentView === "queue") $("#jobs").innerHTML = `<div class="notice warn">${escapeHtml(e.message)}</div>`, lastJobsJson = "";
    }
  }
  pollTimer = setTimeout(pollJobs, currentView === "queue" ? 1000 : 4000);
}

async function renderJobs(jobs) {
  const logs = {};
  for (const id of openLogs) {
    try { logs[id] = (await api("/api/jobs/" + id, { settings })).log; } catch { openLogs.delete(id); }
  }
  const json = JSON.stringify([jobs, logs, [...confirmDelete]]);
  if (json === lastJobsJson) return;
  lastJobsJson = json;
  $("#noJobs").hidden = jobs.length > 0;
  const statusText = { queued: "Wartet", scheduled: "🌙 Geplant für die Nacht", running: "", finished: "Fertig", error: "Fehler", cancelled: "Abgebrochen" };
  $("#jobs").innerHTML = jobs.map((j) => {
    const running = j.status === "running";
    const indet = running && (!j.stage.startsWith("Lädt herunter") || !j.percent);
    const meta = [];
    meta.push(`<span class="st-${j.status}">${escapeHtml(running ? j.stage : statusText[j.status])}</span>`);
    if (running && j.percent && j.stage.startsWith("Lädt")) meta.push(`${j.percent.toFixed(0)} %`);
    if (running && j.speed) meta.push(fmtBytes(j.speed) + "/s");
    if (running && j.eta != null) meta.push("noch " + fmtTime(j.eta));
    if (j.status === "finished") {
      const size = j.files.reduce((a, f) => a + (f.size || 0), 0);
      if (size) meta.push(fmtBytes(size));
      if (j.files.length > 1) meta.push(`${j.files.length} Dateien`);
      if (j.files.length && j.files.every((f) => !f.exists)) meta.push("Datei gelöscht");
    }
    const o = j.options || {};
    meta.push(escapeHtml(o.mode === "audio" ? (o.audioFormat || "").toUpperCase() : o.mode === "thumbnail" ? "Bild"
      : o.convert?.type === "gif" ? "GIF" : o.convert?.type === "small" ? `≤ ${o.convert.targetMB} MB` : (o.quality === "best" ? "Beste" : qualityLabel(+o.quality))));
    const acts = [];
    if (j.status === "scheduled") acts.push(`<button class="link" data-act="start">▶ Jetzt starten</button>`);
    if (["running", "queued", "scheduled"].includes(j.status)) acts.push(`<button class="link" data-act="cancel">Abbrechen</button>`);
    if (j.status === "finished" && j.files.some((f) => f.exists)) acts.push(`<button class="link" data-act="save">⬇ Auf PC${j.files.length > 1 ? ` (${j.files.length})` : ""}</button>`);
    if (j.status === "error" || j.status === "cancelled") acts.push(`<button class="link" data-act="retry">↻ Nochmal</button>`);
    if (!["running", "queued", "scheduled"].includes(j.status)) {
      acts.push(`<button class="link" data-act="remove">Entfernen</button>`);
      if (j.files.some((f) => f.exists)) acts.push(`<button class="link" data-act="delfile" style="color:var(--err)">${confirmDelete.has(j.id) ? "Wirklich löschen?" : "Datei löschen"}</button>`);
    }
    acts.push(`<button class="link" data-act="log">${openLogs.has(j.id) ? "Log ausblenden" : "Log"}</button>`);
    return `
    <div class="job ${j.status}" data-id="${j.id}">
      <div class="jt" style="background-image:url('${escapeHtml(j.thumbnail || "")}')"></div>
      <div class="jb">
        <div class="jn" title="${escapeHtml(j.title)}">${escapeHtml(j.title)}</div>
        <div class="bar ${indet ? "indet" : ""}"><i style="width:${j.status === "finished" ? 100 : j.percent || 0}%"></i></div>
        <div class="js">${meta.join("<span>·</span>")}</div>
        ${j.error ? `<div class="err">${escapeHtml(j.error)}</div>` : ""}
        <div class="ja">${acts.join("")}</div>
        ${logs[j.id] ? `<pre style="max-height:140px;overflow:auto;font-size:10px;background:var(--bg3);padding:6px;border-radius:6px;white-space:pre-wrap;word-break:break-all;margin:0">${escapeHtml(logs[j.id].slice(-40).join("\n"))}</pre>` : ""}
      </div>
    </div>`;
  }).join("");
}

function bindQueue() {
  $("#jobs").addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const id = b.closest(".job").dataset.id;
    const act = b.dataset.act;
    try {
      if (act === "cancel") await api(`/api/jobs/${id}/cancel`, { method: "POST", settings });
      if (act === "start") await api(`/api/jobs/${id}/start`, { method: "POST", settings });
      if (act === "retry") {
        const j = await api(`/api/jobs/${id}/retry`, { method: "POST", settings });
        chrome.runtime.sendMessage({ type: "track", id: j.id, saveToPc: !!j.options?.saveToPc, title: j.title });
      }
      if (act === "remove") await api(`/api/jobs/${id}`, { method: "DELETE", settings });
      if (act === "delfile") {
        if (!confirmDelete.has(id)) { confirmDelete.add(id); setTimeout(() => { confirmDelete.delete(id); lastJobsJson = ""; }, 4000); }
        else { confirmDelete.delete(id); await api(`/api/jobs/${id}?files=1`, { method: "DELETE", settings }); toast("Datei auf dem Server gelöscht"); }
      }
      if (act === "log") openLogs.has(id) ? openLogs.delete(id) : openLogs.add(id);
      if (act === "save") {
        const j = await api(`/api/jobs/${id}`, { settings });
        for (let i = 0; i < j.files.length; i++) {
          if (!j.files[i].exists) continue;
          await chrome.downloads.download({ url: await fileUrl(id, i), filename: j.files[i].name.replace(/[\\/:*?"<>|]/g, "_"), conflictAction: "uniquify" });
        }
      }
    } catch (err) {
      toast(err.message, true);
    }
    lastJobsJson = "";
    pollJobs();
  });
  $("#clearDone").addEventListener("click", async () => {
    try { await api("/api/jobs/clear", { method: "POST", settings }); } catch (e) { toast(e.message, true); }
    lastJobsJson = "";
    pollJobs();
  });
}

// ------------------------------------------------------------------------

let toastTimer;
function toast(text, err = false) {
  const t = $("#toast");
  t.textContent = text;
  t.className = "toast" + (err ? " err" : "");
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), err ? 5000 : 2500);
}

// Damit Einstellungen aus dem Options-Tab sofort greifen
chrome.storage.onChanged.addListener(async (c, area) => {
  if (area !== "sync") return;
  settings = await getSettings();
  if (c.presets || c.hiddenBuiltins) renderPresets().then(render);
  $("#setupHint").hidden = !!settings.serverUrl;
});

