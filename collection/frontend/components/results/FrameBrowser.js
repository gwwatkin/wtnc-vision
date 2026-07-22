/**
 * FrameBrowser.js — Frame-browser overlay for manual crossing creation.
 *
 * Ports browser.js: filmstrip/scrubber, frame image + bounding-box canvas
 * overlay, and the add-crossing row. Frames are fetched via api.fetchFrames;
 * image URLs are built via api.frameUrl. New crossings are submitted through
 * the onCreateCrossing callback — no direct api.js mutations from this component.
 *
 * @module components/results/FrameBrowser
 */

import { html, useState, useEffect, useRef, useCallback, useMemo } from '../../vendor/preact-setup.js';
import * as api from '../../api.js';
import { setRosterOptions } from './roster.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Default span seconds when COLLECTION_CONFIG is absent */
const DEFAULT_SPAN_S = 12;
/** Default frame limit when COLLECTION_CONFIG is absent */
const DEFAULT_LIMIT = 300;
/** Scrubber debounce ms */
const SCRUB_DEBOUNCE_MS = 150;

/** @returns {{ spanS: number, limit: number }} */
function getFrameConfig() {
  const cfg = /** @type {any} */ (window).COLLECTION_CONFIG ?? {};
  return {
    spanS: cfg.FRAMES_SPAN_S != null ? cfg.FRAMES_SPAN_S : DEFAULT_SPAN_S,
    limit: cfg.FRAMES_LIMIT  != null ? cfg.FRAMES_LIMIT  : DEFAULT_LIMIT,
  };
}

// ---------------------------------------------------------------------------
// Canvas overlay for rider bounding boxes
// ---------------------------------------------------------------------------

/**
 * @param {{ imgEl: HTMLImageElement|null, riders: Array<{box:number[],status:string,number:string|null,raw_text:string|null,confidence:number}>|null }} props
 */
function RiderBoxCanvas({ imgEl, riders }) {
  const canvasRef = useRef(/** @type {HTMLCanvasElement|null} */ (null));

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgEl;
    if (!canvas || !img) return;

    canvas.width  = img.naturalWidth  || img.offsetWidth;
    canvas.height = img.naturalHeight || img.offsetHeight;
    canvas.style.width  = `${img.offsetWidth}px`;
    canvas.style.height = `${img.offsetHeight}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!riders || riders.length === 0) return;

    const scaleX = img.offsetWidth  / (img.naturalWidth  || img.offsetWidth);
    const scaleY = img.offsetHeight / (img.naturalHeight || img.offsetHeight);

    /** @type {Record<string,string>} */
    const COLOR = {
      confident:    '#22c55e',
      needs_review: '#f59e0b',
      rejected:     '#ef4444',
    };

    for (const rider of riders) {
      if (!rider.box || rider.box.length < 4) continue;
      const [x1, y1, x2, y2] = rider.box;
      const rx = x1 * scaleX;
      const ry = y1 * scaleY;
      const rw = (x2 - x1) * scaleX;
      const rh = (y2 - y1) * scaleY;
      const color = COLOR[rider.status] ?? '#94a3b8';

      ctx.strokeStyle = color;
      ctx.lineWidth   = 2;
      ctx.strokeRect(rx, ry, rw, rh);

      const label = `${rider.number ?? rider.raw_text ?? '?'} (${(rider.confidence * 100).toFixed(0)}%)`;
      ctx.font = 'bold 12px sans-serif';
      const textMetrics = ctx.measureText(label);
      const textH = 14;
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(rx, ry - textH - 2, textMetrics.width + 4, textH + 2);
      ctx.fillStyle = color;
      ctx.fillText(label, rx + 2, ry - 3);
    }
  }, [imgEl, riders]);

  useEffect(() => {
    const img = imgEl;
    if (!img) return;
    if (img.complete && img.naturalWidth > 0) {
      draw();
    } else {
      img.addEventListener('load', draw);
    }
    let ro = /** @type {ResizeObserver|null} */ (null);
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => { if (img.naturalWidth > 0) draw(); });
      ro.observe(img);
    }
    return () => {
      img.removeEventListener('load', draw);
      if (ro) ro.disconnect();
    };
  }, [imgEl, draw]);

  return html`<canvas
    ref=${canvasRef}
    class="frame-canvas-overlay"
    style="position:absolute;top:0;left:0;pointer-events:none;"
  />`;
}

// ---------------------------------------------------------------------------
// Main frame view
// ---------------------------------------------------------------------------

/**
 * @param {{ runLabel: string, frame: object|null }} props
 */
function MainFrameView({ runLabel, frame }) {
  const imgRef = useRef(/** @type {HTMLImageElement|null} */ (null));
  const [imgEl, setImgEl] = useState(/** @type {HTMLImageElement|null} */ (null));

  // capture ref to the img element so canvas can observe it
  const imgCallbackRef = useCallback((/** @type {HTMLImageElement|null} */ el) => {
    imgRef.current = el;
    setImgEl(el);
  }, []);

  if (!frame) return null;

  const f = /** @type {any} */ (frame);
  const src = api.frameUrl(runLabel, f.filename);
  const riders = f.processed ? (f.riders ?? []) : null;
  const altText = `Frame at ${_formatTimeOfDay(f.client_ts)}`;

  return html`
    <div class="frame-browser__main">
      ${!f.processed
        ? html`<p class="frame-browser__no-outcome">No outcome data (frame not yet processed)</p>`
        : null}
      <div class="frame-canvas-wrapper">
        <img
          ref=${imgCallbackRef}
          src=${src}
          alt=${altText}
          style="width:100%;display:block;"
        />
        ${f.processed
          ? html`<${RiderBoxCanvas} imgEl=${imgEl} riders=${riders} />`
          : null}
      </div>
      ${f.processed
        ? html`<div class="frame-browser__outcome"></div>`
        : null}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Add-crossing row
// ---------------------------------------------------------------------------

/**
 * @param {{ runLabel: string, frame: object|null,
 *   onCreateCrossing: (payload: object) => Promise<void> }} props
 */
function AddCrossingRow({ runLabel, frame, onCreateCrossing }) {
  const [open, setOpen] = useState(false);
  const [numberValue, setNumberValue] = useState('');
  const [feedback, setFeedback] = useState('');
  const [saving, setSaving] = useState(false);

  const handleOpen = useCallback(() => {
    setOpen(true);
    setFeedback('');
    setNumberValue('');
  }, []);

  const handleCancel = useCallback(() => {
    setOpen(false);
    setNumberValue('');
    setFeedback('');
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!frame) return;
    const f = /** @type {any} */ (frame);
    setSaving(true);
    setFeedback('Saving…');
    try {
      await onCreateCrossing({
        run:      runLabel,
        filename: f.filename,
        clientTs: f.client_ts,
        number:   numberValue.trim(),
      });
      setFeedback('Crossing added.');
      setNumberValue('');
      setTimeout(() => {
        setFeedback('');
        setOpen(false);
      }, 2000);
    } catch (/** @type {any} */ err) {
      setFeedback(`Error: ${err.message ?? 'unknown'}`);
    } finally {
      setSaving(false);
    }
  }, [frame, runLabel, numberValue, onCreateCrossing]);

  if (!frame) return null;

  return html`
    <div class="frame-browser__add-row">
      ${!open
        ? html`<button type="button" onClick=${handleOpen}>Add crossing here</button>`
        : html`
            <div>
              <input
                type="text"
                placeholder="Race number (blank = unidentified)"
                list="roster-numbers"
                autocomplete="off"
                value=${numberValue}
                onInput=${(/** @type {any} */ e) => setNumberValue(e.target.value)}
              />
              <button type="button" disabled=${saving} onClick=${handleSubmit}>Save crossing</button>
              <button type="button" onClick=${handleCancel}>Cancel</button>
              ${feedback ? html`<span class="frame-browser__feedback">${feedback}</span>` : null}
            </div>
          `}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// FrameBrowser (public export)
// ---------------------------------------------------------------------------

/**
 * Frame-browser overlay. Fetches frames centred on anchorTs and renders the
 * filmstrip/scrubber/main view. Keyboard navigation (← →) is wired via a
 * document-level listener that is torn down on unmount.
 *
 * @param {import('../../types').FrameBrowserProps} props
 * @returns {any}
 */
export function FrameBrowser(props) {
  const { runLabel, anchorTs, onClose, onCreateCrossing } = props;

  // ── Fetch state ────────────────────────────────────────────────────────────
  /** @type {[Array<any>|null, Function]} */
  const [frames, setFrames] = useState(/** @type {Array<any>|null} */ (null));
  /** @type {[object|null, Function]} */
  const [meta, setMeta] = useState(/** @type {object|null} */ (null));
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [loadError, setLoadError] = useState(/** @type {string|null} */ (null));
  const [loading, setLoading] = useState(true);

  // Tracks the anchor used for the current window, so the scrubber can reload.
  const [windowAnchor, setWindowAnchor] = useState(anchorTs);

  // ── Populate roster datalist on open ──────────────────────────────────────
  useEffect(() => {
    if (runLabel) setRosterOptions(runLabel);
  }, [runLabel]);

  // ── Load frame window ─────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const { spanS, limit } = getFrameConfig();

    setLoading(true);
    setLoadError(null);
    setFrames(null);
    setMeta(null);

    api.fetchFrames(runLabel, { anchorTs: windowAnchor, spanS, limit })
      .then((data) => {
        if (cancelled) return;
        const d = /** @type {any} */ (data);
        const framesArr = d.frames ?? [];
        const metaObj   = d.meta   ?? {};

        if (framesArr.length === 0) {
          setLoadError('No frames found for this run.');
          setLoading(false);
          return;
        }

        // Select the frame closest to the anchor.
        let bestIdx = framesArr.length - 1;
        if (windowAnchor) {
          const anchorMs = new Date(windowAnchor).getTime();
          let bestDelta = Infinity;
          framesArr.forEach((/** @type {any} */ f, /** @type {number} */ i) => {
            const delta = Math.abs(new Date(f.client_ts).getTime() - anchorMs);
            if (delta < bestDelta) { bestDelta = delta; bestIdx = i; }
          });
        }

        setFrames(framesArr);
        setMeta(metaObj);
        setSelectedIdx(bestIdx);
        setLoading(false);
      })
      .catch((/** @type {any} */ err) => {
        if (cancelled) return;
        setLoadError(`Error loading frames: ${err.message ?? 'unknown'}`);
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, [runLabel, windowAnchor]);

  // ── Scrubber state ─────────────────────────────────────────────────────────
  const scrubTimerRef = useRef(/** @type {ReturnType<typeof setTimeout>|null} */ (null));

  const handleScrub = useCallback((/** @type {any} */ e) => {
    if (scrubTimerRef.current != null) clearTimeout(scrubTimerRef.current);
    const chosenMs = Number(e.target.value);
    scrubTimerRef.current = setTimeout(() => {
      scrubTimerRef.current = null;
      setWindowAnchor(new Date(chosenMs).toISOString());
    }, SCRUB_DEBOUNCE_MS);
  }, []);

  // ── Keyboard navigation ────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (/** @type {KeyboardEvent} */ e) => {
      if (!frames || frames.length === 0) return;
      const target = /** @type {any} */ (e.target);
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return;
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();

      setSelectedIdx((/** @type {number} */ cur) => {
        if (e.key === 'ArrowRight') {
          if (cur < frames.length - 1) return cur + 1;
          // Past the right edge — reload centred on the last frame.
          setWindowAnchor(frames[frames.length - 1].client_ts);
          return cur;
        } else {
          if (cur > 0) return cur - 1;
          // Past the left edge — reload centred on the first frame.
          setWindowAnchor(frames[0].client_ts);
          return cur;
        }
      });
    };

    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [frames]);

  // ── Derived values ─────────────────────────────────────────────────────────
  const selectedFrame = frames ? frames[selectedIdx] ?? null : null;

  const metaObj = /** @type {any} */ (meta ?? {});
  const firstMs = metaObj.first_ts ? new Date(metaObj.first_ts).getTime() : null;
  const lastMs  = metaObj.last_ts  ? new Date(metaObj.last_ts).getTime()  : null;
  const hasRange = firstMs !== null && lastMs !== null && lastMs > firstMs;
  const scrubMin   = hasRange ? String(firstMs) : '0';
  const scrubMax   = hasRange ? String(lastMs)  : '1';
  const scrubValue = selectedFrame ? String(new Date(selectedFrame.client_ts).getTime()) : scrubMax;
  const timeLabel  = selectedFrame ? _formatTimeOfDay(selectedFrame.client_ts) : '';

  // ── Filmstrip scroll ref ───────────────────────────────────────────────────
  const filmstripRef = useRef(/** @type {HTMLElement|null} */ (null));
  useEffect(() => {
    const filmstrip = filmstripRef.current;
    if (!filmstrip) return;
    const thumb = filmstrip.querySelector(`.filmstrip__thumb[data-idx="${selectedIdx}"]`);
    if (thumb) /** @type {Element} */ (thumb).scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [selectedIdx, frames]);

  // ── Render ─────────────────────────────────────────────────────────────────
  return html`
    <div class="frame-browser__overlay" role="dialog" aria-modal="true">
      <div class="sidebar__header">
        <button
          type="button"
          class="sidebar__close"
          aria-label="Close frame browser"
          onClick=${onClose}
        >×</button>
      </div>

      ${loading
        ? html`<p class="frame-browser__no-outcome">Loading frames…</p>`
        : loadError
          ? html`<p class="frame-browser__no-outcome">${loadError}</p>`
          : html`
              <div class="frame-browser">
                <div class="frame-browser__scrubber">
                  <input
                    type="range"
                    min=${scrubMin}
                    max=${scrubMax}
                    step="1"
                    value=${scrubValue}
                    onInput=${handleScrub}
                  />
                  <span>${timeLabel}</span>
                </div>

                <div class="frame-browser__filmstrip" ref=${filmstripRef}>
                  ${(frames ?? []).map((/** @type {any} */ f, /** @type {number} */ idx) => html`
                    <img
                      key=${f.filename ?? idx}
                      class=${'filmstrip__thumb' + (idx === selectedIdx ? ' filmstrip__thumb--active' : '')}
                      src=${api.frameUrl(runLabel, f.filename)}
                      alt=${'Frame ' + (idx + 1)}
                      loading="lazy"
                      data-idx=${String(idx)}
                      onClick=${() => setSelectedIdx(idx)}
                    />
                  `)}
                </div>

                <${MainFrameView} runLabel=${runLabel} frame=${selectedFrame} />

                <${AddCrossingRow}
                  runLabel=${runLabel}
                  frame=${selectedFrame}
                  onCreateCrossing=${onCreateCrossing}
                />
              </div>
            `}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Utilities (local)
// ---------------------------------------------------------------------------

/**
 * Format an ISO timestamp or Date as HH:MM:SS.mmm (local time).
 * @param {string|Date} isoOrDate
 * @returns {string}
 */
function _formatTimeOfDay(isoOrDate) {
  const d = isoOrDate instanceof Date ? isoOrDate : new Date(isoOrDate);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  const ms = String(d.getMilliseconds()).padStart(3, '0');
  return `${hh}:${mm}:${ss}.${ms}`;
}
