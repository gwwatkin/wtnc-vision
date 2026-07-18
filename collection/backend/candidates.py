"""candidates.py — CandidateTracker: groups non-confident detections into candidates.

Stub implementation for wave-A scaffold (task1). All method bodies raise
NotImplementedError; task2 provides the real implementation.

Thread-safety note (refinement 5): CandidateTracker is NOT internally
thread-safe. Every call from the worker thread (observe, suppress_around) and
from HTTP handlers (set_state) MUST be made while the caller holds the engine's
self._lock (threading.RLock). Do NOT add a separate lock inside this class.
"""
from __future__ import annotations

from .results_models import Candidate


class CandidateTracker:
    """Groups non-confident detections into reviewable candidates (§4.2).

    NOT thread-safe — callers hold the engine lock (design §8, refinement 5).
    """

    def __init__(
        self,
        run_root: str,
        window_s: float,
        min_det_conf: float,
        statuses: tuple[str, ...],
    ) -> None:
        """Initialise the tracker.

        Args:
            run_root: path to the storage root (holds runs/<run>/ dirs).
            window_s: grouping window in seconds; detections within this span
                      of the open candidate's last_seen are folded in.
            min_det_conf: minimum YOLO detection confidence; weaker boxes
                          are ignored (noise floor).
            statuses: tuple of CrossingResult statuses that feed candidates,
                      e.g. ("needs_review", "rejected").
        """
        self._run_root = run_root
        self._window_s = window_s
        self._min_det_conf = min_det_conf
        self._statuses = statuses

    def load_existing(self) -> None:
        """Scan runs/*/candidates.json on engine start.

        Loads persisted candidate state so a restart doesn't lose history.
        """
        raise NotImplementedError

    def observe(
        self,
        run: str,
        ts: str,
        filename: str,
        results: list,
        had_confident: bool,
    ) -> None:
        """Worker thread hook called after every pipeline.run call.

        Folds each result with status in self._statuses and
        det_conf >= min_det_conf into the run's single open candidate.

        - had_confident=True (frame also produced a confident fold) ⇒ ignore
          the frame entirely (FR15).
        - ts − open.last_seen <= window_s ⇒ fold; else leave the old candidate
          open for the operator and start a new one.

        Persists candidates.json on every mutation (atomic temp+os.replace).
        """
        raise NotImplementedError

    def suppress_around(self, run: str, ts: str) -> None:
        """Called on EVERY confident fold (new crossing, same-crossing update,
        or absorb-only).

        Any OPEN candidate whose [time, last_seen] span overlaps ts ± window_s
        transitions to state="suppressed". Promoted/dismissed states never change.
        """
        raise NotImplementedError

    def list(self, run: str) -> list[Candidate]:
        """Return all candidates for the run (all states)."""
        raise NotImplementedError

    def get(self, candidate_id: str) -> Candidate | None:
        """Return a single candidate by id, or None if not found."""
        raise NotImplementedError

    def set_state(
        self,
        candidate_id: str,
        state: str,
        promoted_crossing_id: str | None = None,
    ) -> Candidate:
        """Transition a candidate to a new state.

        Only "promoted" and "dismissed" are accepted via this method.
        Raises ValueError on unknown candidate_id or unsupported state.
        """
        raise NotImplementedError
