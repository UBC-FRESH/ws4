"""The solver-core boundary: a problem adapter.

A solver is problem-agnostic. It needs only an objective evaluator, the candidate move
set, and an operator registry. WS4 supplies one :class:`Problem`; a future shared solver
core would take the same shape for WS3 or FHOPS (see
`notes/design/ws4-optimization-stack.md`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .operators import Candidates, OperatorRegistry, Schedule

Evaluate = Callable[[Schedule], float]

#: Called with a schedule and returns the realized account cells for a live snapshot.
Snapshot = Callable[[Schedule], Mapping[tuple[int, str], float]]


@dataclass
class Problem:
    """The problem a solver searches.

    Attributes
    ----------
    evaluate : callable
        The objective evaluator (lower is better).
    candidates : Candidates
        The candidate moves per decision unit.
    registry : OperatorRegistry
        The neighbourhood operators.
    snapshot : callable or None, optional
        Return the realized account cells for a schedule, for a live map and target view. When
        omitted, a solver that would otherwise emit a snapshot sends an empty mapping.
    """

    evaluate: Evaluate
    candidates: Candidates
    registry: OperatorRegistry
    snapshot: Snapshot | None = None
