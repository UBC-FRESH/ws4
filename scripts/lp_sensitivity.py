#!/usr/bin/env python3
"""Report LP target duals and option reduced costs for a small subproblem.

The LP relaxes the binary option variables to ``[0, 1]`` but keeps the same target and
opening rows as the MIP bound. Its objective is a lower bound; a target dual is the
objective reduction from relaxing that bound by one unit, and an option reduced cost is
the per-unit cost of forcing a little of that option into the relaxation.

This is advisory. It prices the relaxation, not a schedule, and a full landscape is much
larger than the intended subproblem. Use ``--limit-blocks`` to declare a subset.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.mip import relaxation_for
from ws4.opt.objective import load_targets


def lp_report(
    *,
    dataset: Path,
    targets: Path,
    years: int = 1,
    limit_blocks: int | None = None,
    topology: Path | None = None,
    max_opening_ha: float | None = None,
    top: int = 20,
) -> dict[str, Any]:
    """Solve the LP and return its dual/reduced-cost report.

    Parameters
    ----------
    dataset : Path
        The compiled dataset.
    targets : Path
        The targets YAML.
    years : int, optional
        The simulation horizon. Defaults to 1.
    limit_blocks : int or None, optional
        Keep only the first N blocks by identifier. None keeps every candidate.
    topology : Path or None, optional
        The block topology for the opening constraints.
    max_opening_ha : float or None, optional
        The maximum opening area.
    top : int, optional
        The most nonzero reduced costs to report. Defaults to 20.

    Returns
    -------
    dict of str to Any
        The LP result, the top reduced costs, and a Markdown report.
    """
    if top < 1:
        raise ValueError("top must be positive")
    if limit_blocks is not None and limit_blocks < 1:
        raise ValueError("limit_blocks must be positive")
    goal_list = load_targets(targets)
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=years))
    candidates = optimizer.candidates()
    if limit_blocks is not None:
        keep = set(sorted(candidates)[:limit_blocks])
        candidates = {block: options for block, options in candidates.items() if block in keep}
    result = relaxation_for(
        dataset,
        goal_list,
        candidates,
        years,
        topology_path=topology,
        max_opening_ha=max_opening_ha,
    )
    reduced = sorted(
        (cost for cost in result.reduced_costs if abs(cost.reduced_cost) > 1e-9),
        key=lambda cost: (-abs(cost.reduced_cost), cost.block),
    )[:top]
    report: dict[str, Any] = {
        "dataset": str(dataset),
        "targets": str(targets),
        "years": years,
        "limit_blocks": limit_blocks,
        "topology": str(topology) if topology else None,
        "max_opening_ha": max_opening_ha,
        "status": result.status,
        "objective": result.objective,
        "variables": result.variables,
        "message": result.message,
        "duals": [dual.as_dict() for dual in result.duals],
        "reduced_costs": [cost.as_dict() for cost in reduced],
        "reduced_cost_total": len(result.reduced_costs),
    }
    report["markdown"] = render_markdown(report)
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """Render the LP sensitivity report as Markdown.

    Parameters
    ----------
    report : dict of str to Any
        A report from :func:`lp_report`.

    Returns
    -------
    str
        The report.
    """
    lines = [
        "# LP sensitivity",
        "",
        f"- Dataset: `{report['dataset']}`",
        f"- Targets: `{report['targets']}`",
        f"- Status: {report['status']} · objective: {report['objective']:.6g} · "
        f"options: {report['variables']}",
    ]
    if report.get("limit_blocks") is not None:
        lines.append(f"- Block subset: first {report['limit_blocks']} by identifier")
    if report.get("message"):
        lines.append(f"- Solver: {report['message']}")
    lines.extend(
        [
            "",
            "## Target duals",
            "",
            "| Account | Period | Bound | Dual | Slack | Binding |",
            "| --- | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for dual in report["duals"]:
        lines.append(
            f"| {dual['account']} | {dual['period']} | {dual['bound']} | "
            f"{dual['dual']:.6g} | {dual['slack']:.6g} | {dual['binding']} |"
        )
    lines.extend(
        [
            "",
            "Dual is the objective reduction per unit of relaxing the bound (lowering a minimum",
            "or raising a maximum). A non-binding row is zero.",
            "",
            "## Option reduced costs",
            "",
            "| Block | Treatments | Value | Reduced cost |",
            "| ---: | --- | ---: | ---: |",
        ]
    )
    for cost in report["reduced_costs"]:
        treatments = " → ".join(f"{treatment}@{offset}" for treatment, offset in cost["treatments"])
        lines.append(
            f"| {cost['block']} | {treatments} | {cost['value']:.6g} | {cost['reduced_cost']:.6g} |"
        )
    if not report["reduced_costs"]:
        lines.append("| — | no nonzero reduced costs | — | — |")
    lines.extend(
        [
            "",
            f"Showing {len(report['reduced_costs'])} of {report['reduced_cost_total']} option"
            " variables with a nonzero reduced cost.",
            "The LP is a relaxation, so these prices are advisory, not a schedule or a",
            "certified optimum.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the LP sensitivity report from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when the LP solved, and ``1`` otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--years", type=int, default=1)
    parser.add_argument("--limit-blocks", type=int, default=None)
    parser.add_argument("--topology", type=Path, default=None)
    parser.add_argument("--max-opening-ha", type=float, default=None)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)
    report = lp_report(
        dataset=args.dataset,
        targets=args.targets,
        years=args.years,
        limit_blocks=args.limit_blocks,
        topology=args.topology,
        max_opening_ha=args.max_opening_ha,
        top=args.top,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "lp_sensitivity.json").write_text(
        json.dumps({key: value for key, value in report.items() if key != "markdown"}, indent=2),
        encoding="utf-8",
    )
    (args.out / "lp_sensitivity.md").write_text(str(report["markdown"]) + "\n", encoding="utf-8")
    print(str(report["markdown"]))
    return 0 if report["status"] == "optimal" else 1


if __name__ == "__main__":
    raise SystemExit(main())
