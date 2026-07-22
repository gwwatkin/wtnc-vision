# Frontend — FE Developer Guide

The front end is a **buildless Preact 10 + htm 3** application served by FastAPI's
`StaticFiles` mount. No bundler, no compilation step, no Node on the serving path.
`tsc` and the test runner are dev-only tools; running them does not produce or modify
any served file.

---

## Layout

```
collection/frontend/
  index.html                    Landing page — links to collect.html and view.html only
  collect.html                  Collector page — mounts CaptureApp (no results)
  view.html                     Viewer page — mounts ResultsApp (no capture)
  collect.js                    Entry for collect.html: render(h(CaptureApp,null), #capture-root)
  view.js                       Entry for view.html:   render(h(ResultsApp,null), #results-root)
  backend-url.js                Cookie-backed runtime base-URL store (FROZEN-1)
                                  getBackendUrl / setBackendUrl / onBackendUrlChange /
                                  normalizeBackendUrl / backendLabel
  api.js                        Fetch layer — ALL calls route through BASE()=getBackendUrl()
                                  (page-split: +exportUrl, +fetchExportBlob; frameUrl prepends BASE)
  styles.css                    Single stylesheet (dark theme, no framework)
  config.js                     Classic script — sets window.COLLECTION_CONFIG;
                                  BACKEND_URL is the default fallback when no cookie is set
  types.d.ts                    Frozen JSDoc contracts: State, Action, Pack, Lane,
                                  and every component's Props typedef
  tsconfig.json                 tsc check-only config (allowJs + checkJs + noEmit)
  package.json                  Dev toolchain (typescript + happy-dom only)

  vendor/
    preact-setup.js             Authored shim — the ONE import for all Preact primitives
    preact.module.js            Preact 10 ESM (pinned, vendored)
    preact-hooks.module.js      Preact hooks ESM (pinned, vendored)
    htm.module.js               htm 3 ESM (pinned, vendored)
    vendor.md                   Provenance record (name, version, source URL)

  components/
    common/
      BackendSettings.js        Shared collapsible URL editor + health indicator (FROZEN-6)
                                  Rendered on both Collector and Viewer; props = {} (self-contained)
    capture/
      CaptureApp.js             Root: source select, capture loop, roster upload, BackendSettings
      SourceSelector.js         Camera / video toggle
      CameraPreview.js          getUserMedia stream (owns its own stream ref)
      CaptureControls.js        Label input + Start/Stop button + status
      RosterUpload.js           CSV upload + status feedback
    results/
      ResultsApp.js             Root: reducer, poll loop, all mutation handlers + BackendSettings
      state.js                  Reducer + initialState + deriveView + hashPayload
      Timeline.js               Timeline grid + Pack + GapSeparator (one file)
      Card.js                   Crossing card + Candidate card
      format.js                 formatTimeOfDay + formatGapLabel (pure, tested)
      Sidebar.js                Detail overlay: edit/delete/frame-step
      FrameBrowser.js           Frame scrubber overlay (add manual crossing)
      StatusBar.js              Pipeline status readout
      RunSelector.js            Run drop-down
      roster.js                 setRosterOptions — populates #roster-numbers datalist
      download.js               downloadResults(run, format) — blob→anchor download (DOM here)

  results/
    data.js                     Pure data transforms (UNCHANGED from pre-port)
    data.d.ts                   Type stubs so tsc resolves data.js types

  tests/
    setup-dom.js                happy-dom globals (preloaded via --import)
    data.test.js                Pure-logic tests for results/data.js (102 cases)
    timeline.test.js            Component test: Timeline renders under Node
    backend-url.test.js         Unit tests for backend-url.js (normalise, cookie, label, subscribe)
```

> **`main.js` is gone.** The old entry that mounted both roots on a single page has been
> deleted. Each page now has its own entry (`collect.js` / `view.js`).

> **`api.js` routes every call through `BASE()`**, which reads the cookie-backed store
> from `backend-url.js`. No bare same-origin paths remain — `frameUrl` and all fetch
> calls prepend `BASE()`. The `BACKEND_URL` value in `config.js` is only the default
> fallback used by `backend-url.js` when no `wtnc_backend_url` cookie is set.

---

## Running the checks

One-time install (dev deps only — typescript + happy-dom):

```bash
npm ci
```

Then:

| Command | What it does |
|---|---|
| `npm run check` | **The gate** — typecheck then unit tests. Run this before every commit. |
| `npm run typecheck` | `tsc --noEmit` alone — catches contract/prop mismatches early. |
| `npm run unit` | `node --test` alone — fast logic + component tests. |

No back-end, browser, or venv is needed. Nothing is emitted or served — `tsc` runs in
`--noEmit` mode and the test runner uses Node's built-in `node:test` harness.

Expected output on a clean run: `tsc` exits 0 (no output), `node --test` reports all
tests passed (111 cases, < 1 s).

---

## Types and contracts

### Where they live

`types.d.ts` is the single source of truth for shared types:

- **`State`** and **`Action`** — the results-page reducer state (design §8 / FROZEN-4).
- **`Pack`** and **`Lane`** — data shapes from `results/data.js` (FROZEN-1).
- **Per-component props typedefs** — `TimelineProps`, `CardProps`, `SidebarProps`, etc.
  (design §9 / FROZEN-5).

Components are plain `.js` files. They reference these types via JSDoc rather than
redeclaring them:

```js
/** @param {import('../../types').TimelineProps} props */
export function Timeline(props) { … }
```

The import specifier is **extension-less** (`../../types`, not `../../types.d.ts`).
Writing the `.d.ts` suffix explicitly is a tsc error under `moduleResolution: bundler`.
`checkJs` then verifies each component's prop usage against the shared contract.

### How to extend a type

1. Add or update the props `@typedef` in `types.d.ts`.
2. Annotate the component's `@param` as above.
3. Run `npm run typecheck` — tsc will flag any callers that violate the new shape.

### The htm blind spot

`tsc` checks a component's *own* prop usage but **not** props threaded through
`html\`…\`` (htm tagged template) literals — those are opaque string calls to the
type checker. Keep prop names byte-exact with the typedef, and lean on
`tests/timeline.test.js` (and future component tests) for call-site wiring
verification. `main.js` uses `h(Component, null)` directly (not htm), so the mount
call-sites are fully checked.

---

## Adding a component

1. Create `components/<page>/MyComponent.js`.
2. Import Preact primitives from `../../vendor/preact-setup.js` (the one shim):
   ```js
   import { html, useState } from '../../vendor/preact-setup.js';
   ```
3. Define a props typedef in `types.d.ts`:
   ```ts
   /** @typedef {{ value: string, onChange: (v: string) => void }} MyComponentProps */
   ```
4. Annotate the component:
   ```js
   /** @param {import('../../types').MyComponentProps} props */
   export function MyComponent({ value, onChange }) { … }
   ```
5. Wire it into its parent component via `html\`<${MyComponent} .../>\``.
6. Run `npm run typecheck` to verify. If the component carries logic, add a test in
   `tests/` (see `timeline.test.js` as a template for component tests under happy-dom).

---

## Updating a vendored dependency

Vendored files are plain ESM committed as-is — no build step required.

To update (e.g. Preact 10.x → 10.y):

1. Download the new pinned ESM file from the CDN (esm.sh or unpkg):
   ```bash
   curl -o vendor/preact.module.js 'https://esm.sh/preact@10.y.z/dist/preact.module.js'
   curl -o vendor/preact-hooks.module.js 'https://esm.sh/preact@10.y.z/hooks/dist/hooks.module.js'
   ```
2. If the hooks shim changed its import path, update `vendor/preact-setup.js`
   accordingly (the single place all components import from).
3. Update the version and source URL in `vendor/vendor.md`.
4. Run `npm run check` — typecheck + tests must stay green.

No build tooling, no lock-file changes for vendored deps (those are tracked as source
files, not npm packages).
