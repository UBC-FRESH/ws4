"""Patch metrics over a block adjacency topology.

A patch is a connected component of selected (for example, disturbed) blocks in the
block adjacency graph. Metrics are the patch count, the size distribution, and the
mean size.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import pandas as pd


def load_topology(csv_path: Path) -> pd.DataFrame:
    """Load a proximal topology edgelist: ``src_block,dst_block,distance_m``.

    The edges are treated as undirected.

    Parameters
    ----------
    csv_path : Path
        The topology CSV.

    Returns
    -------
    pandas.DataFrame
        The edge list.
    """
    return pd.read_csv(csv_path)


def _find(parent: dict[int, int], node: int) -> int:
    """Find the representative of a node's set (with path compression)."""
    root = node
    while parent[root] != root:
        root = parent[root]
    while parent[node] != root:
        parent[node], node = root, parent[node]
    return root


def connected_patches(selected: Iterable[int], edges: Iterable[tuple[int, int]]) -> list[set[int]]:
    """Group selected blocks into connected patches.

    Parameters
    ----------
    selected : iterable of int
        The selected block ids.
    edges : iterable of (int, int)
        The adjacency edges (undirected).

    Returns
    -------
    list of set of int
        One set of block ids per patch.
    """
    nodes = set(selected)
    parent = {node: node for node in nodes}
    for u, v in edges:
        if u in nodes and v in nodes:
            ru, rv = _find(parent, u), _find(parent, v)
            if ru != rv:
                parent[ru] = rv
    patches: dict[int, set[int]] = {}
    for node in nodes:
        patches.setdefault(_find(parent, node), set()).add(node)
    return list(patches.values())


def patch_size_classes(
    patches: Sequence[set[int]], block_area: Mapping[int, float], breaks: Sequence[float]
) -> dict[str, int]:
    """Count patches by area size class.

    Parameters
    ----------
    patches : sequence of set of int
        The patches, from :func:`connected_patches`.
    block_area : mapping of int to float
        The area of each block, in hectares.
    breaks : sequence of float
        The upper bounds of the classes, ascending. A patch whose area is at or below
        a break belongs to that class; a patch above the last break is ``"over"``.

    Returns
    -------
    dict of str to int
        The patch count per class. Class names are ``"le<b>"`` for a break ``b`` and
        ``"over"`` for the last class.
    """
    counts = {f"le{break_point:g}": 0 for break_point in breaks}
    counts["over"] = 0
    for patch in patches:
        area = sum(block_area.get(block, 0.0) for block in patch)
        for break_point in breaks:
            if area <= break_point:
                counts[f"le{break_point:g}"] += 1
                break
        else:
            counts["over"] += 1
    return counts


def patch_metrics(
    selected: Iterable[int],
    edges: Iterable[tuple[int, int]],
    block_area: Mapping[int, float],
    breaks: Sequence[float],
) -> dict[str, float]:
    """Compute patch count, mean size, and the size-class distribution.

    Parameters
    ----------
    selected : iterable of int
        The selected block ids.
    edges : iterable of (int, int)
        The adjacency edges.
    block_area : mapping of int to float
        The area of each block.
    breaks : sequence of float
        The size-class upper bounds.

    Returns
    -------
    dict of str to float
        ``patch_count``, ``mean_patch_area``, and one entry per size class.
    """
    patches = connected_patches(selected, edges)
    areas = [sum(block_area.get(block, 0.0) for block in patch) for patch in patches]
    metrics: dict[str, float] = {
        "patch_count": float(len(patches)),
        "mean_patch_area": (sum(areas) / len(areas)) if areas else 0.0,
    }
    metrics.update(patch_size_classes(patches, block_area, breaks))
    return metrics
