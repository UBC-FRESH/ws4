#!/usr/bin/env python3
"""Report target slack and the marginal penalty of relaxing each bound.

The report is advisory. It reads a run's ``report_targets.csv`` and the target file
that produced it, then reports, for each target, how far the realized value sits
from its bounds, whether the bound is binding, and the per-unit penalty weight that
applies if the bound is relaxed or tightened. It does not change a schedule.

This is the decision-support side of the goal-programming objective: a target that
is missed has a marginal cost per unit, and a target with slack is not controlling
the plan.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from ws4.opt.objective import Target, load_targets, normalization_scale

TOLERANCE: float = 1e-6


def _target_index(targets: list[Target]) -> dict[tuple[str, int | None], Target]:
    """Index targets by account and period."""
    return {(target.account, target.period): target for target in targets}


def _slack(value: float, minimum: float | None, maximum: float | None) -> float:
    """Return the distance to the nearest bound, or zero outside the band."""
    distances: list[float] = []
    if minimum is not None:
        distances.append(value - minimum)
    if maximum is not None:
        distances.append(maximum - value)
    if not distances:
        return 0.0
    return max(0.0, min(distances))


def run_sensitivity(run: Path, targets: Path) -> dict[str, object]:
    """Read a run and its targets and return the sensitivity report.

    Parameters
    ----------
    run : Path
        Run directory containing ``report_targets.csv``.
    targets : Path
        The target YAML that produced the run.

    Returns
    -------
    dict of str to object
        The per-target records and a Markdown report.

    Raises
    ------
    FileNotFoundError
        When the run has no ``report_targets.csv``.
    """
    frame = pd.read_csv(run / "report_targets.csv")
    index = _target_index(load_targets(targets))
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        account = str(row["account"])
        period_value = row.get("period")
        period = int(period_value) if pd.notna(period_value) else None
        target = index.get((account, period))
        value = float(row["value"])
        minimum = float(row["minimum"]) if pd.notna(row["minimum"]) else None
        maximum = float(row["maximum"]) if pd.notna(row["maximum"]) else None
        below = max(0.0, minimum - value) if minimum is not None else 0.0
        above = max(0.0, value - maximum) if maximum is not None else 0.0
        at_bound = (minimum is not None and abs(value - minimum) <= TOLERANCE) or (
            maximum is not None and abs(value - maximum) <= TOLERANCE
        )
        marginal = 0.0
        scale = normalization_scale(target) if target is not None else 1.0
        if below > 0.0 and target is not None:
            marginal = float(target.min_weight) / scale
        elif above > 0.0 and target is not None:
            marginal = float(target.max_weight) / scale
        records.append(
            {
                "account": account,
                "period": period,
                "value": round(value, 6),
                "minimum": minimum,
                "maximum": maximum,
                "status": str(row.get("status", "")),
                "penalty": round(float(row.get("penalty", 0.0)), 6),
                "shortfall": round(below, 6),
                "excess": round(above, 6),
                "slack": round(_slack(value, minimum, maximum), 6),
                "binding": bool(at_bound),
                "normalization": target.normalization if target is not None else "none",
                "priority": target.priority if target is not None else 1,
                "scale": scale,
                "marginal_relaxation": marginal,
            }
        )
    report: dict[str, object] = {
        "run": str(run),
        "targets": str(targets),
        "records": records,
        "binding_count": sum(1 for record in records if record["binding"]),
        "missed_count": sum(1 for record in records if record["status"] != "met"),
    }
    report["markdown"] = render_markdown(report)
    return report


def render_markdown(report: dict[str, object]) -> str:
    """Render a sensitivity report as a Markdown table.

    Parameters
    ----------
    report : dict of str to object
        A report from :func:`run_sensitivity`.

    Returns
    -------
    str
        A heading and a table.
    """
    records = report.get("records", [])
    assert isinstance(records, list)
    lines = [
        "# Target sensitivity",
        "",
        f"- Run: `{report['run']}`",
        f"- Targets: `{report['targets']}`",
        f"- Binding: {report['binding_count']} · missed: {report['missed_count']}",
        "",
        "| Account | Period | Value | Min | Max | Status | Slack | Binding | Scale | Marginal |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | ---: |",
    ]
    for record in records:
        assert isinstance(record, dict)
        lines.append(
            f"| {record['account']} | {record['period']} | {record['value']} | "
            f"{record['minimum']} | {record['maximum']} | {record['status']} | "
            f"{record['slack']} | {record['binding']} | {record['scale']} | "
            f"{record['marginal_relaxation']} |"
        )
    lines.extend(
        [
            "",
            "Marginal is the normalized objective weight per unit when the value is outside a",
            "bound; it is zero inside the band. Scale is the automatic normalization divisor.",
            "A binding target at its bound with zero shortfall has no immediate penalty to remove,",
            "so its marginal is also zero.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the sensitivity report from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` on success.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = run_sensitivity(args.run, args.targets)
    markdown = str(report["markdown"])
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "sensitivity.json").write_text(
            json.dumps(
                {key: value for key, value in report.items() if key != "markdown"}, indent=2
            ),
            encoding="utf-8",
        )
        (args.out / "sensitivity.md").write_text(markdown + "\n", encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
