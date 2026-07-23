# Implementation Report — JSDoc → TypeScript (JSX, npm deps, Vite bundler)

Run via the spec-first, parallel-agent workflow (`tasks/README.md`). Three waves,
gated on green checks, with a commit + push checkpoint between each. All work landed
on `main`.

## Outcome

Feature **implemented and pushed**; all automated gates green. Interactive browser
parity (camera / video / HMR / runtime config re-point) is the only remaining
verification (see below).

| Wave | Tasks | Commit | Result |
|------|-------|--------|--------|
| A — scaffold (blocking) | task1 | `66b175d` | Vite/Vitest/TS toolchain, `types.ts`, full `Card.tsx` + test, every other module stubbed, `vendor/` deleted |
| B — parallel convert | task2–task8 | `3732dca` | 18 stubs filled + 6 suites ported; htm→JSX byte-parity; 140 tests |
| C — integration | task9 | `fbf7efd` | entries + HTML + `config.js`→`public/`, `dist/` mount, old world deleted, build + docs |

## What shipped, by task

- **task1 — scaffold (Wave A, blocking).** Stood up the toolchain: `preact` dep;
  `vite`, `@preact/preset-vite`, `vitest`, `typescript`, `happy-dom` devDeps; the six
  FROZEN-3 scripts. `vite.config.ts` (multi-page `index`/`collect`/`view` inputs,
  `happy-dom` test env), `tsconfig.json` (`jsx: react-jsx`, `jsxImportSource: preact`,
  `allowJs`/`checkJs` removed). Copied `types.d.ts` → `types.ts` verbatim in shape
  (FROZEN-2), converted `Card.tsx` + `card-badges.test.ts` end-to-end as the worked
  reference (FROZEN-1/FROZEN-4), and **stubbed every other module** (FROZEN-8) so
  `tsc` is green and incremental. Deleted `vendor/`.
- **task2 — `results/data.ts` de-quarantine (+ `data.test.ts`).** Collapsed
  `data.js` + `data.d.ts` into one strict module (FROZEN-6), names/signatures kept.
  `Date` subtraction → `.getTime()`; widened literals annotated to the frozen
  `Result`/`CandidateResult` shapes / `as const`; loose `any` payload params →
  `unknown` narrowed at the boundary. Ported 71-case suite; runtime output identical
  (NFR6/SC3). No `any` on the public surface, no `@ts-nocheck`.
- **task3 — `Timeline.tsx` + `format.ts` (+ timeline/format tests).** Converted
  `Timeline`, `Pack`, `GapSeparator` to JSX with byte-for-byte DOM (`.timeline` root
  with `--lane-count`, `.lane-header[data-category]`, `column` to cards,
  `.gap-separator`, `.timeline__empty`). **Reconciled `format.ts` read-only** — task1
  had already given it a real body (Card needed `formatTimeOfDay`); task3 confirmed it
  matched `format.js` and left it untouched, then ported both suites.
- **task4 — `Sidebar.tsx` + `FrameBrowser.tsx` + `roster.ts` (+ reorder test).**
  htm→JSX conversions with mutations flowing through props; `roster.setRosterOptions`
  writes the shared `#roster-numbers` datalist via `api.fetchRoster`; frame fetches via
  `api` (`fetchFrames`, `frameUrl`). Typed `useRef` on the canvas/filmstrip refs.
- **task5 — `StatusBar.tsx` + `RunSelector.tsx` + `BackendSettings.tsx`.** Three
  parity conversions; `BackendSettings` keeps its `.backend-settings*` classes, reads/
  writes via `backend-url.ts` and probes `api.checkHealth`.
- **task6 — capture page (5 components).** `CaptureApp`, `CameraPreview`,
  `CaptureControls`, `RosterUpload`, `SourceSelector`. `getUserMedia` stays in a
  `useEffect` keyed on `active` with teardown on `active=false`/unmount; capture fetches
  via `api` (`checkHealth`, `postFrame`, `uploadRoster`). Internal reducer/state kept as
  the old file had it (not frozen), now typed.
- **task7 — I/O layer: `api.ts` + `backend-url.ts` + `download.ts` (+ backend-url
  test).** Every request routes through `BASE()=getBackendUrl()` (prepended once in
  `_fetch`); wire contract untouched (D5/NFR2); responses typed via the `types.ts`
  payload interfaces. `backend-url.ts` reads `window.COLLECTION_CONFIG?.BACKEND_URL` +
  the `wtnc_backend_url` cookie. Ported 23-case suite.
- **task8 — `ResultsApp.tsx` + `state.ts` (+ state test).** Reducer typed
  `(State, Action) => State`, keeping the `POLL_RESULTS` derive-in-reducer and the
  identical-`hash` ⇒ same-object bail (NFR1). `ResultsApp` threads props to every child
  through their **frozen `*Props`**, so JSX call-sites are now type-checked (the htm
  blind spot closes, FR16).
- **task9 — integration (Wave C).** Filled `collect.tsx`/`view.tsx` entries; wired
  `collect.html`/`view.html` (classic `/config.js` then module entry, FROZEN-5); moved
  `config.js` verbatim to `public/config.js` (copied to `dist/config.js`, unhashed,
  operator-editable with no rebuild); `.gitignore` for `dist/` + `node_modules/`; the
  single `app.py` `StaticFiles` line now serves `frontend/dist` (FROZEN-7); deleted the
  entire old `.js`/`.d.ts`/`vendor` world; `npm run build`; and updated
  `frontend/README.md`, `CLAUDE.md` (FE section), `run.sh`, and top-level `README.md`.

## Gates (final combined tree, independently re-verified)

- **FE** `npm run check` — `tsc --noEmit` exit 0; unit **7 suites / 140 tests**
  (`card-badges` 6, `data` 71, `timeline` 9, `format` 12, `sidebar-reorder` 4,
  `backend-url` 23, `state` 15), stable across repeated runs.
- **FE** `npm run build` — emits `dist/` with the three page HTML bundles + hashed
  `assets/` JS/CSS + **unhashed `config.js`**; `npm run preview` serves `/`,
  `/collect.html`, `/config.js` (HTTP 200).
- **Backend** `.venv/bin/pytest` — **317 passed**; the one-line `StaticFiles` change is
  the only Python edit and no test asserted the old mount path.
- **SC4** — grep clean: no `.js` FE source (only `public/config.js` remains,
  intentional), no `vendor/`, no `htm`, no `preact-setup.js`, no `@param {import(...)}`,
  no `allowJs`/`checkJs` in `tsconfig`.
- **SC2** — a deliberately mistyped prop at a JSX call-site fails `npm run check`
  (`TS2322`); reverted, tree clean again — proving parents now type-check their children.

## Deviations logged during the run

- **Vite 8, not the design's Vite 5.** OQ-D1 said pin the *latest stable*; that is
  Vite 8.1.5 (with `@preact/preset-vite` 2.10.6), which satisfies Node 25.6.1's engine
  range and builds/installs clean. Recorded in `tasks/README.md` FROZEN-3.
- **`format.ts` implemented in Wave A, not stubbed.** `Card.tsx` (task1's reference)
  calls `formatTimeOfDay` at render, so the card test needed a real body. task3 owns
  `format.ts` but reconciled it read-only rather than re-filling an empty stub — it
  matched `format.js` byte-for-byte and gained no new exports.
- **`vite.config.ts` uses `vitest/config`** for a typed `test` block, and
  **`resolve.extensions`** puts `.ts`/`.tsx` before `.js` so the coexisting old `.js`
  sources were never resolved during Waves A→B. Both invisible to `tsc`; noted in
  FROZEN-3. `vitest.setup.ts` ended up empty (happy-dom supplies `document`/`window`
  globally, resolving the OQ-D2 spike) — later test-porters needed no manual DOM install.

No agent flagged a frozen contract as genuinely wrong; all Wave B tasks coded against
the frozen surfaces without divergence, and no CSS classes were added (parity reused
existing classes).

## Issues found and resolved during the run

- **Transient parallel-wave typecheck errors.** Because the seven Wave B agents ran
  concurrently in a shared tree, each `tsc` snapshot caught siblings mid-edit — agents
  variously reported errors in `results/data.ts:194`, `FrameBrowser.tsx`, and
  `ResultsApp.tsx`. The final combined tree is clean (140/140, tsc exit 0), verified
  independently rather than trusting per-agent reports. This is the normal race of
  agents running `tsc` at different moments, not a contract defect.

## Remaining manual verification (browser — not automatable headlessly)

Run against a real back-end after `npm --prefix collection/frontend ci && npm --prefix
collection/frontend run build` + `./collection/run.sh`:

- **Landing / serve** — `:8000` landing loads; both page links present.
- **Viewer** (`/view.html`) — timeline (packs/gaps/time labels); card → sidebar; edit a
  number (✎ badge persists across reload); reorder sticks; candidates toggle; CSV/JSON
  download.
- **Collector** (`/collect.html`) — camera Start → `getUserMedia` preview + frame posts;
  Stop; video-file source plays and sends frames; roster CSV upload populates
  autocomplete.
- **Frame browser** — scrubber + ←/→ step; add manual crossing (✚ badge appears in
  timeline).
- **SC6 runtime re-point (no rebuild)** — edit `dist/config.js` `BACKEND_URL`,
  hard-reload, confirm BackendSettings reflects it; revert.
- **SC5 HMR** — `npm run dev` at `:5173`, edit a component label, confirm hot reload
  without a full refresh.

## Notes

- Checkpoints landed directly on `main` per the run decision; the pre-existing
  `specs/FUTURE.md` edit and the local `.claude/` artifacts were left out of the
  commits.
- Per the workflow, the final step after the manual pass is moving
  `specs/jsdoc-to-ts/` under `specs/completed/`.
</content>
</invoke>
