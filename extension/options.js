import { api, getSettings, saveSettings, normalizeUrl, BUILTIN_PRESETS, DEFAULT_OPTIONS, DEFAULT_SETTINGS, escapeHtml, libraryUrl, fmtBytes } from "./lib/common.js";

const $ = (s) => document.querySelector(s);
let settings;
let isAdminUser = true;

init();

async function init() {
  settings = await getSettings();
  $("#serverUrl").value = settings.serverUrl;
  $("#token").value = settings.token;
  $("#showYoutubeButton").checked = settings.showYoutubeButton;
  $("#notify").checked = settings.notify;
  $("#showSocialButtons").checked = settings.showSocialButtons;
  renderPresets();
  if (settings.serverUrl) test(false);

  $("#test").addEventListener("click", () => test(true));
  for (const id of ["showYoutubeButton", "showSocialButtons", "notify"]) {
    $("#" + id).addEventListener("change", (e) => saveSettings({ [id]: e.target.checked }));
  }
  $("#shortcuts").addEventListener("click", (e) => { e.preventDefault(); chrome.tabs.create({ url: "chrome://extensions/shortcuts" }); });
  $("#saveServer").addEventListener("click", saveServer);
  $("#update").addEventListener("click", updateYtdlp);
  $("#openLibrary").addEventListener("click", async () => chrome.tabs.create({ url: await libraryUrl() }));
  $("#famLink").addEventListener("click", async (e) => { e.preventDefault(); chrome.tabs.create({ url: await libraryUrl() }); });
  $("#saveCleanup").addEventListener("click", saveCleanup);
  $("#runCleanup").addEventListener("click", runCleanup);
  $("#resetDefaults").addEventListener("click", async () => {
    await saveSettings({ defaults: structuredClone(DEFAULT_OPTIONS) });
    flash($("#resetDefaults"), "Zurückgesetzt ✓");
  });
  $("#export").addEventListener("click", exportSettings);
  $("#import").addEventListener("click", () => $("#importFile").click());
  $("#importFile").addEventListener("change", importSettings);
}

function result(el, ok, html) {
  el.className = "result " + (ok ? "ok" : "bad");
  el.innerHTML = html;
}

async function test(save) {
  const url = normalizeUrl($("#serverUrl").value);
  const token = $("#token").value.trim();
  $("#serverUrl").value = url;
  if (save) {
    settings.serverUrl = url; settings.token = token;
    await saveSettings({ serverUrl: url, token });
  }
  if (!url) return result($("#testResult"), false, "Bitte die Adresse des Servers eintragen.");
  $("#testResult").className = "result ok";
  $("#testResult").textContent = "Verbinde …";
  try {
    const p = await api("/api/ping", { settings: { serverUrl: url, token }, timeout: 8000 });
    const y = (v) => (v ? `<span class="yes">✓ ${v === true ? "vorhanden" : escapeHtml(v)}</span>` : `<span class="no">✗ fehlt</span>`);
    const who = p.user ? `<div style="display:flex;align-items:center;gap:10px;margin-top:8px"><span style="width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-size:19px;background:${escapeHtml(p.user.color)}">${escapeHtml(p.user.avatar)}</span><span>Angemeldet als <b>${escapeHtml(p.user.name)}</b>${p.is_admin ? " (Admin)" : ""}</span></div>` : "";
    result($("#testResult"), true, `<b>Verbunden!</b>${who}
<div class="check" style="margin-top:8px">
  <b>yt-dlp</b><span>${escapeHtml(p.ytdlp)}</span>
  <b>ffmpeg</b>${y(p.ffmpeg)}
  <b>JavaScript</b>${y(p.js_runtime)}
  <b>Ordner</b><span>${escapeHtml(p.download_dir)}</span>
  <b>Cookies</b><span>${p.cookies ? "eingerichtet" : "keine (optional)"}</span>
</div>${!p.ffmpeg ? "<p>ffmpeg fehlt: install.bat erneut ausführen oder <code>winget install Gyan.FFmpeg</code>.</p>" : ""}${!p.js_runtime ? "<p>Ohne deno klappt YouTube oft nicht: <code>winget install DenoLand.Deno</code>, danach Server neu starten.</p>" : ""}`);
    $("#serverPanel").hidden = p.user ? !p.is_admin : false;
    $("#libRow").hidden = false;
    $("#downloadDir").value = p.download_dir;
    $("#maxParallel").value = String(p.max_parallel);
    fillCleanup(p);
  } catch (e) {
    let hint = "";
    if (e.status === 401) hint = "Der Token stimmt nicht. Kopiere ihn aus dem Server-Fenster oder aus settings.json.";
    else if (e.status === 0) hint = "Prüfe: Läuft start.bat auf dem Server? Stimmt die IP? Ist Port 8765 in der Windows-Firewall freigegeben (install.bat als Admin)?";
    result($("#testResult"), false, `<b>${escapeHtml(e.message)}</b>\n${hint}`);
    $("#serverPanel").hidden = true;
    $("#cleanupPanel").hidden = true;
  }
}

function fillCleanup(p) {
  if (!p.cleanup) return;          // alter Server ohne diese Funktion
  $("#cleanupPanel").hidden = false;
  $("#cAfter").checked = !!p.cleanup.after_pc_download;
  $("#cDays").value = p.cleanup.max_age_days || 0;
  $("#cGb").value = p.cleanup.max_size_gb || 0;
  const admin = p.user ? p.is_admin : true;
  $("#nightBox").hidden = !admin;
  document.querySelectorAll(".nightField").forEach((f) => (f.hidden = !admin));
  isAdminUser = admin;
  $("#nStart").value = (p.night?.start || "01:00").padStart(5, "0");
  $("#nEnd").value = (p.night?.end || "07:00").padStart(5, "0");
  renderLib(p.library, p.cleanup_log);
}

function renderLib(lib, log) {
  if (lib) $("#libStats").innerHTML = `<b>Mediathek:</b> ${lib.count} Dateien · ${fmtBytes(lib.size) || "0 B"}`;
  $("#cleanLog").innerHTML = (log || []).map((l) =>
    `${new Date(l.time * 1000).toLocaleString()} – ${escapeHtml(l.name)} (${fmtBytes(l.size)}) · ${escapeHtml(l.reason)}`).join("<br>");
}

async function saveCleanup() {
  try {
    const body = { cleanup: { after_pc_download: $("#cAfter").checked, max_age_days: +$("#cDays").value || 0, max_size_gb: +$("#cGb").value || 0 } };
    if (isAdminUser) body.night = { start: $("#nStart").value || "01:00", end: $("#nEnd").value || "07:00" };
    const p = await api("/api/settings", { method: "POST", body });
    const c = p.cleanup, parts = [];
    if (c.after_pc_download) parts.push(t("nach dem Laden aufs Gerät"));
    if (+c.max_age_days) parts.push(t(`nach ${c.max_age_days} Tagen`));
    if (+c.max_size_gb) parts.push(t(`ab ${c.max_size_gb} GB`));
    result($("#cleanupResult"), true, parts.length ? `Gespeichert. Automatisch löschen: ${escapeHtml(parts.join(" · "))}` : "Gespeichert. Automatisches Aufräumen ist aus.");
  } catch (e) { result($("#cleanupResult"), false, escapeHtml(e.message)); }
}

async function runCleanup() {
  try {
    const r = await api("/api/cleanup/run", { method: "POST" });
    result($("#cleanupResult"), true, r.removed ? `${r.removed} Dateien gelöscht.` : "Nichts zu löschen – alles innerhalb deiner Regeln.");
    renderLib(r.library, r.cleanup_log);
  } catch (e) { result($("#cleanupResult"), false, escapeHtml(e.message)); }
}

async function saveServer() {
  try {
    const p = await api("/api/settings", { method: "POST", body: { download_dir: $("#downloadDir").value.trim(), max_parallel: Number($("#maxParallel").value) } });
    result($("#serverResult"), true, `Gespeichert. Ordner: ${escapeHtml(p.download_dir)} · parallel: ${p.max_parallel}`);
  } catch (e) {
    result($("#serverResult"), false, escapeHtml(e.message));
  }
}

async function updateYtdlp() {
  const b = $("#update");
  b.disabled = true;
  b.textContent = "Aktualisiere … (kann dauern)";
  try {
    const r = await api("/api/update", { method: "POST", timeout: 320000 });
    result($("#serverResult"), r.ok, `${r.ok ? "Aktuell" : "Update fehlgeschlagen"}: yt-dlp ${escapeHtml(r.ytdlp)}\n<small class="muted">${escapeHtml(r.output)}</small>`);
  } catch (e) {
    result($("#serverResult"), false, escapeHtml(e.message));
  } finally {
    b.disabled = false;
    b.textContent = "yt-dlp aktualisieren";
  }
}

function describe(o) {
  if (o.mode === "audio") return `Audio · ${(o.audioFormat || "mp3").toUpperCase()}${o.audioBitrate && !["flac", "wav", "best"].includes(o.audioFormat) ? " " + o.audioBitrate + " kbps" : ""}`;
  if (o.mode === "thumbnail") return "Vorschaubild";
  if (o.convert?.type === "gif") return "Video → GIF";
  if (o.convert?.type === "small") return `Video → max. ${o.convert.targetMB} MB`;
  return `Video · ${o.quality === "best" || !o.quality ? t("beste Qualität") : o.quality + "p"} · ${(o.container || "mp4").toUpperCase()}`;
}

function renderPresets() {
  const list = $("#presetList");
  list.innerHTML =
    BUILTIN_PRESETS.map((p) => `
      <div class="pitem"><span>${escapeHtml(p.icon)}</span>
        <div class="n">${escapeHtml(p.name)}<div class="d">${t("Eingebaut")} · ${describe(p.options)}</div></div>
        <label class="switch small" title="Anzeigen"><input type="checkbox" data-builtin="${p.id}" ${settings.hiddenBuiltins.includes(p.id) ? "" : "checked"}><span></span></label>
      </div>`).join("") +
    settings.presets.map((p) => `
      <div class="pitem"><span>${escapeHtml(p.icon || "•")}</span>
        <div class="n">${escapeHtml(p.name)}<div class="d">${describe(p.options)}</div></div>
        <button class="link" data-default="${p.id}">Als Standard</button>
        <button class="link" data-rename="${p.id}">Umbenennen</button>
        <button class="link" data-del="${p.id}" style="color:var(--err)">Löschen</button>
      </div>`).join("");

  list.onchange = async (e) => {
    const id = e.target.dataset.builtin;
    if (!id) return;
    const set = new Set(settings.hiddenBuiltins);
    e.target.checked ? set.delete(id) : set.add(id);
    settings.hiddenBuiltins = [...set];
    await saveSettings({ hiddenBuiltins: settings.hiddenBuiltins });
  };
  list.onclick = async (e) => {
    const el = e.target;
    if (el.dataset.del) {
      settings.presets = settings.presets.filter((p) => p.id !== el.dataset.del);
      await saveSettings({ presets: settings.presets });
    } else if (el.dataset.rename) {
      const p = settings.presets.find((x) => x.id === el.dataset.rename);
      const name = prompt(t("Neuer Name:"), p.name);
      if (!name) return;
      p.name = name.trim();
      await saveSettings({ presets: settings.presets });
    } else if (el.dataset.default) {
      const p = settings.presets.find((x) => x.id === el.dataset.default);
      await saveSettings({ defaults: { ...structuredClone(DEFAULT_OPTIONS), ...structuredClone(p.options) } });
      flash(el, "✓ Standard");
      return;
    } else return;
    renderPresets();
  };
}

function flash(el, text) {
  const old = el.textContent;
  el.textContent = text;
  setTimeout(() => (el.textContent = old), 1500);
}

async function exportSettings() {
  const s = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  delete s.token;
  const blob = new Blob([JSON.stringify(s, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "kinbox-einstellungen.json";
  a.click();
}

async function importSettings(e) {
  const f = e.target.files[0];
  if (!f) return;
  try {
    const data = JSON.parse(await f.text());
    const allowed = Object.fromEntries(Object.entries(data).filter(([k]) => k in DEFAULT_SETTINGS && k !== "token"));
    await saveSettings(allowed);
    location.reload();
  } catch {
    alert(t("Die Datei konnte nicht gelesen werden."));
  }
}
