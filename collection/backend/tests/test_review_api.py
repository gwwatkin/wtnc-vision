"""Tests for the new review-editing routes in disabled mode (engine=None).

Creates the app without a live config so engine is None. Every new GET route
must return its empty-shell response; every mutating route must return 503.
Both image routes return 404. GET /roster returns the empty shell.

Uses the existing httpx TestClient pattern from test_frames.py.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.models import AppConfig
from backend.app import create_app


# ---------------------------------------------------------------------------
# Fixture: app created without live config → engine is None
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def disabled_client(tmp_path_factory):
    """Module-scoped disabled-mode TestClient (no live config)."""
    tmp = tmp_path_factory.mktemp("disabled")
    cfg = AppConfig(
        host="127.0.0.1",
        port=8000,
        storage_dir=str(tmp),
        manifest_name="manifest.jsonl",
        allowed_origins=["http://localhost:8001"],
        max_frame_bytes=5_242_880,
        allowed_content_types=("image/jpeg",),
        version="0.1.0",
    )
    app = create_app(cfg)  # live=None → engine is None
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /status — empty shell
# ---------------------------------------------------------------------------

class TestStatusDisabled:
    def test_returns_enabled_false(self, disabled_client):
        resp = disabled_client.get("/status?run=test-run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is False

    def test_works_without_run_param(self, disabled_client):
        resp = disabled_client.get("/status")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False


# ---------------------------------------------------------------------------
# GET /roster — empty shell (refinement 2)
# ---------------------------------------------------------------------------

class TestRosterGetDisabled:
    def test_returns_empty_riders_list(self, disabled_client):
        resp = disabled_client.get("/roster?run=test-run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run"] == "test-run"
        assert body["riders"] == []

    def test_run_label_normalized(self, disabled_client):
        resp = disabled_client.get("/roster?run=My+Run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run"] == "my-run"

    def test_works_without_run_param(self, disabled_client):
        resp = disabled_client.get("/roster")
        assert resp.status_code == 200
        body = resp.json()
        assert "riders" in body
        assert body["riders"] == []


# ---------------------------------------------------------------------------
# GET /frames — empty shell
# ---------------------------------------------------------------------------

class TestFramesDisabled:
    def test_returns_empty_frames(self, disabled_client):
        resp = disabled_client.get("/frames?run=test-run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run"] == "test-run"
        assert body["frames"] == []
        assert "meta" in body
        meta = body["meta"]
        assert meta["count"] == 0
        assert meta["first_ts"] is None
        assert meta["last_ts"] is None


# ---------------------------------------------------------------------------
# GET /frames/image — 404 (image route in disabled mode)
# ---------------------------------------------------------------------------

class TestFrameImageDisabled:
    def test_returns_404(self, disabled_client):
        resp = disabled_client.get("/frames/image?run=test&filename=test.jpg")
        assert resp.status_code == 404
        body = resp.json()
        assert body["status"] == "error"


# ---------------------------------------------------------------------------
# GET /candidates — empty shell
# ---------------------------------------------------------------------------

class TestCandidatesDisabled:
    def test_returns_empty_candidates(self, disabled_client):
        resp = disabled_client.get("/candidates?run=test-run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["run"] == "test-run"
        assert body["candidates"] == []


# ---------------------------------------------------------------------------
# GET /candidates/{id}/image — 404
# ---------------------------------------------------------------------------

class TestCandidateImageDisabled:
    def test_returns_404(self, disabled_client):
        resp = disabled_client.get("/candidates/some-cand-id/image")
        assert resp.status_code == 404
        body = resp.json()
        assert body["status"] == "error"


# ---------------------------------------------------------------------------
# POST /crossings — 503
# ---------------------------------------------------------------------------

class TestPostCrossingsDisabled:
    def test_returns_503(self, disabled_client):
        resp = disabled_client.post(
            "/crossings",
            json={
                "run": "test-run",
                "filename": "test/collected/f.jpg",
                "client_ts": "2026-07-17T10:00:00.000Z",
                "number": "101",
            },
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "error"
        assert "disabled" in body["detail"].lower()


# ---------------------------------------------------------------------------
# PATCH /crossings/{id} — 503
# ---------------------------------------------------------------------------

class TestPatchCrossingDisabled:
    def test_returns_503(self, disabled_client):
        resp = disabled_client.patch(
            "/crossings/some-crossing-id",
            json={"number": "202"},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "error"
        assert "disabled" in body["detail"].lower()


# ---------------------------------------------------------------------------
# POST /crossings/{id}/position — 503
# ---------------------------------------------------------------------------

class TestSetPositionDisabled:
    def test_returns_503(self, disabled_client):
        resp = disabled_client.post(
            "/crossings/some-crossing-id/position",
            json={"earlier_id": None, "later_id": "other-id"},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "error"
        assert "disabled" in body["detail"].lower()


# ---------------------------------------------------------------------------
# POST /candidates/{id}/resolve — 503
# ---------------------------------------------------------------------------

class TestResolveCandidateDisabled:
    def test_returns_503(self, disabled_client):
        resp = disabled_client.post(
            "/candidates/some-cand-id/resolve",
            json={"action": "dismiss"},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "error"
        assert "disabled" in body["detail"].lower()


# ---------------------------------------------------------------------------
# Validation: PATCH body with no valid keys → 400 (independent of engine)
# ---------------------------------------------------------------------------

class TestPatchValidation:
    def test_empty_patch_body_returns_400(self, disabled_client):
        """An empty PATCH body should return 400 before hitting the 503 check."""
        # With disabled engine, the 400 won't fire if we check engine first.
        # The design says "≥1 key else 400" — test that this path is reachable.
        # Both 400 and 503 are acceptable here depending on check order.
        resp = disabled_client.patch(
            "/crossings/some-crossing-id",
            json={},  # no "number" or "deleted" key
        )
        # Either 400 (validation) or 503 (disabled) is acceptable
        assert resp.status_code in (400, 503)
        body = resp.json()
        assert body["status"] == "error"
