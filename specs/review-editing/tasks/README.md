# Review & Editing — Task Plan

Delegation plan for the **frames / manual crossings / order / queue status** feature
described in `../requirements.md` and `../design.md`. Each `taskN.md` is scoped for
**one subagent** working from a cold start: self-contained, names the files it owns,
codes against the frozen contracts.

## Read-first (every agent)
- `../requirements.md` — what & why (esp. §5 FRs, §8 success criteria)
- `../design.md` — the frozen contracts: §2 on-disk layout, §3 data model, §4 back-end
  modules, §5 HTTP API, §6 front-end, §7 reconciliation, §8 concurrency, §9 config
- This file — dependency graph, waves, task-split refinements, and the shared
  conventions at the bottom (they refine the design where the task split needed it)

## Dependency graph

```
                     task1  (scaffold: models, config, routes, stubs, DOM, CSS)
                       │  ← BLOCKING: must land before anything else starts
   ┌─────────┬─────────┼─────────┬──────────┬──────────┬──────────┐
   ▼         ▼         ▼         ▼          ▼          ▼          ▼
 task2     task3     task4     task5      task6      task7      task8    ← PARALLEL
 candi-    frames    engine    data.js    status.js  sidebar.js browser.js
 dates.py  _index.py integr.   render.js  results.js edits.js
   └─────────┴─────────┴─────────┴──────────┴──────────┴──────────┘
                       ▼
                     task9  (integration, end-to-end verification, docs)
```

## Waves
- **Wave A:** task1 alone (sonnet). Everything below codes against what it lands.
- **Wave B:** tasks 2–8 in parallel (sonnet each) — exclusive file ownership, no
  overlap. Task4's unit tests **fake** the task2/task3 classes (refinement 4), so
  nothing in the wave waits on a sibling.
- **Wave C:** task9 (sonnet) — real-collaborator test run, end-to-end verification,
  cross-module fixes, docs.

Waves are gated on explicit operator go-ahead; commit checkpoints between waves.

## Ownership map

| task | model | owns (exclusive during wave B) |
|---|---|---|
| 1 | sonnet | `collection/backend/{results_models,live_config,edits}.py`, `config.yaml`, `app.py`, stubs of `engine.py` additions + `candidates.py` + `frames_index.py`, `src/rider_id/{types,pipeline}.py`, `tests/{test_edits,test_review_api}.py`, `frontend/{index.html,config.js,styles.css}`, stubs of `results/{status,edits,browser}.js` |
| 2 | sonnet | `collection/backend/candidates.py`, `tests/test_candidates.py` |
| 3 | sonnet | `collection/backend/frames_index.py`, `tests/test_frames_index.py` |
| 4 | sonnet | `collection/backend/engine.py`, `tests/test_engine.py`, `tests/test_engine_review.py` |
| 5 | sonnet | `frontend/results/data.js`, `frontend/results/render.js` |
| 6 | sonnet | `frontend/results/status.js`, `frontend/results/results.js` |
| 7 | sonnet | `frontend/results/sidebar.js`, `frontend/results/edits.js` |
| 8 | sonnet | `frontend/results/browser.js` |
| 9 | sonnet | integration — ownership released; also `README.md` (repo) |

Paths `tests/…` above mean `collection/backend/tests/…`; `frontend/…` means
`collection/frontend/…`.

## Task-split refinements (decided here, frozen for this run)

The design's contracts stand unchanged; these resolve gaps the task split exposed.
**Flagged for human review before wave A.**

1. **`CrossingResult.det_conf` plumbing.** Design §3.3/§4.2 consume a per-rider
   detector confidence, but `src/rider_id/types.py::CrossingResult` doesn't carry
   one (it's dropped inside `pipeline.run`; `RiderBox.det_conf` has it).
   Resolution: `CrossingResult` gains `det_conf: float = 0.0` (last field, default
   keeps every existing constructor call valid) and `pipeline.run` populates it from
   the rider's `RiderBox.det_conf`. No behavior change anywhere else. Owner: task1.
2. **`GET /roster?run=` read endpoint.** §6.4/§6.4-browser need a roster
   `<datalist>`, but the API only has `POST /roster`. Resolution: new route
   `GET /roster?run=` → `{"run": <safe>, "riders": [{"number", "name", "category"},
   …]}` sorted by number, `[]` when no roster; disabled ⇒ same empty shell (GET
   pattern). Backed by `RunRosters.get` — no new engine method; the route reads the
   roster via the engine's existing rosters object. Owner: task1 (route),
   `edits.js::loadRosterNumbers` (client, task7).
3. **`crossings.csv` scope.** `create_crossing` appends `time,number` to
   `crossings.csv` exactly like an auto fold (the csv stays an append-only creation
   log). Edits, deletes, and reorders do **not** touch the csv — `crossings.json`
   is the source of truth for current state.
4. **Engine collaborators are monkeypatch points.** `engine.py` imports the classes
   as module attributes (`from .candidates import CandidateTracker`,
   `from .frames_index import FramesIndex`) and constructs them via those names, so
   task4's tests monkeypatch `engine.CandidateTracker`/`engine.FramesIndex` with
   fakes (same pattern as `engine.pipeline.run`). Real-object integration is task9.
5. **`CandidateTracker` is not internally thread-safe.** Every call (worker `observe`
   / `suppress_around`, HTTP `set_state`) happens under the engine's `self._lock`
   (§8). Task2 documents this in the class docstring and does not add its own lock.
6. **`edits.py` ships complete in the scaffold.** `midpoint_key`/`enrich` are pure
   ~20-line helpers that engine work and tests depend on; task1 implements + tests
   them. Task4 refactors `_fold`'s enrichment block to call `enrich` (no dup logic).
7. **`styles.css` has one owner.** Task1 writes all new rules (§6.5: status dot,
   badges, `.card--candidate`, filmstrip, canvas overlay, sidebar action rows,
   frame-browser layout). Wave-B tasks only *use* class names; if a rule is missing
   or wrong, note it in the final report for task9 — don't edit the file.
8. **"Move earlier / Move later" neighbor rule.** The timeline displays newest-first
   (DESC by `order_key`); order-of-record is ASC. Neighbors are computed from the
   DOM: all `[data-crossing-id]` cards in `#timeline` in document order, **skipping
   candidate cards** (`data-candidate-id` — candidates aren't in the order of
   record). *Move earlier* (down in the DESC display): let `Y` = card below the
   selected one, `Z` = card below `Y`; call the position endpoint with
   `earlier_id = Z?.id ?? null`, `later_id = Y.id`. *Move later* is symmetric with
   the cards above. Button disabled at the respective end.
9. **Serialization.** Crossing/Candidate dicts are `dataclasses.asdict` outputs;
   `/results` crossings automatically gain the new fields (design §5), candidate
   dicts gain `"image_url": "/candidates/<id>/image"`, frame dicts gain
   `"url": "/frames/image?run=…&filename=…"` (query-string-encoded).

### FROZEN — DOM id contract (markup created by task1)

| id | element | behavior owner |
|---|---|---|
| `queue-status` | `<div>` under `#status`, initially hidden | task6 (`status.js`) |
| `browse-frames-btn` | button in `#run-controls` | task6 wires click → `openBrowser` |
| `candidates-toggle` | checkbox in `#run-controls`, **checked** by default | task6 reads it per tick |
| `candidates-toggle-count` | `<span>` inside the toggle's label (open count) | task6 |
| `roster-numbers` | `<datalist>` (empty) | task7 (`edits.js::loadRosterNumbers`) |
| existing: `timeline`, `sidebar`, `sidebar-content`, `sidebar-close`, `label-input`, `run-select`, `status` | unchanged | as today |

### FROZEN — JS module contracts (stubs created by task1)

```js
// results/status.js                                  (implemented by task6)
export async function pollStatus(label)
  // fetch GET /status?run=label, render #queue-status (§6.1); its own
  // unchanged-payload skip; hides the element when label is "" or enabled:false;
  // never throws (network errors leave the last render in place).

// results/edits.js                                   (implemented by task7)
export async function createCrossing({ run, filename, clientTs, number })
export async function patchCrossing(crossingId, { number, deleted })   // ≥1 key
export async function setPosition(crossingId, { earlierId, laterId })  // null ok
export async function resolveCandidate(candidateId, { action, number })
export async function loadRosterNumbers(run)
  // fills #roster-numbers <datalist> from GET /roster; returns the riders array.
  // Every mutator: on 2xx dispatch new CustomEvent("wtnc:edited") on document and
  // return the parsed body; on non-2xx throw Error(detail).

// results/browser.js                                 (implemented by task8)
export function openBrowser({ run, centerTs })
  // renders frame-browser mode into #sidebar-content (opens #sidebar if closed);
  // centerTs: ISO string anchor, or null ⇒ anchor at meta.last_ts.

// results/sidebar.js — existing exports unchanged; openSidebar(result) now also
// accepts pseudo-results with isCandidate: true (candidate mode, §6.4).
```

## Shared conventions — READ BEFORE RUNNING ANY COMMAND

These exist so your commands match the session's permission allowlist. A command
that doesn't match the expected shape triggers an approval prompt **and stalls
the entire run** — the operator is not watching your prompt.

- **Working directory: the repo root.** Never `cd` anywhere, not even as part of
  a compound command. If a command needs to target a subdirectory, use paths
  relative to the repo root (e.g. `.venv/bin/pytest collection/backend/tests/`)
  or absolute paths.
- **Invoke venv binaries directly**: `.venv/bin/python`, `.venv/bin/pytest`,
  `.venv/bin/pip`. **Never** `source .venv/bin/activate && …`, never bare
  `python`/`pytest`/`pip`, never system `python3` (3.14 lacks paddle/torch
  wheels; the venv is Python 3.12).
- **No compound commands** (`&&`, `;`, `|` chains) unless every part is
  read-only. Permission matching works on command prefixes; chaining defeats it.
  Run steps as separate commands instead.
- **Backend runs via `./collection/run.sh`** (serves on :8000). Unit tests never
  need it; only task9 runs it.
- **No real inference in unit tests** — monkeypatch `engine.pipeline.run` (and per
  refinement 4, `engine.CandidateTracker`/`engine.FramesIndex` where appropriate).
  No model downloads in tests.
- **Atomic writes** for anything a reader may see mid-write: temp file +
  `os.replace` (`crossings.json`, `candidates.json`, `processed_offset`).
  Append-only for `manifest.jsonl`, `frames_index.jsonl`, `crossings.csv`;
  malformed JSONL lines are skipped on read, never fatal.
- **Front-end is a static site — no build step, no framework.** `results/*.js`
  are ES modules; pure logic gets brief inline self-checks (no test framework),
  runnable with `node` where a file has no DOM imports.
- **Timestamps** stay ISO-8601 strings on disk and over HTTP; comparisons go
  through the existing `_epoch_ms`/`_ts_seconds` style helpers; `order_key` is
  epoch-ms as float.
- **Contracts are frozen.** If a signature in `design.md` or a block above is
  genuinely wrong, STOP and flag it in your final report — never silently
  diverge; sibling agents code against the same contracts.
- Source of truth: `../requirements.md` and `../design.md` (this spec), plus
  your own `taskN.md`. Do not edit files owned by other tasks.

## Generated data
`runs/` (frames, manifests, crossings, candidates, frames-index, annotated images)
is generated output — already gitignored, never committed. Tests build their own
run dirs under `tmp_path`.
