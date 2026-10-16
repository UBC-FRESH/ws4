"""Spatial constraints over the block adjacency topology.

A maximum opening size caps the area of a connected patch of blocks disturbed in the same
year. A green-up rule requires a minimum number of years between disturbances of adjacent
blocks. The functions here report violations, so the simulator can show them and the
optimizer can penalize them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from .metrics import connected_patches, core_area, patch_perimeter


def openings_by_year(
    selected_by_year: Mapping[int, Iterable[int]],
    edges: Iterable[tuple[int, int]],
    block_area: Mapping[int, float],
) -> dict[int, float]:
    """Return the largest opening area per year.

    Parameters
    ----------
    selected_by_year : mapping of int to iterable of int
        The blocks disturbed in each year.
    edges : iterable of (int, int)
        The adjacency edges (undirected).
    block_area : mapping of int to float
        The area of each block, in hectares.

    Returns
    -------
    dict of int to float
        The largest connected opening area in each year that had a disturbance.
    """
    edge_list = list(edges)
    result: dict[int, float] = {}
    for year, selected in selected_by_year.items():
        patches = connected_patches(selected, edge_list)
        areas = [sum(block_area.get(block, 0.0) for block in patch) for patch in patches]
        result[int(year)] = max(areas) if areas else 0.0
    return result


def opening_violations(
    selected_by_year: Mapping[int, Iterable[int]],
    edges: Iterable[tuple[int, int]],
    block_area: Mapping[int, float],
    max_opening_ha: float,
) -> list[dict[str, object]]:
    """Return one record per patch whose area exceeds the maximum opening size.

    Parameters
    ----------
    selected_by_year : mapping of int to iterable of int
        The blocks disturbed in each year.
    edges : iterable of (int, int)
        The adjacency edges.
    block_area : mapping of int to float
        The area of each block.
    max_opening_ha : float
        The maximum permitted opening area.

    Returns
    -------
    list of dict
        Each record has ``kind`` (``"opening"``), ``year``, ``area_ha``, and ``limit``.
    """
    edge_list = list(edges)
    records: list[dict[str, object]] = []
    for year, selected in selected_by_year.items():
        for patch in connected_patches(selected, edge_list):
            area = sum(block_area.get(block, 0.0) for block in patch)
            if area > max_opening_ha:
                records.append(
                    {
                        "kind": "opening",
                        "year": int(year),
                        "area_ha": area,
                        "limit": max_opening_ha,
                    }
                )
    return records


def green_up_violations(
    disturbance_years: Mapping[int, Sequence[int]],
    edges: Iterable[tuple[int, int]],
    min_years: int,
) -> list[dict[str, object]]:
    """Return one record per adjacent pair disturbed within the green-up interval.

    A block may be disturbed several times (rotations). A pair is a violation when the
    closest of their disturbance years is within the interval, and the record's ``years`` is
    that closest gap.

    Parameters
    ----------
    disturbance_years : mapping of int to sequence of int
        The years each block is disturbed.
    edges : iterable of (int, int)
        The adjacency edges (undirected).
    min_years : int
        The minimum number of years between disturbances of adjacent blocks.

    Returns
    -------
    list of dict
        Each record has ``kind`` (``"green_up"``), ``block_a``, ``block_b``, ``years``, and
        ``limit``.
    """
    records: list[dict[str, object]] = []
    for u, v in edges:
        years_u = disturbance_years.get(u)
        years_v = disturbance_years.get(v)
        if not years_u or not years_v:
            continue
        gap = min(abs(int(a) - int(b)) for a in years_u for b in years_v)
        if gap < min_years:
            records.append(
                {
                    "kind": "green_up",
                    "block_a": int(u),
                    "block_b": int(v),
                    "years": gap,
                    "limit": min_years,
                }
            )
    return records


def spatial_penalty(
    selected_by_year: Mapping[int, Iterable[int]],
    disturbance_years: Mapping[int, Sequence[int]],
    edges: Iterable[tuple[int, int]],
    block_area: Mapping[int, float],
    max_opening_ha: float | None,
    min_green_up_years: int | None,
) -> float:
    """Return a penalty for the spatial violations of a schedule.

    The penalty is the summed excess opening area plus the summed green-up shortfall, so a
    schedule that respects the constraints scores zero.

    Parameters
    ----------
    selected_by_year : mapping of int to iterable of int
        The blocks disturbed in each year.
    disturbance_years : mapping of int to sequence of int
        The years each block is disturbed.
    edges : iterable of (int, int)
        The adjacency edges.
    block_area : mapping of int to float
        The area of each block.
    max_opening_ha : float or None
        The maximum opening size, or None to skip the opening check.
    min_green_up_years : int or None
        The green-up interval, or None to skip the green-up check.

    Returns
    -------
    float
        The penalty; zero when the schedule respects every active constraint.
    """
    edge_list = list(edges)
    penalty = 0.0
    if max_opening_ha is not None:
        for record in opening_violations(selected_by_year, edge_list, block_area, max_opening_ha):
            penalty += float(str(record["area_ha"])) - max_opening_ha
    if min_green_up_years is not None:
        for record in green_up_violations(disturbance_years, edge_list, min_green_up_years):
            penalty += float(min_green_up_years - int(str(record["years"])))
    return penalty


def core_area_violations(
    selected_by_year: Mapping[int, Iterable[int]],
    edges: Iterable[tuple[int, int, float]],
    block_area: Mapping[int, float],
    buffer_m: float,
    min_core_area_ha: float,
) -> list[dict[str, object]]:
    """Return one record per patch whose core area is below the minimum.

    The core area removes a strip of ``buffer_m`` metres around the patch perimeter (see
    :func:`ws4.patch.metrics.core_area`), so a core-area rule keeps interior habitat, not
    just the disturbed area.

    Parameters
    ----------
    selected_by_year : mapping of int to iterable of int
        The blocks disturbed in each year.
    edges : iterable of (int, int, float)
        The adjacency edges ``(src, dst, shared_length)``.
    block_area : mapping of int to float
        The area of each block, in hectares.
    buffer_m : float
        The buffer width, in metres.
    min_core_area_ha : float
        The minimum core area, in hectares.

    Returns
    -------
    list of dict
        Each record has ``kind`` (``"core_area"``), ``year``, ``area_ha`` (the core),
        and ``limit``.
    """
    edge_list = list(edges)
    adjacency = [(source, target) for source, target, _ in edge_list]
    records: list[dict[str, object]] = []
    for year, selected in selected_by_year.items():
        for patch in connected_patches(selected, adjacency):
            area = sum(block_area.get(block, 0.0) for block in patch)
            perimeter = patch_perimeter(patch, edge_list)
            core = core_area(area, perimeter, buffer_m)
            if core < min_core_area_ha:
                records.append(
                    {
                        "kind": "core_area",
                        "year": int(year),
                        "area_ha": core,
                        "limit": min_core_area_ha,
                        "block_a": -1,
                        "block_b": -1,
                        "years": 0,
                    }
                )
    return records


def core_area_penalty(
    selected_by_year: Mapping[int, Iterable[int]],
    edges: Iterable[tuple[int, int, float]],
    block_area: Mapping[int, float],
    buffer_m: float,
    min_core_area_ha: float,
) -> float:
    """Return the summed core-area shortfall of a schedule.

    Parameters
    ----------
    selected_by_year : mapping of int to iterable of int
        The blocks disturbed in each year.
    edges : iterable of (int, int, float)
        The adjacency edges ``(src, dst, shared_length)``.
    block_area : mapping of int to float
        The area of each block, in hectares.
    buffer_m : float
        The buffer width, in metres.
    min_core_area_ha : float
        The minimum core area, in hectares.

    Returns
    -------
    float
        The summed shortfall; zero when every patch's core is at least the minimum.
    """
    return sum(
        min_core_area_ha - float(str(record["area_ha"]))
        for record in core_area_violations(
            selected_by_year, edges, block_area, buffer_m, min_core_area_ha
        )
    )


def edge_contrast(
    values1: Mapping[int, float],
    values2: Mapping[int, float],
    edges: Iterable[tuple[int, int, float]],
    factor: float = 1.0,
) -> float:
    """Return the contrast edge between two attributes over an adjacency.

    Following the established edge metric, the contrast is the shared edge where one side
    matches the first attribute and the other side matches the second, weighted by the
    per-unit values and the shared edge length. Formally, an edge ``(A, B)`` contributes
    ``abs(v1(A)*v2(B) - v1(B)*v2(A)) * shared_length``: it is nonzero exactly when the
    two sides differ in type. A scale ``factor`` weights some edge types more heavily.

    Parameters
    ----------
    values1 : mapping of int to float
        The per-block value of the first attribute.
    values2 : mapping of int to float
        The per-block value of the second attribute.
    edges : iterable of (int, int, float)
        The adjacency edges ``(src, dst, shared_length)``.
    factor : float, optional
        A scaling factor applied to the difference.

    Returns
    -------
    float
        The contrast edge (a length), zero when no adjacent pair contrasts.
    """
    total = 0.0
    for source, target, length in edges:
        cross = abs(
            values1.get(source, 0.0) * values2.get(target, 0.0)
            - values1.get(target, 0.0) * values2.get(source, 0.0)
        )
        total += cross * length
    return total * factor


def schedule_years(
    schedule: Sequence[tuple[int, int]],
) -> tuple[dict[int, set[int]], dict[int, list[int]]]:
    """Split a schedule into per-year blocks and each block's disturbance years.

    A block may be disturbed more than once (rotations), so the second result maps each
    block to every year it is disturbed, sorted.

    Parameters
    ----------
    schedule : sequence of (int, int)
        ``(block_id, year)`` pairs.

    Returns
    -------
    tuple of (dict, dict)
        The blocks disturbed in each year, and the disturbance years per block.
    """
    selected_by_year: dict[int, set[int]] = {}
    disturbance_years: dict[int, set[int]] = {}
    for block, year in schedule:
        selected_by_year.setdefault(int(year), set()).add(int(block))
        disturbance_years.setdefault(int(block), set()).add(int(year))
    return selected_by_year, {block: sorted(years) for block, years in disturbance_years.items()}
