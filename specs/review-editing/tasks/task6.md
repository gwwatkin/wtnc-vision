# Task 6 — Queue status readout + poll orchestration

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task9
**Runs in parallel with:** tasks 2–5, 7, 8 (disjoint files)

## Objective
Implement `status.js` (queue readout, design §6.1) and rewire `results.js`'s tick
to poll `/results` + `/candidates` + `/status` per label with per-concern
unchanged-payload skips, the candidates toggle, the edited-event listener, and the
browse/candidate entry points (§6.5 last paragraph).

## Read first
`../design.md` §6.1, §6.5 (esp. the per-concern skip paragraph — frozen), §5
(payload shapes). `../requirements.md` FR13, FR16–FR19, NFR1. `README.md`: the
FROZEN JS module contracts (you implement `pollStatus`, you *consume*
`openBrowser` and the `wtnc:edited` event) and the DOM id contract. Read the
current `results.js` first — extend its idioms.

## Files you own
```
collection/frontend/results/status.js   # replace task1's stub
collection/frontend/results/results.js  # extend
```
Do **not** touch `data.js`/`render.js` (import task5's frozen exports),
`sidebar.js`, `edits.js`, `browser.js`, `index.html`, `styles.css`.

## Implement — `status.js`
`pollStatus(label)` per the frozen contract: fetch `GET /status?run=`, render into
`#queue-status` (task1's markup/classes):
- draining: `Queue: 412 captured · 280 processed · 132 pending — processing…`
  (amber dot) plus `results current to 14:32:07` from `processed_through` (FR17);
- caught up: `Queue: 412 captured · all processed — ✓ up to date` (green dot);
- hidden when `label` is empty or payload has `enabled: false`.
Keep its **own** last-payload compare (skip re-render on identical JSON) — never
tied to the timeline's compare. Swallow fetch errors (leave last render).

## Implement — `results.js`
- Tick: fetch `/results?run=` and `/candidates?run=` together (`Promise.all`),
  then `pollStatus(label)` (fire-and-forget). Timeline skip compares the
  **combined** results+candidates JSON; `/status` never forces a timeline
  re-render (§6.5 — frozen).
- Pipeline: `resultsFromCrossings` → `mergeCandidates` with
  `candidatesToResults` (only when `#candidates-toggle` is checked) →
  `sortByOrder` → existing packs/lanes/render. Toggle change ⇒ clear the cached
  payload JSON and re-render immediately. Always update
  `#candidates-toggle-count` with the open-candidate count (even when unchecked).
- `document.addEventListener("wtnc:edited", …)` ⇒ clear `_lastPayloadJson` so the
  next tick re-renders (NFR6 — no optimistic state).
- Timeline click handler: extend the existing delegation — `[data-crossing-id]`
  cards keep today's behavior; `[data-candidate-id]` cards build the
  pseudo-result from the card's `data-*` (task5's attribute names, listed in its
  final report — coordinate via the frozen list in README if needed) and call
  `openSidebar(result)`.
- `#browse-frames-btn` click ⇒ `openBrowser({ run: labelEl.value.trim(),
  centerTs: null })` (import from `./browser.js` — stub until task8 lands).
- Run switch (`run-select`/label change) hides `#queue-status` until the next
  successful poll.

## Acceptance criteria
- `node --check` on both files.
- Manual reasoning check documented in your report: a draining backlog changes
  `/status` every tick but the timeline render count stays flat when
  results/candidates are unchanged (the §6.5 requirement).
- With the toggle unchecked and no edits, behavior is exactly today's plus the
  status line (NFR1).

## Out of scope
Sidebar/candidate actions (task7), the browser itself (task8), CSS, back-end.

## Final report to include
Confirm the per-concern skip wiring; the exact event/import points you consume;
any contract friction (STOP rule).
