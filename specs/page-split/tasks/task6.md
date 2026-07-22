# task6 — `ResultsApp` integration: settings + download + live re-point (Wave B)

**Model:** sonnet · Depends on task1 (`backend-url.js`, `BackendSettings` & `download.js` stubs).

Source of truth: `../design.md` (§5, §6.2), `tasks/README.md` (FROZEN-1, FROZEN-4, FROZEN-6).
Codes against frozen contracts of `BackendSettings` (`{}`) and `download.js`
(`downloadResults(run, format)`), not their implementations (task3/task2). Run FE commands
from `collection/frontend/`.

## Owns (exclusive)
- `collection/frontend/components/results/ResultsApp.js`

## Do (additive edits — preserve all existing results behavior, parity)

1. Import `{ BackendSettings }` from `../common/BackendSettings.js`,
   `{ downloadResults }` from `./download.js`, and
   `{ onBackendUrlChange }` from `../../backend-url.js`.
2. **Toolbar additions** in `.results__toolbar`:
   - `<${BackendSettings} />` (the always-visible target/health indicator sits in the
     status region alongside `StatusBar`).
   - A download group (FROZEN-4 classes):
     ```html
     <div class="results__download">
       <button class="download-btn" disabled=${!state.selectedRun}
               onClick=${() => downloadResults(state.selectedRun, 'csv')}>Download CSV</button>
       <button class="download-btn" disabled=${!state.selectedRun}
               onClick=${() => downloadResults(state.selectedRun, 'json')}>Download JSON</button>
     </div>
     ```
     Buttons are disabled when no run is selected.
3. **Live re-point (OQ2).** Subscribe to `onBackendUrlChange` on mount (unsubscribe on
   unmount). On change: dispatch `SET_RUNS` with `[]` and `SELECT_RUN` cleared **or** the
   existing reset path, then immediately re-run the runs load so stale runs from the old
   back-end disappear and the viewer re-points at once. Reuse the existing `loadRuns` /
   `loadResults` functions — do not duplicate the poll logic. If clearing `selectedRun`
   needs a reducer affordance the current actions don't provide, prefer re-using
   `SELECT_RUN` with the first run of the freshly fetched list; **flag** if a new action is
   genuinely required (frozen state shape).

## Constraints
- No `styles.css` edits (use FROZEN-4 classes; flag any gap to task8). `StatusBar` is **not**
  edited. Polling economy (NFR2) preserved — the download buttons and subscription must not
  add per-tick work.

## Done when
- `npm run typecheck` green. Viewer shows the settings panel + Download CSV/JSON (disabled
  with no run); changing the back-end URL re-points the viewer without a reload; timeline,
  sidebar, frame browser, candidates all still work.
