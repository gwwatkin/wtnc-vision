"""engine.py — ResultsEngine: manifest tailer, dedup, per-run crossings.

Implements the worker loop, _process_frame, and _fold (design §6/§6.1).
Signatures are FROZEN (design §6). Do not change them.

sys.path shim: inserts <repo>/src so rider_id can be imported without
pip-installing it (same approach as run_poc.py).
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import shutil
import sys
import threading
from datetime import datetime, timezone
from typing import Any

# Allow importing rider_id from <repo>/src without pip install.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_SRC = os.path.join(_REPO_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import cv2  # noqa: E402

# Import pipeline as a module so tests can monkeypatch pipeline.run
from rider_id import pipeline  # noqa: E402
from rider_id.io_out import write_annotated_image  # noqa: E402

from . import edits as edits_mod
from .candidates import CandidateTracker
from .frames_index import FramesIndex
from .live_config import LiveConfig
from .results_models import Candidate, Crossing, _OpenCrossing
from .rosters import RunRosters
from .storage import FrameStore

log = logging.getLogger(__name__)


def _epoch_ms(ts: str) -> int:
    """Convert an ISO-8601 timestamp string to integer epoch milliseconds."""
    dt = datetime.fromisoformat(ts)
    # Ensure timezone-aware; if naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _ts_seconds(ts: str) -> float:
    """Convert an ISO-8601 timestamp string to seconds since epoch (float)."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _read_offset(run_dir: str) -> int:
    """Read the processed_offset file; return 0 if absent or unreadable."""
    offset_path = os.path.join(run_dir, "processed_offset")
    try:
        with open(offset_path, "r", encoding="utf-8") as fh:
            return int(fh.read().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_offset_atomic(run_dir: str, offset: int) -> None:
    """Atomically rewrite processed_offset via temp + os.replace."""
    offset_path = os.path.join(run_dir, "processed_offset")
    tmp_path = offset_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(str(offset))
    os.replace(tmp_path, offset_path)


def _read_manifest_lines(run_dir: str) -> list[dict]:
    """Read all JSON lines from the run's manifest.jsonl; return list of dicts."""
    manifest_path = os.path.join(run_dir, "manifest.jsonl")
    lines = []
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    try:
                        lines.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        log.warning("Skipping malformed manifest line: %r", stripped)
    except FileNotFoundError:
        pass
    return lines


def _crossings_to_json_list(crossings: list[Crossing]) -> list[dict]:
    """Convert a list of Crossing dataclasses to a JSON-serialisable list."""
    return [dataclasses.asdict(c) for c in crossings]


def _write_crossings_json_atomic(run_dir: str, crossings: list[Crossing]) -> None:
    """Atomically rewrite crossings.json with the full current crossing list."""
    crossings_path = os.path.join(run_dir, "crossings.json")
    tmp_path = crossings_path + ".tmp"
    data = _crossings_to_json_list(crossings)
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp_path, crossings_path)


def _append_crossings_csv(run_dir: str, time: str, number: str) -> None:
    """Append a time,number row to crossings.csv (append-only)."""
    csv_path = os.path.join(run_dir, "crossings.csv")
    with open(csv_path, "a", encoding="utf-8") as fh:
        fh.write(f"{time},{number}\n")


def _load_crossings_json(run_dir: str) -> list[Crossing]:
    """Load crossings.json and return list of Crossing objects; [] on missing/bad.

    Loader rule (§3.1): after constructing each Crossing, order_key == 0.0 ⇒
    order_key = float(_epoch_ms(time)).
    """
    crossings_path = os.path.join(run_dir, "crossings.json")
    try:
        with open(crossings_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        result = []
        for item in data:
            c = Crossing(**item)
            if c.order_key == 0.0:
                c.order_key = float(_epoch_ms(c.time))
            result.append(c)
        return result
    except (FileNotFoundError, json.JSONDecodeError, TypeError, KeyError):
        return []


class ResultsEngine:
    """Manages the manifest-tail worker, per-run dedup, and crossing persistence."""

    def __init__(self, live: LiveConfig, cv_cfg: dict, run_root: str) -> None:
        """Initialise with live config, cv config, and the storage root.

        cv_cfg = rider_id.config.load_config(live.cv_config_path)
        run_root = AppConfig.storage_dir (holds runs/<safe_label>/)
        """
        self._live = live
        self._cv_cfg = cv_cfg
        self._run_root = run_root

        # Per-run open-crossing dedup state: (run, number) -> _OpenCrossing
        self._open: dict[tuple[str, str], _OpenCrossing] = {}

        # Per-run crossing list: safe run id -> list[Crossing]
        self._crossings: dict[str, list[Crossing]] = {}

        # id -> Crossing index (populated from _crossings, maintained on fold)
        self._crossing_index: dict[str, Crossing] = {}

        # Dirty run ids pending processing
        self._dirty: set[str] = set()

        # Worker control
        self._wake: asyncio.Event = asyncio.Event()
        self._running: bool = False
        self._worker_task: asyncio.Task | None = None

        # Lock guarding ALL crossing/candidate mutation (design §8)
        self._lock: threading.RLock = threading.RLock()

        # Manifest stats cache: run_id -> (cache_key, captured, processed_through)
        # cache_key = (mtime, size) of manifest.jsonl or None when file absent
        self._manifest_stats_cache: dict[str, tuple[Any, int, str | None]] = {}

        # Permanent delegation — task4 owns the bodies but not these lines
        self._rosters = RunRosters(run_root)

        # Candidate tracker and frames index — module-level names are monkeypatch
        # points for task4's tests (refinement 4).
        self._candidates = CandidateTracker(
            run_root,
            live.candidate_window_s,
            live.candidate_min_det_conf,
            live.candidate_statuses,
        )
        self._frames = FramesIndex(run_root)

    async def start(self) -> None:
        """Scan runs/*/; load crossings; launch the worker task."""
        # Load rosters from disk
        self._rosters.load_existing()

        # Scan all run dirs under run_root
        if os.path.isdir(self._run_root):
            for entry in os.scandir(self._run_root):
                if not entry.is_dir():
                    continue
                run = entry.name
                run_dir = entry.path

                # Load persisted crossings into memory
                crossings = _load_crossings_json(run_dir)
                self._crossings[run] = crossings

                # Rebuild id index and open-crossing dedup state (§7 restart)
                for c in crossings:
                    self._crossing_index[c.crossing_id] = c
                    # Rebuild _open from persisted last_seen/confidence
                    key = (c.run, c.number)
                    existing = self._open.get(key)
                    if existing is None or _ts_seconds(c.last_seen) > _ts_seconds(existing.last_seen):
                        # §7 restart: manual/edited/deleted crossings get absorb_only=True
                        absorb_only = (
                            c.source == "manual"
                            or c.edited
                            or c.deleted
                        )
                        self._open[key] = _OpenCrossing(
                            crossing_id=c.crossing_id,
                            first_seen=c.time,
                            last_seen=c.last_seen,
                            best_conf=c.confidence,
                            absorb_only=absorb_only,
                        )

                # Mark dirty if manifest has lines beyond offset
                offset = _read_offset(run_dir)
                manifest_lines = _read_manifest_lines(run_dir)
                if len(manifest_lines) > offset:
                    self._dirty.add(run)

        # Set the wake event if anything is dirty
        if self._dirty:
            self._wake.set()

        # Load existing candidates into tracker
        self._candidates.load_existing()

        # Launch background worker
        self._running = True
        self._worker_task = asyncio.ensure_future(self._worker())

    async def stop(self) -> None:
        """Signal + await the worker; state is already on disk."""
        self._running = False
        self._wake.set()
        if self._worker_task is not None:
            await self._worker_task
            self._worker_task = None

    def notify(self, run: str) -> None:
        """Mark `run` dirty + set the wake event. O(1), no work state."""
        self._dirty.add(run)
        self._wake.set()

    def runs(self) -> list[str]:
        """Known run ids (safe labels) for GET /runs.

        Permanent delegation to rosters (task4 fills the real body).
        """
        return self._rosters.list_runs()

    def set_roster(self, label: str, csv_text: str) -> tuple[str, int]:
        """Normalize label → run id; parse roster; atomically write files.

        Permanent delegation — task4 fills RunRosters.set.
        Raises ValueError on bad input (task4 enforces; stub never raises).
        """
        return self._rosters.set(label, csv_text)

    def crossings(self, label: str) -> tuple[str, list[Crossing]]:
        """Normalize label → run id; return snapshot of that run's crossings.

        Returns (run_id, []) for an unknown run — never a 404.
        Filters deleted crossings; sorts ascending by (order_key, time) — the
        order of record (FR9).
        """
        run_id = FrameStore.safe_label(label)
        with self._lock:
            all_crossings = list(self._crossings.get(run_id, []))
        # Filter deleted, sort by (order_key, time) ascending
        active = [c for c in all_crossings if not c.deleted]
        active.sort(key=lambda c: (c.order_key, c.time))
        return (run_id, active)

    def annotated_path(self, crossing_id: str) -> str | None:
        """Absolute path to the crossing's annotated jpg, or None.

        Resolved via the in-memory id->crossing index.
        NEVER by string-splitting the id (safe labels may contain hyphens).
        """
        c = self._crossing_index.get(crossing_id)
        if c is None:
            return None
        return os.path.join(self._run_root, c.annotated_path)

    # -----------------------------------------------------------------------
    # New public methods (§4.4)
    # -----------------------------------------------------------------------

    def status(self, label: str) -> dict:
        """Return queue status dict for GET /status.

        {"run", "enabled": True, "captured", "processed", "pending",
         "state": "up_to_date"|"processing", "processed_through": str|None,
         "candidates_open": int}

        Cost guard (NFR2): manifest stats are cached per run keyed on the
        file's (mtime, size) — an idle poll never re-reads the manifest.
        """
        run_id = FrameStore.safe_label(label)
        run_dir = os.path.join(self._run_root, run_id)
        manifest_path = os.path.join(run_dir, "manifest.jsonl")

        # Read processed offset
        processed = _read_offset(run_dir)

        # Manifest stats with cache
        cache_key: tuple[float, int] | None = None
        captured = 0
        processed_through: str | None = None

        try:
            stat = os.stat(manifest_path)
            cache_key = (stat.st_mtime, stat.st_size)
        except FileNotFoundError:
            cache_key = None

        # Check cache
        cached = self._manifest_stats_cache.get(run_id)
        if cached is not None and cached[0] == cache_key:
            captured = cached[1]
            processed_through_cached = cached[2]
        else:
            # Read manifest
            manifest_lines = _read_manifest_lines(run_dir)
            captured = len(manifest_lines)
            # processed_through = client_ts of last processed manifest entry
            if processed > 0 and manifest_lines:
                last_processed_idx = min(processed, len(manifest_lines)) - 1
                processed_through_cached = manifest_lines[last_processed_idx].get("client_ts")
            else:
                processed_through_cached = None
            # Store in cache
            self._manifest_stats_cache[run_id] = (cache_key, captured, processed_through_cached)

        processed_through = processed_through_cached
        pending = max(0, captured - processed)

        state = "up_to_date" if pending == 0 else "processing"

        # Count open candidates
        with self._lock:
            all_cands = self._candidates.list(run_id)
        candidates_open = sum(1 for c in all_cands if c.state == "open")

        return {
            "run": run_id,
            "enabled": True,
            "captured": captured,
            "processed": processed,
            "pending": pending,
            "state": state,
            "processed_through": processed_through,
            "candidates_open": candidates_open,
        }

    def frames(
        self,
        label: str,
        center: str | None,
        span_s: float,
        limit: int,
    ) -> dict:
        """Return frame browser payload for GET /frames.

        {"run", "meta": {...}, "frames": [...]}
        """
        run_id = FrameStore.safe_label(label)
        meta = self._frames.meta(run_id)
        frames_list = self._frames.frames(run_id, center, span_s, limit)
        return {
            "run": run_id,
            "meta": meta,
            "frames": frames_list,
        }

    def frame_path(self, label: str, filename: str) -> str | None:
        """Absolute path for GET /frames/image, or None (traversal-guarded).

        Normalized absolute path MUST be under <run_root>/<run_id>/collected/;
        returns None (→ 404) otherwise.
        """
        run_id = FrameStore.safe_label(label)
        collected_dir = os.path.normpath(
            os.path.join(self._run_root, run_id, "collected")
        ) + os.sep  # ensure trailing sep for prefix check

        # Build normalized absolute path of the requested file
        candidate_path = os.path.normpath(
            os.path.join(self._run_root, filename)
        )

        # Guard: must be under the run's collected/ dir
        if not candidate_path.startswith(collected_dir):
            return None

        return candidate_path

    def create_crossing(
        self,
        label: str,
        filename: str,
        client_ts: str,
        number: str,
        box: list[float] | None = None,
    ) -> Crossing:
        """Manually create a crossing from a frame (POST /crossings).

        cid = f"{run}-manual-{epoch_ms(client_ts)}"
        source="manual", confidence=0.0, order_key=epoch_ms(client_ts).
        """
        run_id = FrameStore.safe_label(label)
        run_dir = os.path.join(self._run_root, run_id)
        annotated_dir = os.path.join(run_dir, "annotated")
        os.makedirs(annotated_dir, exist_ok=True)

        epoch_ms_val = _epoch_ms(client_ts)
        cid = f"{run_id}-manual-{epoch_ms_val}"

        # Enrich from roster
        roster = self._rosters.get(run_id)
        name, category, matched = edits_mod.enrich(number, roster)

        # Representative image: copy raw frame + optional box
        src_path = os.path.join(self._run_root, filename)
        annotated_rel = os.path.join(run_id, "annotated", f"{cid}.jpg")
        annotated_abs = os.path.join(self._run_root, annotated_rel)

        img = cv2.imread(src_path)
        if img is not None:
            if box is not None and len(box) == 4:
                x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imwrite(annotated_abs, img)
        else:
            # Fallback: try to copy raw file; if that fails, write a blank image
            try:
                shutil.copy2(src_path, annotated_abs)
            except Exception:
                blank = __import__("numpy").zeros((10, 10, 3), dtype=__import__("numpy").uint8)
                cv2.imwrite(annotated_abs, blank)

        order_key = float(epoch_ms_val)

        crossing = Crossing(
            crossing_id=cid,
            run=run_id,
            number=number,
            time=client_ts,
            confidence=0.0,
            name=name,
            category=category,
            matched=matched,
            annotated_path=annotated_rel,
            last_seen=client_ts,
            source="manual",
            edited=False,
            deleted=False,
            order_key=order_key,
            order_overridden=False,
        )

        with self._lock:
            # Append to crossings.csv (refinement 3)
            _append_crossings_csv(run_dir, client_ts, number)

            # Add to memory structures
            self._crossings.setdefault(run_id, []).append(crossing)
            self._crossing_index[cid] = crossing

            # Register absorb-only open entry if number != "" (§7 collision rule)
            if number != "":
                key = (run_id, number)
                existing_oc = self._open.get(key)
                # Only install absorb entry when absent or already pointing at THIS crossing
                if existing_oc is None or existing_oc.crossing_id == cid:
                    self._open[key] = _OpenCrossing(
                        crossing_id=cid,
                        first_seen=client_ts,
                        last_seen=client_ts,
                        best_conf=0.0,
                        absorb_only=True,
                    )
                # If it points at a DIFFERENT live crossing, leave it alone (collision rule)

            # Persist
            _write_crossings_json_atomic(run_dir, self._crossings[run_id])

        return crossing

    def edit_crossing(
        self,
        crossing_id: str,
        *,
        number: str | None = None,
        deleted: bool | None = None,
    ) -> Crossing:
        """Edit a crossing's number or soft-delete flag (PATCH /crossings/{id}).

        Raises KeyError on unknown crossing_id.
        """
        with self._lock:
            crossing = self._crossing_index.get(crossing_id)
            if crossing is None:
                raise KeyError(crossing_id)

            run_id = crossing.run
            run_dir = os.path.join(self._run_root, run_id)

            if number is not None:
                old_number = crossing.number
                new_number = number

                # Re-enrich from roster
                roster = self._rosters.get(run_id)
                name, category, matched = edits_mod.enrich(new_number, roster)

                # §7 collision rule: handle OLD number absorb entry
                if old_number != "" and old_number != new_number:
                    old_key = (run_id, old_number)
                    old_oc = self._open.get(old_key)
                    # Point old number to this crossing with absorb_only=True
                    # (collision rule: only if absent or already pointing here)
                    if old_oc is None or old_oc.crossing_id == crossing_id:
                        self._open[old_key] = _OpenCrossing(
                            crossing_id=crossing_id,
                            first_seen=crossing.time,
                            last_seen=crossing.last_seen,
                            best_conf=crossing.confidence,
                            absorb_only=True,
                        )
                    # If it points at a different crossing, leave it alone

                # §7 collision rule: handle NEW number absorb entry
                if new_number != "":
                    new_key = (run_id, new_number)
                    new_oc = self._open.get(new_key)
                    if new_oc is None or new_oc.crossing_id == crossing_id:
                        self._open[new_key] = _OpenCrossing(
                            crossing_id=crossing_id,
                            first_seen=crossing.time,
                            last_seen=crossing.last_seen,
                            best_conf=crossing.confidence,
                            absorb_only=True,
                        )
                    # If it points at a different crossing, leave it alone

                # Update crossing fields
                crossing.number = new_number
                crossing.name = name
                crossing.category = category
                crossing.matched = matched
                crossing.edited = True

            if deleted is not None:
                crossing.deleted = deleted
                if deleted:
                    # Flip existing _open entry to absorb-only tombstone (§7)
                    key = (run_id, crossing.number)
                    existing_oc = self._open.get(key)
                    if existing_oc is not None and existing_oc.crossing_id == crossing_id:
                        existing_oc.absorb_only = True
                    elif existing_oc is None:
                        # Install a tombstone
                        self._open[key] = _OpenCrossing(
                            crossing_id=crossing_id,
                            first_seen=crossing.time,
                            last_seen=crossing.last_seen,
                            best_conf=crossing.confidence,
                            absorb_only=True,
                        )

            # Persist
            _write_crossings_json_atomic(run_dir, self._crossings[run_id])

        return crossing

    def set_position(
        self,
        crossing_id: str,
        earlier_id: str | None,
        later_id: str | None,
    ) -> Crossing:
        """Reorder a crossing between its neighbors (POST /crossings/{id}/position).

        Neighbors are in ORDER-OF-RECORD (ascending order_key). At least one
        must be given; both must belong to the same run as crossing_id.
        Raises ValueError if: no neighbor given, cross-run neighbor.
        Raises KeyError if: unknown id.
        """
        if earlier_id is None and later_id is None:
            raise ValueError("at least one of earlier_id or later_id must be provided")

        with self._lock:
            crossing = self._crossing_index.get(crossing_id)
            if crossing is None:
                raise KeyError(crossing_id)

            run_id = crossing.run

            # Validate neighbors belong to the same run
            if earlier_id is not None:
                earlier = self._crossing_index.get(earlier_id)
                if earlier is None:
                    raise KeyError(earlier_id)
                if earlier.run != run_id:
                    raise ValueError(
                        f"earlier_id {earlier_id!r} belongs to run {earlier.run!r}, "
                        f"not {run_id!r}"
                    )
            else:
                earlier = None

            if later_id is not None:
                later = self._crossing_index.get(later_id)
                if later is None:
                    raise KeyError(later_id)
                if later.run != run_id:
                    raise ValueError(
                        f"later_id {later_id!r} belongs to run {later.run!r}, "
                        f"not {run_id!r}"
                    )
            else:
                later = None

            earlier_key = earlier.order_key if earlier is not None else None
            later_key = later.order_key if later is not None else None

            new_key = edits_mod.midpoint_key(earlier_key, later_key)
            crossing.order_key = new_key
            crossing.order_overridden = True

            run_dir = os.path.join(self._run_root, run_id)
            _write_crossings_json_atomic(run_dir, self._crossings[run_id])

        return crossing

    def candidates(self, label: str) -> tuple[str, list[Candidate]]:
        """Return (run_id, all_candidates) for GET /candidates."""
        run_id = FrameStore.safe_label(label)
        with self._lock:
            cands = self._candidates.list(run_id)
        return (run_id, cands)

    def resolve_candidate(
        self,
        candidate_id: str,
        action: str,
        number: str = "",
    ) -> dict:
        """Resolve a candidate via promote or dismiss (POST /candidates/{id}/resolve).

        action="dismiss" ⇒ set_state("dismissed").
        action="promote" ⇒ create_crossing + set_state("promoted", cid).
        Returns {"candidate", "crossing"?}.
        """
        with self._lock:
            cand = self._candidates.get(candidate_id)
        if cand is None:
            raise KeyError(candidate_id)

        if action == "dismiss":
            with self._lock:
                updated_cand = self._candidates.set_state(candidate_id, "dismissed")
            return {"candidate": dataclasses.asdict(updated_cand)}

        elif action == "promote":
            # create_crossing acquires its own lock
            crossing = self.create_crossing(
                cand.run,
                cand.rep_filename,
                cand.time,
                number,
                box=cand.rep_box,
            )
            with self._lock:
                updated_cand = self._candidates.set_state(
                    candidate_id, "promoted", crossing.crossing_id
                )
            return {
                "candidate": dataclasses.asdict(updated_cand),
                "crossing": dataclasses.asdict(crossing),
            }
        else:
            raise ValueError(f"Unknown action: {action!r}")

    def candidate_image_path(self, candidate_id: str) -> str | None:
        """Absolute path of the candidate's representative raw frame, or None.

        Used by GET /candidates/{id}/image. Same traversal stance as frame_path.
        """
        with self._lock:
            cand = self._candidates.get(candidate_id)
        if cand is None:
            return None

        run_id = cand.run
        # rep_filename is root-relative; guard traversal
        candidate_path = os.path.normpath(
            os.path.join(self._run_root, cand.rep_filename)
        )
        collected_dir = os.path.normpath(
            os.path.join(self._run_root, run_id, "collected")
        ) + os.sep

        if not candidate_path.startswith(collected_dir):
            return None

        return candidate_path

    # -----------------------------------------------------------------------
    # Worker loop
    # -----------------------------------------------------------------------

    async def _worker(self) -> None:
        """The background manifest-tail worker (design §6 frozen shape)."""
        while self._running:
            await self._wake.wait()
            self._wake.clear()

            # Drain all currently dirty runs
            dirty_snapshot = self._drain_dirty()
            for run in dirty_snapshot:
                run_dir = os.path.join(self._run_root, run)
                offset = _read_offset(run_dir)
                manifest_lines = _read_manifest_lines(run_dir)

                for entry in manifest_lines[offset:]:
                    if not self._running:
                        # Shutting down — write the offset we've reached and exit
                        _write_offset_atomic(run_dir, offset)
                        return
                    try:
                        await asyncio.to_thread(self._process_frame, run, entry)
                    except Exception:
                        log.exception(
                            "Frame failed, skipping: run=%r entry=%r", run, entry
                        )
                    offset += 1
                    _write_offset_atomic(run_dir, offset)

            # Re-check dirtiness: a notify() arriving mid-drain must not be lost.
            # If _wake is already set, the outer while loop will re-enter immediately.

    def _drain_dirty(self) -> set[str]:
        """Atomically consume and return the current dirty set."""
        dirty = self._dirty.copy()
        self._dirty.clear()
        return dirty

    # -----------------------------------------------------------------------
    # Internal — run in the worker thread
    # -----------------------------------------------------------------------

    def _process_frame(self, run: str, entry: dict) -> None:
        """Process one manifest entry: decode frame, run pipeline, call _fold.

        entry = one parsed manifest line (filename, client_ts, …).
        Raises on failure (caught by worker loop — FR6).
        """
        # Point cv_cfg at this run's roster.csv (may not exist → confidence-only)
        self._cv_cfg["validate"]["roster"] = self._rosters.roster_csv_path(run)

        # Resolve frame path: filename is root-relative (README refinement 2)
        frame_path = os.path.join(self._run_root, entry["filename"])
        img = cv2.imread(frame_path)
        if img is None:
            raise ValueError(f"cv2.imread returned None for path: {frame_path!r}")

        # Run CV pipeline (monkeypatched in tests)
        frame_results = pipeline.run(img, self._cv_cfg)

        # §4.4 worker lines — always append to frames index (guard on config)
        if self._live.frames_index_enabled:
            self._frames.append(run, entry, frame_results)

        # Compute had_confident before the fold loop
        had_confident = any(r.status in self._live.statuses for r in frame_results)

        # Fold each confident (per live config statuses) result (unchanged loop)
        client_ts = entry["client_ts"]
        for result in frame_results:
            if result.status in self._live.statuses:
                self._fold(run, result.number, result.confidence, client_ts, img, frame_results)

        # §4.4 candidate observe — guard on config; tracker calls under lock (refinement 5)
        if self._live.candidates_enabled:
            with self._lock:
                self._candidates.observe(
                    run, client_ts, entry["filename"], frame_results, had_confident
                )

    def _fold(
        self,
        run: str,
        number: str,
        conf: float,
        client_ts: str,
        image_bgr,
        frame_results,
    ) -> None:
        """Dedup within `run` + open/update crossing + annotate + persist (§6.1).

        Changes (§4.4):
        (a) Acquires self._lock.
        (b) Calls self._candidates.suppress_around on EVERY fold path.
        (c) When absorb_only=True, update last_seen only and return.
        (d) Skip (absorb) folding into deleted crossings — tombstone, never resurrect.
        (e) Uses edits.enrich for roster lookup (refinement 6).
        (f) New crossings get order_key = float(_epoch_ms(t)).
        """
        with self._lock:
            t = client_ts

            # Step 1: Look up open crossing for (run, number)
            key = (run, number)
            oc = self._open.get(key)

            # Step 2: Determine if this is a new crossing or same crossing
            is_new = (
                oc is None
                or (_ts_seconds(t) - _ts_seconds(oc.last_seen)) > self._live.dedup_window_s
            )

            # Always call suppress_around (§4.2 / §7)
            self._candidates.suppress_around(run, t)

            # Prepare run-level directories
            run_dir = os.path.join(self._run_root, run)
            annotated_dir = os.path.join(run_dir, "annotated")
            os.makedirs(annotated_dir, exist_ok=True)

            if is_new:
                # --- New crossing ---
                cid = f"{run}-{number}-{_epoch_ms(t)}"

                # Enrich from this run's roster (refinement 6)
                roster = self._rosters.get(run)
                name, category, matched = edits_mod.enrich(number, roster)

                # Write annotated representative frame
                write_annotated_image(
                    image_bgr,
                    frame_results,
                    annotated_dir,
                    filename=f"{cid}.jpg",
                )

                # annotated_path is relative to run_root
                annotated_rel = os.path.join(run, "annotated", f"{cid}.jpg")

                # Append to crossings.csv (time,number)
                _append_crossings_csv(run_dir, t, number)

                # Build Crossing object — order_key = float(epoch_ms(t)) (§3.1)
                crossing = Crossing(
                    crossing_id=cid,
                    run=run,
                    number=number,
                    time=t,
                    confidence=conf,
                    name=name,
                    category=category,
                    matched=matched,
                    annotated_path=annotated_rel,
                    last_seen=t,
                    order_key=float(_epoch_ms(t)),
                )

                # Add to memory structures
                self._crossings.setdefault(run, []).append(crossing)
                self._crossing_index[cid] = crossing

                # Update open-crossing dedup state
                self._open[key] = _OpenCrossing(
                    crossing_id=cid,
                    first_seen=t,
                    last_seen=t,
                    best_conf=conf,
                )

                # Atomically rewrite crossings.json
                _write_crossings_json_atomic(run_dir, self._crossings[run])

            else:
                # --- Same crossing (within window) ---

                # (§7) If this open crossing is absorb_only:
                #   update last_seen only and return — no confidence bump, no re-annotation.
                # Also handle deleted crossings as tombstones (§7).
                existing = self._crossing_index.get(oc.crossing_id)

                if oc.absorb_only:
                    # Absorb-only: update last_seen only
                    if _ts_seconds(t) > _ts_seconds(oc.last_seen):
                        oc.last_seen = t
                        if existing is not None:
                            existing.last_seen = oc.last_seen
                    return

                # Check if the target crossing is deleted — tombstone, absorb silently
                if existing is not None and existing.deleted:
                    return

                # Update last_seen to max(last_seen, t)
                if _ts_seconds(t) > _ts_seconds(oc.last_seen):
                    oc.last_seen = t

                if existing is not None:
                    existing.last_seen = oc.last_seen

                # On better confidence: re-render annotated image and update confidence
                if conf > oc.best_conf:
                    oc.best_conf = conf
                    if existing is not None:
                        existing.confidence = conf

                    # Re-render annotated frame
                    write_annotated_image(
                        image_bgr,
                        frame_results,
                        annotated_dir,
                        filename=f"{oc.crossing_id}.jpg",
                    )

                    # Atomically rewrite crossings.json
                    run_crossings = self._crossings.get(run, [])
                    _write_crossings_json_atomic(run_dir, run_crossings)
