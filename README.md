# WTNC Vision

A computer-vision system that detects cyclists crossing a finish line and reads the
back-number printed on their jersey — with a live browser UI for capturing frames and
viewing results as they are produced.

## Requirements

- A laptop that can build this project (tested on Linux, but Mac and WSL should work).
  - **Python 3.12** (the ML wheels — PaddlePaddle, Ultralytics — require Python ≤ 3.12; do **not** use system Python 3.14+)
  - Linux (tested on Arch Linux); macOS should work with the same steps. Perhaps WSL too
  - Internet access for installation and first run (YOLO and PaddleOCR models are auto-downloaded; subsequent runs use the cache)

---

## Setup

```bash
# 1. Create and activate a Python 3.12 virtual environment
/usr/bin/python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r collection/backend/requirements.txt
```

> If you see a `ccache` warning from PaddlePaddle, it is harmless — the pipeline runs without it.

---

## Live Pipeline (Camera → CV → Results)

The main workflow is a single page that captures frames from your camera (or a
pre-recorded video file) and displays recognized rider numbers live as the CV
pipeline processes them.

```bash
./collection/run.sh
# Open http://localhost:8000
```

On first run, YOLO (`yolov8n.pt`) and PaddleOCR (`PP-OCRv6`) models are downloaded
automatically (~100 MB total). Subsequent runs are fast.

### Workflow

1. **(Optional)** Upload a roster CSV (`number,name,category` rows) using the button
   on the page — rider names and categories appear in the timeline.
2. Set a **label** (e.g. `lap3-nearside`) — this is the *run* name.
3. Choose a **source** — *Camera* or *Video file*.
4. **Start** capturing. Frames stream to disk and are processed asynchronously.
   Crossings appear in the timeline below the camera view as they are detected.
5. Click a crossing card to open a **sidebar** with the annotated frame (bounding box
   + recognized number drawn). Replace by clicking another card; close with ×.
6. Use the **View run** selector to browse past runs.

### Review & Editing

The timeline and sidebar support full operator review and correction of the crossing
record. All edits persist to disk immediately and survive back-end restarts.

**Frame browser (FR1–FR4)**

Click **Browse frames** (in the run controls) or **View frames** from any crossing or
candidate sidebar to open the frame browser inside the sidebar. Use the scrubber to
jump to any point in the run's timeline; the filmstrip shows thumbnails with `←`/`→`
keyboard stepping. Each frame displays the pipeline's outcome when available: rider
bounding boxes colored by status (green = confident, amber = needs_review, red =
rejected). Frames not yet processed show "no outcome data".

**Manual crossing creation (FR5–FR7)**

In the frame browser, click **Add crossing here** below the main frame view, enter a
race number (or leave blank for unidentified), and confirm. The crossing appears in the
timeline with a `✚ manual` provenance badge.

**Editing and deleting crossings (FR8)**

Opening a crossing in the sidebar reveals:
- **Edit number** — type a new number (roster autocomplete available) and save.
  Automatic crossings that are edited gain a `✎ edited` badge.
- **Move earlier / Move later** — reorder the crossing relative to its neighbours in
  the order of record. The crossing gains a `↕ moved` badge and keeps it across
  restarts. New automatic crossings arriving later slot in by capture time without
  disturbing manual overrides.
- **Delete** — soft-deletes the crossing (confirms first). The record stays on disk;
  the timeline hides it.

**Candidate crossings (FR12–FR15)**

Riders that the pipeline detected but could not read confidently are automatically
grouped into *candidate crossings*. These appear inline in the timeline with a dashed
border and a `? unidentified` (or `? 128?` when a number was partially read) label.
Toggle their visibility with **Show candidates** in the run controls.

Opening a candidate shows the representative frame with the detected rider box, the
pipeline's hint number (if any), and two actions:
- **Promote** — assign a number and add it to the timeline as a manual crossing.
- **Dismiss** — mark as noise / duplicate; it disappears from the active view.

Candidates that overlap a confident crossing in time are automatically *suppressed*
(FR15) and not shown to the operator.

**Queue / processing status (FR16–FR19)**

Below the recording status line, a queue readout shows:

```
● Queue: 412 captured · 280 processed · 132 pending — processing…
                results current to 14:32:07
```

or, when fully caught up:

```
● Queue: 412 captured · all processed — ✓ up to date
```

The amber dot pulses while the backlog drains; it turns green when up to date. This
reflects live capture as well as reopened past runs.

### On-disk layout

All data lives under `runs/` (gitignored):

```
runs/
  <safe_label>/                    # one directory per run/label
    collected/*.jpg                # stored frames
    manifest.jsonl                 # append-only frame index (the worker queue)
    processed_offset               # worker resume point
    crossings.csv                  # append-only: time,number per crossing
    crossings.json                 # rich crossing state (served by GET /results)
    annotated/<crossing_id>.jpg    # annotated representative frame per crossing
    roster.csv                     # uploaded roster: number,name,category (also
                                   # read by the CV pipeline for validation)
```

### On-disk layout (additions)

The review feature adds two new per-run files:

```
runs/
  <safe_label>/
    ...                              # existing files unchanged
    frames_index.jsonl               # NEW: per-processed-frame outcome log
    candidates.json                  # NEW: grouped candidate crossings (all states)
```

Old runs (processed before this feature) have no `frames_index.jsonl`; frame browsing
still works for them (raw frames served, outcome overlay shows "no data"). Candidates
are going-forward only.

### Configuration

`collection/backend/config.yaml` — key live-pipeline settings:

| key | default | meaning |
|---|---|---|
| `live.enabled` | `true` | `false` → pure frame storage, no CV |
| `live.dedup_window_s` | `5.0` | seconds within which same number = one crossing |
| `live.cv_config` | `../../config.yaml` | repo POC pipeline config |
| `live.candidates.enabled` | `true` | `false` → candidate tracker inert (frame index still written) |
| `live.candidates.statuses` | `[needs_review, rejected]` | which per-frame statuses feed candidates |
| `live.candidates.window_s` | (inherits `dedup_window_s`) | grouping window in seconds; absent → use `dedup_window_s` |
| `live.candidates.min_det_conf` | `0.5` | ignore YOLO boxes below this detection confidence (noise floor) |
| `live.frames_index.enabled` | `true` | `false` → no per-frame outcome retention; frame browser degrades to raw frames |

See `collection/README.md` for full configuration reference.

---

## Single-image POC

To run the CV pipeline on a single still image (original proof of concept):

```bash
source .venv/bin/activate
python run_poc.py ridersFromThBack.jpg
```

Output appears in `out/`:

```
out/
  results.json        # number, confidence, status, bounding box, crop path
  annotated.jpg       # image with rider boxes and recognized numbers
  crops/101_0.jpg     # cropped number-panel for each confident read
```

See `EVALUATION.md` for the full baseline assessment (the sample image reads `101`
at 0.997 confidence).

### Adjusting config.yaml

All tunable parameters live in `config.yaml`. This file is shared: it drives both the
single-image POC and the live pipeline (which points at it via `live.cv_config` in
`collection/backend/config.yaml`), so changes here affect both.

**Detection — whether a rider is found at all (`detector:`)**

- **`detector.person_conf`** — minimum YOLO confidence for a `person` box (default
  `0.35`). **Lower it** (e.g. `0.25`) to recover distant, blurred, or partially
  occluded riders; the cost is more spurious boxes, which are usually filtered out
  later when OCR finds no number. This is the biggest lever for missed riders.
- **`detector.weights`** — the YOLO model file (default `yolov8n.pt`, the *nano*
  model — fastest, least accurate). Swapping to `yolov8s.pt` or `yolov8m.pt` improves
  recall on small/blurry riders at the cost of CPU speed (`m` is several× slower per
  frame, which matters for keeping up with the live stream). The file auto-downloads
  on first use.

**Recognition — whether a found rider becomes a result**

- **`locate.back_band`** — vertical fraction of the rider box where the number panel
  sits (`[0.20, 0.55]` = skip top 20%, crop to 55%). If your camera angle or number
  placement differs from the tuned sample, the panel can fall outside this band and
  OCR sees nothing — widen it (e.g. `[0.15, 0.65]`).
- **`score.confidence_threshold`** — reads below this → `needs_review` instead of
  `confident` (default `0.60`). In the live pipeline only `confident` reads open a
  crossing (`live.statuses` in `collection/backend/config.yaml`); lower this to surface
  more riders, at the cost of noisier reads.
- **`validate.roster`** — path to the roster file: either plain numbers (one per
  line) or a `number,name,category` CSV (first column used, header tolerated).

> **Missing riders?** There are two distinct failure points. Pick a frame where a
> rider was dropped and check whether YOLO drew *any* box on them: no box → tune the
> **detection** knobs above; box but no number → tune the **recognition** knobs (and
> check the live UI's candidates queue — the rider may already be sitting there for
> review). The two directions trade off against speed and false positives, so tune the
> stage that is actually failing.

---

## Known Limitations

1. **Single frame, no tracking (POC)**: the `run_poc.py` script processes one still
   image. The live pipeline handles the multi-frame case via time-window deduplication.

2. **No finish-line geometry**: every detected rider in frame is OCR'd — there is no
   crossing-zone filter (dropped; camera angles made it counterproductive). "When did
   they cross" is approximated by when the number first reads confidently.

3. **Double-number panel layout**: some UCI panels print the number twice. When
   PaddleOCR detects both tokens, the combined string may exceed `max_digits=3` and be
   rejected. In practice the clearest read wins via edit-distance snapping.

4. **CPU-only, single laptop**: inference is CPU-only. The live pipeline accepts lag
   during fast bursts and drains the queue after capture stops (by design — no frames
   are dropped).

5. **AGPL license (YOLO)**: YOLO is licensed AGPL-3.0. For internal use this is fine;
   if distributed as a network service, replace `detector.py` or obtain a commercial
   Ultralytics license.

---

## Specs

- `specs/completed/poc/` — single-image POC requirements, design, and tasks
- `specs/completed/collection/` — frame-collection app requirements, design, and tasks
- `specs/completed/results-ux/` — original standalone results viewer (superseded by the
  live pipeline's unified page; kept for historical reference)
- `specs/completed/live-pipeline/` — live pipeline requirements, design, and tasks
- `specs/review-editing/` — review & editing feature (frame browser, manual crossings, order, candidates, queue status)
