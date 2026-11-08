"""Adapt a Nemora tree table to the WS4 scene tree contract.

Nemora is an external synthetic-stand generator. WS4 reads its exported tree table, joins
each tree to a real VRI polygon, and builds the ``ws4.tree.inventory.v1`` inventory. Nemora
is never imported at runtime; the adapter is a thin file boundary.

The tree layer is synthetic. The polygons and their attributes are the real input. Every
scene manifest records the adapter version, Nemora version, seed, polygon source, and CRS.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pandas as pd
from shapely.geometry import Point, Polygon, shape

from .trees import TREE_COLUMNS, Tree, TreeInventory

NEMORA_ADAPTER_VERSION: Final[str] = "ws4.nemora.adapter.v1"
DEFAULT_SURFACE_FUEL_T_HA: Final[float] = 10.0


class NemoraAdapterError(ValueError):
    """Raised when a Nemora table or VRI polygon layer cannot be adapted."""


@dataclass(frozen=True)
class VriFragment:
    """One real VRI polygon and its fragment attributes.

    Parameters
    ----------
    fragment_id : int
        WS4 fragment id.
    ring : tuple of (float, float)
        Exterior ring in scene coordinates.
    area_ha : float
        Polygon area in hectares.
    properties : dict
        Source attributes retained for provenance.
    """

    fragment_id: int
    ring: tuple[tuple[float, float], ...]
    area_ha: float
    properties: dict[str, object] = field(default_factory=dict)


def load_vri_polygons(
    path: str | Path,
    *,
    fragment_field: str = "fragment_id",
    area_field: str = "area_ha",
) -> dict[int, VriFragment]:
    """Load VRI polygons from a GeoJSON FeatureCollection.

    Parameters
    ----------
    path : str or Path
        GeoJSON file. Polygon and MultiPolygon features are accepted; a MultiPolygon uses
        its largest part.
    fragment_field : str, optional
        Property that carries the fragment id (default ``fragment_id``).
    area_field : str, optional
        Property that carries the area in hectares (default ``area_ha``). When absent, the
        polygon area is used in the layer's coordinate units.

    Returns
    -------
    dict of int to VriFragment
        The polygons keyed by fragment id.

    Raises
    ------
    NemoraAdapterError
        If the file, geometry, id, or area is invalid.
    """
    source = Path(path)
    if not source.is_file():
        raise NemoraAdapterError(f"VRI polygon layer does not exist: {source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise NemoraAdapterError("VRI layer must be a GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise NemoraAdapterError("VRI layer has no features")
    polygons: dict[int, VriFragment] = {}
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            continue
        fragment_value = properties.get(fragment_field, properties.get("block_id"))
        if fragment_value is None:
            raise NemoraAdapterError(f"VRI feature has no {fragment_field!r} property")
        fragment_id = int(str(fragment_value))
        if fragment_id in polygons:
            raise NemoraAdapterError(f"duplicate VRI fragment id: {fragment_id}")
        geom = shape(geometry)
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda item: item.area)
        if geom.geom_type != "Polygon" or geom.is_empty:
            raise NemoraAdapterError(f"VRI fragment {fragment_id} is not a Polygon")
        ring = tuple((float(x), float(y)) for x, y in list(geom.exterior.coords)[:-1])
        if len(ring) < 3:
            raise NemoraAdapterError(f"VRI fragment {fragment_id} has a degenerate ring")
        raw_area = properties.get(area_field)
        area_ha = float(str(raw_area)) if raw_area is not None else float(geom.area) / 10_000.0
        if not math.isfinite(area_ha) or area_ha <= 0.0:
            raise NemoraAdapterError(f"VRI fragment {fragment_id} has an invalid area")
        polygons[fragment_id] = VriFragment(
            fragment_id=fragment_id,
            ring=ring,
            area_ha=area_ha,
            properties={str(key): value for key, value in properties.items()},
        )
    if not polygons:
        raise NemoraAdapterError("VRI layer has no usable polygons")
    return polygons


def load_nemora_tree_table(
    path: str | Path,
    *,
    column_map: Mapping[str, str] | None = None,
    nemora_version: str = "unknown",
    surface_fuel_t_ha: float = DEFAULT_SURFACE_FUEL_T_HA,
) -> pd.DataFrame:
    """Load a Nemora tree table and normalize it to the scene columns.

    Parameters
    ----------
    path : str or Path
        CSV or Parquet tree table.
    column_map : mapping of str to str, optional
        Extra source-to-contract column aliases.
    nemora_version : str, optional
        Nemora version to record in the tree provenance.
    surface_fuel_t_ha : float, optional
        Surface fuel assigned when the table has no surface-fuel column (default 10).

    Returns
    -------
    pandas.DataFrame
        A table with the ``ws4.tree.inventory.v1`` columns.

    Raises
    ------
    NemoraAdapterError
        If the table is missing required columns or has invalid values.
    """
    source = Path(path)
    if not source.is_file():
        raise NemoraAdapterError(f"Nemora tree table does not exist: {source}")
    frame = pd.read_parquet(source) if source.suffix.lower() == ".parquet" else pd.read_csv(source)
    aliases = {
        "dbh": "dbh_cm",
        "height": "height_m",
        "crown": "crown_ratio",
        "crown_radius": "crown_radius_m",
        "crown_fuel": "crown_fuel_t",
        "surface_fuel": "surface_fuel_t_ha",
        "snag": "snag_t",
        "biomass": "biomass_t",
        "biomass_tonnes": "biomass_t",
    }
    if column_map:
        aliases.update({str(key): str(value) for key, value in column_map.items()})
    frame = frame.rename(columns={key: value for key, value in aliases.items() if key in frame})
    required = ("x", "y", "dbh_cm", "height_m")
    missing = [name for name in required if name not in frame]
    if missing:
        raise NemoraAdapterError(f"Nemora tree table is missing columns: {', '.join(missing)}")
    if "species" not in frame:
        frame["species"] = "UNK"
    if "z" not in frame:
        frame["z"] = 0.0
    if "crown_ratio" not in frame:
        frame["crown_ratio"] = 0.45
    if "crown_radius_m" not in frame:
        frame["crown_radius_m"] = 0.12 * frame["height_m"].astype(float)
    if "live" not in frame:
        frame["live"] = True
    if "decay_class" not in frame:
        frame["decay_class"] = 0
    if "crown_fuel_t" not in frame:
        if "biomass_t" in frame:
            frame["crown_fuel_t"] = 0.2 * frame["biomass_t"].astype(float)
        else:
            frame["crown_fuel_t"] = 0.0015 * frame["dbh_cm"].astype(float) ** 2
    if "surface_fuel_t_ha" not in frame:
        frame["surface_fuel_t_ha"] = surface_fuel_t_ha
    if "snag_t" not in frame:
        frame["snag_t"] = 0.0
    if "tree_id" not in frame:
        frame["tree_id"] = [f"nemora-{index:06d}" for index in range(len(frame))]
    if "provenance" not in frame:
        frame["provenance"] = f"nemora={nemora_version}; {NEMORA_ADAPTER_VERSION}"
    for column in (
        "x",
        "y",
        "z",
        "dbh_cm",
        "height_m",
        "crown_ratio",
        "crown_radius_m",
        "crown_fuel_t",
        "surface_fuel_t_ha",
        "snag_t",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if (
        frame[
            [
                *required,
                "z",
                "crown_ratio",
                "crown_radius_m",
                "crown_fuel_t",
                "surface_fuel_t_ha",
                "snag_t",
            ]
        ]
        .isna()
        .any()
        .any()
    ):
        raise NemoraAdapterError("Nemora tree table has non-numeric or missing values")
    if (frame["dbh_cm"] <= 0.0).any() or (frame["height_m"] <= 0.0).any():
        raise NemoraAdapterError("Nemora tree table has non-positive DBH or height")
    frame["live"] = frame["live"].map(_as_bool)
    frame["decay_class"] = frame["decay_class"].fillna(0).astype(int)
    return frame[[column for column in TREE_COLUMNS if column in frame]]


def trees_from_nemora(
    frame: pd.DataFrame,
    polygons: Mapping[int, VriFragment],
    *,
    seed: int,
    source: str,
    crs: str = "local",
    nemora_version: str = "unknown",
) -> TreeInventory:
    """Join a normalized tree table to VRI polygons and build the scene inventory.

    Parameters
    ----------
    frame : pandas.DataFrame
        Output of :func:`load_nemora_tree_table`.
    polygons : mapping of int to VriFragment
        VRI polygons keyed by fragment id.
    seed : int
        Generator seed recorded in the provenance.
    source : str
        Polygon source label.
    crs : str, optional
        Coordinate reference system label (default ``local``).
    nemora_version : str, optional
        Nemora version recorded in the provenance.

    Returns
    -------
    TreeInventory
        The validated inventory with real polygon footprints.

    Raises
    ------
    NemoraAdapterError
        If a tree cannot be assigned to exactly one polygon or lies outside it.
    """
    if not isinstance(seed, int) or seed < 0:
        raise NemoraAdapterError("seed must be a non-negative integer")
    if not polygons:
        raise NemoraAdapterError("at least one VRI polygon is required")
    shapes = {fragment_id: Polygon(item.ring) for fragment_id, item in polygons.items()}
    trees: list[Tree] = []
    for index, row in enumerate(frame.to_dict("records")):
        x = float(str(row["x"]))
        y = float(str(row["y"]))
        point = Point(x, y)
        explicit = row.get("fragment_id")
        if explicit is not None and not pd.isna(explicit):
            fragment_id = int(str(explicit))
            if fragment_id not in shapes:
                raise NemoraAdapterError(f"tree names unknown fragment: {fragment_id}")
            if not (point.within(shapes[fragment_id]) or point.touches(shapes[fragment_id])):
                raise NemoraAdapterError(
                    f"tree {row.get('tree_id', index)!r} lies outside VRI fragment {fragment_id}"
                )
        else:
            matches = [
                fragment
                for fragment, shape in shapes.items()
                if point.within(shape) or point.touches(shape)
            ]
            if len(matches) != 1:
                raise NemoraAdapterError(
                    f"tree {row.get('tree_id', index)!r} belongs to {len(matches)} VRI polygons"
                )
            fragment_id = matches[0]
        trees.append(
            Tree(
                tree_id=str(row.get("tree_id", f"nemora-{index:06d}")),
                fragment_id=fragment_id,
                x=x,
                y=y,
                z=float(str(row.get("z", 0.0))),
                species=str(row.get("species", "UNK")),
                dbh_cm=float(str(row["dbh_cm"])),
                height_m=float(str(row["height_m"])),
                crown_ratio=float(str(row["crown_ratio"])),
                crown_radius_m=float(str(row["crown_radius_m"])),
                live=bool(row.get("live", True)),
                decay_class=int(str(row.get("decay_class", 0))),
                crown_fuel_t=float(str(row["crown_fuel_t"])),
                surface_fuel_t_ha=float(str(row["surface_fuel_t_ha"])),
                snag_t=float(str(row["snag_t"])),
                provenance=str(row.get("provenance", f"nemora={nemora_version}")),
            )
        )
    origins = {
        fragment: (min(point[0] for point in item.ring), min(point[1] for point in item.ring))
        for fragment, item in polygons.items()
    }
    inventory = TreeInventory(
        trees=tuple(trees),
        fragment_areas={fragment: item.area_ha for fragment, item in polygons.items()},
        fragment_origins=origins,
        fragment_polygons={fragment: item.ring for fragment, item in polygons.items()},
        seed=seed,
        source=f"{source}; nemora={nemora_version}; crs={crs}; {NEMORA_ADAPTER_VERSION}",
    )
    violations = inventory.bounds_violations()
    if violations:
        raise NemoraAdapterError(f"trees outside their VRI polygons: {', '.join(violations[:5])}")
    return inventory


def load_nemora_scene(
    tree_table: str | Path,
    polygons: str | Path,
    *,
    seed: int,
    source: str,
    crs: str = "local",
    nemora_version: str = "unknown",
    column_map: Mapping[str, str] | None = None,
) -> TreeInventory:
    """Load a tree table and VRI layer and return the scene inventory.

    Parameters
    ----------
    tree_table : str or Path
        Nemora CSV or Parquet tree table.
    polygons : str or Path
        VRI GeoJSON FeatureCollection.
    seed : int
        Generator seed.
    source : str
        Polygon source label.
    crs : str, optional
        Coordinate reference system label (default ``local``).
    nemora_version : str, optional
        Nemora version label.
    column_map : mapping of str to str, optional
        Extra column aliases.

    Returns
    -------
    TreeInventory
        The adapted inventory.
    """
    frame = load_nemora_tree_table(tree_table, column_map=column_map, nemora_version=nemora_version)
    vri = load_vri_polygons(polygons)
    return trees_from_nemora(
        frame,
        vri,
        seed=seed,
        source=source,
        crs=crs,
        nemora_version=nemora_version,
    )


def _as_bool(value: object) -> bool:
    """Return a boolean from common table encodings."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y", "live"}
