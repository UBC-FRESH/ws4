"""The exact option-selection lane for small instances.

The MIP in :mod:`ws4.opt.mip` chooses one treatment chain per block and prices additive
targets. It can enforce the stand-centred opening rows, but it does **not** model green-up,
core area, patch distribution, routes, or spread connectivity. This module wraps that model
in the run artefacts so an exact result can be inspected and compared honestly.

The schedule is replayed through the simulator after the solve. The option model's objective
and the replayed target penalty are both reported; a disagreement is a model-boundary signal,
not a silent success.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..report import write_report
from ..sim.engine import Simulator
from .archive import write_schedule
from .engine import OptimizeConfig, Optimizer
from .mip import MipResult, bound_for
from .objective import Target, objective


def solve_option_model(
    dataset: Path,
    targets: list[Target],
    years: int,
    *,
    topology_path: Path | None = None,
    max_opening_ha: float | None = None,
    limit_blocks: int | None = None,
) -> MipResult:
    """Solve the option-selection model, optionally over the first N blocks.

    Parameters
    ----------
    dataset : Path
        The compiled dataset.
    targets : list of Target
        The targets priced by the model.
    years : int
        The simulation horizon.
    topology_path : Path or None, optional
        The topology for the stand-centred opening rows.
    max_opening_ha : float or None, optional
        The maximum opening area.
    limit_blocks : int or None, optional
        Keep only the first N blocks by identifier. This is a diagnostic subproblem.

    Returns
    -------
    MipResult
        The option model's bound, schedule, status, and variable count.

    Raises
    ------
    ValueError
        When ``limit_blocks`` is not positive.
    """
    if limit_blocks is not None and limit_blocks < 1:
        raise ValueError("limit_blocks must be positive")
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=years))
    candidates = optimizer.candidates()
    if limit_blocks is not None:
        keep = set(sorted(candidates)[:limit_blocks])
        candidates = {block: options for block, options in candidates.items() if block in keep}
    return bound_for(
        dataset,
        targets,
        candidates,
        years,
        topology_path=topology_path,
        max_opening_ha=max_opening_ha,
    )


def write_exact_result(
    out_dir: Path,
    dataset: Path,
    targets: list[Target],
    years: int,
    result: MipResult,
    *,
    topology_path: Path | None = None,
    max_opening_ha: float | None = None,
    limit_blocks: int | None = None,
) -> dict[str, Any]:
    """Write the exact schedule, replay it, and return the artefact report.

    Parameters
    ----------
    out_dir : Path
        The output directory.
    dataset : Path
        The compiled dataset.
    targets : list of Target
        The targets.
    years : int
        The simulation horizon.
    result : MipResult
        The option model result.
    topology_path : Path or None, optional
        The topology used for the opening rows and replay.
    max_opening_ha : float or None, optional
        The maximum opening area.
    limit_blocks : int or None, optional
        The diagnostic block subset, recorded in the report.

    Returns
    -------
    dict of str to Any
        The model status, option objective, replayed target penalty, and paths.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    schedule_path = out_dir / "schedule.csv"
    write_schedule(schedule_path, result.schedule)
    simulator = Simulator.from_dataset(dataset)
    values = simulator.run(
        schedule_path,
        years=years,
        out_dir=out_dir,
        topology_csv=topology_path,
        max_opening_ha=max_opening_ha,
    )
    write_report(values, targets, out_dir)
    actual = objective(values, targets)
    violations = out_dir / "spatial_violations.csv"
    violation_count = 0
    if violations.is_file() and violations.stat().st_size:
        try:
            violation_count = len(pd.read_csv(violations))
        except (OSError, ValueError):
            violation_count = 0
    report: dict[str, Any] = {
        "status": result.status,
        "model": "option-selection",
        "model_note": (
            "Additive target penalties with optional stand-centred opening rows; green-up, "
            "core area, patch distribution, routes, and spread connectivity are not modelled."
        ),
        "option_objective": result.objective,
        "actual_target_penalty": actual,
        "variables": result.variables,
        "blocks_scheduled": len(result.schedule),
        "years": years,
        "limit_blocks": limit_blocks,
        "spatial_violation_count": violation_count,
        "schedule": "schedule.csv",
        "report_targets": "report_targets.csv",
        "account_values": "account_values.csv",
    }
    (out_dir / "mip.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report
