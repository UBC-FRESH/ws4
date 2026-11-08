"""Tests for the FBP surface-fire layer.

The reference values in ``tests/fixtures/fire`` were generated with the ``cffdrs`` R package
(Canadian Forest Fire Behaviour Prediction System). The package is a validation oracle only;
the Python implementation is independent.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from ws4.fire.fbp import (
    FBP_FUEL_TYPE_TABLE,
    FBP_FUEL_TYPES,
    buildup_effect,
    canonical_fuel_type,
    fbp_surface_fire,
    surface_fuel_consumption,
)
from ws4.fire.fuel import FireFuelError

FIXTURES = Path(__file__).parent / "fixtures" / "fire"


def reference(name: str) -> list[dict[str, str]]:
    """Read one FBP reference table."""
    with (FIXTURES / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_fbp_fuel_type_table() -> None:
    assert len(FBP_FUEL_TYPES) == 17
    assert set(FBP_FUEL_TYPES) == set(FBP_FUEL_TYPE_TABLE)
    assert canonical_fuel_type("C-2") == "C2"
    assert canonical_fuel_type("o1a") == "O1A"
    with pytest.raises(FireFuelError, match="fuel_type must be one of"):
        canonical_fuel_type("X9")


def test_base_surface_fire_matches_the_reference() -> None:
    for row in reference("fbp_surface_base.csv"):
        result = fbp_surface_fire(row["ID"], 90.0, 60.0, 10.0)
        assert result.rate_of_spread_m_min == pytest.approx(float(row["ROS"]), abs=0.02)
        assert result.surface_fuel_consumption_kg_m2 == pytest.approx(float(row["SFC"]), abs=0.02)
        assert result.surface_only is True
        if float(row["CFB"]) == 0.0:
            assert result.head_fire_intensity_kw_m == pytest.approx(float(row["HFI"]), abs=0.5)
        else:
            assert result.head_fire_intensity_kw_m < float(row["HFI"])


def test_c6_surface_matches_the_reference() -> None:
    row = reference("fbp_surface_c6.csv")[0]
    result = fbp_surface_fire("C6", 90.0, 60.0, 10.0)

    assert result.rate_of_spread_m_min == pytest.approx(float(row["ROS"]), abs=0.02)
    assert result.surface_fuel_consumption_kg_m2 == pytest.approx(float(row["SFC"]), abs=0.02)
    assert result.head_fire_intensity_kw_m == pytest.approx(float(row["HFI"]), abs=0.5)


def test_grid_matches_the_reference() -> None:
    for row in reference("fbp_surface_grid.csv"):
        result = fbp_surface_fire(
            row["FuelType"],
            float(row["FFMC"]),
            float(row["BUI"]),
            float(row["WS"]),
        )
        assert result.rate_of_spread_m_min == pytest.approx(float(row["ROS"]), abs=0.02)
        assert result.surface_fuel_consumption_kg_m2 == pytest.approx(float(row["SFC"]), abs=0.02)


def test_buildup_effect_and_surface_fuel_consumption() -> None:
    low = buildup_effect("C2", 10.0)
    high = buildup_effect("C2", 100.0)

    assert low < 1.0 < high
    assert surface_fuel_consumption("O1A", 90.0, 60.0, grass_fuel_load_kg_m2=0.4) == pytest.approx(
        0.4
    )
    assert surface_fuel_consumption("C1", 90.0, 60.0) > 0.0
    assert surface_fuel_consumption("S3", 90.0, 60.0) > surface_fuel_consumption("S1", 90.0, 60.0)


def test_surface_fire_result_serializes() -> None:
    result = fbp_surface_fire("C2", 90.0, 60.0, 10.0)
    payload = result.to_dict()

    assert payload["fuel_type"] == "C2"
    assert payload["surface_only"] is True
    assert float(str(payload["rate_of_spread_m_min"])) > 0.0
    assert float(str(payload["flame_length_m"])) > 0.0


def test_surface_fire_rejects_bad_inputs() -> None:
    with pytest.raises(FireFuelError, match="ffmc"):
        fbp_surface_fire("C2", 102.0, 60.0, 10.0)
    with pytest.raises(FireFuelError, match="bui"):
        fbp_surface_fire("C2", 90.0, -1.0, 10.0)
    with pytest.raises(FireFuelError, match="wind_kmh"):
        fbp_surface_fire("C2", 90.0, 60.0, -1.0)
    with pytest.raises(FireFuelError, match="conifer_percent"):
        fbp_surface_fire("M1", 90.0, 60.0, 10.0, conifer_percent=120.0)
