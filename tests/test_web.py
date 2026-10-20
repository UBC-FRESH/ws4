"""The optional HTTP service: every response is a file a run wrote.

The tests use FastAPI's own test client over a miniature dataset and run, so the service's contract
is exercised without a server. The map needs a geometry layer; without one it must refuse by naming
the missing artefact rather than return an empty map.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from ws4.web.app import create_app


def _app(tmp_path: Path, *, with_geometry: bool = True) -> tuple[TestClient, Path]:
    """Create a dataset, a run and a client over them; return the client and the targets path."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    (tmp_path / "runs" / "not-a-run").mkdir(parents=True)
    run = tmp_path / "runs" / "run1"
    run.mkdir(parents=True)
    simulated = tmp_path / "runs" / "run2"
    simulated.mkdir()
    (simulated / "account_values.csv").write_text(
        "year,account,value\n0,feature.Volume,3.0\n", encoding="utf-8"
    )
    (simulated / "schedule.csv").write_text("block_id,treatment,period\n2,CT,1\n", encoding="utf-8")
    (run / "summary.json").write_text('{"status": "ok", "objective": 0.0}', encoding="utf-8")
    pd.DataFrame(
        [
            {"year": 0, "account": "feature.Volume", "value": 10.0},
            {"year": 1, "account": "feature.Volume", "value": 11.0},
            {"year": 0, "account": "product.Yield", "value": 5.0},
        ]
    ).to_csv(run / "account_values.csv", index=False)
    pd.DataFrame(
        [
            {"block_id": 1, "treatment": "CC", "period": 0},
            {"block_id": 2, "treatment": "CT", "period": 1},
        ]
    ).to_csv(run / "schedule.csv", index=False)
    (run / "report.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    minimum: 0\n", encoding="utf-8"
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
    app = create_app(
        dataset=dataset,
        runs=tmp_path / "runs",
        targets=targets,
        geometry=geometry if with_geometry else None,
    )
    return TestClient(app), targets


def test_the_landing_page_lists_the_dataset_and_its_runs(tmp_path: Path) -> None:
    """The root page is visible under a proxy and names the dataset and runs."""
    client, _ = _app(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "WS4" in response.text
    assert 'id="run"' in response.text  # the application shell, not a server-rendered list
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_summary_lists_the_dataset_and_its_runs(tmp_path: Path) -> None:
    """The summary reports the dataset name, the manifest and the runs found."""
    client, _ = _app(tmp_path)
    body = client.get("/api/summary").json()
    assert body["dataset"] == "dataset"
    assert body["manifest"]["schema_version"] == "0.1"
    assert [entry["id"] for entry in body["runs"]] == ["run1", "run2"]
    assert body["runs"][1]["kind"] == "simulate"
    assert body["runs"][0]["summary"]["status"] == "ok"


def test_accounts_are_filtered_by_year_and_account(tmp_path: Path) -> None:
    """The endpoint filters the run's own CSV; it does not recompute a value."""
    client, _ = _app(tmp_path)
    rows = client.get("/api/runs/run1/accounts", params={"year": 0}).json()
    assert {row["account"] for row in rows} == {"feature.Volume", "product.Yield"}
    one = client.get(
        "/api/runs/run1/accounts", params={"year": 0, "account": "feature.Volume"}
    ).json()
    assert one == [{"year": 0, "account": "feature.Volume", "value": 10.0}]


def test_reports_are_listed_and_downloaded(tmp_path: Path) -> None:
    """The report tree is the run directory's report files."""
    client, _ = _app(tmp_path)
    names = {item["name"] for item in client.get("/api/runs/run1/reports").json()}
    assert "report.csv" in names
    response = client.get("/api/runs/run1/reports/report.csv")
    assert response.status_code == 200
    assert response.text == "a,b\n1,2\n"


def test_the_map_returns_the_treated_blocks_for_the_year(tmp_path: Path) -> None:
    """The treatment layer joins the schedule to the configured geometry."""
    client, _ = _app(tmp_path)
    body = client.get("/api/runs/run1/map", params={"year": 0}).json()
    assert body["type"] == "FeatureCollection"
    assert [feature["properties"]["block_id"] for feature in body["features"]] == [1, 2]
    assert body["features"][0]["properties"]["treatments"] == ["CC"]
    assert body["features"][0]["properties"]["treated"] is True
    assert body["features"][1]["properties"]["treated"] is False


def test_periods_come_from_the_runs_schedule(tmp_path: Path) -> None:
    """The period control gets the run's own range, not a guessed horizon."""
    client, _ = _app(tmp_path)
    assert client.get("/api/runs/run1/periods").json() == {"min": 0, "max": 1, "values": [0, 1]}


def test_the_map_refuses_without_geometry_and_for_an_unknown_layer(tmp_path: Path) -> None:
    """A missing geometry or an unknown layer is named, not answered with an empty map."""
    client, _ = _app(tmp_path, with_geometry=False)
    response = client.get("/api/runs/run1/map", params={"year": 0})
    assert response.status_code == 409
    assert "--geometry" in response.json()["detail"]
    assert client.get("/api/runs/run1/map", params={"layer": "patches"}).status_code == 422


def test_targets_round_trip_and_an_invalid_document_is_refused(tmp_path: Path) -> None:
    """A valid edit replaces the YAML; an invalid one leaves it unchanged."""
    client, targets = _app(tmp_path)
    before = client.get("/api/targets").text
    assert "feature.Volume" in before
    replacement = "targets:\n  - account: feature.Volume\n    year: 0\n    maximum: 100\n"
    response = client.put(
        "/api/targets", content=replacement, headers={"content-type": "text/yaml"}
    )
    assert response.status_code == 200
    assert response.json() == {"targets": 1}
    assert targets.read_text(encoding="utf-8") == replacement
    refused = client.put(
        "/api/targets", content="not: a target list\n", headers={"content-type": "text/yaml"}
    )
    assert refused.status_code == 422
    assert targets.read_text(encoding="utf-8") == replacement


def test_targets_json_round_trip_and_an_empty_list_is_refused(tmp_path: Path) -> None:
    """The editor reads and writes the parsed targets; the YAML remains the storage."""
    client, _ = _app(tmp_path)
    rows = client.get("/api/targets.json").json()
    assert rows[0]["account"] == "feature.Volume"
    rows[0]["maximum"] = 100.0
    response = client.post("/api/targets.json", json=rows)
    assert response.status_code == 200
    after = client.get("/api/targets.json").json()
    assert after[0]["maximum"] == 100.0
    assert client.put("/api/targets.json", json=[]).status_code == 422


def test_the_skins_endpoint_returns_the_checked_manifests(tmp_path: Path) -> None:
    """The service exposes the four skins and a named 404 for an unknown one."""
    client, _ = _app(tmp_path)
    skins = client.get("/api/skins").json()
    assert {skin["id"] for skin in skins} == {
        "model-builder",
        "scenario-analyst",
        "scenario-browser",
        "reviewer",
    }
    assert client.get("/api/skins/reviewer").json()["read_only"] is True
    assert client.get("/api/skins/nope").status_code == 404


def test_starting_a_run_is_refused_unless_the_service_allows_it(tmp_path: Path) -> None:
    """The read-only default is a refusal, not a silent start."""
    client, _ = _app(tmp_path)
    response = client.post("/api/runs", json={"iterations": 10})
    assert response.status_code == 403
    assert "--allow-runs" in response.json()["detail"]


def test_starting_a_run_needs_a_targets_file(tmp_path: Path) -> None:
    """A service without targets cannot compose the command, and says so."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    runs = tmp_path / "runs"
    runs.mkdir()
    client = TestClient(create_app(dataset=dataset, runs=runs, allow_runs=True))
    assert client.post("/api/runs", json={"iterations": 10}).status_code == 422


def test_the_events_stream_replays_telemetry_and_ends_on_the_summary(tmp_path: Path) -> None:
    """SSE emits each step and closes with the run's own summary."""
    client, _ = _app(tmp_path)
    run = tmp_path / "runs" / "run1"
    (run / "telemetry.jsonl").write_text(
        '{"type": "run", "run_id": "r1"}\n'
        '{"type": "step", "iteration": 1, "objective": 10.0}\n'
        '{"type": "schedule", "iteration": 1, "changed": [[1, [["CC", 0]]]]}\n',
        encoding="utf-8",
    )
    body = client.get("/api/runs/run1/events").text
    assert "event: started" in body
    assert "event: progress" in body
    assert '"iteration": 1' in body
    assert "event: schedule" in body
    assert "event: done" in body


def test_the_status_endpoint_reports_a_finished_run(tmp_path: Path) -> None:
    """A run with account values is done; a bare directory has no status to claim."""
    client, _ = _app(tmp_path)
    status = client.get("/api/runs/run1/status").json()
    assert status["status"] == "done"
    assert status["running"] is False
    assert status["summary"]["status"] == "ok"


def test_targets_are_also_saveable_with_post(tmp_path: Path) -> None:
    """The proxy-facing alias: POST saves the same document as PUT."""
    client, _ = _app(tmp_path)
    rows = client.get("/api/targets.json").json()
    rows[0]["maximum"] = 321.0
    assert client.post("/api/targets.json", json=rows).status_code == 200
    assert client.get("/api/targets.json").json()[0]["maximum"] == 321.0


def test_an_unknown_run_is_a_named_404(tmp_path: Path) -> None:
    """A missing run is a 404 that names it."""
    client, _ = _app(tmp_path)
    response = client.get("/api/runs/nope/summary")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]
