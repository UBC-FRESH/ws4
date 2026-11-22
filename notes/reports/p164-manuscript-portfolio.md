# P164 manuscript portfolio

Status: four private `UBC-FRESH` LaTeX manuscript repositories, drafts only.

All four build a PDF in GitHub Actions. None is submitted or public. Author metadata, target-journal
format, archive DOIs, and final data sign-off are still pending.

| Paper | Repository | Draft | Claim boundary |
| --- | --- | --- | --- |
| 1. Open integration | `UBC-FRESH/fresh_ws4_fire_regime_manuscript` | 15 pages | Open, suppression-aware integration and calibration/transfer diagnosis; not a validated forecast |
| 2. Calibration/transfer | `UBC-FRESH/fresh_ws4_fire_calibration_manuscript` | 9 pages | Regional suppression calibration is a fit, not a forecast; transfer is negative |
| 3. Optimization/scale | `UBC-FRESH/fresh_ws4_fire_optimization_manuscript` | 7 pages | Sharded process-based fire-risk workflow; fire-evaluated, not fire-aware; not a global optimum |
| 4. Data/benchmark | `UBC-FRESH/fresh_ws4_fire_benchmark_manuscript` | 8 pages | Reproducible TSA24 benchmark and data descriptor; not a validated fire forecast |

## Archive

Reproducibility archive: `https://github.com/UBC-FRESH/fresh_ws4_fire_regime_repro` (private). It contains compact results, a source catalogue, stage scripts, and a verified hash manifest. The README explicitly states that the full raw-data rerun is not complete.

## Common structure

The repositories follow the `fresh_daugherty_manuscript` pattern:

- small `main.tex`;
- section files under `sections/`;
- separate `title-page.tex`;
- figures and `references.bib`;
- `Makefile` with `make pdf`, `make title`, `make clean`;
- GitHub Actions build and PDF artifact;
- `planning/` and `review/` notes.

## Paper 1

*An open, suppression-aware fire regime for forest estate optimization: integration, calibration,
and transfer diagnostics.*

- six figures;
- full-layer TSA24 case;
- five-seed risk ensemble;
- sharded optimizer case;
- Dogrib FireSTARR external benchmark;
- negative transfer and hierarchical results in the main text.

## Paper 2

*Regional suppression calibration is a fit, not a forecast: transfer and tail diagnostics in an open
FBP-based fire regime.*

- global no-go;
- regional in-sample residuals;
- fixed 11-tile transfer test;
- hierarchical ridge;
- conclusion: potential/weather covariates do not identify a transferable suppression regime.

## Paper 3

*A sharded, process-based fire-risk workflow for large forest estates: a TSA24 case study.*

- 112 of 133 tiles optimized;
- 179 scheduled events;
- 20,775.6 ha harvested;
- 74.25 ha burned;
- 655.5 s on 36 workers;
- explicit non-global-optimum boundary;
- fire-blind repeat produced the same schedule, showing the local objective is harvest-only.

## Paper 4

*A reproducible TSA24 open fire-regime benchmark: layers, calibration, and estate-scale cases.*

- 133-tile layer cache;
- full support coverage;
- calibration and transfer summaries;
- risk and estate-scale cases;
- reproducibility manifest and licence audit;
- data descriptor format.

## Submission blockers

- Author list, affiliations, ORCIDs, CRediT contributions, funding, competing interests.
- Target-journal format for each paper.
- Data-owner/licence sign-off and archive DOI.
- TSA24-specific external benchmark.
- Global or near-global optimization baseline for Paper 3.
- Clean-machine reproduction audit.
- Final proof of figures, tables, and references.
