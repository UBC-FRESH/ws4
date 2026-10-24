"""A constructive binary-search flow ceiling.

Given a volume account and a period width, the command searches for the highest constant
per-period floor a schedule can meet. It probes the existing optimizer at each level; a
probe is feasible when every period's realized account value is at least the level within
a relative tolerance, and the run reports no spatial violations.

The result is advisory. The high bound is an additive upper envelope over block options,
and each probe is a finite search, so the reported ceiling is the best level this
procedure verified, not a certified maximum.
"""

from __future__ import annotations

import json
import math
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .calibrate import write_targets
from .engine import OptimizeConfig, Optimizer
from .objective import Target, accumulates, load_targets


@dataclass(frozen=True)
class Probe:
    """One binary-search probe.

    Attributes
    ----------
    level : float
        The requested constant per-period floor.
    feasible : bool
        Whether every period met the floor and the run was spatially feasible.
    objective : float or None
        The optimizer's incumbent objective, when the run produced one.
    values : mapping of int to float
        The realized account value per period.
    run_dir : str
        The probe's run directory.
    error : str
        A failure message, empty on success.
    """

    level: float
    feasible: bool
    objective: float | None
    values: Mapping[int, float]
    run_dir: str
    error: str = ""

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready record.

        Returns
        -------
        dict of str to object
            The level, feasibility, objective, values, run directory, and error.
        """
        return {
            "level": round(self.level, 6),
            "feasible": self.feasible,
            "objective": None if self.objective is None else round(self.objective, 6),
            "values": {
                str(period): round(value, 6) for period, value in sorted(self.values.items())
            },
            "run_dir": self.run_dir,
            "error": self.error,
        }


def period_values(
    frame: pd.DataFrame, account: str, years: int, period_width: int
) -> dict[int, float]:
    """Return the account value per accounting period.

    Parameters
    ----------
    frame : pandas.DataFrame
        An ``account_values.csv`` frame with ``offset``, ``account``, and ``value``.
    account : str
        The account name.
    years : int
        The simulation horizon.
    period_width : int
        The years per accounting period.

    Returns
    -------
    dict of int to float
        The value per 1-based period. A product account sums its offsets; a level
        account reads its period's end offset.

    Raises
    ------
    ValueError
        When the horizon is not divisible by the period width.
    """
    if period_width < 1 or years < 1 or years % period_width:
        raise ValueError("years must be a positive multiple of period_width")
    subset = frame[frame["account"].astype(str) == account]
    index = {
        int(float(str(row.offset))): float(str(row.value)) for row in subset.itertuples(index=False)
    }
    values: dict[int, float] = {}
    for period in range(1, years // period_width + 1):
        offsets = range((period - 1) * period_width, period * period_width)
        if accumulates(account):
            values[period] = sum(index.get(offset, 0.0) for offset in offsets)
        else:
            values[period] = index.get(offsets[-1], 0.0)
    return values


def high_bound(optimizer: Optimizer, account: str, years: int, period_width: int) -> float:
    """Return an additive upper envelope for the account's period values.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer whose block deltas are read.
    account : str
        The account name.
    years : int
        The simulation horizon.
    period_width : int
        The years per accounting period.

    Returns
    -------
    float
        The minimum over periods of the empty-schedule base plus each block's best
        option contribution. It is an upper bound, not a schedule.
    """
    periods = years // period_width
    empty = optimizer._base_values()
    base = [
        sum(
            empty.get((offset, account), 0.0)
            for offset in range((period - 1) * period_width, period * period_width)
        )
        if accumulates(account)
        else empty.get((period * period_width - 1, account), 0.0)
        for period in range(1, periods + 1)
    ]
    best = [0.0] * periods
    for block, options in optimizer.candidates().items():
        block_best = [0.0] * periods
        for chain in options:
            delta = optimizer._block_delta(block, chain, {account})
            for position in range(periods):
                offsets = range(position * period_width, (position + 1) * period_width)
                if accumulates(account):
                    value = sum(delta.get((offset, account), 0.0) for offset in offsets)
                else:
                    value = delta.get(((position + 1) * period_width - 1, account), 0.0)
                block_best[position] = max(block_best[position], value)
        for position, value in enumerate(block_best):
            best[position] += value
    return max(0.0, min(base[position] + best[position] for position in range(periods)))


def _probe_targets(
    path: Path,
    base_targets: Sequence[Target],
    account: str,
    level: float,
    years: int,
    period_width: int,
) -> Path:
    """Write a target file with the flow floor and the other targets preserved."""
    periods = years // period_width
    others = [target for target in base_targets if target.account != account]
    floors = [
        Target(
            account=account,
            period=period,
            period_width=period_width,
            minimum=level,
            min_weight=1.0,
        )
        for period in range(1, periods + 1)
    ]
    return write_targets(path, [*others, *floors])


def run_max_flow(
    *,
    dataset: Path,
    targets: Path,
    account: str,
    out_dir: Path,
    years: int = 100,
    period_width: int = 10,
    iterations: int = 100,
    seed: int = 1,
    metaheuristic: str = "sa",
    threads: int = 1,
    probes: int = 8,
    tolerance: float = 0.01,
    high: float | None = None,
    topology: Path | None = None,
    max_opening_ha: float | None = None,
    min_green_up_years: int | None = None,
    core_buffer_m: float | None = None,
    min_core_area_ha: float | None = None,
    constraint_strategy: str = "reject",
) -> dict[str, Any]:
    """Binary-search the highest feasible constant flow floor.

    Parameters
    ----------
    dataset : Path
        The compiled dataset.
    targets : Path
        The base targets. Targets on ``account`` are replaced by the probe floors; all
        other targets are preserved.
    account : str
        The volume account.
    out_dir : Path
        The output directory.
    years : int, optional
        The horizon. Defaults to 100.
    period_width : int, optional
        The accounting period width. Defaults to 10.
    iterations : int, optional
        The iteration budget per probe. Defaults to 100.
    seed : int, optional
        The probe seed. Defaults to 1.
    metaheuristic : str, optional
        The optimizer engine. Defaults to ``"sa"``.
    threads : int, optional
        BLAS threads. Defaults to 1.
    probes : int, optional
        The binary-search probes. Defaults to 8.
    tolerance : float, optional
        The relative shortfall allowed per period. Defaults to 0.01.
    high : float or None, optional
        A known upper bound. None computes the additive envelope.
    topology : Path or None, optional
        The spatial topology.
    max_opening_ha : float or None, optional
        The maximum opening area.
    min_green_up_years : int or None, optional
        The green-up interval.
    core_buffer_m : float or None, optional
        The core-area buffer.
    min_core_area_ha : float or None, optional
        The minimum core area.
    constraint_strategy : str, optional
        The spatial policy for the probes. Defaults to ``"reject"``.

    Returns
    -------
    dict of str to Any
        The ceiling, probes, high bound, and a Markdown report.

    Raises
    ------
    ValueError
        When the horizon, period width, probe count, or tolerance is invalid.
    """
    if period_width < 1 or years < 1 or years % period_width:
        raise ValueError("years must be a positive multiple of period_width")
    if probes < 1:
        raise ValueError("probes must be positive")
    if tolerance < 0.0:
        raise ValueError("tolerance must be zero or positive")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_targets = load_targets(targets)
    optimizer = Optimizer.from_dataset(dataset, OptimizeConfig(years=years, threads=threads))
    initial_high = (
        float(high) if high is not None else high_bound(optimizer, account, years, period_width)
    )
    if initial_high < 0.0:
        raise ValueError("high must be zero or positive")
    upper = initial_high
    low = 0.0
    records: list[Probe] = []
    best: Probe | None = None
    last_config: OptimizeConfig | None = None
    for index in range(probes):
        level = (low + upper) / 2.0
        if level <= 0.0:
            break
        probe_dir = out_dir / "probes" / f"probe-{index:03d}"
        probe_dir.mkdir(parents=True, exist_ok=True)
        target_path = _probe_targets(
            probe_dir / "targets.yaml",
            base_targets,
            account,
            level,
            years,
            period_width,
        )
        config = OptimizeConfig(
            targets_path=str(target_path),
            years=years,
            iterations=iterations,
            seed=seed,
            threads=threads,
            metaheuristic=metaheuristic,
            topology_path=str(topology) if topology is not None else "",
            max_opening_ha=max_opening_ha,
            min_green_up_years=min_green_up_years,
            core_buffer_m=core_buffer_m,
            min_core_area_ha=min_core_area_ha,
            constraint_strategy=constraint_strategy,
        )
        last_config = config
        try:
            summary = Optimizer.from_dataset(dataset, config).run(probe_dir / "run")
            frame = pd.read_csv(probe_dir / "run" / "account_values.csv")
            values = period_values(frame, account, years, period_width)
            feasible = bool(summary.get("constraint_feasible", True)) and all(
                value >= level * (1.0 - tolerance) for value in values.values()
            )
            record = Probe(
                level=level,
                feasible=feasible,
                objective=float(summary.get("incumbent_objective", math.inf)),
                values=values,
                run_dir=str(probe_dir / "run"),
            )
        except Exception as error:
            record = Probe(
                level=level,
                feasible=False,
                objective=None,
                values={},
                run_dir=str(probe_dir / "run"),
                error=str(error),
            )
        records.append(record)
        if record.feasible:
            low = level
            best = record
        else:
            upper = level
    schedule_path: Path | None = None
    if best is not None and best.run_dir:
        source = Path(best.run_dir) / "schedule.csv"
        if source.is_file():
            schedule_path = out_dir / "best-schedule.csv"
            shutil.copyfile(source, schedule_path)
    if schedule_path is None:
        schedule_path = out_dir / "best-schedule.csv"
        schedule_path.write_text("block_id,treatment,offset\n", encoding="utf-8")
    report: dict[str, Any] = {
        "dataset": str(dataset),
        "targets": str(targets),
        "account": account,
        "years": years,
        "period_width": period_width,
        "iterations": iterations,
        "seed": seed,
        "metaheuristic": metaheuristic,
        "constraint_strategy": constraint_strategy,
        "tolerance": tolerance,
        "high_bound": initial_high,
        "ceiling": low,
        "best_probe": best.as_dict() if best is not None else None,
        "best_schedule": str(schedule_path) if schedule_path else None,
        "probes": [record.as_dict() for record in records],
        "feasible": best is not None,
    }
    report["markdown"] = render_markdown(report)
    (out_dir / "max_flow.json").write_text(
        json.dumps({key: value for key, value in report.items() if key != "markdown"}, indent=2),
        encoding="utf-8",
    )
    (out_dir / "max_flow.md").write_text(str(report["markdown"]) + "\n", encoding="utf-8")
    if last_config is not None:
        (out_dir / "probe-config.json").write_text(
            json.dumps(asdict(last_config), indent=2), encoding="utf-8"
        )
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the max-flow result as Markdown.

    Parameters
    ----------
    report : mapping
        A report from :func:`run_max_flow`.

    Returns
    -------
    str
        The report.
    """
    lines = [
        "# Binary-search flow ceiling",
        "",
        f"- Account: `{report['account']}` · periods: {report['years'] // report['period_width']} "
        f"of {report['period_width']} years each",
        f"- Constraint strategy: {report['constraint_strategy']} · tolerance: "
        f"{report['tolerance']:.1%}",
        f"- Additive high bound: {report['high_bound']:.6g}",
        f"- **Advisory ceiling: {report['ceiling']:.6g}**",
        f"- Best schedule: `{report['best_schedule']}`",
        "",
        "| Probe | Level | Feasible | Objective | Per-period values |",
        "| ---: | ---: | --- | ---: | --- |",
    ]
    for index, probe in enumerate(report.get("probes", [])):
        values = ", ".join(
            f"{period}:{value:.6g}" for period, value in sorted(probe["values"].items())
        )
        objective = "" if probe["objective"] is None else f"{probe['objective']:.6g}"
        lines.append(
            f"| {index} | {probe['level']:.6g} | {probe['feasible']} | {objective} | {values} |"
        )
    lines.extend(
        [
            "",
            "The high bound is an additive envelope over block options; the ceiling is the",
            "highest level a finite probe verified. It is advisory, not a certified maximum.",
        ]
    )
    return "\n".join(lines)
