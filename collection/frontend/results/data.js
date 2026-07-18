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
 *  @property {string}   source       "auto" | "manual"
 *  @property {boolean}  edited       operator changed number/rider after creation
 *  @property {number}   orderKey     epoch-ms float — order-of-record sort key
 *  @property {boolean}  orderOverridden  operator moved this crossing
 *  @property {false}    isCandidate  always false for real crossings
 *  @property {string}   numberText   number string or "—" when empty
 */

/** @typedef {Object} CandidateResult  pseudo-Result from GET /candidates
 *  @property {true}     isCandidate
 *  @property {string}   candidateId
 *  @property {string}   run
 *  @property {Date}     time          first seen (its timeline position)
 *  @property {Date}     lastSeen
 *  @property {number}   frameCount
 *  @property {string|null} hintNumber
 *  @property {number}   hintConf
 *  @property {string}   imageUrl
 *  @property {number[]} repBox        [x1,y1,x2,y2]
 *  @property {number}   orderKey      epoch-ms of time
 *  @property {string}   numberText    hintNumber+"?" or "—"
 *  @property {string}   category      always UNKNOWN_CATEGORY (no lane data)
 */

/** @typedef {Object} Pack          crossings within gapSeconds of each other
 *  @property {Date}      startTime  newest crossing time in the pack (separator label)
 *  @property {Result[]}  results    descending by orderKey
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
 * Result gains: crossingId {string}, annotatedUrl {string},
 *   source, edited, orderKey, orderOverridden, isCandidate, numberText.
 * Skips entries with an unparseable time. Pure — no DOM, no fetch.
 *
 * @param {{ crossings: Array<{
 *   crossing_id: string,
 *   number: string,
 *   time: string,
 *   name: string|null,
 *   category: string|null,
 *   matched: boolean,
 *   annotated_url: string,
 *   source?: string,
 *   edited?: boolean,
 *   order_key?: number,
 *   order_overridden?: boolean,
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

    // order_key: if back-end doesn't send it (old payload), derive from time.
    const orderKey = (c.order_key != null && c.order_key !== 0)
      ? Number(c.order_key)
      : time.getTime();

    const numberStr = c.number ?? "";

    out.push({
      time,
      raceNumber: isNaN(raceNumber) ? 0 : raceNumber,
      name: c.name ?? null,
      category: c.category ?? UNKNOWN_CATEGORY,
      matched: Boolean(c.matched),
      crossingId: String(c.crossing_id),
      annotatedUrl: String(c.annotated_url),
      source: c.source ?? "auto",
      edited: Boolean(c.edited),
      orderKey,
      orderOverridden: Boolean(c.order_overridden),
      isCandidate: false,
      numberText: numberStr === "" ? "—" : numberStr,
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Candidate pseudo-results — new
// ---------------------------------------------------------------------------

/**
 * Convert a GET /candidates payload into CandidateResult pseudo-Results.
 * Only "open" candidates are included — others are silently skipped.
 * Skips entries with an unparseable time. Pure — no DOM, no fetch.
 *
 * @param {{ candidates: Array<{
 *   candidate_id: string,
 *   run: string,
 *   time: string,
 *   last_seen: string,
 *   frame_count: number,
 *   hint_number: string|null,
 *   hint_conf: number,
 *   rep_filename: string,
 *   rep_box: number[],
 *   state: string,
 *   image_url: string,
 * }> }} payload   raw JSON body from GET /candidates
 * @returns {CandidateResult[]}
 */
export function candidatesToResults(payload) {
  const out = [];
  const candidates = (payload && Array.isArray(payload.candidates))
    ? payload.candidates
    : [];

  for (const c of candidates) {
    if (c.state !== "open") continue;             // only open candidates

    const time = new Date(c.time);
    if (isNaN(time.getTime())) continue;          // same tolerance as resultsFromCrossings

    const lastSeen = new Date(c.last_seen);
    // lastSeen parse failure is tolerated — fall back to time.
    const lastSeenDate = isNaN(lastSeen.getTime()) ? time : lastSeen;

    const orderKey = time.getTime();
    const hintNumber = c.hint_number ?? null;

    out.push({
      isCandidate: true,
      candidateId: String(c.candidate_id),
      run: String(c.run),
      time,
      lastSeen: lastSeenDate,
      frameCount: Number(c.frame_count) || 0,
      hintNumber,
      hintConf: Number(c.hint_conf) || 0,
      imageUrl: String(c.image_url ?? ""),
      repBox: Array.isArray(c.rep_box) ? c.rep_box : [],
      orderKey,
      numberText: hintNumber ? hintNumber + "?" : "—",
      // Candidates have no lane — place them in UNKNOWN_CATEGORY so computeLanes/
      // groupIntoPacks see a valid category field without special-casing.
      category: UNKNOWN_CATEGORY,
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Sorting — extended
// ---------------------------------------------------------------------------

/**
 * Stable sort, newest first (legacy export — other code may import this).
 * @param {Result[]} results
 * @returns {Result[]}
 */
export function sortDescending(results) {
  // Array.prototype.sort is stable in all modern engines (ECMAScript 2019+).
  return [...results].sort((a, b) => b.time - a.time);
}

/**
 * Sort DESC by orderKey, tie → time DESC.
 * Drop-in replacement for sortDescending in the pipeline once order-of-record
 * is active. sortDescending remains exported for backward compat.
 *
 * @param {Array<Result|CandidateResult>} results
 * @returns {Array<Result|CandidateResult>}
 */
export function sortByOrder(results) {
  return [...results].sort((a, b) => {
    const keyDiff = b.orderKey - a.orderKey;
    if (keyDiff !== 0) return keyDiff;
    return b.time - a.time;                       // tie-break: newer time first
  });
}

// ---------------------------------------------------------------------------
// Merge helpers — new
// ---------------------------------------------------------------------------

/**
 * Concatenate crossing results and candidate pseudo-results into one array.
 * Does NOT sort — caller must call sortByOrder afterwards.
 *
 * @param {Result[]}          results
 * @param {CandidateResult[]} candidateResults
 * @returns {Array<Result|CandidateResult>}
 */
export function mergeCandidates(results, candidateResults) {
  return results.concat(candidateResults);
}

// ---------------------------------------------------------------------------
// Pack / lane grouping — unchanged; verified to tolerate pseudo-results
// ---------------------------------------------------------------------------

/**
 * Descending results → packs.  New pack whenever the gap to the previous
 * (newer) crossing exceeds gapSeconds.  Each pack's startTime = its newest
 * result's time.
 *
 * Pseudo-results (candidates) have a `time` property set to their first-seen
 * Date — the same field used for gap computation — so they integrate correctly
 * without any special-casing. Candidates have no `raceNumber`; no field
 * access here assumes a crossing — only `time` is read.
 *
 * @param {Array<Result|CandidateResult>} results  assumed descending (newest first)
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
 *
 * Candidate pseudo-results carry category=UNKNOWN_CATEGORY so they slot into
 * the unknown lane with no special-casing here. Lane-based placement in
 * render.js falls back to the last column when the category is unknown, which
 * is the correct visual treatment for candidates (D4).
 *
 * @param {Array<Result|CandidateResult>} results
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

// ---------------------------------------------------------------------------
// Inline self-checks (run with: node collection/frontend/results/data.js)
// Convention: assertions that throw on failure; silent on success.
// ---------------------------------------------------------------------------

function _assert(condition, msg) {
  if (!condition) throw new Error("self-check failed: " + msg);
}

function _runSelfChecks() {
  // ── sortByOrder ────────────────────────────────────────────────────────────
  {
    const t1 = new Date("2024-01-01T10:00:00Z");
    const t2 = new Date("2024-01-01T09:00:00Z");
    const t3 = new Date("2024-01-01T08:00:00Z");
    const r1 = { time: t1, orderKey: t1.getTime(), category: UNKNOWN_CATEGORY };
    const r2 = { time: t2, orderKey: t2.getTime(), category: UNKNOWN_CATEGORY };
    const r3 = { time: t3, orderKey: t3.getTime(), category: UNKNOWN_CATEGORY };
    // Input out of order; sortByOrder should give [r1, r2, r3] (DESC).
    const sorted = sortByOrder([r3, r1, r2]);
    _assert(sorted[0] === r1, "sortByOrder: newest first");
    _assert(sorted[1] === r2, "sortByOrder: middle");
    _assert(sorted[2] === r3, "sortByOrder: oldest last");

    // Tie-break: same orderKey, different time — newer time should come first.
    const sharedKey = 1_000_000;
    const ra = { time: t1, orderKey: sharedKey, category: UNKNOWN_CATEGORY };
    const rb = { time: t2, orderKey: sharedKey, category: UNKNOWN_CATEGORY };
    const tieSorted = sortByOrder([rb, ra]);
    _assert(tieSorted[0] === ra, "sortByOrder tie-break: newer time first");
    _assert(tieSorted[1] === rb, "sortByOrder tie-break: older time second");
  }

  // ── candidatesToResults filtering & mapping ────────────────────────────────
  {
    const now = "2024-01-01T10:00:00Z";
    const payload = {
      candidates: [
        {
          candidate_id: "run1-cand-1000",
          run: "run1",
          time: now,
          last_seen: "2024-01-01T10:00:05Z",
          frame_count: 3,
          hint_number: "128",
          hint_conf: 0.72,
          rep_filename: "run1/collected/frame001.jpg",
          rep_box: [10, 20, 100, 200],
          state: "open",
          image_url: "/candidates/run1-cand-1000/image",
        },
        {
          // promoted — should be filtered out
          candidate_id: "run1-cand-2000",
          run: "run1",
          time: now,
          last_seen: now,
          frame_count: 1,
          hint_number: null,
          hint_conf: 0,
          rep_filename: "run1/collected/frame002.jpg",
          rep_box: [],
          state: "promoted",
          image_url: "/candidates/run1-cand-2000/image",
        },
        {
          // invalid time — should be filtered out
          candidate_id: "run1-cand-3000",
          run: "run1",
          time: "not-a-date",
          last_seen: now,
          frame_count: 1,
          hint_number: null,
          hint_conf: 0,
          rep_filename: "run1/collected/frame003.jpg",
          rep_box: [],
          state: "open",
          image_url: "/candidates/run1-cand-3000/image",
        },
      ],
    };

    const results = candidatesToResults(payload);
    _assert(results.length === 1, "candidatesToResults: only open+valid");
    const r = results[0];
    _assert(r.isCandidate === true, "candidatesToResults: isCandidate");
    _assert(r.candidateId === "run1-cand-1000", "candidatesToResults: candidateId");
    _assert(r.hintNumber === "128", "candidatesToResults: hintNumber");
    _assert(r.numberText === "128?", "candidatesToResults: numberText with hint");
    _assert(r.orderKey === new Date(now).getTime(), "candidatesToResults: orderKey");
    _assert(r.repBox.length === 4, "candidatesToResults: repBox");
    _assert(r.category === UNKNOWN_CATEGORY, "candidatesToResults: category");
  }

  // ── numberText cases ───────────────────────────────────────────────────────
  {
    const payload = {
      crossings: [
        {
          crossing_id: "c1",
          number: "42",
          time: "2024-01-01T10:00:00Z",
          name: "Alice",
          category: "Cat 1",
          matched: true,
          annotated_url: "/annotated/c1.jpg",
        },
        {
          crossing_id: "c2",
          number: "",
          time: "2024-01-01T10:01:00Z",
          name: null,
          category: null,
          matched: false,
          annotated_url: "/annotated/c2.jpg",
        },
      ],
    };
    const results = resultsFromCrossings(payload);
    _assert(results.length === 2, "numberText: two results");
    const r42 = results.find((r) => r.crossingId === "c1");
    const rEmpty = results.find((r) => r.crossingId === "c2");
    _assert(r42.numberText === "42", "numberText: non-empty number");
    _assert(rEmpty.numberText === "—", "numberText: empty number → dash");

    // candidate with no hint
    const noHintPayload = {
      candidates: [
        {
          candidate_id: "x1",
          run: "r1",
          time: "2024-01-01T10:00:00Z",
          last_seen: "2024-01-01T10:00:00Z",
          frame_count: 1,
          hint_number: null,
          hint_conf: 0,
          rep_filename: "",
          rep_box: [],
          state: "open",
          image_url: "",
        },
      ],
    };
    const cResults = candidatesToResults(noHintPayload);
    _assert(cResults[0].numberText === "—", "numberText: candidate no hint → dash");
  }
}

// Run self-checks only when executed directly (node data.js), not on browser import.
// In the browser `process` is not defined; the check is safely skipped.
if (typeof process !== "undefined" && process.argv && process.argv[1] &&
    process.argv[1].endsWith("data.js")) {
  _runSelfChecks();
  // eslint-disable-next-line no-console
  console.log("data.js self-checks passed.");
}
