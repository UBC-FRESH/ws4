# LANDIS R kernel parity

Status: implemented (P199)
Phase: P199 (#1173)
Date: 2026-11-14
Related: `notes/design/ws4-predictive-ecology-benchmarks.md`,
`tests/test_landis_r_parity.py`

## 1. Purpose

P185/P189 compared the WS4 LANDIS kernel to numeric values transcribed from the public
Biomass_core tests. P199 removes the "R/SpaDES unavailable" caveat by running the published R
functions directly and comparing them with the WS4 kernel on identical randomized cases.

This is kernel parity, not a full landscape LBSE run.

## 2. R stack

The verification used an isolated library outside the repository:

- R 4.3.3;
- LandR 1.2.0.9064;
- SpaDES.core 3.2.1.9067;
- SpaDES.tools 2.2.0;
- reproducible 3.2.1.9087;
- data.table 1.14.10;
- fpCompare 0.2.6;
- pipeR 0.6.1.3;
- MuMIn 1.48.4.

The Biomass_core source was the registered commit
`21b3392324c2787a47751be808cbf9e595f308c0`. Only `R/helpers.R` was sourced; no third-party code
is copied into WS4.

## 3. Cases

The fixture contains:

- 40 randomized age-mortality rows, spin-up and non-spin-up;
- 40 randomized ANPP rows, both stages;
- 40 randomized growth/mortality rows, both stages;
- 23 competition rows, both stages;
- 30 sumB rows at current times 18 and 19.

Inputs and R outputs are in `tests/fixtures/landis_r_parity/`. The Python test consumes the
captured outputs, so CI does not need R.

## 4. Results

Maximum absolute differences between WS4 and the R kernel:

| Comparison | Max abs difference |
| --- | --- |
| age mortality, spin-up | 4.73e-11 |
| age mortality, non-spin-up | 4.73e-11 |
| ANPP, spin-up | 4.97e-13 |
| ANPP, non-spin-up | 4.97e-13 |
| growth mortality, spin-up | 4.55e-13 |
| growth mortality, non-spin-up | 4.55e-13 |
| competition bAP, spin-up | 3.61e-16 |
| competition bPM, spin-up | 4.72e-16 |
| competition bAP, non-spin-up | 4.44e-16 |
| competition bPM, non-spin-up | 4.72e-16 |
| sumB at 18 | 0 |
| sumB at 19 | 0 |

## 5. Limits

- This is a kernel-level comparison; it does not run a spatial Biomass_core landscape.
- Seed dispersal, serotiny, resprouting, and full LBSE trajectory behaviour are not covered.
- The isolated R stack is verification infrastructure, not a WS4 runtime dependency.
- The next reference step is a pinned landscape run, not more transcription of unit values.
