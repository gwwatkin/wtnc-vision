# task1 — Scaffold: toolchain, `types.ts`, Card reference + stub the tree (Wave A, blocking)

**Model:** sonnet · **Blocks:** all of Wave B. Nothing else starts until this lands and
`npm run check` is green.

Source of truth: `../requirements.md` + `../design.md` (§1, §3, §4, §7, §10, §12) +
`tasks/README.md` (FROZEN-1…8). All paths under `collection/frontend/`.

## Goal

Stand up the Vite + Vitest + TypeScript toolchain, convert the frozen type surface and **one
reference component end-to-end**, and **stub every other source module** so the parallel
converters in Wave B start against a green, incremental `tsc`.

## What you own

Create/replace: `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`,
`types.ts`, `vitest.setup.ts`, `components/results/Card.tsx` (full), `tests/card-badges.test.ts`
(full), and a **stub** for every module in FROZEN-8. Delete `vendor/`.

## Steps

1. **Dependencies (FROZEN-3).** Add `preact` as a dependency; `vite`,
   `@preact/preset-vite`, `vitest`, `typescript`, `happy-dom` as devDependencies. Pin the
   latest stable Vite + a compatible `@preact/preset-vite` (OQ-D1; confirm no Node-25
   conflict). Run `npm install` so `package-lock.json` is regenerated and committed. Replace
   the `package.json` `scripts` with the six in FROZEN-3.

2. **`vite.config.ts` (FROZEN-3).** `defineConfig` with `plugins: [preact()]`,
   `build.outDir: 'dist'`, `build.rollupOptions.input: { index: 'index.html',
   collect: 'collect.html', view: 'view.html' }`, and the `test` block
   (`environment: 'happy-dom'`, `setupFiles: ['./vitest.setup.ts']`,
   `include: ['tests/**/*.test.ts']`). Default `publicDir: 'public'` (task9 populates it).

3. **`tsconfig.json` (FROZEN-3).** Add `jsx: "react-jsx"`, `jsxImportSource: "preact"`,
   `types: ["vite/client"]`; **remove `allowJs` and `checkJs`**; keep `strict`, `noEmit`,
   `target ES2022`, `module ESNext`, `moduleResolution "bundler"`, `lib ["ES2022","DOM"]`,
   `skipLibCheck`. Set `include: ["**/*.ts", "**/*.tsx"]`, `exclude: ["dist","node_modules"]`.
   (No more `results/data.js` / `vendor` excludes — the old `.js` are simply not `.ts`.)

4. **`types.ts` (FROZEN-2).** Copy `types.d.ts` **verbatim in shape** to `types.ts`; it is
   already all `export interface`/`export type`. Adjust only the header comment (drop the
   "referenced via JSDoc `import('../types')`" note). Do **not** weaken any shape. Leave the
   old `types.d.ts` in place (task9 deletes it).

5. **Delete `vendor/`.** Remove `vendor/preact.module.js`, `preact-hooks.module.js`,
   `htm.module.js`, `preact-setup.js`, `vendor.md`. Nothing in the `.ts`/`.tsx` world may
   import them (the old `.js` still do, but they are out of `tsc`'s scope — harmless).

6. **Reference component — `components/results/Card.tsx` (FROZEN-1, full).** Convert
   `Card.js` (both `Card` and `CandidateCard`) to JSX exactly per the FROZEN-1 rules:
   import `formatTimeOfDay` from `./format`, `import type { CardProps, CandidateCardProps,
   Result, CandidateResult } from '../../types'`; `crossing as Result` / `candidate as
   CandidateResult`; `class=`, `style={{ gridColumn: column }}`, `onClick={onClick}`;
   badges as `{cond ? <span …/> : null}`; **identical DOM/classes/text**. This is the
   pattern every Wave B agent copies — make it clean.

7. **Reference test — `tests/card-badges.test.ts` (FROZEN-4, full).** Port
   `card-badges.test.js`: `describe/it` from `vitest`, keep `node:assert/strict`,
   `import { h, render } from 'preact'`, import `Card` from `'../components/results/Card'`,
   drop `@ts-nocheck`. Assertions unchanged.

8. **`vitest.setup.ts` (OQ-D2 spike).** Port `tests/setup-dom.js`, then test whether Vitest's
   `environment: 'happy-dom'` already provides `document`/`window` so the manual global
   install can be dropped. Keep only the residue that is actually needed (possibly an empty
   file). **Record the outcome** in the task summary so Wave B test-porters know whether the
   setup file matters.

9. **Stub every other module (FROZEN-8).** For each listed module create the new
   `.ts`/`.tsx` with correct types but a placeholder body:
   - **component `.tsx`:** `export function Name(props: NameProps) { return <div />; }`
     (and any named sibling exports the frozen contracts require, e.g. `Pack`/`GapSeparator`
     from `Timeline.tsx`, `CandidateCard` is already real in `Card.tsx`).
   - **logic `.ts`:** export each frozen signature (FROZEN-6 for `data`, `api`/`backend-url`
     surfaces from the `page-split` design, `format`/`roster`/`download`/`state`) with a
     typed placeholder body — a typed empty return or `throw new Error('stub: <name>')`.
   - **entries `collect.tsx`/`view.tsx`:** minimal stub (task9 fills).
   Goal: every extension-less import across the tree resolves and `tsc` passes. Stubs must
   **type-check**, not run.

10. **Freeze the conventions.** Ensure `tasks/README.md` FROZEN-1…8 match what you actually
    scaffolded (Card pattern, import paths, script names, config.js decision). If reality
    forced a deviation, **update the README and flag it** — do not let siblings code against
    a stale contract.

## Definition of done

- `npm run check` (i.e. `tsc --noEmit` + `vitest run`) is **green**: Card slice fully
  converted, card-badges test passing, all stubs type-checking, no `vendor/` imports in
  `.ts`/`.tsx`.
- `package-lock.json` committed; `npm ci` reproduces.
- Task summary records: pinned Vite/preset versions, the `vitest.setup.ts` OQ-D2 outcome,
  and any README/contract deviations.

## Do NOT

- Touch any back-end file, `styles.css`, `config.js`, or the HTML entries (task9).
- Delete any old `.js` source or `types.d.ts` (task9 deletes them).
- Implement real bodies for anything except `Card.tsx`, `types.ts`, and the ported test.
</content>
