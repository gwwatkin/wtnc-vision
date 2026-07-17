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
    roster.csv                     # uploaded name/category table
    roster.txt                     # valid numbers (used by the CV pipeline)
```

### Configuration

`collection/backend/config.yaml` — key live-pipeline settings:

| key | default | meaning |
|---|---|---|
| `live.enabled` | `true` | `false` → pure frame storage, no CV |
| `live.dedup_window_s` | `5.0` | seconds within which same number = one crossing |
| `live.cv_config` | `../../config.yaml` | repo POC pipeline config |

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
  annotated.jpg       # image with rider boxes, crossing zone, and recognized number
  crops/101_0.jpg     # cropped number-panel for each confident read
```

See `EVALUATION.md` for the full baseline assessment (the sample image reads `101`
at 0.997 confidence).

### Adjusting config.yaml

All tunable parameters live in `config.yaml`:

- **`crossing_zone.polygon`** — `null` = bottom 20% of frame (default); or explicit
  `[[x,y], …]` pixel polygon.
- **`locate.back_band`** — vertical fraction of the rider box where the number panel
  sits (`[0.20, 0.55]` = skip top 20%, crop to 55%).
- **`score.confidence_threshold`** — reads below this → `needs_review` (default 0.60).
- **`validate.roster`** — path to `roster.txt` (one valid number per line).

---

## Known Limitations

1. **Single frame, no tracking (POC)**: the `run_poc.py` script processes one still
   image. The live pipeline handles the multi-frame case via time-window deduplication.

2. **Finish-line zone is approximate**: the default zone (bottom 20% of frame) works
   well for a static finish-line camera but is not a true virtual finish line.

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
- `specs/live-pipeline/` — live pipeline requirements, design, and tasks
