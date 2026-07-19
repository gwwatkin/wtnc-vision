# Task 8 — Frame browser: scrubber, filmstrip, outcomes, add-crossing

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task9
**Runs in parallel with:** tasks 2–7 (disjoint files)

## Objective
Implement `browser.js` (design §6.4 last block): the in-sidebar frame browser —
time scrubber over the whole run, windowed frame loading, filmstrip + main view
with per-rider outcome overlays, keyboard stepping, and "Add crossing here"
(FR1–FR6).

## Read first
`../design.md` §6.4 (browser bullet — frozen), §5 (`GET /frames` shape: `meta` +
`frames`, each frame carries `url`, `processed`, `riders`). `../requirements.md`
FR1–FR6, SC1, SC3. `README.md`: FROZEN JS contracts (you implement `openBrowser`;
you call `edits.createCrossing` + `edits.loadRosterNumbers` — stubs until task7
lands, code against the contract), DOM contract, refinement 7 (task1's CSS
classes; don't touch the stylesheet). `config.js` keys `FRAMES_SPAN_S` /
`FRAMES_LIMIT`.

## Files you own
```
collection/frontend/results/browser.js   # replace task1's stub
```
Nothing else. You import from `./edits.js` only.

## Implement — `openBrowser({ run, centerTs })`
Renders browser mode into `#sidebar-content` (open `#sidebar` if hidden; the
existing `#sidebar-close` button must keep working and must tear down your
keyboard listener).

- **Load**: `GET /frames?run=&center=&span=&limit=` with the config values;
  `centerTs null` ⇒ omit `center` (server anchors at newest), scrubber then sits
  at `meta.last_ts`.
- **Scrubber**: `<input type=range>` mapped linearly over
  `meta.first_ts…meta.last_ts` (epoch ms); on change (debounced ~150 ms) reload
  the window around the chosen time. Show the current frame's `client_ts` as
  time-of-day next to it.
- **Filmstrip**: thumbnails from each frame's `url` (CSS-scaled, task1's
  classes), current frame highlighted, click selects; `←`/`→` step
  selection (document-level keydown active only while browser mode is displayed);
  stepping past the loaded window's edge reloads centered on the edge frame.
- **Main view**: selected frame's image at full width with a positioned
  `<canvas>` overlay drawing each rider box, colored by status — green
  `confident`, amber `needs_review`, red `rejected` — with `number ?? raw_text`
  and confidence as the label. `processed: false` ⇒ the "no outcome data" note
  (task1's class) instead of an overlay; `riders: []` ⇒ no boxes (that IS the
  outcome: nothing detected). Rescale on image load.
- **Add crossing here** (FR5–FR6): button under the main view → inline form:
  number input with `list="roster-numbers"` (call `loadRosterNumbers(run)` when
  the form opens), blank allowed = unidentified → `createCrossing({ run,
  filename: frame.filename, clientTs: frame.client_ts, number })`; on success
  show a brief confirmation and leave the browser open (the timeline updates on
  the next poll via `wtnc:edited` — task6's listener).
- Errors (fetch failure, empty run): render a plain message in place; never
  throw out of event handlers.

## Acceptance criteria
- `node --check` passes.
- Behavior walked through in your report against SC1 and SC3 step by step
  (scrub → step → add → appears after poll).
- No calls anywhere except `GET /frames*` and the two `edits.js` imports.

## Out of scope
Sidebar crossing/candidate modes (task7), polling (task6), CSS, back-end.

## Final report to include
The SC1/SC3 walkthroughs; how the keyboard listener attaches/detaches; any
contract friction (STOP rule).
