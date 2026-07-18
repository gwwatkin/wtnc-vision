"""
Pipeline orchestrator — Task 5.

Orchestrates the full rider-number recognition pipeline:
  1. detect_riders      — YOLO person boxes
  2. number_region      — crop lower-back sub-region per box
  3. read_number        — PaddleOCR on each sub-region
  4. validate           — numeric filter + roster match
  5. classify           — confidence → status string
  6. (outputs handled by caller via io_out)
"""
from __future__ import annotations

import numpy as np

from . import detector, locate, ocr, validate, score
from .types import CrossingResult


def run(image_bgr: np.ndarray, cfg: dict) -> list[CrossingResult]:
    """Run the full rider-number recognition pipeline on a single image.

    Args:
        image_bgr: Full input image as an OpenCV BGR np.ndarray.
        cfg: Parsed config dict (from config.load_config()).

    Returns:
        List of CrossingResult instances, one per detected rider (including
        rejected results for traceability).
    """
    # Stage 1: Detect riders
    boxes = detector.detect_riders(image_bgr, cfg)

    # Stage 2-5: Process each detected rider
    roster = validate.load_roster(cfg)

    results: list[CrossingResult] = []
    for box in boxes:
        # Stage 2: Locate number region (lower-back sub-crop)
        crop = locate.number_region(image_bgr, box, cfg)

        # Stage 3: OCR on the sub-region
        reads = ocr.read_number(crop, cfg)

        # Stage 4: Validate against roster
        number, raw_text, conf = validate.validate(reads, roster, cfg)

        # Stage 5: Classify confidence → status
        status = score.classify(number, conf, cfg)

        # Build CrossingResult (crop_path filled later by io_out.write_crops)
        results.append(CrossingResult(
            number=number,
            raw_text=raw_text,
            confidence=conf,
            status=status,
            rider_box=box.xyxy,
            crop_path=None,
            det_conf=box.det_conf,  # refinement 1: plumb RiderBox.det_conf through
        ))

    return results
