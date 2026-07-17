"""
Rider detector — Ultralytics YOLO person detection.
This module is swappable (AGPL boundary — see design §4).

The YOLO model is loaded once as a module-level lazy singleton; subsequent calls
to detect_riders() reuse the cached model without reloading weights.
"""
from __future__ import annotations

import numpy as np
from ultralytics import YOLO

from .types import RiderBox

# COCO class index for "person"
_COCO_PERSON = 0

# Module-level model cache: (weights_path -> YOLO instance)
_model_cache: dict[str, YOLO] = {}


def _get_model(weights: str) -> YOLO:
    """Return a cached YOLO model, loading it on first use."""
    if weights not in _model_cache:
        model = YOLO(weights)
        _model_cache[weights] = model
    return _model_cache[weights]


def detect_riders(image_bgr: np.ndarray, cfg: dict) -> list[RiderBox]:
    """Detect riders in a BGR image using YOLO person detection.

    Loads the model from cfg["detector"]["weights"] (auto-downloads on first run).
    Only COCO class 'person' detections with confidence >= cfg["detector"]["person_conf"]
    are returned. Runs CPU-only.

    Args:
        image_bgr: Full input image as an OpenCV BGR np.ndarray.
        cfg: Parsed config dict; uses cfg["detector"]["weights"] and
             cfg["detector"]["person_conf"].

    Returns:
        List of RiderBox instances, one per detected person, with absolute pixel
        xyxy coordinates (floats) in the full input image.
    """
    weights: str = cfg["detector"]["weights"]
    person_conf: float = float(cfg["detector"]["person_conf"])

    model = _get_model(weights)

    # Run inference: CPU-only, restrict to person class, apply confidence threshold.
    results = model(
        image_bgr,
        classes=[_COCO_PERSON],
        conf=person_conf,
        device="cpu",
        verbose=False,
    )

    boxes: list[RiderBox] = []
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            boxes.append(RiderBox(xyxy=(x1, y1, x2, y2), det_conf=conf))

    return boxes
