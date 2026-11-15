# P219 re-wetting sortie and fleet lower bound

Date: 2026-11-15
Phase: P219 (#1268)
Tasks: P219.1 (#1269), P219.2 (#1270)
Branch: `feature/p219-rewetting-capacity`
Artifact: `notes/reports/p219-rewetting-capacity.json`

## Assumptions

- 15-minute re-wetting interval from P217
- two 6,000 L drops per cell per application
- 4.25-minute mean aircraft cycle from P180
- perfect continuous dispatch, no refill, weather or maintenance constraints
- 100 m fine-grid line height used as 75 cells

## Result

| Case | Cells | Sorties/application | Sorties/h | Aircraft lower bound | Water/h |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gap only | 5 | 10 | 40 | **3** | 240,000 L |
| Full line | 75 | 150 | 600 | **43** | 3,600,000 L |

## Interpretation

The P217 containment result applies only to a five-cell gap. Closing that gap at 15-minute
persistence has a **three-aircraft lower bound** under perfect dispatch.

Wetting the entire 75-cell line is a different problem: roughly 43 aircraft and 3.6 million litres
per hour.

These are lower bounds, not operational plans. They assume no refill, transit, weather, maintenance
or coverage loss.

## Decision

Go for the gap-only operational-capacity calculation. No-go for claiming that a small fleet can wet
the entire line.

## Limits

- No dispatch simulation, water source, refill or queue.
- No coverage loss or drop overlap beyond the two-drop assumption.
- No calibration and no operational claim.
