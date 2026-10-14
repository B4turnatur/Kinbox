// Linien-Icons für die Kinbox-Knöpfe auf fremden Seiten (Kopie aus icons.svg – dort kein Zugriff auf die Datei).
(() => {
  const P = {
    "download": "<path d=\"M12 15V3\"/><path d=\"m7 10 5 5 5-5\"/><path d=\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\"/>",
    "sliders": "<path d=\"M4 21v-7\"/><path d=\"M4 10V3\"/><path d=\"M12 21v-9\"/><path d=\"M12 8V3\"/><path d=\"M20 21v-5\"/><path d=\"M20 12V3\"/><path d=\"M2 14h4\"/><path d=\"M10 8h4\"/><path d=\"M18 16h4\"/>",
    "chevron": "<path d=\"m6 9 6 6 6-6\"/>",
    "star": "<path d=\"m12 2 3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z\"/>",
    "play": "<path d=\"M6 3v18l14-9z\"/>",
    "music": "<path d=\"M9 18V5l12-2v13\"/><circle cx=\"6\" cy=\"18\" r=\"3\"/><circle cx=\"18\" cy=\"16\" r=\"3\"/>",
    "chat": "<path d=\"M7.9 20A9 9 0 1 0 4 16.1L2 22Z\"/>",
    "image": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\"/><circle cx=\"9\" cy=\"9\" r=\"2\"/><path d=\"m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21\"/>",
    "mic": "<path d=\"M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z\"/><path d=\"M19 10v2a7 7 0 0 1-14 0v-2\"/><path d=\"M12 19v3\"/>",
    "check": "<path d=\"M20 6 9 17l-5-5\"/>",
    "swap": "<path d=\"M8 3 4 7l4 4\"/><path d=\"M4 7h16\"/><path d=\"m16 21 4-4-4-4\"/><path d=\"M20 17H4\"/>",
    "ban": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"m4.9 4.9 14.2 14.2\"/>"
  };
  const MAP = { "★": "star", "▶": "play", "♪": "music", "♫": "music", "💬": "chat", "🖼": "image", "🎙": "mic" };
  globalThis.kbIcon = (name) => {
    const d = P[MAP[name] || name];
    return d ? `<svg class="kb-i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>` : "";
  };
})();
