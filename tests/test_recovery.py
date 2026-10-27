"""Post-fire recovery status ingest tests."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box
from ws4.recovery import (
    RecoveryError,
    sample_recovery_raster,
    summarize_recovery_status,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Write a recovery raster and two block polygons."""
    raster = tmp_path / "recovery.tif"
    data = np.array(
        [[3, 3, 2, 2], [3, 3, 2, 2], [1, 1, 15, 15], [1, 1, 15, 15]],
        dtype=np.uint8,
    )
    with rasterio.open(
        raster,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype="uint8",
        crs="EPSG:3005",
        transform=from_origin(0, 120, 30, 30),
        nodata=15,
    ) as dst:
        dst.write(data, 1)
    blocks = gpd.GeoDataFrame(
        {
            "block_id": [1, 2],
            "area_ha": [4.0, 4.0],
            "geometry": [box(0, 60, 60, 120), box(0, 0, 60, 60)],
        },
        crs="EPSG:3005",
    )
    path = tmp_path / "blocks.geojson"
    blocks.to_file(path, driver="GeoJSON")
    return raster, path


def test_recovery_status_fractions_and_dominant(tmp_path: Path) -> None:
    """Class fractions and dominant status are computed from valid pixels."""
    raster, blocks = _fixture(tmp_path)
    status, source = sample_recovery_raster(raster, blocks, source_version="fixture-v1")
    first = status[status.block_id == 1].iloc[0]
    second = status[status.block_id == 2].iloc[0]

    assert source.disturbance_years == "1986-2012"
    assert first.dominant_status == "not_recovered"
    assert first.not_recovered_fraction == pytest.approx(1.0)
    assert second.dominant_status == "faster"
    assert second.faster_fraction == pytest.approx(1.0)
    assert second.not_recovered_fraction == pytest.approx(0.0)


def test_recovery_status_marks_outside_footprint(tmp_path: Path) -> None:
    """A block with no recovery classes is outside the footprint, not failed."""
    raster, _blocks = _fixture(tmp_path)
    outside = gpd.GeoDataFrame(
        {"block_id": [3], "area_ha": [1.0], "geometry": [box(60, 0, 90, 30)]},
        crs="EPSG:3005",
    )
    path = tmp_path / "outside.geojson"
    outside.to_file(path, driver="GeoJSON")
    status, _source = sample_recovery_raster(raster, path, source_version="fixture-v1")
    assert status.iloc[0]["dominant_status"] == "outside_footprint"
    assert status.iloc[0]["valid_pixels"] == 0


def test_recovery_requires_version(tmp_path: Path) -> None:
    """An empty source version is rejected."""
    raster, blocks = _fixture(tmp_path)
    with pytest.raises(RecoveryError, match="source_version"):
        sample_recovery_raster(raster, blocks, source_version=" ")


def test_recovery_summary(tmp_path: Path) -> None:
    """The summary groups block count and area by dominant status."""
    raster, blocks = _fixture(tmp_path)
    status, _source = sample_recovery_raster(raster, blocks, source_version="fixture-v1")
    summary = summarize_recovery_status(status)
    assert set(summary["dominant_status"]) == {"faster", "not_recovered"}
    assert summary["blocks"].sum() == 2
