// Aussehen (Stil + Akzentfarbe) sofort anwenden. localStorage dient als schneller
// Zwischenspeicher, damit das Popup nicht kurz im Standard-Design aufblitzt.
(() => {
  const d = document.documentElement;
  const apply = window.kbLook = (s) => {
    d.dataset.style = s.style || "classic";
    d.style.setProperty("--accent", s.accent || "#7c5cff");
    try { localStorage.kbLook = JSON.stringify({ style: s.style, accent: s.accent }); } catch {}
  };
  try { apply(JSON.parse(localStorage.kbLook || "{}")); } catch {}
  chrome.storage.sync.get({ style: "classic", accent: "#7c5cff" }, apply);
})();
