/**
 * api.js — Single fetch layer for both the results and capture pages.
 * All functions are pure async — no globals mutated, no DOM touched.
 * Paths are the existing wire contract (FROZEN-2, page-split spec); do not change them.
 *
 * @module api
 */

// @ts-check

import { getBackendUrl } from './backend-url.js';

/** @returns {string} Current back-end base URL (cookie override → config default → same-origin). */
const BASE = () => getBackendUrl();

// ── internal helper ──

/**
 * Fetch wrapper that throws on non-2xx responses.
 * Prepends BASE() so every caller automatically targets the configured back-end.
 * @param {string} path  Leading-slash API path, e.g. '/runs'.
 * @param {RequestInit} [init]
 * @returns {Promise<Response>}
 */
async function _fetch(path, init) {
  const resp = await fetch(BASE() + path, init);
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const err = await resp.json();
      if (err && typeof err.detail === 'string') detail = err.detail;
      else if (err && err.detail) detail = String(err.detail);
    } catch (_) { /* non-JSON error body */ }
    throw new Error(detail);
  }
  return resp;
}

// ── reads ──

/**
 * @returns {Promise<string[]>}
 */
export async function fetchRuns() {
  const resp = await _fetch('/runs', { cache: 'no-store' });
  const data = await resp.json();
  return Array.isArray(data.runs) ? data.runs : [];
}

/**
 * @param {string} runLabel
 * @returns {Promise<unknown>}
 */
export async function fetchResults(runLabel) {
  const resp = await _fetch(
    `/results?run=${encodeURIComponent(runLabel)}`,
    { cache: 'no-store' },
  );
  return resp.json();
}

/**
 * @param {string} runLabel
 * @returns {Promise<unknown>}
 */
export async function fetchCandidates(runLabel) {
  const resp = await _fetch(
    `/candidates?run=${encodeURIComponent(runLabel)}`,
    { cache: 'no-store' },
  );
  return resp.json();
}

/**
 * @param {string} runLabel
 * @returns {Promise<unknown>}
 */
export async function fetchStatus(runLabel) {
  const resp = await _fetch(
    `/status?run=${encodeURIComponent(runLabel)}`,
    { cache: 'no-store' },
  );
  return resp.json();
}

/**
 * Fetch a frame window from the server.
 * Query params: run, span (seconds, from spanS), limit, center (ISO, from anchorTs).
 *
 * @param {string} runLabel
 * @param {{ anchorTs: string | null, spanS: number, limit: number }} opts
 * @returns {Promise<unknown>}
 */
export async function fetchFrames(runLabel, { anchorTs, spanS, limit }) {
  const params = new URLSearchParams({
    run:   runLabel,
    span:  String(spanS),
    limit: String(limit),
  });
  if (anchorTs) params.set('center', anchorTs);
  const resp = await _fetch(`/frames?${params}`);
  return resp.json();
}

/**
 * Fetch the roster for a run. Tolerates an empty/absent roster.
 *
 * @param {string} runLabel
 * @returns {Promise<Array<{ number: string, name: string }>>}
 */
export async function fetchRoster(runLabel) {
  const resp = await _fetch(`/roster?run=${encodeURIComponent(runLabel)}`);
  const payload = await resp.json();
  return Array.isArray(payload.riders) ? payload.riders : [];
}

// ── results-side mutations ──

/**
 * Edit a crossing's number or soft-delete flag (PATCH /crossings/{id}).
 * Body: { number?, deleted? } — at least one key expected.
 *
 * @param {string} runLabel
 * @param {string} crossingId
 * @param {object} fields
 * @returns {Promise<void>}
 */
export async function postEdit(runLabel, crossingId, fields) {
  await _fetch(`/crossings/${encodeURIComponent(crossingId)}`, {
    method:  'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(fields),
  });
}

/**
 * Soft-delete via PATCH { deleted: true } — there is no DELETE route.
 *
 * @param {string} runLabel
 * @param {string} crossingId
 * @returns {Promise<void>}
 */
export async function deleteEdit(runLabel, crossingId) {
  await _fetch(`/crossings/${encodeURIComponent(crossingId)}`, {
    method:  'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ deleted: true }),
  });
}

/**
 * Create a manual crossing (POST /crossings).
 * The caller supplies the ready wire-format payload
 * { run, filename, client_ts, number }.
 *
 * @param {string} runLabel
 * @param {object} payload
 * @returns {Promise<void>}
 */
export async function postManualCrossing(runLabel, payload) {
  await _fetch('/crossings', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });
}

/**
 * Neighbour-based reorder — posts { earlier_id, later_id } to the backend.
 *
 * @param {string} runLabel
 * @param {string} crossingId
 * @param {{ earlierId: string | null, laterId: string | null }} neighbours
 * @returns {Promise<void>}
 */
export async function reorderCrossing(runLabel, crossingId, { earlierId, laterId }) {
  await _fetch(`/crossings/${encodeURIComponent(crossingId)}/position`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      earlier_id: earlierId ?? null,
      later_id:   laterId  ?? null,
    }),
  });
}

/**
 * Promote a candidate to a crossing (POST /candidates/{id}/resolve).
 * payload must carry { action: 'promote', number }.
 *
 * @param {string} runLabel
 * @param {string} candidateId
 * @param {{ action: string, number: string }} payload
 * @returns {Promise<void>}
 */
export async function promoteCandidate(runLabel, candidateId, payload) {
  await _fetch(`/candidates/${encodeURIComponent(candidateId)}/resolve`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ action: 'promote', number: payload.number ?? '' }),
  });
}

/**
 * Dismiss a candidate (POST /candidates/{id}/resolve).
 *
 * @param {string} runLabel
 * @param {string} candidateId
 * @returns {Promise<void>}
 */
export async function dismissCandidate(runLabel, candidateId) {
  await _fetch(`/candidates/${encodeURIComponent(candidateId)}/resolve`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ action: 'dismiss' }),
  });
}

// ── capture-side ──

/**
 * Health probe. Returns true when the back-end responds with 2xx.
 *
 * @returns {Promise<boolean>}
 */
export async function checkHealth() {
  try {
    const resp = await fetch(BASE() + '/health');
    return resp.ok;
  } catch (_) {
    return false;
  }
}

/**
 * Upload a captured frame (POST /frames). Sends a FormData body with
 * fields: image (Blob, jpeg), label, client_ts, seq, session_id (optional).
 * The payload object must carry { image, label, client_ts, seq, session_id? }.
 *
 * @param {{ image: Blob, label: string, client_ts: string, seq: string|number, session_id?: string }} payload
 * @returns {Promise<unknown>}
 */
export async function postFrame(payload) {
  const formData = new FormData();
  formData.append('image', payload.image, 'frame.jpg');
  formData.append('label', payload.label);
  formData.append('client_ts', payload.client_ts);
  formData.append('seq', String(payload.seq));
  if (payload.session_id) {
    formData.append('session_id', payload.session_id);
  }
  // Do NOT set Content-Type — browser sets multipart boundary automatically.
  const resp = await _fetch('/frames', {
    method: 'POST',
    body:   formData,
  });
  return resp.json();
}

/**
 * Upload a roster CSV for a run (POST /roster).
 * Sends a FormData body with fields: run (string), roster (File).
 *
 * @param {string} runLabel
 * @param {File} file
 * @returns {Promise<void>}
 */
export async function uploadRoster(runLabel, file) {
  const formData = new FormData();
  formData.append('run', runLabel);
  formData.append('roster', file);
  // Do NOT set Content-Type — browser sets multipart boundary automatically.
  await _fetch('/roster', {
    method: 'POST',
    body:   formData,
  });
}

// ── sync URL builders (no fetch) ──

/**
 * Build the URL for serving a raw frame image.
 * GET /frames/image?run=&filename=
 * This function performs NO fetch.
 *
 * @param {string} runLabel
 * @param {string} filename
 * @returns {string}
 */
export function frameUrl(runLabel, filename) {
  return BASE() + `/frames/image?run=${encodeURIComponent(runLabel)}&filename=${encodeURIComponent(filename)}`;
}

/**
 * Build the URL for the export endpoint (sync, no fetch).
 * GET /results/export?run=&format=csv|json
 * This function performs NO fetch.
 *
 * @param {string} runLabel
 * @param {'csv'|'json'} format
 * @returns {string}
 */
export function exportUrl(runLabel, format) {
  return BASE() + `/results/export?run=${encodeURIComponent(runLabel)}&format=${encodeURIComponent(format)}`;
}

/**
 * Fetch the export endpoint and return the response body as a Blob.
 * Throws (via _fetch) on non-2xx responses.
 * DOM anchor is NOT created here — that lives in download.js.
 *
 * @param {string} runLabel
 * @param {'csv'|'json'} format
 * @returns {Promise<Blob>}
 */
export async function fetchExportBlob(runLabel, format) {
  const resp = await _fetch(`/results/export?run=${encodeURIComponent(runLabel)}&format=${encodeURIComponent(format)}`);
  return resp.blob();
}
