# Task 3 — Data transforms (Wave 1, parallel) · sonnet

Implement the pure transforms in `web/data.js`, replacing the Wave-0 stubs. Keep the
frozen typedefs and `UNKNOWN_CATEGORY`. **No DOM, no fetch** — pure functions only.

## Exclusive file
- `web/data.js` (implement; may `import` types from `./csv.js` if useful, but do not edit it)

## Contracts (design §5.2) — implement exactly
```js
export function parseCrossings(rows) /*: Crossing[] */
export function parseRoster(rows)    /*: Map<number, RosterEntry> */
export function mergeResults(crossings, roster) /*: Result[] */
export function sortDescending(results)         /*: Result[] */
export function groupIntoPacks(results, gapSeconds) /*: Pack[] */
export function computeLanes(results, opts)         /*: Lane[] */
```

## Behaviour
- **parseCrossings**: each row `[time, race_number]`. Parse ISO-8601-with-offset via
  `new Date(...)`; `race_number` via `Number(...)`. Skip a row if the date is `Invalid`
  or the number is `NaN` (NFR4). Return `Crossing[]`.
- **parseRoster**: each row `[race_number, name, category]` → `Map` keyed by numeric
  race number. Trim name/category. Bad rows skipped; later duplicates overwrite earlier.
- **mergeResults**: for each crossing, look up roster. Matched → `{name, category,
  matched:true}`. Unmatched → `{name:null, category:UNKNOWN_CATEGORY, matched:false}`.
  Carry `time` and `raceNumber` through.
- **sortDescending**: newest `time` first; **stable** for equal times.
- **groupIntoPacks**: input assumed descending (call `sortDescending` first if unsure).
  Walk the list; start a new `Pack` whenever the gap from the current result to the
  **previous (newer)** result exceeds `gapSeconds`. The first result always starts a
  pack. `pack.startTime` = the pack's **newest** (first) result's `time`. Results within
  a pack stay descending.
- **computeLanes**: distinct categories present in `results`. Order: any category listed
  in `opts.laneOrder` first (in that order), then remaining categories in
  first-appearance order, and **`UNKNOWN_CATEGORY` always last** regardless. Assign
  0-based `index` per resulting order. `opts` may be `{}` / `laneOrder` undefined.

## Acceptance (use the sample CSVs' values)
- Crossings `[14:51:17, 14:51:15, 14:47:00, 14:46:58]` with `gapSeconds=3` →
  **2 packs**: `[14:51:17,14:51:15]` (start 14:51:17) and `[14:47:00,14:46:58]`
  (start 14:47:00).
- `501` (absent from roster) → `matched:false`, `category:"Unknown"`, `name:null`.
- `computeLanes` over Cat 3 / Cat 4 / Unknown with `laneOrder:["Cat 4","Cat 3"]` →
  indices `Cat 4=0, Cat 3=1, Unknown=2`.
- Include brief inline self-checks (no framework).
