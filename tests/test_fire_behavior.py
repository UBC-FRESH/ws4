"""Tests for explicit fire-behaviour classes and transitions."""

from __future__ import annotations

import pytest
from ws4.fire.behavior import (
    FireBehaviourClass,
    classify_fire_behaviour,
    transition,
)
from ws4.fire.fuel import FireFuelError


def test_behaviour_boundaries_are_explicit() -> None:
    """CFB and flame-length boundaries map to the four classes."""
    assert (
        classify_fire_behaviour(crown_fraction_burned=0.9, flame_length_m=10.0)
        is FireBehaviourClass.ACTIVE_CROWN
    )
    assert (
        classify_fire_behaviour(crown_fraction_burned=0.1, flame_length_m=10.0)
        is FireBehaviourClass.PASSIVE_CROWN
    )
    assert (
        classify_fire_behaviour(crown_fraction_burned=0.0, flame_length_m=0.5)
        is FireBehaviourClass.SURFACE
    )
    assert (
        classify_fire_behaviour(crown_fraction_burned=0.0, flame_length_m=0.49)
        is FireBehaviourClass.GROUND
    )


def test_behaviour_rejects_bad_values() -> None:
    """Invalid fractions and negative lengths are rejected."""
    with pytest.raises(FireFuelError):
        classify_fire_behaviour(crown_fraction_burned=1.1, flame_length_m=1.0)
    with pytest.raises(FireFuelError):
        classify_fire_behaviour(crown_fraction_burned=0.0, flame_length_m=-1.0)


def test_transition_labels_are_explicit() -> None:
    """Transitions carry the previous and current classes."""
    change = transition(FireBehaviourClass.SURFACE, FireBehaviourClass.PASSIVE_CROWN)

    assert change.label == "surface->passive_crown"
    assert change.is_transition
    assert change.to_dict() == {
        "previous": "surface",
        "current": "passive_crown",
        "label": "surface->passive_crown",
    }
    same = transition(FireBehaviourClass.ACTIVE_CROWN, FireBehaviourClass.ACTIVE_CROWN)
    assert same.label == "unchanged"
    assert not same.is_transition


def test_transition_requires_enum_values() -> None:
    """Raw strings are not accepted as classes."""
    with pytest.raises(FireFuelError):
        transition("surface", FireBehaviourClass.SURFACE)  # type: ignore[arg-type]
