# task3 — Results timeline view: Timeline / Pack / Card / Candidate / Gap (Wave B)

**Model:** sonnet. **Depends on:** task1. Parity source: `results/render.js`.

## Exclusive files (fill task1 stubs)
```
components/results/Timeline.js   → exports Timeline, Pack, GapSeparator
components/results/Card.js       → exports Card, CandidateCard
components/results/format.js     → exports formatGapLabel, formatTimeOfDay   (pure; NEW logic per FR8)
tests/format.test.js             → NEW
```

## Do
1. **`format.js`** — copy `formatGapLabel` (`hh:mm`) and `formatTimeOfDay` (`hh:mm:ss`)
   verbatim from `render.js:21–37` into a pure module. Add `tests/format.test.js`
   (`node --test`) covering both (FR8) — pad-to-two-digits, midnight/noon edges.
2. **`Card` / `CandidateCard`** (`Card.js`) — presentational, per **FROZEN-3**. Props are
   `CardProps` / `CandidateCardProps` (design §9): `{ crossing|candidate, column, selected,
   onClick }`. Root gets inline `style="grid-column:<column>"`, classes exactly as
   FROZEN-3 (incl. `card--selected` when `selected`, `card--unknown` when `!matched`),
   badges, `card__number`/`card__name`/`card__meta`. Use `format.js` for the meta time.
   **No `data-*` wiring attributes, no imperative selection** — selection is the
   `selected` prop; click is `onClick` (FR13/SC5).
3. **`Pack`** (`Timeline.js`) — props `PackProps` `{ pack, lanes, selectedId, onSelect }`.
   Renders a leading `GapSeparator` from `pack.startTime`, then one `Card`/`CandidateCard`
   per `pack.results`, **resolving each card's `column` from `lanes`** per FROZEN-3
   (crossing: `laneByCategory.get(cat).index+1` else `lanes.length`; candidate:
   `lanes.length || 1`). Pass `selected = (item id === selectedId)` and
   `onClick = () => onSelect(item)`.
4. **`GapSeparator`** — props `{ label }`; `div.gap-separator` spanning `1 / -1`. Parent
   passes `label = formatGapLabel(pack.startTime)`.
5. **`Timeline`** — props `TimelineProps` `{ packs, lanes, candidatesVisible, selectedId,
   onSelect }`. Root `div.timeline` with inline `style="--lane-count:<lanes.length>"`,
   one `lane-header` per lane, empty state `p.timeline__empty` when no results. Renders a
   `Pack` per pack. `candidatesVisible` is already reflected in `packs` (deriveView) —
   Timeline does not re-filter; it just renders what it's given.

## Acceptance
- `npm run typecheck` passes; `npm run unit` green (format tests).
- Rendered DOM matches FROZEN-3 classes/structure so `styles.css` styles it **unchanged**
  (parity). Cross-check against `render.js` output for a sample pack.

## Do not
Touch `styles.css` (flag any genuinely-needed class to task9), `data.js`, or other tasks'
files. Do not fetch or hold state — this layer is pure presentation driven by props.
