#!/usr/bin/env python3
"""
CLI entrypoint for the rider-number recognition POC.

Usage:
    python run_poc.py <image_path> [--config config.yaml]

Loads config, reads the image with OpenCV, calls pipeline.run(), then writes
the three output artifacts (crops, annotated image, results.json) to out/.
Prints a one-line summary per result to stdout.
"""
import argparse
import os
import sys

import cv2

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rider_id.config import load_config
from rider_id import pipeline, zones
from rider_id.io_out import write_crops, write_annotated_image, write_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rider number recognition POC — processes a single still image."
    )
    parser.add_argument(
        "image_path",
        help="Path to the input image (e.g. ridersFromThBack.jpg)",
    )
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(__file__), "config.yaml"),
        help="Path to config.yaml (default: config.yaml next to this script)",
    )
    args = parser.parse_args()

    # Load config
    cfg = load_config(args.config)

    # Read image
    image_bgr = cv2.imread(args.image_path)
    if image_bgr is None:
        print(f"ERROR: could not read image: {args.image_path}", file=sys.stderr)
        sys.exit(1)

    # Run pipeline (stages 1-6; outputs handled below)
    results = pipeline.run(image_bgr, cfg)

    # Resolve output directory
    out_dir = cfg.get("output", {}).get("dir", "out/")
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # Resolve the crossing zone for annotation (same logic as pipeline.run)
    frame_height = image_bgr.shape[0]
    raw_zone = zones.load_zone(cfg)
    resolved_zone = zones.resolve_zone(raw_zone, frame_height)

    # Stage 7 outputs — order matters: crops first so crop_path is set before JSON
    write_crops(image_bgr, results, out_dir)
    write_annotated_image(image_bgr, results, resolved_zone, out_dir)
    write_json(results, out_dir)

    # Print one-line summary per result
    for r in results:
        number_label = r.number if r.number is not None else "unknown"
        raw = r.raw_text if r.raw_text is not None else "(no read)"
        print(
            f"  [{r.status}] number={number_label!r}  "
            f"conf={r.confidence:.3f}  raw={raw!r}  crop={r.crop_path}"
        )

    print(
        f"\nWrote {len(results)} result(s) to {out_dir}  "
        f"(results.json, annotated.jpg, crops/)"
    )


if __name__ == "__main__":
    main()
