/**
 * data.js — Typedefs + pure data transforms.
 * Owned exclusively by task3 for implementation; stubs created in task1.
 * No DOM, no fetch — pure functions only.
 */

// ---------------------------------------------------------------------------
// Typedefs (frozen — siblings import and depend on these)
// ---------------------------------------------------------------------------

/** @typedef {Object} Crossing
 *  @property {Date}    time         parsed from ISO-8601 w/ offset
 *  @property {number}  raceNumber
 */

/** @typedef {Object} RosterEntry
 *  @property {number}  raceNumber
 *  @property {string}  name
 *  @property {string}  category     e.g. "Cat 3"
 */

/** @typedef {Object} Result        merged, display-ready crossing
 *  @property {Date}     time
 *  @property {number}   raceNumber
 *  @property {?string}  name         null when unmatched
 *  @property {string}   category     roster category, or UNKNOWN_CATEGORY
 *  @property {boolean}  matched      false ⇒ no roster row
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
// Transforms
// ---------------------------------------------------------------------------

/** rows → Crossing[]. Skips rows with unparseable time or non-numeric number (NFR4).
 *  @param {string[][]} rows
 *  @returns {Crossing[]}
 */
export function parseCrossings(rows) {
  const out = [];
  for (const row of rows) {
    if (row.length < 2) continue;
    const time = new Date(row[0]);
    if (isNaN(time.getTime())) continue;
    const raceNumber = Number(row[1]);
    if (isNaN(raceNumber)) continue;
    out.push({ time, raceNumber });
  }
  return out;
}

/** rows → Map<raceNumber, RosterEntry>. Later duplicates win; bad rows skipped.
 *  @param {string[][]} rows
 *  @returns {Map<number, RosterEntry>}
 */
export function parseRoster(rows) {
  const map = new Map();
  for (const row of rows) {
    if (row.length < 3) continue;
    const raceNumber = Number(row[0]);
    if (isNaN(raceNumber)) continue;
    const name = row[1].trim();
    const category = row[2].trim();
    map.set(raceNumber, { raceNumber, name, category });
  }
  return map;
}

/** Join crossings to roster. Unmatched ⇒ name:null, matched:false, category:UNKNOWN.
 *  @param {Crossing[]} crossings
 *  @param {Map<number, RosterEntry>} roster
 *  @returns {Result[]}
 */
export function mergeResults(crossings, roster) {
  return crossings.map((crossing) => {
    const entry = roster.get(crossing.raceNumber);
    if (entry) {
      return {
        time: crossing.time,
        raceNumber: crossing.raceNumber,
        name: entry.name,
        category: entry.category,
        matched: true,
      };
    }
    return {
      time: crossing.time,
      raceNumber: crossing.raceNumber,
      name: null,
      category: UNKNOWN_CATEGORY,
      matched: false,
    };
  });
}

/** Stable sort, newest first.
 *  @param {Result[]} results
 *  @returns {Result[]}
 */
export function sortDescending(results) {
  // Array.prototype.sort is stable in all modern engines (ECMAScript 2019+).
  return [...results].sort((a, b) => b.time - a.time);
}

/** Descending results → packs. New pack whenever the gap to the previous (newer)
 *  crossing exceeds gapSeconds. Each pack's startTime = its newest result's time.
 *  @param {Result[]} results  assumed descending (newest first)
 *  @param {number} gapSeconds
 *  @returns {Pack[]}
 */
export function groupIntoPacks(results, gapSeconds) {
  if (results.length === 0) return [];
  const packs = [];
  let currentPack = { startTime: results[0].time, results: [results[0]] };
  for (let i = 1; i < results.length; i++) {
    const prev = results[i - 1];
    const curr = results[i];
    // prev is newer; gap = prev.time - curr.time (both in ms)
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

/** Distinct categories present → ordered lanes. laneOrder (array|null) sets explicit
 *  order; unlisted categories follow in first-appearance order; UNKNOWN always last.
 *  @param {Result[]} results
 *  @param {{laneOrder?: string[]}} opts
 *  @returns {Lane[]}
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
