"""Build the TSA24 block GeoJSON from the source stand shapefile.

The compiled WS4 dataset does not store polygons. This script assigns
``block_id`` from the source record order and preserves the source CRS.
Run it from the instance root after materialising the source shapefile:

    python scripts/build_tsa24_geometry.py \
        --source /path/to/tsa24.shp/stands.shp \
        --output runtime/geometry/tsa24-blocks.geojson
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


def main() -> None:
    """Build the block GeoJSON from the source stand shapefile."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--simplify", type=float, default=5.0)
    parser.add_argument("--crs", default="EPSG:3005")
    args = parser.parse_args()

    frame = gpd.read_file(args.source).to_crs(args.crs)
    frame["block_id"] = pd.Series(range(1, len(frame) + 1), dtype="int64")
    frame["area_ha"] = pd.to_numeric(frame["area"], errors="coerce").round(1)
    frame["age"] = pd.to_numeric(frame["age"], errors="coerce").fillna(0).astype(int)
    frame["au"] = pd.to_numeric(frame["theme2"], errors="coerce").fillna(0).astype(int)
    frame = frame[["block_id", "area_ha", "age", "au", "geometry"]]
    frame["geometry"] = frame.geometry.simplify(args.simplify, preserve_topology=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(args.output, driver="GeoJSON")
    print(f"wrote {args.output} features={len(frame)} bytes={args.output.stat().st_size}")


if __name__ == "__main__":
    main()
