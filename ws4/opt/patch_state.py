"""Incremental patch state for one criterion group and one year.

A period's patch accounts are derived from the connected components of the member blocks and their
areas and perimeters. Rebuilding them from scratch on every move is what makes patch targets slow.
This class maintains the components directly, so a move is cheap: a detach only walks the component
when the block could be an articulation point, and that walk stops as soon as it has proved the
component stays connected. A bulk move (an LNS operator changes hundreds of blocks) relabels the
touched components in a compiled kernel.

The membership, criterion value and component of each block are held in arrays, so the kernel shares
the same representation and a bulk move needs no marshalling; the per-component aggregates are
dictionaries keyed by component id, and only the components a move touches are written back. The
class is held to exact parity with the from-scratch computation (see ``tests/test_patch_state.py``).
"""

from __future__ import annotations

import array
import math
from collections.abc import Mapping, Sequence

import numpy as np

from ..patch.accounts import PatchAccount, size_class_labels
from .patch_kernels import (
    component_from,
    label_all,
    label_from_seeds,
    piece_aggregate,
    reachable_from,
)


def compactness(area_ha: float, perimeter_m: float) -> float:
    """Return a patch's compactness from 0 to 100 (100 is a circle)."""
    area_m2 = area_ha * 10000.0
    if area_m2 <= 0.0 or perimeter_m <= 0.0:
        return 0.0
    return min(100.0, 100.0 * 4.0 * math.pi * area_m2 / (perimeter_m * perimeter_m))


def class_index(size_classes: Sequence[float], area: float) -> int:
    """Return the size-class index an area falls in."""
    for index, upper in enumerate(size_classes):
        lower = 0.0 if index == 0 else size_classes[index - 1]
        if lower < area <= upper:
            return index
    return len(size_classes) - 1


class PatchGroupYear:
    """The patch components and size-class sums of one criterion group in one year.

    Parameters
    ----------
    accounts : sequence of PatchAccount
        The accounts sharing the group's criterion and threshold.
    threshold : float
        The criterion value a block must exceed to be a member.
    neighbours : mapping of int to sequence of (int, float)
        The adjacency ``(neighbour, shared_length)`` per block.
    block_area : mapping of int to float
        The area of each block.

    Attributes
    ----------
    count : int
        The number of components.
    total : float
        The total patch area (the criterion value times the block area, summed).
    area : dict of int to float
        The area per component.
    perimeter : dict of int to float
        The shared boundary length per component.
    """

    def __init__(
        self,
        accounts: Sequence[PatchAccount],
        threshold: float,
        neighbours: Mapping[int, Sequence[tuple[int, float]]],
        block_area: Mapping[int, float],
    ) -> None:
        self.accounts = tuple(accounts)
        self.threshold = threshold
        self.neighbours = neighbours
        self.block_area = block_area
        self.blocks: tuple[int, ...] = tuple(sorted(set(block_area) | set(neighbours)))
        self.index: dict[int, int] = {block: i for i, block in enumerate(self.blocks)}
        size = len(self.blocks)
        # The per-node and per-edge state lives in array.array: indexing it from Python (the
        # per-block walks) costs about what a list does, while the compiled kernels get a
        # writable zero-copy numpy view, so a bulk relabel needs no marshalling either way.
        self.is_member = array.array("b", bytes(size))
        self.value = array.array("d", bytes(8 * size))
        self.comp = array.array("i", [-1] * size)
        self._area = array.array("d", (float(block_area.get(block, 0.0)) for block in self.blocks))
        ptr = array.array("q", bytes(8 * (size + 1)))
        index = array.array("q")
        length = array.array("d")
        for position, block in enumerate(self.blocks):
            for other, shared in neighbours.get(block, ()):
                neighbour = self.index.get(other)
                if neighbour is not None:
                    index.append(neighbour)
                    length.append(float(shared))
            ptr[position + 1] = len(index)
        self._ptr = ptr
        self._indices = index
        self._lengths = length
        self._v_member = np.frombuffer(self.is_member, dtype=np.int8)
        self._v_value = np.frombuffer(self.value, dtype=np.float64)
        self._v_comp = np.frombuffer(self.comp, dtype=np.int32)
        self._v_area = np.frombuffer(self._area, dtype=np.float64)
        self._v_ptr = np.frombuffer(self._ptr, dtype=np.int64)
        self._v_indices = np.frombuffer(self._indices, dtype=np.int64)
        self._v_lengths = np.frombuffer(self._lengths, dtype=np.float64)
        for view in (
            self._v_member,
            self._v_value,
            self._v_comp,
            self._v_area,
            self._v_ptr,
            self._v_indices,
            self._v_lengths,
        ):
            view.flags.writeable = True
        self.count_of: dict[int, int] = {}
        self.area: dict[int, float] = {}
        self.perimeter: dict[int, float] = {}
        self.next_id = 0
        self.total = 0.0
        self.count = 0
        self._labels = [size_class_labels(account.size_classes) for account in self.accounts]
        self._bounds = [tuple(account.size_classes) for account in self.accounts]
        self.class_of: list[dict[int, str]] = [{} for _ in self.accounts]
        self.sums: list[dict[str, list[float]]] = [
            {label: [0.0, 0.0, 0.0] for label in labels} for labels in self._labels
        ]
        self._buf_stack: np.ndarray | None = None
        self._buf_walk: np.ndarray | None = None
        self._buf_visited: np.ndarray | None = None
        self._buf_target: np.ndarray | None = None
        self._buf_stale: np.ndarray | None = None
        self._buf_area: np.ndarray | None = None
        self._buf_perim: np.ndarray | None = None
        self._buf_count: np.ndarray | None = None
        self._gen = 0

    def _new_id(self) -> int:
        """Return a fresh component id."""
        self.next_id += 1
        return self.next_id

    def _ensure_scratch(self) -> None:
        """Allocate the kernel scratch buffers on first use."""
        if self._buf_stack is not None:
            return
        size = len(self.blocks)
        self._buf_stack = np.empty(size, dtype=np.int32)
        self._buf_walk = np.empty(size, dtype=np.int32)
        self._buf_visited = np.zeros(size, dtype=np.int32)
        self._buf_target = np.zeros(size, dtype=np.uint8)
        self._buf_stale = np.zeros(size, dtype=np.int32)
        self._buf_area = np.empty(size, dtype=np.float64)
        self._buf_perim = np.empty(size, dtype=np.float64)
        self._buf_count = np.empty(size, dtype=np.int64)

    def _drop_class(self, cid: int) -> None:
        """Remove a component's contribution from every account's sums."""
        for index, table in enumerate(self.class_of):
            label = table.pop(cid, None)
            if label is None:
                continue
            entry = self.sums[index][label]
            entry[0] -= self.area[cid]
            entry[1] -= compactness(self.area[cid], self.perimeter[cid])
            entry[2] -= 1.0

    def _add_class(self, cid: int) -> None:
        """Add a component's contribution to every account's sums."""
        area = self.area[cid]
        shape = compactness(area, self.perimeter[cid])
        for index in range(len(self.accounts)):
            label = self._labels[index][class_index(self._bounds[index], area)]
            self.class_of[index][cid] = label
            entry = self.sums[index][label]
            entry[0] += area
            entry[1] += shape
            entry[2] += 1.0

    def rebuild(self, values: Mapping[int, float]) -> None:
        """Replace the member set, rebuilding the components and sums.

        Parameters
        ----------
        values : mapping of int to float
            The criterion value per member block.
        """
        size = len(self.blocks)
        self.is_member[:] = array.array("b", bytes(size))
        self.value[:] = array.array("d", bytes(8 * size))
        self.comp[:] = array.array("i", [-1] * size)
        self.total = 0.0
        for block, value in values.items():
            position = self.index.get(block)
            if position is None or value <= self.threshold:
                continue
            self.is_member[position] = 1
            self.value[position] = value
            self.total += value * self._area[position]
        self.count_of = {}
        self.area = {}
        self.perimeter = {}
        self.class_of = [{} for _ in self.accounts]
        self.sums = [{label: [0.0, 0.0, 0.0] for label in labels} for labels in self._labels]
        self._ensure_scratch()
        assert self._buf_stack is not None
        assert self._buf_visited is not None
        assert self._buf_area is not None
        assert self._buf_perim is not None
        assert self._buf_count is not None
        base = self.next_id + 1
        count = label_all(
            self._v_ptr,
            self._v_indices,
            self._v_lengths,
            self._v_area,
            self._v_member,
            self._v_value,
            self._v_comp,
            base,
            self._buf_stack,
            self._buf_area,
            self._buf_perim,
            self._buf_count,
        )
        for offset in range(count):
            cid = base + offset
            self.area[cid] = float(self._buf_area[offset])
            self.perimeter[cid] = float(self._buf_perim[offset])
            self.count_of[cid] = int(self._buf_count[offset])
            self._add_class(cid)
        self.next_id = base + count - 1
        self.count = count

    def rebuild_local(self, changed: Sequence[int], values: Mapping[int, float]) -> None:
        """Apply new criterion values to the changed blocks, rebuilding nearby components.

        Only the components containing a changed block or one of its member neighbours can change,
        so everything else is left untouched — the spatial locality of patches. The changed
        components are relabelled in the compiled kernel.

        Parameters
        ----------
        changed : sequence of int
            The blocks whose criterion value changed.
        values : mapping of int to float
            The new criterion value per changed block (0.0 when it is not a member).
        """
        positions: list[int] = []
        for block in changed:
            position = self.index.get(block)
            if position is None:
                continue
            positions.append(position)
            new = values.get(block, 0.0)
            previous = float(self.value[position]) if self.is_member[position] else 0.0
            if new > self.threshold:
                self.is_member[position] = 1
                self.value[position] = new
                self.total += (new - previous) * self._area[position]
            elif self.is_member[position]:
                self.is_member[position] = 0
                self.value[position] = 0.0
                self.total -= previous * self._area[position]
        if not positions:
            return
        self._ensure_scratch()
        assert self._buf_stack is not None
        assert self._buf_walk is not None
        assert self._buf_visited is not None
        assert self._buf_stale is not None
        assert self._buf_area is not None
        assert self._buf_perim is not None
        assert self._buf_count is not None
        self._gen += 2
        base = self.next_id + 1
        count, stale_count = label_from_seeds(
            self._v_ptr,
            self._v_indices,
            self._v_lengths,
            self._v_area,
            self._v_member,
            self._v_value,
            self._v_comp,
            np.array(positions, dtype=np.int64),
            base,
            self._buf_stack,
            self._buf_walk,
            self._buf_visited,
            self._gen,
            self._buf_area,
            self._buf_perim,
            self._buf_count,
            self._buf_stale,
        )
        # the kernel reports which component ids the changed blocks and their member neighbours
        # had, so the drop needs no scan of the neighbourhood here
        for cid in set(self._buf_stale[:stale_count].tolist()):
            self._drop_class(cid)
            self.count_of.pop(cid, None)
            self.area.pop(cid, None)
            self.perimeter.pop(cid, None)
            self.count -= 1
        for offset in range(count):
            cid = base + offset
            self.area[cid] = float(self._buf_area[offset])
            self.perimeter[cid] = float(self._buf_perim[offset])
            self.count_of[cid] = int(self._buf_count[offset])
            self._add_class(cid)
            self.count += 1
        self.next_id = base + count - 1

    def is_gap(self, position: int) -> bool:
        """Return whether a non-member joins two or more components.

        A gap block is the negative space between patches: adding it would merge the components its
        member-neighbours belong to, which is what a merge move deliberately targets.

        Parameters
        ----------
        position : int
            The block's dense index.

        Returns
        -------
        bool
            True when the block is a non-member with member-neighbours in two or more components.
        """
        if self.is_member[position]:
            return False
        first = -1
        for edge in range(self._ptr[position], self._ptr[position + 1]):
            neighbour = self._indices[edge]
            if not self.is_member[neighbour]:
                continue
            cid = int(self.comp[neighbour])
            if first < 0:
                first = cid
            elif cid != first:
                return True
        return False

    def is_cut(self, position: int) -> bool:
        """Return whether removing this member would split its component.

        Temporarily removes the block and asks the early-exit connectivity test whether every
        member-neighbour is still reachable, restoring the block afterwards. It is the same test a
        detach uses, so a split-targeted move can pick a block that will really split a patch.

        Parameters
        ----------
        position : int
            The block's dense index.

        Returns
        -------
        bool
            True when the block is an articulation point of its component.
        """
        if not self.is_member[position]:
            return False
        ptr = self._ptr
        indices = self._indices
        neighbours = [
            indices[edge]
            for edge in range(ptr[position], ptr[position + 1])
            if self.is_member[indices[edge]]
        ]
        if len(neighbours) <= 1:
            return False
        cid = int(self.comp[position])
        self.is_member[position] = 0
        self.comp[position] = -1
        self._ensure_scratch()
        assert self._buf_stack is not None
        assert self._buf_walk is not None
        assert self._buf_visited is not None
        assert self._buf_target is not None
        self._gen += 2
        reached_all, _count = reachable_from(
            self._v_ptr,
            self._v_indices,
            self._v_member,
            self._v_comp,
            neighbours[0],
            np.array(neighbours[1:], dtype=np.int64),
            self._buf_target,
            cid,
            self._buf_visited,
            self._buf_stack,
            self._buf_walk,
            self._gen,
        )
        self.is_member[position] = 1
        self.comp[position] = cid
        return not reached_all

    def value_of(self, block: int) -> float | None:
        """Return a block's criterion value, or None when it is not a member.

        Parameters
        ----------
        block : int
            The block.

        Returns
        -------
        float or None
            The criterion value, or None.
        """
        position = self.index.get(block)
        if position is None or not self.is_member[position]:
            return None
        return float(self.value[position])

    def set_value(self, block: int, value: float | None) -> None:
        """Set a block's criterion value, or remove it (``None`` or at/below the threshold).

        Parameters
        ----------
        block : int
            The block.
        value : float or None
            The criterion value.
        """
        position = self.index.get(block)
        if position is None:
            return
        if value is None or value <= self.threshold:
            if self.is_member[position]:
                self._detach(position)
            return
        if not self.is_member[position]:
            self._attach(position, value)
        elif float(self.value[position]) != value:
            self._resize(position, value)

    def _attach(self, position: int, value: float) -> None:
        """Add a member, merging the components it bridges."""
        self.is_member[position] = 1
        self.value[position] = value
        ptr = self._ptr
        indices = self._indices
        adjacent: list[tuple[int, float]] = []
        add_perimeter = 0.0
        for edge in range(ptr[position], ptr[position + 1]):
            neighbour = indices[edge]
            if self.is_member[neighbour]:
                adjacent.append((neighbour, float(self._lengths[edge])))
            else:
                add_perimeter += float(self._lengths[edge])
        representatives: dict[int, int] = {}
        for neighbour, _ in adjacent:
            cid = int(self.comp[neighbour])
            representatives.setdefault(cid, neighbour)
        for cid in representatives:
            self._drop_class(cid)
        for neighbour, length in adjacent:
            self.perimeter[int(self.comp[neighbour])] -= length
        if not representatives:
            cid = self._new_id()
            self.area[cid] = 0.0
            self.perimeter[cid] = 0.0
            self.count_of[cid] = 0
            merged = 0
        else:
            # absorb the smaller components into the largest, so the re-pointing walk is short
            order = sorted(representatives, key=lambda other: self.count_of[other], reverse=True)
            cid = order[0]
            for other in order[1:]:
                self.count_of[cid] += self.count_of[other]
                self.area[cid] += self.area[other]
                self.perimeter[cid] += self.perimeter[other]
                self._repoint(representatives[other], other, cid)
                self.count_of.pop(other, None)
                self.area.pop(other, None)
                self.perimeter.pop(other, None)
            merged = len(order)
        self.comp[position] = cid
        self.count_of[cid] += 1
        self.area[cid] += value * self._area[position]
        self.perimeter[cid] += add_perimeter
        self.total += value * self._area[position]
        self.count += 1 - merged
        self._add_class(cid)

    def _repoint(self, node: int, old: int, new: int) -> None:
        """Re-point every member of component ``old`` to ``new``, walking from ``node``."""
        ptr = self._ptr
        indices = self._indices
        member = self.is_member
        comp = self.comp
        comp[node] = new
        stack = [node]
        while stack:
            current = stack.pop()
            for edge in range(ptr[current], ptr[current + 1]):
                neighbour = indices[edge]
                if member[neighbour] and comp[neighbour] == old:
                    comp[neighbour] = new
                    stack.append(neighbour)

    def _detach(self, position: int) -> None:
        """Remove a member, splitting its component if it disconnects."""
        cid = int(self.comp[position])
        self.comp[position] = -1
        value = float(self.value[position])
        self.is_member[position] = 0
        self.value[position] = 0.0
        self.count_of[cid] -= 1
        removed = value * self._area[position]
        self._drop_class(cid)
        self.area[cid] -= removed
        self.total -= removed
        ptr = self._ptr
        indices = self._indices
        neighbour_nodes: list[int] = []
        for edge in range(ptr[position], ptr[position + 1]):
            neighbour = indices[edge]
            if self.is_member[neighbour]:
                self.perimeter[cid] += float(self._lengths[edge])
                neighbour_nodes.append(neighbour)
            else:
                self.perimeter[cid] -= float(self._lengths[edge])
        if self.count_of[cid] == 0:
            self.count_of.pop(cid, None)
            self.area.pop(cid, None)
            self.perimeter.pop(cid, None)
            self.count -= 1
            return
        if len(neighbour_nodes) <= 1:
            # a leaf removal cannot disconnect the component, so skip the connectivity walk
            self._add_class(cid)
            return
        self._ensure_scratch()
        assert self._buf_stack is not None
        assert self._buf_walk is not None
        assert self._buf_visited is not None
        assert self._buf_target is not None
        self._gen += 2
        reached_all, count = reachable_from(
            self._v_ptr,
            self._v_indices,
            self._v_member,
            self._v_comp,
            neighbour_nodes[0],
            np.array(neighbour_nodes[1:], dtype=np.int64),
            self._buf_target,
            cid,
            self._buf_visited,
            self._buf_stack,
            self._buf_walk,
            self._gen,
        )
        if reached_all:
            # every member-neighbour is reachable without the block: it is not an articulation
            # point, so the component stays connected
            self._add_class(cid)
            return
        self.count += self._split(cid, count, neighbour_nodes)

    def _split(self, cid: int, first_count: int, neighbour_nodes: Sequence[int]) -> int:
        """Split ``cid`` into connected pieces; return the change in the component count.

        The first piece is already in the walk buffer from the connectivity test, and every other
        piece contains a member-neighbour of the removed block, so the walk can start from those and
        never needs the component's member list. Stamping the first piece's component id before the
        later walks also stops them re-traversing it.
        """
        self._drop_class(cid)
        self.count_of.pop(cid, None)
        self.area.pop(cid, None)
        self.perimeter.pop(cid, None)
        assert self._buf_walk is not None
        assert self._buf_stack is not None
        assert self._buf_visited is not None
        added = 0
        new_id = self._new_id()
        area, perimeter = piece_aggregate(
            self._v_ptr,
            self._v_indices,
            self._v_lengths,
            self._v_member,
            self._v_value,
            self._v_area,
            self._buf_walk,
            first_count,
            new_id,
            self._v_comp,
        )
        self.count_of[new_id] = first_count
        self.area[new_id] = float(area)
        self.perimeter[new_id] = float(perimeter)
        self._add_class(new_id)
        added += 1
        for start in neighbour_nodes:
            if int(self._v_comp[start]) != cid:
                # already re-stamped as part of an earlier piece
                continue
            self._gen += 2
            count = component_from(
                self._v_ptr,
                self._v_indices,
                self._v_member,
                self._v_comp,
                start,
                cid,
                self._buf_visited,
                self._buf_stack,
                self._buf_walk,
                self._gen,
            )
            new_id = self._new_id()
            area, perimeter = piece_aggregate(
                self._v_ptr,
                self._v_indices,
                self._v_lengths,
                self._v_member,
                self._v_value,
                self._v_area,
                self._buf_walk,
                count,
                new_id,
                self._v_comp,
            )
            self.count_of[new_id] = count
            self.area[new_id] = float(area)
            self.perimeter[new_id] = float(perimeter)
            self._add_class(new_id)
            added += 1
        return added - 1

    def _resize(self, position: int, value: float) -> None:
        """Change a member's value without changing its membership."""
        old = float(self.value[position])
        self.value[position] = value
        cid = int(self.comp[position])
        area = self._area[position]
        self._drop_class(cid)
        self.area[cid] += (value - old) * area
        self.total += (value - old) * area
        self._add_class(cid)

    def cells(self) -> dict[str, float]:
        """Return the group's patch cells.

        Returns
        -------
        dict of str to float
            The sub-account values for each account in the group.
        """
        out: dict[str, float] = {}
        for index, account in enumerate(self.accounts):
            labels = self._labels[index]
            sums = self.sums[index]
            for label in labels:
                area, shape, count = sums[label]
                out[f"{account.name}.{label}.area"] = area
                out[f"{account.name}.{label}.size"] = (
                    100.0 * area / self.total if self.total > 0.0 else 0.0
                )
                out[f"{account.name}.{label}.frequency"] = count
                out[f"{account.name}.{label}.shape"] = shape / count if count else 0.0
            out[f"{account.name}.TOTAL.area"] = self.total
            out[f"{account.name}.TOTAL.frequency"] = float(self.count)
            if account.attractor is not None:
                out[f"{account.name}.{labels[account.attractor]}.attractor"] = 1.0
        return out
