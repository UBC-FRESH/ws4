# Antagonistic external review: WS4 fire-research program and four drafts

Date: 2026-11-23

Status: read-only scientific review. No manuscript, code, data, or git state was modified. The only file created is this report.

## 1. Reviewer identity and scope

**Reviewer identity.** Anonymous external peer reviewer and program evaluator. Expertise assumed for this review: forest estate optimization, fire behaviour and fire-regime modelling, calibration and transfer statistics, and computational reproducibility. No author relationship and no financial conflict are declared. The reviewer is deliberately hostile in the sense of looking for reasons to reject, but is required to be fair about what the evidence actually supports.

**Scope.** Reviewed:

- `notes/design/ws4-fire-research-program.md` (program plan);
- `fresh_ws4_fire_regime_manuscript` (`main.tex`, `title-page.tex`, all `sections/*.tex`, `planning/`, `README.md`, `references.bib` as needed);
- `fresh_ws4_fire_calibration_manuscript` (same);
- `fresh_ws4_fire_optimization_manuscript` (same);
- `fresh_ws4_fire_benchmark_manuscript` (same);
- `fresh_ws4_fire_regime_repro` (`README.md`, `README-BENCHMARK.md`, `MANIFEST.json`, `MANIFEST.sha256`, `protocol/event-validation.md`, `config/`, `results/`, selected scripts, selected raw history files);
- `notes/reports/tsa24-event-validation.md`;
- `notes/reports/tsa24-full-support-map.md`;
- `notes/reports/tsa24-block-support-50m.md`;
- the p164.8 reports and the FireSTARR/Dogrib reports;
- current result JSONs and selected git history/commits in the archive.

**Method.** I checked manuscript numbers against the archive JSON and code where possible, read the archive's own status statements, and recomputed simple statistics (bootstrap intervals, sign tests, paired differences, and sensitivity to excluded events) from the result JSON. I did not rerun the full model, did not rebuild the layer cache, did not rerun FireSTARR, and did not independently verify every raw VRI/SRTM/weather download. Those limits are stated where they matter.

**Evidence standard.** A claim is treated as supported only when the archive contains an artifact or code path that can produce it, and the artifact is consistent with the text. "The authors say so" is not evidence. A number that appears only in a manuscript or a prose report, with no matching artifact, is treated as unverified.

## 2. Executive verdict table

| Paper | Declared venue | Decision | One-line reason |
| --- | --- | --- | --- |
| 1. Open integration / regime (`fresh_ws4_fire_regime_manuscript`) | *Environmental Modelling & Software* | **Major revision; do not submit now; merge the defensible calibration core** | The integration is real, but the "independent" event validation is in-sample and leaky, the positioning table overclaims, and several headline numbers are stale or not traceable. It can be salvaged only as an honest methods/integration and negative-diagnostic paper. |
| 2. Calibration / transfer (`fresh_ws4_fire_calibration_manuscript`) | *International Journal of Wildland Fire* | **Reject/merge as standalone; major revision only after a genuinely independent validation** | The negative transfer result is the best scientific signal in the portfolio, but the paper calls the regional map "held-out" when it was fitted on the validation tiles, and the event section reuses the calibration fires. As written it is a section of Paper 1, not a separate IJWF paper. |
| 3. Optimization / scale (`fresh_ws4_fire_optimization_manuscript`) | *Canadian Journal of Forest Research* | **Reject/merge; kill as a standalone optimization paper** | The objective is harvest-area feasibility, the fire source is three fixed ignitions with constant weather, the decision space is about 0.5% of blocks, and there is no baseline, quality bound, or near-global comparison. The paper proves a data path, not a fire-aware optimization. |
| 4. Data / benchmark (`fresh_ws4_fire_benchmark_manuscript`) | *Data in Brief* | **Kill as standalone; convert to a technical report or merge into Paper 1** | The data are not public, the support map and 24 calibration tiles are frozen derived inputs, there is no DOI, reuse example, or known-failure table, and the Dogrib one-fire check is not a TSA24 benchmark. It is neither a data descriptor nor a model-evaluation paper. |

**Portfolio verdict.** Four papers from one model, one dataset, one calibration, and one set of results are not justified. The four drafts overlap almost completely; submitting them as four papers would create a duplicate-publication/salami-slicing problem. The defensible portfolio is one paper (integration plus a rigorously framed negative diagnostic) plus one public data/software archive, or at most two papers if a genuinely independent validation and a genuinely fire-aware optimization are added.

## 3. Cross-cutting fatal issues

These issues recur in every paper. They are not cosmetic.

### 3.1 The event validation is not independent: the calibration data contain the validation fires

The strongest claim in the portfolio is that ten TSA24 events provide an "independent point-ignition test." The archive contradicts this.

`calibrate_regions.py` reads every historical fire size for each tile and fits the six suppression parameters to them:

- `fresh_ws4_fire_regime_repro/scripts/calibrate_regions.py:73-80` reads `raw/history/{tile}.json`, takes `sizes_ha`, and fits if `len(sizes) >= 5`. There is no year filter and no exclusion of the validation events.
- `fresh_ws4_fire_regime_repro/raw/history/t19.json` contains 24 sizes, including `4767.80209097183`.
- `fresh_ws4_fire_regime_repro/results/event-selection.json` selects `G41511` with `area_ha = 4767.8` in tile `t19`.
- The regional map for `t19` in `results/region-calibration.json` was fitted on that same `t19` history.

This is not a coincidence for one event. Eight of the ten event areas appear in the tile history files within 0.1%:

| Event | Observed ha | Matching history file/value |
| --- | ---: | --- |
| G41511 | 4767.8 | `raw/history/t19.json`: 4767.802 |
| G41422 | 780.0 | `raw/history/t17.json`: 780.037 |
| G40639 | 327.3 | `raw/history/t17.json`: 327.321 |
| G40226 | 236.0 | `raw/history/t17.json`: 235.995 |
| G51212 | 151.7 | `raw/history/t18.json`: 151.692 |
| G40324 | 142.7 | `raw/history/t19.json`: 142.68 |
| G12186 | 122.7 | `raw/history/t03.json`: 122.719 |
| G13085 | 112.3 | `raw/history/t14.json`: 112.382 |

`G41560` and `G41728` do not match exactly in the majority tile, but that does not rescue the design: the map for their tiles was still fitted on all historical fires in those tiles, and the event selection does not exclude any validation year.

Worse, `G12186` is in tile `t03`, which is one of the **training** tiles (`config/tiles.json:3`). The event selection rule only splits by year (`select_event_validation.py:32`), not by tile. The protocol says events are assigned to the majority tile and the spatial holdout is `t01`-`t12` vs `t13`-`t23` (`protocol/event-validation.md:30-35`), but the event test includes a training-tile fire.

The manuscript's claims are therefore false as written:

- Regime abstract, `sections/0_abstract.tex:18`: "An independent point-ignition test on ten TSA24 events also failed."
- Calibration abstract, `sections/0_abstract.tex:16-17`: "A point-ignition test on ten independent TSA24 events also failed."
- Calibration methods, `sections/2_methods.tex:72-74`: "From 247 independent perimeters of at least 100 ha, 18 had a matched incident record; ten validation fires..."
- Calibration discussion, `sections/4_discussion.tex:11`: "The independent event check strengthens the conclusion."

The correct description is **in-sample event reconstruction on ten events, at least eight of which were in the calibration history, with one in a training tile**. That is still a negative result, and arguably a more damning one, but it is not an independent validation. A referee who checks the archive will treat the word "independent" as a misrepresentation.

**Fatal or fixable?** Fatal to the "independent validation" claim. The underlying negative result can be salvaged by reframing it as an in-sample reconstruction, but then it cannot be the paper's independent evidence.

### 3.2 The regional model is post hoc and was fitted on the validation tiles

The pre-registered P164.8 protocol specifies a **global** six-parameter model, 12 training tiles, 11 validation tiles, gates on both, and a no-go if training fails (`notes/design/ws4-regime-calibration-protocol.md:41-49, 111-131`). The global fit failed training maximum and over-5,000 (`notes/reports/p164-8-regime-calibration.md:33-47`). The response was to fit one parameter set per tile, including the validation tiles, with no gate.

The papers then describe the result as a held-out transfer test:

- Regime abstract, `sections/0_abstract.tex:13-14`: "Independent transfer to 11 held-out tiles was negative..."
- Calibration abstract, `sections/0_abstract.tex:12`: "On the fixed 11-tile holdout, the in-sample score was 1.50..."
- Calibration methods, `sections/2_methods.tex:43-46`: "The fixed split is t01-t12 for training and t13-t23 for validation... Parameters were frozen before validation."
- Regime methods, `sections/2_methods.tex:106-109`: "The fixed split was t01-t12 for training and t13-t23 for validation; t24 has no historical perimeter sample and is excluded. Parameters were frozen before validation."

The regional map in `results/region-calibration.json` has keys `t01` through `t23`, including `t13`-`t23`. Each validation tile's parameters were fitted on that tile's own historical data (`calibrate_regions.py:69-85`). Only the **global**, **training-median**, **potential-analogue**, and **historical-analogue** methods use training-only parameters; the "in-sample" row uses each validation tile's own fit. That is a legitimate in-sample diagnostic, but it is not a "held-out" model and it is not a validation of the regional map.

The paper's own methods admit the in-sample status (`calibration sections/2_methods.tex:39`: "The regional map is in-sample. No global pass/fail gate is applied to it"; `regime sections/2_methods.tex:102`: "No global pass/fail gate is applied to the regional map"). The abstract and title still use "held-out" and "independent transfer," which is misleading. A referee will ask: "Which model was frozen before validation?" The answer is: not the regional map.

**Fatal or fixable?** Fatal to the "held-out regional calibration" framing. The transfer test of the training-only methods is salvageable; the regional map itself must be described as a full-data in-sample fit.

### 3.3 There is almost no statistical inference

The portfolio relies on point estimates from small samples:

- Event validation: n = 10, one deterministic survival draw.
- Tile transfer: n = 11 validation tiles, no paired test.
- Risk ensemble: n = 5 seeds; the "CVaR95" is the worst observed seed.
- Hierarchical ridge: 12 training tiles, six parameters, seven predictors, lambda selected at the grid boundary.
- Regional calibration: 23 tile fits, each with as few as 6 historical fires, six parameters, 1,000 candidates, and five realizations per potential fire.

The manuscripts report no confidence intervals, no standard errors, no paired tests, no multiple-comparison correction, no power analysis, and no sensitivity to score weights. Recomputing simple statistics from the JSON shows why this matters:

- Event median relative bias: +25.3%, bootstrap 95% interval about **[-49.1%, +358.6%]**, which includes zero. A sign test of 6 overpredictions and 4 underpredictions gives p ≈ **0.75**. The directional claim "the model overpredicts" is not statistically supported.
- Event median absolute bias: 58.6%, bootstrap 95% interval about **[43.3%, 358.6%]**. Excluding the two 420-day records gives **66.9%**; excluding the single G40324 outlier gives **49.9%**. The headline 58.6% is sensitive to inclusion choices that the paper does not justify.
- Global vs potential/weather analogue: mean paired difference -1.322, bootstrap 95% interval **[-2.739, +0.145]**, which includes zero. The paper's statement that the analogue "performed worse than the global fit" (`regime sections/3_results.tex:88-89`; `calibration sections/3_results.tex:69-71`) is not statistically supported with 11 tiles.
- Hierarchical ridge vs complete pooling: mean difference -1.358, bootstrap 95% interval **[-2.972, +0.247]**, which includes zero. The paper's "did not outperform complete pooling" is a point-estimate statement, not a tested one.
- In-sample vs global: mean difference -3.792, 95% interval **[-5.737, -1.963]**, which is significant. The core overfitting diagnosis is robust; the ranking of the transfer methods is not.

**Fatal or fixable?** Fixable with the existing data (bootstrap, paired tests, sensitivity), but the papers cannot be submitted without it. The claims must be weakened where intervals include zero.

### 3.4 The "fire-aware optimization" does not exist

The optimization paper is explicit in places that the objective is harvest-only, but the title, abstract, and benchmark paper still present a "fire-risk workflow." The code is decisive:

- `full_estate_optimizer.py:122` selects `candidates[:MAX_BLOCKS]`, i.e., the 20 largest eligible CC blocks per tile.
- `full_estate_optimizer.py:163-168` sets a `Target(account="harvest.area_ha_total", minimum=0.1 * selected_area)`. This is a 10% harvest-area feasibility target, not an objective to maximize.
- `full_estate_optimizer.py:184-200` calls `optimize_process_schedule` with a fire source, but `:191` passes `FireConfig(ignition_rate_per_fragment_year=0.0, batch_fire=True)`, and the local target contains no fire term.
- `full_estate_optimizer.py:224-243` builds **three** fixed ignitions, one in each of regions 1, 13, and 22, with `active_days=2`, `fwi=30`, `bui=80`, `wind_kmh=10`. These are arbitrary demo values, not the calibrated regional fire regime.
- `full_estate_optimizer.py:244-259` uses one constant weather step (`ffmc=92`, `bui=80`, wind 10 km/h, RH 30%, no rain).
- `results/optimizer-full-estate-fireblind.json` has the same schedule SHA-256 as `results/optimizer-full-estate-schedule.csv` (`f804430c...` in `MANIFEST.json:70-83`), and the same accounts. The paper admits this at `sections/0_abstract.tex:15-17`.

The "optimizer" therefore does not optimize a fire-risk objective, does not use the calibrated event weather, and does not use the calibrated ignition process. It selects a small, arbitrary subset of blocks and finds a feasible schedule that meets a local 10% harvest target. The 74.25 ha burned is the output of three fixed two-day ignitions under constant weather, not a risk estimate.

**Fatal or fixable?** Fatal to the paper as an optimization paper. It can be a methods/feasibility note inside Paper 1, but not a CJFR optimization contribution.

### 3.5 The benchmark paper is not a data descriptor and not a benchmark

A data descriptor requires a citable, reusable dataset with a DOI, a data dictionary, licence terms, and a reuse example. This paper has none:

- The archive `fresh_ws4_fire_regime_repro` is **private** (`gh repo view` reports `visibility: PRIVATE`); the manuscript repos are private too.
- The archive README says: "Status: **partial raw-data rerun**... the support map and calibration-tile layer files are archived frozen derived inputs, not yet regenerated from their block geometry" (`README.md:5-10`); "The support grid is archived as a frozen derived input... the 24 named calibration-tile NPZ files are also archived frozen inputs" (`README.md:51-54`).
- The 24 calibration tiles are not hashed in `MANIFEST.json` (58 files) or `layers/manifest.json` (133 full-estate tiles). They are extra files in `layers/` and are not covered by the "SHA-256 hash for every tile" claim.
- The support map is not a one-to-one block geometry: `notes/reports/tsa24-full-support-map.md:3-19` reports 458,708 blocks projecting onto 260,144 distinct fragment cells, 198,564 blocks without a cell, 1,310,129 fragment memberships, 180,074 multi-fragment cells, and up to seven fragments per cell. The papers say "preserves all 458,708 blocks" but do not disclose that 43% of blocks are assigned to representative cells.
- The benchmark paper has no data dictionary, no reuse example, no known-failure table, no DOI, and no licence sign-off. Its "reuse" section (`sections/4_discussion.tex:13-16`) says a user can keep the layer cache and support grid, but those are local and not redistributed.
- The Dogrib comparison is one historical fire in Alberta, not a TSA24 benchmark. The benchmark paper itself says so (`sections/3_results.tex:82-84`: "This is one historical fire, not a TSA24 calibration benchmark"), which is honest but leaves the paper without a benchmark task.

**Fatal or fixable?** Fatal to the Data in Brief submission. It can become a technical report or a data-availability section, but not a data descriptor until the data are public and the frozen inputs are regenerated.

### 3.6 The reproducibility claims are contradicted by the archive

The archive is more honest than the papers, and in several places the archive's own current artifacts contradict the manuscript numbers.

**Runtime.** All four papers cite 655.5 s for the sharded optimizer:

- Regime `sections/0_abstract.tex:25`, `sections/3_results.tex:192`;
- Optimization `sections/0_abstract.tex:13`, `sections/3_results.tex:57`;
- Benchmark `sections/0_abstract.tex:16`, `sections/3_results.tex:55`.

The current `results/optimizer-full-estate.json` says `"elapsed_seconds": 727.1`. The fire-blind run says 865.7. The prose report `notes/reports/p164-8-sharded-fireblind-baseline.md:13-14` still says 655.5 and 865.7. The reproducibility manifest (`results/reproducibility-manifest.json`) records an older hash `b368f9e1...` for `optimizer-full-estate.json`; the archive `MANIFEST.json` records `00671444...` for the current file. The cited 655.5 is the old run, not the current artifact.

**Transfer numbers.** The papers' transfer table (in-sample 1.495, global 4.799, training median 4.680, potential analogue 6.121) matches `results/transfer-validation.json`. The archive's documented `make transfer` target (`Makefile:46-53`) writes `results/transfer-validation-refit.json`, which has in-sample **1.065**, global **5.257**, training median **5.459**, and potential analogue **5.541**. The paper's ranking and magnitudes are not reproduced by the documented pipeline. The refit in-sample row is different; the global/potential gap collapses from 1.32 to 0.28. A reader who runs `make transfer` gets a different paper.

**Regional calibration tile count.** `Makefile:39-44` runs `calibrate_regions.py` on `results/potential/train.json`, which yields **12** tiles (`results/region-calibration-refit.json` has 12 keys). The archive README says "Fit regional map ... verified: 23 tiles" (`README.md:43`), and the papers say 23 regions. `results/region-calibration.json` has 23 keys, but it is an older artifact; the current `make calibrate` does not produce it. The 23-tile map is not reproducible from the documented command.

**Event result.** The 90-day event file is not a single pipeline output: the first six events lack `year`, `split`, `fwi`, `bui`, `wind_kmh`, and `fragments`; the remaining four have them. The archive has a "remaining" checkpoint and a full 10-event file (`results/event-simulations-validation-90d.json`, `...-90d-remaining.json`). The `make event-sim` target writes `results/event-simulations-validation.json`, which is the older 30-day result (median absolute bias 73.5%, not 58.6%). The command to reproduce the paper's 90-day table is not documented.

**Environment.** `requirements.txt` is unpinned (`numpy>=1.26`, `pandas>=2.2`, etc.). The paper reports Python/NumPy/pandas versions from one run but provides no lock, container, CPU model, memory, or storage. The archive README says a clean-host `make resolve -> make verify` run is still required (`README.md:103-108`). It has not been done.

**Hash consistency.** The `results/reproducibility-manifest.json` hashes for `optimizer-full-estate.json` and `risk-ensemble-5seed.json` do not match the current `MANIFEST.json` hashes. `make verify` verifies only 58 files, not the 133 layer tiles, the 24 calibration tiles, or the raw cache. The paper's statement that "the reproducibility manifest records ... SHA-256 hashes" is true as a description of the file, but the file does not describe the current results.

**Fatal or fixable?** Fixable in principle, but not by editing a sentence. The archive must be rebuilt and re-verified, and the paper numbers must be regenerated from the public archive.

### 3.7 Negative results are omitted or removed

The program plan says "Report failures. A failed validation is a result, not a reason to retune on the test set" (`notes/design/ws4-fire-research-program.md:34`). The drafts do not follow this.

- The global calibration failed **validation** p90 (793.3 ha; gate 350-700) and validation maximum (9,474 ha; gate >= 10,000) as well as the training gates (`notes/reports/p164-8-regime-calibration.md:33-47`). The papers mention only the training maximum and over-5,000 failures (`regime sections/3_results.tex:28-29`; `calibration sections/3_results.tex:6-7`; `benchmark sections/3_results.tex:19`). The validation failures are omitted.
- The FireSTARR TSA24 attempt crashed with SIGFPE; the protocol records it (`protocol/event-validation.md:108-115`). Commit `7a858048` "Remove the failed FireSTARR harness from the archive manifest" deletes `results/firestarr-events-smoke.json` and `scripts/run_firestarr_events.py` from the manifest. The papers do not report the failure; they say only that TSA24 external comparisons remain future work (`regime sections/4_discussion.tex:68-69`; `benchmark sections/4_discussion.tex:26`). Removing the evidence and not reporting the attempt is exactly the opposite of the program plan's rule.
- The 30-day event result (median absolute bias 73.5%) is in the archive but not in the papers; the 90-day result (58.6%) is used. The 90-day choice is defensible under the recorded-duration protocol, but a sensitivity table is required.
- The two 420-day event records are included in the headline n=10 even though the paper calls them "implausible" (`regime sections/3_results.tex:143-145`; `calibration sections/2_methods.tex:81-83`). Excluding them changes the median absolute bias from 58.6% to 66.9%. The paper should report both, or exclude them from the primary analysis and report the inclusive result as sensitivity.
- The fire-blind optimizer baseline (same schedule and accounts) is reported in the optimization paper but not in the regime or benchmark paper, even though those papers also present the "optimizer" result. The benchmark paper's table lists the optimizer case without the fire-blind caveat (`benchmark sections/3_results.tex:57-71`).

**Fatal or fixable?** The omissions are fixable by reporting; the FireSTARR removal is a research-integrity problem that must be corrected before submission.

### 3.8 The positioning table and "open data end-to-end" claims are false

Regime `sections/1_introduction.tex` Table 1 (`tab:positioning`) says:

- "Forest estate optimization ... process-coupled" for "This work" (line 61). The objective is harvest-only; the fire-blind repeat produces the same schedule (`optimization sections/0_abstract.tex:15-17`). This is not process-coupled optimization.
- "Open data end-to-end ... yes" for "This work" (line 63). The layer cache, support map, 24 calibration tiles, and compiled dataset are local or frozen; the archive is private; the papers link to private repositories. This is not open data end-to-end.
- "Full-estate BC case ... yes" (line 64). The optimizer covers 112 of 133 tiles and at most 20 blocks per tile (about 2,240 of 458,708 blocks, 0.49%); the five-year case is a fixed schedule evaluation, not a full-estate optimization. The label is at best ambiguous.

The table is a qualitative positioning device, but these three rows are the paper's novelty claim. A hostile referee will treat them as misrepresentation, not as "qualitative."

### 3.9 The data-completeness story is not disclosed

The support-map report (`notes/reports/tsa24-full-support-map.md:3-19`) says the 250 m single-valued raster loses 198,564 blocks (43% of the inventory) and that the area-weighted support assigns them to representative cells. The paper's methods (`regime sections/2_methods.tex:143-145`) say the support map "preserves all 458,708 blocks" but never mention the 43% assignment, the 180,074 multi-fragment cells, or the displacement. The benchmark paper's methods (`sections/2_methods.tex:15-19`) say the grid "preserves all 458,708 compiled blocks" without the caveat.

The archive README says the support map and 24 calibration tiles are frozen, not regenerated (`README.md:51-54`). The report `tsa24-full-support-map.md:32-33` says the support map "was built from the public block geometry and compiled fragment table," which contradicts the README's "not yet scripted here." One of these statements is wrong. The papers cite neither.

This is a data-completeness and reproducibility issue, not just a wording issue. A reader cannot tell whether the 198,564 assigned blocks are spatially meaningful, whether the area weights are correct, or whether the fire results depend on the assignment.

### 3.10 The portfolio is redundant and the authorship/data-governance plan is incomplete

The regime paper contains the calibration paper's results, the benchmark paper's results, and the optimization paper's results. The four papers share figures (`fig1-workflow.png`, `fig2-support.png`, `fig3-calibration.png`, `fig5-risk.png`), numbers, and large blocks of text. The authors' own `notes/reports/p164-manuscript-portfolio.md:3` says the drafts are "not publication-grade until its validation, benchmark, and optimizer gates are met"; `notes/reports/p164-publication-concepts.md:36-45` recommends one primary paper, one applied paper after reconciliation, an optional third calibration paper only if the independent holdout supports a distinct result, and technical reports for the benchmark. The four-paper split ignores that advice.

The authorship/funding/data plan is also incomplete:

- Title pages say "Author list is provisional; co-authors ... pending" while `main.tex` lists one author and the CRediT statement lists only Gregory Paradis.
- Funding is "to be confirmed" in all four.
- The data provider `UBC-FRESH/femic-tsa24-instance` is not cited or acknowledged in any manuscript, although the compiled TSA24 dataset and schedule come from it (`config/sources.json:38-50`).
- No data-owner sign-off, DOI, or public licence for the layer/calibration archive exists.
- The manuscript repositories and the archive are private; the data-availability sections link to them as if they were public.
- The open-source WS4/WS3 competing interest is declared, which is good, but the data-provider credit/authorship question is not addressed.

These are submission blockers independent of the science.

## 4. Paper-by-paper review

### 4.1 Paper 1: `fresh_ws4_fire_regime_manuscript` (open integration / regime)

**What the paper claims.** The abstract (`sections/0_abstract.tex:3-32`) claims an open, reproducible coupling of FBP behaviour, spatial growth, reduced-form suppression/escape, LANDIS succession, estate accounting, and optimization on a compiled TSA24 dataset; a global calibration that failed its training gates; a 23-region in-sample calibration; negative independent transfer; a failed independent point-ignition test on ten events; a five-seed risk ensemble; a five-year full-estate evaluation; a 36-worker sharded optimizer; and a Dogrib/FireSTARR growth comparison. It concludes that the results show "both the practical value and the current limits" of process-based fire risk.

**Fatal-claim audit.**

| Claim (exact sentence or close paraphrase) | Where | Evidence gap | Severity |
| --- | --- | --- | --- |
| "We present an open, reproducible coupling..." | `sections/0_abstract.tex:3-4` | Code is public (WS4), but the data, layer cache, support map, 24 calibration tiles, and result archive are private or frozen; the documented pipeline does not reproduce the paper's transfer numbers. "Reproducible" is not supported. | Fatal as written; fixable only with a public, regenerated archive. |
| "A global suppression calibration under a pre-registered protocol failed its training gates." | `sections/0_abstract.tex:10-11` | The global calibration also failed validation p90 and maximum (`p164-8-regime-calibration.md:33-47`). The protocol status is "proposed; no calibration result exists yet" (`ws4-regime-calibration-protocol.md:9`), and the regional model was not pre-registered. The sentence is incomplete and the "pre-registered" framing covers only the abandoned global model. | Major. |
| "A 23-region in-sample calibration reproduced the median fire size (23.8 ha versus 23.0 ha historical) and the maximum (20,770.4 ha versus 25,114.8 ha)..." | `sections/0_abstract.tex:11-12` | The maximum is 17.3% low, not "reproduced"; p90 is 26.3% low, p95 42.6% low, over-1,000 30.4% low, over-5,000 40% low. The "3,450 fires" are 5 realizations of 690 potential fires, not 3,450 independent fires. No confidence intervals. The maximum equals a fitted escape cap, so it is a parameter artifact, not distributional skill. | Major/Fatal to "reproduced." |
| "Independent transfer to 11 held-out tiles was negative..." | `sections/0_abstract.tex:13-14` | The regional map was fitted on all 23 tiles, including the 11 "held-out" tiles (`region-calibration.json` keys; `calibrate_regions.py:69-85`). Only the training-only baselines are transfer methods. The in-sample score is not a held-out score. | Fatal to "held-out regional calibration." |
| "An empirical-Bayes ridge selected by training-only cross-validation also failed on held-out tiles (6.54) and did not outperform complete pooling (5.18)." | `sections/0_abstract.tex:15-16` | The model is a ridge regression on six noisy per-tile parameter estimates, not a hierarchical/empirical-Bayes model (`hierarchical_validation.py:144-148`). Lambda 100 is the largest grid value; the CV score is monotone to the boundary. The best pooling baseline is the training median at 4.68, not complete pooling at 5.18. The ridge-vs-pooling difference is not significant (bootstrap CI includes 0). | Major/Fatal to "hierarchical." |
| "An independent point-ignition test on ten TSA24 events also failed..." | `sections/0_abstract.tex:18-19` | Not independent: 8/10 event areas are in the calibration history; one event is in a training tile; the regional map was fitted on the validation tiles. | Fatal. |
| "median absolute area bias was 58.6%, with a range from -67.4% to +3163.0%." | `sections/0_abstract.tex:18-19` | n=10, one deterministic draw, no CI. Median bias CI includes 0; sign test p≈0.75. Excluding the two 420-day records gives 66.9%; excluding G40324 gives 49.9%. The 58.6% is not robust to defensible inclusion choices. | Major. |
| "A five-seed full-layer risk ensemble produced a median burned area of 7,889.6 ha and a CVaR95 volume loss of 1.04 million m3 against a no-fire baseline of 822.55 million m3." | `sections/0_abstract.tex:22-23` | CVaR95 with five seeds is the worst observed seed (`risk-ensemble-5seed.json`; results text admits at `sections/3_results.tex:152-154`). The volume loss is 0.126% of the baseline; no uncertainty, no parameter/weather ensemble, no decision relevance. The abstract omits the caveat. | Major. |
| "A five-year full-estate evaluation burned 8,374.1 ha and harvested 156,358.8 ha." | `sections/0_abstract.tex:24` | 8,374.1 ha is seed 20261122, run 1 of the five-seed risk ensemble; it is not an independent case. The fixed schedule has one dropped block (`estate-case-5yr-full-layers.json`). | Major. |
| "A 36-worker sharded optimizer produced a 179-event schedule and a full-estate evaluation in 655.5 s." | `sections/0_abstract.tex:25-26` | 179 are harvest entries (blocks), not fire events; the current artifact says 727.1 s, not 655.5; the fire source is three fixed ignitions with constant weather; no sequential baseline. | Fatal to the runtime/optimizer claim. |
| "On a documented Dogrib fire, the growth engine overpredicted area by 191% versus 36% for FireSTARR, but had higher overlap (IoU 0.252 versus 0.140); neither result is an operational validation." | `sections/0_abstract.tex:26-27` | One fire, one deterministic run per model, different inputs (WS4 raw wind; FireSTARR deterministic; no Scenario 2b patch), no uncertainty. WS4's documented Scenario 2b run is +58.9% area and IoU 0.385 (`p157-observed-validation.md:79-87`), which is not reported. "Documented fire" is ambiguous. | Major. |
| "The results show both the practical value and the current limits of open, process-based fire risk in forest estate planning." | `sections/0_abstract.tex:30-31` | The fire effect is ~0.1% of volume; the optimizer ignores fire; no decision analysis, no user case, no NPV. "Practical value" is not demonstrated. | Fatal to the framing. |
| "The gap is an open, auditable, end-to-end workflow... with the code, inputs, seeds, and residuals available for inspection." | `sections/1_introduction.tex:23-29` | Inputs are not available; the archive is private; the support map and 24 calibration tiles are frozen; the 133-tile cache is local. | Fatal to the novelty claim. |
| Table 1: "Forest estate optimization ... process-coupled"; "Open data end-to-end ... yes"; "Full-estate BC case ... yes." | `sections/1_introduction.tex:61-64` | See 3.8. These are false or misleading. | Fatal to the positioning table. |

**Methods.** The fire behaviour and growth model is described in one paragraph (`sections/2_methods.tex:26-41`) with no equations, no parameter values, no numerical scheme, and no validation of the growth engine beyond the Dogrib one-fire check. The suppression model (`sections/2_methods.tex:69-86`) is a two-stage retained-fraction model with six parameters but no equations for the contained/escaped distributions or the escape hazard. The calibration objective (`sections/2_methods.tex:88-102`) does not give the weights used in the fit, the candidate generation, or the acceptance gates. The transfer score (`sections/2_methods.tex:124-126`) gives weights but no normalization, uncertainty, or sensitivity. The event test (`sections/2_methods.tex:52-67`) omits the 247→18→11→10 exclusion flow, the tile assignment, the exact snapping distance, and the fact that the calibration used the same historical fires.

The largest methods omission is the **potential sample**: `build_potential.py:27` sets `ACTIVE_DAYS_MAX = 7`, and `:289-293` caps each potential fire at seven active days (or less if rain stops it). The suppression model is fitted on 0.5-7 day potential fires, then applied to 90-day event simulations (`run_event_simulations.py:110-112`). The paper says "90-day antecedent weather spin-up for tail-event sampling" (`sections/2_methods.tex:37-38`) but never says the potential fires themselves are at most seven days. The event test is therefore an extrapolation of the suppression hazard far outside its calibration duration range. This is a fatal validity threat to the event test, independent of the leakage.

The second omission is the **2023-only weather**. `build_potential.py:30-31` fixes `WEATHER_START = "2023-02-01"` and `WEATHER_END = "2023-09-30"` for every tile, while the historical perimeters span 1950-2024 (`ws4-regime-calibration-protocol.md:55`). The calibration fits a 2023-weather potential distribution to a multi-year historical size distribution. The paper says "one 2023 weather season" in limitations but does not discuss the mismatch. A 2023-weather sample cannot identify a multi-year suppression regime; it can only identify a 2023-weather-year adjustment. The in-sample median match may be a weather-year coincidence.

The third omission is the **support map**: the paper says "area-weighted FragmentSupport grid" and "preserves all 458,708 blocks" (`sections/2_methods.tex:143-145`), but the support report says 198,564 blocks are assigned to representative cells, with 1,310,129 memberships and 180,074 multi-fragment cells. The paper does not disclose the assignment, the displacement, or the fact that the support map is a frozen derived input. This is a data-completeness issue that affects every estate-scale result.

**Statistics.** The paper reports point estimates as if they were precise. The regional table (`sections/3_results.tex:31-51`) compares 432 historical fires to 3,450 simulated realizations and gives one decimal place. There is no bootstrap over potential fires, no parameter posterior, no weather ensemble, no observation error, and no multiple-comparison correction. The 1,000 candidates per tile × 23 tiles = 23,000 candidate fits are selected on the same data; the reported residuals are optimized, not out-of-sample. The transfer scores are an arbitrary weighted sum (`validate_transfer.py:78-87`) with no CI; the ranking of methods changes between the original and refit runs. The event test has n=10, one draw, and no CI. The risk ensemble has n=5 and calls the worst seed "CVaR95." The runtime is one run on unspecified hardware.

**Reproducibility.** The paper's data-availability section (`sections/6_data-availability.tex:4-23`) says the analysis scripts and caches are local under `work/fire_regime/`, the layer manifest and compact artifacts are tracked, and a reproducibility manifest records commit/versions/seeds/sizes/hashes. In practice:

- The archive is private.
- The support map and 24 calibration tiles are frozen.
- `make calibrate` produces 12 tiles, not 23.
- `make transfer` produces 1.065/5.257/5.459/5.541, not 1.495/4.799/4.680/6.121.
- The 655.5 s runtime is not in the current JSON.
- The reproducibility manifest hashes for the optimizer and risk ensemble do not match the current files.
- `requirements.txt` is unpinned; no container/lock; no clean-machine run.

The paper's "reproducibility package that another group can inspect and rerun" (`sections/1_introduction.tex:40`) is not true today.

**Writing and presentation.** The paper is 17 pages and tries to be four papers. The abstract is 33 lines with 15+ numbers; the reader cannot tell which result is the contribution. The introduction's Table 1 is a novelty claim that the results do not support. The results are a sequence of unrelated tables (calibration, transfer, events, risk, estate, optimizer, Dogrib) with no unifying analysis. The discussion repeats the limitations but does not resolve the contradictions. The conclusion says "the broader contribution is methodological" (`sections/5_conclusion.tex:16`) but the methods are underdescribed.

Specific presentation defects:

- Table 1 (`sections/3_results.tex:40`) labels 3,450 simulated realizations as "Fires."
- Table 1 (`sections/3_results.tex:77-83`) includes "Complete pooling" and "Hierarchical ridge" rows that are not defined in the methods (the methods list five methods plus a separate hierarchical test).
- The text says "5.287 for the global fit in that run" (`sections/3_results.tex:93-94`) while the table says 4.799; two global scores are presented without explanation.
- The text says "the central distribution and maximum are close" (`sections/3_results.tex:53`) while the maximum is 17% low and the p90/p95 are 26%/43% low.
- The text says the 90-day caps "affect the largest-event comparison, but not the small-event overpredictions" (`sections/3_results.tex:144-145`); G51212 is a 151.7 ha event capped from 144.9 days, so the statement is false for at least one small event.
- The Dogrib section reports only the raw-wind WS4 case, not the documented Scenario 2b case; the report's Scenario 2b result is much better on area (+58.9%) and overlap (IoU 0.385), and its omission makes the comparison look worse for WS4 on area while still claiming better overlap.
- The "179-event schedule" is described as "179 blocks/events" (`sections/3_results.tex:190`) and "16 fragment-level events" (`:191`); the word "event" is overloaded.

**Required revisions (minimum).**

1. Remove or reframe every "independent" event claim. Either (a) exclude all validation events from the regional calibration and fit on pre-2018 training tiles only, or (b) call the event test an in-sample reconstruction and remove it from the abstract's validation claim.
2. Refit the regional map on training tiles/years only; freeze it; then evaluate on t13-t23 and 2018-2023. Report the full global training and validation gate table.
3. Add bootstrap/paired intervals for event bias, transfer scores, and risk; report sensitivity to the 420-day records, G40324, score weights, and the 30-day vs 90-day event cap.
4. Report the 7-day potential-fire cap and the 2023-only weather; either extend the potential sample to multi-year weather or state that the calibration is a 2023-weather-year fit and cannot identify a multi-year suppression regime.
5. Replace the "process-coupled"/"open data end-to-end" table rows with accurate descriptions; remove "practical value" unless a decision analysis is added.
6. Use one authoritative artifact for 655.5 vs 727.1; report hardware, repetitions, and a sequential baseline.
7. Publish the archive with a DOI, regenerate the support map and 24 calibration tiles, and run the documented pipeline on a clean host.
8. Report the FireSTARR TSA24 failure and the global validation failures.
9. Quantify the optimizer decision space (2,240/458,708 blocks) and call it a feasibility schedule, not an optimization.
10. Narrow the paper to one contribution: open integration plus a rigorously framed negative diagnostic. Move the event test to a separate paper only if it becomes truly independent.

**Decision.** **Major revision; do not submit now.** The open integration is a real engineering contribution and the negative transfer diagnosis is worth publishing, but the current manuscript's central validation claim is not independent, the positioning table is false, and the archive does not reproduce the numbers. A revised paper that removes the false claims and merges the calibration core could be a credible *Environmental Modelling & Software* methods/diagnostic paper. It is not a validation paper.

### 4.2 Paper 2: `fresh_ws4_fire_calibration_manuscript` (calibration / transfer)

**What the paper claims.** The title and abstract are more honest than Paper 1: "Regional suppression calibration is a fit, not a forecast" (`main.tex:44`), and the abstract says the regional map is "a description of the calibration data, not a validated regional or event-level forecast" (`sections/0_abstract.tex:18-19`). The paper's core result is that a training-only transfer test is much worse than the in-sample fit, and that a ridge with potential/weather covariates does not recover transferable skill.

**Fatal-claim audit.**

| Claim | Where | Evidence gap | Severity |
| --- | --- | --- | --- |
| "We test whether a regional suppression calibration transfers to held-out tiles..." | `sections/0_abstract.tex:4-5` | The regional calibration was fitted on all 23 tiles, including the 11 held-out tiles. The test is whether training-only parameters transfer, not whether the regional map transfers. The framing is backwards. | Fatal. |
| "On the fixed 11-tile holdout, the in-sample score was 1.50..." | `sections/0_abstract.tex:12` | "In-sample score" is correctly labeled here, but "holdout" makes it sound like a holdout method. The in-sample row uses each validation tile's own fitted parameters; it is a fit, not a holdout result. | Major. |
| "compared with 6.12 for a deployable potential/weather analogue and 4.80 for the global fit. A training median scored 4.68..." | `sections/0_abstract.tex:12-14` | The potential analogue is not the best deployable baseline; the training median (4.68) is better. The global-vs-analogue difference is not significant (paired 95% CI [-2.74, +0.15]). The analogue uses five features in code (`validate_transfer.py:90-98`), while the methods claim seven (`sections/2_methods.tex:54-56`). | Major. |
| "An empirical-Bayes ridge selected by training-only simulation score scored 6.54 and did not outperform complete pooling (5.18)." | `sections/0_abstract.tex:14-15` | It is a ridge regression, not hierarchical/empirical Bayes. Lambda 100 is the grid boundary. It also did not outperform the training median (4.68). The ridge-vs-pooling difference is not significant. | Major. |
| "A point-ignition test on ten independent TSA24 events also failed..." | `sections/0_abstract.tex:16-17` | Not independent; 8/10 event areas are in the calibration history; one event is in a training tile. | Fatal. |
| "The regional map is a description of the calibration data, not a validated regional or event-level forecast." | `sections/0_abstract.tex:18-19` | This sentence is correct and should be the paper's conclusion. But the preceding "independent" and "holdout" language contradicts it. | Fixable by consistency. |
| "A transferable model needs explicit suppression-capacity covariates, multi-year weather, and observed active-spread durations." | `sections/0_abstract.tex:21-23` | This is a hypothesis, not a result. The paper did not test suppression-capacity covariates, multi-year weather, or observed durations. The negative result is consistent with many causes: wrong model structure, noisy per-tile fits, 2023-only weather, 7-day potential fires, small n, or an inappropriate score. | Major causal overreach. |
| "The result also explains why global suppression parameters fail: regions differ in suppression capacity, access, response, fuel structure, and fire weather." | `sections/4_discussion.tex:18-20` | No suppression-capacity, access, response, or fuel-structure covariates were measured. The paper cannot distinguish these explanations from model misspecification or sampling noise. | Fatal to the causal claim. |

**Methods.** The paper is a calibration paper, so the methods must be complete. They are not.

- The six-parameter suppression model is described only qualitatively (`sections/2_methods.tex:30-37`); there are no equations for the contained/escaped distributions, the escape hazard, or the absolute cap. The reader cannot implement it from the paper.
- The regional objective is described as "a weighted distance over the 10th, 25th, 50th, 75th, 90th, and 95th percentiles plus the over-500, over-1,000, and over-5,000 fractions" (`sections/2_methods.tex:32-34`) but the weights are not given. The code uses 3,3,2 for over-500/1,000/5,000 (`calibrate_regions.py:41-48`); the paper does not say.
- The global calibration gates are not tabulated. The paper says the global fit "failed the maximum and over-5,000 gates" but does not give the gate ranges, the training metrics, or the validation metrics. The report has them; the manuscript does not.
- The regional fit uses every tile with at least five historical fires (`sections/2_methods.tex:32-33`). The archive shows some tiles have 6, 7, or 8 historical fires (`region-calibration.json` `historical.n`); six parameters fitted to six fires is saturation. The paper should report per-tile n and either drop small tiles or use partial pooling.
- The paper says "30 potential fires per tile" but the regional metrics use 5 realizations per potential fire (150 per tile; 3,450 total). The table's "3,450" (`sections/3_results.tex:24`) is not explained; the effective sample size is 690 potential fires, and the historical sample is 432. The 3,450 are not independent.
- The paper says "The calibration uses 24 fixed 30 km tiles from the pre-registered protocol" (`sections/2_methods.tex:8`), but the regional model is post hoc and is fitted on 23 tiles. The pre-registered protocol covers the global model only. The paper should say "the global protocol was pre-registered; the regional model is a post-hoc diagnostic."
- The event section (`sections/2_methods.tex:70-83`) does not say that the same fires are in the calibration history, does not report the tile assignment, and does not report the actual snap distances. It says "No event-specific tuning was performed" (`:83`), which is true but irrelevant: tile-level fitting on the same events is still leakage.

**Statistics.** The same problems as Paper 1, plus the transfer comparison:

- The transfer score is a weighted sum of absolute errors with arbitrary weights (3,3,2,0.5). There is no normalization by historical variance, no CI, no paired test, no sensitivity analysis, and no pre-registration of the weights. The score is a diagnostic, but the paper's conclusions about method ranking require at least a paired bootstrap.
- The in-sample score 1.495 is not comparable to the transfer scores because it is computed on the same data used to fit the parameters. The paper labels it "in-sample upper bound" (`sections/3_results.tex:60`), which is ambiguous: lower score is better, so it is an upper bound on skill, not on error. A reader can misread it as a bound that transfer methods should approach.
- The global fit is the failed P164.8 candidate, not a refit baseline. It failed training and validation gates (`p164-8-regime-calibration.md:33-47`). Using it as the "global fit" comparator is weak; a training-only global refit with a proper objective would be fairer.
- The hierarchical ridge is a set of six independent ridge regressions (`hierarchical_validation.py:144-148`), with a shared lambda selected by leave-one-tile-out simulation score. The lambda grid ends at 100 and the best score is at 100 (`p164-8-hierarchical-validation.md:37-53`); the paper does not report the boundary. The model treats the per-tile parameter estimates as known responses, ignoring their estimation error. It is not a hierarchical model in the usual sense (no partial pooling of residuals, no posterior, no group-level variance). The label "empirical-Bayes ridge" is not justified.
- The complete pooling comparator is the mean/median training parameter set; the training median 4.68 is better than the "complete pooling" 5.18. The paper's abstract compares the ridge to 5.18, not to 4.68, which makes the ridge look closer to the best baseline than it is.
- The "potential/weather analogue" donor selection is based on five standardized features, not the seven described. Seven of eleven validation tiles select `t03`; that is a red flag for feature scaling or a dominant feature, not evidence that "features do not distinguish regimes." The paper should report feature distances and a sensitivity analysis with different feature sets/metrics.
- The event test has n=10, one draw, no CI, and the same leakage. The sign test is not significant; the median bias CI includes zero. The paper's "failed by a wide margin" is supported by the magnitude of absolute errors, but the directional/causal interpretation is not.

**Reproducibility.** The data-availability section (`sections/6_data-availability.tex:1-7`) is seven lines and has no URL, DOI, or archive description. It says the results are "tracked in UBC-FRESH/ws4"; the archive is a separate private repo. The paper's transfer table is from `transfer-validation.json`, not the archive's `make transfer` output (`transfer-validation-refit.json`). The regional map is from `region-calibration.json` (23 tiles), not the current `make calibrate` output (12 tiles). The hierarchical 6.540/5.182 numbers are from `hierarchical-validation-simcv.json`, not the current `make hierarchical` output (`hierarchical-validation-refit.json`, 7.356/1.065). A reader cannot reproduce the paper's table from the documented commands.

**Writing and presentation.** The paper is 10 pages and reads like a compressed version of Paper 1's calibration/transfer/event sections. The abstract is dense but mostly honest; the title is good. The results table (`sections/3_results.tex:51-67`) has five rows while the methods list six methods; complete pooling and the hierarchical ridge appear only in the text, and the text's global score 5.287 differs from the table's 4.799. The reader sees two global fits. The event section (`sections/3_results.tex:87-131`) is longer than the transfer section but is not independent. The discussion (`sections/4_discussion.tex:18-21`) makes causal claims the design cannot support. The conclusion (`sections/5_conclusion.tex:4-8`) repeats the abstract numbers without the caveats.

**Required revisions (minimum).**

1. Refit the regional map on `t01`-`t12` only (and ideally pre-2018 only), freeze it, and evaluate on `t13`-`t23`/2018-2023. Report the regional map's true held-out score, not the in-sample score.
2. Remove the event section or make it truly independent: exclude all event years/fires from calibration, use a training-tile-only map, report the tile assignment, and add multiple draws/weather ensembles.
3. Add paired bootstrap CIs for all method comparisons; report the full table including training median, complete pooling, and hierarchical ridge; use the best pooling baseline (training median) in the abstract.
4. Report the full global gate table, including validation p90/max failures; report per-tile historical n; drop or partially pool tiles with <10 fires.
5. Correct the feature description (five vs seven) and report donor distances/feature sensitivity; do not claim "features do not distinguish regimes" from a nearest-neighbor result alone.
6. Call the ridge a ridge regression, not hierarchical/empirical Bayes; report the lambda boundary and a proper partial-pooling alternative if the "hierarchical" claim is kept.
7. Remove causal claims about suppression capacity/access/response; frame them as hypotheses.
8. Make the data/archive public and reproduce the table from the documented commands; otherwise the paper is not reproducible.
9. If the paper remains standalone, add an external benchmark (FSim/BurnP3+/Cell2Fire) on the same tiles or events; otherwise merge into Paper 1.

**Decision.** **Reject/merge as a standalone paper.** The negative transfer diagnostic is the best scientific signal in the portfolio, but the paper's "held-out" framing is false, the event test is in-sample, and the transfer comparison is underpowered and selective. A major revision could turn it into a credible short negative-result paper in *Fire* or *IJWF* **only if** the regional map is refit on training tiles and the event test is made independent. As currently written, it is a section of Paper 1. If the authors want an IJWF paper, the minimum is a genuinely independent temporal/spatial validation with spatial metrics and an external benchmark; without that, IJWF is the wrong venue.

### 4.3 Paper 3: `fresh_ws4_fire_optimization_manuscript` (optimization / scale)

**What the paper claims.** The paper claims a "sharded, process-based fire-risk workflow for large forest estates" (`main.tex:44`), with a calibrated FBP-based fire source evaluated through the estate process engine; 133 tiles, 112 eligible, up to 20 blocks per tile, two hill-climb rounds, 179 scheduled events, 20,775.6 ha harvested, 859.98 million m3, 74.25 ha burned in 16 fragment-level events, 655.5 s on 36 workers. It admits the result is a bounded decomposition heuristic, not a global optimum, and that a fire-blind repeat produces the same schedule and accounts.

**Fatal-claim audit.**

| Claim | Where | Evidence gap | Severity |
| --- | --- | --- | --- |
| Title: "A sharded, process-based fire-risk workflow for large forest estates" | `main.tex:44` | The workflow evaluates a fire source but the objective is harvest-area feasibility; the fire-blind repeat is identical. "Fire-risk workflow" implies fire risk drives the schedule; it does not. | Fatal to the title. |
| "A calibrated FBP-based fire source is evaluated through the compiled estate process engine." | `sections/0_abstract.tex:6-7` | The source uses three fixed ignitions (regions 1, 13, 22), two active days, constant weather (FWI 30, BUI 80, wind 10 km/h), not the calibrated event/weather regime (`full_estate_optimizer.py:224-259`). It is "calibrated" only in the suppression map, not in the ignition/weather scenario. | Fatal/Major. |
| "The estate is divided into 133 30 km tiles; each eligible tile selects up to 20 blocks and runs two local hill-climb rounds with a 10% local harvest target. The 112 tiles ... produce 179 scheduled events." | `sections/0_abstract.tex:7-10` | 112 × 20 = 2,240 blocks out of 458,708 (0.49%). The "hill-climb" is a feasibility search for a 10% harvest-area target; `best_objective` is 0.0, not a maximized value. The 179 are harvest entries, not fire events. | Fatal to "large forest estate optimization." |
| "The full-estate evaluation harvests 20,775.6 ha and produces 859.98 million m3; 74.25 ha burn in 16 fragment-level fire events." | `sections/0_abstract.tex:12-13` | The 74.25 ha is from three fixed two-day ignitions with constant weather; it is not a calibrated risk estimate. The 16 "events" are fragments reached by those ignitions, not 16 fires. | Major. |
| "The sharded run takes 655.5 s with 36 workers." | `sections/0_abstract.tex:13` | Current `optimizer-full-estate.json` says 727.1 s; the fire-blind run says 865.7 s. No sequential baseline, hardware, or repetition. | Fatal to the runtime claim. |
| "This is a bounded decomposition heuristic, not a global joint optimum... A fire-blind repeat ... produced the same schedule and accounts, showing that the current shard objective is harvest-only..." | `sections/0_abstract.tex:14-17` | This is the paper's most honest sentence. It also means the paper is not a fire-risk optimization paper. The program plan's go/no-go says no paper until the fire-aware objective changes the schedule or the null is demonstrated against a near-global baseline (`ws4-fire-research-program.md:95-111`). The draft violates that gate. | Fatal to the paper's premise. |
| "The contribution is a reproducible scale path for process-based fire risk..." | `sections/0_abstract.tex:17-18` | "Reproducible" is not demonstrated (private archive, stale runtime, no clean-machine run). "Scale path" is one run on one workstation; no scaling study. | Major. |
| "This paper demonstrates one such strategy: shard the estate into 30 km tiles, optimize each tile independently with the calibrated fire source..." | `sections/1_introduction.tex:18-20` | "Optimize" is not supported; the local target is a 10% harvest-area feasibility constraint. The fire source is not the calibrated event source. | Fatal. |
| "The wall time is far below a fully sequential equivalent..." | `sections/3_results.tex:57-59` | No sequential run was made. The claim is an inference, not a measurement. | Major. |
| "The workflow demonstrates that a process-based fire regime can be carried through a full-estate optimization at TSA24 scale." | `sections/4_discussion.tex:6-7` | The optimization covers 112/133 tiles and 20 blocks/tile; the fire source is a three-ignition demo; the objective is harvest-only. It demonstrates a data path, not a full-estate optimization. | Fatal. |
| "The approach is embarrassingly parallel across tiles, which matches the Linux/HPC operating model." | `sections/4_discussion.tex:19-22` | One 36-worker `ProcessPoolExecutor` run on a workstation; no HPC test, no scaling curve, no CPU/memory data. | Major. |

**Methods.** The methods section is 34 lines (`sections/2_methods.tex:1-34`). It does not define the objective function, the decision variables, the constraints, the search algorithm, the stopping rule, or the solution quality. It says "selects up to the 20 largest eligible CC blocks" and "runs two hill-climb rounds" (`:14-17`), which is a selection heuristic, not an optimization model. The "10% harvest-area target" is a constraint; there is no volume, NPV, risk, adjacency, or flow objective. The local shards are independent; there is no cross-tile coordination. The aggregate evaluation is a simulation of the concatenated schedule; it is not a re-optimization.

The fire source is the biggest methods problem. The paper says "calibrated fire source," but `full_estate_optimizer.py:224-243` uses three fixed ignitions, one in each of three regions, with arbitrary `active_days=2`, `fwi=30`, `bui=80`, `wind_kmh=10`; `:244-259` uses one constant weather step. The calibrated regional map supplies suppression parameters, but the ignition/weather scenario is not calibrated or sampled from the historical distribution. The 74.25 ha burned is therefore not comparable to the 8,374.1 ha five-year case or to the risk ensemble. The paper does not disclose this in the abstract or results; it says "calibrated FBP-based fire source," which a reader will interpret as the calibrated regime.

**Statistics and baselines.** There is no baseline, no quality bound, no global/near-global comparison, no multi-seed risk ensemble in the optimizer, and no sensitivity analysis. The paper says "not compared with a global optimization baseline" (`sections/4_discussion.tex:32`) and "one calibrated fire source and one weather state; no multi-scenario risk ensemble in the optimizer" (`:30-31`). These are not limitations to be fixed by a sentence; they are the missing evidence for the paper's claim. The fire-blind repeat is the only comparison, and it shows the fire source has no effect. The "179 events" and "20,775.6 ha" are a single feasible schedule, not an optimum or a distribution. There is no way to know whether the schedule is good, bad, or arbitrary.

**Reproducibility.** The runtime is not traceable (655.5 vs 727.1). The `optimizer-full-estate.json` has no explicit seed field; the code uses `seed=20261122 + tile_id` (`full_estate_optimizer.py:174`). The `schedule_events`/`schedule_blocks` are 179/179. The paper says the run records "worker count, seeds, shard count, evaluated candidates, and full-estate accounts" (`sections/2_methods.tex:31-34`), but the JSON has no top-level `seeds` field; the per-shard runs have no seed field either. The data-availability section (`sections/6_data-availability.tex:4-8`) points to `work/fire_regime/results/` paths that are not in the archive. The archive is private; no DOI. The paper is not reproducible.

**Writing and presentation.** The paper is 7 pages, too thin for CJFR. The title and abstract promise a fire-risk workflow; the results show a harvest-only feasibility schedule. The methods do not define the optimization problem. The results table (`sections/3_results.tex:25-46`) gives one run; no variance, no baseline, no quality. The figure `fig5-risk.png` is in the repository but not referenced in the results; the results reference `fig:support` and `fig:workflow` only. The discussion admits the fatal limitation, which makes the paper read as a negative methods note rather than a research article. The conclusion (`sections/5_conclusion.tex:4-7`) says "reproducible scale path" and "not a global optimum"; the first is unverified, the second is honest.

**Required revisions (minimum).**

1. Add a fire-risk term to the local objective (e.g., CVaR of burned area or volume loss) and show that it changes the schedule relative to fire-blind and burn-probability-overlay baselines.
2. Build a near-global baseline on a reduced estate (10-20 tiles) or a coordinated decomposition with quality bounds; report the gap.
3. Use the calibrated ignition/weather process, not three fixed ignitions; run multiple seeds and weather scenarios; report the distribution.
4. Report the full decision-space coverage (2,240/458,708 blocks), the local target, and the objective value; call the result a feasible schedule, not an optimization.
5. Report runtime with hardware, repetitions, sequential baseline, and scaling; explain 655.5 vs 727.1.
6. Add volume/NPV/flow, burned area, CVaR, and biomass accounts; compare the optimizer schedule to the fixed five-year schedule.
7. Make the archive public and reproducible; add the missing seed/command metadata.
8. If the fire-aware objective does not change the schedule, do not submit as an optimization paper; merge the feasibility note into Paper 1 or publish it as a technical report.

**Decision.** **Reject/merge; kill as a standalone optimization paper.** The paper is a useful engineering note about a data path, but it is not an optimization contribution, and the program plan's own gate says not to submit it. It should be merged into Paper 1 as a short "scale/feasibility" subsection, with the fire-blind null result stated, or kept as an internal technical report. CJFR is the wrong venue for a 7-page harvest-area feasibility demo with no baseline.

### 4.4 Paper 4: `fresh_ws4_fire_benchmark_manuscript` (data / benchmark)

**What the paper claims.** The paper describes a "reproducible TSA24 open fire-regime benchmark" with 458,708 compiled blocks, 1,111,565 support cells, a 133-tile layer cache, a 90,375,672-byte layer cache, a 34-tile SRTM cache, a global calibration no-go, a 23-region in-sample map, a fixed held-out transfer test, a five-seed risk ensemble, a five-year estate case, a sharded optimizer case, and a Dogrib/FireSTARR growth check. It says the contribution is a data/software benchmark, not a validated forecast, and that large rasters are not redistributed but the package records provenance, hashes, licences, seeds, and exact commands.

**Fatal-claim audit.**

| Claim | Where | Evidence gap | Severity |
| --- | --- | --- | --- |
| "We describe a reproducible TSA24 benchmark..." | `sections/0_abstract.tex:4-5` | The archive is private; the support map and 24 calibration tiles are frozen; the documented pipeline produces different transfer numbers. "Reproducible" is not supported. | Fatal. |
| "Open wildfire modelling still lacks reusable, inspectable benchmark packages..." | `sections/1_introduction.tex:4-12` | No systematic review; the claim "lacks" is a novelty claim without a search protocol. There are existing open fire-model packages and data sets (the paper itself cites Cell2Fire, BurnP3+, LANDIS-II). The gap may be real, but this sentence is not evidence. | Major novelty overclaim. |
| "The benchmark includes a pre-registered global calibration that failed its gates, a 23-region in-sample suppression map, a fixed held-out transfer test, a five-seed full-layer risk ensemble, a five-year full-estate case, and a sharded optimizer case." | `sections/0_abstract.tex:10-12` | A benchmark is a common task/data/evaluation protocol, not a bundle of project results. The "fixed held-out transfer test" is not a data benchmark; the "sharded optimizer case" is a harvest-only feasibility run. The "23-region" is 23 tiles. | Fatal to the "benchmark" framing. |
| "The regional map reproduces the median ... and maximum ... but underproduces the tail..." | `sections/0_abstract.tex:12-14` | The maximum is 17.3% low; the table omits over-100 and over-5,000; the "reproduces" language overstates. | Major. |
| "The five-year case burns 8,374.1 ha and harvests 156,358.8 ha. The sharded optimizer schedules 179 events and harvests 20,775.6 ha in 655.5 s..." | `sections/0_abstract.tex:14-16` | 8,374.1 is seed 1 of the risk ensemble; 179 are harvest entries; 655.5 vs 727.1; the optimizer's 74.25 ha is from three fixed ignitions. | Major. |
| "The contribution is a data and software benchmark, not a validated fire forecast. Large rasters are not redistributed; the package records provenance, hashes, licences, seeds, and the exact commands needed to rebuild the cases." | `sections/0_abstract.tex:18-20` | The data are not redistributed; the archive is private; the 24 calibration tiles/support map are frozen; the `make` pipeline does not reproduce the paper; the "exact commands" are not documented for the 90-day event table. A reader cannot rebuild the cases. | Fatal to the data descriptor. |
| "It is intended for reuse by groups that want to test a fire-regime, suppression, succession, or estate-optimization method on a real, spatially explicit dataset without rebuilding the data stack." | `sections/1_introduction.tex:14-18` | Reuse requires the data; the data stack is not distributed. A user cannot test a method on a private, frozen cache. | Fatal. |
| "A user can replace the fire source, suppression map, succession process, or optimizer while keeping the layer cache, support grid, manifests, and case outputs." | `sections/4_discussion.tex:13-16` | The layer cache and support grid are local; the 24 calibration tiles are frozen; the archive is private. This is false. | Fatal. |
| "The cache contains 90,375,672 bytes of layer data and a manifest with SHA-256 hashes; the DEM cache contains 34 SRTM tiles and 881,769,668 bytes." | `sections/0_abstract.tex:6-8` | The 90.4 MB is the 133 full-estate tiles; the 24 calibration tiles are extra and not in the manifest; the 24 are frozen. "Manifest with SHA-256 hashes" does not cover the 24. | Major. |
| "The Dogrib FireSTARR comparison is included as a growth-model check: WS4 raw wind overpredicted area by 191% (IoU 0.252); FireSTARR overpredicted by 36% (IoU 0.140). This is one historical fire, not a TSA24 calibration benchmark." | `sections/3_results.tex:82-84` | One fire, one deterministic run per model, different inputs; not a benchmark. The sentence is honest about the limitation, but the paper's title/abstract still call it a benchmark. | Major. |
| "The benchmark supports reproducibility, model comparison, and scenario analysis on a real public estate." | `sections/4_discussion.tex:6-7` | No public data; no model comparison on TSA24; no scenario analysis example. | Fatal. |

**Methods.** The methods section is a data/software description, but it lacks the elements a data descriptor needs:

- No data dictionary: variable names, units, types, missing-value codes, coordinate reference system, tile indexing, layer names, and file formats are not described.
- No per-layer provenance: VRI version/date, SRTM tile list, Open-Meteo request dates, BC Wildfire perimeter/incident service versions, and the compiled TSA24 artifact commit are not in the paper.
- No licence table in the paper: the data availability section says "the data licences are documented in the WS4 licence audit" (`sections/6_data-availability.tex:4-7`), but the paper does not include the required OGL-BC/NASA/Open-Meteo attribution.
- No reuse example; no known-failure table; no DOI; no archive location.
- The 24 calibration tiles and support map are not described as frozen inputs; the paper says "layer cache" as if all layers are regenerated.
- The Dogrib comparison is not a TSA24 benchmark; the paper includes it as a "growth-model check" but does not report the FireSTARR TSA24 SIGFPE failure or the absent TSA24 external benchmark.

**Statistics.** The paper reproduces the same point estimates as Papers 1 and 2, with the same absence of CIs. It also selectively reports the calibration table: `sections/3_results.tex:24-41` omits over-100, over-5,000, mean, and the 432/3,450 sample sizes; the abstract says "reproduces the median and maximum" without the 17% maximum gap. The risk ensemble's CVaR95 is the worst of five; the paper does not caveat in the abstract. The optimizer case is one run. The Dogrib comparison is one fire with no uncertainty. A benchmark paper should report distributions, not selected point estimates.

**Reproducibility.** This is the paper's central claim, and it fails:

- Archive private; no DOI; no public URL.
- Support map and 24 calibration tiles frozen, not regenerated from block geometry.
- `make calibrate` produces 12 tiles, not 23; the paper's 23-tile map is an older artifact.
- `make transfer` produces 1.065/5.257/5.459/5.541, not the paper's 1.495/4.799/4.680/6.121.
- `make event-sim` writes the 30-day result (73.5% median absolute bias), not the paper's 90-day result (58.6%).
- The 655.5 s runtime is not in the current JSON (727.1).
- The reproducibility manifest's optimizer/risk hashes do not match the current files.
- `requirements.txt` unpinned; no lock/container; no clean-machine run.
- The 24 calibration tiles are not hashed in the manifest; the raw cache is gitignored.
- The archive README says the full raw-data rerun is not complete (`README.md:5-10, 103-108`).

**Writing and presentation.** The paper is 8 pages and reads as a project summary. The title "A reproducible TSA24 open fire-regime benchmark: layers, calibration, and estate-scale cases" promises a benchmark/data descriptor; the content is a set of results. The abstract is dense with numbers but does not state what the benchmark task is, what a user should run, or what a successful comparison looks like. The results section has a concrete figure/label error: the text says the transfer test is shown in `Figure~\ref{fig:transfer}` (`sections/3_results.tex:19-22`), but the figure environment at `sections/3_results.tex:43-48` includes `fig3-calibration.png` with the caption "Regional calibration residuals" and `\label{fig:transfer}`. The paper has no transfer figure (`figures/` has no `fig4-transfer.png`). The table `tab:calibration` omits over-100/over-5,000 and sample sizes. The "benchmark case summary" table (`sections/3_results.tex:57-71`) mixes a risk median, a five-year fixed-schedule case, and a harvest-only optimizer case as if they were comparable.

**Required revisions (minimum).**

1. Decide what the paper is: a data descriptor or a model-evaluation paper. A Data in Brief submission requires a public dataset with a DOI, a data dictionary, licence/attribution, a reuse example, and a known-failure table.
2. Regenerate the support map from block geometry and the 24 calibration tiles from raw; document the 198,564 assigned blocks and the area weights.
3. Make the archive public, add a DOI, pin the environment, and run the full pipeline on a clean host; include the exact command for the 90-day event table.
4. Fix the `make calibrate`/`make transfer`/`make hierarchical` targets so they reproduce the paper's numbers, or change the paper to the numbers they produce.
5. Add the FireSTARR TSA24 failure and the absent TSA24 external benchmark to the known-failure table; do not call Dogrib a TSA24 benchmark.
6. Add CIs and full tables; remove selective reporting.
7. If the data cannot be public, do not submit to Data in Brief; publish a technical report or merge the data description into Paper 1.

**Decision.** **Kill as a standalone paper.** The data/software package is potentially useful, but the paper does not meet the minimum for a data descriptor or a benchmark, and the public-data/reuse claim is false. It should become a technical report or a data-availability section of Paper 1. Data in Brief is not a venue for a private, frozen, partially rerun package with a one-fire external check.

## 5. Program-plan review

**What the plan gets right.** `notes/design/ws4-fire-research-program.md` is the most honest document in the portfolio. Its "honest starting point" correctly identifies the in-sample calibration, negative transfer, demonstration-only estate case, harvest-only optimizer, one-fire Dogrib benchmark, and frozen support map/24 layers (`:7-19`). Its shared principles (pre-register, separate calibration from validation, use independent data, benchmark externally, propagate uncertainty, report failures, keep the path reproducible) are the right principles (`:24-36`). Its Paper 2 go/no-go is a real gate, and its Paper 3 required-work list is a real checklist (`:95-111, 123-129`). The "success criteria" (`:152-162`) are sensible.

**What the plan does not do.**

1. **It has no timetable, owners, budget, compute, or decision points.** The "immediate next actions" (`:164-171`) are six unchecked boxes. There is no estimate of how long the independent event inventory, support-map regeneration, temporal/spatial refit, hierarchical model, fire-risk objective, near-global baseline, and public archive will take. The plan is a wish list, not a feasible schedule.
2. **The gates are mostly intentions, not falsifiable checklists.** Paper 1's gate says "the paper is publishable as a validation if the protocol is followed and the result is reported, whether positive or negative" (`:81-82`). That is not a gate; a protocol can be followed and still produce an uninformative n=10 result. The plan does not specify minimum n, power, effect sizes, CIs, or what counts as "independent." The current event test would pass this gate on a literal reading, which shows the gate is too weak.
3. **The plan's Paper 1 and Paper 4 overlap.** Paper 1 is an independent validation paper; Paper 4 is a methods/software paper that "should cite Paper 1 for validation and Paper 2 for the optimization application" (`:131-139`). But the regime draft is already a methods/software paper that includes validation and optimization. There is no distinct Paper 4 draft. The plan's four-paper structure is not the four drafts' structure.
4. **The plan's Paper 2 is correctly blocked, but the draft exists.** The plan says "no paper until the fire-aware objective changes the schedule or the null result is demonstrated against a near-global baseline" (`:110-111`). The optimization draft does neither. The plan should mark it killed/merged, not "current blocker."
5. **The plan's Paper 3 required work is unstarted.** "derive the support map from block geometry, not a frozen NPZ; regenerate the 24 named calibration layers from raw; one-command pipeline from raw sources to results; DOI, licence audit, and clean-machine run; reuse example and known-failure table" (`:123-129`). None is done. The benchmark draft is not a data descriptor.
6. **The plan has no authorship/credit/data-governance section.** The data come from `femic-tsa24-instance`; the manuscripts do not cite or acknowledge that repository or its authors. The plan says "the other agent works asynchronously in `femic-tsa23-instance`" in AGENTS, but there is no credit/authorship/decision-rights plan. The four manuscripts have a provisional sole author while title pages say co-authors are pending. This is a dispute risk.
7. **The plan's "external benchmark" is not operationalized.** It lists FSim, BurnP3+, FireSTARR, or Cell2Fire "on a shared landscape; document input differences" (`:31-33`). The only completed comparison is one Dogrib fire; FireSTARR on TSA24 crashed with SIGFPE (`protocol/event-validation.md:108-115`). The plan does not say what happens if no external model runs on TSA24, which is the current state.
8. **The plan's uncertainty requirement is not operationalized.** It says "bootstrap potential sample, parameter posterior, weather ensemble, observation error" (`:73-76`). The current work has five seeds only; no parameter posterior, no weather ensemble, no observation error. The plan should specify the minimum uncertainty analysis for each paper.
9. **The plan's "open data" depends on unresolved licences.** VRI/BC Wildfire are OGL-BC with attribution; SRTM is public domain; Open-Meteo is CC BY 4.0 but the free endpoint is non-commercial; the Dogrib sample has no explicit licence; the compiled TSA24 artifact's terms are unclear. The plan does not include a licence decision tree or a fallback if redistribution is not permitted.
10. **The plan is not a submission plan; it is a research plan.** It says "supersedes the four manuscript drafts as a submission plan" (`:3`), but it does not decide which drafts die, which merge, or which venue gets which contribution. The portfolio note `p164-publication-concepts.md:36-45` already recommends a smaller portfolio; the plan should follow it.

**Plan-versus-evidence table.**

| Plan requirement | Current evidence | Status |
| --- | --- | --- |
| Independent temporal/spatial validation | Event test uses calibration fires; one event in training tile; no temporal refit | Not met |
| Event-level spatial metrics (area, perimeter, centroid, IoU, Sorensen, orientation) | Only area bias in `event-simulations-validation-90d.json`; protocol lists spatial metrics | Not met |
| Uncertainty (bootstrap, posterior, weather, observation) | Five seeds only; one event draw; no CIs | Not met |
| External benchmark on shared landscape | One Dogrib fire; FireSTARR TSA24 SIGFPE; no FSim/BurnP3+/Cell2Fire | Not met |
| Fire-aware optimization | Harvest-only target; fire-blind identical schedule | Not met |
| Near-global baseline / quality bound | None | Not met |
| Support map from block geometry | Frozen NPZ; README says not regenerated | Not met |
| 24 calibration layers from raw | Frozen NPZ; not hashed | Not met |
| One-command pipeline | `make` targets produce different numbers; event target wrong | Not met |
| DOI, licence audit, clean-machine run | Private archive; no DOI; no clean-machine run | Not met |
| Reuse example, known-failure table | None in manuscript; archive has partial known-failure list | Not met |
| Authorship/funding/competing interests | Sole author provisional; funding pending; data provider uncredited | Not met |

**Plan verdict.** The plan is a good diagnosis and a useful internal roadmap. It is not a feasible submission plan on the current evidence timeline, and it should not be used to justify submitting the four drafts. Its first act should be to kill/merge the drafts that fail its own gates, then fund the independent validation and fire-aware optimization work. The plan's own "honest starting point" says the drafts are not publication-grade; the review agrees.

## 6. Portfolio and salami-slicing assessment

**Overlap matrix.**

| Result | Paper 1 regime | Paper 2 calibration | Paper 3 optimization | Paper 4 benchmark |
| --- | --- | --- | --- | --- |
| Global calibration no-go | Yes | Yes | No | Yes |
| 23-region in-sample map | Yes | Yes | No | Yes |
| Transfer scores / hierarchical ridge | Yes | Yes | No | Yes (partial) |
| Event validation | Yes | Yes | No | No |
| Five-seed risk ensemble | Yes | No | No | Yes |
| Five-year fixed-schedule estate case | Yes | No | Mentioned | Yes |
| Sharded optimizer | Yes | No | Yes | Yes |
| Dogrib/FireSTARR | Yes | No | No | Yes |
| Layer/support data | Yes (methods) | Yes (methods) | Yes (methods) | Yes (main) |

Paper 1 contains every result. Paper 2 is a subset (calibration + transfer + event). Paper 3 is a subset (optimizer + estate). Paper 4 is a superset of the data/results with less analysis. The figures are reused across repositories: `fig1-workflow.png`, `fig2-support.png`, `fig3-calibration.png`, `fig5-risk.png` appear in multiple papers. The same numbers (1.495, 6.121, 4.799, 6.540, 5.182, 8,374.1, 655.5) appear in three or four papers. This is not four independent contributions; it is one contribution sliced four ways.

**Is the four-paper split justified?** No.

- Paper 2 (calibration/transfer) is the scientific core of Paper 1; it should be a section, not a separate paper, unless it adds a genuinely independent temporal validation that Paper 1 does not contain.
- Paper 3 (optimization) is a feasibility note with no fire objective; it is not a paper. It should be a subsection of Paper 1 or a technical report.
- Paper 4 (benchmark) is a data/software package; it is not a paper until the data are public and the frozen inputs are regenerated. It should be a technical report/Zenodo archive, then a data descriptor if the data are reusable.
- Paper 1 is the only draft with a plausible standalone contribution (open integration + negative diagnostic), but it is too broad and contains the false validation claim. It should be narrowed and revised.

**Recommended portfolio.**

Option A (preferred, lowest risk):

1. One paper: "An open, auditable fire-regime layer for spatial forest estate optimization: integration and a negative calibration/transfer diagnostic." Target *Environmental Modelling & Software* or *Geoscientific Model Development*. It includes the architecture, the global no-go, the in-sample regional fit, the training-only transfer diagnostic, the in-sample event reconstruction, the risk/estate cases, and the optimizer feasibility note. It explicitly does not claim independent validation, operational skill, fire-aware optimization, or a global optimum.
2. One public archive: code, layer manifest, support map, 24 calibration tiles regenerated from raw, results, seeds, environment lock, licence/attribution, known-failure table, DOI. This is the benchmark/data contribution; it can be a technical report and a Zenodo DOI, not a Data in Brief paper until reuse is demonstrated.

Option B (only if the new evidence is done):

1. Paper 1 as above (integration/diagnostic).
2. Paper 2: a genuinely independent temporal/spatial validation with pre-registration, an event inventory independent of calibration, spatial metrics, multiple draws/weather ensembles, CIs, and an external benchmark. Target *International Journal of Wildland Fire*.
3. Paper 3: a genuinely fire-aware optimization with a near-global baseline and quality bound. Target *Canadian Journal of Forest Research* or *Environmental Modelling & Software*.
4. Data descriptor: public data/DOI/reuse. Target *Data in Brief*/*Scientific Data*.

Option B is a multi-month program, not a revision. The current drafts are not Option B.

**Venue strategy.** The declared venues are aspirational, not matched to the evidence:

- *Environmental Modelling & Software* for Paper 1: plausible only if the paper is a software/integration paper with a rigorous evaluation; the current 17-page bundle and false "process-coupled" table will draw an "engineering, not science" rejection.
- *International Journal of Wildland Fire* for Paper 2: plausible only with independent fire-science validation; the current paper is an in-sample calibration diagnostic. *Fire* is the better fit for a negative diagnostic, but even *Fire* will require the leakage fix and CIs.
- *Canadian Journal of Forest Research* for Paper 3: not credible. CJFR expects a management/optimization contribution; a 7-page harvest-area feasibility demo with no baseline is a desk-reject risk. *Forests* is not a rescue.
- *Data in Brief* for Paper 4: not credible until the data are public and reusable. *Scientific Data* is a higher bar, not a backup.

**Authorship/funding/competing interests.** The sole-author/provisional-co-author inconsistency, the missing funding statement, the uncredited data provider, the private archive, the missing DOI, and the unresolved licences are all submission blockers. The generative-AI declaration is present and appropriately specific, but the number of factual inconsistencies in the manuscripts (655.5/727.1, 1.495/1.065, 3,450/690, 23/12, "independent"/in-sample) suggests the declared review of AI-assisted outputs was not effective. That is a credibility problem, not a formal ethics violation. The competing-interest declaration for the WS4/WS3 developer is adequate; the data-provider credit is not.

## 7. Ten questions a hostile referee will ask

Each question is followed by the evidence needed to answer it. If the evidence does not exist, the paper should not be submitted.

**Q1. Were the ten event-validation fires used to fit the regional suppression map?**
Answer needed: a refit that excludes every validation event and every post-2017 fire from the calibration history, plus a table showing the excluded fires. Evidence now: 8/10 event areas match `raw/history` values; `calibrate_regions.py` has no year filter. Without the refit, the answer is yes, and the "independent" claim is false.

**Q2. How can a 2023-only weather sample reproduce a multi-year historical fire-size distribution?**
Answer needed: a multi-year weather sample, or a year-stratified calibration/validation showing that the 2023 weather year is not doing the work. Evidence now: `build_potential.py` fixes 2023-02-01 to 2023-09-30; the historical perimeters span 1950-2024; the paper reports one 2023 season only.

**Q3. What is the effective sample size for the regional calibration: 3,450, 690, or 432?**
Answer needed: a clear statement that 3,450 = 5 realizations × 690 potential fires, that the 5 realizations are not independent, and bootstrap CIs over the 690 potential fires and the 432 historical fires. Evidence now: `calibrate_regions.py:51-55` loops 5 reps; the table calls them "Fires." The paper's precision is overstated.

**Q4. Are the method differences statistically significant?**
Answer needed: paired bootstrap/permutation tests across the 11 tiles and 10 events, with intervals. Evidence now: global vs potential analogue 95% CI [-2.74, +0.15]; ridge vs pooling [-2.97, +0.25]; event median bias CI [-49.1, +358.6]. Several headline rankings are not significant.

**Q5. Why is the best deployable baseline (training median 4.68) not the comparator?**
Answer needed: a full table with training median, complete pooling, global, analogue, and hierarchical ridge, and a statement of which is best. Evidence now: the training median is better than the "complete pooling" 5.18 used in the abstract; the paper emphasizes the worst deployable baseline.

**Q6. Is the "hierarchical/empirical-Bayes" model actually hierarchical?**
Answer needed: model equations, group-level variance, partial pooling of residuals, a proper posterior or empirical-Bayes derivation, and a lambda sensitivity that does not sit at the grid boundary. Evidence now: it is six independent ridge regressions with a shared penalty (`hierarchical_validation.py:144-148`); lambda 100 is the largest grid value; no posterior.

**Q7. Does the optimizer have a fire-risk objective, and does fire change the schedule?**
Answer needed: an objective with a fire term, a fire-blind vs fire-aware vs burn-probability-overlay comparison, multiple seeds, and a schedule difference. Evidence now: the objective is `harvest.area_ha_total` with a 10% minimum; the fire-blind schedule is identical; the fire source is three fixed ignitions with constant weather.

**Q8. Is 655.5 s reproducible, and what is the sequential baseline?**
Answer needed: the exact command, hardware, repetitions, and a sequential run. Evidence now: the current JSON says 727.1 s; the fire-blind run says 865.7 s; the paper says 655.5 s; no sequential baseline.

**Q9. Can a reader obtain the layer cache, support map, 24 calibration tiles, and raw data?**
Answer needed: a public DOI, a clean-machine run, a data dictionary, hashes for the 24 tiles, and a regenerated support map from block geometry. Evidence now: archive private; support map/24 tiles frozen; 24 tiles not in `MANIFEST.json`; `make calibrate` produces 12 tiles; raw cache gitignored.

**Q10. Is the Dogrib one-fire comparison an external benchmark for TSA24?**
Answer needed: a TSA24-specific benchmark on a shared landscape with FSim, BurnP3+, FireSTARR, or Cell2Fire, or a clear statement that no such benchmark exists. Evidence now: one Dogrib fire in Alberta, different inputs, one deterministic run; FireSTARR TSA24 crashed with SIGFPE; no TSA24 external result.

Optional Q11 (the one an editor will ask): **Why are there four papers with the same results?** Answer needed: a contribution matrix showing non-overlapping questions and a citation plan. Evidence now: Paper 1 contains every result; Papers 2-4 are subsets; the authors' own portfolio note recommends a smaller portfolio.

Optional Q12 (the one a data editor will ask): **What is the licence and attribution for VRI, BC Wildfire, Open-Meteo, SRTM, and the compiled TSA24 artifact?** Answer needed: a licence table, attribution text, data-owner sign-off, and a redistribution decision. Evidence now: `DATA_LICENSES.md` is a draft with unchecked release actions; the papers do not include the attribution; the archive is private.

## 8. Minimum publishable path and kill criteria

### 8.1 Cross-cutting minimum (all papers)

1. **One public archive with a DOI.** Code, manifest, support map, 24 calibration tiles, compact results, seeds, environment lock/container, licence/attribution, known-failure table. A private GitHub repo is not a reproducibility package.
2. **One clean-machine run.** `make resolve -> make layers -> make potential -> make calibrate -> make transfer -> make hierarchical -> make risk -> make estate -> make optimizer -> make verify` must reproduce the paper's numbers, or the paper must report the numbers the pipeline produces.
3. **One evidence table.** Every number in every manuscript must map to a JSON key or a table in the archive. The current 655.5/727.1, 1.495/1.065, 3,450/690, 23/12, and hash mismatches must be resolved.
4. **One statistical standard.** Bootstrap/paired intervals for all comparisons; report n, effective n, exclusions, and sensitivity; do not call a five-seed worst case "CVaR95" without a caveat; do not call an in-sample fit "upper bound" without explaining the direction.
5. **One claim boundary.** No "independent" unless the calibration excludes the validation data; no "operational" unless there is an operational test; no "global optimum" unless there is a global solve; no "benchmark" unless there is a common task and a baseline; no "open data" unless the data are public.
6. **One authorship/data-governance statement.** Final author list, CRediT, funding, competing interests, data-provider credit, licence sign-off, DOI. The current "provisional co-authors" and uncredited `femic-tsa24-instance` are not acceptable at submission.

### 8.2 Paper 1 (regime) minimum

- Remove the "independent" event claim or make it independent (exclude validation events, refit on training tiles/years, multiple draws, spatial metrics, CIs).
- Refit the regional map on `t01`-`t12` only and report its true held-out score; keep the in-sample fit as a separate diagnostic.
- Report the full global training/validation gate table.
- Report the 7-day potential-fire cap and the 2023-only weather; either extend to multi-year weather or state the limitation clearly.
- Fix the positioning table: "process-coupled" is false, "open data end-to-end" is false, "full-estate" is partial.
- Remove "practical value" unless a decision analysis is added; report the 0.126% volume effect and compare it to uncertainty.
- Use one authoritative runtime and report hardware/sequential baseline.
- Publish the archive and regenerate the support map/24 tiles.
- Report the FireSTARR TSA24 failure and the 30-day/90-day event sensitivity.
- Narrow the paper to one contribution; move the event test to a separate paper only if it becomes independent.

If these are done, Paper 1 can be a credible *EMS*/*GMD* methods and negative-diagnostic paper. If they are not, it should not be submitted.

### 8.3 Paper 2 (calibration) minimum

- Refit the regional map on training tiles/years only; freeze it; evaluate on the validation tiles/years.
- Make the event test independent or remove it.
- Add paired CIs; report the full table including training median, complete pooling, global, analogue, and ridge; use the best baseline in the abstract.
- Report the full global gate table, per-tile n, and the lambda boundary.
- Correct the feature description (five vs seven) and report donor distances/sensitivity.
- Call the ridge a ridge regression; use a proper hierarchical model if the "hierarchical" claim is kept.
- Remove causal claims about suppression capacity/access/response; frame them as hypotheses.
- Add an external benchmark on the same tiles/events, or merge into Paper 1.

If these are done, Paper 2 can be a credible short negative-result paper in *Fire* or *IJWF*. If the event test cannot be made independent, it should be a section of Paper 1, not a standalone paper.

### 8.4 Paper 3 (optimization) minimum

- Add a fire-risk term (CVaR burned area/volume loss) to the objective and show a schedule change.
- Add a near-global baseline on a reduced estate (10-20 tiles) or a coordinated decomposition with quality bounds.
- Use the calibrated ignition/weather process, multiple seeds, and a risk ensemble.
- Report the decision-space coverage (2,240/458,708) and call the result a feasible schedule, not an optimization.
- Report runtime with hardware, repetitions, and a sequential/scaling baseline.
- Add volume/NPV/flow, burned area, CVaR, biomass; compare to the fixed five-year schedule.
- Make the archive reproducible; add seeds/commands.

If the fire-aware objective does not change the schedule, kill the standalone paper and merge the feasibility note into Paper 1.

### 8.5 Paper 4 (benchmark) minimum

- Make the data public with a DOI: layer cache, support map, 24 calibration tiles, compact results, manifests, seeds, licence/attribution.
- Regenerate the support map from block geometry and the 24 calibration tiles from raw; document the 198,564 assigned blocks and area weights.
- Add a data dictionary, per-layer provenance, reuse example, known-failure table, and clean-machine run.
- Fix the `make` targets so they reproduce the paper; otherwise change the paper.
- Add a TSA24-specific external benchmark, or state that the paper is a data descriptor, not a benchmark.
- If the data cannot be public, do not submit to Data in Brief; publish a technical report or merge the data description into Paper 1.

### 8.6 Kill criteria

- **Kill the independent-validation claim** if the calibration cannot exclude the validation events and the validation tiles/years. The event result can remain as an in-sample reconstruction, but not as validation.
- **Kill Paper 2 as a standalone** if it cannot add a genuinely independent temporal/spatial test; merge it into Paper 1.
- **Kill Paper 3 as a standalone** if the fire-aware objective does not change the schedule or no near-global baseline exists.
- **Kill Paper 4 as a standalone** if the data cannot be public, the support map/24 tiles cannot be regenerated, or there is no DOI/reuse example.
- **Kill the four-paper portfolio** if the overlap matrix remains as it is; submit one paper plus one archive.
- **Kill any claim** that the model is "operational," "validated," "fire-aware," "global," or a "benchmark" without the specific evidence above.

### 8.7 Decision tree

1. Can the archive be made public with a DOI and a clean-machine run in the next revision cycle?
   - No: stop. Do not submit any paper. The reproducibility claims are central.
   - Yes: continue.
2. Can the event validation be made independent (exclude validation events, refit on training tiles/years, multiple draws, spatial metrics)?
   - No: remove the independent-validation claim; make Paper 1 a methods/diagnostic paper; merge Paper 2.
   - Yes: Paper 2 can be a standalone validation paper; Paper 1 cites it.
3. Can the optimizer get a fire-risk objective and a near-global baseline?
   - No: kill Paper 3; merge a feasibility note into Paper 1.
   - Yes: Paper 3 can be a standalone optimization paper.
4. Can the data be public and reusable with a DOI/reuse example?
   - No: kill Paper 4; technical report only.
   - Yes: Paper 4 can be a data descriptor.
5. Does the resulting portfolio have non-overlapping contributions?
   - No: merge.
   - Yes: submit.

## 9. Exact-file/line appendix

The following table lists the evidence used in this review. Paths are repository-relative to the four manuscript repos and the archive; the repositories are siblings in the review workspace. Line numbers are the file line numbers at the time of review. JSON values are cited by key because JSON line numbers are not stable.

### 9.1 Manuscript claims

| Finding | File | Lines / key | Evidence |
| --- | --- | --- | --- |
| "Open, reproducible coupling" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 3-8 | Archive private; support map/24 tiles frozen; `make transfer` produces different numbers. |
| Global calibration "failed its training gates" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 10-11 | Omits validation p90/max failures in `notes/reports/p164-8-regime-calibration.md:33-47`. |
| "23-region in-sample calibration reproduced ... maximum" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 11-13 | Maximum 17.3% low; `region-calibration.json` max 20,770.4 vs historical 25,114.8. |
| "Independent transfer to 11 held-out tiles" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 13-14 | `region-calibration.json` has t13-t23; `calibrate_regions.py:69-85` fits each tile on its own history. |
| "Empirical-Bayes ridge ... did not outperform complete pooling (5.18)" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 15-16 | `hierarchical_validation.py:144-148` ridge; lambda 100 boundary; training median 4.68 better. |
| "Independent point-ignition test on ten TSA24 events" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 18-20 | 8/10 event areas in `raw/history`; G12186 in training tile t03. |
| "CVaR95 volume loss" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 22-23 | `risk-ensemble-5seed.json`: cvar95 = 1,036,485.94, tail_count 1, 5 seeds. |
| "179-event schedule ... 655.5 s" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 25-26 | `optimizer-full-estate.json`: schedule_events 179, elapsed_seconds 727.1. |
| Dogrib "191% vs 36%" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 26-27 | `p157-firestarr-comparison.md:26-30`; WS4 Scenario 2b +58.9% / IoU 0.385 in `p157-observed-validation.md:79-87` not reported. |
| "Practical value" | `fresh_ws4_fire_regime_manuscript/sections/0_abstract.tex` | 30-31 | Volume loss 1.04M/822.55M = 0.126%; no decision analysis. |
| "Process-coupled" / "Open data end-to-end" / "Full-estate BC case" | `fresh_ws4_fire_regime_manuscript/sections/1_introduction.tex` | 61-64 | Harvest-only objective; private/frozen data; 2,240/458,708 blocks. |
| "Inputs ... available for inspection" | `fresh_ws4_fire_regime_manuscript/sections/1_introduction.tex` | 23-29 | Private archive; frozen support map/24 tiles. |
| "90-day antecedent ... tail-event sampling" | `fresh_ws4_fire_regime_manuscript/sections/2_methods.tex` | 37-38 | `build_potential.py:27` `ACTIVE_DAYS_MAX=7`; `:289-293` caps active days. |
| "247 ... ten validation fires ... calibrated regional map" | `fresh_ws4_fire_regime_manuscript/sections/2_methods.tex` | 54-60 | `calibrate_regions.py` uses all history; event selection no tile filter. |
| "30 per tile ... global 1,500" | `fresh_ws4_fire_regime_manuscript/sections/2_methods.tex` | 90-94 | Regional uses 23 tiles/690; 5 realizations; `region-calibration.json` n=150 per tile. |
| "every tile with at least five historical fires" | `fresh_ws4_fire_regime_manuscript/sections/2_methods.tex` | 100-101 | Some tiles have 6, 7, 8 historical fires; six parameters. |
| "Parameters were frozen before validation" | `fresh_ws4_fire_regime_manuscript/sections/2_methods.tex` | 106-109 | Regional map includes t13-t23; only training-only baselines frozen. |
| Seven-feature analogue | `fresh_ws4_fire_regime_manuscript/sections/2_methods.tex` | 118-120 | `validate_transfer.py:90-98` uses five features. |
| "bounded decomposition heuristic ... not global" | `fresh_ws4_fire_regime_manuscript/sections/2_methods.tex` | 154-156 | Correct; but title/abstract call it optimizer. |
| "Fires 432 vs 3,450" | `fresh_ws4_fire_regime_manuscript/sections/3_results.tex` | 40 | `region-calibration.json` metrics n=150 × 23; 5 reps. |
| "Complete pooling 5.182" / "Hierarchical ridge 6.540" | `fresh_ws4_fire_regime_manuscript/sections/3_results.tex` | 77-83 | Not defined in methods; training median 4.680 better. |
| "global fit 5.287 in that run" | `fresh_ws4_fire_regime_manuscript/sections/3_results.tex` | 93-94 | Table says 4.799; two scores unexplained. |
| "Two ... moved ... nearest burnable cell within 12.5 km" | `fresh_ws4_fire_regime_manuscript/sections/3_results.tex` | 141-145 | `_nearest_burnable` square search `run_event_simulations.py:60-71`; not nearest; no distance recorded. |
| "caps ... not small-event overpredictions" | `fresh_ws4_fire_regime_manuscript/sections/3_results.tex` | 143-145 | G51212 151.7 ha capped from 144.9 days; false. |
| "confirm the independent-transfer diagnosis" | `fresh_ws4_fire_regime_manuscript/sections/3_results.tex` | 147-148 | Event test is in-sample; cannot confirm independence. |
| "five-year ... 8,374.1 ... 179 blocks/events ... 655.5" | `fresh_ws4_fire_regime_manuscript/sections/3_results.tex` | 185-192 | 8,374.1 is `risk-ensemble-5seed.json` seed 20261122; 179 harvest entries; 727.1 current. |
| Dogrib "same order of magnitude" | `fresh_ws4_fire_regime_manuscript/sections/3_results.tex` | 218-222 | One fire; raw wind; different inputs; no uncertainty. |
| "failures identify the missing process" | `fresh_ws4_fire_regime_manuscript/sections/4_discussion.tex` | 37-43 | Event test cannot identify cause; leakage/weather/snap/duration confounds. |
| "directly useful" | `fresh_ws4_fire_regime_manuscript/sections/5_conclusion.tex` | 16-18 | No decision analysis; fire effect 0.126% volume. |
| "We test whether a regional suppression calibration transfers to held-out tiles" | `fresh_ws4_fire_calibration_manuscript/sections/0_abstract.tex` | 4-5 | Regional map fitted on all 23 tiles. |
| "On the fixed 11-tile holdout, the in-sample score..." | `fresh_ws4_fire_calibration_manuscript/sections/0_abstract.tex` | 12 | In-sample row uses validation tiles' own fits. |
| "6.12 potential analogue ... 4.80 global ... 4.68 training median" | `fresh_ws4_fire_calibration_manuscript/sections/0_abstract.tex` | 12-14 | Paired CI global-potential [-2.74,+0.15]; analogue 5 features. |
| "ridge 6.54 ... complete pooling 5.18" | `fresh_ws4_fire_calibration_manuscript/sections/0_abstract.tex` | 14-15 | Lambda 100 boundary; training median 4.68; ridge-pooling CI includes 0. |
| "ten independent TSA24 events" | `fresh_ws4_fire_calibration_manuscript/sections/0_abstract.tex` | 16-17 | 8/10 in history; G12186 training tile. |
| "transferable model needs suppression-capacity covariates..." | `fresh_ws4_fire_calibration_manuscript/sections/0_abstract.tex` | 21-23 | Hypothesis, not tested. |
| "regions differ in suppression capacity..." | `fresh_ws4_fire_calibration_manuscript/sections/4_discussion.tex` | 18-21 | No covariates measured; causal overreach. |
| "six methods" | `fresh_ws4_fire_calibration_manuscript/sections/2_methods.tex` | 48-58 | Table has five; complete pooling/hierarchical only in text. |
| "seven features" | `fresh_ws4_fire_calibration_manuscript/sections/2_methods.tex` | 54-56 | `validate_transfer.py:90-98` five. |
| "global training fit failed ... no validation-tile tuning" | `fresh_ws4_fire_calibration_manuscript/sections/2_methods.tex` | 25-28 | Global validation also failed p90/max; regional fit uses validation tiles. |
| "The regional map is in-sample" | `fresh_ws4_fire_calibration_manuscript/sections/2_methods.tex` | 39 | Correct; contradicts abstract "holdout." |
| "lambda 100 ... 6.540 ... 5.182 ... 5.287" | `fresh_ws4_fire_calibration_manuscript/sections/3_results.tex` | 82-85 | `hierarchical-validation-simcv.json`; lambda boundary not mentioned. |
| "The test failed ... 58.6%" | `fresh_ws4_fire_calibration_manuscript/sections/3_results.tex` | 96-98 | n=10, one draw, no CI; leakage. |
| "calibrated FBP-based fire source" | `fresh_ws4_fire_optimization_manuscript/sections/0_abstract.tex` | 6-7 | `full_estate_optimizer.py:224-259` three fixed ignitions, constant weather. |
| "20 blocks ... 10% local harvest target ... 179 events" | `fresh_ws4_fire_optimization_manuscript/sections/0_abstract.tex` | 7-10 | 2,240/458,708 blocks; `Target` harvest.area_ha_total; 179 harvest entries. |
| "74.25 ha ... 16 fragment-level fire events" | `fresh_ws4_fire_optimization_manuscript/sections/0_abstract.tex` | 12-13 | Three fixed ignitions; 16 fragments; not a risk estimate. |
| "655.5 s" | `fresh_ws4_fire_optimization_manuscript/sections/0_abstract.tex` | 13 | `optimizer-full-estate.json` 727.1. |
| "fire-blind repeat ... harvest-only" | `fresh_ws4_fire_optimization_manuscript/sections/0_abstract.tex` | 15-17 | Correct; this kills the fire-risk premise. |
| "selects up to 20 largest ... two hill-climb rounds" | `fresh_ws4_fire_optimization_manuscript/sections/2_methods.tex` | 14-17 | `full_estate_optimizer.py:122, 163-168`; feasibility target. |
| "not an all-block optimization" | `fresh_ws4_fire_optimization_manuscript/sections/2_methods.tex` | 19-20 | Correct; 2,240/458,708. |
| "far below a fully sequential equivalent" | `fresh_ws4_fire_optimization_manuscript/sections/3_results.tex` | 57-59 | No sequential run. |
| "embarrassingly parallel ... HPC" | `fresh_ws4_fire_optimization_manuscript/sections/4_discussion.tex` | 19-22 | One 36-worker workstation run. |
| "reproducible TSA24 benchmark" | `fresh_ws4_fire_benchmark_manuscript/sections/0_abstract.tex` | 4-5 | Private archive; frozen inputs; different make outputs. |
| "exact commands needed to rebuild" | `fresh_ws4_fire_benchmark_manuscript/sections/0_abstract.tex` | 18-20 | `make calibrate` 12 tiles; `make transfer` refit; `make event-sim` 30-day. |
| "preserves all 458,708 compiled blocks" | `fresh_ws4_fire_benchmark_manuscript/sections/2_methods.tex` | 15-19 | 198,564 blocks assigned to representative cells; frozen. |
| "Figure~\ref{fig:transfer}" but calibration figure | `fresh_ws4_fire_benchmark_manuscript/sections/3_results.tex` | 19-22, 43-48 | `fig3-calibration.png` labeled `fig:transfer`; no fig4-transfer. |
| "benchmark supports reproducibility..." | `fresh_ws4_fire_benchmark_manuscript/sections/4_discussion.tex` | 6-7 | No public data; no TSA24 model comparison. |
| "A user can replace ... keeping the layer cache" | `fresh_ws4_fire_benchmark_manuscript/sections/4_discussion.tex` | 13-16 | Cache local/private; false. |

### 9.2 Archive evidence

| Finding | File | Lines / key | Evidence |
| --- | --- | --- | --- |
| Archive status partial | `fresh_ws4_fire_regime_repro/README.md` | 5-10 | "partial raw-data rerun"; support map/24 tiles frozen. |
| Support map frozen | `fresh_ws4_fire_regime_repro/README.md` | 51-54 | "not yet scripted here"; 24 named calibration tiles frozen. |
| Archive private | `fresh_ws4_fire_regime_repro/README.md` | 107 | Link says private; `gh repo view` confirms. |
| Support map loses blocks | `notes/reports/tsa24-full-support-map.md` | 3-19 | 260,144 distinct cells; 198,564 blocks without a cell; 1,310,129 memberships; 180,074 multi-fragment cells. |
| Support map built from geometry (contradiction) | `notes/reports/tsa24-full-support-map.md` | 32-33 | "built from the public block geometry"; contradicts README. |
| 250m drops blocks | `notes/reports/tsa24-block-support-50m.md` | 3-21 | 250m 2,751/4,593 blocks; 50m 4,593 with fallback. |
| Global gates | `notes/reports/p164-8-regime-calibration.md` | 33-47 | Validation p90 793.28 fail; max 9,474.34 fail; training over-5000 fail. |
| Regional in-sample | `notes/reports/p164-8-region-calibration.md` | 31-45, 58-61 | 432 historical vs 3,450; in-sample. |
| Transfer scores | `notes/reports/p164-8-transfer-validation.md` | 34-57 | 1.495, 4.799, 6.121; nearest donor t03/t04. |
| Hierarchical lambda | `notes/reports/p164-8-hierarchical-validation.md` | 37-83 | Lambda 100 best; 6.540 vs 5.182; 5.287. |
| Fireblind baseline | `notes/reports/p164-8-sharded-fireblind-baseline.md` | 11-26 | 655.5/865.7; same schedule; harvest-only. |
| Estate handoff 655.5 | `notes/reports/p164-8-estate-handoff.md` | 95-110 | 655.5; 112/133; 20 blocks. |
| FireSTARR Dogrib | `notes/reports/p157-firestarr-comparison.md` | 24-45 | WS4 29,480/+191%; FireSTARR 13,808/+36.3%; one fire; no Scenario 2b. |
| WS4 Scenario 2b | `notes/reports/p157-observed-validation.md` | 79-87, 148-161 | +58.9%, IoU 0.385; not reported in paper. |
| FireSTARR TSA24 SIGFPE | `fresh_ws4_fire_regime_repro/protocol/event-validation.md` | 108-115 | "crashes (SIGFPE)"; no TSA24 result. |
| FireSTARR harness removed | `fresh_ws4_fire_regime_repro` git commit | `7a858048` | Removes `results/firestarr-events-smoke.json` and `scripts/run_firestarr_events.py` from manifest. |
| Event result corrected | `fresh_ws4_fire_regime_repro` git commit | `82abdee` | Adds 90-day result; changes README. |
| Event selection leakage | `fresh_ws4_fire_regime_repro/results/event-selection.json` | G41511/G40324 t19; G12186 t03 | Areas 4767.8/142.7/122.7; t19/t03 histories. |
| Event history match | `fresh_ws4_fire_regime_repro/raw/history/t19.json` | sizes_ha includes 4767.802 | Fits calibration. |
| Event snap code | `fresh_ws4_fire_regime_repro/scripts/run_event_simulations.py` | 60-71, 126-131 | Square search, first row-major, radius 49; not nearest. |
| Event duration cap | `fresh_ws4_fire_regime_repro/scripts/run_event_simulations.py` | 100-112 | `min(90, duration+1)`; 420-day records. |
| Potential 7-day cap | `fresh_ws4_fire_regime_repro/scripts/build_potential.py` | 27, 289-293 | `ACTIVE_DAYS_MAX=7`; weather stopping. |
| 2023-only weather | `fresh_ws4_fire_regime_repro/scripts/build_potential.py` | 30-31, 145-150 | 2023-02-01 to 2023-09-30. |
| Calibration no year filter | `fresh_ws4_fire_regime_repro/scripts/calibrate_regions.py` | 69-85 | Reads all `sizes_ha`; uses t13-t23. |
| 5 realizations | `fresh_ws4_fire_regime_repro/scripts/calibrate_regions.py` | 51-55 | `for rep in range(5)`. |
| Transfer features 5 | `fresh_ws4_fire_regime_repro/scripts/validate_transfer.py` | 90-98 | log median, log p90, fwi, bui, wind. |
| Transfer score weights | `fresh_ws4_fire_regime_repro/scripts/validate_transfer.py` | 78-87 | 3,3,2,0.5; no CI. |
| Ridge not hierarchical | `fresh_ws4_fire_regime_repro/scripts/hierarchical_validation.py` | 144-148 | `np.linalg.solve` ridge; six separate. |
| Lambda grid | `fresh_ws4_fire_regime_repro/scripts/hierarchical_validation.py` | 181-194 | 0.01..100; selects min. |
| Optimizer selection | `fresh_ws4_fire_regime_repro/scripts/full_estate_optimizer.py` | 122, 163-168 | 20 largest; harvest area target. |
| Optimizer fire demo | `fresh_ws4_fire_regime_repro/scripts/full_estate_optimizer.py` | 224-259 | 3 ignitions; fwi 30, bui 80, wind 10; constant weather. |
| Fireblind same schedule | `fresh_ws4_fire_regime_repro/MANIFEST.json` | 70-83 | Same SHA `f804...` for both schedules. |
| Optimizer runtime current | `fresh_ws4_fire_regime_repro/results/optimizer-full-estate.json` | `elapsed_seconds` | 727.1. |
| Fireblind runtime | `fresh_ws4_fire_regime_repro/results/optimizer-full-estate-fireblind.json` | `elapsed_seconds` | 865.7. |
| Risk ensemble | `fresh_ws4_fire_regime_repro/results/risk-ensemble-5seed.json` | keys | cvar95 1,036,485.94; tail_count 1; 5 runs. |
| Estate case | `fresh_ws4_fire_regime_repro/results/estate-case-5yr-full-layers.json` | keys | source_events 885; 8,374.1; 156,358.8; dropped_schedule_blocks 1. |
| 12-tile refit | `fresh_ws4_fire_regime_repro/results/region-calibration-refit.json` | keys | 12 keys. |
| 23-tile old map | `fresh_ws4_fire_regime_repro/results/region-calibration.json` | keys | 23 keys. |
| Transfer refit | `fresh_ws4_fire_regime_repro/results/transfer-validation-refit.json` | summary | 1.065/5.257/5.459/5.541. |
| Paper transfer | `fresh_ws4_fire_regime_repro/results/transfer-validation.json` | summary | 1.495/4.799/4.680/6.121. |
| Hier refit | `fresh_ws4_fire_regime_repro/results/hierarchical-validation-refit.json` | summary | 7.356/1.065. |
| Hier paper | `fresh_ws4_fire_regime_repro/results/hierarchical-validation-simcv.json` | summary | 6.540/5.182/5.287/1.495. |
| Hash mismatch | `fresh_ws4_fire_regime_repro/results/reproducibility-manifest.json` | artifacts | optimizer hash `b368...` vs current `0067...`; risk hash `1f97...` vs current `df2e...`. |
| Requirements unpinned | `fresh_ws4_fire_regime_repro/requirements.txt` | 1-8 | `>=` only. |
| Make targets | `fresh_ws4_fire_regime_repro/Makefile` | 31-79 | calibrate train only; transfer old map; event-sim 30-day output. |
| 24 tiles not in manifest | `fresh_ws4_fire_regime_repro/MANIFEST.json` | 58 files | No 24 calibration NPZ; `layers/manifest.json` 133 full tiles. |
| Support map not hashed | `fresh_ws4_fire_regime_repro/MANIFEST.json` | 1-300 | `manifests/tsa24-full-250m-support.npz` is hashed; but not the 24 calibration NPZ. |
| Archive README says partial | `fresh_ws4_fire_regime_repro/README.md` | 5-10, 103-108 | Full raw rerun not complete. |
| Data licence release actions unchecked | `fresh_ws4_fire_regime_repro/DATA_LICENSES.md` | 94-104 | Attribution/DOI/sign-off unchecked. |
| Config split | `fresh_ws4_fire_regime_repro/config/tiles.json` | 2-5 | train t01-t12; validation t13-t24. |
| Sources | `fresh_ws4_fire_regime_repro/config/sources.json` | 38-50 | Compiled TSA24 and schedule from `femic-tsa24-instance`. |

### 9.3 Selected statistics recomputed for this review

These are not in the manuscripts; they are simple checks from the archive JSON. They are included so the authors can reproduce the critique.

| Check | Result | Source |
| --- | --- | --- |
| Event median relative bias | +25.33%; bootstrap 95% [-49.06, +358.60] | `event-simulations-validation-90d.json` |
| Event median absolute bias | 58.64%; bootstrap 95% [43.28, 358.60] | same |
| Event median absolute, excluding 420-day records | 66.88% (n=8) | same |
| Event median absolute, excluding G40324 | 49.91% (n=9) | same |
| Event sign test (6 over, 4 under) | p ≈ 0.754 | same |
| Global vs potential analogue | mean diff -1.322; 95% [-2.739, +0.145] | `transfer-validation.json` |
| Hierarchical ridge vs complete pooling | mean diff -1.358; 95% [-2.972, +0.247] | `hierarchical-validation-simcv.json` |
| In-sample vs global | mean diff -3.792; 95% [-5.737, -1.963] | `transfer-validation.json` |
| Hierarchical ridge vs global | mean diff -1.253; 95% [-2.077, -0.411] | `hierarchical-validation-simcv.json` |

## 10. Bottom line

The WS4 fire program has a real open implementation, a real negative calibration/transfer result, and an honest internal plan. It does not have four publishable papers. The current drafts overclaim independent validation, fire-aware optimization, reproducibility, and benchmark status; the archive does not reproduce several headline numbers; and the event validation is in-sample. The correct decision is not to submit any of the four drafts now.

The shortest defensible path is:

1. Make the archive public and reproducible; regenerate the support map and 24 calibration tiles.
2. Keep one paper: an open integration plus an honestly framed negative diagnostic, with the event test described as in-sample unless and until it is made independent.
3. Kill the standalone optimization paper until a fire-risk objective and a near-global baseline exist.
4. Kill the standalone benchmark paper until the data are public, reusable, and DOI-backed.
5. If the authors want a second paper, make it a genuinely independent temporal/spatial validation with spatial metrics, multiple draws, CIs, and an external TSA24 benchmark. Do not call the current in-sample event test "independent."

A hostile referee will not reject the negative result. A hostile referee will reject the claim that it is independent, reproducible, fire-aware, or a benchmark when the archive shows otherwise.

## 11. Post-review corrections already applied

After this review was written, the following corrections were made and are not reflected in the
line-number appendix above:

- Papers 1 and 2 now call the event exercise an **in-sample reconstruction**, not independent
  validation, and state the calibration-history overlap and the training-tile event.
- Papers 1 and 2 now report bootstrap intervals for the event bias and the transfer comparisons, and
  the sensitivity of the event result to the 420-day records and G40324.
- Papers 1, 3, and 4 now use the current optimizer runtime (727.1 s), not the old 655.5 s.
- Papers 1 and 2 now say the regional maximum is 17% low instead of claiming it was reproduced, and
  describe 3,450 realizations as five draws from 690 potential fires.
- The archive README, protocol, and program plan now state that the event reconstruction is not
  independent.
- The false "independent" claim remains corrected only for the event/transfer exercise. The other
  blockers in this review (fire-aware objective, global baseline, public data/DOI, support-map
  regeneration, clean-host run, four-paper overlap) remain open.

These corrections improve honesty. They do not make the four drafts publishable.
