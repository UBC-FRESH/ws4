"""Optional native kernels for the simulator's hot loops.

numba is an optional dependency (the ``opt`` extra). When it is installed the simulator
uses an ``njit`` kernel for the per-block product gather — the loop that dominates a
move-based objective evaluation — and falls back to the pure-Python loop otherwise. The two
paths are held to exact parity by ``tests/test_kernels.py``.

The kernel takes prepared, array-shaped inputs (a CSR index over ``(track, treatment)``
products and transitions), so no per-call dictionary work is done in Python beyond mapping
the output product slots back to their labels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .engine import Simulator

try:  # pragma: no cover - which branch runs depends on the environment
    from numba import njit

    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    HAVE_NUMBA = False

    def njit(*args: object, **kwargs: object) -> object:  # type: ignore[no-redef]
        """Stand in for :func:`numba.njit` when numba is absent."""

        def wrap(func: object) -> object:
            return func

        if args and callable(args[0]):
            return args[0]
        return wrap


Cell = tuple[int, str]
_CAPACITY = 1024


@njit(cache=True)
def gather_chain_products(
    pos_track: np.ndarray,
    pos_age: np.ndarray,
    pos_area: np.ndarray,
    event_years: np.ndarray,
    event_slots: np.ndarray,
    transitions: np.ndarray,
    product_start: np.ndarray,
    product_count: np.ndarray,
    product_rows: np.ndarray,
    product_slots: np.ndarray,
    table: np.ndarray,
    age_max: int,
    out_year: np.ndarray,
    out_slot: np.ndarray,
    out_value: np.ndarray,
) -> int:
    """Write a block chain's product cells into the output arrays; return the count.

    Parameters
    ----------
    pos_track, pos_age, pos_area : numpy.ndarray
        The block's fragments' track slots, ages, and areas.
    event_years, event_slots : numpy.ndarray
        The chain's event years and treatment slots, in year order.
    transitions : numpy.ndarray
        ``[track_slot, treatment_slot, 2]`` -> successor track slot and reset age, or -1.
    product_start, product_count : numpy.ndarray
        ``[track_slot, treatment_slot]`` -> the slice of ``product_rows``/``product_slots``.
    product_rows, product_slots : numpy.ndarray
        The curve-table row and product label slot of each product.
    table : numpy.ndarray
        The curve table, indexed by row and integer age.
    age_max : int
        The largest valid age column.
    out_year, out_slot, out_value : numpy.ndarray
        Output buffers (at least the number of cells long).

    Returns
    -------
    int
        The number of cells written.
    """
    tracks = pos_track.copy()
    ages = pos_age.copy()
    n = tracks.shape[0]
    current = 0
    count = 0
    for e in range(event_years.shape[0]):
        year = event_years[e]
        slot = event_slots[e]
        gap = year - current
        if gap:
            for i in range(n):
                ages[i] += gap
            current = year
        for i in range(n):
            track = tracks[i]
            new_track = transitions[track, slot, 0]
            if new_track < 0:
                continue
            start = product_start[track, slot]
            stop = start + product_count[track, slot]
            area = pos_area[i]
            age = ages[i]
            if age < 0:
                age = 0
            elif age > age_max:
                age = age_max
            for j in range(start, stop):
                out_year[count] = year
                out_slot[count] = product_slots[j]
                out_value[count] = area * table[product_rows[j], age]
                count += 1
            tracks[i] = new_track
            ages[i] = transitions[track, slot, 1]
    return count


class ProductKernel:
    """A prepared native index for the per-block product gather.

    Attributes
    ----------
    simulator : Simulator
        The simulator whose (static) indexes are read.
    """

    def __init__(self, simulator: Simulator) -> None:
        """Build the CSR index over ``(track, treatment)`` products and transitions."""
        self.simulator = simulator
        labels = sorted(
            {label for pairs in simulator._products_by_key.values() for _, label in pairs}
        )
        self.labels = labels
        self.label_slot = {label: index for index, label in enumerate(labels)}
        self.treatment_slot = {
            name: index
            for index, name in enumerate(sorted(simulator.treatments["treatment"].unique()))
        }
        tracks = sorted(
            {int(track) for track in simulator.fragments["track_id"].unique()}
            | {int(track) for track in simulator.treatments["track_id"].unique()}
            | {int(track) for track in simulator.treatments["new_track"].unique()}
        )
        self.track_slot = {track: index for index, track in enumerate(tracks)}
        self.max_products = 1
        rows: list[int] = []
        slots: list[int] = []
        n_track = len(self.track_slot)
        n_treat = len(self.treatment_slot)
        self.product_start = np.zeros((n_track, n_treat), dtype=np.int64)
        self.product_count = np.zeros((n_track, n_treat), dtype=np.int64)
        for (track, treatment), pairs in simulator._products_by_key.items():
            track_index = self.track_slot.get(int(track))
            treat_index = self.treatment_slot.get(str(treatment))
            if track_index is None or treat_index is None:
                continue
            self.product_start[track_index, treat_index] = len(rows)
            self.product_count[track_index, treat_index] = len(pairs)
            self.max_products = max(self.max_products, len(pairs))
            for curve_id, label in pairs:
                rows.append(simulator._curve_table.row_of[int(curve_id)])
                slots.append(self.label_slot[label])
        self.product_rows = np.asarray(rows, dtype=np.int64)
        self.product_slots = np.asarray(slots, dtype=np.int64)
        self.transitions = np.full((n_track, n_treat, 2), -1, dtype=np.int64)
        for (track, treatment), (new_track, new_offset) in simulator._treatment_by_key.items():
            track_index = self.track_slot.get(int(track))
            treat_index = self.treatment_slot.get(str(treatment))
            if track_index is None or treat_index is None:
                continue
            self.transitions[track_index, treat_index, 0] = self.track_slot.get(int(new_track), -1)
            self.transitions[track_index, treat_index, 1] = int(new_offset)
        self.table = simulator._curve_table.table
        self.age_max = int(simulator._curve_table.age_max)
        self._blocks: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        self._chains: dict[tuple[int, object], tuple[np.ndarray, np.ndarray]] = {}
        self._out = (
            np.zeros(_CAPACITY, dtype=np.int64),
            np.zeros(_CAPACITY, dtype=np.int64),
            np.zeros(_CAPACITY, dtype=np.float64),
        )

    def _block(self, block: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """Return (and cache) a block's fragment track slots, ages, and areas."""
        cached = self._blocks.get(block)
        if cached is not None:
            return cached
        positions = self.simulator._block_index().get(int(block), [])
        if not positions:
            return None
        arrays_track, arrays_offset, arrays_area = self.simulator._fragment_arrays()
        pos = np.asarray(positions, dtype=np.int64)
        prepared = (
            np.asarray([self.track_slot[int(t)] for t in arrays_track[pos]], dtype=np.int64),
            arrays_offset[pos].copy(),
            arrays_area[pos].copy(),
        )
        self._blocks[block] = prepared
        return prepared

    def _chain(
        self, block: int, events: Sequence[tuple[str, int]]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (and cache) a chain's event years and treatment slots."""
        key = (block, tuple(events))
        cached = self._chains.get(key)
        if cached is not None:
            return cached
        ordered = sorted(events, key=lambda event: event[1])
        years = np.asarray([year for _, year in ordered], dtype=np.int64)
        slots = np.asarray(
            [self.treatment_slot[str(treatment)] for treatment, _ in ordered], dtype=np.int64
        )
        self._chains[key] = (years, slots)
        return years, slots

    def products(self, block: int, events: Sequence[tuple[str, int]]) -> dict[Cell, float]:
        """Return the product cells a chain makes on a block, using the kernel.

        Parameters
        ----------
        block : int
            The block.
        events : sequence of (str, int)
            The treatments and the year each is applied.

        Returns
        -------
        dict of (int, str) to float
            The product value per ``(year, label)`` cell (non-zero entries only).
        """
        prepared = self._block(block)
        if prepared is None or not events:
            return {}
        years, slots = self._chain(block, events)
        needed = prepared[0].shape[0] * max(1, years.shape[0]) * self.max_products
        if needed > self._out[0].shape[0]:
            self._out = (
                np.zeros(needed, dtype=np.int64),
                np.zeros(needed, dtype=np.int64),
                np.zeros(needed, dtype=np.float64),
            )
        count = gather_chain_products(
            prepared[0],
            prepared[1],
            prepared[2],
            years,
            slots,
            self.transitions,
            self.product_start,
            self.product_count,
            self.product_rows,
            self.product_slots,
            self.table,
            self.age_max,
            self._out[0],
            self._out[1],
            self._out[2],
        )
        year_out, slot_out, value_out = self._out
        totals: dict[Cell, float] = {}
        for index in range(int(count)):
            # Chain events and account cells are both offsets.
            cell = (int(year_out[index]), self.labels[int(slot_out[index])])
            totals[cell] = totals.get(cell, 0.0) + float(value_out[index])
        return {cell: value for cell, value in totals.items() if value != 0.0}
