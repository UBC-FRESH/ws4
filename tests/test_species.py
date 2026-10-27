"""Species composition ingest and comparison tests."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box
from ws4.species import (
    SpeciesClass,
    SpeciesError,
    build_species_fractions,
    compare_leading_species,
    read_class_map,
    sample_species_raster,
    summarize_comparison,
    summarize_species_fractions,
)

CLASSES = (
    SpeciesClass(0, "Non treed"),
    SpeciesClass(11, "Yellow-cedar", "CHAM.NOO"),
    SpeciesClass(33, "Western redcedar", "THUJ.PLI"),
    SpeciesClass(35, "Western hemlock", "TSUG.HET"),
)


def _raster_and_blocks(tmp_path: Path) -> tuple[Path, Path]:
    """Write a 4 x 4 class raster and two block polygons."""
    raster = tmp_path / "species.tif"
    data = np.array(
        [
            [33, 33, 33, 11],
            [33, 33, 35, 11],
            [35, 35, 35, 11],
            [35, 35, 0, 0],
        ],
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
        nodata=255,
    ) as dst:
        dst.write(data, 1)
    blocks = gpd.GeoDataFrame(
        {
            "block_id": [1, 2],
            "geometry": [box(0, 60, 120, 120), box(0, 0, 120, 60)],
        },
        crs="EPSG:3005",
    )
    blocks_path = tmp_path / "blocks.geojson"
    blocks.to_file(blocks_path, driver="GeoJSON")
    return raster, blocks_path


def test_read_class_map(tmp_path: Path) -> None:
    """A CSV class map round-trips code and names."""
    path = tmp_path / "classes.csv"
    path.write_text(
        "code,name,nfi_code\n11,Yellow-cedar,CHAM.NOO\n33,Western redcedar,THUJ.PLI\n",
        encoding="utf-8",
    )
    classes = read_class_map(path)
    assert [(item.code, item.name) for item in classes] == [
        (11, "Yellow-cedar"),
        (33, "Western redcedar"),
    ]


def test_sample_species_raster_fractions_and_leading(tmp_path: Path) -> None:
    """Block fractions are pixel counts divided by total valid pixels."""
    raster, blocks = _raster_and_blocks(tmp_path)
    composition, source = sample_species_raster(
        raster,
        blocks,
        CLASSES,
        source_version="fixture-v1",
        year=2022,
    )
    block_one = composition[composition["block_id"] == 1]
    block_two = composition[composition["block_id"] == 2]

    assert source.source_version == "fixture-v1"
    assert source.year == 2022
    assert block_one.loc[block_one["is_leading"], "species_code"].tolist() == [33]
    assert block_one.loc[block_one["species_code"] == 33, "class_fraction"].iloc[
        0
    ] == pytest.approx(5 / 8)
    assert block_two.loc[block_two["is_leading"], "species_code"].tolist() == [35]
    assert block_two["class_fraction"].sum() == pytest.approx(1.0)


def test_sample_species_raster_rejects_missing_coverage(tmp_path: Path) -> None:
    """A block outside the raster is a coverage failure, not a zero."""
    raster, _ = _raster_and_blocks(tmp_path)
    outside = gpd.GeoDataFrame(
        {"block_id": [99], "geometry": [box(1000, 1000, 1030, 1030)]}, crs="EPSG:3005"
    )
    outside_path = tmp_path / "outside.geojson"
    outside.to_file(outside_path, driver="GeoJSON")
    with pytest.raises(SpeciesError, match="does not cover"):
        sample_species_raster(raster, outside_path, CLASSES, source_version="fixture-v1")


def test_sample_species_raster_requires_version(tmp_path: Path) -> None:
    """An empty source version is rejected before sampling."""
    raster, blocks = _raster_and_blocks(tmp_path)
    with pytest.raises(SpeciesError, match="source_version"):
        sample_species_raster(raster, blocks, CLASSES, source_version=" ")


def test_compare_leading_species_and_summary() -> None:
    """Agreement is explicit and missing reference blocks are counted."""
    composition = pd.DataFrame(
        {
            "block_id": [1, 1, 2, 2, 3],
            "species_code": [33, 35, 35, 33, 11],
            "species_name": [
                "Western redcedar",
                "Western hemlock",
                "Western hemlock",
                "Western redcedar",
                "Yellow-cedar",
            ],
            "class_fraction": [0.8, 0.2, 0.7, 0.3, 1.0],
            "is_leading": [True, False, True, False, True],
        }
    )
    reference = pd.DataFrame({"block_id": [1, 2], "leading_species_code": [33, 11]})
    comparison = compare_leading_species(composition, reference)
    summary = summarize_comparison(comparison)

    assert summary["blocks_compared"] == 2
    assert summary["matches"] == 1
    assert summary["agreement_pct"] == 50.0
    assert summary["missing_reference"] == 1
    assert comparison.loc[comparison["block_id"] == 1, "match"].iloc[0]
    assert not comparison.loc[comparison["block_id"] == 2, "match"].iloc[0]


def test_build_species_fractions_and_summary() -> None:
    """Explicit VRI percentages become fractions and a non-leading share."""
    frame = pd.DataFrame(
        {
            "feature_id": [1, 2, 3],
            "species_cd_1": ["CW", "YC", None],
            "species_pct_1": [45.0, 60.0, None],
            "species_cd_2": ["YC", "CW", None],
            "species_pct_2": [35.0, 40.0, None],
            "species_cd_3": ["HW", None, None],
            "species_pct_3": [20.0, None, None],
        }
    )
    fractions, metadata = build_species_fractions(
        frame,
        class_map=CLASSES,
        code_map={"CW": 33, "YC": 11, "HW": 35},
        source_id="vri-fixture",
        source_version="fixture-v1",
        species_columns=("species_cd_1", "species_cd_2", "species_cd_3"),
        percent_columns=("species_pct_1", "species_pct_2", "species_pct_3"),
        block_id_column="feature_id",
        allow_missing=True,
    )
    summary = summarize_species_fractions(fractions)

    assert metadata["missing_blocks"] == [3]
    assert metadata["block_count"] == 2
    assert fractions.loc[fractions["block_id"] == 1, "fraction"].sum() == pytest.approx(1.0)
    assert summary.loc[summary["block_id"] == 1, "leading_species_code"].iloc[0] == 33
    assert summary.loc[summary["block_id"] == 1, "non_leading_fraction"].iloc[0] == pytest.approx(
        0.55
    )
    assert summary.loc[summary["block_id"] == 2, "leading_species_code"].iloc[0] == 11


def test_species_fractions_reject_percentages_that_do_not_sum_to_100() -> None:
    """Percentages are not silently normalized."""
    frame = pd.DataFrame(
        {
            "feature_id": [1],
            "species_cd_1": ["CW"],
            "species_pct_1": [70.0],
            "species_cd_2": ["YC"],
            "species_pct_2": [20.0],
        }
    )
    with pytest.raises(SpeciesError, match="sum to"):
        build_species_fractions(
            frame,
            class_map=CLASSES,
            code_map={"CW": 33, "YC": 11},
            source_id="vri-fixture",
            source_version="fixture-v1",
            species_columns=("species_cd_1", "species_cd_2"),
            percent_columns=("species_pct_1", "species_pct_2"),
        )
