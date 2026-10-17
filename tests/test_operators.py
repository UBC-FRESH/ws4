"""Tests for the neighbourhood operators."""

from __future__ import annotations

import random

from ws4.opt.operators import ClusterOperator, MergeOperator, Schedule, restore


def _candidates() -> dict[int, list[tuple[tuple[str, int], ...]]]:
    """Two options per block for five blocks."""
    return {block: [(("CC", 0),), (("CC", 1),)] for block in range(1, 6)}


def test_cluster_operator_changes_a_connected_set() -> None:
    """A cluster move rechooses a connected set of at most ``size`` blocks."""
    neighbours = {1: (2,), 2: (1, 3), 3: (2, 4), 4: (3,), 5: ()}
    operator = ClusterOperator(size=3, neighbours=neighbours)
    schedule: Schedule = {}
    undo = operator.propose_inplace(schedule, random.Random(0), _candidates())
    assert undo is not None
    assert 1 <= len(undo) <= 3
    for block in undo:
        assert block in schedule
    # every block in the move is reachable from the seed along the topology
    seed = next(iter(undo))
    reached = {seed}
    frontier = [seed]
    while frontier:
        block = frontier.pop()
        for other in neighbours.get(block, ()):
            if other in undo and other not in reached:
                reached.add(other)
                frontier.append(other)
    assert reached == set(undo)


def test_cluster_operator_undo_restores_the_schedule() -> None:
    """Undoing a cluster move restores the previous assignments."""
    neighbours = {1: (2,), 2: (1, 3), 3: (2,), 4: ()}
    operator = ClusterOperator(size=4, neighbours=neighbours)
    schedule: Schedule = {1: (("CC", 0),), 2: (("CC", 1),)}
    before = dict(schedule)
    undo = operator.propose_inplace(schedule, random.Random(1), _candidates())
    assert undo is not None
    restore(schedule, undo)
    assert schedule == before


def test_cluster_operator_without_neighbours_moves_one_block() -> None:
    """Without a topology the cluster is just the seed block."""
    operator = ClusterOperator(size=8, neighbours={})
    schedule: Schedule = {}
    undo = operator.propose_inplace(schedule, random.Random(2), _candidates())
    assert undo is not None
    assert len(undo) == 1


class _NoPatch:
    """An optimizer stand-in with no patch model."""

    def active_patch_model(self) -> None:
        """Return no model."""
        return None


def test_merge_operator_cannot_move_without_a_patch_model() -> None:
    """The merge operator declines when the run has no patch accounts."""
    operator = MergeOperator(_NoPatch())
    assert operator.propose_inplace({}, random.Random(3), _candidates()) is None
