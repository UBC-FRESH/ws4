"""Spread connectivity: how far a fire could run through the untreated blocks.

The patch-size accounts measure *shape*: how large the connected clusters of a criterion are. A
fuel-treatment pattern can win against fire while making that shape *worse* — on the TSA23 bridge
test a wind-perpendicular barrier burns least of three equal-area patterns and has the largest
large-patch share — because what a barrier does is **break the connectivity a fire spreads
through**, across the direction the fire travels. This module measures that property directly.

The topology is an undirected block adjacency (``src_block, dst_block, distance_m``) and carries no
bearings, so the direction comes from the account: a bearing in degrees clockwise from north, the
way a wind direction is stated. The graph is then **directed**: an edge transmits spread only from
its upwind end to its downwind one, and a treated block transmits nothing, so a band of treated
blocks cuts the paths that cross it.

Two things matter, and a first attempt got both wrong:

- **reachability is directed.** A fire does not run upwind, so the clusters are the *reachable* sets
  following downwind edges only. Undirected components made a band lying along the wind look
  exactly as good as one across it, which is the opposite of what the measure is for.
- **the cone is what makes a direction mean anything.** An edge transmits when it lies within
  ``tolerance`` degrees of the bearing. At 90 degrees *every* edge transmits, so on a regular
  lattice the measure collapses into the undirected one and the two bands are indistinguishable;
  at 60 degrees the edges that cross the fire's path are selected and the signal appears.

Three sub-accounts, all of which a fire-spread model would want *lower*:

``largest_component``
    The area of the largest set reachable from one untreated block: the compartment a fire could
    run through from a single ignition.
``percolation_reach``
    The mean area reachable from an untreated block, over the untreated blocks: the expected burned
    area from an ignition anywhere, which is the quantity a percolation threshold shows up in.
``edge_cut``
    The share of the downwind edges *leaving* the untreated blocks that the treatment stops. This is
    the directed barrier metric: a band across the wind stops every northward path and scores high,
    a band along the wind stops only the one path in front of it and scores low.

Every value is an area in hectares except ``edge_cut``, which is a percentage.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

#: A block's coordinate, in metres, as ``(x, y)`` east and north.
Point = tuple[float, float]


@dataclass(frozen=True)
class SpreadAccount:
    """A spread-connectivity account definition.

    Attributes
    ----------
    name : str
        The account name, used as the prefix of its sub-account cells.
    criteria : str
        The criterion label marking the **treated** blocks: a feature or a product, resolved the way
        a patch criterion is. A block is treated when its value exceeds ``threshold``.
    threshold : float
        The criterion value a block must exceed to count as treated (default 0.5, a block at least
        half covered by the criterion).
    bearing : float
        The spread direction, in degrees clockwise from north — the direction the fire travels,
        which is the wind direction. Default 225, the bridge test's wind.
    tolerance : float
        How far off the bearing an edge may lie and still transmit spread, in degrees (default 60, a
        cone 60 degrees wide each side of the bearing). At 90 every edge transmits and the direction
        stops discriminating, which the synthetic oracle pins.
    search_distance : float | None
        The longest hop an edge may span, in metres; None considers every edge (default 500, a
        generous hop for a block topology whose edges are shared boundaries).
    """

    name: str
    criteria: str
    threshold: float = 0.5
    bearing: float = 225.0
    tolerance: float = 60.0
    search_distance: float | None = 500.0

    def __post_init__(self) -> None:
        """Refuse a direction or a tolerance that cannot describe a spread cone."""
        if not 0.0 <= self.tolerance <= 90.0:
            raise ValueError(
                f"{self.name}: a spread tolerance is at least 0 and at most 90 degrees, and "
                f"{self.tolerance} is not"
            )
        if not math.isfinite(self.bearing):
            raise ValueError(f"{self.name}: a spread bearing is a finite number of degrees")


def bearing_of(source: Point, target: Point) -> float:
    """Return the bearing from one point to another, in degrees clockwise from north.

    Parameters
    ----------
    source : tuple of float
        The ``(x, y)`` start, in metres.
    target : tuple of float
        The ``(x, y)`` end, in metres.

    Returns
    -------
    float
        The bearing in ``[0, 360)``; 0 when the points coincide.
    """
    dx = target[0] - source[0]
    dy = target[1] - source[1]
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return math.degrees(math.atan2(dx, dy)) % 360.0


def angle_between(first: float, second: float) -> float:
    """Return the smallest angle between two bearings, in degrees.

    Parameters
    ----------
    first : float
        A bearing, in degrees.
    second : float
        A bearing, in degrees.

    Returns
    -------
    float
        The angle in ``[0, 180]``.
    """
    difference = abs((first - second) % 360.0)
    return min(difference, 360.0 - difference)


def directed_edges(
    edges: Sequence[tuple[int, int, float]],
    points: Mapping[int, Point],
    account: SpreadAccount,
) -> list[tuple[int, int]]:
    """Return the topology edges oriented downwind, for the edges that transmit at all.

    An edge transmits when it spans no more than the account's search distance and lies within the
    account's tolerance of the spread direction, measured without regard to which end is which. It
    is then oriented from its upwind end to its downwind one; an edge exactly across the bearing has
    no downwind component and is oriented both ways, because a fire does spread sideways.

    Parameters
    ----------
    edges : sequence of (int, int, float)
        The topology edges ``(src, dst, distance_m)``.
    points : mapping of int to tuple of float
        The ``(x, y)`` centroid of each block, in metres.
    account : SpreadAccount
        The account definition: its bearing, tolerance and search distance.

    Returns
    -------
    list of (int, int)
        The directed edges, as ``(upwind, downwind)`` pairs.
    """
    oriented: list[tuple[int, int]] = []
    for source, target, distance in edges:
        if source not in points or target not in points:
            continue
        if account.search_distance is not None and distance > account.search_distance:
            continue
        edge = bearing_of(points[source], points[target])
        if angle_between(edge, account.bearing) > account.tolerance:
            continue
        projection = math.cos(math.radians(edge - account.bearing))
        if projection > 0.0:
            oriented.append((source, target))
        elif projection < 0.0:
            oriented.append((target, source))
        else:
            oriented.append((source, target))
            oriented.append((target, source))
    return oriented


def reachable(start: int, adjacency: Mapping[int, Sequence[int]]) -> set[int]:
    """Return the blocks reachable from one, following directed edges only.

    Parameters
    ----------
    start : int
        The block the fire starts in.
    adjacency : mapping of int to sequence of int
        The downwind neighbours of each block.

    Returns
    -------
    set of int
        The reachable blocks, the start included.
    """
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for other in adjacency.get(node, ()):
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return seen


def spread_account_values(
    account: SpreadAccount,
    values: Mapping[int, float],
    edges: Sequence[tuple[int, int, float]],
    points: Mapping[int, Point],
    block_area: Mapping[int, float],
) -> dict[str, float]:
    """Compute one period's spread-connectivity sub-accounts.

    Parameters
    ----------
    account : SpreadAccount
        The account definition.
    values : mapping of int to float
        The criterion value per block; a block is treated when it exceeds the threshold.
    edges : sequence of (int, int, float)
        The topology edges ``(src, dst, distance_m)``.
    points : mapping of int to tuple of float
        The ``(x, y)`` centroid of each block, in metres, which is where an edge's bearing is read.
    block_area : mapping of int to float
        The area of each block, in hectares.

    Returns
    -------
    dict of str to float
        ``largest_component``, ``percolation_reach`` and ``edge_cut``, keyed by the account name,
        plus ``TOTAL.area`` and ``TOTAL.blocks`` for the untreated set.
    """
    treated = {block for block, value in values.items() if value > account.threshold}
    untreated = [block for block in values if block not in treated]
    adjacency: dict[int, list[int]] = {}
    leaving = 0
    blocked = 0
    for source, target in directed_edges(edges, points, account):
        if source in treated:
            continue
        leaving += 1
        if target in treated:
            blocked += 1
            continue
        adjacency.setdefault(source, []).append(target)
    reaches = [reachable(block, adjacency) for block in untreated]
    areas = [math.fsum(block_area.get(block, 0.0) for block in reach) for reach in reaches]
    largest = max(areas) if areas else 0.0
    mean = math.fsum(areas) / len(areas) if areas else 0.0
    return {
        f"{account.name}.largest_component": largest,
        f"{account.name}.percolation_reach": mean,
        f"{account.name}.edge_cut": (100.0 * blocked / leaving) if leaving else 0.0,
        f"{account.name}.TOTAL.area": math.fsum(block_area.get(block, 0.0) for block in untreated),
        f"{account.name}.TOTAL.blocks": float(len(untreated)),
    }
