/**
 * data.ts — Data transform functions for results pipeline.
 * STUB: task2 fills the real implementation (de-quarantine of data.js).
 *
 * @module results/data
 */

import type { Result, CandidateResult, Pack, Lane } from '../types';

export const UNKNOWN_CATEGORY = 'Unknown';

export function resultsFromCrossings(crossings: unknown[]): Result[] {
  throw new Error('stub: resultsFromCrossings');
}

export function candidatesToResults(candidates: unknown[]): CandidateResult[] {
  throw new Error('stub: candidatesToResults');
}

export function sortByOrder(items: Array<Result | CandidateResult>): Array<Result | CandidateResult> {
  throw new Error('stub: sortByOrder');
}

export function sortDescending(items: Array<Result | CandidateResult>): Array<Result | CandidateResult> {
  throw new Error('stub: sortDescending');
}

export function mergeCandidates(
  crossings: Result[],
  candidates: CandidateResult[],
): Array<Result | CandidateResult> {
  throw new Error('stub: mergeCandidates');
}

export function groupIntoPacks(
  items: Array<Result | CandidateResult>,
  gapSeconds: number,
): Pack[] {
  throw new Error('stub: groupIntoPacks');
}

export function computeLanes(
  items: Array<Result | CandidateResult>,
  opts: { laneOrder: string[] | null },
): Lane[] {
  throw new Error('stub: computeLanes');
}
