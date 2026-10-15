"""Patch metrics over a block adjacency topology.

A patch is a connected component of selected (for example, disturbed) blocks in the
block adjacency graph. Metrics are the patch count, the size distribution, the mean
size, the perimeter, and the core area (the interior beyond a buffer from the edge).
"""

from __future__ import annotations

import math
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
        ``patch_count``, ``mean_patch_area``, ``max_patch_area`` (the largest opening),
        and one entry per size class.
    """
    patches = connected_patches(selected, edges)
    areas = [sum(block_area.get(block, 0.0) for block in patch) for patch in patches]
    metrics: dict[str, float] = {
        "patch_count": float(len(patches)),
        "mean_patch_area": (sum(areas) / len(areas)) if areas else 0.0,
        "max_patch_area": max(areas) if areas else 0.0,
    }
    metrics.update(patch_size_classes(patches, block_area, breaks))
    return metrics


def patch_perimeter(patch: Iterable[int], edges: Iterable[tuple[int, int, float]]) -> float:
    """Return a patch's boundary length (edges with one member end).

    Parameters
    ----------
    patch : iterable of int
        The patch's block ids.
    edges : iterable of (int, int, float)
        The adjacency edges ``(src, dst, shared_length)``.

    Returns
    -------
    float
        The summed length of the edges on the patch boundary.
    """
    members = set(patch)
    perimeter = 0.0
    for source, target, length in edges:
        if (source in members) != (target in members):
            perimeter += length
    return perimeter


def core_area(area_ha: float, perimeter_m: float, buffer_m: float) -> float:
    """Return the core area of a patch: its area beyond a buffer from the edge.

    The core is the patch area with a strip of width ``buffer_m`` removed around the
    perimeter, so ``core = area - perimeter * buffer + pi * buffer**2`` (the last term
    restores the rounded corners). The result is clipped at zero.

    Parameters
    ----------
    area_ha : float
        The patch area, in hectares.
    perimeter_m : float
        The patch perimeter, in metres.
    buffer_m : float
        The buffer width, in metres.

    Returns
    -------
    float
        The core area, in hectares (zero when the buffer consumes the patch).
    """
    area_m2 = area_ha * 10000.0
    core_m2 = area_m2 - perimeter_m * buffer_m + math.pi * buffer_m * buffer_m
    return max(0.0, core_m2) / 10000.0


def patch_core_areas(
    patches: Sequence[set[int]],
    edges: Iterable[tuple[int, int, float]],
    block_area: Mapping[int, float],
    buffer_m: float,
) -> list[dict[str, float]]:
    """Return each patch's area, perimeter, and core area.

    Parameters
    ----------
    patches : sequence of set of int
        The patches.
    edges : iterable of (int, int, float)
        The adjacency edges ``(src, dst, shared_length)``.
    block_area : mapping of int to float
        The area of each block, in hectares.
    buffer_m : float
        The buffer width, in metres.

    Returns
    -------
    list of dict
        One record per patch, with ``area_ha``, ``perimeter_m``, and ``core_area_ha``.
    """
    edge_list = list(edges)
    records: list[dict[str, float]] = []
    for patch in patches:
        area = sum(block_area.get(block, 0.0) for block in patch)
        perimeter = patch_perimeter(patch, edge_list)
        records.append(
            {
                "area_ha": area,
                "perimeter_m": perimeter,
                "core_area_ha": core_area(area, perimeter, buffer_m),
            }
        )
    return records
