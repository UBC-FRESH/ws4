"""Tests for FBP crown fire initiation, propagation, and classification.

The reference values in ``tests/fixtures/fire`` were generated with the ``cffdrs`` R package.
The package is a validation oracle only; the Python implementation is independent.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from ws4.fire.crown import (
    CrownFireResult,
    critical_surface_intensity,
    critical_surface_ros,
    crown_fraction_burned,
    crown_rate_of_spread_c6,
    fbp_crown_fire,
    foliar_moisture_content,
    van_wagner_active_crown,
)
from ws4.fire.fuel import FireFuelError

FIXTURES = Path(__file__).parent / "fixtures" / "fire"


def reference(name: str) -> list[dict[str, str]]:
    """Read one crown-fire reference table."""
    with (FIXTURES / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_base_crown_fire_matches_the_reference() -> None:
    for row in reference("fbp_surface_base.csv"):
        result = fbp_crown_fire(row["ID"], 90.0, 60.0, 10.0)
        assert result.crown_fraction_burned == pytest.approx(float(row["CFB"]), abs=0.02)
        assert result.fire_description == row["FD"]
        assert result.rate_of_spread_m_min == pytest.approx(float(row["ROS"]), abs=0.02)
        assert result.head_fire_intensity_kw_m == pytest.approx(float(row["HFI"]), abs=1.0)
        assert result.surface_only is False


def test_c6_crown_cases_match_the_reference() -> None:
    cases = {
        "C6a": (95.0, 80.0, 20.0),
        "C6b": (98.0, 100.0, 30.0),
        "C6c": (90.0, 60.0, 15.0),
    }
    for row in reference("fbp_c6_crown.csv"):
        ffmc, bui, wind = cases[row["ID"]]
        result = fbp_crown_fire("C6", ffmc, bui, wind)
        assert result.crown_fraction_burned == pytest.approx(float(row["CFB"]), abs=0.02)
        assert result.fire_description == row["FD"]
        assert result.rate_of_spread_m_min == pytest.approx(float(row["ROS"]), abs=0.02)
        assert result.head_fire_intensity_kw_m == pytest.approx(float(row["HFI"]), abs=1.0)


def test_crown_grid_matches_the_reference() -> None:
    for row in reference("fbp_surface_grid.csv"):
        result = fbp_crown_fire(
            row["FuelType"],
            float(row["FFMC"]),
            float(row["BUI"]),
            float(row["WS"]),
        )
        assert result.crown_fraction_burned == pytest.approx(float(row["CFB"]), abs=0.02)
        assert result.fire_description == row["FD"]
        assert result.rate_of_spread_m_min == pytest.approx(float(row["ROS"]), abs=0.02)
        assert result.head_fire_intensity_kw_m == pytest.approx(float(row["HFI"]), abs=1.0)


def test_foliar_moisture_matches_the_reference() -> None:
    assert foliar_moisture_content(55.0, -120.0, 0.0, 180) == pytest.approx(97.7764, abs=1e-4)
    assert foliar_moisture_content(55.0, 120.0, 0.0, 180) == pytest.approx(97.7764, abs=1e-4)


def test_critical_intensity_and_active_crown_threshold() -> None:
    csi = critical_surface_intensity(97.7764, 3.0)
    assert csi > 0.0
    assert critical_surface_ros(csi, 2.492) > 0.0

    assert van_wagner_active_crown(40.0, 0.1)
    assert not van_wagner_active_crown(2.0, 1.0)
    with pytest.raises(FireFuelError, match="canopy_bulk_density"):
        van_wagner_active_crown(10.0, 0.0)


def test_crown_fraction_is_bounded_and_monotone() -> None:
    assert crown_fraction_burned(1.0, 2.0) == 0.0
    assert 0.0 < crown_fraction_burned(5.0, 2.0) < 1.0
    assert crown_fraction_burned(10.0, 2.0) > crown_fraction_burned(5.0, 2.0)
    assert crown_rate_of_spread_c6(7.09, 97.7764) > 0.0


def test_active_crown_is_reported_when_cbd_is_given() -> None:
    result = fbp_crown_fire(
        "C6",
        95.0,
        80.0,
        20.0,
        canopy_bulk_density_kg_m3=0.1,
    )

    assert result.active_crown is True
    assert result.crown_rate_of_spread_m_min is not None
    assert result.crown_rate_of_spread_m_min > 0.0


def test_crown_result_serializes() -> None:
    result = fbp_crown_fire("C2", 90.0, 60.0, 10.0)
    payload = result.to_dict()

    assert isinstance(result, CrownFireResult)
    assert payload["fuel_type"] == "C2"
    assert payload["surface_only"] is False
    assert float(str(payload["crown_fraction_burned"])) > 0.0
    assert float(str(payload["head_fire_intensity_kw_m"])) > 0.0


def test_crown_fire_rejects_bad_inputs() -> None:
    with pytest.raises(FireFuelError, match="latitude_deg"):
        fbp_crown_fire("C2", 90.0, 60.0, 10.0, latitude_deg=100.0)
    with pytest.raises(FireFuelError, match="crown_base_height_m"):
        fbp_crown_fire("C2", 90.0, 60.0, 10.0, crown_base_height_m=-1.0)
    with pytest.raises(FireFuelError, match="surface_fuel_consumption"):
        critical_surface_ros(100.0, 0.0)
