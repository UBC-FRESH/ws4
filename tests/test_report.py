"""Tests for accounts and reporting."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from ws4.opt.objective import Target, objective
from ws4.report import account_summary, ratio_account, target_status, write_report


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
