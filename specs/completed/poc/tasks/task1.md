# Task 1 — Project Scaffold, Shared Contracts & Environment

**Agent:** sonnet  **Depends on:** nothing  **Blocks:** all other tasks
**Milestone:** M1 (design §10)

## Objective
Stand up the project so every other agent has a fixed skeleton, frozen interface
contracts, a working Python environment, and a CLI that runs end-to-end on the sample
image producing an (empty) `results.json`. This proves the plumbing before any CV logic.

## Read first
`../requirements.md`, `../design.md` (esp. §4 module breakdown, §7 config, §8 structure).

## Files you own (create all)
```
comp-vision-results/
  config.yaml
  roster.txt                     # stub roster to exercise validation
  requirements.txt
  .gitignore
  run_poc.py                     # CLI entrypoint
  src/rider_id/__init__.py
  src/rider_id/types.py          # FROZEN CONTRACT — dataclasses
  src/rider_id/config.py         # load_config(path) -> dict
  src/rider_id/detector.py       # stub signature only
  src/rider_id/zones.py          # stub signature only
  src/rider_id/locate.py         # stub signature only
  src/rider_id/ocr.py            # stub signature only
  src/rider_id/validate.py       # stub signature only
  src/rider_id/score.py          # stub signature only
  src/rider_id/pipeline.py       # stub: returns [] for now
  src/rider_id/io_out.py         # stub signature only
```
Downstream tasks fill in the stub modules. You provide the **signatures + docstrings**
so their contracts are frozen.

## Contracts to define (exact — do not let downstream change these)

`types.py`:
```python
from dataclasses import dataclass

@dataclass
class RiderBox:
    xyxy: tuple[float, float, float, float]   # x1,y1,x2,y2 absolute px in full image
    det_conf: float

@dataclass
class OcrResult:
    text: str                                 # raw recognized string
    ocr_conf: float                           # 0..1
    box: tuple[float, float, float, float]    # x1,y1,x2,y2 relative to the crop given

@dataclass
class CrossingResult:
    number: str | None        # validated roster number, or None if rejected
    raw_text: str | None      # OCR text before validation (for review)
    confidence: float         # final 0..1
    status: str               # "confident" | "needs_review" | "rejected"
    rider_box: tuple[float, float, float, float]
    crop_path: str | None
```

Module signatures (bodies are stubs raising `NotImplementedError`, except `pipeline`):
```python
# detector.py
def detect_riders(image_bgr, cfg) -> list[RiderBox]: ...
# zones.py
def load_zone(cfg): ...                         # returns a usable zone object/polygon
def in_crossing_zone(box: RiderBox, zone) -> bool: ...
# locate.py
def number_region(image_bgr, box: RiderBox, cfg): ...   # -> BGR crop (np.ndarray)
# ocr.py
def read_number(crop_bgr, cfg) -> list[OcrResult]: ...
# validate.py
def load_roster(cfg) -> set[str] | None: ...
def validate(ocr_results: list[OcrResult], roster, cfg): ...  # -> (number|None, raw_text|None, conf)
# score.py
def classify(number, confidence, cfg) -> str: ...   # "confident"|"needs_review"|"rejected"
# io_out.py
def write_json(results, out_dir): ...
def write_annotated_image(image_bgr, results, zone, out_dir): ...
def write_crops(image_bgr, results, out_dir): ...
# pipeline.py
def run(image_bgr, cfg) -> list[CrossingResult]:    # for M1: return []
    return []
```

## config.yaml
Reproduce design §7 verbatim (with the resolved decisions):
```yaml
detector:
  weights: yolov8n.pt
  person_conf: 0.35
crossing_zone:
  polygon: null              # null = default to near/lower band of frame; task2 defines default
locate:
  back_band: [0.45, 0.85]
ocr:
  engine: paddleocr
  use_angle_cls: true
validate:
  roster: roster.txt
  min_digits: 1
  max_digits: 3
  leading_zeros: false
  max_edit_distance: 1
score:
  confidence_threshold: 0.60
output:
  dir: out/
```

## roster.txt
Stub, one number per line, `101` through `199` (covers the visible numbers; user will
replace with the real start-list later).

## requirements.txt
Pin the full stack so downstream agents never pip-install concurrently:
```
ultralytics
paddleocr
paddlepaddle
opencv-python-headless
numpy
pyyaml
```

## run_poc.py
CLI: `python run_poc.py <image_path> [--config config.yaml]`. Loads config, reads the
image with OpenCV, calls `pipeline.run(image, cfg)`, then `io_out.write_json(...)`.
For M1 the pipeline returns `[]`, so it writes `out/results.json` = `[]`.

## Environment

**Use Python 3.12 — NOT the system default.** The machine's default `python3` is
**3.14**, which lacks wheels for `paddlepaddle`/`torch`. Python **3.12** is installed at
`/usr/bin/python3.12` (verified 3.12.13); build the venv with it explicitly:

```bash
cd comp-vision-results
/usr/bin/python3.12 -m venv .venv
source .venv/bin/activate
python --version            # must print Python 3.12.x
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Do **not** run `python -m venv` with the bare `python`/`python3` — that would pick up
3.14 and the install will fail on the paddle/torch wheels.

Then verify imports succeed:
```bash
python -c "import ultralytics, paddleocr, cv2, yaml; print('imports OK')"
```

If `paddlepaddle`/`paddleocr` still fails to install even under 3.12, **document the
exact error in your final report** and note the EasyOCR fallback (design §2) — do NOT
silently drop OCR from requirements.

## Acceptance criteria
- `source .venv/bin/activate && python run_poc.py ../ridersFromThBack.jpg` exits 0 and
  writes `out/results.json` containing `[]`.
- `python -c "import ultralytics, paddleocr, cv2, yaml"` succeeds (or install failure is
  clearly documented per above).
- All stub modules import without error; `types.py` matches the contract exactly.
- `.gitignore` excludes `.venv/`, `out/`, `*.pt`, `__pycache__/`.

## Out of scope
Any real detection/OCR/validation logic — those are tasks 2–5.

## Final report to include
Confirm acceptance criteria, note any install issues, and list the exact frozen
signatures so downstream agents can rely on them.
