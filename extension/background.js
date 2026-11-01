import "./lib/i18n.js";
import { api, getSettings, allPresets, deepMerge, DEFAULT_OPTIONS, fileUrl, libraryUrl, youtubeId, isSocial, mediaUrlForTab, injectContent } from "./lib/common.js";

// ------------------------------------------------------------------------
// Kontextmenü
// ------------------------------------------------------------------------

// Nacheinander: zwei gleichzeitige Durchläufe (Installation + Preset-Änderung) gäben „duplicate id“-Fehler.
let menuQueue = Promise.resolve();
const buildMenus = () => (menuQueue = menuQueue.catch(() => {}).then(rebuildMenus));

async function rebuildMenus() {
  await chrome.contextMenus.removeAll();
  const contexts = ["link", "page", "video", "audio", "image"];
  chrome.contextMenus.create({ id: "root", title: t("Mit Kinbox herunterladen"), contexts });
  chrome.contextMenus.create({ id: "default", parentId: "root", title: t("Standard-Einstellungen"), contexts });
  chrome.contextMenus.create({ id: "sep1", parentId: "root", type: "separator", contexts });
  for (const p of await allPresets()) {
    chrome.contextMenus.create({ id: "preset:" + p.id, parentId: "root", title: `${p.icon || "•"}  ${t(p.name)}`, contexts });
  }
  chrome.contextMenus.create({ id: "sep2", parentId: "root", type: "separator", contexts });
  chrome.contextMenus.create({ id: "custom", parentId: "root", title: t("Mit Optionen…"), contexts });
}

chrome.runtime.onInstalled.addListener(async (d) => {
  await buildMenus();
  const s = await getSettings();
  if (d.reason === "install" || !s.serverUrl) chrome.runtime.openOptionsPage();
  // Schon offene Tabs bekommen die Content-Skripte sonst erst nach dem Neuladen (nach Updates: tote Knöpfe)
  if (d.reason === "install" || d.reason === "update") {
    for (const cs of chrome.runtime.getManifest().content_scripts) {
      for (const tab of await chrome.tabs.query({ url: cs.matches })) injectContent(tab.id, cs.js.at(-1)).catch(() => {});
    }
  }
});
chrome.runtime.onStartup.addListener(() => { buildMenus(); poll(); });

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "sync" && (changes.presets || changes.hiddenBuiltins)) buildMenus();
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  let url = info.linkUrl || info.pageUrl;
  if ((info.mediaType === "video" || info.mediaType === "audio") && info.srcUrl && !info.srcUrl.startsWith("blob:")) {
    url = youtubeId(info.pageUrl) ? info.pageUrl : info.srcUrl;
  }
  if (info.menuItemId === "custom") {
    if (!info.linkUrl && isSocial(info.pageUrl)) url = (await mediaUrlForTab(tab, "contextMediaUrl")) || (await mediaUrlForTab(tab)) || url;
    return openOptionsWindow(url, tab?.id);
  }
  let presetOpts = {};
  if (String(info.menuItemId).startsWith("preset:")) {
    const p = (await allPresets()).find((x) => "preset:" + x.id === info.menuItemId);
    presetOpts = p?.options || {};
  }
  if (!info.linkUrl && isSocial(info.pageUrl)) {
    url = (await mediaUrlForTab(tab, "contextMediaUrl")) || url;
    if (url === info.pageUrl) url = (await mediaUrlForTab(tab)) || url;
  }
  const sameAsPage = url === info.pageUrl;
  await quickQueue(url, presetOpts, sameAsPage ? { title: tab?.title } : {}, tab?.id);
});

chrome.commands.onCommand.addListener(async (cmd, tab) => {
  tab = tab || (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
  if (!tab?.url) return;
  const url = await mediaUrlForTab(tab);
  const meta = { title: url === tab.url ? tab.title : "" };
  if (cmd === "quick-download") await quickQueue(url, {}, meta, tab.id);
  if (cmd === "quick-mp3") await quickQueue(url, { mode: "audio", audioFormat: "mp3", audioBitrate: "320" }, meta, tab.id);
});

function openOptionsWindow(url, tabId) {
  const q = new URLSearchParams({ url: url || "", tab: tabId ?? "", window: "1" });
  return chrome.windows.create({ url: chrome.runtime.getURL("popup.html?" + q), type: "popup", width: 460, height: 780 });
}

// ------------------------------------------------------------------------
// Aufträge anlegen
// ------------------------------------------------------------------------

function cleanTitle(title) {
  return (title || "").replace(/^\(\d+\)\s*/, "").replace(/\s*[-–|]\s*YouTube( Music)?$/i, "").trim();
}

export async function queueJob(options) {
  const job = await api("/api/jobs", { method: "POST", body: options });
  await track(job.id, { saveToPc: !!options.saveToPc, title: job.title });
  poll();
  return job;
}

async function quickQueue(url, presetOpts, meta = {}, tabId) {
  const s = await getSettings();
  const opts = deepMerge(deepMerge(structuredClone(DEFAULT_OPTIONS), s.defaults), presetOpts);
  opts.url = url;
  if (meta.title) opts.title = cleanTitle(meta.title);
  const yt = youtubeId(url);
  if (yt) opts.thumbnail = `https://i.ytimg.com/vi/${yt}/hqdefault.jpg`;
  try {
    const job = await queueJob(opts);
    toast(tabId, `✓ ${t("Zur Warteschlange hinzugefügt")}: ${job.title}`);
    return job;
  } catch (e) {
    toast(tabId, `✗ ${t(e.message)}`, true);
    notify("err-" + Date.now(), t("Download fehlgeschlagen"), t(e.message));
    throw e;
  }
}

async function toast(tabId, text, error = false) {
  if (!tabId) return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      args: [text, error],
      func: (text, error) => {
        const el = document.createElement("div");
        el.textContent = text;
        Object.assign(el.style, {
          position: "fixed", bottom: "24px", left: "50%", transform: "translateX(-50%) translateY(20px)",
          background: error ? "#b3261e" : "#1f1f23", color: "#fff", padding: "12px 18px", borderRadius: "12px",
          font: "500 14px system-ui, sans-serif", zIndex: 2147483647, boxShadow: "0 8px 30px rgba(0,0,0,.35)",
          opacity: "0", transition: "all .25s ease", maxWidth: "80vw", borderLeft: `4px solid ${error ? "#ffb4ab" : "#7c5cff"}`,
        });
        document.documentElement.appendChild(el);
        requestAnimationFrame(() => { el.style.opacity = "1"; el.style.transform = "translateX(-50%)"; });
        setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 300); }, 3500);
      },
    });
  } catch { /* Seite erlaubt kein Skript (z. B. chrome://) */ }
}

// ------------------------------------------------------------------------
// Fortschritt verfolgen: Badge, Benachrichtigungen, auf PC speichern
// ------------------------------------------------------------------------

// Lesen-Ändern-Schreiben nacheinander, sonst überschreibt pollOnce() einen gerade neu verfolgten Auftrag
// (dann fehlten Benachrichtigung und „Auf PC speichern“).
let trackQueue = Promise.resolve();
function editTracked(fn) {
  return (trackQueue = trackQueue.catch(() => {}).then(async () => {
    const { tracked = {} } = await chrome.storage.local.get("tracked");
    fn(tracked);
    await chrome.storage.local.set({ tracked });
  }));
}

function track(id, data) {
  return editTracked((tracked) => { tracked[id] = { ...data, added: Date.now() }; });
}

let polling = false;

async function poll() {
  if (polling) return;
  polling = true;
  try {
    for (let i = 0; i < 400; i++) {             // max. ~20 Min am Stück, danach übernimmt der Alarm
      const active = await pollOnce();
      if (!active) break;
      await new Promise((r) => setTimeout(r, 3000));
    }
  } finally {
    polling = false;
  }
}

async function pollOnce() {
  let jobs;
  try {
    jobs = await api("/api/jobs", { timeout: 8000 });
  } catch {
    showBadge([]);
    return false;
  }
  const active = jobs.filter((j) => j.status === "running" || j.status === "queued");
  showBadge(active);

  const { tracked = {} } = await chrome.storage.local.get("tracked");
  const s = await getSettings();
  const gone = [];
  for (const [id, tk] of Object.entries(tracked)) {
    const j = jobs.find((x) => x.id === id);
    if (!j) {
      if (Date.now() - tk.added > 86400000) gone.push(id);
      continue;
    }
    if (j.status === "finished") {
      if (s.notify) notify("done-" + id, t("Download fertig ✓"), j.title, j.files.length && !tk.saveToPc);
      if (tk.saveToPc) await saveToPc(j);
      gone.push(id);
    } else if (j.status === "error") {
      if (s.notify) notify("err-" + id, t("Download fehlgeschlagen"), `${j.title}\n${t(j.error)}`);
      gone.push(id);
    } else if (j.status === "cancelled") {
      gone.push(id);
    }
  }
  if (gone.length) await editTracked((tr) => { for (const id of gone) delete tr[id]; });
  return active.length > 0;
}

// Badge: Anzahl laufender Downloads, bei genau einem der Fortschritt in %; Tooltip listet die Aufträge.
function showBadge(active) {
  const pct = active.length === 1 && active[0].status === "running" && active[0].percent;
  chrome.action.setBadgeBackgroundColor({ color: "#7c5cff" });
  chrome.action.setBadgeText({ text: pct ? Math.floor(pct) + "%" : active.length ? String(active.length) : "" });
  const lines = active.slice(0, 5).map((j) => `${j.status === "running" ? Math.floor(j.percent || 0) + " %" : t("Wartet")} · ${j.title}`);
  if (active.length > 5) lines.push(t(`+ ${active.length - 5} weitere`));
  chrome.action.setTitle({ title: [chrome.i18n.getMessage("actionTitle"), ...lines].join("\n") });
}

async function saveToPc(job) {
  for (let i = 0; i < job.files.length; i++) {
    if (!job.files[i].exists) continue;
    chrome.downloads.download({ url: await fileUrl(job.id, i), filename: job.files[i].name.replace(/[\\/:*?"<>|]/g, "_"), conflictAction: "uniquify" });
  }
}

function notify(id, title, message, withSaveButton = false) {
  chrome.notifications.create(id, {
    type: "basic", iconUrl: "icons/icon128.png", title, message: message || "",
    buttons: withSaveButton ? [{ title: t("Auf diesen PC speichern") }] : [],
    priority: 0,
  });
}

chrome.notifications.onButtonClicked.addListener(async (nid) => {
  if (!nid.startsWith("done-")) return;
  try {
    const job = await api("/api/jobs/" + nid.slice(5));
    await saveToPc(job);
  } catch (e) { notify("err-" + Date.now(), t("Speichern fehlgeschlagen"), t(e.message)); }
  chrome.notifications.clear(nid);
});

// Klick auf „Download fertig“ öffnet die Mediathek
chrome.notifications.onClicked.addListener(async (nid) => {
  chrome.notifications.clear(nid);
  if (nid.startsWith("done-")) chrome.tabs.create({ url: await libraryUrl() });
});

chrome.alarms.create("poll", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "poll") poll(); });

// ------------------------------------------------------------------------
// Nachrichten von Popup und YouTube-Skript
// ------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    try {
      switch (msg.type) {
        case "presets":
          return reply({ ok: true, presets: await allPresets() });
        case "quick": {
          let opts = msg.options || {};
          if (msg.presetId) opts = (await allPresets()).find((p) => p.id === msg.presetId)?.options || {};
          const job = await quickQueue(msg.url, opts, { title: msg.title }, sender.tab?.id);
          return reply({ ok: true, job });
        }
        case "queue":
          return reply({ ok: true, job: await queueJob(msg.options) });
        case "openCustom":
          await openOptionsWindow(msg.url, sender.tab?.id);
          return reply({ ok: true });
        case "track":
          await track(msg.id, { saveToPc: !!msg.saveToPc, title: msg.title });
          poll();
          return reply({ ok: true });
        case "poll":
          poll();
          return reply({ ok: true });
        default:
          return reply({ ok: false, error: "Unbekannte Nachricht" });
      }
    } catch (e) {
      reply({ ok: false, error: e.message });
    }
  })();
  return true;
});
