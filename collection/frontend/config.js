// config.js — Frozen front-end configuration keys (design §7).
// DO NOT rename or remove keys — task3 and the capture loop depend on them.
window.COLLECTION_CONFIG = {
  BACKEND_URL:      "",          // same-origin now (served by the back-end, OQ6)
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
