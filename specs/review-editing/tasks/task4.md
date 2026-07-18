# Task 4 — Engine integration: edits, order, status, absorb-only reconciliation

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task9
**Runs in parallel with:** tasks 2, 3, 5–8 (disjoint files — your tests FAKE the
task2/task3 classes; see Testing)

## Objective
Implement every new engine body (design §4.4): status with cached manifest stats,
frame serving with traversal guard, manual crossing creation, number edit / soft
delete, order-of-record positioning, candidate resolution, the three worker-loop
lines, the `_fold` changes, restart rebuild of absorb state, and lock discipline
(§8). Plus the §7 reconciliation rules in full.

## Read first
`../design.md` §4.4 (frozen signatures + semantics), §7 (reconciliation — read it
twice, including the collision rule and the restart paragraph), §8 (locking), §3.1
(loader rule). `../requirements.md` FR5–FR11, FR16–FR22, SC4–SC6. `README.md`
refinements 3, 4, 5, 6, 9.

## Files you own
```
collection/backend/engine.py                    # implement task1's stubs + worker/_fold/start/crossings changes
collection/backend/tests/test_engine.py         # existing — extend/adjust only where ordering assumptions change
collection/backend/tests/test_engine_review.py  # NEW — all new-behavior tests
```
Do **not** touch `candidates.py`/`frames_index.py` (call their frozen APIs),
`edits.py`, `app.py`, `results_models.py`, or the front-end.

## Implement — cross-cutting
- **Lock (§8):** every mutation of `_crossings`/`_crossing_index`/`_open` and every
  persistence call runs under `self._lock` (task1 created it). `_fold` acquires it;
  each new public method body acquires it. Reads (`crossings`, `candidates`,
  `status`) take it only to copy snapshots.
- **Loader rule (§3.1):** in `_load_crossings_json`, after constructing each
  `Crossing`, `order_key == 0.0` ⇒ `order_key = float(_epoch_ms(time))`.
- **`_fold`:** (a) new crossings get `order_key = float(_epoch_ms(t))`;
  (b) call `self._candidates.suppress_around(run, t)` on **every** fold path;
  (c) when the open crossing has `absorb_only=True`, update `last_seen` only and
  return — no confidence bump, no re-annotation (§7); (d) if the target crossing
  is `deleted`, absorb silently too (tombstone — never resurrect); (e) refactor the
  enrichment block to `edits.enrich` (refinement 6).
- **Worker (`_process_frame`), after `pipeline.run`:** the three §4.4 lines —
  `self._frames.append(...)` always (guard on `live.frames_index_enabled`);
  compute `had_confident`; existing fold loop unchanged; then
  `self._candidates.observe(...)` (guard on `live.candidates_enabled`). Tracker
  calls happen under `self._lock` (refinement 5).
- **`start()`:** after rebuilding `_open`, set `absorb_only=True` for crossings
  with `source == "manual"`, `edited`, or `deleted` (§7 restart); call
  `self._candidates.load_existing()`.
- **`crossings(label)`:** filter `deleted`, sort ascending `(order_key, time)`.

## Implement — new public methods (§4.4 semantics, plus)
- `status`: counts per A3; manifest stats cached per run keyed on the file's
  `(mtime, size)` — an idle poll must not re-read the manifest (NFR2);
  `processed_through` = `client_ts` of the last processed manifest entry (None at
  offset 0); `candidates_open` = count of open candidates.
- `frames`: delegate to `self._frames.frames`/`.meta`; shape per §5 route contract
  (the route adds URLs — refinement 9).
- `frame_path`: normalized absolute path must be under
  `<run_root>/<run_id>/collected/` — else `None`.
- `create_crossing`: §4.4 verbatim — `cid = f"{run}-manual-{epoch_ms(client_ts)}"`,
  `source="manual"`, `confidence=0.0`, enrich via `edits.enrich`, representative =
  copy of the raw frame into `annotated/<cid>.jpg` (plain `cv2.rectangle` when
  `box` given), append `time,number` to `crossings.csv` (refinement 3), register
  absorb-only `_open` entry when `number != ""` **subject to the §7 collision
  rule**, persist, return the `Crossing`.
- `edit_crossing`: number ⇒ set + re-enrich + `edited=True` + re-point BOTH old and
  new number absorb entries per §7 (collision rule on each side); deleted ⇒ set
  flag (restore = False) and on delete flip its `_open` entry to absorb-only
  tombstone; unknown id ⇒ `KeyError`; persist.
- `set_position`: validate ≥1 neighbor, same-run membership (else `ValueError`),
  `order_key = edits.midpoint_key(...)` (neighbors' keys in ASC order-of-record),
  `order_overridden=True`, persist.
- `candidates`: normalize label, snapshot from tracker.
- `resolve_candidate`: dismiss ⇒ `set_state("dismissed")`; promote ⇒
  `create_crossing(run, rep_filename, cand.time, number, box=rep_box)` then
  `set_state("promoted", cid)`; returns `{"candidate": …, "crossing": …?}` dicts.
- `candidate_image_path`: absolute path of `rep_filename` under the run root (same
  traversal stance as `frame_path`).

## Testing
Monkeypatch `engine.CandidateTracker` and `engine.FramesIndex` with in-memory fakes
**before constructing the engine** (refinement 4) — record calls, implement just
enough (`observe`, `suppress_around`, `load_existing`, `set_state`, `get`, `list`).
Keep monkeypatching `engine.pipeline.run` as today. Real-object integration is
task9's job. Extend `test_engine.py` only where the new sort/filter changes old
assertions; put everything new in `test_engine_review.py`:
- Old-schema `crossings.json` loads with defaults; `order_key` derived from time.
- `crossings()` excludes deleted, sorts by `(order_key, time)`; a new auto crossing
  slots between moved ones by time without touching overrides (FR11 / SC5).
- `set_position` midpoints (between / top / bottom), cross-run neighbor ⇒
  `ValueError`, unknown id ⇒ `KeyError`.
- `create_crossing`: id format, provenance fields, annotated copy exists (with and
  without box), csv row appended, absorb entry installed; collision rule — number
  with a live (non-absorb) open crossing ⇒ no absorb entry installed, live crossing
  keeps folding normally.
- `edit_crossing`: re-enrich against roster, `edited=True`; late read of old AND
  new number absorbed (no clobber, no duplicate — FR22); delete ⇒ excluded from
  `crossings()`, late read absorbed, restore works; unknown id ⇒ `KeyError`.
- Absorb-only fold: `last_seen` bumps, confidence/annotation untouched.
- `suppress_around` called on every fold path (assert via fake): new crossing,
  same-crossing update, absorb-only.
- Restart: engine #2 over the same dirs marks manual/edited/deleted crossings
  absorb-only (drive `start()`/`stop()` like existing tests).
- `status`: counts + `processed_through` correct mid-backlog and when drained;
  cached stats not re-read on unchanged manifest (assert by mtime-freezing or a
  read-counting monkeypatch).
- `frame_path` traversal guard (`../`, absolute, other-run filenames ⇒ None).
- Worker wiring: `_process_frame` calls `frames.append` always and
  `candidates.observe` with the right `had_confident`; disabled flags skip them.

## Acceptance criteria
`.venv/bin/pytest collection/backend/tests/ tests/` fully green.

## Out of scope
Real `CandidateTracker`/`FramesIndex` internals, HTTP routes, front-end.

## Final report to include
Confirm acceptance; map each §7 rule to the test that proves it; flag any contract
friction (STOP rule — especially if a §4.4 signature fights the implementation).
