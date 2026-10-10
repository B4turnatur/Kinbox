// Selbsttest der Übersetzung:  node tests/test_i18n.mjs
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const ext = readFileSync(new URL("../extension/lib/i18n.js", import.meta.url), "utf8");
const srv = readFileSync(new URL("../server/static/i18n.js", import.meta.url), "utf8");
assert.equal(ext, srv, "extension/lib/i18n.js und server/static/i18n.js müssen identisch sein");

const load = (lang) => {
  const g = { navigator: { languages: [lang] } };
  new Function("globalThis", "navigator", ext)(g, g.navigator);
  return g.t;
};

const t = load("en-US");
const cases = [
  ["Speichern", "Save"],
  ["⬇ Auf PC", "⬇ To PC"],                                 // Symbol bleibt erhalten
  ["  Wer schaut?  ", "  Who's watching?  "],               // Rand-Leerzeichen bleiben
  ["MP4 (empfohlen)", "MP4 (recommended)"],
  ["Lädt herunter (3/10)", "Downloading (3/10)"],
  ["✓ Schon in der Kinbox (vor 3 Tagen):", "✓ Already in Kinbox (3 days ago):"],   // Platzhalter rekursiv
  ["noch 1:20", "1:20 left"],
  ["Ungültiger Wert für fps", "Invalid value for fps"],
  ["Mein Lieblingsvideo", "Mein Lieblingsvideo"],          // Unbekanntes bleibt unverändert
  ["⭐", "⭐"],
];
for (const [de, en] of cases) assert.equal(t(de), en, de);

assert.equal(load("de-DE")("Speichern"), "Speichern", "deutscher Browser: keine Übersetzung");
console.log(`i18n ok (${cases.length + 1} Fälle)`);
