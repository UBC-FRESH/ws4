"""Evaluate the frozen P159 surrogate on held-out synthetic and Dogrib OOD cases."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from ws4.fire.comparison import PerimeterMetrics
    from ws4.fire.observed import ObservedFire, ObservedGrid
    from ws4.fire.surrogate import SurrogateSample


def _grid(rows: int, cols: int, cell_size_m: float = 100.0) -> ObservedGrid:
    """Return a local metric grid for a sample."""
    from ws4.fire.observed import ObservedGrid

    return ObservedGrid(cols, rows, 0.0, 0.0, cell_size_m, 0.0, "local")


def _metrics(predicted: np.ndarray, observed: np.ndarray, rows: int, cols: int) -> PerimeterMetrics:
    """Return P157 comparison metrics for a predicted mask."""
    from ws4.fire.comparison import compare_masks

    return compare_masks(predicted, observed, _grid(rows, cols))


def _dogrib_sample(fire: ObservedFire) -> tuple[SurrogateSample, np.ndarray]:
    """Convert the Dogrib fixture into a surrogate sample for OOD prediction."""
    from ws4.fire.comparison import observed_mask, reference_weather
    from ws4.fire.growth import slope_aspect_from_elevation
    from ws4.fire.surrogate import SURROGATE_FUEL_ORDER, SurrogateSample

    rows, cols = fire.grid.nrows, fire.grid.ncols
    fuel_lookup = {name: index + 1 for index, name in enumerate(SURROGATE_FUEL_ORDER)}
    fuel_names = fire.fbp_fuel_grid()
    fuel_index = np.zeros((rows, cols), dtype=np.uint8)
    for row in range(rows):
        for col in range(cols):
            name = fuel_names[row, col]
            if name is not None:
                fuel_index[row, col] = fuel_lookup[name]
    slope, aspect = slope_aspect_from_elevation(
        fire.elevation_m, fire.grid.cell_size_m, nodata=fire.grid.nodata
    )
    x, y = fire.ignition_xy
    ign_col = int((x - fire.grid.xll) // fire.grid.cell_size_m)
    ign_row = rows - 1 - int((y - fire.grid.yll) // fire.grid.cell_size_m)
    burnable = fuel_index > 0
    if not (0 <= ign_row < rows and 0 <= ign_col < cols and burnable[ign_row, ign_col]):
        candidates = np.argwhere(burnable)
        distances = (candidates[:, 0] - ign_row) ** 2 + (candidates[:, 1] - ign_col) ** 2
        nearest = candidates[int(np.argmin(distances))]
        ign_row, ign_col = int(nearest[0]), int(nearest[1])
    weather = reference_weather(fire)
    observed = observed_mask(fire, -1)
    return SurrogateSample(
        sample_id="dogrib-ood",
        split="validation",
        fuel_index=fuel_index,
        slope_percent=slope,
        aspect_deg=aspect,
        ignition=(ign_row, ign_col),
        wind_kmh=float(weather["wind_kmh"]),
        wind_direction_deg=float(weather["wind_direction_deg"]),
        ffmc=float(weather["ffmc"]),
        bui=float(weather["bui"]),
        duration_min=402.0,
        arrival_time_min=np.full((rows, cols), np.inf),
        burned_mask=observed,
    ), observed


def main() -> None:
    """Run held-out synthetic and Dogrib OOD evaluation."""
    from ws4.fire.observed import load_dogrib
    from ws4.fire.surrogate import generate_corpus
    from ws4.fire.surrogate_model import SurrogateModel

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=ROOT / "notes" / "reports" / "p159-model")
    parser.add_argument(
        "--dogrib", type=Path, default=ROOT / "tests" / "fixtures" / "fire" / "dogrib"
    )
    parser.add_argument("--count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=159)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--cols", type=int, default=32)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "notes" / "reports" / "p159-evaluation.csv"
    )
    parser.add_argument(
        "--summary", type=Path, default=ROOT / "notes" / "reports" / "p159-evaluation.json"
    )
    args = parser.parse_args()
    model = SurrogateModel.load(args.model)
    corpus = generate_corpus(
        count=args.count,
        seed=args.seed,
        rows=args.rows,
        cols=args.cols,
        duration_min=args.duration,
    )
    rows: list[dict[str, object]] = []
    synthetic_metrics: list[PerimeterMetrics] = []
    for sample in corpus.samples:
        if sample.split != "validation":
            continue
        start = time.perf_counter()
        predicted = model.predict_mask(sample)
        elapsed = time.perf_counter() - start
        metrics = _metrics(predicted, np.asarray(sample.burned_mask), *sample.shape)
        synthetic_metrics.append(metrics)
        rows.append(
            {
                "case": "synthetic-holdout",
                "sample_id": sample.sample_id,
                "inference_ms": elapsed * 1000.0,
                **metrics.to_dict(),
            }
        )
    dogrib = load_dogrib(args.dogrib)
    ood_sample, observed = _dogrib_sample(dogrib)
    start = time.perf_counter()
    predicted = model.predict_mask(ood_sample)
    elapsed = time.perf_counter() - start
    ood_metrics = _metrics(predicted, observed, *ood_sample.shape)
    rows.append(
        {
            "case": "dogrib-ood",
            "sample_id": "dogrib-ood",
            "inference_ms": elapsed * 1000.0,
            **ood_metrics.to_dict(),
        }
    )
    summary = {
        "model": model.to_dict(),
        "synthetic_holdout": {
            "count": len(synthetic_metrics),
            "mean_iou": float(np.mean([item.iou for item in synthetic_metrics])),
            "mean_sorensen": float(np.mean([item.sorensen for item in synthetic_metrics])),
            "mean_centroid_km": float(
                np.mean([item.centroid_distance_m / 1000.0 for item in synthetic_metrics])
            ),
        },
        "dogrib_ood": ood_metrics.to_dict(),
        "limitations": (
            "The surrogate has no duration feature and was trained on 60-minute 32x32 burns; "
            "Dogrib is a 402-minute 357x223 out-of-distribution case."
        ),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    pd.DataFrame(rows).to_csv(args.output, index=False)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: summary[k] for k in ("synthetic_holdout", "dogrib_ood", "limitations")},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
