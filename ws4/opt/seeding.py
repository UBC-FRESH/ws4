"""Build an initial schedule by construction, for aggregate targets under a ceiling.

The generic operators move one random block at a time, so a target that needs hundreds of moves
— an aggregate floor on a product account, held under a ceiling on a cost account — is a needle in
a haystack: on the TSA23 fuel-treatment instance a trivial greedy reaches penalty 0 where the search
reaches 335 hectares of a 16,000 hectare floor. This module is that greedy, made general: it reads
the targets the run declares, so a floor is any target with a ``minimum`` and a ceiling any with a
``maximum``, and it names no account, model or treatment.
"""

from __future__ import annotations

from collections.abc import Sequence

from .incremental import IncrementalObjective
from .objective import Target, accumulates, penalty
from .operators import Candidates, Chain, Schedule

#: A tie-break for ranking when a candidate costs nothing measurable.
_UNIT_COST = 1e-9


def target_cells(target: Target, years: int) -> tuple[tuple[int, str], ...]:
    """Return the cells a target reads, under the objective's own convention.

    An accumulating account sums its period, a level is read at the period's end, and a flow target
    spans its window — the same reading :class:`~ws4.opt.engine.Optimizer` prices, so a schedule
    built against these cells is built against what the search is scored on.

    Parameters
    ----------
    target : Target
        The target.
    years : int
        The horizon, in years, for a flow target that states no end.

    Returns
    -------
    tuple of (int, str)
        The ``(year, account)`` cells the target reads.
    """
    if target.flow:
        stop = target.flow_end if target.flow_end is not None else years
        return tuple((year, target.account) for year in range(target.flow_start, stop))
    if not accumulates(target.account):
        return ((target.year, target.account),)
    return tuple((year, target.account) for year in target.cell_years())


def target_value(cells: Sequence[tuple[int, str]], totals: dict[tuple[int, str], float]) -> float:
    """Return what a target reads, given the running totals of its cells.

    Parameters
    ----------
    cells : sequence of (int, str)
        The cells the target reads.
    totals : dict of (int, str) to float
        The running value of every tracked cell.

    Returns
    -------
    float
        The sum of the cells' values, which is the target's value for an accumulating account and
        the one cell's value for a level.
    """
    return sum(totals.get(cell, 0.0) for cell in cells)


def greedy_schedule(
    evaluator: IncrementalObjective, candidates: Candidates, limit: int | None = None
) -> Schedule:
    """Return an initial schedule built to satisfy the declared floors within the declared ceilings.

    The rule is deliberately simple and general. Every candidate chain is scored once — the penalty
    it removes from the floors, per unit of the ceilings it spends — the candidates are taken in
    that order, **skipping any that would push a ceiling past its maximum**. Nothing is enforced:
    the result is a starting point for the search, which is still free to soften any bound, and the
    ceilings are respected only so that the seed is not worse than the schedule the search already
    rejects.

    A candidate is a whole chain for a block, so a block is treated at most once and the schedule
    returned is a valid search state.

    Parameters
    ----------
    evaluator : IncrementalObjective
        The evaluator for the run, which holds the targets and the per-chain contributions.
    candidates : Candidates
        The candidate chains per block.
    limit : int or None, optional
        The most moves to take, or None for one per block at most.

    Returns
    -------
    Schedule
        The schedule the ranking produced, as a block-to-chain mapping.

    Raises
    ------
    ValueError
        When a limit is given that is not positive.
    """
    if limit is not None and limit < 1:
        raise ValueError(f"a limit of {limit} moves is not a schedule")
    targets = evaluator.targets
    ceilings = [index for index, target in enumerate(targets) if target.maximum is not None]
    floors = [index for index, target in enumerate(targets) if target.minimum is not None]
    if not floors:
        return {}
    years = evaluator.optimizer.cfg.years
    cells = [target_cells(target, years) for target in targets]
    evaluator.reset({})
    totals = dict(evaluator.totals)
    scored: list[tuple[float, int, Chain]] = []
    for block, options in candidates.items():
        for chain in options:
            if not chain:
                continue
            contribution = evaluator.contribution(block, chain)
            gain = 0.0
            for index in floors:
                target = targets[index]
                before = target_value(cells[index], totals)
                after = before + sum(contribution.get(cell, 0.0) for cell in cells[index])
                gain += penalty(before, target) - penalty(after, target)
            if gain <= 0.0:
                continue
            cost = 0.0
            for index in ceilings:
                cost += sum(max(contribution.get(cell, 0.0), 0.0) for cell in cells[index])
            scored.append((gain / (cost + _UNIT_COST), block, chain))
    scored.sort(key=lambda entry: -entry[0])
    chosen: Schedule = {}
    spent: dict[int, float] = dict.fromkeys(ceilings, 0.0)
    for _score, block, chain in scored:
        if block in chosen:
            continue
        if limit is not None and len(chosen) >= limit:
            break
        contribution = evaluator.contribution(block, chain)
        addition = {
            index: sum(max(contribution.get(cell, 0.0), 0.0) for cell in cells[index])
            for index in ceilings
        }
        breached = False
        for index in ceilings:
            ceiling = targets[index].maximum
            if ceiling is not None and spent[index] + addition[index] > ceiling:
                breached = True
                break
        if breached:
            continue
        chosen[block] = chain
        for index in ceilings:
            spent[index] += addition[index]
    evaluator.reset(chosen)
    return chosen
