# Task 5 — Front-end results: live timeline + sidebar

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task7
**Runs in parallel with:** tasks 2, 3, 4, 6 (disjoint files)

## Objective
Make the timeline live: poll `GET /results?run=<label>` for the active run, render with
the viewer's proven pack/lane model, make every card clickable into a sidebar showing
the crossing's annotated frame, and populate the past-run selector from `GET /runs`.

## Read first
`../requirements.md` §5.1, §5.4 (FR1–FR4, FR12–FR15); `../design.md` §4 (the
`/results` JSON you consume), §8 (front-end structure — your blueprint); `README.md`
here (DOM contract — **`label-input` is the active run**; no CSV; ES modules). Source
material: `web/data.js`, `web/render.js` (copy-and-adapt), `web/styles.css` (steal
timeline styles).

## Files you own
```
collection/frontend/results/data.js     # adapted copy of web/data.js
collection/frontend/results/render.js   # adapted copy of web/render.js
collection/frontend/results/results.js  # poll loop + wiring (entry module)
collection/frontend/results/sidebar.js  # sidebar open/replace/close
collection/frontend/styles.css          # timeline/card/sidebar styles (extend task1's layout)
```
Do **not** touch `index.html` or `config.js` (task1's frozen shell), `app.js`
(task6), anything under `web/` (deleted later by task7), or the back-end.

## Implement

- **`data.js`** — start from `web/data.js`. Keep `sortDescending`, `groupIntoPacks`,
  `computeLanes`, `UNKNOWN_CATEGORY` as-is. Drop `parseCrossings`/`parseRoster`/
  `mergeResults` (the server enriches; no CSV — README). Add the one new transform:
  ```js
  /** GET /results payload → Result[] (design §4).
   *  Result gains: crossingId {string}, annotatedUrl {string}.
   *  time: new Date(c.time); raceNumber: Number(c.number);
   *  name/matched from the payload; category: c.category ?? UNKNOWN_CATEGORY.
   *  Skips entries with unparseable time. Pure — no DOM, no fetch. */
  export function resultsFromCrossings(payload) { … }
  ```
- **`render.js`** — start from `web/render.js`. Keep formatters, lane headers, gap
  separators, the `card--unknown` treatment. Each card additionally sets
  `card.dataset.crossingId` / `card.dataset.annotatedUrl` and a `card--selectable`
  class; `renderTimeline` gains nothing else (selection highlight is applied *after*
  render by `results.js`, so re-renders stay pure).
- **`results.js`** (entry module) —
  - Poll every `RESULTS_POLL_MS` (from `window.COLLECTION_CONFIG`): read
    `#label-input.value` (raw — server normalizes), skip the fetch when blank, else
    `fetch(\`/results?run=${encodeURIComponent(label)}\`, {cache:"no-store"})` →
    `resultsFromCrossings` → `sortDescending` → `groupIntoPacks(…, 3)` →
    `computeLanes(…, {laneOrder: null})` → `renderTimeline(#timeline, …,
    {collapseBreakpointPx: 640})` (viewer defaults, hardcoded here).
  - **FR4:** render only into `#timeline`; never touch capture controls, never focus or
    `scrollIntoView`; skip the DOM write when the payload is unchanged from the last
    render (cheap JSON string compare) so idle polls are no-ops. A fetch/HTTP error
    keeps the last rendered state (NFR6) — no error banners over live data.
  - When the label changes between ticks, clear `#timeline` and re-render fresh.
  - After each render, re-apply the `card--selected` class to the card whose
    `crossingId` the sidebar is showing (stable across polls, design §8).
  - Delegated click handler on `#timeline`: a click on a `[data-crossing-id]` card
    calls `openSidebar(result)`.
  - Populate `#run-select` from `GET /runs` (every few poll ticks is fine): options =
    run ids plus a placeholder; on change, set `#label-input.value` to the chosen id
    (that's the whole coupling — README DOM contract) and reset the selector to the
    placeholder if you prefer a "jump to run" affordance. Keep the user's typing
    authoritative: never overwrite a non-empty label except on explicit selection.
- **`sidebar.js`** — `openSidebar(result)`: unhide `#sidebar`, replace its content
  (no stacking, FR14) with the annotated `<img src=result.annotatedUrl>` and
  number / name ("Unknown rider" when unmatched) / category / time-of-day;
  `#sidebar-close` hides it and clears the selection highlight. Export what
  `results.js` needs (e.g. `openSidebar`, `closeSidebar`, `selectedCrossingId()`).
- **`styles.css`** — extend (don't rewrite) task1's layout: port the viewer's timeline
  grid/card/separator styles onto the same class names, add `card--selectable` cursor +
  hover, `card--selected` highlight, sidebar panel styling (beside the timeline;
  overlay below the ~640px breakpoint), image constrained to the panel width.

## Acceptance criteria
Back-end tasks may not be merged yet, so verify against a **stubbed API**: run a tiny
static/mock server (or temporarily serve canned JSON at `/results` and `/runs` via any
local means) that returns the §4 sample payload plus an unknown-rider crossing and a
real JPEG at the `annotated_url`. Then, in a browser:
- Timeline renders packs/lanes newest-first below the capture UI; unknown rider shows
  the `card--unknown` treatment (FR3).
- New crossing in the payload appears within one poll tick, no reload, no scroll/focus
  theft while typing in the label field (FR2, FR4).
- Card click opens the sidebar with image + details; clicking another card replaces it;
  close works; highlight survives a re-render (FR12–FR14, SC4).
- Blank label ⇒ no requests; changing the label swaps the timeline; `#run-select`
  reflects `/runs` and clicking an entry repoints the poll.
- No console errors; `app.js` capture flow untouched.

## Out of scope
Capture/video/roster-upload controls (task6), any back-end change, deleting `web/`
(task7).

## Final report to include
Confirm acceptance criteria (say how you stubbed the API); list the exact exports of
each module; flag any DOM-contract or §4-payload friction rather than working around it.
