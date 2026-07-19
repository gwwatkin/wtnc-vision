# Task 3 — FramesIndex: per-frame outcome retention + windowed browse reads

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task9
**Runs in parallel with:** tasks 2, 4–8 (disjoint files)

## Objective
Implement `FramesIndex` (design §4.1): append one JSONL line per processed frame
(§3.3), and serve time-windowed merges of `manifest.jsonl` (all captured frames)
with `frames_index.jsonl` (pipeline outcomes) for the frame browser, plus run meta
for the scrubber.

## Read first
`../design.md` §3.3 (line shape — frozen), §4.1 (signatures — frozen), §2 (layout).
`../requirements.md` FR1–FR4, NFR2/NFR3. `README.md` refinement 9 (URL added by the
route, NOT by you).

## Files you own
```
collection/backend/frames_index.py             # replace task1's stub bodies
collection/backend/tests/test_frames_index.py  # NEW
```
Do **not** touch `engine.py`, `storage.py`, or other tests.

## Implement
Keep task1's frozen signatures.

- **`append(run, entry, results)`** — build the §3.3 line: `filename`/`client_ts`/
  `seq` copied from the manifest `entry`; `riders` maps each `CrossingResult` to
  `{"box": list(r.rider_box), "det_conf": r.det_conf, "status": r.status,
  "number": r.number, "raw_text": r.raw_text, "confidence": r.confidence}` —
  **including `riders: []`** when the pipeline saw nothing (FR3). Append a single
  line to `runs/<run>/frames_index.jsonl` (open-append-close, flush; same
  crash-tolerance stance as the manifest). Called from the worker thread; must be
  cheap — no reads.
- **`frames(run, center_ts, span_s, limit)`** — read both files on demand (never
  cache across calls — browse is interactive-only, NFR2): manifest lines are the
  spine; index lines join on `filename`. Output dicts:
  `{"filename", "client_ts", "seq", "processed": bool, "riders": [...] | None}`
  (`processed=True, riders=[…or empty]` when an index line exists; else
  `False, None`). Window: `client_ts ∈ [center − span_s, center + span_s]`,
  time-ordered ascending, capped at `limit` (drop from the edges farthest from
  `center`); `center_ts=None` ⇒ the newest `limit` frames, ascending. Missing
  files ⇒ `[]`; malformed lines skipped.
- **`meta(run)`** — `{"count", "first_ts", "last_ts"}` from the manifest alone
  (`None`s + 0 when absent/empty).

## Tests — `test_frames_index.py`
`tmp_path` run dirs with hand-written manifests. Cover at least:
- `append` writes the exact §3.3 shape (incl. empty riders); lines accumulate.
- Merge: processed frames carry riders, unprocessed carry `processed=False,
  riders=None` (a manifest longer than the index — the backlog case).
- Windowing: center picks the right span; ascending order; `limit` cap keeps the
  frames nearest the center; `center=None` returns the newest `limit`.
- Robustness: missing manifest / missing index / malformed line in either.
- `meta` on empty, missing, and populated runs.

## Acceptance criteria
`.venv/bin/pytest collection/backend/tests/` green (pre-existing suites included).

## Out of scope
Who calls `append` (task4), HTTP layer (task1 landed the routes), image serving.

## Final report to include
Confirm acceptance; note the windowing edge cases you covered; flag any contract
friction (STOP rule).
