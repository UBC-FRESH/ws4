"""Resident GPU population session for repeated full-model runs.

A one-shot search rebuilds the option map and base state before it can breed.  For a batch
of seeds or a persistent worker, those are invariant for a fixed dataset, target set, and
candidate map.  :class:`GpuSearchSession` builds one :class:`GenomePopulation` and resets
only its random stream, genomes, and incumbent between runs.

The session does not share method state across independent workers.  It is a single
resident population; a caller that needs independent workers should create one session per
worker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .gpu_ga import GenomePopulation, PopulationResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .engine import Optimizer
    from .gpu_effects import EffectTable
    from .incremental import IncrementalObjective
    from .operators import Candidates, Chain


class GpuSearchSession:
    """A resident GPU population that can run several seeds without rebuilding its plan.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer that owns the exact model.
    evaluator : IncrementalObjective
        The exact evaluator used to check the population's device scores.
    table : EffectTable
        The effect table for the fixed target set.
    candidates : mapping of int to list of tuple
        The candidate chains per block.
    seed_schedule : mapping of int to tuple of (str, int) or None
        The initial schedule for every run.
    population : int, optional
        Number of genomes.  Defaults to 64.
    initial_seed : int, optional
        Seed used for the initial population construction.  Defaults to 7.
    random_fraction : float, optional
        Fraction of random genomes.  Defaults to 0.05.
    initial_mutation_rate : float, optional
        Mutation rate for the initial seeded genomes.  Defaults to 0.02.
    mutation_rate : float, optional
        Mutation rate during breeding.  Defaults to 0.002.
    islands : int, optional
        Number of search islands.  Defaults to 1.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        evaluator: IncrementalObjective,
        table: EffectTable,
        *,
        candidates: Candidates,
        seed_schedule: Mapping[int, Chain] | None,
        population: int = 64,
        initial_seed: int = 7,
        random_fraction: float = 0.05,
        initial_mutation_rate: float = 0.02,
        mutation_rate: float = 0.002,
        islands: int = 1,
    ) -> None:
        self.seed_schedule = seed_schedule
        self.population = GenomePopulation(
            optimizer,
            evaluator,
            table,
            population=population,
            seed=initial_seed,
            seed_schedule=seed_schedule,
            candidates=candidates,
            random_fraction=random_fraction,
            initial_mutation_rate=initial_mutation_rate,
            mutation_rate=mutation_rate,
            islands=islands,
        )

    def run(self, seed: int, generations: int, *, check: int = 1) -> PopulationResult:
        """Reseed the resident population and run one exact search.

        Parameters
        ----------
        seed : int
            Random seed for the population initialization and breeding.
        generations : int
            Number of evolved generations.
        check : int, optional
            Number of initial genomes to compare with a fresh exact evaluator.  Defaults
            to 1.

        Returns
        -------
        PopulationResult
            The exact incumbent and run counters.
        """
        self.population.reset(self.seed_schedule, seed=seed)
        return self.population.run(generations, check=check)
