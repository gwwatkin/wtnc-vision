"""candidates.py — CandidateTracker: groups non-confident detections into candidates.

Thread-safety note (refinement 5): CandidateTracker is NOT internally
thread-safe. Every call from the worker thread (observe, suppress_around) and
from HTTP handlers (set_state) MUST be made while the caller holds the engine's
self._lock (threading.RLock). Do NOT add a separate lock inside this class.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
from datetime import datetime, timezone

from .results_models import Candidate

log = logging.getLogger(__name__)


def _epoch_ms(ts: str) -> int:
    """Convert ISO-8601 timestamp string to integer epoch milliseconds."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _ts_seconds(ts: str) -> float:
    """Convert ISO-8601 timestamp string to seconds since epoch (float)."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _box_area(box: tuple | list) -> float:
    """Compute area of an [x1, y1, x2, y2] box; returns 0.0 for degenerate boxes."""
    x1, y1, x2, y2 = box
    w = max(0.0, float(x2) - float(x1))
    h = max(0.0, float(y2) - float(y1))
    return w * h


def _write_candidates_json_atomic(run_dir: str, candidates: list[Candidate]) -> None:
    """Atomically rewrite candidates.json with the full current candidate list."""
    path = os.path.join(run_dir, "candidates.json")
    tmp_path = path + ".tmp"
    data = [dataclasses.asdict(c) for c in candidates]
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp_path, path)


def _load_candidates_json(run_dir: str) -> list[Candidate]:
    """Load candidates.json; return [] on missing or malformed file."""
    path = os.path.join(run_dir, "candidates.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [Candidate(**item) for item in data]
    except FileNotFoundError:
        return []
    except Exception as exc:
        log.warning("Skipping malformed candidates.json in %r: %s", run_dir, exc)
        return []


class CandidateTracker:
    """Groups non-confident detections into reviewable candidates (§4.2).

    NOT thread-safe — callers hold the engine lock (design §8, refinement 5).

    After load_existing, a resumed open candidate restarts its hint tally from its
    persisted hint_number/hint_conf (count 1). This is a known limitation: the full
    per-candidate tally is not persisted, only the winning hint state.
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

        # per-run list of candidates (all states): run -> list[Candidate]
        self._candidates: dict[str, list[Candidate]] = {}
        # id -> Candidate index
        self._index: dict[str, Candidate] = {}
        # per-run hint tally for the open candidate: run -> {number: [count, best_conf]}
        # Structure: {run: {number: [count, best_conf]}}
        self._hint_tallies: dict[str, dict[str, list]] = {}

    # -------------------------------------------------------------------------
    # Persistence helpers
    # -------------------------------------------------------------------------

    def _run_dir(self, run: str) -> str:
        return os.path.join(self._run_root, run)

    def _persist(self, run: str) -> None:
        """Atomically rewrite candidates.json for the given run."""
        run_dir = self._run_dir(run)
        os.makedirs(run_dir, exist_ok=True)
        _write_candidates_json_atomic(run_dir, self._candidates.get(run, []))

    def _open_candidate(self, run: str) -> Candidate | None:
        """Return the single open candidate for the run, or None."""
        for c in reversed(self._candidates.get(run, [])):
            if c.state == "open":
                return c
        return None

    # -------------------------------------------------------------------------
    # Hint tally helpers
    # -------------------------------------------------------------------------

    def _tally_needs_review(self, run: str, results: list) -> None:
        """Update the hint tally for the given run using needs_review results."""
        tally = self._hint_tallies.setdefault(run, {})
        for r in results:
            # Only needs_review results (not rejected) contribute to hints
            if r.status != "needs_review":
                continue
            if r.number is None:
                continue
            num = r.number
            conf = r.confidence
            if num not in tally:
                tally[num] = [1, conf]
            else:
                tally[num][0] += 1
                if conf > tally[num][1]:
                    tally[num][1] = conf

    def _compute_hint(self, run: str) -> tuple[str | None, float]:
        """Derive hint_number/hint_conf from the current tally.

        Tie-breaking: most frequent first; ties broken by higher best confidence;
        remaining ties broken by earliest seen (implicit via dict insertion order).
        Returns (None, 0.0) if tally is empty.
        """
        tally = self._hint_tallies.get(run, {})
        if not tally:
            return None, 0.0
        # Sort: primary key = count DESC, secondary = best_conf DESC
        best_num = max(tally, key=lambda n: (tally[n][0], tally[n][1]))
        best_conf = max(conf for (_, conf) in tally.values()) if tally else 0.0
        # hint_conf is best confidence among ALL needs_review numbers (spec §4.2)
        return best_num, best_conf

    def _reset_hint_tally(self, run: str, candidate: Candidate) -> None:
        """Reset tally from persisted hint state (count=1 bootstrap after restart)."""
        tally: dict[str, list] = {}
        if candidate.hint_number is not None:
            tally[candidate.hint_number] = [1, candidate.hint_conf]
        self._hint_tallies[run] = tally

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def load_existing(self) -> None:
        """Scan runs/*/candidates.json on engine start.

        Loads persisted candidate state so a restart doesn't lose history.
        Malformed or missing files for a run are skipped with a log warning.
        After loading, any open candidate has its hint tally bootstrapped from its
        persisted hint_number/hint_conf (count=1 — full tally is not persisted).
        """
        if not os.path.isdir(self._run_root):
            return
        for entry in os.scandir(self._run_root):
            if not entry.is_dir():
                continue
            run = entry.name
            run_dir = entry.path
            candidates_path = os.path.join(run_dir, "candidates.json")
            if not os.path.exists(candidates_path):
                continue
            try:
                candidates = _load_candidates_json(run_dir)
                self._candidates[run] = candidates
                for c in candidates:
                    self._index[c.candidate_id] = c
                # Bootstrap hint tally from the open candidate (if any)
                open_cand = self._open_candidate(run)
                if open_cand is not None:
                    self._reset_hint_tally(run, open_cand)
            except Exception as exc:
                log.warning("Failed loading candidates for run %r: %s", run, exc)

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
          the frame entirely (FR15 prospective half).
        - ts − open.last_seen <= window_s ⇒ fold; else leave the old candidate
          open for the operator and start a new one.

        Persists candidates.json on every mutation (atomic temp+os.replace).
        """
        # FR15 prospective: if this frame had a confident result, skip entirely
        if had_confident:
            return

        # Filter results to those feeding candidates
        surviving = [
            r for r in results
            if r.status in self._statuses and r.det_conf >= self._min_det_conf
        ]
        if not surviving:
            return

        ts_sec = _ts_seconds(ts)
        open_cand = self._open_candidate(run)

        # Largest surviving box (by area) is the representative for this frame
        best_result = max(surviving, key=lambda r: _box_area(r.rider_box))
        best_box = list(best_result.rider_box)
        best_area = _box_area(best_result.rider_box)

        if open_cand is None or (ts_sec - _ts_seconds(open_cand.last_seen)) > self._window_s:
            # Start a new candidate
            cid = f"{run}-cand-{_epoch_ms(ts)}"
            self._hint_tallies[run] = {}
            # Tally needs_review from this frame
            self._tally_needs_review(run, surviving)
            hint_number, hint_conf = self._compute_hint(run)

            candidate = Candidate(
                candidate_id=cid,
                run=run,
                time=ts,
                last_seen=ts,
                frame_count=1,
                hint_number=hint_number,
                hint_conf=hint_conf,
                rep_filename=filename,
                rep_box=best_box,
                state="open",
            )
            self._candidates.setdefault(run, []).append(candidate)
            self._index[cid] = candidate
        else:
            # Fold into existing open candidate
            open_cand.last_seen = ts
            open_cand.frame_count += 1

            # Tally needs_review from this frame
            self._tally_needs_review(run, surviving)
            hint_number, hint_conf = self._compute_hint(run)
            open_cand.hint_number = hint_number
            open_cand.hint_conf = hint_conf

            # Adopt this frame as rep if its largest box is bigger
            if best_area > _box_area(open_cand.rep_box):
                open_cand.rep_filename = filename
                open_cand.rep_box = best_box

        self._persist(run)

    def suppress_around(self, run: str, ts: str) -> None:
        """Called on EVERY confident fold (new crossing, same-crossing update,
        or absorb-only).

        Any OPEN candidate whose [time, last_seen] span overlaps ts ± window_s
        transitions to state="suppressed". Promoted/dismissed states never change.
        """
        ts_sec = _ts_seconds(ts)
        window_start = ts_sec - self._window_s
        window_end = ts_sec + self._window_s

        changed = False
        for c in self._candidates.get(run, []):
            if c.state != "open":
                continue
            cand_start = _ts_seconds(c.time)
            cand_end = _ts_seconds(c.last_seen)
            # Overlap check: [cand_start, cand_end] overlaps [window_start, window_end]
            if cand_start <= window_end and cand_end >= window_start:
                c.state = "suppressed"
                changed = True

        if changed:
            self._persist(run)

    def list(self, run: str) -> list[Candidate]:
        """Return all candidates for the run (all states) as copies."""
        return [dataclasses.replace(c) for c in self._candidates.get(run, [])]

    def get(self, candidate_id: str) -> Candidate | None:
        """Return a single candidate snapshot by id, or None if not found."""
        c = self._index.get(candidate_id)
        if c is None:
            return None
        return dataclasses.replace(c)

    def set_state(
        self,
        candidate_id: str,
        state: str,
        promoted_crossing_id: str | None = None,
    ) -> Candidate:
        """Transition a candidate to a new state.

        Only "promoted" and "dismissed" are accepted via this method.
        Raises ValueError on unknown candidate_id or unsupported state.
        Returns a copy of the updated Candidate.
        """
        if state not in ("promoted", "dismissed"):
            raise ValueError(
                f"set_state: unsupported state {state!r}; "
                "only 'promoted' and 'dismissed' are allowed"
            )
        c = self._index.get(candidate_id)
        if c is None:
            raise ValueError(f"set_state: unknown candidate_id {candidate_id!r}")

        c.state = state
        if state == "promoted" and promoted_crossing_id is not None:
            c.promoted_crossing_id = promoted_crossing_id

        self._persist(c.run)
        return dataclasses.replace(c)
