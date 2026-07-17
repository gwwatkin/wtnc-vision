"""Tests for ResultsEngine — Task 2.

No real inference: engine.pipeline.run is monkeypatched to return canned
CrossingResult objects.  Frames are tiny cv2.imwrite'd arrays in tmp_path-built
run dirs; manifest lines are written by the test itself (root-relative filenames).

Coverage:
  - Dedup: repeated reads within window → one crossing; after window → new crossing
  - Distinct numbers → distinct crossings
  - Better-confidence fold updates confidence + annotated file; time unchanged
  - crossings.csv gains one row per crossing; crossings.json matches memory;
    processed_offset equals lines consumed
  - Poison frame → logged, offset advances, later lines still process (FR6)
  - Restart: new engine resumes from offset, reloads crossings,
    read within window of persisted last_seen does NOT open a duplicate
  - needs_review / rejected results produce nothing (FR7)
  - Roster enrichment: number in roster → name/category + matched=True;
    absent → name=None, category="Unknown", matched=False
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

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

from backend.engine import ResultsEngine, _epoch_ms, _ts_seconds
from backend.live_config import LiveConfig
from backend.results_models import Crossing
from backend.rosters import EMPTY_ROSTER, Roster


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_live(dedup_window_s: float = 5.0) -> LiveConfig:
    """Minimal LiveConfig for tests — cv_config_path unused (pipeline is mocked)."""
    return LiveConfig(
        enabled=True,
        cv_config_path="/dev/null",  # unused — pipeline is monkeypatched
        dedup_window_s=dedup_window_s,
        statuses=("confident",),
    )


def _make_cv_cfg() -> dict:
    """Minimal cv_cfg dict that satisfies engine._process_frame."""
    return {
        "validate": {"roster": None, "accept_unmatched": True},
        "score": {"confidence_threshold": 0.60},
    }


def _make_tiny_image() -> np.ndarray:
    """Return a tiny 10×10 black BGR image for test frames."""
    return np.zeros((10, 10, 3), dtype=np.uint8)


def _write_frame(run_dir: str, name: str) -> str:
    """Write a tiny JPEG under <run_dir>/collected/<name> and return root-relative path."""
    collected_dir = os.path.join(run_dir, "collected")
    os.makedirs(collected_dir, exist_ok=True)
    abs_path = os.path.join(collected_dir, name)
    cv2.imwrite(abs_path, _make_tiny_image())
    # root-relative = <run_name>/collected/<name>
    run_name = os.path.basename(run_dir)
    return f"{run_name}/collected/{name}"


def _append_manifest_line(run_dir: str, entry: dict) -> None:
    """Append a JSON line to <run_dir>/manifest.jsonl."""
    manifest_path = os.path.join(run_dir, "manifest.jsonl")
    with open(manifest_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _make_manifest_entry(rel_filename: str, client_ts: str, seq: int = 0) -> dict:
    """Build a minimal manifest entry dict."""
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


def _make_result(number: str, conf: float, status: str = "confident") -> CrossingResult:
    """Build a minimal CrossingResult."""
    return CrossingResult(
        number=number,
        raw_text=number,
        confidence=conf,
        status=status,
        rider_box=(0.0, 0.0, 5.0, 5.0),
        crop_path=None,
    )


def _setup_run(tmp_path, run_name: str):
    """Create a run directory and return (engine, run_dir)."""
    run_dir = os.path.join(str(tmp_path), run_name)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _make_engine(tmp_path) -> ResultsEngine:
    """Create a ResultsEngine backed by tmp_path."""
    live = _make_live()
    cv_cfg = _make_cv_cfg()
    return ResultsEngine(live, cv_cfg, str(tmp_path))


# ---------------------------------------------------------------------------
# Direct _fold / _process_frame tests (no asyncio needed)
# ---------------------------------------------------------------------------

class TestFoldDedup:
    """Dedup logic within and across the window."""

    def test_single_read_creates_one_crossing(self, tmp_path):
        engine = _make_engine(tmp_path)
        run_dir = _setup_run(tmp_path, "run1")

        ts = "2026-07-17T10:00:00.000Z"
        img = _make_tiny_image()
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        assert len(engine._crossings.get("run1", [])) == 1
        c = engine._crossings["run1"][0]
        assert c.number == "101"
        assert c.confidence == pytest.approx(0.95)
        assert c.time == ts
        assert c.last_seen == ts

    def test_repeated_reads_within_window_collapse_to_one_crossing(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:02.000Z"  # 2 s later, within 5 s window
        t3 = "2026-07-17T10:00:04.000Z"  # 4 s later, still within window

        engine._fold("run1", "101", 0.90, t1, img, [_make_result("101", 0.90)])
        engine._fold("run1", "101", 0.88, t2, img, [_make_result("101", 0.88)])
        engine._fold("run1", "101", 0.92, t3, img, [_make_result("101", 0.92)])

        crossings = engine._crossings.get("run1", [])
        assert len(crossings) == 1, f"Expected 1 crossing, got {len(crossings)}"
        c = crossings[0]
        # time is first-seen (OQ2)
        assert c.time == t1
        # confidence should reflect the best (0.92)
        assert c.confidence == pytest.approx(0.92)

    def test_read_after_window_creates_second_crossing(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:06.000Z"  # 6 s later — beyond 5 s window

        engine._fold("run1", "101", 0.95, t1, img, [_make_result("101", 0.95)])
        engine._fold("run1", "101", 0.90, t2, img, [_make_result("101", 0.90)])

        crossings = engine._crossings.get("run1", [])
        assert len(crossings) == 2, f"Expected 2 crossings, got {len(crossings)}"
        times = {c.time for c in crossings}
        assert t1 in times
        assert t2 in times

    def test_distinct_numbers_create_distinct_crossings(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])
        engine._fold("run1", "202", 0.88, ts, img, [_make_result("202", 0.88)])

        crossings = engine._crossings.get("run1", [])
        assert len(crossings) == 2
        numbers = {c.number for c in crossings}
        assert numbers == {"101", "202"}

    def test_same_number_different_runs_are_isolated(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "runA")
        _setup_run(tmp_path, "runB")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("runA", "101", 0.95, ts, img, [_make_result("101", 0.95)])
        engine._fold("runB", "101", 0.92, ts, img, [_make_result("101", 0.92)])

        # Two separate crossings — one per run
        assert len(engine._crossings.get("runA", [])) == 1
        assert len(engine._crossings.get("runB", [])) == 1


class TestFoldBetterConfidence:
    """Better-confidence fold updates confidence + annotated file; time unchanged."""

    def test_better_confidence_updates_confidence(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:01.000Z"

        engine._fold("run1", "101", 0.80, t1, img, [_make_result("101", 0.80)])
        engine._fold("run1", "101", 0.95, t2, img, [_make_result("101", 0.95)])

        c = engine._crossings["run1"][0]
        assert c.confidence == pytest.approx(0.95)
        assert c.time == t1, "time must remain first-seen (OQ2)"

    def test_lower_confidence_does_not_update(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:01.000Z"

        engine._fold("run1", "101", 0.95, t1, img, [_make_result("101", 0.95)])
        engine._fold("run1", "101", 0.70, t2, img, [_make_result("101", 0.70)])

        c = engine._crossings["run1"][0]
        assert c.confidence == pytest.approx(0.95), "Lower confidence must NOT overwrite"

    def test_better_confidence_updates_annotated_file(self, tmp_path):
        """Re-render replaces the annotated file (mtime changes)."""
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:01.000Z"

        engine._fold("run1", "101", 0.80, t1, img, [_make_result("101", 0.80)])
        c = engine._crossings["run1"][0]
        annotated_abs = os.path.join(str(tmp_path), c.annotated_path)
        assert os.path.isfile(annotated_abs)
        mtime_before = os.path.getmtime(annotated_abs)

        # Small sleep to ensure mtime difference is detectable
        import time; time.sleep(0.05)

        engine._fold("run1", "101", 0.95, t2, img, [_make_result("101", 0.95)])
        mtime_after = os.path.getmtime(annotated_abs)
        assert mtime_after > mtime_before, "Annotated file should have been rewritten"


class TestPersistence:
    """crossings.csv, crossings.json, processed_offset."""

    def test_crossings_csv_one_row_per_crossing(self, tmp_path):
        engine = _make_engine(tmp_path)
        run_dir = _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:06.000Z"  # beyond window → new crossing

        engine._fold("run1", "101", 0.95, t1, img, [_make_result("101", 0.95)])
        engine._fold("run1", "101", 0.90, t2, img, [_make_result("101", 0.90)])

        csv_path = os.path.join(run_dir, "crossings.csv")
        assert os.path.isfile(csv_path)
        with open(csv_path, "r", encoding="utf-8") as fh:
            rows = [l.strip() for l in fh if l.strip()]
        assert len(rows) == 2, f"Expected 2 CSV rows, got {len(rows)}: {rows}"

    def test_crossings_json_matches_memory(self, tmp_path):
        engine = _make_engine(tmp_path)
        run_dir = _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        json_path = os.path.join(run_dir, "crossings.json")
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        assert len(data) == 1
        in_memory = engine._crossings["run1"][0]
        assert data[0]["crossing_id"] == in_memory.crossing_id
        assert data[0]["number"] == in_memory.number
        assert data[0]["confidence"] == pytest.approx(in_memory.confidence)

    def test_annotated_image_written_on_new_crossing(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        c = engine._crossings["run1"][0]
        annotated_abs = os.path.join(str(tmp_path), c.annotated_path)
        assert os.path.isfile(annotated_abs), f"Annotated image not found: {annotated_abs}"


async def _run_engine(tmp_path_str, monkeypatch_fn=None) -> ResultsEngine:
    """Start and stop an engine within a single event loop. Return the stopped engine."""
    live = _make_live()
    cv_cfg = _make_cv_cfg()
    engine = ResultsEngine(live, cv_cfg, tmp_path_str)
    if monkeypatch_fn:
        monkeypatch_fn(engine)
    await engine.start()
    # Give the worker a chance to drain the queue before stopping
    await asyncio.sleep(0.1)
    await engine.stop()
    return engine


class TestProcessedOffset:
    """processed_offset advances per line (success and poison)."""

    def test_offset_advances_per_successful_line(self, tmp_path, monkeypatch):
        """After processing N lines the offset file holds N."""
        run = "run1"
        run_dir = _setup_run(tmp_path, run)

        # Write 3 frame files + manifest lines
        ts_base = "2026-07-17T10:00:{:02d}.000Z"
        for i in range(3):
            rel = _write_frame(run_dir, f"frame_{i:03d}.jpg")
            entry = _make_manifest_entry(rel, ts_base.format(i * 10), seq=i)
            _append_manifest_line(run_dir, entry)

        # Monkeypatch pipeline.run to return an empty list (no confident reads)
        import backend.engine as engine_mod
        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [])

        asyncio.run(_run_engine(str(tmp_path)))

        offset_path = os.path.join(run_dir, "processed_offset")
        assert os.path.isfile(offset_path)
        with open(offset_path, "r") as fh:
            assert int(fh.read().strip()) == 3

    def test_poison_frame_offset_advances_and_later_lines_process(
        self, tmp_path, monkeypatch
    ):
        """A missing/corrupt frame file is logged and the offset still advances (FR6)."""
        run = "run1"
        run_dir = _setup_run(tmp_path, run)

        # Line 0: valid frame
        rel0 = _write_frame(run_dir, "frame_000.jpg")
        entry0 = _make_manifest_entry(rel0, "2026-07-17T10:00:00.000Z", seq=0)
        _append_manifest_line(run_dir, entry0)

        # Line 1: poison — file does not exist
        entry1 = _make_manifest_entry(
            f"{run}/collected/MISSING_FILE.jpg", "2026-07-17T10:00:05.000Z", seq=1
        )
        _append_manifest_line(run_dir, entry1)

        # Line 2: valid frame
        rel2 = _write_frame(run_dir, "frame_002.jpg")
        entry2 = _make_manifest_entry(rel2, "2026-07-17T10:00:10.000Z", seq=2)
        _append_manifest_line(run_dir, entry2)

        processed_lines = []

        import backend.engine as engine_mod

        def fake_pipeline(img, cfg):
            processed_lines.append(id(img))
            return []

        monkeypatch.setattr(engine_mod.pipeline, "run", fake_pipeline)

        asyncio.run(_run_engine(str(tmp_path)))

        # Offset should be 3 (all lines consumed — poison + skipped)
        offset_path = os.path.join(run_dir, "processed_offset")
        with open(offset_path, "r") as fh:
            assert int(fh.read().strip()) == 3

        # Pipeline was called for the two good frames (not the missing one)
        assert len(processed_lines) == 2


class TestWorkerWithPipeline:
    """Full worker loop with monkeypatched pipeline.run."""

    def test_confident_results_create_crossings(self, tmp_path, monkeypatch):
        run = "run1"
        run_dir = _setup_run(tmp_path, run)

        rel = _write_frame(run_dir, "frame_000.jpg")
        entry = _make_manifest_entry(rel, "2026-07-17T10:00:00.000Z")
        _append_manifest_line(run_dir, entry)

        result = _make_result("101", 0.95, "confident")

        import backend.engine as engine_mod
        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [result])

        engine = asyncio.run(_run_engine(str(tmp_path)))

        crossings = engine._crossings.get(run, [])
        assert len(crossings) == 1
        assert crossings[0].number == "101"

    def test_needs_review_and_rejected_produce_nothing(self, tmp_path, monkeypatch):
        """Statuses not in live.statuses must not create crossings (FR7)."""
        run = "run1"
        run_dir = _setup_run(tmp_path, run)

        rel = _write_frame(run_dir, "frame_000.jpg")
        entry = _make_manifest_entry(rel, "2026-07-17T10:00:00.000Z")
        _append_manifest_line(run_dir, entry)

        results = [
            _make_result("101", 0.55, "needs_review"),
            _make_result("202", 0.20, "rejected"),
        ]

        import backend.engine as engine_mod
        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: results)

        engine = asyncio.run(_run_engine(str(tmp_path)))

        crossings = engine._crossings.get(run, [])
        assert len(crossings) == 0, (
            f"needs_review/rejected must NOT become crossings, got {crossings}"
        )

    def test_notify_triggers_processing(self, tmp_path, monkeypatch):
        """engine.notify() wakes the worker even when called after start."""
        run = "run1"
        run_dir = _setup_run(tmp_path, run)

        import backend.engine as engine_mod
        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [])

        async def _run():
            live = _make_live()
            cv_cfg = _make_cv_cfg()
            engine = ResultsEngine(live, cv_cfg, str(tmp_path))
            await engine.start()
            # Now add a frame to an empty run and notify
            rel = _write_frame(run_dir, "frame_000.jpg")
            entry = _make_manifest_entry(rel, "2026-07-17T10:00:00.000Z")
            _append_manifest_line(run_dir, entry)
            engine.notify(run)
            # Give the worker a moment to drain
            await asyncio.sleep(0.2)
            await engine.stop()
            return engine

        engine = asyncio.run(_run())

        offset_path = os.path.join(run_dir, "processed_offset")
        assert os.path.isfile(offset_path)
        with open(offset_path, "r") as fh:
            assert int(fh.read().strip()) == 1


class TestRestart:
    """New engine over same dirs resumes correctly."""

    def test_restart_resumes_from_offset(self, tmp_path, monkeypatch):
        """After stop+restart, the engine does NOT reprocess already-done lines."""
        run = "run1"
        run_dir = _setup_run(tmp_path, run)

        # Write 2 manifest lines
        for i in range(2):
            rel = _write_frame(run_dir, f"frame_{i:03d}.jpg")
            entry = _make_manifest_entry(rel, f"2026-07-17T10:00:{i * 10:02d}.000Z", seq=i)
            _append_manifest_line(run_dir, entry)

        processed_count = [0]

        import backend.engine as engine_mod

        def counting_pipeline(img, cfg):
            processed_count[0] += 1
            return []

        monkeypatch.setattr(engine_mod.pipeline, "run", counting_pipeline)

        # First run: process both lines
        asyncio.run(_run_engine(str(tmp_path)))
        assert processed_count[0] == 2

        # Second run: should not reprocess anything
        processed_count[0] = 0
        asyncio.run(_run_engine(str(tmp_path)))
        assert processed_count[0] == 0, (
            f"Engine should skip already-processed lines; reprocessed {processed_count[0]}"
        )

    def test_restart_reloads_crossings(self, tmp_path, monkeypatch):
        """After restart, crossings from disk are back in memory."""
        run = "run1"
        run_dir = _setup_run(tmp_path, run)

        rel = _write_frame(run_dir, "frame_000.jpg")
        entry = _make_manifest_entry(rel, "2026-07-17T10:00:00.000Z")
        _append_manifest_line(run_dir, entry)

        result = _make_result("101", 0.95, "confident")

        import backend.engine as engine_mod
        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [result])

        # First run creates the crossing
        engine1 = asyncio.run(_run_engine(str(tmp_path)))
        assert len(engine1._crossings.get(run, [])) == 1

        # Second run (no new frames) — crossing must be reloaded
        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [])
        engine2 = asyncio.run(_run_engine(str(tmp_path)))
        crossings = engine2._crossings.get(run, [])
        assert len(crossings) == 1, "Crossing should be reloaded from disk on restart"
        assert crossings[0].number == "101"

    def test_restart_read_within_window_no_duplicate(self, tmp_path, monkeypatch):
        """After restart, a read within the persisted last_seen window is NOT a duplicate."""
        run = "run1"
        run_dir = _setup_run(tmp_path, run)

        t1 = "2026-07-17T10:00:00.000Z"
        t2 = "2026-07-17T10:00:02.000Z"  # within 5 s window

        # Frame 0 processed in engine1
        rel0 = _write_frame(run_dir, "frame_000.jpg")
        entry0 = _make_manifest_entry(rel0, t1, seq=0)
        _append_manifest_line(run_dir, entry0)

        result = _make_result("101", 0.90, "confident")

        import backend.engine as engine_mod
        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [result])

        engine1 = asyncio.run(_run_engine(str(tmp_path)))
        assert len(engine1._crossings.get(run, [])) == 1

        # Frame 1: within window — added to manifest after engine1 stops
        rel1 = _write_frame(run_dir, "frame_001.jpg")
        entry1 = _make_manifest_entry(rel1, t2, seq=1)
        _append_manifest_line(run_dir, entry1)

        result2 = _make_result("101", 0.95, "confident")
        monkeypatch.setattr(engine_mod.pipeline, "run", lambda img, cfg: [result2])

        engine2 = asyncio.run(_run_engine(str(tmp_path)))

        crossings = engine2._crossings.get(run, [])
        assert len(crossings) == 1, (
            f"Within-window read after restart should NOT open a new crossing; got {len(crossings)}"
        )
        # Confidence should have been updated to the better value
        assert crossings[0].confidence == pytest.approx(0.95)


class TestRosterEnrichment:
    """Roster enrichment: matched / unmatched (stub or monkeypatched rosters.get)."""

    def test_number_in_roster_matched_true(self, tmp_path, monkeypatch):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        # Stub self._rosters.get to return a roster containing "101"
        test_roster = Roster(
            numbers=frozenset({"101"}),
            entries={"101": ("Alice Smith", "Cat 3")},
        )
        monkeypatch.setattr(engine._rosters, "get", lambda run: test_roster)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        c = engine._crossings["run1"][0]
        assert c.matched is True
        assert c.name == "Alice Smith"
        assert c.category == "Cat 3"

    def test_number_absent_from_roster_matched_false(self, tmp_path, monkeypatch):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        # Roster has OTHER numbers but not "202"
        test_roster = Roster(
            numbers=frozenset({"101"}),
            entries={"101": ("Alice Smith", "Cat 3")},
        )
        monkeypatch.setattr(engine._rosters, "get", lambda run: test_roster)

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("run1", "202", 0.90, ts, img, [_make_result("202", 0.90)])

        c = engine._crossings["run1"][0]
        assert c.matched is False
        assert c.name is None
        assert c.category == "Unknown"

    def test_empty_roster_produces_unmatched(self, tmp_path):
        """No roster uploaded → all numbers are unmatched (FR20 / confidence-only)."""
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        c = engine._crossings["run1"][0]
        assert c.matched is False
        assert c.name is None
        assert c.category == "Unknown"


class TestCrossingsAndAnnotatedPath:
    """crossings() and annotated_path() public methods."""

    def test_crossings_returns_empty_for_unknown_run(self, tmp_path):
        engine = _make_engine(tmp_path)
        run_id, crossings = engine.crossings("no-such-run")
        assert run_id == "no-such-run"
        assert crossings == []

    def test_crossings_returns_snapshot(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        run_id, snapshot = engine.crossings("run1")
        assert run_id == "run1"
        assert len(snapshot) == 1

    def test_annotated_path_resolves_via_index(self, tmp_path):
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        c = engine._crossings["run1"][0]
        result = engine.annotated_path(c.crossing_id)
        assert result is not None
        assert os.path.isabs(result)
        assert os.path.isfile(result)

    def test_annotated_path_unknown_id_returns_none(self, tmp_path):
        engine = _make_engine(tmp_path)
        assert engine.annotated_path("no-such-id-12345") is None

    def test_crossings_label_normalized(self, tmp_path):
        """crossings() normalizes the label via safe_label (e.g. spaces → dashes)."""
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "lap-1")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"
        engine._fold("lap-1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        run_id, snapshot = engine.crossings("Lap 1")
        assert run_id == "lap-1"
        assert len(snapshot) == 1


class TestIdempotency:
    """Replaying the same manifest line converges to the same state."""

    def test_replay_does_not_create_duplicate_crossing(self, tmp_path):
        """Same crossing_id → same outcome (idempotent fold), §5."""
        engine = _make_engine(tmp_path)
        _setup_run(tmp_path, "run1")

        img = _make_tiny_image()
        ts = "2026-07-17T10:00:00.000Z"

        # Fold the same read twice (simulates replay after a crash before offset write)
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])
        engine._fold("run1", "101", 0.95, ts, img, [_make_result("101", 0.95)])

        # Both folds have same ts → same crossing_id → collapse into one
        crossings = engine._crossings.get("run1", [])
        assert len(crossings) == 1, (
            f"Replay of same frame within window must produce only 1 crossing; got {len(crossings)}"
        )
