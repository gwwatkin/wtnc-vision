"""
Confidence scorer for validated rider-number reads.

Implements:
  classify(number, confidence, cfg) -> str

Returns one of:
  "rejected"     — number is None (validation rejected the read)
  "confident"    — number is not None AND confidence >= confidence_threshold
  "needs_review" — number is not None AND confidence <  confidence_threshold
"""


def classify(number: str | None, confidence: float, cfg: dict) -> str:
    """Classify a validated read into a status string.

    Args:
        number:     Validated number string, or None if validation rejected.
        confidence: Combined confidence score 0..1 from validate().
        cfg:        Parsed config dict; uses cfg["score"]["confidence_threshold"].

    Returns:
        "rejected"     if number is None
        "confident"    if confidence >= confidence_threshold
        "needs_review" otherwise
    """
    if number is None:
        return "rejected"

    threshold: float = cfg.get("score", {}).get("confidence_threshold", 0.60)
    return "confident" if confidence >= threshold else "needs_review"
