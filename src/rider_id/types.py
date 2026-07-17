"""
FROZEN CONTRACT — do not change these dataclasses.
All modules and downstream tasks depend on these exact definitions.
"""
from dataclasses import dataclass


@dataclass
class RiderBox:
    xyxy: tuple[float, float, float, float]   # x1,y1,x2,y2 absolute px in full image
    det_conf: float


@dataclass
class OcrResult:
    text: str                                 # raw recognized string
    ocr_conf: float                           # 0..1
    box: tuple[float, float, float, float]    # x1,y1,x2,y2 relative to the crop given


@dataclass
class CrossingResult:
    number: str | None        # validated roster number, or None if rejected
    raw_text: str | None      # OCR text before validation (for review)
    confidence: float         # final 0..1
    status: str               # "confident" | "needs_review" | "rejected"
    rider_box: tuple[float, float, float, float]
    crop_path: str | None
