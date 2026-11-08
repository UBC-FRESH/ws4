"""Benchmark the Huygens growth engine against the public FBP ellipse.

The script runs a homogeneous fuel/weather matrix and a deterministic weather/fuel-moisture
ensemble. It writes the per-scenario comparison and a summary JSON. The analytic ellipse is a
public growth model, not an observed perimeter; the report says what that does and does not
validate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from ws4.fire.benchmark import WeatherScenario

BENCHMARK_FUELS = ("C2", "C3", "C7", "M1", "S1")
BENCHMARK_WINDS = (0.0, 10.0, 20.0, 30.0)
ENSEMBLE_FUELS = ("C2", "C3", "C7")
ENSEMBLE_FFMC = (85.0, 90.0, 95.0)
ENSEMBLE_BUI = (30.0, 60.0, 90.0)
ENSEMBLE_WINDS = (10.0, 20.0)
AREA_THRESHOLDS = (1.0, 10.0, 50.0, 100.0)


def benchmark_scenarios() -> list[WeatherScenario]:
    """Return the homogeneous fuel/wind benchmark matrix.

    Returns
    -------
    list of WeatherScenario
        One scenario per fuel and wind speed at FFMC 90, BUI 60, and 60 minutes.
    """
    from ws4.fire.benchmark import WeatherScenario

    return [
        WeatherScenario(
            scenario_id=f"bench-{fuel}-w{int(wind)}",
            fuel_type=fuel,
            ffmc=90.0,
            bui=60.0,
            wind_kmh=wind,
            duration_min=60.0,
        )
        for fuel in BENCHMARK_FUELS
        for wind in BENCHMARK_WINDS
    ]


def ensemble_scenarios() -> list[WeatherScenario]:
    """Return the deterministic weather/fuel-moisture ensemble.

    Returns
    -------
    list of WeatherScenario
        One scenario per fuel, FFMC, BUI, and wind speed at 60 minutes.
    """
    from ws4.fire.benchmark import WeatherScenario

    return [
        WeatherScenario(
            scenario_id=f"ens-{fuel}-f{int(ffmc)}-b{int(bui)}-w{int(wind)}",
            fuel_type=fuel,
            ffmc=ffmc,
            bui=bui,
            wind_kmh=wind,
            duration_min=60.0,
        )
        for fuel in ENSEMBLE_FUELS
        for ffmc in ENSEMBLE_FFMC
        for bui in ENSEMBLE_BUI
        for wind in ENSEMBLE_WINDS
    ]


def _error_summary(frame: pd.DataFrame) -> dict[str, float]:
    """Return the absolute-error summary of a benchmark frame."""
    summary: dict[str, float] = {}
    for column in (
        "length_relative_error",
        "width_relative_error",
        "area_relative_error",
        "perimeter_relative_error",
    ):
        values = [abs(float(value)) for value in frame[column]]
        summary[f"{column}_mean_abs"] = sum(values) / len(values)
        summary[f"{column}_max_abs"] = max(values)
    return summary


def main() -> None:
    """Run the benchmark and write the per-scenario and summary artifacts."""
    from ws4.fire.benchmark import run_growth_ensemble, summarize_ensemble

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/reports/p156-benchmark.csv"),
        help="Per-scenario CSV destination.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("notes/reports/p156-benchmark-summary.json"),
        help="Summary JSON destination.",
    )
    parser.add_argument("--cell-size-m", type=float, default=10.0)
    args = parser.parse_args()

    benchmark = run_growth_ensemble(benchmark_scenarios(), cell_size_m=args.cell_size_m)
    ensemble = run_growth_ensemble(ensemble_scenarios(), cell_size_m=args.cell_size_m)
    combined = pd.concat(
        [
            benchmark.assign(suite="benchmark"),
            ensemble.assign(suite="ensemble"),
        ],
        ignore_index=True,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.output, index=False)

    summary = {
        "benchmark": _error_summary(benchmark),
        "ensemble": summarize_ensemble(ensemble, thresholds=AREA_THRESHOLDS),
        "cell_size_m": args.cell_size_m,
        "benchmark_scenarios": len(benchmark),
        "ensemble_scenarios": len(ensemble),
        "note": (
            "The analytic ellipse is the public FBP growth model. It shares the head ROS "
            "with the growth engine, so this validates geometry, not independent fire "
            "behaviour. No observed perimeter is used."
        ),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
