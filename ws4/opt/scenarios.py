"""Compare completed run directories over one landscape.

The comparison is read-only: it reads each run's summary, target report, account values,
constraint report, and schedule, then writes a shared table, target/account tables, and an
optional Pareto front over named metrics. A missing artefact is reported as unavailable
rather than failing the other runs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from .archive import Direction, Elite, pareto_front

_TOLERANCE = 1e-9


def parse_run_spec(text: str) -> tuple[str, Path]:
    """Parse ``label=path`` or a bare path.

    Parameters
    ----------
    text : str
        The argument value.

    Returns
    -------
    tuple of (str, Path)
        The label and run directory. A bare path uses its directory name as the label.

    Raises
    ------
    ValueError
        When the label or path is empty.
    """
    label, separator, raw_path = text.partition("=")
    if separator:
        label = label.strip()
        path = Path(raw_path.strip())
    else:
        path = Path(text.strip())
        label = path.name
    if not label or not str(path):
        raise ValueError(f"run argument {text!r} needs label=path")
    return label, path


def parse_metric(text: str) -> tuple[str, Direction]:
    """Parse ``account`` or ``account:min|max``.

    Parameters
    ----------
    text : str
        The metric argument.

    Returns
    -------
    tuple of (str, str)
        The account and its direction, defaulting to ``max``.

    Raises
    ------
    ValueError
        When the direction is not ``min`` or ``max``.
    """
    account, separator, direction = text.partition(":")
    account = account.strip()
    if not account:
        raise ValueError("metric name is empty")
    resolved = direction.strip() if separator else "max"
    if resolved == "min":
        return account, "min"
    if resolved == "max":
        return account, "max"
    raise ValueError(f"metric {text!r} needs :min or :max")


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a CSV, returning an empty frame when it is missing."""
    if not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, ValueError):
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object, returning an empty mapping when it is missing."""
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _final_accounts(frame: pd.DataFrame) -> dict[str, float]:
    """Return each account's value at its last offset."""
    if frame.empty or not {"offset", "account", "value"} <= set(frame.columns):
        return {}
    values: dict[str, float] = {}
    for account, group in frame.groupby("account", sort=True):
        last = float(group["offset"].astype(float).max())
        rows = group[group["offset"].astype(float) == last]
        values[str(account)] = float(rows["value"].astype(float).sum())
    return values


def _run_record(label: str, path: Path, metrics: Sequence[str]) -> dict[str, Any]:
    """Read one run and return its comparison record."""
    summary = _read_json(path / "summary.json")
    targets = _read_csv(path / "report_targets.csv")
    account_frame = _read_csv(path / "account_values.csv")
    accounts = _final_accounts(account_frame)
    ending_frame = _read_csv(path / "ending_inventory.csv")
    if ending_frame.empty:
        final = accounts
        ending = [
            {"account": name, "value": value}
            for name, value in sorted(final.items())
            if name.startswith("feature.")
        ]
    else:
        ending = [
            {"account": str(row.account), "value": float(str(row.value))}
            for row in ending_frame.itertuples(index=False)
        ]
    constraint = _read_json(path / "constraint_report.json")
    met = (
        int((targets.get("status", pd.Series(dtype=str)) == "met").sum())
        if not targets.empty
        else 0
    )
    missed = (
        int((targets.get("status", pd.Series(dtype=str)) != "met").sum())
        if not targets.empty
        else 0
    )
    target_rows: list[dict[str, Any]] = []
    if not targets.empty:
        for row in targets.to_dict(orient="records"):
            target_rows.append({str(key): value for key, value in row.items()})
    return {
        "label": label,
        "path": str(path),
        "available": bool(summary),
        "objective": summary.get("incumbent_objective"),
        "blocks_scheduled": summary.get("blocks_scheduled"),
        "iterations": summary.get("iterations"),
        "seed": summary.get("seed"),
        "metaheuristic": summary.get("metaheuristic"),
        "status": summary.get("status"),
        "constraint_feasible": constraint.get("feasible"),
        "violations": len(constraint.get("violations", [])),
        "targets_met": met,
        "targets_missed": missed,
        "metrics": {name: accounts.get(name) for name in metrics},
        "targets": target_rows,
        "flows": _flow_rows(target_rows),
        "ending": ending,
        "accounts": accounts,
        "schedule": path / "schedule.csv",
    }


def _flow_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return flow target rows with a percent change from the prior/reference period."""
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if str(row.get("flow", "")):
            grouped.setdefault(str(row.get("account", "")), []).append(row)
    result: list[dict[str, Any]] = []
    for account, group in grouped.items():
        ordered = sorted(
            group, key=lambda item: float(item.get("offset", item.get("period", 0)) or 0)
        )
        values = [float(item.get("value", 0.0) or 0.0) for item in ordered]
        flow = str(ordered[0].get("flow", ""))
        for index, item in enumerate(ordered):
            change: float | None = None
            if index > 0 and values[index - 1] > 0.0:
                if flow == "ndy":
                    change = 100.0 * (values[index] - values[index - 1]) / values[index - 1]
                elif values[-1] > 0.0:
                    change = 100.0 * (values[index] - values[-1]) / values[-1]
            result.append(
                {
                    "account": account,
                    "period": item.get("period"),
                    "offset": item.get("offset"),
                    "flow": flow,
                    "value": values[index],
                    "change_percent": change,
                    "status": item.get("status"),
                }
            )
    return result


def compare_scenarios(
    runs: Sequence[tuple[str, Path]],
    out_dir: Path,
    *,
    metrics: Mapping[str, Direction] | None = None,
) -> dict[str, Any]:
    """Compare labelled runs and write the reports.

    Parameters
    ----------
    runs : sequence of (str, Path)
        The label and run directory pairs.
    out_dir : Path
        The comparison directory.
    metrics : mapping of str to str or None, optional
        Named account metrics and their ``min``/``max`` directions for the front. No
        metrics means no front.

    Returns
    -------
    dict of str to Any
        The records, front, directions, and Markdown report.

    Raises
    ------
    ValueError
        When no runs or a duplicate label is supplied.
    """
    if not runs:
        raise ValueError("at least one run is required")
    labels = [label for label, _ in runs]
    if len(set(labels)) != len(labels):
        raise ValueError("run labels must be unique")
    directions = dict(metrics or {})
    metric_names = list(directions)
    records = [_run_record(label, path, metric_names) for label, path in runs]
    for record in records:
        record.pop("schedule", None)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    front: list[Elite] = []
    if metric_names:
        candidates: list[Elite] = []
        for label, path in runs:
            record = next(item for item in records if item["label"] == label)
            values = record.get("metrics", {})
            if any(values.get(name) is None for name in metric_names):
                continue
            objective = record.get("objective")
            if objective is None:
                continue
            schedule = _load_schedule(path / "schedule.csv")
            candidates.append(
                Elite(
                    objective=float(objective),
                    metrics={name: float(values[name]) for name in metric_names},
                    schedule=schedule,
                    source=label,
                )
            )
        front = pareto_front(candidates, directions)
    run_rows = [
        {
            key: record[key]
            for key in (
                "label",
                "path",
                "available",
                "objective",
                "blocks_scheduled",
                "iterations",
                "seed",
                "metaheuristic",
                "status",
                "constraint_feasible",
                "violations",
                "targets_met",
                "targets_missed",
            )
        }
        for record in records
    ]
    pd.DataFrame(run_rows).to_csv(out_dir / "scenario_runs.csv", index=False)
    target_rows = [
        {"run": record["label"], **target} for record in records for target in record["targets"]
    ]
    pd.DataFrame(target_rows).to_csv(out_dir / "scenario_targets.csv", index=False)
    account_rows = [
        {"run": record["label"], "account": account, "value": value}
        for record in records
        for account, value in sorted(record["accounts"].items())
    ]
    pd.DataFrame(account_rows).to_csv(out_dir / "scenario_accounts.csv", index=False)
    ending_rows = [
        {"run": record["label"], **item} for record in records for item in record["ending"]
    ]
    pd.DataFrame(ending_rows).to_csv(out_dir / "scenario_ending.csv", index=False)
    flow_rows = [{"run": record["label"], **item} for record in records for item in record["flows"]]
    pd.DataFrame(flow_rows).to_csv(out_dir / "scenario_flows.csv", index=False)
    report: dict[str, Any] = {
        "runs": records,
        "front": [elite.source for elite in front],
        "ending": ending_rows,
        "flows": flow_rows,
        "directions": directions,
        "metrics": metric_names,
        "markdown": render_markdown(records, front, directions),
    }
    (out_dir / "scenarios.json").write_text(
        json.dumps({key: value for key, value in report.items() if key != "markdown"}, indent=2),
        encoding="utf-8",
    )
    (out_dir / "scenarios.md").write_text(str(report["markdown"]) + "\n", encoding="utf-8")
    return report


def _load_schedule(path: Path) -> dict[int, tuple[tuple[str, int], ...]]:
    """Load a schedule for the front, or return an empty one when it is unavailable."""
    if not path.is_file():
        return {}
    try:
        from .engine import load_schedule_csv

        return load_schedule_csv(path)
    except (OSError, ValueError):
        return {}


def render_markdown(
    records: Sequence[Mapping[str, Any]],
    front: Sequence[Elite],
    directions: Mapping[str, Direction],
) -> str:
    """Render the scenario comparison as Markdown.

    Parameters
    ----------
    records : sequence of mapping
        The scenario records.
    front : sequence of Elite
        The Pareto front.
    directions : mapping of str to str
        The metric directions.

    Returns
    -------
    str
        The report.
    """
    ending_rows = [
        {"run": record["label"], **item} for record in records for item in record.get("ending", [])
    ]
    flow_rows = [
        {"run": record["label"], **item} for record in records for item in record.get("flows", [])
    ]
    lines = [
        "# Scenario comparison",
        "",
        "| Run | Objective | Blocks | Iterations | Seed | Engine | Constraints | "
        "Targets met/missed |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for record in records:
        objective = record.get("objective")
        objective_text = "" if objective is None else f"{float(objective):.6g}"
        constraints = (
            "not reported"
            if record.get("constraint_feasible") is None
            else "feasible"
            if record.get("constraint_feasible")
            else "violations"
        )
        lines.append(
            f"| {record['label']} | {objective_text} | {record.get('blocks_scheduled', '')} | "
            f"{record.get('iterations', '')} | {record.get('seed', '')} | "
            f"{record.get('metaheuristic', '')} | {constraints} | "
            f"{record.get('targets_met', 0)}/{record.get('targets_missed', 0)} |"
        )
    if front:
        names = list(directions)
        lines.extend(
            [
                "",
                "## Pareto front",
                "",
                "| Run | Objective | " + " | ".join(names) + " |",
                "| --- | ---: | " + " | ".join("---:" for _ in names) + " |",
            ]
        )
        for elite in front:
            values = " | ".join(f"{elite.metrics[name]:.6g}" for name in names)
            lines.append(f"| {elite.source} | {elite.objective:.6g} | {values} |")
    elif directions:
        lines.extend(["", "No run had every requested metric; the front is unavailable."])
    if ending_rows:
        lines.extend(
            [
                "",
                "## Ending inventory",
                "",
                "| Run | Account | Value |",
                "| --- | --- | ---: |",
            ]
        )
        for row in ending_rows:
            lines.append(f"| {row['run']} | {row['account']} | {float(row['value']):.6g} |")
    if flow_rows:
        lines.extend(
            [
                "",
                "## Flow targets",
                "",
                "| Run | Account | Period | Value | Change % | Status |",
                "| --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for row in flow_rows:
            change = "" if row["change_percent"] is None else f"{row['change_percent']:.3g}"
            lines.append(
                f"| {row['run']} | {row['account']} | {row['period']} | "
                f"{row['value']:.6g} | {change} | {row['status']} |"
            )
    lines.extend(
        [
            "",
            "Missing summaries, target reports, or constraint reports are shown as unavailable,",
            "not as passing. The comparison is advisory and does not change a run.",
        ]
    )
    return "\n".join(lines)
