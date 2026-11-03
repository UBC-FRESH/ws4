"""Tests for the profile-aware GPU web worker helpers."""

from __future__ import annotations

from ws4.opt.gpu_profile_run import _schedule_changes, _target_event_payload


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


def test_target_event_payload_uses_sparse_cells() -> None:
    """Target values and series come from the incumbent's cell totals."""
    from ws4.opt.objective import Target

    target = Target("feature.Volume", period=1, period_width=1, minimum=1.0)
    payload = _target_event_payload([target], {(0, "feature.Volume"): 5.0}, 7)
    assert payload["profile"] is True
    assert payload["iteration"] == 7
    assert payload["values"] == [
        {
            "index": 0,
            "account": "feature.Volume",
            "period": 1,
            "year": 1,
            "flow": "",
            "value": 5.0,
        }
    ]
    assert payload["series"] == [{"year": 1, "account": "feature.Volume", "value": 5.0}]
