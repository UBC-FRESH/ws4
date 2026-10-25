#!/usr/bin/env python3
"""Compare the exact option-selection model with the heuristic on a small instance.

The exact side solves the option-selection MIP and replays its schedule. The heuristic side
runs ``ws4 optimize`` under the same targets, horizon, and iteration budget. The report names
the option-model status, both replayed target penalties, and the gap. The exact model ignores
green-up, core area, patch distribution, routes, and spread connectivity; that boundary is
part of the output, not a footnote.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from ws4.opt.engine import OptimizeConfig, Optimizer
from ws4.opt.exact import solve_option_model, write_exact_result
from ws4.opt.objective import load_targets, objective


def run_comparison(
    *,
    dataset: Path,
    targets: Path,
    out_dir: Path,
    years: int = 50,
    iterations: int = 200,
    seed: int = 1,
    topology: Path | None = None,
    max_opening_ha: float | None = None,
) -> dict[str, Any]:
    """Run both lanes and return the comparison report.

    Parameters
    ----------
    dataset : Path
        The compiled dataset.
    targets : Path
        The targets YAML.
    out_dir : Path
        The output directory.
    years : int, optional
        Simulation horizon. Defaults to 50.
    iterations : int, optional
        Heuristic iteration budget. Defaults to 200.
    seed : int, optional
        Heuristic seed. Defaults to 1.
    topology : Path or None, optional
        Topology for the option model and heuristic.
    max_opening_ha : float or None, optional
        Maximum opening area.

    Returns
    -------
    dict of str to Any
        The two schedules, penalties, gap, statuses, and a Markdown report.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target_list = load_targets(targets)
    exact_dir = out_dir / "exact"
    heuristic_dir = out_dir / "heuristic"
    exact_result = solve_option_model(
        dataset,
        target_list,
        years,
        topology_path=topology,
        max_opening_ha=max_opening_ha,
    )
    exact = write_exact_result(
        exact_dir,
        dataset,
        target_list,
        years,
        exact_result,
        topology_path=topology,
        max_opening_ha=max_opening_ha,
    )
    heuristic_config = OptimizeConfig(
        targets_path=str(targets),
        years=years,
        iterations=iterations,
        seed=seed,
        threads=1,
        topology_path=str(topology) if topology is not None else "",
        max_opening_ha=max_opening_ha,
    )
    heuristic_summary = Optimizer.from_dataset(dataset, heuristic_config).run(heuristic_dir)
    heuristic_values = pd.read_csv(heuristic_dir / "account_values.csv")
    heuristic_penalty = objective(heuristic_values, target_list)
    exact_penalty = float(exact["actual_target_penalty"])
    gap = heuristic_penalty - exact_penalty
    report: dict[str, Any] = {
        "dataset": str(dataset),
        "targets": str(targets),
        "years": years,
        "iterations": iterations,
        "seed": seed,
        "exact": {
            "status": exact["status"],
            "option_objective": exact["option_objective"],
            "actual_target_penalty": exact_penalty,
            "schedule": str(exact_dir / "schedule.csv"),
            "model_note": exact["model_note"],
        },
        "heuristic": {
            "objective": heuristic_summary.get("incumbent_objective"),
            "actual_target_penalty": heuristic_penalty,
            "schedule": str(heuristic_dir / "schedule.csv"),
        },
        "gap": gap,
        "optimal": exact["status"] == "optimal",
        "markdown": "",
    }
    report["markdown"] = render_markdown(report)
    (out_dir / "exact_vs_heuristic.json").write_text(
        json.dumps({key: value for key, value in report.items() if key != "markdown"}, indent=2),
        encoding="utf-8",
    )
    (out_dir / "exact_vs_heuristic.md").write_text(str(report["markdown"]) + "\n", encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """Render the comparison report.

    Parameters
    ----------
    report : dict of str to Any
        A report from :func:`run_comparison`.

    Returns
    -------
    str
        The Markdown report.
    """
    exact = report["exact"]
    heuristic = report["heuristic"]
    lines = [
        "# Exact versus heuristic",
        "",
        f"- Dataset: `{report['dataset']}`",
        f"- Targets: `{report['targets']}`",
        f"- Exact status: **{exact['status']}**",
        "",
        "| Lane | Option objective | Replayed target penalty | Schedule |",
        "| --- | ---: | ---: | --- |",
        f"| Exact | {exact['option_objective']:.6g} | {exact['actual_target_penalty']:.6g} | "
        f"`{exact['schedule']}` |",
        f"| Heuristic | {heuristic['objective']} | {heuristic['actual_target_penalty']:.6g} | "
        f"`{heuristic['schedule']}` |",
        "",
        f"Gap (heuristic - exact): **{report['gap']:.6g}**",
        "",
        "The exact model solves the option-selection formulation only. It does not model green-up,",
        "core area, patch distribution, routes, or spread connectivity, so a zero gap means the",
        "heuristic matched this bounded model on this instance, not that either is optimal for the",
        "full spatial problem.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the comparison from the command line.

    Parameters
    ----------
    argv : list of str or None, optional
        Arguments to parse. ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        ``0`` when the report was written.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--years", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--topology", type=Path, default=None)
    parser.add_argument("--max-opening-ha", type=float, default=None)
    args = parser.parse_args(argv)
    report = run_comparison(
        dataset=args.dataset,
        targets=args.targets,
        out_dir=args.out,
        years=args.years,
        iterations=args.iterations,
        seed=args.seed,
        topology=args.topology,
        max_opening_ha=args.max_opening_ha,
    )
    print(str(report["markdown"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
