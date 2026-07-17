# Task 2 — Results engine: manifest tailer, dedup, persistence, annotated frames

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task7
**Runs in parallel with:** tasks 3, 4, 5, 6 (disjoint files)

## Objective
Implement `ResultsEngine` end-to-end: the single worker that tails each run's
`manifest.jsonl` from its persisted `processed_offset`, runs `pipeline.run` per frame in
a thread, folds confident reads into deduplicated crossings, writes the annotated
representative frame, and persists everything under `runs/<run>/`. Also make the two
small `rider_id` edits the engine consumes.

## Read first
`../design.md` — §5 (on-disk layout, offset/idempotency semantics), §6 (signatures,
worker loop — both **frozen**, including the `try/except`), §6.1 (dedup algorithm + the
two notes on per-run roster and `accept_unmatched`), §11 (risks). `../requirements.md`
§5.2–§5.3. `README.md` here (rosters contract, root-relative manifest `filename`,
monkeypatch convention).

## Files you own
```
collection/backend/engine.py             # implement all bodies (signatures frozen)
collection/backend/tests/test_engine.py  # NEW
src/rider_id/io_out.py                   # add filename= param to write_annotated_image
src/rider_id/validate.py                 # add accept_unmatched mode
tests/test_validate.py                   # cases for accept_unmatched
config.yaml                              # repo root: add validate.accept_unmatched: true
```
Do **not** touch `rosters.py` (task4 — you call its frozen API), `storage.py`/
`test_frames.py` (task3), `app.py`/`live_config.py`/`results_models.py` (task1's
frozen output), or anything under `collection/frontend/`.

## Implement — `rider_id` edits (do these first; they're your dependencies)

- **`io_out.write_annotated_image(image_bgr, results, zone, out_dir,
  filename="annotated.jpg")`** — new keyword-only-in-spirit last parameter; output path
  becomes `<out_dir>/<filename>`. Default preserves POC behavior exactly.
- **`validate.validate`** — in the step-4c branch (ambiguous snap or no roster entry
  within the edit budget), when `cfg["validate"]["accept_unmatched"]` is truthy, return
  `(best_digits, best_raw, best_conf)` **as-is** instead of `(None, …)`. Exact match
  (4a) and unique snap (4b, with `SNAP_PENALTY`) are unchanged; the digit-count and
  leading-zero filters still apply first. Key absent/false ⇒ POC behavior.
- **`tests/test_validate.py`** — add: (a) no-match within budget, flag on → accepted
  as-is, full confidence; (b) ambiguous nearest entries, flag on → accepted as-is;
  (c) flag off/absent → both still rejected (regression); (d) unique snap still snaps
  (and penalizes) with the flag on.
- **repo `config.yaml`** — add `accept_unmatched: true` under `validate:` (design §7).

## Implement — `engine.py`

Keep task1's frozen signatures and its `set_roster`/`runs` delegations untouched.

- **`start`** — scan `run_root/*/`: load each `crossings.json` into memory, rebuild
  `self._open` from each crossing's persisted `last_seen`/`confidence` (key
  `(run, number)`), build the id→crossing index, `self._rosters.load_existing()`, mark
  every run whose manifest has lines beyond its `processed_offset` dirty, set the wake
  event, then launch the worker task. Startup is the normal loop — no special recovery
  path (design §5).
- **Worker loop** — exactly the frozen §6 shape: wait/clear the `asyncio.Event`, drain
  the dirty-run set, per run read `processed_offset` and iterate manifest lines from it
  strictly in order; each line runs `await asyncio.to_thread(self._process_frame, run,
  entry)` inside `try/except Exception` (log + continue — FR6); after each line
  (success **or** failure) atomically rewrite `processed_offset` (temp + `os.replace`).
  A `notify` arriving mid-drain must not be lost — re-check dirtiness before sleeping.
- **`notify(run)`** — add to the dirty set + set the event. O(1), no work state.
- **`stop`** — signal shutdown, set the event, await the worker; state is already on
  disk (offset written per line), so no extra flush logic beyond finishing the current
  frame.
- **`_process_frame(run, entry)`** (worker thread) — set
  `self._cv_cfg["validate"]["roster"] = self._rosters.roster_txt_path(run)` (you are
  the only `cv_cfg` writer); `img = cv2.imread(os.path.join(run_root,
  entry["filename"]))` (`filename` is storage-root-relative, README refinement 2);
  `None` ⇒ raise (poison frame → logged/skipped by the loop);
  `frame_results = pipeline.run(img, self._cv_cfg)` — call it as `pipeline.run` on the
  imported module (monkeypatch point); for each result whose `status` is in
  `live.statuses`: `self._fold(run, result.number, result.confidence,
  entry["client_ts"], img, frame_results)`.
- **`_fold`** — implement §6.1 verbatim: `(run, number)` lookup; **new crossing** when
  absent or gap `> dedup_window_s` — build `crossing_id =
  f"{run}-{number}-{epoch_ms(first_ts)}"`, enrich from `self._rosters.get(run)`
  (`matched` = membership in `roster.numbers`), write
  `runs/<run>/annotated/<cid>.jpg` via `write_annotated_image(img, frame_results,
  resolved_zone, annotated_dir, filename=f"{cid}.jpg")` (resolve the zone per frame
  from `cv_cfg` via `zones.load_zone` + `resolve_zone(zone, img.shape[0])`), append
  `time,number` to `crossings.csv`, add to memory + id index, atomically rewrite
  `crossings.json`; **same crossing** otherwise — `last_seen = max(last_seen, t)`, and
  on better confidence re-render the annotated image, update `confidence`, rewrite
  `crossings.json` (`time` stays first-seen, OQ2). Replay of a manifest line must
  converge to identical state (idempotency, §5).
- **`crossings(label)`** — normalize, return a **copied** snapshot (design §6
  concurrency rules). **`annotated_path(id)`** — via the id index only; never parse the
  id string.
- Timestamps: parse ISO-8601 `client_ts` with `datetime.fromisoformat`; window
  comparisons in seconds; serialized fields stay the original ISO strings.

## Tests — `tests/test_engine.py`

No real inference: monkeypatch `engine.pipeline.run` to return canned
`CrossingResult`s keyed by filename; frames are tiny `cv2.imwrite`d arrays in
`tmp_path`-built run dirs (write manifest lines yourself, root-relative filenames).
Drive the engine either via `asyncio.run` around `start`/`notify`/`stop` or by calling
`_process_frame`/`_fold` directly for the pure logic. Cover at least:
- Repeated confident reads within the window → **one** crossing; after the window →
  a **second** crossing (FR9/FR10); distinct numbers → distinct crossings.
- Better-confidence fold updates `confidence` + annotated file; `time` unchanged.
- `crossings.csv` gains one row per crossing; `crossings.json` matches memory;
  `processed_offset` equals lines consumed.
- Poison frame (manifest line whose file is corrupt/missing) → logged, offset still
  advances, later lines process (FR6).
- Restart: new engine over the same dirs resumes from the offset, reloads crossings,
  and a read within the window of a persisted `last_seen` does **not** open a duplicate.
- `needs_review`/`rejected` results produce nothing (FR7).
- Roster enrichment: number in roster ⇒ name/category + `matched=True`; absent ⇒
  `name=None`, `category="Unknown"`, `matched=False` (stub `self._rosters.get` or
  monkeypatch — task4's real bodies may not exist yet).

## Acceptance criteria
- `.venv/bin/pytest tests/ collection/backend/tests/` all green
  (including task1's suites — you broke nothing).
- `.venv/bin/python run_poc.py ridersFromThBack.jpg` still works (io_out/validate defaults
  preserved; note `accept_unmatched: true` is now on in the repo config — confirm the
  POC image's output is still sane).
- Engine behavior demonstrably matches §5/§6.1: show the test run output.

## Out of scope
Roster parsing/writing (task4), per-run frame writes (task3), any HTTP or front-end
work, end-to-end runs with real models (task7).

## Final report to include
Confirm acceptance criteria; describe dedup/persistence test coverage; call out any
frozen-contract friction you had to stop on (you must **not** change §6 signatures, the
worker-loop shape, or the rosters contract).
