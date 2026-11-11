// Heim-/Unterwegs-Adresse: nimmt die erreichbare Adresse (node tests/test_failover.mjs)
import http from "node:http";
import assert from "node:assert";
globalThis.chrome = { storage: { sync: { get: async (d) => d } } };
const { serverBase, api } = await import("../extension/lib/common.js");

let pings = 0, posts = 0, slow = false;
const srv = http.createServer((q, r) => {
  if (q.url === "/api/ping") pings++;
  if (q.method === "POST") posts++;
  r.setHeader("Content-Type", "application/json");
  if (slow && q.url !== "/api/ping") return setTimeout(() => r.end('{"ok":true}'), 500);
  r.end('{"ok":true}');
});
await new Promise((ok) => srv.listen(0, "127.0.0.1", ok));
const away = `http://127.0.0.1:${srv.address().port}`;
const home = "http://127.0.0.1:1";   // nicht erreichbar

assert.equal(await serverBase({ serverUrl: away }), away);
assert.equal(await serverBase({ serverUrl: home, serverUrl2: away }, true), away);
assert.equal(await serverBase({ serverUrl: away, serverUrl2: home }, true), away);
assert.deepEqual(await api("/api/ping", { settings: { serverUrl: home, serverUrl2: away, token: "x" } }), { ok: true });

// Gleichzeitige Aufrufe teilen sich EINE Prüfung (je Adresse ein Ping)
const both = { serverUrl: `http://localhost:${srv.address().port}`, serverUrl2: away };
pings = 0;
const r = await Promise.all([serverBase(both, true), serverBase(both), serverBase(both), serverBase(both)]);
assert.deepEqual(r, Array(4).fill(both.serverUrl), "Heim bevorzugt, wenn beide antworten");
assert.equal(pings, 2, "eine gemeinsame Prüfung, Heim und Unterwegs parallel");
pings = 0;
assert.equal(await serverBase(both), both.serverUrl);
assert.equal(pings, 0, "Ergebnis wird gemerkt");

// storage.session: anderer Teil der Erweiterung (frischer Modulzustand) übernimmt das Ergebnis
const session = {};
globalThis.chrome.storage.session = { get: async (k) => (k in session ? { [k]: session[k] } : {}), set: async (p) => Object.assign(session, p) };
const order = { serverUrl: home, serverUrl2: away };
assert.equal(await serverBase(order, true), away);
assert.equal(session.kbBase?.base, away, "in storage.session gemerkt");
const fresh = await import("../extension/lib/common.js?zweite-instanz");
pings = 0;
assert.equal(await fresh.serverBase(order), away);
assert.equal(pings, 0, "aus storage.session, ohne neue Prüfung");
session.kbBase.at -= 120000;                                       // abgelaufen → neu prüfen
assert.equal(await fresh.serverBase({ serverUrl: away, serverUrl2: home }), away);
delete globalThis.chrome.storage.session;

// Wiederholen: POST nur, wenn danach die ANDERE Adresse gilt; Zeitüberschreitung nie
const flip = { serverUrl: home, serverUrl2: away, token: "x" };
const inst = await import("../extension/lib/common.js?dritte-instanz");
assert.equal(await inst.serverBase(flip, true), away);
posts = 0;
await assert.rejects(inst.api("/api/jobs", { method: "POST", body: {}, settings: { serverUrl: "http://127.0.0.1:2", serverUrl2: "http://127.0.0.1:3", token: "x" } }), /nicht erreichbar/);
slow = true; posts = 0;
await assert.rejects(inst.api("/api/jobs", { method: "POST", body: {}, timeout: 100, settings: flip }), /Zeitüberschreitung/);
await new Promise((ok) => setTimeout(ok, 600));
assert.equal(posts, 1, "nach Zeitüberschreitung kein zweiter POST");
slow = false;
// gemerkt war die (inzwischen tote) Heim-Adresse → POST scheitert sofort → Prüfung → einmal über Unterwegs
const stale = { kbBase: { key: `${home} ${away}`, base: home, at: Date.now() } };
globalThis.chrome.storage.session = { get: async () => stale, set: async (p) => Object.assign(stale, p) };
const inst4 = await import("../extension/lib/common.js?vierte-instanz");
posts = 0;
assert.deepEqual(await inst4.api("/api/jobs", { method: "POST", body: {}, settings: flip }), { ok: true });
assert.equal(posts, 1, "genau ein POST über die andere Adresse");
assert.equal(stale.kbBase.base, away);
delete globalThis.chrome.storage.session;

srv.close();
console.log("failover ok");
