# task7 — `api.js` fetch layer (Wave B)

**Model:** sonnet. **Depends on:** task1. Parity sources: `fetch`/mutation calls in
`results.js`, `edits.js`, `sidebar.js`, `browser.js`, `app.js`. Wire contract is **frozen**
(FROZEN-6 / design §7 / A2) — change call-sites, never the API.

## Exclusive files (fill task1 stub)
```
collection/frontend/api.js
```

## Do
Implement the full **FROZEN-6** surface. `BASE = () => window.COLLECTION_CONFIG?.BACKEND_URL ?? ''`.
All functions pure async, **no DOM, no globals mutated**; throw on non-OK responses.

| Function | Method + path | Body / notes |
|---|---|---|
| `fetchRuns()` | GET `/runs` | → `string[]` |
| `fetchResults(runLabel)` | GET `/results?run=` | → raw JSON |
| `fetchCandidates(runLabel)` | GET `/candidates?run=` | → raw JSON |
| `fetchStatus(runLabel)` | GET `/status?run=` | → raw JSON |
| `fetchFrames(runLabel,{anchorTs,spanS,limit})` | GET `/frames?run=&...` | → raw JSON |
| `fetchRoster(runLabel)` | GET `/roster?run=` | → riders[] (tolerate empty) |
| `postEdit(runLabel,crossingId,fields)` | PATCH `/crossings/{id}` | `{ number?, deleted? }` |
| `deleteEdit(runLabel,crossingId)` | PATCH `/crossings/{id}` | `{ deleted:true }` (no DELETE route) |
| `postManualCrossing(runLabel,payload)` | POST `/crossings` | |
| `reorderCrossing(runLabel,crossingId,{earlierId,laterId})` | POST `/crossings/{id}/position` | body `{ earlier_id, later_id }` |
| `promoteCandidate(runLabel,candidateId,payload)` | POST `/candidates/{id}/resolve` | `{ action:'promote', number }` |
| `dismissCandidate(runLabel,candidateId)` | POST `/candidates/{id}/resolve` | `{ action:'dismiss' }` |
| `checkHealth()` | GET `/health` | → boolean |
| `postFrame(payload)` | POST `/frames` | capture upload; → raw JSON |
| `uploadRoster(runLabel,file)` | POST `/roster` | multipart CSV upload |
| `frameUrl(runLabel,filename)` | — | **sync** string builder for GET `/frames/image?...` |

Match the exact query-param names and JSON body keys the current modules send
(`earlier_id`/`later_id`, `client_ts`, `action`/`number`, etc.) — cross-check
`edits.js` / `browser.js` / `app.js`.

## Acceptance
- `npm run typecheck` passes. Every path/param/body byte-matches the current wire contract
  (A2) — the Python backend tests must still pass without change.
- `frameUrl` performs **no** fetch. No DOM access anywhere in the module.

## Do not
Touch component files, `data.js`, `config.js`, or the backend. If a current call-site uses
a path/param not covered by FROZEN-6, **flag it** rather than inventing an endpoint.
