# Live Pipeline — Task Plan

Delegation plan for the **collection → processing → live results** feature described in
`../requirements.md` and `../design.md`. Each `taskN.md` is scoped for **one subagent**
working from a cold start: self-contained, names the files it owns, codes against the
frozen contracts.

## Read-first (every agent)
- `../requirements.md` — what & why (esp. §5 FRs, §8 success criteria)
- `../design.md` — the frozen contracts: §4 HTTP API, §5 on-disk layout, §6 back-end
  signatures + worker loop + dedup algorithm (§6.1), §7 config, §8 front-end structure
- This file — dependency graph, waves, and the shared conventions below (they refine the
  design where the task split needed it)

## Dependency graph

```
                 task1  (scaffold: modules, routes, DOM shell, config)
                   │  ← BLOCKING: must land before anything else starts
   ┌───────┬───────┼──────────────┬───────────────┐
   ▼       ▼       ▼              ▼               ▼
 task2   task3   task4          task5           task6      ← PARALLEL (disjoint files)
 engine  per-run rosters      front-end       front-end
 + CV    storage module       results+sidebar capture+video+roster UI
   └───────┴───────┴──────────────┴───────────────┘
                   ▼
                 task7  (integration, tuning, run.sh, delete web/, READMEs)
```

## Suggested waves
- **Wave A:** task1 alone (sonnet). Everything below codes against what it lands.
- **Wave B:** tasks 2–6 in parallel (sonnet each) — exclusive file ownership, no overlap.
- **Wave C:** task7 (sonnet) — end-to-end verification, tuning, cleanup.

## Task-split refinements (decided here, frozen for this run)

The design's contracts stand unchanged; these three points resolve ambiguities the task
split exposed. **Flagged for human review before wave A.**

1. **`rosters.py` extraction.** Design §12 lists *Engine* and *Roster* as separate
   parallel tasks but §3.1 puts both in `engine.py` — that breaks exclusive ownership.
   Resolution: per-run roster state moves to a new module
   `collection/backend/rosters.py` (contract below, created as stubs by task1, owned by
   task4). `ResultsEngine.set_roster` / `ResultsEngine.runs` keep their **frozen §6
   signatures** and become one-line delegations written once by task1 — task2 and task4
   never edit the same file.
2. **Manifest `filename` stays storage-root-relative.** Under the per-run layout (§5) a
   manifest line's `filename` (and the 201 `stored` field) is
   `<safe_label>/collected/<name>.jpg`, relative to `storage.dir` — the engine resolves
   frames as `os.path.join(run_root, entry["filename"])` with no per-run path logic.
3. **Routes with live processing disabled** (`live` absent or `enabled: false`, NFR6):
   `GET /runs` → `{"runs": []}`; `GET /results?run=…` → `{"run": <safe>, "crossings": []}`;
   `POST /roster` → **503** `{"status":"error","detail":"live processing disabled"}`;
   `GET /crossings/{id}/image` → 404. Capture/storage and the page itself work unchanged.

### FROZEN — `collection/backend/rosters.py` (created by task1, implemented by task4)

```python
@dataclass(frozen=True)
class Roster:
    numbers: frozenset[str]               # valid-number set (mirrors roster.txt)
    entries: dict[str, tuple[str, str]]   # number -> (name, category)

EMPTY_ROSTER = Roster(frozenset(), {})

class RunRosters:
    def __init__(self, run_root: str) -> None: ...
        # run_root = AppConfig.storage_dir (holds runs/<safe_label>/)
    def load_existing(self) -> None: ...
        # scan run_root/*/roster.csv into memory (engine.start calls this)
    def set(self, label: str, csv_text: str) -> tuple[str, int]: ...
        # FrameStore.safe_label(label) -> run id; parse number,name,category
        # (header tolerated, quoted fields ok); create the run dir if needed;
        # ATOMICALLY write roster.csv + roster.txt; rebind the in-memory Roster
        # (replace, don't mutate — design §6 concurrency rules);
        # return (run_id, accepted_row_count). Raise ValueError on blank label
        # or a roster with zero parseable rows — previous roster stays active.
    def get(self, run: str) -> Roster: ...
        # current Roster for a safe run id; EMPTY_ROSTER when none uploaded
    def roster_txt_path(self, run: str) -> str: ...
        # run_root/<run>/roster.txt — returned even if the file doesn't exist
        # (validate.load_roster then yields None = confidence-only mode, FR20)
    def list_runs(self) -> list[str]: ...
        # run ids = directories under run_root (exists once captured-to or rostered)
```

### FROZEN — DOM id contract (markup created by task1; behavior split 5/6)

| id | element | behavior owner |
|---|---|---|
| `camera-select`, `label-input`, `toggle-btn`, `preview`, `status` | existing capture controls | task6 (`app.js`, as today) |
| `source-select` | `<select>`: `camera` \| `video` (D7) | task6 |
| `video-file` | `<input type=file accept="video/*">` | task6 |
| `roster-file`, `roster-upload-btn`, `roster-status` | roster upload control + feedback line | task6 |
| `run-select` | `<select>` of known runs (`GET /runs`) | task5 |
| `timeline` | `<main>` — `renderTimeline` root | task5 |
| `sidebar`, `sidebar-close` | `<aside hidden>` + its close button | task5 |

**`label-input` is the active run** (design §8). `results/results.js` reads its raw value
on every poll tick (the back-end normalizes); picking a run in `run-select` simply sets
`label-input.value`. `app.js` and `results/*.js` are separate script entry points that
share **only** this DOM contract — no imports, no events between them.

## Shared conventions (all agents)
- **Do not change the frozen contracts** — design §4/§5/§6/§7 and the blocks above. If
  one is genuinely wrong, **stop and flag it in your final report**; never silently
  diverge — siblings depend on it.
- **File ownership is exclusive.** Only edit files your task lists under "Files you own."
- **One process, one port, same origin** (:8000, OQ6). `BACKEND_URL` is `""` — all
  front-end fetches are relative paths.
- **Run ids are normalized server-side only** via `FrameStore.safe_label`; the front-end
  always sends the raw label and uses the echoed safe id.
- **`/results` is JSON, already enriched** — the front-end never parses CSV; `web/csv.js`
  is *not* copied into `results/`.
- **Python 3.12 venv only** — call its binaries directly from the repo root
  (`.venv/bin/pytest`, `.venv/bin/python`); never system `python3`, never
  `source .venv/bin/activate && …` chains (they trigger permission prompts — CLAUDE.md).
  Back-end tests: `.venv/bin/pytest collection/backend/tests/`; rider_id tests:
  `.venv/bin/pytest tests/`.
- **`rider_id` is not pip-installed.** `engine.py` carries the same `sys.path` shim as
  `run_poc.py` (inserting `<repo>/src`), added by task1 — don't add another.
- **Engine unit tests must not run real inference** — monkeypatch `pipeline.run`
  (engine calls it as `pipeline.run(...)` on the imported module for exactly this
  reason). No model downloads in unit tests.
- **Front-end is a static site — no build step.** `results/*.js` are ES modules
  (entry: `<script type="module" src="results/results.js">`); `app.js` stays a plain
  script, as today.
- **Atomic writes** for anything a reader may see mid-write: temp file + `os.replace`
  (`processed_offset`, `crossings.json`, `roster.csv`, `roster.txt`). Append-only for
  `manifest.jsonl` and `crossings.csv`.

## Generated data
`runs/` (frames, manifests, crossings, annotated images, rosters) is generated output —
**gitignored, never committed**. Task1 updates `.gitignore` (the old `collected/` entry
stays for pre-spec data). Old `collected/` data is **not migrated** (design §5).
