// Heim-/Unterwegs-Adresse: nimmt die erreichbare Adresse (node tests/test_failover.mjs)
import http from "node:http";
import assert from "node:assert";
globalThis.chrome = { storage: { sync: { get: async (d) => d } } };
const { serverBase, api } = await import("../extension/lib/common.js");

const srv = http.createServer((q, r) => { r.setHeader("Content-Type", "application/json"); r.end('{"ok":true}'); });
await new Promise((ok) => srv.listen(0, "127.0.0.1", ok));
const away = `http://127.0.0.1:${srv.address().port}`;
const home = "http://127.0.0.1:1";   // nicht erreichbar

assert.equal(await serverBase({ serverUrl: away }), away);
assert.equal(await serverBase({ serverUrl: home, serverUrl2: away }, true), away);
assert.equal(await serverBase({ serverUrl: away, serverUrl2: home }, true), away);
assert.deepEqual(await api("/api/ping", { settings: { serverUrl: home, serverUrl2: away, token: "x" } }), { ok: true });
srv.close();
console.log("failover ok");
