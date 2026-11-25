# P164.9 open issues and execution plan

Phase identifier: P164
Task: P164.9
Date: 2026-11-25
Parent issue: #977
Task issue: #1436

## Objective

Produce one defensible TSA24 paper with:

- fire-level calibration and validation;
- a pre-2018 versus post-2018 calibration comparison;
- post-2018 event reconstruction under both calibrations;
- an estate-wide ignition/weather ensemble with a defensible scenario-selection rule;
- a TSA24 external benchmark, or a documented, reproducible failure that is not presented as a benchmark;
- a paper whose claims match the artifacts.

## Open issues

### P164.9-A: Post-2018 calibration and event comparison — **done, negative result**

**Problem.** The canonical global model is fitted to all years. The 2018+ period has a larger
fire-size tail, and the user wants future predictions based on the post-2018 regime. We have not yet
fitted a post-2018-only model or compared post-2018 events against it.

**Plan.**

1. Build period-filtered inputs:
   - potential records with dates 2018-01-01 through 2024-12-31;
   - unique fires with years 2018--2024, at or above 6.25 ha.
2. Fit a global seven-parameter retention model on the post-2018 sample with the same 5,000-candidate,
   common-random-number workflow as the canonical all-year fit.
3. Summarize the post-2018 in-sample calibration and compare it with the all-year model.
4. Run the frozen 10 post-2018 event reconstructions with:
   - the all-year map (current canonical);
   - the post-2018 map.
5. Compare simulated-versus-observed event areas, median absolute bias, median bias, range, and
   number of events within a factor of two.
6. State clearly that the post-2018 event comparison is in-sample if the event fires are in the
   calibration target. If feasible, run a leave-events-out variant as a sensitivity check.
7. Add the comparison to the paper as a regime-shift diagnostic, not as independent validation unless
   the event fires were excluded from the fit.

**Acceptance.**

- `results/potential-post2018.json`, `raw/history-unique-post2018/`,
  `results/region-retention-post2018.json`, `results/temporal-post2018-summary.json`.
- Event results for both maps, with per-event biases and summary statistics.
- A table/figure and paper text that states the calibration period and whether the comparison is
  in-sample.
- No claim that post-2018 calibration is validated merely because it fits the post-2018 data.

### P164.9-B: Estate-wide ignition/weather ensemble — **done with FWI-quantile rule**

**Problem.** The current 12-scenario ensemble uses three fixed mid-August dates. The 2021-08-15
scenario has FWI 3.2 and produces only 96--117 ha, while other dates produce up to 3,148 ha. This is
not a defensible weather sample; it was selected after seeing the record and is dominated by one low
fire-danger date.

**Plan.**

1. Define the scenario rule before evaluating outcomes:
   - sample fire-season dates from the post-2018 weather record, or
   - use explicit FWI quantiles (e.g., median, p90, p99) across the post-2018 fire seasons.
2. Use a fixed, documented ignition sampler across the full burnable estate.
3. Run at least 12 scenarios (3 weather states x 4 ignition sets) and retain the 5-seed suppression
   sensitivity separately.
4. Report the scenario definition, dates/quantiles, FWI/BUI/wind, and per-scenario results.
5. Add the ensemble to the paper as a weather/ignition sensitivity, not a calibrated risk estimate.

**Acceptance.**

- A scenario manifest with selection rule, dates/quantiles, and weather values.
- Result JSON with all scenarios and summary quantiles.
- Paper table/figure and text.
- No post-hoc date selection.

### P164.9-C: FireSTARR TSA24 external benchmark — **tile and one observed event run; no matched benchmark**

**Problem.** FireSTARR v0.9.29 now passes the original SIGFPE and grid loading on a TSA24 tile, but
fails with `map::at` while loading scenario 0. No external benchmark exists.

**Plan.**

1. Reproduce the minimal TSA24 FireSTARR fixture with tiled fuel/DEM/start rasters.
2. Inspect the FireSTARR scenario loader expectations: weather schema, start date, timezone,
   start perimeter, fuel LUT, and output offsets.
3. Try a known-good weather file and a point ignition to isolate whether the failure is weather or
   grid.
4. If FireSTARR cannot run, test Cell2Fire or another open FBP implementation on a TSA24 tile.
5. Record the exact command, input hashes, and failure/success. Do not present a failed run as a
   benchmark.

**Acceptance.**

- A runnable external comparison on at least one TSA24 tile, or a minimal reproducible failure with
  the bug isolated.
- Paper text that says exactly what was compared.

### P164.9-D: Paper integration — **done pending final review**

**Plan.**

1. Update the paper with:
   - unique-fire calibration;
   - temporal holdout failure;
   - post-2018 calibration and event comparison;
   - estate-wide ensemble;
   - external benchmark result or documented failure.
2. Keep the pre/post contrast central: do not claim future skill from the all-year model.
3. Add tables/figures only where they carry evidence; update figure scripts from JSON.
4. Rebuild PDF and check warnings/references.

### P164.9-E: Reproducibility and archive — **main artifacts and hashes updated**

**Plan.**

1. Add period filters, post-2018 map, event outputs, ensemble manifest, and external test inputs to
   the archive.
2. Regenerate `INPUT_MANIFEST` and `MANIFEST`; verify.
3. Update archive README and superseded-status notes.
4. Keep large/raw caches out of Git; hash them locally.

### P164.9-F: Review

**Plan.**

1. Run a fresh adversarial review of the updated paper, archive, and code.
2. Address Critical/High findings.
3. Do not submit until the review passes and the archive/DOI decisions are approved.

## Out of scope

- Fire-aware optimizer objective for this paper.
- Resource-allocation suppression mechanism; the paper uses a fitted retention-size distribution.
- Public archive visibility, DOI, and release until explicit approval.

## Execution order

1. P164.9-A post-2018 calibration and event comparison.
2. P164.9-B ensemble redesign and rerun.
3. P164.9-C FireSTARR debug.
4. P164.9-D paper integration.
5. P164.9-E archive/manifest.
6. P164.9-F review.
