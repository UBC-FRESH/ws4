"""A fixture-based matrix-builder regression, and the Model II expansion invariants."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from ws4.build.compiler import build_canonical_dataset
from ws4.model.schema import validate_dataset

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "matrix"
TABLES = ("tracks", "strata", "treatments", "blocks", "features", "products", "protoaccounts")


def _build(tmp_path: Path) -> Path:
    """Compile the regression fixture."""
    return build_canonical_dataset(
        FIXTURE / "recipe.xml", FIXTURE / "fragments.csv", tmp_path / "compiled"
    )


def _as_text(frame: pd.DataFrame) -> list[str]:
    """Render a frame as sorted comma-joined rows, for a dtype-insensitive comparison."""
    return sorted(",".join(str(value) for value in row) for row in frame.itertuples(index=False))


def test_the_fixture_compiles_without_problems(tmp_path: Path) -> None:
    """The regression fixture compiles into a valid dataset."""
    assert validate_dataset(_build(tmp_path)) == []


@pytest.mark.parametrize("table", TABLES)
def test_table_matches_the_reference_fixture(tmp_path: Path, table: str) -> None:
    """Each compiled table matches the committed expected table."""
    mine = pd.read_parquet(_build(tmp_path) / f"{table}.parquet")
    expected = pd.read_csv(FIXTURE / "expected" / f"{table}.csv")
    assert list(mine.columns) == list(expected.columns)
    assert _as_text(mine) == _as_text(expected)


def test_every_stratum_has_a_track(tmp_path: Path) -> None:
    """Each stratum belongs to a real track."""
    dataset = _build(tmp_path)
    tracks = set(pd.read_parquet(dataset / "tracks.parquet")["track_id"])
    strata = pd.read_parquet(dataset / "strata.parquet")
    assert set(strata["track_id"]) <= tracks


def test_every_treatment_connects_to_a_real_track(tmp_path: Path) -> None:
    """Each treatment's target track is real, or 0 for no transition."""
    dataset = _build(tmp_path)
    tracks = set(pd.read_parquet(dataset / "tracks.parquet")["track_id"])
    treatments = pd.read_parquet(dataset / "treatments.parquet")
    assert set(treatments["new_track"]) - {0} <= tracks


def test_retention_splits_conserve_area(tmp_path: Path) -> None:
    """The fragment area equals the summed block area, so retention conserves area."""
    dataset = _build(tmp_path)
    fragments = pd.read_parquet(dataset / "fragments.parquet")
    blocks = pd.read_parquet(dataset / "blocks.parquet")
    assert fragments["area_ha"].sum() == pytest.approx(blocks["area_ha"].sum())


@given(areas=st.lists(st.floats(min_value=0.1, max_value=100.0), min_size=1, max_size=6))
@settings(max_examples=10, deadline=None)
def test_area_is_conserved_for_random_fragments(areas: list[float]) -> None:
    """A retention split conserves area for an arbitrary set of fragment areas."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        fragments = root / "fragments.csv"
        pd.DataFrame(
            {
                "BLOCK": list(range(1, len(areas) + 1)),
                "AREA_HA": areas,
                "F_AGE": [30] * len(areas),
                "AU": ["A"] * len(areas),
                "IFM": ["managed"] * len(areas),
                "RETENTION": [0.3] * len(areas),
            }
        ).to_csv(fragments, index=False)
        dataset = build_canonical_dataset(FIXTURE / "recipe.xml", fragments, root / "compiled")
        frag = pd.read_parquet(dataset / "fragments.parquet")
        blocks = pd.read_parquet(dataset / "blocks.parquet")
        assert frag["area_ha"].sum() == pytest.approx(blocks["area_ha"].sum())
