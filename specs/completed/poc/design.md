# Design — Finish-Line Rider Number Recognition (POC)

Companion to `requirements.md`. This document fixes the **tech stack** and the
**POC architecture**, and shows how each POC piece extends to the full video system.

---

## 1. Design Philosophy

- **Build the POC as the first vertical slice of the real pipeline**, not a throwaway.
  Every module we write for the still image (detect → locate number → OCR → score →
  output) is reused verbatim in the video system; the video system just adds *tracking*
  and *line-crossing* in front of it.
- **Pretrained models only for the POC.** No custom training, no labeled dataset. We
  lean on off-the-shelf person detection + off-the-shelf OCR. Custom training is a
  later optimization, not a prerequisite.
- **Bias toward flagging uncertainty** (per NFR1): every read carries a confidence and
  a saved crop, and low-confidence reads are marked `needs_review` rather than dropped
  or asserted.

---

## 2. Tech Stack

| Concern | Choice | License | Why |
|---|---|---|---|
| Language | **Python 3.11+** | — | The entire CV/OCR ecosystem lives here. |
| Rider detection | **Ultralytics YOLO** (v8 or v11, `yolo*.pt` COCO weights) | AGPL-3.0 ⚠️ | Best-in-class pretrained **person** detector, zero training needed. Internal-use only (see LR2). |
| Number OCR | **PaddleOCR** (detector + angle classifier + recognizer) | Apache-2.0 | Strong on **printed digits**, includes text *detection* so it localizes the number, and an **angle classifier** that handles the tilt of a pinned cloth panel. |
| Image / video I/O | **OpenCV** + **NumPy** | Apache / BSD | Read image, crop, draw overlays, later decode video frames. |
| Tracking (video phase) | **ByteTrack** (via supervision) | MIT | Stable per-rider IDs across frames. |
| Line crossing + annotation (video phase) | **supervision** (Roboflow) | MIT | `LineZone` crossing primitive + clean box/label annotators. |
| Config | **YAML** (PyYAML) | MIT | Adjustable thresholds & zones without code changes (NFR4). |
| Packaging / env | **uv** or **venv + pip** | — | Reproducible install. |

**OCR choice — PaddleOCR over EasyOCR/Tesseract:** all three are Apache/permissive.
Tesseract is weak on non-document, angled, real-world text. EasyOCR is fine but
PaddleOCR's built-in **angle classifier** and stronger scene-text detector suit a
tilted cloth panel better. This is a swappable module (see §4, `ocr` interface) — if
PaddleOCR underperforms on our footage we can drop in EasyOCR without touching the
rest of the pipeline.

**Licensing note (LR1/LR2):** only YOLO is AGPL. If the system is ever distributed or
offered as a service to third parties, we swap YOLO for **YOLOX (Apache-2.0)** or buy
an Ultralytics commercial license. Everything else is already permissive. The module
boundary in §4 (`detector`) makes that swap isolated.

---

## 3. POC Pipeline (single still image)

```
                ┌─────────────────────────────────────────────────────────┐
   image  ──▶   │  1. DETECT      YOLO person detection → rider boxes      │
                │  2. ZONE FILTER keep boxes inside the "crossing zone"    │
                │  3. LOCATE      take lower-back sub-region of each box   │
                │  4. OCR         PaddleOCR on sub-region → digit strings  │
                │  5. VALIDATE    keep numeric; (optional) match roster    │
                │  6. SCORE       confidence → confident | needs_review    │
                │  7. OUTPUT      JSON + annotated image + per-number crops │
                └─────────────────────────────────────────────────────────┘
```

**Stage detail:**

1. **Detect** — Run YOLO restricted to COCO class `person`. Output: list of rider
   bounding boxes + detection confidences.
2. **Zone filter** — A configurable **crossing zone** (polygon/box, default = the near
   region of the frame where numbers are large and legible per A2) filters out riders
   up the road whose numbers we explicitly do **not** try to read (Out-of-Scope §8).
   For the still image the zone will contain the nearest rider (`101`).
3. **Locate number region** — Within each kept rider box, crop the **lower-back
   sub-region** (a configurable fractional band of the box, since the panel is pinned
   low). This narrows OCR to where the number is and cuts false text (sponsor logos,
   frame numbers).
4. **OCR** — PaddleOCR runs detection+recognition on the sub-region, returning
   candidate text boxes, strings, and per-string confidences.
5. **Validate** — Keep numeric tokens only, then validate against the rider
   **roster/start-list** (available — confirmed): accept only numbers that exist in the
   roster, snapping near-misses (e.g. a single confused digit) to the nearest valid
   roster number within an edit-distance budget, and rejecting reads with no plausible
   match. This is the single highest-leverage accuracy win and is **on by default**.
   Numbers are **1–3 digits, black on white, no leading zeros** (confirmed).
6. **Score** — Combine OCR confidence (and roster match, if enabled) into a final
   score; compare to `confidence_threshold`. Below → `needs_review`.
7. **Output** — Emit the three artifacts (§5).

**No tracking, no line-crossing, no lap counting in the POC** — a still image has one
moment in time. Those are the video-phase additions (§6).

---

## 4. Module Breakdown & Interfaces

Kept small and swap-friendly. Each is a plain function/class with a typed boundary:

```
detector.py    detect_riders(image) -> list[RiderBox]          # YOLO; swappable
zones.py       in_crossing_zone(box, zone_cfg) -> bool
locate.py      number_region(image, box, cfg) -> image_crop     # lower-back band
ocr.py         read_number(crop) -> list[OcrResult]             # PaddleOCR; swappable
validate.py    validate(ocr_results, roster|None) -> Number|None
score.py       classify(number, conf, threshold) -> "confident" | "needs_review"
pipeline.py    orchestrates 1–7, returns list[CrossingResult]
io_out.py      write_json / write_annotated_image / write_crops
run_poc.py     CLI entrypoint: image path + config -> artifacts
```

Types (dataclasses):
```
RiderBox      = {xyxy, det_conf}
OcrResult     = {text, ocr_conf, box}
CrossingResult= {number, confidence, status, rider_box, crop_path}
```

The two `# swappable` modules (`detector`, `ocr`) are exactly the AGPL and
accuracy-risk boundaries — isolating them means either can be replaced without
touching the pipeline.

---

## 5. Outputs (POC)

Written to a configurable `out/` dir (satisfies FR4–FR7, NFR2):

1. **`results.json`** — array of `CrossingResult` records:
   ```json
   [{"number":"101","confidence":0.94,"status":"confident",
     "rider_box":[x1,y1,x2,y2],"crop":"crops/101_0.jpg"}]
   ```
2. **`annotated.jpg`** — input image with rider boxes, the crossing zone, and the
   recognized number drawn on each rider (FR5).
3. **`crops/`** — one cropped image per detected number panel (FR7), filename encodes
   the read + index so hand-review is a glance.

---

## 6. Extension to the Full Video System

The POC pipeline (stages 1–7) becomes the **per-frame inner loop**. We wrap it:

```
video frames ─▶ YOLO detect ─▶ ByteTrack (stable IDs)
                                   │
                                   ▼
                supervision LineZone: did track ID cross finish line?
                                   │ yes
                                   ▼
                run POC stages 3–6 on that rider's crop  ──▶ number
                                   │
                                   ▼
                lap_count[number] += 1  ──▶ append crossing log row
                (number, lap, timestamp, confidence, crop)
```

- **Tracking (ByteTrack)** gives each rider a persistent ID so we OCR them once per
  crossing, not once per frame, and we can pick the single clearest frame (A3).
- **LineZone (supervision)** provides the crossing event + direction (FR9–FR11).
- **Lap bookkeeping** is a dict keyed by validated number (FR12); unreadable crossings
  emit an `unknown/needs_review` row rather than being skipped (FR13).
- Everything in stages 3–6 is unchanged — that's the payoff of building the POC as the
  first slice.

**Crossing timestamp rule (resolved, OQ2):** a rider's crossing time is the timestamp
of the **first frame in which that track is detected crossing the line**, not an
interpolated sub-frame estimate. For two riders crossing near-simultaneously, each gets
their own event and their order follows whichever is detected crossing first. This is
simple, deterministic, and good enough given imprecise-timing tolerance (A6); true ties
go to human review.

---

## 7. Configuration (`config.yaml`)

```yaml
detector:
  weights: yolov8n.pt         # start small/fast; upgrade to m/l if accuracy needs it
  person_conf: 0.35
crossing_zone:                # polygon in image coords; default = near band of frame
  polygon: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
locate:
  back_band: [0.45, 0.85]     # vertical fraction of rider box to search for the panel
ocr:
  engine: paddleocr           # start here; swappable to easyocr if sample results poor
  use_angle_cls: true
validate:
  roster: roster.txt          # start-list of valid numbers (available) — on by default
  min_digits: 1
  max_digits: 3               # confirmed: 1–3 digits
  leading_zeros: false        # confirmed: no leading zeros
  max_edit_distance: 1        # snap a near-miss read to nearest valid roster number
score:
  confidence_threshold: 0.60  # below → needs_review
output:
  dir: out/
```

---

## 8. Project Structure

```
comp-vision-results/          # (this folder — POC lives here)
  ridersFromThBack.jpg        # sample input
  requirements.md
  design.md
  config.yaml
  pyproject.toml / requirements.txt
  src/rider_id/
    detector.py  zones.py  locate.py  ocr.py
    validate.py  score.py  pipeline.py  io_out.py  types.py
  run_poc.py
  out/                        # generated artifacts (gitignored)
```

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| OCR misreads tilted / low-contrast panel | wrong number | PaddleOCR angle classifier; **roster validation** (OQ3); flag low-conf. |
| YOLO misses a rider in a tight pack | missed crossing | Crossing zone is near/large where riders separate; upgrade YOLO size; video phase has many frames per rider. |
| AGPL (YOLO) blocks future distribution | legal | Isolated `detector` module; swap to YOLOX / commercial license if needed. |
| Sponsor logos / frame numbers OCR'd as the number | false read | Lower-back band restriction + numeric/roster filter. |
| Two riders overlap in the zone | ambiguous read | POC returns both with boxes; video phase disambiguates via tracking; contentious → human review (A6). |

---

## 10. Build Milestones

1. **M1 — Skeleton:** project scaffold, config loader, CLI reads image → writes empty
   `results.json`. Proves plumbing.
2. **M2 — Detection + zone:** YOLO person boxes + crossing-zone filter drawn on
   `annotated.jpg`.
3. **M3 — OCR read:** locate lower-back band → PaddleOCR → recognize `101` (and any
   other legible zone numbers) with confidence.
4. **M4 — Outputs + scoring:** full `results.json`, crops, `needs_review` flagging.
5. **M5 — Tune & evaluate:** thresholds/zone against the still; record baseline; decide
   go/no-go for the video phase (SC4).

---

## 11. Deployment (resolved, OQ5)

The entire system — POC and full video pipeline — runs **locally on a single laptop**:
no server, no GPU box, no network dependency (reinforces NFR3/NFR5). Implications:

- **Model sizing:** default to small, fast weights (`yolov8n`/`yolov8s`); step up only
  if accuracy requires it and the laptop can sustain the frame rate.
- **Compute:** assume **CPU or a modest laptop GPU**. If no usable GPU, the full system
  processes **recorded video offline** (faster-or-slower than real-time is fine — A6),
  rather than requiring live real-time throughput.
- **Footprint:** models and dependencies (~hundreds of MB) ship with the app; PaddleOCR
  and YOLO both run CPU-only if needed.
- **Distribution:** because it's a self-contained laptop app, revisit the AGPL/YOLO
  constraint (LR2) only if the app is ever handed to third parties.

## 12. Decisions — Resolved

- **D1 (roster)** — ✅ **Available.** Roster validation is a first-class step, **on by
  default** (`validate.roster`), with edit-distance snapping of near-misses.
- **D2 (format)** — ✅ **1–3 digits, black on white, no leading zeros.** Sets
  `validate.max_digits: 3`, `leading_zeros: false`.
- **D3 (OCR engine)** — ✅ **Decide during build.** Start with **PaddleOCR**; switch to
  EasyOCR only if PaddleOCR underperforms on the sample or its install causes friction.
  The `ocr` module is swappable either way.
```
