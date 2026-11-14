# P208 single drop-depth pilot

Date: 2026-11-14
Phase: P208 (#1237)
Tasks: P208.1 (#1238), P208.2 (#1239), P208.3 (#1240)
Branch: `feature/p208-drop-depth`
Artifacts: `notes/reports/p208-drop-depth.json`, `p208-drop-depth.csv`

## Question

Can a real depth/coverage field from a small number of drops suppress the FBP fire at the 500 m
benchmark resolution?

## Setup

- case: `2003_96`, 500 m grid
- P201 barrier with a 5-cell gap
- two 6,000 L drops per gap cell
- 100 m x 50 m elliptical footprint
- drop times 12,000, 13,000 and 14,000 min
- required depth 0.75 mm; 60-minute linear decay
- five P178 weather members

## Result

The two drops produce a **cell-mean depth of 0.044 mm** on the 500 m grid. That is about 17 times
below the 0.75 mm suppression threshold.

Every run crosses the gap and ends at the free-burn area (158,025 ha). The drop timing has no
effect because the depth never reaches the threshold.

## Interpretation

This is a **resolution/scale failure**, not evidence that water is ineffective. A 100 m x 50 m drop
covers a small fraction of a 500 m cell; the cell-mean depth is much lower than the depth inside the
drop footprint.

The 100 m fine-grid run was started but exceeded the execution budget and is not claimed.

## Decision

**No-go** for drop-depth suppression at 500 m with two 6,000 L drops per cell.

A valid next test needs one of:

- a 100 m grid or subcell wetness aggregation;
- many more litres per 500 m cell;
- a line of overlapping drops rather than two drops per cell.

Do not tune the depth threshold to make this pass.

## Limits

- One case and synthetic barrier.
- No tanker, helicopter, refill or dispatch.
- Fine-grid test not completed.
- No calibration and no operational claim.
