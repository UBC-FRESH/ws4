# Compiled yield curves in the process bridge

Status: implemented (P234)
Phase: P234 (#1335)
Date: 2026-11-15
Related: `notes/design/ws4-age-volume-curves.md`

## 1. Purpose

P231 used a hand-written test curve. P234 loads the compiled dataset `curves.parquet` into the
process bridge and runs the shared schedule against the actual natural yield curve.

## 2. Loader

`age_volume_curves_from_frame(frame, species_curves)`:

- requires `curve_id`, `x`, and `y`;
- selects one compiled curve per species;
- requires non-negative integer ages;
- requires finite non-negative volumes;
- rejects duplicate ages.

The compiled natural curve for `PL` is `0 -> 0`, `40 -> 120`, `80 -> 220`.

## 3. Shared-schedule result

After `CC` on block 1:

- estate `feature.Volume`: **340**;
- process `bridge.volume_m3`: **340**;
- P223 absolute difference: **0**.

The process age 60 cohort interpolates the compiled curve to 170, and the harvested age-0 cohort
uses the compiled zero.

## 4. Evidence

- Bridge loader tests pass.
- Shared-schedule compiled-curve test passes.
- Two shared-schedule tests in total.
- Full dashboard: **OVERALL: GREEN**.

## 5. Limits

- The curve is loaded for a single species (`PL`).
- No track-change semantics beyond the harvested age-0 case.
- No fire, succession, or regeneration in this comparison.
- Not an observed-data validation.
