"""The solver-core boundary: a problem adapter.

A solver is problem-agnostic. It needs only an objective evaluator, the candidate move
set, and an operator registry. WS4 supplies one :class:`Problem`; a future shared solver
core would take the same shape for WS3 or FHOPS (see
`notes/design/ws4-optimization-stack.md`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .operators import Candidates, OperatorRegistry, Schedule

Evaluate = Callable[[Schedule], float]


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
    """

    evaluate: Evaluate
    candidates: Candidates
    registry: OperatorRegistry
