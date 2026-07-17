"""live_config.py — LiveConfig dataclass + load_live_config(path).

Parses the `live:` section of the back-end config.yaml.
Returns None when the section is absent or enabled is false.
"""
from __future__ import annotations

from dataclasses import dataclass

import yaml


@dataclass
class LiveConfig:
    enabled: bool
    cv_config_path: str          # path to repo POC config.yaml
    dedup_window_s: float
    statuses: tuple[str, ...]    # e.g. ("confident",)


def load_live_config(path: str) -> LiveConfig | None:
    """Parse the `live:` section of the back-end config.yaml.

    Returns None when the section is absent or when enabled is false,
    meaning live processing is disabled.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    live = raw.get("live")
    if live is None:
        return None

    enabled = bool(live.get("enabled", False))
    if not enabled:
        return None

    # Resolve cv_config relative to the config.yaml's directory
    import os
    config_dir = os.path.dirname(os.path.abspath(path))
    cv_config_raw = live["cv_config"]
    cv_config_path = os.path.normpath(os.path.join(config_dir, cv_config_raw))

    return LiveConfig(
        enabled=True,
        cv_config_path=cv_config_path,
        dedup_window_s=float(live.get("dedup_window_s", 5.0)),
        statuses=tuple(live.get("statuses", ["confident"])),
    )
