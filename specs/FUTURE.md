# Future Work

Ideas extracted from the completed specs (`completed/poc/`, `completed/collection/`,
`completed/results-ux/`) and the in-progress one (`live-pipeline/`). Each item cites
where it came from. These are candidates, not commitments — pull one into its own
`requirements.md` when it's time to build it.

Note: the collection spec's biggest "later phase" — live processing of collected
frames — is **not** listed here because it *is* the `live-pipeline` spec.

---

## 1. CV accuracy & models

- **Custom-trained models on our own footage.** The POC deliberately uses pretrained
  models only ("custom training is a later optimization, not a prerequisite" — POC
  design §1). The collection app now produces a labeled dataset; fine-tuning the
  detector and/or OCR on real finish-line frames is the natural next accuracy step.
- **Set the accuracy target.** POC OQ1 is still open: which % of crossings must be
  auto-captured before human review is acceptable. Needs a baseline measured on real
  collected sessions first.
- **Model upsizing.** Start-small policy (`yolov8n`) with an explicit path to
  `s`/`m`/`l` weights if accuracy requires and the laptop keeps up (POC design §7, §11).
- **OCR engine swap.** `ocr.py` is a swappable boundary; drop in EasyOCR if PaddleOCR
  underperforms on real footage (POC design §2, D3).
- **Multi-frame voting.** The POC needs only one good frame per rider (A3); combining
  OCR reads across a crossing's many frames (beyond live-pipeline's keep-best-confidence
  dedup) could raise accuracy on marginal panels.
- **GPU acceleration / real-time throughput.** Explicitly deferred everywhere
  (POC NFR3, live-pipeline §7.2): CPU-only with lag-and-drain is accepted today; GPU or
  faster models become relevant if live results must keep up with capture.

## 2. Tracking & the full video system

- **Real multi-object tracking.** Replace live-pipeline's time-window dedup heuristic
  with ByteTrack (or similar) stable per-rider IDs — the original POC design §6 plan.
  The design notes `_fold` can be swapped for a tracker without touching the HTTP/disk
  contracts (live-pipeline §9).
- **Virtual finish line & crossing direction.** POC FR9–FR10: a configured line/zone
  with a real crossing *event* (e.g. supervision `LineZone`) instead of "a confident
  read appeared."
- **Lap counting.** POC FR11–FR12: per-rider lap counts keyed by validated number,
  emitted on each crossing. Deliberately out of scope in results-ux and live-pipeline,
  but a core full-system requirement.
- **Unreadable-crossing events.** POC FR13: a rider whose number can't be read on a
  lap should still emit an "unknown / needs review" crossing rather than vanish.
  Live-pipeline currently drops non-confident reads entirely (FR7).

## 3. Human review & correction workflow

- **Surface `needs_review` reads.** Deferred in live-pipeline OQ3. The engine already
  computes them; showing them is a `statuses` config addition plus a distinct card
  treatment (live-pipeline §9), and it's the prerequisite for the review-first accuracy
  philosophy (POC G3/NFR1) to work end-to-end.
- **Correction UI.** Editing/correcting recognized numbers and roster data in the UI is
  out of scope in both results-ux §3.2 and live-pipeline §7.2. A minimal version:
  confirm/fix a flagged crossing from its annotated frame in the sidebar.
- **Dataset review/annotation UI.** A gallery over `collected/` with label corrections
  (collection §3.2) — useful both for dataset curation and for building the custom
  training set (§1).

## 4. Results & timeline UX

- **Push updates (SSE/websocket).** Both the viewer and live-pipeline keep polling by
  decision (results-ux OQ1, live-pipeline OQ5), each noting push is a later swap behind
  the same `refresh()` / render entry point.
- **Richer results on cards.** Laps, elapsed/race time, placings, category standings —
  results-ux design §9 sizes this as "add fields to `Result` + card markup; transforms
  and lane logic unchanged."
- **Colour-coded lanes.** Per-category accent colour exists but is off by default
  (results-ux OQ3/design §1); one styling switch to enable.
- **Pixel-proportional timeline spacing.** Vertical distance ∝ elapsed time instead of
  ordinal rows — named a "future enhancement" in results-ux design §7.
- **Tune the gap threshold.** results-ux OQ4: is the 3 s pack separator right once real
  crossing data exists?
- **Results publishing/export & multi-race management.** Out of scope in results-ux
  §3.2; `crossings.csv` is already the portable export seed (live-pipeline §5).

## 5. Capture & dataset

- **Encoded video-clip recording.** Record `.mp4`/`.webm` clips instead of (or beside)
  JPEG bursts if temporal fidelity demands it (collection §3.2, OQ1).
- **Tune capture rate & image size.** Collection OQ5: confirm the default fps/quality/
  resolution against real session volume and disk.
- **Advanced video-file handling.** Live-pipeline §7.2 defers scrubbing/seek UI,
  timestamp extraction from container metadata, and batch re-processing of a video
  library; the last is the most useful — re-run an improved pipeline over old footage.
- **Dataset hygiene.** Deduplication, compression tuning, cloud upload/backup of the
  collected dataset (collection §7).

## 6. Deployment & platform

- **Multi-device / remote capture.** A phone at the line streaming to a laptop
  elsewhere — needs transport security and auth, all currently excluded (collection
  §3.2, live-pipeline §7.2).
- **AGPL exit for distribution.** If the app is ever handed to third parties, swap
  Ultralytics YOLO for YOLOX (Apache-2.0) or buy a commercial license; the `detector`
  module boundary exists for exactly this (POC LR2, design §2).
- **Worker parallelism.** Live-pipeline §9: a bounded worker pool with per-number
  affinity could parallelise inference if CPU allows, keeping dedup correct per number.

## 7. Results adjudication: bunches, arrival order & durable annotations

The layer that turns raw per-frame crossings into an **official, ordered, human-trusted
result**. Today a crossing is a CV artefact (`live-pipeline` §6 `Crossing`) with no
notion of bunches, no authoritative order, and no record of operator judgement. These
three ideas are one theme — a human-in-the-loop adjudication pass over the timeline — and
are best built together.

- **Bunch grouping (shared-time packs).** In road racing, riders finishing together are a
  *bunch* awarded a **shared time** (the front-of-bunch time) while keeping individual
  placings. This is distinct from results-ux's **visual** "packs" (a 3 s gap separator for
  display only — results-ux design §7, OQ4): a bunch is a **timing/results** construct with
  a canonical time and boundaries. Seed it from the same gap heuristic, then let the
  operator split/merge bunch boundaries and pick the bunch time. Reuses `crossings.csv`'s
  `time` column as the per-rider raw time and adds a resolved bunch time beside it.
- **Arrival order resolution.** Establish the **sequence** riders crossed, especially
  within a bunch where capture timestamps (~fps-limited, `client_ts`) and confident-read
  timing are too coarse to trust. This is **not** automated photo-finish precision — that
  stays rejected below (POC A6). It's an **operator-assisted** reorder: the sidebar's
  annotated frames (live-pipeline D3/FR13) let a human drag crossings into the right order,
  with near-simultaneous ties flagged for that review. The resolution mechanism *is* the
  human, which is exactly what the rejected photo-finish item defers to.
- **Persistence of human annotations.** The durable backbone that makes the two above (and
  §3's correction UI) real: every operator decision — a corrected number, a confirmed or
  dismissed crossing, a manual reorder, a bunch assignment, a free-text note — is written
  to disk as an **append-only annotation/audit log** and reflected in the authoritative
  `crossings.json` (live-pipeline §5, already atomic-rewrite + restart-loaded). Two
  invariants: annotations **survive restart** (like crossings do, D8), and they **win over
  CV** — re-processing a frame or uploading a new roster (OQ8) must **never silently
  overwrite** a human decision. This closes the loop on the review-first accuracy
  philosophy (POC G3/NFR1): human effort spent correcting results is never lost.

Sequencing note: **annotation persistence is the foundation** — build it first (extend the
crossing store with an annotation log + "human-locked" flag), then layer bunch grouping and
arrival-order resolution as UI + resolved-fields on top. Pairs naturally with §3's
correction UI and §4's richer cards (placings/standings).

---

## Deliberately rejected (don't resurrect without new evidence)

- Transponder/RFID hardware timing; identity beyond the printed number (face
  recognition) — POC §8.
- Precise **automated** photo-finish ordering of near-simultaneous crossings — timing
  tolerance is a product assumption (POC A6); contentious ties go to human review. Note the
  human-assisted arrival-order resolution in §7 is the sanctioned path for those ties — it's
  operator judgement, not sub-frame CV precision, so it does not resurrect this item.
- A second standalone viewer — `web/` is absorbed into `collection/frontend/results/`
  and deleted by the live-pipeline spec; future viewer work has one home.
