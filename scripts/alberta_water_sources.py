"""P229: screen Alberta waterbodies near the HWF113 gap."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from pyproj import Transformer
from shapely.geometry import Point, Polygon


@dataclass(frozen=True)
class WaterSource:
    """One candidate waterbody for aerial refilling.

    Parameters
    ----------
    object_id : int
        Source service object identifier.
    feature_type : str
        Alberta waterbody feature type.
    name : str or None
        Waterbody name, when present.
    area_ha : float
        Projected waterbody area in hectares.
    distance_km : float
        Distance from the gap centre in kilometres.
    """

    object_id: int
    feature_type: str
    name: str | None
    area_ha: float
    distance_km: float


def _rings_from_geometry(geometry: dict[str, Any]) -> list[list[list[float]]]:
    """Return polygon rings from ArcGIS or GeoJSON geometry.

    Parameters
    ----------
    geometry : dict
        ArcGIS geometry with ``rings`` or GeoJSON polygon geometry.

    Returns
    -------
    list of list of list of float
        Polygon rings in longitude and latitude.
    """
    if geometry.get("rings"):
        return cast("list[list[list[float]]]", geometry["rings"])
    coordinates = geometry.get("coordinates")
    if not coordinates:
        raise ValueError("geometry has no polygon rings")
    if geometry.get("type") == "Polygon":
        return cast("list[list[list[float]]]", coordinates)
    if geometry.get("type") == "MultiPolygon":
        rings = [ring for polygon in coordinates for ring in polygon]
        return cast("list[list[list[float]]]", rings)
    raise ValueError(f"unsupported geometry type: {geometry.get('type')}")


def _project_polygon(polygon: Polygon, transformer: Transformer) -> Polygon:
    """Project a longitude/latitude polygon.

    Parameters
    ----------
    polygon : shapely.geometry.Polygon
        Polygon in longitude and latitude.
    transformer : pyproj.Transformer
        Transformer to the target projected CRS.

    Returns
    -------
    shapely.geometry.Polygon
        Projected polygon.
    """
    shell = [transformer.transform(x, y) for x, y in polygon.exterior.coords]
    holes = [
        [transformer.transform(x, y) for x, y in interior.coords] for interior in polygon.interiors
    ]
    return Polygon(shell, holes)


def screen_waterbodies(
    features: list[dict[str, Any]],
    *,
    gap_x: float,
    gap_y: float,
    min_area_ha: float = 1.0,
    max_distance_km: float = 20.0,
    crs: int = 32611,
) -> list[WaterSource]:
    """Screen waterbodies by projected area and distance from the gap.

    Parameters
    ----------
    features : list of dict
        ArcGIS or GeoJSON polygon features.
    gap_x : float
        Gap centre easting in the projected CRS.
    gap_y : float
        Gap centre northing in the projected CRS.
    min_area_ha : float, optional
        Minimum waterbody area in hectares (default 1).
    max_distance_km : float, optional
        Maximum distance from the gap in kilometres (default 20).
    crs : int, optional
        Target projected CRS (default 32611).

    Returns
    -------
    list of WaterSource
        Candidates sorted by distance, then area.
    """
    transformer = Transformer.from_crs(4326, crs, always_xy=True)
    gap = Point(gap_x, gap_y)
    sources: list[WaterSource] = []
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        rings = _rings_from_geometry(geometry)
        polygon = Polygon(rings[0], rings[1:])
        projected = _project_polygon(polygon, transformer)
        area_ha = projected.area / 10_000.0
        distance_km = projected.distance(gap) / 1000.0
        if area_ha < min_area_ha or distance_km > max_distance_km:
            continue
        attributes = feature.get("attributes", {})
        sources.append(
            WaterSource(
                object_id=int(attributes.get("OBJECTID", 0)),
                feature_type=str(attributes.get("FEATURE_TYPE", "")),
                name=attributes.get("NAME"),
                area_ha=area_ha,
                distance_km=distance_km,
            )
        )
    return sorted(sources, key=lambda source: (source.distance_km, -source.area_ha))


def nearest_by_min_area(
    sources: list[WaterSource],
    minima_ha: tuple[float, ...] = (1.0, 5.0, 10.0, 50.0, 100.0),
) -> dict[str, dict[str, object] | None]:
    """Find the nearest source above each area threshold.

    Parameters
    ----------
    sources : list of WaterSource
        Screened candidate sources.
    minima_ha : tuple of float, optional
        Area thresholds in hectares.

    Returns
    -------
    dict of str to dict or None
        Nearest source for each threshold, keyed by threshold.
    """
    result: dict[str, dict[str, object] | None] = {}
    for minimum in minima_ha:
        candidates = [source for source in sources if source.area_ha >= minimum]
        key = f"{minimum:g}_ha"
        result[key] = asdict(candidates[0]) if candidates else None
    return result


def load_features(path: Path) -> list[dict[str, Any]]:
    """Load features from an ArcGIS JSON or GeoJSON file.

    Parameters
    ----------
    path : pathlib.Path
        Input JSON file.

    Returns
    -------
    list of dict
        Feature records.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("input has no feature list")
    return features


def main() -> None:
    """Run the waterbody screen and print JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--gap-x", type=float, required=True)
    parser.add_argument("--gap-y", type=float, required=True)
    parser.add_argument("--min-area-ha", type=float, default=1.0)
    parser.add_argument("--max-distance-km", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    features = load_features(args.features)
    sources = screen_waterbodies(
        features,
        gap_x=args.gap_x,
        gap_y=args.gap_y,
        min_area_ha=args.min_area_ha,
        max_distance_km=args.max_distance_km,
    )
    payload = {
        "gap_utm": {"x": args.gap_x, "y": args.gap_y, "crs": 32611},
        "parameters": {
            "min_area_ha": args.min_area_ha,
            "max_distance_km": args.max_distance_km,
        },
        "feature_count": len(features),
        "candidate_count": len(sources),
        "sources": [asdict(source) for source in sources],
        "nearest_by_min_area": nearest_by_min_area(sources),
    }
    text = json.dumps(payload, indent=2)
    if args.output is None:
        print(text)
    else:
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
