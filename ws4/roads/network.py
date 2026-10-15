"""Road network routing: access, route length, haul cost, and route accounts.

The network is four tables (the established route model; see the Patchworks Route Model
concepts in ``notes/design/ws4-matrix-builder-and-interop.md``):

- ``vertices``: ``vertex_id`` (a road junction).
- ``segments``: ``segment_id``, ``from_vertex``, ``to_vertex``, ``length_m``, ``haul_cost``,
  ``build_cost``, ``maintain_cost`` (an undirected edge between two vertices).
- ``destinations``: ``name`` (the destination account, for example ``destination.MILL1``)
  and ``vertex_id`` (the vertex it is attached to). Several destinations may share a
  vertex.
- ``linkages``: ``block_id``, ``vertex_id``. Each block is assigned to **exactly one**
  vertex, so the linkage is a one-to-one map from block to network node.

Route length and cost are the shortest path over the segment graph. A destination is
identified by its **account name**, not by its vertex: the sample route model attaches
more than one mill to the same vertex, and the account name is the identity the route
tables and reports use.

The legacy column names of the established format are accepted: ``SEGMENT``, ``FNODE``,
``TNODE``, ``LENGTH``, ``HAUL``, ``BUILD``, ``MAINTAIN``, ``NODE``, ``ACCOUNT``, ``BLOCK``.
"""

from __future__ import annotations

import csv
import heapq
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

_HAUL = "haul"
_LENGTH = "length"


@dataclass(frozen=True)
class Segment:
    """One road segment.

    Attributes
    ----------
    segment_id : int
        The segment identity.
    from_vertex, to_vertex : int
        The vertices at each end.
    length_m : float
        The segment length, in metres.
    haul_cost : float
        The haul cost per unit of volume over this segment.
    build_cost : float
        The cost to build this segment, charged once when it is first used.
    maintain_cost : float
        The maintenance cost, charged each period the segment is used.
    """

    segment_id: int
    from_vertex: int
    to_vertex: int
    length_m: float
    haul_cost: float
    build_cost: float
    maintain_cost: float


@dataclass(frozen=True)
class Destination:
    """A destination (mill) account attached to a network vertex.

    Attributes
    ----------
    name : str
        The destination account name, such as ``destination.MILL1``.
    vertex : int
        The vertex the destination is attached to.
    """

    name: str
    vertex: int


@dataclass(frozen=True)
class Route:
    """A route from a block to a destination.

    Attributes
    ----------
    destination : str
        The destination account name.
    segment_ids : tuple of int
        The segment ids along the route, from the block to the destination.
    length_m : float
        The total route length, in metres.
    haul_cost : float
        The total haul cost per unit of volume over the route.
    build_cost : float
        The total build cost of the segments along the route.
    maintain_cost : float
        The total maintenance cost of the segments along the route.
    """

    destination: str
    segment_ids: tuple[int, ...]
    length_m: float
    haul_cost: float
    build_cost: float
    maintain_cost: float


def _as_int(value: object) -> int:
    """Convert a pandas scalar to an int."""
    return int(float(str(value)))


def _as_float(value: object) -> float:
    """Convert a pandas scalar to a float."""
    if value is None:
        return 0.0
    text = str(value)
    if text == "" or text.lower() == "nan":
        return 0.0
    return float(text)


def _get(row: object, *names: str, default: object = None) -> object:
    """Return the first named attribute present on a row, else ``default``."""
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    if default is not None:
        return default
    raise KeyError(f"none of {names} on the row")


def load_route_tables(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load ``vertices.csv``, ``segments.csv``, ``destinations.csv``, ``linkages.csv``.

    Parameters
    ----------
    root : Path
        Directory holding the four CSV files.

    Returns
    -------
    tuple of pandas.DataFrame
        ``(vertices, segments, destinations, linkages)``.
    """
    vertices = pd.read_csv(root / "vertices.csv")
    segments = pd.read_csv(root / "segments.csv")
    destinations = pd.read_csv(root / "destinations.csv")
    linkages = pd.read_csv(root / "linkages.csv")
    return vertices, segments, destinations, linkages


def load_route_eligibility(path: Path) -> dict[str, tuple[str, ...]]:
    """Load a product-to-destination eligibility table.

    The table has a ``product`` column and a ``destination`` column; a product may name
    more than one destination. The result maps each product label to the destinations
    that may receive it.

    Parameters
    ----------
    path : Path
        The eligibility CSV, with ``product,destination`` columns.

    Returns
    -------
    dict of str to tuple of str
        The eligible destinations per product label.
    """
    eligible: dict[str, list[str]] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            product = (row.get("product") or "").strip()
            destination = (row.get("destination") or "").strip()
            if product and destination:
                eligible.setdefault(product, []).append(destination)
    return {product: tuple(names) for product, names in eligible.items()}


@dataclass
class RouteNetwork:
    """A road network with least-cost routing between blocks and destinations.

    Attributes
    ----------
    segments : tuple of Segment
        The road segments.
    destinations : tuple of Destination
        The destinations, identified by account name.
    block_vertex : mapping of int to int
        The single vertex each block is assigned to.
    """

    segments: tuple[Segment, ...]
    destinations: tuple[Destination, ...]
    block_vertex: Mapping[int, int]
    _distance_cache: dict[tuple[int, str], dict[int, float]] = field(
        default_factory=dict, compare=False, repr=False
    )
    _previous_cache: dict[tuple[int, str], dict[int, tuple[int, int]]] = field(
        default_factory=dict, compare=False, repr=False
    )

    @classmethod
    def from_tables(
        cls,
        segments: pd.DataFrame,
        destinations: pd.DataFrame,
        linkages: pd.DataFrame,
    ) -> RouteNetwork:
        """Build a network from the segments, destinations, and linkages tables.

        Parameters
        ----------
        segments : pandas.DataFrame
            The segment table. Legacy ``FNODE``/``TNODE``/``LENGTH``/``HAUL``/``BUILD``/
            ``MAINTAIN`` and WS4 names are both accepted.
        destinations : pandas.DataFrame
            The destination table. The destination name comes from ``ACCOUNT`` /
            ``destination`` / ``name`` / ``dest_id``; the vertex from ``NODE`` /
            ``vertex_id``.
        linkages : pandas.DataFrame
            The block-to-vertex table (``BLOCK``/``block_id``, ``NODE``/``vertex_id``).

        Returns
        -------
        RouteNetwork
            The assembled network.
        """
        built: list[Segment] = []
        for index, row in enumerate(segments.itertuples(index=False)):
            built.append(
                Segment(
                    segment_id=_as_int(_get(row, "segment_id", "SEGMENT", default=index)),
                    from_vertex=_as_int(_get(row, "from_vertex", "FNODE")),
                    to_vertex=_as_int(_get(row, "to_vertex", "TNODE")),
                    length_m=_as_float(_get(row, "length_m", "LENGTH", default=0.0)),
                    haul_cost=_as_float(_get(row, "haul_cost", "cost", "HAUL", default=0.0)),
                    build_cost=_as_float(_get(row, "build_cost", "BUILD", default=0.0)),
                    maintain_cost=_as_float(_get(row, "maintain_cost", "MAINTAIN", default=0.0)),
                )
            )
        built_destinations: list[Destination] = []
        for row in destinations.itertuples(index=False):
            built_destinations.append(
                Destination(
                    name=str(_get(row, "name", "destination", "dest_id", "ACCOUNT")),
                    vertex=_as_int(_get(row, "vertex_id", "NODE", default=0)),
                )
            )
        block_vertex = {
            _as_int(_get(row, "block_id", "BLOCK")): _as_int(_get(row, "vertex_id", "NODE"))
            for row in linkages.itertuples(index=False)
        }
        return cls(
            segments=tuple(built),
            destinations=tuple(built_destinations),
            block_vertex=block_vertex,
        )

    def destination_names(self) -> tuple[str, ...]:
        """Return the destination account names, in table order."""
        return tuple(destination.name for destination in self.destinations)

    def _segments_by_id(self) -> dict[int, Segment]:
        """Return the segments keyed by id."""
        return {segment.segment_id: segment for segment in self.segments}

    def _adjacency(self) -> dict[int, list[int]]:
        """Return an adjacency map: vertex to the segment ids that touch it."""
        adjacency: dict[int, list[int]] = {}
        for segment in self.segments:
            adjacency.setdefault(segment.from_vertex, []).append(segment.segment_id)
            adjacency.setdefault(segment.to_vertex, []).append(segment.segment_id)
        return adjacency

    def _weight(self, segment: Segment, weight: str) -> float:
        """Return a segment's traversal weight for ``length`` or ``haul``."""
        return segment.length_m if weight == _LENGTH else segment.haul_cost

    def _shortest(
        self, source: int, weight: str
    ) -> tuple[dict[int, float], dict[int, tuple[int, int]]]:
        """Return shortest distances and predecessors from a source.

        Parameters
        ----------
        source : int
            The source vertex.
        weight : {"length", "haul"}
            The traversal weight.

        Returns
        -------
        tuple of (dict, dict)
            The distance to each reachable vertex, and, for each vertex, the incoming
            ``(previous_vertex, segment_id)``.
        """
        cached = self._distance_cache.get((source, weight))
        if cached is not None:
            return cached, self._previous_cache[(source, weight)]
        by_id = self._segments_by_id()
        adjacency = self._adjacency()
        distances: dict[int, float] = {source: 0.0}
        previous: dict[int, tuple[int, int]] = {}
        queue: list[tuple[float, int]] = [(0.0, source)]
        while queue:
            distance, node = heapq.heappop(queue)
            if distance > distances.get(node, float("inf")):
                continue
            for segment_id in adjacency.get(node, []):
                segment = by_id[segment_id]
                neighbour = (
                    segment.to_vertex if segment.from_vertex == node else segment.from_vertex
                )
                candidate = distance + self._weight(segment, weight)
                if candidate < distances.get(neighbour, float("inf")):
                    distances[neighbour] = candidate
                    previous[neighbour] = (node, segment_id)
                    heapq.heappush(queue, (candidate, neighbour))
        self._distance_cache[(source, weight)] = distances
        self._previous_cache[(source, weight)] = previous
        return distances, previous

    def _destination(self, name: str) -> Destination | None:
        """Return a destination by name, or None."""
        for destination in self.destinations:
            if destination.name == name:
                return destination
        return None

    def route(self, block_id: int, destination: str) -> Route | None:
        """Return the least-haul-cost route from a block to a destination.

        Parameters
        ----------
        block_id : int
            The block.
        destination : str
            The destination account name.

        Returns
        -------
        Route or None
            The route, or None when the block or destination is not linked, or no path
            exists.
        """
        target = self._destination(destination)
        source = self.block_vertex.get(block_id)
        if target is None or source is None:
            return None
        distances, previous = self._shortest(source, _HAUL)
        if target.vertex not in distances:
            return None
        segment_ids: list[int] = []
        node = target.vertex
        while node != source and node in previous:
            node, segment_id = previous[node]
            segment_ids.append(segment_id)
        segment_ids.reverse()
        by_id = self._segments_by_id()
        chosen = [by_id[segment_id] for segment_id in segment_ids]
        return Route(
            destination=destination,
            segment_ids=tuple(segment_ids),
            length_m=sum(segment.length_m for segment in chosen),
            haul_cost=sum(segment.haul_cost for segment in chosen),
            build_cost=sum(segment.build_cost for segment in chosen),
            maintain_cost=sum(segment.maintain_cost for segment in chosen),
        )

    def route_length(self, block_id: int, destination: str) -> float | None:
        """Return the shortest route length (metres) from a block to a destination.

        Parameters
        ----------
        block_id : int
            The block.
        destination : str
            The destination account name.

        Returns
        -------
        float or None
            The route length, or None when the block or destination is not linked.
        """
        target = self._destination(destination)
        source = self.block_vertex.get(block_id)
        if target is None or source is None:
            return None
        distances, _ = self._shortest(source, _LENGTH)
        return distances.get(target.vertex)

    def route_cost(self, block_id: int, destination: str) -> float | None:
        """Return the shortest haul cost from a block to a destination.

        Parameters
        ----------
        block_id : int
            The block.
        destination : str
            The destination account name.

        Returns
        -------
        float or None
            The haul cost, or None when the block or destination is not linked.
        """
        target = self._destination(destination)
        source = self.block_vertex.get(block_id)
        if target is None or source is None:
            return None
        distances, _ = self._shortest(source, _HAUL)
        return distances.get(target.vertex)

    def nearest_destination(
        self, block_id: int, eligible: Iterable[str] | None = None
    ) -> tuple[str, float] | None:
        """Return the least-haul-cost destination for a block, or None.

        Parameters
        ----------
        block_id : int
            The block.
        eligible : iterable of str, optional
            The destination names the block's product may be sent to. When omitted, every
            destination is eligible.

        Returns
        -------
        tuple of (str, float) or None
            The destination account name and route length, or None when no eligible
            destination is reachable.
        """
        allowed = None if eligible is None else set(eligible)
        best: tuple[str, float] | None = None
        best_cost = float("inf")
        for destination in self.destinations:
            if allowed is not None and destination.name not in allowed:
                continue
            cost = self.route_cost(block_id, destination.name)
            if cost is None or cost >= best_cost:
                continue
            length = self.route_length(block_id, destination.name)
            best = (destination.name, length if length is not None else 0.0)
            best_cost = cost
        return best


def destination_eligibility(products: pd.DataFrame, dest_id: str) -> Sequence[str]:
    """Return the product labels a destination may receive.

    Parameters
    ----------
    products : pandas.DataFrame
        The product table. When it carries a ``destination`` column, a product is
        eligible for the destination named in that column.
    dest_id : str
        The destination account name.

    Returns
    -------
    sequence of str
        The eligible product labels. Empty when the table has no ``destination`` column.
    """
    if "destination" not in products.columns:
        return ()
    mask = products["destination"].astype(str) == str(dest_id)
    return tuple(products.loc[mask, "label"].astype(str).unique())
