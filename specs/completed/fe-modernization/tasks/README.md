# Tasks — FE Modernization (Toolchain, Tests, Preact)

The map for the parallel-agent run. **Read this before spawning any agent.** Source of
truth is `../requirements.md` + `../design.md`; this file adds the dependency graph,
execution waves, exclusive-file ownership, and the **frozen contracts** every task codes
against.

## Execution waves

| Wave | Tasks | Model | Gate |
|------|-------|-------|------|
| **A — Scaffold (blocking)** | task1 | sonnet | must land + `npm run check` green (no components yet) before Wave B starts |
| **B — Parallel** | task2 · task3 · task4 · task5 · task6 · task7 · task8 | sonnet (task2 haiku-ok) | each passes `npm run typecheck`; task2/task8 also `npm run unit` |
| **C — Integration** | task9 | sonnet | `npm run check` green + parity checklist + docs |

```
        task1  (scaffold: manifest, tsconfig, types.d.ts, vendor/, ALL stub files)
          │
   ┌──────┼──────┬──────┬──────┬──────┬──────┐
 task2  task3  task4  task5  task6  task7  task8      ← Wave B (exclusive file owners)
   └──────┴──────┴──────┴──────┴──────┴──────┘
          │
        task9  (mount, delete old, component test, parity, docs)
```

Wave B tasks **fill stubs task1 created** — each owns its file(s) exclusively and never
touches another task's file. Because task1 stubs every symbol, all imports resolve and
`tsc` is incremental from the start. task8 (`ResultsApp`) codes against the **frozen §9
child contracts**, not their implementations, so it is Wave-B-parallel-safe.

## Delegation protocol (per CLAUDE.md)

- Give each agent its `taskN.md` **plus** `requirements.md` + `design.md` as source of truth.
- **Contracts are frozen for this run.** An agent that believes a frozen signature is
  genuinely wrong must **stop and flag it**, never silently diverge — siblings depend on it.
- One wave at a time; **gate each wave on explicit human go-ahead**; commit + push a
  checkpoint between waves. Keep subagent scratch/artifacts out of commits.
- Every component imports Preact primitives from `../../vendor/preact-setup.js` (design §5)
  and annotates props via `import('../../types').XxxProps` (extension-less; design §13).

---

## FROZEN-1 · Data object shapes (`results/data.js` — UNCHANGED)

Every results component reads these fields; **do not rename or add fields**. Mirrored as
typedefs in `types.d.ts` (task1). Full JSDoc is in `results/data.js:14–56`.

```
Result           { time:Date, raceNumber:number, name:string|null, category:string,
                   matched:boolean, crossingId:string, annotatedUrl:string, source:"auto"|"manual",
                   edited:boolean, orderKey:number, orderOverridden:boolean,
                   isCandidate:false, numberText:string }        // numberText = number or "—"
CandidateResult  { isCandidate:true, candidateId:string, run:string, time:Date, lastSeen:Date,
                   frameCount:number, hintNumber:string|null, hintConf:number, imageUrl:string,
                   repBox:[number,number,number,number], orderKey:number, numberText:string,
                   category:"Unknown" }
Pack             { startTime:Date, results:Array<Result|CandidateResult> }   // groupIntoPacks
Lane             { category:string, index:number }                            // computeLanes (0-based)
```

`data.js` exports (all pure, tested by task2): `resultsFromCrossings`, `candidatesToResults`,
`sortByOrder`, `sortDescending`, `mergeCandidates`, `groupIntoPacks(results, gapSeconds)`,
`computeLanes(results, { laneOrder })`, `UNKNOWN_CATEGORY` (= `"Unknown"`).

## FROZEN-2 · The results view pipeline (`deriveView`, task8)

Verbatim port of today's `results.js` render pipeline (results.js:341–351), lifted to a
pure helper in `components/results/state.js`:

```js
function deriveView(crossings, candidates, candidatesVisible) {
  const base   = candidatesVisible ? mergeCandidates(crossings, candidates) : crossings;
  const sorted = sortByOrder(base);
  return {
    packs: groupIntoPacks(sorted, 3),               // 3-second gap window (frozen)
    lanes: computeLanes(sorted, { laneOrder: null }),
  };
}
```

## FROZEN-3 · Card DOM & CSS classes (parity — `results/render.js` is the reference)

Cards reproduce the **visible** structure of `render.js:155–281` exactly. Selection and
click wiring move to Preact props — the old `data-*` wiring attributes and the
imperative re-selection are **dropped** (that machinery is what FR13/SC5 delete). Keep
only the classes/structure below.

**Crossing card** (`Card`):
- root classes: `card card--selectable`, plus `card--unknown` when `!matched`, plus
  `card--selected` when selected. Grid column set via inline `style="grid-column:<column>"`.
- badges (in this order, before the number): `span.badge.badge--manual` "✚ manual" when
  `source==="manual"`; `span.badge.badge--edited` "✎ edited" when `edited`;
  `span.badge.badge--moved` "↕ moved" when `orderOverridden`.
- `span.card__number` → `#<raceNumber>`, or `# —` when `numberText === "—"`.
- `span.card__name` → `name`, or `"Unknown rider"` when unmatched.
- `span.card__meta` → `"<category> · <hh:mm:ss>"` (matched) or just `"<hh:mm:ss>"` (unknown).

**Candidate card** (`CandidateCard`): classes `card card--candidate card--selectable`
(+`card--selected`); `span.card__number` → `? <hintNumber>?` or `? unidentified`;
`span.card__meta` → `<hh:mm:ss>`. Column = `lanes.length || 1`.

**Column resolution** (done in `Pack`, passed to cards as `column`): for a crossing,
`laneByCategory.get(result.category).index + 1`, falling back to `lanes.length`; for a
candidate, `lanes.length || 1`. **Timeline root**: class `timeline`, inline
`style="--lane-count:<lanes.length>"`; one `div.lane-header[data-category]` per lane at
its column; empty state `p.timeline__empty` "No crossings yet — waiting for riders…".
**Gap separator** (`GapSeparator`): `div.gap-separator` spanning `grid-column:1 / -1`,
text = `formatGapLabel(pack.startTime)` (`hh:mm`).

`formatGapLabel` / `formatTimeOfDay` relocate from `render.js` into a **new pure module**
`components/results/format.js` (task3), tested per FR8.

## FROZEN-4 · State & Action shapes — `ResultsApp` (design §8)

Declared as `State` / `Action` typedefs in `types.d.ts` (task1); the reducer + initial
state live in `components/results/state.js` (task8). Shapes are **verbatim design §8** —
`runs, selectedRun, crossings, candidates, lastPayloadHash, packs, lanes,
candidatesVisible, selectedId, sidebar{open,item}, browser{open,anchorTs},
statusPayload, pollError`. Actions: `SET_RUNS, SELECT_RUN, POLL_RESULTS, POLL_STATUS,
TOGGLE_CANDIDATES, SELECT_ITEM, OPEN_SIDEBAR, CLOSE_SIDEBAR, OPEN_BROWSER,
CLOSE_BROWSER, POLL_ERROR`. `POLL_RESULTS` derives packs+lanes in-reducer (FROZEN-2);
identical `hash` ⇒ return the **same state object** (Preact bails the re-render — NFR2/SC5).

## FROZEN-5 · Component prop signatures (design §9)

Verbatim design §9. Each is a props `@typedef` in `types.d.ts` (task1). Owners:

| Component(s) | File | Owner |
|---|---|---|
| `Timeline`, `Pack`, `GapSeparator` | `components/results/Timeline.js` | task3 |
| `Card`, `CandidateCard` | `components/results/Card.js` | task3 |
| `formatGapLabel`, `formatTimeOfDay` | `components/results/format.js` | task3 |
| `Sidebar` | `components/results/Sidebar.js` | task4 |
| `FrameBrowser` | `components/results/FrameBrowser.js` | task4 |
| `setRosterOptions` (datalist helper) | `components/results/roster.js` | task4 |
| `StatusBar` | `components/results/StatusBar.js` | task5 |
| `RunSelector` | `components/results/RunSelector.js` | task5 |
| `CaptureApp` + `SourceSelector`, `CameraPreview`, `CaptureControls`, `RosterUpload` | `components/capture/*.js` | task6 |
| `api.js` | `api.js` | task7 |
| `ResultsApp`, reducer/`deriveView`/initial state | `components/results/ResultsApp.js`, `components/results/state.js` | task8 |

> **htm blind spot (design §9):** `tsc` checks each component's *own* prop usage but not
> props threaded through `` html`…` `` literals. Keep prop names byte-exact; the task9
> component test covers call-site wiring.

## FROZEN-6 · `api.js` surface (design §7)

Verbatim design §7 — the single fetch layer for **both** pages. Paths are the existing
wire contract (do not change). Functions are pure async (no DOM). Includes:
`fetchRuns, fetchResults, fetchCandidates, fetchStatus, fetchFrames, fetchRoster,
postEdit, deleteEdit, postManualCrossing, reorderCrossing({earlierId,laterId}),
promoteCandidate, dismissCandidate, checkHealth, postFrame, uploadRoster, frameUrl`.

## FROZEN-7 · `config.js` (UNCHANGED, read-only)

Components read `window.COLLECTION_CONFIG` — keys: `BACKEND_URL, CAPTURE_FPS,
JPEG_QUALITY, TARGET_WIDTH, MAX_IN_FLIGHT, RESULTS_POLL_MS, DEFAULT_SOURCE,
FRAMES_SPAN_S, FRAMES_LIMIT`. Do not rename/remove. `config.js` stays a classic script.

## FROZEN-8 · `#roster-numbers` datalist (design OQ-D2)

A **shared static** `<datalist id="roster-numbers">` in the `index.html` shell (already
present). Both `Sidebar` and `FrameBrowser` bind number inputs via `list="roster-numbers"`.
The **open** overlay populates its `<option>`s through `setRosterOptions(run)`
(task4, `components/results/roster.js`), which calls `api.fetchRoster(run)` then writes
options to the shared node. Not component-owned state — do not move the datalist into a
component's render output.

## FROZEN-9 · Capture behaviors & OQ-D3 (design §9, OQ-D3)

Parity source is `app.js`. Behaviors to preserve (A4): source selector (camera|video),
live camera preview, video-file ingest, capture start/stop with in-flight/frame counters,
roster upload + status. **OQ-D3 resolved:** `CameraPreview` **owns** `getUserMedia` in a
`useEffect` keyed on its `active` prop (matches the §9 note "manages its own stream ref
internally") and tears the stream down on `active=false`/unmount; `CaptureApp` only owns
recording/inflight/source state. Capture fetches go through `api.js` (`checkHealth`,
`postFrame`, `uploadRoster`). `CaptureApp`'s internal reducer shape is **not** frozen.

## Shared conventions

- **No edits to** `results/data.js`, `config.js`, `styles.css`, or anything under
  `../backend/` during Wave B. Reuse existing CSS classes (FROZEN-2/3) for parity; if a
  component genuinely needs a new class, **flag it to task9** rather than editing
  `styles.css` (avoids a shared-file conflict). The old modules (`app.js`, `results/*.js`
  except `data.js`) are **never edited** — only replaced, then deleted by task9.
- Every new component must pass `npm run typecheck` against `types.d.ts` before its task
  is done. task2 & task8 additionally add passing `node --test` suites.

---


