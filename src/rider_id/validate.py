"""
Roster validation for OCR results.

Implements:
  load_roster(cfg) -> set[str] | None
  validate(ocr_results, roster, cfg) -> (number | None, raw_text | None, conf)

Leading-zero policy
-------------------
When cfg["validate"]["leading_zeros"] is False, any candidate whose digit string
starts with "0" AND has more than one digit is *rejected outright* (e.g. "007" → rejected).
A single digit "0" would be accepted if it falls within [min_digits, max_digits]
and the roster contains "0". This matches the confirmed domain rule (§12 D2):
"1–3 digits, black on white, no leading zeros."

Snap-penalty
------------
When a roster snap is needed (edit-distance ≥ 1), a flat penalty of
SNAP_PENALTY = 0.05 is subtracted from the raw OCR confidence before returning.
The penalty is clamped to [0.0, 1.0]. This deliberately keeps low-confidence
snaps below the confidence_threshold so they reach "needs_review" rather than
being silently accepted.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from .types import OcrResult

# Flat confidence penalty applied whenever edit-distance snapping was used.
SNAP_PENALTY = 0.05


# ---------------------------------------------------------------------------
# Levenshtein distance (pure Python; no external dependency required)
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings."""
    m, n = len(a), len(b)
    # Use a single row DP (O(n) space).
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_roster(cfg: dict) -> set[str] | None:
    """Load the rider roster from the file specified in config.

    Reads cfg["validate"]["roster"] as a filesystem path (relative paths are
    resolved against the current working directory, which should be the project
    root when run via run_poc.py or pytest from the project root).

    Returns:
        Set of valid number strings (stripped, one per line), or None if the
        config key is absent/null or the file cannot be found.
    """
    validate_cfg: dict = cfg.get("validate", {})
    roster_path = validate_cfg.get("roster")
    if not roster_path:
        return None

    path = Path(roster_path)
    if not path.is_file():
        return None

    numbers: set[str] = set()
    with path.open("r") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                numbers.add(stripped)
    return numbers if numbers else None


def validate(
    ocr_results: list[OcrResult],
    roster: set[str] | None,
    cfg: dict,
) -> tuple[str | None, str | None, float]:
    """Validate OCR results against the roster and return the best match.

    Algorithm:
      1. For each OcrResult, extract the digit string (strip all non-digit chars).
      2. Apply digit-count and leading-zero filters from cfg["validate"].
      3. Pick the best surviving candidate: highest ocr_conf; ties broken by
         longest digit string (more digits = more specific).
      4. If roster is not None, perform roster matching:
           a. Exact match → accept as-is.
           b. Find nearest roster entry by Levenshtein distance. If exactly one
              entry achieves the minimum distance and that distance is ≤
              max_edit_distance → snap to it, apply SNAP_PENALTY.
           c. Otherwise (ambiguous or no entry within budget) → reject.
      5. If roster is None, accept the candidate directly (confidence-only mode).

    Returns:
        (number, raw_text, confidence) where:
          number    — validated string, or None if rejected
          raw_text  — original OcrResult.text for the chosen candidate
          confidence — ocr_conf of chosen candidate, minus SNAP_PENALTY if snapped
    """
    validate_cfg: dict = cfg.get("validate", {})
    min_digits: int = validate_cfg.get("min_digits", 1)
    max_digits: int = validate_cfg.get("max_digits", 3)
    allow_leading_zeros: bool = validate_cfg.get("leading_zeros", False)
    max_edit_distance: int = validate_cfg.get("max_edit_distance", 1)

    # ------------------------------------------------------------------
    # Step 1-2: Extract and filter candidates
    # ------------------------------------------------------------------
    # Each candidate: (digit_string, raw_ocr_text, ocr_conf)
    candidates: list[tuple[str, str, float]] = []
    for result in ocr_results:
        digits = re.sub(r"[^0-9]", "", result.text)
        if not digits:
            continue
        # Digit count filter
        if not (min_digits <= len(digits) <= max_digits):
            continue
        # Leading-zero filter
        if not allow_leading_zeros and len(digits) > 1 and digits[0] == "0":
            continue
        candidates.append((digits, result.text, result.ocr_conf))

    if not candidates:
        return (None, None, 0.0)

    # ------------------------------------------------------------------
    # Step 3: Pick best candidate (highest ocr_conf; tie-break: longest)
    # ------------------------------------------------------------------
    best_digits, best_raw, best_conf = max(
        candidates,
        key=lambda c: (c[2], len(c[0])),
    )

    # ------------------------------------------------------------------
    # Step 4: Roster matching
    # ------------------------------------------------------------------
    if roster is None:
        # No roster — accept on confidence alone
        return (best_digits, best_raw, best_conf)

    # 4a. Exact match
    if best_digits in roster:
        return (best_digits, best_raw, best_conf)

    # 4b. Nearest-neighbour search within edit budget
    min_dist = max_edit_distance + 1  # sentinel: above budget
    nearest: list[str] = []

    for roster_entry in roster:
        dist = _levenshtein(best_digits, roster_entry)
        if dist < min_dist:
            min_dist = dist
            nearest = [roster_entry]
        elif dist == min_dist:
            nearest.append(roster_entry)

    # Accept only if there is exactly one nearest entry within budget
    if min_dist <= max_edit_distance and len(nearest) == 1:
        snapped_number = nearest[0]
        penalized_conf = max(0.0, best_conf - SNAP_PENALTY)
        return (snapped_number, best_raw, penalized_conf)

    # 4c. Ambiguous or no match within budget → reject
    return (None, best_raw, best_conf)
