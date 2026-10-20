"""Spread connectivity: how fragmented the fuel body a fire could run through is.

The patch-size accounts measure *shape*: how large the connected clusters of a criterion are. A
fuel-treatment pattern can win against fire while making that shape *worse* — on the TSA23 bridge
test a wind-perpendicular barrier burns least of three equal-area patterns and has the largest
large-patch share — because what a barrier does is **break the fuel body a fire spreads through**.
This module measures that property directly.

The topology is an undirected block adjacency (``src_block, dst_block, distance_m``) and carries no
bearings, so the direction comes from the account: a bearing in degrees clockwise from north, the
way a wind direction is stated. Only edges that lie within the account's cone of that bearing
transmit — the *fast* edges, the ones a fire crosses at head or near-head rate. A treated block
transmits nothing, so a band of treated blocks cuts the landscape.

**The compartment is the measure, and the traversal is undirected.** A fire travels on its flanks
and behind it, so it goes *around* an obstacle rather than being stopped dead by it; what confines a
fire is the connected fuel body it can wander through. On the TSA23 bridge instance the largest
compartment over the within-cone edges reproduces the fire model's ranking of the three equal-area
patterns (82,800 / 104,600 / 187,173 ha against 19,640 / 19,870 / 20,298 ha burned), and its
area-weighted mean does too. The fire outcome is escape-dominated — a mean of 393 ha burned per
ignition but a p90 near 38,000 — so compartment size, not the average local run, is what governs it.

A first attempt measured the *directed* reach — the set reachable following downwind edges only —
and it does not survive contact with a real map. Its largest value was a boundary corridor no
treatment touched, so all three patterns read the same 3,390.6 ha, and its mean ranked the barrier
*worst*: a thin barrier only shortens the runs that cross it, while scattered treatment shortens
every run. The full comparison is in the phase notes.

**Direction is in the cone, not in the traversal.** A full-span band lying along the wind fragments
an undirected graph just as much as one across it, and the synthetic oracle pins that: what the
account can say is *how fragmented the fast-edge fuel body is*, not *which way a band runs*.
Separating those needs anisotropic rates and a burn duration, which is a fire model, not an account.

Two sub-accounts, both of which a fire-spread model would want *lower*:

``largest_component``
    The area of the largest connected set of untreated blocks over the within-cone edges: the fuel
    body a fire can wander through from one ignition.
``percolation_reach``
    The area-weighted mean compartment area, ``sum(area**2) / sum(area)``: what a random *hectare*
    sees. The per-block mean is the wrong average on a fragmented map — it is dominated by the many
    isolated blocks, and on the bridge instance it read 9.5 ha for all three patterns.

Both are areas in hectares.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

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
        How far off the bearing an edge may lie and still count as a fast edge, in degrees (default
        60, a cone 60 degrees wide each side of the bearing). At 90 every edge is fast and the cone
        stops selecting; the oracle pins what that does to the measure.
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


def load_spread_accounts(path: Path) -> tuple[SpreadAccount, ...]:
    """Load spread-connectivity account definitions from YAML.

    The file is a mapping with an ``accounts`` list; each entry has ``name``, ``criteria``, and
    any of ``threshold``, ``bearing``, ``tolerance`` and ``search_distance``. A
    ``search_distance`` of ``null`` considers every edge.

    Parameters
    ----------
    path : Path
        The YAML file.

    Returns
    -------
    tuple of SpreadAccount
        The definitions.
    """
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    entries = raw.get("accounts", []) if isinstance(raw, dict) else []
    accounts: list[SpreadAccount] = []
    for entry in entries:
        distance = entry.get("search_distance", 500.0)
        accounts.append(
            SpreadAccount(
                name=str(entry["name"]),
                criteria=str(entry["criteria"]),
                threshold=float(entry.get("threshold", 0.5)),
                bearing=float(entry.get("bearing", 225.0)),
                tolerance=float(entry.get("tolerance", 60.0)),
                search_distance=None if distance is None else float(distance),
            )
        )
    return tuple(accounts)


def load_block_coordinates(path: Path) -> dict[int, Point]:
    """Load block centroids from a CSV, in metres.

    The table carries a block id and an ``x`` and a ``y`` column; the names are matched loosely,
    so a table with ``BLOCK,X,Y`` or ``block_id,easting,northing`` reads the same way.

    Parameters
    ----------
    path : Path
        The CSV file.

    Returns
    -------
    dict of int to tuple of float
        The ``(x, y)`` centroid per block.

    Raises
    ------
    ValueError
        When the table has no block id, ``x`` or ``y`` column.
    """
    import pandas as pd

    frame = pd.read_csv(path)
    lowered = {str(column).strip().lower(): column for column in frame.columns}

    def pick(*names: str) -> str | None:
        return next((lowered[name] for name in names if name in lowered), None)

    block = pick("block", "block_id", "src_block", "id")
    east = pick("x", "easting", "east", "centroid_x", "xc")
    north = pick("y", "northing", "north", "centroid_y", "yc")
    if block is None or east is None or north is None:
        raise ValueError(
            f"{Path(path).name} needs a block id, an x and a y column, and has "
            f"{list(frame.columns)}"
        )
    return {
        int(one_block): (float(one_x), float(one_y))
        for one_block, one_x, one_y in zip(frame[block], frame[east], frame[north], strict=True)
    }


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


def transmitting_edges(
    edges: Sequence[tuple[int, int, float]],
    points: Mapping[int, Point],
    account: SpreadAccount,
) -> list[tuple[int, int]]:
    """Return the topology edges inside the spread cone, as undirected pairs.

    An edge transmits when it spans no more than the account's search distance and lies within the
    account's tolerance of the spread direction, measured without regard to which end is which. The
    direction selects whether an edge is *fast*; the traversal over the selected edges is
    undirected, because a fire goes around an obstacle as well as through it.

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
        The transmitting edges, as ``(src, dst)`` pairs in their input order.
    """
    selected: list[tuple[int, int]] = []
    for source, target, distance in edges:
        if source not in points or target not in points:
            continue
        if account.search_distance is not None and distance > account.search_distance:
            continue
        edge = bearing_of(points[source], points[target])
        if angle_between(edge, account.bearing) > account.tolerance:
            continue
        selected.append((source, target))
    return selected


def compartment_class(area: float) -> str:
    """Return the size class of a spread compartment, in hectares.

    Parameters
    ----------
    area : float
        The compartment area.

    Returns
    -------
    str
        ``0_10``, ``10_50``, ``50_150`` or ``150_9999999``.
    """
    if area <= 10.0:
        return "0_10"
    if area <= 50.0:
        return "10_50"
    if area <= 150.0:
        return "50_150"
    return "150_9999999"


def spread_account_values(
    account: SpreadAccount,
    values: Mapping[int, float],
    edges: Sequence[tuple[int, int, float]],
    points: Mapping[int, Point],
    block_area: Mapping[int, float],
    membership: list[dict[str, object]] | None = None,
) -> dict[str, float]:
    """Compute one period's spread-connectivity sub-accounts.

    Parameters
    ----------
    account : SpreadAccount
        The account definition.
    values : mapping of int to float
        The criterion value per block; a block is treated when it exceeds the threshold. A block
        absent from the mapping has no criterion value and is untreated — which matters for a
        *product* criterion, where only the blocks that produced in the period appear.
    edges : sequence of (int, int, float)
        The topology edges ``(src, dst, distance_m)``.
    points : mapping of int to tuple of float
        The ``(x, y)`` centroid of each block, in metres, which is where an edge's bearing is read.
    block_area : mapping of int to float
        The area of each block, in hectares.
    membership : list of dict or None, optional
        When given, receives one row per untreated block: the account, compartment index,
        compartment class and area, block, and block area. The largest compartment is index 0.

    Returns
    -------
    dict of str to float
        ``largest_component`` and ``percolation_reach``, keyed by the account name, plus
        ``TOTAL.area`` and ``TOTAL.blocks`` for the untreated set.
    """
    # the landscape is every block the bearing can be read for, not only the blocks the criterion
    # happens to mention: a product criterion names the blocks that produced this period, and every
    # other block is untreated fuel
    if not points:
        return {
            f"{account.name}.largest_component": 0.0,
            f"{account.name}.percolation_reach": 0.0,
            f"{account.name}.TOTAL.area": 0.0,
            f"{account.name}.TOTAL.blocks": 0.0,
        }
    treated = {block for block in points if values.get(block, 0.0) > account.threshold}
    untreated = [block for block in points if block not in treated]
    adjacency: dict[int, list[int]] = {}
    for source, target in transmitting_edges(edges, points, account):
        if source in treated or target in treated:
            continue
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, []).append(source)
    remaining = set(untreated)
    components: list[tuple[list[int], float]] = []
    while remaining:
        start = remaining.pop()
        blocks = [start]
        area = block_area.get(start, 0.0)
        stack = [start]
        while stack:
            node = stack.pop()
            for other in adjacency.get(node, ()):
                if other in remaining:
                    remaining.remove(other)
                    area += block_area.get(other, 0.0)
                    blocks.append(other)
                    stack.append(other)
        components.append((blocks, area))
    components.sort(key=lambda component: (-component[1], min(component[0])))
    areas = [area for _, area in components]
    largest = max(areas) if areas else 0.0
    total = math.fsum(areas)
    weighted = math.fsum(area * area for area in areas) / total if total else 0.0
    if membership is not None:
        for index, (blocks, area) in enumerate(components):
            label = compartment_class(area)
            for block in blocks:
                membership.append(
                    {
                        "account": account.name,
                        "compartment": index,
                        "compartment_area_ha": area,
                        "compartment_class": label,
                        "block": block,
                        "area_ha": block_area.get(block, 0.0),
                    }
                )
    return {
        f"{account.name}.largest_component": largest,
        f"{account.name}.percolation_reach": weighted,
        f"{account.name}.TOTAL.area": total,
        f"{account.name}.TOTAL.blocks": float(len(untreated)),
    }
