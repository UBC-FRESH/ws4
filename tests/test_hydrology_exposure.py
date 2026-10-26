from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from ws4.io.hydrology_exposure import (
    HYDROLOGY_EXPOSURE_SCHEMA,
    HydrologyExposureError,
    load_hydrology_exposure,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hydrology" / "exposure" / "valid.json"


def _payload() -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_load_valid_exposure_and_features() -> None:
    exposure = load_hydrology_exposure(FIXTURE)

    assert exposure.exposure_id == "exposure-fixture-001"
    assert exposure.review_status == "reviewed"
    assert exposure.reviewer_id == "reviewer-1"
    assert exposure.schedule_sha256 == "a" * 64
    assert exposure.watershed_ids == ("watershed-1", "watershed-2")
    assert exposure.periods == (0, 1)
    assert len(exposure.rows) == 4
    assert exposure.rows[0].watershed_id == "watershed-1"
    assert exposure.rows[0].period == 0
    assert exposure.sha256
    features = exposure.features_for("watershed-1", 1)
    assert features["road_built_km"] == pytest.approx(0.5)
    assert features["road_used_km"] == pytest.approx(1.75)
    assert features["culvert_exposed_count"] == pytest.approx(2.0)
    assert exposure.to_dict()["schema_version"] == HYDROLOGY_EXPOSURE_SCHEMA


def test_exposure_rejects_missing_declared_row(tmp_path: Path) -> None:
    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list)
    payload["rows"] = rows[:-1]
    path = _write(tmp_path / "missing.json", payload)

    with pytest.raises(HydrologyExposureError, match="missing 1 declared row"):
        load_hydrology_exposure(path)


def test_exposure_rejects_duplicate_row(tmp_path: Path) -> None:
    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list)
    payload["rows"] = [*rows, rows[0]]
    path = _write(tmp_path / "duplicate.json", payload)

    with pytest.raises(HydrologyExposureError, match="Duplicate exposure row"):
        load_hydrology_exposure(path)


def test_exposure_rejects_negative_and_nonfinite_values(tmp_path: Path) -> None:
    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)
    first["road_used_km"] = -1.0
    path = _write(tmp_path / "negative.json", payload)
    with pytest.raises(HydrologyExposureError, match="finite non-negative"):
        load_hydrology_exposure(path)

    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)
    first["road_used_km"] = math.inf
    path = _write(tmp_path / "infinite.json", payload)
    with pytest.raises(HydrologyExposureError, match="finite non-negative"):
        load_hydrology_exposure(path)


def test_exposure_rejects_non_integer_counts(tmp_path: Path) -> None:
    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)
    first["culvert_count"] = 1.5
    path = _write(tmp_path / "float-count.json", payload)

    with pytest.raises(HydrologyExposureError, match="non-negative integer"):
        load_hydrology_exposure(path)


def test_exposure_review_and_schedule_rules(tmp_path: Path) -> None:
    payload = _payload()
    payload["reviewer_id"] = None
    path = _write(tmp_path / "reviewed-no-reviewer.json", payload)
    with pytest.raises(HydrologyExposureError, match="reviewer_id"):
        load_hydrology_exposure(path)

    payload = _payload()
    payload["review_status"] = "not_reviewed"
    payload["reviewer_id"] = None
    path = _write(tmp_path / "not-reviewed.json", payload)
    exposure = load_hydrology_exposure(path)
    assert exposure.review_status == "not_reviewed"
    assert exposure.reviewer_id is None

    payload = _payload()
    payload["schedule_sha256"] = "not-a-digest"
    path = _write(tmp_path / "bad-schedule.json", payload)
    with pytest.raises(HydrologyExposureError, match="64-character hex"):
        load_hydrology_exposure(path)


def test_exposure_rejects_unknown_watershed_and_period(tmp_path: Path) -> None:
    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)
    first["watershed_id"] = "watershed-99"
    path = _write(tmp_path / "unknown-watershed.json", payload)
    with pytest.raises(HydrologyExposureError, match="undeclared watershed"):
        load_hydrology_exposure(path)

    payload = _payload()
    rows = payload["rows"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)
    first["period"] = 99
    path = _write(tmp_path / "unknown-period.json", payload)
    with pytest.raises(HydrologyExposureError, match="undeclared period"):
        load_hydrology_exposure(path)


def test_exposure_rejects_empty_declarations_and_bad_schema(tmp_path: Path) -> None:
    payload = _payload()
    payload["watershed_ids"] = []
    path = _write(tmp_path / "empty-watersheds.json", payload)
    with pytest.raises(HydrologyExposureError, match="watershed_ids"):
        load_hydrology_exposure(path)

    payload = _payload()
    payload["periods"] = []
    path = _write(tmp_path / "empty-periods.json", payload)
    with pytest.raises(HydrologyExposureError, match="periods"):
        load_hydrology_exposure(path)

    payload = _payload()
    payload["schema_version"] = "ws4.hydrology.exposure.v2"
    path = _write(tmp_path / "bad-schema.json", payload)
    with pytest.raises(HydrologyExposureError, match="Unsupported exposure schema"):
        load_hydrology_exposure(path)


def test_exposure_features_for_unknown_pair_fails() -> None:
    exposure = load_hydrology_exposure(FIXTURE)

    with pytest.raises(HydrologyExposureError, match="no row"):
        exposure.features_for("watershed-99", 0)
