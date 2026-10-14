"""Road network tables: access, haul cost, destinations, and routing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_route_tables(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load vertices.csv, segments.csv, destinations.csv, linkages.csv.

    Returns (vertices, segments, destinations, linkages).
    """
    verts = pd.read_csv(root / "vertices.csv")
    segs = pd.read_csv(root / "segments.csv")
    dests = pd.read_csv(root / "destinations.csv")
    links = pd.read_csv(root / "linkages.csv")
    return verts, segs, dests, links
