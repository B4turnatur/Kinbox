// Fügt auf YouTube einen „Kinbox"-Button unter dem Video ein (mit Schnellmenü).
(() => {
  const BTN_ID = "kinbox-btn";
  const MENU_ID = "kinbox-menu";
  let presets = [];
  let enabled = true;

  // Gewählte Akzentfarbe/Stil (Einstellungen → Aussehen) an die Kinbox-Knöpfe weitergeben.
  const look = (s) => { const d = document.documentElement; d.style.setProperty("--kb-accent", s.accent); d.dataset.kbStyle = s.style; };
  chrome.storage.sync.get({ style: "classic", accent: "#7c5cff" }, look);
  chrome.storage.onChanged.addListener((c, area) => {
    if (area === "sync" && (c.style || c.accent)) chrome.storage.sync.get({ style: "classic", accent: "#7c5cff" }, look);
  });
  chrome.storage.sync.get({ showYoutubeButton: true }, (s) => {
    enabled = s.showYoutubeButton;
    if (enabled) start();
  });
  chrome.storage.onChanged.addListener((c, area) => {
    if (area === "sync" && c.showYoutubeButton) {
      enabled = c.showYoutubeButton.newValue;
      enabled ? start() : document.getElementById(BTN_ID)?.remove();
    }
    if (area === "sync" && (c.presets || c.hiddenBuiltins)) presets = [];
  });

  let started = false;
  function start() {
    if (started) { inject(); return; }
    started = true;
    document.addEventListener("yt-navigate-finish", () => setTimeout(inject, 300));
    let pending = null;
    new MutationObserver(() => {
      if (pending || document.getElementById(BTN_ID)?.isConnected) return;
      pending = setTimeout(() => { pending = null; inject(); }, 400);
    }).observe(document.documentElement, { childList: true, subtree: true });
    inject();
  }

  function isVideoPage() {
    return /^\/(watch|shorts\/|live\/)/.test(location.pathname) || location.hostname === "music.youtube.com" && location.pathname === "/watch";
  }

  const ANCHORS = [
    "ytd-watch-metadata #actions #top-level-buttons-computed",
    "ytd-watch-metadata #actions-inner #menu",
    "#info #menu-container #top-level-buttons-computed",
    "ytmusic-player-bar .middle-controls-buttons",
  ];

  let injecting = false;
  function inject() {
    if (!enabled || injecting) return;
    const existing = document.getElementById(BTN_ID);
    if (!isVideoPage()) { existing?.remove(); return; }
    if (existing && existing.isConnected) return;
    injecting = true;
    try {
      const anchor = ANCHORS.map((s) => document.querySelector(s)).find((el) => el && el.offsetParent !== null);
      const wrap = document.createElement("div");
      wrap.id = BTN_ID;
      wrap.innerHTML = `
        <button class="kinbox-main" title="Mit Kinbox herunterladen">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M12 3a1 1 0 0 1 1 1v9.59l3.3-3.3a1 1 0 1 1 1.4 1.42l-5 5a1 1 0 0 1-1.4 0l-5-5a1 1 0 1 1 1.4-1.42l3.3 3.3V4a1 1 0 0 1 1-1zM5 19h14a1 1 0 1 1 0 2H5a1 1 0 1 1 0-2z"/></svg>
          <span>Kinbox</span>
        </button>
        <button class="kinbox-more" title="Mehr Optionen">${kbIcon("chevron")}</button>`;
      translateEl(wrap);
      if (anchor) {
        anchor.prepend(wrap);
      } else if (/^\/shorts\//.test(location.pathname)) {
        wrap.classList.add("kinbox-floating");
        document.body.appendChild(wrap);
      } else {
        return; // Seite noch nicht fertig – der Observer versucht es erneut
      }
      wrap.querySelector(".kinbox-main").addEventListener("click", (e) => { e.stopPropagation(); quick(null); });
      wrap.querySelector(".kinbox-more").addEventListener("click", (e) => { e.stopPropagation(); toggleMenu(wrap); });
    } finally {
      injecting = false;
    }
  }

  async function toggleMenu(wrap) {
    if (document.getElementById(MENU_ID)) return closeMenu();
    if (!presets.length) {
      const r = await chrome.runtime.sendMessage({ type: "presets" }).catch(() => null);
      presets = r?.presets || [];
    }
    const menu = document.createElement("div");
    menu.id = MENU_ID;
    const add = (ic, label, fn, cls = "") => {
      const b = document.createElement("button");
      b.className = cls;
      b.innerHTML = kbIcon(ic);
      b.append(t(label));
      b.addEventListener("click", (e) => { e.stopPropagation(); closeMenu(); fn(); });
      menu.appendChild(b);
    };
    add("download", "Standard-Einstellungen", () => quick(null));
    for (const p of presets) add(p.icon, p.name, () => quick(p.id));
    add("sliders", "Mit Optionen … (zuschneiden, Kapitel …)", () => chrome.runtime.sendMessage({ type: "openCustom", url: currentUrl() }), "kinbox-accent");
    // direkt an <body>: YouTubes Knopfleiste schneidet überstehende Elemente ab
    document.body.appendChild(menu);
    const r = wrap.getBoundingClientRect(), h = menu.offsetHeight;
    menu.style.left = Math.max(8, Math.min(r.left, innerWidth - menu.offsetWidth - 8)) + "px";
    menu.style.top = (r.bottom + 6 + h > innerHeight && r.top - 6 - h > 0 ? r.top - 6 - h : r.bottom + 6) + "px";
    menu._close = (e) => { if (e.type === "scroll" || !menu.contains(e.target) && !wrap.contains(e.target)) closeMenu(); };
    document.addEventListener("pointerdown", menu._close, true);  // „click“ kommt nicht immer an (YouTube baut beim Drücken um)
    addEventListener("scroll", menu._close, true);
  }

  function closeMenu() {
    const menu = document.getElementById(MENU_ID);
    if (!menu) return;
    document.removeEventListener("pointerdown", menu._close, true);
    removeEventListener("scroll", menu._close, true);
    menu.remove();
  }

  function currentUrl() {
    const u = new URL(location.href);
    // Zeitstempel & Tracking entfernen, Playlist-Parameter behalten
    for (const k of ["t", "pp", "si", "feature", "index", "start_radio"]) u.searchParams.delete(k);
    return u.toString();
  }

  async function quick(presetId) {
    const btn = document.querySelector(`#${BTN_ID} .kinbox-main`);
    btn?.classList.add("busy");
    try {
      const r = await chrome.runtime.sendMessage({ type: "quick", url: currentUrl(), presetId, title: document.title });
      if (r?.ok) {
        btn?.classList.add("done");
        setTimeout(() => btn?.classList.remove("done"), 2000);
      }
    } catch {
      alert(t("Kinbox: Erweiterung wurde neu geladen – bitte Seite aktualisieren."));
    } finally {
      btn?.classList.remove("busy");
    }
  }
})();
