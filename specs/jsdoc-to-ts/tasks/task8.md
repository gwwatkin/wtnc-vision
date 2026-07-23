# task8 — ResultsApp + state reducer + state test (Wave B)

**Model:** sonnet · **Depends on:** task1. **Parallel with:** task2–task7.

`ResultsApp` is the results-page integrator: it imports nearly every results module. It is
Wave-B-safe because it codes against the **frozen prop/state contracts** (FROZEN-2), not the
sibling implementations — task1's stubs make all those imports resolve and type-check.

Source of truth: `../design.md` §9, §10 + `tasks/README.md` FROZEN-1, FROZEN-2, FROZEN-4.
All paths under `collection/frontend/`.

## What you own (fill)

- `components/results/ResultsApp.tsx`
- `components/results/state.ts` — reducer, `deriveView`, initial state.
- `tests/state.test.ts` — port `tests/state.test.js`.

## Steps

1. **`state.ts`.** Convert `state.js` to strict TS. `import type { State, Action, Result,
   CandidateResult, Pack, Lane } from '../../types'`; import the pure transforms from
   `./data` (`mergeCandidates`, `sortByOrder`, `groupIntoPacks`, `computeLanes`). Reducer
   typed `(state: State, action: Action): State`. Keep the `POLL_RESULTS` derive-in-reducer
   behavior and the identical-`hash` ⇒ **same state object** bail (Preact elides the
   re-render — NFR1). Behavior unchanged.

2. **`ResultsApp.tsx` (FROZEN-1).** Convert `ResultsApp.js` to JSX. `import type
   { ResultsAppProps } from '../../types'`; `useReducer` from `preact/hooks` over `state.ts`;
   render `<RunSelector/>`, `<StatusBar/>`, `<Timeline/>`, `<Sidebar/>`, `<FrameBrowser/>`,
   `<BackendSettings/>`, and the download control, threading props per FROZEN-2. Fetches go
   through `api.ts`; roster options via `roster.setRosterOptions`; export via `download.ts`.
   Byte-for-byte DOM parity. **JSX call-sites are now type-checked** — a wrong prop passed to
   any child fails `tsc` (this is the htm blind spot closing; keep prop names exact).

3. **Port the test (FROZEN-4).** `state.test.js` → `.test.ts`: `vitest` imports, keep
   `node:assert/strict`, import from `'../components/results/state'`, drop `@ts-nocheck`.
   Assertions unchanged — this guards the reducer's derive + bail behavior.

## Definition of done

- `npm run typecheck` passes; `npm run unit` passes with `state.test.ts` green.
- ResultsApp wiring type-checks against every child's real `*Props`; reducer behavior and
  DOM are parity.

## Do NOT

- Edit any child component, `api.ts`, `data.ts`, `types.ts`, `styles.css`, or other tasks'
  files. Flag any missing CSS class to task9.
</content>
