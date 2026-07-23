# task2 — `results/data.ts` de-quarantine + `data` test port (Wave B)

**Model:** sonnet (haiku-ok — mechanical, but the strict-typing spots need care) ·
**Depends on:** task1. **Parallel with:** task3–task8.

Source of truth: `../requirements.md` (FR13, NFR6, SC3) + `../design.md` §8, §12 +
`tasks/README.md` FROZEN-6, FROZEN-4. All paths under `collection/frontend/`.

## What you own

- `results/data.ts` — fill the task1 stub with the real, strict conversion of `results/data.js`.
- `tests/data.test.ts` — port `tests/data.test.js`.

Do **not** edit `results/data.js` or `results/data.d.ts` (task9 deletes both).

## Steps

1. **Port the body (FROZEN-6).** Convert every export of `results/data.js` to strict TS,
   keeping names/signatures: `resultsFromCrossings`, `candidatesToResults`, `sortByOrder`,
   `sortDescending`, `mergeCandidates`, `groupIntoPacks(results, gapSeconds)`,
   `computeLanes(results, { laneOrder })`, `UNKNOWN_CATEGORY`. Return `Result`,
   `CandidateResult`, `Pack`, `Lane` from `types.ts` — `import type { … } from '../types'`.

2. **Fix the quarantine spots — types only, behavior identical:**
   - `Date` subtraction → `a.time.getTime() - b.time.getTime()` everywhere TS rejects
     `Date` arithmetic (behavior-identical).
   - Widened literals: `isCandidate: false`, `category: "Unknown"` etc. must land as the
     literal types `Result`/`CandidateResult` declare — annotate the constructed object with
     its interface, or use `as const` / satisfy the discriminant. `UNKNOWN_CATEGORY` should
     carry `"Unknown"` (e.g. `as const`) so `category` stays the literal type.
   - Loose `any` payload params (the malformed-input boundary) → `unknown` or a typed input
     shape so the edge-case tests still compile and run. Narrow before use.

3. **Port the test (FROZEN-4).** `tests/data.test.js` → `tests/data.test.ts`: `vitest`
   imports, keep `node:assert/strict`, import from `'../results/data'`, drop `@ts-nocheck`.
   **Assertions unchanged in substance** — this suite is the regression net proving the
   transform outputs are identical (SC3/NFR6). If a genuine behavioral change is needed to
   type-check, **stop and flag it** — that would violate NFR6.

## Definition of done

- `npm run typecheck` passes; `npm run unit` passes with `data.test.ts` green.
- `results/data.ts` has no `any`-typed public surface and no `@ts-nocheck`; the sidecar's job
  (shielding loose spots) is now done at the source.

## Do NOT

- Change any runtime output of `data` functions. Add/rename fields on the data shapes.
- Edit `types.ts`, the old `.js`/`.d.ts`, or any other task's files.
</content>
