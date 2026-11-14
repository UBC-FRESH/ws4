"""End-to-end process optimization over a deterministic schedule grammar.

P190 evaluates a schedule, P191 prices it, P192 ranks candidates, P193 climbs, and P194 supplies
the moves. This module closes the loop: it runs the hill-climb with a schedule grammar and
returns the best process evaluation together with its search history.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from ..ecosystem.bridge import VolumeBridgeConfig
from ..ecosystem.fire import FireConfig, FireEdge
from ..ecosystem.process import Process
from ..ecosystem.regeneration import RegenerationConfig
from ..ecosystem.state import CohortState
from ..ecosystem.succession import SuccessionConfig
from .objective import Target
from .process_neighbourhood import ProcessNeighbourhoodResult, search_process_neighbourhood
from .process_search import ProcessSearchCandidate, ProcessSearchEvaluation
from .schedule_grammar import ScheduleMoveGrammar

PROCESS_OPTIMIZATION_VERSION: Final[str] = "ws4.process-optimization.v1"


class ProcessOptimizationError(ValueError):
    """Raised when a process optimization request is invalid."""


@dataclass(frozen=True)
class ProcessOptimizationResult:
    """The best schedule and its search trace.

    Attributes
    ----------
    search : ProcessNeighbourhoodResult
        Hill-climb result.
    block_fragments : mapping of int to sequence of int
        Block to fragment ids used by the evaluation.
    """

    search: ProcessNeighbourhoodResult
    block_fragments: Mapping[int, Sequence[int]]

    def __post_init__(self) -> None:
        """Validate and canonicalize the block mapping."""
        if not isinstance(self.block_fragments, Mapping):
            raise ProcessOptimizationError("block_fragments must be a mapping")
        canonical: dict[int, tuple[int, ...]] = {}
        for raw_block, raw_fragments in self.block_fragments.items():
            if isinstance(raw_block, bool) or not isinstance(raw_block, int) or raw_block <= 0:
                raise ProcessOptimizationError("block ids must be positive integers")
            fragments = tuple(int(fragment) for fragment in raw_fragments)
            if not fragments or any(fragment <= 0 for fragment in fragments):
                raise ProcessOptimizationError("fragment ids must be positive")
            canonical[raw_block] = tuple(sorted(set(fragments)))
        object.__setattr__(self, "block_fragments", dict(sorted(canonical.items())))

    @property
    def best(self) -> ProcessSearchEvaluation:
        """Return the best evaluation.

        Returns
        -------
        ProcessSearchEvaluation
            Best candidate evaluation.
        """
        return self.search.best

    def _best_schedule(self) -> list[list[object]]:
        """Return the best schedule in a JSON-ready shape.

        Returns
        -------
        list
            Block and treatment/offset rows.
        """
        schedule = self.best.candidate.schedule
        return [
            [block, [[treatment, offset] for treatment, offset in events]]
            for block, events in sorted(schedule.items())
        ]

    def summary(self) -> dict[str, object]:
        """Return a stable optimization summary.

        Returns
        -------
        dict
            Version, search summary, best candidate, best schedule, and best accounts.
        """
        accounts = {
            str(row.account): float(str(row.value))
            for row in self.best.evaluation.accounts.itertuples(index=False)
        }
        return {
            "schema_version": PROCESS_OPTIMIZATION_VERSION,
            "search": self.search.summary(),
            "best_candidate": self.best.candidate.candidate_id,
            "best_objective": self.best.objective,
            "best_schedule": self._best_schedule(),
            "best_accounts": dict(sorted(accounts.items())),
        }

    def write_estate_inputs(self, out_dir: Path) -> None:
        """Write the best schedule in the canonical estate input format.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.
        """
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        with (target / "schedule.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("block_id", "treatment", "offset"))
            for block, events in sorted(self.best.candidate.schedule.items()):
                for treatment, offset in sorted(events, key=lambda item: (item[1], item[0])):
                    writer.writerow((block, treatment, offset))
        with (target / "block_fragments.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("block_id", "fragment_id"))
            for block, fragments in sorted(self.block_fragments.items()):
                for fragment in fragments:
                    writer.writerow((block, fragment))
        self.write(target)

    def write(self, out_dir: Path) -> None:
        """Write the search trace, best evaluation, and summary.

        Parameters
        ----------
        out_dir : Path
            Output directory, created when missing.
        """
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        self.search.write(target)
        self.best.evaluation.write(target / "best_evaluation")
        (target / "process_optimization.json").write_text(
            json.dumps(self.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def optimize_process_schedule(
    state: CohortState,
    edges: Sequence[FireEdge],
    grammar: ScheduleMoveGrammar,
    initial: ProcessSearchCandidate,
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
) -> ProcessOptimizationResult:
    """Optimize a process-conditioned schedule with the grammar and hill-climb.

    Parameters
    ----------
    state : CohortState
        Initial cohort state.
    edges : sequence of FireEdge
        Landscape graph.
    grammar : ScheduleMoveGrammar
        Add/remove/optional-move grammar.
    initial : ProcessSearchCandidate
        Starting candidate.
    block_fragments : mapping of int to sequence of int
        Block to fragment ids.
    horizon_years : int
        Evaluation horizon; must match the grammar horizon.
    fire : FireConfig
        Fire and salvage parameters.
    targets : sequence of Target
        Level targets used to price every candidate.
    max_iterations : int
        Maximum hill-climb rounds.
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
    ProcessOptimizationResult
        Best evaluation and search trace.

    Raises
    ------
    ProcessOptimizationError
        If the grammar horizon or initial schedule is invalid.
    """
    if grammar.horizon_years != horizon_years:
        raise ProcessOptimizationError("grammar horizon must match horizon_years")
    grammar.validate(initial.schedule)
    search = search_process_neighbourhood(
        state,
        edges,
        initial,
        grammar.neighbours,
        block_fragments,
        horizon_years=horizon_years,
        fire=fire,
        targets=targets,
        max_iterations=max_iterations,
        succession=succession,
        regeneration=regeneration,
        bridge=bridge,
        succession_process=succession_process,
        harvest_fraction=harvest_fraction,
        seed=seed,
    )
    return ProcessOptimizationResult(
        search=search,
        block_fragments={
            block: tuple(fragments) for block, fragments in sorted(block_fragments.items())
        },
    )
