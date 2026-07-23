# task4 — Sidebar + FrameBrowser + roster helper + reorder test (Wave B)

**Model:** sonnet · **Depends on:** task1 (uses stubbed `api.ts`, `roster.ts`, `types.ts`).
**Parallel with:** task2, task3, task5–task8.

Source of truth: `../design.md` §9, §10 + `tasks/README.md` FROZEN-1, FROZEN-2, FROZEN-4.
All paths under `collection/frontend/`.

## What you own

- `components/results/Sidebar.tsx` — fill.
- `components/results/FrameBrowser.tsx` — fill.
- `components/results/roster.ts` — fill (`setRosterOptions` datalist helper, no JSX).
- `tests/sidebar-reorder.test.ts` — port `tests/sidebar-reorder.test.js`.

## Steps

1. **`roster.ts`.** Convert `roster.js`: `setRosterOptions(run)` calls `api.fetchRoster(run)`
   then writes `<option>`s into the shared static `#roster-numbers` datalist. Import from
   `../../api` (extension-less). Strict types; no JSX.

2. **`Sidebar.tsx` (FROZEN-1).** Convert `Sidebar.js` to JSX. `import type { SidebarProps }
   from '../../types'`; hooks from `preact/hooks`; call the async `api` functions
   (`postEdit`, `deleteEdit`, `reorderCrossing({ earlierId, laterId })`, `promoteCandidate`,
   `dismissCandidate`) through the props (`onEdit`/`onDelete`/`onReorder`/… — do not import
   `api` directly if the old file went through props). Preserve number inputs bound via
   `list="roster-numbers"`. Byte-for-byte DOM parity.

3. **`FrameBrowser.tsx` (FROZEN-1).** Convert `FrameBrowser.js` to JSX. `import type
   { FrameBrowserProps } from '../../types'`; hooks from `preact/hooks`; frame fetches via
   `api` (`fetchFrames`, `frameUrl`) exactly as today. Preserve DOM/classes and the
   number-input datalist binding.

4. **Port the test (FROZEN-4).** `sidebar-reorder.test.js` → `.test.ts`: `vitest` imports,
   keep `node:assert/strict`, `import { h, render } from 'preact'`, extension-less component
   imports, drop `@ts-nocheck`. Assertions unchanged. Follow task1's `vitest.setup.ts`
   decision.

## Definition of done

- `npm run typecheck` passes; `npm run unit` passes with `sidebar-reorder.test.ts` green.
- Sidebar edit/delete/reorder and FrameBrowser render + datalist binding are byte-for-byte
  parity with the htm originals.

## Do NOT

- Edit `api.ts`, `types.ts`, `styles.css`, or any other task's files. Flag any missing CSS
  class to task9.
</content>
