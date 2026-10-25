from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box
from typer.testing import CliRunner
from ws4.cli import app
from ws4.io.lidar import (
    FemicLidarError,
    bundle_pin,
    integrate_lidar_mapping_into_dataset,
    load_femic_lidar_bundle,
    load_registered_femic_lidar_bundle,
    map_femic_canopy_to_fragments,
    map_femic_lidar_to_fragments,
    read_registered_femic_lidar,
    register_femic_lidar_bundle,
    summarize_femic_lidar_for_polygons,
    validate_femic_lidar_bundle,
    validate_registered_femic_lidar,
    write_canopy_mapping,
    write_lidar_mapping,
)
from ws4.model.schema import TABLES, validate_dataset
from ws4.model.types import CanonicalDatasetManifest
from ws4.sim.engine import Simulator


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
    tree_path = products / "individual_tree__03__trees.geojson"
    trees = gpd.GeoDataFrame(
        {
            "tree_id": ["t1", "t2", "t3"],
            "height_m": [10.0, 12.0, 14.0],
            "species": ["HW", "CW", "HW"],
        },
        geometry=[Point(0.5, 0.5), Point(2.5, 1.5), Point(3.5, 1.5)],
        crs="EPSG:3005",
    )
    trees.to_file(tree_path, driver="GeoJSON")
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
            "product_count": 3,
            "total_bytes": (
                raster_path.stat().st_size + chm_path.stat().st_size + tree_path.stat().st_size
            ),
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
            {
                "product": "individual_tree",
                "relative_path": "products/individual_tree__03__trees.geojson",
                "sha256": _sha256(tree_path),
                "size_bytes": tree_path.stat().st_size,
                "crs": "EPSG:3005",
                "resolution_m": None,
                "vertical_datum": "CGVD2013",
                "licence_id": "OGL-BC",
                "source_tile_ids": ["lidarbc:5:1"],
                "derived": False,
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


def _vri(tmp_path: Path) -> Path:
    frame = gpd.GeoDataFrame(
        {
            "feature_id": [1],
            "proj_height_1": [8.0],
            "crown_closure": [80.0],
        },
        geometry=[box(0, 0, 4, 3)],
        crs="EPSG:3005",
    )
    path = tmp_path / "vri.geojson"
    frame.to_file(path, driver="GeoJSON")
    return path


def test_map_canopy_vri_and_trees(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    fragments = _fragments(tmp_path)
    vri = _vri(tmp_path)
    bundle = load_registered_femic_lidar_bundle(dataset)

    result = map_femic_canopy_to_fragments(
        bundle,
        fragments,
        vri_path=vri,
        tree_product="individual_tree",
        generated_utc="2026-10-25T00:00:00+00:00",
    )

    assert len(result.fragments) == 3
    assert len(result.blocks) == 2
    first = result.fragments[0]
    assert first["chm_mean"] == pytest.approx(4.5)
    assert first["chm_cover_ge_2"] == pytest.approx(83.3333333)
    assert first["vri_height_m"] == pytest.approx(8.0)
    assert first["vri_cover_pct"] == pytest.approx(80.0)
    assert first["tree_count"] == 1
    assert first["tree_height_mean_m"] == pytest.approx(10.0)
    assert result.vri_summary is not None
    assert result.vri_summary["matched_supports"] == 2
    assert result.tree_summary is not None
    assert result.tree_summary["tree_count"] == 3
    assert result.tree_summary["supports_with_trees"] == 3
    assert result.caveats

    paths = write_canopy_mapping(result, tmp_path / "canopy")
    assert paths["fragments"].is_file()
    assert paths["blocks"].is_file()
    assert paths["manifest"].is_file()
    payload = json.loads(paths["manifest"].read_text())
    assert payload["vri_summary"]["matched_supports"] == 2
    assert payload["tree_summary"]["tree_count"] == 3


def test_canopy_mapping_rejects_vri_crs(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    fragments = _fragments(tmp_path)
    vri = gpd.read_file(_vri(tmp_path)).to_crs("EPSG:4326")
    wrong = tmp_path / "vri_wrong.geojson"
    vri.to_file(wrong, driver="GeoJSON")
    bundle = load_registered_femic_lidar_bundle(dataset)

    with pytest.raises(FemicLidarError, match="VRI CRS"):
        map_femic_canopy_to_fragments(bundle, fragments, vri_path=wrong)


def test_lidar_cli_canopy_map(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    fragments = _fragments(tmp_path)
    vri = _vri(tmp_path)
    out = tmp_path / "canopy"

    result = CliRunner().invoke(
        app,
        [
            "lidar",
            "canopy",
            "--dataset",
            str(dataset),
            "--fragments",
            str(fragments),
            "--vri",
            str(vri),
            "--tree-product",
            "individual_tree",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "vri_matched_supports: 2" in result.output
    assert "trees: 3" in result.output
    assert (out / "canopy_fragments.csv").is_file()
    assert (out / "canopy_mapping_manifest.json").is_file()


def _compiled_dataset(tmp_path: Path) -> Path:
    dataset = tmp_path / "compiled"
    dataset.mkdir()
    tables = {
        "fragments": pd.DataFrame(
            {
                "fragment_id": [1, 2, 3],
                "block_id": [10, 10, 20],
                "area_ha": [0.5, 0.5, 0.25],
                "age": [40, 60, 50],
                "track_id": [1, 1, 1],
            }
        ),
        "blocks": pd.DataFrame(
            {"block_id": [10, 20], "track_id": [1, 1], "offset": [0, 0], "area_ha": [1.0, 0.25]}
        ),
        "tracks": pd.DataFrame({"track_id": [1], "name": ["natural"]}),
        "strata": pd.DataFrame({"track_id": [1], "offset": [0], "next_age": [0], "cycle": [0]}),
        "treatments": pd.DataFrame(
            {
                "track_id": [1],
                "begin": [40],
                "end": [80],
                "treatment": ["CC"],
                "new_track": [1],
                "offset": [0],
                "retain": [0],
            }
        ),
        "curves": pd.DataFrame({"curve_id": [1, 1], "x": [0.0, 10.0], "y": [0.0, 1.0]}),
        "features": pd.DataFrame({"track_id": [1], "label": ["feature.Area"], "curve_id": [1]}),
        "products": pd.DataFrame(
            {"track_id": [1], "treatment": ["CC"], "label": ["product.Volume"], "curve_id": [1]}
        ),
        "protoaccounts": pd.DataFrame(
            {
                "group": ["all"],
                "attribute": ["feature.Area"],
                "account": ["feature.Area"],
                "sum": [1.0],
            }
        ),
        "accounts": pd.DataFrame(
            {
                "group": ["all"],
                "attribute": ["feature.Area"],
                "account": ["feature.Area"],
                "sum": [1.0],
            }
        ),
        "groups": pd.DataFrame({"block_id": [10, 20], "group": ["forest", "forest"]}),
        "messages": pd.DataFrame({"severity": ["info"], "message": ["ok"]}),
    }
    for table in TABLES:
        tables[table.name].to_parquet(dataset / table.file, index=False)
    manifest = CanonicalDatasetManifest(tables={table.name: table.file for table in TABLES})
    (dataset / "manifest.json").write_text(manifest.model_dump_json(indent=2))
    return dataset


def test_integrate_lidar_fields_into_dataset(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _compiled_dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    fragments = _fragments(tmp_path)
    vri = _vri(tmp_path)
    bundle = load_registered_femic_lidar_bundle(dataset)
    mapping = map_femic_canopy_to_fragments(
        bundle,
        fragments,
        vri_path=vri,
        tree_product="individual_tree",
        generated_utc="2026-10-25T00:00:00+00:00",
    )
    paths = write_canopy_mapping(mapping, tmp_path / "mapping")

    assert validate_dataset(dataset) == []
    result = integrate_lidar_mapping_into_dataset(
        dataset,
        paths["fragments"],
        block_mapping_path=paths["blocks"],
        generated_utc="2026-10-25T00:00:00+00:00",
    )

    assert result.fragment_rows == 3
    assert result.block_rows == 2
    assert "lidar_chm_mean" in result.fragment_fields
    assert "lidar_vri_height_m" in result.fragment_fields
    assert "lidar_tree_count" in result.fragment_fields
    fragments_table = pd.read_parquet(dataset / "fragments.parquet")
    blocks_table = pd.read_parquet(dataset / "blocks.parquet")
    assert "lidar_chm_mean" in fragments_table.columns
    assert "lidar_chm_mean" in blocks_table.columns
    assert fragments_table.loc[0, "lidar_chm_mean"] == pytest.approx(4.5)
    assert validate_dataset(dataset) == []
    simulator = Simulator.from_dataset(dataset)
    assert len(simulator.fragments) == 3
    assert "lidar_chm_mean" in simulator.fragments.columns
    manifest = json.loads((dataset / "manifest.json").read_text())
    assert manifest["metadata"]["lidar_fields"]["bundle_id"] == "lidarbc-test"
    assert manifest["metadata"]["lidar_fields"]["fragment_fields"] == list(result.fragment_fields)

    with pytest.raises(FemicLidarError, match="already has LiDAR fields"):
        integrate_lidar_mapping_into_dataset(
            dataset,
            paths["fragments"],
            block_mapping_path=paths["blocks"],
        )
    overwritten = integrate_lidar_mapping_into_dataset(
        dataset,
        paths["fragments"],
        block_mapping_path=paths["blocks"],
        overwrite=True,
    )
    assert overwritten.fragment_rows == 3


def test_integration_rejects_unknown_ids_and_missing_registration(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _compiled_dataset(tmp_path)
    fragments = _fragments(tmp_path)
    mapping = map_femic_lidar_to_fragments(
        load_femic_lidar_bundle(bundle_dir),
        fragments,
    )
    paths = write_lidar_mapping(mapping, tmp_path / "mapping")
    with pytest.raises(FemicLidarError, match="no registered"):
        integrate_lidar_mapping_into_dataset(dataset, paths["fragments"])

    register_femic_lidar_bundle(dataset, bundle_dir)
    fragment_frame = pd.read_csv(paths["fragments"])
    fragment_frame.loc[0, "fragment_id"] = 999
    bad = tmp_path / "bad_fragments.csv"
    fragment_frame.to_csv(bad, index=False)
    with pytest.raises(FemicLidarError, match="unknown"):
        integrate_lidar_mapping_into_dataset(dataset, bad)


def test_lidar_cli_integrate(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    dataset = _compiled_dataset(tmp_path)
    register_femic_lidar_bundle(dataset, bundle_dir)
    fragments = _fragments(tmp_path)
    mapping = map_femic_lidar_to_fragments(
        load_registered_femic_lidar_bundle(dataset),
        fragments,
    )
    paths = write_lidar_mapping(mapping, tmp_path / "mapping")
    result = CliRunner().invoke(
        app,
        [
            "lidar",
            "integrate",
            "--dataset",
            str(dataset),
            "--fragments-mapping",
            str(paths["fragments"]),
            "--blocks-mapping",
            str(paths["blocks"]),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "fragment_rows: 3" in result.output
    assert "lidar_slope_mean" in result.output
