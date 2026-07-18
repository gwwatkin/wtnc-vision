"""results_models.py — Crossing dataclass + internal _OpenCrossing state.

Crossing is the public crossing object serialised for GET /results.
_OpenCrossing is the engine's in-memory dedup state (per §6.1).
Candidate is the public candidate object serialised for GET /candidates.
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
    # ── new (this spec) ──
    source: str = "auto"            # "auto" | "manual"   (manual incl. promoted candidates)
    edited: bool = False            # an operator changed number/rider after creation
    deleted: bool = False           # soft delete — excluded from /results, kept on disk
    order_key: float = 0.0          # order-of-record sort key; 0.0 ⇒ derive from time on load
    order_overridden: bool = False  # operator moved this crossing (badge, D3)


@dataclass
class Candidate:
    """Public candidate object serialised for GET /candidates."""
    candidate_id: str          # f"{run}-cand-{first_seen_epoch_ms}"
    run: str
    time: str                  # ISO-8601 first_seen — its timeline position
    last_seen: str             # newest non-confident detection folded in
    frame_count: int           # detections folded into this candidate
    hint_number: str | None    # most-frequent needs_review number in the span (OQ3)
    hint_conf: float           # best needs_review confidence, else 0.0
    rep_filename: str          # root-relative path of representative frame
    rep_box: list[float]       # [x1,y1,x2,y2] rider box on rep frame (client overlay)
    state: str                 # "open" | "promoted" | "dismissed" | "suppressed"
    promoted_crossing_id: str | None = None


@dataclass
class _OpenCrossing:
    """Internal dedup state held in ResultsEngine._open."""
    crossing_id: str
    first_seen: str    # ISO-8601
    last_seen: str     # ISO-8601
    best_conf: float
    absorb_only: bool = False   # folds update last_seen ONLY — no confidence bump,
                                # no re-annotation, no new crossing (FR22, §7)
