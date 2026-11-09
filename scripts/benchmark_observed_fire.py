"""Run the Dogrib observed-fire comparison and a small sensitivity set.

The script writes a per-scenario CSV and JSON summary under ``notes/reports``. It is a
validation artifact, not a calibration: every override is explicit in the scenario table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from ws4.fire.comparison import DogribCase
    from ws4.fire.observed import ObservedFire


def load_dogrib(path: Path) -> ObservedFire:
    """Load the observed fire without importing WS4 during doc audits.

    Parameters
    ----------
    path : Path
        Directory containing the Dogrib fixture.

    Returns
    -------
    ObservedFire
        The validated observed fire.
    """
    from ws4.fire.observed import load_dogrib as _load

    return _load(path)


def run_dogrib_case(fire: ObservedFire, **kwargs: Any) -> DogribCase:  # noqa: ANN401
    """Run one Dogrib case without importing WS4 during doc audits.

    Parameters
    ----------
    fire : ObservedFire
        The observed fire.
    **kwargs : Any
        Keyword overrides passed to the comparison runner.

    Returns
    -------
    DogribCase
        The simulated case and comparison metrics.
    """
    from ws4.fire.comparison import run_dogrib_case as _run

    return _run(fire, **kwargs)


def write_comparison_svg(fire: ObservedFire, case: DogribCase, path: Path) -> Path:
    """Write the comparison view without importing WS4 during doc audits.

    Parameters
    ----------
    fire : ObservedFire
        The observed fire.
    case : DogribCase
        The simulated case.
    path : Path
        Destination SVG path.

    Returns
    -------
    Path
        The written SVG path.
    """
    from ws4.fire.observed_view import write_comparison_svg as _write

    return _write(fire, case, path)


SCENARIOS: tuple[str, ...] = (
    "scenario-2b",
    "heterogeneous-hourly-402",
    "heterogeneous",
    "homogeneous",
    "scenario-2b-1372",
    "heterogeneous-hourly-1372",
    "heterogeneous-long-1372",
)
EXTRA_SCENARIOS: tuple[str, ...] = (
    "scenario-2b-thresholds",
    "scenario-2b-rh-above",
)
WIND_GRID_SCENARIOS: tuple[str, ...] = (
    "scenario-2c",
    "scenario-2d",
)


def load_wind_grids(root: Path) -> dict[str, dict[int, Any]]:
    """Load the two WindNinja methods under a Dogrib wind-grid root.

    Parameters
    ----------
    root : Path
        Directory containing ``conserv_mass/`` and ``conserv_mass_moment/``.

    Returns
    -------
    dict of str to dict
        Grids keyed by method, then by domain-average direction.
    """
    from ws4.fire.observed import DOGRIB_CRS
    from ws4.fire.wind import load_windninja_directory

    return {
        "conservation_of_mass": load_windninja_directory(
            root / "conserv_mass",
            method="conservation_of_mass",
            source="Dogrib_v624 WindNinja conservation-of-mass grids",
            crs=DOGRIB_CRS,
        ),
        "conservation_of_mass_and_momentum": load_windninja_directory(
            root / "conserv_mass_moment",
            method="conservation_of_mass_and_momentum",
            source="Dogrib_v624 WindNinja conservation-of-mass-and-momentum grids",
            crs=DOGRIB_CRS,
        ),
    }


def run_scenario(
    fire: ObservedFire,
    name: str,
    wind_grids: dict[str, dict[int, Any]] | None = None,
) -> DogribCase:
    """Run one named sensitivity scenario.

    Parameters
    ----------
    fire : ObservedFire
        Dogrib observed fire.
    name : str
        Scenario name from ``SCENARIOS`` or ``WIND_GRID_SCENARIOS``.
    wind_grids : dict, optional
        WindNinja grids keyed by method. Required for 2c and 2d.

    Returns
    -------
    DogribCase
        The simulated growth and comparison.
    """
    if name in {"scenario-2b-thresholds", "scenario-2b-rh-above", "scenario-2c", "scenario-2d"}:
        from ws4.fire.comparison import dogrib_burning_conditions

        if name in {"scenario-2b-thresholds", "scenario-2b-rh-above"}:
            interpretation = "gt" if name == "scenario-2b-rh-above" else "lt"
            return run_dogrib_case(
                fire,
                scenario=name,
                heterogeneous=True,
                hourly_weather=True,
                weather_patches=True,
                point_ignition=True,
                fuel_break_start=True,
                duration_min=402.0,
                burning_conditions=dogrib_burning_conditions(relative_humidity=interpretation),
            )
        if wind_grids is None:
            raise ValueError(f"{name} requires WindNinja grids")
        method = (
            "conservation_of_mass" if name == "scenario-2c" else "conservation_of_mass_and_momentum"
        )
        return run_dogrib_case(
            fire,
            scenario=name,
            heterogeneous=True,
            hourly_weather=True,
            point_ignition=True,
            fuel_break_start=True,
            duration_min=402.0,
            burning_conditions=dogrib_burning_conditions(),
            wind_grids=wind_grids[method],
        )
    if name == "scenario-2b":
        return run_dogrib_case(
            fire,
            scenario=name,
            heterogeneous=True,
            hourly_weather=True,
            weather_patches=True,
            point_ignition=True,
            fuel_break_start=True,
            duration_min=402.0,
        )
    if name == "scenario-2b-1372":
        return run_dogrib_case(
            fire,
            scenario=name,
            heterogeneous=True,
            hourly_weather=True,
            weather_patches=True,
            point_ignition=True,
            fuel_break_start=True,
            duration_min=1372.0,
        )
    if name == "heterogeneous-hourly-402":
        return run_dogrib_case(
            fire, scenario=name, heterogeneous=True, hourly_weather=True, duration_min=402.0
        )
    if name == "heterogeneous-hourly-1372":
        return run_dogrib_case(
            fire, scenario=name, heterogeneous=True, hourly_weather=True, duration_min=1372.0
        )
    if name == "homogeneous":
        return run_dogrib_case(fire, scenario=name)
    if name == "heterogeneous-long-1372":
        return run_dogrib_case(fire, scenario=name, heterogeneous=True, duration_min=1372.0)
    return run_dogrib_case(fire, scenario=name, heterogeneous=True)


def main() -> None:
    """Run the scenarios and write the evidence files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "notes" / "reports" / "p157-dogrib-results.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT / "notes" / "reports" / "p157-dogrib-summary.json",
    )
    parser.add_argument(
        "--view",
        type=Path,
        default=ROOT / "notes" / "reports" / "p157-dogrib-view.svg",
    )
    parser.add_argument(
        "--wind-grids-root",
        type=Path,
        default=None,
        help="Dogrib WindNinja root with conserv_mass/ and conserv_mass_moment/.",
    )
    args = parser.parse_args()
    fire = load_dogrib(ROOT / "tests" / "fixtures" / "fire" / "dogrib")
    wind_grids = None if args.wind_grids_root is None else load_wind_grids(args.wind_grids_root)
    scenarios = list(SCENARIOS) + list(EXTRA_SCENARIOS)
    if wind_grids is not None:
        scenarios.extend(WIND_GRID_SCENARIOS)
    rows: list[dict[str, object]] = []
    base_case: DogribCase | None = None
    for name in scenarios:
        case = run_scenario(fire, name, wind_grids)
        if name == "scenario-2b":
            base_case = case
        row: dict[str, object] = {
            "scenario": case.scenario,
            "duration_min": case.duration_min,
            "fuel_type": case.fuel_type,
            "fuel_mode": case.fuel_mode,
            "weather_mode": case.weather_mode,
            "ffmc": case.ffmc,
            "bui": case.bui,
            "wind_kmh": case.wind_kmh,
            "wind_direction_deg": case.wind_direction_deg,
            "slope_percent": case.slope_percent,
            "aspect_deg": case.aspect_deg,
            "start_cells": case.start_cells,
            "initial_burned_ha": 0.0
            if case.initial_burned_mask is None
            else float(case.initial_burned_mask.sum()) * case.growth.grid.cell_area_ha,
            "head_ros_m_min": case.growth.head_ros_m_min,
            "length_to_breadth": case.growth.length_to_breadth,
            "burned_area_ha": case.growth.burned_area_ha,
            "burning_conditions": (
                None
                if case.growth.config.burning_conditions is None
                else case.growth.config.burning_conditions.to_dict()
            ),
            "wind_grids": case.to_dict()["wind_grids"],
        }
        row.update({f"metric_{key}": value for key, value in case.metrics.to_dict().items()})
        rows.append(row)
    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    if base_case is not None:
        write_comparison_svg(fire, base_case, args.view)
    summary = {
        "fire": fire.to_dict(),
        "scenarios": rows,
        "view": str(args.view),
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    columns = [
        "scenario",
        "burned_area_ha",
        "metric_area_obs_ha",
        "metric_area_bias",
        "metric_perimeter_bias",
        "metric_centroid_distance_m",
        "metric_iou",
        "metric_sorensen",
        "metric_orientation_error_deg",
    ]
    print(frame[columns].to_string(index=False))


if __name__ == "__main__":
    main()
