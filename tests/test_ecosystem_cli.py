"""Integration tests for the ecosystem event-log command."""

from __future__ import annotations

import json
from pathlib import Path

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
