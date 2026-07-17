# Task 6 — App wiring & verification (Wave 2, integration) · sonnet

Implement `web/app.js` and verify the whole thing end-to-end. Runs after Wave 1.

## Exclusive file
- `web/app.js` (implement; read all of `web/`, edit nothing else)

## Contracts (design §5.4) — implement exactly
```js
function resolveConfig()      /*: Config */
async function loadData(config) /*: Promise<{crossingsText, rosterText}> */
async function refresh(config)  /*: Promise<void> */
function start()                /*: void */
```

## Behaviour
- **resolveConfig**: merge `DEFAULT_CONFIG` (design §6) ← `window.RESULTS_CONFIG` ←
  query-string overrides. Query keys: `gap`→`gapSeconds` (int), `refresh`→`refreshMs`
  (int), `crossings`→`crossingsUrl`, `roster`→`rosterUrl`. Ignore absent/invalid.
- **loadData**: `fetch` both URLs with `cache: "no-store"`; throw on non-OK HTTP;
  return `{crossingsText, rosterText}`.
- **refresh**: `loadData` → `parseCsv` (both) → `parseCrossings` / `parseRoster` →
  `mergeResults` → `sortDescending` → `groupIntoPacks(_, gapSeconds)` +
  `computeLanes(_, {laneOrder})` → `renderTimeline(#timeline, packs, lanes,
  {collapseBreakpointPx})`. On any error, render a non-blocking **error banner** and
  keep the previous view; log to console.
- **start**: `resolveConfig()`, run `refresh` once, then `setInterval(refresh,
  refreshMs)` **only if `refreshMs > 0`** (0 ⇒ render once). Guard against overlapping
  refreshes.
- Import from `./csv.js`, `./data.js`, `./render.js`. No logic that belongs in those
  modules.

## Verification (do this, report results)
1. `cd web && python -m http.server 8000`, open `http://localhost:8000/`.
2. Confirm against `../requirements.md` §7 UX + §8 success criteria:
   - newest-first; 3 lanes (Cat 3 / Cat 4 / Unknown); `#422`/`#456` pack above
     `#412`/`#501`; two gap labels `14:51` and `14:47` (SC1, SC2).
   - `#501` renders as unknown rider in the Unknown lane (SC3).
   - `?gap=1` splits the packs; `?refresh=0` disables polling — spot-check.
   - narrow viewport (≤375px) collapses to one column, no horizontal scroll (SC4).
3. Note any contract mismatch discovered (per repo rules, flag — don't silently patch a
   sibling's file).

## Acceptance
- Page renders the sample data correctly with no console errors; polling and config
  overrides work; verification notes recorded in the final report.
