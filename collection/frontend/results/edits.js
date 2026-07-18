// edits.js — Thin API client for crossing/candidate edit operations (stub; task7).
//
// Every mutator: on 2xx dispatches new CustomEvent("wtnc:edited") on document
// and returns the parsed body; on non-2xx throws Error(detail).
//
// Exports:
//   createCrossing({ run, filename, clientTs, number })
//   patchCrossing(crossingId, { number, deleted })   // ≥1 key required
//   setPosition(crossingId, { earlierId, laterId })  // null ok
//   resolveCandidate(candidateId, { action, number })
//   loadRosterNumbers(run)
//     → fills #roster-numbers <datalist> from GET /roster; returns riders array.

/**
 * Create a manual crossing.
 *
 * @param {{ run: string, filename: string, clientTs: string, number: string }} params
 * @returns {Promise<object>} parsed crossing dict
 */
export async function createCrossing({ run, filename, clientTs, number }) {
  throw new Error("not implemented");
}

/**
 * Edit a crossing's number or soft-delete flag.
 *
 * @param {string} crossingId
 * @param {{ number?: string, deleted?: boolean }} patch — at least one key required
 * @returns {Promise<object>} parsed crossing dict
 */
export async function patchCrossing(crossingId, { number, deleted } = {}) {
  throw new Error("not implemented");
}

/**
 * Reorder a crossing between neighbors.
 *
 * @param {string} crossingId
 * @param {{ earlierId: string|null, laterId: string|null }} neighbors
 * @returns {Promise<object>} parsed crossing dict
 */
export async function setPosition(crossingId, { earlierId, laterId } = {}) {
  throw new Error("not implemented");
}

/**
 * Promote or dismiss a candidate.
 *
 * @param {string} candidateId
 * @param {{ action: string, number: string }} opts
 * @returns {Promise<object>} parsed result dict
 */
export async function resolveCandidate(candidateId, { action, number } = {}) {
  throw new Error("not implemented");
}

/**
 * Load roster numbers into #roster-numbers <datalist>.
 * No-op stub; task7 implements.
 *
 * @param {string} run
 * @returns {Promise<Array>} riders array
 */
export async function loadRosterNumbers(run) {
  return [];
}
