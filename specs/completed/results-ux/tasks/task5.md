# Task 5 — Layout & styling (Wave 1, parallel) · haiku

Implement the timeline styling in `web/styles.css`, replacing the Wave-0 marker. CSS
only — do not touch JS. Style the classes the renderer (task4) emits.

## Exclusive file
- `web/styles.css` (implement; you may **read** `web/index.html` for structure)

## Classes emitted by the renderer (target these)
`timeline`, `lane-header`, `gap-separator`, `card`, `card__number`, `card__name`,
`card__meta`, `card--unknown`. Cards/headers carry `data-category`; `root` exposes lane
count via a `--lane-count` custom property (or class).

## Requirements (design §7; requirements §6 NFR2, §7 UX, OQ5)
- **Grid**: `.timeline { display: grid; grid-template-columns: repeat(var(--lane-count), 1fr); }`
  with row gap. Lane headers sit in row 1, sticky at top is a nice-to-have.
- Cards keep the **name as the headline**, number prominent (`#422`), category + time as
  secondary meta (NFR2). Legible at arm's length on a phone.
- **Gap separators** span all columns (`grid-column: 1 / -1`), visually distinct
  horizontal rule with the time label centred/left.
- **`card--unknown`** visually distinct (muted / dashed border) but still readable.
- **Responsive collapse (OQ5)**: below the collapse breakpoint (~640px), switch
  `grid-template-columns` to a single column so cards render full-width in time order;
  hide lane headers; ensure the category still shows on each card (a chip is fine — you
  may style a `::before` from `data-category`, or just show `.card__meta`). Use a media
  query at 640px (match `collapseBreakpointPx` default).
- Optional, off by default: a subtle per-lane accent keyed on `data-category` (OQ3).
  Keep it tasteful and easy to remove.

## Acceptance
- With the sample data the desktop view shows 3 side-by-side lanes on a shared vertical
  timeline; below 640px it collapses to one column preserving newest-first order.
- No layout overflow / horizontal scroll on a 375px-wide viewport.
- Pure CSS; no JS edits.
