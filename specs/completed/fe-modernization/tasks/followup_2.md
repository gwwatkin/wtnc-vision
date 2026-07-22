# followup_2 — "Browse frames" button when there are no crossings

**Model:** sonnet. **Depends on:** fe-modernization shipped (task9). **Runs parallel with**
followup_1 and followup_3 — see *Exclusive files* (no overlap).

## Problem
The frame browser (`FrameBrowser`) is only reachable from a crossing's sidebar via
**View frames**. When a run has **no crossings yet**, there is no selected item, so there is
no way to open the browser at all — an operator can't inspect frames / manually add the
first crossing. We need an always-available entry point.

## Background (already in place — no new plumbing needed)
- `OPEN_BROWSER` takes an `anchorTs`; `state.browser = { open, anchorTs }`
  (`components/results/state.js`).
- `FrameBrowser` accepts `anchorTs: string | null`
  (`components/results/FrameBrowser.js:258,270`).
- `api.fetchFrames` already tolerates a null anchor — it simply omits the `center` query
  param (`api.js:94`), so the backend returns the most recent frames. **So opening with
  `anchorTs: null` is safe and needs no api/backend change.**

## Do
1. **`ResultsApp.js`** — add a **"Browse frames"** button to the results toolbar
   (`.results__toolbar`, next to the candidates toggle) that dispatches
   `{ type: 'OPEN_BROWSER', anchorTs: null }`. It must be enabled regardless of crossing
   count (that's the whole point). Reuse the existing `onCreateCrossing` wiring already
   passed to `FrameBrowser` so adding the first crossing from the browser works.
   - While in this file, tighten its `@type {any}` casts (see followup_3 standard) — e.g.
     the `window.COLLECTION_CONFIG` reads and the inline dispatch param annotations.
2. **`Timeline.js`** *(optional but preferred)* — in the empty state
   (`.timeline__empty`, "No crossings yet — waiting for riders…") add a secondary affordance
   or leave the toolbar button as the sole entry point. If you add one here it must call a
   passed-in callback (keep `Timeline` presentational — no dispatch inside it); thread a new
   optional `onBrowseFrames` prop from `ResultsApp` and add it to `TimelineProps` in
   `types.d.ts`. If this complicates the frozen `TimelineProps`, **prefer the toolbar-only
   solution** and skip the Timeline change.
3. **`styles.css`** — style the new toolbar button consistently with existing toolbar
   controls (reuse existing classes if possible; add a minimal class only if needed).

## Exclusive / owned files
```
components/results/ResultsApp.js  ← MODIFIED
components/results/Timeline.js     ← MODIFIED (only if adding the empty-state affordance)
styles.css                         ← MODIFIED (button styling)
types.d.ts                         ← MODIFIED (only if adding TimelineProps.onBrowseFrames)
```
Do **not** touch `Card.js` (followup_1) or the type-only files owned by followup_3
(`Sidebar.js`, `FrameBrowser.js`, `StatusBar.js`, `CaptureApp.js`, `api.js`). `FrameBrowser`
itself needs no change — reuse its existing null-anchor support.

> **Coordination note (types.d.ts):** followup_3 also edits `types.d.ts`. To avoid a
> conflict, followup_2 touches `types.d.ts` **only** if it adds `TimelineProps.onBrowseFrames`;
> if it does, land followup_2 before followup_3 starts, or have followup_3 rebase. Prefer the
> toolbar-only solution to keep `types.d.ts` out of this task entirely.

## Acceptance
- With a run that has **zero** crossings, the operator can open the frame browser from the
  toolbar and add the first crossing.
- `npm run check` green. Existing timeline/component tests still pass. Add a small assertion
  (extend `tests/timeline.test.js` only if you added `onBrowseFrames`; otherwise a manual
  note in the PR is fine since the toolbar button lives in `ResultsApp`).
