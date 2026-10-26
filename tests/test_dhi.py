"""Dynamic Habitat Index ingest, account, report, and web-layer tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from ws4.dhi import (
    DhiAccount,
    DhiError,
    DhiSource,
    read_dhi_account,
    sample_dhi_raster,
    write_dhi_ingest,
)
from ws4.report import write_report

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "dhi_pilot"
SOURCE_VERSION = "MODIS 6.1 Terra NDVI Composite RGB (2003-2022)"


def _account() -> DhiAccount:
    """Read the committed pilot values."""
    return read_dhi_account(EXAMPLE / "dhi_values.csv", EXAMPLE / "dhi_metadata.json")


def test_sample_dhi_raster_covers_blocks_and_records_provenance() -> None:
    """The real subset samples all four blocks and keeps source metadata."""
    pytest.importorskip("geopandas")
    pytest.importorskip("rasterio")

    values, source = sample_dhi_raster(
        EXAMPLE / "dhi_ndvi_terra_500m_subset.tif",
        EXAMPLE / "blocks.geojson",
        source_version=SOURCE_VERSION,
        retrieved_utc="2026-10-26T00:00:00+00:00",
    )
    committed = pd.read_csv(EXAMPLE / "dhi_values.csv")

    assert values["block_id"].tolist() == [1, 2, 3, 4]
    for band in ("cum", "min", "var"):
        assert values[band].between(0.0, 1.0).all()
        pd.testing.assert_series_equal(values[band], committed[band], check_names=False, rtol=1e-12)
    assert source.source_version == SOURCE_VERSION
    assert source.year_range == "2003-2022"
    assert source.valid_pixels > 0
    assert source.bbox[0] < -122.9 < source.bbox[2]


def test_sample_dhi_raster_refuses_a_block_outside_the_layer(tmp_path: Path) -> None:
    """A block with no valid pixels is a coverage failure, not a zero."""
    pytest.importorskip("geopandas")
    pytest.importorskip("rasterio")

    outside = tmp_path / "outside.geojson"
    outside.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"block_id": 1},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[0.0, 0.0], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01], [0.0, 0.0]]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DhiError, match="does not cover"):
        sample_dhi_raster(
            EXAMPLE / "dhi_ndvi_terra_500m_subset.tif",
            outside,
            source_version=SOURCE_VERSION,
        )


def test_source_requires_version() -> None:
    """Dropping the source version fails rather than silently losing provenance."""
    payload = json.loads((EXAMPLE / "dhi_metadata.json").read_text())
    payload.pop("source_version")
    with pytest.raises(DhiError, match="source_version"):
        DhiSource.from_dict(payload)


def test_read_dhi_account_requires_both_files(tmp_path: Path) -> None:
    """A values file without metadata is not a usable account."""
    with pytest.raises(DhiError, match="metadata"):
        read_dhi_account(EXAMPLE / "dhi_values.csv", tmp_path / "missing.json")


def test_dhi_account_removes_treated_blocks_from_the_totals() -> None:
    """The account is a level: total index-hectares and a mean over surviving blocks."""
    account = _account()
    areas = {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}

    baseline = account.account_values(areas)
    harvested = account.account_values(areas, excluded_blocks={1})

    assert baseline["feature.DHI.area"] == pytest.approx(40.0)
    assert harvested["feature.DHI.area"] == pytest.approx(30.0)
    assert harvested["feature.DHI.cum"] < baseline["feature.DHI.cum"]
    assert harvested["feature.DHI.cum.mean"] == pytest.approx(
        (account.values[2]["cum"] + account.values[3]["cum"] + account.values[4]["cum"]) / 3
    )


def test_dhi_account_requires_every_dataset_block() -> None:
    """A layer that does not cover every block is rejected before it is reported."""
    account = _account()
    with pytest.raises(DhiError, match="missing"):
        account.account_values({1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0, 99: 10.0})


def test_simulate_records_the_dhi_trajectory_for_two_schedules(tmp_path: Path) -> None:
    """The baseline stays flat; the harvest schedule drops the surviving DHI area."""
    pytest.importorskip("geopandas")
    pytest.importorskip("rasterio")
    from ws4.build.compiler import build_canonical_dataset
    from ws4.sim.engine import Simulator

    dataset = build_canonical_dataset(
        EXAMPLE / "recipe.xml", EXAMPLE / "fragments.csv", tmp_path / "compiled"
    )
    account = _account()

    baseline_dir = tmp_path / "baseline"
    Simulator.from_dataset(dataset).run(
        EXAMPLE / "schedule_baseline.csv",
        10,
        baseline_dir,
        dhi_account=account,
    )
    harvest_dir = tmp_path / "harvest"
    Simulator.from_dataset(dataset).run(
        EXAMPLE / "schedule_harvest.csv",
        10,
        harvest_dir,
        dhi_account=account,
    )

    baseline = pd.read_csv(baseline_dir / "account_values.csv")
    harvest = pd.read_csv(harvest_dir / "account_values.csv")
    base_area = baseline.loc[baseline["account"] == "feature.DHI.area", "value"].to_numpy()
    harvest_area = harvest.loc[harvest["account"] == "feature.DHI.area", "value"].to_numpy()

    assert base_area.min() == pytest.approx(40.0)
    assert base_area.max() == pytest.approx(40.0)
    assert harvest_area[0] == pytest.approx(40.0)
    assert harvest_area[-1] == pytest.approx(20.0)
    assert (baseline_dir / "dhi_values.csv").is_file()
    assert (baseline_dir / "dhi_metadata.json").is_file()
    metadata = json.loads((baseline_dir / "dhi_metadata.json").read_text())
    assert metadata["source_version"] == SOURCE_VERSION


def test_report_writes_a_dhi_block_with_the_caveat(tmp_path: Path) -> None:
    """The standard report gains a DHI table that names its source and limits."""
    account = _account()
    areas = {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}
    values = pd.DataFrame(
        [
            {"offset": -1, "account": key, "value": value}
            for key, value in account.account_values(areas).items()
        ]
        + [
            {"offset": 0, "account": key, "value": value}
            for key, value in account.account_values(areas, excluded_blocks={1}).items()
        ]
    )
    (tmp_path / "dhi_metadata.json").write_text(
        json.dumps(account.source.to_dict()), encoding="utf-8"
    )

    write_report(values, [], tmp_path)

    report = pd.read_csv(tmp_path / "report_dhi.csv")
    row = report.loc[report["account"] == "feature.DHI.area"].iloc[0]
    assert row["unit"] == "ha"
    assert row["final"] == pytest.approx(30.0)
    assert row["source_version"] == SOURCE_VERSION
    assert "not a species observation" in row["caveat"]


def test_web_dhi_endpoint_returns_values_and_a_geojson_layer(tmp_path: Path) -> None:
    """The service exposes the run's DHI values and joins them to block geometry."""
    pytest.importorskip("fastapi")
    pytest.importorskip("geopandas")
    from fastapi.testclient import TestClient
    from ws4.web.app import create_app

    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    run = tmp_path / "runs" / "run1"
    run.mkdir(parents=True)
    account = _account()
    account.write(run)

    app = create_app(
        dataset=dataset,
        runs=tmp_path / "runs",
        geometry=EXAMPLE / "blocks.geojson",
        crs="EPSG:3005",
    )
    client = TestClient(app)

    response = client.get("/api/runs/run1/dhi")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["bands"] == ["cum", "min", "var"]
    assert len(payload["values"]) == 4
    assert payload["metadata"]["source_version"] == SOURCE_VERSION

    layer = client.get("/api/runs/run1/dhi?format=geojson").json()
    assert layer["type"] == "FeatureCollection"
    assert len(layer["features"]) == 4
    assert layer["features"][0]["properties"]["dhi"] == pytest.approx(account.values[1]["cum"])
    assert "not a species observation" in layer["caveat"]


def test_dhi_ingest_writes_both_artifacts(tmp_path: Path) -> None:
    """The ingest writer leaves a values CSV and a source JSON that round-trip."""
    pytest.importorskip("geopandas")
    pytest.importorskip("rasterio")
    values, source = sample_dhi_raster(
        EXAMPLE / "dhi_ndvi_terra_500m_subset.tif",
        EXAMPLE / "blocks.geojson",
        source_version=SOURCE_VERSION,
    )
    output = tmp_path / "values.csv"
    metadata = tmp_path / "metadata.json"
    write_dhi_ingest(values, source, output, metadata)

    loaded = read_dhi_account(output, metadata)
    assert loaded.source.source_version == SOURCE_VERSION
    assert sorted(loaded.values) == [1, 2, 3, 4]
