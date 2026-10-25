from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box
from typer.testing import CliRunner
from ws4.cli import app
from ws4.io.lidar import (
    FemicLidarError,
    bundle_pin,
    load_femic_lidar_bundle,
    load_registered_femic_lidar_bundle,
    map_femic_lidar_to_fragments,
    read_registered_femic_lidar,
    register_femic_lidar_bundle,
    summarize_femic_lidar_for_polygons,
    validate_femic_lidar_bundle,
    validate_registered_femic_lidar,
    write_lidar_mapping,
)
from ws4.model.types import CanonicalDatasetManifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    products = root / "products"
    products.mkdir(parents=True)
    raster_path = products / "slope__01__slope.tif"
    values = np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0], [70.0, 80.0, 90.0]])
    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        width=3,
        height=3,
        count=1,
        dtype="float32",
        crs="EPSG:3005",
        transform=from_origin(0, 3, 1, 1),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(values, 1)
    chm_path = products / "chm__02__chm.tif"
    with rasterio.open(
        chm_path,
        "w",
        driver="GTiff",
        width=3,
        height=3,
        count=1,
        dtype="float32",
        crs="EPSG:3005",
        transform=from_origin(0, 3, 1, 1),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(np.arange(1.0, 10.0).reshape(3, 3), 1)
    manifest = {
        "schema_version": "femic.lidar.product.v1",
        "layout_version": "femic.lidar.bundle.v1",
        "bundle_id": "lidarbc-test",
        "bundle_version": "test-1",
        "source": {
            "source_id": "lidarbc",
            "licence_id": "OGL-BC",
            "native_crs": "EPSG:3005",
        },
        "selection": {
            "sha256": "a" * 64,
            "tile_ids": ["lidarbc:5:1"],
            "products": ["slope"],
        },
        "processing": {"version": "test"},
        "summary": {
            "product_count": 2,
            "total_bytes": raster_path.stat().st_size + chm_path.stat().st_size,
        },
        "products": [
            {
                "product": "slope",
                "relative_path": "products/slope__01__slope.tif",
                "sha256": _sha256(raster_path),
                "size_bytes": raster_path.stat().st_size,
                "crs": "EPSG:3005",
                "resolution_m": 1.0,
                "vertical_datum": "CGVD2013",
                "licence_id": "OGL-BC",
                "source_tile_ids": ["lidarbc:5:1"],
                "derived": True,
                "lineage": ["test"],
            },
            {
                "product": "chm",
                "relative_path": "products/chm__02__chm.tif",
                "sha256": _sha256(chm_path),
                "size_bytes": chm_path.stat().st_size,
                "crs": "EPSG:3005",
                "resolution_m": 1.0,
                "vertical_datum": "CGVD2013",
                "licence_id": "OGL-BC",
                "source_tile_ids": ["lidarbc:5:1"],
                "derived": True,
                "lineage": ["test"],
            },
        ],
        "consumer_contract": {"manifest_path": "manifest.json"},
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


def test_load_and_pin_bundle(tmp_path: Path) -> None:
    root = _bundle(tmp_path)

    bundle = load_femic_lidar_bundle(
        root,
        expected_bundle_id="lidarbc-test",
        expected_bundle_version="test-1",
    )

    assert bundle.bundle_id == "lidarbc-test"
    assert bundle.products["slope"].crs == "EPSG:3005"
    assert bundle.products["slope"].resolution_m == 1.0
    pin = bundle_pin(bundle)
    assert pin["bundle_id"] == "lidarbc-test"
    assert pin["products"]["slope"]["sha256"]
    assert validate_femic_lidar_bundle(root).is_valid


def test_tampered_bundle_is_rejected(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    (root / "products/slope__01__slope.tif").write_bytes(b"tampered")

    report = validate_femic_lidar_bundle(root)
    assert not report.is_valid
    assert any("checksum" in error for error in report.errors)
    with pytest.raises(FemicLidarError, match="Invalid FEMIC"):
        load_femic_lidar_bundle(root)


def test_expected_pin_mismatch_is_rejected(tmp_path: Path) -> None:
    root = _bundle(tmp_path)

    with pytest.raises(FemicLidarError, match="Bundle id"):
        load_femic_lidar_bundle(root, expected_bundle_id="other")


def test_polygon_summary(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    bundle = load_femic_lidar_bundle(root)
    polygons = gpd.GeoDataFrame(
        {"feature_id": ["p1"]},
        geometry=[box(0, 0, 3, 3)],
        crs="EPSG:3005",
    )
    polygon_path = tmp_path / "polygons.geojson"
    polygons.to_file(polygon_path, driver="GeoJSON")

    summaries = summarize_femic_lidar_for_polygons(
        bundle,
        polygon_path,
        id_field="feature_id",
    )

    assert len(summaries) == 1
    assert summaries[0].polygon_id == "p1"
    assert summaries[0].valid_pixels == 9
    assert summaries[0].statistics["mean"] == pytest.approx(50.0)
    assert summaries[0].statistics["p95"] == pytest.approx(86.0)


def test_polygon_summary_rejects_crs_mismatch(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    bundle = load_femic_lidar_bundle(root)
    polygons = gpd.GeoDataFrame(
        {"feature_id": ["p1"]},
        geometry=[box(0, 0, 3, 3)],
        crs="EPSG:4326",
    )
    polygon_path = tmp_path / "polygons.geojson"
    polygons.to_file(polygon_path, driver="GeoJSON")

    with pytest.raises(FemicLidarError, match="CRS"):
        summarize_femic_lidar_for_polygons(bundle, polygon_path)


def _dataset(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    root.mkdir()
    manifest = CanonicalDatasetManifest(tables={}, sources=[], metadata={})
    (root / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    return root


def test_register_bundle_in_dataset(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)

    registration = register_femic_lidar_bundle(
        dataset,
        bundle_dir,
        expected_bundle_id="lidarbc-test",
        registered_utc="2026-10-25T00:00:00+00:00",
    )

    assert registration["bundle_id"] == "lidarbc-test"
    assert registration["bundle_version"] == "test-1"
    assert registration["registered_utc"] == "2026-10-25T00:00:00+00:00"
    assert (dataset / "lidar_products.json").is_file()
    manifest = json.loads((dataset / "manifest.json").read_text())
    assert manifest["metadata"]["lidar_products"]["bundle_id"] == "lidarbc-test"
    assert read_registered_femic_lidar(dataset)["bundle_id"] == "lidarbc-test"
    assert validate_registered_femic_lidar(dataset).is_valid


def test_register_bundle_is_idempotent(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    first = register_femic_lidar_bundle(dataset, bundle_dir)
    second = register_femic_lidar_bundle(dataset, bundle_dir)

    assert first["bundle_id"] == second["bundle_id"]
    assert first["manifest_sha256"] == second["manifest_sha256"]


def test_register_rejects_missing_dataset_and_wrong_pin(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    with pytest.raises(FemicLidarError, match="Dataset manifest"):
        register_femic_lidar_bundle(tmp_path / "missing", bundle_dir)

    dataset = _dataset(tmp_path)
    with pytest.raises(FemicLidarError, match="Bundle id"):
        register_femic_lidar_bundle(dataset, bundle_dir, expected_bundle_id="other")


def test_registered_bundle_detects_tamper(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    (bundle_dir / "products/slope__01__slope.tif").write_bytes(b"tampered")

    report = validate_registered_femic_lidar(dataset)
    assert not report.is_valid
    assert any("checksum" in error for error in report.errors)


def test_lidar_cli_register_inspect_validate(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    runner = CliRunner()

    registered = runner.invoke(
        app,
        ["lidar", "register", "--dataset", str(dataset), "--bundle", str(bundle_dir)],
    )
    assert registered.exit_code == 0, registered.output
    inspected = runner.invoke(app, ["lidar", "inspect", "--dataset", str(dataset)])
    assert inspected.exit_code == 0, inspected.output
    assert "lidarbc-test" in inspected.output
    validated = runner.invoke(app, ["lidar", "validate", "--dataset", str(dataset)])
    assert validated.exit_code == 0, validated.output
    assert '"is_valid": true' in validated.output


def test_lidar_cli_missing_registration(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    inspected = CliRunner().invoke(app, ["lidar", "inspect", "--dataset", str(dataset)])
    assert inspected.exit_code == 0
    assert "No FEMIC LidarBC product" in inspected.output
    validated = CliRunner().invoke(app, ["lidar", "validate", "--dataset", str(dataset)])
    assert validated.exit_code == 1


def _fragments(tmp_path: Path) -> Path:
    frame = gpd.GeoDataFrame(
        {
            "fragment_id": [1, 2, 3],
            "block_id": [10, 10, 20],
            "area_ha": [0.5, 0.5, 0.25],
        },
        geometry=[box(0, 0, 1.5, 3), box(1.5, 0, 3, 3), box(3, 0, 4, 3)],
        crs="EPSG:3005",
    )
    path = tmp_path / "fragments.geojson"
    frame.to_file(path, driver="GeoJSON")
    return path


def test_map_lidar_to_fragments_and_blocks(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    fragments = _fragments(tmp_path)
    bundle = load_registered_femic_lidar_bundle(dataset)

    result = map_femic_lidar_to_fragments(
        bundle,
        fragments,
        generated_utc="2026-10-25T00:00:00+00:00",
    )

    assert len(result.fragments) == 3
    assert len(result.blocks) == 2
    first = result.fragments[0]
    assert first["slope_mean"] == pytest.approx(45.0)
    assert first["chm_mean"] == pytest.approx(4.5)
    block = result.blocks[0]
    assert block["block_id"] == 10
    assert block["slope_mean"] == pytest.approx(50.0)
    assert block["chm_mean"] == pytest.approx(5.0)
    assert result.aggregation_rules["resolution"].startswith("native")
    assert result.manifest_sha256

    paths = write_lidar_mapping(result, tmp_path / "mapping")
    assert paths["fragments"].is_file()
    assert paths["blocks"].is_file()
    assert paths["manifest"].is_file()
    manifest = json.loads(paths["manifest"].read_text())
    assert manifest["bundle_id"] == "lidarbc-test"
    assert manifest["fragment_count"] == 3


def test_map_lidar_rejects_missing_product_and_crs(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    fragments = _fragments(tmp_path)
    bundle = load_registered_femic_lidar_bundle(dataset)

    with pytest.raises(FemicLidarError, match="does not contain product"):
        map_femic_lidar_to_fragments(bundle, fragments, products=("dem",))

    wrong_crs = gpd.read_file(fragments).to_crs("EPSG:4326")
    wrong_path = tmp_path / "wrong_crs.geojson"
    wrong_crs.to_file(wrong_path, driver="GeoJSON")
    with pytest.raises(FemicLidarError, match="CRS"):
        map_femic_lidar_to_fragments(bundle, wrong_path)


def test_lidar_cli_map(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    fragments = _fragments(tmp_path)
    out = tmp_path / "mapping"

    result = CliRunner().invoke(
        app,
        [
            "lidar",
            "map",
            "--dataset",
            str(dataset),
            "--fragments",
            str(fragments),
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "fragments: 3" in result.output
    assert (out / "lidar_fragments.csv").is_file()
    assert (out / "lidar_blocks.csv").is_file()
