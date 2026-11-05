"""The solver-core boundary: a problem adapter.

A solver is problem-agnostic. It needs only an objective evaluator, the candidate move
set, and an operator registry. WS4 supplies one :class:`Problem`; the shared kernel in
``fresh-solutions`` supplies the solvers and the operator registry.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fresh_solutions.kernel import Problem as KernelProblem

from .operators import Candidates, OperatorRegistry, Schedule


class Problem(KernelProblem[Schedule, Candidates]):
    """The WS4 problem a solver searches.

    Parameters
    ----------
    evaluate : callable
        The exact objective evaluator (lower is better).
    candidates : Candidates
        The candidate chains per block.
    registry : OperatorRegistry
        The neighbourhood operators.
    snapshot : callable or None, optional
        Return the realized account cells for a schedule, for a live map and target view.
        When omitted, a solver that would otherwise emit a snapshot sends an empty mapping.
    """

    def __init__(
        self,
        evaluate: Callable[[Schedule], float],
        candidates: Candidates,
        registry: OperatorRegistry[Schedule, Candidates],
        snapshot: Callable[[Schedule], Mapping[Any, float]] | None = None,
    ) -> None:
        super().__init__(
            evaluate=evaluate,
            candidates=candidates,
            registry=registry,
            snapshot=snapshot,
            empty=dict,
            clone=dict,
        )


__all__ = ["Problem"]
