# task1 — Scaffold: `backend-url.js`, types, stubs (Wave A, blocking)

**Model:** sonnet · **Gate:** must land and `npm run check` green (with stubs) before Wave B.

Source of truth: `../requirements.md`, `../design.md` (§2, §3), `tasks/README.md`
(FROZEN-1, FROZEN-6). Run FE commands from `collection/frontend/`.

## Owns (exclusive)
- `collection/frontend/backend-url.js` — **full implementation**
- `collection/frontend/tests/backend-url.test.js` — unit test (node --test)
- `collection/frontend/types.d.ts` — add typedefs
- `collection/frontend/components/common/BackendSettings.js` — **stub only** (task3 fills)
- `collection/frontend/components/results/download.js` — **stub only** (task2 fills)

## Do

1. **`backend-url.js`** — implement FROZEN-1 exactly (design §3):
   - `normalizeBackendUrl(raw)`: `String(raw ?? '').trim()`, then strip a single trailing `/`.
   - `getBackendUrl()`: read cookie `wtnc_backend_url` from `document.cookie`; if present,
     `normalizeBackendUrl(decodeURIComponent(value))`; else `normalizeBackendUrl(window.COLLECTION_CONFIG?.BACKEND_URL ?? '')`.
   - `setBackendUrl(url)`: `const v = normalizeBackendUrl(url)`; write
     `wtnc_backend_url=<encodeURIComponent(v)>; path=/; max-age=31536000; SameSite=Lax`
     (an empty `v` still writes an empty override, which resolves to same-origin); then call
     every subscriber with `v`.
   - `onBackendUrlChange(cb)`: add to an in-module `Set`; return an unsubscribe closure.
   - `backendLabel(url)`: `''` → `'same-origin'`; else try `new URL(url).host` (fallback to the
     raw string if unparseable).
   - Pure module — no Preact import, no top-level side effects beyond declaring the Set.

2. **`tests/backend-url.test.js`** (`node --test`, uses the happy-dom shim already wired in
   `tests/setup-dom.js`): cover `normalizeBackendUrl` (blank, trailing slash, whitespace),
   cookie round-trip (`setBackendUrl` then `getBackendUrl`), default fallback when no cookie,
   `backendLabel` (`''`, a full URL), and that `onBackendUrlChange` fires on `setBackendUrl`
   and stops after unsubscribe. Reset `document.cookie` between cases.

3. **`types.d.ts`** — add `export interface BackendSettingsProps {}` and (optional)
   `export type ExportFormat = 'csv' | 'json';`. Do not alter existing typedefs.

4. **Stubs** so Wave B imports resolve and `tsc` is incremental:
   - `components/common/BackendSettings.js`:
     ```js
     import { html } from '../../vendor/preact-setup.js';
     /** @param {import('../../types').BackendSettingsProps} _props */
     export function BackendSettings(_props) { return html`<div class="backend-settings"></div>`; }
     ```
   - `components/results/download.js`:
     ```js
     /** @param {string} _run @param {'csv'|'json'} _format @returns {Promise<void>} */
     export async function downloadResults(_run, _format) { /* task2 fills */ }
     ```

## Done when
- `npm run check` (typecheck + unit) is green, including the new `backend-url` suite.
- `backend-url.js` matches FROZEN-1 names/signatures; stubs export the exact symbols Wave B imports.
- No other files touched; no `styles.css` edits.
