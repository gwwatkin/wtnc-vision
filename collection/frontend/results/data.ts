/**
 * data.ts — Pure data transforms for the live results feed.
 * Converted from results/data.js + results/data.d.ts (task2, jsdoc-to-ts spec).
 * Type changes only; runtime output is identical (NFR6/SC3).
 *
 * @module results/data
 */

import type { Result, CandidateResult, Pack, Lane } from '../types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const UNKNOWN_CATEGORY = 'Unknown' as const;

// ---------------------------------------------------------------------------
// Internal payload shapes (loose-boundary types for raw API JSON)
// ---------------------------------------------------------------------------

interface RawCrossing {
  crossing_id: unknown;
  number: unknown;
  time: unknown;
  name?: unknown;
  category?: unknown;
  matched?: unknown;
  annotated_url: unknown;
  source?: unknown;
  edited?: unknown;
  order_key?: unknown;
  order_overridden?: unknown;
}

interface RawCandidate {
  candidate_id: unknown;
  run: unknown;
  time: unknown;
  last_seen: unknown;
  frame_count: unknown;
  hint_number?: unknown;
  hint_conf: unknown;
  rep_filename?: unknown;
  rep_box?: unknown;
  state: unknown;
  image_url?: unknown;
}

// ---------------------------------------------------------------------------
// New transform — the one addition over web/data.js
// ---------------------------------------------------------------------------

/**
 * Convert a GET /results payload into Result[].
 * Skips entries with an unparseable time. Pure — no DOM, no fetch.
 */
export function resultsFromCrossings(payload: unknown): Result[] {
  const out: Result[] = [];
  const p = payload as { crossings?: unknown } | null | undefined;
  const crossings: RawCrossing[] = (p && Array.isArray(p.crossings))
    ? (p.crossings as RawCrossing[])
    : [];

  for (const c of crossings) {
    const time = new Date(c.time as string);
    if (isNaN(time.getTime())) continue;          // skip unparseable timestamps

    const raceNumber = Number(c.number);

    // order_key: if back-end doesn't send it (old payload), derive from time.
    const rawOrderKey = c.order_key;
    const orderKey = (rawOrderKey != null && Number(rawOrderKey) !== 0)
      ? Number(rawOrderKey)
      : time.getTime();

    const numberStr = (c.number != null ? String(c.number) : '');

    const result: Result = {
      time,
      raceNumber: isNaN(raceNumber) ? 0 : raceNumber,
      name: c.name != null ? String(c.name) : null,
      category: c.category != null ? String(c.category) : UNKNOWN_CATEGORY,
      matched: Boolean(c.matched),
      crossingId: String(c.crossing_id),
      annotatedUrl: String(c.annotated_url),
      source: (c.source === 'manual') ? 'manual' : 'auto',
      edited: Boolean(c.edited),
      orderKey,
      orderOverridden: Boolean(c.order_overridden),
      isCandidate: false,
      numberText: numberStr === '' ? '—' : numberStr,
    };
    out.push(result);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Candidate pseudo-results
// ---------------------------------------------------------------------------

/**
 * Convert a GET /candidates payload into CandidateResult pseudo-Results.
 * Only "open" candidates are included — others are silently skipped.
 * Skips entries with an unparseable time. Pure — no DOM, no fetch.
 */
export function candidatesToResults(payload: unknown): CandidateResult[] {
  const out: CandidateResult[] = [];
  const p = payload as { candidates?: unknown } | null | undefined;
  const candidates: RawCandidate[] = (p && Array.isArray(p.candidates))
    ? (p.candidates as RawCandidate[])
    : [];

  for (const c of candidates) {
    if (c.state !== 'open') continue;             // only open candidates

    const time = new Date(c.time as string);
    if (isNaN(time.getTime())) continue;          // same tolerance as resultsFromCrossings

    const lastSeen = new Date(c.last_seen as string);
    // lastSeen parse failure is tolerated — fall back to time.
    const lastSeenDate = isNaN(lastSeen.getTime()) ? time : lastSeen;

    const orderKey = time.getTime();
    const hintNumber = (c.hint_number != null ? String(c.hint_number) : null);

    // repBox: cast to the 4-tuple — the API contract guarantees [x1,y1,x2,y2].
    // Defensive fallback to empty array for malformed input (matching JS source behavior);
    // cast satisfies the tuple type while preserving runtime output (NFR6/SC3).
    const rawBox = c.rep_box;
    const repBox = (Array.isArray(rawBox)
      ? (rawBox as number[]).map(Number)
      : []) as [number, number, number, number];

    const candidate: CandidateResult = {
      isCandidate: true,
      candidateId: String(c.candidate_id),
      run: String(c.run),
      time,
      lastSeen: lastSeenDate,
      frameCount: Number(c.frame_count) || 0,
      hintNumber,
      hintConf: Number(c.hint_conf) || 0,
      imageUrl: String(c.image_url ?? ''),
      repBox,
      orderKey,
      numberText: hintNumber ? hintNumber + '?' : '—',
      // Candidates have no lane — place them in UNKNOWN_CATEGORY so computeLanes/
      // groupIntoPacks see a valid category field without special-casing.
      category: UNKNOWN_CATEGORY,
    };
    out.push(candidate);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Sorting — extended
// ---------------------------------------------------------------------------

/**
 * Stable sort, newest first (legacy export — other code may import this).
 */
export function sortDescending(results: Array<Result | CandidateResult>): Array<Result | CandidateResult> {
  // Array.prototype.sort is stable in all modern engines (ECMAScript 2019+).
  return [...results].sort((a, b) => b.time.getTime() - a.time.getTime());
}

/**
 * Sort DESC by orderKey, tie → time DESC.
 * Drop-in replacement for sortDescending in the pipeline once order-of-record
 * is active. sortDescending remains exported for backward compat.
 */
export function sortByOrder(results: Array<Result | CandidateResult>): Array<Result | CandidateResult> {
  return [...results].sort((a, b) => {
    const keyDiff = b.orderKey - a.orderKey;
    if (keyDiff !== 0) return keyDiff;
    return b.time.getTime() - a.time.getTime();   // tie-break: newer time first
  });
}

// ---------------------------------------------------------------------------
// Merge helpers
// ---------------------------------------------------------------------------

/**
 * Concatenate crossing results and candidate pseudo-results into one array.
 * Does NOT sort — caller must call sortByOrder afterwards.
 */
export function mergeCandidates(
  results: Result[],
  candidateResults: CandidateResult[],
): Array<Result | CandidateResult> {
  return (results as Array<Result | CandidateResult>).concat(candidateResults);
}

// ---------------------------------------------------------------------------
// Pack / lane grouping
// ---------------------------------------------------------------------------

/**
 * Descending results → packs.  New pack whenever the gap to the previous
 * (newer) crossing exceeds gapSeconds.  Each pack's startTime = its newest
 * result's time.
 */
export function groupIntoPacks(
  results: Array<Result | CandidateResult>,
  gapSeconds: number,
): Pack[] {
  if (results.length === 0) return [];
  const packs: Pack[] = [];
  let currentPack: Pack = { startTime: results[0].time, results: [results[0]] };
  for (let i = 1; i < results.length; i++) {
    const prev = results[i - 1];
    const curr = results[i];
    // prev is newer; gap = prev.time − curr.time (both in ms)
    const gapMs = prev.time.getTime() - curr.time.getTime();
    if (gapMs > gapSeconds * 1000) {
      packs.push(currentPack);
      currentPack = { startTime: curr.time, results: [curr] };
    } else {
      currentPack.results.push(curr);
    }
  }
  packs.push(currentPack);
  return packs;
}

/**
 * Distinct categories present → ordered lanes.
 * laneOrder (array|null) sets explicit order; unlisted categories follow in
 * deterministic alphabetical order; UNKNOWN always last.
 */
export function computeLanes(
  results: Array<Result | CandidateResult>,
  opts: { laneOrder?: string[] | null },
): Lane[] {
  const laneOrder = (opts && opts.laneOrder) || [];

  // Collect all distinct categories present.
  const seen = new Set<string>();
  for (const r of results) {
    seen.add(r.category);
  }

  // Build ordered list:
  //   1. laneOrder items that are actually present, in laneOrder sequence.
  //   2. Remaining categories alphabetically, excluding UNKNOWN_CATEGORY.
  //   3. UNKNOWN_CATEGORY last, if present.
  const ordered: string[] = [];
  const placed = new Set<string>();

  for (const cat of laneOrder) {
    if (seen.has(cat) && cat !== UNKNOWN_CATEGORY && !placed.has(cat)) {
      ordered.push(cat);
      placed.add(cat);
    }
  }

  // Deterministic, locale-independent alphabetical (UTF-16 code-unit) sort so
  // lane columns don't depend on crossing arrival/sort order.
  const remaining: string[] = [];
  for (const cat of seen) {
    if (!placed.has(cat) && cat !== UNKNOWN_CATEGORY) {
      remaining.push(cat);
    }
  }
  remaining.sort();
  for (const cat of remaining) {
    ordered.push(cat);
    placed.add(cat);
  }

  if (seen.has(UNKNOWN_CATEGORY)) {
    ordered.push(UNKNOWN_CATEGORY);
  }

  return ordered.map((category, index) => ({ category, index }));
}
