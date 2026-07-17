"""
Pipeline orchestrator — Task 5.

Orchestrates the full rider-number recognition pipeline (design §3 stages 1–7):
  1. detect_riders      — YOLO person boxes
  2. zone filter        — keep boxes inside the crossing zone
  3. number_region      — crop lower-back sub-region per box
  4. read_number        — PaddleOCR on each sub-region
  5. validate           — numeric filter + roster match
  6. classify           — confidence → status string
  7. (outputs handled by caller via io_out)
"""
from __future__ import annotations

import numpy as np

from . import detector, zones, locate, ocr, validate, score
from .types import CrossingResult


def run(image_bgr: np.ndarray, cfg: dict) -> list[CrossingResult]:
    """Run the full rider-number recognition pipeline on a single image.

    Args:
        image_bgr: Full input image as an OpenCV BGR np.ndarray.
        cfg: Parsed config dict (from config.load_config()).

    Returns:
        List of CrossingResult instances, one per rider detected in the
        crossing zone (including rejected results for traceability).
    """
    frame_height = image_bgr.shape[0]

    # Stage 1: Detect riders
    boxes = detector.detect_riders(image_bgr, cfg)

    # Stage 2: Zone filter — resolve the zone against actual frame height first
    zone = zones.load_zone(cfg)
    resolved_zone = zones.resolve_zone(zone, frame_height)
    in_zone_boxes = [box for box in boxes if zones.in_crossing_zone(box, resolved_zone)]

    # Stage 3-6: Process each in-zone rider
    roster = validate.load_roster(cfg)

    results: list[CrossingResult] = []
    for box in in_zone_boxes:
        # Stage 3: Locate number region (lower-back sub-crop)
        crop = locate.number_region(image_bgr, box, cfg)

        # Stage 4: OCR on the sub-region
        reads = ocr.read_number(crop, cfg)

        # Stage 5: Validate against roster
        number, raw_text, conf = validate.validate(reads, roster, cfg)

        # Stage 6: Classify confidence → status
        status = score.classify(number, conf, cfg)

        # Build CrossingResult (crop_path filled later by io_out.write_crops)
        results.append(CrossingResult(
            number=number,
            raw_text=raw_text,
            confidence=conf,
            status=status,
            rider_box=box.xyxy,
            crop_path=None,
        ))

    return results
