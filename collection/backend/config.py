"""config.py — load_config(path) -> AppConfig.

Parses config.yaml (server, storage, limits sections) into the frozen AppConfig
dataclass. This is implemented here so task2 can rely on it.
"""
from __future__ import annotations

import yaml

from .models import AppConfig


def load_config(path: str) -> AppConfig:
    """Parse *path* (a YAML file) and return an AppConfig.

    Expected YAML structure (design §9):
        server:
          host, port, version, allowed_origins
        storage:
          dir, manifest_name
        limits:
          max_frame_bytes, allowed_content_types
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    server = raw["server"]
    storage = raw["storage"]
    limits = raw["limits"]

    return AppConfig(
        host=server["host"],
        port=int(server["port"]),
        storage_dir=storage["dir"],
        manifest_name=storage["manifest_name"],
        allowed_origins=list(server["allowed_origins"]),
        max_frame_bytes=int(limits["max_frame_bytes"]),
        allowed_content_types=tuple(limits["allowed_content_types"]),
        version=str(server["version"]),
    )
