"""A grid and random tuner over the optimizer's scalar parameters.

The tuner is orchestration, not a new search: every candidate is an
:class:`~ws4.opt.engine.OptimizeConfig` with a few fields replaced, run through the
same :class:`~ws4.opt.engine.Optimizer` on the same dataset, targets, seed set, and
iteration budget. A candidate is ranked by its best objective and then its median, so
a lucky seed does not win on its own. The report is advisory: it compares a finite
budget, not a certified optimum.
"""

from __future__ import annotations

import itertools
import json
import math
import random
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any, Protocol

from .engine import OptimizeConfig, Optimizer

#: Configuration fields the tuner may not change: paths and the evaluation seed.
_EXCLUDED = {
    "targets_path",
    "initial_schedule_path",
    "control_path",
    "weights_path",
    "topology_path",
    "route_config_path",
    "edge_elements_path",
    "patch_accounts_path",
    "spread_accounts_path",
    "block_coordinates_path",
    "seed",
}

#: String fields with a closed set of values.
_CHOICES: dict[str, set[str]] = {
    "metaheuristic": {"sa", "tabu", "ils", "threshold"},
    "cooling_mode": {"geometric", "adaptive"},
}


class Runner(Protocol):
    """The part of an optimizer the tuner needs."""

    def run(self, out_dir: Path) -> dict[str, Any]:
        """Run one candidate and write its outputs.

        Parameters
        ----------
        out_dir : Path
            The run directory.

        Returns
        -------
        dict of str to Any
            The run summary.
        """


def _field_types() -> dict[str, type[Any] | None]:
    """Return the declared type per configuration field, or None when unresolved."""
    result: dict[str, type[Any] | None] = {}
    for item in fields(OptimizeConfig):
        default = item.default
        result[item.name] = type(default) if default is not None else None
    return result


def validate_space(space: Mapping[str, Sequence[Any]]) -> dict[str, list[Any]]:
    """Validate a parameter space before any run.

    Parameters
    ----------
    space : mapping of str to sequence
        The candidate values per field.

    Returns
    -------
    dict of str to list
        The normalized space.

    Raises
    ------
    ValueError
        When a field is unknown, excluded, has no values, has a duplicate value, or a value
        does not match the field's scalar type or closed choices.
    """
    types = _field_types()
    normalized: dict[str, list[Any]] = {}
    for name, values in space.items():
        if name not in types:
            raise ValueError(f"unknown configuration field {name!r}")
        if name in _EXCLUDED:
            raise ValueError(f"field {name!r} is not tunable")
        candidates = list(values)
        if not candidates:
            raise ValueError(f"field {name!r} has no values")
        seen: list[Any] = []
        for value in candidates:
            if isinstance(value, (list, dict, tuple, set)):
                raise ValueError(f"field {name!r} needs scalar values")
            if value in seen:
                raise ValueError(f"field {name!r} repeats a value")
            seen.append(value)
            expected = types[name]
            if expected is bool and not isinstance(value, bool):
                raise ValueError(f"field {name!r} needs boolean values")
            if expected is int and (not isinstance(value, int) or isinstance(value, bool)):
                raise ValueError(f"field {name!r} needs integer values")
            if expected is float and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
            ):
                raise ValueError(f"field {name!r} needs numeric values")
            if expected is str and not isinstance(value, str):
                raise ValueError(f"field {name!r} needs string values")
        choices = _CHOICES.get(name)
        if choices is not None:
            unknown = [value for value in candidates if value not in choices]
            if unknown:
                raise ValueError(
                    f"field {name!r} has unknown value(s): {', '.join(map(str, unknown))}"
                )
        normalized[name] = candidates
    if not normalized:
        raise ValueError("the parameter space is empty")
    return normalized


def candidates(
    space: Mapping[str, Sequence[Any]],
    *,
    mode: str = "grid",
    budget: int = 16,
    seed: int = 42,
    max_candidates: int = 64,
) -> list[dict[str, Any]]:
    """Enumerate or sample the candidate configurations.

    Parameters
    ----------
    space : mapping of str to sequence
        The validated parameter space.
    mode : str, optional
        ``"grid"`` for the full product or ``"random"`` for a seeded sample. Defaults to
        ``"grid"``.
    budget : int, optional
        The most random candidates. Defaults to 16.
    seed : int, optional
        The random sampler seed. Defaults to 42.
    max_candidates : int, optional
        The hard cap for a grid. Defaults to 64.

    Returns
    -------
    list of dict of str to object
        The candidate parameter mappings, in deterministic order.

    Raises
    ------
    ValueError
        When the mode is unknown, the budget is not positive, or the grid is over the cap.
    """
    resolved = validate_space(space)
    keys = list(resolved)
    total = math.prod(len(resolved[key]) for key in keys)
    if mode == "grid":
        if total > max_candidates:
            raise ValueError(f"grid has {total} candidates, over the {max_candidates} cap")
        return [
            dict(zip(keys, values, strict=True))
            for values in itertools.product(*(resolved[key] for key in keys))
        ]
    if mode != "random":
        raise ValueError(f"unknown tuning mode {mode!r}; use grid or random")
    if budget < 1:
        raise ValueError("budget must be positive")
    count = min(budget, total)
    rng = random.Random(seed)
    combinations = list(itertools.product(*(resolved[key] for key in keys)))
    picked = rng.sample(combinations, count)
    return [dict(zip(keys, values, strict=True)) for values in picked]


def _run_rows(
    *,
    dataset: Path,
    base: OptimizeConfig,
    parameters: Mapping[str, Any],
    out_dir: Path,
    seeds: Sequence[int],
    runner_factory: Callable[[Path, OptimizeConfig], Runner],
) -> dict[str, Any]:
    """Run one candidate over its seeds and return its row."""
    objectives: list[float] = []
    failures: list[str] = []
    seed_records: list[dict[str, Any]] = []
    for seed in seeds:
        run_dir = out_dir / f"seed-{seed:03d}"
        try:
            config = replace(base, seed=seed, **dict(parameters))
            summary = runner_factory(dataset, config).run(run_dir)
            if "incumbent_objective" not in summary:
                raise ValueError("the run summary has no incumbent_objective")
            objective = float(summary["incumbent_objective"])
            objectives.append(objective)
            seed_records.append({"seed": seed, "objective": objective, "status": "ok"})
        except Exception as error:
            failures.append(f"seed {seed}: {error}")
            seed_records.append({"seed": seed, "objective": None, "status": "failed"})
    return {
        "parameters": dict(parameters),
        "seeds": seed_records,
        "best": round(min(objectives), 6) if objectives else None,
        "median": round(statistics.median(objectives), 6) if objectives else None,
        "mean": round(statistics.mean(objectives), 6) if objectives else None,
        "runs": len(objectives),
        "failures": failures,
    }


def run_tuning(
    *,
    dataset: Path,
    targets: Path,
    out_dir: Path,
    space: Mapping[str, Sequence[Any]],
    mode: str = "grid",
    budget: int = 16,
    seeds: Sequence[int] = (1,),
    base: OptimizeConfig | None = None,
    iterations: int = 200,
    years: int = 50,
    threads: int = 1,
    random_seed: int = 42,
    max_candidates: int = 64,
    runner_factory: Callable[[Path, OptimizeConfig], Runner] = Optimizer.from_dataset,
) -> dict[str, Any]:
    """Run the tuner and write its candidates, ranking, and winner.

    Parameters
    ----------
    dataset : Path
        Compiled ws4 dataset.
    targets : Path
        The targets YAML.
    out_dir : Path
        The tuning directory.
    space : mapping of str to sequence
        The candidate values per configuration field.
    mode : str, optional
        ``"grid"`` or ``"random"``. Defaults to ``"grid"``.
    budget : int, optional
        The random-mode sample size. Defaults to 16.
    seeds : sequence of int, optional
        One run per seed per candidate. Defaults to ``(1,)``.
    base : OptimizeConfig or None, optional
        The base configuration. Defaults to a fresh configuration with the targets, horizon,
        iteration budget, thread count, and seed set.
    iterations : int, optional
        The iteration budget when ``base`` is None. Defaults to 200.
    years : int, optional
        The horizon when ``base`` is None. Defaults to 50.
    threads : int, optional
        BLAS threads when ``base`` is None. Defaults to 1.
    random_seed : int, optional
        The sampler seed. Defaults to 42.
    max_candidates : int, optional
        The grid cap. Defaults to 64.
    runner_factory : callable, optional
        Builds a runner from the dataset and a configuration. Defaults to
        :meth:`Optimizer.from_dataset`; tests substitute a fake.

    Returns
    -------
    dict of str to Any
        The candidates, winner, failures, and a Markdown report.

    Raises
    ------
    ValueError
        When the seeds are empty or the base configuration is incompatible with the space.
    """
    if not seeds:
        raise ValueError("at least one seed is required")
    resolved = validate_space(space)
    grid = candidates(
        resolved,
        mode=mode,
        budget=budget,
        seed=random_seed,
        max_candidates=max_candidates,
    )
    base = base or OptimizeConfig(
        targets_path=str(targets),
        years=years,
        iterations=iterations,
        threads=threads,
    )
    if not base.targets_path:
        base = replace(base, targets_path=str(targets))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for index, parameters in enumerate(grid):
        candidate_dir = out_dir / f"candidate-{index:03d}"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        (candidate_dir / "parameters.json").write_text(
            json.dumps(parameters, indent=2, sort_keys=True), encoding="utf-8"
        )
        row = _run_rows(
            dataset=dataset,
            base=base,
            parameters=parameters,
            out_dir=candidate_dir,
            seeds=seeds,
            runner_factory=runner_factory,
        )
        row["label"] = f"candidate-{index:03d}"
        rows.append(row)
    ranked = sorted(
        (row for row in rows if row["best"] is not None),
        key=lambda row: (float(row["best"]), float(row["median"] or 0.0), row["label"]),
    )
    winner = ranked[0] if ranked else None
    report: dict[str, Any] = {
        "dataset": str(dataset),
        "targets": str(targets),
        "space": {key: list(values) for key, values in resolved.items()},
        "mode": mode,
        "budget": budget,
        "seeds": list(seeds),
        "base_config": asdict(base),
        "candidates": rows,
        "ranking": [row["label"] for row in ranked],
        "winner": winner,
        "failures": sum(1 for row in rows if row["failures"]),
        "markdown": render_markdown(rows, ranked),
    }
    (out_dir / "tuning.json").write_text(
        json.dumps({key: value for key, value in report.items() if key != "markdown"}, indent=2),
        encoding="utf-8",
    )
    (out_dir / "tuning.md").write_text(str(report["markdown"]) + "\n", encoding="utf-8")
    if winner is not None:
        (out_dir / "best.json").write_text(
            json.dumps(winner, indent=2, sort_keys=True), encoding="utf-8"
        )
    return report


def render_markdown(rows: Sequence[Mapping[str, Any]], ranked: Sequence[Mapping[str, Any]]) -> str:
    """Render the tuning result as a Markdown table.

    Parameters
    ----------
    rows : sequence of mapping
        Every candidate row.
    ranked : sequence of mapping
        The successful rows in rank order.

    Returns
    -------
    str
        The report.
    """
    lines = [
        "# Search tuner",
        "",
        f"- Candidates: {len(rows)} · ranked: {len(ranked)}",
        "",
        "| Candidate | Parameters | Runs | Best | Median | Failures |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        parameters = ", ".join(
            f"{key}={value}" for key, value in sorted(dict(row["parameters"]).items())
        )
        best = "" if row["best"] is None else f"{row['best']:.6g}"
        median = "" if row["median"] is None else f"{row['median']:.6g}"
        lines.append(
            f"| {row['label']} | {parameters} | {row['runs']} | {best} | {median} | "
            f"{len(row['failures'])} |"
        )
    if ranked:
        lines.extend(
            [
                "",
                f"Winner: **{ranked[0]['label']}** with best {ranked[0]['best']} and "
                f"median {ranked[0]['median']}.",
            ]
        )
    failures = [(row["label"], failure) for row in rows for failure in row["failures"]]
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {label}: {failure}" for label, failure in failures)
    lines.extend(
        [
            "",
            "The ranking is a finite budget on a stochastic search; it is advisory, not a",
            "certified optimum.",
        ]
    )
    return "\n".join(lines)
