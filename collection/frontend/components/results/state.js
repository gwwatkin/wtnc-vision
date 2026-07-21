/**
 * state.js — Reducer, initial state, and view-derivation helpers for ResultsApp.
 * Stub bodies filled by task8.
 *
 * @module components/results/state
 */

/**
 * Initial state for ResultsApp.
 * @type {import('../../types').State}
 */
export const initialState = /** @type {any} */ (null);

/**
 * Pure reducer for ResultsApp.
 * @param {import('../../types').State} state
 * @param {import('../../types').Action} action
 * @returns {import('../../types').State}
 */
export function reducer(state, action) { throw new Error('stub'); }

/**
 * Port of today's results.js render pipeline (FROZEN-2).
 * @param {import('../../types').Result[]} crossings
 * @param {import('../../types').CandidateResult[]} candidates
 * @param {boolean} candidatesVisible
 * @returns {{ packs: import('../../types').Pack[], lanes: import('../../types').Lane[] }}
 */
export function deriveView(crossings, candidates, candidatesVisible) { throw new Error('stub'); }

/**
 * Compute a string hash over raw poll payload for change-detection (task8).
 * @param {string} resultsJson
 * @param {string} candidatesJson
 * @returns {string}
 */
export function hashPayload(resultsJson, candidatesJson) { throw new Error('stub'); }
