# P198 report: LANDIS kernel parity against the open-source R reference

Date: 2026-11-14
Phase: P198 (#1173)
Branch: `feature/p198-landis-r-parity`
Design note: `notes/design/ws4-landis-r-parity.md`

## Result

The published Biomass_core R kernel executes in the isolated R stack and matches the WS4 Python
kernel on identical randomized cases. SpaDES is open source; the previous "runtime unavailable"
caveat is removed.

## Runtime

- R 4.3.3
- LandR 1.2.0.9064
- SpaDES.core 3.2.1.9067
- SpaDES.tools 2.2.0
- reproducible 3.2.1.9087
- data.table 1.14.10
- fpCompare 0.2.6
- pipeR 0.6.1.3
- MuMIn 1.48.4

Biomass_core commit: `21b3392324c2787a47751be808cbf9e595f308c0`.

## Method

1. Installed the R stack into an isolated library outside the repository.
2. Sourced the published `Biomass_core/R/helpers.R` functions.
3. Generated identical randomized cohort tables for each kernel function.
4. Ran the R functions and captured their CSV outputs.
5. Ran the WS4 Python functions on the same inputs and asserted parity at `1e-8`.

The captured inputs and R outputs are in `tests/fixtures/landis_r_parity/`; CI validates them
without requiring R.

## Evidence

`tests/test_landis_r_parity.py`: 5 passed.

| Comparison | n | Max abs difference |
| --- | --- | --- |
| age mortality, spin-up | 40 | 4.73e-11 |
| age mortality, non-spin-up | 40 | 4.73e-11 |
| ANPP, spin-up | 40 | 4.97e-13 |
| ANPP, non-spin-up | 40 | 4.97e-13 |
| growth mortality, spin-up | 40 | 4.55e-13 |
| growth mortality, non-spin-up | 40 | 4.55e-13 |
| competition bAP, spin-up | 23 | 3.61e-16 |
| competition bPM, spin-up | 23 | 4.72e-16 |
| competition bAP, non-spin-up | 23 | 4.44e-16 |
| competition bPM, non-spin-up | 23 | 4.72e-16 |
| sumB at 18 | 30 | 0 |
| sumB at 19 | 30 | 0 |

## What this proves

- The R stack loads and the published Biomass_core functions execute.
- WS4 matches the R kernel across randomized inputs for the five implemented kernel functions.
- The exact test values are now backed by a live reference run, not only transcribed numbers.

## What this does not prove

- No spatial Biomass_core landscape was run.
- Seed dispersal, serotiny, resprouting, and full LBSE trajectory behaviour are not covered.
- The R stack is verification infrastructure, not a WS4 runtime dependency.

## Next

Run a pinned, small spatial Biomass_core landscape to obtain a trajectory reference. That is the
remaining reference step before a WS4-vs-LBSE landscape comparison.
