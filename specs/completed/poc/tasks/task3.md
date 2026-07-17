# Task 3 — Number Localization + OCR

**Agent:** sonnet  **Depends on:** task1  **Parallel with:** task2, task4
**Milestone:** M3 (design §10)

## Objective
Given a rider box, crop the lower-back region where the number panel sits, and read the
digits with OCR (design §3 steps 3–4).

## Read first
`../requirements.md` (§5 FR3), `../design.md` (§3 stages 3–4, §7 config, §9 risks).
Do NOT change `types.py` or any signatures from task1.

## Files you own
```
src/rider_id/locate.py
src/rider_id/ocr.py
```
(Optional `scripts/preview_ocr.py` for your own testing.)

## Specification

### locate.py — `number_region(image_bgr, box: RiderBox, cfg)` -> BGR crop
- Take the rider box `xyxy` and return a sub-crop covering the **lower-back band** where
  the pinned cloth panel is, using vertical fractions `cfg["locate"]["back_band"]`
  (default `[0.45, 0.85]` of the box height). Keep full box width (optionally center
  60–80% to trim arms — your judgement; document it).
- Clamp to image bounds. Return the cropped `np.ndarray` (BGR).
- If the band is degenerate (tiny box), return the whole box crop rather than erroring.

### ocr.py — `read_number(crop_bgr, cfg)` -> list[OcrResult]
- Engine selected by `cfg["ocr"]["engine"]` — implement **`paddleocr`** first.
  - Use PaddleOCR with `use_angle_cls = cfg["ocr"]["use_angle_cls"]` (handles the tilt of
    a pinned panel — design §2). CPU mode.
  - Run detection+recognition on the crop; for each result produce
    `OcrResult(text=..., ocr_conf=..., box=(x1,y1,x2,y2) relative to the crop)`.
  - Load the OCR model once (module-level singleton).
- **Also implement an `easyocr` branch** behind the same `engine` switch (design §2 —
  swappable), so task6 can compare if PaddleOCR underreads. Keep it minimal.
- Do **no** filtering/validation here — return raw reads (may include non-numeric text
  like sponsor logos). Filtering is task4's job.

## Acceptance criteria
- `number_region` on the nearest rider's box (from the sample) yields a crop that
  visibly contains the `101` panel.
- `read_number` on that crop returns an `OcrResult` whose `text` contains `101` (possibly
  among other reads) with a plausible confidence.
- PaddleOCR (and EasyOCR fallback) load once and run CPU-only.
- No changes to `types.py` or other modules.

## Coordination note
You need a rider box to test, but task2 (which produces boxes) runs in parallel. **Do not
depend on task2's code.** For your own testing, hardcode an approximate box around the
nearest rider in the sample image (e.g. eyeball pixel coords) or crop the lower-left
quadrant. Your deliverable functions take `box`/`crop` as inputs and must not import
`detector.py`/`zones.py`.

## How to verify
Save the located crop and print OCR reads for the nearest rider; confirm `101` appears.

## Out of scope
Detection, zone logic, roster validation, scoring, final output assembly.

## Final report
Report the OCR reads for the nearest rider (raw text + confidences), which engine was
used, and any install/accuracy caveats (feeds task6's engine decision).
