# scfm fire-regime benchmarks

Status: implemented (P187)
Phase: P187 (#1107)
Date: 2026-11-13
Related: `notes/design/ws4-predictive-ecology-benchmarks.md`,
`ws4/fire/regime.py`

## 1. Purpose

P185 registered the Predictive Ecology scfm fire-regime tests as a benchmark layer. P187
implements the formulas in original Python and reproduces the published toy values.

This is a **distributional** benchmark. It is not an event-perimeter comparison and does not
replace the P156 FBP growth kernel.

## 2. Parameter formulas

`fire_regime_parameters` computes:

- ignition rate: fires per hectare per year;
- escape probability: fraction of fires larger than one cell;
- mean and maximum escaped-fire size;
- empirical burn rate;
- annual per-pixel ignition probability;
- maximum burn cells from the mean escaped size.

A polygon with no fires has zero ignition rate and probability and NaN size statistics.

## 3. Diagnostics

`fire_regime_diagnostics` compares simulated fires with a historical regime:

- target/achieved ignitions per year;
- target/achieved escapes per year;
- simulated and historical mean escaped size;
- historical median escaped size;
- achieved and target fire return interval.

The historical burn rate can be supplied explicitly when the regime target is a separate
calibration input, as in the scfm diagnostic test.

## 4. Exact reference values

`tests/test_fire_regime.py` reproduces the scfm toy polygon:

- 20 × 20 pixels of 250 m (6.25 ha);
- 180 flammable pixels in polygon 1;
- historical sizes 1, 2, 50, 100 ha over 10 years;
- ignition rate 4 / (10 × 1125);
- escape probability 0.5;
- mean escaped size 75 ha;
- max burn cells 12.

It also reproduces the scfm diagnostic toy simulation:

- 2500 ha burnable;
- two simulated years;
- three fires, two escaped;
- target ignitions 1/year;
- achieved ignitions 1.5/year;
- achieved escapes 1/year;
- model mean 75 ha;
- historical mean/median 30 ha;
- achieved FRI 33.33 years;
- target FRI 100 years.

## 5. Limits

- No R or SpaDES runtime dependency.
- Only the scfm parameter and diagnostic formulas are implemented.
- LandMine FRI/reburn invariants remain a documented follow-up.
- The formulas are distributional; they do not simulate spatial fire growth.
- The benchmark layer remains separate from event-perimeter validation.
