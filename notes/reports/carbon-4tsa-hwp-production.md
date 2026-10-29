# Four-TSA full-landscape HWP carbon sweep

Date: 2026-10-29
Status: exact full-landscape runs complete
Scope: TSA08, TSA16, TSA40, TSA41; 50-year all-block schedules; public-default HWP

## Setup

- Datasets: `tsaXX-p120-matrix-full`
- Packages: `tsaXX-p120-matrix-package`
- Schedules: `tsaXX-all.schedule.csv`
- HWP: `config/carbon/hwp.bc.yaml` (public defaults, `df=1.0`)
- Horizon: `--years 50`
- Engine: libcbm 2.10.2, CBM defaults 1.2.9300.391

These are the exact carbon runs, not optimizer ledger runs. HWP adds lifecycle accounts
only; the ecosystem series is bit-identical to the prior no-HWP full schedules.

## Results

| TSA | Area (ha) | Ecosystem @50 (tC) | HWP @50 (tC) | System @50 (tC) | Cumulative system emissions @50 (tCO2e) | Wall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TSA08 | 4,341,402.9 | 844,189,238.06 | 38,268,592.62 | 882,457,830.68 | 633,877,786.90 | 662 s |
| TSA16 | 2,807,096.4 | 404,510,934.23 | 24,024,128.48 | 428,535,062.70 | 669,797,138.70 | 591 s |
| TSA40 | 2,497,704.2 | 379,138,290.35 | 23,389,313.49 | 402,527,603.84 | 546,298,365.94 | 737 s |
| TSA41 | 1,954,327.1 | 282,497,146.99 | 20,898,154.38 | 303,395,301.38 | 470,295,556.45 | 374 s |

`system = ecosystem + HWP` holds to ≤6e-8 tC.

At offset 49 (the last year before the terminal snapshot), ecosystem values are:

- TSA08 841,131,904.55 tC
- TSA16 402,770,853.58 tC
- TSA40 376,751,822.61 tC
- TSA41 280,729,664.81 tC

The prior no-HWP references were offset 50, not offset 49. At offset 50 the new ecosystem
values match them to 0.1 tC rounding.

## Package identities

- TSA08: `femic-carbon-08-11a11f1d4fbf`
- TSA16: `femic-carbon-16-f49c604fcd16`
- TSA40: `femic-carbon-40-01e9bb44a09b`
- TSA41: `femic-carbon-41-0e5b491e6a34`

Fingerprints and full account tables are in the run manifests under
`carbon-handoff/ws4-tsaXX-full-50y-hwp/`.

## Reading

- HWP is a meaningful share of the 50-year system stock: 38.3M tC on TSA08, 24.0M on
  TSA16, 23.4M on TSA40, and 20.9M on TSA41.
- Cumulative emissions differ materially by TSA; TSA16 has the highest cumulative total
  despite a smaller area than TSA08 because its ecosystem drawdown is larger.
- These are full-landscape exact carbon baselines, not optimized schedules and not
  policy recommendations.
- HWP defaults are public scenario assumptions. A high-displacement sensitivity sweep
  has not yet been run for these four landscapes.

## Artifacts

- `/srv/shared-data/gep/ws4/carbon-handoff/ws4-tsa08-full-50y-hwp/`
- `/srv/shared-data/gep/ws4/carbon-handoff/ws4-tsa16-full-50y-hwp/`
- `/srv/shared-data/gep/ws4/carbon-handoff/ws4-tsa40-full-50y-hwp/`
- `/srv/shared-data/gep/ws4/carbon-handoff/ws4-tsa41-full-50y-hwp/`
- `/srv/shared-data/gep/ws4/carbon-handoff/ws4-hwp-4tsa-50y-report.md`
