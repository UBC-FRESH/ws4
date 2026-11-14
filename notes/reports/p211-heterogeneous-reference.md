# P211 report: heterogeneous spatial reference

Date: 2026-11-14
Phase: P211 (#1222)
Branch: `feature/p211-heterogeneous-reference`
Design note: `notes/design/ws4-heterogeneous-reference.md`

## Result

The heterogeneous Biomass_core reference is deterministic and the aligned WS4 process matches it
within **0.113%** at year 10.

## Reference

- 20 × 20, 100 m, 400 pixels.
- Four pixel groups, two species.
- Initial ages 10–100, B 500–5000 g/m².
- Seed `20261114`.
- Year 10: biomass **10822**, ANPP **928**, mortality **342**, regeneration **1**.

## WS4 comparison

- After init: **4420.0** vs 4420.
- Year 10: **10809.75** vs 10822.
- Relative error: **-0.113%**.

## Evidence

- `tests/test_landis_heterogeneous_comparison.py`: 1 passed.
- Two independent R runs are byte-identical.
- Full dashboard: **OVERALL: GREEN**.

## Boundary

Hand-built four-group landscape, not a real forest. Regeneration and cohort-death bookkeeping are
still missing from the process. No calibration or observed-data claim.

## Next

Add cohort death and regeneration bookkeeping, or run a larger multi-ecoregion case. The residual
should be decomposed before claiming full module parity.
