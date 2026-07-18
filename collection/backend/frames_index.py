"""frames_index.py — FramesIndex: per-frame outcome retention for the frame browser.

Stub implementation for wave-A scaffold (task1). All method bodies raise
NotImplementedError; task3 provides the real implementation.
"""
from __future__ import annotations


class FramesIndex:
    """Maintains frames_index.jsonl for frame-browser queries (§4.1).

    Append-only writes; crash-tolerant reads (malformed lines skipped).
    """

    def __init__(self, run_root: str) -> None:
        """Initialise with the storage root (holds runs/<run>/ dirs)."""
        self._run_root = run_root

    def append(self, run: str, entry: dict, results: list) -> None:
        """Append one §3.3 line to runs/<run>/frames_index.jsonl.

        Args:
            run: safe run id.
            entry: the manifest line dict for the processed frame.
            results: list[CrossingResult] from pipeline.run for this frame.
                     An empty list means "frame processed, no riders detected".
        """
        raise NotImplementedError

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
        within [center − span_s, center + span_s], time-ordered, capped at limit.
        center_ts=None ⇒ newest `limit` frames.
        """
        raise NotImplementedError

    def meta(self, run: str) -> dict:
        """Return scrubber metadata for the run.

        Returns:
            {"count": int, "first_ts": str|None, "last_ts": str|None}
        """
        raise NotImplementedError
