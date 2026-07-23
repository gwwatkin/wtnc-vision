/**
 * StatusBar.tsx — Polling status indicator bar.
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

import type { StatusBarProps, StatusPayload } from '../../types';

/**
 * Format a processed_through ISO timestamp as HH:MM:SS.
 * Returns null if the value is missing or unparseable.
 */
function formatProcessedThrough(processedThrough: string | null | undefined): string | null {
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

export function StatusBar({ status }: StatusBarProps) {
  // null = pre-first-poll or poll error — render hidden placeholder matching
  // the initial <div id="queue-status" hidden></div> in index.html.
  if (status === null || status === undefined) {
    return <div id="queue-status" hidden></div>;
  }

  // Cast to typed shape — status prop is declared as object | null (frozen contract);
  // StatusPayload gives tsc the exact field set used below.
  const payload = status as StatusPayload;

  // enabled: false — hide just like status.js does.
  if (!payload.enabled) {
    return <div id="queue-status" hidden></div>;
  }

  const { captured, processed, pending, state, processed_through } = payload;

  let dotClass: string;
  let statusText: string;

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

  return (
    <div id="queue-status">
      <span class={dotClass} aria-hidden="true"></span>
      <span class="status-text">{statusText}</span>
      {currentToTime &&
        <span class="status-current-to">results current to {currentToTime}</span>
      }
    </div>
  );
}
