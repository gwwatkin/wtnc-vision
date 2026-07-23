# Tasks — JSDoc → TypeScript (JSX, npm deps, Vite bundler)

The map for the parallel-agent run. **Read this before spawning any agent.** Source of
truth is `../requirements.md` + `../design.md`; this file adds the dependency graph,
execution waves, exclusive-file ownership, and the **frozen contracts** every task codes
against.

## The shape of this port

This is a *conversion*, not a green-field build: every `.js` under `collection/frontend/`
becomes `.ts`/`.tsx`. The rule (design §13) is **replace, never edit**:

- Wave A (scaffold) creates the toolchain, `types.ts`, converts **one reference component
  end-to-end** (`Card.tsx`) + its test, and **stubs every remaining source module** as a
  correctly-typed `.ts`/`.tsx` so all cross-module imports resolve and `tsc` is incremental
  from the first parallel task (the same enabling move as `fe-modernization` task1).
- Wave B tasks **fill the stubs** — each converts the real body of the old `.js` into the
  new `.tsx` it owns, coding against `types.ts` + the frozen conversion rules.
- The old `.js` sources are **left untouched** the whole time and are **deleted in Wave C**
  (task9), together with `vendor/` residue, `.d.ts` sidecars, and the old `.test.js` files.
  A half-converted tree therefore never ships.

`tsc` only sees `.ts`/`.tsx` (Wave A drops `allowJs`/`checkJs` — FROZEN-3), so the old `.js`
files sitting alongside the new `.tsx` are invisible to the gate and harmless.

## Execution waves

| Wave | Tasks | Model | Gate |
|------|-------|-------|------|
| **A — Scaffold (blocking)** | task1 | sonnet | `npm run check` green (Card slice + all stubs) before Wave B starts |
| **B — Parallel convert** | task2 · task3 · task4 · task5 · task6 · task7 · task8 | sonnet (task2 haiku-ok) | each passes `npm run typecheck`; task2/3/4/7/8 also `npm run unit` for the suites they port |
| **C — Integration** | task9 | sonnet | `npm run build` **and** `npm run check` green + backend pytest + parity checklist + docs |

```
        task1  (toolchain + tsconfig(jsx) + types.ts + Card.tsx ref + card test
                + vitest.setup + STUB every other source module; delete vendor/)
          │
   ┌──────┼──────┬──────┬──────┬──────┬──────┐
 task2  task3  task4  task5  task6  task7  task8       ← Wave B (exclusive file owners)
 data   Timeline Sidebar Status capture  api/    ResultsApp
 +test  +format  +Frame  +Run   /*      backend  +state
        +tests  +roster  +Backd         -url/dl  +test
   └──────┴──────┴──────┴──────┴──────┴──────┘
          │
        task9  (entries collect/view.tsx + HTML + config.js + app.py dist mount
                + .gitignore + delete all old .js/vendor/sidecars + build + parity + docs)
```

Every Wave B task fills stubs task1 created; task8 (`ResultsApp`) renders its children
through their **frozen prop contracts** (FROZEN-2), not their implementations, so it is
Wave-B-parallel-safe.

## Delegation protocol (per CLAUDE.md)

- Give each agent its `taskN.md` **plus** `requirements.md` + `design.md` as source of truth.
- **Contracts are frozen for this run.** An agent that believes a frozen signature is
  genuinely wrong must **stop and flag it**, never silently diverge — siblings depend on it.
- One wave at a time; **gate each wave on explicit human go-ahead**; commit + push a
  checkpoint between waves. Keep subagent scratch/artifacts out of commits.
- FE commands use **node/npm from `collection/frontend/`** (`npm run typecheck`,
  `npm run unit`, `npm run check`). The Python back-end and its venv rules are **untouched**
  except task9's single `StaticFiles` line (design §6) — use `.venv/bin/pytest` from repo
  root for that one test, never `source … && …`.
- **Do not touch the CV engine, frame pipeline, `models.py`, `config.py`, the `runs/`
  layout, the wire contract, or any endpoint** — this spec only changes how the FE is
  *authored and served* (requirements D4/D5/NFR2).

## Exclusive file ownership

Paths are under `collection/frontend/` unless noted. "Fills" = replace the task1 stub body
with the real conversion of the identically-named old `.js`.

| Task | Owns (creates / fills) |
|------|------------------------|
| task1 | `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, `types.ts`, `vitest.setup.ts`, `components/results/Card.tsx` (**full**), `tests/card-badges.test.ts` (**full**); **STUB** every other module listed in FROZEN-8; delete `vendor/` |
| task2 | `results/data.ts` (fill, de-quarantine §8), `tests/data.test.ts` (port) |
| task3 | `components/results/Timeline.tsx` (fill; `Pack`+`GapSeparator` live here), `components/results/format.ts` (fill), `tests/timeline.test.ts` (port), `tests/format.test.ts` (port) |
| task4 | `components/results/Sidebar.tsx` (fill), `components/results/FrameBrowser.tsx` (fill), `components/results/roster.ts` (fill), `tests/sidebar-reorder.test.ts` (port) |
| task5 | `components/results/StatusBar.tsx` (fill), `components/results/RunSelector.tsx` (fill), `components/common/BackendSettings.tsx` (fill) |
| task6 | `components/capture/CaptureApp.tsx`, `CameraPreview.tsx`, `CaptureControls.tsx`, `RosterUpload.tsx`, `SourceSelector.tsx` (fill all 5) |
| task7 | `api.ts` (fill), `backend-url.ts` (fill), `components/results/download.ts` (fill), `tests/backend-url.test.ts` (port) |
| task8 | `components/results/ResultsApp.tsx` (fill), `components/results/state.ts` (fill), `tests/state.test.ts` (port) |
| task9 | `collect.tsx`, `view.tsx` (fill), `index.html`, `collect.html`, `view.html`, `public/config.js` (relocate), `.gitignore`, `collection/backend/app.py` (1 line) + its test, `collection/frontend/README.md`, `../../CLAUDE.md`, `run.sh`/`README.md` docs; **deletes** all old `.js`, `vendor/`, `results/data.d.ts`, old `tests/*.test.js`, `tests/setup-dom.js`, `config.js` at old path |

No two Wave-B tasks share a file. `config.js` content is **unchanged**; only task9 moves it.

---

## FROZEN-1 · htm → JSX conversion rules (design §9)

Every component converts its render body from an htm tagged template to JSX. `Card.tsx`
(task1) is the worked reference; match it exactly.

- **Automatic JSX runtime** — **no `h`/`html` import** in components. Delete every
  `import … from '../../vendor/preact-setup.js'`. The `react-jsx` runtime with
  `jsxImportSource: "preact"` (tsconfig, FROZEN-3) injects the factory.
- **Import hooks from `preact/hooks`** (`useState`, `useEffect`, `useReducer`, `useRef`,
  `useMemo`, `useCallback`); **`render`, `Fragment`, `createContext` from `preact`**.
- **Keep `class`, not `className`** (OQ5) — Preact accepts it; smaller, exact-parity diff.
  All standard DOM attrs/events stay verbatim (`onClick`, `for`, `onInput`, `style`, …).
- **Props typed by annotation**: `export function Timeline({ … }: TimelineProps) { … }`
  importing the interface from `types.ts` (FROZEN-2). No JSDoc `@param`.
- **Inline casts** `/** @type {X} */ (v)` → `v as X`. `CardProps.crossing`/`candidate` are
  typed `object`; cast to `Result`/`CandidateResult` as `Card.tsx` does.
- **Fragments** → `<>…</>` (or `Fragment` from `preact`). Conditionals `cond ? <…/> : null`.
- **Rendered DOM is byte-for-byte identical** — same tags, classes, attribute values,
  handler wiring, text. This is re-syntaxing, not restyling (FR11/G5). If parity forces a
  new CSS class, **flag it to task9** (owns `styles.css`); do not add classes silently.

## FROZEN-2 · `types.ts` surface (design §10)

task1 renames `types.d.ts` → `types.ts` **verbatim in shape**: the file already uses
`export interface`/`export type`, so it is a copy-move (drop the "referenced via JSDoc
`import('../types')`" header note). **Shapes do not weaken** (FR10): `Result`,
`CandidateResult`, `Pack`, `Lane`, `State`, the `Action` union, every `*Props` interface,
and the additive payload/`CollectionConfig`/`ExportFormat` typedefs stay exactly as in
`types.d.ts` today.

Consumers switch from `import('../../types').XxxProps` JSDoc to real imports:

```ts
import type { CardProps, Result } from '../../types';   // components: ../../types
import type { State, Action }    from './types';        // root-level modules: ./types
```

New this spec: JSX call-sites are type-checked, so a parent passing a wrong prop through
`<Timeline …/>` fails `tsc` — the htm blind spot is closed (FR16). Keep prop names exact.

## FROZEN-3 · Toolchain surface (design §1, §4) — task1 owns, everyone runs

`package.json` scripts (the only commands any task should invoke for the FE):

```
dev       → vite                                 build     → vite build
preview   → vite preview                         typecheck → tsc --noEmit
unit      → vitest run                           check     → npm run typecheck && npm run unit
```

- **deps:** `preact`; **devDeps:** `vite`, `@preact/preset-vite`, `vitest`, `typescript`,
  `happy-dom`. Pin the latest stable Vite + a compatible `@preact/preset-vite` at scaffold
  time (OQ-D1); commit the lockfile so `npm ci` reproduces.
- **`vite.config.ts`** — `preact()` plugin; `build.rollupOptions.input` = the three HTML
  entries `{ index, collect, view }` (multi-page, FR12); `test` block =
  `{ environment: 'happy-dom', setupFiles: ['./vitest.setup.ts'], include: ['tests/**/*.test.ts'] }`.
  **Also:** `resolve.extensions: ['.mjs', '.mts', '.ts', '.tsx', '.js', '.jsx', '.json']`
  (TS/TSX before JS) — required because the old `.js` files coexist with the new `.ts`/`.tsx`
  during Waves A→B; Vite's default order resolves `.js` first, which would pull in the
  vendor-importing originals and break tests. **Import using `vitest/config` not `vite`** so
  the `test` block is typed. Note: `format.ts` carries a real implementation (not a stub)
  because `Card.tsx` (the Wave A reference) calls `formatTimeOfDay` at render time and the
  card-badges test must pass. Task3 owns `format.ts` and will verify/fill it in Wave B.
- **`tsconfig.json`** — add `"jsx": "react-jsx"`, `"jsxImportSource": "preact"`,
  `"types": ["vite/client"]`; **remove `allowJs`, `checkJs`**; keep `strict`, `noEmit`,
  `moduleResolution: "bundler"`; `include: ["**/*.ts", "**/*.tsx"]`, `exclude: ["dist",
  "node_modules"]`. `tsc --noEmit` remains the sole type authority (Vite/esbuild does not
  type-check).

## FROZEN-4 · Test harness (design §12) — Vitest

The 8 suites port with **assertions unchanged**; only the harness swaps. Per file:

- `import { describe, it } from 'node:test'` → `from 'vitest'`. Keep
  `import assert from 'node:assert/strict'` (works under Vitest) — do **not** rewrite
  assertions to `expect`.
- `import { h, render } from '../vendor/preact-setup.js'` → `from 'preact'`.
- Component import extension `.js` → extension-less (`'../components/results/Card'`).
- Remove `// @ts-nocheck`; the ported test must type-check. Rename `*.test.js` → `*.test.ts`.
- **`happy-dom` globals** (OQ-D2): Vitest `environment: 'happy-dom'` supplies `document`/
  `window` globally, so `tests/setup-dom.js`'s manual install is likely unnecessary. task1
  spikes this against the Card test: `vitest.setup.ts` shrinks to whatever residue remains
  (possibly empty). task1 decides and records the outcome; later ports follow it.

## FROZEN-5 · Runtime config injection (design §7, OQ-D3) — task9 owns

`config.js` stays a **classic, non-module `<script>` run before the entry module**, so
`window.COLLECTION_CONFIG` exists at boot; it is **never bundled** (deploy state, FR7/SC6).
Resolution of OQ-D3: **`config.js` moves to `collection/frontend/public/config.js`**
(Vite's default `publicDir`), copied verbatim to `dist/config.js`, referenced as
`/config.js`. The operator edits the deployed `dist/config.js` post-build with **no
rebuild** (SC6). Content is unchanged. `backend-url.ts` reads it exactly as today. Page HTML:

```html
<script src="/config.js"></script>                        <!-- classic, un-bundled -->
<script type="module" src="/collect.tsx"></script>        <!-- Vite hashes on build -->
```

`index.html` is the static landing (no config, no module) but **stays a Vite input** so it
lands in `dist/` (OQ-D4).

## FROZEN-6 · `data.ts` de-quarantine (design §8) — task2 owns

`results/data.js` + `results/data.d.ts` collapse into one strict `results/data.ts`.
**Type change only; runtime output identical** (NFR6/SC3) — the ported `data.test.ts` is
the regression net and passes unchanged in substance. Fix the loose spots at the source:

- `Date` subtraction (`a.time - b.time`) → `a.time.getTime() - b.time.getTime()`.
- Widened literals (`isCandidate: false`, `category: "Unknown"`) → annotate with the literal
  types the frozen `Result`/`CandidateResult` shapes declare, or `as const`.
- Loose `any` payload params → `unknown`/typed-input at the boundary so the malformed-input
  edge-case tests still compile and run.

Exports keep their names/signatures (`resultsFromCrossings`, `candidatesToResults`,
`sortByOrder`, `sortDescending`, `mergeCandidates`, `groupIntoPacks`, `computeLanes`,
`UNKNOWN_CATEGORY`).

## FROZEN-7 · Entries, mount & the one back-end line (design §6, §7) — task9 owns

- `collect.tsx` → `render(<CaptureApp />, document.getElementById('capture-root')!)`;
  `view.tsx` → `render(<ResultsApp />, document.getElementById('results-root')!)`.
  (Preserves the `page-split` mount shape / roots / `#roster-numbers` datalist.)
- **`app.py` (design §6): the only Python edit.** Point `StaticFiles` at `…/frontend/dist`
  instead of `…/frontend`. Update the Python test that asserts the mount dir. **No** route,
  payload, or handler change.
- `dist/` and `node_modules/` are **git-ignored** (OQ1/NFR4); `npm ci && npm run build` is a
  documented one-time deploy prerequisite (run after FE edits). Node builds the FE; Python
  still *serves* it — `run.sh`'s Python path is unchanged.

## FROZEN-8 · Stub inventory (task1 creates; Wave B fills)

task1 creates each of these as a **correctly-typed** stub so imports resolve and `tsc`
passes. A component stub returns minimal valid JSX (e.g. `return <div />;`) annotated with
its `*Props`; a logic-module stub exports the frozen signatures with placeholder bodies
(`throw new Error('stub')` or a typed empty return) — enough to type-check, not to run.
`Card.tsx` and `types.ts` are **fully implemented** by task1, not stubbed.

```
STUB (component .tsx):  Timeline, Sidebar, FrameBrowser, RunSelector, StatusBar,
                        ResultsApp   (components/results/)
                        BackendSettings  (components/common/)
                        CaptureApp, CameraPreview, CaptureControls, RosterUpload,
                        SourceSelector   (components/capture/)
STUB (logic .ts):       api, backend-url            (frontend root)
                        data, format, roster, download, state   (results helpers)
STUB (entry .tsx):      collect, view               (root; task9 fills)
FULL (task1):           types.ts, components/results/Card.tsx, tests/card-badges.test.ts,
                        vitest.setup.ts
```

## Shared conventions

- **Replace, never edit** the old `.js` — every Wave B task creates/fills the new `.ts`/`.tsx`
  and leaves the sibling `.js` alone; task9 deletes all old files at the end.
- **No new CSS classes / no `styles.css` edits** in Wave B — reuse existing classes for
  parity; if parity genuinely needs a class, flag it to task9.
- **No back-end, engine, `config.py`, `models.py`, or `runs/` edits** — task9's single
  `app.py` line is the only Python touch.
- Every new/filled FE module passes `npm run typecheck` before its task is done; the tasks
  that port a suite also keep `npm run unit` green for it.

---
</content>
</invoke>
