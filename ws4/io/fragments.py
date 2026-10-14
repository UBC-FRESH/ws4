"""Read a fragment inventory from a shapefile, CSV, or Parquet.

A shapefile carries the fragment attributes and geometry. The matrix builder needs the
attributes (block, area, age, and the state variables); the geometry is kept separately
for spatial work. The geospatial dependency is imported lazily, so the core package does
not require it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_VECTOR_SUFFIXES = {".shp", ".geojson", ".gpkg"}
_TABLE_SUFFIXES = {".csv", ".txt", ".parquet", ".pq"}


def read_fragments(path: Path) -> pd.DataFrame:
    """Read a fragment inventory's attributes.

    Parameters
    ----------
    path : Path
        A shapefile (``.shp``), GeoJSON, GeoPackage, CSV, or Parquet file.

    Returns
    -------
    pandas.DataFrame
        The fragment attributes, without geometry.

    Raises
    ------
    ValueError
        When the file format is not supported.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in _VECTOR_SUFFIXES:
        import geopandas  # imported lazily; requires the geo extra

        frame = geopandas.read_file(path)
        if "geometry" in frame.columns:
            frame = frame.drop(columns="geometry")
        return pd.DataFrame(frame)
    raise ValueError(f"unsupported fragment inventory format: {path.suffix}")


def read_geometry(path: Path) -> object:
    """Read a fragment inventory's geometry.

    Parameters
    ----------
    path : Path
        A shapefile, GeoJSON, or GeoPackage file.

    Returns
    -------
    geopandas.GeoDataFrame
        The fragments with geometry.

    Raises
    ------
    ValueError
        When the file format is not a vector format.
    """
    path = Path(path)
    if path.suffix.lower() not in _VECTOR_SUFFIXES:
        raise ValueError(f"not a vector format: {path.suffix}")
    import geopandas

    return geopandas.read_file(path)
