"""Tests for the profile-aware GPU web worker helpers."""

from __future__ import annotations

from ws4.opt.gpu_profile_run import _schedule_changes


def test_schedule_changes_reset_then_diff() -> None:
    """The first event is a full reset; later events carry only changed blocks."""
    first: dict[int, tuple[tuple[str, int], ...]] = {
        1: (("CC", 10),),
        2: (("CT", 2),),
    }
    reset, payload = _schedule_changes(None, first)
    assert reset is True
    assert payload == [[1, (("CC", 10),)], [2, (("CT", 2),)]]
    second: dict[int, tuple[tuple[str, int], ...]] = {
        1: (("CC", 10),),
        2: (("CT", 3),),
    }
    reset, payload = _schedule_changes(first, second)
    assert reset is False
    assert payload == [[2, (("CT", 3),)]]
