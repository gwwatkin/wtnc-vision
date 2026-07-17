"""
Throwaway preview script for task2 verification.
Draws all detected rider boxes and the crossing zone on the image, colours boxes
green (in-zone) or red (out-of-zone), and saves to out/preview_detect.png.

Usage:
    source .venv/bin/activate
    python scripts/preview_detect.py [image_path]
"""
from __future__ import annotations

import sys
import os

# Make the src package importable when run from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
import yaml

from rider_id.detector import detect_riders
from rider_id.zones import load_zone, resolve_zone, in_crossing_zone, Y_MIN_FRAC

# ------------------------------------------------------------------
IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "ridersFromThBack.jpg")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "out", "preview_detect.png")
# ------------------------------------------------------------------

if len(sys.argv) > 1:
    IMAGE_PATH = sys.argv[1]

with open(CONFIG_PATH) as f:
    cfg = yaml.safe_load(f)

img = cv2.imread(IMAGE_PATH)
if img is None:
    sys.exit(f"Cannot read image: {IMAGE_PATH}")

h, w = img.shape[:2]
print(f"Image: {w}x{h}")

# --- detect ---
boxes = detect_riders(img, cfg)
print(f"Detected {len(boxes)} riders")

# --- zone ---
zone = load_zone(cfg)
zone = resolve_zone(zone, h)
print(f"Zone: {zone}")

# --- draw zone ---
canvas = img.copy()
if "y_min" in zone:
    y_min = zone["y_min"]
    # Semi-transparent fill for the crossing zone band
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, y_min), (w, h), (0, 200, 0), -1)
    cv2.addWeighted(overlay, 0.15, canvas, 0.85, 0, canvas)
    cv2.line(canvas, (0, y_min), (w, y_min), (0, 220, 0), 2)
    label = f"Crossing zone: y >= {y_min}px ({Y_MIN_FRAC*100:.0f}% of {h}px)"
    cv2.putText(canvas, label, (4, y_min - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (0, 220, 0), 1, cv2.LINE_AA)
elif "polygon" in zone:
    pts = [[int(p[0]), int(p[1])] for p in zone["polygon"]]
    import numpy as np
    overlay = canvas.copy()
    cv2.fillPoly(overlay, [np.array(pts)], (0, 200, 0))
    cv2.addWeighted(overlay, 0.15, canvas, 0.85, 0, canvas)
    cv2.polylines(canvas, [np.array(pts)], True, (0, 220, 0), 2)

# --- draw boxes ---
for i, box in enumerate(sorted(boxes, key=lambda b: (b.xyxy[2]-b.xyxy[0])*(b.xyxy[3]-b.xyxy[1]), reverse=True)):
    x1, y1, x2, y2 = [int(v) for v in box.xyxy]
    cx = int((x1 + x2) / 2)
    cy = int(y2)
    in_zone = in_crossing_zone(box, zone)
    color = (0, 255, 0) if in_zone else (0, 0, 255)
    label = f"#{i} {box.det_conf:.2f} {'IN' if in_zone else 'OUT'}"
    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
    cv2.circle(canvas, (cx, cy), 5, color, -1)
    cv2.putText(canvas, label, (x1, max(y1 - 6, 10)), cv2.FONT_HERSHEY_SIMPLEX,
                0.40, color, 1, cv2.LINE_AA)
    print(f"  [{i}] conf={box.det_conf:.2f} xyxy=({box.xyxy[0]:.0f},{box.xyxy[1]:.0f},"
          f"{box.xyxy[2]:.0f},{box.xyxy[3]:.0f}) lower-center=({cx},{cy}) "
          f"cy/h={cy/h:.3f} -> {'IN ZONE' if in_zone else 'out of zone'}")

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
cv2.imwrite(OUT_PATH, canvas)
print(f"\nSaved preview to: {OUT_PATH}")
