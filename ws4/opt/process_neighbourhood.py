"""Bounded hill-climb over process-conditioned schedule candidates.

P192 ranks a supplied candidate set. This module adds a deterministic search loop: a caller
supplies the neighbour function, every unseen neighbour is evaluated through P192, and the
search keeps strict improvements until the iteration bound or a non-improving round.

The caller owns the schedule mutation grammar. That keeps the search testable and avoids
inventing treatment semantics or hidden spatial moves.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from ..ecosystem.bridge import VolumeBridgeConfig
from ..ecosystem.fire import FireConfig, FireEdge
from ..ecosystem.process import Process
from ..ecosystem.regeneration import RegenerationConfig
from ..ecosystem.state import CohortState
from ..ecosystem.succession import SuccessionConfig
from .objective import Target
from .process_search import (
    ProcessSearchCandidate,
    ProcessSearchEvaluation,
    search_process_candidates,
)

PROCESS_NEIGHBOURHOOD_VERSION: Final[str] = "ws4.process-neighbourhood.v1"


class ProcessNeighbourhoodError(ValueError):
    """Raised when a process neighbourhood search is invalid."""


NeighbourFunction = Callable[[ProcessSearchCandidate], Sequence[ProcessSearchCandidate]]


@dataclass(frozen=True)
class ProcessNeighbourhoodStep:
    """One completed neighbourhood round.

    Attributes
    ----------
    iteration : int
        One-based round number.
    candidate_id : str
        Candidate selected for the next round.
    objective : float
        Its objective.
    improved : bool
        Whether the selected candidate strictly improved the incumbent.
    evaluated : int
        Number of unseen neighbours evaluated in the round.
    """

    iteration: int
    candidate_id: str
    objective: float
    improved: bool
    evaluated: int


@dataclass(frozen=True)
class ProcessNeighbourhoodResult:
    """The outcome of a bounded process neighbourhood search.

    Attributes
    ----------
    initial : ProcessSearchCandidate
        Starting candidate.
    best : ProcessSearchEvaluation
        Best evaluation found.
    history : tuple of ProcessNeighbourhoodStep
        Completed rounds.
    evaluations : tuple of ProcessSearchEvaluation
        Every evaluated candidate, including the initial one.
    seed : int
        Shared random-tape seed.
    horizon_years : int
        Evaluation horizon.
    targets : tuple of Target
        Targets used for every candidate.
    max_iterations : int
        Round bound.
    """

    initial: ProcessSearchCandidate
    best: ProcessSearchEvaluation
    history: tuple[ProcessNeighbourhoodStep, ...]
    evaluations: tuple[ProcessSearchEvaluation, ...]
    seed: int
    horizon_years: int
    targets: tuple[Target, ...]
    max_iterations: int

    @property
    def iterations(self) -> int:
        """Return the number of completed rounds.

        Returns
        -------
        int
            Completed rounds.
        """
        return len(self.history)

    def summary(self) -> dict[str, object]:
        """Return a stable search summary.

        Returns
        -------
        dict
            Version, bounds, best candidate, and completed rounds.
        """
        return {
            "schema_version": PROCESS_NEIGHBOURHOOD_VERSION,
            "seed": self.seed,
            "horizon_years": self.horizon_years,
            "max_iterations": self.max_iterations,
            "iterations": self.iterations,
            "initial_candidate": self.initial.candidate_id,
            "best_candidate": self.best.candidate.candidate_id,
            "best_objective": self.best.objective,
            "target_accounts": [target.account for target in self.targets],
            "evaluated_candidates": [item.candidate.candidate_id for item in self.evaluations],
            "history": [
                {
                    "iteration": step.iteration,
                    "candidate_id": step.candidate_id,
                    "objective": step.objective,
                    "improved": step.improved,
                    "evaluated": step.evaluated,
                }
                for step in self.history
            ],
        }

    def write(self, out_dir: Path) -> None:
        """Write the history and summary artifacts.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.
        """
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        history = self.summary()["history"]
        if not isinstance(history, list):
            raise ProcessNeighbourhoodError("history summary is malformed")
        pd.DataFrame(history).to_csv(target / "process_neighbourhood_history.csv", index=False)
        (target / "process_neighbourhood_search.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def _positive_int(value: object, field: str) -> int:
    """Return a positive integer.

    Parameters
    ----------
    value : object
        Candidate value.
    field : str
        Field name for the error.

    Returns
    -------
    int
        The validated value.

    Raises
    ------
    ProcessNeighbourhoodError
        If the value is not a positive integer.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProcessNeighbourhoodError(f"{field} must be a positive integer")
    return value


def search_process_neighbourhood(
    state: CohortState,
    edges: Sequence[FireEdge],
    initial: ProcessSearchCandidate,
    neighbours: NeighbourFunction,
    block_fragments: Mapping[int, Sequence[int]],
    *,
    horizon_years: int,
    fire: FireConfig,
    targets: Sequence[Target],
    max_iterations: int,
    succession: SuccessionConfig | None = None,
    regeneration: RegenerationConfig | None = None,
    bridge: VolumeBridgeConfig | None = None,
    succession_process: Process | None = None,
    harvest_fraction: float = 1.0,
    seed: int = 0,
) -> ProcessNeighbourhoodResult:
    """Run a bounded strict-improvement search over process candidates.

    Parameters
    ----------
    state : CohortState
        Initial cohort state.
    edges : sequence of FireEdge
        Landscape graph.
    initial : ProcessSearchCandidate
        Starting candidate.
    neighbours : callable
        Returns candidate neighbours for one candidate. The caller owns schedule mutations.
    block_fragments : mapping of int to sequence of int
        Block to fragment ids.
    horizon_years : int
        Evaluation horizon.
    fire : FireConfig
        Fire and salvage parameters.
    targets : sequence of Target
        Level targets used to price every candidate.
    max_iterations : int
        Maximum number of rounds.
    succession : SuccessionConfig or None, optional
        Default succession parameters.
    regeneration : RegenerationConfig or None, optional
        Regeneration parameters.
    bridge : VolumeBridgeConfig or None, optional
        Provisional volume bridge parameters.
    succession_process : Process or None, optional
        Override the default succession source.
    harvest_fraction : float, optional
        Fraction removed by a harvest (default 1.0).
    seed : int, optional
        Shared random-tape seed (default zero).

    Returns
    -------
    ProcessNeighbourhoodResult
        Best candidate, round history, and all evaluations.

    Raises
    ------
    ProcessNeighbourhoodError
        If the bound, targets, or neighbour output is invalid.
    ProcessSearchError
        If a candidate evaluation or ranking is invalid.
    """
    bound = _positive_int(max_iterations, "max_iterations")
    if not isinstance(initial, ProcessSearchCandidate):
        raise ProcessNeighbourhoodError("initial must be a ProcessSearchCandidate")
    if not targets:
        raise ProcessNeighbourhoodError("a neighbourhood search needs at least one target")
    first = search_process_candidates(
        state,
        edges,
        (initial,),
        block_fragments,
        horizon_years=horizon_years,
        fire=fire,
        targets=targets,
        succession=succession,
        regeneration=regeneration,
        bridge=bridge,
        succession_process=succession_process,
        harvest_fraction=harvest_fraction,
        seed=seed,
    ).results[0]
    evaluations: list[ProcessSearchEvaluation] = [first]
    seen = {initial.candidate_id}
    history: list[ProcessNeighbourhoodStep] = []
    current = first
    for iteration in range(1, bound + 1):
        proposed = neighbours(current.candidate)
        if not isinstance(proposed, Sequence):
            raise ProcessNeighbourhoodError("neighbours must return a sequence of candidates")
        unique: list[ProcessSearchCandidate] = []
        ids: set[str] = set()
        for candidate in proposed:
            if not isinstance(candidate, ProcessSearchCandidate):
                raise ProcessNeighbourhoodError(
                    "neighbours must contain ProcessSearchCandidate values"
                )
            if candidate.candidate_id in ids:
                raise ProcessNeighbourhoodError(
                    f"duplicate neighbour id: {candidate.candidate_id!r}"
                )
            ids.add(candidate.candidate_id)
            if candidate.candidate_id not in seen:
                unique.append(candidate)
        if not unique:
            break
        ranked = search_process_candidates(
            state,
            edges,
            unique,
            block_fragments,
            horizon_years=horizon_years,
            fire=fire,
            targets=targets,
            succession=succession,
            regeneration=regeneration,
            bridge=bridge,
            succession_process=succession_process,
            harvest_fraction=harvest_fraction,
            seed=seed,
        )
        evaluations.extend(ranked.results)
        seen.update(item.candidate.candidate_id for item in ranked.results)
        best_neighbour = ranked.best
        improved = best_neighbour.objective < current.objective
        history.append(
            ProcessNeighbourhoodStep(
                iteration=iteration,
                candidate_id=best_neighbour.candidate.candidate_id,
                objective=best_neighbour.objective,
                improved=improved,
                evaluated=len(unique),
            )
        )
        if not improved:
            break
        current = best_neighbour
    return ProcessNeighbourhoodResult(
        initial=initial,
        best=current,
        history=tuple(history),
        evaluations=tuple(evaluations),
        seed=seed,
        horizon_years=horizon_years,
        targets=tuple(targets),
        max_iterations=bound,
    )
