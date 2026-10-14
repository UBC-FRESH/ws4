"""Road network routing: access, route length, and haul cost.

The network is four tables:

- ``vertices``: ``vertex_id`` (a road junction).
- ``segments``: ``from_vertex``, ``to_vertex``, ``length_m``, ``cost`` (an undirected
  edge between two vertices).
- ``destinations``: ``dest_id``, ``vertex_id`` (a mill attached to a vertex).
- ``linkages``: ``block_id``, ``vertex_id``. Each block is assigned to **exactly one**
  vertex, so the linkage is a one-to-one map from block to network node.

Route length and cost are the shortest path over the segment graph.
"""

from __future__ import annotations

import heapq
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

Edge = tuple[int, int, float, float]


def _as_int(value: object) -> int:
    """Convert a pandas scalar to an int."""
    return int(float(str(value)))


def _as_float(value: object) -> float:
    """Convert a pandas scalar to a float."""
    return float(str(value))


def _get(row: object, *names: str) -> object:
    """Return the first named attribute present on a row."""
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
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


@dataclass(frozen=True)
class RouteNetwork:
    """A road network with shortest-path routing.

    Attributes
    ----------
    edges : tuple of Edge
        ``(from_vertex, to_vertex, length_m, cost)``.
    block_vertex : dict of int to int
        The single vertex each block is assigned to.
    destination_vertex : dict of int to int
        The vertex each destination is attached to.
    """

    edges: tuple[Edge, ...]
    block_vertex: Mapping[int, int]
    destination_vertex: Mapping[int, int]

    @classmethod
    def from_tables(
        cls,
        segments: pd.DataFrame,
        destinations: pd.DataFrame,
        linkages: pd.DataFrame,
    ) -> RouteNetwork:
        """Build a network from the segments, destinations, and linkages tables."""
        edges = tuple(
            (
                _as_int(_get(row, "from_vertex", "FNODE")),
                _as_int(_get(row, "to_vertex", "TNODE")),
                _as_float(_get(row, "length_m", "LENGTH")),
                _as_float(_get(row, "cost", "HAUL") or 0.0),
            )
            for row in segments.itertuples(index=False)
        )
        block_vertex = {
            _as_int(_get(row, "block_id", "BLOCK")): _as_int(_get(row, "vertex_id", "NODE"))
            for row in linkages.itertuples(index=False)
        }
        destination_vertex = {
            _as_int(_get(row, "dest_id", "NODE")): _as_int(_get(row, "vertex_id", "NODE"))
            for row in destinations.itertuples(index=False)
        }
        return cls(edges=edges, block_vertex=block_vertex, destination_vertex=destination_vertex)

    def _adjacency(self) -> dict[int, list[tuple[int, float, float]]]:
        """Return an adjacency map: vertex to (neighbour, length, cost)."""
        adjacency: dict[int, list[tuple[int, float, float]]] = {}
        for u, v, length, cost in self.edges:
            adjacency.setdefault(u, []).append((v, length, cost))
            adjacency.setdefault(v, []).append((u, length, cost))
        return adjacency

    def _shortest(self, source: int, weight: str) -> dict[int, float]:
        """Return the shortest distance from a source by ``length`` or ``cost``."""
        index = 1 if weight == "length" else 2
        adjacency = self._adjacency()
        distances: dict[int, float] = {source: 0.0}
        queue: list[tuple[float, int]] = [(0.0, source)]
        while queue:
            distance, node = heapq.heappop(queue)
            if distance > distances.get(node, float("inf")):
                continue
            for neighbour in adjacency.get(node, []):
                candidate = distance + neighbour[index]
                if candidate < distances.get(neighbour[0], float("inf")):
                    distances[neighbour[0]] = candidate
                    heapq.heappush(queue, (candidate, neighbour[0]))
        return distances

    def route_length(self, block_id: int, dest_id: int) -> float | None:
        """Return the shortest route length (metres) from a block to a destination.

        Parameters
        ----------
        block_id : int
            The block.
        dest_id : int
            The destination.

        Returns
        -------
        float or None
            The route length, or None when the block or destination is not linked.
        """
        return self._route(block_id, dest_id, "length")

    def route_cost(self, block_id: int, dest_id: int) -> float | None:
        """Return the shortest route cost from a block to a destination."""
        return self._route(block_id, dest_id, "cost")

    def _route(self, block_id: int, dest_id: int, weight: str) -> float | None:
        """Return the shortest length or cost from a block to a destination."""
        source = self.block_vertex.get(block_id)
        target = self.destination_vertex.get(dest_id)
        if source is None or target is None:
            return None
        distances = self._shortest(source, weight)
        return distances.get(target)

    def nearest_destination(self, block_id: int) -> tuple[int, float] | None:
        """Return the nearest destination and route length for a block, or None."""
        best: tuple[int, float] | None = None
        for dest_id in self.destination_vertex:
            length = self.route_length(block_id, dest_id)
            if length is not None and (best is None or length < best[1]):
                best = (dest_id, length)
        return best


def destination_eligibility(products: pd.DataFrame, dest_id: int) -> Sequence[str]:
    """Return the product labels a destination may receive (placeholder).

    A destination-eligibility column is not yet in the product table; this returns an
    empty sequence until that contract is added.
    """
    del products, dest_id
    return ()
