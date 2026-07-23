# Requirements — JSDoc → TypeScript: JSX, npm deps, bundler

## 1. Background & Purpose

The front-end (`collection/frontend/`, ~3,600 lines across 23 source modules) is written
as plain `.js` with JSDoc types, served **buildless**: FastAPI's `StaticFiles` mount
(`app.py:670`) hands the source tree to the browser, which runs it as native ES modules.
Preact + htm are **vendored** as ESM files (`vendor/*.module.js`); components render with
htm tagged-template literals; types live in a frozen `types.d.ts` and are enforced only by
a dev-time `tsc --noEmit` (`checkJs`, `strict`). This is exactly the shape the
`fe-modernization` spec deliberately chose (its D1 "no-build", D5 "Vite-ready is not a
goal", OQ4 "htm not JSX", D2 "deps vendored").

That stance has held up, but the project owner now wants the front-end on **idiomatic
TypeScript**: real `.tsx`/`.ts` sources, JSX instead of htm, npm-managed dependencies, and
a proper bundler — accepting the build step that entails. The driver is developer-facing:
first-class editor/tooling support, standard component authoring (JSX), and access to the
npm ecosystem when a component library or utility is eventually wanted.

**This spec explicitly supersedes** the `fe-modernization` no-build decisions for the
front-end. Per this repo's convention, "frozen" contracts are per-spec: a later spec may
edit an earlier one's decisions, and this one does. What it does **not** touch: the
back-end, the wire contract, or the *behavior* of either page.

This document is *what & why*. Because the feature is itself technical, the technology the
owner has already chosen (bundler adoption, Preact-retained, JSX, npm deps) is recorded
below as resolved decisions; everything still open (bundler/runner specifics, dev-vs-prod
serving mechanics, file-by-file conversion order, `data.js` handling) belongs in
`design.md`.

## 2. Goals

- **G1 — Idiomatic TypeScript sources.** Every front-end module is authored in `.ts`/
  `.tsx` with real type annotations; JSDoc `@param {import(...)}` / inline-cast typing is
  gone. The frozen type surface (`types.d.ts`) becomes real importable TS types.
- **G2 — JSX rendering.** Components render with JSX, not htm tagged templates. The htm
  dependency and the `preact-setup.js` shim are removed.
- **G3 — npm-managed dependencies + a bundler.** Preact and companions come from npm and
  are resolved/bundled by a build tool; the hand-vendored `vendor/*.module.js` files are
  deleted. A dev server gives fast iteration; a production build emits static assets.
- **G4 — Unchanged runtime serving model, from built output.** FastAPI still serves static
  files to the browser — but from the **build output**, not the source tree. The operator's
  run experience and the wire contract are unchanged.
- **G5 — Behavior & type-coverage parity.** This is a re-platforming, not a redesign: both
  pages (collect, view) look and behave identically before and after, and type coverage is
  no weaker than today's `strict` `checkJs` gate.

## 3. Resolved Decisions

Made by the product owner during scoping (this session):

- **D1 — Full idiomatic port.** Real `.tsx` JSX + npm deps + bundler — not a mechanical
  `.js`→`.ts` rename that keeps htm and vendored files. The design targets the idiomatic
  end state.
- **D2 — Stay on Preact, not React.** For this app (multi-page, no client router, no
  external component libraries, own `useReducer` state) Preact keeps its size advantage
  with no ecosystem cost; a `preact/compat` alias remains available as a future escape
  hatch if a React-only library is ever needed. Migrating to React (bundle size,
  `class`→`className` churn) buys nothing here.
- **D3 — A build step is accepted.** The front-end gains a bundle/transpile step and the
  browser is served built assets. This reverses `fe-modernization` D1/D5. Node becomes
  required to *build* the front-end; the design decides whether node is on the *run* path
  (OQ1).
- **D4 — This supersedes the no-build stance for the FE only.** The back-end, its tests,
  the Python workflow, `run.sh`'s Python side, and CLAUDE.md's Python rules are untouched.
- **D5 — Wire contract frozen.** No API/endpoint changes. The FE keeps polling the same
  routes with the same payloads; only how the FE is authored and served changes.
- **D6 — Behavior parity is the bar.** Same pages, same flows, same performance feel. No
  UX/feature changes ride along (they resume on top of the ported FE).

## 4. Key Facts (what already exists to build on)

- **A1 — Types are already written and enforced.** `types.d.ts` holds the frozen contracts
  (all component props, `State`, the 11-arm `Action` union, data shapes); `results/data.d.ts`
  is a sidecar for the quarantined pure module. `tsc --noEmit` runs `strict` + `checkJs`
  today, so the code is *already* fully type-checked. The port converts an existing,
  passing type surface — it does not invent types from scratch.
- **A2 — The FE is cleanly layered.** `results/data.js` is pure (no DOM, no fetch) with its
  own test suite. `api.js` / `backend-url.js` isolate all server I/O. Components are
  presentational, driven by the frozen props. This layering makes file-by-file conversion
  tractable.
- **A3 — Multi-page, no client router.** Three HTML entries — `index.html` (static landing,
  no script), `collect.html` → `collect.js`, `view.html` → `view.js`. The two app pages
  each mount a Preact root from their entry module. A bundler must produce **two entry
  bundles**, not one SPA.
- **A4 — Runtime config is injected, not bundled.** `config.js` is loaded as a classic
  `<script>` before the module entry and sets `window.COLLECTION_CONFIG`; `backend-url.js`
  (from `page-split`) lets the FE target an arbitrary backend URL at runtime. This
  injection pattern must survive bundling — config is deployment state, not build state.
- **A5 — The back-end serves the FE and is otherwise stable.** `StaticFiles` mount at
  `app.py:670`; endpoints are covered by Python tests. The mount path (which directory is
  served) is the single back-end line this spec expects to touch.
- **A6 — Tooling baseline exists.** `package.json` (dev-only: `typescript`, `happy-dom`),
  `tsconfig.json` (`checkJs`/`strict`/`noEmit`), and 8 test files run via
  `node --test --import ./tests/setup-dom.js`. Node 25 + npm 11 are on the dev machine.
- **A7 — `data.js` is deliberately quarantined.** It predates strict checking, is not
  `strict`-clean (Date arithmetic, widened literals), and is shielded by `data.d.ts` so
  consumers get its types without checking its body. Under a real bundler it will be
  transpiled directly — this quarantine must be resolved, not carried (OQ4).

## 5. Functional Requirements

### 5.1 Toolchain & build (G3, G4)
- **FR1** — `package.json` declares the bundler, dev server, TS, JSX/Preact preset, and
  test runner as dev dependencies, with a lockfile; `npm ci` reproduces the environment.
  Preact (and any runtime libs) are npm dependencies, not vendored files.
- **FR2** — A single documented command produces a production build: two page bundles
  (collect, view) plus assets, emitted to a build-output directory, with hashed/immutable
  asset names as the tool's default allows.
- **FR3** — A single documented command starts a dev server with fast rebuild/HMR for
  editing components against a running back-end.
- **FR4** — A single documented command runs the full check (type-check + tests); it needs
  only node + the manifest — no venv, no browser, no running back-end.
- **FR5** — The vendored runtime files (`vendor/*.module.js`, `preact-setup.js`) and the
  htm dependency are deleted; nothing imports them.

### 5.2 Serving (G4)
- **FR6** — FastAPI serves the FE from the **build output** directory, not the source tree.
  The served result is behavior-identical to today for the operator; the wire contract
  (A5) is unchanged.
- **FR7** — The runtime config injection (`config.js` → `window.COLLECTION_CONFIG`,
  `backend-url.js` targeting) keeps working against built bundles — config remains
  deployment-time state, editable without a rebuild.
- **FR8** — The operator's start-the-app story is documented end to end, including how the
  build output is produced/refreshed (the build-vs-commit decision is OQ1).

### 5.3 TypeScript & JSX port (G1, G2, G5)
- **FR9** — Every `.js` source (components, `api.js`, `backend-url.js`, stores, `collect.js`,
  `view.js`, `results/data.js`, format/roster/download/state helpers) becomes `.ts`/`.tsx`.
  JSDoc type annotations and inline `/** @type */` casts are replaced by native TS
  annotations and `as` casts.
- **FR10** — The frozen type surface in `types.d.ts` becomes real, importable TS types
  (module or ambient — design's call). Component prop types remain the enforced boundary
  between tasks; the shapes do not weaken.
- **FR11** — Component render bodies convert from htm tagged templates to JSX, wired to the
  Preact JSX runtime. Rendered DOM (tags, classes, attributes, event handlers) is
  unchanged (G5).
- **FR12** — The two page entries (`collect.js`, `view.js`) become TS entry modules the
  bundler consumes; `index.html`/`collect.html`/`view.html` reference the built entry
  assets (directly or via the dev server), preserving the multi-page structure (A3).
- **FR13** — `results/data.js`'s quarantine is resolved: it is ported to typed TS and made
  `strict`-clean (its `data.d.ts` sidecar folds away), **without** changing its runtime
  behavior — its existing test suite must pass unchanged (OQ4 picks the exact approach).
- **FR14** — The old `.js` sources and the JSDoc/`checkJs` scaffolding (`allowJs`,
  `checkJs`, the `.d.ts` sidecars) are removed in the same iteration; the end state is
  single-implementation, no dead files, no mixed idiom.

### 5.4 Tests (G5)
- **FR15** — All existing tests (pure-logic `data` suite, component tests, format/state/
  timeline/etc.) are ported to run against the TS sources under the chosen runner, with
  assertions no weaker than today. The `data` suite in particular passes unchanged in
  substance (regression net for FR13).
- **FR16** — Type-checking is part of the check gate (FR4): a component reading a prop
  absent from its declared type, or a call-site passing the wrong props, fails the check —
  and unlike today's htm blind spot, **JSX call-sites are now type-checked too** (a
  strict improvement over the current gate).

### 5.5 Docs (G4)
- **FR17** — The FE developer docs (`collection/frontend/README.md`) are updated: new
  layout, how to run dev server / build / checks, how the multi-page entries and runtime
  config work, how to add a component, and how deps are now managed via npm.
- **FR18** — CLAUDE.md's FE guidance is updated to describe the TS/bundler workflow
  (superseding the vendored/no-build description), as a sibling to the untouched Python
  rules.

## 6. Non-Functional Requirements

- **NFR1 (Runtime parity)** — First meaningful render of either page is not perceptibly
  worse than today. The production bundle stays lean (Preact-class footprint); no
  regression in poll-tick render economy (Preact VDOM diff still elides no-op updates).
- **NFR2 (Back-end isolation)** — The back-end, its tests, and the Python workflow are
  untouched save the single `StaticFiles` directory change (FR6). CLAUDE.md's Python rules
  are unchanged (D4).
- **NFR3 (Dev ergonomics)** — Edit a component → see it via HMR/fast rebuild against a
  running back-end (FR3). The check gate (FR4) runs in seconds so it can gate every change.
- **NFR4 (Reviewability)** — The diff is dominated by mechanical conversion; generated
  build output is git-ignored (or, if committed per OQ1, clearly segregated) so human
  review stays on source.
- **NFR5 (Parity provable)** — Where parity matters (both pages' live flows: timeline,
  sidebar edit/reorder, frame browser, candidate toggle, status; capture camera/video/
  roster; export/download; backend-URL settings), tasks include explicit manual
  verification against a real run, not just unit tests.
- **NFR6 (No behavioral drift in `data.js`)** — FR13's retyping/cleanup changes types only;
  the transform outputs are identical, proven by the unchanged `data` suite.

## 7. Scope

### 7.1 This phase
- Bundler + dev server + npm dependency management; production build; check gate (G3, FR1–FR5).
- FastAPI serving from build output; runtime-config injection preserved (G4, FR6–FR8).
- Full `.ts`/`.tsx` port with JSX of every FE module, including `data.js` de-quarantine;
  `types.d.ts` → real TS types; deletion of vendored files, htm, and JSDoc/`checkJs`
  scaffolding (G1, G2, FR9–FR14).
- Port of all tests to the new runner; type-check in the gate (FR15–FR16).
- FE README + CLAUDE.md updates (FR17–FR18).

### 7.2 Out of scope (captured for context)
- **Any UX/feature/visual change** — parity only (D6, G5). New features resume on the
  ported FE.
- **Back-end / API / wire-contract changes** beyond the single `StaticFiles` directory
  line (D5, NFR2).
- **Switching framework to React** (D2) — retained decision; only revisited if a concrete
  React-only dependency appears.
- **CI wiring** — there is no CI in this repo; the build + check commands are the
  deliverables, scheduling them elsewhere is a later concern.
- **E2E browser tests** (Playwright et al.) — still deferred, as in `fe-modernization`.
- **Linter/formatter toolchain** — still out (a separate spec can add it); the bundler's
  built-in TS handling is the only new tooling.
- **SSR / server rendering / import maps** — not relevant to this static-serve app.

## 8. Success Criteria

- **SC1** — From a fresh clone: `npm ci` then the build command emits two page bundles to
  the output dir; FastAPI serving that dir renders both pages at parity against a real run
  (FR2, FR6, NFR5).
- **SC2** — `npm run <check>` (type-check + tests) passes with no back-end running; a
  deliberately mistyped prop (wrong type, or wrong prop passed at a JSX call-site) fails it
  (FR4, FR16).
- **SC3** — The `data` test suite passes unchanged in substance after `data.js` is ported
  to strict TS; a deliberate transform-invariant breakage is still caught (FR13, FR15,
  NFR6).
- **SC4** — `grep` finds no remaining `.js` FE sources, no `vendor/`, no `htm`, no
  `preact-setup.js`, no JSDoc `@param {import(...)}` typing, and no `checkJs`/`allowJs`
  in `tsconfig` — the end state is single-idiom TS (FR5, FR9, FR14).
- **SC5** — Dev server starts, serves both pages against a running back-end, and reflects a
  component edit via HMR/fast rebuild (FR3, NFR3).
- **SC6** — Editing `config.js` / the backend URL at deploy time re-points a built bundle
  with no rebuild (FR7).
- **SC7** — The app still starts through the operator's documented flow (`run.sh` + the
  documented build step), and the FE README + CLAUDE.md describe the new workflow
  (FR8, FR17, FR18).

## 9. Open Questions (resolve before / during design)

- **OQ1 — Node on the run path vs. committed build output.** A build step exists (D3), but
  is the built output produced by `run.sh`/deploy (node required to run), committed to the
  repo (node required only to develop), or built manually before deploy? This trades
  "fresh Python-only clone runs the app" (today's FR4-equivalent) against a checked-in
  `dist/`. **Leaning:** git-ignore the build output; document a one-time `npm run build`
  as a deploy prerequisite; keep node off the *serving* path but accept it on the *build*
  path. Confirm at design.
- **OQ2 — Bundler & test-runner choice.** Vite + `@preact/preset-vite` + Vitest is the
  presumptive stack (dev server/HMR, native multi-entry, preact JSX + `preact/compat`
  alias, Vitest reuses the Vite config and today's `happy-dom` env). Design confirms and
  pins versions, or justifies an alternative (e.g. bare esbuild if the dev server is judged
  unnecessary).
- **OQ3 — Dev-mode back-end wiring.** With `backend-url.js` (A4) the dev server can target
  a separately-running FastAPI via the configured URL (no proxy), or a dev proxy can
  forward API routes. Design picks one and documents it.
- **OQ4 — `data.js` de-quarantine approach.** Port-and-fix to strict TS (preferred: single
  idiom, sidecar deleted) vs. keep loose with `// @ts-nocheck`-equivalent. FR13 prefers the
  former; design confirms the exact typing of its Date/literal rough edges without changing
  behavior (NFR6).
- **OQ5 — `class` vs `className` in JSX.** Preact accepts `class`, so JSX conversion can
  keep the existing attribute names verbatim (smaller diff). Design confirms keeping
  `class` (and standard DOM attrs) rather than a React-style `className` sweep.
- **OQ6 — Entry HTML & asset references.** How `collect.html`/`view.html` reference built
  entry bundles (Vite-managed HTML inputs with hashed assets, vs. fixed asset paths) and
  where `config.js` slots in relative to the module entry (must stay a pre-module classic
  script, A4). Design specifies the exact HTML shape for dev and prod.
