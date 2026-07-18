# Task 5 — Front-end transforms & rendering: candidates, badges, order

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task9
**Runs in parallel with:** tasks 2–4, 6–8 (disjoint files)

## Objective
Extend the pure data layer (`data.js`) with the new crossing fields, candidate
pseudo-results, and order-of-record sorting; extend `render.js` with provenance
badges and subordinate candidate cards (design §6.2–§6.3).

## Read first
`../design.md` §6.2, §6.3 (frozen), §5 (the `/results` + `/candidates` payload
shapes you consume). `../requirements.md` FR7, FR10, FR13, D3/D4, NFR1.
`README.md` refinement 7 (use task1's CSS class names — do NOT edit styles.css)
and the DOM contract. Read the current `data.js`/`render.js` first — extend their
idioms, don't restyle them.

## Files you own
```
collection/frontend/results/data.js     # extend
collection/frontend/results/render.js   # extend
```
Do **not** touch `results.js`, `sidebar.js`, `status.js`, `edits.js`,
`browser.js`, `styles.css`, `index.html`.

## Implement — `data.js` (stay pure: no DOM, no fetch)
- `Result` typedef gains: `source`, `edited`, `orderKey` (number), `orderOverridden`,
  `isCandidate: false`, `numberText` (`number`, or `"—"` when `""`). Map them in
  `resultsFromCrossings` (missing fields from an old back-end ⇒ safe defaults:
  `"auto"`, `false`, epoch-ms of `time`, `false`).
- `candidatesToResults(payload)` — **open** candidates only → pseudo-Results:
  `{isCandidate: true, candidateId, run, time (Date of c.time), lastSeen,
  frameCount, hintNumber, hintConf, imageUrl, repBox, orderKey: ms(time),
  numberText: hintNumber ? hintNumber + "?" : "—"}`. Skip entries with invalid
  times (same tolerance as `resultsFromCrossings`).
- `sortByOrder(results)` — DESC by `orderKey`, tie → `time` DESC — the drop-in
  replacement for `sortDescending` in the pipeline (leave `sortDescending`
  exported; other code may still import it).
- `mergeCandidates(results, candidateResults)` — concat, no sorting (caller runs
  `sortByOrder` after).
- `groupIntoPacks`/`computeLanes` unchanged — verify they tolerate pseudo-results
  (guard any field access that assumes a crossing; candidates have no
  `raceNumber`).
- Brief inline self-checks (no framework, existing convention): `sortByOrder`
  ordering + tie-break, `candidatesToResults` filtering/mapping, `numberText`
  cases. Keep the file importable in the browser (self-checks must not throw on
  load; follow how `data.js` does it today).

## Implement — `render.js`
- Crossing cards: provenance badges from task1's classes — `✚ manual` when
  `source === "manual"`, `✎ edited`, `↕ moved` when `orderOverridden` (D3). Small
  inline markers; card layout otherwise untouched.
- Candidate cards: `card card--candidate`, label `? unidentified` or
  `? <hint>?` when `hintNumber`; rendered inline at their sorted position (OQ2) by
  the same timeline walk — no special-casing in the pack loop beyond what the
  pseudo-result already provides. Set `data-candidate-id` (NOT `data-crossing-id`).
- Every card carries `data-*` for all fields the sidebar needs (existing pattern —
  extend it: source/edited/orderKey/orderOverridden for crossings; candidate id,
  hint, image URL, rep box (JSON-encoded), time for candidates).

## Acceptance criteria
- `node --check` passes on both files; self-checks pass under
  `node collection/frontend/results/data.js` if the file supports direct
  execution, else document how they run.
- With candidates absent, rendered output is character-identical to today's
  (SC7's toggle-off half depends on this).

## Out of scope
Polling/toggle logic (task6), sidebar behavior (task7), any CSS.

## Final report to include
The exact `data-*` attribute names you emit (task7 reads them); confirmation packs
tolerate pseudo-results; any contract friction (STOP rule).
