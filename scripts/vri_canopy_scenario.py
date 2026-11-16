"""Run a controlled BC VRI canopy-only treatment scenario."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from shapely import contains_xy
from shapely.geometry import shape
from ws4.fire.growth import GrowthConfig, SiteGrid, grow_fire
from ws4.fire.prescription import FFS_TREATMENT_CHANGES


def _features(payload: dict[str, object]) -> list[tuple[float, Any]]:
    """Return complete VRI polygon features and their crown closure."""
    raw = payload.get("features")
    if not isinstance(raw, list):
        raise ValueError("input has no feature list")
    result: list[tuple[float, Any]] = []
    for feature in raw:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            continue
        if properties.get("BCLCS_LEVEL_1") != "V":
            continue
        closure = properties.get("CROWN_CLOSURE")
        if closure is None:
            continue
        result.append((float(closure), shape(geometry)))
    if not result:
        raise ValueError("no complete VRI forest polygons")
    return result


def _run(
    closure: np.ndarray,
    *,
    fuel_type: str,
    max_time_min: float,
    cell_size_m: float,
) -> dict[str, float]:
    """Run one fixed-weather growth case."""
    rows, cols = closure.shape
    fuel = np.full((rows, cols), fuel_type, dtype=object)
    grid = SiteGrid(
        fuel_type=fuel_type,
        rows=rows,
        cols=cols,
        cell_size_m=cell_size_m,
        ffmc=90.0,
        bui=60.0,
        wind_kmh=20.0,
        wind_direction_deg=270.0,
        slope_percent=0.0,
        aspect_deg=0.0,
        latitude_deg=49.25,
        longitude_deg=-122.55,
        julian_day=200,
        elevation_m=0.0,
        fuel_type_grid=fuel,
        burnable=np.ones((rows, cols), dtype=bool),
        crown_closure_percent_grid=closure,
        conifer_percent_grid=np.full((rows, cols), 60.0),
        dead_fir_percent_grid=np.zeros((rows, cols)),
    )
    result = grow_fire(
        grid,
        GrowthConfig(
            ignition_cells=((rows // 2, 0),),
            max_time_min=max_time_min,
            snapshot_interval_min=60.0,
            neighbor_radius=2,
        ),
    )
    return {
        "burned_area_ha": result.burned_area_ha,
        "perimeter_m": result.perimeter_m,
        "head_ros_m_min": result.head_ros_m_min,
    }


def main() -> None:
    """Run the canopy-only scenario and write JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--treatment",
        choices=("thin-only", "burn-only", "thin-burn"),
        default="thin-burn",
    )
    parser.add_argument("--max-time-min", type=float, default=120.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    stands = _features(payload)
    min_x = min(geometry.bounds[0] for _, geometry in stands)
    min_y = min(geometry.bounds[1] for _, geometry in stands)
    max_x = max(geometry.bounds[2] for _, geometry in stands)
    max_y = max(geometry.bounds[3] for _, geometry in stands)
    cell = 100.0
    cols = int((max_x - min_x) // cell) + 2
    rows = int((max_y - min_y) // cell) + 2
    xs = min_x + (np.arange(cols) + 0.5) * cell
    ys = max_y - (np.arange(rows) + 0.5) * cell
    x_grid, y_grid = np.meshgrid(xs, ys)
    closure = np.full((rows, cols), 60.0)
    for value, geometry in stands:
        closure[contains_xy(geometry, x_grid, y_grid)] = value
    change = FFS_TREATMENT_CHANGES[args.treatment]["canopy_cover_pct"]
    treated = closure * (1.0 + change / 100.0)
    control_result = _run(closure, fuel_type="C2", max_time_min=args.max_time_min, cell_size_m=cell)
    treated_result = _run(treated, fuel_type="C2", max_time_min=args.max_time_min, cell_size_m=cell)
    result = {
        "source": "BC VRI 2025 Rank 1, Open Government Licence - British Columbia",
        "treatment": args.treatment,
        "canopy_cover_pct": change,
        "weather": {"ffmc": 90.0, "bui": 60.0, "wind_kmh": 20.0, "wind_direction_deg": 270.0},
        "grid": {"rows": rows, "cols": cols, "cell_size_m": cell, "fuel_type": "C2"},
        "control": control_result,
        "treated": treated_result,
        "area_difference_ha": treated_result["burned_area_ha"] - control_result["burned_area_ha"],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
