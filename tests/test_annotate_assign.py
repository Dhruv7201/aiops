"""Tests for round-robin image assignment."""

import pytest

from aiops.annotate.assign import round_robin_assign

FILES = [f"img_{i:02d}.png" for i in range(10)]


class TestRoundRobinAssign:
    def test_even_split_counts(self):
        result = round_robin_assign(FILES, ["a", "b", "c"])
        counts = {u: sum(1 for v in result.values() if v == u) for u in "abc"}
        assert sorted(counts.values(), reverse=True) == [4, 3, 3]
        assert set(result) == set(FILES)

    def test_deterministic(self):
        assert round_robin_assign(FILES, ["a", "b"]) == round_robin_assign(
            FILES, ["a", "b"]
        )

    def test_keep_existing(self):
        existing = {"img_00.png": "carol"}
        result = round_robin_assign(FILES, ["a", "b"], existing=existing)
        assert result["img_00.png"] == "carol"

    def test_keep_existing_false_reassigns(self):
        existing = {"img_00.png": "carol"}
        result = round_robin_assign(
            FILES, ["a", "b"], existing=existing, keep_existing=False
        )
        assert result["img_00.png"] in ("a", "b")

    def test_stale_existing_dropped(self):
        existing = {"gone.png": "carol"}
        result = round_robin_assign(FILES, ["a"], existing=existing)
        assert "gone.png" not in result

    def test_no_users_raises(self):
        with pytest.raises(ValueError):
            round_robin_assign(FILES, [])
