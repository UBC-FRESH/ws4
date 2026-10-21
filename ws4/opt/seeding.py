"""Build an initial schedule by construction, for aggregate targets under a ceiling.

The generic operators move one random block at a time, so a target that needs hundreds of moves
— an aggregate floor on a product account, held under a ceiling on a cost account — is a needle in
a haystack: on the TSA23 fuel-treatment instance a trivial greedy reaches penalty 0 where the search
reaches 335 hectares of a 16,000 hectare floor. This module is that greedy, made general: it reads
the targets the run declares, so a floor is any target with a ``minimum`` and a ceiling any with a
``maximum``, and it names no account, model or treatment.
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

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


@dataclass
class _GoalContext:
    """The immutable state a worker needs to score one block's candidate chains."""

    evaluator: IncrementalObjective
    candidates: Candidates
    targets: Sequence[Target]
    cells: Sequence[Sequence[tuple[int, str]]]
    totals: Mapping[tuple[int, str], float]
    goal: Target
    goal_cells: Sequence[tuple[int, str]]
    ceilings: Sequence[int]
    goal_value: float


_GOAL_CONTEXT: _GoalContext | None = None


def _score_goal_block(context: _GoalContext, block: int) -> list[tuple[float, int, Chain]]:
    """Score one block's candidate chains against a reduction goal."""
    scored: list[tuple[float, int, Chain]] = []
    for chain in context.candidates.get(block, []):
        if not chain:
            continue
        contribution = context.evaluator.contribution(block, chain)
        after = context.goal_value + sum(contribution.get(cell, 0.0) for cell in context.goal_cells)
        gain = penalty(context.goal_value, context.goal) - penalty(after, context.goal)
        if gain <= 0.0:
            continue
        cost = 0.0
        for index in context.ceilings:
            cost += sum(max(contribution.get(cell, 0.0), 0.0) for cell in context.cells[index])
        scored.append((gain / (cost + _UNIT_COST), block, chain))
    return scored


def _score_goal_block_worker(block: int) -> list[tuple[float, int, Chain]]:
    """Fork-pool entry point; the context is inherited from the parent."""
    if _GOAL_CONTEXT is None:
        return []
    return _score_goal_block(_GOAL_CONTEXT, block)


def greedy_schedule(
    evaluator: IncrementalObjective,
    candidates: Candidates,
    limit: int | None = None,
    goal_account: str | None = None,
    workers: int = 1,
) -> Schedule:
    """Return an initial schedule built by construction against the run's targets.

    The default mode satisfies the declared floors within the declared ceilings. Every candidate
    chain is scored once — the penalty it removes from the floors, per unit of the ceilings it
    spends — and the candidates are taken in that order, **skipping any that would push a ceiling
    past its maximum**. Nothing is enforced: the result is a starting point for the search, which
    is still free to soften any bound, and the ceilings are respected only so that the seed is not
    worse than the schedule the search already rejects.

    With ``goal_account``, the named target is a **reduction goal** instead: it must have a
    maximum, and the other maximum targets are its cost ceilings. A candidate is scored by the
    penalty it removes from that goal per unit of cost it adds, and candidates are taken until the
    goal is met or the budget is exhausted. This is the hazard-shaped case (one maximum to reduce
    under several cost ceilings); the area-shaped case is the default floor mode.

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
    goal_account : str or None, optional
        A target account to reduce to its maximum, rather than a floor to satisfy. The account
        must name exactly one active target with a maximum; its other maximum targets are the cost
        ceilings. None (the default) uses the floor mode.
    workers : int, optional
        The number of forked processes used to score reduction-goal candidates. The default, 1,
        scores serially. Forking preserves the evaluator and its caches; results are ranked in the
        parent, so the schedule is unchanged.

    Returns
    -------
    Schedule
        The schedule the ranking produced, as a block-to-chain mapping.

    Raises
    ------
    ValueError
        When a limit is given that is not positive, or ``goal_account`` names no unique active
        target with a maximum.
    """
    if limit is not None and limit < 1:
        raise ValueError(f"a limit of {limit} moves is not a schedule")
    if workers < 1:
        raise ValueError(f"a seed worker count of {workers} is not positive")
    targets = evaluator.targets
    years = evaluator.optimizer.cfg.years
    cells = [target_cells(target, years) for target in targets]
    if goal_account is not None:
        matches = [index for index, target in enumerate(targets) if target.account == goal_account]
        if len(matches) != 1 or targets[matches[0]].maximum is None:
            raise ValueError(
                f"goal account {goal_account!r} must name exactly one active target with a maximum"
            )
        goal_index = matches[0]
        goal = targets[goal_index]
        goal_cells = cells[goal_index]
        ceilings = [
            index
            for index, target in enumerate(targets)
            if index != goal_index and target.maximum is not None
        ]
        evaluator.reset({})
        totals = dict(evaluator.totals)
        goal_value = target_value(goal_cells, totals)
        if goal.maximum is not None and goal_value <= goal.maximum:
            return {}
        context = _GoalContext(
            evaluator=evaluator,
            candidates=candidates,
            targets=targets,
            cells=cells,
            totals=totals,
            goal=goal,
            goal_cells=goal_cells,
            ceilings=ceilings,
            goal_value=goal_value,
        )
        if workers > 1:
            global _GOAL_CONTEXT
            _GOAL_CONTEXT = context
            try:
                mp_context = multiprocessing.get_context("fork")
                with ProcessPoolExecutor(
                    max_workers=min(workers, len(candidates)),
                    mp_context=mp_context,
                ) as pool:
                    chunks = pool.map(
                        _score_goal_block_worker,
                        candidates.keys(),
                        chunksize=max(1, len(candidates) // (workers * 4)),
                    )
                    scored = [entry for chunk in chunks for entry in chunk]
            finally:
                _GOAL_CONTEXT = None
        else:
            scored = [entry for block in candidates for entry in _score_goal_block(context, block)]
        scored.sort(key=lambda entry: -entry[0])
        chosen: Schedule = {}
        spent: dict[int, float] = {
            index: sum(max(totals.get(cell, 0.0), 0.0) for cell in cells[index])
            for index in ceilings
        }
        current = goal_value
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
            current += sum(contribution.get(cell, 0.0) for cell in goal_cells)
            for index in ceilings:
                spent[index] += addition[index]
            if goal.maximum is not None and current <= goal.maximum:
                break
        evaluator.reset(chosen)
        return chosen
    ceilings = [index for index, target in enumerate(targets) if target.maximum is not None]
    floors = [index for index, target in enumerate(targets) if target.minimum is not None]
    if not floors:
        return {}
    evaluator.reset({})
    totals = dict(evaluator.totals)
    scored = []
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
    chosen = {}
    spent = dict.fromkeys(ceilings, 0.0)
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
