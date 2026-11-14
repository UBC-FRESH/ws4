# P198 close-out: LANDIS kernel parity against the open-source R reference

Date: 2026-11-14
Phase: P198 (#1173)
Branch: `feature/p198-landis-r-parity`
Tasks: P198.1 (#1174), P198.2 (#1175), P198.3 (#1176)
Design note: `notes/design/ws4-landis-r-parity.md`
Report: `notes/reports/p198-landis-r-parity.md`

## Result

The published Biomass_core R kernel was executed in an isolated LandR/SpaDES.core stack and
matched the WS4 Python kernel on randomized identical cases. No "SpaDES unavailable" caveat
remains.

## What changed

- Captured 15 fixture files from a live R run in `tests/fixtures/landis_r_parity/`.
- Added `tests/test_landis_r_parity.py` with 5 parity tests.
- Recorded package versions and Biomass_core commit provenance.
- Updated the benchmark registry and LANDIS reference page.

## Evidence

- R parity tests: 5 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Functions covered: age mortality, ANPP, growth mortality, competition, sumB.
- Maximum absolute difference: **4.73e-11**.
- sumB and competition differences are at floating-point noise or zero.

## Boundary

This is kernel parity, not a spatial landscape run. Seed dispersal, serotiny, resprouting, and
full LBSE trajectory behaviour remain unverified. The R stack is verification infrastructure,
not a WS4 runtime dependency.

## Next

Run a pinned, small spatial Biomass_core landscape to capture a trajectory reference. That is the
remaining step before a WS4-vs-LBSE landscape comparison.

## Pull request

PR: #1178 is queued for maintainer approval. Do not merge without approval.
