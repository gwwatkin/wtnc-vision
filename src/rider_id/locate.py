"""
Number-region locator — Task 3.

Crops the lower-back sub-region of a rider box where the number panel sits.
"""
import numpy as np
from .types import RiderBox

# Minimum band height in pixels below which we fall back to the full box crop.
_MIN_BAND_HEIGHT = 4


def number_region(image_bgr: np.ndarray, box: RiderBox, cfg: dict) -> np.ndarray:
    """Crop the lower-back number-panel region from a rider box.

    Takes the vertical band defined by ``cfg["locate"]["back_band"]`` within the
    rider bounding box.  This narrows OCR to where the number panel is and avoids
    sponsor logos on helmets, collars, and frame numbers.

    Width strategy: the full box width is used (no arm-trimming). Race number
    panels are pinned to the *centre* of the lower back, so arm-trimming would
    need to be tuned per-event and risks clipping the panel edge; the OCR model
    deals comfortably with the arms visible alongside the panel.

    Args:
        image_bgr: Full input image as an OpenCV BGR ``np.ndarray``.
        box: :class:`RiderBox` with ``xyxy`` in absolute pixel coords of the
             full image (floats).
        cfg: Parsed config dict; uses ``cfg["locate"]["back_band"]`` — a
             ``[top_frac, bottom_frac]`` pair defining the vertical slice of the
             rider box to crop (e.g. ``[0.45, 0.85]``).

    Returns:
        BGR crop (``np.ndarray``) of the lower-back number-panel region.  Falls
        back to the whole box crop if the requested band is degenerate (< a few
        pixels tall after clamping).
    """
    img_h, img_w = image_bgr.shape[:2]

    x1f, y1f, x2f, y2f = box.xyxy
    # Convert to integers, keeping x1 < x2 and y1 < y2.
    bx1 = int(round(min(x1f, x2f)))
    bx2 = int(round(max(x1f, x2f)))
    by1 = int(round(min(y1f, y2f)))
    by2 = int(round(max(y1f, y2f)))

    box_height = by2 - by1

    # Fallback: if the box itself is degenerate, return whatever we can crop.
    if box_height < _MIN_BAND_HEIGHT or bx2 <= bx1:
        cx1 = max(0, bx1)
        cy1 = max(0, by1)
        cx2 = min(img_w, bx2)
        cy2 = min(img_h, by2)
        if cx2 <= cx1 or cy2 <= cy1:
            # Completely out of bounds — return a 1x1 black pixel rather than error.
            return np.zeros((1, 1, 3), dtype=np.uint8)
        return image_bgr[cy1:cy2, cx1:cx2].copy()

    back_band: list[float] = cfg["locate"]["back_band"]
    top_frac, bot_frac = float(back_band[0]), float(back_band[1])

    band_y1 = int(round(by1 + top_frac * box_height))
    band_y2 = int(round(by1 + bot_frac * box_height))

    # Clamp to image bounds.
    band_y1 = max(0, min(band_y1, img_h))
    band_y2 = max(0, min(band_y2, img_h))
    cx1 = max(0, bx1)
    cx2 = min(img_w, bx2)

    band_height = band_y2 - band_y1

    # Fallback: if the computed band is too small, return the full (clamped) box.
    if band_height < _MIN_BAND_HEIGHT or cx2 <= cx1:
        full_y1 = max(0, by1)
        full_y2 = min(img_h, by2)
        if full_y2 <= full_y1 or cx2 <= cx1:
            return np.zeros((1, 1, 3), dtype=np.uint8)
        return image_bgr[full_y1:full_y2, cx1:cx2].copy()

    return image_bgr[band_y1:band_y2, cx1:cx2].copy()
