# Finish-Line Rider Number Recognition — POC

A computer-vision proof of concept that detects cyclists crossing a finish line and reads the back-number printed on their jersey from a still image. The system proves that off-the-shelf person detection (YOLO) and OCR (PaddleOCR) can reliably read race numbers from a fixed overhead camera without any custom model training. See [requirements.md](specs/completed/poc/requirements.md) for the full problem statement and [design.md](specs/completed/poc/design.md) for the architecture.

---

## Requirements

- **Python 3.12** (the ML wheels — PaddlePaddle, Ultralytics — require Python ≤ 3.12; do **not** use system Python 3.14+)
- Linux (tested on Arch Linux); macOS should work with the same steps
- Internet access on first run (YOLO and PaddleOCR models are auto-downloaded; subsequent runs use the cache)

---

## Setup

```bash
# 1. Create and activate a Python 3.12 virtual environment
/usr/bin/python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

> If you see a `ccache` warning from PaddlePaddle, it is harmless — the pipeline runs without it.

---

## Run

```bash
# Activate the venv first (every session)
source .venv/bin/activate

# Run the pipeline on the sample image
python run_poc.py ridersFromThBack.jpg
```

On first run, YOLO (`yolov8n.pt`) and PaddleOCR (`PP-OCRv6`) models are downloaded automatically (~100 MB total). Subsequent runs use the cached models and take a few seconds on a laptop CPU.

### What appears in out/

```
out/
  results.json        # structured results: number, confidence, status, bounding box, crop path
  annotated.jpg       # input image with rider boxes, crossing zone, and recognized number overlaid
  crops/
    101_0.jpg         # cropped number-panel image for the confident read
```

`results.json` example:
```json
[
  {
    "number": "101",
    "raw_text": "101",
    "confidence": 0.997,
    "status": "confident",
    "rider_box": [64.0, 38.0, 288.3, 350.1],
    "crop": "crops/101_0.jpg"
  }
]
```

Each result has a `status` of either `confident` (confidence ≥ threshold) or `needs_review` (below threshold, flag for human check). Results where OCR finds no valid number show `status: rejected`.

---

## Pointing at a New Image

```bash
python run_poc.py /path/to/your/image.jpg
```

The pipeline expects a single JPEG/PNG still frame from a fixed finish-line camera with riders' backs visible.

---

## Adjusting the Zone and Thresholds in config.yaml

All tunable parameters live in `config.yaml`. No code changes are needed.

### Crossing zone

```yaml
crossing_zone:
  polygon: null   # null = use default: bottom 20% of frame height
```

- **`null` (default)**: the zone is the bottom 20% of the frame. Riders whose lower edge (`y2`) is in the bottom 20% are in zone. On the sample image (352 px tall), this threshold is `y=282`, which cleanly isolates the nearest rider.
- **Explicit polygon**: to define an exact region, replace `null` with a list of `[x, y]` pixel coordinates tracing the zone boundary, e.g.:
  ```yaml
  crossing_zone:
    polygon: [[0, 250], [561, 250], [561, 352], [0, 352]]
  ```
  Use the grid overlay in `out/annotated.jpg` as a visual reference for choosing coordinates.

### Back-band (where the number panel is on the rider)

```yaml
locate:
  back_band: [0.20, 0.55]   # fraction of rider box height, from top
```

`[0.20, 0.55]` means: skip the top 20% of the detected rider box (helmet, shoulders) and crop from 20% to 55% of the box height. Adjust if your camera angle places the number higher or lower on the rider.

### Confidence threshold

```yaml
score:
  confidence_threshold: 0.60   # reads below this → needs_review
```

Lower this to be more permissive (more `confident` reads, more potential errors). Raise it to be more conservative (more `needs_review`, fewer false confident reads). The default 0.60 is appropriate for PaddleOCR on clear crops.

### Roster

```yaml
validate:
  roster: roster.txt        # one valid number per line
  max_edit_distance: 1      # allow 1-character OCR errors to snap to nearest roster entry
```

Update `roster.txt` to match your event's start list. The validator rejects any OCR read that doesn't match a roster number (within 1 edit distance), eliminating sponsor text and other false reads.

---

## Known Limitations

1. **Single frame, no tracking**: the POC processes one still image. In video, the same rider appears in many frames — multi-frame confirmation and per-rider tracking (ByteTrack) are needed to avoid duplicate reads and to fire a timestamped crossing event.

2. **Finish-line zone is approximate**: the default zone (bottom 20% of frame) approximates "at the line" but is not a true virtual finish line. The video phase should use `supervision.LineZone` for precise crossing detection.

3. **Double-number panel layout**: some UCI race-number panels print the number twice (small above, large below). When PaddleOCR detects both, the combined string (e.g. "02 102") may exceed `max_digits=3` and be rejected. In practice the largest/clearest number wins, but this is an edge case to handle in the video phase.

4. **Far riders not read**: by design, riders more than ~1 rider-length back from the camera are excluded by the zone. Their numbers are small and partially occluded; the OCR accuracy on those crops is lower. This is correct behaviour for the finish-line use case.

5. **CPU-only, single laptop**: inference is CPU-only (no GPU required or assumed). On a modern laptop CPU, a single image takes ~3–5 seconds. Video-speed processing will require frame-skipping or a GPU.

6. **AGPL license (YOLO)**: YOLO is licensed AGPL-3.0, acceptable for internal use. If the system is distributed or offered as a network service to third parties, replace `detector.py` with a permissively-licensed detector (e.g. YOLOX Apache-2.0) or obtain a commercial Ultralytics license. The `detector` module is intentionally isolated for this swap.

---

## Next Steps (Video Phase)

See [design.md §6](specs/completed/poc/design.md) for the full video-phase extension plan. The three highest-priority additions are:

1. **ByteTrack tracking** — stable per-rider IDs across frames, OCR triggered once per crossing
2. **supervision LineZone** — virtual finish line with timestamped crossing events
3. **Multi-token validation** — pick the best single OCR token from a crop rather than requiring a clean single-token read

All existing pipeline stages (detect → zone → locate → OCR → validate → score → output) are reused unchanged in the video phase. See [EVALUATION.md](EVALUATION.md) for the full baseline assessment and go/no-go recommendation.

---

## Results Timeline (web UI)

A companion static web app in [`web/`](web/) displays finish-line crossings as a
scrollable, category-laned timeline. It merges a crossings CSV (`time, race_number` —
produced by a future video-phase iteration of the pipeline) with a roster CSV
(`race_number, name, category`) and renders crossings newest-first, one lane per
category on a shared time axis, with gap separators between packs.

```bash
cd web && python -m http.server 8000   # then open http://localhost:8000/
```

No build step and no runtime dependencies — vanilla ES modules served statically. See
[web/README.md](web/README.md) for configuration (gap threshold, refresh interval, CSV
paths) and [specs/completed/results-ux/](specs/completed/results-ux/) for the
requirements, design, and task breakdown.
