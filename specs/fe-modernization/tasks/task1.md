# task1 — Scaffold & frozen contracts (Wave A · blocking)

**Model:** sonnet. **Blocks:** all other tasks. Nothing in Wave B starts until this lands
and `npm run check` is green.

## Goal
Create the FE dev toolchain skeleton, the vendored Preact runtime, the single frozen
type surface (`types.d.ts`), and a **typechecking stub for every file** Wave B will fill —
so all imports resolve and `tsc` is incremental from the first parallel task.

## Exclusive files (all NEW)
```
collection/frontend/
  package.json           package-lock.json          tsconfig.json
  types.d.ts
  vendor/preact.module.js   vendor/preact-hooks.module.js   vendor/htm.module.js
  vendor/preact-setup.js    vendor/vendor.md
  tests/setup-dom.js
  # stubs (bodies filled by Wave B; task1 creates them exporting the right symbols):
  api.js
  components/results/{ResultsApp,state,Timeline,Card,Sidebar,FrameBrowser,StatusBar,RunSelector,format,roster}.js
  components/capture/{CaptureApp,SourceSelector,CameraPreview,CaptureControls,RosterUpload}.js
```

## Do
1. **`package.json`** exactly per design §10 (`type:module`, scripts `typecheck`/`unit`/
   `check`, devDeps `typescript` + `happy-dom`). `unit` =
   `node --test --import ./tests/setup-dom.js tests/*.test.js`. Run `npm install` to
   produce `package-lock.json`. **devDependencies only** — no runtime deps.
2. **`tsconfig.json`** exactly per design §10 (`allowJs`+`checkJs`+`noEmit`+`strict`,
   `moduleResolution:bundler`, `lib:["ES2022","DOM"]`, `include:["**/*.js","types.d.ts"]`,
   `exclude:["vendor/**","node_modules"]`).
3. **Vendor** Preact 10, preact/hooks, htm 3 as pinned ESM into `vendor/` (curl from
   esm.sh/unpkg), record provenance in `vendor.md` (design §4). Author `preact-setup.js`
   exactly per design §5, with lightweight `@type` JSDoc on the re-exports so `html`,
   `useState`, etc. carry usable signatures downstream (design §10 last ¶).
4. **`types.d.ts`** — the single frozen type surface. Declare, verbatim from design §8/§9:
   - `Result`, `CandidateResult`, `Pack`, `Lane` (FROZEN-1).
   - `State`, `Action` (union of all 12 action shapes) (FROZEN-4).
   - one props `@typedef` per component in FROZEN-5 (`TimelineProps`, `PackProps`,
     `CardProps`, `CandidateCardProps`, `GapSeparatorProps`, `SidebarProps`,
     `FrameBrowserProps`, `StatusBarProps`, `RunSelectorProps`, `SourceSelectorProps`,
     `CameraPreviewProps`, `CaptureControlsProps`, `RosterUploadProps`).
5. **`tests/setup-dom.js`** per design §10 (happy-dom globals: `window`, `document`,
   `customElements`).
6. **Stubs** — each stub imports from `../../vendor/preact-setup.js`, annotates its
   `@param` with the matching `types.d.ts` typedef, and returns `html\`\`` (or `null` for
   `ResultsApp`/`CaptureApp` roots). `api.js`/`state.js`/`format.js`/`roster.js` export
   the FROZEN-6/2/3/8 named symbols with `throw new Error("stub")` bodies typed to the
   frozen return. Goal: **`npm run typecheck` passes on the skeleton.**

## Acceptance
- `npm ci` from a fresh state works; `npm run check` is green (typecheck passes;
  `node --test` runs with zero/na test files).
- `vendor/` is the only place third-party code lives; `git diff` shows vendored files
  segregated (NFR5).
- Nothing under `../backend/`, `run.sh`, `index.html`, `config.js`, or `results/data.js`
  is touched.

## Flag, don't diverge
If any design §8/§9 signature can't be expressed as a sound typedef, **stop and flag** —
do not weaken it; every Wave B task depends on it.
