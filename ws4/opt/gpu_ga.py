"""GPU-native candidate-index population search over the sparse effect table.

This is the P83.8 bounded prototype.  It is deliberately **not** a GPU port of the
sequential simulated annealer: every generation evaluates a whole population of genomes in
one batched device operation, then applies elitism, tournament selection, uniform
crossover, and mutation.  The CPU simulated annealer remains the reference and the
fallback.

Representation
--------------
A genome is one candidate index per block::

    genome[block_position] = option index into that block's candidate list

The candidate lists are stable for a fixed dataset and configuration, so a genome is a
categorical treatment choice, not a continuous random key.  A seed chain that is absent
from the candidate list is appended to that block's options (an extra effect row), which
keeps the seed representable without a repair pass.

Fitness
-------
Fitness is the exact WS4 objective for one priority tier, no patch accounts, no route
accounts, and no spatial rules.  One genome's cell totals are the base totals plus the
segmented sum of its effect rows.  The device pricer then reproduces the incremental
objective's per-target penalty sum.  Anything outside that contract raises
:class:`NotImplementedError` instead of returning a silently different objective.

``torch`` is an optional dependency (the ``gpu`` extra).  Importing this module succeeds
without it; constructing or running a population raises :class:`RuntimeError` instead.

Islands
-------
An island run adapts the MQT AGrp structure without its job server or per-solution Python
loop.  The master owns the population tensor and does selection, crossover, mutation, and
elite placement for every worker island in one batched device call.  Each worker is a
contiguous subpopulation that can run for several generations; at an exchange the workers
return elites and the master replaces the destination worst genomes.  ``exchange="ring"``
moves elites between neighbouring workers.  ``exchange="agrp"`` keeps the global elite set
and re-seeds every worker with it, which is the AGrp master-best seeding rule.  The job
server is unnecessary because the population and effect table already share device memory.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

try:  # pragma: no cover - which branch runs depends on the environment
    import torch

    HAVE_TORCH = True
except ImportError:  # pragma: no cover
    HAVE_TORCH = False
    torch = None  # type: ignore[assignment]  # torch is optional; methods raise without it.

from .gpu_search import _ObjectivePricer

if TYPE_CHECKING:
    from collections.abc import Mapping

    import torch as torch_type

    from .engine import Optimizer
    from .gpu_effects import EffectTable
    from .incremental import IncrementalObjective
    from .operators import Candidates, Chain, Schedule


def _require_torch() -> None:
    """Raise a clear error when torch is not installed."""
    if not HAVE_TORCH:
        raise RuntimeError(
            "the GPU population search needs torch; install the optional 'gpu' dependency "
            "(pip install 'ws4[gpu]')"
        )


@dataclass(frozen=True)
class PopulationResult:
    """The best genome and the measured cost of a population run.

    Parameters
    ----------
    schedule : dict of int to tuple of (str, int)
        The best assignment found, one chain per block in the search slice.
    objective : float
        The exact incremental objective of ``schedule``.
    initial_objective : float
        The objective of the seeded genome.
    generations : int
        The number of evolved generations, excluding the initial evaluation.
    evaluations : int
        The total number of genome evaluations, including the initial population.
    seconds : float
        Wall-clock seconds spent in initialization, evaluation, and operators.  The effect
        table build and upload are not included.
    best_generation : int
        The generation that produced the incumbent (zero is the seeded generation).
    best_island : int
        The island that produced the incumbent, or zero without islands.
    history : tuple of float
        The best-ever objective after the initial evaluation and after each generation.

    Attributes
    ----------
    objective_gain : float
        ``initial_objective - objective``.
    """

    schedule: Schedule
    objective: float
    initial_objective: float
    generations: int
    evaluations: int
    seconds: float
    best_generation: int
    best_island: int
    history: tuple[float, ...]

    @property
    def objective_gain(self) -> float:
        """Return the objective improvement over the seeded genome.

        Returns
        -------
        float
            ``initial_objective - objective``.
        """
        return self.initial_objective - self.objective


class GenomePopulation:
    """A candidate-index population search driven by an :class:`EffectTable`.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer that owns the candidate chains and the base account values.
    evaluator : IncrementalObjective
        The exact evaluator, used for its target metadata and one-priority contract.
    table : EffectTable
        The effect table for the same blocks, already on the device to search on.
    population : int, optional
        The number of genomes.  Defaults to 64.
    seed : int, optional
        The seed of the device random source.  Defaults to one.
    seed_schedule : dict of int to tuple of (str, int) or None, optional
        The accepted schedule.  Its chains seed the first genome and are appended to a
        block's options when the candidate list does not contain them.  None uses the first
        candidate of every block.
    candidates : mapping of int to list of tuple, optional
        The per-block candidate chains.  None calls ``optimizer.candidates()``.  Passing a
        precomputed mapping is useful when a persisted table is reloaded.
    random_fraction : float, optional
        The fraction of the initial population that is uniformly random.  Defaults to 0.15.
    initial_mutation_rate : float, optional
        The per-block mutation probability applied to the seeded genomes.  Defaults to 0.05.
    mutation_rate : float, optional
        The per-block mutation probability applied to every child.  Defaults to 0.002.
    elite_fraction : float, optional
        The fraction of each island copied unchanged into the next generation.  Defaults to
        0.1.
    tournament_size : int, optional
        The number of contenders in one tournament.  Defaults to 3.
    islands : int, optional
        The number of contiguous worker subpopulations.  One disables migration.
        Defaults to one.
    exchange : {"ring", "agrp"}, optional
        The elite-exchange topology.  ``"ring"`` copies each island's best migrants over
        the next island's worst.  ``"agrp"`` is the adapted MQT AGrp structure: every
        worker returns its best migrants, the master keeps the global elite set, and that
        set replaces the worst migrants of every worker, so each worker is re-seeded from
        the master incumbent.  Defaults to ``"ring"``.
    migration_interval : int, optional
        The generations between elite exchanges (worker runs, in the AGrp framing).
        Defaults to zero, which disables migration.
    migrants : int, optional
        The number of best genomes copied from one island to the next.  Defaults to one.

    Raises
    ------
    NotImplementedError
        When the target set is outside the one-tier, no-patch, no-route, no-spatial, and
        non-``ndy`` contract.
    ValueError
        When an operator parameter is invalid or the table cannot represent a block's
        options.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        evaluator: IncrementalObjective,
        table: EffectTable,
        *,
        population: int = 64,
        seed: int = 1,
        seed_schedule: Mapping[int, Chain] | None = None,
        candidates: Candidates | None = None,
        random_fraction: float = 0.15,
        initial_mutation_rate: float = 0.05,
        mutation_rate: float = 0.002,
        elite_fraction: float = 0.1,
        tournament_size: int = 3,
        islands: int = 1,
        exchange: str = "ring",
        migration_interval: int = 0,
        migrants: int = 1,
    ) -> None:
        _require_torch()
        _check_supported(evaluator)
        if population < 2:
            raise ValueError("population must be at least two")
        if not 0.0 <= random_fraction <= 1.0:
            raise ValueError("random_fraction must be in [0, 1]")
        if not 0.0 <= initial_mutation_rate <= 1.0:
            raise ValueError("initial_mutation_rate must be in [0, 1]")
        if not 0.0 <= mutation_rate <= 1.0:
            raise ValueError("mutation_rate must be in [0, 1]")
        if not 0.0 <= elite_fraction < 1.0:
            raise ValueError("elite_fraction must be in [0, 1)")
        if tournament_size < 1:
            raise ValueError("tournament_size must be positive")
        if islands < 1:
            raise ValueError("islands must be positive")
        if population % islands != 0:
            raise ValueError("population must be divisible by islands")
        if exchange not in {"ring", "agrp"}:
            raise ValueError("exchange must be 'ring' or 'agrp'")
        if migration_interval < 0:
            raise ValueError("migration_interval must not be negative")
        if migrants < 0:
            raise ValueError("migrants must not be negative")

        self.optimizer = optimizer
        self.evaluator = evaluator
        self.table = table
        self.population = population
        self.seed = seed
        self.random_fraction = random_fraction
        self.initial_mutation_rate = initial_mutation_rate
        self.mutation_rate = mutation_rate
        self.elite_fraction = elite_fraction
        self.tournament_size = tournament_size
        self.islands = islands
        self.exchange = exchange
        self.migration_interval = migration_interval
        self.migrants = migrants
        self.device = table.device
        self.generator = torch.Generator(device=self.device)
        self.generator.manual_seed(seed)
        self.pricer = _ObjectivePricer(evaluator, table.cells, self.device)
        self.blocks = tuple(table.blocks)
        if not self.blocks:
            raise ValueError("the effect table has no blocks")
        self.block_index = torch.arange(len(self.blocks), dtype=torch.int64, device=self.device)
        self.lengths, self.option_rows, self.option_chains = self._options(
            candidates if candidates is not None else optimizer.candidates(), seed_schedule
        )
        self.base_totals = self._base_totals()
        self.genomes = self._initialize(seed_schedule)
        self.scores: torch_type.Tensor | None = None
        self.totals: torch_type.Tensor | None = None
        self.generation = 0
        self.best_genome = self.genomes[0].clone()
        self.best_objective = math.inf
        self.best_generation = 0
        self.best_island = 0
        self.history: list[float] = []

    def _options(
        self,
        candidates: Candidates,
        seed_schedule: Mapping[int, Chain] | None,
    ) -> tuple[torch_type.Tensor, torch_type.Tensor, dict[int, tuple[Chain, ...]]]:
        """Return the option lengths, padded row ids, and chains for every block."""
        chains_by_block: dict[int, tuple[Chain, ...]] = {}
        for block in self.blocks:
            chains = list(candidates.get(block, ()))
            if seed_schedule is not None:
                seed_chain = seed_schedule.get(block)
                if seed_chain is not None and seed_chain not in chains:
                    # An extra effect row keeps a seed chain that is not a candidate usable
                    # as a genome option, so crossover and mutation need no repair pass.
                    chains.append(seed_chain)
            if not chains:
                raise ValueError(f"block {block} has no candidate chains")
            chains_by_block[block] = tuple(chains)
        width = max(len(chains) for chains in chains_by_block.values())
        lengths = torch.tensor(
            [len(chains_by_block[block]) for block in self.blocks],
            dtype=torch.int64,
            device=self.device,
        )
        rows = torch.zeros((len(self.blocks), width), dtype=torch.int64, device=self.device)
        # ``EffectTable.build`` assigns every block's candidate rows consecutively, in
        # candidate order, before appending any seed-only extra rows.  Resolve the first
        # and last candidate row per block and fill the run with ``arange`` instead of
        # doing one Python dict lookup for every one of the tens of millions of chains.
        # A non-contiguous table falls back to the exact per-chain lookup.
        for index, block in enumerate(self.blocks):
            block_chains = chains_by_block[block]
            candidate_count = len(candidates.get(block, ()))
            if candidate_count:
                first = self.table.block_starts.get(block)
                if first is not None:
                    if first + candidate_count > self.table.rows:
                        raise ValueError(
                            f"the effect table's candidate row range for block {block} is "
                            "outside the table; rebuild it with this candidate set"
                        )
                    rows[index, :candidate_count] = torch.arange(
                        first, first + candidate_count, dtype=torch.int64, device=self.device
                    )
                else:
                    try:
                        first = self.table.row_id(block, block_chains[0])
                        last = self.table.row_id(block, block_chains[candidate_count - 1])
                    except KeyError as exc:
                        raise ValueError(
                            f"the effect table has no row for block {block}; rebuild it with "
                            "this chain in extra_pairs"
                        ) from exc
                    if last - first == candidate_count - 1:
                        rows[index, :candidate_count] = torch.arange(
                            first, first + candidate_count, dtype=torch.int64, device=self.device
                        )
                    else:
                        for position in range(candidate_count):
                            try:
                                rows[index, position] = self.table.row_id(
                                    block, block_chains[position]
                                )
                            except KeyError as exc:
                                raise ValueError(
                                    f"the effect table has no row for block {block}; rebuild it "
                                    "with this chain in extra_pairs"
                                ) from exc
            for position in range(candidate_count, len(block_chains)):
                try:
                    rows[index, position] = self.table.row_id(block, block_chains[position])
                except KeyError as exc:
                    raise ValueError(
                        f"the effect table has no row for block {block}; rebuild it with "
                        "this chain in extra_pairs"
                    ) from exc
        return lengths, rows, chains_by_block

    def _base_totals(self) -> torch_type.Tensor:
        """Return the empty-schedule base totals as one float64 device vector."""
        base = torch.zeros(len(self.table.cells), dtype=torch.float64, device=self.device)
        cell_index = {cell: column for column, cell in enumerate(self.table.cells)}
        for cell, value in self.optimizer._base_values().items():
            column = cell_index.get(cell)
            if column is not None:
                base[column] = value
        return base

    def _seed_indices(self, seed_schedule: Mapping[int, Chain] | None) -> torch_type.Tensor:
        """Return the genome indices of the seed schedule, or the first option."""
        indices = torch.zeros(len(self.blocks), dtype=torch.int64, device=self.device)
        if seed_schedule is None:
            return indices
        for position, block in enumerate(self.blocks):
            chain = seed_schedule.get(block)
            if chain is None:
                continue
            options = self.option_chains[block]
            try:
                indices[position] = options.index(chain)
            except ValueError as exc:  # pragma: no cover - _options appends the chain
                raise ValueError(f"the seed chain for block {block} is not an option") from exc
        return indices

    def _random_indices(self, shape: tuple[int, ...]) -> torch_type.Tensor:
        """Return uniform valid option indices for every block position."""
        unit = torch.rand(shape, dtype=torch.float64, device=self.device, generator=self.generator)
        return torch.minimum(
            (unit * self.lengths.unsqueeze(0)).to(torch.int64),
            self.lengths.unsqueeze(0) - 1,
        )

    def _mutate(self, genomes: torch_type.Tensor, rate: float) -> torch_type.Tensor:
        """Return ``genomes`` with each block mutated at the given probability.

        A mutated block picks uniformly from its options, so the current chain is one of the
        outcomes; a mutation to the same option is the prototype's stay-with-current-chain
        move and leaves the schedule unchanged.
        """
        if rate <= 0.0:
            return genomes
        mask = (
            torch.rand(
                genomes.shape, dtype=torch.float64, device=self.device, generator=self.generator
            )
            < rate
        )
        return torch.where(mask, self._random_indices(tuple(genomes.shape)), genomes)

    def _initialize(self, seed_schedule: Mapping[int, Chain] | None) -> torch_type.Tensor:
        """Return the initial population: the seed, its mutants, and random genomes."""
        seeded = self._seed_indices(seed_schedule)
        genomes = seeded.unsqueeze(0).repeat(self.population, 1)
        random_count = round(self.population * self.random_fraction)
        random_count = min(random_count, self.population - 1)
        mutant_count = self.population - 1 - random_count
        if mutant_count > 0:
            mutants = self._mutate(genomes[1 : 1 + mutant_count], self.initial_mutation_rate)
            genomes[1 : 1 + mutant_count] = mutants
        if random_count > 0:
            genomes[self.population - random_count :] = self._random_indices(
                (random_count, len(self.blocks))
            )
        return genomes

    def reseed(self, seed_schedule: Mapping[int, Chain] | None) -> None:
        """Replace the population with a fresh initialization from a schedule.

        A persistent worker uses this at a migration boundary: its effect table, option
        mapping, and random stream stay local, while the new elite becomes the seed genome
        and the incumbent counters reset.  No external population or master state is
        shared.

        Parameters
        ----------
        seed_schedule : mapping of int to tuple of (str, int) or None
            The accepted schedule.  None uses the first candidate of every block.

        Raises
        ------
        ValueError
            When a seed chain is not in the table's option list for its block.
        """
        self.genomes = self._initialize(seed_schedule)
        self.scores = None
        self.totals = None
        self.generation = 0
        self.best_genome = self.genomes[0].clone()
        self.best_objective = math.inf
        self.best_generation = 0
        self.best_island = 0
        self.history = []

    def _rows(self, genomes: torch_type.Tensor) -> torch_type.Tensor:
        """Return the effect-table row ids of every genome and block."""
        return self.option_rows[self.block_index.unsqueeze(0), genomes]

    def evaluate(self, genomes: torch_type.Tensor | None = None) -> torch_type.Tensor:
        """Return the exact objective of every genome in one batched device call.

        Parameters
        ----------
        genomes : torch.Tensor or None, optional
            A ``[count, blocks]`` candidate-index tensor.  None evaluates the current
            population.  Defaults to None.

        Returns
        -------
        torch.Tensor
            A ``[count]`` float64 tensor of exact objectives.

        Raises
        ------
        ValueError
            When the genomes do not match the population's block count or hold an option
            index outside a block's candidate list.
        """
        source = self.genomes if genomes is None else genomes
        if source.ndim != 2 or source.shape[1] != len(self.blocks):
            raise ValueError("genomes must be a [count, blocks] tensor")
        if bool(((source < 0) | (source >= self.lengths.unsqueeze(0))).any()):
            raise ValueError("a genome option index is outside its block's candidate list")
        count = source.shape[0]
        rows = self._rows(source)
        segments = torch.arange(count, dtype=torch.int64, device=self.device).repeat_interleave(
            len(self.blocks)
        )
        totals = self.base_totals.unsqueeze(0) + self.table.segmented_delta(
            rows.reshape(-1), segments
        )
        scores = self.pricer.scores(totals)
        self.scores = scores
        self.totals = totals
        return scores

    def schedule(self, genome: torch_type.Tensor) -> Schedule:
        """Return the schedule named by one genome.

        Parameters
        ----------
        genome : torch.Tensor
            A ``[blocks]`` candidate-index tensor.

        Returns
        -------
        dict of int to tuple of (str, int)
            The chain of every block in the search slice.
        """
        indices = genome.tolist()
        return {
            block: self.option_chains[block][int(index)]
            for block, index in zip(self.blocks, indices, strict=True)
        }

    def _tournament(self, scores: torch_type.Tensor, count: int) -> torch_type.Tensor:
        """Return ``count`` parent indices, each the best of a random tournament."""
        size = min(self.tournament_size, scores.numel())
        # Sample each tournament without replacement: a tournament can never draw the same
        # genome twice, and a full-size tournament is a deterministic best-of-population.
        draws = torch.rand(
            (count, scores.numel()),
            dtype=torch.float64,
            device=self.device,
            generator=self.generator,
        )
        contenders = torch.topk(draws, size, dim=1, largest=False).indices
        winners = torch.argmin(scores[contenders], dim=1)
        return contenders[torch.arange(count, dtype=torch.int64, device=self.device), winners]

    def _offspring(self) -> torch_type.Tensor:
        """Return one elite-and-bred generation, optionally with island migration."""
        if self.scores is None:
            raise RuntimeError("evaluate the population before breeding")
        children = self.genomes.clone()
        sizes = [self.population // self.islands] * self.islands
        start = 0
        for size in sizes:
            stop = start + size
            island_scores = self.scores[start:stop]
            elite_count = min(size, max(1, round(size * self.elite_fraction)))
            elite = torch.topk(island_scores, elite_count, largest=False).indices
            children[start : start + elite_count] = self.genomes[start:stop][elite]
            bred = size - elite_count
            if bred > 0:
                parents_a = start + self._tournament(island_scores, bred)
                parents_b = start + self._tournament(island_scores, bred)
                pick = (
                    torch.rand(
                        (bred, len(self.blocks)),
                        dtype=torch.float64,
                        device=self.device,
                        generator=self.generator,
                    )
                    < 0.5
                )
                crossover = torch.where(pick, self.genomes[parents_a], self.genomes[parents_b])
                children[start + elite_count : stop] = self._mutate(crossover, self.mutation_rate)
            start = stop
        return children

    def _migrate(self) -> None:
        """Exchange elites between worker islands, replacing the destination worst."""
        if self.islands < 2 or self.migrants < 1 or self.scores is None:
            return
        size = self.population // self.islands
        count = min(self.migrants, size)
        genomes = self.genomes.clone()
        scores = self.scores.clone()
        if self.exchange == "agrp":
            # Adapted MQT AGrp: every worker returns its best migrants, the master keeps
            # the global elite set, and that set re-seeds the worst slot of every worker.
            returned_genomes: list[torch_type.Tensor] = []
            returned_scores: list[torch_type.Tensor] = []
            for island in range(self.islands):
                start = island * size
                best = torch.topk(self.scores[start : start + size], count, largest=False).indices
                returned_genomes.append(self.genomes[start + best])
                returned_scores.append(self.scores[start + best])
            elite_genomes = torch.cat(returned_genomes)
            elite_scores = torch.cat(returned_scores)
            master = torch.topk(elite_scores, count, largest=False).indices
            elite_genomes = elite_genomes[master]
            elite_scores = elite_scores[master]
            for island in range(self.islands):
                start = island * size
                worst = torch.topk(self.scores[start : start + size], count, largest=True).indices
                genomes[start + worst] = elite_genomes
                scores[start + worst] = elite_scores
            self.genomes = genomes
            self.scores = scores
            return
        for island in range(self.islands):
            source_start = island * size
            target_start = ((island + 1) % self.islands) * size
            best = torch.topk(
                self.scores[source_start : source_start + size], count, largest=False
            ).indices
            worst = torch.topk(
                self.scores[target_start : target_start + size], count, largest=True
            ).indices
            genomes[target_start + worst] = self.genomes[source_start + best]
            # The copied genomes carry known scores, so the population stays evaluated and
            # the next generation can breed without an extra migration re-evaluation.
            scores[target_start + worst] = self.scores[source_start + best]
        self.genomes = genomes
        self.scores = scores

    def _update_best(self, scores: torch_type.Tensor) -> None:
        """Record the global incumbent and the island that produced it."""
        index = int(torch.argmin(scores))
        objective = float(scores[index])
        if objective < self.best_objective - 1e-9:
            size = self.population // self.islands
            self.best_objective = objective
            self.best_genome = self.genomes[index].clone()
            self.best_generation = self.generation
            self.best_island = index // size

    def run(
        self, generations: int, *, check: int = 0, deadline: float | None = None
    ) -> PopulationResult:
        """Evolve the initial population for a fixed number of generations.

        Parameters
        ----------
        generations : int
            The number of evolved generations.  Zero only evaluates the initial
            population.
        check : int, optional
            Compare the first ``check`` initial genomes with a fresh
            :class:`IncrementalObjective` and raise when they differ.  Zero disables the
            check.  Defaults to zero.
        deadline : float or None, optional
            A :func:`time.monotonic` value to stop breeding at, or None to run the
            generation budget out.  The initial population is always evaluated.  Defaults
            to None.

        Returns
        -------
        PopulationResult
            The incumbent schedule, its exact objective, and run counters.
            ``generations`` is the number actually evolved.

        Raises
        ------
        ValueError
            When ``generations`` is negative.
        AssertionError
            When ``check`` is positive and a device score differs from the exact evaluator.
        """
        if generations < 0:
            raise ValueError("generations must not be negative")
        started = time.perf_counter()
        self.generation = 0
        self.best_objective = math.inf
        self.history = []
        scores = self.evaluate()
        if check > 0:
            self._check(scores, min(check, self.population))
        self._update_best(scores)
        self.history.append(self.best_objective)
        initial_objective = float(scores[0])
        evaluations = self.population
        completed = 0
        for generation in range(1, generations + 1):
            if deadline is not None and time.monotonic() >= deadline:
                break
            if (
                self.islands > 1
                and self.migration_interval > 0
                and generation % self.migration_interval == 0
            ):
                self._migrate()
            self.genomes = self._offspring()
            self.generation = generation
            scores = self.evaluate()
            self._update_best(scores)
            self.history.append(self.best_objective)
            evaluations += self.population
            completed = generation
        elapsed = time.perf_counter() - started
        return PopulationResult(
            schedule=self.schedule(self.best_genome),
            objective=self.best_objective,
            initial_objective=initial_objective,
            generations=completed,
            evaluations=evaluations,
            seconds=elapsed,
            best_generation=self.best_generation,
            best_island=self.best_island,
            history=tuple(self.history),
        )

    def _check(self, scores: torch_type.Tensor, count: int) -> None:
        """Raise when a device score differs from a fresh exact evaluator."""
        from .incremental import IncrementalObjective

        for index in range(count):
            verifier = IncrementalObjective(self.optimizer, self.evaluator.targets)
            verifier.reset(self.schedule(self.genomes[index]))
            expected = verifier.objective
            actual = float(scores[index])
            if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-6):
                raise AssertionError(
                    f"device score {actual!r} differs from exact objective {expected!r}"
                )

    def save_state(self, path: str | Path) -> Path:
        """Write the genomes and generation counter to one torch archive.

        The effect table itself is not duplicated; persist it with
        :meth:`EffectTable.save` and reconstruct this population against the loaded table.

        Parameters
        ----------
        path : str or pathlib.Path
            Destination file.

        Returns
        -------
        pathlib.Path
            The written path.
        """
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "genomes": self.genomes.detach().cpu(),
                "generation": self.generation,
                "best_genome": self.best_genome.detach().cpu(),
                "best_objective": self.best_objective,
            },
            destination,
        )
        return destination

    def load_state(self, path: str | Path) -> None:
        """Load a state written by :meth:`save_state` into this population.

        Parameters
        ----------
        path : str or pathlib.Path
            The torch archive.

        Raises
        ------
        ValueError
            When the stored population shape or an option index does not fit this table.
        """
        payload = torch.load(Path(path), weights_only=False)
        genomes = payload["genomes"].to(device=self.device, dtype=torch.int64)
        best = payload["best_genome"].to(device=self.device, dtype=torch.int64)
        if genomes.shape != (self.population, len(self.blocks)):
            raise ValueError("the stored population shape does not fit this table")
        if best.shape != (len(self.blocks),):
            raise ValueError("the stored incumbent shape does not fit this table")
        if bool(((genomes < 0) | (genomes >= self.lengths.unsqueeze(0))).any()):
            raise ValueError("a stored genome option index is outside its candidate list")
        self.genomes = genomes
        self.best_genome = best
        self.generation = int(payload["generation"])
        self.best_objective = float(payload["best_objective"])
        self.scores = None
        self.totals = None

    def evaluate_genome(self, genome: torch_type.Tensor) -> float:
        """Return the exact objective of one genome.

        Parameters
        ----------
        genome : torch.Tensor
            A ``[blocks]`` candidate-index tensor.

        Returns
        -------
        float
            The exact objective.
        """
        return float(self.evaluate(genome.unsqueeze(0))[0])


def _check_supported(evaluator: IncrementalObjective) -> None:
    """Reject a target configuration the population prototype cannot price exactly."""
    from .gpu_search import _check_supported as check_batched

    check_batched(evaluator)
    for target in evaluator.targets:
        if target.flow == "ndy":
            raise NotImplementedError(
                "the population pricer does not price non-declining-yield flow"
            )
