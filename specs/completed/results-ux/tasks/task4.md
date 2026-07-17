# Task 4 — Timeline renderer (Wave 1, parallel) · sonnet

Implement rendering in `web/render.js`, replacing the Wave-0 stubs. Build DOM only —
**no fetch, no data transforms** (consume `Pack[]` / `Lane[]` from `data.js`).

## Exclusive file
- `web/render.js` (implement; import types from `./data.js`, do not edit it)

## Contracts (design §5.3) — implement exactly
```js
export function renderTimeline(root, packs, lanes, opts) /*: void */
export function formatTimeOfDay(d) /*: string */   // "hh:mm:ss"
export function formatGapLabel(d)  /*: string */   // "hh:mm"
```

## Behaviour (design §7 rendering model; requirements §5 FR2–FR8)
- **Clear `root` first**, then build fresh.
- Render a **lane header row**: one header cell per `lane`, labelled `lane.category`,
  placed in column `lane.index + 1`.
- For each `pack` (already newest-first):
  - a **full-width gap separator** row showing `formatGapLabel(pack.startTime)`,
    spanning all columns (`grid-column: 1 / -1`);
  - then each `result` as a **card** placed in its lane's column
    (`grid-column: <laneIndexForCategory> + 1`) in its **own grid row** so cross-lane
    order reads top-to-bottom.
- **Card contents** (FR3): race number (e.g. `#422`), name, category, and
  `formatTimeOfDay(result.time)`. When `!result.matched` (FR5): show "Unknown rider",
  no category text, distinct class (e.g. `card--unknown`); still show number + time.
- Use **semantic classes** so task5 can style: e.g. `timeline`, `lane-header`,
  `gap-separator`, `card`, `card__number`, `card__name`, `card__meta`, `card--unknown`.
  Set `data-category` on cards and headers to enable per-lane styling.
- Set `--lane-count` (custom property) or a class on `root` reflecting `lanes.length`
  so CSS can size `grid-template-columns`. Pass `opts.collapseBreakpointPx` through as a
  data attribute / custom property; **the actual collapse is CSS (task5)** — don't
  branch layout in JS.
- Empty `packs` → a friendly empty-state element (FR/NFR4).

## Formatting
- `formatTimeOfDay` → 24h `hh:mm:ss`, zero-padded, from the Date's local components.
- `formatGapLabel` → 24h `hh:mm`, zero-padded.

## Acceptance
- Given the sample data's packs/lanes, produces: 3 lane headers, 2 gap separators
  (`14:51`, `14:47`), 4 cards, with `#422`/`#456` above `#412`/`#501` and `#501` in the
  Unknown lane as `card--unknown`.
- No console errors; no data logic leaks into this file.
- Brief inline self-check acceptable (no framework).
