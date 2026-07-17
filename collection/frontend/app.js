// app.js — Frame collection UI logic.
// Reads all tunable values from window.COLLECTION_CONFIG (config.js must load first).
// Design §7, task3; extended for source selector + video ingest + roster upload (task6).

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
    DEFAULT_SOURCE,
  } = window.COLLECTION_CONFIG;

  const FRAME_INTERVAL_MS = 1000 / CAPTURE_FPS;

  // ---------------------------------------------------------------------------
  // DOM handles — task6 owns behavior of source-select, video-file,
  // roster-file, roster-upload-btn, roster-status (README DOM contract).
  // ---------------------------------------------------------------------------
  const videoEl         = document.getElementById('preview');
  const selectEl        = document.getElementById('camera-select');
  const labelEl         = document.getElementById('label-input');
  const toggleBtn       = document.getElementById('toggle-btn');
  const statusEl        = document.getElementById('status');
  const sourceSelectEl  = document.getElementById('source-select');
  const videoFileEl     = document.getElementById('video-file');
  const rosterFileEl    = document.getElementById('roster-file');
  const rosterUploadBtn = document.getElementById('roster-upload-btn');
  const rosterStatusEl  = document.getElementById('roster-status');

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
  // Source abstraction (D7 / FR4a)
  // ---------------------------------------------------------------------------

  // Active source: "camera" | "video"
  let activeSource = DEFAULT_SOURCE || 'camera';

  // Object URL for the current video file; revoked when replaced.
  let videoObjectUrl = null;

  // Wall-clock timestamp (ms) recorded the moment the video starts playing.
  // Used to derive client_ts for video frames: new Date(videoStartWallclock +
  // preview.currentTime * 1000).toISOString()  — design §8 A1.
  let videoStartWallclock = null;

  /**
   * Return the current client_ts string.
   * Camera: wall-clock now (unchanged from original).
   * Video: wallclock of video start + elapsed video time, so frames spread
   * across the video's own timeline (design §8, A1).
   */
  function currentClientTs() {
    if (activeSource === 'video' && videoStartWallclock !== null) {
      return new Date(videoStartWallclock + videoEl.currentTime * 1000).toISOString();
    }
    return new Date().toISOString();
  }

  /**
   * Apply the source state to the DOM controls — called once on boot and
   * whenever the source-select changes.
   * Does NOT touch the stream or the video element's src; that happens in
   * initCamera / acquireStream / video-file change handler.
   */
  function applySourceUi(source) {
    if (source === 'camera') {
      videoFileEl.hidden   = true;
      videoFileEl.disabled = true;
      selectEl.disabled    = false;
    } else {
      // video
      videoFileEl.hidden   = false;
      videoFileEl.disabled = false;
      selectEl.disabled    = true;
    }
  }

  /**
   * Switch to camera source.
   * Releases any video object URL and restores getUserMedia to the preview.
   * Called from source-select change handler (after stopping recording).
   */
  async function switchToCamera() {
    // Release previous video object URL.
    if (videoObjectUrl) {
      URL.revokeObjectURL(videoObjectUrl);
      videoObjectUrl = null;
    }
    videoEl.removeEventListener('ended', onVideoEnded);
    videoEl.pause();
    videoEl.removeAttribute('src');
    videoEl.srcObject = null;     // will be set by acquireStream below
    videoEl.autoplay  = true;     // camera preview plays live
    toggleBtn.disabled = true;    // re-enabled by acquireStream success
    await acquireStream(selectEl.value);
  }

  /**
   * Switch to video source.
   * Tears down the camera stream; the preview stays blank until the user
   * chooses a file.
   */
  function switchToVideo() {
    // Stop camera tracks — we no longer need them.
    if (activeStream) {
      activeStream.getTracks().forEach(t => t.stop());
      activeStream = null;
    }
    videoEl.srcObject = null;
    videoEl.autoplay  = false;   // video: no autoplay; Start calls play()
    videoEl.muted     = true;

    // Enable Start only if a file is already chosen.
    toggleBtn.disabled = (videoObjectUrl === null);
  }

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
  // Source-agnostic: draws preview to canvas regardless of source.
  // ---------------------------------------------------------------------------
  function captureTick() {
    // Backpressure: drop this frame rather than queue if too many are in flight.
    if (inFlight >= MAX_IN_FLIGHT) {
      droppedCount++;
      renderStatus();
      return;
    }

    // Guard: preview must have renderable data regardless of source.
    // For camera: srcObject set and readyState adequate.
    // For video: src set (object URL) and readyState adequate.
    // videoWidth/videoHeight being 0 means metadata not yet loaded — skip cleanly.
    const hasData =
      activeSource === 'camera'
        ? (videoEl.srcObject !== null && videoEl.readyState >= videoEl.HAVE_CURRENT_DATA)
        : (videoEl.src !== '' && videoEl.readyState >= videoEl.HAVE_CURRENT_DATA);

    if (!hasData) return;

    const vw = videoEl.videoWidth;
    const vh = videoEl.videoHeight;
    if (!vw || !vh) return;   // metadata not loaded yet — skip tick cleanly

    // Determine canvas size: downscale to TARGET_WIDTH if set and video is wider.
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
    const captureLabel   = labelEl.value;
    const clientTs       = currentClientTs();   // source-aware (design §8 A1)
    const captureSeq     = seq++;
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
      const res = await fetch(`${BACKEND_URL}/frames`, {
        method: 'POST',
        body: formData,
        // Do NOT set Content-Type — the browser sets it with the correct boundary.
      });

      if (res.ok) {
        sentCount++;
        let detail = String(res.status);
        try {
          const json = await res.json();
          // Design §4: 201 body gains "run" field; "stored" unchanged.
          if (json.stored) detail += ' ' + json.stored;
          if (json.run)    detail += ' [' + json.run + ']';
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
  // Start / Stop (FR4, D7)
  // ---------------------------------------------------------------------------

  /**
   * Auto-stop handler for the video `ended` event (task6 spec).
   * Stored as a named function so it can be removed on source switch.
   */
  function onVideoEnded() {
    if (captureTimer !== null) {
      stopRecording();
      setStatusMsg('Video ended — recording stopped automatically.');
    }
  }

  function startRecording() {
    if (captureTimer !== null) return;  // already running

    // Video source: require a chosen file.
    if (activeSource === 'video') {
      if (!videoObjectUrl) {
        setStatusMsg('Choose a video file before starting.');
        return;
      }
      // Record the wall-clock instant the video starts playing (design §8 A1).
      videoStartWallclock = Date.now();
      videoEl.play().catch(err => {
        setStatusMsg('Could not play video: ' + err.message);
      });
      // Listen for natural end of video — auto-stop recording.
      videoEl.removeEventListener('ended', onVideoEnded);
      videoEl.addEventListener('ended', onVideoEnded, { once: true });
    }

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

    // Pause the video if we were playing one.
    if (activeSource === 'video') {
      videoEl.pause();
      videoStartWallclock = null;
      // Remove ended listener in case Stop was clicked before the video finished.
      videoEl.removeEventListener('ended', onVideoEnded);
    }

    toggleBtn.textContent = 'Start';
    toggleBtn.classList.remove('recording');
    renderStatus();
  }

  // ---------------------------------------------------------------------------
  // Event listeners
  // ---------------------------------------------------------------------------

  // Toggle Start/Stop
  toggleBtn.addEventListener('click', () => {
    if (captureTimer !== null) {
      stopRecording();
    } else {
      startRecording();
    }
  });

  // Camera selector change — only relevant when source = camera
  selectEl.addEventListener('change', async () => {
    if (activeSource !== 'camera') return;

    const wasRecording = captureTimer !== null;
    if (wasRecording) stopRecording();

    await acquireStream(selectEl.value);

    // Resume recording if it was running before the camera switch.
    if (wasRecording) startRecording();
  });

  // Source selector change (D7)
  sourceSelectEl.addEventListener('change', async () => {
    const newSource = sourceSelectEl.value;
    if (newSource === activeSource) return;

    // Stop any active recording before switching source.
    if (captureTimer !== null) {
      stopRecording();
    }

    activeSource = newSource;
    applySourceUi(activeSource);

    if (activeSource === 'camera') {
      await switchToCamera();
    } else {
      switchToVideo();
    }
  });

  // Video file input — load the chosen file into the preview element (D7)
  videoFileEl.addEventListener('change', () => {
    const file = videoFileEl.files && videoFileEl.files[0];
    if (!file) return;

    // Revoke any previous object URL to free memory.
    if (videoObjectUrl) {
      URL.revokeObjectURL(videoObjectUrl);
      videoObjectUrl = null;
    }

    // Remove the ended listener from any prior playback.
    videoEl.removeEventListener('ended', onVideoEnded);

    // If recording was active, stop it cleanly before replacing the source.
    if (captureTimer !== null) {
      stopRecording();
    }

    videoEl.srcObject = null;
    videoObjectUrl    = URL.createObjectURL(file);
    videoEl.src       = videoObjectUrl;
    videoEl.muted     = true;
    videoEl.autoplay  = false;   // no autoplay; Start calls play()
    // Do not call play() here — operator decides when to Start.

    // A file is now chosen — enable Start.
    toggleBtn.disabled = false;
    setStatusMsg(`Video file selected: ${file.name}`);
  });

  // ---------------------------------------------------------------------------
  // Roster upload (FR16–FR19)
  // ---------------------------------------------------------------------------
  rosterUploadBtn.addEventListener('click', async () => {
    // Require non-blank run label (README: label-input is the active run).
    const run = labelEl.value.trim();
    if (!run) {
      rosterStatusEl.textContent = 'Enter a label/run name before uploading a roster.';
      return;
    }

    // Require a chosen file.
    const file = rosterFileEl.files && rosterFileEl.files[0];
    if (!file) {
      rosterStatusEl.textContent = 'Choose a roster CSV file first.';
      return;
    }

    rosterStatusEl.textContent = 'Uploading…';

    const formData = new FormData();
    formData.append('run', run);          // raw label — back-end normalizes (design §4)
    formData.append('roster', file);

    try {
      const res = await fetch(`${BACKEND_URL}/roster`, {
        method: 'POST',
        body: formData,
        // Do NOT set Content-Type — the browser sets multipart boundary.
      });

      let body;
      try {
        body = await res.json();
      } catch (_) {
        body = null;
      }

      if (res.ok) {
        // 200 → { status:"ok", run:"<safe_id>", count: N }
        const safeRun = (body && body.run)   ? body.run   : run;
        const count   = (body && body.count != null) ? body.count : '?';
        rosterStatusEl.textContent = `Roster set for ${safeRun}: ${count} riders`;
      } else if (res.status === 503) {
        // Live processing disabled (README task-split refinement 3).
        const detail = (body && body.detail) ? body.detail : 'live processing disabled';
        rosterStatusEl.textContent = `Upload rejected: ${detail}`;
      } else {
        // 400 or other — show server's detail message (FR19).
        const detail = (body && body.detail) ? body.detail : `HTTP ${res.status}`;
        rosterStatusEl.textContent = `Upload failed: ${detail}`;
      }
    } catch (err) {
      // Network error.
      rosterStatusEl.textContent = `Roster upload failed: ${err.message}`;
    }
  });

  // ---------------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------------

  // Initialise source selector to the configured default.
  sourceSelectEl.value = activeSource;
  applySourceUi(activeSource);

  if (activeSource === 'camera') {
    initCamera();
  } else {
    // Video source on boot — camera won't be initialised; Start disabled until file chosen.
    videoEl.autoplay  = false;
    videoEl.muted     = true;
    toggleBtn.disabled = true;
    setStatusMsg('Select a video file to begin.');
  }
})();
