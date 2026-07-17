# Task 4 — Per-run rosters

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task7
**Runs in parallel with:** tasks 2, 3, 5, 6 (disjoint files)

## Objective
Implement `RunRosters` — parse an uploaded `number,name,category` CSV, atomically write
one run's `roster.csv` + `roster.txt`, and hold the immutable in-memory `Roster` the
engine reads for enrichment. This makes `POST /roster` and `GET /runs` real (task1
already wired the routes to `engine.set_roster`/`engine.runs`, which delegate to you).

## Read first
`../requirements.md` §5.5 (FR16–FR20); `../design.md` §1 (D6/OQ8 rows), §4
(`POST /roster`, `GET /runs`), §5 (roster files), §6 (concurrency conventions);
`README.md` here — the **frozen `rosters.py` contract** you are implementing.

## Files you own
```
collection/backend/rosters.py             # implement the frozen contract
collection/backend/tests/test_rosters.py  # NEW
```
Do **not** touch `engine.py`, `app.py`, `storage.py`, or their tests.

## Implement — `rosters.py`

Signatures are frozen in `tasks/README.md`; behavior:

- **`set(label, csv_text)`** —
  1. `label.strip()` empty → `ValueError("run label must not be blank")` (task1's route
     maps `ValueError` → the 400 body).
  2. `run = FrameStore.safe_label(label)`.
  3. Parse with `csv.reader` (handles quoted fields): rows need ≥3 cells with a
     non-empty digit-string number; `name`/`category` are stripped text. A first row
     whose number cell isn't numeric is treated as a header and skipped; other bad rows
     are skipped silently (mirrors the old viewer's tolerance). Later duplicate numbers
     win. **Zero accepted rows → `ValueError`** with a human-readable reason — and no
     files touched, no state changed (FR19: previous roster stays active).
  4. Parse-then-swap: only after a successful parse, `os.makedirs(run dir, exist_ok=
     True)` (roster before first frame is the normal flow), atomically write
     `roster.csv` (the accepted rows, normalized `number,name,category` lines) and
     `roster.txt` (numbers, one per line) — temp file + `os.replace` each.
  5. Rebind `self._by_run[run]` to a **new** frozen `Roster` (replace-don't-mutate —
     the worker thread reads it lock-free).
  6. Return `(run, count)`.
- **`load_existing()`** — scan `run_root/*/roster.csv`, parse each with the same rules,
  populate the in-memory map (used by `engine.start` so enrichment survives restart).
  A malformed on-disk roster is logged and skipped, never fatal.
- **`get(run)`** — current `Roster` or `EMPTY_ROSTER`. **`roster_txt_path(run)`** — the
  path whether or not the file exists (missing file ⇒ `validate.load_roster` returns
  `None` ⇒ confidence-only mode, FR20). **`list_runs()`** — directory names directly
  under `run_root` (a run exists once captured-to *or* rostered), `[]` when the root
  doesn't exist yet.

## Tests — `tests/test_rosters.py`

`tmp_path` as `run_root`. Cover:
- Happy path: header + quoted names + 2 rows → `(safe_id, 2)`; files exist; `roster.txt`
  = numbers; `get` returns both entries; raw label `"Lap 3 / Nearside"` normalizes.
- Replacement: second `set` for the same run fully supersedes (old number gone from
  files and memory); the returned `Roster` object is a **new** instance (FR18 + the
  swap rule).
- Rejection: empty text, header-only, and all-bad-rows each raise `ValueError` and
  leave a previously-written roster intact on disk **and** in memory (FR19).
- Duplicate numbers: later row wins.
- `list_runs` sees a rostered-but-never-captured run; `load_existing` on a fresh
  instance restores state; `get` on unknown run → `EMPTY_ROSTER`;
  `roster_txt_path` for a roster-less run points at a non-existent file.
- Route-level (FastAPI `TestClient`, engine enabled with a stub/no-op worker is fine —
  task1's stubs delegate to you): `POST /roster` happy → 200 `{"status":"ok","run":…,
  "count":…}`; malformed → 400 error body; then `GET /runs` lists the run.

## Acceptance criteria
- `.venv/bin/pytest collection/backend/tests/` all green.
- Manual: boot the app; `curl -F run="Lap 3 / Nearside" -F roster=@- ...` (or a temp
  CSV file) → 200 with `run: lap-3-nearside`, files under `runs/lap-3-nearside/`;
  a garbage upload → 400 and the previous files untouched.

## Out of scope
How the engine consumes rosters at process time (task2), the upload button (task6),
name/category display (task5).

## Final report to include
Confirm acceptance criteria; state the exact parse-acceptance rules you implemented
(header detection, bad-row policy) so task7 can document them; flag any contract
friction rather than diverging.
