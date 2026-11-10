# P162 close-out: calibration sensitivity diagnostic

Date: 2026-11-10
Parent issue: #961
Tasks: P162.1 (#962), P162.2 (#963), P162.3 (#964)
Branch: `feature/p162-calibration-sensitivity`
Status: no-go for calibration; PR queued for approval
Report: `notes/reports/p162-sensitivity.md`

## Result

The Hay River case is parameter-sensitive at one-day and three-day windows, but it is not
viable for calibration. At the lowest registered point (`0.70, 0.50`):

- day-1: 2,692 ha vs 29 ha observed (+9,183%);
- day-3: 10,594 ha vs 832 ha observed (+1,173%);
- full event: 10,846 ha vs 2,987 ha observed (+263%).

The full-event window is saturated: all 25 P161 points and all three P162 points burn the
entire 10,846-cell burnable domain.

## Decision

P162 closes **no-go for calibration**.

Sensitivity alone is not enough. The model is far above observed daily growth at every
registered point, so a fit would be forced to the boundary and would not address the structural
mismatch. The full-event case is saturated and cannot identify parameters at all.

No parameter set is selected. No new calibration protocol is started. The diagnostic harness
and daily-comparison runner are retained.

## What was added

- `observed_index` on `run_observed_case`, allowing comparison with a matching daily perimeter.
- `scripts/benchmark_hay_river_sensitivity.py`.
- Fixed day-1/day-3/full windows and baseline/low/high points.
- `notes/reports/p162-sensitivity.csv` and `.json`.
- Tests for the daily-index runner and the sensitivity script wiring.

## Limits

- One fire, satellite-derived daily perimeters, no suppression or spotting.
- The ignition is the first-day satellite centroid, not an official report.
- The domain is a small buffer; the full-event run saturates it.
- The low/high points are diagnostic, not fitted.
- No operational validation or regional calibration claim.

## Recommendation

Keep the Hay River fixture for diagnostic and point-ignition checks, but do not calibrate
against it. A future calibration phase needs a different case with a defensible ignition time,
a start perimeter or hourly progression, and enough domain that the final perimeter is not a
domain boundary. That must be a new pre-registration, not an extension of P161.

P159 remains a separate planned surrogate study.

## Pull request

PR: to be opened.
