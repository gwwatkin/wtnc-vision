# task4 — Sidebar + FrameBrowser + roster datalist helper (Wave B)

**Model:** sonnet. **Depends on:** task1. Parity sources: `results/sidebar.js`,
`results/browser.js`, `results/edits.js` (mutation calls now live in `api.js`, task7).

## Exclusive files (fill task1 stubs)
```
components/results/Sidebar.js       (replaces sidebar.js + edits.js view logic)
components/results/FrameBrowser.js   (replaces browser.js)
components/results/roster.js         → exports setRosterOptions(run)   (FROZEN-8)
```

## Do
1. **`Sidebar`** — props `SidebarProps` (design §9): `{ item, frameOffset, runLabel,
   onClose, onStepFrame, onEdit, onDelete, onPromote, onDismiss, onOpenBrowser }`. Port
   `sidebar.js`'s overlay for **both** a crossing and a candidate `item`: annotated image
   (`sidebar__image`), details (`sidebar__number`/`sidebar__name`/`sidebar__category`/
   `sidebar__time`), number `<input class="sidebar__number-input" list="roster-numbers">`,
   frame-step controls (call `onStepFrame(±1)`), and the action row (`sidebar__actions`,
   `sidebar__btn` variants `--primary`/`--danger`). Wire actions to the **passed-in async
   callbacks** — `onEdit(crossingId, fields)`, `onDelete(crossingId)`,
   `onPromote(candidateId, payload)`, `onDismiss(candidateId)`, `onOpenBrowser(anchorTs)`.
   Do **not** call `api.js` directly and do **not** dispatch a `wtnc:edited` event —
   `ResultsApp` owns mutations + refresh (FR13/SC5). On open, call
   `setRosterOptions(runLabel)`.
2. **`FrameBrowser`** — props `FrameBrowserProps`: `{ runLabel, anchorTs, onClose,
   onCreateCrossing }`. Port `browser.js`: filmstrip/scrubber (`frame-browser*` classes),
   frame image + bounding-box canvas overlay (`frame-canvas-*`), and the add-crossing row
   (`frame-browser__add-row`, number input bound to `list="roster-numbers"`). Fetch frames
   via `api.fetchFrames(runLabel, {anchorTs, spanS, limit})` using `FRAMES_SPAN_S`/
   `FRAMES_LIMIT` from config; build image src via `api.frameUrl`. Submit new crossings
   through `onCreateCrossing(payload)`. On open, call `setRosterOptions(runLabel)`.
3. **`roster.js`** — `setRosterOptions(run)`: `await api.fetchRoster(run)` then write
   `<option value=number label=name>` into the shared `#roster-numbers` datalist
   (FROZEN-8). Tolerate empty/absent roster (swallow errors — datalist degrades). This is
   the one sanctioned imperative touch of a shared shell node.

## Acceptance
- `npm run typecheck` passes. Overlays reproduce the `sidebar__*` / `frame-browser*` /
  `frame-canvas-*` classes so `styles.css` styles them unchanged (parity).
- No direct `fetch`, no `wtnc:edited` dispatch, no selection re-application code (SC5).

## Do not
Touch `styles.css`, `data.js`, `api.js`, or other tasks' files. Mutations/refresh are
`ResultsApp`'s job — this task only renders and calls the provided callbacks.
