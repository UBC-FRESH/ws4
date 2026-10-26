"""Tests for merging carbon accounts into a simulation run and its report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.carbon.libcbm import merge_carbon_accounts
from ws4.report import write_report


def _run_dir(tmp_path: Path) -> Path:
    """Write a tiny simulation run with one non-carbon account."""
    run = tmp_path / "run"
    run.mkdir()
    pd.DataFrame(
        {
            "offset": [0, 1],
            "account": ["feature.volume", "feature.volume"],
            "value": [100.0, 101.0],
        }
    ).to_csv(run / "account_values.csv", index=False)
    return run


def _carbon_accounts(tmp_path: Path) -> Path:
    """Write a tiny carbon account table."""
    path = tmp_path / "carbon_accounts.csv"
    pd.DataFrame(
        {
            "offset": [0, 1, 0, 1, 0, 1],
            "account": [
                "carbon.ecosystem.total",
                "carbon.ecosystem.total",
                "carbon.flux.net",
                "carbon.flux.net",
                "fertilization.co2e_t",
                "fertilization.co2e_t",
            ],
            "value": [200.0, 201.0, 0.0, 1.0, 10.0, 11.0],
        }
    ).to_csv(path, index=False)
    return path


def test_merge_carbon_accounts_preserves_non_carbon_and_is_idempotent(tmp_path: Path) -> None:
    """Merging twice does not duplicate carbon rows or overwrite other accounts."""
    run = _run_dir(tmp_path)
    accounts = _carbon_accounts(tmp_path)
    manifest = tmp_path / "carbon_manifest.json"
    manifest.write_text('{"package_id": "p"}', encoding="utf-8")

    first = merge_carbon_accounts(run, accounts, carbon_manifest=manifest)
    second = merge_carbon_accounts(run, accounts, carbon_manifest=manifest)

    assert first.shape == second.shape
    assert (second["account"] == "carbon.ecosystem.total").sum() == 2
    assert (second["account"] == "fertilization.co2e_t").sum() == 2
    assert (second["account"] == "feature.volume").sum() == 2
    assert (run / "carbon_manifest.json").is_file()
    written = pd.read_csv(run / "account_values.csv")
    assert len(written) == len(second)


def test_report_includes_carbon_accounts(tmp_path: Path) -> None:
    """The standard account report carries the merged carbon accounts."""
    run = _run_dir(tmp_path)
    merge_carbon_accounts(run, _carbon_accounts(tmp_path))
    values = pd.read_csv(run / "account_values.csv")
    write_report(values, [], run)
    summary = pd.read_csv(run / "report_accounts.csv")
    assert "carbon.ecosystem.total" in set(summary["account"])
    assert "feature.volume" in set(summary["account"])
