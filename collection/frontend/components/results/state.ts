/**
 * state.ts — Reducer, initial state, and view-derivation helpers for ResultsApp.
 * STUB: task8 fills the real implementation.
 *
 * @module components/results/state
 */

import type { State, Action, Result, CandidateResult, Pack, Lane } from '../../types';

export function deriveView(
  crossings: Result[],
  candidates: CandidateResult[],
  candidatesVisible: boolean,
): { packs: Pack[]; lanes: Lane[] } {
  throw new Error('stub: deriveView');
}

export function hashPayload(resultsJson: string, candidatesJson: string): string {
  throw new Error('stub: hashPayload');
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
  sidebar: { open: false, item: null },
  browser: { open: false, anchorTs: null },
  statusPayload: null,
  pollError: null,
};

export function reducer(state: State, action: Action): State {
  throw new Error('stub: reducer');
}
