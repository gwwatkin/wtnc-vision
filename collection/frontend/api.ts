/**
 * api.ts — Single fetch layer for both the results and capture pages.
 * All functions are pure async — no globals mutated, no DOM touched.
 * Paths are the existing wire contract (FROZEN-2, page-split spec); do not change them.
 *
 * @module api
 */

import type { ExportFormat, PostFrameResult } from './types';
import { getBackendUrl } from './backend-url';

/** Current back-end base URL (cookie override → config default → same-origin). */
const BASE = (): string => getBackendUrl();

// ── internal helper ──

/**
 * Fetch wrapper that throws on non-2xx responses.
 * Prepends BASE() so every caller automatically targets the configured back-end.
 */
async function _fetch(path: string, init?: RequestInit): Promise<Response> {
  const resp = await fetch(BASE() + path, init);
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const err = await resp.json() as { detail?: unknown };
      if (err && typeof err.detail === 'string') detail = err.detail;
      else if (err && err.detail) detail = String(err.detail);
    } catch (_) { /* non-JSON error body */ }
    throw new Error(detail);
  }
  return resp;
}

// ── reads ──

export async function fetchRuns(): Promise<string[]> {
  const resp = await _fetch('/runs', { cache: 'no-store' });
  const data = await resp.json() as { runs?: unknown };
  return Array.isArray(data.runs) ? data.runs as string[] : [];
}

export async function fetchResults(runLabel: string): Promise<unknown> {
  const resp = await _fetch(
    `/results?run=${encodeURIComponent(runLabel)}`,
    { cache: 'no-store' },
  );
  return resp.json();
}

export async function fetchCandidates(runLabel: string): Promise<unknown> {
  const resp = await _fetch(
    `/candidates?run=${encodeURIComponent(runLabel)}`,
    { cache: 'no-store' },
  );
  return resp.json();
}

export async function fetchStatus(runLabel: string): Promise<unknown> {
  const resp = await _fetch(
    `/status?run=${encodeURIComponent(runLabel)}`,
    { cache: 'no-store' },
  );
  return resp.json();
}

export async function fetchFrames(
  runLabel: string,
  opts: { anchorTs: string | null; spanS: number; limit: number },
): Promise<unknown> {
  const { anchorTs, spanS, limit } = opts;
  const params = new URLSearchParams({
    run:   runLabel,
    span:  String(spanS),
    limit: String(limit),
  });
  if (anchorTs) params.set('center', anchorTs);
  const resp = await _fetch(`/frames?${params}`);
  return resp.json();
}

export async function fetchRoster(
  runLabel: string,
): Promise<Array<{ number: string; name: string }>> {
  const resp = await _fetch(`/roster?run=${encodeURIComponent(runLabel)}`);
  const payload = await resp.json() as { riders?: unknown };
  return Array.isArray(payload.riders) ? payload.riders as Array<{ number: string; name: string }> : [];
}

// ── results-side mutations ──

export async function postEdit(
  runLabel: string,
  crossingId: string,
  fields: object,
): Promise<void> {
  await _fetch(`/crossings/${encodeURIComponent(crossingId)}`, {
    method:  'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(fields),
  });
}

export async function deleteEdit(runLabel: string, crossingId: string): Promise<void> {
  await _fetch(`/crossings/${encodeURIComponent(crossingId)}`, {
    method:  'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ deleted: true }),
  });
}

export async function postManualCrossing(runLabel: string, payload: object): Promise<void> {
  await _fetch('/crossings', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });
}

export async function reorderCrossing(
  runLabel: string,
  crossingId: string,
  neighbours: { earlierId: string | null; laterId: string | null },
): Promise<void> {
  const { earlierId, laterId } = neighbours;
  await _fetch(`/crossings/${encodeURIComponent(crossingId)}/position`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      earlier_id: earlierId ?? null,
      later_id:   laterId  ?? null,
    }),
  });
}

export async function promoteCandidate(
  runLabel: string,
  candidateId: string,
  payload: { action: string; number: string },
): Promise<void> {
  await _fetch(`/candidates/${encodeURIComponent(candidateId)}/resolve`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ action: 'promote', number: payload.number ?? '' }),
  });
}

export async function dismissCandidate(runLabel: string, candidateId: string): Promise<void> {
  await _fetch(`/candidates/${encodeURIComponent(candidateId)}/resolve`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ action: 'dismiss' }),
  });
}

// ── capture-side ──

export async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch(BASE() + '/health');
    return resp.ok;
  } catch (_) {
    return false;
  }
}

export async function postFrame(payload: {
  image: Blob;
  label: string;
  client_ts: string;
  seq: string | number;
  session_id?: string;
}): Promise<PostFrameResult> {
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
  return resp.json() as Promise<PostFrameResult>;
}

export async function uploadRoster(runLabel: string, file: File): Promise<void> {
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

export function frameUrl(runLabel: string, filename: string): string {
  return BASE() + `/frames/image?run=${encodeURIComponent(runLabel)}&filename=${encodeURIComponent(filename)}`;
}

export function exportUrl(runLabel: string, format: ExportFormat): string {
  return BASE() + `/results/export?run=${encodeURIComponent(runLabel)}&format=${encodeURIComponent(format)}`;
}

export async function fetchExportBlob(runLabel: string, format: ExportFormat): Promise<Blob> {
  const resp = await _fetch(`/results/export?run=${encodeURIComponent(runLabel)}&format=${encodeURIComponent(format)}`);
  return resp.blob();
}
