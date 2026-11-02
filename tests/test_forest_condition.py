"""Tests for the forest-condition report-card contract."""

from __future__ import annotations

import json

import pytest
from ws4.forest_condition import (
    ConditionAlert,
    ConditionIndicator,
    ForestConditionReport,
    load_report,
    write_report,
)


def _indicator(**overrides: object) -> ConditionIndicator:
    values: dict[str, object] = {
        "name": "basal_area",
        "value": 24.5,
        "unit": "m2/ha",
        "source": "femic.inventory.als",
        "source_version": "2026.1",
        "uncertainty": 8.86,
        "uncertainty_kind": "RMSE",
        "applicability": "TSA23 IDF; BA-only pilot",
        "status": "ok",
        "trend": "stable",
    }
    values.update(overrides)
    return ConditionIndicator(**values)  # type: ignore[arg-type]


def _report() -> ForestConditionReport:
    return ForestConditionReport(
        report_id="tsa23-pilot-2026",
        scenario_id="c5-seeded",
        generated_utc="2026-11-02T00:00:00Z",
        period="2026",
        review_status="draft",
        indicators=(_indicator(),),
        alerts=(
            ConditionAlert(
                code="ba-outside-domain",
                severity="watch",
                message="Some blocks are outside the BA applicability domain.",
                indicator="basal_area",
            ),
        ),
        provenance={"inventory": "femic-tsa23-instance@b12b051"},
    )


def test_report_json_round_trip() -> None:
    """A valid report round-trips through JSON."""
    report = _report()
    restored = ForestConditionReport.from_json(report.to_json())
    assert restored == report
    assert json.loads(report.to_json())["schema_version"] == "ws4.forest_condition.report.v1"


def test_markdown_names_limits_and_provenance() -> None:
    """The Markdown card exposes the review status, source, and limitations."""
    text = _report().to_markdown()
    assert "# Forest condition report" in text
    assert "report-only" in text
    assert "basal_area" in text
    assert "femic.inventory.als" in text
    assert "TSA23 IDF; BA-only pilot" in text
    assert "ba-outside-domain" in text
    assert "does not change objectives" in text


def test_empty_indicators_render_without_a_table() -> None:
    """An empty card is explicit rather than silently omitted."""
    report = ForestConditionReport(
        report_id="empty",
        scenario_id="test",
        generated_utc="2026-11-02T00:00:00Z",
        period="2026",
        indicators=(),
        review_status="draft",
    )
    assert "No indicators were supplied." in report.to_markdown()


def test_non_finite_value_is_rejected() -> None:
    """NaN and infinity are not valid indicator values."""
    with pytest.raises(ValueError, match="finite"):
        _indicator(value=float("nan"))


def test_missing_source_is_rejected() -> None:
    """A report card must cite its source."""
    with pytest.raises(ValueError, match="source"):
        _indicator(source="")


def test_invalid_status_is_rejected() -> None:
    """Unknown status values fail validation."""
    with pytest.raises(ValueError, match="status"):
        _indicator(status="good")


def test_duplicate_indicator_names_are_rejected() -> None:
    """Indicator names are unique within a report."""
    with pytest.raises(ValueError, match="unique"):
        ForestConditionReport(
            report_id="duplicate",
            scenario_id="test",
            generated_utc="2026-11-02T00:00:00Z",
            period="2026",
            indicators=(_indicator(), _indicator()),
            review_status="draft",
        )


def test_non_advisory_alert_is_rejected() -> None:
    """Alerts cannot opt out of the advisory boundary."""
    with pytest.raises(ValueError, match="advisory"):
        ConditionAlert.from_dict(
            {
                "code": "x",
                "severity": "warning",
                "message": "x",
                "advisory": False,
            }
        )


def test_invalid_review_status_is_rejected() -> None:
    """Only the declared review states are accepted."""
    with pytest.raises(ValueError, match="review_status"):
        ForestConditionReport(
            report_id="bad-review",
            scenario_id="test",
            generated_utc="2026-11-02T00:00:00Z",
            period="2026",
            indicators=(),
            review_status="operational",  # type: ignore[arg-type]
        )


def test_load_and_write_report(tmp_path: object) -> None:
    """A report can be written and loaded from disk."""
    from pathlib import Path

    path = Path(str(tmp_path)) / "card.json"
    report = _report()
    write_report(report, path)
    assert load_report(path) == report
