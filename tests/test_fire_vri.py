"""Tests for the VRI-to-FBP fuel-type mapping and its provenance."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.fire.vri import (
    VRI_FBP_VERSION,
    FbpFuelAssignment,
    VriError,
    VriStand,
    map_vri_stand,
    map_vri_table,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fire" / "vri_fbp_stands.csv"


def fixture_frame() -> pd.DataFrame:
    """Read the representative VRI fixture."""
    return pd.read_csv(FIXTURE)


def test_fixture_maps_every_stand_with_provenance() -> None:
    frame = fixture_frame()
    for record in frame.to_dict("records"):
        row = {str(key): value for key, value in record.items()}
        if row["expected_rule"] == "unknown-species":
            with pytest.raises(VriError, match="unknown leading_species"):
                map_vri_stand(VriStand.from_row(row))
            continue
        assignment = map_vri_stand(VriStand.from_row(row))
        expected = row["expected_fuel_type"]
        assert assignment.fuel_type == (None if pd.isna(expected) else expected)
        assert assignment.rule_id == row["expected_rule"]
        assert assignment.version == VRI_FBP_VERSION
        assert 0.0 <= assignment.confidence <= 1.0
        assert assignment.source_fields
        assert assignment.is_burnable is (assignment.fuel_type is not None)


def test_table_mapping_keeps_the_provenance_columns() -> None:
    frame = fixture_frame()
    valid = frame[frame["expected_rule"] != "unknown-species"]
    mapped = map_vri_table(valid)

    assert list(mapped.columns) == [
        "stand_id",
        "fuel_type",
        "rule_id",
        "version",
        "confidence",
        "source_fields",
        "is_burnable",
        "notes",
    ]
    assert len(mapped) == len(valid)
    assert mapped["version"].eq(VRI_FBP_VERSION).all()
    row = mapped.loc[mapped["stand_id"] == "S012"].iloc[0]
    assert pd.isna(row["fuel_type"])
    assert bool(row["is_burnable"]) is False


def test_mapping_is_deterministic_and_json_serializable() -> None:
    stand = VriStand(
        stand_id="S100",
        leading_species="Lodgepole pine",
        conifer_fraction=0.9,
        deciduous_fraction=0.1,
        crown_closure_percent=55.0,
        age_years=75,
        height_m=22.0,
    )
    first = map_vri_stand(stand)
    second = map_vri_stand(stand)

    assert first == second
    assert json.loads(json.dumps(first.to_dict()))["fuel_type"] == "C3"


def test_species_aliases_and_explicit_types() -> None:
    douglas_fir = VriStand(
        stand_id="S101",
        leading_species="Douglas-fir",
        conifer_fraction=0.9,
        deciduous_fraction=0.1,
        crown_closure_percent=60.0,
    )
    assert map_vri_stand(douglas_fir).fuel_type == "C7"

    explicit = VriStand(
        stand_id="S102",
        leading_species=None,
        conifer_fraction=0.0,
        deciduous_fraction=0.0,
        crown_closure_percent=0.0,
        fuel_type="C-2",
    )
    assignment = map_vri_stand(explicit)
    assert assignment.fuel_type == "C2"
    assert assignment.rule_id == "explicit-fbp"
    assert assignment.confidence == 1.0


def test_unknown_and_invalid_inputs_fail_explicitly() -> None:
    with pytest.raises(VriError, match="sum to at most one"):
        VriStand(
            stand_id="bad",
            leading_species="Pl",
            conifer_fraction=0.8,
            deciduous_fraction=0.5,
            crown_closure_percent=50.0,
        )
    with pytest.raises(VriError, match="crown_closure_percent"):
        VriStand(
            stand_id="bad",
            leading_species="Pl",
            conifer_fraction=1.0,
            deciduous_fraction=0.0,
            crown_closure_percent=120.0,
        )
    with pytest.raises(VriError, match="land_cover"):
        VriStand(
            stand_id="bad",
            leading_species="Pl",
            conifer_fraction=1.0,
            deciduous_fraction=0.0,
            crown_closure_percent=50.0,
            land_cover="moon",
        )
    with pytest.raises(VriError, match="explicit fuel_type"):
        map_vri_stand(
            VriStand(
                stand_id="bad",
                leading_species=None,
                conifer_fraction=0.0,
                deciduous_fraction=0.0,
                crown_closure_percent=0.0,
                fuel_type="X9",
            )
        )
    with pytest.raises(VriError, match="no leading species"):
        map_vri_stand(
            VriStand(
                stand_id="bad",
                leading_species=None,
                conifer_fraction=0.9,
                deciduous_fraction=0.1,
                crown_closure_percent=50.0,
            )
        )


def test_sparse_cover_is_an_explicit_non_fuel_assignment() -> None:
    stand = VriStand(
        stand_id="S103",
        leading_species=None,
        conifer_fraction=0.0,
        deciduous_fraction=0.0,
        crown_closure_percent=2.0,
    )
    assignment = map_vri_stand(stand)
    assert assignment.fuel_type is None
    assert assignment.rule_id == "sparse-cover"
    assert isinstance(assignment, FbpFuelAssignment)
