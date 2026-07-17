"""
OCR module — Task 3.

Reads text from a number-panel crop using the engine selected by
``cfg["ocr"]["engine"]``.  Engines implemented:

  * ``"paddleocr"`` (default) — PaddleOCR v3 (PP-OCRv6).  Handles the tilt of
    a pinned cloth panel via ``use_textline_orientation``.  Loaded once as a
    module-level singleton; CPU-only.

  * ``"easyocr"`` — EasyOCR fallback for task-6 comparison.  Also singleton,
    CPU-only.  Requires ``easyocr`` to be installed (``pip install easyocr``);
    if the package is absent the call raises ``ImportError`` with a clear
    message.

Returns raw reads with no numeric filtering — that is task 4's job.
``OcrResult.box`` is in ``(x1, y1, x2, y2)`` coords *relative to the crop*.

Runtime note
------------
PaddleOCR v3 (paddlepaddle 3.3+) uses the oneDNN backend by default on CPU,
which currently has an unimplemented pass for the PP-OCRv6 models on non-Intel
AVX512 hardware.  We disable the oneDNN backend by setting the paddlex flag
``PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=0`` via ``os.environ`` before the first
``paddleocr`` import.  The flag must be set before the import; this module sets
it unconditionally at module load time (setting it to "0" when oneDNN is already
disabled is a no-op).
"""

import os

# Must be set before paddleocr / paddlex are imported.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

import cv2
import numpy as np

from .types import OcrResult

# Minimum short-side resolution before we upscale the crop.
# PaddleOCR v3 (PP-OCRv6) fails to detect text reliably on very small crops;
# upscaling to at least this many pixels on the short side restores accuracy.
_MIN_SHORT_SIDE = 160

# ---------------------------------------------------------------------------
# Module-level singletons — loaded once on first use.
# ---------------------------------------------------------------------------
_paddle_ocr = None       # PaddleOCR instance
_easyocr_reader = None   # easyocr.Reader instance


def _get_paddle_ocr(use_textline_orientation: bool):
    """Return (and lazily initialise) the PaddleOCR singleton."""
    global _paddle_ocr
    if _paddle_ocr is None:
        from paddleocr import PaddleOCR  # noqa: PLC0415

        _paddle_ocr = PaddleOCR(
            # Angle classifier handles tilted number panels (design §2).
            use_textline_orientation=use_textline_orientation,
            # Skip heavy document-level pre-processors that are not needed and
            # currently trigger a Paddle/oneDNN incompatibility.
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            lang="en",
            # Return all detections; task 4 applies confidence gating.
            text_rec_score_thresh=0.0,
        )
    return _paddle_ocr


def _get_easyocr_reader():
    """Return (and lazily initialise) the EasyOCR singleton."""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "The 'easyocr' engine was requested but the package is not "
                "installed.  Install it with:  pip install easyocr"
            ) from exc

        # gpu=False — CPU-only per design §11.
        _easyocr_reader = easyocr.Reader(["en"], gpu=False)
    return _easyocr_reader


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_number(crop_bgr: np.ndarray, cfg: dict) -> list[OcrResult]:
    """Run OCR on a number-panel crop and return candidate text results.

    Uses the engine specified in ``cfg["ocr"]["engine"]`` (default:
    ``"paddleocr"``).

    PaddleOCR runs text detection + optional textline-orientation classification
    + recognition, which handles the tilt of a pinned cloth panel (design §2).

    No numeric filtering is applied here — that is task 4's job.  Sponsor logo
    text and other non-number strings will appear in the returned list.

    Args:
        crop_bgr: BGR crop of the lower-back number-panel region
                  (``np.ndarray``), as returned by
                  :func:`locate.number_region`.
        cfg: Parsed config dict; uses:

             * ``cfg["ocr"]["engine"]`` — ``"paddleocr"`` | ``"easyocr"``
             * ``cfg["ocr"]["use_angle_cls"]`` — whether to enable the
               textline-orientation classifier (``bool``).

    Returns:
        List of :class:`OcrResult`.  Each result's ``box`` is
        ``(x1, y1, x2, y2)`` **relative to the crop** (not the full image).
        Returns an empty list when no text is detected.
    """
    engine: str = cfg["ocr"].get("engine", "paddleocr").lower()
    use_angle_cls: bool = bool(cfg["ocr"].get("use_angle_cls", True))

    # Upscale small crops so the OCR model can detect text reliably.
    # PaddleOCR v3 (PP-OCRv6) struggles on crops shorter than ~160px.
    # We scale uniformly to bring the short side up to _MIN_SHORT_SIDE while
    # preserving aspect ratio; this is transparent to the caller since returned
    # OcrResult.box coordinates are mapped back to the original crop space.
    h, w = crop_bgr.shape[:2]
    short_side = min(h, w)
    if short_side < _MIN_SHORT_SIDE:
        scale = _MIN_SHORT_SIDE / short_side
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        crop_for_ocr = cv2.resize(
            crop_bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4
        )
    else:
        scale = 1.0
        crop_for_ocr = crop_bgr

    if engine == "paddleocr":
        raw_results = _run_paddleocr(crop_for_ocr, use_angle_cls)
    elif engine == "easyocr":
        raw_results = _run_easyocr(crop_for_ocr)
    else:
        raise ValueError(
            f"Unknown OCR engine {engine!r}.  Supported: 'paddleocr', 'easyocr'."
        )

    # Map box coordinates back to the original (pre-upscale) crop space.
    if scale != 1.0:
        return [
            OcrResult(
                text=r.text,
                ocr_conf=r.ocr_conf,
                box=(
                    r.box[0] / scale,
                    r.box[1] / scale,
                    r.box[2] / scale,
                    r.box[3] / scale,
                ),
            )
            for r in raw_results
        ]
    return raw_results


# ---------------------------------------------------------------------------
# Engine implementations
# ---------------------------------------------------------------------------

def _run_paddleocr(crop_bgr: np.ndarray, use_textline_orientation: bool) -> list[OcrResult]:
    """PaddleOCR implementation (PP-OCRv6, CPU)."""
    ocr = _get_paddle_ocr(use_textline_orientation)

    # ``predict`` returns a list with one result dict per image.
    raw = ocr.predict(crop_bgr)
    if not raw:
        return []

    result_dict = raw[0]
    texts = result_dict.get("rec_texts", [])
    scores = result_dict.get("rec_scores", [])
    # ``rec_boxes`` are xyxy arrays relative to the input image (here = the crop).
    boxes = result_dict.get("rec_boxes", [])

    out: list[OcrResult] = []
    for text, score, box in zip(texts, scores, boxes):
        # ``box`` may be a numpy array [x1, y1, x2, y2].
        x1, y1, x2, y2 = (float(v) for v in box)
        out.append(OcrResult(
            text=str(text),
            ocr_conf=float(score),
            box=(x1, y1, x2, y2),
        ))
    return out


def _run_easyocr(crop_bgr: np.ndarray) -> list[OcrResult]:
    """EasyOCR implementation (CPU).

    EasyOCR returns a list of ``([tl, tr, br, bl], text, conf)`` tuples.
    We convert the four-corner polygon to an axis-aligned ``(x1,y1,x2,y2)``
    box to match the :class:`OcrResult` contract.
    """
    reader = _get_easyocr_reader()

    # ``detail=1`` returns bounding boxes; ``paragraph=False`` keeps individual
    # text lines (preferred for number panels with a single number per line).
    raw = reader.readtext(crop_bgr, detail=1, paragraph=False)

    out: list[OcrResult] = []
    for (polygon, text, conf) in raw:
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        out.append(OcrResult(
            text=str(text),
            ocr_conf=float(conf),
            box=(float(x1), float(y1), float(x2), float(y2)),
        ))
    return out
