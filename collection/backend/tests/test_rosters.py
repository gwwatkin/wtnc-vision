"""Tests for RunRosters (task4 — per-run rosters).

Coverage:
- _parse_csv internals (header detection, quoted fields, bad rows, duplicates)
- RunRosters.set happy path + file contents + Roster in memory
- RunRosters.set label normalization
- RunRosters.set replacement (FR18, swap rule)
- RunRosters.set rejection (blank label, header-only, all-bad-rows, empty text) → ValueError
  and previous roster stays intact (FR19)
- Duplicate numbers: later row wins
- RunRosters.get unknown run → EMPTY_ROSTER
- RunRosters.list_runs: sees a rostered-but-never-captured run; [] when root absent
- RunRosters.roster_csv_path: path for missing file
- RunRosters.load_existing: restores state on a fresh instance
- Route-level via FastAPI TestClient using a stub engine (POST /roster, GET /runs)
"""
from __future__ import annotations

import io
import os

import pytest
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.models import AppConfig
from backend.app import create_app
from backend.rosters import EMPTY_ROSTER, Roster, RunRosters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rosters(tmp_path) -> RunRosters:
    return RunRosters(str(tmp_path))


def _make_cfg(tmp_path) -> AppConfig:
    return AppConfig(
        host="127.0.0.1",
        port=8000,
        storage_dir=str(tmp_path),
        manifest_name="manifest.jsonl",
        allowed_origins=["*"],
        max_frame_bytes=5_242_880,
        allowed_content_types=("image/jpeg",),
        version="0.1.0",
    )


# ---------------------------------------------------------------------------
# Unit tests — RunRosters.set happy path
# ---------------------------------------------------------------------------

class TestSetHappyPath:
    def test_returns_safe_run_id_and_count(self, tmp_path):
        rr = _make_rosters(tmp_path)
        run_id, count = rr.set("Lap 3 / Nearside", "number,name,category\n101,Alice,Cat1\n202,Bob,Cat2\n")
        assert run_id == "lap-3-nearside"
        assert count == 2

    def test_label_normalization(self, tmp_path):
        rr = _make_rosters(tmp_path)
        run_id, count = rr.set("  Lap 3 / Nearside  ", "number,name,category\n101,Alice,Cat1\n")
        # safe_label is applied to the stripped label
        assert run_id == "lap-3-nearside"
        assert count == 1

    def test_run_directory_created(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("TestRun", "101,Alice,Cat1\n")
        assert os.path.isdir(str(tmp_path / "testrun"))

    def test_roster_csv_written(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "number,name,category\n101,Alice Smith,Cat1\n202,Bob Jones,Cat2\n")
        roster_csv = tmp_path / "myrun" / "roster.csv"
        assert roster_csv.exists()
        content = roster_csv.read_text()
        # Header line present
        assert "number,name,category" in content
        # Both numbers present
        assert "101" in content
        assert "202" in content

    def test_no_roster_txt_written(self, tmp_path):
        """roster.csv is the single roster file; no derived roster.txt."""
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "number,name,category\n101,Alice,Cat1\n202,Bob,Cat2\n")
        assert not (tmp_path / "myrun" / "roster.txt").exists()
        csv_lines = (tmp_path / "myrun" / "roster.csv").read_text().strip().split("\n")
        numbers_in_file = {line.split(",")[0] for line in csv_lines[1:]}
        assert numbers_in_file == {"101", "202"}

    def test_get_returns_both_entries(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "number,name,category\n101,Alice,Cat1\n202,Bob,Cat2\n")
        roster = rr.get("myrun")
        assert "101" in roster.numbers
        assert "202" in roster.numbers
        assert roster.entries["101"] == ("Alice", "Cat1")
        assert roster.entries["202"] == ("Bob", "Cat2")

    def test_header_with_quoted_names(self, tmp_path):
        """Header + quoted names containing commas → 2 rows accepted."""
        csv_text = 'number,name,category\n101,"Smith, Alice",Cat3\n202,"Jones, Bob",Cat1\n'
        rr = _make_rosters(tmp_path)
        run_id, count = rr.set("race1", csv_text)
        assert count == 2
        roster = rr.get("race1")
        assert roster.entries["101"] == ("Smith, Alice", "Cat3")
        assert roster.entries["202"] == ("Jones, Bob", "Cat1")

    def test_roster_before_first_frame_creates_dir(self, tmp_path):
        """Roster directory is created even when no frames have been written yet."""
        rr = _make_rosters(tmp_path)
        run_dir = tmp_path / "lap-3-nearside"
        assert not run_dir.exists()
        rr.set("Lap 3 / Nearside", "101,Alice,Cat1\n")
        assert run_dir.exists()


# ---------------------------------------------------------------------------
# Unit tests — replacement (FR18, swap rule)
# ---------------------------------------------------------------------------

class TestSetReplacement:
    def test_second_set_supersedes_old_number_in_files(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "101,Alice,Cat1\n")
        rr.set("myrun", "202,Bob,Cat2\n")

        roster_csv = (tmp_path / "myrun" / "roster.csv").read_text()
        assert "202" in roster_csv
        assert "101" not in roster_csv

    def test_second_set_supersedes_old_number_in_memory(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "101,Alice,Cat1\n")
        rr.set("myrun", "202,Bob,Cat2\n")

        roster = rr.get("myrun")
        assert "202" in roster.numbers
        assert "101" not in roster.numbers

    def test_replacement_returns_new_roster_object(self, tmp_path):
        """Verify replace-don't-mutate: second set returns a brand-new Roster instance (FR18)."""
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "101,Alice,Cat1\n")
        first_roster = rr.get("myrun")
        rr.set("myrun", "202,Bob,Cat2\n")
        second_roster = rr.get("myrun")
        # Must be a different object
        assert first_roster is not second_roster

    def test_replacement_csv_file_fully_rewritten(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "101,Alice,Cat1\n")
        rr.set("myrun", "202,Bob,Cat2\n")
        content = (tmp_path / "myrun" / "roster.csv").read_text()
        assert "101" not in content
        assert "202" in content


# ---------------------------------------------------------------------------
# Unit tests — rejection (FR19)
# ---------------------------------------------------------------------------

class TestSetRejection:
    def test_blank_label_raises(self, tmp_path):
        rr = _make_rosters(tmp_path)
        with pytest.raises(ValueError, match="blank"):
            rr.set("   ", "101,Alice,Cat1\n")

    def test_empty_csv_text_raises(self, tmp_path):
        rr = _make_rosters(tmp_path)
        with pytest.raises(ValueError):
            rr.set("myrun", "")

    def test_header_only_raises(self, tmp_path):
        rr = _make_rosters(tmp_path)
        with pytest.raises(ValueError):
            rr.set("myrun", "number,name,category\n")

    def test_all_bad_rows_raises(self, tmp_path):
        rr = _make_rosters(tmp_path)
        # Rows have fewer than 3 cells or non-digit number cells
        with pytest.raises(ValueError):
            rr.set("myrun", "abc,Alice,Cat1\nxyz,Bob,Cat2\n")

    def test_rejection_leaves_previous_roster_in_memory(self, tmp_path):
        """FR19: previous roster stays active when a new upload is rejected."""
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "101,Alice,Cat1\n")
        first_roster = rr.get("myrun")

        with pytest.raises(ValueError):
            rr.set("myrun", "")  # bad upload

        roster_after = rr.get("myrun")
        assert roster_after is first_roster
        assert "101" in roster_after.numbers

    def test_rejection_leaves_previous_roster_on_disk(self, tmp_path):
        """FR19: disk files are untouched when a new upload is rejected."""
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "101,Alice,Cat1\n")
        csv_before = (tmp_path / "myrun" / "roster.csv").read_text()

        with pytest.raises(ValueError):
            rr.set("myrun", "number,name,category\n")  # header-only

        csv_after = (tmp_path / "myrun" / "roster.csv").read_text()
        assert csv_after == csv_before

    def test_rejection_no_files_created_for_new_run(self, tmp_path):
        """If no prior roster, a rejected upload must not create the run dir."""
        rr = _make_rosters(tmp_path)
        with pytest.raises(ValueError):
            rr.set("brandnewrun", "number,name,category\n")
        assert not (tmp_path / "brandnewrun").exists()


# ---------------------------------------------------------------------------
# Unit tests — duplicate numbers
# ---------------------------------------------------------------------------

class TestDuplicateNumbers:
    def test_later_row_wins(self, tmp_path):
        csv_text = "101,Alice,Cat1\n101,Bob,Cat2\n"
        rr = _make_rosters(tmp_path)
        _, count = rr.set("myrun", csv_text)
        roster = rr.get("myrun")
        # count reflects unique keys (later wins)
        assert count == 1
        assert roster.entries["101"] == ("Bob", "Cat2")

    def test_later_row_wins_with_header(self, tmp_path):
        csv_text = "number,name,category\n101,Alice,Cat1\n101,Bob,Cat2\n"
        rr = _make_rosters(tmp_path)
        _, count = rr.set("myrun", csv_text)
        roster = rr.get("myrun")
        assert count == 1
        assert roster.entries["101"] == ("Bob", "Cat2")


# ---------------------------------------------------------------------------
# Unit tests — get, list_runs, roster_csv_path
# ---------------------------------------------------------------------------

class TestGetListRosterPath:
    def test_get_unknown_run_returns_empty_roster(self, tmp_path):
        rr = _make_rosters(tmp_path)
        assert rr.get("nonexistent") is EMPTY_ROSTER

    def test_list_runs_empty_when_root_absent(self, tmp_path):
        rr = RunRosters(str(tmp_path / "doesnotexist"))
        assert rr.list_runs() == []

    def test_list_runs_sees_rostered_run(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("MyRun", "101,Alice,Cat1\n")
        runs = rr.list_runs()
        assert "myrun" in runs

    def test_list_runs_sees_multiple_runs(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("Run1", "101,Alice,Cat1\n")
        rr.set("Run2", "202,Bob,Cat2\n")
        runs = rr.list_runs()
        assert set(runs) == {"run1", "run2"}

    def test_roster_csv_path_for_roster_less_run(self, tmp_path):
        """roster_csv_path returns a path even when the file doesn't exist yet."""
        rr = _make_rosters(tmp_path)
        path = rr.roster_csv_path("no-roster-yet")
        assert path.endswith(os.path.join("no-roster-yet", "roster.csv"))
        assert not os.path.exists(path)

    def test_roster_csv_path_for_known_run(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "101,Alice,Cat1\n")
        path = rr.roster_csv_path("myrun")
        assert os.path.isfile(path)


# ---------------------------------------------------------------------------
# Unit tests — load_existing
# ---------------------------------------------------------------------------

class TestLoadExisting:
    def test_load_existing_restores_state(self, tmp_path):
        """load_existing on a fresh RunRosters instance restores state from disk."""
        rr1 = _make_rosters(tmp_path)
        rr1.set("myrun", "number,name,category\n101,Alice,Cat1\n202,Bob,Cat2\n")

        rr2 = _make_rosters(tmp_path)
        assert rr2.get("myrun") is EMPTY_ROSTER  # not yet loaded

        rr2.load_existing()
        roster = rr2.get("myrun")
        assert "101" in roster.numbers
        assert "202" in roster.numbers
        assert roster.entries["101"] == ("Alice", "Cat1")

    def test_load_existing_noop_when_root_absent(self, tmp_path):
        """load_existing does not raise when run_root doesn't exist."""
        rr = RunRosters(str(tmp_path / "doesnotexist"))
        rr.load_existing()  # must not raise
        assert rr.list_runs() == []

    def test_load_existing_skips_malformed_roster(self, tmp_path):
        """A run directory with a bad roster.csv is skipped; others still loaded."""
        # Good run
        rr1 = _make_rosters(tmp_path)
        rr1.set("goodrun", "101,Alice,Cat1\n")

        # Bad run: write a directory with an invalid roster.csv manually
        bad_run_dir = tmp_path / "badrun"
        bad_run_dir.mkdir()
        (bad_run_dir / "roster.csv").write_text("not,a,valid\nnumber,at,all\n")

        rr2 = _make_rosters(tmp_path)
        rr2.load_existing()

        # goodrun loaded
        assert "101" in rr2.get("goodrun").numbers
        # badrun has no parseable rows → logged and skipped, not in memory
        assert rr2.get("badrun") is EMPTY_ROSTER

    def test_load_existing_skips_run_without_roster_csv(self, tmp_path):
        """Directories without roster.csv (pure frame dirs) are not loaded."""
        run_dir = tmp_path / "framesonly"
        run_dir.mkdir()
        (run_dir / "manifest.jsonl").write_text("")  # has frames but no roster

        rr = _make_rosters(tmp_path)
        rr.load_existing()
        # list_runs sees it (it's a directory), but get returns EMPTY_ROSTER
        assert "framesonly" in rr.list_runs()
        assert rr.get("framesonly") is EMPTY_ROSTER

    def test_load_existing_multiple_runs(self, tmp_path):
        rr1 = _make_rosters(tmp_path)
        rr1.set("alpha", "101,Alice,Cat1\n")
        rr1.set("beta", "202,Bob,Cat2\n")

        rr2 = _make_rosters(tmp_path)
        rr2.load_existing()

        assert "101" in rr2.get("alpha").numbers
        assert "202" in rr2.get("beta").numbers


# ---------------------------------------------------------------------------
# CSV parsing edge cases
# ---------------------------------------------------------------------------

class TestCsvParsing:
    def test_no_header_plain_rows(self, tmp_path):
        rr = _make_rosters(tmp_path)
        run_id, count = rr.set("myrun", "101,Alice,Cat1\n202,Bob,Cat2\n")
        assert count == 2

    def test_whitespace_stripped_from_name_category(self, tmp_path):
        rr = _make_rosters(tmp_path)
        rr.set("myrun", "101,  Alice  ,  Cat1  \n")
        roster = rr.get("myrun")
        assert roster.entries["101"] == ("Alice", "Cat1")

    def test_bad_row_fewer_than_3_cells_skipped(self, tmp_path):
        rr = _make_rosters(tmp_path)
        # Mix of good and too-few-cells rows
        _, count = rr.set("myrun", "101,Alice,Cat1\nbadrow\n202,Bob,Cat2\n")
        assert count == 2

    def test_first_row_non_digit_treated_as_header(self, tmp_path):
        """First row with non-digit number cell is treated as header and skipped."""
        rr = _make_rosters(tmp_path)
        _, count = rr.set("myrun", "number,name,category\n101,Alice,Cat1\n")
        assert count == 1

    def test_first_row_digit_not_treated_as_header(self, tmp_path):
        """First row with a digit number cell is a data row, not a header."""
        rr = _make_rosters(tmp_path)
        _, count = rr.set("myrun", "101,Alice,Cat1\n202,Bob,Cat2\n")
        assert count == 2

    def test_non_digit_number_in_non_first_row_skipped(self, tmp_path):
        """Non-first rows with non-digit number cells are skipped silently."""
        rr = _make_rosters(tmp_path)
        _, count = rr.set("myrun", "101,Alice,Cat1\nabc,Bad,Row\n202,Bob,Cat2\n")
        assert count == 2

    def test_empty_number_cell_skipped(self, tmp_path):
        rr = _make_rosters(tmp_path)
        _, count = rr.set("myrun", ",Alice,Cat1\n101,Bob,Cat2\n")
        assert count == 1

    def test_quoted_fields_handled(self, tmp_path):
        """csv.reader handles quoted fields with embedded commas."""
        rr = _make_rosters(tmp_path)
        csv_text = '101,"Smith, Alice","Cat 3"\n'
        _, count = rr.set("myrun", csv_text)
        assert count == 1
        roster = rr.get("myrun")
        assert roster.entries["101"] == ("Smith, Alice", "Cat 3")


# ---------------------------------------------------------------------------
# Route-level tests via FastAPI TestClient
#
# Strategy (per task4.md caveats): task2 is rewriting engine.py in parallel,
# so we cannot instantiate a real ResultsEngine (it imports rider_id, which
# requires model files). Instead we inject a stub engine object via monkeypatching
# app.py's engine variable after create_app() constructs it — or, more robustly,
# we build a mock engine that wraps a real RunRosters and pass it in via
# create_app's internal logic.
#
# Cleanest approach that doesn't touch engine.py:
#   - create_app(cfg, live=None) → engine=None → POST /roster → 503.
#   - For the positive /roster and /runs tests: patch the engine attribute
#     on the ASGI app after creation using a minimal stub.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Stub engine + mini-app factory for route tests.
#
# Strategy: task2 is rewriting engine.py in parallel and imports rider_id
# at module level (triggering cv model paths). We avoid instantiating the
# real ResultsEngine entirely. Instead we build a minimal FastAPI app whose
# /roster and /runs routes delegate directly to a real RunRosters instance.
#
# The route handlers MUST be defined at module level (not inside a helper
# function) so that FastAPI/Pydantic can fully resolve the UploadFile
# ForwardRef at class-creation time. We use a module-level _STUB_ROSTERS
# reference that the fixture swaps before building the TestClient.
# ---------------------------------------------------------------------------

# Module-level sentinel; replaced per-test by _make_client_with_stub_engine.
_STUB_ROSTERS: RunRosters | None = None

_mini_app = FastAPI()


@_mini_app.post("/roster")
async def _mini_post_roster(run: str = Form(...), roster: UploadFile = File(...)):
    csv_text = (await roster.read()).decode("utf-8", errors="replace")
    assert _STUB_ROSTERS is not None
    try:
        run_id, count = _STUB_ROSTERS.set(run, csv_text)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "detail": str(exc)},
        )
    return {"status": "ok", "run": run_id, "count": count}


@_mini_app.get("/runs")
async def _mini_get_runs():
    assert _STUB_ROSTERS is not None
    return {"runs": _STUB_ROSTERS.list_runs()}


def _make_client_with_stub_engine(tmp_path):
    """Return (TestClient, RunRosters) backed by a real RunRosters on tmp_path."""
    global _STUB_ROSTERS
    rr = RunRosters(str(tmp_path))
    _STUB_ROSTERS = rr
    return TestClient(_mini_app), rr


class TestRouteLevel:
    def test_post_roster_happy(self, tmp_path):
        client, _ = _make_client_with_stub_engine(tmp_path)
        csv_bytes = b"number,name,category\n101,Alice,Cat1\n202,Bob,Cat2\n"
        resp = client.post(
            "/roster",
            data={"run": "Lap 3 / Nearside"},
            files={"roster": ("roster.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["run"] == "lap-3-nearside"
        assert body["count"] == 2

    def test_post_roster_creates_files(self, tmp_path):
        client, stub = _make_client_with_stub_engine(tmp_path)
        csv_bytes = b"101,Alice,Cat1\n"
        client.post(
            "/roster",
            data={"run": "Lap 3 / Nearside"},
            files={"roster": ("roster.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        run_dir = tmp_path / "lap-3-nearside"
        assert (run_dir / "roster.csv").exists()
        assert not (run_dir / "roster.txt").exists()

    def test_post_roster_malformed_returns_400(self, tmp_path):
        client, _ = _make_client_with_stub_engine(tmp_path)
        csv_bytes = b"number,name,category\n"  # header-only
        resp = client.post(
            "/roster",
            data={"run": "myrun"},
            files={"roster": ("roster.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["status"] == "error"
        assert "detail" in body

    def test_post_roster_blank_run_returns_400(self, tmp_path):
        client, _ = _make_client_with_stub_engine(tmp_path)
        csv_bytes = b"101,Alice,Cat1\n"
        resp = client.post(
            "/roster",
            data={"run": "   "},
            files={"roster": ("roster.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 400

    def test_post_roster_malformed_leaves_previous_intact(self, tmp_path):
        """FR19: bad upload leaves the previous roster on disk untouched."""
        client, stub = _make_client_with_stub_engine(tmp_path)
        good_csv = b"101,Alice,Cat1\n"
        # First upload — good
        client.post(
            "/roster",
            data={"run": "myrun"},
            files={"roster": ("roster.csv", io.BytesIO(good_csv), "text/csv")},
        )
        first_csv = (tmp_path / "myrun" / "roster.csv").read_text()

        # Second upload — bad
        bad_csv = b"number,name,category\n"
        resp = client.post(
            "/roster",
            data={"run": "myrun"},
            files={"roster": ("roster.csv", io.BytesIO(bad_csv), "text/csv")},
        )
        assert resp.status_code == 400
        assert (tmp_path / "myrun" / "roster.csv").read_text() == first_csv

    def test_get_runs_lists_rostered_run(self, tmp_path):
        client, _ = _make_client_with_stub_engine(tmp_path)
        # Upload a roster first
        csv_bytes = b"101,Alice,Cat1\n"
        client.post(
            "/roster",
            data={"run": "Lap 3 / Nearside"},
            files={"roster": ("roster.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        resp = client.get("/runs")
        assert resp.status_code == 200
        body = resp.json()
        assert "lap-3-nearside" in body["runs"]

    def test_get_runs_no_engine_returns_empty(self, tmp_path):
        """With no engine (live disabled), GET /runs returns {"runs": []}."""
        cfg = _make_cfg(tmp_path)
        app = create_app(cfg)  # engine=None
        from fastapi.testclient import TestClient as _TC
        client = _TC(app)
        resp = client.get("/runs")
        assert resp.status_code == 200
        assert resp.json() == {"runs": []}

    def test_post_roster_no_engine_returns_503(self, tmp_path):
        """With no engine (live disabled), POST /roster returns 503."""
        cfg = _make_cfg(tmp_path)
        app = create_app(cfg)  # engine=None
        from fastapi.testclient import TestClient as _TC
        client = _TC(app)
        csv_bytes = b"101,Alice,Cat1\n"
        resp = client.post(
            "/roster",
            data={"run": "myrun"},
            files={"roster": ("roster.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "error"
        assert "disabled" in body["detail"]
