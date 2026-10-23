"""Accounts and reporting over a run's values.

The simulator writes account values (and product values). This module turns them into
reports: a per-account summary, a ratio account, and a target-status table that says
whether each target was met.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from .opt.objective import Target, flow_series, penalty, period_value


def _by_offset(values: pd.DataFrame) -> dict[tuple[int, str], float]:
    """Index values by (offset, account)."""
    return {
        (int(float(str(row.offset))), str(row.account)): float(str(row.value))
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
    final = (
        values.sort_values("offset").groupby("account")["value"].last().reset_index(name="final")
    )
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
    index: Mapping[tuple[int, str], float] = _by_offset(values)
    offsets = sorted({offset for offset, _ in index})
    rows: list[dict[str, object]] = []
    for offset in offsets:
        top = index.get((offset, numerator), 0.0)
        bottom = index.get((offset, denominator), 0.0)
        rows.append({"offset": offset, "account": name, "value": (top / bottom) if bottom else 0.0})
    return pd.DataFrame(rows, columns=["offset", "account", "value"])


def _status(value: float, target: Target) -> str:
    """Return whether a value is within a target's bounds.

    Parameters
    ----------
    value : float
        The target's value for the period.
    target : Target
        The target.

    Returns
    -------
    str
        ``met``, ``below`` or ``above``.
    """
    if target.minimum is not None and value < target.minimum:
        return "below"
    if target.maximum is not None and value > target.maximum:
        return "above"
    return "met"


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
    index = _by_offset(values)
    horizon = max((offset for offset, _ in index), default=-1) + 1
    rows: list[dict[str, object]] = []
    for target in targets:
        if not target.active:
            rows.append(
                {
                    "account": target.account,
                    "period": target.period,
                    "year": target.year,
                    "value": 0.0,
                    "minimum": target.minimum,
                    "maximum": target.maximum,
                    "penalty": 0.0,
                    "status": "inactive",
                }
            )
            continue
        if target.flow:
            # A flow target constrains the shape of a profile, so its report is the series itself:
            # one row per period, exactly as the reference reports it, with a zero for the period an
            # even-flow comparison is made against. Reporting the single value a level target would
            # have made a flow target look met while the search paid for it.
            for end_offset, value in sorted(flow_series(index, target, horizon).items()):
                width = max(1, target.period_width)
                rows.append(
                    {
                        "account": target.account,
                        "period": (end_offset + 1) // width
                        if (end_offset + 1) % width == 0
                        else None,
                        "offset": end_offset,
                        "year": end_offset + 1,
                        "value": value,
                        "minimum": target.minimum,
                        "maximum": target.maximum,
                        "penalty": penalty(value, target),
                        "status": _status(value, target),
                    }
                )
            continue
        # A target is priced over its period exactly as the objective prices it: the window's sum
        # for an accumulating account, the period's end value for a level. Reading one year of it
        # reported a periodic target as unmet — with a penalty the search never applied — whenever
        # the period's later years carried it over the line.
        value = period_value(index, target)
        status = _status(value, target)
        rows.append(
            {
                "account": target.account,
                "period": target.period,
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
