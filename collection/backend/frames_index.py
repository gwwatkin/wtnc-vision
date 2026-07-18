"""frames_index.py — FramesIndex: per-frame outcome retention for the frame browser.

Implements design §4.1: append one JSONL line per processed frame (§3.3), and
serve time-windowed merges of manifest.jsonl (all captured frames) with
frames_index.jsonl (pipeline outcomes) for the frame browser.

Append-only writes; crash-tolerant reads (malformed lines skipped).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def _parse_ts(ts: str) -> float:
    """Parse an ISO-8601 timestamp string into epoch seconds (float).

    Handles both Z-suffix and +00:00 offset.  Returns 0.0 on any parse error.
    """
    try:
        ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def _read_jsonl(path: str) -> list[dict]:
    """Read a JSONL file, skipping any malformed lines.  Returns [] if missing."""
    if not os.path.isfile(path):
        return []
    lines = []
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    lines.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass  # malformed — skip, never fatal
    except OSError:
        return []
    return lines


class FramesIndex:
    """Maintains frames_index.jsonl for frame-browser queries (§4.1).

    Append-only writes; crash-tolerant reads (malformed lines skipped).
    """

    def __init__(self, run_root: str) -> None:
        """Initialise with the storage root (holds runs/<run>/ dirs)."""
        self._run_root = run_root

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_dir(self, run: str) -> str:
        return os.path.join(self._run_root, run)

    def _index_path(self, run: str) -> str:
        return os.path.join(self._run_dir(run), "frames_index.jsonl")

    def _manifest_path(self, run: str) -> str:
        return os.path.join(self._run_dir(run), "manifest.jsonl")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, run: str, entry: dict, results: list) -> None:
        """Append one §3.3 line to runs/<run>/frames_index.jsonl.

        Args:
            run: safe run id.
            entry: the manifest line dict for the processed frame.
            results: list[CrossingResult] from pipeline.run for this frame.
                     An empty list means "frame processed, no riders detected".
        """
        riders = [
            {
                "box": list(r.rider_box),
                "det_conf": r.det_conf,
                "status": r.status,
                "number": r.number,
                "raw_text": r.raw_text,
                "confidence": r.confidence,
            }
            for r in results
        ]

        record = {
            "filename": entry["filename"],
            "client_ts": entry["client_ts"],
            "seq": entry["seq"],
            "riders": riders,
        }

        index_path = self._index_path(run)
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        with open(index_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
            fh.flush()

    def frames(
        self,
        run: str,
        center_ts: str | None,
        span_s: float,
        limit: int,
    ) -> list[dict]:
        """Return frame dicts for the browser (§4.1).

        Merges manifest.jsonl (all frames) + frames_index.jsonl (outcomes) into
        [{filename, client_ts, seq, processed: bool, riders: [...]|None}]
        within [center − span_s, center + span_s], time-ordered ascending,
        capped at limit (keeping frames nearest center).
        center_ts=None ⇒ newest `limit` frames, ascending.

        Missing files ⇒ []; malformed lines skipped.
        """
        manifest_lines = _read_jsonl(self._manifest_path(run))
        if not manifest_lines:
            return []

        # Build index lookup: filename → riders list
        index_lines = _read_jsonl(self._index_path(run))
        index_by_filename: dict[str, list] = {}
        for line in index_lines:
            try:
                fn = line["filename"]
                index_by_filename[fn] = line["riders"]
            except (KeyError, TypeError):
                pass  # malformed — skip

        if center_ts is None:
            # Newest `limit` frames, no window filtering — sort by client_ts ascending,
            # take last `limit` entries.
            candidates = []
            for line in manifest_lines:
                try:
                    fn = line["filename"]
                    ts = line["client_ts"]
                    seq = line["seq"]
                except (KeyError, TypeError):
                    continue  # malformed manifest line — skip
                epoch = _parse_ts(ts)
                candidates.append((epoch, ts, seq, fn))

            # Sort ascending by timestamp, take the last `limit`
            candidates.sort(key=lambda x: x[0])
            candidates = candidates[-limit:] if limit < len(candidates) else candidates

            result = []
            for _epoch, ts, seq, fn in candidates:
                if fn in index_by_filename:
                    result.append({
                        "filename": fn,
                        "client_ts": ts,
                        "seq": seq,
                        "processed": True,
                        "riders": index_by_filename[fn],
                    })
                else:
                    result.append({
                        "filename": fn,
                        "client_ts": ts,
                        "seq": seq,
                        "processed": False,
                        "riders": None,
                    })
            return result

        # Window-based query
        center_epoch = _parse_ts(center_ts)
        lo = center_epoch - span_s
        hi = center_epoch + span_s

        # Collect all manifest entries within the window
        in_window: list[tuple[float, str, int, str]] = []
        for line in manifest_lines:
            try:
                fn = line["filename"]
                ts = line["client_ts"]
                seq = line["seq"]
            except (KeyError, TypeError):
                continue  # malformed — skip
            epoch = _parse_ts(ts)
            if lo <= epoch <= hi:
                in_window.append((epoch, ts, seq, fn))

        # Sort ascending by time
        in_window.sort(key=lambda x: x[0])

        # Cap at `limit` keeping frames nearest the center
        if len(in_window) > limit:
            # Compute distance from center for each frame and keep the closest
            indexed = list(enumerate(in_window))
            indexed.sort(key=lambda pair: abs(pair[1][0] - center_epoch))
            keep_indices = sorted(i for i, _ in indexed[:limit])
            in_window = [in_window[i] for i in keep_indices]

        result = []
        for _epoch, ts, seq, fn in in_window:
            if fn in index_by_filename:
                result.append({
                    "filename": fn,
                    "client_ts": ts,
                    "seq": seq,
                    "processed": True,
                    "riders": index_by_filename[fn],
                })
            else:
                result.append({
                    "filename": fn,
                    "client_ts": ts,
                    "seq": seq,
                    "processed": False,
                    "riders": None,
                })
        return result

    def meta(self, run: str) -> dict:
        """Return scrubber metadata for the run.

        Returns:
            {"count": int, "first_ts": str|None, "last_ts": str|None}
        """
        manifest_lines = _read_jsonl(self._manifest_path(run))
        if not manifest_lines:
            return {"count": 0, "first_ts": None, "last_ts": None}

        timestamps = []
        for line in manifest_lines:
            try:
                ts = line["client_ts"]
                timestamps.append((_parse_ts(ts), ts))
            except (KeyError, TypeError):
                pass  # malformed — skip

        if not timestamps:
            return {"count": 0, "first_ts": None, "last_ts": None}

        timestamps.sort(key=lambda x: x[0])
        return {
            "count": len(manifest_lines),
            "first_ts": timestamps[0][1],
            "last_ts": timestamps[-1][1],
        }
