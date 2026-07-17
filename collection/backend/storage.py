"""FrameStore — filename policy, frame write, manifest append.

Signatures are FROZEN (design §6). Fully implemented by task2.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from .models import FrameMeta, StoredFrame


class FrameStore:
    def __init__(self, root: str, manifest_name: str) -> None:
        """Store root directory path and manifest name; create root if missing."""
        self.root = root
        self.manifest_name = manifest_name
        os.makedirs(root, exist_ok=True)

    @staticmethod
    def safe_label(label: str) -> str:
        """Convert an arbitrary label into a filesystem-safe directory component.

        Rules (design §5):
          - lowercase
          - every run of characters outside [a-z0-9] collapses to a single '-'
          - leading/trailing '-' stripped
          - empty result → "unlabeled"
          - capped at 64 chars
        """
        lower = label.lower()
        collapsed = re.sub(r"[^a-z0-9]+", "-", lower)
        stripped = collapsed.strip("-")
        result = stripped[:64] if stripped else "unlabeled"
        return result

    def save(self, frame_bytes: bytes, meta: FrameMeta) -> StoredFrame:
        """Write <root>/<safe_label>/collected/<name>.jpg and append one per-run manifest line.

        Layout (design §5):
          - Frame:    <root>/<safe>/collected/<filename_base>
          - Manifest: <root>/<safe>/manifest.jsonl  (per-run, not global)
          - filename field (root-relative): <safe>/collected/<filename_base>

        Returns a StoredFrame describing what was written.
        """
        safe = self.safe_label(meta.label)

        # Ensure per-run collected/ sub-directory exists
        collected_dir = os.path.join(self.root, safe, "collected")
        os.makedirs(collected_dir, exist_ok=True)

        # server_ts: ISO-8601 UTC with millisecond precision, e.g. "2026-07-11T09:30:15.501Z"
        now_utc = datetime.now(timezone.utc)
        ms = now_utc.microsecond // 1000
        server_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"

        # filename: <safe>_<YYYYmmdd-HHMMSS-mmm>_<seq:06d>.jpg
        ts_part = now_utc.strftime("%Y%m%d-%H%M%S-") + f"{ms:03d}"
        filename_base = f"{safe}_{ts_part}_{meta.seq:06d}.jpg"
        # Root-relative path: <safe>/collected/<filename_base> (README refinement 2)
        rel_path = f"{safe}/collected/{filename_base}"
        abs_path = os.path.join(self.root, rel_path)

        # Write frame bytes verbatim — no re-encode (NFR1)
        with open(abs_path, "wb") as fh:
            fh.write(frame_bytes)

        # Append one JSON line to the per-run manifest (design §5)
        manifest_path = os.path.join(self.root, safe, self.manifest_name)
        record = {
            "label": meta.label,
            "safe_label": safe,
            "filename": rel_path,
            "seq": meta.seq,
            "session_id": meta.session_id,
            "client_ts": meta.client_ts,
            "server_ts": server_ts,
            "bytes": len(frame_bytes),
            "content_type": meta.content_type,
        }
        with open(manifest_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        return StoredFrame(
            filename=rel_path,
            safe_label=safe,
            server_ts=server_ts,
            bytes=len(frame_bytes),
        )
