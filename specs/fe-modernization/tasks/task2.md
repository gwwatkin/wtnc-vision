# task2 — Pure-logic tests for `results/data.js` (Wave B)

**Model:** haiku ok (mechanical). **Depends on:** task1. **Independent of all other Wave B
tasks.** Written **pre-port** against the *current* `results/data.js` — these double as the
port's regression net (D6/FR7/SC2).

## Exclusive files (NEW)
```
collection/frontend/tests/data.test.js
```

## Do
Write `node --test` cases (using `node:test` + `node:assert/strict`) covering **every**
export of the current `results/data.js` (FROZEN-1 list): `resultsFromCrossings`,
`candidatesToResults`, `sortByOrder`, `sortDescending`, `mergeCandidates`,
`groupIntoPacks`, `computeLanes`, plus `UNKNOWN_CATEGORY`.

Cover, per FR6:
- **Normal cases** — realistic `/results` + `/candidates` payloads → expected field
  mapping (snake_case → camelCase, `numberText`, `orderKey` fallback to `time.getTime()`
  when `order_key` absent/0, `category` defaulting to `UNKNOWN_CATEGORY`).
- **Edge cases** — empty input (`{crossings:[]}`, `[]`), **unparseable timestamps**
  (skipped, not thrown), **duplicate ids**, missing optional fields, candidates
  overlapping confident crossings in `mergeCandidates`.
- **Invariants other modules rely on** — `groupIntoPacks` splits when the gap between
  adjacent (by order) crossings exceeds `gapSeconds`; each `Pack.startTime` = its newest
  time; `sortByOrder` is descending by `orderKey`; `computeLanes` assigns 0-based
  `index` in first-appearance order; candidates land in the fallback column.
- **SC7** — include at least one test that would **fail if the pack-grouping window
  invariant broke** (e.g. two crossings `gapSeconds+ε` apart must be in separate packs).

## Acceptance
- `node --test --import ./tests/setup-dom.js tests/data.test.js` (and `npm run unit`) is
  **green against today's `results/data.js`**, in well under the FR10 budget.
- Tests import `../results/data.js` directly; **no DOM, no fetch, no component imports**.
- Assertions are written so they will pass **unchanged** after the port (SC2) — assert on
  data.js's public behavior, not on internals that the port may relocate.

## Do not
Edit `results/data.js` or any other file. If a test reveals a real bug in `data.js`,
**flag it** — do not fix it here (that would change frozen behavior mid-run).
