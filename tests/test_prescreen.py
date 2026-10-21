"""Tests for the cheap feature-goal screen."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from ws4.opt.objective import Target
from ws4.opt.prescreen import feature_goal_blocks


def _dataset(root: Path) -> Path:
    """Write the small tables the screen reads."""
    pd.DataFrame(
        {
            "block_id": [1, 2],
            "track_id": [10, 20],
            "offset": [5.0, 5.0],
            "area_ha": [10.0, 10.0],
        }
    ).to_parquet(root / "blocks.parquet", index=False)
    pd.DataFrame(
        {
            "track_id": [10, 10, 20, 20],
            "begin": [0.0, 0.0, 0.0, 0.0],
            "end": [10.0, 10.0, 10.0, 10.0],
            "treatment": ["FT", "FB", "FT", "FB"],
            "new_track": [30, 31, 40, 41],
        }
    ).to_parquet(root / "treatments.parquet", index=False)
    pd.DataFrame(
        {
            "track_id": [10, 20, 30, 40],
            "label": ["feature.Hazard"] * 4,
            "curve_id": [1, 2, 1, 2],
        }
    ).to_parquet(root / "features.parquet", index=False)
    pd.DataFrame(
        {
            "curve_id": [1, 1, 2, 2, 3],
            "x": [0.0, 10.0, 0.0, 10.0, 0.0],
            "y": [1.0, 0.2, 1.0, 0.5, 100.0],
        }
    ).to_parquet(root / "curves.parquet", index=False)
    pd.DataFrame(
        {
            "track_id": [10, 20],
            "treatment": ["FT", "FT"],
            "label": ["product.Cost", "product.Cost"],
            "curve_id": [3, 3],
        }
    ).to_parquet(root / "products.parquet", index=False)
    return root


def test_the_screen_ranks_cost_per_unit_of_reduction(tmp_path: Path) -> None:
    """The cheaper block per hazard-ha is the one the exact seed should price first."""
    root = _dataset(tmp_path)
    targets = [
        Target("feature.Hazard", 10, maximum=0.0),
        Target("product.Cost", 10, maximum=1000.0),
    ]
    blocks = feature_goal_blocks(root, "feature.Hazard", targets, 10, limit=1)
    assert blocks == {1}


def test_the_screen_returns_none_when_it_does_not_apply(tmp_path: Path) -> None:
    """A non-feature goal or a directory without the tables falls back to the full candidate set."""
    assert feature_goal_blocks(tmp_path, "product.Cost", [], 0) is None
    root = _dataset(tmp_path)
    assert feature_goal_blocks(root, "feature.Missing", [], 10) is None
