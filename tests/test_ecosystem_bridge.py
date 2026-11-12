"""Tests for the provisional biomass-to-volume bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.ecosystem.bridge import (
    BRIDGE_VERSION,
    BridgeError,
    SpeciesVolumeBridge,
    VolumeBridgeConfig,
)
from ws4.ecosystem.fire import synthetic_grid
from ws4.ecosystem.state import CohortState


def _state(species: str = "PL", biomass: float = 100.0) -> CohortState:
    """Return a small synthetic state."""
    _schema, state, _edges = synthetic_grid(3, 3)
    frame = state.cohorts.copy()
    frame["species"] = species
    frame["biomass_t_ha"] = biomass
    return CohortState(
        cohorts=frame.reset_index(drop=True),
        schema=state.schema,
        fragment_areas=state.fragment_areas,
    )


def test_bridge_maps_biomass_to_volume() -> None:
    state = _state()
    bridge = SpeciesVolumeBridge(
        VolumeBridgeConfig(volume_m3_per_t={"PL": 1.2}, default_volume_m3_per_t=1.0)
    )

    table = bridge.table(state)

    assert list(table.columns) == [
        "fragment_id",
        "area_ha",
        "biomass_t_ha",
        "volume_m3_ha",
        "volume_m3",
    ]
    assert table["volume_m3"].tolist() == pytest.approx([1200.0] * 9)
    assert table["volume_m3_ha"].tolist() == pytest.approx([120.0] * 9)


def test_bridge_uses_default_for_unknown_species_and_zero_biomass() -> None:
    bridge = SpeciesVolumeBridge(VolumeBridgeConfig(volume_m3_per_t={"PL": 1.2}))
    unknown = bridge.table(_state(species="XX", biomass=10.0))
    empty = bridge.table(_state(biomass=0.0))

    assert unknown["volume_m3"].tolist() == pytest.approx([100.0] * 9)
    assert empty["volume_m3"].tolist() == pytest.approx([0.0] * 9)


def test_bridge_attaches_to_management() -> None:
    state = _state()
    management = pd.DataFrame({"fragment_id": [1, 2], "track_id": ["a", "b"]})
    bridged = SpeciesVolumeBridge().apply(management, state)

    assert list(bridged["track_id"]) == ["a", "b"]
    assert list(bridged["volume_m3"]) == pytest.approx([1000.0, 1000.0])


def test_bridge_requires_fragment_id() -> None:
    with pytest.raises(BridgeError, match="fragment_id"):
        SpeciesVolumeBridge().apply(pd.DataFrame({"track_id": ["a"]}), _state())


def test_bridge_parameters_are_versioned_and_written(tmp_path: Path) -> None:
    config = VolumeBridgeConfig(volume_m3_per_t={"PL": 1.2})
    path = config.write(tmp_path / "bridge.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == BRIDGE_VERSION
    assert payload["calibration_status"] == "provisional"
    assert payload["volume_m3_per_t"] == {"PL": 1.2}
