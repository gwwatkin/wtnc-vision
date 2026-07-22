/**
 * ResultsApp.js — Root Preact component for the results page.
 *
 * Self-contained via COLLECTION_CONFIG; no props. Owns ALL results-page state
 * through a single `useReducer` (state.js / FROZEN-4) and the poll loop. It is
 * the ONLY place server mutations + refresh live (FR13): child overlays call the
 * `on*` callbacks below, which hit `api.js` then re-poll. The old
 * `wtnc:edited` document event and JSON-diff DOM-skip are gone (SC5) — the
 * skip is now the reducer's identical-hash no-op + Preact's VDOM diff (NFR2).
 *
 * @module components/results/ResultsApp
 */

import {
  html,
  useReducer,
  useEffect,
  useCallback,
  useRef,
} from '../../vendor/preact-setup.js';
import * as api from '../../api.js';
import { resultsFromCrossings, candidatesToResults } from '../../results/data.js';
import { reducer, initialState, hashPayload } from './state.js';
import { RunSelector } from './RunSelector.js';
import { StatusBar } from './StatusBar.js';
import { Timeline } from './Timeline.js';
import { Sidebar } from './Sidebar.js';
import { FrameBrowser } from './FrameBrowser.js';

const RESULTS_POLL_MS = /** @type {any} */ (window).COLLECTION_CONFIG?.RESULTS_POLL_MS || 1500;
/** Refresh the run list every ~10 result ticks (~15 s at default cadence). */
const RUNS_POLL_MS = RESULTS_POLL_MS * 10;

/**
 * @param {import('../../types').ResultsAppProps} _props
 * @returns {any}
 */
export default function ResultsApp(_props) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const { selectedRun } = state;

  // Live mirror of selectedRun so the runs-poll interval's auto-select checks
  // the current value (not the stale mount-time closure).
  const selectedRunRef = useRef(selectedRun);
  selectedRunRef.current = selectedRun;

  // ---- server reads -------------------------------------------------------

  /** Fetch /results + /candidates together, transform, and dispatch. */
  const loadResults = useCallback(async (/** @type {string} */ label) => {
    if (!label) return;
    try {
      const [resultsPayload, candidatesPayload] = await Promise.all([
        api.fetchResults(label),
        api.fetchCandidates(label),
      ]);
      const crossings = resultsFromCrossings(resultsPayload);
      const candidates = candidatesToResults(candidatesPayload);
      const hash = hashPayload(
        JSON.stringify(resultsPayload),
        JSON.stringify(candidatesPayload),
      );
      dispatch({ type: 'POLL_RESULTS', crossings, candidates, hash });
    } catch (err) {
      dispatch({ type: 'POLL_ERROR', error: err instanceof Error ? err.message : String(err) });
    }
  }, []);

  /** Fetch /status (independent of the timeline — never forces its re-render). */
  const loadStatus = useCallback(async (/** @type {string} */ label) => {
    if (!label) return;
    try {
      const status = await api.fetchStatus(label);
      dispatch({ type: 'POLL_STATUS', status });
    } catch (_err) {
      // Status failure must not disturb the timeline (parity: fire-and-forget).
    }
  }, []);

  // ---- poll loops ---------------------------------------------------------

  // Runs list: on mount, then periodically. Auto-select the first run so the
  // page shows data without an explicit pick (blank == nothing to poll).
  useEffect(() => {
    let alive = true;
    async function loadRuns() {
      try {
        const runs = await api.fetchRuns();
        if (!alive) return;
        dispatch({ type: 'SET_RUNS', runs });
        if (runs.length > 0 && !selectedRunRef.current) {
          dispatch({ type: 'SELECT_RUN', runLabel: runs[0] });
        }
      } catch (_err) {
        // Ignore — run selector just won't update this tick.
      }
    }
    loadRuns();
    const id = setInterval(loadRuns, RUNS_POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, []);

  // Results + status: (re)start whenever the selected run changes.
  useEffect(() => {
    if (!selectedRun) return undefined;
    let alive = true;
    async function tick() {
      if (!alive) return;
      await loadResults(selectedRun);
      loadStatus(selectedRun); // fire-and-forget
    }
    tick();
    const id = setInterval(tick, RESULTS_POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, [selectedRun, loadResults, loadStatus]);

  // ---- mutation handlers (the only place mutations live — FR13) -----------

  const refresh = useCallback(() => loadResults(selectedRun || ''), [loadResults, selectedRun]);

  const onEdit = useCallback(async (/** @type {string} */ crossingId, /** @type {object} */ fields) => {
    await api.postEdit(selectedRun || '', crossingId, fields);
    await refresh();
  }, [selectedRun, refresh]);

  const onDelete = useCallback(async (/** @type {string} */ crossingId) => {
    await api.deleteEdit(selectedRun || '', crossingId);
    await refresh();
  }, [selectedRun, refresh]);

  const onPromote = useCallback(async (/** @type {string} */ candidateId, /** @type {object} */ payload) => {
    await api.promoteCandidate(selectedRun || '', candidateId, /** @type {any} */ (payload));
    await refresh();
  }, [selectedRun, refresh]);

  const onDismiss = useCallback(async (/** @type {string} */ candidateId) => {
    await api.dismissCandidate(selectedRun || '', candidateId);
    await refresh();
  }, [selectedRun, refresh]);

  const onCreateCrossing = useCallback(async (/** @type {object} */ payload) => {
    await api.postManualCrossing(selectedRun || '', payload);
    await refresh();
  }, [selectedRun, refresh]);

  // ---- render -------------------------------------------------------------

  const openCount = state.candidates.length;

  return html`
    <div class="results">
      <div class="results__toolbar">
        <${RunSelector}
          runs=${state.runs}
          selected=${state.selectedRun}
          onChange=${(/** @type {string} */ runLabel) => dispatch({ type: 'SELECT_RUN', runLabel })}
        />
        <label class="candidates-toggle">
          <input
            type="checkbox"
            checked=${state.candidatesVisible}
            onChange=${() => dispatch({ type: 'TOGGLE_CANDIDATES' })}
          />
          <span>Show candidates</span>
          <span class="candidates-toggle__count">${openCount}</span>
        </label>
      </div>

      <${StatusBar} status=${state.statusPayload} />

      <${Timeline}
        packs=${state.packs}
        lanes=${state.lanes}
        candidatesVisible=${state.candidatesVisible}
        selectedId=${state.selectedId}
        onSelect=${(/** @type {object} */ item) => dispatch({ type: 'OPEN_SIDEBAR', item })}
      />

      ${state.sidebar.item && html`
        <${Sidebar}
          item=${state.sidebar.item}
          frameOffset=${state.sidebar.frameOffset}
          runLabel=${state.selectedRun || ''}
          onClose=${() => dispatch({ type: 'CLOSE_SIDEBAR' })}
          onStepFrame=${(/** @type {number} */ delta) => dispatch({ type: 'STEP_FRAME', delta })}
          onEdit=${onEdit}
          onDelete=${onDelete}
          onPromote=${onPromote}
          onDismiss=${onDismiss}
          onOpenBrowser=${(/** @type {string} */ anchorTs) => dispatch({ type: 'OPEN_BROWSER', anchorTs })}
        />
      `}

      ${state.browser.open && html`
        <${FrameBrowser}
          runLabel=${state.selectedRun || ''}
          anchorTs=${state.browser.anchorTs}
          onClose=${() => dispatch({ type: 'CLOSE_BROWSER' })}
          onCreateCrossing=${onCreateCrossing}
        />
      `}
    </div>
  `;
}
