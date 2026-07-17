// config.js — Frozen front-end configuration keys (design §7).
// DO NOT rename or remove keys — task3 and the capture loop depend on them.
window.COLLECTION_CONFIG = {
  BACKEND_URL:  "http://localhost:8000",  // POST target (§4)
  CAPTURE_FPS:  6,                         // burst rate while recording
  JPEG_QUALITY: 0.85,                      // canvas.toBlob quality
  TARGET_WIDTH: 1280,                      // 0 = camera-native; else downscale to width
  MAX_IN_FLIGHT: 3,                        // backpressure cap (NFR3)
};
