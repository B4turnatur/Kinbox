// Reine Helfer aus extension/lib/common.js:  node tests/test_common.mjs
import assert from "node:assert/strict";

// Nachgebauter chrome.storage: getrennte Bereiche (Browser) oder ein gemeinsamer (Android-App)
function area(data = {}) {
  return {
    data,
    async get(def) {
      if (typeof def === "string") return def in data ? { [def]: structuredClone(data[def]) } : {};
      return Object.fromEntries(Object.entries(def).map(([k, v]) => [k, structuredClone(k in data ? data[k] : v)]));
    },
    async set(p) { Object.assign(data, structuredClone(p)); },
    async remove(k) { delete data[k]; },
  };
}
globalThis.chrome = { storage: { sync: area(), local: area() } };
const C = await import("../extension/lib/common.js");
const { youtubeId, parseTime, fmtTime, presetOptions, diffOptions, sanitizeImport, DEFAULT_OPTIONS, BUILTIN_PRESETS } = C;

// ---- youtubeId
const yt = [
  ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"],
  ["https://www.youtube.com/watch?list=PL1&v=dQw4w9WgXcQ&t=42", "dQw4w9WgXcQ"],
  ["https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"],
  ["https://music.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"],
  ["https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
  ["https://www.youtube.com/shorts/abcdEFGH123", "abcdEFGH123"],
  ["https://www.youtube.com/live/abcdEFGH123?si=x", "abcdEFGH123"],
  ["https://www.youtube.com/embed/abcdEFGH123", "abcdEFGH123"],
  ["https://www.youtube.com/playlist?list=PL123", null],
  ["https://www.youtube.com/@kanal", null],
  ["https://www.notyoutube.org/watch?v=x", null],
  ["kein link", null],
];
for (const [u, id] of yt) assert.equal(youtubeId(u), id, u);

// ---- parseTime / fmtTime
assert.equal(parseTime(""), null);
assert.equal(parseTime("  "), null);
assert.equal(parseTime("90"), 90);
assert.equal(parseTime("1:30"), 90);
assert.equal(parseTime("1:02:03"), 3723);
assert.equal(parseTime("0:05.5"), 5.5);
assert.ok(Number.isNaN(parseTime("1:2:3:4")));
assert.ok(Number.isNaN(parseTime("abc")));
assert.ok(Number.isNaN(parseTime("1:234")));
assert.equal(fmtTime(null), "");
assert.equal(fmtTime(NaN), "");
assert.equal(fmtTime(0), "0:00");
assert.equal(fmtTime(65), "1:05");
assert.equal(fmtTime(3723), "1:02:03");
assert.equal(fmtTime(65, true), "0:01:05");
assert.equal(fmtTime(5.46), "0:05.5");
assert.equal(fmtTime(-3), "0:00");
for (const s of [0, 59, 61.5, 3599, 3600, 7322.3]) assert.equal(parseTime(fmtTime(s)), s, `Rundlauf ${s}`);

// ---- Presets (Befund: eingebaute Presets dürfen nichts vom eigenen Standard „erben“, was das Ergebnis verändert)
const builtin = (id) => BUILTIN_PRESETS.find((p) => p.id === id);
const whatsappAsDefault = presetOptions(null, builtin("whatsapp"));      // Nutzer hat „WhatsApp“ als Standard gespeichert
Object.assign(whatsappAsDefault, { alsoAudio: true, when: "night", musicOnly: true, musicTags: true, normalize: true, saveToPc: true, subfolder: "Handy", organize: "channel" });
whatsappAsDefault.subs.enabled = true;
whatsappAsDefault.sponsorblock.mode = "remove";

const best = presetOptions(whatsappAsDefault, builtin("best"));
assert.equal(best.convert.type, "none", "„Beste Qualität“ verkleinert nicht");
assert.equal(best.quality, "best");
assert.equal(best.alsoAudio, false);
assert.equal(best.when, "now");
assert.equal(best.musicOnly, false);
assert.equal(best.musicTags, false);
assert.equal(best.normalize, false);
assert.equal(best.subs.enabled, false);
assert.equal(best.subs.langs, DEFAULT_OPTIONS.subs.langs, "übrige Untertitel-Werte bleiben vollständig");
assert.equal(best.convert.targetMB, DEFAULT_OPTIONS.convert.targetMB, "convert bleibt vollständig");
// … aber persönliche Ablage-Einstellungen bleiben
assert.equal(best.saveToPc, true);
assert.equal(best.subfolder, "Handy");
assert.equal(best.organize, "channel");
assert.equal(best.sponsorblock.mode, "remove");

const wa = presetOptions(DEFAULT_OPTIONS, builtin("whatsapp"));
assert.equal(wa.convert.type, "small");
assert.equal(wa.convert.targetMB, 15);
assert.equal(wa.convert.gifFps, DEFAULT_OPTIONS.convert.gifFps);
assert.equal(presetOptions(whatsappAsDefault, builtin("both")).alsoAudio, true, "Preset darf neutrale Werte selbst setzen");
assert.equal(presetOptions(whatsappAsDefault, builtin("music")).musicTags, true);
assert.equal(presetOptions(whatsappAsDefault, builtin("podcast")).normalize, true);
assert.equal(presetOptions(whatsappAsDefault, { id: "mp3", options: { mode: "audio" } }).convert.type, "none", "MP3-Tastenkürzel = eingebaut");

// Standard (kein Preset) = eigene Standards
assert.deepEqual(presetOptions(whatsappAsDefault, null), whatsappAsDefault);
assert.deepEqual(presetOptions(null, null), DEFAULT_OPTIONS);
// presetOptions verändert seine Eingaben nicht
const before = JSON.stringify(whatsappAsDefault);
presetOptions(whatsappAsDefault, builtin("gif"));
assert.equal(JSON.stringify(whatsappAsDefault), before);
assert.equal(builtin("whatsapp").options.convert.gifFps, undefined, "BUILTIN_PRESETS unverändert");

// Eigene Presets: als Unterschied gespeichert, genau so wiederhergestellt – unabhängig vom Standard
const mine = structuredClone(DEFAULT_OPTIONS);
mine.quality = "1080"; mine.convert.type = "gif"; mine.sponsorblock.categories = ["sponsor"]; mine.subs.enabled = true;
const d = diffOptions(mine);
assert.deepEqual(d, { quality: "1080", convert: { type: "gif" }, sponsorblock: { categories: ["sponsor"] }, subs: { enabled: true } });
assert.deepEqual(diffOptions(DEFAULT_OPTIONS), {});
const user = { id: "u1", name: "Meins", options: d };
assert.deepEqual(presetOptions(whatsappAsDefault, user), mine, "eigenes Preset ignoriert den aktuellen Standard");
const oldFull = { id: "u2", name: "Alt", options: structuredClone(mine) };      // vor dieser Version: volle Optionen
assert.deepEqual(presetOptions(whatsappAsDefault, oldFull), mine, "alte, volle Presets bleiben lesbar");
// ein großes Preset passt jetzt locker in 8 KB pro storage.sync-Eintrag
const many = Array.from({ length: 30 }, (_, i) => ({ id: "u" + i, name: "Preset " + i, icon: "▶", options: diffOptions({ ...mine, quality: "720" }) }));
assert.ok(JSON.stringify(many).length < 8192, "30 Presets < 8 KB");

// ---- Import aus Datei
const imp = sanitizeImport({
  token: "geheim", serverUrl: "http://nas:8765", notify: "ja", socialOff: "tiktok", hiddenBuiltins: ["gif", 3, null],
  socialPos: "xx", accent: "#123456", unbekannt: 1, defaults: [1, 2],
  presets: [{ id: "u1", name: "Ok", icon: "▶", options: mine }, { id: 5, name: "kaputt", options: {} }, "x", { id: "u3", name: "ohne Optionen" }],
});
assert.deepEqual(Object.keys(imp).sort(), ["accent", "hiddenBuiltins", "presets", "serverUrl"]);
assert.deepEqual(imp.hiddenBuiltins, ["gif"]);
assert.equal(imp.presets.length, 1);
assert.deepEqual(imp.presets[0].options, d, "importierte Presets werden verkleinert");
assert.deepEqual(sanitizeImport({ socialOff: ["x"], socialPos: "br", notify: false, defaults: { quality: "720" } }),
  { socialOff: ["x"], socialPos: "br", notify: false, defaults: { quality: "720" } });
for (const bad of [null, 5, "x", [1]]) assert.deepEqual(sanitizeImport(bad), {});

// ---- Token: von storage.sync nach storage.local (einmalig), sync danach ohne Token
const { sync, local } = chrome.storage;
sync.data.token = "alt123"; sync.data.serverUrl = "http://nas:8765";
let s = await C.getSettings();
assert.equal(s.token, "alt123");
assert.equal(local.data.token, "alt123");
assert.ok(!("token" in sync.data), "Token aus sync gelöscht");
assert.equal((await C.getSettings()).token, "alt123", "zweiter Start: aus local");
await C.saveSettings({ token: "neu", notify: false });
assert.equal(local.data.token, "neu");
assert.ok(!("token" in sync.data));
assert.equal(sync.data.notify, false);
sync.data.token = "von-altem-PC";                                                      // ältere Version auf anderem PC
assert.equal((await C.getSettings()).token, "neu", "lokaler Token gewinnt");
assert.ok(!("token" in sync.data), "fremder sync-Token wird entfernt");
// Android-App: sync und local sind derselbe Speicher → nichts löschen
const one = area({ token: "app" });
chrome.storage = { sync: one, local: one };
assert.equal((await C.getSettings()).token, "app");
assert.equal(one.data.token, "app");
await C.saveSettings({ token: "app2" });
assert.equal((await C.getSettings()).token, "app2");

console.log("common ok");
