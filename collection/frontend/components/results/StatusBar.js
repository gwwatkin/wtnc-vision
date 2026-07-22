/**
 * StatusBar.js — Polling status indicator bar.
 *
 * Presentational port of results/status.js's rendering logic.
 * No fetch — the status payload is polled by ResultsApp and passed as a prop.
 *
 * Rendering rules (design §6.1 / status.js parity):
 *   - status === null (pre-first-poll or poll error): render hidden placeholder.
 *   - status.enabled === false: render hidden (empty).
 *   - state === "up_to_date":
 *       <dot green> Queue: N captured · all processed — ✓ up to date
 *   - state === "processing" (draining):
 *       <dot amber> Queue: N captured · M processed · P pending — processing…
 *       results current to HH:MM:SS   (when processed_through is present)
 *
 * @module components/results/StatusBar
 */

import { html } from '../../vendor/preact-setup.js';

/**
 * Format a processed_through ISO timestamp as HH:MM:SS.
 * Returns null if the value is missing or unparseable.
 *
 * @param {string|null|undefined} processedThrough
 * @returns {string|null}
 */
function formatProcessedThrough(processedThrough) {
  if (!processedThrough) return null;
  try {
    const d = new Date(processedThrough);
    if (isNaN(d.getTime())) return null;
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  } catch (_e) {
    return null;
  }
}

/**
 * @param {import('../../types').StatusBarProps} props
 * @returns {any}
 */
export function StatusBar({ status }) {
  // null = pre-first-poll or poll error — render hidden placeholder matching
  // the initial <div id="queue-status" hidden></div> in index.html.
  if (status === null || status === undefined) {
    return html`<div id="queue-status" hidden></div>`;
  }

  // Cast to typed shape — status prop is declared as object | null (frozen contract);
  // StatusPayload gives tsc the exact field set used below.
  const payload = /** @type {import('../../types').StatusPayload} */ (status);

  // enabled: false — hide just like status.js does.
  if (!payload.enabled) {
    return html`<div id="queue-status" hidden></div>`;
  }

  const { captured, processed, pending, state, processed_through } = payload;

  /** @type {string} */
  let dotClass;
  /** @type {string} */
  let statusText;

  if (state === 'up_to_date') {
    dotClass   = 'status-dot status-dot--green';
    statusText = `Queue: ${captured} captured · all processed — ✓ up to date`;
  } else {
    // state === "processing" (draining)
    dotClass   = 'status-dot status-dot--amber';
    statusText =
      `Queue: ${captured} captured · ${processed} processed · ` +
      `${pending} pending — processing…`;
  }

  // "results current to HH:MM:SS" — shown only while draining (FR17).
  const currentToTime = state !== 'up_to_date'
    ? formatProcessedThrough(processed_through)
    : null;

  return html`
    <div id="queue-status">
      <span class=${dotClass} aria-hidden="true"></span>
      <span class="status-text">${statusText}</span>
      ${currentToTime && html`
        <span class="status-current-to">results current to ${currentToTime}</span>
      `}
    </div>
  `;
}
