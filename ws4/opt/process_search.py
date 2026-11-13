"""Deterministic candidate search over process-conditioned schedules.

The estate optimizer still searches account overlays. This module evaluates a supplied set of
candidate schedules through the P190 process evaluator and ranks them with the P191 objective
adapter. It is the bridge to a future metaheuristic over process runs, not a replacement for
the existing optimizer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from ..ecosystem.bridge import VolumeBridgeConfig
from ..ecosystem.evaluation import (
    ProcessScheduleEvaluation,
    evaluate_process_schedule,
)
from ..ecosystem.fire import FireConfig, FireEdge
from ..ecosystem.process import Process
from ..ecosystem.regeneration import RegenerationConfig
from ..ecosystem.state import CohortState
from ..ecosystem.succession import SuccessionConfig
from .objective import Target

PROCESS_SEARCH_VERSION: Final[str] = "ws4.process-candidate-search.v1"


class ProcessSearchError(ValueError):
    """Raised when a process candidate search is invalid."""


@dataclass(frozen=True)
class ProcessSearchCandidate:
    """One candidate schedule for a process search.

    Parameters
    ----------
    candidate_id : str
        Stable candidate label, unique within a search.
    schedule : mapping of int to sequence of (str, int)
        Block to ordered treatment/offset entries.
    """

    candidate_id: str
    schedule: Mapping[int, Sequence[tuple[str, int]]]

    def __post_init__(self) -> None:
        """Validate the candidate id and schedule mapping."""
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise ProcessSearchError("candidate_id must be a non-empty string")
        if not isinstance(self.schedule, Mapping):
            raise ProcessSearchError("schedule must be a mapping")


@dataclass(frozen=True)
class ProcessSearchEvaluation:
    """One candidate and its process evaluation.

    Attributes
    ----------
    candidate : ProcessSearchCandidate
        The candidate schedule.
    evaluation : ProcessScheduleEvaluation
        Its process-conditioned evaluation.
    """

    candidate: ProcessSearchCandidate
    evaluation: ProcessScheduleEvaluation

    @property
    def objective(self) -> float:
        """Return the candidate objective.

        Returns
        -------
        float
            The weighted penalty.

        Raises
        ------
        ProcessSearchError
            If the evaluation has no objective.
        """
        if self.evaluation.objective is None:
            raise ProcessSearchError("candidate evaluation has no objective")
        return self.evaluation.objective


@dataclass(frozen=True)
class ProcessSearchResult:
    """A ranked set of process candidate evaluations.

    Attributes
    ----------
    results : tuple of ProcessSearchEvaluation
        Evaluations in input order.
    seed : int
        Shared random-tape seed.
    horizon_years : int
        Evaluation horizon.
    targets : tuple of Target
        Targets used for every candidate.
    """

    results: tuple[ProcessSearchEvaluation, ...]
    seed: int
    horizon_years: int
    targets: tuple[Target, ...]

    @property
    def ranking(self) -> tuple[ProcessSearchEvaluation, ...]:
        """Return candidates sorted by objective and id.

        Returns
        -------
        tuple of ProcessSearchEvaluation
            Best candidate first.
        """
        return tuple(
            sorted(self.results, key=lambda item: (item.objective, item.candidate.candidate_id))
        )

    @property
    def best(self) -> ProcessSearchEvaluation:
        """Return the best candidate.

        Returns
        -------
        ProcessSearchEvaluation
            The lowest-objective candidate.
        """
        return self.ranking[0]

    def summary(self) -> dict[str, object]:
        """Return a stable ranking summary.

        Returns
        -------
        dict
            Version, search inputs, best candidate, and ranked rows.
        """
        rows = []
        for rank, item in enumerate(self.ranking, start=1):
            accounts = {
                str(row.account): float(str(row.value))
                for row in item.evaluation.accounts.itertuples(index=False)
            }
            rows.append(
                {
                    "rank": rank,
                    "candidate_id": item.candidate.candidate_id,
                    "objective": item.objective,
                    "terms": list(item.evaluation.terms),
                    "harvest_area_ha": accounts.get("harvest.area_ha_total", 0.0),
                    "biomass_t": accounts.get("state.biomass_t", 0.0),
                }
            )
        return {
            "schema_version": PROCESS_SEARCH_VERSION,
            "seed": self.seed,
            "horizon_years": self.horizon_years,
            "target_accounts": [target.account for target in self.targets],
            "candidate_count": len(self.results),
            "best_candidate": self.best.candidate.candidate_id,
            "best_objective": self.best.objective,
            "ranking": rows,
        }

    def write(self, out_dir: Path) -> None:
        """Write the ranking CSV and JSON summary.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.
        """
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        rows = self.summary()["ranking"]
        if not isinstance(rows, list):
            raise ProcessSearchError("ranking summary is malformed")
        frame = pd.DataFrame(rows)
        frame.to_csv(target / "process_candidate_ranking.csv", index=False)
        (target / "process_candidate_search.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def search_process_candidates(
    state: CohortState,
    edges: Sequence[FireEdge],
    candidates: Sequence[ProcessSearchCandidate],
    block_fragments: Mapping[int, Sequence[int]],
    *,
    horizon_years: int,
    fire: FireConfig,
    targets: Sequence[Target],
    succession: SuccessionConfig | None = None,
    regeneration: RegenerationConfig | None = None,
    bridge: VolumeBridgeConfig | None = None,
    succession_process: Process | None = None,
    harvest_fraction: float = 1.0,
    seed: int = 0,
) -> ProcessSearchResult:
    """Evaluate and rank candidate schedules through the process engine.

    Every candidate uses the same seed and block mapping, so differences come from the
    schedules rather than from the random tape.

    Parameters
    ----------
    state : CohortState
        Initial cohort state.
    edges : sequence of FireEdge
        Landscape graph.
    candidates : sequence of ProcessSearchCandidate
        Candidate schedules.
    block_fragments : mapping of int to sequence of int
        Block to fragment ids.
    horizon_years : int
        Evaluation horizon.
    fire : FireConfig
        Fire and salvage parameters.
    targets : sequence of Target
        Level targets used to price every candidate.
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
    ProcessSearchResult
        Candidate evaluations and ranking.

    Raises
    ------
    ProcessSearchError
        If the candidate list or target list is empty, ids are duplicated, or a candidate
        evaluation lacks an objective.
    """
    if not candidates:
        raise ProcessSearchError("a candidate search needs at least one candidate")
    if not targets:
        raise ProcessSearchError("a candidate search needs at least one target")
    ids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, ProcessSearchCandidate):
            raise ProcessSearchError("candidates must contain ProcessSearchCandidate values")
        if candidate.candidate_id in ids:
            raise ProcessSearchError(f"duplicate candidate id: {candidate.candidate_id!r}")
        ids.add(candidate.candidate_id)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ProcessSearchError("seed must be a non-negative integer")
    evaluations: list[ProcessSearchEvaluation] = []
    for candidate in candidates:
        evaluation = evaluate_process_schedule(
            state,
            edges,
            candidate.schedule,
            block_fragments,
            horizon_years=horizon_years,
            fire=fire,
            succession=succession,
            regeneration=regeneration,
            bridge=bridge,
            succession_process=succession_process,
            targets=targets,
            harvest_fraction=harvest_fraction,
            scenario_id=candidate.candidate_id,
            seed=seed,
        )
        evaluations.append(ProcessSearchEvaluation(candidate=candidate, evaluation=evaluation))
    return ProcessSearchResult(
        results=tuple(evaluations),
        seed=seed,
        horizon_years=horizon_years,
        targets=tuple(targets),
    )
