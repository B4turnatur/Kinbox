// Kinbox-App: ersetzt die chrome.*-Schnittstellen der Erweiterung, damit Popup und Einstellungen
// unverändert in der Android-App laufen. Gegenstück: MainActivity.Bridge (KinboxApp).
(() => {
  const K = window.KB_KEY, A = window.KinboxApp;
  const P = new URLSearchParams(location.search);
  const lib = () => import("/kbapp/lib/common.js");
  const store = () => JSON.parse(A.load(K) || "{}");
  const listeners = [];

  function get(def, cb) {
    const s = store();
    let r;
    if (def == null) r = s;
    else if (typeof def === "string") r = def in s ? { [def]: s[def] } : {};
    else if (Array.isArray(def)) r = Object.fromEntries(def.filter((k) => k in s).map((k) => [k, s[k]]));
    else r = Object.fromEntries(Object.entries(def).map(([k, v]) => [k, k in s ? s[k] : v]));
    r = structuredClone(r);
    cb?.(r);
    return Promise.resolve(r);
  }
  function set(patch, cb) {
    const s = store(), changes = {};
    for (const [k, v] of Object.entries(patch)) { changes[k] = { oldValue: s[k], newValue: v }; s[k] = v; }
    A.save(K, JSON.stringify(s));
    for (const f of listeners) f(changes, "sync");
    cb?.();
    return Promise.resolve();
  }
  const area = { get, set };

  // Links: Kinbox-Seiten in der App, alles andere im Browser
  function go(url) {
    const u = new URL(url, location.href);
    if (u.host === location.host) location.href = u.href;
    else if (/^https?:$/.test(u.protocol)) A.open(K, u.href);
  }

  window.chrome = {
    storage: { sync: area, local: area, onChanged: { addListener: (f) => listeners.push(f) } },
    tabs: {
      query: async () => [],
      get: async () => ({ id: 1, title: P.get("title") || "", url: P.get("url") || "" }),
      create: ({ url }) => go(url),
      sendMessage: async () => { throw new Error("kein Tab"); },
    },
    runtime: {
      openOptionsPage: () => (location.href = "/kbapp/options.html"),
      onMessage: { addListener() {} },
      async sendMessage(m) {
        try {
          if (m.type === "queue") {
            const { api } = await lib();
            const job = await api("/api/jobs", { method: "POST", body: m.options });
            A.track(K, job.id, !!m.options.saveToPc);
            return { ok: true, job };
          }
          if (m.type === "track") A.track(K, m.id, !!m.saveToPc);
          return { ok: true };
        } catch (e) {
          return { ok: false, error: e.message };
        }
      },
    },
    downloads: { download: async ({ url, filename }) => A.download(K, url, filename) },
  };

  // Was es nur im Browser gibt (YouTube-Knöpfe, Tastenkürzel, Export als Datei), ausblenden
  document.documentElement.classList.add("kb-app");
  const css = document.createElement("style");
  css.textContent = `label:has(#showYoutubeButton), label:has(#showSocialButtons), p:has(#shortcuts), #export { display: none !important; }`;
  document.head.appendChild(css);
})();
