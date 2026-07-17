// app.js — Frame collection UI logic.
// Reads all tunable values from window.COLLECTION_CONFIG (config.js must load first).
// Design §7, task3.

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Config — read once from the frozen window object; never hard-code these.
  // ---------------------------------------------------------------------------
  const {
    BACKEND_URL,
    CAPTURE_FPS,
    JPEG_QUALITY,
    TARGET_WIDTH,
    MAX_IN_FLIGHT,
  } = window.COLLECTION_CONFIG;

  const FRAME_INTERVAL_MS = 1000 / CAPTURE_FPS;

  // ---------------------------------------------------------------------------
  // DOM handles
  // ---------------------------------------------------------------------------
  const videoEl    = document.getElementById('preview');
  const selectEl   = document.getElementById('camera-select');
  const labelEl    = document.getElementById('label-input');
  const toggleBtn  = document.getElementById('toggle-btn');
  const statusEl   = document.getElementById('status');

  // Offscreen canvas — reused every tick to avoid GC pressure.
  const canvas  = document.createElement('canvas');
  const ctx     = canvas.getContext('2d');

  // ---------------------------------------------------------------------------
  // Session & loop state
  // ---------------------------------------------------------------------------
  let captureTimer = null;     // setInterval handle; null means stopped
  let sessionId    = null;
  let seq          = 0;
  let inFlight     = 0;        // count of POSTs currently awaiting response

  // Cumulative counters — reset on each Start
  let sentCount    = 0;
  let droppedCount = 0;
  let lastResult   = 'none';

  // Current live stream — track so we can stop it before switching camera.
  let activeStream = null;

  // ---------------------------------------------------------------------------
  // Status helpers
  // ---------------------------------------------------------------------------
  function renderStatus() {
    const recording = captureTimer !== null;
    const state = recording ? 'Recording' : 'Stopped';
    statusEl.textContent =
      `${state} — sent: ${sentCount}  dropped: ${droppedCount}  last: ${lastResult}`;
  }

  function setStatusMsg(msg) {
    statusEl.textContent = msg;
  }

  // ---------------------------------------------------------------------------
  // Camera initialisation (FR1, FR2)
  // ---------------------------------------------------------------------------

  /**
   * Populate the camera <select> element using enumerateDevices().
   * Must be called after getUserMedia() so device labels are available.
   */
  async function populateCameraList() {
    let devices;
    try {
      devices = await navigator.mediaDevices.enumerateDevices();
    } catch (err) {
      setStatusMsg('Could not enumerate devices: ' + err.message);
      return;
    }

    const videoInputs = devices.filter(d => d.kind === 'videoinput');

    // Remove all existing options except the placeholder.
    while (selectEl.options.length > 1) {
      selectEl.remove(1);
    }

    videoInputs.forEach((device, idx) => {
      const opt = document.createElement('option');
      opt.value = device.deviceId;
      opt.textContent = device.label || `Camera ${idx + 1}`;
      selectEl.appendChild(opt);
    });

    // Auto-select the first real camera.
    if (videoInputs.length > 0) {
      selectEl.value = videoInputs[0].deviceId;
    }
  }

  /**
   * Acquire a media stream for the given deviceId (or any camera if blank).
   * Stops the current stream first.
   */
  async function acquireStream(deviceId) {
    // Stop any running tracks on the old stream.
    if (activeStream) {
      activeStream.getTracks().forEach(t => t.stop());
      activeStream = null;
    }

    const constraints = {
      video: deviceId ? { deviceId: { exact: deviceId } } : true,
      audio: false,
    };

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (err) {
      const msg = err.name === 'NotAllowedError'
        ? 'Camera permission denied. Please allow camera access and reload.'
        : `Camera error: ${err.message}`;
      setStatusMsg(msg);
      toggleBtn.disabled = true;
      return;
    }

    activeStream = stream;
    videoEl.srcObject = stream;
    toggleBtn.disabled = false;
    renderStatus();
  }

  /**
   * On page load: get initial permission (unlocks device labels), enumerate,
   * then stream the first camera.
   */
  async function initCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatusMsg('Camera API not available. Use a browser that supports getUserMedia.');
      return;
    }

    // First call — permission prompt and label unlock.
    try {
      const tempStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      // Stop immediately; we'll re-acquire with the correct deviceId after enumeration.
      tempStream.getTracks().forEach(t => t.stop());
    } catch (err) {
      const msg = err.name === 'NotAllowedError'
        ? 'Camera permission denied. Please allow camera access and reload.'
        : `Camera error: ${err.message}`;
      setStatusMsg(msg);
      return;
    }

    await populateCameraList();

    // Stream the currently selected camera (or any camera if nothing selected).
    await acquireStream(selectEl.value);

    // Optionally probe back-end health — informational only.
    checkBackendHealth();
  }

  // ---------------------------------------------------------------------------
  // Back-end health probe (optional, informational)
  // ---------------------------------------------------------------------------
  async function checkBackendHealth() {
    try {
      const res = await fetch(BACKEND_URL + '/health');
      if (res.ok) {
        const data = await res.json();
        lastResult = `backend ok (v${data.version})`;
      } else {
        lastResult = `backend ${res.status}`;
      }
    } catch (_) {
      lastResult = 'backend unreachable';
    }
    renderStatus();
  }

  // ---------------------------------------------------------------------------
  // Capture tick — called by setInterval (FR4, FR5, NFR3)
  // ---------------------------------------------------------------------------
  function captureTick() {
    // Backpressure: drop this frame rather than queue if too many are in flight.
    if (inFlight >= MAX_IN_FLIGHT) {
      droppedCount++;
      renderStatus();
      return;
    }

    // Must have live video to capture.
    if (!videoEl.srcObject || videoEl.readyState < videoEl.HAVE_CURRENT_DATA) {
      return;
    }

    // Determine canvas size: downscale to TARGET_WIDTH if set and video is wider.
    const vw = videoEl.videoWidth  || 640;
    const vh = videoEl.videoHeight || 480;

    let drawW = vw;
    let drawH = vh;
    if (TARGET_WIDTH > 0 && vw > TARGET_WIDTH) {
      drawW = TARGET_WIDTH;
      drawH = Math.round(vh * (TARGET_WIDTH / vw));
    }

    canvas.width  = drawW;
    canvas.height = drawH;
    ctx.drawImage(videoEl, 0, 0, drawW, drawH);

    // Snapshot the label and timestamps at the moment of capture (FR3).
    const captureLabel = labelEl.value;
    const clientTs     = new Date().toISOString();
    const captureSeq   = seq++;
    const captureSession = sessionId;

    // Encode to JPEG and POST asynchronously; per-send errors never stop the loop (FR7).
    canvas.toBlob(blob => {
      if (!blob) return;
      sendFrame(blob, captureLabel, clientTs, captureSeq, captureSession);
    }, 'image/jpeg', JPEG_QUALITY);
  }

  // ---------------------------------------------------------------------------
  // Frame POST — isolated error handling means a failure never stops the loop (FR7)
  // ---------------------------------------------------------------------------
  async function sendFrame(blob, label, clientTs, frameSeq, sid) {
    inFlight++;

    const formData = new FormData();
    formData.append('image', blob, 'frame.jpg');   // file part, image/jpeg
    formData.append('label', label);
    formData.append('client_ts', clientTs);
    formData.append('seq', String(frameSeq));
    if (sid) {
      formData.append('session_id', sid);
    }

    try {
      const res = await fetch(BACKEND_URL + '/frames', {
        method: 'POST',
        body: formData,
        // Do NOT set Content-Type — the browser sets it with the correct boundary.
      });

      if (res.ok) {
        sentCount++;
        let detail = String(res.status);
        try {
          const json = await res.json();
          if (json.stored) detail += ' ' + json.stored;
        } catch (_) { /* non-JSON body is fine */ }
        lastResult = 'ok ' + detail;
      } else {
        let errDetail = String(res.status);
        try {
          const json = await res.json();
          if (json.detail) errDetail += ' ' + json.detail;
        } catch (_) { /* ignore */ }
        lastResult = 'error ' + errDetail;
      }
    } catch (err) {
      // Network error, CORS block, or back-end down — log to status and carry on (FR7).
      lastResult = 'send failed: ' + err.message;
    } finally {
      inFlight--;
      renderStatus();
    }
  }

  // ---------------------------------------------------------------------------
  // Start / Stop (FR4)
  // ---------------------------------------------------------------------------
  function startRecording() {
    if (captureTimer !== null) return;  // already running

    // New session — fresh UUID and sequence counter.
    sessionId    = crypto.randomUUID();
    seq          = 0;
    sentCount    = 0;
    droppedCount = 0;
    lastResult   = 'none';

    captureTimer = setInterval(captureTick, FRAME_INTERVAL_MS);
    toggleBtn.textContent = 'Stop';
    toggleBtn.classList.add('recording');
    renderStatus();
  }

  function stopRecording() {
    if (captureTimer === null) return;  // already stopped

    clearInterval(captureTimer);
    captureTimer = null;
    toggleBtn.textContent = 'Start';
    toggleBtn.classList.remove('recording');
    renderStatus();
  }

  // ---------------------------------------------------------------------------
  // Event listeners
  // ---------------------------------------------------------------------------
  toggleBtn.addEventListener('click', () => {
    if (captureTimer !== null) {
      stopRecording();
    } else {
      startRecording();
    }
  });

  selectEl.addEventListener('change', async () => {
    const wasRecording = captureTimer !== null;
    if (wasRecording) stopRecording();

    await acquireStream(selectEl.value);

    // Resume recording if it was running before the camera switch.
    if (wasRecording) startRecording();
  });

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------
  initCamera();
})();
