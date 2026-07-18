/**
 * status.js — Queue status poller (design §6.1).
 *
 * Exports:
 *   pollStatus(label) — async; polls GET /status?run=label and renders
 *     #queue-status (§6.1). Hidden when label is "" or enabled:false.
 *     Never throws (network errors leave last render in place).
 *
 * Per-concern skip: keeps its OWN last-payload compare, independent of
 * results.js's timeline compare (design §6.5 — status changing every tick
 * while a backlog drains must never force a timeline re-render).
 *
 * @module results/status
 */

// ---------------------------------------------------------------------------
// Module state — status.js owns its own skip logic, never tied to results.js
// ---------------------------------------------------------------------------

/** Last JSON string rendered into #queue-status — skip re-render when equal. */
let _lastStatusJson = null;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Poll GET /status?run=label and update the #queue-status element.
 *
 * Rendering rules (design §6.1):
 *   - label "" or payload.enabled === false  ⇒ hide element, do NOT update
 *     _lastStatusJson (so the next non-empty label gets a fresh render).
 *   - draining (state === "processing"):
 *       <dot amber> Queue: N captured · M processed · P pending — processing…
 *       results current to HH:MM:SS   (when processed_through is present)
 *   - caught up (state === "up_to_date"):
 *       <dot green> Queue: N captured · all processed — ✓ up to date
 *
 * @param {string} label - the current run label (may be empty or raw)
 * @returns {Promise<void>}
 */
export async function pollStatus(label) {
  const statusEl = document.getElementById("queue-status");
  if (!statusEl) return;

  // Hide immediately when label is blank — don't leave a stale readout.
  if (!label) {
    statusEl.setAttribute("hidden", "");
    // Clear the skip-cache so a new label gets its first render promptly.
    _lastStatusJson = null;
    return;
  }

  let payload;
  try {
    const resp = await fetch(
      `/status?run=${encodeURIComponent(label)}`,
      { cache: "no-store" }
    );
    if (!resp.ok) return;   // network/server error — leave last render in place
    payload = await resp.json();
  } catch (_err) {
    // Network error — swallow, leave last render (NFR6 / task6 spec).
    return;
  }

  // enabled: false  ⇒ hide and clear cache so a future re-enable re-renders.
  if (!payload.enabled) {
    statusEl.setAttribute("hidden", "");
    _lastStatusJson = null;
    return;
  }

  // Per-concern skip: only re-render when the status payload actually changed.
  const json = JSON.stringify(payload);
  if (json === _lastStatusJson) return;
  _lastStatusJson = json;

  // Build the rendered HTML.
  const { captured, processed, pending, state, processed_through } = payload;

  let dotClass;
  let statusText;

  if (state === "up_to_date") {
    dotClass  = "status-dot status-dot--green";
    statusText =
      `Queue: ${captured} captured · all processed — ✓ up to date`;
  } else {
    // state === "processing" (draining)
    dotClass  = "status-dot status-dot--amber";
    statusText =
      `Queue: ${captured} captured · ${processed} processed · ` +
      `${pending} pending — processing…`;
  }

  // Include "results current to HH:MM:SS" while draining (FR17).
  let currentToHtml = "";
  if (state !== "up_to_date" && processed_through) {
    try {
      const d = new Date(processed_through);
      if (!isNaN(d.getTime())) {
        const hh = String(d.getHours()).padStart(2, "0");
        const mm = String(d.getMinutes()).padStart(2, "0");
        const ss = String(d.getSeconds()).padStart(2, "0");
        currentToHtml =
          ` <span class="status-current-to">results current to ${hh}:${mm}:${ss}</span>`;
      }
    } catch (_e) {
      // ignore bad timestamp
    }
  }

  statusEl.innerHTML =
    `<span class="${dotClass}" aria-hidden="true"></span>` +
    `<span class="status-text">${statusText}</span>` +
    currentToHtml;

  statusEl.removeAttribute("hidden");
}
