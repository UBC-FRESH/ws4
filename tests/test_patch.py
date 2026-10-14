"""Tests for patch metrics over block topology."""

from __future__ import annotations

from ws4.patch.metrics import connected_patches, patch_metrics, patch_size_classes


def test_connected_patches_groups_adjacent_blocks() -> None:
    """Selected blocks form connected components over the edges."""
    edges = [(1, 2), (2, 3), (4, 5)]
    patches = connected_patches({1, 2, 3, 4}, edges)
    assert sorted(sorted(patch) for patch in patches) == [[1, 2, 3], [4]]


def test_patch_size_classes_counts_by_area() -> None:
    """Patches are counted by area class."""
    patches = [{1, 2, 3}, {4}]
    area = {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}
    assert patch_size_classes(patches, area, [5.0, 10.0]) == {"le5": 1, "le10": 1, "over": 0}


def test_patch_metrics_summary() -> None:
    """The summary reports the count, the mean size, and the classes."""
    metrics = patch_metrics(
        {1, 2, 3, 4}, [(1, 2), (2, 3), (4, 5)], {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}, [5.0, 10.0]
    )
    assert metrics["patch_count"] == 2.0
    assert metrics["mean_patch_area"] == 5.0
    assert metrics["le5"] == 1
    assert metrics["le10"] == 1


def test_isolated_blocks_are_singletons() -> None:
    """A selected block with no selected neighbour is its own patch."""
    assert connected_patches({7}, [(1, 2)]) == [{7}]
