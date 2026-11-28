"""Tests for treatment age adjustment (relative versus absolute).

Treatments are state-transition triggers and age is a state dimension. The XML
default is absolute adjustment with offset 0 (age resets); a relative adjustment
adds the offset to the age at which the fragment is treated, so a relative offset
of 0 preserves the age.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.io.forest_model_xml import _treatment
from ws4.sim.engine import Simulator

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
_RECIPE = _FIXTURE / "recipe.xml"
_FRAGMENTS = _FIXTURE / "fragments.csv"


def _element(xml: str) -> ET.Element:
    """Parse a single treatment element."""
    return ET.fromstring(xml)


def test_absolute_is_the_default_when_adjust_is_absent() -> None:
    """No adjust attribute means absolute adjustment with offset 0."""
    treatment = _treatment(_element('<treatment label="CC" minage="40" maxage="120" />'))
    assert treatment.adjust == ""
    assert treatment.offset == 0


def test_relative_adjustment_is_parsed() -> None:
    """A relative adjustment exposes its mode and offset."""
    treatment = _treatment(
        _element('<treatment label="FT" minage="30" maxage="30" adjust="R" offset="-10" />')
    )
    assert treatment.adjust.upper().startswith("R")
    assert treatment.offset == -10


def test_relative_zero_offset_preserves_age(tmp_path: Path) -> None:
    """A relative treatment with offset 0 must not change the fragment's age."""
    dataset = build_canonical_dataset(_RECIPE, _FRAGMENTS, tmp_path / "compiled")
    treatments = pd.read_parquet(dataset / "treatments.parquet")
    treatments.loc[treatments["treatment"] == "CC", "relative"] = 1
    treatments.loc[treatments["treatment"] == "CC", "offset"] = 0
    treatments.to_parquet(dataset / "treatments.parquet", index=False)

    simulator = Simulator.from_dataset(dataset)
    before = int(simulator.fragments["offset"].iloc[0])
    assert before == 40  # the synthetic fixture's first fragment

    schedule = pd.DataFrame({"block_id": [1], "treatment": ["CC"], "offset": [0]})
    simulator.apply_treatments(schedule, 0)
    assert int(simulator.fragments["offset"].iloc[0]) == before


def test_absolute_zero_offset_resets_age(tmp_path: Path) -> None:
    """The default absolute treatment resets the fragment's age to the offset."""
    dataset = build_canonical_dataset(_RECIPE, _FRAGMENTS, tmp_path / "compiled")
    simulator = Simulator.from_dataset(dataset)
    assert int(simulator.fragments["offset"].iloc[0]) == 40

    schedule = pd.DataFrame({"block_id": [1], "treatment": ["CC"], "offset": [0]})
    simulator.apply_treatments(schedule, 0)
    assert int(simulator.fragments["offset"].iloc[0]) == 0


def test_relative_negative_offset_makes_the_fragment_younger(tmp_path: Path) -> None:
    """A relative offset of -10 makes the treated fragment ten years younger."""
    dataset = build_canonical_dataset(_RECIPE, _FRAGMENTS, tmp_path / "compiled")
    treatments = pd.read_parquet(dataset / "treatments.parquet")
    treatments.loc[treatments["treatment"] == "CC", "relative"] = 1
    treatments.loc[treatments["treatment"] == "CC", "offset"] = -10
    treatments.to_parquet(dataset / "treatments.parquet", index=False)

    simulator = Simulator.from_dataset(dataset)
    schedule = pd.DataFrame({"block_id": [1], "treatment": ["CC"], "offset": [0]})
    simulator.apply_treatments(schedule, 0)
    assert int(simulator.fragments["offset"].iloc[0]) == 30


def test_compiled_dataset_carries_the_relative_column(tmp_path: Path) -> None:
    """The compiler writes the column even when the recipe does not ask for it."""
    dataset = build_canonical_dataset(_RECIPE, _FRAGMENTS, tmp_path / "compiled")
    treatments = pd.read_parquet(dataset / "treatments.parquet")
    assert "relative" in treatments.columns
    assert set(treatments["relative"]) <= {0, 1}
    assert set(treatments["relative"]) == {0}  # the fixture declares absolute
