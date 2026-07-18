"""test_review_integration.py — Wave-C real-collaborator integration test.

Tests the full stack with real CandidateTracker + real FramesIndex over a
scripted frame sequence (canned pipeline.run). No fakes for those collaborators.

Coverage per task9.md step 1:
  - Burst of needs_review frames → one open candidate in GET /candidates (SC2 half).
  - Promote via POST /candidates/{id}/resolve → manual-provenance crossing in
    GET /results, candidate state promoted (SC2 full).
  - A confident fold near a second candidate suppresses it (SC7 half).
  - Absorb-only reconciliation: create_crossing with number N, then a late
    confident read of N → last_seen bumped, no duplicate crossing.
  - restart rebuild of absorb state: manual crossing survives restart as absorb_only.
  - status endpoint: captured/processed/pending counts.
  - frames endpoint: windowing returns frames in the window.

Asyncio pattern: all start/sleep/stop calls happen within a single asyncio.run()
call (same as test_engine.py's _run_engine helper) — running start then stop in
separate asyncio.run() calls triggers CancelledError because to_thread futures
outlive their event loop.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
from datetime import datetime, timezone, timedelta
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

from rider_id.types import CrossingResult

import backend.engine as engine_mod
from backend.engine import ResultsEngine, _epoch_ms, _ts_seconds
from backend.live_config import LiveConfig
from backend.results_models import Candidate, Crossing, _OpenCrossing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_live(
    dedup_window_s: float = 5.0,
    candidate_window_s: float = 5.0,
    candidates_enabled: bool = True,
    frames_index_enabled: bool = True,
    min_det_conf: float = 0.0,
) -> LiveConfig:
    return LiveConfig(
        enabled=True,
        cv_config_path="/dev/null",
        dedup_window_s=dedup_window_s,
        statuses=("confident",),
        candidates_enabled=candidates_enabled,
        candidate_statuses=("needs_review", "rejected"),
        candidate_window_s=candidate_window_s,
        candidate_min_det_conf=min_det_conf,
        frames_index_enabled=frames_index_enabled,
    )


def _make_cv_cfg() -> dict:
    return {
        "validate": {"roster": None, "accept_unmatched": True},
        "score": {"confidence_threshold": 0.60},
    }


def _make_tiny_jpeg(run_dir: str, name: str) -> str:
    """Write a tiny JPEG under <run_dir>/collected/<name>; return root-relative path."""
    collected_dir = os.path.join(run_dir, "collected")
    os.makedirs(collected_dir, exist_ok=True)
    abs_path = os.path.join(collected_dir, name)
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    cv2.imwrite(abs_path, img)
    run_name = os.path.basename(run_dir)
    return f"{run_name}/collected/{name}"


def _manifest_entry(rel_filename: str, client_ts: str, seq: int = 0) -> dict:
    return {
        "filename": rel_filename,
        "client_ts": client_ts,
        "seq": seq,
        "label": rel_filename.split("/")[0],
        "safe_label": rel_filename.split("/")[0],
        "session_id": "itest",
        "server_ts": client_ts,
        "bytes": 4,
        "content_type": "image/jpeg",
    }


def _append_manifest(run_dir: str, entry: dict) -> None:
    with open(os.path.join(run_dir, "manifest.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _result(number: str | None, conf: float, status: str,
            det_conf: float = 0.9) -> CrossingResult:
    return CrossingResult(
        number=number,
        raw_text=number,
        confidence=conf,
        status=status,
        rider_box=(0.0, 0.0, 50.0, 50.0),
        crop_path=None,
        det_conf=det_conf,
    )


def _ts(base: datetime, delta_s: float) -> str:
    return (base + timedelta(seconds=delta_s)).isoformat()


async def _run(engine: ResultsEngine, *, extra_sleep: float = 0.1) -> None:
    """Start the engine, wait for the worker to drain, then stop.

    All within one event loop — matching the pattern in test_engine.py's
    _run_engine helper. Running start/stop in separate asyncio.run() calls
    causes CancelledError because to_thread futures outlive their loop.
    """
    await engine.start()
    await asyncio.sleep(extra_sleep)
    await engine.stop()


# ---------------------------------------------------------------------------
# SC2 integration: needs_review burst → candidate → promote → crossing
# ---------------------------------------------------------------------------

class TestCandidateFlowIntegration:
    """Real CandidateTracker + real FramesIndex: needs_review burst through promotion."""

    def test_needs_review_burst_creates_one_candidate(self, tmp_path):
        """Three consecutive needs_review frames → exactly one open candidate."""
        run = "itest-sc2"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Write 3 frames; all needs_review within the 5 s window
        frames = [
            (_make_tiny_jpeg(run_dir, f"f{i:02d}.jpg"), _ts(base, i))
            for i in range(3)
        ]
        for (fn, ts), seq in zip(frames, range(3)):
            _append_manifest(run_dir, _manifest_entry(fn, ts, seq))

        # All frames return needs_review for the same rider
        canned_results = [
            [_result("128", 0.45, "needs_review", det_conf=0.8)],
            [_result("128", 0.48, "needs_review", det_conf=0.8)],
            [_result("128", 0.51, "needs_review", det_conf=0.8)],
        ]
        call_count = [0]

        def fake_run(img, cfg):
            idx = call_count[0]
            call_count[0] += 1
            return canned_results[idx] if idx < len(canned_results) else []

        live = _make_live(min_det_conf=0.5)
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        with patch.object(engine_mod.pipeline, "run", side_effect=fake_run):
            asyncio.run(_run(engine))

        # No confident crossings
        _, crossings = engine.crossings(run)
        assert crossings == [], "no confident crossings expected"

        # Exactly one open candidate
        _, cands = engine.candidates(run)
        open_cands = [c for c in cands if c.state == "open"]
        assert len(open_cands) == 1, f"expected 1 open candidate, got {len(open_cands)}"

        cand = open_cands[0]
        assert cand.run == run
        assert cand.frame_count == 3
        assert cand.hint_number == "128"

    def test_promote_candidate_creates_crossing(self, tmp_path):
        """Promote an open candidate → manual-provenance crossing; candidate promoted."""
        run = "itest-sc2-promote"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        fn = _make_tiny_jpeg(run_dir, "frame01.jpg")
        ts = _ts(base, 0)
        _append_manifest(run_dir, _manifest_entry(fn, ts, 0))

        canned = [[_result("99", 0.4, "needs_review", det_conf=0.9)]]
        call_count = [0]

        def fake_run(img, cfg):
            idx = call_count[0]
            call_count[0] += 1
            return canned[idx] if idx < len(canned) else []

        live = _make_live(min_det_conf=0.0)
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        with patch.object(engine_mod.pipeline, "run", side_effect=fake_run):
            asyncio.run(_run(engine))

        # Verify open candidate exists
        _, cands = engine.candidates(run)
        open_cands = [c for c in cands if c.state == "open"]
        assert len(open_cands) == 1
        cand_id = open_cands[0].candidate_id

        # Promote the candidate
        result = engine.resolve_candidate(cand_id, "promote", number="99")
        assert "crossing" in result
        assert "candidate" in result
        assert result["candidate"]["state"] == "promoted"
        assert result["candidate"]["promoted_crossing_id"] is not None

        # Crossing appears in /results with manual source
        _, crossings = engine.crossings(run)
        assert len(crossings) == 1
        c = crossings[0]
        assert c.source == "manual"
        assert c.number == "99"

        # Candidate is now promoted
        _, cands_after = engine.candidates(run)
        promoted = [c for c in cands_after if c.state == "promoted"]
        assert len(promoted) == 1

    def test_confident_fold_suppresses_nearby_candidate(self, tmp_path):
        """Confident fold near an open candidate → candidate suppressed (SC7 half)."""
        run = "itest-sc7-suppress"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Frame 0: needs_review → opens a candidate at t=0
        # Frame 1: confident at t=3 (within 5 s window) → should suppress
        frames = [
            (_make_tiny_jpeg(run_dir, "f00.jpg"), _ts(base, 0)),
            (_make_tiny_jpeg(run_dir, "f01.jpg"), _ts(base, 3)),
        ]
        for (fn, ts), seq in zip(frames, range(2)):
            _append_manifest(run_dir, _manifest_entry(fn, ts, seq))

        canned = [
            [_result(None, 0.0, "needs_review", det_conf=0.9)],
            [_result("42", 0.95, "confident", det_conf=0.95)],
        ]
        call_count = [0]

        def fake_run(img, cfg):
            idx = call_count[0]
            call_count[0] += 1
            return canned[idx] if idx < len(canned) else []

        live = _make_live(min_det_conf=0.0)
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        with patch.object(engine_mod.pipeline, "run", side_effect=fake_run):
            asyncio.run(_run(engine))

        # Confident crossing exists
        _, crossings = engine.crossings(run)
        assert len(crossings) == 1
        assert crossings[0].number == "42"

        # Candidate was suppressed, not open
        _, cands = engine.candidates(run)
        assert all(c.state != "open" for c in cands), \
            f"candidate still open: {[c.state for c in cands]}"
        suppressed = [c for c in cands if c.state == "suppressed"]
        assert len(suppressed) == 1, "expected exactly 1 suppressed candidate"


# ---------------------------------------------------------------------------
# Absorb-only reconciliation
# ---------------------------------------------------------------------------

class TestAbsorbOnlyIntegration:
    """Manual crossing + late confident read of same number must not duplicate."""

    def test_manual_crossing_absorbs_late_confident_read(self, tmp_path):
        """create_crossing(N) → absorb-only entry; a late confident read of N
        within the window bumps last_seen but does NOT create a second crossing."""
        run = "itest-absorb"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        ts0 = _ts(base, 0)
        ts1 = _ts(base, 2)  # within 5 s dedup window

        fn0 = _make_tiny_jpeg(run_dir, "f0.jpg")
        fn1 = _make_tiny_jpeg(run_dir, "f1.jpg")

        # Only fn1 goes through the worker (fn0 is the manual-crossing frame)
        _append_manifest(run_dir, _manifest_entry(fn1, ts1, 0))

        canned = [[_result("77", 0.9, "confident")]]
        call_count = [0]

        def fake_run(img, cfg):
            idx = call_count[0]
            call_count[0] += 1
            return canned[idx] if idx < len(canned) else []

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        # Create the manual crossing BEFORE the worker runs (before start)
        # We need the engine to be initialized but not started yet.
        # Pre-create the crossing using direct internal call (engine not started),
        # then run the worker which should absorb the confident read.
        async def _run_with_manual():
            await engine.start()
            # The worker will process fn1 and see confident "77".
            # We pre-create a manual crossing so the absorb-only entry exists.
            # But we need to create it before the worker processes fn1.
            # The engine is now started; the worker is running.
            # Create crossing synchronously (thread-safe via lock).
            engine.create_crossing(run, fn0, ts0, "77")
            await asyncio.sleep(0.2)
            await engine.stop()

        with patch.object(engine_mod.pipeline, "run", side_effect=fake_run):
            asyncio.run(_run_with_manual())

        # Should have exactly ONE crossing (the manual one, worker's read absorbed)
        _, crossings = engine.crossings(run)
        assert len(crossings) == 1, \
            f"expected 1 crossing (absorbed), got {len(crossings)}: {crossings}"
        assert crossings[0].source == "manual"
        assert crossings[0].number == "77"

    def test_absorb_state_survives_restart(self, tmp_path):
        """After engine restart, a manual crossing's absorb-only flag is rebuilt."""
        run = "itest-restart"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ts0 = _ts(base, 0)
        fn0 = _make_tiny_jpeg(run_dir, "f0.jpg")

        live = _make_live()

        async def _first_run():
            engine1 = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))
            with patch.object(engine_mod.pipeline, "run", return_value=[]):
                await engine1.start()
                engine1.create_crossing(run, fn0, ts0, "55")
                await asyncio.sleep(0.05)
                await engine1.stop()
            return engine1

        asyncio.run(_first_run())

        # Restart with a fresh engine
        engine2 = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        async def _second_run():
            with patch.object(engine_mod.pipeline, "run", return_value=[]):
                await engine2.start()
                await asyncio.sleep(0.05)
                await engine2.stop()

        asyncio.run(_second_run())

        # The open-crossing entry for (run, "55") should have absorb_only=True
        key = (run, "55")
        oc = engine2._open.get(key)
        assert oc is not None, f"no open entry for {key}"
        assert oc.absorb_only is True, \
            f"expected absorb_only=True after restart, got {oc.absorb_only}"


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------

class TestStatusIntegration:
    """Real engine: status counts match manifest and offset."""

    def test_status_counts_fully_processed(self, tmp_path):
        """status() returns captured==processed==5, pending==0 after full drain."""
        run = "itest-status"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Write 5 manifest entries
        for i in range(5):
            fn = _make_tiny_jpeg(run_dir, f"f{i:02d}.jpg")
            ts = _ts(base, i)
            _append_manifest(run_dir, _manifest_entry(fn, ts, i))

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        with patch.object(engine_mod.pipeline, "run", return_value=[]):
            asyncio.run(_run(engine))

        st = engine.status(run)
        assert st["enabled"] is True
        assert st["captured"] == 5
        assert st["processed"] == 5
        assert st["pending"] == 0
        assert st["state"] == "up_to_date"

    def test_status_when_partially_processed(self, tmp_path):
        """If processed_offset=2 and 5 frames captured, status shows 3 pending."""
        run = "itest-status-partial"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        for i in range(5):
            fn = _make_tiny_jpeg(run_dir, f"f{i:02d}.jpg")
            ts = _ts(base, i)
            _append_manifest(run_dir, _manifest_entry(fn, ts, i))

        # Write offset = 2 manually (simulate partial processing)
        with open(os.path.join(run_dir, "processed_offset"), "w") as fh:
            fh.write("2")

        # Create engine but DO NOT run the worker — query status directly.
        # We use start() to load existing state, then immediately stop, then
        # reset the offset to 2 before reading status (start() won't re-run
        # processed frames but the worker will drain unprocessed ones).
        # Simpler: just test the status() method directly without the worker.
        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        # Manually load state by scanning directories (bypassing the worker).
        # We don't want the worker to drain the remaining frames.
        # Use asyncio.run with immediate stop (no sleep).
        async def _start_stop_immediately():
            with patch.object(engine_mod.pipeline, "run", return_value=[]):
                await engine.start()
                # Stop immediately before the worker drains all frames.
                # This may or may not leave frames unprocessed due to timing.
                await engine.stop()

        asyncio.run(_start_stop_immediately())

        # Reset offset to 2 after the worker has stopped (it may have advanced).
        with open(os.path.join(run_dir, "processed_offset"), "w") as fh:
            fh.write("2")

        # Clear the manifest stats cache so status re-reads the manifest.
        engine._manifest_stats_cache.clear()

        st = engine.status(run)
        assert st["enabled"] is True
        assert st["captured"] == 5
        assert st["processed"] == 2
        assert st["pending"] == 3
        assert st["state"] == "processing"

    def test_status_manifest_cache_avoids_reread(self, tmp_path):
        """Calling status() twice on an idle run doesn't change the cache hit count."""
        run = "itest-status-cache"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        for i in range(3):
            fn = _make_tiny_jpeg(run_dir, f"f{i:02d}.jpg")
            ts = _ts(base, i)
            _append_manifest(run_dir, _manifest_entry(fn, ts, i))

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))
        with patch.object(engine_mod.pipeline, "run", return_value=[]):
            asyncio.run(_run(engine))

        # First call — cold cache
        assert run not in engine._manifest_stats_cache
        st1 = engine.status(run)
        assert run in engine._manifest_stats_cache
        cache_after_first = dict(engine._manifest_stats_cache)

        # Second call — should hit the cache (same mtime/size, no file change)
        st2 = engine.status(run)
        assert engine._manifest_stats_cache == cache_after_first, \
            "cache should not change when file hasn't changed"
        assert st1["captured"] == st2["captured"]


# ---------------------------------------------------------------------------
# Frames endpoint integration
# ---------------------------------------------------------------------------

class TestFramesIntegration:
    """Real FramesIndex: frames() returns windowed results; meta() is correct."""

    def test_frames_window_returns_nearby_frames(self, tmp_path):
        """frames() returns only frames within the time window."""
        run = "itest-frames"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Write 10 frames, one per second
        for i in range(10):
            fn = _make_tiny_jpeg(run_dir, f"f{i:02d}.jpg")
            ts = _ts(base, i)
            _append_manifest(run_dir, _manifest_entry(fn, ts, i))

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        with patch.object(engine_mod.pipeline, "run", return_value=[]):
            asyncio.run(_run(engine))

        # Request window centered at t=5, span=2 s → should contain ~5 frames
        center_ts = _ts(base, 5)
        result = engine.frames(run, center_ts, span_s=2.0, limit=300)

        assert result["run"] == run
        assert result["meta"]["count"] == 10
        assert result["meta"]["first_ts"] is not None
        assert result["meta"]["last_ts"] is not None
        assert len(result["frames"]) > 0
        # All frames should be within [t=3, t=7]
        for f in result["frames"]:
            ts_val = _ts_seconds(f["client_ts"])
            center_epoch = _ts_seconds(center_ts)
            assert abs(ts_val - center_epoch) <= 2.0 + 1e-6, \
                f"frame outside window: {f['client_ts']}"

    def test_frames_none_center_returns_newest(self, tmp_path):
        """frames() with center=None returns the newest `limit` frames."""
        run = "itest-frames-null-center"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        for i in range(5):
            fn = _make_tiny_jpeg(run_dir, f"f{i:02d}.jpg")
            ts = _ts(base, i)
            _append_manifest(run_dir, _manifest_entry(fn, ts, i))

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))
        with patch.object(engine_mod.pipeline, "run", return_value=[]):
            asyncio.run(_run(engine))

        result = engine.frames(run, center=None, span_s=12.0, limit=3)
        # Should return the 3 newest frames
        assert len(result["frames"]) == 3
        # All frames should be the newest 3 (i=2,3,4 → seconds 2,3,4)
        times = [_ts_seconds(f["client_ts"]) for f in result["frames"]]
        base_epoch = base.timestamp()
        assert min(times) >= base_epoch + 2 - 1e-6, \
            f"expected newest 3 frames (base+2s onward), got times: {times}"

    def test_processed_frames_have_rider_data(self, tmp_path):
        """Frames processed by the worker have processed=True and riders list."""
        run = "itest-frames-processed"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        fn = _make_tiny_jpeg(run_dir, "f0.jpg")
        ts = _ts(base, 0)
        _append_manifest(run_dir, _manifest_entry(fn, ts, 0))

        # The worker returns a needs_review result
        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))
        with patch.object(engine_mod.pipeline, "run",
                          return_value=[_result("128", 0.45, "needs_review")]):
            asyncio.run(_run(engine))

        result = engine.frames(run, center=ts, span_s=1.0, limit=300)
        frames = result["frames"]
        assert len(frames) == 1
        assert frames[0]["processed"] is True
        assert isinstance(frames[0]["riders"], list)
        assert len(frames[0]["riders"]) == 1
        assert frames[0]["riders"][0]["status"] == "needs_review"


# ---------------------------------------------------------------------------
# Cross-seam: crossing field plumbing through the full engine
# ---------------------------------------------------------------------------

class TestCrossingSeamsIntegration:
    """Verify the orchestrator-patched crossing fields arrive in engine output."""

    def test_create_crossing_has_source_manual(self, tmp_path):
        """create_crossing returns a Crossing with source='manual'."""
        run = "itest-seam"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ts0 = _ts(base, 0)
        fn0 = _make_tiny_jpeg(run_dir, "f0.jpg")

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))

        crossing = None

        async def _run_with_manual():
            nonlocal crossing
            with patch.object(engine_mod.pipeline, "run", return_value=[]):
                await engine.start()
                crossing = engine.create_crossing(run, fn0, ts0, "101")
                await asyncio.sleep(0.05)
                await engine.stop()

        asyncio.run(_run_with_manual())

        assert crossing is not None
        assert crossing.source == "manual"
        assert crossing.number == "101"
        assert crossing.confidence == 0.0
        assert crossing.order_key == float(_epoch_ms(ts0))
        assert crossing.order_overridden is False

        # Crossing is in the results
        _, crossings = engine.crossings(run)
        assert len(crossings) == 1
        assert crossings[0].crossing_id == crossing.crossing_id

    def test_auto_crossing_has_source_auto(self, tmp_path):
        """Automated confident fold produces source='auto' crossing."""
        run = "itest-seam-auto"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ts0 = _ts(base, 0)
        fn0 = _make_tiny_jpeg(run_dir, "f0.jpg")
        _append_manifest(run_dir, _manifest_entry(fn0, ts0, 0))

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))
        with patch.object(engine_mod.pipeline, "run",
                          return_value=[_result("42", 0.9, "confident")]):
            asyncio.run(_run(engine))

        _, crossings = engine.crossings(run)
        assert len(crossings) == 1
        assert crossings[0].source == "auto"
        assert crossings[0].number == "42"

    def test_edit_crossing_sets_edited_flag(self, tmp_path):
        """edit_crossing flips edited=True and updates the number."""
        run = "itest-seam-edit"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ts0 = _ts(base, 0)
        fn0 = _make_tiny_jpeg(run_dir, "f0.jpg")
        _append_manifest(run_dir, _manifest_entry(fn0, ts0, 0))

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))
        with patch.object(engine_mod.pipeline, "run",
                          return_value=[_result("10", 0.9, "confident")]):
            asyncio.run(_run(engine))

        _, crossings = engine.crossings(run)
        assert len(crossings) == 1
        cid = crossings[0].crossing_id
        assert crossings[0].edited is False

        # Edit the number
        updated = engine.edit_crossing(cid, number="11")
        assert updated.edited is True
        assert updated.number == "11"

        # Persisted correctly
        _, crossings_after = engine.crossings(run)
        assert crossings_after[0].number == "11"
        assert crossings_after[0].edited is True

    def test_set_position_updates_order_key(self, tmp_path):
        """set_position reorders a crossing and sets order_overridden."""
        run = "itest-seam-order"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Two crossings: rider A at t=0, rider B at t=10
        fn_a = _make_tiny_jpeg(run_dir, "fa.jpg")
        fn_b = _make_tiny_jpeg(run_dir, "fb.jpg")
        ts_a = _ts(base, 0)
        ts_b = _ts(base, 10)
        _append_manifest(run_dir, _manifest_entry(fn_a, ts_a, 0))
        _append_manifest(run_dir, _manifest_entry(fn_b, ts_b, 1))

        results_seq = [
            [_result("1", 0.9, "confident")],
            [_result("2", 0.9, "confident")],
        ]
        call_count = [0]

        def fake_run(img, cfg):
            idx = call_count[0]
            call_count[0] += 1
            return results_seq[idx] if idx < len(results_seq) else []

        # Use dedup_window_s=1 so the two crossings don't dedup into one
        live = _make_live(dedup_window_s=1.0)
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))
        with patch.object(engine_mod.pipeline, "run", side_effect=fake_run):
            asyncio.run(_run(engine))

        _, crossings = engine.crossings(run)
        assert len(crossings) == 2
        # Default order: rider 1 (t=0) before rider 2 (t=10) (ascending order_key)
        assert crossings[0].number == "1"
        assert crossings[1].number == "2"

        c1_id = crossings[0].crossing_id   # rider 1 (currently first)
        c2_id = crossings[1].crossing_id   # rider 2 (currently second)

        # Move rider 2 to be "earlier" (before rider 1 in order of record)
        # set_position(c2, earlier_id=None, later_id=c1) → c2 gets order_key < c1
        updated = engine.set_position(c2_id, earlier_id=None, later_id=c1_id)
        assert updated.order_overridden is True

        _, crossings_after = engine.crossings(run)
        # Now rider 2 should be first (lower order_key)
        assert crossings_after[0].number == "2"
        assert crossings_after[1].number == "1"
        assert crossings_after[0].order_overridden is True

    def test_soft_delete_excludes_from_results(self, tmp_path):
        """edit_crossing(deleted=True) removes the crossing from crossings()."""
        run = "itest-seam-delete"
        run_dir = str(tmp_path / run)
        os.makedirs(run_dir, exist_ok=True)
        base = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        ts0 = _ts(base, 0)
        fn0 = _make_tiny_jpeg(run_dir, "f0.jpg")
        _append_manifest(run_dir, _manifest_entry(fn0, ts0, 0))

        live = _make_live()
        engine = ResultsEngine(live, _make_cv_cfg(), str(tmp_path))
        with patch.object(engine_mod.pipeline, "run",
                          return_value=[_result("99", 0.9, "confident")]):
            asyncio.run(_run(engine))

        _, crossings = engine.crossings(run)
        assert len(crossings) == 1
        cid = crossings[0].crossing_id

        # Soft delete
        engine.edit_crossing(cid, deleted=True)
        _, crossings_after = engine.crossings(run)
        assert crossings_after == [], "deleted crossing should be excluded from results"
