"""Tests for the fragment inventory reader."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.io.fragments import read_fragments


def test_read_fragments_from_csv(tmp_path: Path) -> None:
    """A CSV inventory reads into a DataFrame."""
    path = tmp_path / "fragments.csv"
    pd.DataFrame({"BLOCK": [1], "AREA_HA": [5.0], "F_AGE": [40]}).to_csv(path, index=False)
    frame = read_fragments(path)
    assert list(frame.columns) == ["BLOCK", "AREA_HA", "F_AGE"]
    assert frame["AREA_HA"].iloc[0] == 5.0


def test_read_fragments_from_shapefile(tmp_path: Path) -> None:
    """A shapefile inventory reads into a DataFrame of attributes."""
    geopandas = pytest.importorskip("geopandas")
    from shapely.geometry import Point

    path = tmp_path / "fragments.shp"
    frame = geopandas.GeoDataFrame(
        {"BLOCK": [1, 2], "AREA_HA": [5.0, 3.0], "F_AGE": [40, 60]},
        geometry=[Point(0, 0), Point(1, 1)],
    )
    frame.to_file(path)
    attributes = read_fragments(path)
    assert "geometry" not in attributes.columns
    assert sorted(attributes["BLOCK"]) == [1, 2]


def test_unsupported_format_is_rejected(tmp_path: Path) -> None:
    """An unknown suffix is rejected."""
    with pytest.raises(ValueError, match="unsupported"):
        read_fragments(tmp_path / "fragments.xlsx")
