# Task 7 — Sidebar modes + edit API client

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task9
**Runs in parallel with:** tasks 2–6, 8 (disjoint files)

## Objective
Give the sidebar its two content modes (design §6.4): the crossing action row
(edit number, move, delete, view frames) and the candidate mode (rep frame with
box overlay, promote/dismiss). Implement `edits.js`, the thin API client every
mutation goes through.

## Read first
`../design.md` §6.4 (frozen), §5 (request/response shapes). `../requirements.md`
FR6, FR8, FR9, FR14, D3/D4. `README.md`: FROZEN JS contracts (you implement
`edits.js`; you consume `openBrowser`), refinement 8 (the neighbor rule — follow
it exactly), refinement 2 (`GET /roster`), DOM contract (`#roster-numbers`).
Read the current `sidebar.js` first — extend its idioms.

## Files you own
```
collection/frontend/results/sidebar.js  # extend
collection/frontend/results/edits.js    # replace task1's stub
```
Do **not** touch `results.js`, `status.js`, `browser.js`, `data.js`,
`render.js`, `index.html`, `styles.css`.

## Implement — `edits.js` (frozen exports)
Each mutator maps 1:1 to a §5 route (`POST /crossings`, `PATCH /crossings/{id}`,
`POST /crossings/{id}/position`, `POST /candidates/{id}/resolve`); JSON bodies
exactly as the table specifies; on 2xx dispatch `new CustomEvent("wtnc:edited")`
on `document` and return the parsed body; on non-2xx throw `Error` with the
server's `detail`. `loadRosterNumbers(run)` fetches `GET /roster?run=`, fills
`#roster-numbers` with `<option value=number label="name">`, returns the riders
array; tolerate an empty roster.

## Implement — `sidebar.js`
`openSidebar(result)` branches on `result.isCandidate`; existing exports and the
selection-highlight behavior stay intact.

**Crossing mode** — today's content plus an action row (task1's CSS classes):
- *Edit number*: inline `<input list="roster-numbers">` prefilled with the current
  number; `loadRosterNumbers(result.run)` on open; confirm ⇒
  `patchCrossing(id, { number })` (empty string allowed = unidentified).
- *Move earlier* / *Move later*: neighbor ids per README refinement 8 (DOM walk,
  skip candidate cards, disable at the ends) ⇒ `setPosition(id, { earlierId,
  laterId })`.
- *Delete*: `confirm()` first (FR8) ⇒ `patchCrossing(id, { deleted: true })`,
  then close the sidebar.
- *View frames*: `openBrowser({ run: result.run, centerTs: result.time
  ISO-string })`.
- After any successful mutation the sidebar's own display refreshes from the
  response body (the timeline catches up on the next poll — NFR6).

**Candidate mode** (§6.4): representative image (`result.imageUrl`) with
`repBox` drawn on a positioned `<canvas>` overlay (scale natural→displayed size;
redraw on image load); time + frame count + what the pipeline saw (hint number/
conf when present); number input prefilled with `hintNumber` (datalist as above);
*Promote* ⇒ `resolveCandidate(id, { action: "promote", number })`, then close;
*Dismiss* ⇒ `resolveCandidate(id, { action: "dismiss" })`, then close;
*View frames* as above.

Candidate pseudo-results arrive from the card's `data-*` attributes (task5 emits,
task6 constructs) — code against the pseudo-Result shape in design §6.2, not
against attribute names.

## Acceptance criteria
- `node --check` on both files.
- Every mutator verified against the §5 table (method, path, body, event) — list
  the mapping in your report.
- Neighbor computation demonstrably follows refinement 8 (walk through a 4-card
  example incl. an interleaved candidate card in your report).

## Out of scope
The frame browser body (task8 — you only call `openBrowser`), polling, rendering
cards, CSS, back-end.

## Final report to include
The mutator↔route mapping; the neighbor-rule walkthrough; any contract friction
(STOP rule).
