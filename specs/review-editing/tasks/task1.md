# Task 1 — Scaffold: models, config, routes, stubs, DOM shell, CSS

**Agent:** sonnet  **Depends on:** —  **Blocks:** everything (wave A, run alone)

## Objective
Land every frozen contract as real code so tasks 2–8 can run in parallel against it:
extended dataclasses, new `LiveConfig` keys, the `det_conf` plumbing in `rider_id`,
all new HTTP routes (wired to engine method stubs), complete `edits.py` helpers with
tests, module stubs for `candidates.py`/`frames_index.py` and the three new JS
modules, the DOM additions, and the full stylesheet for the new UI.

## Read first
`../design.md` §2–§5 (data model, module signatures, HTTP API), §9 (config);
`README.md` here — especially refinements 1, 2, 6, 7, 9 and both FROZEN blocks.

## Files you own
```
collection/backend/results_models.py       # extend Crossing/_OpenCrossing, add Candidate
collection/backend/live_config.py          # new LiveConfig fields + parsing
collection/backend/config.yaml             # live.candidates / live.frames_index blocks
collection/backend/edits.py                # NEW — implement FULLY (refinement 6)
collection/backend/candidates.py           # NEW — stub (frozen signatures, NotImplementedError)
collection/backend/frames_index.py         # NEW — stub (frozen signatures, NotImplementedError)
collection/backend/engine.py               # ONLY: imports, __init__ wiring, new method stubs
collection/backend/app.py                  # all new routes (§5 + GET /roster)
collection/backend/tests/test_edits.py     # NEW
collection/backend/tests/test_review_api.py# NEW — disabled-mode shells/503s
src/rider_id/types.py                      # CrossingResult.det_conf = 0.0 (refinement 1)
src/rider_id/pipeline.py                   # populate det_conf from RiderBox
collection/frontend/index.html             # DOM id contract additions
collection/frontend/config.js              # FRAMES_SPAN_S, FRAMES_LIMIT
collection/frontend/styles.css             # ALL new rules (refinement 7)
collection/frontend/results/status.js      # NEW — stub
collection/frontend/results/edits.js       # NEW — stub
collection/frontend/results/browser.js     # NEW — stub
```
Do **not** touch `results/{data,render,sidebar,results}.js`, `rosters.py`,
`storage.py`, or any existing test file.

## Implement — data model & config
- `results_models.py`: extend `Crossing` with the five §3.1 fields (defaults exactly
  as written — old JSON must load via `Crossing(**item)`); add the `Candidate`
  dataclass (§3.2) verbatim; add `absorb_only: bool = False` to `_OpenCrossing`.
- `live_config.py`: add the five §9 fields; `load_live_config()` parses
  `live.candidates.*` / `live.frames_index.*`; absent `candidates.window_s` resolves
  to `dedup_window_s` at load time. Absent blocks ⇒ dataclass defaults.
- `config.yaml`: add the §9 blocks with the documented defaults.
- `rider_id` (refinement 1): `CrossingResult` gains `det_conf: float = 0.0` as the
  **last** field; in `pipeline.run`, pass the rider's `RiderBox.det_conf` through.
  No other behavior change; existing tests must stay green untouched.

## Implement — `edits.py` (complete, frozen §4.3)
`midpoint_key` and `enrich` exactly per §4.3. `enrich` mirrors the enrichment block
in today's `engine._fold` (matched = membership in `roster.numbers`; unmatched or
`number == ""` ⇒ `(None, "Unknown", False)`) — task4 will refactor `_fold` to call it.

## Implement — stubs
- `candidates.py`: class `CandidateTracker` with every §4.2 method at its frozen
  signature; `__init__` stores its args; other bodies `raise NotImplementedError`.
  Docstring notes it is NOT thread-safe — callers hold the engine lock
  (refinement 5).
- `frames_index.py`: class `FramesIndex` likewise (§4.1).
- `engine.py` — **surgical additions only**, nothing else moves:
  - `from .candidates import CandidateTracker` / `from .frames_index import
    FramesIndex` (module-level names — monkeypatch points, refinement 4).
  - `__init__`: `self._lock = threading.RLock()`; construct `self._candidates =
    CandidateTracker(run_root, live.candidate_window_s, live.candidate_min_det_conf,
    live.candidate_statuses)` and `self._frames = FramesIndex(run_root)`.
  - Add every new §4.4 public method (`status`, `frames`, `frame_path`,
    `create_crossing`, `edit_crossing`, `set_position`, `candidates`,
    `resolve_candidate`, `candidate_image_path`) at its frozen signature, body
    `raise NotImplementedError` (task4 implements). Do NOT touch the worker,
    `_fold`, `start`, or `crossings`.
- JS stubs (frozen exports per README): `status.js` `pollStatus` no-op; `edits.js`
  functions `throw new Error("not implemented")` (and `loadRosterNumbers` no-op);
  `browser.js` `openBrowser` renders a "frame browser not available yet"
  placeholder into `#sidebar-content`. The page must keep working exactly as today.

## Implement — `app.py` routes (§5 + refinement 2)
All routes from the §5 table plus `GET /roster?run=`. Follow the existing patterns:
raw label in, `FrameStore.safe_label` normalization server-side; disabled
(`engine is None`) ⇒ GET shells / mutating 503 exactly as §5 specifies
(`GET /status` ⇒ `{"enabled": false}`; `GET /roster` ⇒ `{"run": …, "riders": []}`);
`KeyError → 404`, `ValueError → 400` via the existing exception shape. Engine calls
go through `asyncio.to_thread` for every mutating route **and** `status`/`frames`
(§4.4). Image routes use `FileResponse`, 404 when the engine returns `None`.
`GET /frames`: `span` default 12, `limit` default 300 capped at 300; each frame dict
gains its `"url"` (refinement 9). PATCH body must contain ≥1 of `number`/`deleted`
else 400. Routes compile against the engine stubs (they'll 500 until task4 — fine).

## Implement — front-end shell
- `index.html`: every element in the DOM id contract, positioned per §6.5;
  `#queue-status` starts hidden; toggle checked; `<script>` tags for the three new
  modules are NOT needed (`results.js` imports them as ES modules).
- `config.js`: `FRAMES_SPAN_S: 12`, `FRAMES_LIMIT: 300` (comment: frozen keys).
- `styles.css` (refinement 7): status dot (green/amber variants), provenance badges
  (`✚ manual` / `✎ edited` / `↕ moved` — small inline markers), `.card--candidate`
  (dashed border, muted colors), sidebar action rows + inline number input,
  filmstrip strip (horizontal scroll, thumb highlight for current frame), main-view
  canvas overlay positioning, scrubber row, "no outcome data" note. Class names are
  the contract siblings code against — list them in your final report.

## Tests
- `test_edits.py`: midpoint between neighbors; top-of-order (`later − 60_000`);
  bottom (`earlier + 60_000`); `earlier >= later` ⇒ `ValueError`; `enrich` matched /
  unmatched / empty-number cases against a hand-built `Roster`.
- `test_review_api.py`: app created **without** live config — every new GET returns
  its empty shell, every mutating route returns the 503 error shape, both image
  routes 404, `GET /roster` returns the empty shell. (Use the existing httpx test
  client pattern from `test_frames.py`.)

## Acceptance criteria
- `.venv/bin/pytest collection/backend/tests/ tests/` fully green (existing suites
  untouched and passing — the `det_conf` default guarantees it).
- `.venv/bin/python -c "from backend import app"`-style imports work — verify via
  the test client, not by running the server.
- Front-end: `./collection/run.sh` NOT required; confirm `index.html` references
  and module stubs are syntactically valid (`node --check` per file where DOM-free).

## Out of scope
Any real body of `candidates.py`/`frames_index.py`/the new engine methods; worker
or `_fold` changes; any behavior in the four existing `results/*.js` files.

## Final report to include
The exact list of CSS class names you froze; confirmation the engine stubs match §4.4
signatures character-for-character; any contract friction (STOP rule applies).
