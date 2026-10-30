"""A bounded, flow-directed repair pass over an incumbent schedule.

The even-flow targets compare each accounting period's product volume with a reference
period. A generic move changes one random block, so most proposals do not move volume from
a period that is *above* the reference into one that is *below* it. This module is the
directed version: it finds the blocks whose current chain contributes to an over-target
period, and tries that block's candidate chains whose first event falls in an under-target
period. Every proposal is priced by :class:`~ws4.opt.incremental.IncrementalObjective`, so
a move is accepted only when its **exact** objective delta is an improvement, the target's
own flow penalty falls, and no other even-flow target's penalty rises.

The pass is deliberately bounded by the number of candidate moves it evaluates rather than
by wall-clock time. It changes no target semantics: it reads the same ``even`` flow target
the search prices, uses the same period convention, and leaves the schedule and evaluator in
a state whose objective equals a fresh evaluation.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .incremental import IncrementalObjective
from .objective import Target, accumulates, flow_period_ends, flow_reference_end, penalty
from .operators import Candidates, Chain, Schedule


@dataclass(frozen=True)
class FlowRepairResult:
    """The outcome of a bounded flow-directed repair pass.

    Attributes
    ----------
    schedule : dict of int to tuple of (str, int)
        The repaired schedule.
    objective : float
        The exact objective of ``schedule`` after the pass.
    objective_before : float
        The exact objective of the incumbent before the pass.
    trials : int
        The number of candidate moves priced.
    moves : int
        The number of candidate moves accepted.
    flow_before : dict of str to tuple of float, float
        The worst (minimum, maximum) flow percentage per flow account before the pass.
    flow_after : dict of str to tuple of float, float
        The worst (minimum, maximum) flow percentage per flow account after the pass.
    flow_penalty_before : float
        The summed weighted even-flow penalty before the pass.
    flow_penalty_after : float
        The summed weighted even-flow penalty after the pass.
    """

    schedule: Schedule
    objective: float
    objective_before: float
    trials: int
    moves: int
    flow_before: dict[str, tuple[float, float]]
    flow_after: dict[str, tuple[float, float]]
    flow_penalty_before: float
    flow_penalty_after: float


def _period_cells(target: Target, years: int) -> tuple[tuple[tuple[int, str], ...], ...]:
    """Return the cells that make up each period of a flow target.

    This is the same grouping :class:`IncrementalObjective` uses: an accumulating account
    sums its period's years, while a level is read at the period's end year.

    Parameters
    ----------
    target : Target
        A flow target.
    years : int
        The horizon, for a target that states no end.

    Returns
    -------
    tuple of tuple of (int, str)
        The cells per period, in the target's period order.
    """
    width = max(1, target.period_width)
    ends = flow_period_ends(target, years)
    if accumulates(target.account):
        return tuple(
            tuple((year, target.account) for year in range(max(0, end - width + 1), end + 1))
            for end in ends
        )
    return tuple(((end, target.account),) for end in ends)


def _period_values(
    cells: Sequence[Sequence[tuple[int, str]]], totals: Mapping[tuple[int, str], float]
) -> list[float]:
    """Return the value of each period from the running account totals."""
    return [sum(totals.get(cell, 0.0) for cell in period) for period in cells]


def _percentages(values: Sequence[float], reference: int) -> list[float | None]:
    """Return each period's percent difference from the reference period.

    The reference period itself is ``None`` because it carries no comparison value, which
    is the same convention :func:`ws4.opt.objective.flow_values` uses.
    """
    balance = values[reference]
    if balance <= 0.0:
        return [None if position == reference else math.inf for position in range(len(values))]
    return [
        None if position == reference else 100.0 * (value - balance) / balance
        for position, value in enumerate(values)
    ]


def _flow_gap(
    targets: Sequence[Target], totals: Mapping[tuple[int, str], float], years: int
) -> dict[str, tuple[float, float]]:
    """Return the minimum and maximum flow percentage for each even-flow account."""
    gaps: dict[str, tuple[float, float]] = {}
    for target in targets:
        if target.flow != "even":
            continue
        values = _flow_period_values(target, totals, years)
        if len(values) < 2:
            continue
        ends = flow_period_ends(target, years)
        reference = ends.index(flow_reference_end(target, years))
        percentages = [
            value
            for value in _percentages(values, reference)
            if value is not None and math.isfinite(value)
        ]
        if percentages:
            gaps[target.account] = (min(percentages), max(percentages))
    return gaps


def _flow_period_values(
    target: Target, totals: Mapping[tuple[int, str], float], years: int
) -> list[float]:
    """Return a flow target's period balances under the evaluator's convention."""
    return _period_values(_period_cells(target, years), totals)


def _candidate_chains(
    chains: Sequence[Chain],
    current: Chain,
    low: set[int],
    percentages: Sequence[float | None],
    year_to_period: Mapping[int, int],
    period_center: Mapping[int, float],
) -> list[Chain]:
    """Return a block's candidate chains whose first event is in an under-target period.

    The most deficient period is tried first, then the candidate whose first event is
    closest to the period's midpoint. The caller bounds how many of these it prices.

    Parameters
    ----------
    chains : sequence of tuple of (str, int)
        The block's candidate chains.
    current : tuple of (str, int)
        The block's current chain.
    low : set of int
        The positions of the periods below the target's minimum.
    percentages : sequence of float or None
        The period percentages; the reference period is None.
    year_to_period : mapping of int to int
        The period position that contains each event year.
    period_center : mapping of int to float
        The midpoint year of each period position.

    Returns
    -------
    list of tuple of (str, int)
        The directed candidates, best first.
    """
    ranked: list[tuple[float, float, Chain]] = []
    for chain in chains:
        if not chain or chain == current:
            continue
        position = year_to_period.get(chain[0][1])
        if position is None or position not in low:
            continue
        percentage = percentages[position]
        deficit = percentage if percentage is not None else math.inf
        ranked.append((deficit, abs(chain[0][1] - period_center[position]), chain))
    ranked.sort(key=lambda entry: (entry[0], entry[1]))
    return [chain for _, _, chain in ranked]


def repair_flow_gap(
    evaluator: IncrementalObjective,
    candidates: Candidates,
    *,
    max_trials: int = 400,
    chains_per_block: int = 4,
    min_gain: float = 1e-6,
    deadline: float | None = None,
) -> FlowRepairResult:
    """Shift harvest out of over-target periods into under-target periods.

    For every active even-flow target on an accumulating account, the pass computes the
    period percentages from the reference period. It ranks the scheduled blocks by the
    volume they contribute to the periods above the target's maximum, and prices candidate
    chains whose first event falls in a period below the target's minimum. A proposal is
    applied only when its exact objective delta is negative, the target's flow penalty
    falls, and no other even-flow target's penalty rises; otherwise the evaluator's pending
    patch and spatial state is reverted and the block is restored.

    Parameters
    ----------
    evaluator : IncrementalObjective
        The move-based evaluator, already reset to the incumbent schedule.
    candidates : dict of int to list of tuple of (str, int)
        The candidate chains per block.
    max_trials : int, optional
        The maximum number of candidate moves to price. Defaults to 400.
    chains_per_block : int, optional
        The maximum number of directed candidates to price for one block. Defaults to 4.
    min_gain : float, optional
        The smallest exact objective decrease that counts as an improvement. Defaults to
        one millionth of an objective unit.
    deadline : float or None, optional
        An absolute ``time.monotonic()`` value to stop at, or None for no clock bound.

    Returns
    -------
    FlowRepairResult
        The repaired schedule, its exact objective, and the pass statistics.

    Raises
    ------
    ValueError
        When a bound is not positive.
    """
    if max_trials < 1:
        raise ValueError("max_trials must be positive")
    if chains_per_block < 1:
        raise ValueError("chains_per_block must be positive")
    if min_gain < 0.0:
        raise ValueError("min_gain must not be negative")
    years = evaluator.optimizer.cfg.years
    targets = evaluator.targets
    schedule: Schedule = dict(evaluator.assignments)
    objective_before = evaluator.objective
    flow_before = _flow_gap(targets, evaluator.totals, years)
    flow_meta: list[
        tuple[
            Target, tuple[tuple[tuple[int, str], ...], ...], int, dict[int, int], dict[int, float]
        ]
    ] = []
    for target in targets:
        if target.flow != "even" or not accumulates(target.account):
            continue
        cells = _period_cells(target, years)
        if len(cells) < 2:
            continue
        ends = flow_period_ends(target, years)
        reference = ends.index(flow_reference_end(target, years))
        year_to_period: dict[int, int] = {}
        period_center: dict[int, float] = {}
        for position, period in enumerate(cells):
            for year, _ in period:
                year_to_period[year] = position
            period_center[position] = (period[0][0] + period[-1][0]) / 2.0
        flow_meta.append((target, cells, reference, year_to_period, period_center))
    flow_penalty_before = flow_penalty_total(targets, evaluator.totals, years)
    trials = 0
    moves = 0
    if not flow_meta:
        return FlowRepairResult(
            schedule=schedule,
            objective=objective_before,
            objective_before=objective_before,
            trials=0,
            moves=0,
            flow_before=flow_before,
            flow_after=flow_before,
            flow_penalty_before=flow_penalty_before,
            flow_penalty_after=flow_penalty_before,
        )

    made_progress = True
    while made_progress and trials < max_trials:
        made_progress = False
        if deadline is not None and time.monotonic() >= deadline:
            break
        meta_targets = [entry[0] for entry in flow_meta]
        for target_index, (
            target,
            cells,
            reference,
            year_to_period,
            period_center,
        ) in enumerate(flow_meta):
            values = _period_values(cells, evaluator.totals)
            percentages = _percentages(values, reference)
            high = {
                position
                for position, percentage in enumerate(percentages)
                if percentage is not None
                and target.maximum is not None
                and percentage > target.maximum
                and math.isfinite(percentage)
            }
            low = {
                position
                for position, percentage in enumerate(percentages)
                if percentage is not None
                and target.minimum is not None
                and percentage < target.minimum
                and math.isfinite(percentage)
            }
            if not high or not low:
                continue
            high_cells = [cell for position in high for cell in cells[position]]
            ranked_blocks: list[tuple[float, int]] = []
            for block, chain in schedule.items():
                if not chain:
                    continue
                contribution = evaluator.contribution(block, chain)
                volume = sum(contribution.get(cell, 0.0) for cell in high_cells)
                if volume > 0.0:
                    ranked_blocks.append((volume, block))
            ranked_blocks.sort(key=lambda entry: -entry[0])
            period_penalties = [
                _target_flow_penalty(item, evaluator.totals, years) for item in meta_targets
            ]
            for _, block in ranked_blocks:
                if trials >= max_trials:
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    break
                current = schedule.get(block)
                if not current:
                    continue
                directed = _candidate_chains(
                    candidates.get(block, ()),
                    current,
                    low,
                    percentages,
                    year_to_period,
                    period_center,
                )
                for chain in directed[:chains_per_block]:
                    if trials >= max_trials:
                        break
                    if deadline is not None and time.monotonic() >= deadline:
                        break
                    schedule[block] = chain
                    delta = evaluator.delta([block], schedule)
                    trials += 1
                    if delta < -min_gain:
                        change = _cell_change(evaluator, block, current, chain)
                        after = dict(evaluator.totals)
                        for cell, value in change.items():
                            after[cell] = after.get(cell, 0.0) + value
                        after_penalties = [
                            _target_flow_penalty(item, after, years) for item in meta_targets
                        ]
                        if after_penalties[target_index] < period_penalties[
                            target_index
                        ] - min_gain and all(
                            after <= before + min_gain
                            for after, before in zip(after_penalties, period_penalties, strict=True)
                        ):
                            evaluator.apply([block], schedule)
                            moves += 1
                            made_progress = True
                            period_penalties = after_penalties
                            break
                    schedule[block] = current
                    evaluator.revert()
    objective_after = evaluator.objective
    flow_after = _flow_gap(targets, evaluator.totals, years)
    return FlowRepairResult(
        schedule=schedule,
        objective=objective_after,
        objective_before=objective_before,
        trials=trials,
        moves=moves,
        flow_before=flow_before,
        flow_after=flow_after,
        flow_penalty_before=flow_penalty_before,
        flow_penalty_after=flow_penalty_total(targets, evaluator.totals, years),
    )


def _target_flow_penalty(
    target: Target, totals: Mapping[tuple[int, str], float], years: int
) -> float:
    """Return one even-flow target's weighted penalty from the running totals."""
    values = _flow_period_values(target, totals, years)
    if len(values) < 2:
        return 0.0
    ends = flow_period_ends(target, years)
    reference = ends.index(flow_reference_end(target, years))
    return sum(
        penalty(percentage, target)
        for position, percentage in enumerate(_percentages(values, reference))
        if position != reference and percentage is not None
    )


def _cell_change(
    evaluator: IncrementalObjective, block: int, old: Chain, new: Chain
) -> dict[tuple[int, str], float]:
    """Return the account-cell change from replacing one block's chain.

    Only additive accounts matter to a flow target, so the patch and spatial pending
    changes are not part of this helper; the full objective delta is still priced by
    :meth:`IncrementalObjective.delta`.
    """
    change: dict[tuple[int, str], float] = {}
    for cell, value in evaluator.contribution(block, new).items():
        change[cell] = change.get(cell, 0.0) + value
    for cell, value in evaluator.contribution(block, old).items():
        change[cell] = change.get(cell, 0.0) - value
    return change


def flow_penalty_total(
    targets: Sequence[Target], totals: Mapping[tuple[int, str], float], years: int
) -> float:
    """Return the summed weighted even-flow penalty for the targets.

    This is a report helper, not part of the acceptance rule: the pass accepts only an
    exact full-objective improvement that also lowers the target's own flow penalty, and
    this function lets a caller see the flow component.

    Parameters
    ----------
    targets : sequence of Target
        The run's active targets; only the even-flow ones are priced.
    totals : mapping of (int, str) to float
        The running account values.
    years : int
        The horizon, in years.

    Returns
    -------
    float
        The summed weighted penalty of the even-flow targets.
    """
    return sum(
        _target_flow_penalty(target, totals, years) for target in targets if target.flow == "even"
    )
