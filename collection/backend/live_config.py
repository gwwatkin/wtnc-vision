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
    # ── new (this spec) ──
    candidates_enabled: bool = True
    candidate_statuses: tuple[str, ...] = ("needs_review", "rejected")
    candidate_window_s: float = 5.0     # loader resolves: absent key ⇒ dedup_window_s
    candidate_min_det_conf: float = 0.5
    frames_index_enabled: bool = True


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

    dedup_window_s = float(live.get("dedup_window_s", 5.0))

    # Parse candidates block (§9)
    candidates_block = live.get("candidates", {}) or {}
    candidates_enabled = bool(candidates_block.get("enabled", True))
    candidate_statuses = tuple(
        candidates_block.get("statuses", ["needs_review", "rejected"])
    )
    # absent window_s ⇒ inherit dedup_window_s at load time
    if "window_s" in candidates_block:
        candidate_window_s = float(candidates_block["window_s"])
    else:
        candidate_window_s = dedup_window_s
    candidate_min_det_conf = float(candidates_block.get("min_det_conf", 0.5))

    # Parse frames_index block (§9)
    frames_block = live.get("frames_index", {}) or {}
    frames_index_enabled = bool(frames_block.get("enabled", True))

    return LiveConfig(
        enabled=True,
        cv_config_path=cv_config_path,
        dedup_window_s=dedup_window_s,
        statuses=tuple(live.get("statuses", ["confident"])),
        candidates_enabled=candidates_enabled,
        candidate_statuses=candidate_statuses,
        candidate_window_s=candidate_window_s,
        candidate_min_det_conf=candidate_min_det_conf,
        frames_index_enabled=frames_index_enabled,
    )
