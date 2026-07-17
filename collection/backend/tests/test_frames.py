"""Tests for the collection back-end — Task 3 scope.

Covers:
  - GET /health (kept from task1)
  - FrameStore.safe_label edge-cases
  - POST /frames happy path: 201, file written under <safe>/collected/, bytes match,
    per-run manifest line, "run" field in response
  - POST /frames error paths: 415, 400 (missing/blank label, bad seq), 413
  - Two labels → two run dirs, two separate manifests, no global manifest
  - Restart-safe: two saves to one label → two lines in that run's manifest
"""
from __future__ import annotations

import io
import json
import os
import struct

import pytest
from fastapi.testclient import TestClient

from backend.models import AppConfig
from backend.app import create_app
from backend.storage import FrameStore

# ---------------------------------------------------------------------------
# Minimal valid JPEG bytes (SOI + EOI markers — small but structurally valid
# enough for content-type / size tests; not a renderable image).
# We also have the real ridersFromThBack.jpg for byte-identity checks.
# ---------------------------------------------------------------------------

# A 3-byte JPEG that satisfies header checks: SOI (0xFFD8) + EOI (0xFFD9)
_TINY_JPEG = bytes([0xFF, 0xD8, 0xFF, 0xD9])

# Path to the real sample JPEG in the repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_SAMPLE_JPEG = os.path.join(_REPO_ROOT, "ridersFromThBack.jpg")


def _make_config(tmp_path: str, max_frame_bytes: int = 5_242_880) -> AppConfig:
    """Build a test AppConfig pointing storage at tmp_path."""
    return AppConfig(
        host="127.0.0.1",
        port=8000,
        storage_dir=tmp_path,
        manifest_name="manifest.jsonl",
        allowed_origins=["http://localhost:8001"],
        max_frame_bytes=max_frame_bytes,
        allowed_content_types=("image/jpeg",),
        version="0.1.0",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_client(tmp_path):
    """TestClient whose FrameStore writes to a fresh tmp directory."""
    cfg = _make_config(str(tmp_path))
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c, tmp_path


@pytest.fixture(scope="module")
def real_client():
    """Module-scoped client backed by the real config.yaml (for /health test)."""
    _backend_dir = os.path.join(os.path.dirname(__file__), "..")
    _config_path = os.path.abspath(os.path.join(_backend_dir, "config.yaml"))
    from backend.config import load_config
    cfg = load_config(_config_path)
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# /health (task1 smoke test — kept)
# ---------------------------------------------------------------------------

def test_health_ok(real_client):
    resp = real_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# FrameStore.safe_label
# ---------------------------------------------------------------------------

class TestSafeLabel:
    def test_numeric_label_unchanged(self):
        assert FrameStore.safe_label("101") == "101"

    def test_mixed_case_and_spaces(self):
        assert FrameStore.safe_label("Lap 3 / Nearside") == "lap-3-nearside"

    def test_empty_string_becomes_unlabeled(self):
        assert FrameStore.safe_label("") == "unlabeled"

    def test_only_special_chars_becomes_unlabeled(self):
        assert FrameStore.safe_label("!@#$%") == "unlabeled"

    def test_leading_trailing_special_stripped(self):
        assert FrameStore.safe_label("--hello--") == "hello"

    def test_capped_at_64_chars(self):
        long_label = "a" * 100
        result = FrameStore.safe_label(long_label)
        assert len(result) == 64

    def test_over_long_with_separators_capped(self):
        # Make a label that after collapse is > 64 chars
        long_label = "ab" * 40  # "ababab..." = 80 chars, all [a-z0-9], so stays as-is
        result = FrameStore.safe_label(long_label)
        assert len(result) == 64

    def test_consecutive_separators_collapsed(self):
        assert FrameStore.safe_label("hello   world") == "hello-world"

    def test_mixed_separators_collapsed(self):
        assert FrameStore.safe_label("foo/bar-baz") == "foo-bar-baz"

    def test_whitespace_only_becomes_unlabeled(self):
        assert FrameStore.safe_label("   ") == "unlabeled"


# ---------------------------------------------------------------------------
# POST /frames — happy path (per-run layout)
# ---------------------------------------------------------------------------

def test_post_frames_happy_path(tmp_client):
    client, tmp_path = tmp_client

    resp = client.post(
        "/frames",
        files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
        data={
            "label": "101",
            "client_ts": "2026-07-11T09:30:15.482Z",
            "seq": "0",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ok"
    assert body["seq"] == 0
    assert "server_ts" in body
    assert "stored" in body

    # Response must include the safe run id (task1 additive field)
    assert body["run"] == "101"

    # Stored path is root-relative: <safe>/collected/<filename>
    stored_rel = body["stored"]
    assert stored_rel.startswith("101/collected/101_"), (
        f"expected '101/collected/101_...' prefix, got {stored_rel!r}"
    )
    assert stored_rel.endswith(".jpg")

    # File must exist at <tmp_path>/<safe>/collected/<name>.jpg
    abs_stored = os.path.join(str(tmp_path), stored_rel)
    assert os.path.isfile(abs_stored), f"frame not found at {abs_stored}"
    with open(abs_stored, "rb") as fh:
        on_disk = fh.read()
    assert on_disk == _TINY_JPEG

    # Per-run manifest at <tmp>/101/manifest.jsonl (not a global manifest)
    manifest_path = os.path.join(str(tmp_path), "101", "manifest.jsonl")
    assert os.path.isfile(manifest_path), f"per-run manifest not found at {manifest_path}"

    # No global manifest at storage root
    global_manifest = os.path.join(str(tmp_path), "manifest.jsonl")
    assert not os.path.isfile(global_manifest), "global manifest must not exist"

    with open(manifest_path, encoding="utf-8") as fh:
        lines = [l.strip() for l in fh if l.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["label"] == "101"
    assert record["safe_label"] == "101"
    # filename is root-relative: <safe>/collected/<name>.jpg (README refinement 2)
    assert record["filename"] == stored_rel
    assert record["filename"].startswith("101/collected/")
    assert record["seq"] == 0
    assert record["client_ts"] == "2026-07-11T09:30:15.482Z"
    assert record["bytes"] == len(_TINY_JPEG)
    assert record["content_type"] == "image/jpeg"
    assert "server_ts" in record


def test_post_frames_with_session_id(tmp_client):
    client, tmp_path = tmp_client

    resp = client.post(
        "/frames",
        files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
        data={
            "label": "202",
            "client_ts": "2026-07-11T10:00:00.000Z",
            "seq": "5",
            "session_id": "test-session-uuid",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["seq"] == 5
    assert body["run"] == "202"

    # Per-run manifest for label "202"
    manifest_path = os.path.join(str(tmp_path), "202", "manifest.jsonl")
    with open(manifest_path, encoding="utf-8") as fh:
        records = [json.loads(l) for l in fh if l.strip()]
    matching = [r for r in records if r["label"] == "202"]
    assert len(matching) == 1
    assert matching[0]["session_id"] == "test-session-uuid"


# ---------------------------------------------------------------------------
# POST /frames — 415 wrong content-type
# ---------------------------------------------------------------------------

def test_post_frames_415_wrong_content_type(tmp_client):
    client, _ = tmp_client

    resp = client.post(
        "/frames",
        files={"image": ("frame.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        data={
            "label": "101",
            "client_ts": "2026-07-11T09:30:15.482Z",
            "seq": "0",
        },
    )
    assert resp.status_code == 415
    body = resp.json()
    assert body["status"] == "error"
    assert "detail" in body


# ---------------------------------------------------------------------------
# POST /frames — 400 validation errors
# ---------------------------------------------------------------------------

def test_post_frames_400_missing_label(tmp_client):
    client, _ = tmp_client

    # label field omitted
    resp = client.post(
        "/frames",
        files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
        data={
            "client_ts": "2026-07-11T09:30:15.482Z",
            "seq": "0",
        },
    )
    # A missing required Form field is mapped to the documented 400 + error body
    # (design §4) by the RequestValidationError handler, not FastAPI's default 422.
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error"
    assert "label" in body["detail"]


def test_post_frames_400_blank_label(tmp_client):
    client, _ = tmp_client

    resp = client.post(
        "/frames",
        files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
        data={
            "label": "   ",
            "client_ts": "2026-07-11T09:30:15.482Z",
            "seq": "0",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error"
    assert "label" in body["detail"].lower()


def test_post_frames_400_bad_seq_non_integer(tmp_client):
    client, _ = tmp_client

    resp = client.post(
        "/frames",
        files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
        data={
            "label": "101",
            "client_ts": "2026-07-11T09:30:15.482Z",
            "seq": "notanumber",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error"
    assert "seq" in body["detail"].lower()


def test_post_frames_400_bad_seq_negative(tmp_client):
    client, _ = tmp_client

    resp = client.post(
        "/frames",
        files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
        data={
            "label": "101",
            "client_ts": "2026-07-11T09:30:15.482Z",
            "seq": "-1",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error"


def test_post_frames_400_empty_image(tmp_client):
    client, _ = tmp_client

    resp = client.post(
        "/frames",
        files={"image": ("frame.jpg", io.BytesIO(b""), "image/jpeg")},
        data={
            "label": "101",
            "client_ts": "2026-07-11T09:30:15.482Z",
            "seq": "0",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["status"] == "error"


# ---------------------------------------------------------------------------
# POST /frames — 413 oversized image
# ---------------------------------------------------------------------------

def test_post_frames_413_oversized(tmp_path):
    # Use a tiny max_frame_bytes so our JPEG trips it
    cfg = _make_config(str(tmp_path), max_frame_bytes=3)
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.post(
            "/frames",
            files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
            data={
                "label": "101",
                "client_ts": "2026-07-11T09:30:15.482Z",
                "seq": "0",
            },
        )
    assert resp.status_code == 413
    body = resp.json()
    assert body["status"] == "error"
    assert "detail" in body


# ---------------------------------------------------------------------------
# Two labels → two run dirs, two separate manifests, no global manifest
# ---------------------------------------------------------------------------

def test_two_labels_two_run_dirs_two_manifests(tmp_path):
    """Two captures with different labels must produce two isolated run dirs
    each with their own manifest — no global manifest at the storage root."""
    cfg = _make_config(str(tmp_path))
    app = create_app(cfg)
    with TestClient(app) as client:
        for label, seq in [("alpha", "0"), ("beta", "0")]:
            resp = client.post(
                "/frames",
                files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
                data={
                    "label": label,
                    "client_ts": "2026-07-11T09:30:15.000Z",
                    "seq": seq,
                },
            )
            assert resp.status_code == 201
            assert resp.json()["run"] == label

    # Each label has its own run dir and manifest
    alpha_manifest = os.path.join(str(tmp_path), "alpha", "manifest.jsonl")
    beta_manifest = os.path.join(str(tmp_path), "beta", "manifest.jsonl")
    assert os.path.isfile(alpha_manifest), "alpha run manifest missing"
    assert os.path.isfile(beta_manifest), "beta run manifest missing"

    # Each manifest has exactly one line for its own run only
    with open(alpha_manifest, encoding="utf-8") as fh:
        alpha_records = [json.loads(l) for l in fh if l.strip()]
    assert len(alpha_records) == 1
    assert alpha_records[0]["safe_label"] == "alpha"

    with open(beta_manifest, encoding="utf-8") as fh:
        beta_records = [json.loads(l) for l in fh if l.strip()]
    assert len(beta_records) == 1
    assert beta_records[0]["safe_label"] == "beta"

    # No global manifest at storage root
    global_manifest = os.path.join(str(tmp_path), "manifest.jsonl")
    assert not os.path.isfile(global_manifest), "global manifest must not exist"

    # Frame files are in <safe>/collected/
    alpha_collected = os.path.join(str(tmp_path), "alpha", "collected")
    beta_collected = os.path.join(str(tmp_path), "beta", "collected")
    assert os.path.isdir(alpha_collected), "alpha/collected/ dir missing"
    assert os.path.isdir(beta_collected), "beta/collected/ dir missing"

    alpha_files = [f for f in os.listdir(alpha_collected) if f.endswith(".jpg")]
    beta_files = [f for f in os.listdir(beta_collected) if f.endswith(".jpg")]
    assert len(alpha_files) == 1
    assert len(beta_files) == 1


# ---------------------------------------------------------------------------
# Restart-safe: two saves append two lines to that run's manifest
# ---------------------------------------------------------------------------

def test_restart_safe_two_saves(tmp_client):
    client, tmp_path = tmp_client

    for i in range(2):
        resp = client.post(
            "/frames",
            files={"image": ("frame.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
            data={
                "label": "restart-test",
                "client_ts": f"2026-07-11T09:30:1{i}.000Z",
                "seq": str(i),
            },
        )
        assert resp.status_code == 201

    # Per-run manifest for "restart-test" (safe_label = "restart-test")
    manifest_path = os.path.join(str(tmp_path), "restart-test", "manifest.jsonl")
    assert os.path.isfile(manifest_path), f"per-run manifest missing at {manifest_path}"
    with open(manifest_path, encoding="utf-8") as fh:
        lines = [l.strip() for l in fh if l.strip() and json.loads(l)["label"] == "restart-test"]
    assert len(lines) == 2

    # Verify both stored files still exist with correct bytes
    for line in lines:
        record = json.loads(line)
        abs_path = os.path.join(str(tmp_path), record["filename"])
        assert os.path.isfile(abs_path), f"stored frame missing at {abs_path}"
        with open(abs_path, "rb") as fh:
            assert fh.read() == _TINY_JPEG


def test_restart_safe_existing_files_untouched(tmp_path):
    """Simulate a restart: create a second FrameStore on the same root; prior data intact.
    Each label's manifest is per-run; there is no global manifest."""
    cfg = _make_config(str(tmp_path))
    app1 = create_app(cfg)
    with TestClient(app1) as c1:
        r = c1.post(
            "/frames",
            files={"image": ("f.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
            data={"label": "before-restart", "client_ts": "2026-01-01T00:00:00.000Z", "seq": "0"},
        )
        assert r.status_code == 201
        first_stored = r.json()["stored"]
        assert "before-restart/collected/" in first_stored

    # "Restart" — new app instance, same storage root
    app2 = create_app(cfg)
    with TestClient(app2) as c2:
        r2 = c2.post(
            "/frames",
            files={"image": ("f.jpg", io.BytesIO(_TINY_JPEG), "image/jpeg")},
            data={"label": "after-restart", "client_ts": "2026-01-01T00:00:01.000Z", "seq": "0"},
        )
        assert r2.status_code == 201
        second_stored = r2.json()["stored"]
        assert "after-restart/collected/" in second_stored

    # Both files exist on disk
    assert os.path.isfile(os.path.join(str(tmp_path), first_stored))
    assert os.path.isfile(os.path.join(str(tmp_path), second_stored))

    # Each label has its own per-run manifest with one line
    before_manifest = os.path.join(str(tmp_path), "before-restart", "manifest.jsonl")
    after_manifest = os.path.join(str(tmp_path), "after-restart", "manifest.jsonl")
    assert os.path.isfile(before_manifest), "before-restart manifest missing"
    assert os.path.isfile(after_manifest), "after-restart manifest missing"

    with open(before_manifest, encoding="utf-8") as fh:
        before_lines = [l.strip() for l in fh if l.strip()]
    assert len(before_lines) == 1
    assert json.loads(before_lines[0])["label"] == "before-restart"

    with open(after_manifest, encoding="utf-8") as fh:
        after_lines = [l.strip() for l in fh if l.strip()]
    assert len(after_lines) == 1
    assert json.loads(after_lines[0])["label"] == "after-restart"

    # No global manifest at storage root
    global_manifest = os.path.join(str(tmp_path), "manifest.jsonl")
    assert not os.path.isfile(global_manifest), "global manifest must not exist"


# ---------------------------------------------------------------------------
# Byte-identity test using the real sample JPEG
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.isfile(_SAMPLE_JPEG), reason="ridersFromThBack.jpg not found")
def test_stored_bytes_identical_to_source(tmp_path):
    """Stored file must be byte-identical to the uploaded JPEG (verbatim store, NFR1)."""
    with open(_SAMPLE_JPEG, "rb") as fh:
        jpeg_bytes = fh.read()

    cfg = _make_config(str(tmp_path))
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.post(
            "/frames",
            files={"image": ("ridersFromThBack.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            data={
                "label": "101",
                "client_ts": "2026-07-11T09:30:15.482Z",
                "seq": "123",
            },
        )
    assert resp.status_code == 201
    stored_rel = resp.json()["stored"]
    assert "101/collected/" in stored_rel

    abs_stored = os.path.join(str(tmp_path), stored_rel)
    with open(abs_stored, "rb") as fh:
        on_disk = fh.read()

    assert on_disk == jpeg_bytes, "Stored bytes must be identical to original upload"
