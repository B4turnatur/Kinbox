// „Kinbox"-Button für Videos auf TikTok, Instagram, X/Twitter und Reddit.
// Ein schwebender Knopf erscheint über dem Video, auf das die Maus zeigt.
// Außerdem liefert das Skript dem Popup/Kontextmenü die echte Video-Adresse
// (auf TikTok & Co. ist die Adresse im Browser oft nicht die des Videos).
(() => {
  if (window.__kinboxSocial) return;
  window.__kinboxSocial = true;

  const host = location.hostname.replace(/^www\./, "").replace(/^m\./, "");
  const SITE = /tiktok\.com$/.test(host) ? "tiktok" : /instagram\.com$/.test(host) ? "instagram"
    : /(^|\.)(x|twitter)\.com$/.test(host) ? "x" : /reddit\.com$/.test(host) ? "reddit" : null;
  if (!SITE) return;

  const VIDEO_HOSTS = "video, shreddit-player, shreddit-player-2";

  // ---------------------------------------------------------------------
  // Adresse zu einem Video finden
  // ---------------------------------------------------------------------
  const abs = (href) => { try { return new URL(href, location.origin).href.split("?")[0]; } catch { return null; } };

  function ancestors(el, max = 25) {
    const out = [];
    for (let i = 0; el && i < max; i++) {
      out.push(el);
      el = el.parentElement || (el.getRootNode && el.getRootNode().host) || null;
    }
    return out;
  }

  function findLink(el, re, max = 25) {
    for (const a of ancestors(el, max)) {
      if (a.matches?.("a[href]") && re.test(a.getAttribute("href"))) return abs(a.getAttribute("href"));
      const links = a.querySelectorAll ? a.querySelectorAll("a[href]") : [];
      const hits = [...links].filter((l) => re.test(l.getAttribute("href")));
      const uniq = [...new Set(hits.map((l) => abs(l.getAttribute("href"))))];
      if (uniq.length === 1) return uniq[0];
      if (uniq.length > 1) {
        // mehrere Links im Block – den nehmen, der dem Video am nächsten liegt
        const r = el.getBoundingClientRect();
        hits.sort((p, q) => dist(p, r) - dist(q, r));
        return abs(hits[0].getAttribute("href"));
      }
    }
    return null;
  }
  function dist(l, r) {
    const b = l.getBoundingClientRect();
    return Math.hypot((b.left + b.right) / 2 - (r.left + r.right) / 2, (b.top + b.bottom) / 2 - (r.top + r.bottom) / 2);
  }

  function resolve(videoEl) {
    const path = location.pathname;
    if (SITE === "tiktok") {
      for (const a of ancestors(videoEl)) {
        const m = (a.id || "").match(/(?:xgwrapper-\d+-|^)(\d{15,})$/);
        if (m) {
          const author = a.closest?.("[data-e2e*='item'], article, section")?.querySelector("[data-e2e*='author-uniqueid'], [data-e2e='video-author-uniqueid'], a[href^='/@']");
          const user = author ? (author.getAttribute("href") || "").match(/^\/@([\w.-]+)/)?.[1] || author.textContent.trim().replace(/^@/, "") : "";
          return `https://www.tiktok.com/@${/^[\w.-]+$/.test(user) ? user : ""}/video/${m[1]}`;
        }
      }
      const link = findLink(videoEl, /\/@[\w.-]+\/(video|photo)\/\d+/, 12);
      if (link) return link;
      if (/\/video\/\d+/.test(path)) return abs(path);
    }
    if (SITE === "instagram") {
      if (/^\/(reels?|p)\/[\w-]+/.test(path) && !videoEl.closest("article")) return abs(path.match(/^\/(reels?|p)\/[\w-]+\/?/)[0]);
      const link = findLink(videoEl, /\/(p|reels?|tv)\/[\w-]+/, 30);
      if (link) return link;
      if (/^\/(reels?|p|tv)\/[\w-]+/.test(path)) return abs(path);
    }
    if (SITE === "x") {
      const art = videoEl.closest("article") || ancestors(videoEl).find((a) => a.tagName === "ARTICLE");
      if (art) {
        const t = art.querySelector("a[href*='/status/'] time")?.closest("a");
        if (t) return abs(t.getAttribute("href")).replace(/\/(photo|video|analytics)\/\d*$/, "");
      }
      const link = findLink(videoEl, /\/status\/\d+/, 30);
      if (link) return link.replace(/\/(photo|video|analytics)\/\d*$/, "");
      if (/\/status\/\d+/.test(path)) return abs(path);
    }
    if (SITE === "reddit") {
      const post = ancestors(videoEl).find((a) => a.tagName === "SHREDDIT-POST" || a.getAttribute?.("permalink"));
      const pl = post?.getAttribute("permalink");
      if (pl) return abs(pl);
      const link = findLink(videoEl, /\/comments\/\w+/, 30);
      if (link) return link;
      if (/\/comments\/\w+/.test(path)) return abs(path);
    }
    return null;
  }

  function mediaRect(el) {
    const r = el.getBoundingClientRect();
    return r.width > 120 && r.height > 90 ? r : null;
  }

  function mostVisibleVideo() {
    let best = null, bestArea = 0;
    for (const v of document.querySelectorAll(VIDEO_HOSTS)) {
      const r = v.getBoundingClientRect();
      const w = Math.min(r.right, innerWidth) - Math.max(r.left, 0);
      const h = Math.min(r.bottom, innerHeight) - Math.max(r.top, 0);
      const area = w > 0 && h > 0 ? w * h : 0;
      const playing = v.tagName === "VIDEO" && !v.paused ? 1.5 : 1;
      if (area * playing > bestArea) { bestArea = area * playing; best = v; }
    }
    return best;
  }

  function videoAt(x, y) {
    for (const el of document.elementsFromPoint(x, y)) {
      if (el.matches?.(VIDEO_HOSTS)) return el;
      if (el.shadowRoot) {
        const v = el.shadowRoot.querySelector("video");
        if (v) return el;
      }
    }
    return null;
  }

  // ---------------------------------------------------------------------
  // Schwebender Knopf
  // ---------------------------------------------------------------------
  let enabled = true;
  // Gewählte Akzentfarbe/Stil (Einstellungen → Aussehen) an die Kinbox-Knöpfe weitergeben.
  const look = (s) => { const d = document.documentElement; d.style.setProperty("--kb-accent", s.accent); d.dataset.kbStyle = s.style; };
  chrome.storage.sync.get({ style: "classic", accent: "#7c5cff" }, look);
  chrome.storage.onChanged.addListener((c, area) => {
    if (area === "sync" && (c.style || c.accent)) chrome.storage.sync.get({ style: "classic", accent: "#7c5cff" }, look);
  });
  chrome.storage.sync.get({ showYoutubeButton: true, showSocialButtons: true }, (s) => { enabled = s.showSocialButtons; });
  chrome.storage.onChanged.addListener((c, area) => {
    if (area === "sync" && c.showSocialButtons) { enabled = c.showSocialButtons.newValue; if (!enabled) hide(true); }
  });

  const root = document.createElement("div");
  root.id = "kinbox-float";
  root.hidden = true;
  root.innerHTML = `
    <button class="kinbox-f-main" title="Mit Kinbox herunterladen">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 3a1 1 0 0 1 1 1v9.59l3.3-3.3a1 1 0 1 1 1.4 1.42l-5 5a1 1 0 0 1-1.4 0l-5-5a1 1 0 1 1 1.4-1.42l3.3 3.3V4a1 1 0 0 1 1-1zM5 19h14a1 1 0 1 1 0 2H5a1 1 0 1 1 0-2z"/></svg><span>Kinbox</span>
    </button><button class="kinbox-f-more" title="Mehr Optionen">${kbIcon("chevron")}</button>
    <div class="kinbox-f-menu" hidden></div>`;
  translateEl(root);
  let attached = false;
  function attach() { if (!attached || !root.isConnected) { document.documentElement.appendChild(root); attached = true; } }

  let target = null, hideTimer = null, menuOpen = false;

  function place() {
    if (!target || !target.isConnected) return hide(true);
    const r = mediaRect(target);
    if (!r || r.bottom < 0 || r.top > innerHeight) return hide(true);
    root.style.top = Math.max(8, r.top + 10) + "px";
    root.style.left = Math.max(8, Math.min(innerWidth - 150, r.left + 10)) + "px";
  }
  function show(v) {
    if (!enabled) return;
    attach();
    clearTimeout(hideTimer);
    if (target !== v) { target = v; closeMenu(); }
    root.hidden = false;
    place();
  }
  function hide(now = false) {
    if (menuOpen && !now) return;
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => { root.hidden = true; closeMenu(); target = null; }, now ? 0 : 900);
  }

  let raf = 0, lastXY = [0, 0];
  document.addEventListener("mousemove", (e) => {
    lastXY = [e.clientX, e.clientY];
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      if (root.contains(document.elementFromPoint(...lastXY))) { clearTimeout(hideTimer); return; }
      const v = videoAt(...lastXY);
      if (v && mediaRect(v)) show(v); else hide();
    });
  }, { passive: true });
  addEventListener("scroll", () => { if (!root.hidden) place(); }, { passive: true, capture: true });
  addEventListener("resize", () => { if (!root.hidden) place(); });

  const targetUrl = () => (target && resolve(target)) || null;

  root.querySelector(".kinbox-f-main").addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); quick(null); });
  root.querySelector(".kinbox-f-more").addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); menuOpen ? closeMenu() : openMenu(); });
  for (const ev of ["mousedown", "pointerdown", "touchstart", "dblclick"]) root.addEventListener(ev, (e) => e.stopPropagation());

  async function openMenu() {
    const menu = root.querySelector(".kinbox-f-menu");
    const r = await chrome.runtime.sendMessage({ type: "presets" }).catch(() => null);
    menu.innerHTML = "";
    const add = (ic, label, fn, cls = "") => {
      const b = document.createElement("button");
      b.innerHTML = kbIcon(ic);
      b.append(t(label)); b.className = cls;
      b.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); closeMenu(); fn(); });
      menu.appendChild(b);
    };
    add("download", "Standard-Einstellungen", () => quick(null));
    for (const p of r?.presets || []) add(p.icon, p.name, () => quick(p.id));
    add("sliders", "Mit Optionen …", () => {
      const url = targetUrl();
      if (!url) return flash("Adresse nicht gefunden", true);
      chrome.runtime.sendMessage({ type: "openCustom", url });
    }, "kinbox-f-accent");
    menu.hidden = false;
    menuOpen = true;
  }
  function closeMenu() { root.querySelector(".kinbox-f-menu").hidden = true; menuOpen = false; }

  async function quick(presetId) {
    const url = targetUrl();
    if (!url) return flash("Video-Adresse nicht gefunden – öffne das Video einzeln", true);
    const btn = root.querySelector(".kinbox-f-main");
    btn.classList.add("busy");
    try {
      const r = await chrome.runtime.sendMessage({ type: "quick", url, presetId });
      if (r?.ok) flash("✓"); else flash("Fehler", true);
    } catch {
      flash("Seite neu laden", true);
    } finally { btn.classList.remove("busy"); }
  }
  function flash(text, err = false) {
    const s = root.querySelector(".kinbox-f-main span");
    s.textContent = t(text);
    root.classList.toggle("err", err);
    setTimeout(() => { s.textContent = "Kinbox"; root.classList.remove("err"); }, err ? 3000 : 1800);
  }

  // ---------------------------------------------------------------------
  // Für Popup, Tastenkürzel und Rechtsklick: welches Video ist gemeint?
  // ---------------------------------------------------------------------
  let ctxXY = null;
  document.addEventListener("contextmenu", (e) => { ctxXY = [e.clientX, e.clientY]; }, true);

  chrome.runtime.onMessage.addListener((msg, _s, reply) => {
    if (msg.type === "currentMediaUrl") {
      const v = (target && !root.hidden && target) || mostVisibleVideo();
      reply({ url: v ? resolve(v) : null, site: SITE });
    } else if (msg.type === "contextMediaUrl") {
      const v = ctxXY ? videoAt(...ctxXY) : null;
      reply({ url: v ? resolve(v) : null });
    }
  });
})();
