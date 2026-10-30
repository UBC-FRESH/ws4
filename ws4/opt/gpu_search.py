"""Batched large-neighbourhood search over the sparse GPU effect table.

This is a bounded prototype, not the production search.  It keeps one schedule and prices
a batch of independent LNS proposals in one device operation, then accepts the best
proposal of the batch under a Metropolis rule.  The CPU simulated annealer remains the
reference and the fallback.

The exactness contract is narrow on purpose.  The pricer reproduces the incremental
objective for a target set with one priority tier, no patch accounts, no route accounts,
and no spatial rules, which is the c5 configuration.  Anything else raises
:class:`NotImplementedError` rather than returning a silently different objective.

Proposal generation is the same distribution as :class:`~ws4.opt.operators.LnsOperator`
when every block is assigned: a uniform sample of ``min(10% of the schedule, 64)``
assigned blocks, each re-assigned a uniformly random candidate chain.  The prototype
samples that set directly instead of by rejection, which is much cheaper for a full
schedule and leaves the distribution unchanged.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

try:  # pragma: no cover - which branch runs depends on the environment
    import torch

    HAVE_TORCH = True
except ImportError:  # pragma: no cover
    HAVE_TORCH = False
    torch = None  # type: ignore[assignment]  # torch is optional; methods raise without it.

if TYPE_CHECKING:
    from collections.abc import Sequence

    import torch as torch_type

    from .engine import Optimizer
    from .gpu_effects import EffectTable
    from .incremental import IncrementalObjective
    from .objective import Target
    from .operators import Candidates, Chain, Schedule


def _require_torch() -> None:
    """Raise a clear error when torch is not installed."""
    if not HAVE_TORCH:
        raise RuntimeError(
            "the batched GPU search needs torch; install the optional 'gpu' dependency "
            "(pip install 'ws4[gpu]')"
        )


@dataclass(frozen=True)
class SearchResult:
    """The best schedule and the measured cost of a batched LNS run.

    Parameters
    ----------
    schedule : dict of int to tuple of (str, int)
        The best assignment found.
    objective : float
        The exact incremental objective of ``schedule``.
    initial_objective : float
        The objective of the starting schedule.
    rounds : int
        The number of proposal batches evaluated.
    proposals : int
        The total number of proposals evaluated.
    accepted : int
        The number of accepted proposals.
    seconds : float
        Wall-clock seconds spent in proposal generation, pricing, and acceptance.  The
        effect-table build and upload are not included.

    Attributes
    ----------
    objective_gain : float
        ``initial_objective - objective``.
    """

    schedule: Schedule
    objective: float
    initial_objective: float
    rounds: int
    proposals: int
    accepted: int
    seconds: float

    @property
    def objective_gain(self) -> float:
        """Return the objective improvement over the initial schedule.

        Returns
        -------
        float
            ``initial_objective - objective``.
        """
        return self.initial_objective - self.objective


@dataclass(frozen=True)
class _FlowSpec:
    """One flow target's period cells and penalty parameters."""

    mask: torch_type.Tensor
    reference: int
    lo: torch_type.Tensor
    hi: torch_type.Tensor
    has_lo: torch_type.Tensor
    has_hi: torch_type.Tensor
    wlo: torch_type.Tensor
    whi: torch_type.Tensor
    nonlinear: torch_type.Tensor
    scale: torch_type.Tensor


def _penalty(
    values: torch_type.Tensor,
    lo: torch_type.Tensor,
    hi: torch_type.Tensor,
    has_lo: torch_type.Tensor,
    has_hi: torch_type.Tensor,
    wlo: torch_type.Tensor,
    whi: torch_type.Tensor,
    nonlinear: torch_type.Tensor,
    scale: torch_type.Tensor,
) -> torch_type.Tensor:
    """Return the weighted, optionally normalized penalty of each value."""
    deviation = torch.clamp(lo - values, min=0.0)
    deviation = torch.where(nonlinear, deviation * deviation, deviation)
    total = wlo * torch.where(has_lo, deviation, torch.zeros_like(deviation))
    deviation = torch.clamp(values - hi, min=0.0)
    deviation = torch.where(nonlinear, deviation * deviation, deviation)
    total = total + whi * torch.where(has_hi, deviation, torch.zeros_like(deviation))
    return total / scale


class _ObjectivePricer:
    """Price a batch of cell deltas for a single-priority additive target set."""

    def __init__(
        self,
        evaluator: IncrementalObjective,
        cells: Sequence[tuple[int, str]],
        device: torch_type.device,
    ) -> None:
        self.device = device
        self.columns = len(cells)
        self.cell_index = {cell: column for column, cell in enumerate(cells)}
        level_targets = [
            (index, target) for index, target in enumerate(evaluator.targets) if not target.flow
        ]
        self.level_mask = torch.zeros(
            (len(level_targets), self.columns), dtype=torch.float64, device=device
        )
        for row, (index, _target) in enumerate(level_targets):
            for cell in evaluator._target_cells[index]:
                column = self.cell_index.get(cell)
                if column is not None:
                    self.level_mask[row, column] = 1.0
        level_params = self._params([target for _index, target in level_targets])
        self.level_params = level_params
        self.flow: list[_FlowSpec] = []
        for index, target in enumerate(evaluator.targets):
            if not target.flow:
                continue
            periods = evaluator._flow_period_cells[index]
            rows = len(periods)
            mask = torch.zeros((rows, self.columns), dtype=torch.float64, device=device)
            for row, cells_in_period in enumerate(periods):
                for cell in cells_in_period:
                    column = self.cell_index.get(cell)
                    if column is not None:
                        mask[row, column] = 1.0
            params = self._params([target])
            reference = evaluator._flow_reference_index[index]
            assert reference is not None
            self.flow.append(
                _FlowSpec(
                    mask=mask,
                    reference=reference,
                    lo=params[0],
                    hi=params[1],
                    has_lo=params[2],
                    has_hi=params[3],
                    wlo=params[4],
                    whi=params[5],
                    nonlinear=params[6],
                    scale=params[7],
                )
            )

    def _params(
        self, targets: Sequence[Target]
    ) -> tuple[
        torch_type.Tensor,
        torch_type.Tensor,
        torch_type.Tensor,
        torch_type.Tensor,
        torch_type.Tensor,
        torch_type.Tensor,
        torch_type.Tensor,
        torch_type.Tensor,
    ]:
        """Return the per-target penalty parameter vectors."""

        def tensor(values: Sequence[float]) -> torch_type.Tensor:
            return torch.tensor(values, dtype=torch.float64, device=self.device)

        lo = tensor([target.minimum if target.minimum is not None else 0.0 for target in targets])
        hi = tensor([target.maximum if target.maximum is not None else 0.0 for target in targets])
        has_lo = torch.tensor(
            [target.minimum is not None for target in targets],
            dtype=torch.bool,
            device=self.device,
        )
        has_hi = torch.tensor(
            [target.maximum is not None for target in targets],
            dtype=torch.bool,
            device=self.device,
        )
        wlo = tensor([target.min_weight for target in targets])
        whi = tensor([target.max_weight for target in targets])
        nonlinear = torch.tensor(
            [target.shape == "non_linear" for target in targets],
            dtype=torch.bool,
            device=self.device,
        )
        scale = tensor(
            [
                max(
                    [1.0]
                    + [
                        abs(float(bound))
                        for bound in (target.minimum, target.maximum)
                        if bound is not None
                    ]
                )
                if target.normalization == "auto"
                else 1.0
                for target in targets
            ]
        )
        return lo, hi, has_lo, has_hi, wlo, whi, nonlinear, scale

    def totals(self, totals: dict[tuple[int, str], float]) -> torch_type.Tensor:
        """Return the tracked cells as one float64 device vector.

        Parameters
        ----------
        totals : dict of (int, str) to float
            The evaluator's realized totals.

        Returns
        -------
        torch.Tensor
            A ``[columns]`` float64 tensor.
        """
        out = torch.zeros(self.columns, dtype=torch.float64)
        for cell, column in self.cell_index.items():
            out[column] = totals.get(cell, 0.0)
        return out.to(self.device)

    def delta(self, totals: torch_type.Tensor, deltas: torch_type.Tensor) -> torch_type.Tensor:
        """Return the exact objective change for each row of cell deltas.

        Parameters
        ----------
        totals : torch.Tensor
            A ``[columns]`` or ``[rows, columns]`` tensor of current account totals.
        deltas : torch.Tensor
            A ``[rows, columns]`` tensor of candidate cell changes.

        Returns
        -------
        torch.Tensor
            One objective change per candidate row.
        """
        before = totals if totals.ndim == 2 else totals.unsqueeze(0)
        before = before.expand(deltas.shape[0], -1)
        level_before = self._level_penalty(before)
        level_after = self._level_penalty(before + deltas)
        total = level_after - level_before
        for spec in self.flow:
            flow_before = before @ spec.mask.T
            flow_after = flow_before + deltas @ spec.mask.T
            total = (
                total + self._flow_penalty(flow_after, spec) - self._flow_penalty(flow_before, spec)
            )
        return total

    def scores(self, totals: torch_type.Tensor) -> torch_type.Tensor:
        """Return the exact absolute objective for each row of cell totals.

        The incremental objective's scalar is the sum of the per-target penalties when
        every target shares one priority tier, which is the contract this prototype
        enforces.  A flow target is priced from its period balances; a level target from
        its target cells.

        Parameters
        ----------
        totals : torch.Tensor
            A ``[rows, columns]`` tensor of account totals.

        Returns
        -------
        torch.Tensor
            One exact objective per row.
        """
        total = self._level_penalty(totals)
        for spec in self.flow:
            total = total + self._flow_penalty(totals @ spec.mask.T, spec)
        return total

    def _level_penalty(self, totals: torch_type.Tensor) -> torch_type.Tensor:
        values = totals @ self.level_mask.T
        return _penalty(values, *self.level_params).sum(dim=1)

    def _flow_penalty(self, values: torch_type.Tensor, spec: _FlowSpec) -> torch_type.Tensor:
        balance = values[:, spec.reference]
        percentages = (
            100.0 * (values - balance.unsqueeze(1)) / balance.unsqueeze(1).clamp_min(1e-300)
        )
        # The CPU evaluator reports every non-reference period as infinite when the
        # reference balance is not positive; clamping to a huge finite value would change
        # the penalty whenever the target has a maximum bound.
        percentages = torch.where(
            (balance <= 0.0).unsqueeze(1),
            torch.full_like(percentages, math.inf),
            percentages,
        )
        penalty = _penalty(
            percentages,
            spec.lo,
            spec.hi,
            spec.has_lo,
            spec.has_hi,
            spec.wlo,
            spec.whi,
            spec.nonlinear,
            spec.scale,
        )
        mask = torch.arange(values.shape[1], device=self.device) != spec.reference
        return torch.where(mask.unsqueeze(0), penalty, torch.zeros_like(penalty)).sum(dim=1)


def _check_supported(evaluator: IncrementalObjective) -> None:
    """Reject a target configuration the prototype cannot price exactly."""
    if evaluator._mixed_priorities:
        raise NotImplementedError("the batched prototype needs one priority tier")
    if evaluator.patch is not None:
        raise NotImplementedError("the batched prototype does not price patch accounts")
    if evaluator.spatial.enabled:
        raise NotImplementedError("the batched prototype does not price spatial rules")
    if evaluator._has_route_accounts:
        raise NotImplementedError("the batched prototype does not price route accounts")
    if any(target.flow == "ndy" for target in evaluator.targets):
        raise NotImplementedError("the batched prototype does not price ndy flow")


class BatchedLnsSearch:
    """A bounded best-of-batch LNS search over a sparse effect table.

    Parameters
    ----------
    optimizer : Optimizer
        The optimizer the effect table and candidate chains belong to.
    evaluator : IncrementalObjective
        The exact evaluator, used for its target metadata and the initial totals.
    table : EffectTable
        The effect table, already on the device to search on.
    proposals : int, optional
        The number of independent proposals per round.  Defaults to 64.
    temperature : float, optional
        The initial Metropolis temperature.  Defaults to 1000.
    final_temperature : float, optional
        The last temperature, approached geometrically over the run.  Defaults to 1.
    max_destroy : int, optional
        The largest number of blocks one LNS proposal may change.  Defaults to 64.
    destroy_fraction : float, optional
        The fraction of the current schedule one proposal destroys.  Defaults to 0.1.
    seed : int, optional
        The seed of the proposal random source.  Defaults to 1.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        evaluator: IncrementalObjective,
        table: EffectTable,
        *,
        proposals: int = 64,
        temperature: float = 1000.0,
        final_temperature: float = 1.0,
        max_destroy: int = 64,
        destroy_fraction: float = 0.1,
        seed: int = 1,
    ) -> None:
        _require_torch()
        _check_supported(evaluator)
        if proposals < 1:
            raise ValueError("proposals must be positive")
        if temperature <= 0.0 or final_temperature <= 0.0:
            raise ValueError("temperatures must be positive")
        self.optimizer = optimizer
        self.evaluator = evaluator
        self.table = table
        self.proposals = proposals
        self.temperature = temperature
        self.final_temperature = final_temperature
        self.max_destroy = max(1, int(max_destroy))
        self.destroy_fraction = destroy_fraction
        self.rng = random.Random(seed)
        self.pricer = _ObjectivePricer(evaluator, table.cells, table.device)
        self.candidates: Candidates = optimizer.candidates()

    def _proposal(
        self,
        schedule: Schedule,
        current_rows: dict[int, int],
        blocks: Sequence[int],
        option_chains: dict[int, list[Chain]],
        option_rows: dict[int, list[int]],
    ) -> tuple[list[tuple[int, Chain, int]], list[int], list[int]]:
        """Return one proposal's changed entries, new row ids, and old row ids."""
        count = min(
            max(1, int(len(schedule) * self.destroy_fraction)),
            self.max_destroy,
            len(blocks),
        )
        chosen = self.rng.sample(blocks, count)
        entries: list[tuple[int, Chain, int]] = []
        new_rows: list[int] = []
        old_rows: list[int] = []
        for block in chosen:
            options = option_chains[block]
            index = self.rng.randrange(len(options))
            chain = options[index]
            row = option_rows[block][index]
            entries.append((block, chain, row))
            new_rows.append(row)
            old_rows.append(current_rows[block])
        return entries, new_rows, old_rows

    def run(self, initial: Schedule, rounds: int, *, check: int = 0) -> SearchResult:
        """Run a fixed number of proposal batches from ``initial``.

        Parameters
        ----------
        initial : dict of int to tuple of (str, int)
            The starting schedule.  It is not mutated.
        rounds : int
            The number of proposal batches.
        check : int, optional
            Compare the first ``check`` batches' device prices with the exact evaluator
            and raise when they differ.  Zero disables the check.  Defaults to zero.

        Returns
        -------
        SearchResult
            The best schedule, its exact objective, and run counters.

        Raises
        ------
        ValueError
            When ``rounds`` is negative or a proposal would touch no block.
        """
        if rounds < 0:
            raise ValueError("rounds must not be negative")
        if not initial:
            raise ValueError("the batched search needs at least one assigned block")
        started = time.perf_counter()
        schedule = dict(initial)
        self.evaluator.reset(schedule)
        initial_objective = self.evaluator.objective
        totals = self.pricer.totals(self.evaluator.totals).unsqueeze(0)
        current_objective = torch.tensor(
            [initial_objective], dtype=torch.float64, device=self.table.device
        )
        best_objective = initial_objective
        best = dict(schedule)
        journal: list[tuple[int, Chain]] = []
        blocks = tuple(schedule)
        option_chains = {block: self.candidates[block] for block in blocks}
        option_rows = {
            block: [self.table.row_id(block, chain) for chain in chains]
            for block, chains in option_chains.items()
        }
        current_rows = {
            block: (0 if not chain else self.table.row_id(block, chain))
            for block, chain in schedule.items()
        }
        cooling = (self.final_temperature / self.temperature) ** (1.0 / max(1, rounds))
        temperature = self.temperature
        accepted = 0
        for round_index in range(rounds):
            entries: list[list[tuple[int, Chain, int]]] = []
            new_ids: list[list[int]] = []
            old_ids: list[list[int]] = []
            for _ in range(self.proposals):
                entry, new, old = self._proposal(
                    schedule, current_rows, blocks, option_chains, option_rows
                )
                entries.append(entry)
                new_ids.append(new)
                old_ids.append(old)
            new_tensor = torch.tensor(new_ids, dtype=torch.int64, device=self.table.device)
            old_tensor = torch.tensor(old_ids, dtype=torch.int64, device=self.table.device)
            deltas = self.table.lns_deltas(new_tensor, old_tensor)
            objective_delta = self.pricer.delta(totals, deltas)
            if round_index < check:
                self.evaluator.reset(schedule)
                for index, entry in enumerate(entries):
                    changed = [block for block, _chain, _row in entry]
                    proposed = dict(schedule)
                    for block, chain, _row in entry:
                        proposed[block] = chain
                    expected = self.evaluator.delta(changed, proposed)
                    actual = float(objective_delta[index])
                    if not math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6):
                        raise AssertionError(
                            f"device delta {actual!r} differs from exact delta {expected!r}"
                        )
            choice = int(torch.argmin(objective_delta))
            increase = float(objective_delta[choice])
            jump = increase <= 0.0 or self.rng.random() < math.exp(
                -increase / max(temperature, 1e-9)
            )
            if jump:
                accepted += 1
                totals = totals + deltas[choice].unsqueeze(0)
                current_objective = current_objective + objective_delta[choice]
                for block, chain, row in entries[choice]:
                    schedule[block] = chain
                    current_rows[block] = row
                    journal.append((block, chain))
                if float(current_objective[0]) < best_objective - 1e-9:
                    for block, chain in journal:
                        best[block] = chain
                    journal.clear()
                    best_objective = float(current_objective[0])
            temperature *= cooling
        for block, chain in journal:
            best[block] = chain
        elapsed = time.perf_counter() - started
        return SearchResult(
            schedule=best,
            objective=best_objective,
            initial_objective=initial_objective,
            rounds=rounds,
            proposals=rounds * self.proposals,
            accepted=accepted,
            seconds=elapsed,
        )
