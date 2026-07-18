"""edits.py — Pure helpers for crossing edit operations (design §4.3).

These are stateless pure functions; no disk I/O; no engine dependency.
Task4 will refactor _fold's enrichment block to call enrich() instead of
duplicating the logic.
"""
from __future__ import annotations


def midpoint_key(earlier_key: float | None, later_key: float | None) -> float:
    """Return a new order_key between two neighbors.

    Rules (design §4.3):
    - Between two neighbors: (earlier_key + later_key) / 2.
    - Top of order (no earlier neighbor, i.e. earlier_key is None):
      later_key − 60_000.
    - Bottom of order (no later neighbor, i.e. later_key is None):
      earlier_key + 60_000.
    - At least one must be given.
    - When both are given: earlier_key < later_key is required;
      raises ValueError otherwise.
    """
    if earlier_key is None and later_key is None:
        raise ValueError("at least one of earlier_key or later_key must be provided")

    if earlier_key is None:
        # Top of order — nothing earlier
        return later_key - 60_000.0

    if later_key is None:
        # Bottom of order — nothing later
        return earlier_key + 60_000.0

    # Both given: require strict ordering
    if earlier_key >= later_key:
        raise ValueError(
            f"earlier_key ({earlier_key}) must be strictly less than "
            f"later_key ({later_key})"
        )

    return (earlier_key + later_key) / 2.0


def enrich(number: str, roster) -> tuple[str | None, str, bool]:
    """Resolve (name, category, matched) from a RunRosters roster.

    This is the same lookup _fold performs today, extracted so edit ops and
    _fold can share it (design §4.3 / refinement 6).

    Args:
        number: race number string (may be empty string).
        roster: a Roster object with .numbers (frozenset) and
                .entries (dict[str, tuple[str, str]]) attributes.

    Returns:
        (name, category, matched) where:
        - matched=True only when number is non-empty and present in roster.numbers.
        - name is the roster name or None when unmatched.
        - category is the roster category or "Unknown" when unmatched.
    """
    if number and number in roster.numbers:
        name_cat = roster.entries.get(number)
        name = name_cat[0] if name_cat else None
        category = name_cat[1] if name_cat else "Unknown"
        matched = True
    else:
        name = None
        category = "Unknown"
        matched = False

    return (name, category, matched)
