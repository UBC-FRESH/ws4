"""Integration tests for the ecosystem event-log command."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner
from ws4.cli import app
from ws4.ecosystem import Event, EventLog, EventLogMetadata

runner = CliRunner()


def make_log() -> EventLog:
    """Build one small event log for the command tests."""
    metadata = EventLogMetadata(scenario_id="s", scenario_seed=3)
    events = (
        Event(
            event_id="a",
            process_id="fire",
            event_type="fire",
            time=0.1,
            year=0,
            phase="ignition",
            source="test",
            scenario_id="s",
            area_ha=2.0,
        ),
        Event(
            event_id="b",
            process_id="schedule",
            event_type="harvest",
            time=0.2,
            year=0,
            phase="treatment",
            source="test",
            scenario_id="s",
            area_ha=3.0,
        ),
    )
    return EventLog(metadata=metadata, events=events)


def test_validate_log_prints_a_summary(tmp_path: Path) -> None:
    target = tmp_path / "events.json"
    make_log().write(target)

    result = runner.invoke(app, ["ecosystem", "validate-log", "--events", str(target)])

    assert result.exit_code == 0
    assert "Event log" in result.output
    assert "event_count" in result.output


def test_validate_log_emits_json(tmp_path: Path) -> None:
    target = tmp_path / "events.json"
    make_log().write(target)

    result = runner.invoke(app, ["ecosystem", "validate-log", "--events", str(target), "--json"])

    assert result.exit_code == 0
    summary = json.loads(result.output)
    assert summary["event_count"] == 2
    assert summary["area_ha"] == 5.0
    assert summary["processes"] == ["fire", "schedule"]


def test_validate_log_rejects_a_tampered_digest(tmp_path: Path) -> None:
    target = tmp_path / "events.json"
    make_log().write(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["events"][0]["area_ha"] = 99.0
    target.write_text(json.dumps(payload), encoding="utf-8")

    result = runner.invoke(app, ["ecosystem", "validate-log", "--events", str(target)])

    assert result.exit_code != 0
    assert "digest" in result.output


def write_package(root: Path) -> Path:
    """Write a minimal valid ecosystem package for the command tests."""
    root.mkdir(parents=True, exist_ok=True)
    state = pd.DataFrame(
        [
            ["species", "string", "cohort", "", "", "Species"],
            ["age", "int", "cohort", "years", "", "Age"],
            ["area_fraction", "float", "cohort", "", "", "Share"],
            ["biomass_t_ha", "float", "cohort", "t/ha", "0.0", "Biomass"],
            ["fuel_t_ha", "float", "cohort", "t/ha", "0.0", "Fuel"],
            ["snag_t_ha", "float", "cohort", "t/ha", "0.0", "Snags"],
        ],
        columns=["name", "dtype", "scope", "unit", "default", "description"],
    )
    cohorts = pd.DataFrame(
        [["1", "1", "PL", "80", "1.0", "100.0", "20.0", "3.0", "{}"]],
        columns=[
            "fragment_id",
            "cohort_id",
            "species",
            "age",
            "area_fraction",
            "biomass_t_ha",
            "fuel_t_ha",
            "snag_t_ha",
            "attributes_json",
        ],
    )
    bridges = pd.DataFrame(
        [["null", "null", "{}", "", ""]],
        columns=["bridge_id", "type", "params_json", "state_reads", "state_writes"],
    )
    state.to_csv(root / "state_variables.csv", index=False)
    cohorts.to_csv(root / "cohorts.csv", index=False)
    bridges.to_csv(root / "bridges.csv", index=False)
    manifest = {
        "schema_version": "ws4.ecosystem.v1",
        "package_id": "cli",
        "created_utc": "2026-11-07T00:00:00Z",
        "producer": {"name": "test", "version": "1"},
        "sources": [],
        "table_hashes": {
            name: hashlib.sha256((root / f"{name}.csv").read_bytes()).hexdigest()
            for name in ("state_variables", "cohorts", "bridges")
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_validate_package_prints_a_summary(tmp_path: Path) -> None:
    root = write_package(tmp_path / "package")

    result = runner.invoke(app, ["ecosystem", "validate-package", "--package", str(root)])

    assert result.exit_code == 0
    assert "Ecosystem package" in result.output
    assert "cli" in result.output


def test_validate_package_emits_json(tmp_path: Path) -> None:
    root = write_package(tmp_path / "package")

    result = runner.invoke(app, ["ecosystem", "validate-package", "--package", str(root), "--json"])

    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["valid"] is True
    assert report["findings"] == []


def test_validate_package_rejects_a_bad_column(tmp_path: Path) -> None:
    root = write_package(tmp_path / "package")
    frame = pd.read_csv(root / "cohorts.csv", keep_default_na=False)
    frame.drop(columns=["age"]).to_csv(root / "cohorts.csv", index=False)

    result = runner.invoke(app, ["ecosystem", "validate-package", "--package", str(root)])

    assert result.exit_code != 0
    assert "ECOSYSTEM-MISSING-COLUMN" in result.output


def test_validate_package_emits_json_findings(tmp_path: Path) -> None:
    root = write_package(tmp_path / "package")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["schema_version"] = "0.1"
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = runner.invoke(app, ["ecosystem", "validate-package", "--package", str(root), "--json"])

    assert result.exit_code != 0
    report = json.loads(result.output)
    assert report["valid"] is False
    assert any(finding["code"] == "ECOSYSTEM-SCHEMA-VERSION" for finding in report["findings"])
