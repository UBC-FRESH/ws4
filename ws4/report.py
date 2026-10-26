"""Accounts and reporting over a run's values.

The simulator writes account values (and product values). This module turns them into
reports: a per-account summary, a ratio account, and a target-status table that says
whether each target was met.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from .opt.objective import (
    Target,
    flow_series,
    normalization_scale,
    penalty,
    period_value,
    raw_penalty,
)
from .resilience import resilience_report
from .structure_habitat import structure_habitat_report


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


def target_kind(target: Target) -> str:
    """Return the target's reporting kind.

    Parameters
    ----------
    target : Target
        The target.

    Returns
    -------
    str
        ``"level"``, ``"flow.even"``, or ``"flow.ndy"``.
    """
    return f"flow.{target.flow}" if target.flow else "level"


def ending_inventory(values: pd.DataFrame) -> pd.DataFrame:
    """Return the final feature-inventory values.

    The ending inventory is the state at the last offset for accounts whose name starts
    with ``feature.``. A ``product.`` account is harvested output, not closing inventory.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values with ``offset``, ``account``, and ``value``.

    Returns
    -------
    pandas.DataFrame
        ``offset``, ``account``, and ``value`` at the final offset. Empty with those
        columns when there are no feature accounts.
    """
    columns = ["offset", "account", "value"]
    if values.empty or "offset" not in values.columns:
        return pd.DataFrame(columns=columns)
    final = int(float(values["offset"].astype(float).max()))
    frame = values[
        (values["offset"].astype(float) == final)
        & values["account"].astype(str).str.startswith("feature.")
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    ending = frame.groupby("account", sort=True)["value"].sum().reset_index().assign(offset=final)
    return ending[columns]


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
        ``maximum``, ``raw_penalty``, ``penalty`` (normalized), ``scale``,
        ``normalization``, ``priority``, and ``status``.
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
                    "raw_penalty": 0.0,
                    "penalty": 0.0,
                    "scale": normalization_scale(target),
                    "normalization": target.normalization,
                    "priority": target.priority,
                    "kind": target_kind(target),
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
                        "raw_penalty": raw_penalty(value, target),
                        "penalty": penalty(value, target),
                        "scale": normalization_scale(target),
                        "normalization": target.normalization,
                        "priority": target.priority,
                        "kind": target_kind(target),
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
                "raw_penalty": raw_penalty(value, target),
                "penalty": penalty(value, target),
                "scale": normalization_scale(target),
                "normalization": target.normalization,
                "priority": target.priority,
                "kind": target_kind(target),
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def dhi_report(
    values: pd.DataFrame,
    source: Mapping[str, object] | None = None,
) -> pd.DataFrame:
    """Summarize DHI accounts for the report directory.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values with ``offset``, ``account``, and ``value``.
    source : mapping or None, optional
        DHI source metadata from ``dhi_metadata.json``.

    Returns
    -------
    pandas.DataFrame
        One row per DHI account with baseline, final, change, unit, source
        provenance, and the interpretation caveat.
    """
    columns = [
        "account",
        "baseline",
        "final",
        "change",
        "pct_change",
        "unit",
        "source_id",
        "source_version",
        "year_range",
        "resolution_m",
        "crs",
        "licence",
        "caveat",
    ]
    if values.empty or "account" not in values.columns:
        return pd.DataFrame(columns=columns)
    frame = values[values["account"].astype(str).str.startswith("feature.DHI.")]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    offsets = sorted(frame["offset"].astype(float).unique())
    baseline_offset = -1.0 if -1.0 in offsets else offsets[0]
    final_offset = offsets[-1]
    source = source or {}
    caveat = (
        "DHI is a coarse productivity surrogate, not a species observation or a habitat "
        "suitability model. The account removes a block when the schedule treats it and does "
        "not model regrowth, recovery, or species response."
    )
    rows: list[dict[str, object]] = []
    for account in sorted(frame["account"].astype(str).unique()):
        series = frame[frame["account"].astype(str) == account]
        baseline = float(
            series.loc[series["offset"].astype(float) == baseline_offset, "value"].sum()
        )
        final = float(series.loc[series["offset"].astype(float) == final_offset, "value"].sum())
        change = final - baseline
        if account.endswith(".mean"):
            unit = "index"
        elif account.endswith(".area"):
            unit = "ha"
        else:
            unit = "index_ha"
        rows.append(
            {
                "account": account,
                "baseline": baseline,
                "final": final,
                "change": change,
                "pct_change": (100.0 * change / baseline) if baseline else None,
                "unit": unit,
                "source_id": source.get("source_id"),
                "source_version": source.get("source_version"),
                "year_range": source.get("year_range"),
                "resolution_m": source.get("resolution_m"),
                "crs": source.get("crs"),
                "licence": source.get("licence"),
                "caveat": caveat,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def write_report(values: pd.DataFrame, targets: list[Target], out_dir: Path) -> None:
    """Write the account summary and the target status to a directory.

    Parameters
    ----------
    values : pandas.DataFrame
        Account values.
    targets : list of Target
        The targets.
    out_dir : Path
        Directory to write ``report_accounts.csv``, ``report_targets.csv``, and
        ``ending_inventory.csv`` into.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    account_summary(values).to_csv(out_dir / "report_accounts.csv", index=False)
    target_status(values, targets).to_csv(out_dir / "report_targets.csv", index=False)
    ending_inventory(values).to_csv(out_dir / "ending_inventory.csv", index=False)
    metadata_path = out_dir / "dhi_metadata.json"
    metadata: dict[str, object] | None = None
    if metadata_path.is_file():
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = None
        metadata = loaded if isinstance(loaded, dict) else None
    dhi = dhi_report(values, metadata)
    if not dhi.empty:
        dhi.to_csv(out_dir / "report_dhi.csv", index=False)
    structure_metadata_path = out_dir / "structure_habitat_metadata.json"
    structure_metadata: dict[str, object] | None = None
    if structure_metadata_path.is_file():
        try:
            loaded_structure = json.loads(structure_metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded_structure = None
        structure_metadata = loaded_structure if isinstance(loaded_structure, dict) else None
    structure = structure_habitat_report(values, structure_metadata)
    if not structure.empty:
        structure.to_csv(out_dir / "report_structure_habitat.csv", index=False)
    resilience_metadata_path = out_dir / "resilience_metadata.json"
    resilience_metadata: dict[str, object] | None = None
    if resilience_metadata_path.is_file():
        try:
            loaded_resilience = json.loads(resilience_metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded_resilience = None
        resilience_metadata = loaded_resilience if isinstance(loaded_resilience, dict) else None
    resilience = resilience_report(values, resilience_metadata)
    if not resilience.empty:
        resilience.to_csv(out_dir / "report_resilience.csv", index=False)
