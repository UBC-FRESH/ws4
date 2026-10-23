"""Clean-checkout contract: matrix build, patch-first offsets, period targets, web table.

The test is deliberately end-to-end. It starts from the tracked synthetic recipe, builds the
matrix, schedules same-year openings on the offset clock, simulates the run, and reads the target
table through the web API. No runtime artifact is required before the test starts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from ws4.build.compiler import build_canonical_dataset
from ws4.sim.engine import Simulator
from ws4.web.app import create_app

_FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_clean_checkout_builds_matrix_and_period_target_table(tmp_path: Path) -> None:
    """The tracked recipe builds, runs, and appears in the web target table by offset period."""
    dataset = build_canonical_dataset(
        _FIXTURE / "recipe.xml",
        _FIXTURE / "fragments.csv",
        tmp_path / "matrix",
    )
    schedule = tmp_path / "patch-first.csv"
    pd.DataFrame(
        [
            {"block_id": 1, "treatment": "CC", "offset": 0},
            {"block_id": 2, "treatment": "CC", "offset": 10},
        ]
    ).to_csv(schedule, index=False)
    run = tmp_path / "run"
    Simulator.from_dataset(dataset).run(schedule, years=20, out_dir=run)

    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n"
        "  - account: product.Volume\n"
        "    period: 1\n"
        "    period_width: 10\n"
        "    minimum: 350\n"
        "    maximum: 370\n"
        "  - account: product.Volume\n"
        "    period: 2\n"
        "    period_width: 10\n"
        "    minimum: 380\n"
        "    maximum: 400\n",
        encoding="utf-8",
    )
    geometry = tmp_path / "geometry.geojson"
    geometry.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"block_id": block},
                        "geometry": {"type": "Point", "coordinates": [float(block), 0.0]},
                    }
                    for block in (1, 2)
                ],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(
        create_app(
            dataset=dataset,
            runs=tmp_path,
            targets=targets,
            geometry=geometry,
        )
    )

    rows = client.get("/api/runs/run/targets").json()
    assert len(rows) == 2
    assert [row["period"] for row in rows] == [1, 2]
    assert [row["status"] for row in rows] == ["met", "met"]
    assert [row["value"] for row in rows] == pytest.approx([360.0, 390.0])
    assert all(row["year"] >= 0 for row in rows)

    periods = client.get("/api/runs/run/periods").json()
    assert periods["min"] == 0
    assert periods["period_width"] == 10
    assert [period["start"] for period in periods["periods"]] == [0, 10]
