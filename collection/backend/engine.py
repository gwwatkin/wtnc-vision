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
import sys
from datetime import datetime, timezone

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

from .live_config import LiveConfig
from .results_models import Crossing, _OpenCrossing
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
    """Load crossings.json and return list of Crossing objects; [] on missing/bad."""
    crossings_path = os.path.join(run_dir, "crossings.json")
    try:
        with open(crossings_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [Crossing(**item) for item in data]
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

        # Permanent delegation — task4 owns the bodies but not these lines
        self._rosters = RunRosters(run_root)

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

                # Rebuild id index and open-crossing dedup state
                for c in crossings:
                    self._crossing_index[c.crossing_id] = c
                    # Rebuild _open from persisted last_seen/confidence
                    key = (c.run, c.number)
                    existing = self._open.get(key)
                    if existing is None or _ts_seconds(c.last_seen) > _ts_seconds(existing.last_seen):
                        self._open[key] = _OpenCrossing(
                            crossing_id=c.crossing_id,
                            first_seen=c.time,
                            last_seen=c.last_seen,
                            best_conf=c.confidence,
                        )

                # Mark dirty if manifest has lines beyond offset
                offset = _read_offset(run_dir)
                manifest_lines = _read_manifest_lines(run_dir)
                if len(manifest_lines) > offset:
                    self._dirty.add(run)

        # Set the wake event if anything is dirty
        if self._dirty:
            self._wake.set()

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
        """
        run_id = FrameStore.safe_label(label)
        snapshot = list(self._crossings.get(run_id, []))
        return (run_id, snapshot)

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

        # Fold each confident (per live config statuses) result
        client_ts = entry["client_ts"]
        for result in frame_results:
            if result.status in self._live.statuses:
                self._fold(run, result.number, result.confidence, client_ts, img, frame_results)

    def _fold(
        self,
        run: str,
        number: str,
        conf: float,
        client_ts: str,
        image_bgr,
        frame_results,
    ) -> None:
        """Dedup within `run` + open/update crossing + annotate + persist (§6.1)."""
        t = client_ts

        # Step 1: Look up open crossing for (run, number)
        key = (run, number)
        oc = self._open.get(key)

        # Step 2: Determine if this is a new crossing or same crossing
        is_new = (
            oc is None
            or (_ts_seconds(t) - _ts_seconds(oc.last_seen)) > self._live.dedup_window_s
        )

        # Prepare run-level directories
        run_dir = os.path.join(self._run_root, run)
        annotated_dir = os.path.join(run_dir, "annotated")
        os.makedirs(annotated_dir, exist_ok=True)

        if is_new:
            # --- New crossing ---
            cid = f"{run}-{number}-{_epoch_ms(t)}"

            # Enrich from this run's roster
            roster = self._rosters.get(run)
            matched = number in roster.numbers
            if matched:
                name_cat = roster.entries.get(number)
                name = name_cat[0] if name_cat else None
                category = name_cat[1] if name_cat else "Unknown"
            else:
                name = None
                category = "Unknown"

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

            # Build Crossing object
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
            # Update last_seen to max(last_seen, t)
            if _ts_seconds(t) > _ts_seconds(oc.last_seen):
                oc.last_seen = t

            # Find the existing Crossing object
            existing = self._crossing_index.get(oc.crossing_id)
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
