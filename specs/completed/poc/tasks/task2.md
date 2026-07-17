# Task 2 — Rider Detection + Crossing Zone

**Agent:** sonnet  **Depends on:** task1  **Parallel with:** task3, task4
**Milestone:** M2 (design §10)

## Objective
Implement rider detection (YOLO person) and the crossing-zone filter, so the pipeline
can find riders and keep only those in the near "crossing zone" where numbers are
legible (design §3 steps 1–2).

## Read first
`../requirements.md` (§5 FR2), `../design.md` (§3 stages 1–2, §7 config, §9 risks).
Do NOT change `types.py` or any signatures from task1.

## Files you own
```
src/rider_id/detector.py
src/rider_id/zones.py
```
(You may add a small `scripts/preview_detect.py` helper for your own testing, but the
two modules above are the deliverable.)

## Specification

### detector.py — `detect_riders(image_bgr, cfg) -> list[RiderBox]`
- Load Ultralytics YOLO with `cfg["detector"]["weights"]` (default `yolov8n.pt`; it will
  auto-download on first run).
- Run inference on the BGR image, restrict to COCO class **`person`** only.
- Keep detections with confidence ≥ `cfg["detector"]["person_conf"]`.
- Return `RiderBox(xyxy=(x1,y1,x2,y2), det_conf=conf)` with **absolute pixel coords** of
  the full image, floats.
- Load the model once (module-level cache / lazy singleton) — do not reload per call.
- CPU-only; do not assume CUDA.

### zones.py
- `load_zone(cfg)`:
  - If `cfg["crossing_zone"]["polygon"]` is a list of points, use it.
  - If it is `null`/None, return a **sensible default zone** = the near/lower band of the
    frame where the closest rider appears. Recommended default: the bottom ~55% of the
    frame height, full width (tune so the nearest rider `101` in the sample falls inside,
    and the far small riders fall outside). Document the default clearly.
  - Return a representation usable by `in_crossing_zone` (e.g. a polygon or a y-threshold
    struct). Keep it simple.
- `in_crossing_zone(box: RiderBox, zone) -> bool`:
  - Decide membership using the box's **lower-center point** (feet/lower back area):
    `cx = (x1+x2)/2`, `cy = y2`. Return True if that point is inside the zone.
  - Rationale: a rider "is at the line" when their lower body reaches the near band.

## Acceptance criteria
- On `../ridersFromThBack.jpg`, `detect_riders` returns multiple `RiderBox`es including a
  large box around the **nearest rider** (the one wearing `101`).
- With default config (`polygon: null`), `in_crossing_zone` returns **True** for the
  nearest rider and **False** for the far/small riders up the road.
- No changes to `types.py` or other modules' signatures.
- Runs CPU-only, no network at runtime beyond the one-time YOLO weight download.

## How to verify
Write a throwaway snippet (or `scripts/preview_detect.py`) that draws all boxes + the
zone on the image and saves a PNG; eyeball that the nearest rider is boxed and in-zone.
Do not commit large outputs (respect `.gitignore`).

## Out of scope
Number localization, OCR, validation, final annotated output (tasks 3–5). You only
return boxes and the in-zone decision.

## Final report
State how many riders were detected, confirm the nearest rider is detected and in-zone,
and describe the default zone you implemented (so task5 and task6 know the behavior).
