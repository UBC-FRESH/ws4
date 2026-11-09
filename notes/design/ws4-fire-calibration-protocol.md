# Fire-model calibration and holdout protocol

Status: pre-registered before fitting
Phase: P161.3 (#957)
Branch: `feature/p161-second-fire-calibration`
Calibration fire: Hay River / K'atl'odeeche (2023_320)
Holdout fire: Dogrib (RWF085)

## 1. Scope

This protocol fixes the parameters, bounds, objective, search, and holdout rules before any
calibrated result exists. P161.4 may implement the parameters and run the search, but it may
not change this table after seeing the Hay River or Dogrib result.

The purpose is a **two-case transfer test**, not a regional calibration.

## 2. Parameters

Only two global multipliers are eligible. They apply to every fuel type and every cell; no
per-fuel, per-weather-zone, or per-fire parameter is allowed.

| Parameter | Symbol | Lower | Reference | Upper | Applies to |
| --- | --- | ---: | ---: | ---: | --- |
| Ten-metre wind multiplier | `wind_multiplier` | 0.70 | 1.00 | 1.30 | Wind passed to the FBP surface/crown layer and the effective-wind calculation |
| Head rate-of-spread multiplier | `head_ros_multiplier` | 0.50 | 1.00 | 1.50 | Final head ROS from the FBP surface/crown layer before growth |

Bounds are deliberately broad because the two-case design cannot identify a narrow parameter
region. They are not literature estimates; they are a declared search box. The reference point
`1.0, 1.0` is the unmodified WS4 model and is always reported as the baseline.

Not eligible:

- per-fuel FBP coefficients;
- slope adjustment;
- foliar moisture, curing, or fuel load;
- burning-condition thresholds;
- weather-patch geometry;
- spotting, hourly BUI, or any new physics;
- ignition location, perimeter, fuel map, or terrain.

## 3. Fixed inputs

Calibration case: Hay River / K'atl'odeeche `2023_320`, 14–20 May 2023, 100 m UTM zone 11N,
point ignition, seven cumulative daily perimeters, ECCC Hay River Climate hourly weather.
The event starts 14 May 12:00 LST and ends 20 May 23:00 LST.

Holdout case: Dogrib RWF085 Scenario 2b, 402 minutes, 100 m observed grid, point ignition,
observed start perimeter as a fuel break, hourly weather, +15° landscape patch and 280° river
patch, with the P160 burning-condition gate. The Dogrib baseline is the P157/P160 result:
16,241 ha, +58.9% area, +75.9% perimeter, 1.77 km centroid, IoU 0.385, Sorensen 0.556, 6.5°
orientation.

No input is changed between baseline, calibrated, and holdout runs.

## 4. Objective

The calibration score is a weighted sum of the existing P157 metrics. All components are
already in the comparison harness.

```text
score =
    0.25 * abs(area_bias)
  + 0.15 * abs(perimeter_bias)
  + 0.20 * min(centroid_distance_km / 5.0, 1.0)
  + 0.20 * (1.0 - iou)
  + 0.10 * (1.0 - sorensen)
  + 0.10 * min(orientation_error_deg / 30.0, 1.0)
```

Lower is better. The weights sum to 1.0. The centroid and orientation terms are capped at their
P157 screening tolerances (5 km and 30°), so a gross miss cannot dominate the score without
bound. Area and perimeter biases are not capped; a large over- or underprediction remains
visible.

The objective is evaluated on the final Hay River perimeter. Daily progression is reported but
is not part of the calibration score.

## 5. Search

The search is a fixed 5 × 5 grid:

- `wind_multiplier`: 0.70, 0.85, 1.00, 1.15, 1.30
- `head_ros_multiplier`: 0.50, 0.75, 1.00, 1.25, 1.50

That is 25 runs, including the `1.0, 1.0` baseline. There is no random seed, no adaptive
refinement, and no post-hoc expansion. If the best point is on a bound, report that the optimum
is at the search boundary and do not extend the box in the same phase.

Ties are broken by, in order: lower area bias, lower perimeter bias, higher IoU, lower centroid
distance.

## 6. Holdout rule

The single best Hay River point is frozen and applied **once** to Dogrib. No Dogrib parameter
adjustment, re-selection, or per-fire correction is allowed.

The holdout is evaluated with the same score and the same P157 screens. The result is reported
as:

- baseline Dogrib;
- frozen-parameter Dogrib;
- absolute and relative change in each metric.

Dogrib is not used to choose the parameters, the weights, the bounds, or the search grid.

## 7. Decision rule

Calibration is a **pass** when:

1. the best Hay River score improves by at least 10% relative to the Hay River baseline; and
2. at least one of IoU or Sorensen improves; and
3. neither area bias nor perimeter bias worsens by more than 10 percentage points.

Holdout transfer is a **pass** when:

1. the frozen-parameter Dogrib score is not worse than the Dogrib baseline by more than 10%
   relative; and
2. at least one of area bias, perimeter bias, IoU, or Sorensen improves.

The phase closes as:

- **supported** if calibration and holdout both pass;
- **calibration-only** if Hay River passes but Dogrib fails (no transfer claim);
- **no-go** if Hay River fails, or the search cannot be run as specified.

A no-go is a complete result. Do not keep tuning on Dogrib.

## 8. Reporting

The P161.4 report must include:

- the full 25-point table with both parameters and all metrics;
- the baseline row and the selected row;
- the Dogrib baseline and frozen-parameter rows;
- the score components, not only the total;
- the implementation version and commit;
- the exact commands and fixture versions;
- a statement that the result is two-case evidence, not operational validation.

## 9. Approval gate

P161.3 is complete when this protocol is committed and reviewed. P161.4 begins only after that.
No calibrated numbers exist when this file is written.
