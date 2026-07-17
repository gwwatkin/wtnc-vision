"""
Task 3 — acceptance verification script.

Usage (from project root, venv active):
    python scripts/preview_ocr.py

Verifies:
  1. number_region() on the nearest rider's approximate box yields a crop
     containing the 101 panel.
  2. read_number() on that crop returns an OcrResult with text containing '101'.
  3. PaddleOCR loads once and runs CPU-only.
  4. No changes to types.py or any other module are required.

The nearest rider (101) in ridersFromThBack.jpg occupies roughly:
    x=0..250, y=0..220 (absolute pixel coords of the 561x352 image)
This is an eyeballed box — task 2 (detector) will supply real boxes.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from project root or scripts/ dir.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cv2
import yaml

from rider_id.locate import number_region
from rider_id.ocr import read_number
from rider_id.types import RiderBox

PROJECT_ROOT = Path(__file__).parent.parent
IMAGE_PATH = PROJECT_ROOT / "ridersFromThBack.jpg"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
OUT_DIR = PROJECT_ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

# Approximate box for the nearest rider (101) — eyeballed from the image.
# Image is 561x352 pixels; this rider is the large figure on the left.
NEAREST_RIDER_BOX = RiderBox(xyxy=(0.0, 0.0, 250.0, 220.0), det_conf=1.0)


def main() -> None:
    print("=== Task 3 — number_region + read_number acceptance check ===\n")

    # Load config.
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    print(f"Config loaded.  Engine: {cfg['ocr']['engine']}")
    print(f"Back band fractions: {cfg['locate']['back_band']}")

    # Load image.
    image_bgr = cv2.imread(str(IMAGE_PATH))
    if image_bgr is None:
        raise FileNotFoundError(f"Test image not found: {IMAGE_PATH}")
    h, w = image_bgr.shape[:2]
    print(f"Image loaded: {w}x{h} px\n")

    # --- Stage 1: number_region ---
    box = NEAREST_RIDER_BOX
    print(f"Rider box (approx): {box.xyxy}")
    crop = number_region(image_bgr, box, cfg)
    print(f"Crop shape: {crop.shape}  (h={crop.shape[0]}, w={crop.shape[1]})")

    crop_path = OUT_DIR / "nearest_rider_number_region.jpg"
    cv2.imwrite(str(crop_path), crop)
    print(f"Crop saved: {crop_path}\n")

    # --- Stage 2: read_number ---
    print("Running OCR on crop...")
    results = read_number(crop, cfg)

    if not results:
        print("WARNING: OCR returned no results on the crop.")
    else:
        print(f"OCR returned {len(results)} result(s):")
        for i, r in enumerate(results):
            print(f"  [{i}] text={r.text!r:20s}  conf={r.ocr_conf:.4f}  "
                  f"box=({r.box[0]:.0f},{r.box[1]:.0f},"
                  f"{r.box[2]:.0f},{r.box[3]:.0f})")

    # --- Acceptance check ---
    texts_found = [r.text for r in results]
    has_101 = any("101" in t for t in texts_found)
    print()
    if has_101:
        match = next(r for r in results if "101" in r.text)
        print(f"PASS  '101' found in OCR output: "
              f"text={match.text!r}  conf={match.ocr_conf:.4f}")
    else:
        print(f"FAIL  '101' NOT found in OCR output.  Texts found: {texts_found}")

    # --- Also test with 2x upscaled crop (optional enhancement path) ---
    print("\n--- Upscaled crop (2x, for reference) ---")
    import numpy as np
    crop_2x = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
    results_2x = read_number(crop_2x, cfg)
    crop_2x_path = OUT_DIR / "nearest_rider_number_region_2x.jpg"
    cv2.imwrite(str(crop_2x_path), crop_2x)
    print(f"Crop 2x saved: {crop_2x_path}")
    if not results_2x:
        print("  No results on 2x crop.")
    else:
        print(f"  {len(results_2x)} result(s) on 2x crop:")
        for i, r in enumerate(results_2x):
            print(f"    [{i}] text={r.text!r:20s}  conf={r.ocr_conf:.4f}")
        has_101_2x = any("101" in r.text for r in results_2x)
        status = "PASS" if has_101_2x else "FAIL"
        print(f"  {status}  '101' in 2x results: {has_101_2x}")

    print("\nDone.")


if __name__ == "__main__":
    main()
