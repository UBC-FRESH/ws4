"""Incremental patch state for one criterion group and one year.

A period's patch accounts are derived from the connected components of the member blocks and
their areas and perimeters. Rebuilding them from scratch on every move is what makes patch
targets slow. This class maintains the components, their areas and perimeters, and the
per-size-class sums directly, so setting one block's criterion value costs O(degree) in the
common case and O(affected component) when a component splits or merges.

The class is deliberately self-contained and is held to exact parity with the from-scratch
computation (see ``tests/test_patch_state.py``).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

from ..patch.accounts import PatchAccount, size_class_labels


def compactness(area_ha: float, perimeter_m: float) -> float:
    """Return a patch's compactness from 0 to 100 (100 is a circle)."""
    area_m2 = area_ha * 10000.0
    if area_m2 <= 0.0 or perimeter_m <= 0.0:
        return 0.0
    return min(100.0, 100.0 * 4.0 * math.pi * area_m2 / (perimeter_m * perimeter_m))


def class_of(account: PatchAccount, area: float) -> str:
    """Return the size-class label an area falls in."""
    labels = size_class_labels(account.size_classes)
    for index, upper in enumerate(account.size_classes):
        lower = 0.0 if index == 0 else account.size_classes[index - 1]
        if lower < area <= upper:
            return labels[index]
    return labels[-1]


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
        self.values: dict[int, float] = {}
        self.comp: dict[int, int] = {}
        self.members: dict[int, set[int]] = {}
        self.area: dict[int, float] = {}
        self.perimeter: dict[int, float] = {}
        self.next_id = 0
        self.total = 0.0
        self.count = 0
        self.class_of: list[dict[int, str]] = [{} for _ in self.accounts]
        self.sums: list[dict[str, list[float]]] = [
            {label: [0.0, 0.0, 0.0] for label in size_class_labels(a.size_classes)}
            for a in self.accounts
        ]

    def _new_id(self) -> int:
        """Return a fresh component id."""
        self.next_id += 1
        return self.next_id

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
        for index, account in enumerate(self.accounts):
            label = class_of(account, area)
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
        self.values = dict(values)
        self.comp = {}
        self.members = {}
        self.area = {}
        self.perimeter = {}
        self.class_of = [{} for _ in self.accounts]
        self.sums = [
            {label: [0.0, 0.0, 0.0] for label in size_class_labels(a.size_classes)}
            for a in self.accounts
        ]
        self.total = 0.0
        for block, value in self.values.items():
            self.total += value * self.block_area.get(block, 0.0)
        for start in self.values:
            if start in self.comp:
                continue
            cid = self._new_id()
            members: set[int] = set()
            stack = [start]
            self.comp[start] = cid
            area = 0.0
            perimeter = 0.0
            while stack:
                block = stack.pop()
                members.add(block)
                area += self.values[block] * self.block_area.get(block, 0.0)
                for other, length in self.neighbours.get(block, ()):
                    if other in self.values:
                        if other not in self.comp:
                            self.comp[other] = cid
                            stack.append(other)
                    else:
                        perimeter += length
            self.members[cid] = members
            self.area[cid] = area
            self.perimeter[cid] = perimeter
            self._add_class(cid)
        self.count = len(self.members)

    def rebuild_local(self, changed: Sequence[int], lookup: Callable[[int], float]) -> None:
        """Apply new criterion values to the changed blocks, rebuilding only nearby components.

        Only the components containing a changed block or one of its member neighbours can
        change, so everything else is left untouched — the spatial locality of patches.

        Parameters
        ----------
        changed : sequence of int
            The blocks whose criterion value changed.
        lookup : callable
            Returns the new criterion value for a block (0.0 when it is not a member).
        """
        touched: set[int] = set()
        for block in changed:
            value = lookup(block)
            previous = self.values.get(block)
            if value > self.threshold:
                self.values[block] = value
                self.total += (value - (previous or 0.0)) * self.block_area.get(block, 0.0)
            elif previous is not None:
                del self.values[block]
                self.total -= previous * self.block_area.get(block, 0.0)
            touched.add(block)
            for other, _ in self.neighbours.get(block, ()):
                if other in self.values:
                    touched.add(other)
        seeds = {block for block in touched if block in self.values}
        seen: set[int] = set()
        rebuilt: list[set[int]] = []
        for start in seeds:
            if start in seen:
                continue
            piece: set[int] = set()
            stack = [start]
            seen.add(start)
            while stack:
                block = stack.pop()
                piece.add(block)
                for other, _ in self.neighbours.get(block, ()):
                    if other in self.values and other not in seen:
                        seen.add(other)
                        stack.append(other)
            rebuilt.append(piece)
        stale: set[int] = set()
        for block in touched:
            cid = self.comp.get(block)
            if cid is not None:
                stale.add(cid)
        for block in seen:
            cid = self.comp.get(block)
            if cid is not None:
                stale.add(cid)
        for cid in stale:
            self._drop_class(cid)
            self.members.pop(cid, None)
            self.area.pop(cid, None)
            self.perimeter.pop(cid, None)
            self.count -= 1
        for piece in rebuilt:
            cid = self._new_id()
            self.members[cid] = piece
            area = 0.0
            perimeter = 0.0
            for block in piece:
                area += self.values[block] * self.block_area.get(block, 0.0)
                for other, length in self.neighbours.get(block, ()):
                    if other not in self.values:
                        perimeter += length
                self.comp[block] = cid
            self.area[cid] = area
            self.perimeter[cid] = perimeter
            self._add_class(cid)
            self.count += 1

    def set_value(self, block: int, value: float | None) -> None:
        """Set a block's criterion value, or remove it (``None`` or at/below the threshold).

        Parameters
        ----------
        block : int
            The block.
        value : float or None
            The criterion value.
        """
        if value is None or value <= self.threshold:
            if block in self.values:
                self._detach(block)
            return
        old = self.values.get(block)
        if old is None:
            self._attach(block, value)
        elif old != value:
            self._resize(block, value)

    def _attach(self, block: int, value: float) -> None:
        """Add a member, merging the components it bridges."""
        self.values[block] = value
        adjacent: list[tuple[int, float]] = []
        add_perimeter = 0.0
        for other, length in self.neighbours.get(block, ()):
            if other in self.values:
                adjacent.append((other, length))
            else:
                add_perimeter += length
        cids = {self.comp[other] for other, _ in adjacent}
        merged = len(cids)
        for cid in cids:
            self._drop_class(cid)
        for other, length in adjacent:
            self.perimeter[self.comp[other]] -= length
        if not cids:
            cid = self._new_id()
            self.area[cid] = 0.0
            self.perimeter[cid] = 0.0
            self.members[cid] = set()
        else:
            cid = cids.pop()
            for other_cid in cids:
                cid = self._merge(cid, other_cid)
        self.comp[block] = cid
        self.members[cid].add(block)
        self.area[cid] += value * self.block_area.get(block, 0.0)
        self.perimeter[cid] += add_perimeter
        self.total += value * self.block_area.get(block, 0.0)
        self.count += 1 - merged
        self._add_class(cid)

    def _merge(self, keep: int, other: int) -> int:
        """Merge two components, keeping ``keep``'s id."""
        self.area[keep] += self.area[other]
        self.perimeter[keep] += self.perimeter[other]
        for block in self.members[other]:
            self.comp[block] = keep
            self.members[keep].add(block)
        del self.members[other]
        del self.area[other]
        del self.perimeter[other]
        return keep

    def _detach(self, block: int) -> None:
        """Remove a member, splitting its component if it disconnects."""
        cid = self.comp.pop(block)
        value = self.values.pop(block)
        self.members[cid].discard(block)
        removed = value * self.block_area.get(block, 0.0)
        self._drop_class(cid)
        self.area[cid] -= removed
        self.total -= removed
        for other, length in self.neighbours.get(block, ()):
            if other in self.values:
                self.perimeter[cid] += length
            else:
                self.perimeter[cid] -= length
        if not self.members[cid]:
            del self.members[cid]
            del self.area[cid]
            del self.perimeter[cid]
            self.count -= 1
            return
        member_neighbours = sum(
            1 for other, _ in self.neighbours.get(block, ()) if other in self.values
        )
        if member_neighbours <= 1:
            # a leaf removal cannot disconnect the component, so skip the connectivity walk
            self._add_class(cid)
            return
        seen = self._component_from(next(iter(self.members[cid])), cid)
        if len(seen) == len(self.members[cid]):
            self._add_class(cid)
            return
        self.count += self._split(cid, seen)

    def _component_from(self, start: int, cid: int) -> set[int]:
        """Return the members reachable from ``start`` within component ``cid``."""
        seen = {start}
        stack = [start]
        while stack:
            block = stack.pop()
            for other, _ in self.neighbours.get(block, ()):
                if other in self.values and self.comp[other] == cid and other not in seen:
                    seen.add(other)
                    stack.append(other)
        return seen

    def _split(self, cid: int, first: set[int]) -> int:
        """Split ``cid`` into connected pieces; return the change in the component count."""
        pieces: list[set[int]] = [first]
        remaining = self.members[cid] - first
        while remaining:
            start = next(iter(remaining))
            piece = self._component_from(start, cid)
            pieces.append(piece)
            remaining -= piece
        self._drop_class(cid)
        del self.members[cid]
        del self.area[cid]
        del self.perimeter[cid]
        for piece in pieces:
            new_id = self._new_id()
            self.members[new_id] = piece
            area = 0.0
            perimeter = 0.0
            for block in piece:
                area += self.values[block] * self.block_area.get(block, 0.0)
                for other, length in self.neighbours.get(block, ()):
                    if other not in self.values:
                        perimeter += length
            self.area[new_id] = area
            self.perimeter[new_id] = perimeter
            for block in piece:
                self.comp[block] = new_id
            self._add_class(new_id)
        return len(pieces) - 1

    def _resize(self, block: int, value: float) -> None:
        """Change a member's value without changing its membership."""
        old = self.values[block]
        self.values[block] = value
        cid = self.comp[block]
        area = self.block_area.get(block, 0.0)
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
            labels = size_class_labels(account.size_classes)
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
