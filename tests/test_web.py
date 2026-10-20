"""The optional HTTP service: every response is a file a run wrote.

The tests use FastAPI's own test client over a miniature dataset and run, so the service's contract
is exercised without a server. The map needs a geometry layer; without one it must refuse by naming
the missing artefact rather than return an empty map.
"""

from __future__ import annotations

import json
import subprocess
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
        "targets:\n"
        "  - account: feature.Volume\n    year: 0\n    minimum: 0\n"
        "  - account: product.Yield\n    year: 1\n    period_width: 2\n    minimum: 0\n",
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


def test_the_map_serves_simplified_block_polygons_and_compartments(tmp_path: Path) -> None:
    """A polygon layer keeps its geometry and source compartment; the cached base is not mutated."""
    client, _ = _app(tmp_path)
    geometry = tmp_path / "polygons.geojson"
    geometry.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "block_id": 1,
                            "compartment": "ACR",
                            "theme2": "Y7",
                            "theme5": "SEFA",
                            "strata": "0",
                            "lmu": "A",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[1, 0], [1.5, 0], [1.5, 0.5], [1, 0.5], [1, 0]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "block_id": 2,
                            "compartment": "HEC",
                            "theme2": "Y6",
                            "theme5": "SW",
                            "strata": "1",
                            "lmu": "B",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[2, 0], [2.5, 0], [2.5, 0.5], [2, 0.5], [2, 0]]],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    app = create_app(
        dataset=tmp_path / "dataset",
        runs=tmp_path / "runs",
        targets=tmp_path / "targets.yaml",
        geometry=geometry,
    )
    client = TestClient(app)
    treated = client.get("/api/runs/run1/map", params={"year": 0}).json()
    assert treated["features"][0]["geometry"]["type"] == "Polygon"
    assert treated["features"][0]["properties"]["compartment"] == "ACR"
    assert treated["features"][0]["properties"]["treated"] is True
    blocks = client.get("/api/runs/run1/map", params={"year": 0, "layer": "blocks"}).json()
    assert blocks["features"][0]["properties"]["treated"] is False
    assert blocks["features"][1]["properties"]["compartment"] == "HEC"
    layers = client.get("/api/runs/run1/layers").json()
    attributes = {item["name"]: item["values"] for item in layers["base_attributes"]}
    assert attributes["compartment"] == ["ACR", "HEC"]
    assert attributes["theme2"] == ["Y6", "Y7"]
    assert attributes["theme5"] == ["SEFA", "SW"]
    assert attributes["strata"] == ["0", "1"]
    assert attributes["lmu"] == ["A", "B"]


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
    assert client.get("/api/runs/run1/map", params={"layer": "raster"}).status_code == 422


def _patch_run(tmp_path: Path) -> Path:
    """Create a simulate-style run whose spatial artifact is patch membership, not a schedule."""
    run = tmp_path / "runs" / "run-patches"
    run.mkdir()
    (run / "account_values.csv").write_text(
        "year,account,value\n0,feature.Volume,1.0\n1,feature.Volume,2.0\n", encoding="utf-8"
    )
    (run / "patch_membership.csv").write_text(
        "period,year,account,class,patch,block,area_ha\n"
        "1,1,patch.harvested,0_10,0,1,5.0\n"
        "1,1,patch.harvested,10_50,1,2,20.0\n"
        "2,2,patch.harvested,0_10,0,2,6.0\n",
        encoding="utf-8",
    )
    return run


def test_periods_fall_back_to_patch_membership_or_accounts(tmp_path: Path) -> None:
    """A run with no schedule still has a real period range for the map control."""
    client, _ = _app(tmp_path)
    _patch_run(tmp_path)
    assert client.get("/api/runs/run-patches/periods").json() == {
        "min": 1,
        "max": 2,
        "values": [1, 2],
    }


def test_the_layers_endpoint_names_what_the_run_can_draw(tmp_path: Path) -> None:
    """Availability and patch classes come from the run's own files."""
    client, _ = _app(tmp_path)
    _patch_run(tmp_path)
    scheduled = client.get("/api/runs/run1/layers").json()
    assert scheduled["treatments"] is True
    assert scheduled["cumulative"] is True
    assert scheduled["patches"] is False
    assert scheduled["patch_classes"] == []
    assert scheduled["base_attributes"] == []
    patches = client.get("/api/runs/run-patches/layers").json()
    assert patches["treatments"] is False
    assert patches["patches"] is True
    assert patches["patch_classes"] == ["0_10", "10_50"]
    assert patches["compartments"] is False
    assert patches["patch_accounts"] == ["patch.harvested"]
    assert patches["roads"] is False


def test_the_cumulative_layer_marks_current_and_earlier_treatments(tmp_path: Path) -> None:
    """Cumulative is the schedule up to the year, with the current period distinguished."""
    client, _ = _app(tmp_path)
    body = client.get("/api/runs/run1/map", params={"year": 1, "layer": "cumulative"}).json()
    first, second = body["features"]
    assert first["properties"]["treated"] is True
    assert first["properties"]["current"] is False
    assert first["properties"]["treatments"] == ["CC"]
    assert second["properties"]["current"] is True
    assert second["properties"]["treatments"] == ["CT"]


def test_the_patch_layer_joins_membership_to_the_geometry(tmp_path: Path) -> None:
    """The patch layer carries the class, patch id and area for the selected year."""
    client, _ = _app(tmp_path)
    _patch_run(tmp_path)
    body = client.get("/api/runs/run-patches/map", params={"year": 1, "layer": "patches"}).json()
    assert body["patch_classes"] == ["0_10", "10_50"]
    first, second = body["features"]
    assert first["properties"]["treated"] is True
    assert first["properties"]["patch"] == 0
    assert first["properties"]["patch_class"] == "0_10"
    assert first["properties"]["patch_area_ha"] == 5.0
    assert first["properties"]["patch_account"] == "patch.harvested"
    assert second["properties"]["patch_class"] == "10_50"
    later = client.get("/api/runs/run-patches/map", params={"year": 2, "layer": "patches"}).json()
    assert later["features"][0]["properties"]["treated"] is False
    assert later["features"][1]["properties"]["patch"] == 0


def test_the_map_refuses_the_patch_layer_without_membership(tmp_path: Path) -> None:
    """A scheduled run without patch membership names the missing file."""
    client, _ = _app(tmp_path)
    response = client.get("/api/runs/run1/map", params={"year": 0, "layer": "patches"})
    assert response.status_code == 404
    assert "patch_membership.csv" in response.json()["detail"]


def test_inactive_targets_are_kept_in_the_json_and_reported(tmp_path: Path) -> None:
    """The editor can round-trip an inactive target; the run reports it as inactive."""
    client, targets = _app(tmp_path)
    targets.write_text(
        "targets:\n  - account: feature.Volume\n    year: 0\n    minimum: 100\n    active: false\n",
        encoding="utf-8",
    )
    rows = client.get("/api/targets.json").json()
    assert rows[0]["active"] is False
    realized = client.get("/api/runs/run1/targets").json()
    assert realized[0]["active"] is False
    assert realized[0]["status"] == "inactive"


def test_the_model_spread_compartments_layer(tmp_path: Path) -> None:
    """A run's spread membership is served as a layer, with treated breaks marked separately."""
    client, _ = _app(tmp_path)
    run = tmp_path / "runs" / "run1"
    (run / "spread_membership.csv").write_text(
        "year,account,compartment,compartment_class,block,area_ha,compartment_area_ha\n"
        "1,spread.fire,0,10_50,1,5.0,20.0\n",
        encoding="utf-8",
    )
    layers = client.get("/api/runs/run1/layers").json()
    assert layers["compartments"] is True
    assert layers["compartment_accounts"] == ["spread.fire"]
    assert layers["compartment_classes"] == ["10_50"]
    body = client.get("/api/runs/run1/map", params={"year": 1, "layer": "compartments"}).json()
    assert body["account"] == "spread.fire"
    first, second = body["features"]
    assert first["properties"]["treated"] is False
    assert first["properties"]["compartment"] == 0
    assert first["properties"]["compartment_class"] == "10_50"
    # block 2 is treated in period 1, so it is a break rather than a compartment member
    assert second["properties"]["treated"] is True
    assert second["properties"]["compartment"] is None
    assert (
        client.get("/api/runs/run2/map", params={"year": 1, "layer": "compartments"}).status_code
        == 404
    )


def test_a_source_road_layer_is_served_for_the_overlay(tmp_path: Path) -> None:
    """The optional access-road lines are a separate, run-independent GeoJSON layer."""
    _app(tmp_path)
    roads = tmp_path / "roads.geojson"
    roads.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"access_id": 7, "road_type": "T", "length_m": 120.0},
                        "geometry": {"type": "LineString", "coordinates": [[1, 0], [2, 0]]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(
        create_app(
            dataset=tmp_path / "dataset",
            runs=tmp_path / "runs",
            targets=tmp_path / "targets.yaml",
            geometry=tmp_path / "geometry.geojson",
            roads=roads,
        )
    )
    layers = client.get("/api/runs/run1/layers").json()
    assert layers["roads"] is True
    assert layers["roads_reason"] == ""
    body = client.get("/api/roads").json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["geometry"]["type"] == "LineString"
    assert body["features"][0]["properties"]["road_type"] == "T"

    plain = tmp_path / "plain"
    plain.mkdir()
    without, _ = _app(plain)
    assert without.get("/api/roads").status_code == 404
    assert without.get("/api/runs/run1/layers").json()["roads"] is False


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


def _runs_client(tmp_path: Path) -> TestClient:
    """Build the fixture with search-starting enabled."""
    _app(tmp_path)
    return TestClient(
        create_app(
            dataset=tmp_path / "dataset",
            runs=tmp_path / "runs",
            targets=tmp_path / "targets.yaml",
            allow_runs=True,
        )
    )


def test_starting_a_run_bounds_the_island_count(tmp_path: Path) -> None:
    """An island count outside one to sixty-four is refused before any process starts."""
    client = _runs_client(tmp_path)
    assert client.post("/api/runs", json={"iterations": 1, "islands": 0}).status_code == 422
    assert client.post("/api/runs", json={"iterations": 1, "islands": 65}).status_code == 422


def test_starting_a_run_passes_the_island_count_to_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The service turns ``islands`` into parallel starts and one BLAS thread per worker."""
    client = _runs_client(tmp_path)
    captured: dict[str, object] = {}

    class FakePopen:
        pid = 123

        def poll(self) -> int | None:
            return None

    def fake_popen(command: list[str], stdout: object = None, stderr: object = None) -> FakePopen:
        captured["command"] = command
        return FakePopen()

    monkeypatch.setattr("ws4.web.app.subprocess.Popen", fake_popen)
    response = client.post("/api/runs", json={"iterations": 1, "islands": 4})
    assert response.status_code == 200
    assert response.json()["islands"] == 4
    command = captured["command"]
    assert isinstance(command, list)
    assert command[command.index("--starts") + 1] == "4"
    assert command[command.index("--threads") + 1] == "4"


def test_starting_a_run_passes_the_spatial_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Topology and patch accounts reach the CLI, which is what makes patch membership."""
    _app(tmp_path)
    topology = tmp_path / "topology.csv"
    topology.write_text("src,dst,length\n1,2,10\n", encoding="utf-8")
    patches_path = tmp_path / "patches.yaml"
    patches_path.write_text("accounts: []\n", encoding="utf-8")
    client = TestClient(
        create_app(
            dataset=tmp_path / "dataset",
            runs=tmp_path / "runs",
            targets=tmp_path / "targets.yaml",
            allow_runs=True,
            topology=topology,
            patch_accounts=patches_path,
        )
    )
    captured: dict[str, object] = {}

    class FakePopen:
        pid = 123

        def poll(self) -> int | None:
            return None

    def fake_popen(command: list[str], stdout: object = None, stderr: object = None) -> FakePopen:
        captured["command"] = command
        return FakePopen()

    monkeypatch.setattr("ws4.web.app.subprocess.Popen", fake_popen)
    response = client.post("/api/runs", json={"iterations": 1})
    assert response.status_code == 200
    command = captured["command"]
    assert isinstance(command, list)
    assert command[command.index("--topology") + 1] == str(topology)
    assert command[command.index("--patch-accounts") + 1] == str(patches_path)


def test_a_finished_run_closes_the_event_stream(tmp_path: Path) -> None:
    """A completed run returns 204, which tells EventSource to stop reconnecting."""
    client, _ = _app(tmp_path)
    response = client.get("/api/runs/run1/events")
    assert response.status_code == 204
    assert response.content == b""


def test_a_live_run_streams_the_best_island_and_its_schedule(tmp_path: Path) -> None:
    """The stream follows the lowest objective, counts every island's steps, and resets the map."""
    client, _ = _app(tmp_path)
    run = tmp_path / "runs" / "run2"
    records = [
        {"type": "step", "island": "start-0", "iteration": 10, "objective": 10.0},
        {"type": "schedule", "island": "start-0", "iteration": 10, "changed": [[1, [["CC", 0]]]]},
        {"type": "step", "island": "start-1", "iteration": 9, "objective": 5.0},
        {"type": "schedule", "island": "start-1", "iteration": 9, "changed": [[2, [["CT", 0]]]]},
        {
            "type": "targets",
            "island": "start-1",
            "iteration": 9,
            "values": [{"year": 0, "account": "feature.Volume", "value": 11.0}],
        },
        {"type": "step", "island": "start-0", "iteration": 20, "objective": 7.0},
        {"type": "schedule", "island": "start-0", "iteration": 20, "changed": [[3, [["CC", 0]]]]},
    ]
    for island, start_index, end_index in (("start-0", 0, 3), ("start-1", 3, 6)):
        (run / f"telemetry-{island}.jsonl").write_text(
            "\n".join(json.dumps(record) for record in records[start_index:end_index]) + "\n",
            encoding="utf-8",
        )
    body = client.get("/api/runs/run2/events").text
    assert "event: progress" in body
    assert '"total": 3' in body
    assert "event: schedule" in body
    assert '"reset": true' in body
    # the best island is start-1, so its block is the one in the reset map
    assert '"island": "start-1"' in body
    assert '[[2,[["CT",0]]]]' in body.replace(" ", "")
    assert "event: targets" in body
    assert '"series"' in body
    assert "event: error" in body


def test_status_reports_the_best_step_across_islands(tmp_path: Path) -> None:
    """A parallel run's status is the lowest objective, not whichever worker wrote last."""
    client, _ = _app(tmp_path)
    run = tmp_path / "runs" / "run2"
    (run / "telemetry.jsonl").write_text(
        '{"type": "step", "island": "start-0", "iteration": 10, "objective": 9.0}\n'
        '{"type": "step", "island": "start-1", "iteration": 8, "objective": 4.0}\n'
        '{"type": "step", "island": "start-0", "iteration": 20, "objective": 6.0}\n',
        encoding="utf-8",
    )
    step = client.get("/api/runs/run2/status").json()["last_step"]
    assert step["objective"] == 4.0
    assert step["island"] == "start-1"


def test_the_status_endpoint_reports_a_finished_run(tmp_path: Path) -> None:
    """A run with account values is done; a bare directory has no status to claim."""
    client, _ = _app(tmp_path)
    status = client.get("/api/runs/run1/status").json()
    assert status["status"] == "done"
    assert status["running"] is False
    assert status["summary"]["status"] == "ok"


def _chat_client(tmp_path: Path) -> TestClient:
    """Build the same fixture with the optional agent enabled."""
    _app(tmp_path)
    return TestClient(
        create_app(
            dataset=tmp_path / "dataset",
            runs=tmp_path / "runs",
            targets=tmp_path / "targets.yaml",
            geometry=tmp_path / "geometry.geojson",
            allow_agent=True,
            agent_model="test/chat-model",
            agent_cwd=tmp_path,
            agent_timeout=5.0,
        )
    )


def test_the_chat_agent_is_disabled_by_default(tmp_path: Path) -> None:
    """Embedding a shell-capable agent is an explicit opt-in, and the refusal names the flag."""
    client, _ = _app(tmp_path)
    info = client.get("/api/agent").json()
    assert info["enabled"] is False
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 403
    assert "--allow-agent" in response.json()["detail"]


def test_the_chat_agent_validates_its_inputs(tmp_path: Path) -> None:
    """An empty message and a malformed session are refused before a process is spawned."""
    client = _chat_client(tmp_path)
    assert client.post("/api/chat", json={"message": "  "}).status_code == 422
    bad = client.post("/api/chat", json={"message": "hi", "session": "not-a-session"})
    assert bad.status_code == 422
    assert "ses" in bad.json()["detail"]


def test_the_chat_agent_returns_text_tools_and_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The endpoint parses the CLI's JSON events and continues the same session next turn."""
    client = _chat_client(tmp_path)
    captured: dict[str, object] = {}
    stdout = "\n".join(
        [
            json.dumps(
                {
                    "type": "tool_use",
                    "sessionID": "ses_test",
                    "part": {
                        "tool": "shell",
                        "state": {"input": {"command": "ls ws4"}, "title": "shell"},
                    },
                }
            ),
            json.dumps(
                {
                    "type": "text",
                    "sessionID": "ses_test",
                    "part": {"text": "**hello** from ws4"},
                }
            ),
        ]
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr("ws4.web.app.shutil.which", lambda name: "/usr/bin/opencode")
    monkeypatch.setattr("ws4.web.app.subprocess.run", fake_run)
    response = client.post("/api/chat", json={"message": "hi", "run": "run1", "year": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "**hello** from ws4"
    assert body["session"] == "ses_test"
    assert body["actions"] == [{"tool": "shell", "summary": "ls ws4"}]
    command = captured["command"]
    assert isinstance(command, list)
    assert "--model" in command
    assert "test/chat-model" in command
    assert "--auto" in command
    assert "--session" not in command
    assert "run1" in command[-1]
    assert "The year open in the UI is 3." in command[-1]
    assert "User: hi" in command[-1]
    assert captured["cwd"] == str(tmp_path)

    response = client.post("/api/chat", json={"message": "again", "session": "ses_test"})
    assert response.status_code == 200
    command = captured["command"]
    assert isinstance(command, list)
    assert "--session" in command
    assert "ses_test" in command


def test_the_chat_agent_reports_a_missing_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A service without the CLI says so instead of crashing on a file-not-found error."""
    client = _chat_client(tmp_path)
    monkeypatch.setattr("ws4.web.app.shutil.which", lambda name: None)
    response = client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 503
    assert "PATH" in response.json()["detail"]


def test_the_agent_info_names_the_configured_model(tmp_path: Path) -> None:
    """The panel can show the actual model and working directory rather than guessing."""
    client = _chat_client(tmp_path)
    info = client.get("/api/agent").json()
    assert info["enabled"] is True
    assert info["model"] == "test/chat-model"
    assert info["cwd"] == str(tmp_path)


def test_targets_are_also_saveable_with_post(tmp_path: Path) -> None:
    """The proxy-facing alias: POST saves the same document as PUT."""
    client, _ = _app(tmp_path)
    rows = client.get("/api/targets.json").json()
    rows[0]["maximum"] = 321.0
    assert client.post("/api/targets.json", json=rows).status_code == 200
    assert client.get("/api/targets.json").json()[0]["maximum"] == 321.0


def test_the_realized_target_value_uses_the_targets_period(tmp_path: Path) -> None:
    """A product sums its period; a feature reads its end year, as the optimizer does."""
    client, _ = _app(tmp_path)
    rows = client.get("/api/runs/run1/targets").json()
    by_account = {row["account"]: row for row in rows}
    assert by_account["feature.Volume"]["value"] == 10.0
    assert by_account["feature.Volume"]["status"] == "met"
    assert by_account["product.Yield"]["value"] == 5.0


def test_a_run_can_be_paused_resumed_and_stopped(tmp_path: Path) -> None:
    """The control endpoint writes the file the solver polls, and status reports the pause."""
    client, _ = _app(tmp_path)
    run = tmp_path / "runs" / "run1"
    paused = client.post("/api/runs/run1/control", json={"action": "pause"})
    assert paused.status_code == 200
    assert json.loads((run / "control.json").read_text(encoding="utf-8")) == {"action": "pause"}
    assert client.get("/api/runs/run1/status").json()["paused"] is True
    client.post("/api/runs/run1/control", json={"action": "run"})
    assert client.get("/api/runs/run1/status").json()["paused"] is False
    assert client.post("/api/runs/run1/control", json={"action": "explode"}).status_code == 422


def test_an_unknown_run_is_a_named_404(tmp_path: Path) -> None:
    """A missing run is a 404 that names it."""
    client, _ = _app(tmp_path)
    response = client.get("/api/runs/nope/summary")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]
