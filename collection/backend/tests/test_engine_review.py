"""test_engine_review.py — Task 4 new-behavior tests for ResultsEngine.

All new-behavior tests for the review-editing feature:
- Old-schema crossings.json loads with defaults; order_key derived from time.
- crossings() excludes deleted, sorts by (order_key, time).
- set_position midpoints (between / top / bottom), cross-run ⇒ ValueError.
- create_crossing: id format, provenance, annotated copy, csv row, absorb entry; collision rule.
- edit_crossing: re-enrich, edited=True; N→M absorb on both sides; delete ⇒ tombstone; restore.
- Absorb-only fold: last_seen bumps, confidence/annotation untouched.
- suppress_around called on EVERY fold path.
- Restart: manual/edited/deleted crossings become absorb_only after start().
- status: counts, processed_through, cached manifest stats.
- frame_path traversal guard.
- Worker wiring: frames.append always; candidates.observe with had_confident; disabled flags.

Monkeypatching convention (refinement 4): engine.CandidateTracker and engine.FramesIndex
are patched BEFORE constructing the engine, so the engine holds fake collaborators.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, call, patch

import cv2
import numpy as np
import pytest

# Ensure rider_id is importable (same shim as engine.py)
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TESTS_DIR)
_REPO_ROOT = os.path.abspath(os.path.join(_BACKEND_DIR, "..", ".."))
_SRC = os.path.join(_REPO_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from rider_id.types import CrossingResult, RiderBox

import backend.engine as engine_mod
from backend.engine import ResultsEngine, _epoch_ms, _ts_seconds
from backend.live_config import LiveConfig
from backend.results_models import Candidate, Crossing, _OpenCrossing
from backend.rosters import EMPTY_ROSTER, Roster


# ---------------------------------------------------------------------------
# Fake collaborators (refinement 4 — monkeypatch engine.CandidateTracker /
# engine.FramesIndex before constructing the engine)
# ---------------------------------------------------------------------------

class FakeCandidateTracker:
    """Minimal CandidateTracker fake: records calls, stores minimal state."""

    def __init__(self, run_root: str, window_s: float, min_det_conf: float,
                 statuses: tuple) -> None:
        self.run_root = run_root
        self.window_s = window_s
        self.min_det_conf = min_det_conf
        self.statuses = statuses
        # Call log
        self.load_existing_calls: int = 0
        self.observe_calls: list[dict] = []
        self.suppress_calls: list[tuple[str, str]] = []
        self.state_calls: list[tuple] = []
        # In-memory state for list/get/set_state
        self._candidates: dict[str, Candidate] = {}  # id -> Candidate

    def load_existing(self) -> None:
        self.load_existing_calls += 1

    def observe(self, run: str, ts: str, filename: str,
                results: list, had_confident: bool) -> None:
        self.observe_calls.append(
            {"run": run, "ts": ts, "filename": filename,
             "had_confident": had_confident, "results": results}
        )

    def suppress_around(self, run: str, ts: str) -> None:
        self.suppress_calls.append((run, ts))

    def list(self, run: str) -> list[Candidate]:
        return [c for c in self._candidates.values() if c.run == run]

    def get(self, candidate_id: str) -> Candidate | None:
        return self._candidates.get(candidate_id)

    def set_state(self, candidate_id: str, state: str,
                  promoted_crossing_id: str | None = None) -> Candidate:
        c = self._candidates.get(candidate_id)
        if c is None:
            raise ValueError(f"Unknown candidate_id: {candidate_id!r}")
        c.state = state
        if state == "promoted" and promoted_crossing_id is not None:
            c.promoted_crossing_id = promoted_crossing_id
        return dataclasses.replace(c)

    def add_candidate(self, cand: Candidate) -> None:
        """Helper for tests to pre-populate a candidate."""
        self._candidates[cand.candidate_id] = cand


class FakeFramesIndex:
    """Minimal FramesIndex fake: records calls, returns empty structures."""

    def __init__(self, run_root: str) -> None:
        self.run_root = run_root
        self.append_calls: list[dict] = []

    def append(self, run: str, entry: dict, results: list) -> None:
        self.append_calls.append({"run": run, "entry": entry, "results": results})

    def frames(self, run: str, center_ts: str | None, span_s: float,
               limit: int) -> list[dict]:
        return []

    def meta(self, run: str) -> dict:
        return {"count": 0, "first_ts": None, "last_ts": None}


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_live(
    dedup_window_s: float = 5.0,
    candidates_enabled: bool = True,
    frames_index_enabled: bool = True,
) -> LiveConfig:
    return LiveConfig(
        enabled=True,
        cv_config_path="/dev/null",
        dedup_window_s=dedup_window_s,
        statuses=("confident",),
        candidates_enabled=candidates_enabled,
        candidate_statuses=("needs_review", "rejected"),
        candidate_window_s=5.0,
        candidate_min_det_conf=0.5,
        frames_index_enabled=frames_index_enabled,
    )


def _make_cv_cfg() -> dict:
    return {
        "validate": {"roster": None, "accept_unmatched": True},
        "score": {"confidence_threshold": 0.60},
    }


def _make_tiny_image() -> np.ndarray:
    return np.zeros((20, 20, 3), dtype=np.uint8)


def _write_frame(run_dir: str, name: str) -> str:
    """Write a tiny JPEG and return root-relative path."""
    collected_dir = os.path.join(run_dir, "collected")
    os.makedirs(collected_dir, exist_ok=True)
    abs_path = os.path.join(collected_dir, name)
    cv2.imwrite(abs_path, _make_tiny_image())
    run_name = os.path.basename(run_dir)
    return f"{run_name}/collected/{name}"


def _append_manifest_line(run_dir: str, entry: dict) -> None:
    manifest_path = os.path.join(run_dir, "manifest.jsonl")
    with open(manifest_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _make_manifest_entry(rel_filename: str, client_ts: str, seq: int = 0) -> dict:
    return {
        "filename": rel_filename,
        "client_ts": client_ts,
        "seq": seq,
        "label": rel_filename.split("/")[0],
        "safe_label": rel_filename.split("/")[0],
        "session_id": "test",
        "server_ts": client_ts,
        "bytes": 4,
        "content_type": "image/jpeg",
    }


def _make_result(number: str, conf: float, status: str = "confident",
                 det_conf: float = 0.9) -> CrossingResult:
    return CrossingResult(
        number=number,
        raw_text=number,
        confidence=conf,
        status=status,
        rider_box=(0.0, 0.0, 10.0, 10.0),
        crop_path=None,
        det_conf=det_conf,
    )


def _make_engine_with_fakes(
    tmp_path,
    live: LiveConfig | None = None,
) -> tuple[ResultsEngine, FakeCandidateTracker, FakeFramesIndex]:
    """Create an engine with fake CandidateTracker and FramesIndex (refinement 4).

    Monkeypatches engine.CandidateTracker and engine.FramesIndex on the module,
    then constructs the engine so it holds the fake instances.
    """
    if live is None:
        live = _make_live()
    cv_cfg = _make_cv_cfg()

    fake_tracker: FakeCandidateTracker | None = None
    fake_index: FakeFramesIndex | None = None

    orig_tracker_cls = engine_mod.CandidateTracker
    orig_index_cls = engine_mod.FramesIndex

    def fake_tracker_cls(run_root, window_s, min_det_conf, statuses):
        nonlocal fake_tracker
        fake_tracker = FakeCandidateTracker(run_root, window_s, min_det_conf, statuses)
        return fake_tracker

    def fake_index_cls(run_root):
        nonlocal fake_index
        fake_index = FakeFramesIndex(run_root)
        return fake_index

    engine_mod.CandidateTracker = fake_tracker_cls
    engine_mod.FramesIndex = fake_index_cls
    try:
        eng = ResultsEngine(live, cv_cfg, str(tmp_path))
    finally:
        engine_mod.CandidateTracker = orig_tracker_cls
        engine_mod.FramesIndex = orig_index_cls

    assert fake_tracker is not None
    assert fake_index is not None
    return eng, fake_tracker, fake_index


# ---------------------------------------------------------------------------
# Loader rule — old-schema crossings.json
# ---------------------------------------------------------------------------

class TestLoaderRule:
    """§3.1 loader rule: order_key == 0.0 ⇒ derive from time on load."""

    def test_old_schema_without_order_key(self, tmp_path):
        """Old crossings.json without order_key/source/edited/deleted loads with defaults."""
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        ts = "2026-07-17T10:00:00.000Z"
        old_json = [
            {
                "crossing_id": "run1-101-9999",
                "run": "run1",
                "number": "101",
                "time": ts,
                "confidence": 0.9,
                "name": None,
                "category": "Unknown",
                "matched": False,
                "annotated_path": "run1/annotated/run1-101-9999.jpg",
                "last_seen": ts,
                # NO source, edited, deleted, order_key, order_overridden
            }
        ]
        crossings_path = os.path.join(run_dir, "crossings.json")
        with open(crossings_path, "w") as fh:
            json.dump(old_json, fh)

        from backend.engine import _load_crossings_json
        crossings = _load_crossings_json(run_dir)
        assert len(crossings) == 1
        c = crossings[0]
        assert c.source == "auto"
        assert c.edited is False
        assert c.deleted is False
        # order_key was 0.0 in the schema, so loader derives it from time
        expected_key = float(_epoch_ms(ts))
        assert c.order_key == pytest.approx(expected_key)
        assert c.order_overridden is False

    def test_explicit_order_key_not_overwritten(self, tmp_path):
        """If order_key is already set (non-zero), loader leaves it alone."""
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        ts = "2026-07-17T10:00:00.000Z"
        explicit_key = 1234567890123.0
        new_json = [
            {
                "crossing_id": "run1-101-9999",
                "run": "run1",
                "number": "101",
                "time": ts,
                "confidence": 0.9,
                "name": None,
                "category": "Unknown",
                "matched": False,
                "annotated_path": "run1/annotated/run1-101-9999.jpg",
                "last_seen": ts,
                "source": "auto",
                "edited": False,
                "deleted": False,
                "order_key": explicit_key,
                "order_overridden": True,
            }
        ]
        crossings_path = os.path.join(run_dir, "crossings.json")
        with open(crossings_path, "w") as fh:
            json.dump(new_json, fh)

        from backend.engine import _load_crossings_json
        crossings = _load_crossings_json(run_dir)
        assert crossings[0].order_key == pytest.approx(explicit_key)
        assert crossings[0].order_overridden is True


# ---------------------------------------------------------------------------
# crossings() — filter deleted, sort by (order_key, time)
# ---------------------------------------------------------------------------

class TestCrossingsFilterSort:
    """crossings() excludes deleted and sorts ascending by (order_key, time)."""

    def test_deleted_excluded(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts1 = "2026-07-17T10:00:00.000Z"
        ts2 = "2026-07-17T10:00:10.000Z"

        eng._fold("run1", "101", 0.9, ts1, img, [_make_result("101", 0.9)])
        eng._fold("run1", "202", 0.9, ts2, img, [_make_result("202", 0.9)])

        # Soft-delete crossing for "101"
        cid_101 = eng._crossings["run1"][0].crossing_id
        eng.edit_crossing(cid_101, deleted=True)

        _, active = eng.crossings("run1")
        assert all(not c.deleted for c in active)
        assert len(active) == 1
        assert active[0].number == "202"

    def test_sort_by_order_key(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        # Create two crossings at different times
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:10.000Z"
        eng._fold("run1", "101", 0.9, t1, img, [_make_result("101", 0.9)])
        eng._fold("run1", "202", 0.9, t2, img, [_make_result("202", 0.9)])

        _, sorted_crossings = eng.crossings("run1")
        assert len(sorted_crossings) == 2
        assert sorted_crossings[0].time == t1
        assert sorted_crossings[1].time == t2
        assert sorted_crossings[0].order_key < sorted_crossings[1].order_key

    def test_moved_crossing_sorts_by_order_key_not_time(self, tmp_path):
        """After set_position, crossing sorts by its new order_key, not time."""
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        # c1 at t=0, c2 at t=10, c3 at t=20
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:10.000Z"
        t3 = "2026-07-17T10:00:20.000Z"

        eng._fold("run1", "101", 0.9, t1, img, [_make_result("101", 0.9)])
        eng._fold("run1", "202", 0.9, t2, img, [_make_result("202", 0.9)])
        eng._fold("run1", "303", 0.9, t3, img, [_make_result("303", 0.9)])

        # Identify crossings
        crossings = eng._crossings["run1"]
        c1 = next(c for c in crossings if c.number == "101")
        c2 = next(c for c in crossings if c.number == "202")
        c3 = next(c for c in crossings if c.number == "303")

        # Move c3 to be first (before c1)
        # In ASC order: c1, c2, c3. Move c3 to be before c1 means earlier_id=None, later_id=c1
        eng.set_position(c3.crossing_id, earlier_id=None, later_id=c1.crossing_id)

        _, sorted_cs = eng.crossings("run1")
        numbers = [c.number for c in sorted_cs]
        # c3 is now earliest, then c1, then c2
        assert numbers.index("303") < numbers.index("101")
        assert numbers.index("101") < numbers.index("202")

    def test_new_auto_crossing_slots_by_time_without_disturbing_overrides(self, tmp_path):
        """FR11: new auto crossings slot in by time without undoing manual order moves."""
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:10.000Z"
        t3 = "2026-07-17T10:00:05.000Z"  # between t1 and t2

        eng._fold("run1", "101", 0.9, t1, img, [_make_result("101", 0.9)])
        eng._fold("run1", "202", 0.9, t2, img, [_make_result("202", 0.9)])

        crossings = eng._crossings["run1"]
        c1 = next(c for c in crossings if c.number == "101")
        c2 = next(c for c in crossings if c.number == "202")

        # Override: move c2 to before c1 (swap them in the order)
        eng.set_position(c2.crossing_id, earlier_id=None, later_id=c1.crossing_id)
        assert c2.order_overridden is True

        # Now add a new auto crossing at t3 (time-between); it should slot between c2 and c1
        # by order_key (time-based) but not disturb the override
        eng._fold("run1", "303", 0.9, t3, img, [_make_result("303", 0.9)])

        _, sorted_cs = eng.crossings("run1")
        numbers = [c.number for c in sorted_cs]
        # c2 was moved to order_key < c1.order_key (before c1)
        # c3's order_key = epoch_ms(t3) which is between epoch_ms(t1) and epoch_ms(t2)
        # c2 new key = c1.order_key - 60000 (before c1)
        # order: c2 (moved early), c1, c3 (t3 between t1 and t2, so between c1 and c2 original)
        # Actually: c2 key = c1.order_key - 60_000 (top placement, no earlier neighbor)
        # c1 key = epoch_ms(t1), c3 key = epoch_ms(t3), original c2 key = epoch_ms(t2)
        # After moving c2 to top: c2.order_key < c1.order_key < c3.order_key
        assert numbers.index("202") < numbers.index("101")
        assert numbers.index("101") < numbers.index("303")
        # Verify the override is still intact
        c2_refreshed = eng._crossing_index[c2.crossing_id]
        assert c2_refreshed.order_overridden is True


# ---------------------------------------------------------------------------
# set_position
# ---------------------------------------------------------------------------

class TestSetPosition:
    """set_position midpoints, error cases."""

    def test_midpoint_between_two(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:10.000Z"
        t3 = "2026-07-17T10:00:20.000Z"
        for t, num in [(t1, "101"), (t2, "202"), (t3, "303")]:
            eng._fold("run1", num, 0.9, t, img, [_make_result(num, 0.9)])

        cs = eng._crossings["run1"]
        c1 = next(c for c in cs if c.number == "101")
        c2 = next(c for c in cs if c.number == "202")
        c3 = next(c for c in cs if c.number == "303")

        # Move c2 between c1 and c3 (idempotent — it's already there, but let's test midpoint)
        result = eng.set_position(c2.crossing_id, earlier_id=c1.crossing_id,
                                  later_id=c3.crossing_id)
        assert result.order_key == pytest.approx((c1.order_key + c3.order_key) / 2)
        assert result.order_overridden is True

    def test_top_of_order_no_earlier(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:10.000Z"
        for t, num in [(t1, "101"), (t2, "202")]:
            eng._fold("run1", num, 0.9, t, img, [_make_result(num, 0.9)])

        cs = eng._crossings["run1"]
        c1 = next(c for c in cs if c.number == "101")
        c2 = next(c for c in cs if c.number == "202")

        result = eng.set_position(c2.crossing_id, earlier_id=None, later_id=c1.crossing_id)
        assert result.order_key == pytest.approx(c1.order_key - 60_000)

    def test_bottom_of_order_no_later(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:10.000Z"
        for t, num in [(t1, "101"), (t2, "202")]:
            eng._fold("run1", num, 0.9, t, img, [_make_result(num, 0.9)])

        cs = eng._crossings["run1"]
        c1 = next(c for c in cs if c.number == "101")
        c2 = next(c for c in cs if c.number == "202")

        result = eng.set_position(c1.crossing_id, earlier_id=c2.crossing_id, later_id=None)
        assert result.order_key == pytest.approx(c2.order_key + 60_000)

    def test_cross_run_neighbor_raises_valueerror(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        for run in ("runA", "runB"):
            os.makedirs(os.path.join(str(tmp_path), run), exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("runA", "101", 0.9, ts, img, [_make_result("101", 0.9)])
        t2 = "2026-07-17T10:00:10.000Z"
        eng._fold("runB", "202", 0.9, t2, img, [_make_result("202", 0.9)])

        cA = eng._crossings["runA"][0]
        cB = eng._crossings["runB"][0]

        with pytest.raises(ValueError):
            eng.set_position(cA.crossing_id, earlier_id=cB.crossing_id, later_id=None)

    def test_unknown_crossing_id_raises_keyerror(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        with pytest.raises(KeyError):
            eng.set_position("no-such-id", earlier_id=None, later_id="also-bad")

    def test_no_neighbors_raises_valueerror(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, ts, img, [_make_result("101", 0.9)])
        cid = eng._crossings["run1"][0].crossing_id

        with pytest.raises(ValueError):
            eng.set_position(cid, earlier_id=None, later_id=None)

    def test_set_position_persists(self, tmp_path):
        """After set_position, crossings.json reflects new order_key."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:10.000Z"
        for t, num in [(t1, "101"), (t2, "202")]:
            eng._fold("run1", num, 0.9, t, img, [_make_result(num, 0.9)])

        cs = eng._crossings["run1"]
        c2 = next(c for c in cs if c.number == "202")
        c1 = next(c for c in cs if c.number == "101")

        eng.set_position(c2.crossing_id, earlier_id=None, later_id=c1.crossing_id)

        json_path = os.path.join(run_dir, "crossings.json")
        with open(json_path) as fh:
            data = json.load(fh)
        c2_disk = next(d for d in data if d["crossing_id"] == c2.crossing_id)
        assert c2_disk["order_overridden"] is True
        assert c2_disk["order_key"] == pytest.approx(c1.order_key - 60_000)


# ---------------------------------------------------------------------------
# create_crossing
# ---------------------------------------------------------------------------

class TestCreateCrossing:
    """Manual crossing creation."""

    def test_id_format(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        c = eng.create_crossing("run1", rel, ts, "101")

        expected_ms = _epoch_ms(ts)
        assert c.crossing_id == f"run1-manual-{expected_ms}"

    def test_provenance_fields(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        c = eng.create_crossing("run1", rel, ts, "101")

        assert c.source == "manual"
        assert c.confidence == 0.0
        assert c.edited is False
        assert c.deleted is False
        assert c.order_key == pytest.approx(float(_epoch_ms(ts)))

    def test_annotated_copy_written_without_box(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        c = eng.create_crossing("run1", rel, ts, "101", box=None)

        annotated_abs = os.path.join(str(tmp_path), c.annotated_path)
        assert os.path.isfile(annotated_abs)

    def test_annotated_copy_written_with_box(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        c = eng.create_crossing("run1", rel, ts, "101", box=[2.0, 2.0, 8.0, 8.0])

        annotated_abs = os.path.join(str(tmp_path), c.annotated_path)
        assert os.path.isfile(annotated_abs)

    def test_csv_row_appended(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        eng.create_crossing("run1", rel, ts, "101")

        csv_path = os.path.join(run_dir, "crossings.csv")
        assert os.path.isfile(csv_path)
        with open(csv_path) as fh:
            rows = [l.strip() for l in fh if l.strip()]
        assert len(rows) == 1
        assert ts in rows[0]
        assert "101" in rows[0]

    def test_absorb_entry_installed_with_number(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        c = eng.create_crossing("run1", rel, ts, "101")

        oc = eng._open.get(("run1", "101"))
        assert oc is not None
        assert oc.absorb_only is True
        assert oc.crossing_id == c.crossing_id

    def test_no_absorb_entry_for_empty_number(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        eng.create_crossing("run1", rel, ts, "")

        # No absorb entry for empty number
        assert eng._open.get(("run1", "")) is None

    def test_collision_rule_live_crossing_not_hijacked(self, tmp_path):
        """§7 collision rule: create_crossing with a number that is actively
        folding does NOT install an absorb entry for that number."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts_live = "2026-07-17T10:00:00.000Z"
        # Create a live (non-absorb) crossing for "101" via fold
        eng._fold("run1", "101", 0.9, ts_live, img, [_make_result("101", 0.9)])

        live_oc = eng._open.get(("run1", "101"))
        assert live_oc is not None
        assert live_oc.absorb_only is False  # live crossing

        # Now try to create_crossing for the same number
        rel = _write_frame(run_dir, "frame_001.jpg")
        ts_manual = "2026-07-17T10:00:02.000Z"  # within dedup window
        eng.create_crossing("run1", rel, ts_manual, "101")

        # The live crossing's _open entry must NOT be replaced by the absorb entry
        oc_after = eng._open.get(("run1", "101"))
        assert oc_after is not None
        assert oc_after.absorb_only is False, (
            "Collision rule: live open crossing must keep folding normally"
        )
        assert oc_after.crossing_id == live_oc.crossing_id

    def test_roster_enrichment_applied(self, tmp_path, monkeypatch):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        test_roster = Roster(
            numbers=frozenset({"101"}),
            entries={"101": ("Alice Smith", "Cat 3")},
        )
        monkeypatch.setattr(eng._rosters, "get", lambda run: test_roster)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        c = eng.create_crossing("run1", rel, ts, "101")

        assert c.matched is True
        assert c.name == "Alice Smith"
        assert c.category == "Cat 3"


# ---------------------------------------------------------------------------
# edit_crossing
# ---------------------------------------------------------------------------

class TestEditCrossing:
    """Number edit, re-enrich, delete/restore, unknown id."""

    def test_edit_number_re_enriches(self, tmp_path, monkeypatch):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, ts, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]

        test_roster = Roster(
            numbers=frozenset({"202"}),
            entries={"202": ("Bob Jones", "Cat 4")},
        )
        monkeypatch.setattr(eng._rosters, "get", lambda run: test_roster)

        result = eng.edit_crossing(c.crossing_id, number="202")
        assert result.number == "202"
        assert result.name == "Bob Jones"
        assert result.category == "Cat 4"
        assert result.matched is True
        assert result.edited is True

    def test_edit_number_sets_edited_flag(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, ts, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]
        assert c.edited is False

        eng.edit_crossing(c.crossing_id, number="202")
        assert c.edited is True

    def test_edit_unknown_id_raises_keyerror(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        with pytest.raises(KeyError):
            eng.edit_crossing("no-such-id", number="101")

    def test_delete_excludes_from_crossings(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, ts, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]

        eng.edit_crossing(c.crossing_id, deleted=True)

        _, active = eng.crossings("run1")
        assert len(active) == 0

    def test_restore_re_includes(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, ts, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]

        eng.edit_crossing(c.crossing_id, deleted=True)
        _, active = eng.crossings("run1")
        assert len(active) == 0

        eng.edit_crossing(c.crossing_id, deleted=False)
        _, active = eng.crossings("run1")
        assert len(active) == 1

    def test_delete_installs_absorb_tombstone(self, tmp_path):
        """§7: delete ⇒ existing _open entry flips to absorb_only tombstone."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, ts, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]

        # Verify it's a live crossing
        oc = eng._open.get(("run1", "101"))
        assert oc is not None
        assert oc.absorb_only is False

        eng.edit_crossing(c.crossing_id, deleted=True)

        oc_after = eng._open.get(("run1", "101"))
        assert oc_after is not None
        assert oc_after.absorb_only is True

    def test_late_read_of_old_number_absorbed_after_edit(self, tmp_path):
        """§7: after N→M edit, a late confident read of N is absorbed (no new crossing)."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, t1, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]

        # Edit: change number from "101" to "202"
        eng.edit_crossing(c.crossing_id, number="202")

        # Now a late read of "101" within the window should be absorbed
        t_late = "2026-07-17T10:00:02.000Z"  # within 5s window of t1
        eng._fold("run1", "101", 0.95, t_late, img, [_make_result("101", 0.95)])

        # Should still be only 1 crossing (the late read was absorbed)
        _, active = eng.crossings("run1")
        assert len(active) == 1, (
            f"Late read of old number should be absorbed; got {len(active)} crossings"
        )

    def test_late_read_of_new_number_absorbed_after_edit(self, tmp_path):
        """§7: after N→M edit, a late confident read of M is also absorbed (FR22)."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, t1, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]
        eng.edit_crossing(c.crossing_id, number="202")

        # Late read of "202" within window
        t_late = "2026-07-17T10:00:02.000Z"
        eng._fold("run1", "202", 0.95, t_late, img, [_make_result("202", 0.95)])

        _, active = eng.crossings("run1")
        assert len(active) == 1, (
            f"Late read of new number should be absorbed; got {len(active)} crossings"
        )

    def test_collision_rule_edit_to_live_number(self, tmp_path):
        """§7 collision rule: editing crossing A to number N, when crossing B with number N
        is actively folding, leaves crossing B's _open entry alone."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:10.000Z"  # separate crossing

        # Crossing A (number "101")
        eng._fold("run1", "101", 0.9, t1, img, [_make_result("101", 0.9)])
        cA = eng._crossings["run1"][0]

        # Crossing B (number "202") — live, non-absorb
        eng._fold("run1", "202", 0.9, t2, img, [_make_result("202", 0.9)])
        cB = eng._crossings["run1"][1]
        oc_B_before = eng._open.get(("run1", "202"))
        assert oc_B_before is not None
        assert oc_B_before.absorb_only is False

        # Edit crossing A to number "202" (collision: 202 already has a live crossing)
        eng.edit_crossing(cA.crossing_id, number="202")

        # Crossing B's _open entry must NOT have been turned into absorb_only
        oc_B_after = eng._open.get(("run1", "202"))
        assert oc_B_after is not None
        assert oc_B_after.absorb_only is False, (
            "Collision rule: editing to a number with a live open crossing "
            "must leave that entry alone"
        )
        assert oc_B_after.crossing_id == cB.crossing_id

    def test_edit_persists_to_disk(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, ts, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]

        eng.edit_crossing(c.crossing_id, number="202")

        json_path = os.path.join(run_dir, "crossings.json")
        with open(json_path) as fh:
            data = json.load(fh)
        disk = next(d for d in data if d["crossing_id"] == c.crossing_id)
        assert disk["number"] == "202"
        assert disk["edited"] is True


# ---------------------------------------------------------------------------
# Absorb-only fold behavior
# ---------------------------------------------------------------------------

class TestAbsorbOnlyFold:
    """§7: absorb_only fold updates last_seen ONLY."""

    def test_absorb_only_bumps_last_seen(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        rel = _write_frame(run_dir, "frame_000.jpg")
        c = eng.create_crossing("run1", rel, t1, "101")

        initial_last_seen = c.last_seen
        initial_confidence = c.confidence  # 0.0

        # A confident fold within the window (will be absorbed)
        t_late = "2026-07-17T10:00:02.000Z"
        eng._fold("run1", "101", 0.99, t_late, img, [_make_result("101", 0.99)])

        # last_seen should have been updated
        c_refreshed = eng._crossing_index[c.crossing_id]
        assert c_refreshed.last_seen == t_late
        # confidence should NOT have changed (absorb_only)
        assert c_refreshed.confidence == pytest.approx(initial_confidence)

    def test_absorb_only_no_new_crossing(self, tmp_path):
        """Absorb-only fold must NOT create a new crossing."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        rel = _write_frame(run_dir, "frame_000.jpg")
        t1 = "2026-07-17T10:00:00.000Z"
        eng.create_crossing("run1", rel, t1, "101")  # absorb entry installed

        t_late = "2026-07-17T10:00:02.000Z"
        eng._fold("run1", "101", 0.99, t_late, img, [_make_result("101", 0.99)])

        assert len(eng._crossings.get("run1", [])) == 1

    def test_deleted_crossing_absorbs_silently(self, tmp_path):
        """§7: fold into deleted crossing — tombstone, no new crossing."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, t1, img, [_make_result("101", 0.9)])
        c = eng._crossings["run1"][0]
        eng.edit_crossing(c.crossing_id, deleted=True)

        t_late = "2026-07-17T10:00:02.000Z"
        eng._fold("run1", "101", 0.99, t_late, img, [_make_result("101", 0.99)])

        # Should still be only 1 crossing total (deleted + no new)
        assert len(eng._crossings.get("run1", [])) == 1


# ---------------------------------------------------------------------------
# suppress_around called on every fold path
# ---------------------------------------------------------------------------

class TestSuppressAroundCalled:
    """suppress_around must be called on every fold path."""

    def test_suppress_called_on_new_crossing_fold(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        eng._fold("run1", "101", 0.9, ts, img, [_make_result("101", 0.9)])

        assert len(fake_tracker.suppress_calls) >= 1
        assert ("run1", ts) in fake_tracker.suppress_calls

    def test_suppress_called_on_same_crossing_fold(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:02.000Z"  # within window

        eng._fold("run1", "101", 0.9, t1, img, [_make_result("101", 0.9)])
        fake_tracker.suppress_calls.clear()
        eng._fold("run1", "101", 0.95, t2, img, [_make_result("101", 0.95)])

        assert ("run1", t2) in fake_tracker.suppress_calls

    def test_suppress_called_on_absorb_only_fold(self, tmp_path):
        """§7: suppress_around called even on absorb-only folds."""
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        img = _make_tiny_image()
        rel = _write_frame(run_dir, "frame_000.jpg")
        t1 = "2026-07-17T10:00:00.000Z"
        eng.create_crossing("run1", rel, t1, "101")

        fake_tracker.suppress_calls.clear()
        t_late = "2026-07-17T10:00:02.000Z"
        eng._fold("run1", "101", 0.99, t_late, img, [_make_result("101", 0.99)])

        assert ("run1", t_late) in fake_tracker.suppress_calls


# ---------------------------------------------------------------------------
# Restart: absorb_only rebuild
# ---------------------------------------------------------------------------

class TestRestartAbsorbState:
    """§7 restart: manual/edited/deleted crossings get absorb_only=True after start()."""

    def _run_with_fakes(self, tmp_path, monkeypatch, actions_fn=None) -> ResultsEngine:
        """Run an engine lifecycle with fakes patched in."""
        orig_tracker = engine_mod.CandidateTracker
        orig_index = engine_mod.FramesIndex

        engine_mod.CandidateTracker = FakeCandidateTracker
        engine_mod.FramesIndex = FakeFramesIndex
        engine_mod.pipeline.run = lambda img, cfg: []
        try:
            engine = asyncio.run(self._start_stop(tmp_path, actions_fn))
        finally:
            engine_mod.CandidateTracker = orig_tracker
            engine_mod.FramesIndex = orig_index

        return engine

    @staticmethod
    async def _start_stop(tmp_path, actions_fn=None):
        live = _make_live()
        cv_cfg = _make_cv_cfg()
        eng = ResultsEngine(live, cv_cfg, str(tmp_path))
        await eng.start()
        import asyncio as _asyncio
        await _asyncio.sleep(0.05)
        if actions_fn:
            actions_fn(eng)
        await eng.stop()
        return eng

    def test_manual_crossing_absorb_only_after_restart(self, tmp_path, monkeypatch):
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"

        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [])

        # Engine 1: create a manual crossing
        def actions1(eng):
            eng.create_crossing("run1", rel, ts, "101")

        orig_tracker = engine_mod.CandidateTracker
        orig_index = engine_mod.FramesIndex
        engine_mod.CandidateTracker = FakeCandidateTracker
        engine_mod.FramesIndex = FakeFramesIndex
        try:
            asyncio.run(self._start_stop(tmp_path, actions1))
        finally:
            engine_mod.CandidateTracker = orig_tracker
            engine_mod.FramesIndex = orig_index

        # Engine 2: restart — manual crossing should have absorb_only=True
        orig_tracker = engine_mod.CandidateTracker
        orig_index = engine_mod.FramesIndex
        engine_mod.CandidateTracker = FakeCandidateTracker
        engine_mod.FramesIndex = FakeFramesIndex
        try:
            engine2 = asyncio.run(self._start_stop(tmp_path))
        finally:
            engine_mod.CandidateTracker = orig_tracker
            engine_mod.FramesIndex = orig_index

        oc = engine2._open.get(("run1", "101"))
        assert oc is not None, "Open entry for manual crossing should exist after restart"
        assert oc.absorb_only is True, "Manual crossing must be absorb_only after restart"

    def test_edited_crossing_absorb_only_after_restart(self, tmp_path, monkeypatch):
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)
        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"

        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [])

        # Build a crossings.json with an edited crossing
        edited_crossing = {
            "crossing_id": "run1-101-9999",
            "run": "run1",
            "number": "101",
            "time": ts,
            "confidence": 0.9,
            "name": None,
            "category": "Unknown",
            "matched": False,
            "annotated_path": "run1/annotated/run1-101-9999.jpg",
            "last_seen": ts,
            "source": "auto",
            "edited": True,
            "deleted": False,
            "order_key": float(_epoch_ms(ts)),
            "order_overridden": False,
        }
        crossings_path = os.path.join(run_dir, "crossings.json")
        with open(crossings_path, "w") as fh:
            json.dump([edited_crossing], fh)

        orig_tracker = engine_mod.CandidateTracker
        orig_index = engine_mod.FramesIndex
        engine_mod.CandidateTracker = FakeCandidateTracker
        engine_mod.FramesIndex = FakeFramesIndex
        try:
            engine2 = asyncio.run(self._start_stop(tmp_path))
        finally:
            engine_mod.CandidateTracker = orig_tracker
            engine_mod.FramesIndex = orig_index

        oc = engine2._open.get(("run1", "101"))
        assert oc is not None
        assert oc.absorb_only is True, "Edited crossing must be absorb_only after restart"

    def test_deleted_crossing_absorb_only_after_restart(self, tmp_path, monkeypatch):
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)
        ts = "2026-07-17T10:00:00.000Z"

        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [])

        deleted_crossing = {
            "crossing_id": "run1-101-9999",
            "run": "run1",
            "number": "101",
            "time": ts,
            "confidence": 0.9,
            "name": None,
            "category": "Unknown",
            "matched": False,
            "annotated_path": "run1/annotated/run1-101-9999.jpg",
            "last_seen": ts,
            "source": "auto",
            "edited": False,
            "deleted": True,
            "order_key": float(_epoch_ms(ts)),
            "order_overridden": False,
        }
        crossings_path = os.path.join(run_dir, "crossings.json")
        with open(crossings_path, "w") as fh:
            json.dump([deleted_crossing], fh)

        orig_tracker = engine_mod.CandidateTracker
        orig_index = engine_mod.FramesIndex
        engine_mod.CandidateTracker = FakeCandidateTracker
        engine_mod.FramesIndex = FakeFramesIndex
        try:
            engine2 = asyncio.run(self._start_stop(tmp_path))
        finally:
            engine_mod.CandidateTracker = orig_tracker
            engine_mod.FramesIndex = orig_index

        oc = engine2._open.get(("run1", "101"))
        assert oc is not None
        assert oc.absorb_only is True, "Deleted crossing must be absorb_only after restart"

    def test_auto_crossing_not_absorb_only_after_restart(self, tmp_path, monkeypatch):
        """Auto crossings without edits/deletes must still fold normally after restart."""
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)
        ts = "2026-07-17T10:00:00.000Z"

        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [])

        auto_crossing = {
            "crossing_id": "run1-101-9999",
            "run": "run1",
            "number": "101",
            "time": ts,
            "confidence": 0.9,
            "name": None,
            "category": "Unknown",
            "matched": False,
            "annotated_path": "run1/annotated/run1-101-9999.jpg",
            "last_seen": ts,
            "source": "auto",
            "edited": False,
            "deleted": False,
            "order_key": float(_epoch_ms(ts)),
            "order_overridden": False,
        }
        crossings_path = os.path.join(run_dir, "crossings.json")
        with open(crossings_path, "w") as fh:
            json.dump([auto_crossing], fh)

        orig_tracker = engine_mod.CandidateTracker
        orig_index = engine_mod.FramesIndex
        engine_mod.CandidateTracker = FakeCandidateTracker
        engine_mod.FramesIndex = FakeFramesIndex
        try:
            engine2 = asyncio.run(self._start_stop(tmp_path))
        finally:
            engine_mod.CandidateTracker = orig_tracker
            engine_mod.FramesIndex = orig_index

        oc = engine2._open.get(("run1", "101"))
        assert oc is not None
        assert oc.absorb_only is False, "Auto crossing must NOT be absorb_only after restart"


# ---------------------------------------------------------------------------
# status: counts, processed_through, cached manifest
# ---------------------------------------------------------------------------

class TestStatus:
    """status() correctness and caching behavior."""

    def test_status_counts_correct(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        ts_base = "2026-07-17T10:00:{:02d}.000Z"
        # Write 5 manifest lines
        for i in range(5):
            rel = _write_frame(run_dir, f"frame_{i:03d}.jpg")
            entry = _make_manifest_entry(rel, ts_base.format(i * 10), seq=i)
            _append_manifest_line(run_dir, entry)

        # Write processed offset = 3
        from backend.engine import _write_offset_atomic
        _write_offset_atomic(run_dir, 3)

        result = eng.status("run1")
        assert result["run"] == "run1"
        assert result["enabled"] is True
        assert result["captured"] == 5
        assert result["processed"] == 3
        assert result["pending"] == 2
        assert result["state"] == "processing"

    def test_status_up_to_date_when_drained(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        ts = "2026-07-17T10:00:00.000Z"
        rel = _write_frame(run_dir, "frame_000.jpg")
        entry = _make_manifest_entry(rel, ts)
        _append_manifest_line(run_dir, entry)

        from backend.engine import _write_offset_atomic
        _write_offset_atomic(run_dir, 1)

        result = eng.status("run1")
        assert result["state"] == "up_to_date"
        assert result["pending"] == 0

    def test_processed_through_is_none_at_offset_zero(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        ts = "2026-07-17T10:00:00.000Z"
        rel = _write_frame(run_dir, "frame_000.jpg")
        _append_manifest_line(run_dir, _make_manifest_entry(rel, ts))

        result = eng.status("run1")
        assert result["processed_through"] is None

    def test_processed_through_is_last_processed_client_ts(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        ts1 = "2026-07-17T10:00:00.000Z"
        ts2 = "2026-07-17T10:00:10.000Z"
        ts3 = "2026-07-17T10:00:20.000Z"
        for i, (ts, fname) in enumerate([(ts1, "f0.jpg"), (ts2, "f1.jpg"), (ts3, "f2.jpg")]):
            rel = _write_frame(run_dir, fname)
            _append_manifest_line(run_dir, _make_manifest_entry(rel, ts, seq=i))

        from backend.engine import _write_offset_atomic
        _write_offset_atomic(run_dir, 2)  # processed lines 0 and 1

        result = eng.status("run1")
        assert result["processed_through"] == ts2  # last processed entry's client_ts

    def test_status_caches_manifest_stats(self, tmp_path):
        """NFR2: idle poll must not re-read manifest if (mtime, size) unchanged."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        ts = "2026-07-17T10:00:00.000Z"
        rel = _write_frame(run_dir, "frame_000.jpg")
        _append_manifest_line(run_dir, _make_manifest_entry(rel, ts))

        read_count = [0]
        original_read = engine_mod._read_manifest_lines

        def counting_read(run_dir):
            read_count[0] += 1
            return original_read(run_dir)

        engine_mod._read_manifest_lines = counting_read
        try:
            eng.status("run1")  # first call — reads manifest
            count_after_first = read_count[0]
            eng.status("run1")  # second call — should use cache
            count_after_second = read_count[0]
        finally:
            engine_mod._read_manifest_lines = original_read

        assert count_after_first == 1
        assert count_after_second == 1, (
            f"Manifest should be cached; read_count went from {count_after_first} "
            f"to {count_after_second}"
        )

    def test_status_candidates_open_count(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        # Add some candidates to the fake tracker
        ts = "2026-07-17T10:00:00.000Z"
        open_cand = Candidate(
            candidate_id="run1-cand-1000",
            run="run1",
            time=ts,
            last_seen=ts,
            frame_count=3,
            hint_number="101",
            hint_conf=0.6,
            rep_filename="run1/collected/f.jpg",
            rep_box=[0.0, 0.0, 10.0, 10.0],
            state="open",
        )
        dismissed_cand = Candidate(
            candidate_id="run1-cand-2000",
            run="run1",
            time=ts,
            last_seen=ts,
            frame_count=1,
            hint_number=None,
            hint_conf=0.0,
            rep_filename="run1/collected/f2.jpg",
            rep_box=[0.0, 0.0, 10.0, 10.0],
            state="dismissed",
        )
        fake_tracker.add_candidate(open_cand)
        fake_tracker.add_candidate(dismissed_cand)

        result = eng.status("run1")
        assert result["candidates_open"] == 1


# ---------------------------------------------------------------------------
# frame_path traversal guard
# ---------------------------------------------------------------------------

class TestFramePath:
    """frame_path rejects traversal attacks."""

    def test_valid_path_allowed(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(os.path.join(run_dir, "collected"), exist_ok=True)

        result = eng.frame_path("run1", "run1/collected/frame_000.jpg")
        expected = os.path.normpath(
            os.path.join(str(tmp_path), "run1", "collected", "frame_000.jpg")
        )
        assert result == expected

    def test_dotdot_path_rejected(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        result = eng.frame_path("run1", "run1/collected/../../../etc/passwd")
        assert result is None

    def test_absolute_path_rejected(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        result = eng.frame_path("run1", "/etc/passwd")
        assert result is None

    def test_other_run_path_rejected(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        # Valid path but under a different run's collected/ dir
        result = eng.frame_path("run1", "run2/collected/frame_000.jpg")
        assert result is None

    def test_annotated_path_rejected(self, tmp_path):
        """Annotated images are NOT under collected/ — must be rejected."""
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        result = eng.frame_path("run1", "run1/annotated/some_crossing.jpg")
        assert result is None


# ---------------------------------------------------------------------------
# Worker wiring: frames.append and candidates.observe
# ---------------------------------------------------------------------------

class TestWorkerWiring:
    """§4.4: _process_frame calls frames.append always and candidates.observe."""

    def _make_engine_and_run_frame(
        self,
        tmp_path,
        monkeypatch,
        pipeline_results,
        candidates_enabled=True,
        frames_index_enabled=True,
    ):
        live = _make_live(
            candidates_enabled=candidates_enabled,
            frames_index_enabled=frames_index_enabled,
        )
        eng, fake_tracker, fake_index = _make_engine_with_fakes(tmp_path, live=live)

        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)
        rel = _write_frame(run_dir, "frame_000.jpg")
        ts = "2026-07-17T10:00:00.000Z"
        entry = _make_manifest_entry(rel, ts)

        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: pipeline_results)
        eng._process_frame("run1", entry)

        return eng, fake_tracker, fake_index, entry, ts

    def test_frames_append_called_always(self, tmp_path, monkeypatch):
        """frames.append is called regardless of pipeline results."""
        _, _, fake_index, entry, ts = self._make_engine_and_run_frame(
            tmp_path, monkeypatch, []
        )
        assert len(fake_index.append_calls) == 1
        assert fake_index.append_calls[0]["run"] == "run1"

    def test_frames_append_not_called_when_disabled(self, tmp_path, monkeypatch):
        """frames_index_enabled=False ⇒ frames.append skipped."""
        _, _, fake_index, _, _ = self._make_engine_and_run_frame(
            tmp_path, monkeypatch, [], frames_index_enabled=False
        )
        assert len(fake_index.append_calls) == 0

    def test_candidates_observe_called_with_had_confident_true(self, tmp_path, monkeypatch):
        """had_confident=True when a confident result is present."""
        confident_result = _make_result("101", 0.9, "confident")
        _, fake_tracker, _, _, ts = self._make_engine_and_run_frame(
            tmp_path, monkeypatch, [confident_result]
        )
        assert len(fake_tracker.observe_calls) == 1
        obs = fake_tracker.observe_calls[0]
        assert obs["had_confident"] is True
        assert obs["ts"] == ts

    def test_candidates_observe_called_with_had_confident_false(self, tmp_path, monkeypatch):
        """had_confident=False when no confident results."""
        nr_result = _make_result("101", 0.55, "needs_review")
        _, fake_tracker, _, _, ts = self._make_engine_and_run_frame(
            tmp_path, monkeypatch, [nr_result]
        )
        assert len(fake_tracker.observe_calls) == 1
        obs = fake_tracker.observe_calls[0]
        assert obs["had_confident"] is False

    def test_candidates_observe_not_called_when_disabled(self, tmp_path, monkeypatch):
        """candidates_enabled=False ⇒ candidates.observe skipped."""
        confident_result = _make_result("101", 0.9, "confident")
        _, fake_tracker, _, _, _ = self._make_engine_and_run_frame(
            tmp_path, monkeypatch, [confident_result], candidates_enabled=False
        )
        assert len(fake_tracker.observe_calls) == 0

    def test_frames_append_receives_all_results(self, tmp_path, monkeypatch):
        """frames.append gets all pipeline results, not just confident ones."""
        results = [
            _make_result("101", 0.9, "confident"),
            _make_result("202", 0.55, "needs_review"),
        ]
        _, _, fake_index, _, _ = self._make_engine_and_run_frame(
            tmp_path, monkeypatch, results
        )
        assert len(fake_index.append_calls) == 1
        assert len(fake_index.append_calls[0]["results"]) == 2


# ---------------------------------------------------------------------------
# candidates() and resolve_candidate()
# ---------------------------------------------------------------------------

class TestCandidatesAndResolve:
    """candidates() and resolve_candidate() routing."""

    def _make_open_candidate(self, run: str, ts: str, number: str = "101") -> Candidate:
        return Candidate(
            candidate_id=f"{run}-cand-{_epoch_ms(ts)}",
            run=run,
            time=ts,
            last_seen=ts,
            frame_count=2,
            hint_number=number,
            hint_conf=0.7,
            rep_filename=f"{run}/collected/frame.jpg",
            rep_box=[0.0, 0.0, 10.0, 10.0],
            state="open",
        )

    def test_candidates_returns_all_states(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        ts = "2026-07-17T10:00:00.000Z"
        cand = self._make_open_candidate("run1", ts)
        fake_tracker.add_candidate(cand)

        run_id, cands = eng.candidates("run1")
        assert run_id == "run1"
        assert len(cands) == 1

    def test_resolve_candidate_dismiss(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        ts = "2026-07-17T10:00:00.000Z"
        cand = self._make_open_candidate("run1", ts)
        fake_tracker.add_candidate(cand)

        result = eng.resolve_candidate(cand.candidate_id, "dismiss")
        assert "candidate" in result
        assert "crossing" not in result
        assert result["candidate"]["state"] == "dismissed"

    def test_resolve_candidate_promote(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(run_dir, exist_ok=True)

        ts = "2026-07-17T10:00:00.000Z"
        # Write actual frame for the create_crossing call inside promote
        rel = _write_frame(run_dir, "frame.jpg")
        cand = Candidate(
            candidate_id="run1-cand-9999",
            run="run1",
            time=ts,
            last_seen=ts,
            frame_count=2,
            hint_number="101",
            hint_conf=0.7,
            rep_filename=rel,
            rep_box=[0.0, 0.0, 10.0, 10.0],
            state="open",
        )
        fake_tracker.add_candidate(cand)

        result = eng.resolve_candidate(cand.candidate_id, "promote", number="101")
        assert "candidate" in result
        assert "crossing" in result
        assert result["candidate"]["state"] == "promoted"
        cid = result["crossing"]["crossing_id"]
        assert result["candidate"]["promoted_crossing_id"] == cid

    def test_resolve_unknown_candidate_raises_keyerror(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        with pytest.raises(KeyError):
            eng.resolve_candidate("no-such-id", "dismiss")


# ---------------------------------------------------------------------------
# candidate_image_path traversal guard
# ---------------------------------------------------------------------------

class TestCandidateImagePath:
    """candidate_image_path uses same traversal guard as frame_path."""

    def test_valid_path_returned(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        run_dir = os.path.join(str(tmp_path), "run1")
        os.makedirs(os.path.join(run_dir, "collected"), exist_ok=True)

        ts = "2026-07-17T10:00:00.000Z"
        cand = Candidate(
            candidate_id="run1-cand-1000",
            run="run1",
            time=ts,
            last_seen=ts,
            frame_count=1,
            hint_number=None,
            hint_conf=0.0,
            rep_filename="run1/collected/frame.jpg",
            rep_box=[0.0, 0.0, 10.0, 10.0],
            state="open",
        )
        fake_tracker.add_candidate(cand)

        result = eng.candidate_image_path(cand.candidate_id)
        expected = os.path.normpath(
            os.path.join(str(tmp_path), "run1", "collected", "frame.jpg")
        )
        assert result == expected

    def test_traversal_attempt_rejected(self, tmp_path):
        eng, fake_tracker, _ = _make_engine_with_fakes(tmp_path)
        ts = "2026-07-17T10:00:00.000Z"
        cand = Candidate(
            candidate_id="run1-cand-1000",
            run="run1",
            time=ts,
            last_seen=ts,
            frame_count=1,
            hint_number=None,
            hint_conf=0.0,
            rep_filename="run1/collected/../../../etc/passwd",
            rep_box=[0.0, 0.0, 10.0, 10.0],
            state="open",
        )
        fake_tracker.add_candidate(cand)

        result = eng.candidate_image_path(cand.candidate_id)
        assert result is None

    def test_unknown_candidate_returns_none(self, tmp_path):
        eng, _, _ = _make_engine_with_fakes(tmp_path)
        assert eng.candidate_image_path("no-such-id") is None
