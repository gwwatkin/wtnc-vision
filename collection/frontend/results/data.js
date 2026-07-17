/**
 * data.js — Pure data transforms for the live results feed.
 * Adapted from web/data.js; server-enriched payload means no parseCrossings /
 * parseRoster / mergeResults — the back-end returns already-merged crossings.
 * No DOM, no fetch — pure functions only.
 *
 * @module results/data
 */

// ---------------------------------------------------------------------------
// Typedefs (frozen — render.js and results.js depend on these shapes)
// ---------------------------------------------------------------------------

/** @typedef {Object} Result        display-ready crossing from GET /results
 *  @property {Date}     time         parsed from the payload's ISO-8601 string
 *  @property {number}   raceNumber   numeric race number
 *  @property {?string}  name         roster name, or null when unmatched
 *  @property {string}   category     roster category, or UNKNOWN_CATEGORY
 *  @property {boolean}  matched      false ⇒ not in that run's roster
 *  @property {string}   crossingId   stable id — survives re-polls
 *  @property {string}   annotatedUrl relative URL for the sidebar image
 */

/** @typedef {Object} Pack          crossings within gapSeconds of each other
 *  @property {Date}      startTime  newest crossing time in the pack (separator label)
 *  @property {Result[]}  results    descending by time
 */

/** @typedef {Object} Lane
 *  @property {string}   category    "Cat 3" … or UNKNOWN_CATEGORY
 *  @property {number}   index       0-based column position
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const UNKNOWN_CATEGORY = "Unknown";

// ---------------------------------------------------------------------------
// New transform — the one addition over web/data.js
// ---------------------------------------------------------------------------

/**
 * Convert a GET /results payload into Result[].
 * Result gains: crossingId {string}, annotatedUrl {string}.
 * Skips entries with an unparseable time. Pure — no DOM, no fetch.
 *
 * @param {{ crossings: Array<{
 *   crossing_id: string,
 *   number: string,
 *   time: string,
 *   name: string|null,
 *   category: string|null,
 *   matched: boolean,
 *   annotated_url: string
 * }> }} payload   raw JSON body from GET /results
 * @returns {Result[]}
 */
export function resultsFromCrossings(payload) {
  const out = [];
  const crossings = (payload && Array.isArray(payload.crossings))
    ? payload.crossings
    : [];

  for (const c of crossings) {
    const time = new Date(c.time);
    if (isNaN(time.getTime())) continue;          // skip unparseable timestamps

    const raceNumber = Number(c.number);
    // Keep even when NaN (unknown number edge case) — use 0 as sentinel.
    // In practice the back-end always sends a numeric string, but be defensive.

    out.push({
      time,
      raceNumber: isNaN(raceNumber) ? 0 : raceNumber,
      name: c.name ?? null,
      category: c.category ?? UNKNOWN_CATEGORY,
      matched: Boolean(c.matched),
      crossingId: String(c.crossing_id),
      annotatedUrl: String(c.annotated_url),
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Reused from web/data.js verbatim
// ---------------------------------------------------------------------------

/**
 * Stable sort, newest first.
 * @param {Result[]} results
 * @returns {Result[]}
 */
export function sortDescending(results) {
  // Array.prototype.sort is stable in all modern engines (ECMAScript 2019+).
  return [...results].sort((a, b) => b.time - a.time);
}

/**
 * Descending results → packs.  New pack whenever the gap to the previous
 * (newer) crossing exceeds gapSeconds.  Each pack's startTime = its newest
 * result's time.
 * @param {Result[]} results  assumed descending (newest first)
 * @param {number}   gapSeconds
 * @returns {Pack[]}
 */
export function groupIntoPacks(results, gapSeconds) {
  if (results.length === 0) return [];
  const packs = [];
  let currentPack = { startTime: results[0].time, results: [results[0]] };
  for (let i = 1; i < results.length; i++) {
    const prev = results[i - 1];
    const curr = results[i];
    // prev is newer; gap = prev.time − curr.time (both in ms)
    const gapMs = prev.time - curr.time;
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
 * first-appearance order; UNKNOWN always last.
 * @param {Result[]} results
 * @param {{ laneOrder?: string[]|null }} opts
 * @returns {Lane[]}
 */
export function computeLanes(results, opts) {
  const laneOrder = (opts && opts.laneOrder) || [];

  // Collect all distinct categories in first-appearance order.
  const firstAppearance = [];
  const seen = new Set();
  for (const r of results) {
    if (!seen.has(r.category)) {
      seen.add(r.category);
      firstAppearance.push(r.category);
    }
  }

  // Build ordered list:
  //   1. laneOrder items that are actually present, in laneOrder sequence.
  //   2. Remaining categories in first-appearance order, excluding UNKNOWN_CATEGORY.
  //   3. UNKNOWN_CATEGORY last, if present.
  const ordered = [];
  const placed = new Set();

  for (const cat of laneOrder) {
    if (seen.has(cat) && cat !== UNKNOWN_CATEGORY && !placed.has(cat)) {
      ordered.push(cat);
      placed.add(cat);
    }
  }

  for (const cat of firstAppearance) {
    if (!placed.has(cat) && cat !== UNKNOWN_CATEGORY) {
      ordered.push(cat);
      placed.add(cat);
    }
  }

  if (seen.has(UNKNOWN_CATEGORY)) {
    ordered.push(UNKNOWN_CATEGORY);
  }

  return ordered.map((category, index) => ({ category, index }));
}
