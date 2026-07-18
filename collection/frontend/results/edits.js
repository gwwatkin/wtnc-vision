/**
 * edits.js — Thin API client for crossing/candidate edit operations.
 *
 * Every mutator: on 2xx dispatches new CustomEvent("wtnc:edited") on document
 * and returns the parsed body; on non-2xx throws Error with the server's `detail`.
 *
 * Exports (frozen — README §FROZEN JS module contracts):
 *   createCrossing({ run, filename, clientTs, number })
 *   patchCrossing(crossingId, { number, deleted })   // ≥1 key required
 *   setPosition(crossingId, { earlierId, laterId })  // null ok
 *   resolveCandidate(candidateId, { action, number })
 *   loadRosterNumbers(run)
 *     → fills #roster-numbers <datalist> from GET /roster; returns riders array.
 *
 * @module results/edits
 */

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Dispatch the wtnc:edited event so results.js clears its payload cache and
 * re-renders on the next tick (NFR6).
 */
function _dispatchEdited() {
  document.dispatchEvent(new CustomEvent("wtnc:edited"));
}

/**
 * Shared fetch wrapper.  On 2xx returns parsed JSON and fires the edit event.
 * On non-2xx extracts `detail` from the error body and throws.
 *
 * @param {string} url
 * @param {RequestInit} init
 * @returns {Promise<object>}
 */
async function _apiFetch(url, init) {
  const resp = await fetch(url, init);
  if (resp.ok) {
    const body = await resp.json();
    _dispatchEdited();
    return body;
  }
  // Extract the server's detail string from the standard FastAPI error shape.
  let detail = `HTTP ${resp.status}`;
  try {
    const err = await resp.json();
    if (err && typeof err.detail === "string") {
      detail = err.detail;
    } else if (err && err.detail) {
      detail = String(err.detail);
    }
  } catch (_) {
    // non-JSON error body — keep the status string
  }
  throw new Error(detail);
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

/**
 * Create a manual crossing (POST /crossings).
 * Design §5: JSON body { run, filename, client_ts, number }.
 * Returns 201 crossing dict.
 *
 * @param {{ run: string, filename: string, clientTs: string, number: string }} params
 * @returns {Promise<object>} parsed crossing dict
 */
export async function createCrossing({ run, filename, clientTs, number }) {
  return _apiFetch("/crossings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      run,
      filename,
      client_ts: clientTs,
      number,
    }),
  });
}

/**
 * Edit a crossing's number or soft-delete flag (PATCH /crossings/{id}).
 * Design §5: JSON body { number?, deleted? } — at least one key required.
 * Returns crossing dict.
 *
 * @param {string} crossingId
 * @param {{ number?: string, deleted?: boolean }} patch — at least one key required
 * @returns {Promise<object>} parsed crossing dict
 */
export async function patchCrossing(crossingId, { number, deleted } = {}) {
  const body = {};
  if (number !== undefined) body.number = number;
  if (deleted !== undefined) body.deleted = deleted;
  return _apiFetch(`/crossings/${encodeURIComponent(crossingId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/**
 * Reorder a crossing between neighbors (POST /crossings/{id}/position).
 * Design §5: JSON body { earlier_id: str|null, later_id: str|null }.
 * Returns crossing dict.
 *
 * @param {string} crossingId
 * @param {{ earlierId: string|null, laterId: string|null }} neighbors
 * @returns {Promise<object>} parsed crossing dict
 */
export async function setPosition(crossingId, { earlierId, laterId } = {}) {
  return _apiFetch(
    `/crossings/${encodeURIComponent(crossingId)}/position`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        earlier_id: earlierId ?? null,
        later_id: laterId ?? null,
      }),
    }
  );
}

/**
 * Promote or dismiss a candidate (POST /candidates/{id}/resolve).
 * Design §5: JSON body { action: "promote"|"dismiss", number: "" }.
 * Returns { candidate, crossing? }.
 *
 * @param {string} candidateId
 * @param {{ action: string, number?: string }} opts
 * @returns {Promise<object>} parsed result dict
 */
export async function resolveCandidate(candidateId, { action, number = "" } = {}) {
  return _apiFetch(
    `/candidates/${encodeURIComponent(candidateId)}/resolve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, number }),
    }
  );
}

/**
 * Load roster numbers into #roster-numbers <datalist> from GET /roster?run=.
 * Populates <option value=number label="name"> entries (refinement 2).
 * Tolerates empty/absent roster.
 *
 * @param {string} run
 * @returns {Promise<Array>} riders array (may be empty)
 */
export async function loadRosterNumbers(run) {
  const datalist = document.getElementById("roster-numbers");

  let riders = [];
  try {
    const resp = await fetch(`/roster?run=${encodeURIComponent(run)}`);
    if (resp.ok) {
      const payload = await resp.json();
      riders = Array.isArray(payload.riders) ? payload.riders : [];
    }
  } catch (_) {
    // Network error — leave datalist empty; non-fatal.
  }

  if (datalist) {
    datalist.innerHTML = "";
    for (const rider of riders) {
      const opt = document.createElement("option");
      opt.value = String(rider.number);
      opt.label = rider.name ? String(rider.name) : String(rider.number);
      datalist.appendChild(opt);
    }
  }

  return riders;
}
