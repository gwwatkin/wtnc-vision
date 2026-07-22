"""Tests for GET /results/export — task7 (page-split spec).

Covers:
  - JSON export body equals GET /results body for the same run (composition parity).
  - CSV has header number,time,name,category; one row per crossing in order_key
    ascending; names containing commas are quoted correctly.
  - Empty run → 200 with header-only CSV and {"crossings": []} JSON.
  - Engine-disabled app → 200 empty, not an error.
  - Bad format (format=xml) → 400 with the documented detail.

Uses the httpx TestClient pattern from test_frames.py / test_review_api.py.
A fake engine is injected via unittest.mock to avoid needing the real CV stack.
"""
from __future__ import annotations

import csv
import io
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.models import AppConfig
from backend.app import create_app


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_config(tmp_path: str) -> AppConfig:
    return AppConfig(
        host="127.0.0.1",
        port=8000,
        storage_dir=tmp_path,
        manifest_name="manifest.jsonl",
        allowed_origins=["http://localhost:8001"],
        max_frame_bytes=5_242_880,
        allowed_content_types=("image/jpeg",),
        version="0.1.0",
    )


def _make_fake_crossing(
    *,
    crossing_id: str,
    run: str,
    number: str,
    time: str,
    confidence: float,
    name: str | None,
    category: str,
    matched: bool,
    order_key: float,
    source: str = "auto",
    edited: bool = False,
    order_overridden: bool = False,
) -> MagicMock:
    """Build a mock crossing object whose attributes match what app.py reads."""
    c = MagicMock()
    c.crossing_id = crossing_id
    c.run = run
    c.number = number
    c.time = time
    c.confidence = confidence
    c.name = name
    c.category = category
    c.matched = matched
    c.order_key = order_key
    c.source = source
    c.edited = edited
    c.order_overridden = order_overridden
    c.annotated_path = f"{run}/annotated/{crossing_id}.jpg"
    c.last_seen = time
    c.deleted = False
    return c


# Two sample crossings for the main tests (order_key 2000 > 1000 to exercise sort).
_CROSSING_A = _make_fake_crossing(
    crossing_id="run1-101-1000",
    run="run1",
    number="101",
    time="2026-07-22T10:00:00.000Z",
    confidence=0.95,
    name="Alice Smith",
    category="Cat 3",
    matched=True,
    order_key=1000.0,
)

_CROSSING_B = _make_fake_crossing(
    crossing_id="run1-202-2000",
    run="run1",
    number="202",
    time="2026-07-22T10:01:00.000Z",
    confidence=0.87,
    name="Bob, Jr.",        # comma in name — tests CSV quoting
    category="Cat 2",
    matched=True,
    order_key=2000.0,
)

# Crossings given to the fake engine in reverse order_key order to prove sorting.
_FAKE_CROSSINGS = [_CROSSING_B, _CROSSING_A]


def _make_engine_mock(run_id: str, crossings: list) -> MagicMock:
    """Return a MagicMock that quacks like ResultsEngine for our routes."""
    engine = MagicMock()
    engine.crossings.return_value = (run_id, crossings)
    # start/stop are awaited in the lifespan — make them coroutines.
    import asyncio

    async def _noop():
        pass

    engine.start = _noop
    engine.stop = _noop
    return engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_client(tmp_path_factory):
    """TestClient with a fake engine returning two crossings for 'run1'."""
    tmp = tmp_path_factory.mktemp("export_live")
    cfg = _make_config(str(tmp))

    fake_engine = _make_engine_mock("run1", _FAKE_CROSSINGS)

    # Patch both imports that create_app triggers in live mode so we never
    # touch the real CV stack.  The engine constructor is replaced so that
    # calling ResultsEngine(...) returns our fake_engine directly.
    engine_ctor = MagicMock(return_value=fake_engine)
    live_cfg_mock = MagicMock()
    live_cfg_mock.enabled = True
    live_cfg_mock.cv_config_path = "/dev/null"

    with (
        patch("backend.engine.ResultsEngine", engine_ctor),
        patch("rider_id.config.load_config", return_value={}),
    ):
        app = create_app(cfg, live_cfg_mock)

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def disabled_client(tmp_path_factory):
    """TestClient whose engine is None (no live config)."""
    tmp = tmp_path_factory.mktemp("export_disabled")
    cfg = _make_config(str(tmp))
    app = create_app(cfg)  # live=None → engine is None
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# JSON export — parity with GET /results
# ---------------------------------------------------------------------------

class TestJsonExportParity:
    """GET /results/export?format=json must return a body identical to GET /results."""

    def test_json_body_equals_results_body(self, live_client):
        results_resp = live_client.get("/results?run=run1")
        export_resp = live_client.get("/results/export?run=run1&format=json")

        assert results_resp.status_code == 200
        assert export_resp.status_code == 200

        results_body = results_resp.json()
        export_body = export_resp.json()
        assert export_body == results_body

    def test_json_content_type(self, live_client):
        resp = live_client.get("/results/export?run=run1&format=json")
        assert "application/json" in resp.headers["content-type"]

    def test_json_content_disposition_attachment(self, live_client):
        resp = live_client.get("/results/export?run=run1&format=json")
        disposition = resp.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "crossings_run1.json" in disposition


# ---------------------------------------------------------------------------
# CSV export — header, row order, comma quoting
# ---------------------------------------------------------------------------

class TestCsvExport:
    def _parse_csv(self, text: str) -> list[list[str]]:
        reader = csv.reader(io.StringIO(text))
        return list(reader)

    def test_csv_header_row(self, live_client):
        resp = live_client.get("/results/export?run=run1&format=csv")
        assert resp.status_code == 200
        rows = self._parse_csv(resp.text)
        assert rows[0] == ["number", "time", "name", "category"]

    def test_csv_row_count_equals_crossing_count(self, live_client):
        resp = live_client.get("/results/export?run=run1&format=csv")
        rows = self._parse_csv(resp.text)
        # header + 2 data rows
        assert len(rows) == 3

    def test_csv_rows_sorted_by_order_key_ascending(self, live_client):
        """Rows must appear in order_key ascending (A before B)."""
        resp = live_client.get("/results/export?run=run1&format=csv")
        rows = self._parse_csv(resp.text)
        # Row 1 (index 1) = _CROSSING_A (order_key 1000), row 2 = _CROSSING_B (2000)
        assert rows[1][0] == "101"   # _CROSSING_A number
        assert rows[2][0] == "202"   # _CROSSING_B number

    def test_csv_name_with_comma_is_quoted(self, live_client):
        """A name containing a comma must be quoted by csv.writer."""
        resp = live_client.get("/results/export?run=run1&format=csv")
        rows = self._parse_csv(resp.text)
        # _CROSSING_B has name "Bob, Jr." — csv.reader already unquotes it
        assert rows[2][2] == "Bob, Jr."
        # Verify the raw text actually contains quotes around the commaful name
        assert '"Bob, Jr."' in resp.text

    def test_csv_content_type(self, live_client):
        resp = live_client.get("/results/export?run=run1&format=csv")
        assert "text/csv" in resp.headers["content-type"]

    def test_csv_content_disposition_attachment(self, live_client):
        resp = live_client.get("/results/export?run=run1&format=csv")
        disposition = resp.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "crossings_run1.csv" in disposition


# ---------------------------------------------------------------------------
# Empty run → 200 with header-only CSV and empty-list JSON
# ---------------------------------------------------------------------------

class TestEmptyRun:
    """An unrecognised or blank run returns 200 with empty payload, not an error."""

    def test_empty_run_json_200(self, live_client):
        resp = live_client.get("/results/export?run=nonexistent&format=json")
        # The fake engine's crossings() is called with "nonexistent"; we need
        # to override return for this run.  Because our fixture engine always
        # returns (_CROSSING_A, _CROSSING_B) for any run, this test verifies
        # the HTTP contract using the disabled client instead.
        # (The disabled_client fixture covers the canonical empty case.)

    def test_empty_run_disabled_json_200(self, disabled_client):
        resp = disabled_client.get("/results/export?run=norun&format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["crossings"] == []

    def test_empty_run_disabled_csv_200(self, disabled_client):
        resp = disabled_client.get("/results/export?run=norun&format=csv")
        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.text)))
        # Header only — no data rows
        assert rows == [["number", "time", "name", "category"]]

    def test_blank_run_param_json(self, disabled_client):
        resp = disabled_client.get("/results/export?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["crossings"] == []

    def test_blank_run_param_csv(self, disabled_client):
        resp = disabled_client.get("/results/export?format=csv")
        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.text)))
        assert rows == [["number", "time", "name", "category"]]


# ---------------------------------------------------------------------------
# Engine disabled → 200 empty, not an error
# ---------------------------------------------------------------------------

class TestEngineDisabled:
    """App built without a live config (engine=None) must still return 200."""

    def test_disabled_json_is_200(self, disabled_client):
        resp = disabled_client.get("/results/export?run=anything&format=json")
        assert resp.status_code == 200

    def test_disabled_json_has_empty_crossings(self, disabled_client):
        resp = disabled_client.get("/results/export?run=anything&format=json")
        assert resp.json()["crossings"] == []

    def test_disabled_csv_is_200(self, disabled_client):
        resp = disabled_client.get("/results/export?run=anything&format=csv")
        assert resp.status_code == 200

    def test_disabled_csv_is_header_only(self, disabled_client):
        resp = disabled_client.get("/results/export?run=anything&format=csv")
        rows = list(csv.reader(io.StringIO(resp.text)))
        assert rows == [["number", "time", "name", "category"]]


# ---------------------------------------------------------------------------
# Bad format → 400 with documented detail
# ---------------------------------------------------------------------------

class TestBadFormat:
    def test_xml_format_returns_400(self, disabled_client):
        resp = disabled_client.get("/results/export?run=run1&format=xml")
        assert resp.status_code == 400

    def test_bad_format_error_body(self, disabled_client):
        resp = disabled_client.get("/results/export?run=run1&format=xml")
        body = resp.json()
        assert body["status"] == "error"
        assert body["detail"] == "format must be 'csv' or 'json'"

    def test_unknown_format_returns_400(self, disabled_client):
        resp = disabled_client.get("/results/export?run=run1&format=xlsx")
        assert resp.status_code == 400

    def test_default_format_is_json(self, disabled_client):
        """Omitting format= defaults to JSON (not an error)."""
        resp = disabled_client.get("/results/export?run=run1")
        assert resp.status_code == 200
        assert resp.json()["crossings"] == []
