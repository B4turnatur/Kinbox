// content/social.js ohne Browser: welche Adresse meldet das Skript dem Popup/Tastenkürzel?
// TikTok-Sound- (/music/…) und Profilseiten (/@name) ohne Hover-Ziel = die Seite selbst, nicht ein Raster-Video.
// Start: node tests/test_social.mjs
import { readFileSync } from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";

const code = readFileSync(new URL("../extension/content/social.js", import.meta.url), "utf8");

// Platzhalter-Objekt: jede Eigenschaft/jeder Aufruf liefert wieder einen Platzhalter (für DOM-Teile, die hier egal sind)
const dummy = new Proxy(function () {}, {
  get: (_, k) => (k === Symbol.toPrimitive ? () => "" : k === Symbol.iterator ? [][Symbol.iterator].bind([]) : dummy),
  apply: () => dummy, construct: () => dummy, set: () => true,
});

function run(href, videos = []) {
  const url = new URL(href);
  let listener;
  const video = (id, author) => ({
    tagName: "VIDEO", paused: false, id: "", parentElement: { id: `xgwrapper-0-${id}`, tagName: "DIV", parentElement: null,
      closest: () => ({ querySelector: () => ({ getAttribute: () => `/@${author}`, textContent: author }) }) },
    getBoundingClientRect: () => ({ left: 0, top: 0, right: 400, bottom: 700, width: 400, height: 700 }),
    closest: () => null, matches: () => true,
  });
  const document = new Proxy({}, {
    get: (_, k) => k === "querySelectorAll" ? () => videos.map(([id, a]) => video(id, a)) : dummy,
  });
  const ctx = {
    location: { hostname: url.hostname, pathname: url.pathname, href: url.href, origin: url.origin },
    document, innerWidth: 1200, innerHeight: 800, window: {},
    chrome: {
      runtime: { id: "x", onMessage: { addListener: (f) => (listener = f) }, sendMessage: async () => null },
      storage: { sync: { get: () => {}, set: () => {} }, onChanged: { addListener() {} } },
    },
    translateEl() {}, kbIcon: () => "", t: (s) => s, addEventListener() {}, requestAnimationFrame: () => 1,
    setTimeout, clearTimeout, URL,
  };
  vm.runInNewContext(code, ctx);
  return (type = "currentMediaUrl") => new Promise((ok) => listener({ type }, {}, ok));
}

const RASTER = [["7300000000000000001", "jemand"]];
const cases = [
  ["https://www.tiktok.com/music/Original-Sound-7123456789012345678", "https://www.tiktok.com/music/Original-Sound-7123456789012345678"],
  ["https://www.tiktok.com/music/Song-7123456789012345678?lang=de", "https://www.tiktok.com/music/Song-7123456789012345678"],
  ["https://www.tiktok.com/@kanal", "https://www.tiktok.com/@kanal"],
  ["https://www.tiktok.com/@ka.nal_1/", "https://www.tiktok.com/@ka.nal_1/"],
  // Videoseite / Startseite: weiterhin das sichtbare Video
  ["https://www.tiktok.com/@kanal/video/7300000000000000001", "https://www.tiktok.com/@jemand/video/7300000000000000001"],
  ["https://www.tiktok.com/foryou", "https://www.tiktok.com/@jemand/video/7300000000000000001"],
];
for (const [page, want] of cases) assert.equal((await run(page, RASTER)()).url, want, page);
// ohne Videos: Sound-/Profilseite trotzdem die Seite, sonst nichts
assert.equal((await run("https://www.tiktok.com/@kanal")()).url, "https://www.tiktok.com/@kanal");
assert.equal((await run("https://www.tiktok.com/foryou")()).url, null);
// andere Seiten unverändert (Instagram-Profil ist nicht gemeint)
assert.equal((await run("https://www.instagram.com/kanal/")()).url, null);
// Rechtsklick ohne Video darunter → null (Hintergrund fragt dann currentMediaUrl)
assert.equal((await run("https://www.tiktok.com/@kanal", RASTER)("contextMediaUrl")).url, null);

console.log(`social ok (${cases.length + 4} Fälle)`);
