# Task 1 — Scaffold (Wave 0, blocking) · sonnet

Create the `web/` skeleton with **frozen contracts as stubs**, sample data, and run
instructions. Everything else depends on this; keep signatures exactly as in
`../design.md` §4–5. **Do not implement real logic** beyond what's noted — leave stubs.

## Exclusive files (create all)
- `web/index.html`
- `web/csv.js`
- `web/data.js`
- `web/render.js`
- `web/app.js`
- `web/styles.css`
- `web/data/crossings.csv`
- `web/data/roster.csv`
- `web/README.md`

## What to build

### `web/index.html`
- HTML5 shell, viewport meta, `<link rel="stylesheet" href="styles.css">`.
- Config global before app: `<script>window.RESULTS_CONFIG = {};</script>`.
- Mount point: `<main id="timeline"></main>`.
- Load app last: `<script type="module" src="app.js"></script>`.

### `web/data.js`  (frozen typedefs + stubs)
- All JSDoc typedefs from design §4 (`Crossing`, `RosterEntry`, `Result`, `Pack`, `Lane`).
- `export const UNKNOWN_CATEGORY = "Unknown";`
- Export every function in design §5.2 with the exact signature, body
  `throw new Error("not implemented: <name>");`.

### `web/csv.js`, `web/render.js`
- Export the design §5.1 / §5.3 functions as `throw new Error("not implemented")` stubs
  with the exact signatures and JSDoc.

### `web/app.js`
- `DEFAULT_CONFIG` object exactly as design §6.
- `resolveConfig`, `loadData`, `refresh`, `start` as stubs (may leave bodies minimal /
  throwing), plus a bottom-of-file `start();` call. Real wiring is task6.

### `web/styles.css`
- Base reset, page background, and a `#timeline` container. Layout/lanes are task5 —
  leave a clear `/* lanes & cards: task5 */` marker; do not implement the grid.

### Sample data (must exercise every rule)
`web/data/crossings.csv` — no header, `time,race_number`; include a >3s gap, a within-3s
pack, and one number absent from the roster:
```
2026-07-11T14:47:00-07:00,412
2026-07-11T14:46:58-07:00,501
2026-07-11T14:51:15-07:00,456
2026-07-11T14:51:17-07:00,422
```
`web/data/roster.csv` — no header, `race_number,name,category`; omit 501 (unknown rider):
```
412,"George Watkins","Cat 3"
456,"Matthew Wahl","Cat 3"
422,"Alex Clement","Cat 4"
```

### `web/README.md`
- One-liner to run: `cd web && python -m http.server 8000`, open
  `http://localhost:8000/`.
- Note the config layers (query string > `window.RESULTS_CONFIG` > defaults) and the CSV
  paths.

## Acceptance
- `python -m http.server` from `web/` serves the page with no console errors on load
  *except* the expected "not implemented" throws once wiring runs (or keep `start()`
  guarded so load is clean — your call, document it).
- Every design §4–5 symbol exists with the frozen signature. Siblings can import them.
