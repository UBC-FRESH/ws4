"""Tests for the FEMIC disturbance consumer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ws4.disturbance import (
    DisturbanceError,
    DisturbanceEvent,
    events_for_block,
    load_disturbance_events,
    summarize_disturbance_events,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "disturbance"
FIRE = FIXTURE_ROOT / "fire.json"
NSR = FIXTURE_ROOT / "nsr.json"


def test_load_fire_consumer_row() -> None:
    event = load_disturbance_events(FIRE)[0]

    assert event.event_id == "fire-2023-001"
    assert event.event_type == "fire"
    assert event.year == 2023
    assert event.severity_class == "high"
    assert event.severity_value == pytest.approx(0.82)
    assert event.confidence == pytest.approx(0.95)
    assert event.fragment_ids == (1001, 1002)
    assert event.block_ids == (101,)
    assert event.area_ha == pytest.approx(1200.0)
    assert event.source_id == "nbac"


def test_load_nsr_consumer_row() -> None:
    event = load_disturbance_events(NSR)[0]

    assert event.event_type == "partial_mortality"
    assert event.block_ids == (201,)
    assert event.fragment_ids == (2001,)


def test_full_record_extra_fields_are_ignored(tmp_path: Path) -> None:
    payload = json.loads(FIRE.read_text(encoding="utf-8"))
    payload["geometry"] = {"type": "Polygon", "coordinates": [[[0, 0]]]}
    payload["notes"] = "full record"
    target = tmp_path / "full.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    event = load_disturbance_events(target)[0]

    assert event.event_id == "fire-2023-001"


def test_table_list_and_events_object_are_accepted(tmp_path: Path) -> None:
    events = [
        json.loads(FIRE.read_text(encoding="utf-8")),
        json.loads(NSR.read_text(encoding="utf-8")),
    ]
    list_path = tmp_path / "list.json"
    list_path.write_text(json.dumps(events), encoding="utf-8")
    object_path = tmp_path / "object.json"
    object_path.write_text(json.dumps({"events": events}), encoding="utf-8")

    assert load_disturbance_events(list_path) == load_disturbance_events(object_path)


def test_duplicate_event_ids_are_rejected(tmp_path: Path) -> None:
    payload = json.loads(FIRE.read_text(encoding="utf-8"))
    target = tmp_path / "duplicate.json"
    target.write_text(json.dumps([payload, payload]), encoding="utf-8")

    with pytest.raises(DisturbanceError, match="duplicate event ids"):
        load_disturbance_events(target)


def test_unknown_event_type_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(FIRE.read_text(encoding="utf-8"))
    payload["event_type"] = "meteor"
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DisturbanceError, match="event_type must be one of"):
        load_disturbance_events(target)


def test_bad_confidence_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(FIRE.read_text(encoding="utf-8"))
    payload["confidence"] = 1.1
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DisturbanceError, match="confidence must be between"):
        load_disturbance_events(target)


def test_negative_area_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(FIRE.read_text(encoding="utf-8"))
    payload["area_ha"] = -1.0
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DisturbanceError, match="area_ha must be non-negative"):
        load_disturbance_events(target)


def test_missing_source_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(FIRE.read_text(encoding="utf-8"))
    payload.pop("source_id")
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DisturbanceError, match="missing disturbance fields: source_id"):
        load_disturbance_events(target)


def test_summary_reports_events_and_provenance() -> None:
    summary = summarize_disturbance_events(
        (load_disturbance_events(FIRE)[0], load_disturbance_events(NSR)[0])
    )

    assert summary["event_count"] == 2
    assert summary["event_types"] == ["fire", "partial_mortality"]
    assert summary["severity_classes"] == ["high", "moderate"]
    assert summary["year_min"] == 2022
    assert summary["year_max"] == 2023
    assert summary["total_area_ha"] == pytest.approx(1245.5)
    assert summary["affected_blocks"] == [101, 201]
    assert summary["affected_fragments"] == [1001, 1002, 2001]
    assert summary["sources"] == ["hls-nsr", "nbac"]
    assert summary["confidence_min"] == pytest.approx(0.7)
    assert summary["confidence_max"] == pytest.approx(0.95)


def test_events_for_block_selects_direct_block_ids() -> None:
    events = (load_disturbance_events(FIRE)[0], load_disturbance_events(NSR)[0])

    assert events_for_block(events, 201) == (events[1],)


def test_event_round_trip_to_dict() -> None:
    event = load_disturbance_events(FIRE)[0]

    assert DisturbanceEvent.from_dict(event.to_dict()) == event


def test_empty_table_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "empty.json"
    target.write_text("[]", encoding="utf-8")

    with pytest.raises(DisturbanceError, match="contains no disturbance events"):
        load_disturbance_events(target)
