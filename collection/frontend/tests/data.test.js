/**
 * data.test.js — Pure-logic regression tests for results/data.js.
 * Written PRE-PORT against today's implementation (D6/FR7/SC2).
 * Run with: node --test --import ./tests/setup-dom.js tests/data.test.js
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";

import {
  UNKNOWN_CATEGORY,
  resultsFromCrossings,
  candidatesToResults,
  sortDescending,
  sortByOrder,
  mergeCandidates,
  groupIntoPacks,
  computeLanes,
} from "../results/data.js";

// ---------------------------------------------------------------------------
// Helpers — minimal well-formed fixtures
// ---------------------------------------------------------------------------

/** Build a minimal crossing payload entry (snake_case, as the back-end sends).
 * @param {any} [overrides] @returns {any} */
function makeCrossing(overrides = {}) {
  return {
    crossing_id: "c1",
    number: "42",
    time: "2024-06-15T10:00:00.000Z",
    name: "Alice",
    category: "Cat 3",
    matched: true,
    annotated_url: "/annotated/c1.jpg",
    source: "auto",
    edited: false,
    order_key: 1718445600000,
    order_overridden: false,
    ...overrides,
  };
}

/** Build a minimal open-state candidate payload entry.
 * @param {any} [overrides] @returns {any} */
function makeCandidate(overrides = {}) {
  return {
    candidate_id: "run1-cand-1",
    run: "run1",
    time: "2024-06-15T10:00:00.000Z",
    last_seen: "2024-06-15T10:00:05.000Z",
    frame_count: 3,
    hint_number: "128",
    hint_conf: 0.72,
    rep_filename: "run1/frame001.jpg",
    rep_box: [10, 20, 100, 200],
    state: "open",
    image_url: "/candidates/run1-cand-1/image",
    ...overrides,
  };
}

/** Build a minimal Result (camelCase, as returned by resultsFromCrossings).
 * @param {any} [overrides] @returns {any} */
function makeResult(overrides = {}) {
  const time = overrides.time instanceof Date
    ? overrides.time
    : new Date("2024-06-15T10:00:00.000Z");
  return {
    time,
    raceNumber: 42,
    name: "Alice",
    category: "Cat 3",
    matched: true,
    crossingId: "c1",
    annotatedUrl: "/annotated/c1.jpg",
    source: "auto",
    edited: false,
    orderKey: time.getTime(),
    orderOverridden: false,
    isCandidate: false,
    numberText: "42",
    ...overrides,
  };
}

/** Build a minimal CandidateResult (camelCase, as returned by candidatesToResults).
 * @param {any} [overrides] @returns {any} */
function makeCandidateResult(overrides = {}) {
  const time = overrides.time instanceof Date
    ? overrides.time
    : new Date("2024-06-15T10:00:00.000Z");
  return {
    isCandidate: true,
    candidateId: "run1-cand-1",
    run: "run1",
    time,
    lastSeen: new Date("2024-06-15T10:00:05.000Z"),
    frameCount: 3,
    hintNumber: "128",
    hintConf: 0.72,
    imageUrl: "/candidates/run1-cand-1/image",
    repBox: [10, 20, 100, 200],
    orderKey: time.getTime(),
    numberText: "128?",
    category: UNKNOWN_CATEGORY,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// UNKNOWN_CATEGORY
// ---------------------------------------------------------------------------

describe("UNKNOWN_CATEGORY", () => {
  it('equals "Unknown"', () => {
    assert.equal(UNKNOWN_CATEGORY, "Unknown");
  });
});

// ---------------------------------------------------------------------------
// resultsFromCrossings
// ---------------------------------------------------------------------------

describe("resultsFromCrossings", () => {
  it("returns empty array for empty crossings", () => {
    assert.deepEqual(resultsFromCrossings({ crossings: [] }), []);
  });

  it("returns empty array when payload has no crossings property", () => {
    // defensive: payload without crossings key
    assert.deepEqual(resultsFromCrossings({}), []);
  });

  it("returns empty array for null/undefined payload", () => {
    assert.deepEqual(resultsFromCrossings(null), []);
    assert.deepEqual(resultsFromCrossings(undefined), []);
  });

  it("maps a full crossing to a Result with correct camelCase fields", () => {
    const now = "2024-06-15T10:00:00.000Z";
    const orderKeyMs = 1718445600999;
    const [r] = resultsFromCrossings({
      crossings: [
        makeCrossing({
          crossing_id: "cross-1",
          number: "7",
          time: now,
          name: "Bob",
          category: "Cat 1",
          matched: true,
          annotated_url: "/img/cross-1.jpg",
          source: "manual",
          edited: true,
          order_key: orderKeyMs,
          order_overridden: true,
        }),
      ],
    });

    assert.equal(r.time.toISOString(), new Date(now).toISOString());
    assert.equal(r.raceNumber, 7);
    assert.equal(r.name, "Bob");
    assert.equal(r.category, "Cat 1");
    assert.equal(r.matched, true);
    assert.equal(r.crossingId, "cross-1");
    assert.equal(r.annotatedUrl, "/img/cross-1.jpg");
    assert.equal(r.source, "manual");
    assert.equal(r.edited, true);
    assert.equal(r.orderKey, orderKeyMs);
    assert.equal(r.orderOverridden, true);
    assert.equal(r.isCandidate, false);
    assert.equal(r.numberText, "7");
  });

  it("skips entries with unparseable timestamps without throwing", () => {
    const results = resultsFromCrossings({
      crossings: [
        makeCrossing({ crossing_id: "bad", time: "not-a-date" }),
        makeCrossing({ crossing_id: "good", time: "2024-06-15T10:00:00.000Z" }),
      ],
    });
    assert.equal(results.length, 1);
    assert.equal(results[0].crossingId, "good");
  });

  it("defaults category to UNKNOWN_CATEGORY when category is null", () => {
    const [r] = resultsFromCrossings({
      crossings: [makeCrossing({ category: null })],
    });
    assert.equal(r.category, UNKNOWN_CATEGORY);
  });

  it("defaults source to 'auto' when source is absent", () => {
    const crossing = makeCrossing();
    delete crossing.source;
    const [r] = resultsFromCrossings({ crossings: [crossing] });
    assert.equal(r.source, "auto");
  });

  it("defaults edited to false when edited is absent", () => {
    const crossing = makeCrossing();
    delete crossing.edited;
    const [r] = resultsFromCrossings({ crossings: [crossing] });
    assert.equal(r.edited, false);
  });

  it("defaults order_overridden to false when absent", () => {
    const crossing = makeCrossing();
    delete crossing.order_overridden;
    const [r] = resultsFromCrossings({ crossings: [crossing] });
    assert.equal(r.orderOverridden, false);
  });

  it("defaults name to null when name is absent", () => {
    const crossing = makeCrossing();
    delete crossing.name;
    const [r] = resultsFromCrossings({ crossings: [crossing] });
    assert.equal(r.name, null);
  });

  it("produces '—' numberText when number is empty string", () => {
    const [r] = resultsFromCrossings({
      crossings: [makeCrossing({ number: "" })],
    });
    assert.equal(r.numberText, "—");
  });

  it("produces numberText equal to the number string when non-empty", () => {
    const [r] = resultsFromCrossings({
      crossings: [makeCrossing({ number: "99" })],
    });
    assert.equal(r.numberText, "99");
  });

  it("falls back orderKey to time.getTime() when order_key is absent", () => {
    const timeStr = "2024-06-15T10:00:00.000Z";
    const crossing = makeCrossing({ time: timeStr });
    delete crossing.order_key;
    const [r] = resultsFromCrossings({ crossings: [crossing] });
    assert.equal(r.orderKey, new Date(timeStr).getTime());
  });

  it("falls back orderKey to time.getTime() when order_key is 0", () => {
    const timeStr = "2024-06-15T10:00:00.000Z";
    const [r] = resultsFromCrossings({
      crossings: [makeCrossing({ time: timeStr, order_key: 0 })],
    });
    assert.equal(r.orderKey, new Date(timeStr).getTime());
  });

  it("uses order_key when it is non-zero", () => {
    const orderKey = 9_999_999_999_999;
    const [r] = resultsFromCrossings({
      crossings: [makeCrossing({ order_key: orderKey })],
    });
    assert.equal(r.orderKey, orderKey);
  });

  it("handles duplicate crossing_ids by returning both (no dedup)", () => {
    const results = resultsFromCrossings({
      crossings: [
        makeCrossing({ crossing_id: "dup", number: "1" }),
        makeCrossing({ crossing_id: "dup", number: "2" }),
      ],
    });
    assert.equal(results.length, 2);
    assert.equal(results[0].crossingId, "dup");
    assert.equal(results[1].crossingId, "dup");
  });

  it("sets isCandidate to false on every Result", () => {
    const results = resultsFromCrossings({
      crossings: [makeCrossing(), makeCrossing({ crossing_id: "c2", number: "2" })],
    });
    for (const r of results) {
      assert.equal(r.isCandidate, false);
    }
  });

  it("time property is a Date instance", () => {
    const [r] = resultsFromCrossings({
      crossings: [makeCrossing({ time: "2024-06-15T10:00:00.000Z" })],
    });
    assert.ok(r.time instanceof Date);
  });

  it("raceNumber is 0 when number string is not numeric", () => {
    const [r] = resultsFromCrossings({
      crossings: [makeCrossing({ number: "abc" })],
    });
    assert.equal(r.raceNumber, 0);
  });
});

// ---------------------------------------------------------------------------
// candidatesToResults
// ---------------------------------------------------------------------------

describe("candidatesToResults", () => {
  it("returns empty array for empty candidates", () => {
    assert.deepEqual(candidatesToResults({ candidates: [] }), []);
  });

  it("returns empty array when payload lacks candidates key", () => {
    assert.deepEqual(candidatesToResults({}), []);
  });

  it("returns empty array for null payload", () => {
    assert.deepEqual(candidatesToResults(null), []);
  });

  it("filters out non-open candidates", () => {
    const results = candidatesToResults({
      candidates: [
        makeCandidate({ candidate_id: "open1", state: "open" }),
        makeCandidate({ candidate_id: "promoted1", state: "promoted" }),
        makeCandidate({ candidate_id: "dismissed1", state: "dismissed" }),
      ],
    });
    assert.equal(results.length, 1);
    assert.equal(results[0].candidateId, "open1");
  });

  it("skips candidates with unparseable time without throwing", () => {
    const results = candidatesToResults({
      candidates: [
        makeCandidate({ candidate_id: "bad", time: "not-a-date" }),
        makeCandidate({ candidate_id: "good", time: "2024-06-15T10:00:00.000Z" }),
      ],
    });
    assert.equal(results.length, 1);
    assert.equal(results[0].candidateId, "good");
  });

  it("maps fields to camelCase CandidateResult correctly", () => {
    const timeStr = "2024-06-15T10:00:00.000Z";
    const lastSeenStr = "2024-06-15T10:00:05.000Z";
    const [r] = candidatesToResults({
      candidates: [
        makeCandidate({
          candidate_id: "cand-99",
          run: "run2",
          time: timeStr,
          last_seen: lastSeenStr,
          frame_count: 7,
          hint_number: "55",
          hint_conf: 0.9,
          rep_box: [1, 2, 3, 4],
          image_url: "/img/99.jpg",
        }),
      ],
    });

    assert.equal(r.isCandidate, true);
    assert.equal(r.candidateId, "cand-99");
    assert.equal(r.run, "run2");
    assert.equal(r.time.toISOString(), new Date(timeStr).toISOString());
    assert.equal(r.lastSeen.toISOString(), new Date(lastSeenStr).toISOString());
    assert.equal(r.frameCount, 7);
    assert.equal(r.hintNumber, "55");
    assert.equal(r.hintConf, 0.9);
    assert.deepEqual(r.repBox, [1, 2, 3, 4]);
    assert.equal(r.imageUrl, "/img/99.jpg");
    assert.equal(r.orderKey, new Date(timeStr).getTime());
    assert.equal(r.numberText, "55?");
    assert.equal(r.category, UNKNOWN_CATEGORY);
  });

  it("sets numberText to '—' when hint_number is null", () => {
    const [r] = candidatesToResults({
      candidates: [makeCandidate({ hint_number: null })],
    });
    assert.equal(r.hintNumber, null);
    assert.equal(r.numberText, "—");
  });

  it("appends '?' to hint_number in numberText when hint is present", () => {
    const [r] = candidatesToResults({
      candidates: [makeCandidate({ hint_number: "128" })],
    });
    assert.equal(r.numberText, "128?");
  });

  it("always sets category to UNKNOWN_CATEGORY", () => {
    const [r] = candidatesToResults({
      candidates: [makeCandidate()],
    });
    assert.equal(r.category, UNKNOWN_CATEGORY);
  });

  it("orderKey equals time.getTime()", () => {
    const timeStr = "2024-06-15T10:00:00.000Z";
    const [r] = candidatesToResults({
      candidates: [makeCandidate({ time: timeStr })],
    });
    assert.equal(r.orderKey, new Date(timeStr).getTime());
  });

  it("falls back lastSeen to time when last_seen is unparseable", () => {
    const timeStr = "2024-06-15T10:00:00.000Z";
    const [r] = candidatesToResults({
      candidates: [
        makeCandidate({ time: timeStr, last_seen: "bad-date" }),
      ],
    });
    assert.equal(r.lastSeen.toISOString(), new Date(timeStr).toISOString());
  });

  it("time property is a Date instance", () => {
    const [r] = candidatesToResults({
      candidates: [makeCandidate()],
    });
    assert.ok(r.time instanceof Date);
    assert.ok(r.lastSeen instanceof Date);
  });

  it("repBox defaults to empty array when rep_box is not an array", () => {
    const [r] = candidatesToResults({
      candidates: [makeCandidate({ rep_box: null })],
    });
    assert.deepEqual(r.repBox, []);
  });
});

// ---------------------------------------------------------------------------
// sortDescending
// ---------------------------------------------------------------------------

describe("sortDescending", () => {
  it("returns empty array for empty input", () => {
    assert.deepEqual(sortDescending([]), []);
  });

  it("sorts results newest-first by time", () => {
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date("2024-06-15T09:00:00.000Z");
    const t3 = new Date("2024-06-15T08:00:00.000Z");
    const r1 = makeResult({ time: t1, orderKey: t1.getTime() });
    const r2 = makeResult({ time: t2, orderKey: t2.getTime() });
    const r3 = makeResult({ time: t3, orderKey: t3.getTime() });

    const sorted = sortDescending([r3, r1, r2]);
    assert.equal(sorted[0], r1);
    assert.equal(sorted[1], r2);
    assert.equal(sorted[2], r3);
  });

  it("does not mutate the input array", () => {
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date("2024-06-15T09:00:00.000Z");
    const r1 = makeResult({ time: t1, orderKey: t1.getTime() });
    const r2 = makeResult({ time: t2, orderKey: t2.getTime() });
    const input = [r2, r1];
    sortDescending(input);
    assert.equal(input[0], r2, "original array must not be mutated");
    assert.equal(input[1], r1, "original array must not be mutated");
  });

  it("handles single element", () => {
    const r = makeResult({});
    assert.deepEqual(sortDescending([r]), [r]);
  });
});

// ---------------------------------------------------------------------------
// sortByOrder
// ---------------------------------------------------------------------------

describe("sortByOrder", () => {
  it("returns empty array for empty input", () => {
    assert.deepEqual(sortByOrder([]), []);
  });

  it("sorts results descending by orderKey", () => {
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date("2024-06-15T09:00:00.000Z");
    const t3 = new Date("2024-06-15T08:00:00.000Z");
    const r1 = makeResult({ time: t1, orderKey: 3000 });
    const r2 = makeResult({ time: t2, orderKey: 2000 });
    const r3 = makeResult({ time: t3, orderKey: 1000 });

    const sorted = sortByOrder([r3, r1, r2]);
    assert.equal(sorted[0], r1);
    assert.equal(sorted[1], r2);
    assert.equal(sorted[2], r3);
  });

  it("tie-breaks on time DESC when orderKey is equal", () => {
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date("2024-06-15T09:00:00.000Z");
    const sharedKey = 5000;
    const newer = makeResult({ time: t1, orderKey: sharedKey });
    const older = makeResult({ time: t2, orderKey: sharedKey });

    const sorted = sortByOrder([older, newer]);
    assert.equal(sorted[0], newer, "newer time first on tie");
    assert.equal(sorted[1], older);
  });

  it("does not mutate the input array", () => {
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date("2024-06-15T09:00:00.000Z");
    const r1 = makeResult({ time: t1, orderKey: 2000 });
    const r2 = makeResult({ time: t2, orderKey: 1000 });
    const input = [r2, r1];
    sortByOrder(input);
    assert.equal(input[0], r2, "original array must not be mutated");
  });

  it("works with mixed Result and CandidateResult", () => {
    const t1 = new Date("2024-06-15T10:05:00.000Z");
    const t2 = new Date("2024-06-15T10:00:00.000Z");
    const result = makeResult({ time: t2, orderKey: t2.getTime() });
    const candidate = makeCandidateResult({ time: t1, orderKey: t1.getTime() });

    const sorted = sortByOrder([result, candidate]);
    assert.equal(sorted[0], candidate, "candidate with newer orderKey comes first");
    assert.equal(sorted[1], result);
  });

  it("handles single element", () => {
    const r = makeResult({});
    assert.deepEqual(sortByOrder([r]), [r]);
  });
});

// ---------------------------------------------------------------------------
// mergeCandidates
// ---------------------------------------------------------------------------

describe("mergeCandidates", () => {
  it("returns empty array when both inputs are empty", () => {
    assert.deepEqual(mergeCandidates([], []), []);
  });

  it("concatenates results and candidateResults", () => {
    const r1 = makeResult({ crossingId: "c1" });
    const r2 = makeResult({ crossingId: "c2" });
    const c1 = makeCandidateResult({ candidateId: "cand-1" });

    const merged = mergeCandidates([r1, r2], [c1]);
    assert.equal(merged.length, 3);
    assert.equal(merged[0], r1);
    assert.equal(merged[1], r2);
    assert.equal(merged[2], c1);
  });

  it("does not sort the merged array (preserves insertion order)", () => {
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date("2024-06-15T09:00:00.000Z");
    const older = makeResult({ time: t2, orderKey: t2.getTime() });
    const newer = makeCandidateResult({ time: t1, orderKey: t1.getTime() });

    // older result first, newer candidate second — mergeCandidates must NOT sort
    const merged = mergeCandidates([older], [newer]);
    assert.equal(merged[0], older, "order must not be changed by mergeCandidates");
    assert.equal(merged[1], newer);
  });

  it("handles results-only (empty candidateResults)", () => {
    const r = makeResult({});
    const merged = mergeCandidates([r], []);
    assert.equal(merged.length, 1);
    assert.equal(merged[0], r);
  });

  it("handles candidates-only (empty results)", () => {
    const c = makeCandidateResult({});
    const merged = mergeCandidates([], [c]);
    assert.equal(merged.length, 1);
    assert.equal(merged[0], c);
  });

  it("candidates overlapping confident crossings are included without dedup", () => {
    // Simulates a candidate that was also confirmed — both appear, dedup is caller's job
    const t = new Date("2024-06-15T10:00:00.000Z");
    const result = makeResult({ time: t, orderKey: t.getTime() });
    const candidate = makeCandidateResult({ time: t, orderKey: t.getTime() });

    const merged = mergeCandidates([result], [candidate]);
    assert.equal(merged.length, 2, "both crossing and candidate appear");
  });
});

// ---------------------------------------------------------------------------
// groupIntoPacks
// ---------------------------------------------------------------------------

describe("groupIntoPacks", () => {
  it("returns empty array for empty input", () => {
    assert.deepEqual(groupIntoPacks([], 3), []);
  });

  it("wraps a single result in one pack", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const r = makeResult({ time: t, orderKey: t.getTime() });
    const packs = groupIntoPacks([r], 3);
    assert.equal(packs.length, 1);
    assert.equal(packs[0].results.length, 1);
    assert.equal(packs[0].results[0], r);
  });

  it("pack.startTime equals the newest result's time in the pack", () => {
    // groupIntoPacks receives already-sorted (descending) input
    const t1 = new Date("2024-06-15T10:00:00.000Z"); // newest
    const t2 = new Date("2024-06-15T09:59:58.000Z"); // 2 s later — within 3s gap
    const r1 = makeResult({ time: t1, orderKey: t1.getTime() });
    const r2 = makeResult({ time: t2, orderKey: t2.getTime() });

    const packs = groupIntoPacks([r1, r2], 3);
    assert.equal(packs.length, 1);
    assert.equal(packs[0].startTime, t1, "startTime must be the newest time in pack");
  });

  it("groups two crossings within gapSeconds into the same pack", () => {
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date("2024-06-15T09:59:58.000Z"); // 2 s gap — within 3 s
    const r1 = makeResult({ time: t1, orderKey: t1.getTime() });
    const r2 = makeResult({ time: t2, orderKey: t2.getTime() });

    const packs = groupIntoPacks([r1, r2], 3);
    assert.equal(packs.length, 1);
    assert.equal(packs[0].results.length, 2);
  });

  // SC7 — this test MUST FAIL if the pack-grouping window invariant broke
  it("SC7: splits two crossings more than gapSeconds apart into separate packs", () => {
    const gapSeconds = 3;
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    // t2 is gapSeconds + 1 ms beyond t1, which is strictly > gapSeconds
    const t2 = new Date(t1.getTime() - (gapSeconds * 1000 + 1));
    const r1 = makeResult({ time: t1, orderKey: t1.getTime() });
    const r2 = makeResult({ time: t2, orderKey: t2.getTime() });

    const packs = groupIntoPacks([r1, r2], gapSeconds);
    assert.equal(packs.length, 2,
      `crossings ${gapSeconds * 1000 + 1}ms apart must land in separate packs`);
    assert.equal(packs[0].results[0], r1);
    assert.equal(packs[1].results[0], r2);
  });

  it("two crossings exactly gapSeconds * 1000 ms apart stay in the same pack (boundary)", () => {
    // gap > gapSeconds*1000 triggers split; equal does NOT
    const gapSeconds = 3;
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date(t1.getTime() - gapSeconds * 1000); // exactly 3000 ms
    const r1 = makeResult({ time: t1, orderKey: t1.getTime() });
    const r2 = makeResult({ time: t2, orderKey: t2.getTime() });

    const packs = groupIntoPacks([r1, r2], gapSeconds);
    assert.equal(packs.length, 1,
      "crossings exactly gapSeconds apart must stay in the same pack");
  });

  it("creates multiple packs for three crossings spread across two gaps", () => {
    const gap = 3;
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date(t1.getTime() - 1000);        // 1s gap: same pack
    const t3 = new Date(t2.getTime() - (gap * 1000 + 500)); // 3.5s gap: new pack
    const r1 = makeResult({ time: t1, orderKey: t1.getTime() });
    const r2 = makeResult({ time: t2, orderKey: t2.getTime() });
    const r3 = makeResult({ time: t3, orderKey: t3.getTime() });

    const packs = groupIntoPacks([r1, r2, r3], gap);
    assert.equal(packs.length, 2);
    assert.equal(packs[0].results.length, 2);
    assert.equal(packs[1].results.length, 1);
    assert.equal(packs[1].results[0], r3);
  });

  it("each pack's startTime is the newest time in that pack", () => {
    const gap = 3;
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date(t1.getTime() - 1000);
    const t3 = new Date(t2.getTime() - (gap * 1000 + 500));
    const t4 = new Date(t3.getTime() - 1000);
    const r1 = makeResult({ time: t1, orderKey: t1.getTime() });
    const r2 = makeResult({ time: t2, orderKey: t2.getTime() });
    const r3 = makeResult({ time: t3, orderKey: t3.getTime() });
    const r4 = makeResult({ time: t4, orderKey: t4.getTime() });

    const packs = groupIntoPacks([r1, r2, r3, r4], gap);
    assert.equal(packs.length, 2);
    // Pack 0 contains r1 (newest) and r2; startTime must be t1
    assert.equal(packs[0].startTime, t1, "pack 0 startTime must be its newest time");
    // Pack 1 contains r3 (newest in pack) and r4; startTime must be t3
    assert.equal(packs[1].startTime, t3, "pack 1 startTime must be its newest time");
  });

  it("works with CandidateResult entries (uses .time field)", () => {
    const gap = 3;
    const t1 = new Date("2024-06-15T10:00:00.000Z");
    const t2 = new Date(t1.getTime() - (gap * 1000 + 1));
    const c1 = makeCandidateResult({ time: t1, orderKey: t1.getTime() });
    const c2 = makeCandidateResult({ time: t2, orderKey: t2.getTime() });

    const packs = groupIntoPacks([c1, c2], gap);
    assert.equal(packs.length, 2, "candidates follow the same gap logic as crossings");
  });
});

// ---------------------------------------------------------------------------
// computeLanes
// ---------------------------------------------------------------------------

describe("computeLanes", () => {
  it("returns empty array for empty input", () => {
    assert.deepEqual(computeLanes([], { laneOrder: null }), []);
  });

  it("returns empty array when opts is omitted", () => {
    assert.deepEqual(computeLanes([], {}), []);
  });

  it("assigns 0-based index in alphabetical order", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const r1 = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 1" });
    const r2 = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 3" });
    const r3 = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 1" }); // duplicate

    const lanes = computeLanes([r1, r2, r3], { laneOrder: null });
    assert.equal(lanes.length, 2);
    assert.equal(lanes[0].category, "Cat 1");
    assert.equal(lanes[0].index, 0);
    assert.equal(lanes[1].category, "Cat 3");
    assert.equal(lanes[1].index, 1);
  });

  it("orders lanes alphabetically regardless of arrival/sort order", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    // Categories arrive reverse-alphabetically — lanes must still come out A→Z,
    // so that reordering crossings (which changes their sort position) can never
    // shuffle the lane columns.
    const rC = makeResult({ time: t, orderKey: t.getTime(), category: "Charlie" });
    const rA = makeResult({ time: t, orderKey: t.getTime(), category: "Alpha" });
    const rB = makeResult({ time: t, orderKey: t.getTime(), category: "Bravo" });

    const lanes = computeLanes([rC, rA, rB], { laneOrder: null });
    assert.deepEqual(
      lanes.map((l) => l.category),
      ["Alpha", "Bravo", "Charlie"]
    );

    // Same categories, opposite arrival order → identical lane layout.
    const reordered = computeLanes([rA, rB, rC], { laneOrder: null });
    assert.deepEqual(reordered, lanes);
  });

  it("places UNKNOWN_CATEGORY last regardless of first-appearance", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    // UNKNOWN appears first, known categories appear after
    const u = makeResult({ time: t, orderKey: t.getTime(), category: UNKNOWN_CATEGORY });
    const r = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 1" });

    const lanes = computeLanes([u, r], { laneOrder: null });
    const unknownLane = lanes.find((l) => l.category === UNKNOWN_CATEGORY);
    const cat1Lane = lanes.find((l) => l.category === "Cat 1");

    assert.ok(unknownLane, "UNKNOWN_CATEGORY lane must exist");
    assert.ok(cat1Lane, "Cat 1 lane must exist");
    assert.ok(
      unknownLane.index > cat1Lane.index,
      "UNKNOWN_CATEGORY must have a higher index (last)"
    );
  });

  it("candidates (category = UNKNOWN_CATEGORY) land in the last lane", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const result = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 3" });
    const candidate = makeCandidateResult({ time: t, orderKey: t.getTime() });

    const lanes = computeLanes([result, candidate], { laneOrder: null });
    const lastLane = lanes[lanes.length - 1];
    assert.equal(lastLane.category, UNKNOWN_CATEGORY,
      "candidates in UNKNOWN_CATEGORY must be in the last lane");
  });

  it("respects laneOrder — listed categories come first in the given order", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const rA = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 3" });
    const rB = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 1" });
    const rC = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 5" });

    // laneOrder says Cat 1 before Cat 3; Cat 5 not listed
    const lanes = computeLanes([rA, rB, rC], { laneOrder: ["Cat 1", "Cat 3"] });
    assert.equal(lanes[0].category, "Cat 1");
    assert.equal(lanes[1].category, "Cat 3");
    assert.equal(lanes[2].category, "Cat 5");
  });

  it("laneOrder entries not present in results are silently ignored", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const r = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 3" });

    const lanes = computeLanes([r], { laneOrder: ["Cat 1", "Cat 3"] });
    // Cat 1 is not present in results — should not appear in lanes
    assert.equal(lanes.length, 1);
    assert.equal(lanes[0].category, "Cat 3");
    assert.equal(lanes[0].index, 0);
  });

  it("UNKNOWN_CATEGORY in laneOrder is excluded from the ordered prefix (still placed last)", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const r1 = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 3" });
    const r2 = makeResult({ time: t, orderKey: t.getTime(), category: UNKNOWN_CATEGORY });

    // Even though UNKNOWN is in laneOrder, it should still end up last
    const lanes = computeLanes([r1, r2], { laneOrder: [UNKNOWN_CATEGORY, "Cat 3"] });
    const lastLane = lanes[lanes.length - 1];
    assert.equal(lastLane.category, UNKNOWN_CATEGORY,
      "UNKNOWN_CATEGORY must always be last even when listed in laneOrder");
  });

  it("index is 0-based and sequential", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const categories = ["Cat 1", "Cat 2", "Cat 3"];
    const results = categories.map((cat) =>
      makeResult({ time: t, orderKey: t.getTime(), category: cat })
    );

    const lanes = computeLanes(results, { laneOrder: null });
    lanes.forEach((lane, i) => {
      assert.equal(lane.index, i, `lane at position ${i} must have index ${i}`);
    });
  });

  it("single-category input produces one lane with index 0", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const r = makeResult({ time: t, orderKey: t.getTime(), category: "Cat 3" });
    const lanes = computeLanes([r], { laneOrder: null });
    assert.equal(lanes.length, 1);
    assert.equal(lanes[0].category, "Cat 3");
    assert.equal(lanes[0].index, 0);
  });

  it("results-only with UNKNOWN_CATEGORY only produces one lane", () => {
    const t = new Date("2024-06-15T10:00:00.000Z");
    const r = makeResult({ time: t, orderKey: t.getTime(), category: UNKNOWN_CATEGORY });
    const lanes = computeLanes([r], { laneOrder: null });
    assert.equal(lanes.length, 1);
    assert.equal(lanes[0].category, UNKNOWN_CATEGORY);
    assert.equal(lanes[0].index, 0);
  });
});
