# Frontend — FE Developer Guide

The front end is a **Preact 10 + TypeScript + Vite** application. Source lives in
`collection/frontend/`; `npm run build` emits `dist/` which FastAPI serves via its
`StaticFiles` mount. No Node is on the serving path — Node is a build-time tool only.

---

## Layout

```
collection/frontend/
  index.html                    Landing page — links to collect.html and view.html only
  collect.html                  Collector page — mounts CaptureApp (#capture-root)
  view.html                     Viewer page — mounts ResultsApp (#results-root)
  collect.tsx                   Entry for collect.html: render(<CaptureApp />, #capture-root)
  view.tsx                      Entry for view.html:   render(<ResultsApp />, #results-root)
  backend-url.ts                Cookie-backed runtime base-URL store
                                  getBackendUrl / setBackendUrl / onBackendUrlChange /
                                  normalizeBackendUrl / backendLabel
  api.ts                        Fetch layer — ALL calls route through BASE()=getBackendUrl()
  styles.css                    Single stylesheet (dark theme, no framework)
  types.ts                      Frozen shared types: State, Action, Pack, Lane,
                                  and every component's Props interface
  tsconfig.json                 tsc check-only config (strict, noEmit, jsx=react-jsx)
  vite.config.ts                Vite multi-page build + Vitest test config
  package.json                  npm deps: preact (runtime); vite, @preact/preset-vite,
                                  typescript, vitest, happy-dom (devDeps)
  package-lock.json             Lockfile — commit; npm ci reproduces exactly

  public/
    config.js                   Classic script — sets window.COLLECTION_CONFIG;
                                  copied verbatim to dist/config.js (not bundled);
                                  operator-editable post-build with no rebuild

  components/
    common/
      BackendSettings.tsx       Shared collapsible URL editor + health indicator
                                  Rendered on both Collector and Viewer; no props (self-contained)
    capture/
      CaptureApp.tsx            Root: source select, capture loop, roster upload, BackendSettings
      SourceSelector.tsx        Camera / video toggle
      CameraPreview.tsx         getUserMedia stream (owns its own stream ref)
      CaptureControls.tsx       Label input + Start/Stop button + status
      RosterUpload.tsx          CSV upload + status feedback
    results/
      ResultsApp.tsx            Root: reducer, poll loop, all mutation handlers + BackendSettings
      state.ts                  Reducer + initialState + deriveView + hashPayload
      Timeline.tsx              Timeline grid + Pack + GapSeparator (one file)
      Card.tsx                  Crossing card + Candidate card
      format.ts                 formatTimeOfDay + formatGapLabel (pure, tested)
      Sidebar.tsx               Detail overlay: edit/delete/frame-step
      FrameBrowser.tsx          Frame scrubber overlay (add manual crossing)
      StatusBar.tsx             Pipeline status readout
      RunSelector.tsx           Run drop-down
      roster.ts                 setRosterOptions — populates #roster-numbers datalist
      download.ts               downloadResults(run, format) — blob→anchor download

  results/
    data.ts                     Pure data transforms (resultsFromCrossings, sortByOrder, …)

  tests/
    card-badges.test.ts         Component test: Card badges under happy-dom
    data.test.ts                Pure-logic tests for results/data.ts (102 cases)
    timeline.test.ts            Component test: Timeline renders under happy-dom
    format.test.ts              Unit tests for format.ts
    backend-url.test.ts         Unit tests for backend-url.ts
    sidebar-reorder.test.ts     Unit tests for Sidebar reorder logic
    state.test.ts               Unit tests for state.ts reducer

  dist/                         Build output (git-ignored) — produced by npm run build
    index.html
    collect.html
    view.html
    config.js                   Unhashed — verbatim copy of public/config.js
    assets/
      collect-<hash>.js
      view-<hash>.js
      styles-<hash>.css
      …                         Other hashed chunks (shared code split by Rollup)
```

> **Multi-page entries.** `collect.tsx` and `view.tsx` are the two JS entry points.
> `index.html` is the static landing page (no entry module). Vite bundles all three HTML
> files; Rollup hashes the JS/CSS assets automatically.

> **`config.js` is never bundled.** It lives in `public/` so Vite copies it verbatim to
> `dist/config.js`. The operator can edit `dist/config.js` after a build to change
> `BACKEND_URL` or other tuning values — no rebuild required (SC6). Page HTML loads it
> as a classic (synchronous, non-module) `<script>` before the entry module so
> `window.COLLECTION_CONFIG` is set at boot.

---

## Running the checks

One-time install (first clone, or after updating `package-lock.json`):

```bash
npm --prefix collection/frontend ci
```

Then (from the repo root):

| Command | What it does |
|---|---|
| `npm --prefix collection/frontend run check` | **The gate** — typecheck then unit tests. Run before every commit. |
| `npm --prefix collection/frontend run typecheck` | `tsc --noEmit` alone — catches contract/prop mismatches early. |
| `npm --prefix collection/frontend run unit` | Vitest alone — fast logic + component tests (140 cases). |
| `npm --prefix collection/frontend run build` | Produce `dist/` for the backend to serve. |
| `npm --prefix collection/frontend run dev` | Vite HMR dev server (requires a running backend at the configured URL). |
| `npm --prefix collection/frontend run preview` | Serve `dist/` locally for a quick smoke-test after build. |

No Python venv is needed for the FE checks. Nothing is emitted by `check` or `typecheck` —
`tsc` runs in `--noEmit` mode. `build` writes `dist/`.

Expected output on a clean run: `tsc` exits 0 (no output), Vitest reports 140 tests
passed in under 1 s.

---

## Types and contracts

### Where they live

`types.ts` is the single source of truth for shared types:

- **`State`** and **`Action`** — the results-page reducer state.
- **`Pack`** and **`Lane`** — data shapes from `results/data.ts`.
- **Per-component props interfaces** — `TimelineProps`, `CardProps`, `SidebarProps`, etc.

Consumers import directly:

```ts
import type { CardProps, Result } from '../../types';   // from a component
import type { State, Action }    from './types';         // from a root-level module
```

### How to extend a type

1. Add or update the interface in `types.ts`.
2. Update the component's props destructuring annotation:
   ```ts
   export function MyComponent({ value, onChange }: MyComponentProps) { … }
   ```
3. Run `npm --prefix collection/frontend run typecheck` — tsc flags any callers that
   violate the new shape, including JSX prop call-sites.

### JSX call-site checking (SC2)

Unlike the old htm-based approach, tsc now checks every JSX call-site. Passing a
wrong prop name (e.g. `aktive` instead of `active`) produces a compile error:

```
error TS2322: Property 'aktive' does not exist on type 'IntrinsicAttributes & CaptureControlsProps'.
  Did you mean 'active'?
```

`npm run typecheck` (or `npm run check`) is the gate.

---

## Runtime config injection

`public/config.js` sets `window.COLLECTION_CONFIG` before the entry module runs.
Both `collect.html` and `view.html` load it as the first classic script:

```html
<script src="/config.js"></script>                        <!-- classic, un-bundled -->
<script type="module" src="/collect.tsx"></script>        <!-- Vite hashes on build -->
```

`index.html` has no config or entry module — it is purely static HTML.

To change runtime settings after a deploy (e.g. point at a different backend):
1. Edit `dist/config.js` — update `BACKEND_URL` or any other key.
2. Hard-reload the page in the browser.
3. No rebuild needed.

---

## Adding a component

1. Create `components/<page>/MyComponent.tsx`.
2. Import Preact primitives:
   ```ts
   import { useState, useEffect } from 'preact/hooks';
   // render and Fragment come from 'preact' if needed in an entry
   ```
   JSX is injected automatically by the `@preact/preset-vite` plugin — no `h` import.
3. Define a props interface in `types.ts`:
   ```ts
   export interface MyComponentProps {
     value: string;
     onChange: (v: string) => void;
   }
   ```
4. Annotate the component:
   ```ts
   import type { MyComponentProps } from '../../types';
   export function MyComponent({ value, onChange }: MyComponentProps) { … }
   ```
5. Use `class` (not `className`) for CSS classes — Preact accepts it and keeps the diff
   byte-for-byte parity with the original HTML.
6. Wire it into its parent component via JSX: `<MyComponent value={x} onChange={fn} />`.
7. Run `npm --prefix collection/frontend run check` to verify typecheck + tests pass.
   If the component carries logic, add a test in `tests/` (see `card-badges.test.ts` as
   a template for component tests under happy-dom).

---

## Updating an npm dependency

```bash
npm --prefix collection/frontend install --save-exact preact@10.x.y
npm --prefix collection/frontend run check    # typecheck + tests must stay green
npm --prefix collection/frontend run build    # confirm dist/ still emits correctly
```

Commit both `package.json` and `package-lock.json`. `npm ci` in CI/deploy reproduces
the exact locked versions.
