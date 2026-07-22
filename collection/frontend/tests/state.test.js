/**
 * state.test.js — Reducer + deriveView transitions for ResultsApp (task8).
 *
 * Covers FR8/FR13/NFR2/SC5: identical-hash no-op returns the SAME object
 * (Preact bails), changed payload recomputes packs/lanes, TOGGLE_CANDIDATES
 * re-derives from the retained raw arrays, and selection/sidebar/browser
 * transitions. Uses only state.js + data.js (both pure, importable in Wave B).
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  reducer,
  initialState,
  deriveView,
  hashPayload,
} from '../components/results/state.js';
import { resultsFromCrossings, candidatesToResults } from '../results/data.js';

// --- fixtures --------------------------------------------------------------

/** @param {any} [o] @returns {any} */
function crossingPayload(o = {}) {
  return {
    crossings: [
      {
        crossing_id: 'c1', number: '42', time: '2024-06-15T10:00:00.000Z',
        name: 'Alice', category: 'Cat 3', matched: true,
        annotated_url: '/a/c1.jpg', source: 'auto', edited: false,
        order_key: 0, order_overridden: false,
      },
      {
        crossing_id: 'c2', number: '43', time: '2024-06-15T10:00:01.000Z',
        name: 'Bob', category: 'Cat 3', matched: true,
        annotated_url: '/a/c2.jpg', source: 'auto', edited: false,
        order_key: 0, order_overridden: false,
      },
    ],
    ...o,
  };
}

/** @param {any} [o] @returns {any} */
function candidatePayload(o = {}) {
  return {
    candidates: [
      {
        candidate_id: 'run1-cand-1', run: 'run1', time: '2024-06-15T10:00:02.000Z',
        last_seen: '2024-06-15T10:00:03.000Z', frame_count: 3,
        hint_number: '128', hint_conf: 0.7, rep_filename: 'f.jpg',
        rep_box: [1, 2, 3, 4], state: 'open', image_url: '/i',
      },
    ],
    ...o,
  };
}

/** @param {any} rp @param {any} cp @returns {import('../types').Action} */
function pollAction(rp, cp) {
  return {
    type: 'POLL_RESULTS',
    crossings: resultsFromCrossings(rp),
    candidates: candidatesToResults(cp),
    hash: hashPayload(JSON.stringify(rp), JSON.stringify(cp)),
  };
}

// --- deriveView ------------------------------------------------------------

test('deriveView', async (t) => {
  const crossings = resultsFromCrossings(crossingPayload());
  const candidates = candidatesToResults(candidatePayload());

  await t.test('excludes candidates when candidatesVisible is false', () => {
    const { packs } = deriveView(crossings, candidates, false);
    const ids = packs.flatMap((p) => p.results.map((r) => /** @type {any} */ (r).crossingId));
    assert.deepEqual(ids.sort(), ['c1', 'c2']);
    assert.ok(!packs.some((p) => p.results.some((r) => /** @type {any} */ (r).isCandidate)));
  });

  await t.test('includes candidates when candidatesVisible is true', () => {
    const { packs } = deriveView(crossings, candidates, true);
    const hasCandidate = packs.some((p) => p.results.some((r) => /** @type {any} */ (r).isCandidate));
    assert.ok(hasCandidate, 'candidate pseudo-result must appear');
  });

  await t.test('computes lanes for present categories', () => {
    const { lanes } = deriveView(crossings, candidates, false);
    assert.ok(lanes.some((l) => l.category === 'Cat 3'));
  });
});

// --- POLL_RESULTS dedupe (NFR2/SC5) ---------------------------------------

test('POLL_RESULTS', async (t) => {
  await t.test('identical hash returns the SAME state object (no-op)', () => {
    const rp = crossingPayload();
    const cp = candidatePayload();
    const s1 = reducer(initialState, pollAction(rp, cp));
    const s2 = reducer(s1, pollAction(rp, cp)); // same payload → same hash
    assert.strictEqual(s2, s1, 'must return the identical reference so Preact bails');
  });

  await t.test('changed payload recomputes packs/lanes and updates state', () => {
    const s1 = reducer(initialState, pollAction(crossingPayload(), candidatePayload()));
    const changed = crossingPayload({
      crossings: [
        { crossing_id: 'c9', number: '99', time: '2024-06-15T11:00:00.000Z',
          name: 'Zoe', category: 'Cat 1', matched: true, annotated_url: '/a/c9.jpg',
          source: 'auto', edited: false, order_key: 0, order_overridden: false },
      ],
    });
    const s2 = reducer(s1, pollAction(changed, candidatePayload()));
    assert.notStrictEqual(s2, s1);
    assert.equal(s2.crossings.length, 1);
    assert.equal(s2.crossings[0].crossingId, 'c9');
    assert.ok(s2.packs.length >= 1);
  });

  await t.test('candidates are excluded from packs by default (candidatesVisible false)', () => {
    const s1 = reducer(initialState, pollAction(crossingPayload(), candidatePayload()));
    const hasCandidate = s1.packs.some((p) => p.results.some((r) => /** @type {any} */ (r).isCandidate));
    assert.ok(!hasCandidate);
  });
});

// --- TOGGLE_CANDIDATES -----------------------------------------------------

test('TOGGLE_CANDIDATES re-derives from retained raw arrays', () => {
  const s1 = reducer(initialState, pollAction(crossingPayload(), candidatePayload()));
  assert.equal(s1.candidatesVisible, false);

  const s2 = reducer(s1, { type: 'TOGGLE_CANDIDATES' });
  assert.equal(s2.candidatesVisible, true);
  const hasCandidate = s2.packs.some((p) => p.results.some((r) => /** @type {any} */ (r).isCandidate));
  assert.ok(hasCandidate, 'toggling on must surface the retained candidate without a refetch');

  const s3 = reducer(s2, { type: 'TOGGLE_CANDIDATES' });
  assert.equal(s3.candidatesVisible, false);
  assert.ok(!s3.packs.some((p) => p.results.some((r) => /** @type {any} */ (r).isCandidate)));
});

// --- selection / sidebar / browser ----------------------------------------

test('selection and overlay transitions', async (t) => {
  const crossing = { isCandidate: false, crossingId: 'c1' };
  const candidate = { isCandidate: true, candidateId: 'run1-cand-1' };

  await t.test('OPEN_SIDEBAR selects by crossingId and opens', () => {
    const s = reducer(initialState, { type: 'OPEN_SIDEBAR', item: crossing });
    assert.equal(s.selectedId, 'c1');
    assert.equal(s.sidebar.open, true);
    assert.equal(s.sidebar.item, crossing);
  });

  await t.test('OPEN_SIDEBAR selects a candidate by candidateId', () => {
    const s = reducer(initialState, { type: 'OPEN_SIDEBAR', item: candidate });
    assert.equal(s.selectedId, 'run1-cand-1');
  });

  await t.test('CLOSE_SIDEBAR clears selection and closes', () => {
    let s = reducer(initialState, { type: 'OPEN_SIDEBAR', item: crossing });
    s = reducer(s, { type: 'CLOSE_SIDEBAR' });
    assert.equal(s.sidebar.open, false);
    assert.equal(s.sidebar.item, null);
    assert.equal(s.selectedId, null);
  });

  await t.test('OPEN_BROWSER / CLOSE_BROWSER toggle the browser overlay', () => {
    let s = reducer(initialState, { type: 'OPEN_BROWSER', anchorTs: '2024-06-15T10:00:00Z' });
    assert.equal(s.browser.open, true);
    assert.equal(s.browser.anchorTs, '2024-06-15T10:00:00Z');
    s = reducer(s, { type: 'CLOSE_BROWSER' });
    assert.equal(s.browser.open, false);
    assert.equal(s.browser.anchorTs, null);
  });

  await t.test('SELECT_ITEM sets selectedId without opening the sidebar', () => {
    const s = reducer(initialState, { type: 'SELECT_ITEM', item: crossing });
    assert.equal(s.selectedId, 'c1');
    assert.equal(s.sidebar.open, false);
  });
});

// --- runs / status ---------------------------------------------------------

test('runs and status transitions', async (t) => {
  await t.test('SET_RUNS stores the run list', () => {
    const s = reducer(initialState, { type: 'SET_RUNS', runs: ['r1', 'r2'] });
    assert.deepEqual(s.runs, ['r1', 'r2']);
  });

  await t.test('SELECT_RUN resets derived state and dedupe key', () => {
    const polled = reducer(initialState, pollAction(crossingPayload(), candidatePayload()));
    assert.notEqual(polled.lastPayloadHash, '');
    const s = reducer(polled, { type: 'SELECT_RUN', runLabel: 'r2' });
    assert.equal(s.selectedRun, 'r2');
    assert.equal(s.lastPayloadHash, '');
    assert.deepEqual(s.packs, []);
    assert.deepEqual(s.crossings, []);
  });

  await t.test('POLL_STATUS stores the status payload', () => {
    const s = reducer(initialState, { type: 'POLL_STATUS', status: { queue: 3 } });
    assert.deepEqual(s.statusPayload, { queue: 3 });
  });

  await t.test('POLL_ERROR records the error string', () => {
    const s = reducer(initialState, { type: 'POLL_ERROR', error: 'boom' });
    assert.equal(s.pollError, 'boom');
  });
});
