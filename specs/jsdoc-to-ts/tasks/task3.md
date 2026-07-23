# task3 — Timeline + format helpers + their tests (Wave B)

**Model:** sonnet · **Depends on:** task1 (uses the real `Card.tsx` + stubbed `format.ts`).
**Parallel with:** task2, task4–task8.

Source of truth: `../design.md` §9, §10 + `tasks/README.md` FROZEN-1, FROZEN-2, FROZEN-4.
All paths under `collection/frontend/`.

## What you own

- `components/results/Timeline.tsx` — fill. Contains `Timeline`, plus `Pack` and
  `GapSeparator` (they live in this module, per the ownership map).
- `components/results/format.ts` — fill (`formatTimeOfDay`, `formatGapLabel`, pure).
- `tests/timeline.test.ts` — port `tests/timeline.test.js`.
- `tests/format.test.ts` — port `tests/format.test.js`.

## Steps

1. **`format.ts`.** Convert `format.js`'s pure helpers to strict TS; no JSX. Signatures per
   `types.ts`/existing usage (`formatTimeOfDay(t: Date): string`,
   `formatGapLabel(t: Date): string`). Card and Timeline import from `./format`.

2. **`Timeline.tsx` (FROZEN-1).** Convert `Timeline.js` to JSX: `Timeline`, `Pack`,
   `GapSeparator`. Import `Card`/`CandidateCard` from `./Card` (already real), hooks from
   `preact/hooks` if used, `import type { TimelineProps, PackProps, GapSeparatorProps, Lane,
   Result, CandidateResult } from '../../types'`. Preserve the exact DOM: `.timeline` root
   with inline `style` `--lane-count`, `.lane-header[data-category]` per lane, column
   resolution passed to cards as `column`, `.gap-separator`, empty-state `.timeline__empty`.
   **Byte-for-byte parity** — re-syntaxing only.

3. **Port both tests (FROZEN-4).** `vitest` imports, keep `node:assert/strict`,
   `import { h, render } from 'preact'`, import components/helpers extension-less, drop
   `@ts-nocheck`, `.test.js` → `.test.ts`. Assertions unchanged. Follow task1's
   `vitest.setup.ts` decision for `happy-dom` globals.

## Definition of done

- `npm run typecheck` passes; `npm run unit` passes with `timeline.test.ts` +
  `format.test.ts` green.
- Rendered Timeline/Pack/Gap DOM matches the old htm output (classes, attrs, `--lane-count`,
  empty state).

## Do NOT

- Edit `Card.tsx`, `types.ts`, `styles.css`, or any other task's files. If parity needs a CSS
  class that doesn't exist, **flag it to task9** — don't add it.
</content>
