"""Tests for FramesIndex (task3).

Covers:
  - append writes the exact §3.3 shape (incl. empty riders); lines accumulate.
  - Merge: processed frames carry riders, unprocessed carry processed=False/None
    (manifest longer than the index — the backlog case).
  - Windowing: center picks the right span; ascending order; limit cap keeps
    frames nearest the center; center=None returns the newest `limit`.
  - Robustness: missing manifest / missing index / malformed lines in either.
  - meta: empty run, missing run, populated run.
  - Windowing edge cases: exact boundary inclusion, window wider than all frames,
    limit=1 (keeps the single nearest), duplicate timestamps, all frames outside
    window.
"""
from __future__ import annotations

import json
import os

import pytest

from backend.frames_index import FramesIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeCrossingResult:
    """Minimal CrossingResult stand-in (no real inference needed)."""
    def __init__(
        self,
        rider_box=(10.0, 20.0, 50.0, 80.0),
        det_conf=0.91,
        status="confident",
        number="101",
        raw_text="101",
        confidence=0.95,
    ):
        self.rider_box = rider_box
        self.det_conf = det_conf
        self.status = status
        self.number = number
        self.raw_text = raw_text
        self.confidence = confidence


def _make_entry(filename: str, client_ts: str, seq: int = 0) -> dict:
    """Build a minimal manifest entry dict."""
    return {
        "filename": filename,
        "client_ts": client_ts,
        "seq": seq,
        "label": filename.split("/")[0],
        "safe_label": filename.split("/")[0],
    }


def _read_index_lines(run_dir: str) -> list[dict]:
    path = os.path.join(run_dir, "frames_index.jsonl")
    if not os.path.isfile(path):
        return []
    lines = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                lines.append(json.loads(raw))
    return lines


def _write_manifest(run_dir: str, entries: list[dict]) -> None:
    os.makedirs(run_dir, exist_ok=True)
    manifest_path = os.path.join(run_dir, "manifest.jsonl")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")


def _write_index(run_dir: str, records: list[dict]) -> None:
    os.makedirs(run_dir, exist_ok=True)
    index_path = os.path.join(run_dir, "frames_index.jsonl")
    with open(index_path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


# ---------------------------------------------------------------------------
# Tests for append()
# ---------------------------------------------------------------------------

class TestAppend:
    def test_append_creates_index_file(self, tmp_path):
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        entry = _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0)
        fi.append(run, entry, [])
        assert os.path.isfile(os.path.join(str(tmp_path), run, "frames_index.jsonl"))

    def test_append_empty_riders(self, tmp_path):
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        entry = _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0)
        fi.append(run, entry, [])

        lines = _read_index_lines(os.path.join(str(tmp_path), run))
        assert len(lines) == 1
        rec = lines[0]
        assert rec["filename"] == "run1/collected/f001.jpg"
        assert rec["client_ts"] == "2026-07-17T10:00:00.000Z"
        assert rec["seq"] == 0
        assert rec["riders"] == []

    def test_append_with_riders_exact_shape(self, tmp_path):
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        entry = _make_entry("run1/collected/f002.jpg", "2026-07-17T10:00:01.000Z", seq=1)
        r = _FakeCrossingResult(
            rider_box=(5.0, 10.0, 50.0, 90.0),
            det_conf=0.85,
            status="needs_review",
            number=None,
            raw_text="1?8",
            confidence=0.31,
        )
        fi.append(run, entry, [r])

        lines = _read_index_lines(os.path.join(str(tmp_path), run))
        assert len(lines) == 1
        rider = lines[0]["riders"][0]
        assert rider["box"] == [5.0, 10.0, 50.0, 90.0]
        assert rider["det_conf"] == pytest.approx(0.85)
        assert rider["status"] == "needs_review"
        assert rider["number"] is None
        assert rider["raw_text"] == "1?8"
        assert rider["confidence"] == pytest.approx(0.31)

    def test_append_multiple_riders(self, tmp_path):
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        entry = _make_entry("run1/collected/f003.jpg", "2026-07-17T10:00:02.000Z", seq=2)
        r1 = _FakeCrossingResult(number="101", det_conf=0.9, status="confident")
        r2 = _FakeCrossingResult(number=None, det_conf=0.7, status="rejected",
                                  raw_text="??", confidence=0.1)
        fi.append(run, entry, [r1, r2])

        lines = _read_index_lines(os.path.join(str(tmp_path), run))
        assert len(lines[0]["riders"]) == 2

    def test_append_accumulates_lines(self, tmp_path):
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        for i in range(3):
            entry = _make_entry(
                f"run1/collected/f{i:03d}.jpg",
                f"2026-07-17T10:00:0{i}.000Z",
                seq=i,
            )
            fi.append(run, entry, [])

        lines = _read_index_lines(os.path.join(str(tmp_path), run))
        assert len(lines) == 3
        # Each line is a distinct frame
        filenames = [l["filename"] for l in lines]
        assert len(set(filenames)) == 3

    def test_append_box_is_list_not_tuple(self, tmp_path):
        """rider_box from CrossingResult is a tuple; serialised form must be a list."""
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        entry = _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z")
        r = _FakeCrossingResult(rider_box=(1.0, 2.0, 3.0, 4.0))
        fi.append(run, entry, [r])
        lines = _read_index_lines(os.path.join(str(tmp_path), run))
        assert isinstance(lines[0]["riders"][0]["box"], list)
        assert lines[0]["riders"][0]["box"] == [1.0, 2.0, 3.0, 4.0]


# ---------------------------------------------------------------------------
# Tests for frames() — merge and windowing
# ---------------------------------------------------------------------------

class TestFramesMerge:
    def test_all_processed_returns_riders(self, tmp_path):
        """All manifest frames have an index entry → processed=True with riders."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f002.jpg", "2026-07-17T10:00:01.000Z", seq=1),
        ]
        _write_manifest(run_dir, entries)

        index_records = [
            {"filename": "run1/collected/f001.jpg", "client_ts": "2026-07-17T10:00:00.000Z",
             "seq": 0, "riders": [{"box": [1,2,3,4], "det_conf": 0.9, "status": "confident",
                                    "number": "101", "raw_text": "101", "confidence": 0.95}]},
            {"filename": "run1/collected/f002.jpg", "client_ts": "2026-07-17T10:00:01.000Z",
             "seq": 1, "riders": []},
        ]
        _write_index(run_dir, index_records)

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        assert len(result) == 2
        assert all(r["processed"] is True for r in result)
        assert result[0]["riders"] != []      # f001 has a rider
        assert result[1]["riders"] == []      # f002 processed but no riders

    def test_backlog_case_unprocessed_frames(self, tmp_path):
        """Manifest has more frames than the index — unprocessed ones get processed=False."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f002.jpg", "2026-07-17T10:00:01.000Z", seq=1),
            _make_entry("run1/collected/f003.jpg", "2026-07-17T10:00:02.000Z", seq=2),
        ]
        _write_manifest(run_dir, entries)
        # Only f001 is indexed
        index_records = [
            {"filename": "run1/collected/f001.jpg", "client_ts": "2026-07-17T10:00:00.000Z",
             "seq": 0, "riders": []},
        ]
        _write_index(run_dir, index_records)

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        assert len(result) == 3

        by_fn = {r["filename"]: r for r in result}
        assert by_fn["run1/collected/f001.jpg"]["processed"] is True
        assert by_fn["run1/collected/f001.jpg"]["riders"] == []
        assert by_fn["run1/collected/f002.jpg"]["processed"] is False
        assert by_fn["run1/collected/f002.jpg"]["riders"] is None
        assert by_fn["run1/collected/f003.jpg"]["processed"] is False
        assert by_fn["run1/collected/f003.jpg"]["riders"] is None

    def test_result_is_time_ordered_ascending(self, tmp_path):
        """frames() output must be in ascending client_ts order."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        # Write out-of-order in manifest (shouldn't matter)
        entries = [
            _make_entry("run1/collected/f003.jpg", "2026-07-17T10:00:02.000Z", seq=2),
            _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f002.jpg", "2026-07-17T10:00:01.000Z", seq=1),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        assert len(result) == 3
        ts_list = [r["client_ts"] for r in result]
        assert ts_list == sorted(ts_list)


class TestFramesWindowing:
    def test_window_filters_outside_frames(self, tmp_path):
        """Frames outside [center−span, center+span] are excluded."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/far_past.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/in_window.jpg", "2026-07-17T10:00:10.000Z", seq=1),
            _make_entry("run1/collected/far_future.jpg", "2026-07-17T10:00:30.000Z", seq=2),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        # center = 10s, span = 5s → window [5s, 15s]; only in_window qualifies
        result = fi.frames(run, "2026-07-17T10:00:10.000Z", 5.0, 300)
        assert len(result) == 1
        assert result[0]["filename"] == "run1/collected/in_window.jpg"

    def test_window_boundary_inclusive(self, tmp_path):
        """Frames at exactly center ± span_s are included."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        # center = 10s, span = 5s → window [5s, 15s]
        entries = [
            _make_entry("run1/collected/at_lo.jpg", "2026-07-17T10:00:05.000Z", seq=0),
            _make_entry("run1/collected/at_center.jpg", "2026-07-17T10:00:10.000Z", seq=1),
            _make_entry("run1/collected/at_hi.jpg", "2026-07-17T10:00:15.000Z", seq=2),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, "2026-07-17T10:00:10.000Z", 5.0, 300)
        assert len(result) == 3

    def test_limit_keeps_nearest_center(self, tmp_path):
        """When in-window frames exceed limit, keep the ones nearest center."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        # 5 frames, center at t=10, span=100 (all in window), limit=2
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),  # 10s away
            _make_entry("run1/collected/f2.jpg", "2026-07-17T10:00:08.000Z", seq=1),  # 2s away
            _make_entry("run1/collected/f3.jpg", "2026-07-17T10:00:10.000Z", seq=2),  # 0s away
            _make_entry("run1/collected/f4.jpg", "2026-07-17T10:00:12.000Z", seq=3),  # 2s away
            _make_entry("run1/collected/f5.jpg", "2026-07-17T10:00:20.000Z", seq=4),  # 10s away
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, "2026-07-17T10:00:10.000Z", 100.0, 2)
        assert len(result) == 2
        # Must keep f3 (0s) and one of f2/f4 (both 2s away), not f1/f5 (10s away)
        filenames = {r["filename"] for r in result}
        assert "run1/collected/f3.jpg" in filenames
        # Not the furthest ones
        assert "run1/collected/f1.jpg" not in filenames
        assert "run1/collected/f5.jpg" not in filenames

    def test_limit_1_keeps_single_nearest(self, tmp_path):
        """limit=1 keeps only the single closest frame to center."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/far.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/near.jpg", "2026-07-17T10:00:09.000Z", seq=1),
            _make_entry("run1/collected/mid.jpg", "2026-07-17T10:00:05.000Z", seq=2),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, "2026-07-17T10:00:10.000Z", 20.0, 1)
        assert len(result) == 1
        assert result[0]["filename"] == "run1/collected/near.jpg"

    def test_center_none_returns_newest_limit(self, tmp_path):
        """center_ts=None → newest `limit` frames, ascending order."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f2.jpg", "2026-07-17T10:00:01.000Z", seq=1),
            _make_entry("run1/collected/f3.jpg", "2026-07-17T10:00:02.000Z", seq=2),
            _make_entry("run1/collected/f4.jpg", "2026-07-17T10:00:03.000Z", seq=3),
            _make_entry("run1/collected/f5.jpg", "2026-07-17T10:00:04.000Z", seq=4),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 3)
        # Should return the 3 newest: f3, f4, f5 in ascending order
        assert len(result) == 3
        assert result[0]["filename"] == "run1/collected/f3.jpg"
        assert result[1]["filename"] == "run1/collected/f4.jpg"
        assert result[2]["filename"] == "run1/collected/f5.jpg"

    def test_center_none_all_fit_in_limit(self, tmp_path):
        """center_ts=None with fewer frames than limit returns all frames."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f2.jpg", "2026-07-17T10:00:01.000Z", seq=1),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        assert len(result) == 2

    def test_center_none_ascending_order(self, tmp_path):
        """center_ts=None output is ascending even if manifest is unordered."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f3.jpg", "2026-07-17T10:00:02.000Z", seq=2),
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f2.jpg", "2026-07-17T10:00:01.000Z", seq=1),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        ts_list = [r["client_ts"] for r in result]
        assert ts_list == sorted(ts_list)

    def test_no_frames_in_window_returns_empty(self, tmp_path):
        """Window entirely outside all manifest timestamps → []."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        # Center is 1 hour later, span 1s
        result = fi.frames(run, "2026-07-17T11:00:00.000Z", 1.0, 300)
        assert result == []

    def test_window_wider_than_all_frames_returns_all(self, tmp_path):
        """A very wide window returns all manifest frames."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f2.jpg", "2026-07-17T10:00:01.000Z", seq=1),
            _make_entry("run1/collected/f3.jpg", "2026-07-17T10:00:02.000Z", seq=2),
        ]
        _write_manifest(run_dir, entries)
        _write_index(run_dir, [])

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, "2026-07-17T10:00:01.000Z", 3600.0, 300)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Tests for frames() — robustness
# ---------------------------------------------------------------------------

class TestFramesRobustness:
    def test_missing_manifest_returns_empty(self, tmp_path):
        fi = FramesIndex(str(tmp_path))
        result = fi.frames("nonexistent_run", None, 60.0, 300)
        assert result == []

    def test_missing_index_returns_unprocessed(self, tmp_path):
        """No frames_index.jsonl → all frames unprocessed."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
        ]
        _write_manifest(run_dir, entries)
        # No index file written

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        assert len(result) == 1
        assert result[0]["processed"] is False
        assert result[0]["riders"] is None

    def test_malformed_manifest_line_skipped(self, tmp_path):
        """A bad JSON line in manifest.jsonl is silently skipped."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        os.makedirs(run_dir, exist_ok=True)
        manifest_path = os.path.join(run_dir, "manifest.jsonl")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(_make_entry("run1/collected/f1.jpg",
                                            "2026-07-17T10:00:00.000Z", seq=0)) + "\n")
            fh.write("THIS IS NOT JSON\n")
            fh.write(json.dumps(_make_entry("run1/collected/f2.jpg",
                                            "2026-07-17T10:00:01.000Z", seq=1)) + "\n")

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        assert len(result) == 2  # malformed line skipped; 2 valid lines

    def test_malformed_index_line_skipped(self, tmp_path):
        """A bad JSON line in frames_index.jsonl is silently skipped; frame
        still appears as unprocessed (index entry missing)."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
        ]
        _write_manifest(run_dir, entries)

        # Write a bad index file
        index_path = os.path.join(run_dir, "frames_index.jsonl")
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write("GARBAGE LINE\n")

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        assert len(result) == 1
        # Malformed index line means no match → unprocessed
        assert result[0]["processed"] is False

    def test_malformed_index_line_partial_recovery(self, tmp_path):
        """Good index entries before/after a bad line are still used."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f2.jpg", "2026-07-17T10:00:01.000Z", seq=1),
        ]
        _write_manifest(run_dir, entries)

        index_path = os.path.join(run_dir, "frames_index.jsonl")
        good_record = {"filename": "run1/collected/f1.jpg",
                       "client_ts": "2026-07-17T10:00:00.000Z", "seq": 0, "riders": []}
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(good_record) + "\n")
            fh.write("NOT JSON\n")

        fi = FramesIndex(str(tmp_path))
        result = fi.frames(run, None, 60.0, 300)
        by_fn = {r["filename"]: r for r in result}
        assert by_fn["run1/collected/f1.jpg"]["processed"] is True  # good index entry used
        assert by_fn["run1/collected/f2.jpg"]["processed"] is False  # no index entry


# ---------------------------------------------------------------------------
# Tests for meta()
# ---------------------------------------------------------------------------

class TestMeta:
    def test_meta_missing_run(self, tmp_path):
        fi = FramesIndex(str(tmp_path))
        m = fi.meta("nonexistent_run")
        assert m == {"count": 0, "first_ts": None, "last_ts": None}

    def test_meta_empty_manifest(self, tmp_path):
        """An existing but empty manifest.jsonl returns zeros/Nones."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        os.makedirs(run_dir, exist_ok=True)
        open(os.path.join(run_dir, "manifest.jsonl"), "w").close()  # empty file

        fi = FramesIndex(str(tmp_path))
        m = fi.meta(run)
        assert m == {"count": 0, "first_ts": None, "last_ts": None}

    def test_meta_populated(self, tmp_path):
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f2.jpg", "2026-07-17T10:00:02.000Z", seq=1),
            _make_entry("run1/collected/f3.jpg", "2026-07-17T10:00:01.000Z", seq=2),
        ]
        _write_manifest(run_dir, entries)

        fi = FramesIndex(str(tmp_path))
        m = fi.meta(run)
        assert m["count"] == 3
        assert m["first_ts"] == "2026-07-17T10:00:00.000Z"
        assert m["last_ts"] == "2026-07-17T10:00:02.000Z"

    def test_meta_single_frame(self, tmp_path):
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        entries = [
            _make_entry("run1/collected/f1.jpg", "2026-07-17T10:00:00.000Z", seq=0),
        ]
        _write_manifest(run_dir, entries)

        fi = FramesIndex(str(tmp_path))
        m = fi.meta(run)
        assert m["count"] == 1
        assert m["first_ts"] == m["last_ts"] == "2026-07-17T10:00:00.000Z"

    def test_meta_with_malformed_lines(self, tmp_path):
        """Malformed lines in manifest are skipped; count reflects valid lines only."""
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        os.makedirs(run_dir, exist_ok=True)
        manifest_path = os.path.join(run_dir, "manifest.jsonl")
        with open(manifest_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(_make_entry("run1/collected/f1.jpg",
                                            "2026-07-17T10:00:00.000Z")) + "\n")
            fh.write("GARBAGE\n")
            fh.write(json.dumps(_make_entry("run1/collected/f2.jpg",
                                            "2026-07-17T10:00:01.000Z")) + "\n")

        fi = FramesIndex(str(tmp_path))
        m = fi.meta(run)
        # count reflects all non-empty parsed lines (2 good), but meta reads all lines
        # — count is len(manifest_lines) so it should be 2 (malformed skipped)
        assert m["count"] == 2
        assert m["first_ts"] == "2026-07-17T10:00:00.000Z"
        assert m["last_ts"] == "2026-07-17T10:00:01.000Z"


# ---------------------------------------------------------------------------
# Round-trip: append then frames()
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_append_then_frames_shows_processed(self, tmp_path):
        """append() then frames() returns processed=True for appended frames."""
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        os.makedirs(run_dir, exist_ok=True)

        # Write a manifest entry
        entry = _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0)
        _write_manifest(run_dir, [entry])

        # append processes this frame
        r = _FakeCrossingResult(number="101", confidence=0.95, det_conf=0.9,
                                 status="confident", raw_text="101",
                                 rider_box=(0.0, 0.0, 10.0, 10.0))
        fi.append(run, entry, [r])

        result = fi.frames(run, None, 60.0, 300)
        assert len(result) == 1
        assert result[0]["processed"] is True
        assert len(result[0]["riders"]) == 1
        assert result[0]["riders"][0]["number"] == "101"

    def test_append_empty_then_frames_shows_empty_riders(self, tmp_path):
        """append() with no results → processed=True, riders=[]."""
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        os.makedirs(run_dir, exist_ok=True)

        entry = _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0)
        _write_manifest(run_dir, [entry])
        fi.append(run, entry, [])

        result = fi.frames(run, None, 60.0, 300)
        assert result[0]["processed"] is True
        assert result[0]["riders"] == []

    def test_append_multiple_then_meta(self, tmp_path):
        """meta() reflects the manifest (independent of index)."""
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        os.makedirs(run_dir, exist_ok=True)

        entries = [
            _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f002.jpg", "2026-07-17T10:00:05.000Z", seq=1),
        ]
        _write_manifest(run_dir, entries)
        for e in entries:
            fi.append(run, e, [])

        m = fi.meta(run)
        assert m["count"] == 2
        assert m["first_ts"] == "2026-07-17T10:00:00.000Z"
        assert m["last_ts"] == "2026-07-17T10:00:05.000Z"

    def test_windowed_query_with_mixed_processed(self, tmp_path):
        """Window query returns both processed and unprocessed frames correctly merged."""
        fi = FramesIndex(str(tmp_path))
        run = "run1"
        run_dir = os.path.join(str(tmp_path), run)
        os.makedirs(run_dir, exist_ok=True)

        # 3 frames in the manifest, only 2 indexed
        entries = [
            _make_entry("run1/collected/f001.jpg", "2026-07-17T10:00:00.000Z", seq=0),
            _make_entry("run1/collected/f002.jpg", "2026-07-17T10:00:01.000Z", seq=1),
            _make_entry("run1/collected/f003.jpg", "2026-07-17T10:00:02.000Z", seq=2),
        ]
        _write_manifest(run_dir, entries)

        # Only f001 and f003 are processed
        fi.append(run, entries[0], [_FakeCrossingResult()])
        fi.append(run, entries[2], [])

        center = "2026-07-17T10:00:01.000Z"
        result = fi.frames(run, center, 5.0, 300)
        assert len(result) == 3

        by_fn = {r["filename"]: r for r in result}
        assert by_fn["run1/collected/f001.jpg"]["processed"] is True
        assert by_fn["run1/collected/f002.jpg"]["processed"] is False
        assert by_fn["run1/collected/f002.jpg"]["riders"] is None
        assert by_fn["run1/collected/f003.jpg"]["processed"] is True
        assert by_fn["run1/collected/f003.jpg"]["riders"] == []
