"""Run a portfolio over target-weight vectors and report a Pareto front.

A weighted goal program answers one question: given these relative weights, what is
the least-penalty schedule? Forest-planning decisions usually need the neighbouring
answers too — more volume against more old forest, lower cost against more patch
size. The portfolio re-runs the existing optimizer over a grid of weight factors and
keeps every member's metrics. The Pareto filter in :mod:`ws4.opt.archive` then names
the schedules that are not dominated.

The portfolio is advisory. It is a finite grid, the search is stochastic, and a front
member is one schedule under one budget, not a certified optimum.
"""

from __future__ import annotations

import json
import math
import random
import statistics
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pandas as pd
from fresh_solutions.kernel import Runner

from .archive import Direction, Elite, EliteArchive, pareto_front
from .calibrate import write_targets
from .engine import OptimizeConfig, Optimizer, load_schedule_csv
from .objective import Target, load_targets


@dataclass(frozen=True)
class PortfolioMember:
    """One portfolio run.

    Attributes
    ----------
    label : str
        The stable member label, such as ``member-000``.
    factors : mapping of str to float
        The weight factor per account.
    seed : int
        The search seed.
    targets_path : Path
        The scaled targets file for this member.
    run_dir : Path
        The run directory.
    objective : float or None
        The incumbent objective, or None when the run failed.
    metrics : mapping of str to float
        The realized metrics, including ``objective``.
    schedule_path : Path or None
        The incumbent schedule, or None when the run failed.
    status : str
        ``"ok"``, ``"failed"``, or the run's own status.
    error : str
        The failure text, empty on success.
    """

    label: str
    factors: Mapping[str, float]
    seed: int
    targets_path: Path
    run_dir: Path
    objective: float | None
    metrics: Mapping[str, float]
    schedule_path: Path | None
    status: str
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready record.

        Returns
        -------
        dict of str to object
            The member's identity, factors, objective, metrics, paths, and status.
        """

        def finite(value: float) -> float | None:
            """Return a JSON-safe rounded value, or None for an infinity."""
            return round(float(value), 6) if math.isfinite(float(value)) else None

        return {
            "label": self.label,
            "factors": {key: round(float(value), 6) for key, value in sorted(self.factors.items())},
            "seed": self.seed,
            "targets": str(self.targets_path),
            "run_dir": str(self.run_dir),
            "objective": None if self.objective is None else finite(self.objective),
            "metrics": {key: finite(float(value)) for key, value in sorted(self.metrics.items())},
            "schedule": str(self.schedule_path) if self.schedule_path else None,
            "status": self.status,
            "error": self.error,
        }


def parse_vary(text: str) -> dict[str, tuple[float, ...]]:
    """Parse ``account=f1,f2;account2=f3`` into weight factors.

    Parameters
    ----------
    text : str
        Semicolon-separated account groups, each ``account=factor,factor``. A factor may be
        written as ``account@period`` to scale only one target period.

    Returns
    -------
    dict of str to tuple of float
        The ordered factors per account key.

    Raises
    ------
    ValueError
        When a group has no account, no factors, a non-positive factor, or a duplicate account.
    """
    groups: dict[str, tuple[float, ...]] = {}
    for group in text.split(";"):
        group = group.strip()
        if not group:
            continue
        account, separator, raw_factors = group.partition("=")
        account = account.strip()
        if not separator or not account:
            raise ValueError(f"weight group {group!r} needs account=factor,factor")
        factors = tuple(float(item) for item in raw_factors.split(",") if item.strip())
        if not factors:
            raise ValueError(f"weight group {group!r} has no factors")
        if any(not math.isfinite(value) or value <= 0.0 for value in factors):
            raise ValueError(f"weight group {group!r} has a non-positive or non-finite factor")
        if account in groups:
            raise ValueError(f"weight account {account!r} is repeated")
        groups[account] = factors
    if not groups:
        raise ValueError("expected at least one account=factor,factor group")
    return groups


def weight_vectors(
    vary: Mapping[str, Sequence[float]], *, max_members: int = 64
) -> list[dict[str, float]]:
    """Return the Cartesian product of the weight factors.

    Parameters
    ----------
    vary : mapping of str to sequence of float
        The factors per account key.
    max_members : int, optional
        The most vectors to return. A larger product is an error rather than a silent trim.

    Returns
    -------
    list of dict of str to float
        One factor mapping per member, in deterministic order.

    Raises
    ------
    ValueError
        When the product is empty or over ``max_members``.
    """
    if max_members < 1:
        raise ValueError("max_members must be positive")
    keys = list(vary)
    for key in keys:
        if not vary[key]:
            raise ValueError(f"account {key!r} has no factors")
    vectors: list[dict[str, float]] = [{}]
    for key in keys:
        vectors = [{**vector, key: float(factor)} for vector in vectors for factor in vary[key]]
        if len(vectors) > max_members:
            raise ValueError(f"weight grid has {len(vectors)} members, over the {max_members} cap")
    return vectors


def weight_grid_size(vary: Mapping[str, Sequence[float]]) -> int:
    """Return the number of vectors in the Cartesian product.

    Parameters
    ----------
    vary : mapping of str to sequence of float
        The factors per account key.

    Returns
    -------
    int
        The product of the factor counts.

    Raises
    ------
    ValueError
        When a group has no factors.
    """
    size = 1
    for key, factors in vary.items():
        if not factors:
            raise ValueError(f"account {key!r} has no factors")
        size *= len(factors)
    return size


def weight_vector_at(vary: Mapping[str, Sequence[float]], index: int) -> dict[str, float]:
    """Return one grid vector without materializing the whole Cartesian product.

    The order matches :func:`weight_vectors`: the last group varies fastest.

    Parameters
    ----------
    vary : mapping of str to sequence of float
        The factors per account key.
    index : int
        The zero-based grid position.

    Returns
    -------
    dict of str to float
        The factor mapping at that position.

    Raises
    ------
    ValueError
        When the index is outside the grid or a group has no factors.
    """
    total = weight_grid_size(vary)
    if index < 0 or index >= total:
        raise ValueError(f"weight-grid index {index} is outside 0..{total - 1}")
    keys = list(vary)
    factors: dict[str, float] = {}
    remaining = index
    for key in reversed(keys):
        values = vary[key]
        factors[key] = float(values[remaining % len(values)])
        remaining //= len(values)
    return {key: factors[key] for key in keys}


def sample_weight_vectors(
    vary: Mapping[str, Sequence[float]],
    *,
    max_members: int = 64,
    mode: str = "grid",
    seed: int = 1,
) -> list[dict[str, float]]:
    """Return a bounded grid or seeded random sample of weight vectors.

    A 5-7 target scan can exceed a sensible number of optimizer runs. ``grid`` keeps
    the exact Cartesian product and refuses an oversized one; ``random`` samples
    distinct grid positions deterministically without materializing the product.

    Parameters
    ----------
    vary : mapping of str to sequence of float
        The factors per account key.
    max_members : int, optional
        The most vectors to return. Defaults to 64.
    mode : str, optional
        ``"grid"`` or ``"random"``. Defaults to ``"grid"``.
    seed : int, optional
        The random sample seed. Defaults to 1.

    Returns
    -------
    list of dict of str to float
        One factor mapping per member.

    Raises
    ------
    ValueError
        When the mode is unknown, the grid is oversized in grid mode, or the cap is
        not positive.
    """
    if mode not in {"grid", "random"}:
        raise ValueError(f"unknown weight-sampling mode: {mode!r}")
    if max_members < 1:
        raise ValueError("max_members must be positive")
    total = weight_grid_size(vary)
    if mode == "grid":
        return weight_vectors(vary, max_members=max_members)
    if total <= max_members:
        return weight_vectors(vary, max_members=max_members)
    indices = sorted(random.Random(seed).sample(range(total), max_members))
    return [weight_vector_at(vary, index) for index in indices]


def _factor_for(target: Target, factors: Mapping[str, float]) -> float | None:
    """Return the factor that applies to one target, or None."""
    if target.account in factors:
        return float(factors[target.account])
    key = f"{target.account}@{target.period}" if target.period is not None else None
    if key is not None and key in factors:
        return float(factors[key])
    return None


def scale_targets(targets: Sequence[Target], factors: Mapping[str, float]) -> list[Target]:
    """Multiply the matching targets' minimum and maximum weights.

    Parameters
    ----------
    targets : sequence of Target
        The base targets.
    factors : mapping of str to float
        A factor per account, or per ``account@period`` key. A factor of one is the baseline.

    Returns
    -------
    list of Target
        New targets. An account without a factor is unchanged.

    Raises
    ------
    ValueError
        When a factor does not name a target, is not finite, or is not positive.
    """
    matched: set[str] = set()
    scaled: list[Target] = []
    for target in targets:
        factor = _factor_for(target, factors)
        if factor is None:
            scaled.append(target)
            continue
        if not math.isfinite(factor) or factor <= 0.0:
            raise ValueError(f"target {target.account!r} has a non-positive factor")
        matched.add(target.account)
        scaled.append(
            replace(
                target,
                min_weight=target.min_weight * factor,
                max_weight=target.max_weight * factor,
            )
        )
    missing = {key for key in factors if key.split("@", 1)[0] not in matched and key not in matched}
    if missing:
        raise ValueError(f"weight factor names no target: {', '.join(sorted(missing))}")
    return scaled


def metrics_from_accounts(frame: pd.DataFrame, names: Sequence[str]) -> dict[str, float]:
    """Read named metrics from an ``account_values.csv`` frame.

    Parameters
    ----------
    frame : pandas.DataFrame
        A frame with ``offset``, ``account``, and ``value`` columns.
    names : sequence of str
        Metric names. ``account`` reads the last offset, ``account@<offset>`` reads one year,
        and ``account@sum`` sums the horizon.

    Returns
    -------
    dict of str to float
        The value per requested name.

    Raises
    ------
    ValueError
        When a requested account or offset is absent.
    """
    required = {"offset", "account", "value"}
    missing_columns = required - set(frame.columns)
    if missing_columns:
        raise ValueError(f"account values are missing: {', '.join(sorted(missing_columns))}")
    values: dict[str, float] = {}
    for name in names:
        account, separator, selector = name.partition("@")
        subset = frame[frame["account"].astype(str) == account]
        if subset.empty:
            raise ValueError(f"metric {name!r} was not found in the account values")
        if not separator:
            offset = float(subset["offset"].astype(float).max())
            rows = subset[subset["offset"].astype(float) == offset]
            values[name] = float(rows["value"].astype(float).sum())
        elif selector == "sum":
            values[name] = float(subset["value"].astype(float).sum())
        elif selector == "end":
            offset = float(subset["offset"].astype(float).max())
            rows = subset[subset["offset"].astype(float) == offset]
            values[name] = float(rows["value"].astype(float).sum())
        else:
            try:
                offset = float(selector)
            except ValueError as error:
                raise ValueError(f"metric {name!r} has an unknown selector") from error
            rows = subset[subset["offset"].astype(float) == offset]
            if rows.empty:
                raise ValueError(f"metric {name!r} has no value at offset {offset:g}")
            values[name] = float(rows["value"].astype(float).sum())
    return values


def metrics_from_run(run_dir: Path, names: Sequence[str]) -> dict[str, float]:
    """Read realized metrics from a run's account and product tables.

    The optimizer writes level accounts to ``account_values.csv`` and product accounts
    to ``product_values.csv``. A metric selector should not have to know which table
    produced the account.

    Parameters
    ----------
    run_dir : Path
        The completed run directory.
    names : sequence of str
        Metric selectors accepted by :func:`metrics_from_accounts`.

    Returns
    -------
    dict of str to float
        The value per requested metric.
    """
    frames: list[pd.DataFrame] = []
    for filename in ("account_values.csv", "product_values.csv"):
        path = Path(run_dir) / filename
        if path.is_file():
            frames.append(pd.read_csv(path))
    if not frames:
        raise ValueError("the run has no account_values.csv or product_values.csv")
    frame = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    return metrics_from_accounts(frame, names)


def parse_directions(text: str | None, metrics: Sequence[str]) -> dict[str, Direction]:
    """Return the direction per metric, defaulting every unnamed metric to ``max``.

    Parameters
    ----------
    text : str or None
        Semicolon-separated ``metric=min`` or ``metric=max`` pairs.
    metrics : sequence of str
        The metrics that need a direction.

    Returns
    -------
    dict of str to str
        The direction per metric, plus ``objective`` at ``min``.

    Raises
    ------
    ValueError
        When a direction is unknown or names no metric.
    """
    directions: dict[str, Direction] = {"objective": "min"}
    for metric in metrics:
        directions[metric] = "max"
    if text:
        for part in text.split(";"):
            part = part.strip()
            if not part:
                continue
            metric, separator, direction = part.partition("=")
            metric, direction = metric.strip(), direction.strip()
            if not separator or direction not in {"min", "max"}:
                raise ValueError(f"direction {part!r} needs metric=min|max")
            if metric not in directions:
                raise ValueError(f"direction names unknown metric {metric!r}")
            directions[metric] = direction  # type: ignore[assignment]
    return directions


@dataclass(frozen=True)
class _MemberSpec:
    """One member run before it has a result."""

    index: int
    label: str
    factors: Mapping[str, float]
    seed: int
    targets_path: Path
    run_dir: Path
    config: OptimizeConfig


def _run_member(
    spec: _MemberSpec,
    dataset: Path,
    runner_factory: Callable[[Path, OptimizeConfig], Runner] | None,
) -> tuple[int, dict[str, Any] | None, str]:
    """Run one member, returning its summary or failure text.

    The function is top-level and picklable so the default optimizer can run in a
    process pool. A custom runner factory is also passed through; callers that use a
    closure should keep ``workers`` at one.
    """
    try:
        factory = runner_factory or Optimizer.from_dataset
        summary = factory(dataset, spec.config).run(spec.run_dir)
        return spec.index, summary, ""
    except Exception as error:
        return spec.index, None, str(error)


def _run_parallel(
    specs: Sequence[_MemberSpec],
    dataset: Path,
    workers: int,
    runner_factory: Callable[[Path, OptimizeConfig], Runner] | None,
) -> list[tuple[int, dict[str, Any] | None, str]]:
    """Run member specs in a bounded process pool, preserving input order."""
    results: list[tuple[int, dict[str, Any] | None, str]] = []
    with ProcessPoolExecutor(max_workers=min(workers, len(specs))) as pool:
        futures = {pool.submit(_run_member, spec, dataset, runner_factory): spec for spec in specs}
        for future in as_completed(futures):
            spec = futures[future]
            try:
                results.append(future.result())
            except Exception as error:
                results.append((spec.index, None, str(error)))
    return sorted(results, key=lambda item: item[0])


def _member_record(
    *,
    label: str,
    factors: Mapping[str, float],
    seed: int,
    targets_path: Path,
    run_dir: Path,
    objective: float | None,
    metrics: Mapping[str, float],
    schedule_path: Path | None,
    status: str,
    error: str = "",
) -> PortfolioMember:
    """Build a member record with normalized paths."""
    return PortfolioMember(
        label=label,
        factors=dict(factors),
        seed=seed,
        targets_path=targets_path,
        run_dir=run_dir,
        objective=objective,
        metrics=dict(metrics),
        schedule_path=schedule_path,
        status=status,
        error=error,
    )


def run_portfolio(
    *,
    dataset: Path,
    targets: Path,
    out_dir: Path,
    vary: Mapping[str, Sequence[float]],
    metrics: Sequence[str],
    seeds: Sequence[int] = (1,),
    iterations: int = 200,
    years: int = 50,
    threads: int = 1,
    metaheuristic: str = "sa",
    directions: Mapping[str, Direction] | None = None,
    archive_size: int = 20,
    max_members: int = 64,
    weight_mode: str = "grid",
    sample_seed: int = 1,
    workers: int = 1,
    initial_schedule: Path | None = None,
    runner_factory: Callable[[Path, OptimizeConfig], Runner] | None = None,
) -> dict[str, Any]:
    """Run the portfolio and write its members, front, and reports.

    Parameters
    ----------
    dataset : Path
        Compiled ws4 dataset.
    targets : Path
        The base targets YAML.
    out_dir : Path
        The portfolio directory.
    vary : mapping of str to sequence of float
        The weight factors per account.
    metrics : sequence of str
        The realized account metrics that define the front.
    seeds : sequence of int, optional
        One run per seed per weight vector. Defaults to ``(1,)``.
    iterations : int, optional
        The iteration budget per run. Defaults to 200.
    years : int, optional
        The simulation horizon. Defaults to 50.
    threads : int, optional
        BLAS threads per run. Defaults to 1.
    metaheuristic : str, optional
        The engine name. Defaults to ``"sa"``.
    directions : mapping of str to str or None, optional
        The direction per metric. Missing metrics default to ``max`` and ``objective`` is
        always ``min``.
    archive_size : int, optional
        The archive capacity. Defaults to 20.
    max_members : int, optional
        The most weight vectors. Defaults to 64.
    weight_mode : str, optional
        ``"grid"`` keeps the exact Cartesian product; ``"random"`` samples distinct
        grid positions deterministically when the product is over the cap. Defaults
        to ``"grid"``.
    sample_seed : int, optional
        The deterministic sample seed for ``weight_mode="random"``. Defaults to 1.
    workers : int, optional
        Process workers. The default of one keeps memory bounded; each worker loads
        its own dataset, so raise it only when the host has memory for the model.
    initial_schedule : Path or None, optional
        A schedule used as the starting point for every member. Without it, a search
        from an empty schedule can fail flow targets that need a primed account.
    runner_factory : callable or None, optional
        Builds a runner from the dataset and a configuration. Defaults to
        :meth:`Optimizer.from_dataset`; tests substitute a fake. With more than one
        worker the factory must be picklable.

    Returns
    -------
    dict of str to Any
        The members, front labels, directions, and a Markdown report.

    Raises
    ------
    ValueError
        When no metrics are named, a seed list is empty, the worker count is invalid,
        or the weight sample is invalid.
    """
    if not metrics:
        raise ValueError("at least one metric is required")
    if "objective" in metrics:
        raise ValueError("'objective' is reserved and cannot be a metric name")
    if not seeds:
        raise ValueError("at least one seed is required")
    if workers < 1:
        raise ValueError("workers must be at least one")
    dataset = Path(dataset)
    vectors = sample_weight_vectors(
        vary,
        max_members=max_members,
        mode=weight_mode,
        seed=sample_seed,
    )
    supplied = directions or {}
    directions = {metric: supplied.get(metric, "max") for metric in metrics}
    directions["objective"] = "min"
    base_targets = load_targets(targets)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = EliteArchive(capacity=archive_size, directions=directions)
    records: list[PortfolioMember] = []
    specs: list[_MemberSpec] = []
    for index, factors in enumerate(vectors):
        label = f"member-{index:03d}"
        member_dir = out_dir / label
        member_dir.mkdir(parents=True, exist_ok=True)
        scaled_path = member_dir / "targets.yaml"
        write_targets(scaled_path, scale_targets(base_targets, factors))
        for seed in seeds:
            run_dir = member_dir / f"seed-{seed:03d}"
            specs.append(
                _MemberSpec(
                    index=len(specs),
                    label=label,
                    factors=factors,
                    seed=seed,
                    targets_path=scaled_path,
                    run_dir=run_dir,
                    config=OptimizeConfig(
                        targets_path=str(scaled_path),
                        years=years,
                        iterations=iterations,
                        threads=threads,
                        metaheuristic=metaheuristic,
                        seed=seed,
                        initial_schedule_path=str(initial_schedule) if initial_schedule else "",
                    ),
                )
            )
    results = (
        _run_parallel(specs, dataset, workers, runner_factory)
        if workers > 1 and len(specs) > 1
        else [_run_member(spec, dataset, runner_factory) for spec in specs]
    )
    by_index = {spec.index: spec for spec in specs}
    for index, summary, error in results:
        spec = by_index[index]
        try:
            if summary is None:
                raise RuntimeError(error or "the member failed")
            if "incumbent_objective" not in summary:
                raise ValueError("the run summary has no incumbent_objective")
            objective = float(summary["incumbent_objective"])
            measured = metrics_from_run(spec.run_dir, metrics)
            measured["objective"] = objective
            schedule_path = spec.run_dir / "schedule.csv"
            schedule = load_schedule_csv(schedule_path)
            archive.add(
                Elite(
                    objective=objective,
                    metrics=measured,
                    schedule=schedule,
                    source=f"{spec.label}:{spec.seed:03d}",
                    seed=spec.seed,
                )
            )
            records.append(
                _member_record(
                    label=spec.label,
                    factors=spec.factors,
                    seed=spec.seed,
                    targets_path=spec.targets_path,
                    run_dir=spec.run_dir,
                    objective=objective,
                    metrics=measured,
                    schedule_path=schedule_path,
                    status=str(summary.get("status", "ok")),
                )
            )
        except Exception as error:
            records.append(
                _member_record(
                    label=spec.label,
                    factors=spec.factors,
                    seed=spec.seed,
                    targets_path=spec.targets_path,
                    run_dir=spec.run_dir,
                    objective=None,
                    metrics={},
                    schedule_path=None,
                    status="failed",
                    error=str(error),
                )
            )
    # The schedule archive is bounded, but the reported front is not: every successful
    # member is a candidate, so a capacity trim cannot hide a trade-off from the browser.
    front_directions = {metric: directions[metric] for metric in metrics}
    front = pareto_front(
        [
            Elite(
                objective=float(record.objective),
                metrics={key: float(record.metrics[key]) for key in metrics},
                schedule={},
                source=f"{record.label}:{record.seed:03d}",
                seed=record.seed,
            )
            for record in records
            if record.objective is not None
        ],
        front_directions,
    )
    front_labels = {elite.source for elite in front}
    archive_paths = archive.write(out_dir / "archive")
    front_path = out_dir / "front.csv"
    pd.DataFrame(
        [
            {
                "label": elite.source,
                "objective": elite.objective,
                **{key: elite.metrics[key] for key in metrics},
            }
            for elite in front
        ]
    ).to_csv(front_path, index=False)
    report: dict[str, Any] = {
        "dataset": str(dataset),
        "targets": str(targets),
        "vary": {key: list(values) for key, values in vary.items()},
        "seeds": list(seeds),
        "iterations": iterations,
        "years": years,
        "metaheuristic": metaheuristic,
        "weight_mode": weight_mode,
        "sample_seed": sample_seed,
        "workers": workers,
        "initial_schedule": str(initial_schedule) if initial_schedule else None,
        "vector_count": len(vectors),
        "metrics": list(metrics),
        "directions": directions,
        "members": [record.as_dict() for record in records],
        "front": [elite.source for elite in front],
        "front_size": len(front),
        "outcome_front": [elite.source for elite in front],
        "outcome_front_size": len(front),
        "front_path": str(front_path),
        "archive": {key: str(path) for key, path in archive_paths.items()},
        "failures": sum(1 for record in records if record.status == "failed"),
        "markdown": render_markdown(records, front_labels, directions),
    }
    (out_dir / "portfolio.json").write_text(
        json.dumps({key: value for key, value in report.items() if key != "markdown"}, indent=2),
        encoding="utf-8",
    )
    (out_dir / "portfolio.md").write_text(str(report["markdown"]) + "\n", encoding="utf-8")
    return report


def render_markdown(
    records: Sequence[PortfolioMember],
    front_labels: set[str],
    directions: Mapping[str, str],
) -> str:
    """Render the portfolio as a Markdown table.

    Parameters
    ----------
    records : sequence of PortfolioMember
        The member records.
    front_labels : set of str
        The labels on the nondominated front.
    directions : mapping of str to str
        The metric directions, used in the heading.

    Returns
    -------
    str
        The report.
    """
    metric_names = [key for key in directions if key != "objective"]
    lines = [
        "# Search portfolio",
        "",
        f"- Members: {len(records)} · front: {len(front_labels)}",
        f"- Directions: {', '.join(f'{key} ({value})' for key, value in directions.items())}",
        "",
        "| Member | Seed | Objective | " + " | ".join(metric_names) + " | Front |",
        "| --- | ---: | ---: | " + " | ".join("---:" for _ in metric_names) + " | --- |",
    ]
    for record in records:
        front = "yes" if f"{record.label}:{record.seed:03d}" in front_labels else ""
        metric_cells = " | ".join(
            f"{record.metrics.get(name, float('nan')):.6g}" for name in metric_names
        )
        objective = "" if record.objective is None else f"{record.objective:.6g}"
        lines.append(f"| {record.label} | {record.seed} | {objective} | {metric_cells} | {front} |")
    failed = [record for record in records if record.status == "failed"]
    if failed:
        lines.extend(["", "## Failures", ""])
        for record in failed:
            lines.append(f"- {record.label} seed {record.seed}: {record.error}")
    lines.extend(
        [
            "",
            "The front is a finite sample under one budget and one seed per member.",
            "It is advisory, not a certified optimum.",
        ]
    )
    return "\n".join(lines)


def summarize_members(records: Sequence[PortfolioMember]) -> dict[str, float | int]:
    """Return the objective distribution across successful members.

    Parameters
    ----------
    records : sequence of PortfolioMember
        The member records.

    Returns
    -------
    dict of str to float or int
        The number of runs, best, median, mean, and worst objective.
    """
    objectives = [record.objective for record in records if record.objective is not None]
    if not objectives:
        return {"runs": 0}
    return {
        "runs": len(objectives),
        "best": round(min(objectives), 6),
        "median": round(statistics.median(objectives), 6),
        "mean": round(statistics.mean(objectives), 6),
        "worst": round(max(objectives), 6),
    }
