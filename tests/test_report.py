"""Tests for accounts and reporting."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from ws4.opt.objective import Target, objective
from ws4.report import (
    REPORT_PROVENANCE_NAME,
    account_summary,
    build_report_provenance,
    ratio_account,
    target_status,
    write_report,
)


def _values() -> pd.DataFrame:
    """Two accounts over two simulation offsets."""
    return pd.DataFrame(
        {
            "offset": [0, 1, 0, 1],
            "account": ["a", "a", "b", "b"],
            "value": [10.0, 20.0, 5.0, 5.0],
        }
    )


def test_account_summary() -> None:
    """The summary reports min, max, mean, and final per account."""
    summary = account_summary(_values()).set_index("account")
    assert summary.loc["a", "min"] == 10.0
    assert summary.loc["a", "max"] == 20.0
    assert summary.loc["a", "final"] == 20.0
    assert summary.loc["b", "mean"] == 5.0


def test_ratio_account() -> None:
    """A ratio account divides the numerator by the denominator per offset."""
    ratio = ratio_account(_values(), "a", "b", "a_per_b").set_index("offset")["value"]
    assert ratio.loc[0] == 2.0  # 10 / 5
    assert ratio.loc[1] == 4.0  # 20 / 5


def test_an_inactive_target_is_reported_without_a_penalty() -> None:
    """An inactive target stays in the report, marked inactive, with no penalty."""
    status = target_status(_values(), [Target("a", period=1, minimum=50.0, active=False)]).iloc[0]
    assert status["status"] == "inactive"
    assert status["penalty"] == 0.0


def test_target_status() -> None:
    """Each target reports its value and whether it was met."""
    targets = [
        Target("a", period=1, minimum=5.0),  # offset 0 -> 10, met
        Target("a", period=2, minimum=25.0),  # offset 1 -> 20, below
        Target("b", period=1, maximum=1.0),  # offset 0 -> 5, above
    ]
    status = target_status(_values(), targets)
    account_a = status[status["account"] == "a"].sort_values("year")
    assert list(account_a["status"]) == ["met", "below"]
    account_b = status[status["account"] == "b"]
    assert list(account_b["status"]) == ["above"]


def test_write_report(tmp_path: Path) -> None:
    """The report writer emits the two CSV files."""
    write_report(_values(), [Target("a", period=1, minimum=5.0)], tmp_path)
    assert (tmp_path / "report_accounts.csv").is_file()
    assert (tmp_path / "report_targets.csv").is_file()


def test_write_report_writes_provenance_hashes(tmp_path: Path) -> None:
    """The sidecar hashes every report and every source metadata file that exists."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    manifest = dataset / "manifest.json"
    manifest.write_text(
        '{"schema_version": "ws4.dataset.v1", "sources": [{"path": "recipe.xml"}]}',
        encoding="utf-8",
    )
    metadata = tmp_path / "dhi_metadata.json"
    metadata.write_text(
        '{"schema_version": "ws4.dhi.source.v1", "source_id": "dhi", "source_version": "v1"}',
        encoding="utf-8",
    )

    write_report(
        _values(),
        [Target("a", period=1, minimum=5.0)],
        tmp_path,
        dataset=dataset,
        run_id="run-7",
    )

    payload = json.loads((tmp_path / REPORT_PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "ws4.report.provenance.v1"
    assert datetime.fromisoformat(payload["generated_utc"]).tzinfo is not None
    assert payload["run"]["id"] == "run-7"
    assert payload["dataset"]["id"] == "dataset"
    assert (
        payload["dataset"]["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    )

    reports = {entry["name"]: entry for entry in payload["reports"]}
    for name in ("report_accounts.csv", "report_targets.csv", "ending_inventory.csv"):
        assert reports[name]["sha256"] == hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
    sources = {entry["name"]: entry for entry in payload["sources"]}
    assert (
        sources["dhi_metadata.json"]["sha256"] == hashlib.sha256(metadata.read_bytes()).hexdigest()
    )
    assert payload["uncertainty"] == {
        "status": "not_stated",
        "source": None,
        "statement": None,
    }


def test_write_report_records_real_uncertainty_metadata(tmp_path: Path) -> None:
    """An explicit uncertainty block is carried through with its source file."""
    (tmp_path / "dhi_metadata.json").write_text(
        json.dumps(
            {
                "schema_version": "ws4.dhi.source.v1",
                "uncertainty": {
                    "status": "review_required",
                    "statement": "The pilot uses a coarse surrogate.",
                },
            }
        ),
        encoding="utf-8",
    )

    write_report(_values(), [], tmp_path)

    payload = json.loads((tmp_path / REPORT_PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert payload["uncertainty"] == {
        "status": "review_required",
        "source": "dhi_metadata.json",
        "statement": "The pilot uses a coarse surrogate.",
    }


def test_write_report_without_metadata_states_uncertainty_is_not_stated(tmp_path: Path) -> None:
    """Missing metadata is reported as absent, not inferred or silently passed."""
    write_report(_values(), [], tmp_path)

    payload = json.loads((tmp_path / REPORT_PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert payload["sources"] == []
    assert payload["dataset"] is None
    assert payload["uncertainty"] == {
        "status": "not_stated",
        "source": None,
        "statement": None,
    }
    assert payload["warnings"] == []


def test_invalid_metadata_is_hashed_and_reported_without_raising(tmp_path: Path) -> None:
    """A malformed source metadata file is recorded, not allowed to break the reports."""
    (tmp_path / "dhi_metadata.json").write_text("{not json", encoding="utf-8")

    write_report(_values(), [], tmp_path)

    payload = json.loads((tmp_path / REPORT_PROVENANCE_NAME).read_text(encoding="utf-8"))
    source = payload["sources"][0]
    assert source["name"] == "dhi_metadata.json"
    assert source["status"] == "invalid"
    assert source["error"] == "not valid JSON"
    assert source["sha256"] == hashlib.sha256(b"{not json").hexdigest()
    assert payload["uncertainty"]["status"] == "not_stated"
    assert any("dhi_metadata.json" in warning for warning in payload["warnings"])


def test_build_report_provenance_records_missing_files(tmp_path: Path) -> None:
    """Missing report and dataset files are statuses in the record, not exceptions."""
    payload = build_report_provenance(
        tmp_path,
        ["report_accounts.csv", "absent.csv"],
        dataset=tmp_path / "absent-dataset",
        run_id="run-9",
        generated_utc="2026-11-03T00:00:00+00:00",
    )

    raw_reports = payload["reports"]
    assert isinstance(raw_reports, list)
    reports = {entry["name"]: entry for entry in raw_reports}
    assert reports["report_accounts.csv"]["status"] == "missing"
    assert reports["absent.csv"] == {
        "name": "absent.csv",
        "bytes": None,
        "sha256": None,
        "status": "missing",
    }
    assert payload["dataset"] == {"id": "absent-dataset", "status": "missing"}
    assert payload["generated_utc"] == "2026-11-03T00:00:00+00:00"
    raw_warnings = payload["warnings"]
    assert isinstance(raw_warnings, list)
    assert any("absent.csv" in warning for warning in raw_warnings)


def test_a_product_target_is_priced_over_its_period() -> None:
    """A product accumulates over its period's offsets; the snapshot reads offset -1."""
    values = pd.DataFrame({"offset": [0, 1], "account": ["product.a"] * 2, "value": [10.0, 20.0]})
    status = target_status(
        values,
        [
            # period 1 with width 2 covers offsets 0-1 -> 10 + 20 = 30
            Target("product.a", period=1, period_width=2, minimum=30.0, maximum=30.0),
            # period 0 is the zero-length snapshot at offset -1 -> 0
            Target("product.a", period=0, period_width=2, minimum=0.0, maximum=0.0),
        ],
    )
    first, second = status.iloc[0], status.iloc[1]
    assert first["value"] == 30.0
    assert first["status"] == "met"
    assert second["value"] == 0.0
    assert second["status"] == "met"
    off = target_status(values, [Target("product.a", period=1, period_width=2, minimum=35.0)])
    assert off.iloc[0]["value"] == 30.0
    assert off.iloc[0]["status"] == "below"


def test_a_level_target_is_priced_at_its_periods_end() -> None:
    """A feature is a level: the report reads it at the period's end offset, whatever the width."""
    values = pd.DataFrame(
        {
            "offset": [0, 1, 2, 3, 4],
            "account": ["feature.a"] * 5,
            "value": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )
    # period 1 with width 5 covers offsets 0-4, read at its end offset 4 -> 50
    met = target_status(values, [Target("feature.a", period=1, period_width=5, minimum=50.0)])
    assert met.iloc[0]["value"] == 50.0
    assert met.iloc[0]["status"] == "met"
    off = target_status(values, [Target("feature.a", period=1, period_width=5, minimum=55.0)])
    assert off.iloc[0]["value"] == 50.0
    assert off.iloc[0]["status"] == "below"


def test_a_single_year_target_still_reads_that_year() -> None:
    """The one-year case reads the single offset of its period."""
    status = target_status(_values(), [Target("a", period=2, period_width=1, minimum=25.0)]).iloc[0]
    assert status["value"] == 20.0
    assert status["status"] == "below"


def test_the_reported_penalty_matches_the_objective_for_a_periodic_target() -> None:
    """The report prices a periodic target exactly as the objective does."""
    targets = [
        Target("a", period=1, period_width=2, minimum=25.0),  # 10 + 20 = 30, met
        Target("b", period=1, period_width=2, maximum=4.0),  # 5 + 5 = 10, above
    ]
    reported = float(target_status(_values(), targets)["penalty"].sum())
    assert reported == pytest.approx(objective(_values(), targets))
    assert reported > 0.0
