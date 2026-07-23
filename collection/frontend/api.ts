/**
 * api.ts — Single fetch layer for both the results and capture pages.
 * STUB: task7 fills the real implementation.
 *
 * @module api
 */

import type { ExportFormat } from './types';

export async function fetchRuns(): Promise<string[]> {
  throw new Error('stub: fetchRuns');
}

export async function fetchResults(runLabel: string): Promise<unknown> {
  throw new Error('stub: fetchResults');
}

export async function fetchCandidates(runLabel: string): Promise<unknown> {
  throw new Error('stub: fetchCandidates');
}

export async function fetchStatus(runLabel: string): Promise<unknown> {
  throw new Error('stub: fetchStatus');
}

export async function fetchFrames(
  runLabel: string,
  opts: { anchorTs: string | null; spanS: number; limit: number },
): Promise<unknown> {
  throw new Error('stub: fetchFrames');
}

export async function fetchRoster(
  runLabel: string,
): Promise<Array<{ number: string; name: string }>> {
  throw new Error('stub: fetchRoster');
}

export async function postEdit(
  runLabel: string,
  crossingId: string,
  fields: object,
): Promise<void> {
  throw new Error('stub: postEdit');
}

export async function deleteEdit(runLabel: string, crossingId: string): Promise<void> {
  throw new Error('stub: deleteEdit');
}

export async function postManualCrossing(runLabel: string, payload: object): Promise<void> {
  throw new Error('stub: postManualCrossing');
}

export async function reorderCrossing(
  runLabel: string,
  crossingId: string,
  neighbours: { earlierId: string | null; laterId: string | null },
): Promise<void> {
  throw new Error('stub: reorderCrossing');
}

export async function promoteCandidate(
  runLabel: string,
  candidateId: string,
  payload: { action: string; number: string },
): Promise<void> {
  throw new Error('stub: promoteCandidate');
}

export async function dismissCandidate(runLabel: string, candidateId: string): Promise<void> {
  throw new Error('stub: dismissCandidate');
}

export async function checkHealth(): Promise<boolean> {
  throw new Error('stub: checkHealth');
}

export async function postFrame(payload: {
  image: Blob;
  label: string;
  client_ts: string;
  seq: string | number;
  session_id?: string;
}): Promise<unknown> {
  throw new Error('stub: postFrame');
}

export async function uploadRoster(runLabel: string, file: File): Promise<void> {
  throw new Error('stub: uploadRoster');
}

export function frameUrl(runLabel: string, filename: string): string {
  throw new Error('stub: frameUrl');
}

export function exportUrl(runLabel: string, format: ExportFormat): string {
  throw new Error('stub: exportUrl');
}

export async function fetchExportBlob(runLabel: string, format: ExportFormat): Promise<Blob> {
  throw new Error('stub: fetchExportBlob');
}
