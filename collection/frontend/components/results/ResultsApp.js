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
 * page-split additions (task6):
 *   - BackendSettings rendered in toolbar (FROZEN-6 props {}).
 *   - Download CSV / JSON buttons (FROZEN-4 classes).
 *   - Live re-point via onBackendUrlChange subscription (OQ2).
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
import { BackendSettings } from '../common/BackendSettings.js';
import { downloadResults } from './download.js';
import { onBackendUrlChange } from '../../backend-url.js';

/** @type {{ COLLECTION_CONFIG?: { RESULTS_POLL_MS?: number } }} */
const _win = /** @type {any} */ (window);
const RESULTS_POLL_MS = _win.COLLECTION_CONFIG?.RESULTS_POLL_MS || 1500;
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

  /**
   * Fetch /runs, update state, and auto-select the first run if nothing is
   * currently selected. Extracted as a useCallback so the backend-URL change
   * handler can invoke it without duplicating poll logic (OQ2/task6).
   */
  const loadRuns = useCallback(async () => {
    try {
      const runs = await api.fetchRuns();
      dispatch({ type: 'SET_RUNS', runs });
      if (runs.length > 0 && !selectedRunRef.current) {
        dispatch({ type: 'SELECT_RUN', runLabel: runs[0] });
      }
    } catch (_err) {
      // Ignore — run selector just won't update this tick.
    }
  }, []);

  // Runs list: on mount, then periodically. Auto-select the first run so the
  // page shows data without an explicit pick (blank == nothing to poll).
  useEffect(() => {
    let alive = true;
    async function tick() {
      if (!alive) return;
      await loadRuns();
    }
    tick();
    const id = setInterval(tick, RUNS_POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, [loadRuns]);

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

  // Live re-point (OQ2): subscribe to backend URL changes. On change, wipe the
  // current run list + selection so stale data from the old back-end disappears,
  // then immediately re-load runs from the new target. The existing loadRuns
  // function handles the fetch + auto-select — no poll logic is duplicated.
  // SELECT_RUN with '' is a valid string (frozen type: string); the reducer
  // clears derived state and the falsy value halts the results poll until a
  // real run is selected. selectedRunRef is updated manually so that the
  // loadRuns auto-select path (which checks !selectedRunRef.current) fires
  // before the next render sets the ref.
  useEffect(() => {
    const unsub = onBackendUrlChange(() => {
      dispatch({ type: 'SET_RUNS', runs: [] });
      dispatch({ type: 'SELECT_RUN', runLabel: '' });
      selectedRunRef.current = '';
      loadRuns();
    });
    return unsub;
  }, [loadRuns]);

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

  const onReorder = useCallback(async (
    /** @type {string} */ crossingId,
    /** @type {{ earlierId: string | null, laterId: string | null }} */ neighbours,
  ) => {
    await api.reorderCrossing(selectedRun || '', crossingId, neighbours);
    await refresh();
  }, [selectedRun, refresh]);

  const onPromote = useCallback(async (/** @type {string} */ candidateId, /** @type {object} */ payload) => {
    await api.promoteCandidate(selectedRun || '', candidateId, /** @type {{ action: string, number: string }} */ (payload));
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

  // Crossing ids in timeline display order (DESC) — feeds the sidebar's
  // neighbour-based reorder. Candidates are skipped (parity with legacy DOM walk).
  const orderedCrossingIds = state.packs
    .flatMap((/** @type {import('../../types').Pack} */ p) => p.results)
    .filter((/** @type {import('../../types').Result | import('../../types').CandidateResult} */ r) => !r.isCandidate)
    .map((/** @type {import('../../types').Result} */ r) => r.crossingId);

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
        <button
          class="sidebar__btn toolbar__browse-btn"
          onClick=${() => (/** @type {(a: import('../../types').Action) => void} */ (dispatch))({ type: 'OPEN_BROWSER', anchorTs: /** @type {string} */ (/** @type {unknown} */ (null)) })}
        >Browse frames</button>
        <${BackendSettings} />
        <div class="results__download">
          <button
            class="download-btn"
            disabled=${!state.selectedRun}
            onClick=${() => downloadResults(/** @type {string} */ (state.selectedRun), 'csv')}
          >Download CSV</button>
          <button
            class="download-btn"
            disabled=${!state.selectedRun}
            onClick=${() => downloadResults(/** @type {string} */ (state.selectedRun), 'json')}
          >Download JSON</button>
        </div>
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
          runLabel=${state.selectedRun || ''}
          orderedCrossingIds=${orderedCrossingIds}
          onClose=${() => dispatch({ type: 'CLOSE_SIDEBAR' })}
          onEdit=${onEdit}
          onDelete=${onDelete}
          onReorder=${onReorder}
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
