"""
Unit tests for validate.py and score.py (Task 4).

All tests are self-contained: OcrResult instances are constructed directly —
no real OCR, no detector, no image I/O.

Edit-distance reasoning
-----------------------
We use our own pure-Python Levenshtein implementation (no external library).
Distance between two strings = minimum insertions + deletions + substitutions
needed to turn one into the other.

Snap test ("102" vs roster {"101","150","200"})
  lev("102", "101") = 1  ← single substitution at position 2 (2→1)
  lev("102", "150") = 2
  lev("102", "200") = 3
  Unique nearest: "101" at distance 1, which is ≤ max_edit_distance (1).
  → snaps to "101"; raw_text stays "102"; conf penalized by SNAP_PENALTY (0.05).

Rejection test ("577" vs roster {"101","102","103"}, max_edit=1)
  lev("577", "101") = 3  (5→1, 7→0, 7→1)
  lev("577", "102") = 3
  lev("577", "103") = 3
  Minimum distance is 3, which exceeds max_edit_distance (1). → rejected.

Non-numeric test ("skyprocycling")
  After stripping non-digits: "" — zero digits. → no candidates. → (None,None,0.0).

Leading-zero test ("007")
  Digits = "007"; starts with "0" and len > 1; leading_zeros=False → rejected.

Ambiguous-snap test ("108" vs roster {"101","102","103"}, max_edit=1)
  lev("108","101")=1, lev("108","102")=1, lev("108","103")=1 — ALL tie at dist 1.
  Ambiguous (three nearest) → number=None (rejected).

No-roster test
  When roster=None, validate accepts any numeric candidate by confidence alone.
"""
import sys
import os

# Make the src package importable when running from the project root or tests/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from rider_id.types import OcrResult
from rider_id.validate import validate, load_roster, SNAP_PENALTY
from rider_id.score import classify

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

DUMMY_BOX = (0.0, 0.0, 100.0, 50.0)

# Minimal config that matches config.yaml defaults
BASE_CFG = {
    "validate": {
        "roster": None,          # overridden per-test where needed
        "min_digits": 1,
        "max_digits": 3,
        "leading_zeros": False,
        "max_edit_distance": 1,
    },
    "score": {
        "confidence_threshold": 0.60,
    },
}


def make_cfg(roster=None, max_edit_distance=1):
    """Return a copy of BASE_CFG with roster and max_edit_distance overridden."""
    cfg = {
        "validate": {**BASE_CFG["validate"], "roster": roster,
                     "max_edit_distance": max_edit_distance},
        "score": {**BASE_CFG["score"]},
    }
    return cfg


# ---------------------------------------------------------------------------
# Test 1: Exact match → confident
# ---------------------------------------------------------------------------

class TestExactMatch:
    """OcrResult("101", 0.94) with roster {"101","102","103"} → exact match."""

    def setup_method(self):
        self.roster = {"101", "102", "103"}
        self.cfg = make_cfg(roster=self.roster)
        self.results = [OcrResult(text="101", ocr_conf=0.94, box=DUMMY_BOX)]

    def test_validate_exact(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        assert number == "101"
        assert raw_text == "101"
        assert conf == pytest.approx(0.94)

    def test_classify_confident(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        status = classify(number, conf, self.cfg)
        assert status == "confident"


# ---------------------------------------------------------------------------
# Test 2: Near-miss snap (unique nearest) → snapped number, penalized conf
# ---------------------------------------------------------------------------

class TestSnapToNearestUnique:
    """
    OcrResult("102", 0.90) with roster {"101","150","200"}.
    lev("102","101")=1 — unique nearest within max_edit_distance=1.
    Snaps to "101"; raw_text="102"; conf = 0.90 - SNAP_PENALTY.
    """

    def setup_method(self):
        self.roster = {"101", "150", "200"}
        self.cfg = make_cfg(roster=self.roster)
        self.results = [OcrResult(text="102", ocr_conf=0.90, box=DUMMY_BOX)]

    def test_snaps_to_101(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        assert number == "101", f"Expected snap to '101', got {number!r}"

    def test_raw_text_is_original_ocr(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        assert raw_text == "102", (
            f"raw_text should be original OCR string '102', got {raw_text!r}"
        )

    def test_confidence_penalized(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        expected = pytest.approx(0.90 - SNAP_PENALTY)
        assert conf == expected, (
            f"conf should be 0.90 - {SNAP_PENALTY} = {0.90 - SNAP_PENALTY}, got {conf}"
        )

    def test_status_after_snap(self):
        """Penalized confidence (0.85) is still above threshold (0.60) → confident."""
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        status = classify(number, conf, self.cfg)
        assert status == "confident"


# ---------------------------------------------------------------------------
# Test 3: No roster match within edit budget → rejected
# ---------------------------------------------------------------------------

class TestNoMatchWithinBudget:
    """
    OcrResult("577", 0.90) with roster {"101","102","103"}, max_edit=1.
    lev("577","101")=3 — all roster entries at distance ≥ 3. Rejected.
    """

    def setup_method(self):
        self.roster = {"101", "102", "103"}
        self.cfg = make_cfg(roster=self.roster, max_edit_distance=1)
        self.results = [OcrResult(text="577", ocr_conf=0.90, box=DUMMY_BOX)]

    def test_number_is_none(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        assert number is None, f"Expected None (rejected), got {number!r}"

    def test_raw_text_preserved(self):
        """raw_text is preserved even on rejection so humans can review the read."""
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        assert raw_text == "577"

    def test_status_rejected(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        status = classify(number, conf, self.cfg)
        assert status == "rejected"


# ---------------------------------------------------------------------------
# Test 4: Non-numeric text → no candidates → rejected
# ---------------------------------------------------------------------------

class TestNonNumericText:
    """
    OcrResult("skyprocycling", 0.80) — stripping non-digits yields ""; zero candidates.
    Returns (None, None, 0.0).
    """

    def setup_method(self):
        self.roster = {"101", "102", "103"}
        self.cfg = make_cfg(roster=self.roster)
        self.results = [OcrResult(text="skyprocycling", ocr_conf=0.80, box=DUMMY_BOX)]

    def test_returns_none_tuple(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        assert number is None
        assert raw_text is None
        assert conf == 0.0

    def test_status_rejected(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        status = classify(number, conf, self.cfg)
        assert status == "rejected"


# ---------------------------------------------------------------------------
# Test 5: Leading-zero rejection (007-style)
# ---------------------------------------------------------------------------

class TestLeadingZeroRejection:
    """
    OcrResult("007", 0.95) — leading_zeros=False, len>1 starting with "0" → rejected.
    """

    def setup_method(self):
        self.roster = {"007", "101", "102"}   # "007" is in roster but should be filtered
        self.cfg = make_cfg(roster=self.roster)
        self.results = [OcrResult(text="007", ocr_conf=0.95, box=DUMMY_BOX)]

    def test_leading_zero_produces_no_candidate(self):
        """Leading-zero filter fires before roster lookup → no valid candidate."""
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        assert number is None
        assert raw_text is None
        assert conf == 0.0


# ---------------------------------------------------------------------------
# Test 6: Ambiguous snap (multiple nearest at same edit distance) → rejected
# ---------------------------------------------------------------------------

class TestAmbiguousSnap:
    """
    OcrResult("108", 0.90) with roster {"101","102","103"}, max_edit=1.
    lev("108","101")=1, lev("108","102")=1, lev("108","103")=1 — ambiguous.
    → number=None (rejected) because the nearest match is not unique.
    """

    def setup_method(self):
        self.roster = {"101", "102", "103"}
        self.cfg = make_cfg(roster=self.roster, max_edit_distance=1)
        self.results = [OcrResult(text="108", ocr_conf=0.90, box=DUMMY_BOX)]

    def test_ambiguous_snap_rejected(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        assert number is None, (
            "Ambiguous snap (3 equidistant roster entries) should be rejected"
        )

    def test_status_rejected(self):
        number, raw_text, conf = validate(self.results, self.roster, self.cfg)
        status = classify(number, conf, self.cfg)
        assert status == "rejected"


# ---------------------------------------------------------------------------
# Test 7: No roster → accept any valid numeric on confidence alone
# ---------------------------------------------------------------------------

class TestNoRoster:
    """When roster=None, validate accepts any valid numeric candidate."""

    def test_accepted_without_roster(self):
        cfg = make_cfg(roster=None)
        results = [OcrResult(text="999", ocr_conf=0.75, box=DUMMY_BOX)]
        number, raw_text, conf = validate(results, None, cfg)
        assert number == "999"
        assert conf == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Test 8: Best-candidate selection (highest conf wins)
# ---------------------------------------------------------------------------

class TestBestCandidateSelection:
    """When multiple OcrResult items are present, the one with highest ocr_conf wins."""

    def test_picks_highest_confidence(self):
        roster = {"101", "102"}
        cfg = make_cfg(roster=roster)
        results = [
            OcrResult(text="101", ocr_conf=0.70, box=DUMMY_BOX),
            OcrResult(text="102", ocr_conf=0.92, box=DUMMY_BOX),
        ]
        number, raw_text, conf = validate(results, roster, cfg)
        assert number == "102"
        assert conf == pytest.approx(0.92)


# ---------------------------------------------------------------------------
# Test 9: needs_review path — low confidence after snap
# ---------------------------------------------------------------------------

class TestNeedsReviewAfterSnap:
    """
    A snap that penalizes confidence below threshold → needs_review.
    Input conf 0.62, penalized to 0.57 (below 0.60 threshold).
    """

    def test_needs_review_when_penalized_below_threshold(self):
        roster = {"101", "150", "200"}
        cfg = make_cfg(roster=roster)
        # Starting conf 0.62; after SNAP_PENALTY (0.05) → 0.57 < 0.60 threshold
        results = [OcrResult(text="102", ocr_conf=0.62, box=DUMMY_BOX)]
        number, raw_text, conf = validate(results, roster, cfg)
        assert number == "101"
        assert conf == pytest.approx(0.62 - SNAP_PENALTY)
        status = classify(number, conf, cfg)
        assert status == "needs_review"


# ---------------------------------------------------------------------------
# Test 10: load_roster with actual roster.txt
# ---------------------------------------------------------------------------

class TestLoadRoster:
    """load_roster reads the actual roster.txt (101-199) from the project root."""

    def test_load_real_roster(self, tmp_path):
        """Write a small roster.txt and verify load_roster reads it correctly."""
        roster_file = tmp_path / "roster.txt"
        roster_file.write_text("101\n102\n103\n")
        cfg = {"validate": {"roster": str(roster_file)}}
        roster = load_roster(cfg)
        assert roster == {"101", "102", "103"}

    def test_load_roster_missing_path(self):
        """None path returns None."""
        cfg = {"validate": {"roster": None}}
        assert load_roster(cfg) is None

    def test_load_roster_nonexistent_file(self):
        """Non-existent file path returns None gracefully."""
        cfg = {"validate": {"roster": "/tmp/no_such_roster_file_12345.txt"}}
        assert load_roster(cfg) is None

    def test_load_roster_csv_format(self, tmp_path):
        """A number,name,category CSV (as written by the roster upload) works:
        first column is used, header row skipped, quoted fields tolerated."""
        roster_file = tmp_path / "roster.csv"
        roster_file.write_text(
            'number,name,category\n101,"Watkins, George",Cat 3\n545,Alice,Cat 1\n'
        )
        cfg = {"validate": {"roster": str(roster_file)}}
        assert load_roster(cfg) == {"101", "545"}

    def test_load_roster_csv_all_header_returns_none(self, tmp_path):
        """A file with no digit-first-column rows yields None (no roster)."""
        roster_file = tmp_path / "roster.csv"
        roster_file.write_text("number,name,category\n")
        cfg = {"validate": {"roster": str(roster_file)}}
        assert load_roster(cfg) is None


# ---------------------------------------------------------------------------
# Tests 11-14: accept_unmatched flag (design §6.1 note / task2)
# ---------------------------------------------------------------------------

def _make_cfg_unmatched(roster=None, accept_unmatched: bool = False, max_edit_distance: int = 1):
    """Build a cfg dict with accept_unmatched control."""
    return {
        "validate": {
            "roster": roster,
            "min_digits": 1,
            "max_digits": 3,
            "leading_zeros": False,
            "max_edit_distance": max_edit_distance,
            "accept_unmatched": accept_unmatched,
        },
        "score": {"confidence_threshold": 0.60},
    }


class TestAcceptUnmatchedFlag:
    """Design §6.1: accept_unmatched=true passes step-4c reads through as-is."""

    # Test 11: no match within budget, flag ON → accepted as-is, full confidence
    def test_no_match_within_budget_flag_on(self):
        """
        "577" vs roster {"101","102","103"}, max_edit=1.
        All distances ≥ 3 → step 4c; accept_unmatched=True → accepted as-is.
        """
        roster = {"101", "102", "103"}
        cfg = _make_cfg_unmatched(roster=roster, accept_unmatched=True)
        results = [OcrResult(text="577", ocr_conf=0.88, box=DUMMY_BOX)]
        number, raw_text, conf = validate(results, roster, cfg)
        assert number == "577", f"Expected '577' accepted as-is, got {number!r}"
        assert raw_text == "577"
        assert conf == pytest.approx(0.88)

    # Test 12: ambiguous nearest entries, flag ON → accepted as-is
    def test_ambiguous_snap_flag_on(self):
        """
        "108" vs roster {"101","102","103"}, max_edit=1.
        Three equidistant entries at dist 1 → ambiguous → step 4c;
        accept_unmatched=True → accepted as-is (best_digits="108", no penalty).
        """
        roster = {"101", "102", "103"}
        cfg = _make_cfg_unmatched(roster=roster, accept_unmatched=True)
        results = [OcrResult(text="108", ocr_conf=0.75, box=DUMMY_BOX)]
        number, raw_text, conf = validate(results, roster, cfg)
        assert number == "108", f"Expected '108' accepted as-is (ambiguous snap, flag on), got {number!r}"
        assert raw_text == "108"
        assert conf == pytest.approx(0.75)

    # Test 13 (regression): flag OFF/absent → both still rejected
    def test_no_match_flag_off_still_rejected(self):
        """Flag absent → POC behaviour: no-match within budget is rejected."""
        roster = {"101", "102", "103"}
        cfg = _make_cfg_unmatched(roster=roster, accept_unmatched=False)
        results = [OcrResult(text="577", ocr_conf=0.88, box=DUMMY_BOX)]
        number, raw_text, conf = validate(results, roster, cfg)
        assert number is None, "Flag off: should still reject 577"

    def test_ambiguous_flag_off_still_rejected(self):
        """Flag absent → POC behaviour: ambiguous snap is rejected."""
        roster = {"101", "102", "103"}
        cfg = _make_cfg_unmatched(roster=roster, accept_unmatched=False)
        results = [OcrResult(text="108", ocr_conf=0.75, box=DUMMY_BOX)]
        number, raw_text, conf = validate(results, roster, cfg)
        assert number is None, "Flag off: should still reject ambiguous snap"

    def test_flag_key_absent_still_rejected(self):
        """Key entirely absent defaults to False → rejected."""
        roster = {"101", "102", "103"}
        cfg = {
            "validate": {
                "roster": None,
                "min_digits": 1,
                "max_digits": 3,
                "leading_zeros": False,
                "max_edit_distance": 1,
                # no accept_unmatched key
            },
            "score": {"confidence_threshold": 0.60},
        }
        results = [OcrResult(text="577", ocr_conf=0.88, box=DUMMY_BOX)]
        number, raw_text, conf = validate(results, roster, cfg)
        assert number is None, "Key absent defaults to False → rejected"

    # Test 14: unique snap still snaps (and penalizes) with the flag on
    def test_unique_snap_still_snaps_with_flag_on(self):
        """
        Flag on does NOT affect step 4b (unique snap).
        "102" vs roster {"101","150","200"} → unique nearest "101" at dist 1 → snaps.
        Penalty still applied; flag only affects step 4c.
        """
        roster = {"101", "150", "200"}
        cfg = _make_cfg_unmatched(roster=roster, accept_unmatched=True)
        results = [OcrResult(text="102", ocr_conf=0.90, box=DUMMY_BOX)]
        number, raw_text, conf = validate(results, roster, cfg)
        assert number == "101", f"Expected snap to '101', got {number!r}"
        assert raw_text == "102"
        assert conf == pytest.approx(0.90 - SNAP_PENALTY), (
            "Snap penalty must still apply with accept_unmatched=True"
        )
