"""Tests for edits.py — midpoint_key and enrich helpers (task1 / design §4.3)."""
from __future__ import annotations

import pytest

from backend.edits import enrich, midpoint_key
from backend.rosters import EMPTY_ROSTER, Roster


# ---------------------------------------------------------------------------
# midpoint_key tests
# ---------------------------------------------------------------------------

class TestMidpointKey:
    def test_midpoint_between_neighbors(self):
        """Standard case: midpoint of two distinct order keys."""
        result = midpoint_key(1000.0, 3000.0)
        assert result == pytest.approx(2000.0)

    def test_midpoint_between_neighbors_unequal(self):
        """Midpoint is exact average."""
        result = midpoint_key(100.0, 200.0)
        assert result == pytest.approx(150.0)

    def test_top_of_order_no_earlier(self):
        """No earlier neighbor: returns later − 60_000."""
        result = midpoint_key(None, 500_000.0)
        assert result == pytest.approx(440_000.0)

    def test_bottom_of_order_no_later(self):
        """No later neighbor: returns earlier + 60_000."""
        result = midpoint_key(200_000.0, None)
        assert result == pytest.approx(260_000.0)

    def test_raises_when_both_none(self):
        """Both None is invalid — at least one must be given."""
        with pytest.raises(ValueError):
            midpoint_key(None, None)

    def test_raises_when_earlier_equals_later(self):
        """earlier_key >= later_key must raise ValueError."""
        with pytest.raises(ValueError):
            midpoint_key(1000.0, 1000.0)

    def test_raises_when_earlier_greater_than_later(self):
        """earlier_key > later_key must raise ValueError."""
        with pytest.raises(ValueError):
            midpoint_key(2000.0, 1000.0)

    def test_result_is_strictly_between(self):
        """Result must be strictly between both neighbors."""
        a, b = 1_000_000.0, 2_000_000.0
        mid = midpoint_key(a, b)
        assert a < mid < b

    def test_float_precision_large_keys(self):
        """Works correctly with typical epoch-ms float values."""
        # Epoch ms for some date
        a = 1_720_000_000_000.0
        b = 1_720_000_060_000.0
        mid = midpoint_key(a, b)
        assert mid == pytest.approx((a + b) / 2.0)


# ---------------------------------------------------------------------------
# enrich tests
# ---------------------------------------------------------------------------

class TestEnrich:
    def _make_roster(self) -> Roster:
        """A roster with one known rider."""
        return Roster(
            numbers=frozenset({"101", "202"}),
            entries={
                "101": ("Alice Smith", "Cat 3"),
                "202": ("Bob Jones", "Cat 2"),
            },
        )

    def test_matched_number(self):
        """Number present in roster → name, category, matched=True."""
        roster = self._make_roster()
        name, category, matched = enrich("101", roster)
        assert matched is True
        assert name == "Alice Smith"
        assert category == "Cat 3"

    def test_matched_second_number(self):
        """Second roster entry also works correctly."""
        roster = self._make_roster()
        name, category, matched = enrich("202", roster)
        assert matched is True
        assert name == "Bob Jones"
        assert category == "Cat 2"

    def test_unmatched_number(self):
        """Number absent from roster → None, "Unknown", matched=False."""
        roster = self._make_roster()
        name, category, matched = enrich("999", roster)
        assert matched is False
        assert name is None
        assert category == "Unknown"

    def test_empty_number_string(self):
        """Empty string for number → always unmatched (manual with no number)."""
        roster = self._make_roster()
        name, category, matched = enrich("", roster)
        assert matched is False
        assert name is None
        assert category == "Unknown"

    def test_empty_roster(self):
        """EMPTY_ROSTER → always unmatched for any number."""
        name, category, matched = enrich("101", EMPTY_ROSTER)
        assert matched is False
        assert name is None
        assert category == "Unknown"

    def test_return_type(self):
        """Return value is always a 3-tuple."""
        roster = self._make_roster()
        result = enrich("101", roster)
        assert isinstance(result, tuple)
        assert len(result) == 3
