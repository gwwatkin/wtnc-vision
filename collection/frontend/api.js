/**
 * api.js — Single fetch layer for both the results and capture pages.
 * All functions are pure async — no globals mutated, no DOM touched.
 * Paths are the existing wire contract (FROZEN-6); do not change them.
 * Stub bodies; filled by task7.
 *
 * @module api
 */

const BASE = () => /** @type {any} */ (window).COLLECTION_CONFIG?.BACKEND_URL ?? '';

// ── reads ──

/**
 * @returns {Promise<string[]>}
 */
export async function fetchRuns() { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @returns {Promise<unknown>}
 */
export async function fetchResults(runLabel) { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @returns {Promise<unknown>}
 */
export async function fetchCandidates(runLabel) { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @returns {Promise<unknown>}
 */
export async function fetchStatus(runLabel) { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @param {{ anchorTs: string, spanS: number, limit: number }} opts
 * @returns {Promise<unknown>}
 */
export async function fetchFrames(runLabel, opts) { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @returns {Promise<Array<{ number: string, name: string }>>}
 */
export async function fetchRoster(runLabel) { throw new Error('stub'); }

// ── results-side mutations ──

/**
 * @param {string} runLabel
 * @param {string} crossingId
 * @param {object} fields
 * @returns {Promise<void>}
 */
export async function postEdit(runLabel, crossingId, fields) { throw new Error('stub'); }

/**
 * Soft-delete via PATCH { deleted: true } — there is no DELETE route.
 * @param {string} runLabel
 * @param {string} crossingId
 * @returns {Promise<void>}
 */
export async function deleteEdit(runLabel, crossingId) { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @param {object} payload
 * @returns {Promise<void>}
 */
export async function postManualCrossing(runLabel, payload) { throw new Error('stub'); }

/**
 * Neighbour-based reorder — passes { earlier_id, later_id } to the backend.
 * @param {string} runLabel
 * @param {string} crossingId
 * @param {{ earlierId: string, laterId: string }} neighbours
 * @returns {Promise<void>}
 */
export async function reorderCrossing(runLabel, crossingId, neighbours) { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @param {string} candidateId
 * @param {object} payload
 * @returns {Promise<void>}
 */
export async function promoteCandidate(runLabel, candidateId, payload) { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @param {string} candidateId
 * @returns {Promise<void>}
 */
export async function dismissCandidate(runLabel, candidateId) { throw new Error('stub'); }

// ── capture-side ──

/**
 * @returns {Promise<boolean>}
 */
export async function checkHealth() { throw new Error('stub'); }

/**
 * @param {object} payload
 * @returns {Promise<unknown>}
 */
export async function postFrame(payload) { throw new Error('stub'); }

/**
 * @param {string} runLabel
 * @param {File} file
 * @returns {Promise<void>}
 */
export async function uploadRoster(runLabel, file) { throw new Error('stub'); }

// ── sync URL builders (no fetch) ──

/**
 * @param {string} runLabel
 * @param {string} filename
 * @returns {string}
 */
export function frameUrl(runLabel, filename) { throw new Error('stub'); }
