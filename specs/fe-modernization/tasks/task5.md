# task5 — StatusBar + RunSelector (Wave B)

**Model:** haiku ok (small). **Depends on:** task1. Parity sources: `results/status.js`,
run-selector logic in `results/results.js`.

## Exclusive files (fill task1 stubs)
```
components/results/StatusBar.js
components/results/RunSelector.js
```

## Do
1. **`StatusBar`** — props `StatusBarProps` `{ status: object | null }`. Port
   `status.js`'s readout (today it fills `#queue-status`): render the same
   queue/processing/idle summary derived from the `status` payload, including the
   `status-dot` indicator with its `--green`/`--amber` state classes. When `status` is
   `null` (pre-first-poll / poll error) render the neutral/placeholder state today shows.
   Presentational only — no fetch; the payload is polled by `ResultsApp`.
2. **`RunSelector`** — props `RunSelectorProps` `{ runs, selected, onChange }`. A `<select>`
   (or the current control) listing `runs`, current value `selected`, firing
   `onChange(runLabel)` on change. No fetch — `runs` come from state.

## Acceptance
- `npm run typecheck` passes. Both components reproduce the existing classes/ids' visual
  output (`status-dot*`) so `styles.css` styles them unchanged.
- Purely prop-driven; no `window`/`fetch`/timer usage.

## Do not
Touch `styles.css`, `data.js`, or other tasks' files.
