# Task 5 — Pipeline Integration + Outputs

**Agent:** sonnet  **Depends on:** task2, task3, task4 (all complete)  **Parallel with:** none
**Milestone:** M4 (design §10)

## Objective
Wire the finished modules into `pipeline.run()` and implement the three output artifacts,
so `run_poc.py` produces real results on the sample image (design §3 steps 1–7, §5).

## Read first
`../requirements.md` (§5 FR4–FR8, NFR2), `../design.md` (§3 full pipeline, §5 outputs).
Do NOT change `types.py` or the signatures from task1.

## Files you own
```
src/rider_id/pipeline.py     # replace the M1 stub
src/rider_id/io_out.py       # implement the three writers
```
You may read/import every other module but MUST NOT edit them. If a real signature
mismatch blocks you, stop and report it rather than editing another agent's file.

## Specification

### pipeline.py — `run(image_bgr, cfg) -> list[CrossingResult]`
Orchestrate the modules in order:
1. `boxes = detector.detect_riders(image_bgr, cfg)`
2. `zone = zones.load_zone(cfg)`; keep boxes where `zones.in_crossing_zone(box, zone)`.
3. `roster = validate.load_roster(cfg)`.
4. For each in-zone box:
   - `crop = locate.number_region(image_bgr, box, cfg)`
   - `reads = ocr.read_number(crop, cfg)`
   - `number, raw_text, conf = validate.validate(reads, roster, cfg)`
   - `status = score.classify(number, conf, cfg)`
   - build a `CrossingResult(number, raw_text, conf, status, rider_box=box.xyxy,
     crop_path=None)` — `crop_path` is filled by `io_out.write_crops`.
5. Return the list (include `rejected` ones too — they may still warrant human review;
   design §5 keeps everything traceable).

### io_out.py
- `write_json(results, out_dir)` → `out_dir/results.json`, array of records matching
  design §5 (number, confidence, status, rider_box, raw_text, crop).
- `write_crops(image_bgr, results, out_dir)` → save each result's rider-number crop to
  `out_dir/crops/<number-or-unknown>_<i>.jpg`; set each result's `crop_path` accordingly.
  Call this **before** `write_json` so paths are recorded.
- `write_annotated_image(image_bgr, results, zone, out_dir)` → `out_dir/annotated.jpg`:
  draw the crossing zone, each rider box, and a label = `number (status)` colored by
  status (e.g. green=confident, amber=needs_review, red=rejected). Use OpenCV drawing
  (headless).

### run_poc.py
Update the entrypoint (this file is shared with task1 — you may edit it here) so it calls,
in order: `write_crops`, `write_annotated_image`, `write_json`, and prints a one-line
summary per result to stdout.

## Acceptance criteria
- `python run_poc.py ../ridersFromThBack.jpg` produces in `out/`:
  - `results.json` with at least the nearest rider read as **`101`**, `status:"confident"`.
  - `annotated.jpg` showing the zone, boxes, and the `101` label.
  - `crops/` containing the `101` crop, and every result's `crop_path` populated.
- The run exits 0, CPU-only, no runtime network (beyond first-run model downloads).
- No edits to detector/zones/locate/ocr/validate/score/types beyond reading them.

## Out of scope
Threshold/zone tuning and evaluation write-up (task6). Get it working correctly first;
task6 makes it good.

## Final report
Paste the `results.json` for the sample image and confirm `annotated.jpg` + crops were
written. Flag any integration mismatch you had to work around.
