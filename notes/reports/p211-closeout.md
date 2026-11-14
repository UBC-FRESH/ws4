# P211 close-out: heterogeneous spatial reference

Date: 2026-11-14
Phase: P211 (#1222)
Branch: `feature/p211-heterogeneous-reference`
Tasks: P211.1 (#1223), P211.2 (#1224), P211.3 (#1225)
Design note: `notes/design/ws4-heterogeneous-reference.md`
Report: `notes/reports/p211-heterogeneous-reference.md`

## Result

The heterogeneous four-group Biomass_core reference is deterministic, and the aligned WS4
process matches it within **0.113%** at year 10.

## What changed

- `scripts/landis_heterogeneous_reference.R`.
- Fixture in `tests/fixtures/landis_heterogeneous_reference/`.
- `tests/test_landis_heterogeneous_comparison.py`.
- Design note, report, registry entry, and reference documentation.

## Evidence

- Heterogeneous comparison test: 1 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Reference year 10: **10822** biomass.
- WS4 year 10: **10809.75**.
- Relative error: **-0.113%**.
- Two independent R runs are byte-identical.

## Boundary

Four hand-built pixel groups, not a real landscape. Regeneration and cohort-death bookkeeping
remain missing from the process. No calibration or observed-data claim.

## Next

Add cohort death and regeneration bookkeeping, or run a larger multi-ecoregion case. The residual
should be decomposed before claiming full module parity.

## Pull request

Merged as `adf0ab5` (PR #1226); branch deleted.
