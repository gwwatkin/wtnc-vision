# Task 1 — Scaffold: modules, routes, DOM shell, config (BLOCKING)

**Agent:** sonnet  **Depends on:** —  **Blocks:** all other tasks

## Objective
Land every frozen surface the parallel tasks code against: the new back-end modules with
their exact signatures (stub bodies), the fully-wired HTTP routes (thin delegations to
the engine), the per-run config, and the complete page markup (DOM id contract). After
this task the app **boots and serves the page on :8000** with `live.enabled` true *or*
false, all existing tests green — but processes nothing yet.

## Read first
`../requirements.md` (§5), `../design.md` (§3.1 file table, §4 HTTP API, §5 disk layout,
§6 signatures, §7 config, §8 front-end structure), `README.md` in this directory
(rosters.py contract, DOM contract, disabled-route behavior, conventions).

## Files you own
```
collection/backend/live_config.py        # NEW — implement fully
collection/backend/results_models.py     # NEW — implement fully
collection/backend/engine.py             # NEW — frozen signatures, stub bodies
collection/backend/rosters.py            # NEW — frozen signatures, stub bodies
collection/backend/app.py                # extend create_app(cfg, live=None) + routes
collection/backend/__main__.py           # load live config, pass to create_app
collection/backend/config.yaml           # storage.dir: runs/ + live: section
collection/backend/tests/test_frames.py  # ONLY the minimal tweaks noted below
collection/frontend/index.html           # full DOM shell per the id contract
collection/frontend/styles.css           # base layout: camera top / timeline / sidebar
collection/frontend/config.js            # add the three §7 keys
collection/frontend/results/data.js      # NEW — placeholder module (see below)
collection/frontend/results/render.js    # NEW — placeholder module
collection/frontend/results/results.js   # NEW — placeholder entry module
collection/frontend/results/sidebar.js   # NEW — placeholder module
.gitignore                               # add runs/
```

## Back-end

- **`live_config.py`** — implement `LiveConfig` + `load_live_config(path)` exactly per
  design §6 (parses the `live:` section of the back-end `config.yaml`; returns `None`
  when the section is absent).
- **`results_models.py`** — the `Crossing` dataclass verbatim from design §6, plus a
  private `_OpenCrossing` (fields per §6.1: `crossing_id, first_seen, last_seen,
  best_conf`) for the engine's dedup state.
- **`rosters.py`** — the frozen contract from `README.md` with stub bodies that keep the
  app importable and harmless: `set` returns `(FrameStore.safe_label(label), 0)` without
  writing, `get` returns `EMPTY_ROSTER`, `list_runs` returns `[]`, `load_existing` is a
  no-op. Task4 replaces the bodies; do not change the signatures.
- **`engine.py`** — `ResultsEngine` with every frozen §6 signature. Stub bodies:
  `start`/`stop`/`notify` no-ops, `crossings(label)` → `(FrameStore.safe_label(label),
  [])`, `annotated_path` → `None`. Write the two **permanent delegations** now (task2
  keeps them): `self._rosters = RunRosters(run_root)` in `__init__`;
  `set_roster = self._rosters.set(label, csv_text)`; `runs = self._rosters.list_runs()`;
  `start` calls `self._rosters.load_existing()` before its (stub) worker launch.
  Top of file: the `sys.path` shim inserting `<repo>/src` (copy `run_poc.py`'s), then
  `from rider_id import ...` as needed — import `pipeline` as a module so tests can
  monkeypatch `pipeline.run`.
- **`app.py`** — signature becomes `create_app(cfg: AppConfig, live: LiveConfig | None
  = None) -> FastAPI`. When `live and live.enabled`: lazily import `engine` +
  `rider_id.config` inside that branch (pure collection must not import CV deps), build
  `cv_cfg = load_config(live.cv_config_path)`, construct
  `ResultsEngine(live, cv_cfg, cfg.storage_dir)`, and run `await engine.start()` /
  `await engine.stop()` from the app's lifespan. New routes, all **fully wired** as thin
  delegations (they come alive when tasks 2/4 land):
  - `GET /runs` → `{"runs": engine.runs()}`
  - `GET /results?run=…` → normalize via `engine.crossings(run)`; serialize each
    `Crossing` per the §4 sample (fields + derived
    `"annotated_url": f"/crossings/{c.crossing_id}/image"`; omit `annotated_path`)
  - `POST /roster` (multipart `run` + `roster` file) → `engine.set_roster`; map
    `ValueError` → 400 `{"status":"error","detail":…}`; success → 200
    `{"status":"ok","run":…,"count":…}`
  - `GET /crossings/{crossing_id}/image` → `FileResponse(engine.annotated_path(id))` or
    404
  - Disabled-mode behavior for all four per `README.md` refinement 3.
  - `POST /frames`: after `store.save`, add `"run": stored.safe_label` to the 201 body
    and call `engine.notify(stored.safe_label)` when the engine exists. **No other
    change** to the handler.
  - Static mount **last**: `app.mount("/", StaticFiles(directory=<collection/frontend
    resolved relative to __file__>, html=True))`. API routes and `/health` keep
    precedence (they're registered first).
- **`__main__.py`** — also `load_live_config(<same config.yaml path>)` and pass it to
  `create_app`.
- **`config.yaml`** — `storage: dir: runs/` (rename) and the `live:` section verbatim
  from design §7. Note `manifest_name` is now a per-run convention; keep the key (task3
  still reads it) but frames land per-run only after task3.
- **`tests/test_frames.py`** — run the suite; the only edits allowed are assertions
  broken by the added `"run"` field in the 201 body. Task3 owns the layout rewrite.

## Front-end

- **`index.html`** — full markup per the frozen DOM id contract (README): keep the
  existing controls; add source selector, video file input, roster upload controls,
  run selector, `<main id="timeline">`, `<aside id="sidebar" hidden>` with
  `#sidebar-close`. Script tags: `config.js`, `app.js`, then
  `<script type="module" src="results/results.js">`.
- **`styles.css`** — layout only: capture block on top, timeline below, sidebar beside
  the timeline (below a ~640px breakpoint it may overlay), sensible empty states.
  Task5 adds card/sidebar detail styles.
- **`config.js`** — add exactly the three §7 keys: `BACKEND_URL: ""`,
  `RESULTS_POLL_MS: 1500`, `DEFAULT_SOURCE: "camera"`. Existing keys unchanged.
- **`results/*.js`** — placeholder ES modules so the page loads without 404s/errors:
  `results.js` may render a static "waiting for results" state into `#timeline`;
  `data.js`/`render.js`/`sidebar.js` just export empty stubs. Task5 owns the real
  bodies; don't over-build.

## Acceptance criteria
- `.venv/bin/pytest collection/backend/tests/` green.
- The back-end (`../.venv/bin/python -m backend` from `collection/`) with
  `live.enabled: true` boots (engine no-ops),
  and with `enabled: false` boots **without importing** `rider_id`/cv2.
- `http://localhost:8000` serves the page: capture controls on top, empty timeline
  below, hidden sidebar; browser console error-free.
- `GET /runs` → `{"runs": []}`; `GET /results?run=x` → `{"run":"x","crossings":[]}`;
  `POST /frames` 201 body includes `"run"`; with live disabled the four routes behave
  per README refinement 3.
- `git status` shows no generated `runs/` output tracked (`.gitignore` updated).

## Out of scope
Real processing, per-run frame storage, roster parsing, timeline rendering, capture
changes — tasks 2–6.

## Final report to include
Confirm acceptance criteria; list the exact stub behaviors and any test_frames tweaks
made; flag (never fix) anything that seems to contradict a frozen contract.
