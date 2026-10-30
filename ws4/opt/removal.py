"""Exact keep/remove carbon effect table and population search.

The ordinary optimizer prices one move at a time. For a binary keep/remove
decision the effect of every block is additive, so the whole decision space can
be priced once and then searched as a genome. This module builds those exact
effects from the ordinary carbon ledger and runs a small genetic algorithm over
the bits.

The decision is deliberately narrow: each scheduled block keeps its current
treatment chain or is left untreated. It is intended for carbon analyses where
the global removal pattern matters more than local chain shifts. Exact
``ws4 carbon`` replay remains the reporting authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

import numpy as np

try:  # optional GPU backend
    import torch
except ImportError:  # pragma: no cover - exercised only without the gpu extra
    torch = None  # type: ignore[assignment]  # optional dependency

from .objective import PRIORITY_SCALE, Target, accumulates

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .engine import Optimizer
    from .operators import Chain, Schedule

Cell = tuple[int, str]


@dataclass(frozen=True)
class RemovalEffects:
    """Exact per-block effects for a keep/remove genome.

    Parameters
    ----------
    blocks : tuple of int
        The blocks in effect-row order.
    schedule : dict of int to tuple
        The current chain of each block.
    cells : tuple of (int, str)
        The account cells the active targets read.
    base : numpy.ndarray
        Base values for the cells with every block untreated.
    effects : numpy.ndarray
        Shape ``(blocks, cells)``; the exact current-chain delta per block.
    target_cells : tuple of tuple of int
        The effect-column indices each target reads.
    targets : tuple of Target
        The active targets, in objective order.
    build_seconds : float
        Wall-clock seconds spent building and pricing the table.
    """

    blocks: tuple[int, ...]
    schedule: Schedule
    cells: tuple[Cell, ...]
    base: np.ndarray
    effects: np.ndarray
    target_cells: tuple[tuple[int, ...], ...]
    targets: tuple[Target, ...]
    build_seconds: float = 0.0

    def target_matrix(self) -> np.ndarray:
        """Return the block-to-target effect matrix.

        Returns
        -------
        numpy.ndarray
            Shape ``(blocks, targets)``.
        """
        matrix = np.zeros((len(self.blocks), len(self.targets)), dtype=np.float64)
        for index, columns in enumerate(self.target_cells):
            matrix[:, index] = self.effects[:, list(columns)].sum(axis=1)
        return matrix

    def base_targets(self) -> np.ndarray:
        """Return the untreated base value for each target.

        Returns
        -------
        numpy.ndarray
            Shape ``(targets,)``.
        """
        return np.array(
            [self.base[list(columns)].sum() for columns in self.target_cells],
            dtype=np.float64,
        )


@dataclass(frozen=True)
class RemovalResult:
    """The best keep/remove genome and its values.

    Parameters
    ----------
    schedule : dict of int to tuple
        The best schedule, containing only kept blocks.
    keep : numpy.ndarray
        Boolean keep mask in effect-row order.
    objective : float
        The weighted target penalty of the best genome.
    values : dict of (int, str) to float
        The cell totals of the best genome.
    generations : int
        Generations completed.
    search_seconds : float
        Wall-clock seconds spent in the population search.
    """

    schedule: Schedule
    keep: np.ndarray
    objective: float
    values: dict[Cell, float]
    generations: int
    search_seconds: float


def _target_cells(target: Target) -> tuple[int, ...]:
    """Return the offsets a target reads."""
    if target.flow:
        raise ValueError(
            "the removal search supports level targets only; flow targets are not implemented"
        )
    if accumulates(target.account):
        return tuple(target.cell_offsets())
    return (target.end_offset(),)


def build_removal_effects(
    optimizer: Optimizer,
    schedule: Mapping[int, Chain],
    targets: Sequence[Target],
) -> RemovalEffects:
    """Build exact keep/remove effects for a fixed schedule.

    Parameters
    ----------
    optimizer : Optimizer
        An optimizer configured with the carbon package and HWP.
    schedule : mapping of int to tuple
        The current chain per block.
    targets : sequence of Target
        The active targets. Flow targets are rejected.

    Returns
    -------
    RemovalEffects
        The exact effects and target projection.

    Raises
    ------
    ValueError
        When the schedule is empty, the carbon ledger is absent, or a target is
        a flow target.
    """
    if not schedule:
        raise ValueError("the removal search needs a non-empty schedule")
    carbon = optimizer.carbon_ledger()
    if carbon is None:
        raise ValueError("the removal search needs a carbon package")
    active = tuple(target for target in targets if target.active)
    if not active:
        raise ValueError("the removal search needs at least one active target")

    cell_offsets = [
        [(offset, target.account) for offset in _target_cells(target)] for target in active
    ]
    cells = tuple(sorted({cell for group in cell_offsets for cell in group}))
    cell_index = {cell: index for index, cell in enumerate(cells)}
    target_cells = tuple(tuple(cell_index[cell] for cell in group) for group in cell_offsets)

    blocks = tuple(sorted(int(block) for block in schedule))
    chains = {block: tuple(schedule[block]) for block in blocks}
    started = perf_counter()
    carbon.prepare({block: [chains[block]] for block in blocks})
    base_values = optimizer._base_values()
    base = np.array([base_values.get(cell, 0.0) for cell in cells], dtype=np.float64)
    accounts = {cell[1] for cell in cells}
    effects = np.zeros((len(blocks), len(cells)), dtype=np.float64)
    for row, block in enumerate(blocks):
        delta = optimizer._block_delta(block, chains[block], accounts)
        for column, cell in enumerate(cells):
            effects[row, column] = delta.get(cell, 0.0)
    return RemovalEffects(
        blocks=blocks,
        schedule=chains,
        cells=cells,
        base=base,
        effects=effects,
        target_cells=target_cells,
        targets=active,
        build_seconds=perf_counter() - started,
    )


def _penalties(values: np.ndarray, targets: Sequence[Target]) -> np.ndarray:
    """Return the weighted penalty for each target and genome.

    Parameters
    ----------
    values : numpy.ndarray
        Shape ``(genomes, targets)``.
    targets : sequence of Target
        The targets.

    Returns
    -------
    numpy.ndarray
        Shape ``(genomes, targets)``.
    """
    result = np.zeros_like(values, dtype=np.float64)
    for column, target in enumerate(targets):
        column_values = values[:, column]
        if target.minimum is not None:
            shortfall = np.maximum(target.minimum - column_values, 0.0)
            if target.shape == "non_linear":
                shortfall = shortfall * shortfall
            result[:, column] += target.min_weight * shortfall
        if target.maximum is not None:
            excess = np.maximum(column_values - target.maximum, 0.0)
            if target.shape == "non_linear":
                excess = excess * excess
            result[:, column] += target.max_weight * excess
        if target.normalization == "auto":
            bounds = [
                abs(float(bound)) for bound in (target.minimum, target.maximum) if bound is not None
            ]
            result[:, column] /= max([1.0, *bounds])
    return result


def _objective(values: np.ndarray, targets: Sequence[Target]) -> np.ndarray:
    """Return the scalar objective for each genome."""
    penalties = _penalties(values, targets)
    priorities = np.array([target.priority for target in targets], dtype=np.float64)
    highest = float(np.max(priorities))
    weights = np.power(PRIORITY_SCALE, highest - priorities)
    return penalties @ weights


def _greedy_keep(effects: RemovalEffects) -> np.ndarray | None:
    """Return a greedy keep mask for a min-cost/max-benefit target pair.

    The carbon use case has a yield floor and a carbon ceiling. Sorting blocks by
    carbon benefit per unit of yield loss gives a strong feasible seed before the
    population explores combinations. Other target shapes fall back to the random
    seed population.
    """
    targets = effects.targets
    cost_index = next(
        (index for index, target in enumerate(targets) if target.minimum is not None), None
    )
    benefit_index = next(
        (index for index, target in enumerate(targets) if target.maximum is not None), None
    )
    if cost_index is None or benefit_index is None:
        return None
    matrix = effects.target_matrix()
    values = effects.base_targets() + matrix.sum(axis=0)
    cost_effect = matrix[:, cost_index]
    benefit_effect = matrix[:, benefit_index]
    floor = targets[cost_index].minimum
    if floor is None:
        return None
    order = np.argsort(-(benefit_effect / np.maximum(cost_effect, 1e-12)), kind="stable")
    keep = np.ones(len(effects.blocks), dtype=bool)
    remaining = float(values[cost_index])
    for index in order:
        if remaining - cost_effect[index] >= floor:
            keep[index] = False
            remaining -= cost_effect[index]
    return keep


def solve_removal(
    effects: RemovalEffects,
    *,
    population: int = 2048,
    generations: int = 3000,
    seed: int = 1,
    elite_fraction: float = 0.05,
    tournament_size: int = 3,
    mutation_rate: float = 0.0005,
    random_fraction: float = 0.1,
    use_gpu: bool = True,
) -> RemovalResult:
    """Search the binary keep/remove genome with a small genetic algorithm.

    Parameters
    ----------
    effects : RemovalEffects
        The exact effect table.
    population : int, optional
        Number of genomes. Defaults to 2048.
    generations : int, optional
        Generations to evolve. Defaults to 3000.
    seed : int, optional
        Random seed. Defaults to one.
    elite_fraction : float, optional
        Fraction copied unchanged. Defaults to 0.05.
    tournament_size : int, optional
        Tournament size. Defaults to three.
    mutation_rate : float, optional
        Per-block mutation probability. Defaults to 0.0005.
    random_fraction : float, optional
        Fraction of the initial population with random removals. Defaults to 0.1.
    use_gpu : bool, optional
        Use CUDA for the population when available. Defaults to True.

    Returns
    -------
    RemovalResult
        The best genome and its cell totals.
    """
    if population < 2:
        raise ValueError("population must be at least two")
    if generations < 1:
        raise ValueError("generations must be positive")
    if not 0.0 <= elite_fraction < 1.0:
        raise ValueError("elite_fraction must be in [0, 1)")
    if tournament_size < 1:
        raise ValueError("tournament_size must be positive")
    if not 0.0 <= random_fraction <= 1.0:
        raise ValueError("random_fraction must be in [0, 1]")

    if use_gpu and torch is not None and torch.cuda.is_available():
        return _solve_removal_torch(
            effects,
            population=population,
            generations=generations,
            seed=seed,
            elite_fraction=elite_fraction,
            tournament_size=tournament_size,
            mutation_rate=mutation_rate,
            random_fraction=random_fraction,
        )

    rng = np.random.default_rng(seed)
    target_effects = effects.target_matrix()
    base_targets = effects.base_targets()
    blocks = len(effects.blocks)
    keep = np.ones((population, blocks), dtype=bool)
    random_count = int(population * random_fraction)
    for row in range(population - random_count, population):
        rate = float(rng.random() * 0.05)
        keep[row] = rng.random(blocks) >= rate
    greedy = _greedy_keep(effects)
    if greedy is not None:
        keep[1] = greedy
    best_keep = keep[0].copy()
    best_objective = float("inf")
    started = perf_counter()
    for _generation in range(generations):
        values = base_targets + keep.astype(np.float64) @ target_effects
        scores = _objective(values, effects.targets)
        elite_count = max(1, int(population * elite_fraction))
        elite_order = np.argsort(scores, kind="stable")[:elite_count]
        if scores[elite_order[0]] < best_objective:
            best_objective = float(scores[elite_order[0]])
            best_keep = keep[elite_order[0]].copy()
        # Tournament selection.
        contenders = rng.integers(0, population, size=(population, tournament_size))
        winners = np.argmin(scores[contenders], axis=1)
        parents = keep[contenders[np.arange(population), winners]]
        # Uniform crossover.
        mask = rng.random((population, blocks)) < 0.5
        children = np.where(mask, parents, parents[rng.permutation(population)])
        # Mutation.
        mutation = rng.random((population, blocks)) < mutation_rate
        children ^= mutation
        children[:elite_count] = keep[elite_order]
        keep = children
    # Re-evaluate the final generation so the reported values are current.
    values = base_targets + keep.astype(np.float64) @ target_effects
    scores = _objective(values, effects.targets)
    index = int(np.argmin(scores))
    if scores[index] < best_objective:
        best_objective = float(scores[index])
        best_keep = keep[index].copy()
    best_values = effects.base + best_keep.astype(np.float64) @ effects.effects
    schedule = {
        block: effects.schedule[block]
        for block, include in zip(effects.blocks, best_keep, strict=True)
        if bool(include)
    }
    return RemovalResult(
        schedule=schedule,
        keep=best_keep,
        objective=best_objective,
        values={cell: float(best_values[column]) for column, cell in enumerate(effects.cells)},
        generations=generations,
        search_seconds=perf_counter() - started,
    )


def _solve_removal_torch(
    effects: RemovalEffects,
    *,
    population: int,
    generations: int,
    seed: int,
    elite_fraction: float,
    tournament_size: int,
    mutation_rate: float,
    random_fraction: float,
) -> RemovalResult:
    """Run the population search on the CUDA device."""
    if torch is None:  # pragma: no cover - guarded by the caller
        raise RuntimeError("torch is not installed")
    device = torch.device("cuda")
    target_effects = torch.tensor(effects.target_matrix(), dtype=torch.float64, device=device)
    base_targets = torch.tensor(effects.base_targets(), dtype=torch.float64, device=device)
    base = torch.tensor(effects.base, dtype=torch.float64, device=device)
    cell_effects = torch.tensor(effects.effects, dtype=torch.float64, device=device)
    blocks = len(effects.blocks)
    rng = torch.Generator(device=device)
    rng.manual_seed(seed)
    keep = torch.ones((population, blocks), dtype=torch.bool, device=device)
    random_count = int(population * random_fraction)
    for row in range(population - random_count, population):
        rate = float(torch.rand((), dtype=torch.float64, device=device, generator=rng) * 0.05)
        keep[row] = torch.rand(blocks, dtype=torch.float64, device=device, generator=rng) >= rate
    greedy = _greedy_keep(effects)
    if greedy is not None:
        keep[1] = torch.tensor(greedy, dtype=torch.bool, device=device)
    targets = effects.targets
    minimum = torch.tensor(
        [target.minimum if target.minimum is not None else 0.0 for target in targets],
        dtype=torch.float64,
        device=device,
    )
    maximum = torch.tensor(
        [target.maximum if target.maximum is not None else 0.0 for target in targets],
        dtype=torch.float64,
        device=device,
    )
    has_minimum = torch.tensor(
        [target.minimum is not None for target in targets], dtype=torch.bool, device=device
    )
    has_maximum = torch.tensor(
        [target.maximum is not None for target in targets], dtype=torch.bool, device=device
    )
    min_weight = torch.tensor(
        [target.min_weight for target in targets], dtype=torch.float64, device=device
    )
    max_weight = torch.tensor(
        [target.max_weight for target in targets], dtype=torch.float64, device=device
    )
    nonlinear = torch.tensor(
        [target.shape == "non_linear" for target in targets], dtype=torch.bool, device=device
    )
    scale = torch.tensor(
        [
            (
                max(
                    [
                        1.0,
                        *[
                            abs(float(bound))
                            for bound in (target.minimum, target.maximum)
                            if bound is not None
                        ],
                    ]
                )
                if target.normalization == "auto"
                else 1.0
            )
            for target in targets
        ],
        dtype=torch.float64,
        device=device,
    )
    priorities = torch.tensor(
        [target.priority for target in targets], dtype=torch.float64, device=device
    )
    priority_weights = torch.pow(
        torch.tensor(PRIORITY_SCALE, dtype=torch.float64, device=device),
        priorities.max() - priorities,
    )

    def scores_for(genomes: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        values = base_targets + genomes.to(torch.float64) @ target_effects
        shortfall = torch.clamp(minimum - values, min=0.0)
        shortfall = torch.where(nonlinear, shortfall * shortfall, shortfall)
        excess = torch.clamp(values - maximum, min=0.0)
        excess = torch.where(nonlinear, excess * excess, excess)
        penalties = (
            min_weight * torch.where(has_minimum, shortfall, torch.zeros_like(shortfall))
            + max_weight * torch.where(has_maximum, excess, torch.zeros_like(excess))
        ) / scale
        return penalties @ priority_weights, values

    scores, _values = scores_for(keep)
    best_index = int(torch.argmin(scores))
    best_keep = keep[best_index].clone()
    best_objective = float(scores[best_index])
    best_values = base + best_keep.to(torch.float64) @ cell_effects
    started = perf_counter()
    for _generation in range(generations):
        elite_count = max(1, int(population * elite_fraction))
        elite_order = torch.argsort(scores)[:elite_count]
        if float(scores[elite_order[0]]) < best_objective:
            best_objective = float(scores[elite_order[0]])
            best_keep = keep[elite_order[0]].clone()
        contenders = torch.randint(
            population,
            (population, tournament_size),
            dtype=torch.int64,
            device=device,
            generator=rng,
        )
        local_scores = scores[contenders]
        winners = torch.argmin(local_scores, dim=1)
        parents = keep[contenders[torch.arange(population, device=device), winners]]
        crossover = (
            torch.rand((population, blocks), dtype=torch.float64, device=device, generator=rng)
            < 0.5
        )
        children = torch.where(
            crossover,
            parents,
            parents[torch.randperm(population, device=device, generator=rng)],
        )
        mutation = (
            torch.rand((population, blocks), dtype=torch.float64, device=device, generator=rng)
            < mutation_rate
        )
        children = torch.where(mutation, ~children, children)
        children[:elite_count] = keep[elite_order]
        keep = children
        scores, _values = scores_for(keep)
    best_index = int(torch.argmin(scores))
    if float(scores[best_index]) < best_objective:
        best_objective = float(scores[best_index])
        best_keep = keep[best_index].clone()
        best_values = base + best_keep.to(torch.float64) @ cell_effects
    schedule = {
        block: effects.schedule[block]
        for block, include in zip(effects.blocks, best_keep.cpu().tolist(), strict=True)
        if bool(include)
    }
    return RemovalResult(
        schedule=schedule,
        keep=best_keep.cpu().numpy(),
        objective=best_objective,
        values={
            cell: float(best_values[column].item()) for column, cell in enumerate(effects.cells)
        },
        generations=generations,
        search_seconds=perf_counter() - started,
    )


def write_removal_schedule(result: RemovalResult, path: str | Path) -> None:
    """Write a removal result to the optimizer's schedule CSV schema.

    Parameters
    ----------
    result : RemovalResult
        The result to write.
    path : path-like
        Destination CSV path.
    """
    import pandas as pd

    rows = [
        {"block_id": block, "treatment": treatment, "offset": offset}
        for block, chain in result.schedule.items()
        for treatment, offset in chain
    ]
    pd.DataFrame(rows, columns=["block_id", "treatment", "offset"]).to_csv(path, index=False)
