"""Contract tests for the SDMD read and constraint API."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ws4.sdmd.api import SdmdApiError, SdmdStore, create_sdmd_router

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sdmd"
DIAGRAM = (
    Path(__file__).resolve().parents[1]
    / "ws4"
    / "sdmd"
    / "data"
    / "sdmd"
    / "idf-dk3-fdi-illustrative.json"
)
AU = "AU-IDFdk3-FDI"


def _store_dir(tmp_path: Path) -> Path:
    """Build a store directory from the fixture and the diagram.

    Parameters
    ----------
    tmp_path : Path
        The pytest temporary directory.

    Returns
    -------
    Path
        The populated store directory.
    """
    root = tmp_path / "sdmd"
    shutil.copytree(FIXTURE, root)
    shutil.copy(DIAGRAM, root / "diagram.json")
    trajectory = root / "trajectories" / AU / "REG-A-CT60.json"
    trajectory.parent.mkdir(parents=True)
    trajectory.write_text(
        json.dumps({"points": [[2400.0, 0.214], [1700.0, 0.543]]}) + "\n",
        encoding="utf-8",
    )
    return root


def _store(tmp_path: Path) -> SdmdStore:
    """Load a store from a fresh fixture directory."""
    return SdmdStore.from_directory(_store_dir(tmp_path))


def _client(store: SdmdStore) -> TestClient:
    """Create a test client over the SDMD router."""
    app = FastAPI()
    app.include_router(create_sdmd_router(store))
    return TestClient(app)


def _payload(store: SdmdStore, au_id: str = AU) -> dict[str, object]:
    """Build a complete constraint payload from the store."""
    return {"constraints": [asdict(item) for item in store.constraints_for(au_id)]}


def test_store_loads_the_fixture(tmp_path: Path) -> None:
    """The six tables, the diagram, and the saved trajectory load cleanly."""
    store = _store(tmp_path)
    assert store.regions() == ["Interior"]
    assert len(store.regimes) == 13
    assert store.diagram is not None
    assert store.diagram.diagram_id == "idf-dk3-fdi-illustrative"


def test_regions_and_aus(tmp_path: Path) -> None:
    """The read summaries describe both AUs."""
    client = _client(_store(tmp_path))
    regions = client.get("/api/sdmd/regions")
    assert regions.status_code == 200
    assert regions.json()["regions"] == ["Interior"]
    aus = client.get("/api/sdmd/aus", params={"region": "Interior"})
    assert aus.status_code == 200
    payload = aus.json()["aus"]
    assert {item["au_id"] for item in payload} == {AU, "AU-IDFdk3-PLI"}
    first = next(item for item in payload if item["au_id"] == AU)
    assert first["plot_count"] == 5
    assert first["age_min"] == 40
    assert first["leading_species"] == ["FDI"]


def test_unknown_au_is_404(tmp_path: Path) -> None:
    """An unknown AU is named, not returned empty."""
    client = _client(_store(tmp_path))
    response = client.get("/api/sdmd/au/AU-MISSING")
    assert response.status_code == 404
    assert "AU-MISSING" in response.json()["detail"]


def test_au_detail_reports_the_diagram_and_gaps(tmp_path: Path) -> None:
    """The AU detail names the diagram state and the data gaps."""
    client = _client(_store(tmp_path))
    payload = client.get(f"/api/sdmd/au/{AU}").json()
    assert payload["diagram"]["review_status"] == "provisional"
    assert "diagram review status is provisional" in payload["data_gaps"]
    assert payload["constraint_count"] == 7


def test_plots_join_stands(tmp_path: Path) -> None:
    """Plot rows carry their stand summary."""
    client = _client(_store(tmp_path))
    payload = client.get(f"/api/sdmd/au/{AU}/plots").json()["plots"]
    assert len(payload) == 5
    assert {"plot_id", "age", "tph", "volume_m3_ha"} <= set(payload[0])


def test_yield_curve_is_sorted_by_age(tmp_path: Path) -> None:
    """The yield payload is the stand summary in age order."""
    client = _client(_store(tmp_path))
    payload = client.get(f"/api/sdmd/au/{AU}/yield").json()["yield"]
    assert [row["age"] for row in payload] == [40, 60, 80, 100, 120]
    assert all(row["volume_m3_ha"] > 0 for row in payload)


def test_sdmd_points_carry_a_placement(tmp_path: Path) -> None:
    """Each point is placed on the diagram and the envelope is returned."""
    client = _client(_store(tmp_path))
    payload = client.get(f"/api/sdmd/au/{AU}/sdmd").json()
    assert len(payload["points"]) == 5
    assert payload["points"][0]["placement"]["zone"] in {
        "understocked",
        "density-management",
        "competition",
        "outside",
    }
    assert len(payload["envelope"]) >= 3
    assert len(payload["diagram"]["isopleths"]) == 13


def test_regimes_include_constraint_findings(tmp_path: Path) -> None:
    """The selection regime is present but flagged outside the diagram."""
    client = _client(_store(tmp_path))
    payload = client.get(f"/api/sdmd/au/{AU}/regimes").json()["regimes"]
    assert len(payload) == 7
    selection = next(item for item in payload if item["regime_id"] == "REG-A-SELECTION80")
    assert selection["allowed"] is False
    assert "SDMD-REGIME-OUTSIDE-SDMD" in {finding["code"] for finding in selection["findings"]}


def test_constraint_preview_counts(tmp_path: Path) -> None:
    """The preview reports the reduction from the stored constraints."""
    client = _client(_store(tmp_path))
    payload = client.get(f"/api/sdmd/au/{AU}/constraint-preview").json()
    assert payload["counts"] == {
        "regimes_before": 7,
        "regimes_after": 6,
        "entries_before": 11,
        "entries_after": 7,
    }
    assert any(item["regime_id"] == "REG-A-SELECTION80" for item in payload["dropped"])


def test_trajectory_is_assessed_against_the_envelope(tmp_path: Path) -> None:
    """A stored trajectory is assessed; a missing one is reported."""
    client = _client(_store(tmp_path))
    inside = client.get(f"/api/sdmd/au/{AU}/trajectory", params={"regime_id": "REG-A-CT60"})
    assert inside.status_code == 200
    assert inside.json()["status"] == "inside"
    missing = client.get(f"/api/sdmd/au/{AU}/trajectory", params={"regime_id": "REG-A-FUEL50"})
    assert missing.json()["status"] == "unavailable"
    unknown = client.get(f"/api/sdmd/au/{AU}/trajectory", params={"regime_id": "REG-MISSING"})
    assert unknown.status_code == 404


def test_save_constraints_persists_and_previews(tmp_path: Path) -> None:
    """A valid write updates the store and survives a reload."""
    root = _store_dir(tmp_path)
    store = SdmdStore.from_directory(root)
    client = _client(store)
    payload = _payload(store)
    items = payload["constraints"]
    assert isinstance(items, list)
    for item in items:
        if item["regime_id"] in {"REG-A-FUEL50", "REG-A-SELECTION80"}:
            item["allowed"] = False
    response = client.post(f"/api/sdmd/au/{AU}/constraints", json=payload)
    assert response.status_code == 200
    assert response.json()["preview"]["counts"]["regimes_after"] == 5
    assert (root / "constraints" / f"{AU}.json").is_file()

    reloaded = SdmdStore.from_directory(root)
    counts = reloaded.preview(AU)["counts"]
    assert isinstance(counts, dict)
    assert counts["regimes_after"] == 5


def test_save_constraints_is_validated(tmp_path: Path) -> None:
    """Malformed, incomplete, mistyped, and failing sets are refused."""
    root = _store_dir(tmp_path)
    store = SdmdStore.from_directory(root)
    client = _client(store)

    incomplete = _payload(store)
    items = incomplete["constraints"]
    assert isinstance(items, list)
    items.pop()
    assert client.post(f"/api/sdmd/au/{AU}/constraints", json=incomplete).status_code == 422

    unknown = _payload(store)
    items = unknown["constraints"]
    assert isinstance(items, list)
    items[0]["regime_id"] = "REG-MISSING"
    assert client.post(f"/api/sdmd/au/{AU}/constraints", json=unknown).status_code == 422

    inverted = _payload(store)
    items = inverted["constraints"]
    assert isinstance(items, list)
    items[0]["min_entry_age"] = 200
    assert client.post(f"/api/sdmd/au/{AU}/constraints", json=inverted).status_code == 422

    mismatched = _payload(store)
    items = mismatched["constraints"]
    assert isinstance(items, list)
    items[0]["au_id"] = "AU-OTHER"
    assert client.post(f"/api/sdmd/au/{AU}/constraints", json=mismatched).status_code == 422

    failing = _payload(store)
    items = failing["constraints"]
    assert isinstance(items, list)
    for item in items:
        if item["regime_id"] == "REG-A-CT60":
            item["max_removal_fraction"] = 0.1
    assert client.post(f"/api/sdmd/au/{AU}/constraints", json=failing).status_code == 422
    assert (
        client.get(f"/api/sdmd/au/{AU}/constraint-preview").json()["counts"]["regimes_after"] == 6
    )


def test_post_unknown_au_is_404(tmp_path: Path) -> None:
    """A write to an unknown AU is a not-found error."""
    client = _client(_store(tmp_path))
    assert client.post("/api/sdmd/au/AU-MISSING/constraints", json={}).status_code == 404


def test_create_app_mounts_the_router(tmp_path: Path) -> None:
    """The main web app exposes the SDMD router when given a directory."""
    from ws4.web.app import create_app

    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "manifest.json").write_text('{"schema_version": "0.1"}', encoding="utf-8")
    runs = tmp_path / "runs"
    runs.mkdir()
    app = create_app(dataset=dataset, runs=runs, sdmd_dir=_store_dir(tmp_path))
    client = TestClient(app)
    assert client.get("/api/sdmd/regions").status_code == 200


def test_store_reads_a_measured_initial_volume(tmp_path: Path) -> None:
    """The optional initial_volume.json is exposed on the AU payload."""
    root = _store_dir(tmp_path)
    (root / "initial_volume.json").write_text(
        '{"schema_version": "ws4.sdmd.initial-volume.v1", "au_id": "AU-IDFdk3-FDI", '
        '"initial_volume_m3_ha": 500.0, "limit_m3_ha": 800.0, '
        '"source": "test", "review_status": "reviewed"}\n',
        encoding="utf-8",
    )
    store = SdmdStore.from_directory(root)
    payload = store.au("AU-IDFdk3-FDI")
    assert payload["initial_volume"] == {
        "schema_version": "ws4.sdmd.initial-volume.v1",
        "au_id": "AU-IDFdk3-FDI",
        "initial_volume_m3_ha": 500.0,
        "limit_m3_ha": 800.0,
        "source": "test",
        "review_status": "reviewed",
    }


def test_store_refuses_an_initial_volume_above_its_limit(tmp_path: Path) -> None:
    """A volume above its own evidence limit is refused at load time."""
    root = _store_dir(tmp_path)
    (root / "initial_volume.json").write_text(
        '{"au_id": "AU-IDFdk3-FDI", "initial_volume_m3_ha": 900.0, '
        '"limit_m3_ha": 800.0, "source": "test", "review_status": "reviewed"}\n',
        encoding="utf-8",
    )
    with pytest.raises(SdmdApiError, match="at most the limit"):
        SdmdStore.from_directory(root)


def test_store_refuses_an_au_without_tsa_bec_support(tmp_path: Path) -> None:
    """An AU label with an impossible TSA/BEC pair fails at store load."""
    root = _store_dir(tmp_path)
    frame = pd.read_csv(root / "plots.csv")
    frame["au_id"] = "AU-IDFdk3-TSA24-FDI"
    frame.to_csv(root / "plots.csv", index=False)
    with pytest.raises(SdmdApiError, match="TSA 24"):
        SdmdStore.from_directory(root)


def test_store_refuses_a_retired_bec_label(tmp_path: Path) -> None:
    """A store cannot load an AU that uses a retired BEC label."""
    root = _store_dir(tmp_path)
    frame = pd.read_csv(root / "plots.csv")
    frame["au_id"] = "AU-CWHxm1-FDI"
    frame.to_csv(root / "plots.csv", index=False)
    with pytest.raises(SdmdApiError, match="retired in BEC version 13"):
        SdmdStore.from_directory(root)


def test_store_refuses_contradictory_plot_metadata(tmp_path: Path) -> None:
    """The AU label and the plot BEC/TSA columns must agree."""
    root = _store_dir(tmp_path)
    frame = pd.read_csv(root / "plots.csv")
    frame["au_id"] = "AU-IDFdk3-TSA23-FDI"
    frame["bec_variant"] = "2"
    frame["tsa"] = "TSA-24"
    frame.to_csv(root / "plots.csv", index=False)
    with pytest.raises(SdmdApiError, match="BEC-MISMATCH"):
        SdmdStore.from_directory(root)


def test_coverage_endpoint_lists_every_bec_and_names_gaps(tmp_path: Path) -> None:
    """The coverage endpoint is a BC-wide registry, not an AU substitute."""
    client = _client(_store(tmp_path))
    response = client.get("/api/sdmd/coverage")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 219
    assert payload["counts"] == {"no-diagram": 161, "provisional": 57, "reviewed": 1}
    reviewed = next(row for row in payload["rows"] if row["bec"] == "IDFdk3")
    assert reviewed["au_ids"] == "AU-IDFdk3-TSA23-FDI;AU-IDFdk3-TSA23-PLI"
    missing = client.get("/api/sdmd/coverage/XYZ99")
    assert missing.status_code == 404
