# task7 — I/O layer: `api.ts` + `backend-url.ts` + `download.ts` + backend-url test (Wave B)

**Model:** sonnet · **Depends on:** task1. **Parallel with:** task2–task6, task8.

Source of truth: `../design.md` §5, §7, §10 + the `page-split` design (`api`/`backend-url`/
`download` surfaces) + `tasks/README.md` FROZEN-2, FROZEN-4. All paths under
`collection/frontend/`.

## What you own (fill)

- `api.ts` — the single fetch layer for both pages.
- `backend-url.ts` — runtime backend-URL store (from `page-split`).
- `components/results/download.ts` — crossings export/download helper (from `page-split`).
- `tests/backend-url.test.ts` — port `tests/backend-url.test.js`.

These are the leaf modules many others import; keep every name/signature stable.

## Steps

1. **`backend-url.ts`.** Convert `backend-url.js` to strict TS, signatures verbatim:
   `normalizeBackendUrl(raw: string): string`, `getBackendUrl(): string`,
   `setBackendUrl(url: string): void`, `onBackendUrlChange(cb: (url: string) => void):
   () => void`, `backendLabel(url: string): string`. Reads
   `window.COLLECTION_CONFIG?.BACKEND_URL ?? ''` (type via `CollectionConfig` in `types.ts`)
   and the `wtnc_backend_url` cookie exactly as today. Pure module, no JSX.

2. **`api.ts`.** Convert `api.js` to strict TS. Every existing function keeps its
   name/signature (`fetchRuns, fetchResults, fetchCandidates, fetchStatus, fetchFrames,
   fetchRoster, postEdit, deleteEdit, postManualCrossing, reorderCrossing({earlierId,
   laterId}), promoteCandidate, dismissCandidate, checkHealth, postFrame, uploadRoster,
   frameUrl, exportUrl, fetchExportBlob`). `BASE = () => getBackendUrl()` from
   `./backend-url`; `_fetch` prepends `BASE()` once. Wire contract unchanged — do not touch
   paths/payloads. Type responses via the `types.ts` payload interfaces
   (`StatusPayload`, `FrameInfo`, `PostFrameResult`, …) where the old JSDoc did.

3. **`download.ts`.** Convert `download.js`. `import type { ExportFormat } from
   '../../types'`; use `api.exportUrl` / `api.fetchExportBlob`; trigger the browser download
   exactly as today. No JSX.

4. **Port the test (FROZEN-4).** `backend-url.test.js` → `.test.ts`: `vitest` imports, keep
   `node:assert/strict`, import from `'../backend-url'`, drop `@ts-nocheck`. Assertions
   unchanged. Follow task1's `vitest.setup.ts` decision if it touches `document`/cookies.

## Definition of done

- `npm run typecheck` passes; `npm run unit` passes with `backend-url.test.ts` green.
- No bare same-origin path remains in `api.ts` — every request flows through `BASE()`.

## Do NOT

- Change any endpoint path, payload, or the wire contract (D5/NFR2).
- Edit `types.ts`, `styles.css`, or any other task's files.
</content>
