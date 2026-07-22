# followup_3 — Tighten `@type {any}` casts across the FE

**Model:** sonnet. **Depends on:** fe-modernization shipped (task9). **Runs parallel with**
followup_1 and followup_3 via disjoint file ownership (see below).

## Problem
The Preact port leans on ~41 `@type {any}` casts. Many launder a known shape through `any`
purely to satisfy `tsc` at a `` html`…` `` boundary or a config/DOM read, discarding real
type-checking. Replace the avoidable ones with the actual types from `types.d.ts` /
`results/data.d.ts`.

Current distribution (informational — files owned by followup_1/_2 are handled there):
`Sidebar.js` 10 · `FrameBrowser.js` 12 · `CaptureApp.js` 4 · `tests/state.test.js` 6 ·
`StatusBar.js` 1 · `api.js` 1 · (`Card.js` 2 → followup_1, `ResultsApp.js` 5 → followup_2).

## Standard — how to tighten (apply judgement, don't churn)
- Prefer annotating the real typedef: `/** @type {import('../../types').Result} */` /
  `CandidateResult` / `State` / `Action` / prop interfaces, or `import('../../results/data')`
  shapes. A `props` object typed via its `XxxProps` interface removes most casts.
- For `window.COLLECTION_CONFIG` reads, cast **once** to a small typed accessor rather than
  sprinkling `(window).COLLECTION_CONFIG` `any`s.
- For genuinely dynamic values (JSON straight off `fetch`, event targets, canvas contexts)
  a narrow cast is fine — but narrow it (`HTMLImageElement`, `HTMLInputElement`,
  `CanvasRenderingContext2D`, a payload typedef) instead of `any`. Leave a one-line comment
  where `any` genuinely must stay.
- **Do not** change runtime behaviour, prop names, or the frozen contracts. This is a
  types-only pass. If tightening a type reveals a real contract mismatch, **stop and flag**
  it rather than widening the type back to `any`.

## Do
Work through the owned files below, replacing avoidable `any` casts per the standard, and add
missing typedefs to `types.d.ts` only if a shared shape is currently untyped (e.g. the
`/status` or `/frames` payloads, if that removes several `any`s cleanly). Keep each edit
small and locally verifiable with `npm run typecheck`.

## Exclusive / owned files
```
components/results/Sidebar.js       ← MODIFIED
components/results/FrameBrowser.js   ← MODIFIED
components/results/StatusBar.js      ← MODIFIED
components/capture/CaptureApp.js     ← MODIFIED
api.js                               ← MODIFIED
tests/state.test.js                  ← MODIFIED
types.d.ts                           ← MODIFIED (only to ADD shared typedefs; see note)
```
Do **not** touch `Card.js` (followup_1) or `ResultsApp.js`/`Timeline.js`/`styles.css`
(followup_2). Those tasks tighten the `any`s in the files they already own.

> **Coordination note (types.d.ts):** followup_2 may also edit `types.d.ts` (only if it adds
> `TimelineProps.onBrowseFrames`). Keep edits here additive and in a different region; if both
> land, resolve the trivial merge. Recommended order if run as a wave: followup_2 → followup_3.

## Acceptance
- `npm run check` green (typecheck + all tests).
- Net `@type {any}` count in the owned files is substantially reduced; each remaining `any`
  has a one-line justification comment. No runtime/behaviour change (SC-parity intact).
