"""Tests for the spatial constraints: openings, green-up, and the penalty."""

from __future__ import annotations

from ws4.patch.constraints import (
    green_up_violations,
    opening_violations,
    openings_by_year,
    schedule_years,
    spatial_penalty,
)


def test_openings_by_year_returns_the_largest_patch() -> None:
    """Each year reports its largest connected opening."""
    edges = [(1, 2), (2, 3)]
    area = {1: 4.0, 2: 6.0, 3: 10.0}
    assert openings_by_year({0: {1, 2, 3}, 1: {1, 3}}, edges, area) == {0: 20.0, 1: 10.0}


def test_opening_violations_report_the_excess() -> None:
    """A patch over the maximum is reported, and one at the maximum is not."""
    edges = [(1, 2), (2, 3)]
    area = {1: 4.0, 2: 6.0, 3: 10.0}
    records = opening_violations({0: {1, 2, 3}}, edges, area, 15.0)
    assert len(records) == 1
    assert records[0]["kind"] == "opening"
    assert records[0]["area_ha"] == 20.0
    assert opening_violations({0: {1, 2, 3}}, edges, area, 20.0) == []


def test_green_up_violations_report_adjacent_pairs() -> None:
    """Only adjacent pairs disturbed within the interval are reported."""
    records = green_up_violations({1: [0], 2: [1], 3: [5]}, [(1, 2), (2, 3)], 3)
    assert [(r["block_a"], r["block_b"], r["years"]) for r in records] == [(1, 2, 1)]


def test_green_up_violations_use_every_disturbance_year() -> None:
    """With rotations, the closest pair of disturbance years decides the violation."""
    records = green_up_violations({1: [0, 10], 2: [12]}, [(1, 2)], 3)
    assert [(r["block_a"], r["block_b"], r["years"]) for r in records] == [(1, 2, 2)]
    assert green_up_violations({1: [0, 10], 2: [40]}, [(1, 2)], 3) == []


def test_spatial_penalty_is_zero_when_respected() -> None:
    """A schedule that respects every active constraint scores zero."""
    assert spatial_penalty({0: {1}}, {1: [0]}, [(1, 2)], {1: 4.0, 2: 6.0}, 10.0, 3) == 0.0


def test_spatial_penalty_sums_excess_and_shortfall() -> None:
    """The penalty is the excess opening area plus the green-up shortfall."""
    # A 10 ha opening over a 5 ha maximum (+5) and a 1-year gap under a 3-year rule (+2).
    window = {1: [0], 2: [1]}
    assert spatial_penalty({0: {1, 2}}, window, [(1, 2)], {1: 4.0, 2: 6.0}, 5.0, 3) == 7.0


def test_schedule_years_splits_blocks_and_disturbance_years() -> None:
    """The split records the blocks per year and every disturbance year per block."""
    selected, years = schedule_years([(1, 0), (2, 0), (1, 4)])
    assert selected == {0: {1, 2}, 4: {1}}
    assert years == {1: [0, 4], 2: [0]}
