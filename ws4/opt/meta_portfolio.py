"""A fixed round-robin master/worker portfolio over heterogeneous metaheuristics.

The portfolio adapts the archive's AGrp structure to WS4 without sharing mutable worker
state.  A master owns one bounded elite archive; each worker slot runs one method for a
fixed budget from an elite the master records; the worker returns a complete schedule; the
master verifies that schedule with a fresh :class:`~ws4.opt.incremental.IncrementalObjective`
and records the migration.  Workers never receive the master's evaluator, archive, or each
other's population, tabu list, or annealing state.

This is the first bounded version: worker slots are allocated in a fixed round-robin and
there is no adaptive credit.  The design note is
``notes/design/ws4-metaheuristic-portfolio.md``.

The CPU simulated annealer and CPU LNS operator are the reference paths.  When an
:class:`~ws4.opt.gpu_effects.EffectTable` is supplied, the GA slot uses the GPU
:class:`~ws4.opt.gpu_ga.GenomePopulation` and a LNS slot may use the batched GPU
:class:`~ws4.opt.gpu_search.BatchedLnsSearch`.  The GA and GPU LNS paths keep their own
narrow exactness contract; the master still verifies every returned schedule with the exact
incremental objective.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .core import Problem
from .incremental import IncrementalObjective
from .operators import (
    Chain,
    LnsOperator,
    OperatorRegistry,
    Schedule,
    ShiftOperator,
    ToggleOperator,
)
from .solvers import solve_ils, solve_sa_delta, solve_tabu

if TYPE_CHECKING:
    from .engine import Optimizer
    from .gpu_effects import EffectTable
    from .gpu_ga import GenomePopulation
    from .objective import Target

#: The method a worker slot runs.
WorkerMethod = Literal["sa", "tabu", "ils", "ga", "lns"]

#: The LNS pricing backend.
LnsBackend = Literal["cpu", "gpu"]

_METHODS = {"sa", "tabu", "ils", "ga", "lns"}


def _schedule_signature(schedule: Mapping[int, Chain]) -> tuple[tuple[int, Chain], ...]:
    """Return a hashable signature for a schedule, ignoring untreated blocks."""
    return tuple(sorted((block, chain) for block, chain in schedule.items() if chain))


def _same_objective(left: float, right: float) -> bool:
    """Return whether two objectives agree, treating matching infinities as equal."""
    if math.isinf(left) or math.isinf(right):
        return math.isinf(left) and math.isinf(right) and (left > 0) == (right > 0)
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-6)


@dataclass(frozen=True)
class WorkerSpec:
    """One fixed worker slot in the round-robin allocation.

    Parameters
    ----------
    name : str
        The stable worker label, unique within a portfolio.
    method : {"sa", "tabu", "ils", "ga", "lns"}
        The metaheuristic the slot runs.
    budget : int
        The slot's fixed budget: iterations for SA, tabu, ILS, and CPU LNS; generations for
        GA; proposal rounds for GPU LNS.
    seed : int
        The worker's own random seed.  The master seed does not leak into the worker.
    diverse : bool, optional
        When true the slot is seeded from the far end of the archive (the most different
        retained elite) instead of the round-robin position.  Defaults to false.

    Raises
    ------
    ValueError
        When the name is empty, the method is unknown, or the budget is negative.
    """

    name: str
    method: WorkerMethod
    budget: int
    seed: int
    diverse: bool = False

    def __post_init__(self) -> None:
        """Reject an invalid worker slot."""
        if not self.name.strip():
            raise ValueError("a worker needs a non-empty name")
        if self.method not in _METHODS:
            raise ValueError(f"unknown worker method {self.method!r}")
        if self.budget < 0:
            raise ValueError("a worker budget must not be negative")

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready record.

        Returns
        -------
        dict of str to object
            The worker's name, method, budget, seed, and diversity flag.
        """
        return {
            "name": self.name,
            "method": self.method,
            "budget": self.budget,
            "seed": self.seed,
            "diverse": self.diverse,
        }


@dataclass(frozen=True)
class PortfolioElite:
    """A complete schedule retained by the master.

    Parameters
    ----------
    objective : float
        The exact incremental objective of ``schedule``.
    schedule : dict of int to tuple of (str, int)
        The block-to-chain assignment.
    source : str
        A label for the originating worker, such as ``"round-2:sa-1"``.
    method : str
        The method that produced the schedule.
    worker : str
        The worker slot that produced the schedule.
    round_index : int
        The zero-based round-robin round that produced the schedule.
    """

    objective: float
    schedule: Schedule
    source: str
    method: str
    worker: str
    round_index: int

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready record without the schedule.

        Returns
        -------
        dict of str to object
            The objective, provenance, round, and block count.
        """
        return {
            "objective": round(float(self.objective), 6),
            "source": self.source,
            "method": self.method,
            "worker": self.worker,
            "round": self.round_index,
            "blocks": len(self.schedule),
        }


class PortfolioArchive:
    """A bounded master archive of distinct elite schedules.

    Unlike the Pareto archive in :mod:`ws4.opt.archive`, this archive ranks one scalar
    objective and keeps the best distinct schedules.  Distinctness is by complete schedule
    content, so a worker cannot flood the archive with copies of the same elite.

    Parameters
    ----------
    capacity : int, optional
        The most elites to retain.  Defaults to eight.

    Raises
    ------
    ValueError
        When ``capacity`` is below one.
    """

    def __init__(self, capacity: int = 8) -> None:
        """Create an empty archive."""
        if capacity < 1:
            raise ValueError("archive capacity must be at least one")
        self.capacity = capacity
        self._elites: list[PortfolioElite] = []

    @property
    def elites(self) -> list[PortfolioElite]:
        """Return the retained elites, lowest objective first.

        Returns
        -------
        list of PortfolioElite
            A copy of the retained list.
        """
        return list(self._elites)

    def add(self, elite: PortfolioElite) -> bool:
        """Consider one elite for the archive.

        Parameters
        ----------
        elite : PortfolioElite
            The candidate schedule.

        Returns
        -------
        bool
            True when the candidate was retained or replaced a worse copy of the same
            schedule, and false when it was a duplicate or worse than the full archive.
        """
        signature = _schedule_signature(elite.schedule)
        for index, existing in enumerate(self._elites):
            if _schedule_signature(existing.schedule) == signature:
                if elite.objective < existing.objective:
                    self._elites[index] = elite
                    self._sort()
                    return True
                return False
        if len(self._elites) < self.capacity:
            self._elites.append(elite)
            self._sort()
            return True
        worst = self._elites[-1]
        if elite.objective < worst.objective:
            self._elites[-1] = elite
            self._sort()
            return True
        return False

    def _sort(self) -> None:
        """Order the archive by objective and then by source."""
        self._elites.sort(key=lambda item: (item.objective, item.source))


@dataclass(frozen=True)
class MethodContribution:
    """The measured contribution of one method to a portfolio run.

    Parameters
    ----------
    method : str
        The method name.
    slices : int
        The number of worker slices the method ran.
    accepted : int
        The number of returned schedules the master retained.
    improvements : int
        The number of slices that improved on their seed elite.
    best_objective : float
        The best objective the method returned, or ``inf`` when it never ran.
    best_gain : float
        The largest seed-to-return objective improvement the method produced.
    seconds : float
        The summed worker wall-clock seconds.
    evaluations : int
        The summed evaluation count reported by the workers.
    """

    method: str
    slices: int
    accepted: int
    improvements: int
    best_objective: float
    best_gain: float
    seconds: float
    evaluations: int

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready record.

        Returns
        -------
        dict of str to object
            The contribution counters, with ``None`` for a method that never ran.
        """
        return {
            "method": self.method,
            "slices": self.slices,
            "accepted": self.accepted,
            "improvements": self.improvements,
            "best_objective": (
                None if math.isinf(self.best_objective) else round(self.best_objective, 6)
            ),
            "best_gain": round(self.best_gain, 6),
            "seconds": round(self.seconds, 6),
            "evaluations": self.evaluations,
        }


@dataclass
class _ContributionAccumulator:
    """Mutable counters for one method before they are frozen into a report row."""

    method: str
    slices: int = 0
    accepted: int = 0
    improvements: int = 0
    best_objective: float = math.inf
    best_gain: float = 0.0
    seconds: float = 0.0
    evaluations: int = 0

    def freeze(self) -> MethodContribution:
        """Return the immutable contribution record.

        Returns
        -------
        MethodContribution
            The current counters.
        """
        return MethodContribution(
            method=self.method,
            slices=self.slices,
            accepted=self.accepted,
            improvements=self.improvements,
            best_objective=self.best_objective,
            best_gain=self.best_gain,
            seconds=self.seconds,
            evaluations=self.evaluations,
        )


@dataclass(frozen=True)
class Migration:
    """One explicit master-to-worker seed and worker-to-master elite return.

    Parameters
    ----------
    round_index : int
        The zero-based round-robin round.
    worker : str
        The worker slot name.
    method : str
        The worker's method.
    source : str
        The archive elite's source label.
    source_rank : int
        The archive rank used to seed the worker, zero-based.
    seeded_objective : float
        The exact objective of the seed elite.
    returned_objective : float
        The exact objective of the returned schedule.
    improved : bool
        Whether the return beat the seed.
    accepted : bool
        Whether the return entered the master archive.
    seconds : float
        The worker slice's wall-clock time.
    evaluations : int
        The worker's reported evaluation count.
    """

    round_index: int
    worker: str
    method: str
    source: str
    source_rank: int
    seeded_objective: float
    returned_objective: float
    improved: bool
    accepted: bool
    seconds: float
    evaluations: int

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready migration record.

        Returns
        -------
        dict of str to object
            The provenance, seed and return objectives, and counters.
        """
        return {
            "round": self.round_index,
            "worker": self.worker,
            "method": self.method,
            "source": self.source,
            "source_rank": self.source_rank,
            "seeded_objective": round(self.seeded_objective, 6),
            "returned_objective": round(self.returned_objective, 6),
            "improved": self.improved,
            "accepted": self.accepted,
            "seconds": round(self.seconds, 6),
            "evaluations": self.evaluations,
        }


@dataclass(frozen=True)
class _WorkerOutcome:
    """The raw return from one worker slice before master verification."""

    schedule: Schedule
    objective: float
    seconds: float
    evaluations: int


@dataclass(frozen=True)
class PortfolioResult:
    """The verified result of a portfolio run.

    Parameters
    ----------
    schedule : dict of int to tuple of (str, int)
        The best complete schedule.
    objective : float
        Its exact incremental objective, re-evaluated after the search.
    seed_objective : float
        The exact objective of the initial master elite.
    elites : tuple of PortfolioElite
        The retained archive, lowest objective first.
    migrations : tuple of Migration
        Every explicit seed-and-return event, in run order.
    contributions : mapping of str to MethodContribution
        The measured contribution per method.
    workers : tuple of WorkerSpec
        The fixed allocation that ran.
    rounds : int
        The number of round-robin passes completed.
    seconds : float
        The total master wall-clock time, including verification.
    time_to_best : float
        Seconds from the run start to the first best-elite update.
    evaluations : int
        The summed worker evaluation count.
    history : tuple of float
        The best objective after the seed and after every completed slice.
    """

    schedule: Schedule
    objective: float
    seed_objective: float
    elites: tuple[PortfolioElite, ...]
    migrations: tuple[Migration, ...]
    contributions: Mapping[str, MethodContribution]
    workers: tuple[WorkerSpec, ...]
    rounds: int
    seconds: float
    time_to_best: float
    evaluations: int
    history: tuple[float, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready summary without the full schedule.

        Returns
        -------
        dict of str to object
            The objective, archive, contributions, migrations, and counters.
        """
        return {
            "objective": round(self.objective, 6),
            "seed_objective": round(self.seed_objective, 6),
            "rounds": self.rounds,
            "seconds": round(self.seconds, 6),
            "time_to_best": round(self.time_to_best, 6),
            "evaluations": self.evaluations,
            "blocks": len(self.schedule),
            "archive_size": len(self.elites),
            "elites": [elite.as_dict() for elite in self.elites],
            "workers": [worker.as_dict() for worker in self.workers],
            "contributions": {
                name: contribution.as_dict()
                for name, contribution in sorted(self.contributions.items())
            },
            "migrations": [migration.as_dict() for migration in self.migrations],
            "history": [round(value, 6) for value in self.history],
        }


def default_worker_specs(
    *, seed: int = 1, iterations: int = 200, generations: int = 20
) -> tuple[WorkerSpec, ...]:
    """Return the seven-slot AGrp-style fixed allocation.

    The mix is two SA workers, one tabu worker, one ILS worker, one GA worker, one LNS
    worker, and one diverse-restart SA worker.  Tabu and ILS run fewer iterations than SA
    because their existing CPU implementations evaluate whole schedules.  The GA slot needs
    an effect table; callers without one should pass their own worker list.

    Parameters
    ----------
    seed : int, optional
        The first worker seed; each later slot gets the next integer.  Defaults to one.
    iterations : int, optional
        The SA and CPU LNS iteration budget per slice.  Defaults to 200.
    generations : int, optional
        The GA generation budget per slice.  Defaults to 20.

    Returns
    -------
    tuple of WorkerSpec
        The fixed allocation, in round-robin order.

    Raises
    ------
    ValueError
        When a budget is not positive.
    """
    if iterations < 1 or generations < 1:
        raise ValueError("worker budgets must be positive")
    return (
        WorkerSpec("sa-1", "sa", iterations, seed),
        WorkerSpec("sa-2", "sa", iterations, seed + 1),
        WorkerSpec("tabu-1", "tabu", max(1, iterations // 10), seed + 2),
        WorkerSpec("ils-1", "ils", max(1, iterations // 5), seed + 3),
        WorkerSpec("ga-1", "ga", generations, seed + 4),
        WorkerSpec("lns-1", "lns", iterations, seed + 5),
        WorkerSpec("restart-1", "sa", iterations, seed + 6, diverse=True),
    )


class MetaPortfolio:
    """A fixed round-robin master/worker portfolio.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer that owns the candidate chains and account caches.
    targets : sequence of Target
        The exact target set.  Each worker and the master verification build a fresh
        :class:`~ws4.opt.incremental.IncrementalObjective` from it.
    candidates : mapping of int to list of tuple or None, optional
        The common search slice.  None uses every candidate block, or the table's blocks
        when a table is supplied.  When a table is supplied the slice is intersected with
        ``table.blocks`` so GA and CPU workers search the same blocks.
    initial : mapping of int to tuple or None, optional
        The master seed schedule.  None uses each block's first candidate chain.
    table : EffectTable or None, optional
        A sparse effect table on the device to search on.  Required by the GA slot and by
        GPU LNS.
    archive_capacity : int, optional
        The master elite archive capacity.  Defaults to eight.
    workers : sequence of WorkerSpec or None, optional
        The fixed allocation.  None uses :func:`default_worker_specs`.
    rounds : int, optional
        The number of round-robin passes.  Defaults to one.
    temperature : float, optional
        The SA initial temperature.  Defaults to 1000.
    cooling : float, optional
        The SA geometric cooling factor.  Defaults to 0.95.
    tenure : int, optional
        The tabu list length.  Defaults to 10.
    tabu_samples : int, optional
        Candidate moves sampled per tabu iteration.  Defaults to four.
    perturbation : int, optional
        Random moves per ILS perturbation.  Defaults to three.
    ga_population : int, optional
        The GA population size.  Defaults to 64.
    ga_random_fraction : float, optional
        The random fraction of the GA initial population.  Defaults to 0.15.
    ga_mutation_rate : float, optional
        The per-block GA mutation rate.  Defaults to 0.002.
    lns_backend : {"cpu", "gpu"}, optional
        The LNS pricing backend.  Defaults to ``"cpu"``.
    lns_destroy : float, optional
        The CPU LNS destroyed fraction.  Defaults to 0.1.
    lns_max_destroy : int, optional
        The CPU LNS block cap.  Defaults to 64.
    lns_proposals : int, optional
        The GPU LNS proposals per round.  Defaults to 64.
    lns_temperature : float, optional
        The GPU LNS initial temperature.  Defaults to 1000.
    lns_final_temperature : float, optional
        The GPU LNS final temperature.  Defaults to one.

    Raises
    ------
    ValueError
        When a parameter is invalid, a worker method is unavailable, or the worker names
        repeat.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        targets: Sequence[Target],
        *,
        candidates: Mapping[int, Sequence[Chain]] | None = None,
        initial: Mapping[int, Chain] | None = None,
        table: EffectTable | None = None,
        archive_capacity: int = 8,
        workers: Sequence[WorkerSpec] | None = None,
        rounds: int = 1,
        temperature: float = 1000.0,
        cooling: float = 0.95,
        tenure: int = 10,
        tabu_samples: int = 4,
        perturbation: int = 3,
        ga_population: int = 64,
        ga_random_fraction: float = 0.15,
        ga_mutation_rate: float = 0.002,
        lns_backend: LnsBackend = "cpu",
        lns_destroy: float = 0.1,
        lns_max_destroy: int = 64,
        lns_proposals: int = 64,
        lns_temperature: float = 1000.0,
        lns_final_temperature: float = 1.0,
    ) -> None:
        """Store and validate the fixed allocation and worker parameters."""
        if rounds < 1:
            raise ValueError("rounds must be at least one")
        if temperature <= 0.0:
            raise ValueError("temperature must be positive")
        if not 0.0 < cooling <= 1.0:
            raise ValueError("cooling must be in (0, 1]")
        if tenure < 1:
            raise ValueError("tenure must be positive")
        if tabu_samples < 1:
            raise ValueError("tabu_samples must be positive")
        if perturbation < 1:
            raise ValueError("perturbation must be positive")
        if ga_population < 2:
            raise ValueError("ga_population must be at least two")
        if not 0.0 <= ga_random_fraction <= 1.0:
            raise ValueError("ga_random_fraction must be in [0, 1]")
        if not 0.0 <= ga_mutation_rate <= 1.0:
            raise ValueError("ga_mutation_rate must be in [0, 1]")
        if lns_backend not in {"cpu", "gpu"}:
            raise ValueError("lns_backend must be 'cpu' or 'gpu'")
        if not 0.0 < lns_destroy <= 1.0:
            raise ValueError("lns_destroy must be in (0, 1]")
        if lns_max_destroy < 1:
            raise ValueError("lns_max_destroy must be positive")
        if lns_proposals < 1:
            raise ValueError("lns_proposals must be positive")
        if lns_temperature <= 0.0 or lns_final_temperature <= 0.0:
            raise ValueError("LNS temperatures must be positive")

        specs = tuple(workers) if workers is not None else default_worker_specs()
        if not specs:
            raise ValueError("the portfolio needs at least one worker")
        names = [spec.name for spec in specs]
        if len(set(names)) != len(names):
            raise ValueError("worker names must be unique")
        if any(spec.method == "ga" for spec in specs) and table is None:
            raise ValueError("a GA worker needs an effect table")
        if lns_backend == "gpu" and any(spec.method == "lns" for spec in specs) and table is None:
            raise ValueError("GPU LNS workers need an effect table")

        self.optimizer = optimizer
        self.targets = list(targets)
        self.table = table
        self.archive_capacity = archive_capacity
        if archive_capacity < 1:
            raise ValueError("archive capacity must be at least one")
        self.workers = specs
        self.rounds = rounds
        self.temperature = temperature
        self.cooling = cooling
        self.tenure = tenure
        self.tabu_samples = tabu_samples
        self.perturbation = perturbation
        self.ga_population = ga_population
        self.ga_random_fraction = ga_random_fraction
        self.ga_mutation_rate = ga_mutation_rate
        self.lns_backend = lns_backend
        self.lns_destroy = lns_destroy
        self.lns_max_destroy = lns_max_destroy
        self.lns_proposals = lns_proposals
        self.lns_temperature = lns_temperature
        self.lns_final_temperature = lns_final_temperature
        # Toggle, shift, and LNS choose a chain from the block's own candidate list, so a
        # CPU elite stays representable by the table's per-block option rows.  Swap is
        # excluded: it moves a chain to a block where the table may have no row, which the
        # candidate-index GA genome cannot represent.
        weights = optimizer.registry.weights()
        self._move_registry = OperatorRegistry(
            [
                ToggleOperator(weight=weights.get("toggle", 0.0)),
                ShiftOperator(weight=weights.get("shift", 0.0)),
                LnsOperator(
                    weight=weights.get("lns", 0.0),
                    destroy_fraction=lns_destroy,
                    max_destroy=lns_max_destroy,
                ),
            ]
        )
        self._lns_registry = OperatorRegistry(
            [
                LnsOperator(
                    weight=1.0,
                    destroy_fraction=lns_destroy,
                    max_destroy=lns_max_destroy,
                )
            ]
        )

        all_candidates = optimizer.candidates()
        source = candidates if candidates is not None else all_candidates
        unknown = set(source) - set(all_candidates)
        if unknown:
            raise ValueError("the candidate slice names a block the optimizer does not know")
        if table is not None:
            allowed = set(table.blocks)
            self.candidates = {
                block: list(chains)
                for block, chains in source.items()
                if block in allowed and chains
            }
            outside = allowed - set(self.candidates)
            if outside:
                raise ValueError("the effect table names a block outside the candidate slice")
        else:
            self.candidates = {block: list(chains) for block, chains in source.items() if chains}
        if not self.candidates:
            raise ValueError("the portfolio needs at least one candidate block")
        if initial is None:
            seed_schedule: Schedule = {
                block: chains[0] for block, chains in self.candidates.items()
            }
        else:
            seed_schedule = {
                block: chain
                for block, chain in initial.items()
                if block in self.candidates and chain
            }
        if not seed_schedule:
            raise ValueError("the portfolio needs a non-empty seed schedule")
        if table is not None and any(spec.method == "ga" for spec in specs):
            for block, chain in seed_schedule.items():
                try:
                    table.row_id(block, chain)
                except KeyError as exc:
                    raise ValueError(
                        "the effect table has no row for an initial chain; build it with "
                        "the initial schedule in extra_pairs"
                    ) from exc
        self.initial = seed_schedule

    def run(self, *, time_limit: float | None = None) -> PortfolioResult:
        """Run the fixed round-robin and return the verified best schedule.

        Parameters
        ----------
        time_limit : float or None, optional
            Stop before the next worker slice when this many seconds have elapsed.  None
            runs the full fixed allocation.  A time-limited run is not reproducible from
            its seeds alone.

        Returns
        -------
        PortfolioResult
            The verified incumbent, archive, migrations, and contributions.

        Raises
        ------
        ValueError
            When ``time_limit`` is not positive.
        AssertionError
            When a worker's claimed objective differs from a fresh exact evaluation.
        """
        if time_limit is not None and time_limit <= 0.0:
            raise ValueError("time_limit must be positive")
        started = time.monotonic()
        deadline = None if time_limit is None else started + time_limit
        archive = PortfolioArchive(self.archive_capacity)
        seed_objective = self._exact(self.initial)
        archive.add(
            PortfolioElite(
                objective=seed_objective,
                schedule=dict(self.initial),
                source="master:seed",
                method="seed",
                worker="master",
                round_index=0,
            )
        )
        best_schedule = dict(self.initial)
        best_objective = seed_objective
        time_to_best = 0.0
        history = [best_objective]
        migrations: list[Migration] = []
        contributions: dict[str, _ContributionAccumulator] = {}
        evaluations = 0
        completed_rounds = 0
        stopped = False
        ga_workers: dict[str, GenomePopulation] = {}
        for round_index in range(self.rounds):
            ran_in_round = False
            for spec in self.workers:
                if deadline is not None and time.monotonic() >= deadline:
                    stopped = True
                    break
                elites = archive.elites
                rank = self._seed_rank(spec, round_index, len(elites))
                source = elites[rank]
                ran_in_round = True
                outcome = self._run_worker(spec, source, deadline, ga_workers)
                verified = self._exact(outcome.schedule)
                if not _same_objective(outcome.objective, verified):
                    raise AssertionError(
                        f"worker {spec.name!r} claimed objective {outcome.objective!r} "
                        f"but the exact objective is {verified!r}"
                    )
                accepted = archive.add(
                    PortfolioElite(
                        objective=verified,
                        schedule=dict(outcome.schedule),
                        source=f"round-{round_index}:{spec.name}",
                        method=spec.method,
                        worker=spec.name,
                        round_index=round_index,
                    )
                )
                improved = verified < source.objective - 1e-9
                migration = Migration(
                    round_index=round_index,
                    worker=spec.name,
                    method=spec.method,
                    source=source.source,
                    source_rank=rank,
                    seeded_objective=source.objective,
                    returned_objective=verified,
                    improved=improved,
                    accepted=accepted,
                    seconds=outcome.seconds,
                    evaluations=outcome.evaluations,
                )
                migrations.append(migration)
                evaluations += outcome.evaluations
                counter = contributions.setdefault(
                    spec.method, _ContributionAccumulator(method=spec.method)
                )
                counter.slices += 1
                counter.accepted += int(accepted)
                counter.improvements += int(improved)
                counter.best_objective = min(counter.best_objective, verified)
                counter.best_gain = max(counter.best_gain, source.objective - verified)
                counter.seconds += outcome.seconds
                counter.evaluations += outcome.evaluations
                if verified < best_objective - 1e-9:
                    best_schedule = dict(outcome.schedule)
                    best_objective = verified
                    time_to_best = time.monotonic() - started
                history.append(best_objective)
            if ran_in_round:
                completed_rounds += 1
            if stopped:
                break
        final_objective = self._exact(best_schedule)
        if not _same_objective(best_objective, final_objective):
            raise AssertionError(
                f"the incumbent objective {best_objective!r} does not match the final exact "
                f"objective {final_objective!r}"
            )
        return PortfolioResult(
            schedule=dict(best_schedule),
            objective=final_objective,
            seed_objective=seed_objective,
            elites=tuple(archive.elites),
            migrations=tuple(migrations),
            contributions={
                name: counter.freeze() for name, counter in sorted(contributions.items())
            },
            workers=self.workers,
            rounds=completed_rounds,
            seconds=time.monotonic() - started,
            time_to_best=time_to_best,
            evaluations=evaluations,
            history=tuple(history),
        )

    def _seed_rank(self, spec: WorkerSpec, round_index: int, size: int) -> int:
        """Return the archive rank that seeds one worker slice.

        Regular workers receive the global best elite, which is the AGrp master-best
        seeding rule.  A diverse-restart slot walks the archive from the far end so the
        portfolio keeps one exploration stream away from the incumbent.
        """
        if spec.diverse:
            return max(0, size - 1 - (round_index % size))
        return 0

    def _exact(self, schedule: Mapping[int, Chain]) -> float:
        """Return a fresh exact incremental objective for one schedule."""
        evaluator = IncrementalObjective(self.optimizer, self.targets)
        evaluator.reset(dict(schedule))
        return evaluator.objective

    def _run_worker(
        self,
        spec: WorkerSpec,
        source: PortfolioElite,
        deadline: float | None,
        ga_workers: dict[str, GenomePopulation],
    ) -> _WorkerOutcome:
        """Run one worker slot from an elite and return its raw result."""
        seed_schedule = dict(source.schedule)
        started = time.perf_counter()
        if spec.method == "sa":
            outcome = self._run_sa(spec, seed_schedule, deadline)
        elif spec.method == "tabu":
            outcome = self._run_tabu(spec, seed_schedule, deadline)
        elif spec.method == "ils":
            outcome = self._run_ils(spec, seed_schedule, deadline)
        elif spec.method == "ga":
            outcome = self._run_ga(spec, seed_schedule, ga_workers, deadline)
        else:
            outcome = self._run_lns(spec, seed_schedule, deadline)
        return _WorkerOutcome(
            schedule=outcome.schedule,
            objective=outcome.objective,
            seconds=time.perf_counter() - started,
            evaluations=outcome.evaluations,
        )

    def _run_sa(
        self, spec: WorkerSpec, seed_schedule: Schedule, deadline: float | None
    ) -> _WorkerOutcome:
        """Run one CPU simulated-annealing slice."""
        evaluator = IncrementalObjective(self.optimizer, self.targets)
        evaluations = 0

        def on_step(iteration: int, objective: float) -> None:
            nonlocal evaluations
            evaluations = iteration + 1

        schedule, objective = solve_sa_delta(
            evaluator,
            random.Random(spec.seed),
            iterations=spec.budget,
            temperature=self.temperature,
            cooling=self.cooling,
            candidates=self.candidates,
            registry=self._move_registry,
            initial=seed_schedule,
            deadline=deadline,
            on_step=on_step,
        )
        return _WorkerOutcome(schedule, objective, 0.0, evaluations)

    def _run_tabu(
        self, spec: WorkerSpec, seed_schedule: Schedule, deadline: float | None
    ) -> _WorkerOutcome:
        """Run one CPU tabu-search slice with a worker-local evaluator."""
        evaluator = IncrementalObjective(self.optimizer, self.targets)
        evaluations = 0

        def evaluate(schedule: Schedule) -> float:
            nonlocal evaluations
            evaluations += 1
            evaluator.reset(schedule)
            return evaluator.objective

        problem = Problem(
            evaluate=evaluate,
            candidates=self.candidates,
            registry=self._move_registry,
        )
        schedule, objective = solve_tabu(
            problem,
            random.Random(spec.seed),
            iterations=spec.budget,
            tenure=self.tenure,
            samples=self.tabu_samples,
            initial=seed_schedule,
            deadline=deadline,
        )
        return _WorkerOutcome(schedule, objective, 0.0, evaluations)

    def _run_ils(
        self, spec: WorkerSpec, seed_schedule: Schedule, deadline: float | None
    ) -> _WorkerOutcome:
        """Run one CPU iterated-local-search slice with a worker-local evaluator."""
        evaluator = IncrementalObjective(self.optimizer, self.targets)
        evaluations = 0

        def evaluate(schedule: Schedule) -> float:
            nonlocal evaluations
            evaluations += 1
            evaluator.reset(schedule)
            return evaluator.objective

        problem = Problem(
            evaluate=evaluate,
            candidates=self.candidates,
            registry=self._move_registry,
        )
        schedule, objective = solve_ils(
            problem,
            random.Random(spec.seed),
            iterations=spec.budget,
            perturbation=self.perturbation,
            initial=seed_schedule,
            deadline=deadline,
        )
        return _WorkerOutcome(schedule, objective, 0.0, evaluations)

    def _run_ga(
        self,
        spec: WorkerSpec,
        seed_schedule: Schedule,
        ga_workers: dict[str, GenomePopulation],
        deadline: float | None,
    ) -> _WorkerOutcome:
        """Run one GPU population slice from an elite, reusing the slot's device state."""
        from .gpu_ga import GenomePopulation

        if self.table is None:  # pragma: no cover - the constructor rejects this
            raise ValueError("a GA worker needs an effect table")
        population = ga_workers.get(spec.name)
        if population is None:
            evaluator = IncrementalObjective(self.optimizer, self.targets)
            population = GenomePopulation(
                self.optimizer,
                evaluator,
                self.table,
                population=self.ga_population,
                seed=spec.seed,
                seed_schedule=seed_schedule,
                candidates=self.candidates,
                random_fraction=self.ga_random_fraction,
                mutation_rate=self.ga_mutation_rate,
            )
            ga_workers[spec.name] = population
        else:
            population.reseed(seed_schedule)
        result = population.run(spec.budget, deadline=deadline)
        return _WorkerOutcome(result.schedule, result.objective, 0.0, result.evaluations)

    def _run_lns(
        self, spec: WorkerSpec, seed_schedule: Schedule, deadline: float | None
    ) -> _WorkerOutcome:
        """Run one LNS slice on the configured CPU or GPU backend."""
        evaluator = IncrementalObjective(self.optimizer, self.targets)
        if self.lns_backend == "gpu":
            from .gpu_search import BatchedLnsSearch

            if self.table is None:  # pragma: no cover - the constructor rejects this
                raise ValueError("GPU LNS workers need an effect table")
            search = BatchedLnsSearch(
                self.optimizer,
                evaluator,
                self.table,
                proposals=self.lns_proposals,
                temperature=self.lns_temperature,
                final_temperature=self.lns_final_temperature,
                max_destroy=self.lns_max_destroy,
                destroy_fraction=self.lns_destroy,
                seed=spec.seed,
            )
            result = search.run(seed_schedule, rounds=spec.budget)
            return _WorkerOutcome(
                result.schedule,
                result.objective,
                0.0,
                result.proposals,
            )
        evaluations = 0

        def on_step(iteration: int, objective: float) -> None:
            nonlocal evaluations
            evaluations = iteration + 1

        schedule, objective = solve_sa_delta(
            evaluator,
            random.Random(spec.seed),
            iterations=spec.budget,
            temperature=self.temperature,
            cooling=self.cooling,
            candidates=self.candidates,
            registry=self._lns_registry,
            initial=seed_schedule,
            deadline=deadline,
            on_step=on_step,
        )
        return _WorkerOutcome(schedule, objective, 0.0, evaluations)


__all__ = [
    "LnsBackend",
    "MetaPortfolio",
    "MethodContribution",
    "Migration",
    "PortfolioArchive",
    "PortfolioElite",
    "PortfolioResult",
    "WorkerMethod",
    "WorkerSpec",
    "default_worker_specs",
]
