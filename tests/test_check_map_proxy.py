"""Tests for the path-prefix map deployment check."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from check_map_proxy import check_prefix, main


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a tiny dataset, run, and geometry."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    runs = tmp_path / "runs"
    run = runs / "run1"
    run.mkdir(parents=True)
    (run / "summary.json").write_text('{"status": "ok"}', encoding="utf-8")
    (run / "schedule.csv").write_text("block_id,treatment,offset\n1,CC,0\n", encoding="utf-8")
    geometry = tmp_path / "geometry.geojson"
    geometry.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"block_id": 1},
                        "geometry": {"type": "Point", "coordinates": [0.5, 0.5]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return dataset, runs, geometry


def test_prefix_serves_shell_assets_api_and_tile(tmp_path: Path) -> None:
    """Every public surface answers through the mounted prefix."""
    dataset, runs, geometry = _fixture(tmp_path)
    report = check_prefix(
        dataset=dataset,
        runs=runs,
        geometry=geometry,
        prefix="/ws4",
    )
    assert report["ok"] is True
    assert report["relative_urls"] is True
    checks = report["checks"]
    assert isinstance(checks, list)
    assert {check["status"] for check in checks} == {200}


def test_prefix_rejects_an_invalid_value(tmp_path: Path) -> None:
    """The prefix must be an absolute non-root path."""
    dataset, runs, geometry = _fixture(tmp_path)
    with pytest.raises(ValueError, match="prefix"):
        check_prefix(dataset=dataset, runs=runs, geometry=geometry, prefix="ws4")
    with pytest.raises(ValueError, match="prefix"):
        check_prefix(dataset=dataset, runs=runs, geometry=geometry, prefix="/")


def test_main_writes_the_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI writes the report and exits zero on a clean prefix."""
    dataset, runs, geometry = _fixture(tmp_path)
    out = tmp_path / "proxy.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_map_proxy.py",
            "--dataset",
            str(dataset),
            "--runs",
            str(runs),
            "--geometry",
            str(geometry),
            "--prefix",
            "/ws4",
            "--out",
            str(out),
        ],
    )
    assert main() == 0
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is True
