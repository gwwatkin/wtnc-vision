# Implementation Report — Page Split, Configurable Back-end URL & Crossings Download

Run via the spec-first, parallel-agent workflow (`tasks/README.md`). Three waves,
gated on green checks, with a commit + push checkpoint between each. All work landed
on `main`.

## Outcome

Feature **implemented and pushed**; all automated gates green. Manual browser parity
(SC1–SC6) is the only remaining verification (see below).

| Wave | Tasks | Commit | Result |
|------|-------|--------|--------|
| A — scaffold (blocking) | task1 | `951f7e6` | `backend-url.js` store + 144-case suite, `BackendSettings`/`download.js` stubs, additive typedefs |
| B — parallel | task2–task7 | `d1a6250` | 3 pages + entries, `main.js` deleted, `api.js` all-through-`BASE()`, `BackendSettings`, CSV/JSON download, backend `/results/export` |
| C — integration | task8 | `3ac7066` | FROZEN-4 CSS, `config.js` comment, three READMEs |

## What shipped, by task

- **task1 — scaffold.** `collection/frontend/backend-url.js` implementing FROZEN-1
  (cookie-backed runtime base-URL store: `normalizeBackendUrl`, `getBackendUrl`,
  `setBackendUrl`, `onBackendUrlChange`, `backendLabel`; cookie `wtnc_backend_url`).
  `tests/backend-url.test.js` (144 cases), additive `types.d.ts` typedefs
  (`BackendSettingsProps`, `ExportFormat`), and stubs for `BackendSettings.js` /
  `download.js` so Wave B imports resolve and `tsc` stays incremental.
- **task2 — `api.js` rewiring + `download.js`.** Every call now routes through
  `BASE()=getBackendUrl()` (prepended once in `_fetch`; `checkHealth` and `frameUrl`
  fixed; double-base removed from `postFrame`/`uploadRoster`). Added `exportUrl` and
  `fetchExportBlob`. Filled `download.js` (blob→anchor; DOM confined here, `api.js`
  stays DOM-free). Closes the FR8 inconsistency.
- **task3 — `BackendSettings`.** Shared collapsible settings + reachability indicator
  (props `{}`); local `expanded/url/draft/health`, `onBackendUrlChange` subscription,
  URL-keyed health probe; Save / Use default via `setBackendUrl` with live re-apply
  (no reload). Emits the FROZEN-4 classes verbatim.
- **task4 — pages & entries.** `index.html` repurposed to a links-only landing;
  `collect.html` (`#capture-root`, no datalist) + `collect.js`; `view.html`
  (`#results-root` + `#roster-numbers` datalist) + `view.js`. `main.js` deleted.
  No page mounts both roots.
- **task5 — `CaptureApp` integration.** Renders `<BackendSettings/>` at the top;
  status line appends `· back-end: <label>`; on URL change stops any active recording
  and re-probes health. Capture loop otherwise untouched (FR16 parity).
- **task6 — `ResultsApp` integration.** Toolbar gains `<BackendSettings/>` and
  Download CSV / Download JSON (disabled with no run); `onBackendUrlChange`
  subscription resets runs and re-loads so the viewer live re-points. Reused existing
  `loadRuns`/`loadResults`; `SELECT_RUN ''` cleared selection — no new reducer action.
- **task7 — backend export.** Extracted `_compose_crossings(run)` from `get_results`
  (byte-identical `/results` body, guarded by existing tests) and added additive
  `GET /results/export?run=&format=csv|json` before the StaticFiles mount. CSV header
  `number,time,name,category`, `order_key` ASC, stdlib `csv`; JSON == `/results`;
  empty/disabled → 200 empty; bad format → 400. New `test_export.py` (22 tests).
  `config.yaml` gained a CORS/origins comment only. Engine/pipeline untouched.
- **task8 — integration.** FROZEN-4 CSS (landing, backend-settings panel + health dot,
  download buttons) matching the existing dark theme; `config.js` comment noting
  `BACKEND_URL` is now the default fallback; three READMEs documenting the pages, the
  UI URL control (cookie-persisted, live re-apply), the CORS note, and the download.

## Gates (final combined tree)

- **FE** `npm run check` — typecheck exit 0; unit **144/144**, stable across repeated
  runs.
- **Backend** `pytest collection/backend/tests/` — **317 passed** (22 new export tests
  plus unchanged `/results` tests proving the refactor is parity).
- **SC7 wire-up** — no page mounts both roots; `main.js` gone; no raw same-origin
  `fetch('/…')` or bare `frameUrl` in `api.js` (only `_fetch('/…')`, which prepends
  `BASE()`); datalist only in `view.html`; `run.sh` runs `python -m backend`, no node
  (NFR1).

## Issues found and resolved during the run

- **Flaky FROZEN-1 test suite (fixed in Wave A).** `backend-url.test.js` failed ~⅓ of
  runs: `clearCookies()` relied on happy-dom's string `max-age=0` expiry, which is
  unreliable at second granularity, so a leftover `wtnc_backend_url` cookie
  intermittently shadowed the config-default fallback. Replaced with a fresh
  happy-dom `Window` (fresh cookie jar) per test via a root `beforeEach`. Verified
  20/20 clean. This was a test-isolation bug, not a `backend-url.js` contract change.
- **Transient parallel-wave typecheck error.** The task4 agent observed a
  `TS7006` in task3's `BackendSettings.js` while task3 was still mid-edit — the normal
  race of agents running `tsc` at different moments in a shared tree. The final
  combined tree is clean; verified independently rather than trusting per-agent
  reports.

No agent flagged a frozen contract as genuinely wrong; all Wave B tasks coded against
the frozen surfaces without divergence.

## Remaining manual verification (browser — not automatable headlessly)

- **SC1** — landing links open collector and viewer standalone; each loads only its
  own app.
- **SC2** — set a URL, reload, value retained; DevTools Network shows **every** request
  (incl. `frameUrl` images) on the new base.
- **SC3** — FE served from a different origin than the API, with that origin added to
  `config.yaml → server.allowed_origins`, loads/uploads without CORS errors.
- **SC4** — a wrong/unreachable URL shows the red indicator, not a silent blank.
- **SC5** — on an edited/manual/reordered/deleted run, CSV and JSON downloads match the
  timeline (edit applied, manual present, order honored, deleted excluded); an empty
  run yields valid empty files.
- **SC6** — collector captures live from camera and from an uploaded video, with results
  appearing on the viewer pointed at the same back-end.

## Notes

- Checkpoints landed directly on `main` per the run decision; the pre-existing
  `specs/FUTURE.md` edit and the `fe-modernization → completed/` move were left
  untouched.
- Per the workflow, the final step after the manual pass is moving
  `specs/page-split/` under `specs/completed/`.
