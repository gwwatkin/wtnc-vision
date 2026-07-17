"""results_models.py — Crossing dataclass + internal _OpenCrossing state.

Crossing is the public crossing object serialised for GET /results.
_OpenCrossing is the engine's in-memory dedup state (per §6.1).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Crossing:
    crossing_id: str        # f"{run}-{number}-{first_seen_epoch_ms}"
    run: str                # safe-label run id this crossing belongs to
    number: str             # validated race number
    time: str               # ISO-8601 — client_ts of the first confident read (OQ2)
    confidence: float       # best confidence among the reads folded in so far
    name: str | None        # roster name, or None when unmatched
    category: str           # roster category, or "Unknown"
    matched: bool           # roster had this number
    annotated_path: str     # relative to storage root, e.g. "<run>/annotated/<id>.jpg"
    last_seen: str          # ISO-8601 — newest read folded in; persisted for dedup restart


@dataclass
class _OpenCrossing:
    """Internal dedup state held in ResultsEngine._open."""
    crossing_id: str
    first_seen: str    # ISO-8601
    last_seen: str     # ISO-8601
    best_conf: float
