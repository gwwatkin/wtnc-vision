# task9 — Integration: mount, delete old, component test, parity, docs (Wave C)

**Model:** sonnet. **Depends on:** task2–task8 all landed. This is the only task that edits
`index.html`, deletes old files, and touches `styles.css`.

## Exclusive / owned files
```
main.js                 ← NEW: mounts both roots (design §6)
index.html              ← MODIFIED: two root divs + single module entry (design §6)
tests/timeline.test.js  ← NEW: component test via happy-dom (FR9/SC6)
collection/frontend/README.md   ← NEW: FE dev docs (FR5, design §13)
collection/README.md    ← MODIFIED: link to the FE README
styles.css              ← MODIFIED only if a Wave B task flagged a needed class
-- DELETE --
app.js  results/results.js  results/render.js  results/sidebar.js
results/browser.js  results/status.js  results/edits.js
```

## Do
1. **`main.js`** per design §6 — `render(h(CaptureApp,null), #capture-root)` and
   `render(h(ResultsApp,null), #results-root)`. Mount points use `h(Component, props)`
   directly so `tsc` checks them (design §9).
2. **`index.html`** per design §6 — replace the static body with `<div id="capture-root">`,
   `<div id="results-root">`, the shared `<datalist id="roster-numbers">` (keep), classic
   `<script src="config.js">` **before** `<script type="module" src="main.js">`.
3. **Delete** the superseded modules (list above). `results/data.js`, `config.js`,
   `styles.css` stay. Fold any class additions Wave B flagged into `styles.css` now.
4. **`tests/timeline.test.js`** (FR9/SC6) — render `Timeline` under happy-dom (globals via
   the `--import ./tests/setup-dom.js` hook) and assert: correct card count for a given
   `packs`; clicking a card calls `onSelect` with the right item; candidate cards
   appear/hide per `candidatesVisible`; `selectedId` applies `card--selected`.
5. **FE docs** — author `collection/frontend/README.md` per design §13 (layout, running
   the checks, types & contracts + how to extend, adding a component, updating a vendored
   dep) and link it from `collection/README.md`.

## Acceptance — the release gate
- **`npm run check` green** from a fresh `npm ci` in `< 10 s`, no backend running
  (FR2/FR10/SC1). `data.test.js` (task2) passes **unchanged** post-port (SC2).
- App still starts via `run.sh` with **no node** on the serving path (FR4/SC1); node never
  in the workflow.
- **SC5 grep is clean**: no `wtnc:edited`, no serialized-JSON render-skip, no
  `reapplySelectionHighlight`-style code anywhere.
- **Parity checklist (NFR6/SC3/SC4)** against a real captured run, recorded in the PR:
  - results: timeline packs/lanes/gaps, candidate render + toggle, sidebar edit/delete/
    frame-step, frame browser add-crossing, order editing, status readout, run selector;
  - capture: camera preview, video ingest, start/stop + counters, roster upload + status;
  - **SC4**: with the backend idle (unchanged poll payloads) the results page shows **no
    DOM churn** (DevTools paint flashing).
- One component test renders a Preact component under node and asserts on
  interaction-driven output (SC6).

## Do not
Weaken `data.test.js` assertions to make the port pass (SC2) — a failure there is a real
regression to fix in the port. Do not change the backend or the wire contract.
