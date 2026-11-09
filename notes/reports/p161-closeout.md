# P161 close-out: second observed fire and calibration protocol

Date: 2026-11-09
Parent issue: #954
Tasks: P161.1 (#955), P161.2 (#956), P161.3 (#957), P161.4 (#958), P161.5 (#959)
Branch: `feature/p161-second-fire-calibration`
Status: no-go; PR queued for approval
Protocol: `notes/design/ws4-fire-calibration-protocol.md`
Data gate: `notes/design/ws4-second-fire-calibration.md`

## Result

P161 built an independent second fire, pre-registered a calibration protocol, and ran the fixed
25-point grid. The calibration is a **no-go**: every Hay River point burned the entire burnable
domain, so the two multipliers could not change the final footprint.

### Hay River baseline

| Metric | Value |
| --- | ---: |
| Simulated area | 10,846 ha |
| Observed area | 2,987 ha |
| Area bias | +263.1% |
| Perimeter bias | +223.1% |
| Centroid distance | 1.43 km |
| IoU | 0.275 |
| Sorensen | 0.431 |
| Orientation error | 27.6° |
| Weighted score | 1.3436 |
| Burnable cells | 10,846 |
| Simulated burned cells | 10,846 |

The model fills the 131 × 117 grid. That grid is a 1.5 km buffer around the observed fire,
and the 156-hour window is long enough for every parameter point in the registered box to fill
it. All 25 Hay River rows are identical: one unique score, one final mask.

### Grid

The pre-registered grid was 5 × 5 over:

- `wind_multiplier`: 0.70–1.30
- `head_ros_multiplier`: 0.50–1.50

All 25 combinations produced:

- area 10,846 ha;
- perimeter bias +223.1%;
- IoU 0.275;
- Sorensen 0.431;
- score 1.3436.

The best row is an arbitrary tie at the lower boundary (`0.70, 0.50`). It is not a selected
calibration because there is no score improvement.

### Dogrib holdout

Dogrib was not used to choose parameters. As a diagnostic, the arbitrary boundary point was
applied once:

| Case | Area | Area bias | Perimeter bias | Centroid | IoU | Sorensen | Orientation | Score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dogrib baseline | 16,241 ha | +58.9% | +75.9% | 1.77 km | 0.385 | 0.556 | 6.5° | 0.5213 |
| Boundary point `0.70, 0.50` | 2,203 ha | −78.4% | −61.8% | 10.81 km | 0.160 | 0.275 | 37.5° | 0.8293 |

The holdout degrades. This confirms that the boundary point is not a transferable calibration.

## Decision

The pre-registered calibration pass required at least a 10% score improvement and an IoU or
Sorensen improvement. The grid produced **0%** improvement and no metric change. The
calibration fails.

The holdout also fails. P161 closes **no-go** with no selected parameter set and no calibration
claim.

## Why this is a design failure, not a model success

The fixture domain is too small and the window too long for this objective: the model reaches
every burnable cell regardless of the two multipliers. A calibration cannot identify a
parameter region when the observable is saturated. This is a property of the experiment, not
evidence that the unmodified model is correct.

Do not extend the box, shorten the window, or change the domain inside P161. A future
calibration phase would need a new pre-registered case where the model is parameter-sensitive:
a larger domain, a shorter growth window, or a progression-based objective.

## Accepted limits

- One second fire, one historical event, satellite-derived CFSDS perimeter.
- The CFSDS final is 2,770 ha; the fixture raster is 2,987 ha; a 22 May NWT map is 3,208.9 ha.
- No suppression, spotting, or hourly BUI.
- The fuel and terrain are a 100 m FireSTARR subset; the raw datasets have no explicit licence
  file and are not committed.
- The Hay River ignition is the first-day burned centroid, not an official report.
- No operational validation or regional calibration claim.

## Artifacts

- `tests/fixtures/fire/hay_river_2023/`
- `ws4/fire/observed.py` — `load_hay_river`
- `ws4/fire/calibration.py` — registered grid and score
- `notes/design/ws4-fire-calibration-protocol.md`
- `notes/reports/p161-calibration-grid.csv`
- `notes/reports/p161-calibration-grid.json`
- `scripts/benchmark_hay_river_calibration.py`

## Recommendation

Keep the second-fire fixture and the calibration harness. Close P161 as a no-go. A later phase
may pre-register a new calibration experiment on a parameter-sensitive case; it must not reuse
the Dogrib holdout for fitting or quietly widen the current bounds.

## Pull request

PR: to be opened.
