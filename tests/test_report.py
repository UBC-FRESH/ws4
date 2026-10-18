"""Tests for accounts and reporting."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.opt.objective import Target, objective
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


def test_a_periodic_target_is_priced_over_its_period() -> None:
    """A target that its period's later years carry is met, not below, and carries no penalty."""
    targets = [
        Target("a", 0, minimum=25.0, period_width=2),  # 10 + 20 = 30, met
        Target("a", 0, minimum=35.0, period_width=2),  # 30 < 35, below
    ]
    status = target_status(_values(), targets)
    met, below = status.iloc[0], status.iloc[1]
    assert met["value"] == 30.0
    assert met["status"] == "met"
    assert met["penalty"] == 0.0
    assert below["value"] == 30.0
    assert below["status"] == "below"
    assert below["penalty"] > 0.0


def test_a_single_year_target_still_reads_that_year() -> None:
    """The one-year case is the period sum of a single year, unchanged."""
    status = target_status(_values(), [Target("a", 1, minimum=25.0)]).iloc[0]
    assert status["value"] == 20.0
    assert status["status"] == "below"


def test_the_reported_penalty_matches_the_objective_for_a_periodic_target() -> None:
    """The report prices a periodic target exactly as the objective does."""
    targets = [
        Target("a", 0, minimum=25.0, period_width=2),  # 10 + 20 = 30, met
        Target("b", 0, maximum=4.0, period_width=2),  # 5 + 5 = 10, above
    ]
    reported = float(target_status(_values(), targets)["penalty"].sum())
    assert reported == pytest.approx(objective(_values(), targets))
    assert reported > 0.0
