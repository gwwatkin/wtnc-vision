# Task 2 — CandidateTracker: grouping, hints, suppression, persistence

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task9
**Runs in parallel with:** tasks 3–8 (disjoint files)

## Objective
Implement `CandidateTracker` (design §4.2): fold non-confident per-frame rider
results into per-run candidate crossings, maintain hint numbers from `needs_review`
reads, suppress candidates that overlap confident folds, persist every mutation
atomically to `candidates.json`, and reload on start.

## Read first
`../design.md` §3.2 (Candidate dataclass — frozen, landed by task1), §4.2 (all
signatures + algorithm — frozen), §2 (on-disk layout), §7 last paragraph
(candidates never absorb; suppression comes only via `suppress_around`).
`../requirements.md` FR12–FR15, SC2/SC7. `README.md` refinements 4, 5.

## Files you own
```
collection/backend/candidates.py             # replace task1's stub bodies
collection/backend/tests/test_candidates.py  # NEW
```
Do **not** touch `engine.py` (task4 calls you), `results_models.py` (frozen), or
any other test file.

## Implement
Keep task1's frozen signatures. Semantics, per §4.2 with these clarifications:

- **Inputs.** `results` is `list[CrossingResult]`; you consume `status`,
  `det_conf` (task1 plumbed it — default 0.0 means pre-change canned results are
  simply filtered out by `min_det_conf`), `rider_box`, `number`, `confidence`.
- **`observe`** — filter results to `status ∈ self.statuses` and
  `det_conf >= min_det_conf`; if nothing survives, return. If `had_confident`,
  return without folding (FR15, prospective half). Otherwise fold **the whole
  frame once** into the run's single open candidate (a frame with two unreadable
  riders still bumps `frame_count` by 1 — known heuristic limit, §4.2 note):
  - No open candidate, or `ts − open.last_seen > window_s` ⇒ start a new one:
    `candidate_id = f"{run}-cand-{epoch_ms(ts)}"`, `time = last_seen = ts`,
    `frame_count = 1`, rep = this frame with the largest surviving rider box (by
    area) as `rep_box`, `state = "open"`. The previous open candidate just stays
    as-is for the operator.
  - Else fold: `last_seen = ts`, `frame_count += 1`; adopt this frame as rep iff
    its largest surviving box area beats the stored rep's; update hints.
  - **Hints:** track `needs_review` numbers seen in the candidate's span;
    `hint_number` = most frequent (ties → the one with the higher best
    confidence, then earliest seen); `hint_conf` = best `needs_review`
    `confidence` overall, else 0.0. `rejected` results never contribute hints.
    Keep the tally in memory only — after `load_existing` a resumed open
    candidate restarts its tally from its persisted `hint_number`/`hint_conf`
    (count 1) — document this.
  - Persist `candidates.json` after every mutation (atomic temp + `os.replace`,
    same pattern as `crossings.json`).
- **`suppress_around(run, ts)`** — every OPEN candidate whose `[time, last_seen]`
  span overlaps `[ts − window_s, ts + window_s]` → `state = "suppressed"` +
  persist. Promoted/dismissed never change. This is the retroactive half of FR15
  and MUST catch a candidate opened *between* two folds of the same crossing.
- **`load_existing`** — scan `run_root/*/candidates.json` into memory (malformed
  file ⇒ log + skip that run, never raise).
- **`set_state`** — `"promoted"`/`"dismissed"` only; unknown id or other state ⇒
  `ValueError`; sets `promoted_crossing_id` when given; persists; returns the
  updated `Candidate`.
- **`list`/`get`** — return copies/snapshots, all states included.
- **No internal lock** (refinement 5) — document it in the class docstring.

## Tests — `test_candidates.py`
Build tiny run dirs in `tmp_path`; hand-construct `CrossingResult`s. Cover at least:
- Burst of non-confident frames within `window_s` ⇒ **one** candidate,
  `frame_count` = frames folded; a gap `> window_s` ⇒ second candidate while the
  first stays open.
- `had_confident=True` frames are ignored entirely.
- `det_conf < min_det_conf` and statuses outside `self.statuses` filtered out;
  a frame where nothing survives is a no-op.
- Rep adoption: larger box area replaces rep (filename + `rep_box`); smaller
  doesn't.
- Hints: most-frequent needs_review number wins; tie → higher conf; rejected-only
  candidate ⇒ `hint_number is None`, `hint_conf == 0.0`.
- `suppress_around`: overlapping open candidate suppressed; non-overlapping stays
  open; the between-two-folds case (candidate opens after fold 1, `suppress_around`
  from fold 2 kills it); promoted/dismissed untouched.
- Persistence: `candidates.json` matches memory after each mutation; fresh tracker
  + `load_existing` reproduces state; malformed file skipped.
- `set_state`: promote with crossing id; dismiss; bad state / unknown id ⇒
  `ValueError`.

## Acceptance criteria
- `.venv/bin/pytest collection/backend/tests/` green (including the pre-existing
  suites — you broke nothing).

## Out of scope
When/whence you're called (engine — task4), HTTP, front-end, `frames_index.jsonl`.

## Final report to include
Confirm acceptance; describe grouping/suppression coverage; flag any frozen-contract
friction (STOP rule).
