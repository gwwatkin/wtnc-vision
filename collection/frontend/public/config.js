// config.js — Frozen front-end configuration keys (design §7 / page-split design §3).
// DO NOT rename or remove keys — the capture loop and backend-url.js depend on them.
window.COLLECTION_CONFIG = {
  // DEFAULT fallback when no wtnc_backend_url cookie is set (same-origin = "").
  // backend-url.js reads this via window.COLLECTION_CONFIG?.BACKEND_URL ?? ''.
  // Set the back-end URL at runtime from the UI (BackendSettings) — not here.
  BACKEND_URL:      "",          // same-origin default (served by the back-end, OQ6)
  CAPTURE_FPS:      6,           // burst rate while recording
  JPEG_QUALITY:     0.85,        // canvas.toBlob quality
  TARGET_WIDTH:     1280,        // 0 = camera-native; else downscale to width
  MAX_IN_FLIGHT:    3,           // backpressure cap (NFR3)
  RESULTS_POLL_MS:  1500,        // GET /results cadence (OQ5, §7)
  DEFAULT_SOURCE:   "camera",    // "camera" | "video" (D7, §7)
  // ── frozen keys (review-editing spec §6.5) ──
  FRAMES_SPAN_S:    12,          // default time window either side of anchor (s)
  FRAMES_LIMIT:     300,         // max frames per browser request (server-side cap)
};
