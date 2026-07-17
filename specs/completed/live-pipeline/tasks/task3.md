# Task 3 — Per-run frame storage

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task7
**Runs in parallel with:** tasks 2, 4, 5, 6 (disjoint files)

## Objective
Move sink 1 to the per-run layout (design §5): frames under
`runs/<safe_label>/collected/` and a **per-run** `manifest.jsonl`, instead of today's
global tree + single manifest. Update the storage test suite to the new layout.

## Read first
`../design.md` §5 (frozen on-disk layout) and §3.1 (storage row); `README.md` here
(refinement 2 — root-relative `filename`); the current
`collection/backend/storage.py` and `tests/test_frames.py`.

## Files you own
```
collection/backend/storage.py            # per-run save()
collection/backend/tests/test_frames.py  # rewrite layout expectations
```
Do **not** touch `app.py` (task1 already added the `run` field + notify), `engine.py`,
`rosters.py`, or `models.py` (`FrameMeta`/`StoredFrame`/`AppConfig` are frozen from the
collection spec and need no change).

## Implement — `storage.py`

`FrameStore.__init__` and `safe_label` are unchanged (frozen; `safe_label` is also the
run-id normalizer used by the whole back-end — do not alter it). Rework `save()`:

1. `safe = safe_label(meta.label)`; ensure `<root>/<safe>/collected/` exists.
2. `server_ts` + filename policy unchanged
   (`<safe>_<YYYYmmdd-HHMMSS-mmm>_<seq:06d>.jpg`).
3. Frame path: `<root>/<safe>/collected/<filename_base>`; bytes written verbatim
   (no re-encode, NFR1 — unchanged).
4. Manifest: append one JSON line to `<root>/<safe>/manifest.jsonl` (**per-run**, no
   global manifest). Record schema unchanged **except** `filename` is now
   `<safe>/collected/<filename_base>` — still relative to the storage root (README
   refinement 2; the engine joins it onto `run_root`).
5. `StoredFrame.filename` returns the same root-relative path (so the 201 `stored`
   field matches the manifest).

`self.manifest_name` keeps naming the per-run file (`manifest.jsonl`).

## Tests — `tests/test_frames.py`

Update the existing suite to the per-run layout — this file currently asserts the old
global layout (manifest at `<root>/manifest.jsonl` around lines 167/200/368/409; frame
paths `<root>/<safe>/*.jpg`):
- Happy path: file exists at `<tmp>/101/collected/101_*.jpg`; manifest line appended to
  `<tmp>/101/manifest.jsonl`; `filename` field == `101/collected/<name>.jpg`; 201 body
  `stored` matches and includes `"run": "101"` (task1 added the field — assert it here).
- Two labels ⇒ two run dirs, **two separate manifests**, no global manifest file.
- Restart-safe: two saves to one label append two lines to that run's manifest.
- `safe_label` cases, 400/413/415 validation, and `/health` tests carry over unchanged.

## Acceptance criteria
- `.venv/bin/pytest collection/backend/tests/` all green.
- Manual smoke: boot the app, `curl -F image=@ridersFromThBack.jpg -F label="Lap 3 /
  Nearside" -F client_ts=2026-07-17T10:00:00.000Z -F seq=0
  http://127.0.0.1:8000/frames` → 201 with `"run": "lap-3-nearside"`; on disk:
  `runs/lap-3-nearside/collected/lap-3-nearside_*.jpg` +
  `runs/lap-3-nearside/manifest.jsonl` with the root-relative `filename`.

## Out of scope
Engine/offset/crossings files (task2), rosters (task4), anything front-end.

## Final report to include
Confirm acceptance criteria; paste one manifest line so task7 can eyeball the schema;
flag (never fix) any frozen-contract friction.
