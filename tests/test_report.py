"""Tests for accounts and reporting."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.opt.objective import Target
from ws4.report import account_summary, ratio_account, target_status, write_report


def _values() -> pd.DataFrame:
    """Two accounts over two years."""
    return pd.DataFrame(
        {
            "year": [0, 1, 0, 1],
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
    """A ratio account divides the numerator by the denominator per year."""
    ratio = ratio_account(_values(), "a", "b", "a_per_b").set_index("year")["value"]
    assert ratio.loc[0] == 2.0  # 10 / 5
    assert ratio.loc[1] == 4.0  # 20 / 5


def test_target_status() -> None:
    """Each target reports its value and whether it was met."""
    targets = [
        Target("a", 0, minimum=5.0),  # met
        Target("a", 1, minimum=25.0),  # below
        Target("b", 0, maximum=1.0),  # above
    ]
    status = target_status(_values(), targets)
    account_a = status[status["account"] == "a"].sort_values("year")
    assert list(account_a["status"]) == ["met", "below"]
    account_b = status[status["account"] == "b"]
    assert list(account_b["status"]) == ["above"]


def test_write_report(tmp_path: Path) -> None:
    """The report writer emits the two CSV files."""
    write_report(_values(), [Target("a", 0, minimum=5.0)], tmp_path)
    assert (tmp_path / "report_accounts.csv").is_file()
    assert (tmp_path / "report_targets.csv").is_file()
