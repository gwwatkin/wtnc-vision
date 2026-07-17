"""
Output writers — Task 5.

Implements:
  write_crops(image_bgr, results, out_dir)        — saves per-number crops; sets crop_path
  write_annotated_image(image_bgr, results, zone, out_dir) — draws zone + boxes + labels
  write_json(results, out_dir)                    — serialises CrossingResult list to JSON

Call order: write_crops BEFORE write_json so that crop_path is populated in the JSON.
"""
from __future__ import annotations

import dataclasses
import json
import os

import cv2
import numpy as np

from .types import CrossingResult

# BGR colors for each status label on the annotated image.
_STATUS_COLOR: dict[str, tuple[int, int, int]] = {
    "confident":    (0, 200, 0),     # green
    "needs_review": (0, 165, 255),   # amber (orange in BGR)
    "rejected":     (0, 0, 220),     # red
}
_DEFAULT_COLOR = (200, 200, 200)  # grey fallback

# Visual parameters
_BOX_THICKNESS = 2
_ZONE_COLOR = (255, 200, 0)       # cyan-ish blue for the zone band
_ZONE_ALPHA = 0.15                # transparency for zone fill
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE = 0.6
_FONT_THICKNESS = 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_crops(
    image_bgr: np.ndarray,
    results: list[CrossingResult],
    out_dir: str,
) -> None:
    """Save each result's rider-box crop and set result.crop_path.

    Crops are saved to <out_dir>/crops/<number-or-unknown>_<i>.jpg.
    The result objects are mutated in-place so that write_json records the paths.

    Args:
        image_bgr: Full input image (OpenCV BGR).
        results:   List of CrossingResult from pipeline.run() — mutated in-place.
        out_dir:   Output directory; crops/ sub-directory is created if needed.
    """
    crops_dir = os.path.join(out_dir, "crops")
    os.makedirs(crops_dir, exist_ok=True)

    img_h, img_w = image_bgr.shape[:2]

    for i, result in enumerate(results):
        # Label: use validated number or "unknown" for rejected/unread.
        label = result.number if result.number is not None else "unknown"
        filename = f"{label}_{i}.jpg"
        filepath = os.path.join(crops_dir, filename)

        # Crop the rider box from the full image.
        x1, y1, x2, y2 = result.rider_box
        cx1 = max(0, int(round(min(x1, x2))))
        cy1 = max(0, int(round(min(y1, y2))))
        cx2 = min(img_w, int(round(max(x1, x2))))
        cy2 = min(img_h, int(round(max(y1, y2))))

        if cx2 > cx1 and cy2 > cy1:
            crop = image_bgr[cy1:cy2, cx1:cx2]
        else:
            crop = np.zeros((1, 1, 3), dtype=np.uint8)

        cv2.imwrite(filepath, crop)

        # Record relative path (crops/<filename>) so JSON is portable.
        result.crop_path = os.path.join("crops", filename)


def write_annotated_image(
    image_bgr: np.ndarray,
    results: list[CrossingResult],
    zone: dict,
    out_dir: str,
) -> None:
    """Draw crossing zone, rider boxes, and number labels; write annotated.jpg.

    Zone drawing:
      - Polygon zone: draws the polygon outline.
      - Band zone (default): draws a horizontal band from y_min to the bottom.

    Box / label coloring:
      - green  → confident
      - amber  → needs_review
      - red    → rejected

    Args:
        image_bgr: Full input image (OpenCV BGR) — NOT modified in-place.
        results:   List of CrossingResult from pipeline.run().
        zone:      Resolved zone dict from zones.resolve_zone().
        out_dir:   Output directory. Writes to <out_dir>/annotated.jpg.
    """
    os.makedirs(out_dir, exist_ok=True)
    canvas = image_bgr.copy()
    img_h, img_w = canvas.shape[:2]

    # --- Draw the crossing zone ---
    if zone is not None:
        overlay = canvas.copy()
        if "polygon" in zone:
            pts = np.array(zone["polygon"], dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(overlay, [pts], _ZONE_COLOR)
            cv2.polylines(canvas, [pts], isClosed=True, color=_ZONE_COLOR, thickness=2)
        elif "y_min" in zone:
            y_min = int(zone["y_min"])
            cv2.rectangle(overlay, (0, y_min), (img_w, img_h), _ZONE_COLOR, thickness=-1)
            cv2.line(canvas, (0, y_min), (img_w, y_min), _ZONE_COLOR, thickness=2)
        # Blend the semi-transparent fill
        cv2.addWeighted(overlay, _ZONE_ALPHA, canvas, 1 - _ZONE_ALPHA, 0, canvas)

    # --- Draw each rider box and label ---
    for result in results:
        color = _STATUS_COLOR.get(result.status, _DEFAULT_COLOR)
        x1, y1, x2, y2 = result.rider_box
        ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)

        cv2.rectangle(canvas, (ix1, iy1), (ix2, iy2), color, _BOX_THICKNESS)

        # Label: "101 (confident)" or "unknown (rejected)"
        number_label = result.number if result.number is not None else "unknown"
        label_text = f"{number_label} ({result.status})"

        # Place label just above the top of the box; drop below if too close to edge.
        (text_w, text_h), baseline = cv2.getTextSize(
            label_text, _FONT, _FONT_SCALE, _FONT_THICKNESS
        )
        label_y = iy1 - 6
        if label_y - text_h < 0:
            label_y = iy2 + text_h + 6

        # Black background rectangle for readability.
        bg_x1 = ix1
        bg_y1 = label_y - text_h - baseline
        bg_x2 = ix1 + text_w + 4
        bg_y2 = label_y + baseline
        cv2.rectangle(canvas, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), thickness=-1)

        cv2.putText(
            canvas, label_text,
            (ix1 + 2, label_y),
            _FONT, _FONT_SCALE, color, _FONT_THICKNESS, lineType=cv2.LINE_AA,
        )

    out_path = os.path.join(out_dir, "annotated.jpg")
    cv2.imwrite(out_path, canvas)


def write_json(results: list[CrossingResult], out_dir: str) -> None:
    """Serialize results to <out_dir>/results.json.

    Each CrossingResult is converted to a dict matching design §5:
      {"number", "confidence", "status", "rider_box", "raw_text", "crop"}

    The "crop" key uses the crop_path field (set by write_crops).

    Args:
        results: List of CrossingResult instances — crop_path should already be set.
        out_dir: Output directory. Writes to <out_dir>/results.json.
    """
    os.makedirs(out_dir, exist_ok=True)

    records = []
    for r in results:
        d = dataclasses.asdict(r)
        # Rename crop_path -> crop to match design §5 JSON schema.
        d["crop"] = d.pop("crop_path")
        records.append(d)

    out_path = os.path.join(out_dir, "results.json")
    with open(out_path, "w") as fh:
        json.dump(records, fh, indent=2)
