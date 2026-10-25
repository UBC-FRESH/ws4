#!/usr/bin/env python3
"""Run a seeded multi-engine validation sweep over a compiled dataset.

The harness runs the same targets, horizon, and iteration budget through several
engines and seeds, then reports the distribution of incumbents. It is an
orchestrator, not a new solver: it calls the same ``Optimizer`` the CLI uses, so a
reported result can be reproduced with the equivalent ``ws4 optimize`` command.

With ``--mip-bound`` the MIP lower bound and gap are recorded for each run. The
report is advisory; it does not change a schedule.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ws4.opt.engine import OptimizeConfig, Optimizer

ENGINES: tuple[str, ...] = ("sa", "tabu", "ils")


class Runner(Protocol):
    """The part of an optimizer the harness needs."""

    def run(self, out_dir: Path) -> dict[str, object]:
        """Run the search and return its summary.

        Parameters
        ----------
        out_dir : Path
            Directory for the run's outputs.

        Returns
        -------
        dict of str to object
            The run summary.
        """


def _parse_csv(text: str, *, allowed: Sequence[str] | None = None) -> list[str]:
    """Split a comma list, rejecting empty values and unknown choices."""
    values = [item.strip() for item in text.split(",") if item.strip()]
    if not values:
        raise ValueError("expected at least one value")
    if allowed is not None:
        unknown = [value for value in values if value not in allowed]
        if unknown:
            raise ValueError(f"unknown value(s): {', '.join(unknown)}")
    return values


def _as_float(value: object) -> float:
    """Return a numeric summary value as a float, or NaN when it is not numeric.

    Parameters
    ----------
    value : object
        A summary value, normally an int or float.

    Returns
    -------
    float
        The value as a float, or NaN when it cannot be read as a number.
    """
    if isinstance(value, (int, float)):
        return float(value)
    return float("nan")


def _stats(values: Sequence[float]) -> dict[str, float | int]:
    """Return the distribution summary for one engine."""
    if not values:
        return {"runs": 0}
    return {
        "runs": len(values),
        "best": round(min(values), 6),
        "mean": round(statistics.mean(values), 6),
        "median": round(statistics.median(values), 6),
        "worst": round(max(values), 6),
        "stdev": round(statistics.pstdev(values), 6),
    }


def run_validation(
    *,
    dataset: Path,
    targets: Path,
    engines: Sequence[str] = ENGINES,
    seeds: Sequence[int] = (1, 2, 3),
    iterations: int = 200,
    years: int = 50,
    threads: int = 1,
    reversion: int = 0,
    mip_bound: bool = False,
    lp_bound: bool = False,
    workdir: Path | None = None,
    runner_factory: Callable[[Path, OptimizeConfig], Runner] = Optimizer.from_dataset,
) -> dict[str, object]:
    """Run every engine and seed and return the validation report.

    Parameters
    ----------
    dataset : Path
        Compiled ws4 dataset.
    targets : Path
        Goal-programming targets.
    engines : sequence of str, optional
        Engine names from ``("sa", "tabu", "ils")``.
    seeds : sequence of int, optional
        One run per seed per engine.
    iterations : int, optional
        Iteration budget for every run.
    years : int, optional
        Simulation horizon.
    threads : int, optional
        Worker count passed to the optimizer. The default 1 keeps the sweep
        deterministic and serial.
    reversion : int, optional
        Reset the current solution to the incumbent every this many accepted moves;
        0 disables it.
    mip_bound : bool, optional
        Ask each run for the MIP lower bound and gap.
    lp_bound : bool, optional
        Ask each run for the LP relaxation bound and gap.
    workdir : Path or None, optional
        Directory for the run outputs. ``None`` creates and removes a temporary
        directory.
    runner_factory : callable, optional
        The optimizer factory. Tests substitute a fake runner.

    Returns
    -------
    dict of str to object
        The records, per-engine statistics, and the Markdown report.

    Raises
    ------
    ValueError
        When an engine name or a seed is invalid.
    """
    if not engines:
        raise ValueError("at least one engine is required")
    unknown = [engine for engine in engines if engine not in ENGINES]
    if unknown:
        raise ValueError(f"unknown engine(s): {', '.join(unknown)}")
    if not seeds:
        raise ValueError("at least one seed is required")
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if workdir is None:
        temporary = tempfile.TemporaryDirectory(prefix="ws4-validate-")
        root = Path(temporary.name)
    else:
        root = Path(workdir)
        root.mkdir(parents=True, exist_ok=True)
    try:
        records: list[dict[str, object]] = []
        for engine in engines:
            for seed in seeds:
                out = root / f"{engine}-{seed}"
                config = OptimizeConfig(
                    targets_path=str(targets),
                    metaheuristic=engine,
                    seed=seed,
                    iterations=iterations,
                    years=years,
                    threads=threads,
                    workers=threads,
                    reversion=reversion,
                    mip_bound=mip_bound,
                    lp_bound=lp_bound,
                )
                summary = runner_factory(dataset, config).run(out)
                objective = _as_float(summary.get("incumbent_objective"))
                record: dict[str, object] = {
                    "engine": engine,
                    "seed": seed,
                    "objective": round(objective, 6),
                    "zero_penalty": objective <= 1e-9,
                    "out": str(out),
                }
                if "bound" in summary:
                    record["bound"] = summary["bound"]
                    record["gap"] = summary["gap"]
                    record["bound_status"] = summary.get("bound_status")
                if "lp_bound" in summary:
                    record["lp_bound"] = summary["lp_bound"]
                    record["lp_gap"] = summary["lp_gap"]
                    record["lp_status"] = summary.get("lp_status")
                records.append(record)
        by_engine = {
            engine: _stats(
                [_as_float(record["objective"]) for record in records if record["engine"] == engine]
            )
            for engine in engines
        }
        report: dict[str, object] = {
            "generated_utc": datetime.now(UTC).isoformat(),
            "dataset": str(dataset),
            "targets": str(targets),
            "engines": list(engines),
            "seeds": list(seeds),
            "iterations": iterations,
            "years": years,
            "reversion": reversion,
            "mip_bound": mip_bound,
            "lp_bound": lp_bound,
            "records": records,
            "summary": by_engine,
        }
        report["markdown"] = render_markdown(report)
        return report
    finally:
        if temporary is not None:
            temporary.cleanup()


def render_markdown(report: dict[str, object]) -> str:
    """Render a validation report as a Markdown table.

    Parameters
    ----------
    report : dict of str to object
        A report from :func:`run_validation`.

    Returns
    -------
    str
        A heading, a table, and a short interpretation.
    """
    summary = report.get("summary", {})
    assert isinstance(summary, dict)
    lines = [
        "# Validation sweep",
        "",
        f"- Dataset: `{report['dataset']}`",
        f"- Targets: `{report['targets']}`",
        f"- Iterations: {report['iterations']}",
        f"- Years: {report['years']}",
        f"- Reversion: {report['reversion']}",
        f"- MIP bound: {report['mip_bound']}",
        f"- LP bound: {report.get('lp_bound', False)}",
        "",
        "| Engine | Runs | Best | Mean | Median | Worst | Stdev |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for engine, stats in summary.items():
        assert isinstance(stats, dict)
        lines.append(
            f"| {engine} | {stats.get('runs', 0)} | {stats.get('best', 'n/a')} | "
            f"{stats.get('mean', 'n/a')} | {stats.get('median', 'n/a')} | "
            f"{stats.get('worst', 'n/a')} | {stats.get('stdev', 'n/a')} |"
        )
    lines.extend(
        [
            "",
            "Lower is better. `zero_penalty` in the JSON records means every target was met.",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the validation sweep from the command line.

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
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--engines", default=",".join(ENGINES))
    parser.add_argument("--seeds", default="1,2,3")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--years", type=int, default=50)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--reversion", type=int, default=0)
    parser.add_argument("--mip-bound", action="store_true")
    parser.add_argument("--lp-bound", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = run_validation(
        dataset=args.dataset,
        targets=args.targets,
        engines=_parse_csv(args.engines, allowed=ENGINES),
        seeds=[int(value) for value in _parse_csv(args.seeds)],
        iterations=args.iterations,
        years=args.years,
        threads=args.threads,
        reversion=args.reversion,
        mip_bound=args.mip_bound,
        workdir=args.out,
    )
    markdown = str(report["markdown"])
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "validation.json").write_text(
            json.dumps(
                {key: value for key, value in report.items() if key != "markdown"}, indent=2
            ),
            encoding="utf-8",
        )
        (args.out / "validation.md").write_text(markdown + "\n", encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
