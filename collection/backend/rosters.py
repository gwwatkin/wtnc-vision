"""rosters.py — RunRosters: per-run roster state.

Parses number,name,category CSV; atomically writes roster.csv per run (the
single roster file — validate.load_roster reads its first column directly);
holds an immutable Roster the engine reads lock-free.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import tempfile
from dataclasses import dataclass

from .storage import FrameStore

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Roster:
    numbers: frozenset[str]               # valid-number set (roster.csv column 1)
    entries: dict[str, tuple[str, str]]   # number -> (name, category)


EMPTY_ROSTER = Roster(frozenset(), {})


def _parse_csv(csv_text: str) -> dict[str, tuple[str, str]]:
    """Parse number,name,category CSV text.

    Rules (task4.md):
    - Uses csv.reader (handles quoted fields).
    - Rows need >= 3 cells with a non-empty digit-string number cell;
      name/category are stripped text.
    - The first row is treated as a header and skipped if its number cell
      (cell 0, stripped) is NOT a non-empty digit-only string.
    - Other bad rows are skipped silently.
    - Later duplicate numbers win.

    Returns: dict mapping number -> (name, category). Empty dict if nothing parsed.
    """
    entries: dict[str, tuple[str, str]] = {}
    reader = csv.reader(io.StringIO(csv_text))
    first_row = True

    for row in reader:
        if len(row) < 3:
            first_row = False
            continue

        num_cell = row[0].strip()

        if first_row:
            first_row = False
            # If the first row's number cell is not a non-empty digit string,
            # treat it as a header and skip it.
            if not num_cell or not num_cell.isdigit():
                continue

        # Otherwise require a non-empty digit-string number cell.
        if not num_cell or not num_cell.isdigit():
            continue  # bad row — skip silently

        name = row[1].strip()
        category = row[2].strip()
        entries[num_cell] = (name, category)

    return entries


def _write_atomic(path: str, content: str) -> None:
    """Write content to path atomically using a temp file + os.replace."""
    dir_ = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up the temp file on failure (best-effort)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class RunRosters:
    def __init__(self, run_root: str) -> None:
        """run_root = AppConfig.storage_dir (holds runs/<safe_label>/)."""
        self._run_root = run_root
        # In-memory store: safe run id -> Roster (replace-don't-mutate)
        self._by_run: dict[str, Roster] = {}

    def load_existing(self) -> None:
        """Scan run_root/*/roster.csv into memory (engine.start calls this).

        A malformed on-disk roster is logged and skipped, never fatal.
        """
        if not os.path.isdir(self._run_root):
            return

        for entry in os.scandir(self._run_root):
            if not entry.is_dir():
                continue
            run = entry.name
            roster_csv = os.path.join(entry.path, "roster.csv")
            if not os.path.isfile(roster_csv):
                continue
            try:
                with open(roster_csv, "r", encoding="utf-8") as fh:
                    csv_text = fh.read()
                entries = _parse_csv(csv_text)
                if not entries:
                    log.warning(
                        "load_existing: roster for run %r has no parseable rows; skipping", run
                    )
                    continue
                self._by_run[run] = Roster(
                    numbers=frozenset(entries.keys()),
                    entries=entries,
                )
            except Exception:
                log.exception("load_existing: failed to load roster for run %r; skipping", run)

    def set(self, label: str, csv_text: str) -> tuple[str, int]:
        """Normalize label → run id; parse roster; atomically write files.

        Steps:
        1. Validate label (strip; blank → ValueError).
        2. run = FrameStore.safe_label(label).
        3. Parse CSV with _parse_csv.  Zero accepted rows → ValueError; no files touched.
        4. Atomically write roster.csv under run_root/<run>/.
        5. Rebind self._by_run[run] to a new frozen Roster (replace-don't-mutate).
        6. Return (run, count).
        """
        if not label.strip():
            raise ValueError("run label must not be blank")

        run = FrameStore.safe_label(label)

        entries = _parse_csv(csv_text)
        if not entries:
            raise ValueError(
                f"roster has no parseable rows (need non-empty digit number, name, category columns)"
            )

        # Only touch the filesystem after successful parse.
        run_dir = os.path.join(self._run_root, run)
        os.makedirs(run_dir, exist_ok=True)

        # Build file contents.
        # roster.csv: accepted rows, normalized number,name,category.
        csv_lines = ["number,name,category"]
        for number, (name, category) in entries.items():
            # Quote fields that contain commas or quotes via csv module.
            row_buf = io.StringIO()
            writer = csv.writer(row_buf)
            writer.writerow([number, name, category])
            csv_lines.append(row_buf.getvalue().rstrip("\r\n"))
        roster_csv_content = "\n".join(csv_lines) + "\n"

        _write_atomic(os.path.join(run_dir, "roster.csv"), roster_csv_content)

        # Replace-don't-mutate: build a new Roster and rebind.
        new_roster = Roster(
            numbers=frozenset(entries.keys()),
            entries=entries,
        )
        self._by_run[run] = new_roster

        return (run, len(entries))

    def get(self, run: str) -> Roster:
        """Current Roster for a safe run id; EMPTY_ROSTER when none uploaded."""
        return self._by_run.get(run, EMPTY_ROSTER)

    def roster_csv_path(self, run: str) -> str:
        """Absolute path to run_root/<run>/roster.csv (may not exist yet).

        The CV pipeline's validate.load_roster reads this file directly (first
        column); a missing file means confidence-only validation (FR20).
        """
        return os.path.join(self._run_root, run, "roster.csv")

    def list_runs(self) -> list[str]:
        """Run ids = directories directly under run_root.

        Returns [] when run_root doesn't exist yet.
        """
        if not os.path.isdir(self._run_root):
            return []
        return [
            entry.name
            for entry in os.scandir(self._run_root)
            if entry.is_dir()
        ]
