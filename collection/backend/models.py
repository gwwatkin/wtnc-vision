"""Frozen dataclasses for the collection back-end.

DO NOT CHANGE — downstream tasks (task2, task3, task4) depend on these exact
field names and types. See design §6.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppConfig:
    host: str
    port: int
    storage_dir: str
    manifest_name: str            # e.g. "manifest.jsonl"
    allowed_origins: list[str]    # CORS
    max_frame_bytes: int
    allowed_content_types: tuple[str, ...]   # e.g. ("image/jpeg",)
    version: str


@dataclass
class FrameMeta:
    label: str
    seq: int
    session_id: str | None
    client_ts: str                # ISO-8601 from client
    content_type: str


@dataclass
class StoredFrame:
    filename: str                 # relative to storage_dir, e.g. "101/101_..._000123.jpg"
    safe_label: str
    server_ts: str                # ISO-8601 UTC, ms precision
    bytes: int
