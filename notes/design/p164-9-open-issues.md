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
- post-2018 recalibration and a support-map-independent temporal comparison;
- a five-TSA northeast BC AOI expansion (TSA 08, 16, 24, 40, 41);
- an estate-wide ignition/weather ensemble with a defensible scenario-selection rule;
- a TSA24 external benchmark, or a documented, reproducible failure that is not presented as a benchmark;
- a paper whose claims match the artifacts.

## Open issues

### P164.9-A: Post-2018 calibration — **done, negative result; event reconstruction retired from canonical evidence**

**Problem.** The canonical global model is fitted to all years. The 2018+ period has a larger
fire-size tail, and the user wants future predictions based on the post-2018 regime. We have not yet
fitted a post-2018-only model or compared the post-2018 size distribution against it.

**Plan.**

1. Build period-filtered inputs:
   - potential records with dates 2018-01-01 through 2024-12-31;
   - unique fires with years 2018--2024, at or above 6.25 ha.
2. Fit a global seven-parameter retention model on the post-2018 sample with the same 5,000-candidate,
   common-random-number workflow as the canonical all-year fit.
3. Summarize the post-2018 in-sample calibration and compare it with the all-year model.
4. Compare the all-year and post-2018 maps on the post-2018 size distribution.
5. Do not use the legacy support-map event reconstruction as canonical evidence. The earlier event
   run depended on the frozen support map; a fresh event reconstruction would be required before it
   could support a claim.

**Acceptance.**

- `results/potential-post2018.json`, `raw/history-unique-post2018/`,
  `results/region-retention-post2018.json`, `results/temporal-post2018-summary.json`.
- A post-2018 size summary and paper text that states the calibration period and that the
  comparison is in-sample.
- The legacy event outputs are retained only as a support-conditioned diagnostic.
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
   - post-2018 recalibration;
   - estate-wide ensemble;
   - external benchmark result or documented failure.
2. Keep the pre/post contrast central: do not claim future skill from the all-year model.
3. Add tables/figures only where they carry evidence; update figure scripts from JSON.
4. Rebuild PDF and check warnings/references.

### P164.9-E: Reproducibility and archive — **main artifacts and hashes updated**

**Plan.**

1. Add period filters, post-2018 map, legacy event outputs, ensemble manifest, and external test inputs to
   the archive.
2. Regenerate `INPUT_MANIFEST` and `MANIFEST`; verify.
3. Update archive README and superseded-status notes.
4. Keep large/raw caches out of Git; hash them locally.

### P164.9-G: Canonical support map — **done**

**Result.** The positive-overlap, cell-share builder is canonical. It assigns every block to every
cell with positive overlap, caps each cell at total weight one, and conserves block area within 20%
for 99.7% of blocks (median error 0.4%). The legacy frozen map has median block-area error 64.1%
and is retained only as a sensitivity artifact. Canonical support-map SHA-256:
`f47b36eb75a80709a0c2a289671487ef9348bfd0720b162dc52d5e1ddb5c41f4`.

**Applied reruns.** Estate 728 events / 6,360.7 ha; risk median 10,822.6 ha / worst-of-five loss
2.069 million m3; optimizer 113 tiles / 2,075.9 ha, fire-blind schedule invariant.

**Verification and portability.** The committed independent verifier checks coverage, cell-weight
caps, duplicates, and block-area error; it rejects a deliberately corrupted map. The same builder
compiled the public TSA27 block layer (37,461 blocks; 89,139 cells; 259,758 memberships; all blocks
represented). TSA27 is a portability check, not a TSA24 result.

### P164.9-H: Five-TSA northeast BC AOI — **AOI compilation done; process calibration open**

**Result.** The five TSA boundaries dissolve to one **31.9-million-ha** AOI. Public VRI/TSA24
geometry gives 1,550,199 blocks and 17.5 million ha of productive forest. The 250 m support map has
3,763,756 cells, 10,777,196 memberships, 2,948,489 multi-fragment cells, maximum 18, all blocks
represented, and 99.4% of blocks within 20% area. Public BC Wildfire perimeters give 3,834
fire-number/year records and 3,015 fires >=6.25 ha. Five compiled estates load in the WS4 process
engine; the no-fire baseline is 2.652 billion m3 and 1.181 billion t.

**Boundary.** The TSA24 process model remains the calibration core. The other four TSAs contribute
empirical fire-regime targets and estate baselines, not a validated process-model application.
Matched AOI weather and layer caches are not yet built.

**Evidence.** `aoi/README.md` in the reproducibility archive; AOI support SHA-256
`22d9fd23b0b25f5117913625cc02779c3082d7c8d5c4f6766ea74389ba99685f`.

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

1. P164.9-A post-2018 calibration.
2. P164.9-B ensemble redesign and rerun.
3. P164.9-C FireSTARR debug.
4. P164.9-D paper integration.
5. P164.9-E archive/manifest.
6. P164.9-F review.
