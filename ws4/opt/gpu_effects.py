"""Sparse float64 effect table and batched delta kernels for the GPU search path.

The effect table turns every ``(block, chain)`` pair into one sparse row over the target
cells the objective reads.  It is built once, on the CPU, through the existing exact
:meth:`Optimizer._block_deltas` path, so it does not introduce a second simulator or a
different target semantics.  The rows are then uploaded as a CSR tensor and the batched
deltas are evaluated on the device with gather and segmented-sum operations.

Two operations cover the search prototypes:

- a single-block move is ``new_row - old_row``;
- an LNS move is the segment sum of the new rows minus the old rows for one neighbourhood.

``torch`` is an optional dependency (the ``gpu`` extra).  Importing this module succeeds
without it; constructing or evaluating a table raises :class:`RuntimeError` instead.  The
CPU search remains the reference and the fallback.

The table is target-specific.  Changing the active accounts, their period widths, or the
feature checkpoints changes the columns, so the table must be rebuilt.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, replace
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
    from .incremental import IncrementalObjective
    from .operators import Candidates, Chain

Cell = tuple[int, str]


def _require_torch() -> None:
    """Raise a clear error when torch is not installed."""
    if not HAVE_TORCH:
        raise RuntimeError(
            "the GPU effect table needs torch; install the optional 'gpu' dependency "
            "(pip install 'ws4[gpu]')"
        )


def target_cells(evaluator: IncrementalObjective) -> tuple[Cell, ...]:
    """Return every account cell the active targets read, in a stable order.

    The cells come from the evaluator's precomputed target and flow metadata, so the table
    covers exactly the cells a delta can price: accumulating product periods, level
    endpoints, feature checkpoints, and flow period cells.

    Parameters
    ----------
    evaluator : IncrementalObjective
        The move-based evaluator whose targets define the columns.

    Returns
    -------
    tuple of (int, str)
        The sorted ``(offset, account)`` cells.
    """
    cells: set[Cell] = set()
    for target_cells_for_index in evaluator._target_cells:
        cells.update(target_cells_for_index)
    for periods in evaluator._flow_period_cells.values():
        for period in periods:
            cells.update(period)
    if not cells:
        raise ValueError("the active targets read no account cells")
    return tuple(sorted(cells))


@dataclass(frozen=True)
class EffectTable:
    """A sparse float64 ``[rows, target_cells]`` effect table.

    Row zero is the all-zero empty-chain row, so an untreated block is represented by row
    zero and a move never needs a special case on the host.  Every other row is one
    ``(block, chain)`` pair.

    Parameters
    ----------
    cells : tuple of (int, str)
        The ``(offset, account)`` cell for each column.
    indptr : torch.Tensor
        The CSR row pointer, length ``rows + 1``.
    indices : torch.Tensor
        The target-cell column of each nonzero.
    values : torch.Tensor
        The float64 effect value of each nonzero.
    row_index : dict of (int, tuple) to int
        The row for each ``(block, chain)`` pair.  The empty chain maps to row zero.
    blocks : tuple of int
        The blocks whose candidate chains the table contains.

    Attributes
    ----------
    build_seconds : float
        Wall-clock seconds spent building the rows and packing them.
    """

    cells: tuple[Cell, ...]
    indptr: torch_type.Tensor
    indices: torch_type.Tensor
    values: torch_type.Tensor
    row_index: dict[tuple[int, Chain], int]
    blocks: tuple[int, ...]
    build_seconds: float = 0.0
    _max_row_width: int = 1

    @classmethod
    def build(
        cls,
        optimizer: Optimizer,
        evaluator: IncrementalObjective,
        blocks: Sequence[int] | None = None,
        extra_pairs: Sequence[tuple[int, Chain]] = (),
        device: str | torch_type.device | None = None,
        candidates: Candidates | None = None,
    ) -> EffectTable:
        """Build an effect table for a block slice through the exact CPU delta path.

        Parameters
        ----------
        optimizer : Optimizer
            The optimizer that owns the exact block-delta caches.
        evaluator : IncrementalObjective
            The evaluator whose active accounts and feature checkpoints define the rows.
        blocks : sequence of int or None, optional
            The blocks to include.  None uses every candidate block.
        extra_pairs : sequence of (int, tuple), optional
            Further ``(block, chain)`` pairs to include, such as the chains of a seed
            schedule that are not in the candidate list.
        device : str or torch.device or None, optional
            Upload the table to this device.  None leaves it on the CPU.
        candidates : mapping of int to list of tuple, optional
            The candidate chains, when the caller already has them.  This avoids
            rebuilding the candidate set for every table.

        Returns
        -------
        EffectTable
            The sparse table, with row zero reserved for the empty chain.
        """
        _require_torch()
        started = time.perf_counter()
        candidates = optimizer.candidates() if candidates is None else candidates
        chosen = tuple(sorted(candidates) if blocks is None else blocks)
        rows: list[tuple[int, Chain]] = [(0, ())]
        row_index: dict[tuple[int, Chain], int] = {(0, ()): 0}
        for block in chosen:
            for chain in candidates.get(block, ()):
                row_index[(block, chain)] = len(rows)
                rows.append((block, chain))
        for pair in extra_pairs:
            if pair in row_index:
                continue
            row_index[pair] = len(rows)
            rows.append(pair)
        pairs = rows[1:]
        deltas = optimizer._block_deltas(
            pairs, evaluator.accounts, evaluator._wanted_feature_offsets
        )
        cells = target_cells(evaluator)
        cell_index = {cell: column for column, cell in enumerate(cells)}
        # The first CSR row is the empty chain, which has no nonzeros.
        indptr: list[int] = [0, 0]
        indices: list[int] = []
        values: list[float] = []
        for pair in pairs:
            for cell, value in deltas[pair].items():
                column = cell_index.get(cell)
                if column is None or value == 0.0:
                    continue
                indices.append(column)
                values.append(float(value))
            indptr.append(len(indices))
        table = cls(
            cells=cells,
            indptr=torch.tensor(indptr, dtype=torch.int64),
            indices=torch.tensor(indices, dtype=torch.int64),
            values=torch.tensor(values, dtype=torch.float64),
            row_index=row_index,
            blocks=chosen,
            build_seconds=time.perf_counter() - started,
            _max_row_width=max(
                (later - earlier for earlier, later in itertools.pairwise(indptr)),
                default=0,
            ),
        )
        return table if device is None else table.to(device)

    @property
    def rows(self) -> int:
        """Return the number of effect rows, including the empty-chain row.

        Returns
        -------
        int
            The number of rows.
        """
        return int(self.indptr.numel()) - 1

    @property
    def nnz(self) -> int:
        """Return the number of nonzeros in the table.

        Returns
        -------
        int
            The nonzero count.
        """
        return int(self.indices.numel())

    @property
    def columns(self) -> int:
        """Return the number of target-cell columns.

        Returns
        -------
        int
            The column count.
        """
        return len(self.cells)

    @property
    def device(self) -> torch_type.device:
        """Return the device that holds the sparse tensors.

        Returns
        -------
        torch.device
            The tensor device.
        """
        return self.values.device

    def nbytes(self) -> int:
        """Return the bytes held by the three sparse tensors.

        Returns
        -------
        int
            The total tensor storage in bytes.
        """
        return (
            self.indptr.numel() * self.indptr.element_size()
            + self.indices.numel() * self.indices.element_size()
            + self.values.numel() * self.values.element_size()
        )

    def to(self, device: str | torch_type.device) -> EffectTable:
        """Return a copy of the table on another device.

        Parameters
        ----------
        device : str or torch.device
            The destination device.

        Returns
        -------
        EffectTable
            A table whose sparse tensors live on ``device``.
        """
        _require_torch()
        return replace(
            self,
            indptr=self.indptr.to(device),
            indices=self.indices.to(device),
            values=self.values.to(device),
        )

    def row_id(self, block: int, chain: Chain) -> int:
        """Return the table row for a block and chain, or zero for the empty chain.

        Parameters
        ----------
        block : int
            The block.
        chain : tuple of (str, int)
            The treatment chain.

        Returns
        -------
        int
            The row index.

        Raises
        ------
        KeyError
            When the pair is not in this table.
        """
        return 0 if not chain else self.row_index[(block, chain)]

    def gather(self, row_ids: torch_type.Tensor) -> torch_type.Tensor:
        """Return the dense float64 effect rows for the given row ids.

        Parameters
        ----------
        row_ids : torch.Tensor
            Integer row ids with any shape.

        Returns
        -------
        torch.Tensor
            A ``[..., columns]`` float64 tensor.
        """
        flat = row_ids.reshape(-1)
        segments = torch.arange(flat.numel(), dtype=torch.int64, device=self.device)
        out = self._segmented(flat, segments, None, flat.numel())
        return out.reshape(*row_ids.shape, self.columns)

    def row_deltas(self, row_ids: torch_type.Tensor) -> torch_type.Tensor:
        """Return the effect row for each id; a one-row move is just this row.

        Parameters
        ----------
        row_ids : torch.Tensor
            Integer row ids with any shape.

        Returns
        -------
        torch.Tensor
            A ``[..., columns]`` float64 tensor.
        """
        return self.gather(row_ids)

    def move_deltas(
        self,
        new_rows: torch_type.Tensor,
        old_rows: torch_type.Tensor | None = None,
    ) -> torch_type.Tensor:
        """Return the row difference for a batch of single-block moves.

        ``new_rows`` and ``old_rows`` have the same shape.  The result has one
        ``[columns]`` row per leading index; for a 2-D input the last axis is the LNS
        neighbourhood width, so the operation is also the LNS delta.

        Parameters
        ----------
        new_rows : torch.Tensor
            The new-chain row ids.
        old_rows : torch.Tensor or None, optional
            The old-chain row ids.  None treats every old chain as empty (row zero).

        Returns
        -------
        torch.Tensor
            A ``[..., columns]`` float64 tensor.

        Raises
        ------
        ValueError
            When the two id tensors have different shapes.
        """
        if old_rows is None:
            return self.row_deltas(new_rows)
        if new_rows.shape != old_rows.shape:
            raise ValueError("new_rows and old_rows must have the same shape")
        width = new_rows.numel() // max(1, new_rows.shape[0])
        segments = torch.arange(
            new_rows.shape[0], dtype=torch.int64, device=self.device
        ).repeat_interleave(width)
        segments = torch.cat((segments, segments))
        row_ids = torch.cat((new_rows.reshape(-1), old_rows.reshape(-1)))
        signs = torch.cat(
            (
                torch.ones(new_rows.numel(), dtype=torch.float64, device=self.device),
                -torch.ones(old_rows.numel(), dtype=torch.float64, device=self.device),
            )
        )
        return self._segmented(row_ids, segments, signs, new_rows.shape[0])

    def lns_deltas(
        self, new_rows: torch_type.Tensor, old_rows: torch_type.Tensor
    ) -> torch_type.Tensor:
        """Return one segmented delta per LNS neighbourhood.

        Parameters
        ----------
        new_rows : torch.Tensor
            A ``[moves, width]`` tensor of new-chain row ids.
        old_rows : torch.Tensor
            A ``[moves, width]`` tensor of old-chain row ids.

        Returns
        -------
        torch.Tensor
            A ``[moves, columns]`` float64 tensor.
        """
        if new_rows.ndim != 2 or old_rows.ndim != 2:
            raise ValueError("LNS row ids must be two-dimensional")
        return self.move_deltas(new_rows, old_rows)

    def segmented_delta(
        self,
        row_ids: torch_type.Tensor,
        segments: torch_type.Tensor,
        signs: torch_type.Tensor | None = None,
    ) -> torch_type.Tensor:
        """Return a signed segmented sum of effect rows.

        Parameters
        ----------
        row_ids : torch.Tensor
            A one-dimensional tensor of row ids.
        segments : torch.Tensor
            The output segment of each row id.
        signs : torch.Tensor or None, optional
            The sign of each row id.  None adds every row.

        Returns
        -------
        torch.Tensor
            A ``[segments.max() + 1, columns]`` float64 tensor.

        Raises
        ------
        ValueError
            When the inputs have different lengths or a segment is negative.
        """
        if row_ids.ndim != 1 or segments.ndim != 1:
            raise ValueError("row_ids and segments must be one-dimensional")
        if row_ids.numel() != segments.numel():
            raise ValueError("row_ids and segments must have the same length")
        if bool((segments < 0).any()):
            raise ValueError("segments must not be negative")
        count = 0 if segments.numel() == 0 else int(segments.max()) + 1
        return self._segmented(row_ids, segments, signs, count)

    def _segmented(
        self,
        row_ids: torch_type.Tensor,
        segments: torch_type.Tensor,
        signs: torch_type.Tensor | None,
        count: int,
    ) -> torch_type.Tensor:
        """Return the signed segmented sum of the CSR rows.

        Parameters
        ----------
        row_ids : torch.Tensor
            A one-dimensional tensor of row ids.
        segments : torch.Tensor
            The output segment of each row id.
        signs : torch.Tensor or None
            The sign of each row id, already float64.
        count : int
            The number of output segments.

        Returns
        -------
        torch.Tensor
            A ``[count, columns]`` float64 tensor.
        """
        row_ids = row_ids.to(device=self.device, dtype=torch.int64)
        segments = segments.to(device=self.device, dtype=torch.int64)
        if bool(((row_ids < 0) | (row_ids >= self.rows)).any()):
            raise IndexError("row id outside the effect table")
        lengths = self.indptr[row_ids + 1] - self.indptr[row_ids]
        starts = self.indptr[row_ids]
        # Expand each selected row to its nonzeros without a host synchronization.  The
        # grid is [selected rows, widest row]; the mask drops the padding.
        offsets = torch.arange(self._max_row_width, dtype=torch.int64, device=self.device)
        mask = offsets.unsqueeze(0) < lengths.unsqueeze(1)
        nonzero = (starts.unsqueeze(1) + offsets.unsqueeze(0))[mask]
        columns = self.indices[nonzero]
        expanded_segments = torch.repeat_interleave(segments, lengths)
        expanded_values = self.values[nonzero]
        if signs is not None:
            expanded_values = expanded_values * torch.repeat_interleave(
                signs.to(device=self.device, dtype=torch.float64), lengths
            )
        out = torch.zeros((count, self.columns), dtype=torch.float64, device=self.device)
        out.view(-1).index_add_(0, expanded_segments * self.columns + columns, expanded_values)
        return out
