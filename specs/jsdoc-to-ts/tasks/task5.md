# task5 — StatusBar + RunSelector + BackendSettings (Wave B)

**Model:** sonnet · **Depends on:** task1 (uses stubbed `api.ts`, `backend-url.ts`,
`types.ts`). **Parallel with:** task2–task4, task6–task8.

Source of truth: `../design.md` §9, §10 + the `page-split` design for `BackendSettings` +
`tasks/README.md` FROZEN-1, FROZEN-2. All paths under `collection/frontend/`.

## What you own

- `components/results/StatusBar.tsx` — fill.
- `components/results/RunSelector.tsx` — fill.
- `components/common/BackendSettings.tsx` — fill.

(No test files — these three have no dedicated suite; parity is covered by task9's checklist.)

## Steps

1. **`StatusBar.tsx` (FROZEN-1).** Convert `StatusBar.js` to JSX. `import type
   { StatusBarProps } from '../../types'`. Byte-for-byte DOM parity.

2. **`RunSelector.tsx` (FROZEN-1).** Convert `RunSelector.js`. `import type
   { RunSelectorProps } from '../../types'`; `onChange` wiring verbatim (`onInput`/`onChange`
   exactly as the old file). Parity.

3. **`BackendSettings.tsx` (FROZEN-1).** Convert `BackendSettings.js` (page-split component).
   `import type { BackendSettingsProps } from '../../types'` (empty props — self-contained).
   It reads/writes the backend URL via `backend-url.ts` (`getBackendUrl`, `setBackendUrl`,
   `onBackendUrlChange`, `normalizeBackendUrl`, `backendLabel`) and probes `api.checkHealth`.
   Import hooks from `preact/hooks`; keep the `.backend-settings*` class names exactly.

## Definition of done

- `npm run typecheck` passes.
- All three components render byte-for-byte-identical DOM/classes to their htm originals;
  `BackendSettings` still reflects health state + backend-URL changes.

## Do NOT

- Edit `api.ts`, `backend-url.ts`, `types.ts`, `styles.css`, or any other task's files.
  Flag any missing CSS class to task9.
</content>
