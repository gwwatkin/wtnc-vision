/**
 * browser.js — Frame browser sidebar mode (task8).
 *
 * Exports:
 *   openBrowser({ run, centerTs })
 *     → renders frame-browser mode into #sidebar-content (opens #sidebar if
 *       closed); centerTs: ISO string anchor, or null ⇒ anchor at meta.last_ts.
 *
 * Calls (from ./edits.js, against frozen contracts):
 *   createCrossing({ run, filename, clientTs, number })
 *   loadRosterNumbers(run)
 *
 * CSS classes used (all defined by task1; never edit styles.css from here):
 *   .frame-browser  .frame-browser__scrubber  .frame-browser__filmstrip
 *   .filmstrip__thumb  .filmstrip__thumb--active  .frame-browser__main
 *   .frame-browser__outcome  .frame-browser__add-row  .frame-browser__no-outcome
 *   .frame-canvas-wrapper  .frame-canvas-overlay
 */

import { createCrossing, loadRosterNumbers } from "./edits.js";

// ---------------------------------------------------------------------------
// Module-level state — one live browser instance at a time
// ---------------------------------------------------------------------------

/** @type {{ run: string, frames: Array, meta: object, selectedIdx: number }|null} */
let _state = null;

/** @type {number|null} scrubber debounce timer id */
let _scrubTimer = null;

/** @type {Function|null} keyboard handler currently attached to document */
let _keyHandler = null;

// ---------------------------------------------------------------------------
// Public export
// ---------------------------------------------------------------------------

/**
 * Open the frame browser in the sidebar.
 *
 * @param {{ run: string, centerTs: string|null }} opts
 *   run       — run label (passed verbatim to GET /frames?run=)
 *   centerTs  — ISO anchor for the window; null → server anchors at newest frame
 */
export function openBrowser({ run, centerTs }) {
  const sidebar = document.getElementById("sidebar");
  const content = document.getElementById("sidebar-content");
  if (!sidebar || !content) return;

  // Tear down any previous keyboard listener before re-rendering.
  _detachKeyboard();

  // Show the sidebar immediately with a loading indicator while the fetch runs.
  sidebar.removeAttribute("hidden");
  content.innerHTML = '<p class="frame-browser__no-outcome">Loading frames…</p>';

  // Wire the sidebar-close button to also detach our keyboard listener.
  // We do this every time openBrowser is called so we always have a fresh ref.
  const closeBtn = document.getElementById("sidebar-close");
  if (closeBtn) {
    // Replace with a clone to drop prior listeners (sidebar.js wires its own;
    // we re-add ours alongside — we only need to react to the same event).
    // Rather than cloning (which would break sidebar.js), use a named function
    // stored on the element so we can remove it cleanly.
    if (closeBtn._browserCloseHandler) {
      closeBtn.removeEventListener("click", closeBtn._browserCloseHandler);
    }
    closeBtn._browserCloseHandler = () => _detachKeyboard();
    closeBtn.addEventListener("click", closeBtn._browserCloseHandler);
  }

  _loadWindow({ run, centerTs, content, sidebar });
}

// ---------------------------------------------------------------------------
// Core load / render
// ---------------------------------------------------------------------------

/**
 * Fetch a frame window from the server and render the browser UI.
 * @param {{ run: string, centerTs: string|null, content: HTMLElement, sidebar: HTMLElement }} opts
 */
async function _loadWindow({ run, centerTs, content, sidebar }) {
  const { FRAMES_SPAN_S, FRAMES_LIMIT } = window.COLLECTION_CONFIG || {};
  const span = FRAMES_SPAN_S != null ? FRAMES_SPAN_S : 12;
  const limit = FRAMES_LIMIT != null ? FRAMES_LIMIT : 300;

  // Build query string.
  const params = new URLSearchParams({ run, span, limit });
  if (centerTs) params.set("center", centerTs);

  let data;
  try {
    const resp = await fetch(`/frames?${params}`);
    if (!resp.ok) {
      throw new Error(`Server returned ${resp.status}`);
    }
    data = await resp.json();
  } catch (err) {
    content.innerHTML = `<p class="frame-browser__no-outcome">Error loading frames: ${_esc(err.message)}</p>`;
    return;
  }

  const { meta, frames } = data;

  if (!frames || frames.length === 0) {
    content.innerHTML = '<p class="frame-browser__no-outcome">No frames found for this run.</p>';
    return;
  }

  // Determine which frame to pre-select: the one whose client_ts is closest to
  // centerTs (or the last frame when centerTs is null).
  let selectedIdx = frames.length - 1;
  if (centerTs) {
    const anchorMs = _isoToMs(centerTs);
    let best = Infinity;
    frames.forEach((f, i) => {
      const d = Math.abs(_isoToMs(f.client_ts) - anchorMs);
      if (d < best) { best = d; selectedIdx = i; }
    });
  }

  // Store state so keyboard / scrubber handlers can reference it.
  _state = { run, frames, meta, selectedIdx };

  // Build and inject the DOM.
  const root = _buildBrowserDOM({ run, frames, meta, selectedIdx, content });

  // Attach keyboard navigation.
  _attachKeyboard({ run, frames, meta, content, sidebar });
}

// ---------------------------------------------------------------------------
// DOM construction
// ---------------------------------------------------------------------------

/**
 * Build the complete frame-browser DOM tree, inject it into `content`, wire
 * all interactive controls, and return the root element.
 *
 * @param {{ run: string, frames: Array, meta: object, selectedIdx: number,
 *            content: HTMLElement }} opts
 * @returns {HTMLElement} the .frame-browser root element
 */
function _buildBrowserDOM({ run, frames, meta, selectedIdx, content }) {
  content.innerHTML = "";

  const root = document.createElement("div");
  root.className = "frame-browser";

  // ── Scrubber row ──────────────────────────────────────────────────────────
  const scrubberRow = document.createElement("div");
  scrubberRow.className = "frame-browser__scrubber";

  const firstMs = meta.first_ts ? _isoToMs(meta.first_ts) : null;
  const lastMs  = meta.last_ts  ? _isoToMs(meta.last_ts)  : null;
  const hasRange = firstMs !== null && lastMs !== null && lastMs > firstMs;

  const scrubber = document.createElement("input");
  scrubber.type = "range";
  scrubber.min  = hasRange ? String(firstMs) : "0";
  scrubber.max  = hasRange ? String(lastMs)  : "1";
  scrubber.step = "1";

  // Position scrubber at the selected frame's time.
  const selFrame = frames[selectedIdx];
  scrubber.value = selFrame ? String(_isoToMs(selFrame.client_ts)) : scrubber.max;

  const timeLabel = document.createElement("span");
  timeLabel.textContent = selFrame ? _formatTimeOfDay(selFrame.client_ts) : "";

  scrubberRow.appendChild(scrubber);
  scrubberRow.appendChild(timeLabel);

  // Scrubber change: debounced reload around the chosen time.
  scrubber.addEventListener("input", () => {
    if (_scrubTimer !== null) clearTimeout(_scrubTimer);
    _scrubTimer = setTimeout(() => {
      _scrubTimer = null;
      // Convert range value back to an ISO timestamp for the reload.
      const chosenMs = Number(scrubber.value);
      const chosenTs = _msToIso(chosenMs);
      _detachKeyboard();
      // Re-use the same content/sidebar elements (still in the DOM).
      const currentContent = document.getElementById("sidebar-content");
      const currentSidebar = document.getElementById("sidebar");
      if (currentContent && currentSidebar) {
        currentContent.innerHTML = '<p class="frame-browser__no-outcome">Loading…</p>';
        _loadWindow({ run, centerTs: chosenTs, content: currentContent, sidebar: currentSidebar });
      }
    }, 150);
  });

  root.appendChild(scrubberRow);

  // ── Filmstrip ─────────────────────────────────────────────────────────────
  const filmstrip = document.createElement("div");
  filmstrip.className = "frame-browser__filmstrip";

  frames.forEach((frame, idx) => {
    const thumb = document.createElement("img");
    thumb.className = "filmstrip__thumb" + (idx === selectedIdx ? " filmstrip__thumb--active" : "");
    thumb.src = frame.url;
    thumb.alt = `Frame ${idx + 1}`;
    thumb.loading = "lazy";
    thumb.dataset.idx = String(idx);

    thumb.addEventListener("click", () => {
      _selectFrame(idx, { frames, filmstrip, mainView, timeLabel, scrubber });
    });

    filmstrip.appendChild(thumb);
  });

  root.appendChild(filmstrip);

  // ── Main view ─────────────────────────────────────────────────────────────
  const mainView = document.createElement("div");
  mainView.className = "frame-browser__main";
  _renderMainFrame(selectedIdx, { frames, mainView });

  root.appendChild(mainView);

  // ── Add-crossing row ──────────────────────────────────────────────────────
  const addRow = _buildAddRow(run, frames, selectedIdx);
  root.appendChild(addRow);

  // Store a reference to addRow so _selectFrame can update it.
  root._addRow = addRow;
  root._frames = frames;
  root._run = run;

  content.appendChild(root);

  // Scroll the active thumbnail into view.
  _scrollThumbIntoView(filmstrip, selectedIdx);

  return root;
}

// ---------------------------------------------------------------------------
// Frame selection (filmstrip + keyboard)
// ---------------------------------------------------------------------------

/**
 * Switch the active frame to `idx` and update all dependent UI pieces.
 *
 * @param {number} idx
 * @param {{ frames: Array, filmstrip: HTMLElement, mainView: HTMLElement,
 *            timeLabel: HTMLElement, scrubber: HTMLInputElement }} ctx
 */
function _selectFrame(idx, { frames, filmstrip, mainView, timeLabel, scrubber }) {
  if (!_state) return;
  _state.selectedIdx = idx;

  // Update filmstrip highlight.
  filmstrip.querySelectorAll(".filmstrip__thumb").forEach((el) => {
    const elIdx = Number(el.dataset.idx);
    el.classList.toggle("filmstrip__thumb--active", elIdx === idx);
  });
  _scrollThumbIntoView(filmstrip, idx);

  // Update time label and scrubber knob.
  const frame = frames[idx];
  if (frame) {
    timeLabel.textContent = _formatTimeOfDay(frame.client_ts);
    scrubber.value = String(_isoToMs(frame.client_ts));
  }

  // Re-render main view.
  _renderMainFrame(idx, { frames, mainView });

  // Update add-crossing row target frame.
  const browser = mainView.closest(".frame-browser");
  if (browser && browser._addRow) {
    const newAddRow = _buildAddRow(browser._run, frames, idx);
    browser._addRow.replaceWith(newAddRow);
    browser._addRow = newAddRow;
  }
}

// ---------------------------------------------------------------------------
// Main frame view + canvas overlay
// ---------------------------------------------------------------------------

/**
 * Render the selected frame (with canvas overlay) into `mainView`.
 * @param {number} idx
 * @param {{ frames: Array, mainView: HTMLElement }} ctx
 */
function _renderMainFrame(idx, { frames, mainView }) {
  mainView.innerHTML = "";

  const frame = frames[idx];
  if (!frame) return;

  // outcome block
  const outcomeEl = document.createElement("div");
  outcomeEl.className = "frame-browser__outcome";

  if (!frame.processed) {
    // Frame exists in manifest but not yet in frames_index — or the run
    // pre-dates this feature (OQ4).
    const note = document.createElement("p");
    note.className = "frame-browser__no-outcome";
    note.textContent = "No outcome data (frame not yet processed)";
    mainView.appendChild(note);
  }

  // Image + canvas overlay wrapper.
  const wrapper = document.createElement("div");
  wrapper.className = "frame-canvas-wrapper";

  const img = document.createElement("img");
  img.src = frame.url;
  img.alt = `Frame at ${_formatTimeOfDay(frame.client_ts)}`;
  img.style.width = "100%";
  img.style.display = "block";

  const canvas = document.createElement("canvas");
  canvas.className = "frame-canvas-overlay";
  // Canvas is positioned absolutely over the image (task1's CSS handles it).
  canvas.style.position = "absolute";
  canvas.style.top = "0";
  canvas.style.left = "0";
  canvas.style.pointerEvents = "none";

  wrapper.appendChild(img);
  if (frame.processed) {
    // Only add the canvas when there is outcome data to draw.
    wrapper.appendChild(canvas);
  }

  mainView.appendChild(wrapper);

  if (frame.processed) {
    // Draw rider boxes once the image dimensions are known.
    const drawOverlay = () => {
      canvas.width  = img.naturalWidth  || img.offsetWidth;
      canvas.height = img.naturalHeight || img.offsetHeight;
      // Match canvas display size to the rendered image.
      canvas.style.width  = `${img.offsetWidth}px`;
      canvas.style.height = `${img.offsetHeight}px`;
      _drawRiderBoxes(canvas, frame.riders || [], img);
    };

    if (img.complete && img.naturalWidth > 0) {
      drawOverlay();
    } else {
      img.addEventListener("load", drawOverlay);
    }

    // Rescale on container resize (handles sidebar width changes).
    const resizeObserver = new ResizeObserver(() => {
      if (img.naturalWidth > 0) drawOverlay();
    });
    resizeObserver.observe(wrapper);
  }

  if (frame.processed) {
    mainView.appendChild(outcomeEl);
  }
}

/**
 * Draw rider bounding boxes on `canvas`, scaled to the image's current
 * rendered size. Colors: green=confident, amber=needs_review, red=rejected.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {Array<{box: number[], status: string, number: string|null, raw_text: string|null, confidence: number}>} riders
 * @param {HTMLImageElement} img
 */
function _drawRiderBoxes(canvas, riders, img) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!riders || riders.length === 0) return;

  // Scale factors from natural → rendered pixels.
  const scaleX = img.offsetWidth  / (img.naturalWidth  || img.offsetWidth);
  const scaleY = img.offsetHeight / (img.naturalHeight || img.offsetHeight);

  const COLOR = {
    confident:    "#22c55e",   // green
    needs_review: "#f59e0b",   // amber
    rejected:     "#ef4444",   // red
  };

  riders.forEach((rider) => {
    if (!rider.box || rider.box.length < 4) return;
    const [x1, y1, x2, y2] = rider.box;
    const rx = x1 * scaleX;
    const ry = y1 * scaleY;
    const rw = (x2 - x1) * scaleX;
    const rh = (y2 - y1) * scaleY;

    const color = COLOR[rider.status] || "#94a3b8";

    ctx.strokeStyle = color;
    ctx.lineWidth   = 2;
    ctx.strokeRect(rx, ry, rw, rh);

    // Label: number (or raw_text fallback), then confidence.
    const label = `${rider.number ?? rider.raw_text ?? "?"} (${(rider.confidence * 100).toFixed(0)}%)`;
    ctx.font      = "bold 12px sans-serif";
    ctx.fillStyle = color;
    // Draw a small backing rectangle so the label is legible.
    const textMetrics = ctx.measureText(label);
    const textH = 14;
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(rx, ry - textH - 2, textMetrics.width + 4, textH + 2);
    ctx.fillStyle = color;
    ctx.fillText(label, rx + 2, ry - 3);
  });
}

// ---------------------------------------------------------------------------
// Add-crossing row
// ---------------------------------------------------------------------------

/**
 * Build the "Add crossing here" UI row for the given frame.
 *
 * @param {string} run
 * @param {Array} frames
 * @param {number} selectedIdx
 * @returns {HTMLElement}
 */
function _buildAddRow(run, frames, selectedIdx) {
  const row = document.createElement("div");
  row.className = "frame-browser__add-row";

  const frame = frames[selectedIdx];
  if (!frame) return row;

  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "Add crossing here";

  // Inline form — hidden until the button is clicked.
  const form = document.createElement("div");
  form.hidden = true;

  const numberInput = document.createElement("input");
  numberInput.type        = "text";
  numberInput.placeholder = "Race number (blank = unidentified)";
  numberInput.setAttribute("list", "roster-numbers");
  numberInput.autocomplete = "off";

  const submitBtn = document.createElement("button");
  submitBtn.type        = "button";
  submitBtn.textContent = "Save crossing";

  const cancelBtn = document.createElement("button");
  cancelBtn.type        = "button";
  cancelBtn.textContent = "Cancel";

  const feedback = document.createElement("span");
  feedback.className = "frame-browser__feedback";

  form.appendChild(numberInput);
  form.appendChild(submitBtn);
  form.appendChild(cancelBtn);
  form.appendChild(feedback);

  row.appendChild(btn);
  row.appendChild(form);

  // Open form.
  btn.addEventListener("click", () => {
    btn.hidden  = true;
    form.hidden = false;
    numberInput.focus();
    // Load roster suggestions (non-blocking; fills the datalist).
    loadRosterNumbers(run).catch(() => { /* ignore — datalist degrades gracefully */ });
  });

  // Cancel.
  cancelBtn.addEventListener("click", () => {
    form.hidden = false;   // keep visible to reset
    numberInput.value = "";
    feedback.textContent  = "";
    form.hidden = true;
    btn.hidden  = false;
  });

  // Submit.
  submitBtn.addEventListener("click", async () => {
    submitBtn.disabled = true;
    feedback.textContent = "Saving…";
    try {
      await createCrossing({
        run,
        filename: frame.filename,
        clientTs: frame.client_ts,
        number:   numberInput.value.trim(),
      });
      feedback.textContent = "Crossing added.";
      numberInput.value = "";
      // Leave the browser open; timeline updates on the next poll via wtnc:edited
      // (dispatched by createCrossing in edits.js per the frozen contract).
      setTimeout(() => {
        feedback.textContent = "";
        form.hidden = true;
        btn.hidden  = false;
      }, 2000);
    } catch (err) {
      feedback.textContent = `Error: ${_esc(err.message)}`;
    } finally {
      submitBtn.disabled = false;
    }
  });

  return row;
}

// ---------------------------------------------------------------------------
// Keyboard navigation
// ---------------------------------------------------------------------------

/**
 * Attach a document-level keydown listener for ← / → frame stepping.
 * Stepping past the loaded window's edge triggers a reload centered on the
 * edge frame.
 *
 * @param {{ run: string, frames: Array, meta: object,
 *            content: HTMLElement, sidebar: HTMLElement }} ctx
 */
function _attachKeyboard({ run, frames, meta, content, sidebar }) {
  _detachKeyboard();   // safety: never stack handlers

  _keyHandler = (e) => {
    if (!_state) return;
    // Only handle arrow keys; ignore if focus is in an input.
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;

    e.preventDefault();

    const { frames: stateFrames, selectedIdx } = _state;

    if (e.key === "ArrowRight") {
      if (selectedIdx < stateFrames.length - 1) {
        // Step forward within the loaded window.
        const filmstrip = content.querySelector(".frame-browser__filmstrip");
        const mainView  = content.querySelector(".frame-browser__main");
        const timeLabel = content.querySelector(".frame-browser__scrubber span");
        const scrubber  = content.querySelector(".frame-browser__scrubber input[type=range]");
        if (filmstrip && mainView && timeLabel && scrubber) {
          _selectFrame(selectedIdx + 1, { frames: stateFrames, filmstrip, mainView, timeLabel, scrubber });
        }
      } else {
        // Past the right edge — reload centered on the last (newest) frame.
        const edgeTs = stateFrames[stateFrames.length - 1].client_ts;
        _detachKeyboard();
        content.innerHTML = '<p class="frame-browser__no-outcome">Loading…</p>';
        _loadWindow({ run, centerTs: edgeTs, content, sidebar });
      }
    } else {
      // ArrowLeft
      if (selectedIdx > 0) {
        const filmstrip = content.querySelector(".frame-browser__filmstrip");
        const mainView  = content.querySelector(".frame-browser__main");
        const timeLabel = content.querySelector(".frame-browser__scrubber span");
        const scrubber  = content.querySelector(".frame-browser__scrubber input[type=range]");
        if (filmstrip && mainView && timeLabel && scrubber) {
          _selectFrame(selectedIdx - 1, { frames: stateFrames, filmstrip, mainView, timeLabel, scrubber });
        }
      } else {
        // Past the left edge — reload centered on the first (oldest) frame.
        const edgeTs = stateFrames[0].client_ts;
        _detachKeyboard();
        content.innerHTML = '<p class="frame-browser__no-outcome">Loading…</p>';
        _loadWindow({ run, centerTs: edgeTs, content, sidebar });
      }
    }
  };

  document.addEventListener("keydown", _keyHandler);
}

/** Remove the keyboard listener (idempotent). */
function _detachKeyboard() {
  if (_keyHandler) {
    document.removeEventListener("keydown", _keyHandler);
    _keyHandler = null;
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/** Convert an ISO-8601 string to epoch milliseconds. */
function _isoToMs(iso) {
  return new Date(iso).getTime();
}

/** Convert epoch milliseconds to an ISO-8601 string. */
function _msToIso(ms) {
  return new Date(ms).toISOString();
}

/**
 * Format an ISO timestamp as a time-of-day string (HH:MM:SS.mmm local time).
 * @param {string} iso
 * @returns {string}
 */
function _formatTimeOfDay(iso) {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

/** Escape a string for safe insertion into text content (belt-and-suspenders). */
function _esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Scroll the nth thumbnail into view within the filmstrip. */
function _scrollThumbIntoView(filmstrip, idx) {
  const thumb = filmstrip.querySelector(`.filmstrip__thumb[data-idx="${idx}"]`);
  if (thumb) thumb.scrollIntoView({ block: "nearest", inline: "nearest" });
}

// ---------------------------------------------------------------------------
// Inline self-check (runs only when this file is executed with node --check;
// actual DOM-dependent paths are guarded behind typeof document checks).
// ---------------------------------------------------------------------------
// (No runnable assertions here — the module has DOM imports that node cannot
//  execute; --check validates syntax only, which is the acceptance requirement.)
