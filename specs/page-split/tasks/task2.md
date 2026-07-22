# task2 — `api.js` rewiring + `download.js` (Wave B)

**Model:** sonnet · Depends on task1 (`backend-url.js`).

Source of truth: `../design.md` (§4, §6.2), `tasks/README.md` (FROZEN-2, FROZEN-3). This is
the crux fix from the requirements (FR8): today only 3 of ~15 calls honor the configurable
base. Run FE commands from `collection/frontend/`.

## Owns (exclusive)
- `collection/frontend/api.js`
- `collection/frontend/components/results/download.js` (fill task1's stub)

## Do — `api.js`

1. Import the store and re-source `BASE`:
   ```js
   import { getBackendUrl } from './backend-url.js';
   const BASE = () => getBackendUrl();     // replaces the COLLECTION_CONFIG.BACKEND_URL read
   ```
2. **Prepend `BASE()` once, in `_fetch`:** `const resp = await fetch(BASE() + url, init);`
   Keep the existing error handling. Every `_fetch` caller (`fetchRuns`, `fetchResults`,
   `fetchCandidates`, `fetchStatus`, `fetchFrames`, `fetchRoster`, `postEdit`, `deleteEdit`,
   `postManualCrossing`, `reorderCrossing`, `promoteCandidate`, `dismissCandidate`,
   `postFrame`, `uploadRoster`) now hits the configured base automatically.
3. **Remove** the manual `${BASE()}` from `postFrame` and `uploadRoster` (they call `_fetch`
   with `'/frames'` / `'/roster'`; the prefix is now added by `_fetch` — avoid double base).
4. `checkHealth`: `fetch(BASE() + '/health')` (keep the raw `fetch` + try/catch).
5. `frameUrl(run, filename)`: return `` `${BASE()}/frames/image?run=…&filename=…` `` (prepend
   `BASE()`; keep the encoding).
6. **Add** export helpers (FROZEN-3):
   ```js
   export function exportUrl(runLabel, format) {
     return `${BASE()}/results/export?run=${encodeURIComponent(runLabel)}&format=${encodeURIComponent(format)}`;
   }
   export async function fetchExportBlob(runLabel, format) {
     const resp = await _fetch(`/results/export?run=${encodeURIComponent(runLabel)}&format=${encodeURIComponent(format)}`);
     return resp.blob();
   }
   ```
   Keep JSDoc consistent with the file's style. **No** DOM in `api.js`.

After this, grep confirms no bare-path `fetch('/…')` or bare returned `/frames/image` remains.

## Do — `download.js` (fill stub)

```js
import * as api from '../../api.js';
/** Download a run's crossings via the export endpoint; blob→anchor so it works cross-origin. */
export async function downloadResults(run, format) {           // 'csv' | 'json'
  const blob = await api.fetchExportBlob(run, format);
  const url  = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: `crossings_${run}.${format}` });
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
```

## Done when
- `npm run typecheck` and `npm run unit` are green.
- Every path in `api.js` is prefixed via `BASE()` (SC7); export helpers present; `download.js`
  filled. No changes outside the two owned files.
