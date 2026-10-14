"""Tests for the Model II stratum-and-track expansion."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.build.compiler import build_canonical_dataset
from ws4.model.schema import validate_dataset

_RECIPE = """<?xml version="1.0" encoding="UTF-8"?>
<ForestModel horizon="100" year="0" match="multi">
  <curve id="unity"><point x="0" y="1.0"/></curve>
  <curve id="volume"><point x="0" y="0"/><point x="100" y="100"/></curve>
  <define field="status" column="STATUS"/>
  <define field="treatment"/>
  <input block="BLOCK" area="AREA_HA" age="F_AGE"/>
  <output messages="messages.csv"/>
  <select statement="status eq 'N'">
    <features><attribute label="feature.Volume"><curve idref="volume"/></attribute></features>
    <track/>
  </select>
  <select statement="status eq 'C'">
    <features><attribute label="feature.Volume"><curve idref="volume"/></attribute></features>
    <track>
      <treatment label="CC" minage="40" maxage="100">
        <transition><assign field="treatment" value="'CC'"/></transition>
      </treatment>
    </track>
  </select>
</ForestModel>
"""


def _build(tmp_path: Path) -> Path:
    """Compile a two-status, three-fragment Model II fixture."""
    (tmp_path / "recipe.xml").write_text(_RECIPE, encoding="utf-8")
    pd.DataFrame(
        {
            "BLOCK": [1, 1, 2],
            "AREA_HA": [3.0, 2.0, 4.0],
            "F_AGE": [10, 20, 30],
            "STATUS": ["N", "C", "C"],
        }
    ).to_csv(tmp_path / "fragments.csv", index=False)
    return build_canonical_dataset(
        tmp_path / "recipe.xml", tmp_path / "fragments.csv", tmp_path / "c"
    )


def test_expansion_dataset_validates(tmp_path: Path) -> None:
    """The expanded dataset validates."""
    assert validate_dataset(_build(tmp_path)) == []


def test_expansion_enumerates_reachable_strata(tmp_path: Path) -> None:
    """The inventory strata plus the treatment target become tracks."""
    dataset = _build(tmp_path)
    tracks = pd.read_parquet(dataset / "tracks.parquet")
    strata = pd.read_parquet(dataset / "strata.parquet")
    assert len(tracks) == 3  # (N, '') (C, '') (C, 'CC')
    assert len(strata) == 3
    assert set(tracks["name"]) == {
        "status(N)+treatment()",
        "status(C)+treatment()",
        "status(C)+treatment(CC)",
    }


def test_expansion_splits_blocks_by_track(tmp_path: Path) -> None:
    """A block with fragments in two strata gets one row per portion."""
    dataset = _build(tmp_path)
    blocks = pd.read_parquet(dataset / "blocks.parquet")
    assert len(blocks) == 3  # block 1 x2, block 2 x1
    assert int((blocks["block_id"] == 1).sum()) == 2


def test_expansion_emits_per_track_treatments(tmp_path: Path) -> None:
    """A treatment is emitted once per stratum whose select it governs."""
    dataset = _build(tmp_path)
    treatments = pd.read_parquet(dataset / "treatments.parquet")
    assert len(treatments) == 2  # CC on (C, '') and (C, 'CC')
    assert set(treatments["new_track"]) == {3}
