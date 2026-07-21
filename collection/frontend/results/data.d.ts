/**
 * data.d.ts — Type declarations for the legacy pure-transform module `data.js`.
 *
 * `data.js` is FROZEN / UNCHANGED (design §3): it predates this spec and is not
 * strict-`tsc`-clean (Date arithmetic, widened boolean literals, etc.). Because
 * `moduleResolution: bundler` pulls any transitively-imported `.js` into the
 * type program, importing `data.js` directly would surface those legacy errors
 * in every consumer (state.js, tests). This colocated `.d.ts` gives `tsc` the
 * module's types without checking the `.js` body — data.js stays byte-for-byte
 * unchanged while consumers get the precise, frozen return types.
 *
 * Return types are pinned to the frozen shapes in types.d.ts (FROZEN-1).
 * Payload params are intentionally loose (`any`) so the pre-port regression
 * suite (task2) can exercise malformed / edge-case inputs without type friction.
 */

import type { Result, CandidateResult, Pack, Lane } from "../types";

export const UNKNOWN_CATEGORY: "Unknown";

export function resultsFromCrossings(payload: any): Result[];
export function candidatesToResults(payload: any): CandidateResult[];
export function sortDescending(results: Result[]): Result[];
export function sortByOrder(
  results: Array<Result | CandidateResult>,
): Array<Result | CandidateResult>;
export function mergeCandidates(
  results: Result[],
  candidateResults: CandidateResult[],
): Array<Result | CandidateResult>;
export function groupIntoPacks(
  results: Array<Result | CandidateResult>,
  gapSeconds: number,
): Pack[];
export function computeLanes(
  results: Array<Result | CandidateResult>,
  opts: { laneOrder?: string[] | null },
): Lane[];
