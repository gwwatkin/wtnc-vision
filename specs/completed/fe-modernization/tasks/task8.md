# task8 — ResultsApp: state model, reducer, poll loop (Wave B)

**Model:** sonnet. **Depends on:** task1. Codes against the **frozen** §9 child contracts
(FROZEN-5) and §7 api surface (FROZEN-6) — **not** their implementations, so this runs in
parallel with task3/4/5/7. Parity source: `results/results.js` (the orchestrator).

## Exclusive files (fill task1 stubs)
```
components/results/ResultsApp.js
components/results/state.js       → initialState, reducer, deriveView, action creators (pure)
tests/state.test.js               → NEW
```

## Do
1. **`state.js`** (pure, no Preact, no DOM) — `State`/`Action` per FROZEN-4:
   - `initialState`.
   - `reducer(state, action)` handling all 12 actions (FROZEN-4). `POLL_RESULTS` carries
     `{ crossings, candidates, hash }`; if `hash === state.lastPayloadHash` **return the
     same `state` object** (Preact bails the re-render — NFR2/SC5). Otherwise store raw
     `crossings`/`candidates`/`hash` and recompute `packs`+`lanes` via `deriveView`.
     `TOGGLE_CANDIDATES` re-derives from the retained raw arrays.
   - `deriveView(crossings, candidates, candidatesVisible)` **exactly per FROZEN-2**
     (`mergeCandidates`? → `sortByOrder` → `groupIntoPacks(_,3)` → `computeLanes(_,{laneOrder:null})`).
   - a small pure `hashPayload(resultsJson, candidatesJson)` = string compare key over the
     raw JSON (NFR2 note — **no** SHA/`crypto.subtle`).
2. **`ResultsApp`** — no props. `useReducer(reducer, initialState)`. A `useEffect` poll
   loop on `RESULTS_POLL_MS`: `fetchRuns` once + on demand; per tick `fetchResults` +
   `fetchCandidates` → `resultsFromCrossings`/`candidatesToResults` (data.js) →
   `dispatch(POLL_RESULTS,{crossings,candidates,hash})`; `fetchStatus` →
   `dispatch(POLL_STATUS)`. Errors → `dispatch(POLL_ERROR)`. Compose:
   `RunSelector` (`runs`, `selectedRun`, `SELECT_RUN`), `StatusBar` (`statusPayload`),
   candidate toggle (`TOGGLE_CANDIDATES`), `Timeline` (`packs`, `lanes`, `candidatesVisible`,
   `selectedId`, `onSelect → OPEN_SIDEBAR/SELECT_ITEM`), `Sidebar` (from `state.sidebar`,
   wiring `onEdit/onDelete/onPromote/onDismiss` to `api.js` **then** re-poll/refresh,
   `onStepFrame → STEP_FRAME`, `onOpenBrowser → OPEN_BROWSER`), `FrameBrowser` (from
   `state.browser`, `onCreateCrossing → api.postManualCrossing` then refresh).
   ResultsApp is the **only** place mutations + refresh live (FR13) — the old
   `wtnc:edited` event and JSON-diff DOM skip must not reappear (SC5).
3. **`tests/state.test.js`** (`node --test`) — reducer transitions + `deriveView`
   (FR8/FR13): identical `hash` ⇒ same object reference (no-op); changed payload ⇒
   packs/lanes recomputed; `TOGGLE_CANDIDATES` flips candidate inclusion via the retained
   raw arrays; selection/sidebar/browser open/close transitions. Uses only `state.js` +
   `data.js` (both importable now) — passes in Wave B.

## Acceptance
- `npm run typecheck` passes; `npm run unit` green (state tests). The no-op-on-identical-
  hash path is asserted by reference equality.
- No `wtnc:edited`, no serialized-JSON DOM-diff skip, no `reapplySelectionHighlight` (SC5).

## Do not
Touch `data.js`, child component files, `api.js`, or `styles.css`. If a §9 child prop is
genuinely insufficient to wire a behavior, **stop and flag** — do not widen it silently.
