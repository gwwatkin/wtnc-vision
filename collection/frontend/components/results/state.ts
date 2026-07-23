/**
 * state.ts — Reducer, initial state, and view-derivation helpers for ResultsApp.
 *
 * Pure module (no Preact, no DOM). The reducer owns all results-page state
 * (FROZEN-4 / design §8). `deriveView` is the verbatim port of today's
 * results.js render pipeline (FROZEN-2), lifted out of the DOM path.
 *
 * NFR2/SC5: `POLL_RESULTS` short-circuits on an identical payload hash by
 * returning the SAME state object — Preact then bails the re-render. This is a
 * dispatch-level dedupe, NOT the removed compare-then-manually-patch DOM machinery.
 *
 * @module components/results/state
 */

import type { State, Action, Result, CandidateResult, Pack, Lane } from '../../types';
import {
  mergeCandidates,
  sortByOrder,
  groupIntoPacks,
  computeLanes,
} from '../../results/data';

/**
 * Port of today's results.js render pipeline (FROZEN-2): optionally merge open
 * candidates, sort by order-of-record, then group into packs + compute lanes.
 * The 3-second gap window and `laneOrder: null` are frozen.
 */
export function deriveView(
  crossings: Result[],
  candidates: CandidateResult[],
  candidatesVisible: boolean,
): { packs: Pack[]; lanes: Lane[] } {
  const base = candidatesVisible ? mergeCandidates(crossings, candidates) : crossings;
  const sorted = sortByOrder(base);
  return {
    packs: groupIntoPacks(sorted, 3),
    lanes: computeLanes(sorted, { laneOrder: null }),
  };
}

/**
 * Dispatch-level dedupe key over the raw /results + /candidates JSON (NFR2 note
 * — a plain string compare; no SHA / crypto.subtle). Identical inputs ⇒ identical
 * key ⇒ POLL_RESULTS is a no-op ⇒ no new state object.
 */
export function hashPayload(resultsJson: string, candidatesJson: string): string {
  return resultsJson + ' ' + candidatesJson;
}

/**
 * Resolve the stable id of a timeline item (crossing or candidate).
 */
function itemId(item: object | null): string | null {
  if (!item) return null;
  const i = item as { isCandidate?: boolean; candidateId?: string; crossingId?: string };
  return i.isCandidate ? (i.candidateId ?? null) : (i.crossingId ?? null);
}

export const initialState: State = {
  runs: [],
  selectedRun: null,

  crossings: [],
  candidates: [],
  lastPayloadHash: '',

  packs: [],
  lanes: [],

  candidatesVisible: false,
  selectedId: null,

  sidebar: {
    open: false,
    item: null,
  },
  browser: {
    open: false,
    anchorTs: null,
  },

  statusPayload: null,
  pollError: null,
};

/**
 * Pure reducer for ResultsApp — handles all 11 FROZEN-4 actions.
 */
export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_RUNS':
      return { ...state, runs: action.runs };

    case 'SELECT_RUN':
      // New run: clear derived + raw state and reset the dedupe key so the next
      // poll renders from scratch (parity with results.js clearing the timeline).
      return {
        ...state,
        selectedRun: action.runLabel,
        crossings: [],
        candidates: [],
        lastPayloadHash: '',
        packs: [],
        lanes: [],
        selectedId: null,
        statusPayload: null,
        pollError: null,
        sidebar: { open: false, item: null },
        browser: { open: false, anchorTs: null },
      };

    case 'POLL_RESULTS': {
      // NFR2/SC5: identical payload ⇒ return the SAME object (Preact bails).
      if (action.hash === state.lastPayloadHash) return state;
      const { packs, lanes } = deriveView(
        action.crossings,
        action.candidates,
        state.candidatesVisible,
      );
      return {
        ...state,
        crossings: action.crossings,
        candidates: action.candidates,
        lastPayloadHash: action.hash,
        packs,
        lanes,
        pollError: null,
      };
    }

    case 'POLL_STATUS':
      return { ...state, statusPayload: action.status, pollError: null };

    case 'TOGGLE_CANDIDATES': {
      const candidatesVisible = !state.candidatesVisible;
      // Re-derive from the retained raw arrays — no refetch (design §8).
      const { packs, lanes } = deriveView(
        state.crossings,
        state.candidates,
        candidatesVisible,
      );
      return { ...state, candidatesVisible, packs, lanes };
    }

    case 'SELECT_ITEM':
      return { ...state, selectedId: itemId(action.item) };

    case 'OPEN_SIDEBAR':
      return {
        ...state,
        selectedId: itemId(action.item),
        sidebar: {
          open: true,
          item: action.item,
        },
      };

    case 'CLOSE_SIDEBAR':
      return {
        ...state,
        selectedId: null,
        sidebar: { open: false, item: null },
      };

    case 'OPEN_BROWSER':
      return { ...state, browser: { open: true, anchorTs: action.anchorTs } };

    case 'CLOSE_BROWSER':
      return { ...state, browser: { open: false, anchorTs: null } };

    case 'POLL_ERROR':
      return { ...state, pollError: action.error };

    default:
      return state;
  }
}
