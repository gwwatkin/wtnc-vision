# Requirements — Live Pipeline: Collection → Processing → Live Results

## 1. Background & Purpose

Three pieces exist today, built to frozen contracts but never wired together:

- **Collection app** (`specs/completed/collection/`, `collection/`) — a browser front-end
  that streams device-camera frames to a local FastAPI back-end, which **writes each frame
  to disk** with a timestamped filename and an append-only `manifest.jsonl`. It does **no
  computer vision** — it only stores frames.
- **CV pipeline** (`specs/completed/poc/`, `src/rider_id/`) — `pipeline.run(image_bgr, cfg)`
  takes **one** BGR still and returns `list[CrossingResult]` (`number`, `raw_text`,
  `confidence`, `status`, `rider_box`, `crop_path`). It has no notion of time and no video
  loop.
- **Results viewer** (`specs/completed/results-ux/`, `web/`) — a static timeline that polls
  a crossings CSV (`time,race_number`) + a roster CSV, merges them, groups crossings into
  time-gap "packs," and renders them newest-first in per-category lanes.

The collection app's own design already anticipates this step ("Live processing… the
back-end feeds each received frame into the CV pipeline… as a second sink"). This feature
**closes the loop**: as frames are collected, the pipeline processes them and the results
appear **live** on the same page as the camera, and any result can be opened to see the
frame it came from.

This document is *what & why* only. Technology choices belong in `design.md`.

## 2. Goals

- **G1** — Present the **camera/capture view and the results timeline on one page**, with
  the timeline **below** the camera view, so an operator sees captures and their recognized
  numbers together.
- **G2** — As frames are collected, **run the CV pipeline asynchronously** over them
  without blocking capture or storage.
- **G3** — **Live-update** the results timeline as the pipeline finishes each frame — new
  crossings appear without a manual reload.
- **G4** — Let a user **open any result to see the frame that produced it** — an annotated
  full frame (rider box + recognized number drawn on it) — in a **sidebar** beside the
  timeline.
- **G5** — Reuse the existing pieces (collection back-end, `pipeline.run`, viewer render
  logic) rather than rebuilding them; connect, don't rewrite.

## 3. Resolved Product Decisions

Baked into the requirements below (confirmed with the operator):

- **D1 — Layout.** Camera view on top, results timeline **below** it, one page (G1).
- **D2 — Detail view = sidebar.** Opening a result slides in a **sidebar** beside the
  timeline (timeline stays visible); not a modal overlay (G4, FR-DETAIL).
- **D3 — Detail image = annotated frame.** The sidebar shows the **full frame with the
  rider box and number label drawn on it** (reuses `io_out.write_annotated_image`), not
  just the number crop.
- **D4 — Result identity = deduplicated crossings.** A rider crossing at the capture rate
  produces the same number in many consecutive frames. Repeated **confident** reads of the
  same number within a time window collapse into **one crossing** in the timeline.
- **D5 — Throughput = queue every frame.** Every collected frame is processed **in order**
  through the pipeline. Completeness is preferred over liveness: during a fast burst the
  processing queue may **lag** capture and drain after the burst ends. The loop must stay
  bounded and never drop frames silently (see NFR3).
- **D6 — One uploaded roster per run, used for both validation and viewing.** The operator
  **uploads a roster from the page** (a button) **for a run**. That run's roster is the source
  of truth for **both** the pipeline's number validation **and** the timeline's name/category
  enrichment on that run — no separate `roster.txt` vs viewer CSV. Resolves OQ1. (Scoped
  per-run by D9.)
- **D7 — Two frame sources, chosen from the UX.** Frames come from either the **live device
  camera** (as today) **or** a **pre-recorded video file** the operator supplies from the
  page. Both feed the **same** processing sink, dedup, and timeline; the choice is a UX
  control. Resolves OQ4.
- **D8 — Crossings are persisted to disk as they are produced.** Each crossing is written
  to disk the moment the pipeline finishes it (not only held in memory), so results survive
  a back-end restart and can also feed the standalone viewer. Resolves OQ7.
- **D9 — A run = one capture label; all its inputs and outputs are co-located.** The operator's
  capture **label** is the **run** identity. Every input and output for that label — collected
  frames, manifest, that run's roster, its crossings log, and its annotated frames — lives under
  a single `run/<label>/` directory (design §5). Runs are **isolated**: roster, dedup, and the
  timeline are all scoped to one run. The timeline shows the **active** run (the current capture
  label), with a selector to view past runs. This **supersedes** the earlier framing of a single
  session-wide roster (D6/A3) and re-scopes crossing dedup (D4) and persistence (D8) to per-run.

## 4. Data Flow & Key Facts

```
[operator] → upload roster (button) ─────────────────────────┐  (number,name,category)
                                                              ▼
  live camera ─┐                                          [back-end] ── roster used for BOTH:
  video file  ─┼→ [collection front-end] → POST /frames →    ├── sink 1: write frame to disk + manifest  (exists)
  (source chosen in UX — D7)                                 └── sink 2: enqueue frame → PIPELINE (this feature)
                                                                    pipeline.run(frame) per frame
                                                                    → validate number against roster  ◄─┐
                                                                    → filter to confident reads         │ same
                                                                    → dedup into crossings (D4)          │ roster
                                                                    → persist crossing to disk (D8)      │
[browser page]  camera/source view (top) + results timeline (below, live) ──poll──┘  ── name/category ◄──┘
                click a result → sidebar shows that crossing's annotated frame
```

- **A1 — Capture time is the crossing time.** Each collected frame already carries a
  capture timestamp (`client_ts`) in the manifest. That timestamp is the crossing's `time`
  in the viewer's model — the pipeline itself produces no time (POC A: still-image only).
- **A2 — The race number comes from OCR, not the collection label.** The operator's
  free-text **label** (e.g. `lap3-nearside`) organizes collected frames; it is **not** the
  race number. The timeline's `race_number` is the pipeline's validated `number`.
- **A3 — One roster of record per run, uploaded from the page (D6, D9).** The operator uploads
  a roster (`number,name,category`) via a button **for a run**. Its **number** column is the
  valid-number set the pipeline validates that run's frames against; its **name/category**
  columns enrich that run's timeline. This replaces both today's pipeline `roster.txt` and the
  viewer's `web/data/roster.csv` as separate sources. A number present in the run's roster is
  both accepted and nameable; a recognized number **absent** from it falls under the viewer's
  existing "unknown rider" treatment (results-ux FR5).
- **A4 — Single device, single operator, local-only.** Inherits the collection app's stance
  (`localhost`, two-or-fewer ports, no auth, no external network at runtime).
- **A5 — Frames are pipeline-ready as stored.** A collected frame decodes with `cv2.imread`
  to the BGR array `pipeline.run` expects (collection NFR1) — no conversion needed.
- **A6 — Volume is one race/session** (hundreds of crossings, thousands of frames), on a
  CPU-only laptop.

## 5. Functional Requirements

### 5.1 Unified page & live results
- **FR1** — A single page shows the **camera/capture controls on top** and the **results
  timeline directly below** (D1). The existing collection capture UX (preview, camera
  select, label, start/stop, status) is preserved.
- **FR2** — The timeline **live-updates** as the pipeline produces crossings — new
  crossings appear without a manual page reload (G3).
- **FR3** — The timeline reuses the existing viewer's presentation model: newest-first,
  time-gap packs, per-category lanes, name/number/time-of-day/category per row, and the
  "unknown rider" treatment for numbers with no roster match (results-ux FR2–FR8).
- **FR4** — Live updating must not disrupt the operator: it must not steal scroll position,
  reset the capture controls, or block the camera preview.
- **FR4a** — The operator can choose the **frame source from the page**: the **live camera**
  (default) or a **pre-recorded video file** they supply (D7). Both sources feed the same
  processing sink, dedup, timeline, and sidebar; switching source does not require a
  back-end restart. The video's frames carry a capture time (derived from the source) so
  they order on the same timeline (A1).

### 5.2 Asynchronous processing
- **FR5** — When the back-end accepts a frame, it must **hand that frame to the pipeline
  asynchronously** as a second sink, **without blocking or slowing** the disk/manifest sink
  or the HTTP response to the capturing client (G2, G5).
- **FR6** — Every accepted frame is processed **in order, exactly once** (D5, queue). No
  frame is silently skipped; a frame that fails to process is logged and the loop continues
  (does not stall the queue).
- **FR7** — Processing runs `pipeline.run` on each frame and keeps only reads with
  status **`confident`**. Lower-confidence (`needs_review`) and `rejected` reads do **not**
  create crossings in this phase (see OQ3).
- **FR8** — The back-end exposes the produced crossings to the front-end in the shape the
  viewer consumes (time-ordered crossings enrichable by roster), so the timeline can render
  them (G3, G5).
- **FR8a** — Each crossing is **written to disk as it is produced** (D8), append-safe like
  the frame manifest, so results survive a back-end restart and can also be read by the
  standalone viewer. The corresponding annotated frame (FR15) is persisted alongside it.

### 5.3 Crossing deduplication
- **FR9** — Repeated **confident** reads of the **same number** within a configurable time
  window collapse into a **single crossing** (D4). The crossing carries one representative
  time and one representative annotated frame.
- **FR10** — Distinct numbers, or the same number seen again **after** the window, are
  **separate crossings** (a rider on a later lap is a new crossing).
- **FR11** — The dedup window is **configurable** without code edits.

### 5.4 Result detail sidebar
- **FR12** — Each timeline result is **selectable**; selecting it opens a **sidebar** beside
  the timeline (D2) — the timeline remains visible.
- **FR13** — The sidebar shows the crossing's **annotated frame** (full frame with rider box
  + recognized number drawn, per D3) alongside the crossing's number, name, category, and
  time.
- **FR14** — The sidebar is **dismissable** and selecting a different result **replaces** its
  contents (no stacking).
- **FR15** — The back-end must **serve the annotated frame image** for each crossing so the
  sidebar can display it.

### 5.5 Roster upload
- **FR16** — The page provides a **button to upload a roster** (`number,name,category`
  rows). No manual file placement or back-end restart is required to set the roster.
- **FR17** — An uploaded roster becomes the **single source used for both** pipeline
  number **validation** and timeline name/category **enrichment for its run** (D6, D9). A
  number in the run's roster is accepted by validation and nameable in that run's timeline.
- **FR18** — A run's active roster is **replaceable**: uploading a new roster for a run
  supersedes the previous one for **that run's subsequently processed frames only**.
  Already-produced crossings are **not** retroactively re-validated or re-named (OQ8).
- **FR19** — Invalid or malformed roster uploads are **rejected with a clear message**,
  leaving the previously active roster in place; the app does not crash or lose state.
- **FR20** — Until a roster is uploaded, the app must **degrade gracefully**: either use a
  documented default/empty roster or clearly prompt for one — capture and storage still
  work, and recognized numbers show under the "unknown rider" treatment (design to specify).

### 5.6 Configuration
- **FR21** — Whether live processing is **enabled**, the **dedup window**, and the
  **confidence policy** (which statuses become crossings) are configurable without editing
  application logic — consistent with the collection back-end's config approach.

## 6. Non-Functional Requirements

- **NFR1 (Reuse)** — Reuse `pipeline.run`, the collection back-end/front-end, and the
  viewer's render/data modules unchanged where possible; new code is the glue (queue,
  dedup, results endpoint, layout, sidebar) — not reimplementations (G5).
- **NFR2 (Non-blocking capture)** — The capture→store path keeps its current latency and
  backpressure behavior; adding the pipeline sink must not slow frame acceptance or freeze
  the UI (collection NFR2/NFR3).
- **NFR3 (Bounded, ordered queue)** — Processing is a bounded, in-order queue: it may lag
  during bursts and drain afterward, but must not grow unbounded, deadlock, or drop frames
  silently (D5).
- **NFR4 (Local-only / no auth)** — Runs entirely on `localhost`, no auth, no external
  network dependency at runtime (collection NFR5).
- **NFR5 (Live-friendly render)** — Live updates are incremental and cheap enough to run at
  the viewer's existing poll cadence without visible jank on a laptop for one session's
  volume (A6).
- **NFR6 (Graceful degradation)** — If the pipeline is disabled, slow, or errors on a frame,
  the collection app still captures and stores frames, and the page still loads; the
  timeline simply shows what has been processed so far.
- **NFR7 (CPU-only / offline)** — No GPU and no paid services; model pulls only on first run
  (inherits POC/collection constraints).

## 7. Scope

### 7.1 This phase
- One page combining the existing camera capture UI (top) and results timeline (below),
  **consolidated into the collection app** (single app; may be renamed later — OQ6).
- A frame-source selector in the UX: **live camera or a supplied pre-recorded video file**,
  both feeding the same processing path (D7).
- A second, asynchronous pipeline sink in the collection back-end that processes every
  frame in order.
- Dedup of confident reads into crossings, **persisted to disk as produced** (D8), exposed
  to the front-end and live-rendered.
- A sidebar that shows a selected crossing's annotated frame.
- A roster-upload button whose roster is the single source for both validation and viewing.

### 7.2 Out of scope (captured for context)
- Real-time tracking across frames (multi-object tracking / trajectories); dedup here is a
  time-window heuristic, not a tracker.
- Editing/correcting recognized numbers or roster data in the UI.
- Showing `needs_review` reads in the timeline or a human-review/correction workflow (OQ3).
- Lap counting, placings, elapsed/race time, standings (already out of scope in results-ux).
- Multi-device/remote capture, auth, TLS, cloud upload (out of scope in collection).
- Advanced video handling beyond feeding frames through the pipeline: scrubbing/seek UI,
  audio, timestamp extraction from container metadata, or batch re-processing of a library
  of videos. Video-file **ingest** is in scope (D7); a video *editor* is not.
- GPU acceleration or model swaps to hit real-time throughput (D5 accepts lag instead).

## 8. Success Criteria

- **SC1** — Opening the app shows the **camera capture UI on top and an (initially empty)
  results timeline below** on one page (FR1).
- **SC2** — Recording a rider whose number the pipeline reads confidently makes **one
  crossing** appear in the timeline **without a reload**, with the correct number and (if
  rostered) name/category and capture time-of-day (FR2, FR3, FR7, FR9; A1, A2).
- **SC3** — A rider held in frame across many capture frames yields **a single crossing**,
  not one per frame (FR9); the same number seen again after the window yields a **second**
  crossing (FR10).
- **SC4** — Clicking that crossing opens a **sidebar** showing the **annotated frame** (box
  + number drawn) for it, with the timeline still visible; clicking another result replaces
  the sidebar contents; dismissing closes it (FR12–FR14, D2, D3).
- **SC5** — During a fast burst the timeline **catches up after** capture stops (queue
  drains) with **no frames skipped** and capture never freezes (FR5, FR6, NFR2, NFR3).
- **SC6** — With live processing **disabled** in config, the app still captures and stores
  frames exactly as the collection app does today, and the page still loads (FR21, NFR6).
- **SC7** — Uploading a roster **for a run** from the page makes its numbers **validate** in
  the pipeline and its names/categories **appear** on matching crossings in that run's timeline,
  with no file placement or back-end restart; a malformed roster is rejected and the run's prior
  roster stays active (FR16–FR19, D6, D9).
- **SC8** — Selecting a **pre-recorded video file** as the source produces crossings on the
  same timeline as the live camera would, via the same pipeline (FR4a, D7).
- **SC9** — Produced crossings are **on disk as they appear** (not only in memory), so
  restarting the back-end and reloading the page still shows them, and the standalone viewer
  can read them (FR8a, D8).

## 9. Open Questions

- **OQ1 — Roster reconciliation.** ✅ **Resolved (D6, D9).** One roster **per run** is
  **uploaded from the page** (`number,name,category`) and is that run's single source for both
  pipeline validation and timeline naming (FR16–FR20). *Follow-up for design:* when a **new roster is uploaded
  mid-session**, do already-produced crossings get **re-enriched/re-validated**, or does the
  new roster apply only to frames processed afterward (FR18)? *Propose apply-going-forward,
  re-enrich names on next render; decide at design.*
- **OQ2 — Representative frame for a deduped crossing.** ✅ **Resolved** — the sidebar shows
  the **highest-OCR-confidence** frame among the N that collapsed into the crossing (FR9,
  FR13).
- **OQ3 — `needs_review` reads.** ✅ **Resolved** — **not displayed** this phase (FR7).
  Surfacing them (with a distinct treatment / correction workflow) stays deferred.
- **OQ4 — Video-file ingest.** ✅ **Resolved — in scope (D7).** The UX offers a
  pre-recorded video file as an alternative frame source, feeding the same pipeline sink
  (FR4a). Advanced video handling remains out of scope (§7.2). *For design:* how frames are
  extracted (front-end vs back-end) and how each frame's capture time is derived.
- **OQ5 — Transport of live results.** ✅ **Resolved** — keep the viewer's existing
  **polling** model (front-end polls a results endpoint/file). Push (SSE/websocket) stays a
  later option.
- **OQ6 — Serving & consolidation.** ✅ **Directionally resolved** — **consolidate into the
  collection app** as a single served page (rename later if warranted). *For design:* exact
  serving shape (back-end serves the page vs static front-end calling it) and port layout.
- **OQ7 — Persistence of crossings.** ✅ **Resolved (D8)** — crossings are **written to disk
  as produced** (FR8a), append-safe alongside the frame manifest, surviving restart and
  readable by the standalone viewer. *For design:* exact on-disk format/location.
- **OQ8 — Mid-session roster replacement (from OQ1 follow-up).** ✅ **Resolved** — a new
  roster **for a run applies going forward**: it validates/enriches that run's frames processed
  **after** upload. Already-produced crossings are **not** retroactively re-validated or
  re-named (FR18, D9).
