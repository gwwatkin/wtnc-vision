# Requirements — FE Modernization: Toolchain, Tests, Preact

## 1. Background & Purpose

The front-end has grown feature by feature (collection → live-pipeline → results-ux →
review-editing) into ~3,350 lines of hand-written vanilla JS under `collection/frontend/`:
a capture page (`app.js`) and a results timeline (`results/*.js`) with a sidebar, frame
browser, candidate handling, and live status. It is served as-is by the FastAPI back-end
(StaticFiles) — no build step, no node toolchain, no JS tests.

That leanness served the POC well, but the project is maturing and three gaps now cost us:

- **No FE tests at all.** The transform pipeline in `results/data.js` (grouping, lanes,
  candidate merging, ordering) is pure logic with real regression risk — every spec so
  far has reworked it — and nothing guards it. All existing tests are Python.
- **Hand-rolled UI state sync.** The DOM modules manually diff and patch:
  `results.js` skips re-renders by comparing serialized JSON, `sidebar.js` re-applies
  selection highlights after every re-render, `edits.js` broadcasts a `CustomEvent` on
  `document` to trigger refreshes. Each new feature multiplies this bookkeeping and its
  bug surface.
- **No formal FE tooling.** There is no `package.json`, no dependency manifest, no
  single command to check the FE. "The build system" is implicit ("serve the files"),
  which was fine until we wanted tests and a component library.

This iteration modernizes the FE platform in three coupled workstreams: **formalize the
(no-)build system**, **add node-based FE tests**, and **port the UI to Preact**.

This document is *what & why*. Unusually for this repo, the *feature itself is
technical*, so technology already chosen by the product owner (no-build stance, node
test runner, Preact) is recorded as resolved decisions; everything still open
(file layout, vendoring mechanics, component boundaries, test organization) belongs
in `design.md`.

## 2. Goals

- **G1 — A formalized, still-lean build system.** The FE gains an explicit toolchain
  (dependency manifest, vendored runtime deps, one-command test entry point) while the
  *runtime* story stays exactly as today: FastAPI serves static files, no compile step,
  no node in the run/deploy loop.
- **G2 — FE tests that run on node.** The FE's logic is covered by automated tests
  invoked with node, runnable headlessly on this machine with a single command, fast
  enough to run habitually.
- **G3 — The whole FE on Preact.** Both pages — capture (`app.js`) and results
  (`results/*.js`) — are componentized on Preact. Rendering becomes a function of
  state; the hand-rolled skip/re-apply/event-bus machinery is deleted, not wrapped.
- **G4 — Behavior parity.** The port is a re-platforming, not a redesign: the operator
  sees the same pages, flows, and performance characteristics before and after.

## 3. Resolved Decisions

Baked into the requirements below (made by the product owner during scoping):

- **D1 — No-build, formalized.** The runtime remains buildless: checked-in ES modules
  served directly. A `package.json` exists for *development* only (test runner,
  tooling); nothing in `run.sh`, deployment, or the serving path invokes node.
- **D2 — Runtime dependencies are vendored.** Preact (and any companion runtime libs)
  are checked into the repo as ES modules and imported by path, satisfying the existing
  "no network at runtime" constraint. Updating a vendored dep is an explicit,
  scriptable action pinned to a version.
- **D3 — Tests run on node's toolchain.** FE tests execute under node (available on
  this machine at `/usr/bin/node`), not under a browser or a Python harness. The
  design chooses the exact runner; node's built-in runner is the default candidate to
  keep dependencies near zero.
- **D4 — Full port, including the capture page.** Not just the results UI: `app.js`
  is componentized too, so the FE ends uniform — one framework, one idiom, no
  "legacy page" carve-out.
- **D5 — Vite-ready is not a goal.** The design should not contort to keep a future
  bundler adoption cheap; if the no-build idiom and a hypothetical bundler idiom
  conflict, the no-build idiom wins. (A later bundler spec may edit these contracts —
  frozen means per-spec here, as always.)
- **D6 — Tests precede the port where it pays.** Pure-logic tests (today's
  `results/data.js`) are written against the *current* code first and must pass
  unchanged against the ported code — they double as the port's regression net.

## 4. Key Facts (what already exists to build on)

- **A1 — The FE is already layered for this.** `results/data.js` (485 lines) is
  documented and verified pure — no DOM, no fetch. The DOM-heavy modules
  (`render.js`, `sidebar.js`, `browser.js`, `status.js`) and the fetch/mutation module
  (`edits.js`) are cleanly separated. The pure layer ports unchanged; the DOM layer is
  what gets componentized.
- **A2 — The back-end contract is stable and tested.** The FastAPI endpoints
  (`/results`, `/candidates`, `/status`, `/runs`, edit mutations) are covered by
  Python tests (`collection/backend/tests/`). This spec does not change the API; the
  FE keeps polling the same endpoints.
- **A3 — Node exists on the dev machine but not in the workflow.** `/usr/bin/node`,
  `npm`, `npx` are installed system-wide; the repo has no `package.json`,
  `node_modules`, or lockfile.
- **A4 — The current UI's dynamic behaviors are the parity bar.** Live polling with
  per-concern re-render skipping, selection surviving re-renders, sidebar/browser
  overlays, candidate toggle, drag/move order editing, camera capture + video ingest +
  roster upload on the capture page. These behaviors — not the implementation
  mechanisms behind them — must survive the port.
- **A5 — Volume & environment** (unchanged): one session, hundreds of crossings,
  thousands of frames, CPU-only laptop, localhost, single operator, latest-Chromium-
  class browser. No legacy-browser support required.

## 5. Functional Requirements

### 5.1 Build system / toolchain (G1)
- **FR1** — The repo gains a dependency manifest (`package.json` + lockfile) declaring
  all FE dev dependencies; `npm` (or equivalent) reproduces the dev environment from
  it. Runtime vendored deps are pinned and their provenance (name, version, source)
  recorded.
- **FR2** — A single documented command runs all FE tests from the repo (or
  `collection/`) root. It requires only node + the manifest — no venv, no running
  back-end, no browser.
- **FR3** — Updating a vendored runtime dep (e.g. Preact version bump) is a documented,
  scriptable step that leaves the repo runnable with no further build action.
- **FR4** — `run.sh`, the StaticFiles mount, and the operator's start-the-app flow are
  unchanged. A fresh clone with only Python + the venv still runs the app; node is
  needed only to develop/test the FE.
- **FR5** — FE development docs (a section in `collection/README.md` or equivalent)
  cover: layout, how to run tests, how to add a component, how to update vendored deps.

### 5.2 FE tests on node (G2)
- **FR6** — The pure transform layer (today's `results/data.js`: crossing/candidate
  transforms, ordering, pack grouping, lane assignment, merging) is covered by unit
  tests exercising normal cases, edge cases (empty runs, unparseable times, duplicate
  ids), and the invariants other modules rely on.
- **FR7** — Per D6, these tests are written against the current implementation first;
  the ported implementation must pass the same tests unchanged. Where the port
  relocates pure logic, the tests move with it but their assertions do not weaken.
- **FR8** — New pure logic introduced by the port (state derivations, formatting,
  polling bookkeeping extracted from DOM code) lands with tests in the same style.
- **FR9** — Component-level tests (rendering a Preact component against a DOM shim and
  asserting on output/interaction) are **in scope as a stretch tier**: the design must
  choose and wire the mechanism (e.g. a lightweight DOM shim as a dev dependency), and
  at least the highest-risk component (timeline card list with selection) gets
  coverage — but exhaustive component coverage is not required this iteration (OQ2).
- **FR10** — The full test run completes in seconds (target < 10 s) so it can gate
  every FE change.

### 5.3 Preact port (G3, G4)
- **FR11** — The results page (timeline, packs/lanes, gap separators, candidate
  rendering + toggle, sidebar with edit / delete / reorder actions, frame browser
  overlay, status readout, run selector, order editing) is rendered by Preact
  components. Behavior parity per A4.
- **FR12** — The capture page (camera preview, source selector, video-file ingest,
  capture start/stop, in-flight/frame counters, roster upload + status) is rendered by
  Preact components. Behavior parity per A4.
- **FR13** — UI state becomes explicit: polling results feed component state; rendering
  is derived from state. The hand-rolled mechanisms — JSON-comparison render skipping,
  post-render selection re-application, the `wtnc:edited` document event — are removed,
  with their *purposes* (no wasted re-renders, selection stability, refresh after edit)
  met by the framework idiom instead.
- **FR14** — The pure transform layer survives as plain modules (imported by
  components, tested per FR6–FR7); componentization does not smear logic back into
  the view layer.
- **FR15** — Server communication (polling loops, edit mutations, frame/image URLs)
  is consolidated behind a thin, testable layer rather than scattered `fetch` calls,
  without changing the wire contract (A2).
- **FR16** — The old implementations are deleted in the same iteration — no parallel
  legacy page, no dead modules left behind (subject to migration staging during the
  implementation run; the *end state* is single-implementation).

## 6. Non-Functional Requirements

- **NFR1 (Runtime leanness)** — Page load stays buildless and light: no bundler
  output, no source maps requirement, vendored framework cost on the order of a few
  KB gzipped. First meaningful render of the results page is not perceptibly worse.
- **NFR2 (Polling economy)** — The ported page does no more re-render work per poll
  tick than today's skip logic achieves: an unchanged poll payload results in no
  observable DOM churn.
- **NFR3 (Dev ergonomics)** — Edit a component → reload the browser → see the change.
  No compile step, no watcher required (browser-native ESM). Test feedback per FR10.
- **NFR4 (Isolation of concerns)** — The back-end, its tests, and the Python workflow
  are untouched. CLAUDE.md's Python rules gain a sibling FE section rather than
  changing.
- **NFR5 (Reviewability)** — Vendored dependency files are clearly segregated (e.g. a
  `vendor/` directory) so human review can skip them and diffs stay meaningful.
- **NFR6 (Parity provable)** — Where parity matters most (A4 behaviors), the spec's
  tasks include explicit manual verification steps against a real run's data, not just
  unit tests.

## 7. Scope

### 7.1 This phase
- `package.json` + lockfile; vendoring mechanism + pinned Preact; test command; FE
  dev docs (G1).
- Unit tests for the pure transform layer, written pre-port, surviving the port;
  tests for newly extracted pure logic; component-test mechanism wired with at least
  one high-risk component covered (G2).
- Full Preact port of both pages; deletion of superseded machinery and files (G3).
- CLAUDE.md / README updates describing the new FE conventions.

### 7.2 Out of scope (captured for context)
- Any bundler/compile step, JSX, `.ts` sources or TS emit, HMR (D1, D5) — a future spec
  may revisit. **In scope**, however: dev-only `tsc --noEmit` type-checking over
  JSDoc-annotated `.js` — it emits nothing, keeps the runtime buildless (D1 holds), and
  makes the frozen component/state contracts machine-enforced rather than prose. The
  *language* TypeScript stays out; the *checker* comes in (design §10).
- End-to-end browser tests (Playwright et al.) — deliberately deferred; the fixture-
  backed back-end + real browser harness is its own iteration if wanted.
- Visual redesign, UX changes, new features — parity only (G4). Feature work resumes
  on top of the ported FE.
- Back-end/API changes of any kind (A2, NFR4).
- CI wiring — there is no CI in this repo today; the test command is the deliverable,
  scheduling it elsewhere is not.
- Linting/formatting toolchain — see OQ3.

## 8. Success Criteria

- **SC1** — From a fresh clone: `npm ci` (or equivalent) then the single test command
  passes in < 10 s with no back-end running (FR2, FR10); separately, the app still
  starts via `run.sh` with no node involvement (FR4).
- **SC2** — The `data.js` test suite, written before the port, passes unchanged after
  the port (D6, FR7).
- **SC3** — Both pages render and behave at parity against a real captured run:
  timeline with packs/candidates/status, sidebar editing, frame browser, order
  editing; capture page camera/video/roster flows (FR11–FR12, NFR6 checklist).
- **SC4** — With the back-end idle (unchanged poll payloads), the ported results page
  shows no DOM churn — verified via DevTools paint flashing or equivalent (NFR2).
- **SC5** — `grep` finds no remaining `wtnc:edited` dispatches, JSON-diff skip logic,
  or `reapplySelectionHighlight`-style re-application code — the mechanisms are gone,
  and the behaviors they served still hold (FR13).
- **SC6** — At least one component test renders a Preact component under node and
  asserts on interaction-driven output (FR9).
- **SC7** — A deliberate breakage of a transform invariant (e.g. pack grouping
  window) is caught by the FR6 suite.

## 9. Open Questions (resolved before design)

- **OQ1 — Test runner choice.** ✅ **Resolved** — `node --test` (built-in, zero
  dependencies). Vitest is deferred to a separate spec if ever needed.
- **OQ2 — Component-test depth.** ✅ **Resolved** — hold the line: mechanism wired +
  one high-risk component (Timeline card list) covered; exhaustive component coverage
  is a later iteration.
- **OQ3 — Linter/formatter.** ✅ **Resolved** — skip entirely this iteration; a
  separate spec can add tooling without touching the component port.
- **OQ4 — htm vs. alternatives for templates.** ✅ **Resolved** — `htm` (tagged
  template literals, ~1 KB, vendored alongside Preact). Raw `h()` calls are too
  verbose for non-trivial trees; JSX requires a build step (ruled out by D1).
- **OQ5 — Migration staging.** ✅ **Resolved** — one wave (big-bang): all components
  authored in parallel as new files, then wired and old files deleted in the
  integration task. No extended period of mixed idioms.
