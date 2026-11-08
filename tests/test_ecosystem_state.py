"""Unit tests for the typed ecological state and the null bridge."""

from __future__ import annotations

import pandas as pd
import pytest
from ws4.ecosystem import (
    BridgeSpec,
    CohortState,
    CohortStateError,
    NullBridge,
    StateError,
    StateSchema,
    StateVariable,
)
from ws4.ecosystem.state import FRACTION_TOLERANCE

COLUMNS = [
    "fragment_id",
    "cohort_id",
    "species",
    "age",
    "area_fraction",
    "biomass_t_ha",
    "fuel_t_ha",
    "snag_t_ha",
    "attributes_json",
]


def make_schema() -> StateSchema:
    """Build a minimal valid state schema."""
    variables = {
        "species": StateVariable("species", "string", "cohort", "", None, ""),
        "age": StateVariable("age", "int", "cohort", "years", None, ""),
        "area_fraction": StateVariable("area_fraction", "float", "cohort", "", None, ""),
        "biomass_t_ha": StateVariable("biomass_t_ha", "float", "cohort", "t/ha", 0.0, ""),
        "fuel_t_ha": StateVariable("fuel_t_ha", "float", "cohort", "t/ha", 0.0, ""),
        "snag_t_ha": StateVariable("snag_t_ha", "float", "cohort", "t/ha", 0.0, ""),
        "habitat_index": StateVariable("habitat_index", "float", "cohort", "", 0.5, ""),
    }
    bridges = (
        BridgeSpec("null", "null", {}, (), ()),
        BridgeSpec("other", "null", {}, (), ()),
    )
    return StateSchema(variables=variables, bridges=bridges)


def raw_cohorts() -> pd.DataFrame:
    """Build one valid raw cohort table."""
    return pd.DataFrame(
        [
            ["1", "1", "PL", "80", "0.7", "120.0", "30.0", "5.0", "{}"],
            ["1", "2", "PY", "20", "0.3", "40.0", "10.0", "2.0", "{}"],
        ],
        columns=COLUMNS,
    )


def test_null_bridge_rejects_a_non_null_specification() -> None:
    with pytest.raises(StateError, match="not a null bridge"):
        NullBridge(BridgeSpec("bad", "yield", {}, (), ()))


def test_state_schema_returns_named_bridges() -> None:
    schema = make_schema()

    assert schema.bridge().bridge_id == "null"
    assert schema.bridge("other").bridge_id == "other"
    assert schema.null_bridge().spec.bridge_id == "null"


def test_cohort_state_fills_blank_numbers_from_the_default() -> None:
    frame = raw_cohorts()
    frame.loc[0, "biomass_t_ha"] = ""

    state = CohortState.from_tables(frame, make_schema(), {1: 10.0})

    assert state.cohorts.loc[0, "biomass_t_ha"] == 0.0


def test_empty_cohort_state_has_stable_frames() -> None:
    state = CohortState.from_tables(pd.DataFrame(columns=COLUMNS), make_schema(), {1: 10.0})

    assert list(state.aggregate_to_fragments().columns) == [
        "fragment_id",
        "area_ha",
        "cohort_count",
        "age",
        "biomass_t_ha",
        "fuel_t_ha",
        "snag_t_ha",
    ]
    assert list(state.species_fractions().columns) == [
        "fragment_id",
        "species",
        "area_fraction",
        "area_ha",
    ]
    assert state.missing_fragments() == (1,)
    state.check_area_conservation()


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("age", "-1", "age must be non-negative"),
        ("species", "", "species must be non-empty"),
        ("area_fraction", "0", "area_fraction must be in"),
        ("area_fraction", "1.5", "area_fraction must be in"),
        ("biomass_t_ha", "-1", "must be non-negative"),
    ],
)
def test_bad_cohort_values_are_rejected(column: str, value: str, message: str) -> None:
    frame = raw_cohorts()
    frame.loc[0, column] = value

    with pytest.raises(CohortStateError, match=message):
        CohortState.from_tables(frame, make_schema(), {1: 10.0})


def test_bad_area_fraction_sum_is_rejected() -> None:
    frame = raw_cohorts()
    frame.loc[0, "area_fraction"] = "0.5"

    with pytest.raises(CohortStateError, match="sum to"):
        CohortState.from_tables(frame, make_schema(), {1: 10.0})


def test_duplicate_cohort_is_rejected() -> None:
    frame = pd.concat([raw_cohorts(), raw_cohorts().iloc[[0]]], ignore_index=True)

    with pytest.raises(CohortStateError, match="duplicate cohort"):
        CohortState.from_tables(frame, make_schema(), {1: 10.0})


def test_bad_attribute_json_is_rejected() -> None:
    frame = raw_cohorts()
    frame.loc[0, "attributes_json"] = "{not json"

    with pytest.raises(CohortStateError, match="valid JSON"):
        CohortState.from_tables(frame, make_schema(), {1: 10.0})


def test_unknown_cohort_attribute_is_rejected() -> None:
    frame = raw_cohorts()
    frame.loc[0, "attributes_json"] = '{"invented": 1}'

    with pytest.raises(CohortStateError, match="unknown cohort attribute"):
        CohortState.from_tables(frame, make_schema(), {1: 10.0})


def test_fixed_cohort_attribute_is_rejected() -> None:
    frame = raw_cohorts()
    frame.loc[0, "attributes_json"] = '{"age": 1}'

    with pytest.raises(CohortStateError, match="already a cohort column"):
        CohortState.from_tables(frame, make_schema(), {1: 10.0})


def test_non_scalar_cohort_attribute_is_rejected() -> None:
    frame = raw_cohorts()
    frame.loc[0, "attributes_json"] = '{"habitat_index": {"a": 1}}'

    with pytest.raises(CohortStateError, match="JSON scalars"):
        CohortState.from_tables(frame, make_schema(), {1: 10.0})


def test_blank_number_without_a_default_is_rejected() -> None:
    schema = make_schema()
    variables = dict(schema.variables)
    variables["biomass_t_ha"] = StateVariable("biomass_t_ha", "float", "cohort", "t/ha", None, "")
    frame = raw_cohorts()
    frame.loc[0, "biomass_t_ha"] = ""

    with pytest.raises(CohortStateError, match="no numeric default"):
        CohortState.from_tables(frame, StateSchema(variables, schema.bridges), {1: 10.0})


def test_area_conservation_detects_a_bad_fraction_sum() -> None:
    typed = pd.DataFrame(
        [
            {
                "fragment_id": 1,
                "cohort_id": 1,
                "species": "PL",
                "age": 10,
                "area_fraction": 0.5,
                "biomass_t_ha": 1.0,
                "fuel_t_ha": 1.0,
                "snag_t_ha": 1.0,
                "attributes_json": "{}",
            }
        ],
        columns=COLUMNS,
    )
    state = CohortState(cohorts=typed, schema=make_schema(), fragment_areas={1: 10.0})

    assert FRACTION_TOLERANCE < 0.5
    with pytest.raises(CohortStateError, match="sum to"):
        state.check_area_conservation()
