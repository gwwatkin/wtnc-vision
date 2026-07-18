"""Tests for CandidateTracker — task2 / design §4.2.

Builds tiny run dirs in tmp_path; hand-constructs CrossingResult objects.
No real inference.

Coverage:
  - Burst of non-confident frames within window_s → one candidate, correct frame_count;
    gap > window_s → second candidate while first stays open.
  - had_confident=True frames are ignored entirely.
  - det_conf < min_det_conf and statuses outside self.statuses are filtered out;
    a frame where nothing survives is a no-op.
  - Rep adoption: larger box area replaces rep; smaller doesn't.
  - Hints: most-frequent needs_review number wins; tie → higher conf;
    rejected-only candidate → hint_number is None, hint_conf == 0.0.
  - suppress_around: overlapping open candidate suppressed; non-overlapping stays
    open; between-two-folds case (candidate opens after fold 1, suppress_around
    from fold 2 kills it); promoted/dismissed untouched.
  - Persistence: candidates.json matches memory after each mutation; fresh tracker +
    load_existing reproduces state; malformed file skipped.
  - set_state: promote with crossing id; dismiss; bad state / unknown id → ValueError.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from datetime import datetime, timezone

import pytest

# Ensure rider_id is importable (same shim as engine.py)
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.abspath(os.path.join(_BACKEND_DIR, "..", ".."))
_SRC = os.path.join(_REPO_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from rider_id.types import CrossingResult

from backend.candidates import CandidateTracker, _box_area, _epoch_ms, _ts_seconds
from backend.results_models import Candidate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUSES = ("needs_review", "rejected")
_WINDOW_S = 5.0
_MIN_DET_CONF = 0.5


def _make_tracker(tmp_path, window_s: float = _WINDOW_S,
                  min_det_conf: float = _MIN_DET_CONF,
                  statuses: tuple = _STATUSES) -> CandidateTracker:
    return CandidateTracker(str(tmp_path), window_s, min_det_conf, statuses)


def _make_result(
    status: str = "needs_review",
    number: str | None = "101",
    confidence: float = 0.8,
    det_conf: float = 0.9,
    box: tuple = (0.0, 0.0, 10.0, 10.0),
) -> CrossingResult:
    return CrossingResult(
        number=number,
        raw_text=str(number) if number else None,
        confidence=confidence,
        status=status,
        rider_box=box,
        crop_path=None,
        det_conf=det_conf,
    )


def _ts(offset_s: float = 0.0) -> str:
    """Return an ISO-8601 UTC timestamp at a fixed base + offset_s."""
    base_epoch = 1_720_000_000.0  # arbitrary fixed epoch seconds
    epoch = base_epoch + offset_s
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return dt.isoformat()


def _run_dir(tmp_path, run: str) -> str:
    path = os.path.join(str(tmp_path), run)
    os.makedirs(path, exist_ok=True)
    return path


def _load_json(run_dir: str) -> list[dict]:
    path = os.path.join(run_dir, "candidates.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Grouping / window tests
# ---------------------------------------------------------------------------

class TestGrouping:
    def test_burst_within_window_creates_one_candidate(self, tmp_path):
        """Multiple frames within window_s → one candidate with correct frame_count."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        t0 = _ts(0.0)
        t1 = _ts(1.0)
        t2 = _ts(2.0)

        for ts in (t0, t1, t2):
            tracker.observe(run, ts, f"{run}/collected/frame.jpg", [_make_result()], False)

        candidates = tracker.list(run)
        assert len(candidates) == 1
        assert candidates[0].frame_count == 3
        assert candidates[0].state == "open"

    def test_gap_beyond_window_creates_second_candidate(self, tmp_path):
        """A gap > window_s leaves the first open and starts a second."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        t0 = _ts(0.0)
        t1 = _ts(1.0)
        # t1 is at 1.0s; gap needs ts - 1.0 > 5.0, so ts > 6.0; use 7.0
        t_gap = _ts(7.0)
        t_gap2 = _ts(8.0)

        tracker.observe(run, t0, "run1/collected/f0.jpg", [_make_result()], False)
        tracker.observe(run, t1, "run1/collected/f1.jpg", [_make_result()], False)
        tracker.observe(run, t_gap, "run1/collected/fg.jpg", [_make_result()], False)
        tracker.observe(run, t_gap2, "run1/collected/fg2.jpg", [_make_result()], False)

        candidates = tracker.list(run)
        assert len(candidates) == 2
        # Both are open (first was not suppressed or resolved)
        assert all(c.state == "open" for c in candidates)
        assert candidates[0].frame_count == 2
        assert candidates[1].frame_count == 2

    def test_last_seen_updated_on_fold(self, tmp_path):
        """last_seen advances to the newest folded timestamp."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        t0 = _ts(0.0)
        t1 = _ts(2.0)
        tracker.observe(run, t0, "f0.jpg", [_make_result()], False)
        tracker.observe(run, t1, "f1.jpg", [_make_result()], False)

        cand = tracker.list(run)[0]
        assert cand.last_seen == t1

    def test_time_stays_as_first_seen(self, tmp_path):
        """Candidate.time is always the first-seen timestamp."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        t0 = _ts(0.0)
        t1 = _ts(1.0)
        tracker.observe(run, t0, "f0.jpg", [_make_result()], False)
        tracker.observe(run, t1, "f1.jpg", [_make_result()], False)

        cand = tracker.list(run)[0]
        assert cand.time == t0

    def test_candidate_id_contains_run_and_epoch(self, tmp_path):
        """candidate_id follows the f'{run}-cand-{epoch_ms(ts)}' format."""
        tracker = _make_tracker(tmp_path)
        run = "myrun"
        _run_dir(tmp_path, run)

        ts = _ts(0.0)
        tracker.observe(run, ts, "f.jpg", [_make_result()], False)

        cand = tracker.list(run)[0]
        expected_id = f"{run}-cand-{_epoch_ms(ts)}"
        assert cand.candidate_id == expected_id

    def test_multiple_runs_are_independent(self, tmp_path):
        """Candidates for different runs don't interfere."""
        tracker = _make_tracker(tmp_path)
        _run_dir(tmp_path, "runA")
        _run_dir(tmp_path, "runB")

        tracker.observe("runA", _ts(0.0), "fA.jpg", [_make_result()], False)
        tracker.observe("runB", _ts(0.0), "fB.jpg", [_make_result()], False)

        assert len(tracker.list("runA")) == 1
        assert len(tracker.list("runB")) == 1
        assert tracker.list("runA")[0].run == "runA"
        assert tracker.list("runB")[0].run == "runB"


# ---------------------------------------------------------------------------
# Filtering tests
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_had_confident_ignored_entirely(self, tmp_path):
        """had_confident=True means the entire frame is ignored."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], had_confident=True)
        assert tracker.list(run) == []

    def test_det_conf_below_min_filtered(self, tmp_path):
        """det_conf < min_det_conf ⇒ result filtered out; frame is a no-op."""
        tracker = _make_tracker(tmp_path, min_det_conf=0.7)
        run = "run1"
        _run_dir(tmp_path, run)

        low_conf = _make_result(det_conf=0.5)  # below 0.7 threshold
        tracker.observe(run, _ts(0.0), "f.jpg", [low_conf], False)
        assert tracker.list(run) == []

    def test_det_conf_at_min_accepted(self, tmp_path):
        """det_conf == min_det_conf is accepted (>= boundary)."""
        tracker = _make_tracker(tmp_path, min_det_conf=0.7)
        run = "run1"
        _run_dir(tmp_path, run)

        at_threshold = _make_result(det_conf=0.7)
        tracker.observe(run, _ts(0.0), "f.jpg", [at_threshold], False)
        assert len(tracker.list(run)) == 1

    def test_wrong_status_filtered(self, tmp_path):
        """Results with status outside self._statuses are filtered out."""
        tracker = _make_tracker(tmp_path, statuses=("needs_review",))
        run = "run1"
        _run_dir(tmp_path, run)

        # "rejected" is not in statuses when statuses=("needs_review",)
        rejected = _make_result(status="rejected")
        tracker.observe(run, _ts(0.0), "f.jpg", [rejected], False)
        assert tracker.list(run) == []

    def test_confident_status_not_in_candidate_statuses(self, tmp_path):
        """'confident' status doesn't feed candidates."""
        tracker = _make_tracker(tmp_path)  # statuses=("needs_review", "rejected")
        run = "run1"
        _run_dir(tmp_path, run)

        confident = _make_result(status="confident")
        tracker.observe(run, _ts(0.0), "f.jpg", [confident], False)
        assert tracker.list(run) == []

    def test_all_results_filtered_is_no_op(self, tmp_path):
        """When all results for a frame fail the filter, nothing is created."""
        tracker = _make_tracker(tmp_path, min_det_conf=0.99)
        run = "run1"
        _run_dir(tmp_path, run)

        result = _make_result(det_conf=0.5)  # below 0.99
        tracker.observe(run, _ts(0.0), "f.jpg", [result], False)
        assert tracker.list(run) == []

    def test_mixed_results_only_passing_contribute(self, tmp_path):
        """Only results that pass the filter contribute to the candidate."""
        tracker = _make_tracker(tmp_path, statuses=("needs_review",), min_det_conf=0.6)
        run = "run1"
        _run_dir(tmp_path, run)

        passing = _make_result(status="needs_review", det_conf=0.9, box=(0.0, 0.0, 20.0, 20.0))
        failing_status = _make_result(status="rejected", det_conf=0.9, box=(0.0, 0.0, 100.0, 100.0))
        failing_conf = _make_result(status="needs_review", det_conf=0.1, box=(0.0, 0.0, 50.0, 50.0))

        tracker.observe(run, _ts(0.0), "f.jpg", [passing, failing_status, failing_conf], False)
        cand = tracker.list(run)[0]
        # Rep should be from the passing result (20x20), not the huge failing boxes
        assert cand.rep_box == [0.0, 0.0, 20.0, 20.0]


# ---------------------------------------------------------------------------
# Rep adoption tests
# ---------------------------------------------------------------------------

class TestRepAdoption:
    def test_larger_box_replaces_rep(self, tmp_path):
        """A frame with a larger rider box becomes the new representative."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        small_box = (0.0, 0.0, 5.0, 5.0)   # area = 25
        large_box = (0.0, 0.0, 20.0, 20.0)  # area = 400

        small_result = _make_result(box=small_box)
        large_result = _make_result(box=large_box)

        tracker.observe(run, _ts(0.0), "small.jpg", [small_result], False)
        tracker.observe(run, _ts(1.0), "large.jpg", [large_result], False)

        cand = tracker.list(run)[0]
        assert cand.rep_filename == "large.jpg"
        assert cand.rep_box == list(large_box)

    def test_smaller_box_does_not_replace_rep(self, tmp_path):
        """A frame with a smaller rider box does not displace the existing rep."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        large_box = (0.0, 0.0, 20.0, 20.0)
        small_box = (0.0, 0.0, 5.0, 5.0)

        tracker.observe(run, _ts(0.0), "large.jpg", [_make_result(box=large_box)], False)
        tracker.observe(run, _ts(1.0), "small.jpg", [_make_result(box=small_box)], False)

        cand = tracker.list(run)[0]
        assert cand.rep_filename == "large.jpg"

    def test_equal_box_does_not_replace_rep(self, tmp_path):
        """A frame with equal box area does not replace the existing rep."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        box = (0.0, 0.0, 10.0, 10.0)

        tracker.observe(run, _ts(0.0), "first.jpg", [_make_result(box=box)], False)
        tracker.observe(run, _ts(1.0), "second.jpg", [_make_result(box=box)], False)

        cand = tracker.list(run)[0]
        assert cand.rep_filename == "first.jpg"

    def test_best_box_per_frame_chosen(self, tmp_path):
        """When a frame has multiple surviving results, the largest box wins."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        # First frame: initial rep with a medium box
        medium_box = (0.0, 0.0, 10.0, 10.0)
        tracker.observe(run, _ts(0.0), "medium.jpg", [_make_result(box=medium_box)], False)

        # Second frame: two results, second is larger
        large_box = (0.0, 0.0, 30.0, 30.0)
        small_box = (0.0, 0.0, 2.0, 2.0)
        r_large = _make_result(box=large_box, number="101")
        r_small = _make_result(box=small_box, number="202")
        tracker.observe(run, _ts(1.0), "second.jpg", [r_small, r_large], False)

        cand = tracker.list(run)[0]
        assert cand.rep_filename == "second.jpg"
        assert cand.rep_box == list(large_box)


# ---------------------------------------------------------------------------
# Hints tests
# ---------------------------------------------------------------------------

class TestHints:
    def test_most_frequent_number_wins(self, tmp_path):
        """hint_number is the most frequent needs_review number."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        r101 = _make_result(status="needs_review", number="101", confidence=0.7)
        r101b = _make_result(status="needs_review", number="101", confidence=0.6)
        r202 = _make_result(status="needs_review", number="202", confidence=0.9)

        tracker.observe(run, _ts(0.0), "f0.jpg", [r101], False)
        tracker.observe(run, _ts(1.0), "f1.jpg", [r202], False)
        tracker.observe(run, _ts(2.0), "f2.jpg", [r101b], False)

        cand = tracker.list(run)[0]
        assert cand.hint_number == "101"  # seen twice vs 202 once

    def test_hint_conf_is_overall_best(self, tmp_path):
        """hint_conf is the best needs_review confidence overall (not just the winner's)."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        r101 = _make_result(status="needs_review", number="101", confidence=0.6)
        r101b = _make_result(status="needs_review", number="101", confidence=0.7)
        r202 = _make_result(status="needs_review", number="202", confidence=0.95)

        tracker.observe(run, _ts(0.0), "f0.jpg", [r101], False)
        tracker.observe(run, _ts(1.0), "f1.jpg", [r101b], False)
        tracker.observe(run, _ts(2.0), "f2.jpg", [r202], False)

        cand = tracker.list(run)[0]
        # 101 appears twice (wins on count), but hint_conf is max over all numbers = 0.95
        assert cand.hint_number == "101"
        assert abs(cand.hint_conf - 0.95) < 1e-9

    def test_tie_broken_by_higher_confidence(self, tmp_path):
        """Ties in frequency are broken by higher best confidence."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        r101 = _make_result(status="needs_review", number="101", confidence=0.6)
        r202 = _make_result(status="needs_review", number="202", confidence=0.9)

        tracker.observe(run, _ts(0.0), "f0.jpg", [r101], False)
        tracker.observe(run, _ts(1.0), "f1.jpg", [r202], False)

        cand = tracker.list(run)[0]
        # Both seen once; 202 has higher confidence → wins
        assert cand.hint_number == "202"

    def test_rejected_only_candidate_has_no_hint(self, tmp_path):
        """Rejected results never contribute to hints → hint_number None, hint_conf 0.0."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        r_rejected = _make_result(status="rejected", number="101", confidence=0.9)
        tracker.observe(run, _ts(0.0), "f.jpg", [r_rejected], False)

        cand = tracker.list(run)[0]
        assert cand.hint_number is None
        assert cand.hint_conf == 0.0

    def test_hint_number_none_when_no_needs_review_in_span(self, tmp_path):
        """All-rejected frames → hint_number stays None."""
        tracker = _make_tracker(tmp_path, statuses=("needs_review", "rejected"))
        run = "run1"
        _run_dir(tmp_path, run)

        for i in range(3):
            r = _make_result(status="rejected", number=None, confidence=0.0)
            tracker.observe(run, _ts(float(i)), "f.jpg", [r], False)

        cand = tracker.list(run)[0]
        assert cand.hint_number is None

    def test_needs_review_with_none_number_skipped(self, tmp_path):
        """needs_review result with number=None does not contribute to hint tally."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        r = _make_result(status="needs_review", number=None, confidence=0.9)
        tracker.observe(run, _ts(0.0), "f.jpg", [r], False)

        cand = tracker.list(run)[0]
        assert cand.hint_number is None


# ---------------------------------------------------------------------------
# suppress_around tests
# ---------------------------------------------------------------------------

class TestSuppressAround:
    def test_overlapping_open_candidate_suppressed(self, tmp_path):
        """suppress_around suppresses an open candidate whose span overlaps ts ± window_s."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        # Create an open candidate at t=0
        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)

        # suppress_around at t=1 (within window)
        tracker.suppress_around(run, _ts(1.0))

        cand = tracker.list(run)[0]
        assert cand.state == "suppressed"

    def test_non_overlapping_candidate_stays_open(self, tmp_path):
        """suppress_around does not affect a candidate whose span is far outside ts ± window_s."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        # Candidate at t=0..0
        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)

        # suppress_around at t = 3 * window_s (clearly outside)
        tracker.suppress_around(run, _ts(3 * _WINDOW_S + 0.1))

        cand = tracker.list(run)[0]
        assert cand.state == "open"

    def test_suppress_does_not_affect_promoted_or_dismissed(self, tmp_path):
        """suppress_around never changes promoted or dismissed candidates."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        # Create and resolve a candidate
        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id
        tracker.set_state(cid, "promoted", "some-crossing-id")

        tracker.suppress_around(run, _ts(0.5))

        cand = tracker.get(cid)
        assert cand.state == "promoted"

    def test_suppress_does_not_affect_dismissed(self, tmp_path):
        """suppress_around never changes a dismissed candidate."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id
        tracker.set_state(cid, "dismissed")

        tracker.suppress_around(run, _ts(0.5))

        cand = tracker.get(cid)
        assert cand.state == "dismissed"

    def test_between_two_folds_case(self, tmp_path):
        """Candidate opened between two confident folds gets suppressed on second fold.

        Scenario: confident fold at t=0, non-confident frames at t=1..2 open a
        candidate, then confident fold at t=3 (within window) → suppress_around(t=3)
        must catch the candidate.
        """
        tracker = _make_tracker(tmp_path, window_s=5.0)
        run = "run1"
        _run_dir(tmp_path, run)

        # First confident fold: suppress_around at t=0
        tracker.suppress_around(run, _ts(0.0))
        # Nothing to suppress yet

        # Non-confident frames at t=1 and t=2 → opens a candidate
        tracker.observe(run, _ts(1.0), "f1.jpg", [_make_result()], False)
        tracker.observe(run, _ts(2.0), "f2.jpg", [_make_result()], False)
        assert tracker.list(run)[0].state == "open"

        # Second confident fold at t=3 → suppress_around(t=3) should catch the candidate
        tracker.suppress_around(run, _ts(3.0))

        cand = tracker.list(run)[0]
        assert cand.state == "suppressed"

    def test_suppress_multiple_open_candidates(self, tmp_path):
        """When multiple open candidates overlap the window, all are suppressed."""
        tracker = _make_tracker(tmp_path, window_s=10.0)
        run = "run1"
        _run_dir(tmp_path, run)

        # Two bursts well within window of each other
        tracker.observe(run, _ts(0.0), "f0.jpg", [_make_result()], False)
        # Force a second candidate by creating a gap
        tracker.observe(run, _ts(12.0), "f1.jpg", [_make_result()], False)

        # Now suppress at t=6 — window extends from -4 to 16, covers both
        tracker.suppress_around(run, _ts(6.0))

        candidates = tracker.list(run)
        assert all(c.state == "suppressed" for c in candidates)

    def test_already_suppressed_stays_suppressed(self, tmp_path):
        """A suppressed candidate stays suppressed if suppress_around is called again."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        tracker.suppress_around(run, _ts(1.0))
        tracker.suppress_around(run, _ts(2.0))

        cand = tracker.list(run)[0]
        assert cand.state == "suppressed"


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_candidates_json_written_on_observe(self, tmp_path):
        """candidates.json is written after observe creates a candidate."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        rd = _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)

        data = _load_json(rd)
        assert len(data) == 1
        assert data[0]["state"] == "open"

    def test_candidates_json_matches_memory(self, tmp_path):
        """After multiple mutations, candidates.json exactly mirrors memory."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        rd = _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f0.jpg", [_make_result()], False)
        tracker.observe(run, _ts(1.0), "f1.jpg", [_make_result()], False)
        tracker.observe(run, _ts(_WINDOW_S + 1), "f2.jpg", [_make_result()], False)

        memory = [dataclasses.asdict(c) for c in tracker.list(run)]
        disk = _load_json(rd)
        assert memory == disk

    def test_load_existing_reproduces_state(self, tmp_path):
        """A fresh tracker + load_existing reproduces the in-memory state."""
        tracker1 = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker1.observe(run, _ts(0.0), "f0.jpg", [_make_result()], False)
        tracker1.observe(run, _ts(1.0), "f1.jpg", [_make_result()], False)

        # Create fresh tracker and load
        tracker2 = _make_tracker(tmp_path)
        tracker2.load_existing()

        candidates1 = tracker1.list(run)
        candidates2 = tracker2.list(run)

        assert len(candidates1) == len(candidates2)
        for c1, c2 in zip(candidates1, candidates2):
            assert c1.candidate_id == c2.candidate_id
            assert c1.frame_count == c2.frame_count
            assert c1.state == c2.state

    def test_load_existing_skips_malformed_file(self, tmp_path):
        """load_existing skips a run with a malformed candidates.json without raising."""
        run = "badrun"
        rd = _run_dir(tmp_path, run)
        path = os.path.join(rd, "candidates.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not valid json{{{")

        tracker = _make_tracker(tmp_path)
        tracker.load_existing()  # Should not raise

        assert tracker.list(run) == []

    def test_load_existing_handles_missing_run_dir(self, tmp_path):
        """load_existing on an empty run_root succeeds without error."""
        tracker = _make_tracker(tmp_path)
        tracker.load_existing()  # No runs at all — should be fine

    def test_set_state_persists_to_disk(self, tmp_path):
        """set_state updates the on-disk candidates.json."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        rd = _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id

        tracker.set_state(cid, "dismissed")

        data = _load_json(rd)
        assert data[0]["state"] == "dismissed"

    def test_suppress_persists_to_disk(self, tmp_path):
        """suppress_around updates the on-disk candidates.json."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        rd = _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        tracker.suppress_around(run, _ts(1.0))

        data = _load_json(rd)
        assert data[0]["state"] == "suppressed"

    def test_load_existing_hint_tally_bootstrapped(self, tmp_path):
        """After load_existing, an open candidate's hint tally starts from persisted hint."""
        tracker1 = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        # Two frames with "101" and one with "202"
        r101 = _make_result(status="needs_review", number="101", confidence=0.7)
        r202 = _make_result(status="needs_review", number="202", confidence=0.8)
        tracker1.observe(run, _ts(0.0), "f0.jpg", [r101], False)
        tracker1.observe(run, _ts(1.0), "f1.jpg", [r202], False)
        tracker1.observe(run, _ts(2.0), "f2.jpg", [r101], False)

        cand1 = tracker1.list(run)[0]
        assert cand1.hint_number == "101"

        # Reload
        tracker2 = _make_tracker(tmp_path)
        tracker2.load_existing()
        cand2 = tracker2.list(run)[0]
        assert cand2.hint_number == "101"


# ---------------------------------------------------------------------------
# set_state tests
# ---------------------------------------------------------------------------

class TestSetState:
    def test_promote_with_crossing_id(self, tmp_path):
        """set_state("promoted", crossing_id) marks candidate as promoted."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id

        crossing_id = "run1-manual-12345"
        result = tracker.set_state(cid, "promoted", crossing_id)

        assert result.state == "promoted"
        assert result.promoted_crossing_id == crossing_id

        # Verify via get too
        fetched = tracker.get(cid)
        assert fetched.state == "promoted"
        assert fetched.promoted_crossing_id == crossing_id

    def test_dismiss(self, tmp_path):
        """set_state("dismissed") marks candidate as dismissed."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id

        result = tracker.set_state(cid, "dismissed")
        assert result.state == "dismissed"

    def test_bad_state_raises_value_error(self, tmp_path):
        """set_state with an unsupported state raises ValueError."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id

        with pytest.raises(ValueError, match="unsupported state"):
            tracker.set_state(cid, "open")

    def test_suppressed_state_raises_value_error(self, tmp_path):
        """set_state('suppressed') raises ValueError (not allowed via this method)."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id

        with pytest.raises(ValueError):
            tracker.set_state(cid, "suppressed")

    def test_unknown_id_raises_value_error(self, tmp_path):
        """set_state with an unknown candidate_id raises ValueError."""
        tracker = _make_tracker(tmp_path)

        with pytest.raises(ValueError, match="unknown candidate_id"):
            tracker.set_state("no-such-id", "dismissed")

    def test_set_state_returns_copy(self, tmp_path):
        """set_state returns a snapshot (copy), not the live object."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id

        copy = tracker.set_state(cid, "dismissed")
        # Mutating the copy should not affect the tracker's internal state
        copy.state = "open"
        assert tracker.get(cid).state == "dismissed"


# ---------------------------------------------------------------------------
# list / get tests
# ---------------------------------------------------------------------------

class TestListGet:
    def test_list_returns_all_states(self, tmp_path):
        """list returns candidates in all states (open, suppressed, promoted, dismissed)."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f0.jpg", [_make_result()], False)
        tracker.observe(run, _ts(_WINDOW_S + 2), "f1.jpg", [_make_result()], False)

        cids = [c.candidate_id for c in tracker.list(run)]
        tracker.set_state(cids[0], "dismissed")
        tracker.suppress_around(run, _ts(_WINDOW_S + 2))  # suppresses cids[1] if in window

        all_candidates = tracker.list(run)
        states = {c.state for c in all_candidates}
        assert "dismissed" in states

    def test_list_returns_copies(self, tmp_path):
        """list returns independent copies; mutating them doesn't affect tracker state."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        candidates = tracker.list(run)
        candidates[0].state = "suppressed"  # mutate the copy

        # Tracker's internal state should be unaffected
        assert tracker.list(run)[0].state == "open"

    def test_list_empty_for_unknown_run(self, tmp_path):
        """list returns [] for an unknown run."""
        tracker = _make_tracker(tmp_path)
        assert tracker.list("no-such-run") == []

    def test_get_returns_none_for_unknown_id(self, tmp_path):
        """get returns None for an unknown candidate_id."""
        tracker = _make_tracker(tmp_path)
        assert tracker.get("nonexistent-id") is None

    def test_get_returns_copy(self, tmp_path):
        """get returns an independent copy."""
        tracker = _make_tracker(tmp_path)
        run = "run1"
        _run_dir(tmp_path, run)

        tracker.observe(run, _ts(0.0), "f.jpg", [_make_result()], False)
        cid = tracker.list(run)[0].candidate_id

        copy = tracker.get(cid)
        copy.state = "suppressed"

        assert tracker.list(run)[0].state == "open"


# ---------------------------------------------------------------------------
# Box area helper tests
# ---------------------------------------------------------------------------

class TestBoxArea:
    def test_normal_box(self):
        assert _box_area((0.0, 0.0, 10.0, 20.0)) == pytest.approx(200.0)

    def test_zero_width(self):
        assert _box_area((5.0, 0.0, 5.0, 10.0)) == pytest.approx(0.0)

    def test_inverted_box(self):
        """Inverted coordinates return 0.0 (degenerate)."""
        assert _box_area((10.0, 10.0, 5.0, 5.0)) == pytest.approx(0.0)
