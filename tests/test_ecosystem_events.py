"""Tests for the unified ecosystem event record."""

from __future__ import annotations

import itertools
import math
from typing import Final

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from ws4.disturbance import DisturbanceEvent
from ws4.ecosystem import Event, EventError

JsonScalar = str | int | float | bool | None
Attribute = tuple[str, JsonScalar]


def make_event(
    event_id: str = "e1",
    *,
    process_id: str = "fire",
    event_type: str = "fire",
    time: float = 0.0,
    year: int = 0,
    phase: str = "ignition",
    source: str = "test",
    scenario_id: str = "s",
    priority: int = 0,
    fragment_ids: tuple[int, ...] = (),
    site_ids: tuple[int, ...] = (),
    block_ids: tuple[int, ...] = (),
    severity_class: str | None = None,
    severity_value: float | None = None,
    magnitude: float | None = None,
    area_ha: float | None = None,
    parent_event_id: str | None = None,
    confidence: float | None = None,
    attributes: tuple[Attribute, ...] = (),
) -> Event:
    """Build one valid event with overridable fields."""
    return Event(
        event_id=event_id,
        process_id=process_id,
        event_type=event_type,
        time=time,
        year=year,
        phase=phase,
        source=source,
        scenario_id=scenario_id,
        priority=priority,
        fragment_ids=fragment_ids,
        site_ids=site_ids,
        block_ids=block_ids,
        severity_class=severity_class,
        severity_value=severity_value,
        magnitude=magnitude,
        area_ha=area_ha,
        parent_event_id=parent_event_id,
        confidence=confidence,
        attributes=attributes,
    )


def test_event_canonicalizes_ids_and_attributes() -> None:
    event = make_event(fragment_ids=(3, 1), attributes=(("b", 2), ("a", 1)))

    assert event.fragment_ids == (1, 3)
    assert event.attributes == (("a", 1), ("b", 2))


def test_spatial_id_is_the_smallest_named_id() -> None:
    event = make_event(fragment_ids=(5,), site_ids=(3,), block_ids=(9,))

    assert event.spatial_id == 3


def test_spatial_id_is_zero_without_a_location() -> None:
    assert make_event().spatial_id == 0


def test_sort_key_orders_time_phase_priority_space_then_id() -> None:
    early = make_event("early", time=0.1)
    late = make_event("late", time=0.2)
    later_phase = make_event("later-phase", time=0.1, phase="effect")
    higher_priority = make_event("priority", time=0.1, priority=1)
    closer = make_event("closer", time=0.1, fragment_ids=(1,))
    farther = make_event("farther", time=0.1, fragment_ids=(2,))

    assert early.sort_key < late.sort_key
    assert early.sort_key < later_phase.sort_key
    assert early.sort_key < higher_priority.sort_key
    assert closer.sort_key < farther.sort_key
    assert make_event("a").sort_key < make_event("b").sort_key


def test_round_trip_preserves_the_event() -> None:
    event = make_event(
        "round",
        time=3.5,
        year=3,
        phase="treatment",
        event_type="harvest",
        fragment_ids=(1, 2),
        block_ids=(9,),
        severity_class="high",
        severity_value=0.8,
        magnitude=12.5,
        area_ha=4.0,
        parent_event_id="parent",
        confidence=0.9,
        attributes=(("wind", 3.5), ("ok", True), ("nothing", None)),
    )

    assert Event.from_dict(event.to_dict()) == event


def test_to_dict_carries_the_event_schema_version() -> None:
    assert make_event().to_dict()["schema_version"] == "ws4.event.v1"


def test_from_dict_accepts_attribute_pairs() -> None:
    event = Event.from_dict(
        {
            "event_id": "pairs",
            "process_id": "fire",
            "event_type": "fire",
            "time": 0.0,
            "year": 0,
            "phase": "ignition",
            "source": "test",
            "attributes": [["b", 2], ["a", 1]],
        }
    )

    assert event.attributes == (("a", 1), ("b", 2))


def test_negative_zero_is_normalized() -> None:
    event = make_event(magnitude=-0.0)

    assert event.magnitude == 0.0
    assert math.copysign(1.0, event.magnitude) == 1.0


BASE_EVENT: Final[dict[str, object]] = {
    "event_id": "e1",
    "process_id": "fire",
    "event_type": "fire",
    "time": 0.0,
    "year": 0,
    "phase": "ignition",
    "source": "test",
}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"phase": "weather"}, "phase must be one of"),
        ({"time": 1.5, "year": 2}, "year must equal floor"),
        ({"time": -0.1}, "time must be non-negative"),
        ({"area_ha": -1.0}, "area_ha must be non-negative"),
        ({"severity_value": 1.1}, "severity_value must be between"),
        ({"confidence": -0.1}, "confidence must be between"),
        ({"fragment_ids": (1, 1)}, "fragment_ids ids must be unique"),
        ({"site_ids": (0,)}, "site_ids ids must be positive"),
    ],
)
def test_invalid_fields_are_rejected(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(EventError, match=message):
        Event.from_dict({**BASE_EVENT, **overrides})


def test_non_scalar_attribute_is_rejected() -> None:
    with pytest.raises(EventError, match="JSON scalar"):
        Event.from_dict(
            {
                "event_id": "bad",
                "process_id": "fire",
                "event_type": "fire",
                "time": 0.0,
                "year": 0,
                "phase": "ignition",
                "source": "test",
                "attributes": {"nested": {"a": 1}},
            }
        )


def test_duplicate_attribute_key_is_rejected() -> None:
    with pytest.raises(EventError, match="attribute keys must be unique"):
        make_event(attributes=(("a", 1), ("a", 2)))


def test_missing_required_field_is_rejected() -> None:
    with pytest.raises(EventError, match="missing event fields: phase"):
        Event.from_dict(
            {
                "event_id": "bad",
                "process_id": "fire",
                "event_type": "fire",
                "time": 0.0,
                "year": 0,
                "source": "test",
            }
        )


def test_wrong_schema_version_is_rejected() -> None:
    payload = make_event().to_dict()
    payload["schema_version"] = "ws4.event.v0"

    with pytest.raises(EventError, match="schema_version"):
        Event.from_dict(payload)


def test_disturbance_fire_row_is_adapted_to_the_effect_phase() -> None:
    event = Event.from_disturbance_row(
        {
            "event_id": "fire-1",
            "event_type": "fire",
            "year": 2023,
            "severity_class": "high",
            "severity_value": 0.8,
            "confidence": 0.9,
            "source_id": "nbac",
            "fragment_ids": [1001],
            "block_ids": [101],
            "area_ha": 1200.0,
        }
    )

    assert event.time == 2023.0
    assert event.year == 2023
    assert event.phase == "effect"
    assert event.process_id == "nbac"
    assert event.source == "nbac"
    assert event.scenario_id == "default"


def test_disturbance_harvest_row_is_adapted_to_the_treatment_phase() -> None:
    event = Event.from_disturbance_row(
        {
            "event_id": "harvest-1",
            "event_type": "harvest",
            "year": 2024,
            "severity_class": "low",
            "confidence": 1.0,
            "source_id": "ws4.schedule",
        }
    )

    assert event.phase == "treatment"


def test_disturbance_row_requires_a_year() -> None:
    with pytest.raises(EventError, match="year must be an integer"):
        Event.from_disturbance_row({"event_id": "bad", "event_type": "fire", "source_id": "x"})


@settings(max_examples=40, deadline=None)
@given(st.lists(st.integers(min_value=1, max_value=100), unique=True, max_size=6))
def test_generated_ids_are_always_sorted(ids: list[int]) -> None:
    event = make_event(fragment_ids=tuple(ids))

    assert event.fragment_ids == tuple(sorted(ids))


def test_event_phases_are_ordered_as_documented() -> None:
    names: Final[tuple[str, ...]] = (
        "forcing",
        "ignition",
        "propagation",
        "effect",
        "growth",
        "treatment",
        "regeneration",
        "accounting",
    )
    for earlier, later in itertools.pairwise(names):
        assert make_event(phase=earlier).sort_key < make_event(phase=later).sort_key


def test_empty_text_is_rejected() -> None:
    with pytest.raises(EventError, match="event_id must be a non-empty string"):
        Event.from_dict({**BASE_EVENT, "event_id": "   "})


def test_non_numeric_time_is_rejected() -> None:
    with pytest.raises(EventError, match="time must be a number"):
        Event.from_dict({**BASE_EVENT, "time": "soon"})


def test_non_finite_time_is_rejected() -> None:
    with pytest.raises(EventError, match="time must be finite"):
        Event.from_dict({**BASE_EVENT, "time": float("inf")})


def test_ids_must_be_a_sequence() -> None:
    with pytest.raises(EventError, match="fragment_ids must be a sequence"):
        Event.from_dict({**BASE_EVENT, "fragment_ids": 1})


def test_attributes_must_be_a_mapping_or_pairs() -> None:
    with pytest.raises(EventError, match="attributes must be a mapping"):
        Event.from_dict({**BASE_EVENT, "attributes": 5})


def test_attribute_pairs_must_have_two_items() -> None:
    with pytest.raises(EventError, match="attributes must be a mapping"):
        Event.from_dict({**BASE_EVENT, "attributes": [["a"]]})


def test_negative_year_is_rejected() -> None:
    with pytest.raises(EventError, match="year must be non-negative"):
        Event.from_dict({**BASE_EVENT, "time": 0.0, "year": -1})


def test_to_disturbance_dict_round_trips_through_the_consumer() -> None:
    event = make_event(
        "fire-row",
        event_type="fire",
        severity_class="high",
        severity_value=0.8,
        confidence=0.9,
        area_ha=12.0,
        fragment_ids=(1,),
        block_ids=(2,),
    )

    row = event.to_disturbance_dict(2020)
    parsed = DisturbanceEvent.from_dict(row)

    assert parsed.event_id == "fire-row"
    assert parsed.event_type == "fire"
    assert parsed.year == 2020
    assert parsed.severity_class == "high"
    assert parsed.severity_value == pytest.approx(0.8)
    assert parsed.confidence == pytest.approx(0.9)
    assert parsed.source_id == event.source
    assert parsed.fragment_ids == (1,)
    assert parsed.block_ids == (2,)
    assert parsed.area_ha == pytest.approx(12.0)
