"""Block adjacency topology for patch metrics and spatial constraints."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_block_topology(csv_path: Path) -> pd.DataFrame:
    """Load a proximal topology edgelist: src_block,dst_block,distance_m (undirected)."""
    df = pd.read_csv(csv_path)
    return df
