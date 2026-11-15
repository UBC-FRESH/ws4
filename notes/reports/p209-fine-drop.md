# P209 100 m drop-depth pilot

Date: 2026-11-14
Phase: P209 (#1250)
Task: P209.1 (#1251)
Branch: `feature/p209-fine-drop`
Artifacts: `notes/reports/p209-fine-drop.json`, `p209-fine-drop-5800.json`

## Question

Does the P208 drop-depth field suppress at 100 m resolution, where the drop footprint is comparable
to a cell?

## Setup

- `2003_96` fine-grid fixture, 100 m
- P201 barrier with a 5-cell gap
- two 6,000 L drops per gap cell, 100 m x 50 m ellipse
- 0.75 mm threshold, 60-minute linear decay
- baseline member only; the full five-member run exceeded the execution budget

## Result

- gap mean depth: **1.18 mm**
- drop at 13,000 min: final area 146,191 ha, east of barrier 53,464 cells
- drop at 5,800 min: final area 146,191 ha, same crossing
- free burn: 146,532 ha

The 100 m grid produces the intended depth, but the two-drop line does not contain the fire. The
effective hold is short and the front reaches the gap over a long window.

## Interpretation

Resolution was necessary but not sufficient. At 100 m the depth is above threshold; containment
still fails because the treated line is not maintained through the arrival window.

This is consistent with P182/P185: depth at arrival is not the same as persistence.

## Decision

**No-go** for two 6,000 L drops per gap cell and a 60-minute decay at 100 m.

A valid next test needs re-wetting on an interval shorter than the effective hold, more water per
cell, or a longer documented hold.

## Limits

- One weather member; full ensemble exceeded the execution budget.
- Synthetic barrier geometry.
- No tanker, helicopter, refill or dispatch.
- No calibration and no operational claim.
