"""Tests for the forest-condition report-card contract."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner
from ws4.cli import app
from ws4.forest_condition import (
    ConditionAlert,
    ConditionIndicator,
    ForestConditionReport,
    build_report_from_accounts,
    load_report,
    write_report,
)
from ws4.storyboard import build_storyboard


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
    path = Path(str(tmp_path)) / "card.json"
    report = _report()
    write_report(report, path)
    assert load_report(path) == report


def _accounts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"offset": -1, "account": "feature.DHI.cum.mean", "value": 0.40},
            {"offset": 0, "account": "feature.DHI.cum.mean", "value": 0.42},
            {"offset": 1, "account": "feature.DHI.cum.mean", "value": 0.39},
            {"offset": -1, "account": "feature.volume", "value": 100.0},
            {"offset": 0, "account": "feature.volume", "value": 90.0},
        ]
    )


def test_build_report_from_accounts_marks_review_required() -> None:
    """Account-derived indicators carry review_required and a trend."""
    report = build_report_from_accounts(
        _accounts(),
        report_id="run-1",
        scenario_id="scenario-1",
        generated_utc="2026-11-02T00:00:00Z",
        period="run",
        source_version="dataset-1",
        provenance={"run": "run-1"},
    )
    assert len(report.indicators) == 2
    assert all(item.status == "review_required" for item in report.indicators)
    assert {item.name: item.trend for item in report.indicators} == {
        "feature.DHI.cum.mean": "declining",
        "feature.volume": "declining",
    }
    assert report.provenance == {"run": "run-1"}


def test_build_report_rejects_bad_accounts() -> None:
    """Missing columns, empty tables, and non-finite values fail clearly."""
    with pytest.raises(ValueError, match="missing columns"):
        build_report_from_accounts(
            pd.DataFrame({"offset": [0]}),
            report_id="x",
            scenario_id="y",
            generated_utc="z",
            period="p",
        )
    with pytest.raises(ValueError, match="empty"):
        build_report_from_accounts(
            pd.DataFrame(columns=["offset", "account", "value"]),
            report_id="x",
            scenario_id="y",
            generated_utc="z",
            period="p",
        )
    bad = _accounts()
    bad.loc[0, "value"] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        build_report_from_accounts(
            bad,
            report_id="x",
            scenario_id="y",
            generated_utc="z",
            period="p",
        )


def test_condition_card_cli(tmp_path: Path) -> None:
    """The CLI writes JSON and Markdown from a run directory."""
    run = tmp_path / "run"
    run.mkdir()
    _accounts().to_csv(run / "account_values.csv", index=False)
    out = tmp_path / "out"
    result = CliRunner().invoke(
        app,
        [
            "condition-card",
            "--run",
            str(run),
            "--out",
            str(out),
            "--markdown",
            "--generated-utc",
            "2026-11-02T00:00:00Z",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (out / "forest_condition_card.json").is_file()
    assert "review_required" in (out / "forest_condition_card.md").read_text(encoding="utf-8")


def test_storyboard_from_accounts() -> None:
    """A storyboard carries the card and its limits."""
    text = build_storyboard(
        _accounts(),
        scenario_id="run-1",
        generated_utc="2026-11-02T00:00:00Z",
        source_version="dataset-1",
        provenance={"run": "run-1"},
    )
    assert "# Scenario storyboard: run-1" in text
    assert "review_required" in text
    assert "Storyboard limits" in text


def test_storyboard_cli(tmp_path: Path) -> None:
    """The CLI writes a Markdown storyboard from a run."""
    run = tmp_path / "run"
    run.mkdir()
    _accounts().to_csv(run / "account_values.csv", index=False)
    out = tmp_path / "storyboard.md"
    result = CliRunner().invoke(
        app,
        [
            "storyboard",
            "--run",
            str(run),
            "--out",
            str(out),
            "--generated-utc",
            "2026-11-02T00:00:00Z",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Scenario storyboard" in out.read_text(encoding="utf-8")
