// Jeder feste Text in t("…") der Erweiterung hat eine englische Übersetzung:  node tests/test_i18n_literals.mjs
// (Texte mit ${…} werden über PAT-Muster übersetzt und hier nicht geprüft.)
import { readFileSync, readdirSync } from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../extension/", import.meta.url);
const g = { navigator: { languages: ["en-US"] } };
new Function("globalThis", "navigator", readFileSync(new URL("lib/i18n.js", root), "utf8"))(g, g.navigator);

const files = [
  ...readdirSync(root).filter((f) => f.endsWith(".js")),
  ...readdirSync(new URL("content/", root)).filter((f) => f.endsWith(".js")).map((f) => "content/" + f),
];
const missing = [];
let n = 0;
for (const f of files) {
  const src = readFileSync(new URL(f, root), "utf8");
  for (const m of src.matchAll(/(?<![\w.$])t\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|`((?:[^`\\$]|\\.)*)`)\s*\)/g)) {
    const text = JSON.parse(`"${(m[1] ?? m[2] ?? m[3]).replace(/\\'/g, "'").replace(/\\`/g, "`").replace(/"/g, '\\"')}"`);
    if (!/\p{L}/u.test(text)) continue;
    n++;
    if (g.t(text) === text) missing.push(`${f}: ${text}`);
  }
}
assert.ok(n > 20, `zu wenige t()-Texte gefunden (${n}) – Suchmuster kaputt?`);
assert.deepEqual(missing, [], "Ohne englische Übersetzung (in extension/lib/i18n.js ergänzen)");
console.log(`i18n-Literale ok (${n} Texte)`);
