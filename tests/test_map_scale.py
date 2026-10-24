"""The map scale benchmark's grid and smoke path."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark_map_scale import generate_grid, run_benchmark


def test_generate_grid_writes_the_requested_count(tmp_path: Path) -> None:
    """The grid writer stops at the requested feature count."""
    path = tmp_path / "geometry.geojson"
    written = generate_grid(50, path, west=0.0, south=0.0, east=1.0, north=1.0)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert written == 50
    assert len(document["features"]) == 50
    assert document["features"][0]["properties"]["block_id"] == 0
    assert document["features"][-1]["properties"]["block_id"] == 49


def test_scale_benchmark_smoke(tmp_path: Path) -> None:
    """A small synthetic geometry returns positive tile sizes and cache headers."""
    result = run_benchmark(200, workdir=tmp_path)
    assert result["fragments"] == 200
    assert int(result["z0_bytes"]) > 0
    assert int(result["z12_bytes"]) >= 0
    assert result["z0_cache"] == "miss"
    assert result["warm_cache"] in {"memory", "disk"}
