"""Calibrate target weights from a pilot search.

Targets of different magnitudes unbalance the objective: the largest term dominates and the search
freezes before the others are considered. Lockwood and Moore (1993) traced each penalty term as the
control parameter fell and rescaled the terms by hand until they decreased at similar rates. This
module automates the first pass: a short pilot search records the largest penalty each target
reaches, and every target that fired is rescaled so the peaks match.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from pathlib import Path

import yaml

from .engine import Optimizer
from .objective import Target, balance_targets, objective_terms
from .solvers import solve_sa_delta

_DEFAULT_ITERATIONS = 2_000
_DEFAULT_SAMPLES = 32
_DEFAULT_SEED = 42


def pilot_peaks(
    optimizer: Optimizer,
    targets: Sequence[Target],
    *,
    iterations: int,
    seed: int = _DEFAULT_SEED,
    samples: int = _DEFAULT_SAMPLES,
    warm_start: bool = False,
) -> list[float]:
    """Run a pilot search and return the peak penalty each target reaches.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer. It supplies the candidates, the registry, and the evaluator.
    targets : sequence of Target
        The targets to calibrate.
    iterations : int
        The pilot budget.
    seed : int, optional
        The pilot seed. Defaults to 42.
    samples : int, optional
        How often the per-term penalties are sampled. Defaults to 32.
    warm_start : bool, optional
        Start the pilot from each block's first candidate, matching a warm-started run.
        Defaults to False (the empty schedule).

    Returns
    -------
    list of float
        The peak penalty per target, in order.

    Raises
    ------
    ValueError
        If the configuration cannot be priced by the move-based evaluator.
    """
    goals = list(targets)
    evaluator = optimizer.delta_evaluator(goals)
    if evaluator is None:
        raise ValueError("this configuration cannot be calibrated by a pilot search")
    candidates = optimizer.candidates()
    initial = {block: chains[0] for block, chains in candidates.items() if chains}
    peaks = [0.0] * len(goals)
    every = max(1, iterations // max(1, samples))

    def on_step(iteration: int, _objective: float) -> None:
        if iteration % every and iteration != iterations - 1:
            return
        for index, term in enumerate(objective_terms(evaluator.values_frame(), goals)):
            if term > peaks[index]:
                peaks[index] = term

    solve_sa_delta(
        evaluator,
        random.Random(seed),
        iterations=iterations,
        temperature=1000.0,
        cooling=0.99,
        candidates=candidates,
        registry=optimizer.registry,
        on_step=on_step,
        initial=initial if warm_start else None,
        adaptive=True,
    )
    return peaks


def calibrate(
    optimizer: Optimizer,
    targets: Sequence[Target],
    *,
    iterations: int = _DEFAULT_ITERATIONS,
    seed: int = _DEFAULT_SEED,
    samples: int = _DEFAULT_SAMPLES,
    warm_start: bool = False,
) -> list[Target]:
    """Return the targets with their weights balanced by a pilot search.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer.
    targets : sequence of Target
        The targets to calibrate.
    iterations : int, optional
        The pilot budget. Defaults to 2000.
    seed : int, optional
        The pilot seed. Defaults to 42.
    samples : int, optional
        How often the per-term penalties are sampled. Defaults to 32.
    warm_start : bool, optional
        Start the pilot from each block's first candidate. Defaults to False.

    Returns
    -------
    list of Target
        The rescaled targets.
    """
    goals = list(targets)
    peaks = pilot_peaks(
        optimizer, goals, iterations=iterations, seed=seed, samples=samples, warm_start=warm_start
    )
    return balance_targets(goals, peaks)


def write_targets(path: Path, targets: Sequence[Target]) -> Path:
    """Write targets to a YAML file that :func:`ws4.opt.objective.load_targets` reads.

    Parameters
    ----------
    path : Path
        The file to write.
    targets : sequence of Target
        The targets.

    Returns
    -------
    Path
        The path written.
    """
    entries: list[dict[str, object]] = []
    for target in targets:
        entry: dict[str, object] = {"account": target.account}
        if target.period is not None:
            entry["period"] = target.period
        else:
            entry["year"] = target.year
            entry["offset"] = target.end_offset()
        if target.minimum is not None:
            entry["minimum"] = target.minimum
        if target.maximum is not None:
            entry["maximum"] = target.maximum
        entry["min_weight"] = target.min_weight
        entry["max_weight"] = target.max_weight
        if target.period_width != 1:
            entry["period_width"] = target.period_width
        if target.shape != "linear":
            entry["shape"] = target.shape
        if target.flow:
            entry["flow"] = target.flow
            if target.flow_start_period is not None:
                entry["flow_start_period"] = target.flow_start_period
            else:
                entry["flow_start"] = target.flow_start
            if target.flow_end_period is not None:
                entry["flow_end_period"] = target.flow_end_period
            elif target.flow_end is not None:
                entry["flow_end"] = target.flow_end
            if target.flow_reference_period is not None:
                entry["flow_reference_period"] = target.flow_reference_period
            elif target.flow_reference is not None:
                entry["flow_reference"] = target.flow_reference
        if not target.active:
            entry["active"] = False
        entries.append(entry)
    destination = Path(path)
    destination.write_text(yaml.safe_dump({"targets": entries}, sort_keys=False), encoding="utf-8")
    return destination
