"""Tests for the event log, its digest, and the replay validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from ws4.ecosystem import (
    Event,
    EventError,
    EventLog,
    EventLogBuilder,
    EventLogMetadata,
    ReplayError,
)

DIGEST: str = "a" * 64


def make_event(
    event_id: str = "e1",
    *,
    time: float = 0.0,
    year: int = 0,
    scenario_id: str = "s",
    phase: str = "ignition",
    area_ha: float = 1.0,
) -> Event:
    """Build one valid event for the log tests."""
    return Event(
        event_id=event_id,
        process_id="fire",
        event_type="fire",
        time=time,
        year=year,
        phase=phase,
        source="test",
        scenario_id=scenario_id,
        area_ha=area_ha,
    )


def make_metadata(seed: int = 7) -> EventLogMetadata:
    """Build one valid metadata header."""
    return EventLogMetadata(scenario_id="s", scenario_seed=seed, package_hashes=(("fire", DIGEST),))


def test_builder_builds_in_order_and_reports_length() -> None:
    builder = EventLogBuilder(make_metadata())
    first = make_event("a", time=0.1)
    second = make_event("b", time=0.2)

    builder.extend([first, second])

    assert len(builder) == 2
    assert builder.build() == EventLog(metadata=make_metadata(), events=(first, second))


def test_builder_rejects_out_of_order_events() -> None:
    builder = EventLogBuilder(make_metadata())
    builder.append(make_event("late", time=0.2))

    with pytest.raises(EventError, match="out of order"):
        builder.append(make_event("early", time=0.1))


def test_builder_rejects_duplicate_ids() -> None:
    builder = EventLogBuilder(make_metadata())
    builder.append(make_event("same", time=0.1))

    with pytest.raises(EventError, match="duplicate event id"):
        builder.append(make_event("same", time=0.2))


def test_builder_rejects_another_scenario() -> None:
    builder = EventLogBuilder(make_metadata())

    with pytest.raises(EventError, match="names scenario"):
        builder.append(make_event(scenario_id="other"))


def test_log_rejects_out_of_order_events() -> None:
    with pytest.raises(EventError, match="out of order"):
        EventLog(
            metadata=make_metadata(),
            events=(make_event("late", time=0.2), make_event("early", time=0.1)),
        )


def test_log_rejects_duplicate_events() -> None:
    with pytest.raises(EventError, match="duplicate event id"):
        EventLog(
            metadata=make_metadata(),
            events=(make_event("same", time=0.1), make_event("same", time=0.2)),
        )


def test_log_rejects_another_scenario() -> None:
    with pytest.raises(EventError, match="names scenario"):
        EventLog(metadata=make_metadata(), events=(make_event(scenario_id="other"),))


def test_from_events_sorts_by_the_execution_key() -> None:
    events = [
        make_event("c", time=0.3),
        make_event("a", time=0.1),
        make_event("b", time=0.2),
    ]

    log = EventLog.from_events(events, make_metadata())

    assert [event.event_id for event in log.events] == ["a", "b", "c"]


def test_log_round_trips_through_json(tmp_path: Path) -> None:
    log = EventLog.from_events(
        [make_event("a", time=0.1), make_event("b", time=0.2)],
        make_metadata(),
    )
    target = tmp_path / "nested" / "log.json"

    log.write(target)
    again = EventLog.read(target)

    assert again == log
    assert again.replay_token == log.replay_token


def test_read_rejects_a_tampered_event(tmp_path: Path) -> None:
    log = EventLog.from_events([make_event("a")], make_metadata())
    target = tmp_path / "log.json"
    log.write(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["events"][0]["area_ha"] = 99.0
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EventError, match="digest does not match"):
        EventLog.read(target)


def test_read_rejects_an_unknown_top_level_field(tmp_path: Path) -> None:
    log = EventLog.from_events([make_event("a")], make_metadata())
    target = tmp_path / "log.json"
    log.write(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["surprise"] = True
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EventError, match="unknown event-log fields"):
        EventLog.read(target)


def test_read_rejects_a_bad_schema_version(tmp_path: Path) -> None:
    target = tmp_path / "log.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "ws4.event-log.v0",
                "metadata": make_metadata().to_dict(),
                "events": [],
                "event_digest": DIGEST,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EventError, match="schema_version"):
        EventLog.read(target)


def test_read_rejects_a_missing_digest(tmp_path: Path) -> None:
    log = EventLog.from_events([], make_metadata())
    target = tmp_path / "log.json"
    log.write(target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload.pop("event_digest")
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EventError, match="missing event_digest"):
        EventLog.read(target)


def test_read_rejects_malformed_json(tmp_path: Path) -> None:
    target = tmp_path / "log.json"
    target.write_text("{not json", encoding="utf-8")

    with pytest.raises(EventError, match="cannot read event log"):
        EventLog.read(target)


def test_read_rejects_a_non_json_suffix(tmp_path: Path) -> None:
    target = tmp_path / "log.txt"
    target.write_text("{}", encoding="utf-8")

    with pytest.raises(EventError, match="must be JSON"):
        EventLog.read(target)


def test_metadata_round_trips() -> None:
    metadata = EventLogMetadata(
        scenario_id="base",
        scenario_seed=11,
        package_hashes=(("z", DIGEST), ("a", DIGEST)),
        attributes=(("note", "test"),),
    )

    assert EventLogMetadata.from_dict(metadata.to_dict()) == metadata
    assert metadata.package_hashes == (("a", DIGEST), ("z", DIGEST))


def test_metadata_rejects_a_bad_hash() -> None:
    with pytest.raises(EventError, match="64-character"):
        EventLogMetadata(scenario_id="s", package_hashes=(("fire", "abc"),))


def test_metadata_rejects_a_bad_algorithm() -> None:
    with pytest.raises(EventError, match="tape_algorithm"):
        EventLogMetadata(scenario_id="s", tape_algorithm="mersenne")


def test_metadata_rejects_a_negative_seed() -> None:
    with pytest.raises(EventError, match="scenario_seed must be non-negative"):
        EventLogMetadata(scenario_id="s", scenario_seed=-1)


def test_summary_of_an_empty_log_is_stable() -> None:
    summary = EventLog.from_events([], make_metadata()).summary()

    assert summary["event_count"] == 0
    assert summary["year_min"] is None
    assert summary["first_event_id"] is None
    assert summary["last_event_id"] is None


def test_summary_counts_events_areas_and_phases() -> None:
    log = EventLog.from_events(
        [
            make_event("a", time=0.1, area_ha=1.5),
            make_event("b", time=0.2, phase="treatment", area_ha=2.5),
        ],
        make_metadata(),
    )

    summary = log.summary()

    assert summary["event_count"] == 2
    assert summary["area_ha"] == pytest.approx(4.0)
    assert summary["processes"] == ["fire"]
    assert summary["event_types"] == ["fire"]
    assert summary["phases"] == ["ignition", "treatment"]
    assert summary["first_event_id"] == "a"
    assert summary["last_event_id"] == "b"


def test_replay_accepts_the_same_stream() -> None:
    log = EventLog.from_events([make_event("a"), make_event("b", time=0.2)], make_metadata())

    log.verify_replay(lambda metadata: log.events)


def test_replay_rejects_a_changed_event() -> None:
    log = EventLog.from_events([make_event("a")], make_metadata())

    with pytest.raises(ReplayError, match="diverges at event 0"):
        log.verify_replay(lambda metadata: [make_event("a", area_ha=2.0)])


def test_replay_rejects_a_short_stream() -> None:
    log = EventLog.from_events([make_event("a"), make_event("b", time=0.2)], make_metadata())

    with pytest.raises(ReplayError, match="ended after"):
        log.verify_replay(lambda metadata: [make_event("a")])


def test_replay_rejects_a_long_stream() -> None:
    log = EventLog.from_events([make_event("a")], make_metadata())

    with pytest.raises(ReplayError, match="produced 2 events"):
        log.verify_replay(lambda metadata: [make_event("a"), make_event("b", time=0.2)])


def test_replay_rejects_a_different_scenario() -> None:
    log = EventLog.from_events([make_event("a")], make_metadata())

    with pytest.raises(ReplayError, match="replay is invalid"):
        log.verify_replay(lambda metadata: [make_event("a", scenario_id="other")])


@settings(max_examples=40, deadline=None)
@given(
    times=st.lists(
        st.floats(min_value=0.0, max_value=0.999, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=8,
        unique=True,
    )
)
def test_from_events_is_order_invariant(times: list[float]) -> None:
    events = [make_event(f"e{index}", time=time) for index, time in enumerate(times)]
    forward = EventLog.from_events(events, make_metadata())
    backward = EventLog.from_events(list(reversed(events)), make_metadata())

    assert forward == backward
    assert forward.replay_token == backward.replay_token
    assert [event.sort_key for event in forward.events] == sorted(
        event.sort_key for event in forward.events
    )


def test_digest_must_be_hexadecimal() -> None:
    with pytest.raises(EventError, match="must be hexadecimal"):
        EventLogMetadata(scenario_id="s", package_hashes=(("fire", "z" * 64),))


def test_metadata_requires_a_scenario_id() -> None:
    with pytest.raises(EventError, match="missing scenario_id"):
        EventLogMetadata.from_dict({})


def test_metadata_rejects_non_mapping_package_hashes() -> None:
    with pytest.raises(EventError, match="package_hashes must be a mapping"):
        EventLogMetadata.from_dict({"scenario_id": "s", "package_hashes": 5})


def test_read_rejects_a_json_list(tmp_path: Path) -> None:
    target = tmp_path / "log.json"
    target.write_text("[]", encoding="utf-8")

    with pytest.raises(EventError, match="must be a JSON object"):
        EventLog.read(target)


def test_read_rejects_missing_metadata(tmp_path: Path) -> None:
    target = tmp_path / "log.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "ws4.event-log.v1",
                "events": [],
                "event_digest": DIGEST,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EventError, match="missing a metadata object"):
        EventLog.read(target)


def test_read_rejects_missing_events(tmp_path: Path) -> None:
    target = tmp_path / "log.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "ws4.event-log.v1",
                "metadata": make_metadata().to_dict(),
                "event_digest": DIGEST,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EventError, match="missing an events list"):
        EventLog.read(target)


def test_read_rejects_a_non_mapping_event(tmp_path: Path) -> None:
    target = tmp_path / "log.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "ws4.event-log.v1",
                "metadata": make_metadata().to_dict(),
                "events": [1],
                "event_digest": DIGEST,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EventError, match="event 0 is not a mapping"):
        EventLog.read(target)
