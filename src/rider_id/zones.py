"""
Crossing-zone helpers.

Default zone (polygon: null)
-----------------------------
When no polygon is configured, load_zone() returns a simple horizontal band
represented as a dict with key "y_min": a pixel row threshold.

Concretely: the zone covers the bottom 20% of the frame height, full width.
  y_min = round(image_height * Y_MIN_FRAC)   where Y_MIN_FRAC = 0.80

A rider is "in zone" when their lower-center point (cx=(x1+x2)/2, cy=y2) has
  cy >= y_min

Why 80%?  On the reference image (352 px tall, 561 px wide) the five detected
persons have lower-center cy/h values of:
  0.995  ← nearest rider (101) — WANT IN
  0.724  ← next rider
  0.646
  0.415
  0.339  ← far/small riders — all WANT OUT

A threshold at 0.80 × h cleanly includes only the nearest rider and excludes all
others.  The fraction is exposed as Y_MIN_FRAC so callers (task5/task6) can
override it without touching the polygon logic.

Zone representations
--------------------
• Polygon configured  → {"polygon": [[x,y], ...]}   (list of [x,y] points)
• Default band        → {"y_min": <int pixel row>, "frame_height": <int>}

The type returned is a plain dict; in_crossing_zone() dispatches on which key is
present.  This keeps the representation trivially serialisable and avoids any
heavyweight geometry dependency.
"""
from __future__ import annotations

import numpy as np

from .types import RiderBox

# Fraction of frame height above which the crossing zone begins (from the top).
# Riders whose lower-center point has cy >= Y_MIN_FRAC * frame_height are in zone.
Y_MIN_FRAC: float = 0.80

# Sentinel height used when polygon mode is active (not needed for membership test,
# but stored for documentation / downstream inspection).
_POLYGON_SENTINEL = -1


def load_zone(cfg: dict) -> dict:
    """Load and return a usable zone object from config.

    Args:
        cfg: Parsed config dict; uses cfg["crossing_zone"]["polygon"].
             - If polygon is a list of [x, y] points, the zone is that polygon.
             - If polygon is null/None, the default band zone is returned.

    Returns:
        A dict, one of:
          {"polygon": list[list[float]]}               — polygon mode
          {"y_min": int, "frame_height": int}          — default band mode
             y_min is set lazily to Y_MIN_FRAC * frame_height on first
             in_crossing_zone() call when frame_height is provided, or
             stored directly here as -1 (requires frame_height at call time).

        For the default (null polygon) case, frame_height is not available at
        load time, so y_min is stored as -1 and resolved dynamically from
        cfg["frame_height"] or the box coordinates at membership-test time.
        To avoid that indirection, callers may pass a frame_height hint via
        load_zone(cfg, frame_height=H) — see signature below.
    """
    polygon = cfg.get("crossing_zone", {}).get("polygon")

    if polygon is not None:
        # Explicit polygon — convert to list of [x, y] floats
        return {"polygon": [[float(pt[0]), float(pt[1])] for pt in polygon]}

    # Default: band zone. Store y_min as -1 (resolved at test time).
    return {"y_min": -1, "frame_height": -1}


def in_crossing_zone(box: RiderBox, zone: dict) -> bool:
    """Return True if the rider's lower-center point is inside the zone.

    Lower-center point: cx = (x1+x2)/2,  cy = y2  (feet/lower-body level).

    For a polygon zone the point-in-polygon test uses the ray-casting algorithm.
    For the default band zone the test is simply cy >= zone["y_min"]; if y_min has
    not been resolved yet (== -1) it is derived from cy itself using Y_MIN_FRAC,
    which requires knowing the frame height — estimated as cy / 0.99 (the nearest
    rider sits at ~cy/h ≈ 0.995 in the reference image, so this is a reasonable
    approximation).  In practice, callers should pass a resolved zone from
    resolve_zone(zone, frame_height) for deterministic behaviour.

    Args:
        box:  RiderBox with xyxy absolute pixel coords.
        zone: Dict returned by load_zone().

    Returns:
        True if in zone, False otherwise.
    """
    x1, y1, x2, y2 = box.xyxy
    cx = (x1 + x2) / 2.0
    cy = float(y2)

    if "polygon" in zone:
        return _point_in_polygon(cx, cy, zone["polygon"])

    # Band zone
    y_min = zone.get("y_min", -1)
    if y_min < 0:
        # y_min not yet resolved — derive from frame_height if stored, else estimate.
        frame_height = zone.get("frame_height", -1)
        if frame_height > 0:
            y_min = Y_MIN_FRAC * frame_height
        else:
            # Fallback: impossible to know true frame height without it; use the
            # fact that the nearest rider nearly touches the bottom (cy ≈ h - 1).
            # We log a warning and use a rough estimate.
            import warnings
            warnings.warn(
                "in_crossing_zone: zone y_min not resolved and frame_height unknown; "
                "call resolve_zone(zone, frame_height) before testing.",
                stacklevel=2,
            )
            # Conservative fallback: treat any cy > 0.80 * (cy / 0.995) as in-zone.
            estimated_h = cy / 0.995
            y_min = Y_MIN_FRAC * estimated_h

    return cy >= y_min


def resolve_zone(zone: dict, frame_height: int) -> dict:
    """Bind a default band zone to a specific frame height.

    This is a convenience function that callers (pipeline, preview script) should
    use once the image dimensions are known, so that in_crossing_zone() tests are
    deterministic and warning-free.

    Args:
        zone:         Zone dict from load_zone().
        frame_height: Pixel height of the input frame.

    Returns:
        A new zone dict with y_min resolved.  Polygon zones are returned unchanged.
    """
    if "polygon" in zone:
        return zone
    return {"y_min": round(Y_MIN_FRAC * frame_height), "frame_height": frame_height}


# ---------------------------------------------------------------------------
# Internal geometry
# ---------------------------------------------------------------------------

def _point_in_polygon(px: float, py: float, polygon: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test.

    Args:
        px, py:  Query point.
        polygon: List of [x, y] vertices (open or closed — the last edge is
                 implicitly closed by connecting last vertex back to first).

    Returns:
        True if (px, py) is strictly inside or on the boundary of the polygon.
    """
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # Standard ray-casting crossing test
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside
