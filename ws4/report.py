"""Accounts and reporting over a run's values.

The simulator writes account values (and product values). This module turns them into
reports: a per-account summary, a ratio account, and a target-status table that says
whether each target was met.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from .opt.objective import Target, penalty


def _by_year(values: pd.DataFrame) -> dict[tuple[int, str], float]:
    """Index values by (year, account)."""
    return {
        (int(float(str(row.year))), str(row.account)): float(str(row.value))
        for row in values.itertuples(index=False)
    }


def account_summary(values: pd.DataFrame) -> pd.DataFrame:
    """Summarize each account across the years.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values, with ``year``, ``account``, and ``value`` columns.

    Returns
    -------
    pandas.DataFrame
        One row per account with ``min``, ``max``, ``mean``, and ``final`` value.
    """
    if values.empty:
        return pd.DataFrame(columns=["account", "min", "max", "mean", "final"])
    grouped = values.groupby("account")["value"]
    summary = grouped.agg(["min", "max", "mean"]).reset_index()
    final = values.sort_values("year").groupby("account")["value"].last().reset_index(name="final")
    return summary.merge(final, on="account")


def ratio_account(
    values: pd.DataFrame, numerator: str, denominator: str, name: str
) -> pd.DataFrame:
    """Return a ratio account over the years.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values.
    numerator : str
        The numerator account.
    denominator : str
        The denominator account.
    name : str
        The name of the ratio account.

    Returns
    -------
    pandas.DataFrame
        The ratio account values, with ``year``, ``account``, and ``value`` columns.
    """
    index: Mapping[tuple[int, str], float] = _by_year(values)
    years = sorted({year for year, _ in index})
    rows: list[dict[str, object]] = []
    for year in years:
        top = index.get((year, numerator), 0.0)
        bottom = index.get((year, denominator), 0.0)
        rows.append({"year": year, "account": name, "value": (top / bottom) if bottom else 0.0})
    return pd.DataFrame(rows, columns=["year", "account", "value"])


def target_status(values: pd.DataFrame, targets: list[Target]) -> pd.DataFrame:
    """Report each target's value, bounds, and whether it was met.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values.
    targets : list of Target
        The targets.

    Returns
    -------
    pandas.DataFrame
        One row per target with ``account``, ``year``, ``value``, ``minimum``,
        ``maximum``, ``penalty``, and ``status`` (``met``, ``below``, or ``above``).
    """
    index = _by_year(values)
    rows: list[dict[str, object]] = []
    for target in targets:
        # A target applies to the account summed over its period, exactly as the objective
        # prices it (`Target.cell_years()`). Reading only the target's first year reported a
        # periodic target as unmet — with a penalty the search never applied — whenever the
        # period's later years carried it over the line.
        value = sum(index.get((year, target.account), 0.0) for year in target.cell_years())
        if target.minimum is not None and value < target.minimum:
            status = "below"
        elif target.maximum is not None and value > target.maximum:
            status = "above"
        else:
            status = "met"
        rows.append(
            {
                "account": target.account,
                "year": target.year,
                "value": value,
                "minimum": target.minimum,
                "maximum": target.maximum,
                "penalty": penalty(value, target),
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def write_report(values: pd.DataFrame, targets: list[Target], out_dir: Path) -> None:
    """Write the account summary and the target status to a directory.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values.
    targets : list of Target
        The targets.
    out_dir : Path
        Directory to write ``report_accounts.csv`` and ``report_targets.csv`` into.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    account_summary(values).to_csv(out_dir / "report_accounts.csv", index=False)
    target_status(values, targets).to_csv(out_dir / "report_targets.csv", index=False)
