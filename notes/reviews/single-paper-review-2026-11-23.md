# Single-paper review: the consolidated WS4 fire-regime manuscript

Date: 2026-11-23

Status: read-only scientific review. No manuscript, code, data, or git state was modified. The only file created is this report.

## 0. Scope, method, and limits

Reviewed:

- `fresh_ws4_fire_regime_manuscript`: `main.tex`, `title-page.tex`, every `sections/*.tex`, `README.md`, `planning/manuscript-plan.md`, `references.bib`, `main.log`, `main.pdf`.
- `notes/design/ws4-fire-research-program.md`, `notes/reports/p164-manuscript-portfolio.md`, `notes/reviews/antagonistic-review-2026-11-23.md`, `notes/reports/tsa24-event-validation.md`.
- `fresh_ws4_fire_regime_repro`: `README.md`, `MANIFEST.json`, `protocol/event-validation.md`, `Makefile`, `config/tiles.json`, `scripts/calibrate_regions.py`, `scripts/validate_transfer.py`, `scripts/hierarchical_validation.py`, `scripts/run_event_simulations.py`, `scripts/build_potential.py`, and the current result JSONs under `results/`.
- Internal evidence reports: `notes/reports/p164-8-region-calibration.md`, `p164-8-transfer-validation.md`, `p164-8-hierarchical-validation.md`, `p164-8-benchmark-reproducibility.md`, `p157-firestarr-comparison.md`, `tsa24-full-support-map.md`, `tsa24-full-estate-support.md`, `tsa24-compiled-block-subset.md`.

I did not rerun the model, rebuild the layer cache, rerun FireSTARR, or verify every raw VRI/SRTM/weather download. I checked the manuscript numbers against the archive JSON and code, recomputed the pooled historical metrics from `raw/history/*.json`, and recomputed simple statistics (percentile bootstrap for event bias and transfer paired differences, sign test, exclusion sensitivity). Where I could not reproduce a number from the archive, I say so.

Evidence standard: a claim is supported only when the archive contains an artifact or code path that produces it and the artifact is consistent with the text. A number that appears only in a prose report or a figure is treated as unverified.

## 1. Verdict and one-paragraph assessment

**Verdict: major revision; do not submit. The consolidation produced one file, not one defensible paper.**

The consolidation did real work. It removed the main-text claim that the event reconstruction was independent, added a scope table, added two bootstrap intervals and an event-exclusion sensitivity, and changed the main-text optimizer language to "feasibility search." But it did not reconcile the text with the evidence. The calibration objective described in `sections/2_methods.tex:113-115` is not the objective in `scripts/calibrate_regions.py:41-48`; `make calibrate` produces 12 tiles (`results/region-calibration-refit.json`), not the 23-tile map in Table 2; `make transfer` and `make hierarchical` produce 1.065/5.257/5.459/5.541 and 7.356 at lambda 3.0, not the 1.495/4.799/4.680/6.121 and 6.540 at lambda 100 in the paper; and `make event-sim` produces the 30-day 73.5% result, not the 90-day 58.6% table. The figures still say "Optimization" (Fig. 1), "Held-out transfer" and "Hierarchical ridge" (Fig. 4), and "Dogrib external growth benchmark" (Fig. 6). None of the six figures is cited in the text. The title and abstract say "open, auditable" while the archive is private, partial, and does not rerun the reported tables. The paper is still a four-paper bundle at the level of evidence and argument. The negative-diagnostic framing is defensible in principle, but the statistical design is too thin and the archive too partial for *Environmental Modelling & Software* or *Geoscientific Model Development*. It is not submission-ready.

## 2. Contribution test: one paper or four-paper bundle?

**Still a bundle.** The evidence is organized as the four old papers in one file:

1. data/integration (`sections/3_results.tex:4-24`, `sections/3_results.tex:255-260`);
2. calibration/transfer (`sections/3_results.tex:26-114`);
3. in-sample event reconstruction (`sections/3_results.tex:116-165`);
4. estate risk/five-year/feasibility (`sections/3_results.tex:167-213`) plus the Dogrib one-fire check (`sections/3_results.tex:215-253`).

The title promises "integration and negative calibration, transfer, and event diagnostics" — three diagnostics — but the body has eight result subsections. The introduction asks four questions (`sections/1_introduction.tex:32-40`) that map one-to-one onto the old four papers. The abstract is a roughly 380-word list of every result (`sections/0_abstract.tex:3-33`) with more than 15 numbers; the reader cannot tell which result is the contribution. The results are a sequence of unrelated tables with no cross-cutting analysis. The discussion subsections mirror the four old papers (`sections/4_discussion.tex:4-55`). The conclusion restates four sets of caveats (`sections/5_conclusion.tex:4-24`).

### 2.1 Leftover seams

- `sections/1_introduction.tex:78-85` ("Relation to prior work") and `sections/4_discussion.tex:4-10` ("What is new, and what is not") are nearly verbatim duplicates.
- `sections/1_introduction.tex:87-90`: "Reporting those distinctions is more useful than presenting four overlapping papers with the same evidence." This is meta-commentary about the retired portfolio, not science. Remove it.
- `sections/4_discussion.tex:19-22`: "The paper is deliberately narrower than the four-draft portfolio it replaces." Same problem. A journal reader was never part of the portfolio.
- `sections/0_abstract.tex:31`: "negative calibration, transfer, event, and **optimization** diagnostics." There is no optimization result. This is a four-paper leftover.
- `figures/fig1-workflow.png`: the box reads "Optimization harvest schedule." This directly contradicts `sections/2_methods.tex:170-174` and `sections/3_results.tex:212-213`.
- `figures/fig4-transfer.png`: the title reads "Held-out transfer on t13-t23"; the bars include "Hierarchical ridge" and "In-sample (upper bound)." The text says the regional map is not a held-out method (`sections/2_methods.tex:123-124`), calls the model "Ridge" (Table 3, `sections/3_results.tex:88`), and calls the in-sample row "not a transfer method" (`sections/3_results.tex:74-76`).
- `figures/fig6-external.png`: the title reads "Dogrib external growth benchmark." The text says "not a TSA24 benchmark" (`sections/3_results.tex:225-226`), and the program's own writing rule says "No 'benchmark' for Dogrib" (`planning/manuscript-plan.md:58`).
- `sections/2_methods.tex:61`: "ten validation fires." The section is titled "In-sample event reconstruction," and the rest of the paper says the events are not independent validation. The word "validation" survives here and in the table label `tab:event-validation`.
- No `\ref{fig:...}` appears in any section file. All six figures are uncited. The manuscript's own review checklist says "Check that every figure and table is referenced in the text" (`review/README.md:10`).

### 2.2 The actual contribution, and whether it is enough

The only candidate for a single contribution is the negative transfer result: a six-parameter per-tile reduced-form suppression/escape model fitted to fire-size distributions does not transfer to validation tiles using potential-growth/weather covariates, and even an oracle historical analogue is worse than the in-sample fit. That is a legitimate negative result, but the experiment is underpowered (12 training tiles, six parameters, seven predictors, 11 validation tiles) and confounded (2023-only weather, seven-day potential fires, arbitrary score weights, one deterministic draw per tile). The second candidate is the open-source integration, but the paper does not describe the software architecture or API in enough detail for a software paper, does not compare it with FSim, BurnP3+, Cell2Fire, or any other open implementation, and the archive is private.

The event reconstruction is a supporting in-sample diagnostic, not an independent test. The feasibility search is a null computational demonstration, not an optimization result. The Dogrib check is a one-fire case study, not a benchmark. The paper cannot be both a software paper and a negative calibration paper without a synthesis; currently it is neither. For EMS, the software contribution would need a public archive, a clear API/architecture description, and a reuse demonstration. For GMD, the model description would need equations, parameter values, a numerical scheme, and an evaluation against observations. Neither requirement is met.

## 3. Claim/evidence audit

Severity key: **Fatal** = the paper cannot be published as written; the claim must be removed or the evidence produced. **Major** = a referee will require substantial revision. **Minor** = copyedit or presentation.

| # | Claim and location | Check against the archive | Severity |
| --- | --- | --- | --- |
| 1 | "Open, auditable integration" — title (`main.tex:44`), abstract (`sections/0_abstract.tex:4`), keyword `reproducibility` (`main.tex:55`) | WS4 is public, but the reproducibility archive and manuscript repo are private (`sections/6_data-availability.tex:10-17`, `README.md:108-110`; `gh repo view` confirms `fresh_ws4_fire_regime_repro` and `fresh_ws4_fire_regime_manuscript` are private). The archive is partial, the documented pipeline does not rerun the reported tables, and there is no DOI. "Auditable" is false for an external reader. | **Fatal as written**; fix with a public DOI archive and a clean-host run, or retitle. |
| 2 | "23-tile in-sample fit matched the median (23.8 vs 23.0), 17% low on the maximum" — `sections/0_abstract.tex:11-13`, Table 2 `sections/3_results.tex:33-54` | The historical row (432 / 23.0 / 490.2 / 1,918.9 / 26.2% / 10.0% / 7.9% / 3.0% / 25,114.8) matches `raw/history/*.json` exactly. The simulated row (23.8 / 361.5 / 1,100.9 / 23.6% / 8.3% / 5.5% / 1.8% / 20,770.4) matches `notes/reports/p164-8-region-calibration.md`, not a result JSON. `make calibrate` writes `region-calibration-refit.json` with 12 tiles, not 23. The 23-tile map is the frozen `region-calibration.json`. | **Major** (traceability and reproducibility). |
| 3 | "The regional objective was a weighted distance over the 10th, 25th, 50th, 75th, 90th, and 95th percentiles plus the over-500, over-1,000, and over-5,000 fractions" — `sections/2_methods.tex:113-115` | `scripts/calibrate_regions.py:41-48` uses median, p90, p95, and maximum; it does not use p10, p25, p75, or p50 separately. The manuscript describes a different objective than the archived code. | **Fatal to the methods as written**; fix the text or the code and re-run. |
| 4 | "1,000 pre-registered candidates per tile" — `sections/2_methods.tex:111-112` | Only the global 1,500-candidate P164.8 protocol is pre-registered (`notes/design/ws4-regime-calibration-protocol.md`, committed 2026-11-21). The regional model is post hoc; the protocol does not specify per-tile fitting, a regional objective, or "1,000 candidates per tile." The report says "pre-registered-bounded" (bounds, not model). | **Major** (overstated pre-registration). |
| 5 | "A pre-registered global suppression calibration failed both its training and validation gates" — `sections/0_abstract.tex:10-11`, `sections/3_results.tex:28-30` | `results/p164-8-calibration.json` confirms training `maximum: false`, `over_5000: false`; validation `p90: false`, `maximum: false`. But the paper never reports the full gate table: training max 6,059 ha vs ≥10,000, over-5,000 0.56% vs 1–4%; validation p90 793.3 vs 350–700, max 9,474 vs ≥10,000. The negative result is under-reported. | **Major.** |
| 6 | "Training-only transfer: in-sample 1.50, global 4.80, analogue 6.12, ridge 6.54" — `sections/0_abstract.tex:14-16`, Table 3 `sections/3_results.tex:71-91` | Values match the old `results/transfer-validation.json` and `results/hierarchical-validation-simcv.json`. The current `make transfer` output (`results/transfer-validation-refit.json`) is 1.065 / 5.257 / 5.459 / 5.541; `make hierarchical` (`results/hierarchical-validation-refit.json`) gives 7.356 at lambda 3.0. The paper's numbers are not the current archive. | **Fatal to reproducibility**; all headline numbers must be regenerated. |
| 7 | "The ridge selected lambda 100 by training-only simulation score, at the grid boundary. Its held-out score was 6.540" — `sections/3_results.tex:104-106` | Matches `results/hierarchical-validation-simcv.json` (lambda 100, 6.540). The current `hierarchical-validation-refit.json` selects lambda 3.0 and scores 7.356; lambda 3.0 is interior. The boundary selection is a red flag for the old run and is not true of the current run. | **Major.** |
| 8 | "Global-minus-analogue -1.322 (95% interval -2.739 to +0.145)" — `sections/3_results.tex:96-98` | I recomputed a percentile bootstrap over the 11 tiles: -1.322, interval about [-2.726, +0.163]. The point estimate reproduces, but the archive contains no bootstrap script, no seed, and no resample count. The interval is not reproducible as packaged. | **Major.** |
| 9 | "Ridge-minus-pooling difference of -1.358 (95% interval -2.972 to +0.247)" — `sections/3_results.tex:97-98` | Sign is reversed. Ridge 6.540 is worse than pooling 5.182, so ridge-minus-pooling is +1.358; the paper's interval [-2.972, +0.247] is pooling-minus-ridge. My recomputation: ridge-minus-pooling +1.358 [-0.257, +2.972]; pooling-minus-ridge -1.358 [-2.979, +0.232]. | **Major** (factual sign error). |
| 10 | "The in-sample-minus-global gap is -3.792 (95% interval -5.737 to -1.963)" — `sections/3_results.tex:99-100` | -3.792 uses the global score 5.287 from the separate hierarchical run, not the Table 3 global score 4.799. The table-consistent gap is 1.495 - 4.799 = -3.304, with a bootstrap interval about [-5.153, -1.700]. The paper mixes two global fits without saying so. | **Major.** |
| 11 | "Point-ignition reconstruction of ten historical fires ... 58.6%, range -67.4% to +3163.0%; in-sample; at least eight event areas in calibration histories; one in a training tile" — `sections/0_abstract.tex:16-18`, Table 4 `sections/3_results.tex:123-151` | The per-event table matches `results/event-simulations-validation-90d.json`. I confirmed 8/10 exact area matches in `raw/history/*.json`; G12186 is in training tile t03. G13085's area also matches training tile t04, so "one event in a training tile" understates the overlap. | **Major.** |
| 12 | "Median absolute area bias 58.6%" — `sections/0_abstract.tex:17`, `sections/3_results.tex:118-120` | No confidence interval for the headline. A percentile bootstrap over the ten biases gives [43.3%, 358.6%]. The 30-day result in `results/event-simulations-validation.json` is 73.5% median absolute bias; the paper does not report it. The 90-day file is a concatenation of two checkpoints: the first six events lack `year`, `split`, `fwi`, `bui`, `wind_kmh`, and `fragments`; the last four have them. The paper does not disclose the concatenation. | **Major.** |
| 13 | "Those caps affect the largest-event comparison, but not the small-event overpredictions" — `sections/3_results.tex:156-157` | False for G51212: a 151.7 ha fire capped from roughly 145 days to 90 days and overpredicted by +633.4%. The cap limits the simulated area of a small event; it does affect a small-event overprediction. | **Major** (false statement). |
| 14 | "Five-seed risk ensemble: median 7,889.6 ha, CVaR95 1.04 million m3, no-fire baseline 822.55 million m3" — `sections/0_abstract.tex:20-22`, Table 5 `sections/3_results.tex:173-191` | The JSON matches: median 7,889.6, p90/max 8,600.8, baseline 822,552,619, CVaR 1,036,486, `tail_count: 1`. The CVaR is the maximum of five seeds, not a tail estimate. 1.04/822.55 = 0.126% of the baseline. The abstract does not say "worst of five" and does not give the percentage. | **Major** (abstract omission). |
| 15 | "A five-year fixed-schedule evaluation burned 8,374.1 ha and harvested 156,358.8 ha" — `sections/0_abstract.tex:22-23`, `sections/3_results.tex:200-204` | The estate JSON matches, but it is exactly risk seed `20261122`, run 1 of the five-seed ensemble: same burned area, volume, harvest, and biomass. It is not an independent case. `dropped_schedule_blocks: 1` is not reported. The paper presents the same run as two cases. | **Major** (pseudo-replication). |
| 16 | "112-tile feasibility search, 179 harvest entries, 727.1 s on 36 workers; objective harvest area; three fixed two-day ignitions; fire-blind repeat identical; 2,240/458,708 blocks" — `sections/0_abstract.tex:23-26`, `sections/3_results.tex:206-213` | The optimizer JSON matches: 112 tiles, 179 entries, 727.1 s, 20,775.6 ha, 859.98 million m3, 74.25 ha, 16 events. The fire-blind CSV has the same SHA-256 schedule hash. But the abstract's final sentence calls this "optimization diagnostics" (`sections/0_abstract.tex:31`), and Fig. 1 says "Optimization harvest schedule." | **Major** (scope/terminology). |
| 17 | "Dogrib: FireSTARR +36%, WS4 +191%, WS4 higher overlap" — `sections/0_abstract.tex:26-28`, Table 6 `sections/3_results.tex:222-237` | The values match `notes/reports/p157-firestarr-comparison.md`: observed 10,132 ha, WS4 29,480 ha (+191.0%, IoU 0.252), FireSTARR 13,808 ha (+36.3%, IoU 0.140). The abstract omits "WS4 raw wind"; the documented WS4 Scenario 2b run was +58.9% area and IoU 0.385, a materially different result that is not reported. The Dogrib artifacts are not in the reproducibility archive. | **Major.** |
| 18 | "A TSA24 FireSTARR run failed with SIGFPE" — `sections/0_abstract.tex:28`, `sections/2_methods.tex:55-56`, `sections/3_results.tex:241-243` | `protocol/event-validation.md:120-121` records the failure. Commit `7a85804` removed the failed FireSTARR harness from the archive manifest; no failed-run log or result is archived. The claim is supported by prose, not an artifact. | **Minor/Major.** |
| 19 | "198,564 of 458,708 blocks have no cell centre ... assigned to a representative cell; 1,310,129 fragment memberships; 180,074 multi-fragment cells" — `sections/2_methods.tex:10-13` | I verified the support NPZ: 458,708 unique fragments, 1,111,565 unique cells, 1,310,129 memberships, 180,074 multi-fragment cells, maximum 7 fragments per cell. The counts are correct. The assignment rule, the displacement distribution, and the effect on the fire results are not disclosed. `notes/reports/tsa24-full-support-map.md:7-9` reports median 1.6 km, p90 4.0 km, max 13.3 km for the rejected nearest-empty fallback; the paper gives no equivalent for the accepted representative-cell assignment. | **Major.** |
| 20 | "Potential fires capped at seven active days; one 2023 weather season for every tile; historical perimeters 1950–2024" — `sections/2_methods.tex:99-104` | `scripts/build_potential.py:27,30-31,289` confirms `ACTIVE_DAYS_MAX = 7`, `WEATHER_START = 2023-02-01`, `WEATHER_END = 2023-09-30`. The paper discloses the facts but not the consequence: the event reconstruction applies the suppression hazard over 34–90 days, far outside the 0.5–7 day range used to fit it. The 2023-only weather is a weather-year fit to a 1950–2024 distribution, not a multi-year regime. | **Major.** |
| 21 | "The archive contains compact results, the potential sample, calibration and transfer outputs, the event reconstruction, a source catalogue, stage scripts, and a 58-file SHA-256 manifest" — `sections/6_data-availability.tex:10-17` | The manifest has 58 files. The 24 named calibration tiles are tracked in `layers/` but are not in `MANIFEST.json` and are not hashed. `make calibrate` gives 12 tiles; `make transfer` and `make hierarchical` give different scores; `make event-sim` gives the 30-day result; `results/reproducibility-manifest.json` hashes for `optimizer-full-estate.json` and `risk-ensemble-5seed.json` do not match the current `MANIFEST.json`; there is no bootstrap script; there is no clean-host run; `requirements.txt` is unpinned. | **Fatal to the "auditable" claim.** |
| 21a | Stale 655.5 s optimizer runtime | The manuscript is clean: it uses 727.1 s throughout (`sections/0_abstract.tex:24`, `sections/3_results.tex:208`, `sections/5_conclusion.tex:8`). The companion report still says "Full-estate optimizer ... 655.5 s" (`notes/reports/p164-8-benchmark-reproducibility.md:74`), and `README.md:85` lists that report as companion evidence. Update or remove the report before submission. | **Minor/Major** (companion evidence). |
| 22 | "No TSA24 external benchmark" — scope table `sections/1_introduction.tex:72` | The prose is correct. `figures/fig6-external.png` is titled "Dogrib external growth benchmark," and `README.md:90` calls it a "Dogrib external benchmark." Contradiction. | **Major.** |
| 23 | "The regional map is fitted on all 23 tile histories and is not a held-out method" — `sections/2_methods.tex:123-124` | The prose is correct. Fig. 4 is titled "Held-out transfer on t13-t23"; the intro question says "held-out tiles" (`sections/1_introduction.tex:36`). The figure and question undercut the correction. | **Major.** |
| 24 | "Not a fire-aware optimization or a global optimum" — scope table `sections/1_introduction.tex:70-71`, `sections/3_results.tex:212-213` | The prose is correct. Fig. 1 says "Optimization harvest schedule"; the abstract says "optimization diagnostics"; `README.md:37` says "optimization failures." The paper still leaks the old optimization claim through its artifacts. | **Major.** |
| 25 | "Four overlapping papers" — `sections/1_introduction.tex:90`; "four-draft portfolio" — `sections/4_discussion.tex:19-22` | Meta-commentary about the publication process. A journal paper should not mention the retired drafts. | **Minor/Major presentation.** |
| 26 | Figure citations | Zero `\ref{fig:...}` in `sections/*.tex`. All six figures are orphaned. | **Major presentation.** |
| 27 | Study area | The paper never states the TSA24 area, location, or a location map. `notes/reports/tsa24-compiled-block-subset.md:8` gives 5,899,679.6 ha. The reader cannot judge whether 7,889.6 ha burned is large or small. | **Major presentation.** |
| 28 | Duplicated introduction/discussion | `sections/1_introduction.tex:78-85` and `sections/4_discussion.tex:4-10` are nearly verbatim. | **Major presentation.** |

### 3.1 Numbers that do match the archive

To be fair, the following headline numbers check out:

- 458,708 blocks; 1,111,565 support cells; 1,012,231 forest support cells; 133 layer tiles; 90,375,672 bytes of layer data; 34 DEM tiles and 881,769,668 bytes.
- Historical fire-size row: 432 perimeters, median 23.0 ha, p90 490.2 ha, p95 1,918.9 ha, over-100 26.2%, over-500 10.0%, over-1,000 7.9%, over-5,000 3.0%, maximum 25,114.8 ha.
- P164.8 gate outcomes: training maximum and over-5,000 fail; validation p90 and maximum fail.
- Risk: median 7,889.6 ha, p90/max 8,600.8 ha, baseline 822.55 million m3, CVaR 1.04 million m3.
- Estate: 885 events, 8,374.1 ha burned, 156,358.8 ha harvested, 821.6 million m3, 463.8 million t, 139.0 s load, 42.2 s evaluation.
- Optimizer: 112 tiles, 179 entries, 20,775.6 ha, 859.98 million m3, 74.25 ha in 16 events, 727.1 s; fire-blind schedule hash identical.
- Event per-event table; Dogrib table.

The problem is not that every number is wrong. The problem is that the paper's central calibration/transfer table is assembled from frozen artifacts that the documented pipeline no longer produces, and the figures/abstract still carry the old four-paper claims.

## 4. Statistical adequacy

### 4.1 What the paper now does

The paper is more honest than the old drafts. It states that 3,450 realizations are five draws from 690 potential fires (`sections/3_results.tex:57-58`), that the transfer ranking is not resolved by 11 tiles (`sections/3_results.tex:96-103`), that the event n=10 is imprecise with a bootstrap interval and a sign test (`sections/3_results.tex:162-165`), that the CVaR is the worst of five seeds (`sections/3_results.tex:169-171`), and that the support map assigns 198,564 blocks (`sections/2_methods.tex:10-13`). Those are real improvements.

### 4.2 What is still missing

- **No confidence interval for the headline event number.** The abstract reports 58.6% median absolute bias; the paper never gives its interval. My recomputation gives [43.3%, 358.6%]. A negative-result paper's central number needs an interval.
- **No seed ensemble for the event reconstruction.** The event table is one deterministic survival draw (`sections/2_methods.tex:67-68`). The paper reports no seed-to-seed variation. With n=10 and errors up to +3163%, a single draw is not a stable estimate.
- **No seed ensemble for the transfer scores.** The two global scores, 4.799 (`transfer-validation.json`) and 5.287 (`hierarchical-validation-simcv.json`), differ only because the scripts use different tile seed indices. That 0.49 difference is a seed artifact, and the paper does not report or explain it. The "in-sample-minus-global" gap uses the 5.287 score, not the Table 3 4.799 score.
- **No power analysis.** The paper says 11 tiles do not resolve the ranking, but it does not say what difference 11 tiles could detect. A negative-result paper should report the minimum detectable effect or a simulation-based power curve.
- **No multiple-comparison treatment.** Seven methods × seven metrics, with three selected pairwise intervals. The paper does not claim a ranking, which mitigates this, but the selected comparisons should be justified.
- **No sensitivity to the score weights.** The transfer score weights (3, 3, 2, 0.5) are arbitrary (`scripts/validate_transfer.py:78-87`). The paper does not show whether the ranking changes under other weights, although the ranking is already unresolved.
- **No sensitivity to the 30-day vs 90-day event cap.** The archive contains the 30-day result (73.5% median absolute bias, `results/event-simulations-validation.json`) and the 90-day result (58.6%). The paper uses only the 90-day result. The program plan explicitly requires "sensitivity to ... 30-day versus 90-day caps" (`notes/design/ws4-fire-research-program.md:62-63`); the paper does not do it.
- **No sensitivity to the 7-day potential-fire cap or the 2023 weather year.** These are not just limitations; they are alternative explanations for the negative transfer. The paper's causal claim "Potential growth and weather alone do not identify a suppression regime" (`sections/4_discussion.tex:34-37`) cannot be separated from "the calibration design is wrong" without these tests.
- **No formal calibration test.** Table 2 compares a simulated distribution to a historical distribution with no KS/AD test, no bootstrap over potential fires, and no observation-error model. The table gives one decimal place for a 3,450-realization sample that is five correlated draws from 690 fires.
- **No per-tile sample sizes.** The regional fit uses every tile with at least five historical fires (`sections/2_methods.tex:116-117`). Some tiles have 6, 7, or 8 fires for six parameters (`results/region-calibration.json` per-tile `historical.n`). That saturation should be reported; it is a plausible cause of the noisy per-tile parameters and the transfer failure.
- **The "overfitting diagnosis" is close to tautological.** The in-sample row is each tile's own fitted parameters; the transfer methods use training-only parameters. Of course the in-sample score is lower. The paper presents the gap as a scientific result ("the overfitting diagnosis itself is robust," `sections/3_results.tex:100`), but it is a definition unless compared with a proper cross-validation or a synthetic experiment where the true regime is known.
- **The comparator selection is tendentious.** The abstract and discussion compare the in-sample fit to the potential/weather analogue (6.12), the worst deployable method, rather than the training median (4.68), the best deployable method. The paper's own report says "the simple pool mean was the most robust transfer estimator" (`notes/reports/p164-8-hierarchical-validation.md`). The abstract should report the best deployable baseline, not the worst.
- **The ridge lambda is at the grid boundary in the old artifact.** The paper reports lambda 100 at the boundary (`sections/3_results.tex:104`), which means the true optimum may lie outside the grid. The current refit selects lambda 3.0, but the paper does not report the CV curve or widen the grid.
- **The CVaR is the maximum of five seeds.** The paper says so in the results but not in the abstract. 1.04 million m3 is 0.126% of the 822.55 million m3 baseline; the abstract should give the percentage or say the loss is negligible relative to the baseline.
- **The event reconstruction's suppression hazard is extrapolated.** The potential fires are capped at seven active days (`scripts/build_potential.py:27,289`); the event simulations run 34–90 days (`results/event-simulations-validation-90d.json`). The escape hazard is a logistic function of active duration (`sections/2_methods.tex:82-84`); applying it 5–13× beyond the fitted range is a model-misspecification risk that the paper does not discuss.

### 4.3 Assessment

The negative direction of the transfer result is robust: the in-sample fit is far better than every transfer method, and the current refit preserves that. The magnitude and ranking are not robust: the exact scores change between the old and refit artifacts, the ridge lambda changes from 100 to 3, and the global score changes with the seed index. The paper sometimes says this, but the abstract still presents the point estimates as the result. For a negative-result paper in EMS/GMD, that is not enough. The paper needs a proper uncertainty budget, a power analysis, and a sensitivity analysis that rules out the obvious confounds (weather year, duration cap, score weights, potential sample size). It does not have them.

## 5. Reproducibility and archive audit

### 5.1 What the archive contains

- `MANIFEST.json`: 58 files, Python 3.12.3, NumPy 2.5.4, pandas 3.0.6, generated 2026-11-23T06:51Z.
- 133 full-estate layer tiles, hashed in `manifests/full-layer-manifest.json` and `results/reproducibility-manifest.json`; 90,375,672 bytes.
- Support map `manifests/tsa24-full-250m-support.npz`, 5,155,745 bytes, hashed.
- 34 SRTM tiles, 881,769,668 bytes, recorded in `results/reproducibility-manifest.json`.
- Compact results, potential sample, transfer/calibration JSONs, event inventory/selection/weather, risk/estate/optimizer JSONs, and staged scripts.
- 24 calibration tiles in `layers/` (18 `tNN.npz` plus 6 named tiles: `central-west.npz`, `south-east.npz`, `far-east.npz`, `north-west.npz`, `far-north.npz`, `central-east.npz`).

### 5.2 What does not reproduce

- **`make calibrate` produces 12 tiles, not 23.** `Makefile:39-44` passes `results/potential/train.json` and writes `results/region-calibration-refit.json`; that file has keys `t01`–`t12`. The 23-tile `region-calibration-refit-all.json` was produced by a manual run (`logs/calibrate-all.log`) and is not a Makefile target. The archive README says "Fit regional map `make calibrate` **verified**: 23 tiles" (`README.md:44`); that is false.
- **`make transfer` produces different numbers.** `Makefile:46-53` writes `results/transfer-validation-refit.json`: in-sample 1.065, global 5.257, training median 5.459, potential analogue 5.541, historical analogue 2.888. The paper's Table 3 uses the old `transfer-validation.json`: 1.495 / 4.799 / 4.680 / 6.121 / 3.426. The qualitative "negative" result survives, but the paper's numbers do not.
- **`make hierarchical` produces different numbers.** `Makefile:55-61` writes `results/hierarchical-validation-refit.json`: lambda 3.0, ridge 7.356, in-sample 1.065. The paper uses `hierarchical-validation-simcv.json`: lambda 100, ridge 6.540, complete pooling 5.182, global 5.287. The current script also does not produce the complete-pooling or global baselines; those rows exist only in the old artifact.
- **`make event-sim` produces the 30-day result.** `Makefile:68-73` writes `results/event-simulations-validation.json`, which is the 30-day run with median absolute bias 73.5%. The paper's 90-day Table 4 is `results/event-simulations-validation-90d.json`, which is not a Makefile target and is a concatenation of two checkpoints (`event-simulations-validation-90d.log` for the first six; `...-remaining.log` for the last four). The first six events lack `year`, `split`, `fwi`, `bui`, `wind_kmh`, and `fragments`.
- **The reproducibility manifest is stale.** `results/reproducibility-manifest.json` records `optimizer-full-estate.json` SHA-256 `b368f9e1...` (81,431 bytes) and `risk-ensemble-5seed.json` SHA-256 `1f979bda...`; the current `MANIFEST.json` records `00671444...` (81,429 bytes) and `df2e7179...`. The code commit in the reproducibility manifest is `4e63ac46`; the archive HEAD is `676ba6e`. The paper never states which commit produced the results.
- **The 24 calibration tiles are not hashed.** `MANIFEST.json` has 58 files and does not include `layers/t*.npz` or the six named calibration tiles. They are tracked in git, so the git object hash is a de facto check, but the paper's "58-file SHA-256 manifest" does not cover the frozen calibration inputs.
- **No bootstrap script or artifact.** The paper's transfer and event intervals have no script, seed, or resample count in the archive. They cannot be audited or rerun from the archive.
- **No clean-host run.** The archive README says the next required step is a full `make resolve` → `make verify` run on a clean host (`README.md:104-109`). It has not been done. `requirements.txt` is unpinned (`numpy>=1.26`, `pandas>=2.2`, etc.). There is no environment lock or container.
- **No DOI.** The archive is private (`gh repo view` confirms `isPrivate: true`). The manuscript repo is private. The data-availability section links to both private repositories (`sections/6_data-availability.tex:10-24`).
- **The Dogrib evidence is not archived.** `notes/reports/p157-firestarr-comparison.md` has the table, but the repro archive's `MANIFEST.json` has no p157 files. The paper's only external check cannot be reproduced from the archive.
- **The FireSTARR TSA24 failure is prose only.** `protocol/event-validation.md:120-121` records the SIGFPE; commit `7a85804` removed the failed harness from the archive manifest. There is no failed-run log or result in the manifest.

### 5.3 Contradictions inside the archive

- `README.md:90-91`: "`event-simulations-validation-90d.json`: ten independent point-ignition events." The same README says "the in-sample event reconstruction fails and is not independent" (`README.md:93-95`) and the paper says it is in-sample. The word "independent" is still in the archive.
- `README.md:39`: "**frozen**: 10 validation fires, 1 training fire." The paper calls them reconstruction fires, not validation fires.
- `README.md:44`: "`make calibrate` **verified**: 23 tiles." The target produces 12.
- `protocol/event-validation.md:1`: "TSA24 independent event-validation protocol." The post-review disclosure at lines 3 and 9-13 says it is in-sample. The title and body still say independent.
- `protocol/event-validation.md:29-53`: describes a temporal holdout (training through 2017, validation 2018+) and a spatial holdout (t01–t12 train, t13–t23 validation), and says events are selected "largest fires first, capped at 20 per split." The executed selection is 10 validation + 1 training fire; the regional map was fitted on all 23 tiles; G12186 is in a training tile. The protocol is not the protocol that was executed.
- `protocol/event-validation.md:118-119`: "Weather/start-perimeter assembly for selected events: not complete. Model simulations: not started." The paper reports completed simulations. The status section is stale.
- `protocol/event-validation.md:123-124`: "The next step is to assemble the event weather and start perimeters ... then run the model." The model has run. Stale.
- `sections/6_data-availability.tex:13-17`: "It does **not** yet contain a clean-host raw-to-result rerun, a derived support map script, the 24 named calibration-layer source derivations, or a DOI." This is honest, but it sits under a title that says "open, auditable" and a data-availability section that says the archive "contains ... calibration and transfer outputs." The outputs it contains are not the outputs the paper reports.

### 5.4 What must become public before submission

1. The reproducibility archive, with a DOI (Zenodo or institutional), a licence, and a clean-host `make resolve` → `make verify` run.
2. The manuscript source, or a supplement containing the LaTeX, figures, and bibliography.
3. The 24 calibration tiles and the support map, with SHA-256 hashes in `MANIFEST.json`.
4. The bootstrap/sensitivity scripts and their outputs, with seeds and resample counts.
5. The Dogrib derived metrics, the comparison script, and the FireSTARR TSA24 failure log (or a redacted log).
6. An environment lock or container, and the exact code commit for every result.
7. A corrected archive README and protocol: remove "independent," fix the 23-tile claim, update the current-status section, and state which `make` targets produce which paper tables.
8. A data-licence sign-off for VRI, BC Wildfire, SRTM, Open-Meteo, the Dogrib sample, and the compiled TSA24 artifact.

## 6. Writing/structure/figure/table audit

### 6.1 Structure

- The abstract is 382 words and carries more than 15 numbers. It is a four-paper abstract. Cut it to about 300 words around one question: does the reduced-form suppression layer transfer?
- The title says "integration and negative calibration, transfer, and event diagnostics," but the body also reports risk, estate, feasibility, and a Dogrib growth check. The title is narrower than the body; the abstract is broader than the title. Pick one scope.
- The introduction's four questions (`sections/1_introduction.tex:32-40`) are four paper questions. A one-contribution paper should ask one question and use the other results as supporting evidence or supplementary material.
- The "Relation to prior work" subsection is duplicated in the discussion. Delete one.
- The paper mentions the retired four-draft portfolio twice (`sections/1_introduction.tex:90`, `sections/4_discussion.tex:19-22`). Remove both. A journal reader does not need the publication history.
- The discussion's "Future work" section is a six-item plan (`sections/4_discussion.tex:78-93`) that reads like a grant proposal. Keep two or three items that follow directly from the negative result.

### 6.2 Figures

- **No figure is cited in the text.** Add `\ref{fig:...}` for every figure. The manuscript's own checklist requires it (`review/README.md:10`).
- **Fig. 1** says "Optimization harvest schedule." Change to "bounded harvest feasibility search" or remove the box. It contradicts the paper's central scope claim.
- **Fig. 2** has row/column axes, no scale bar, no north arrow, no legend for the orange tiles, and no location inset. It is a raster plot, not a study-area map. The paper has no study-area map and no total area. Add one.
- **Fig. 3** is fine, but the text does not cite it.
- **Fig. 4** says "Held-out transfer on t13-t23," "Hierarchical ridge," and "In-sample (upper bound)." All three are inconsistent with the text. Retitle to "Transfer to validation tiles t13-t23 (training-only methods; in-sample reference)," rename "Hierarchical ridge" to "Ridge," and label the in-sample bar "in-sample reference, not a transfer method."
- **Fig. 5** is fine, but the CVaR line is the maximum bar; the caption should say "CVaR95 = worst observed seed (n=5)."
- **Fig. 6** says "Dogrib external growth benchmark." The text says "not a TSA24 benchmark." Retitle to "Dogrib one-fire growth check (not a benchmark)."

### 6.3 Tables

- **Table 1** (scope) is a compliance table, not a contribution. It is useful, but it should be in the discussion or supplement, not the introduction. Its "Supported" column includes negative claims; the definition "Supported means the paper contains a reproducible artifact" is not true for the private archive. The "TSA24 data assembly" row omits the frozen 24 calibration tiles and support map. The "Estate-scale risk and fixed-schedule cases" row presents two cases that are the same run.
- **Table 2** (calibration) is not traceable to a result JSON. The simulated row comes from a prose report. The table omits the mean (512.9 vs 306.2 ha, a 40% shortfall) and gives p90/p95 shortfalls (26%/43%) without stating them in the text. The table's "Sample size 3,450 realizations" invites the reader to treat correlated draws as independent, even though the caption says they are five draws from 690 fires.
- **Table 3** (transfer) mixes two runs. The in-sample/global/training-median/analogue rows are from `transfer-validation.json`; the complete-pooling/ridge rows are from `hierarchical-validation-simcv.json`. The caption says "The ridge and complete-pooling rows come from the separate run," but the table still ranks them together, and the text then uses the separate run's global score (5.287) for the in-sample gap. Split the table or re-run everything on one sample.
- **Table 4** (event) is traceable to the 90-day JSON, but the caption does not disclose that the 90-day file is two concatenated checkpoints, that one draw per event was used, or that two ignitions were snapped to burnable cells. The text's "caps affect the largest-event comparison, but not the small-event overpredictions" is false for G51212.
- **Table 5** (risk) does not say "CVaR95 = worst of five seeds" in the caption. The text says it, but the table travels alone.
- **Table 6** (Dogrib) is fine as a one-fire case study, but the surrounding figure calls it a benchmark.

### 6.4 Methods

- The suppression model is described qualitatively (`sections/2_methods.tex:78-95`): no equations for the contained/escaped distributions, the logistic escape hazard, or the escape cap. A reader cannot implement it from the paper.
- The growth engine is described in one paragraph (`sections/2_methods.tex:31-46`): no equations for the elliptical perimeter, arrival-time propagation, or slope/wind vector composition. The paper cites FBP and Rothermel, but the implementation is not described.
- The calibration objective is wrong relative to the code (row 3 above).
- The transfer score weights are stated but not justified; the potential/weather analogue is described with seven features (`sections/2_methods.tex:134-135`) but the code uses five (`scripts/validate_transfer.py:90-98`: log median, log p90, FWI, BUI, wind). The ridge uses seven (`scripts/hierarchical_validation.py:65-77`), so the methods sentence "The predictors were the same potential/weather features" (`sections/2_methods.tex:146`) is false for the analogue.
- The paper does not report per-tile historical sample sizes, the candidate bounds table, or the full gate table. Those are in the reports, not the paper.
- The paper says "Predictions were clipped to the pre-registered P164.8 bounds" (`sections/2_methods.tex:148`). The code clips to `ws4.fire.regime_calibration` bounds, which match the protocol, but the paper does not give the bounds. Minor.

### 6.5 Terminology

- "Validation fires" (`sections/2_methods.tex:61`) should be "reconstruction fires" or "in-sample events."
- "Hierarchical ridge" (Fig. 4) should be "ridge"; the paper no longer calls it hierarchical or empirical Bayes in the text, but the figure and the report do.
- "Partial-pooling covariates" (`sections/4_discussion.tex:29`) is inaccurate: the model is six independent ridge regressions with a shared lambda, not a partial-pooling/hierarchical model.
- "Complete pooling" is the mean of the training parameters; the "Training median" is a better complete-pooling baseline. Say which is which and why both are reported.
- "Upper bound" for the in-sample row is ambiguous: lower score is better, so it is a lower bound on the score / upper bound on skill. Use "best-case reference."
- "Optimization diagnostics" (abstract) and "optimization failures" (`README.md:37`) should be "feasibility diagnostics" or "null fire-effect diagnostics."
- "Benchmark" for Dogrib should be "one-fire growth check."
- "Held-out" for the transfer figure should be "validation-tile transfer."

### 6.6 Event consistency: fixed in the text, not in the package

The main text is internally consistent: `sections/2_methods.tex:65-67` says the reconstruction is not independent; the table caption says "not independent validation" (`sections/3_results.tex:129-130`); the discussion says the events, map, and calibration histories overlap (`sections/4_discussion.tex:42-43`); the scope table says "not independent of calibration" (`sections/1_introduction.tex:68`). The remaining "independent" claims are outside the manuscript, in the package the data-availability section points to:

- `fresh_ws4_fire_regime_repro/README.md:90-91`: "ten independent point-ignition events."
- `fresh_ws4_fire_regime_repro/protocol/event-validation.md:1`: "TSA24 independent event-validation protocol," with a post-review disclosure at lines 3 and 9-13.
- `notes/reports/tsa24-event-validation.md:58`: "The model fails independent event-level validation."
- `notes/reports/p164-8-transfer-validation.md:3`: "Status: independent transfer diagnostic."

The main text also still uses "ten validation fires" (`sections/2_methods.tex:61`) and the table label `tab:event-validation`. That is not an independent-validation claim, but it invites the reader to read the table as validation. Replace "validation fires" with "reconstruction fires" or "in-sample events." The archive README and protocol must be corrected before submission, because the data-availability section sends reviewers to them.

### 6.7 Feasibility versus optimization: prose fixed, artifacts not

The prose separation is correct. `sections/2_methods.tex:170-174` says the search is not a fire-aware optimization; `sections/3_results.tex:206-213` says it demonstrates a computational path and a null fire effect; the discussion says "feasibility demonstration" and "no fire-risk objective, no global coordination, and no quality bound" (`sections/4_discussion.tex:51-55`); the conclusion says "do not demonstrate a fire-aware optimization" (`sections/5_conclusion.tex:16-20`); the scope table says "Not supported" for fire-aware optimization and global optimum. No prose claim of process-coupled or fire-aware optimization remains.

The artifacts still imply it. The abstract's last sentence calls the result "optimization diagnostics" (`sections/0_abstract.tex:31`); Fig. 1 has a box labelled "Optimization harvest schedule"; `README.md:37` says the paper reports "optimization failures." Those three must be changed to "feasibility" or "harvest-only search" before the paper can be read as a negative-diagnostic paper rather than a failed optimization paper.

## 7. Remaining blockers to submission

1. **Public archive with DOI and clean-host run.** The title/abstract's "open, auditable" claim cannot stand with a private, partial archive. This is the single largest blocker.
2. **One canonical result set.** The paper currently mixes old and refit artifacts: 12 vs 23 calibration tiles, old vs refit transfer scores, lambda 100 vs 3, 30-day vs 90-day events, old vs new reproducibility-manifest hashes. Pick one code commit and one map, regenerate every table, and update the hashes.
3. **Correct methods description.** Fix the calibration objective, the analogue feature count, the ridge description, and the per-tile sample sizes. Add the equations for the suppression model and the growth engine, or cite a methods paper that contains them.
4. **Full global gate table.** The negative no-go is the paper's strongest claim; it needs the full training/validation table, not two validation numbers.
5. **Uncertainty and sensitivity.** Add the event median-absolute-bias CI, the event/transfer seed ensembles, the 30-vs-90-day sensitivity, the score-weight sensitivity, the lambda-grid sensitivity, the 7-day cap/weather-year discussion, and a power analysis. Fix the ridge sign and the global score in the in-sample gap.
6. **Support-map disclosure.** Give the assignment rule, the displacement distribution, and the effect on the fire results. The 198,564 count alone is not enough.
7. **Event-run disclosure.** State that the 90-day file is two concatenated checkpoints, that one draw per event was used, and that the suppression hazard is extrapolated 5–13× beyond its 7-day calibration range. Run a multi-draw event ensemble.
8. **Study-area map and total area.** The paper never says how large TSA24 is. Add a location map with the 24 tiles, the validation tiles, and the historical fires.
9. **Figure and table audit.** Cite every figure; fix the stale titles; split Table 3 or re-run it on one sample; add the caveats to Table 5; remove the "benchmark" label from Fig. 6.
10. **Scope reduction.** Cut the four-paper language and the duplicated intro/discussion. Decide whether this is a calibration/transfer paper or a software/integration paper. Do not try to be both.
11. **Author/funding/licence/competing interests.** The title page says the author list is provisional; funding is "to be confirmed"; the archive has no DOI or licence sign-off. These are standard submission blockers.
12. **Venue decision.** EMS and GMD need different papers. EMS needs a public software/archive and a reuse demonstration; GMD needs a full model description and an evaluation. The current manuscript fits neither.

## 8. Minimum revision list

If the author wants the smallest credible submission, do these in order:

1. **Narrow the paper to one question.** Use the negative transfer result as the contribution: "Can a six-parameter reduced-form suppression layer calibrated to fire-size distributions transfer across TSA24 tiles?" Move the event reconstruction, feasibility search, and Dogrib check to a short "additional diagnostics" section or a supplement. Delete the four-paper language and the duplicated intro/discussion.
2. **Freeze one code commit and one 23-tile map.** Fix `make calibrate` to produce 23 tiles from `results/potential/all.json`; regenerate the transfer, hierarchical, event, risk, and estate tables from that map; update every number and hash in the paper. If the old map is canonical, say so and archive it with a hash; do not mix old and refit rows.
3. **Fix the methods.** Replace `sections/2_methods.tex:113-115` with the code's actual objective (median, p90, p95, maximum; over-500/1,000/5,000 with weights 3, 3, 2), or change the code to the described p10/p25/p50/p75/p90/p95 objective and re-run. Fix the analogue feature list to five features and the ridge to seven. Add the suppression/growth equations or a methods citation.
4. **Report the full global gate table.** Training and validation, all metrics, gates, pass/fail, in one table. Label the regional fit post hoc.
5. **Add the statistical package.** A `scripts/bootstrap.py` and JSON with the event median-absolute-bias CI, the transfer paired intervals (method, seed, resamples), seed ensembles for event/transfer, 30-vs-90-day sensitivity, score-weight sensitivity, lambda-grid sensitivity, and the 7-day cap/weather-year discussion. Fix the ridge-minus-pooling sign and use the Table 3 global score consistently.
6. **Disclose the support map.** Add the assignment rule, the displacement distribution, and a sensitivity or a clear caveat. The 198,564/458,708 count is necessary but not sufficient.
7. **Disclose the event run.** State the two-checkpoint concatenation, the one-draw design, the snapping of two ignitions (with distances), and the 90-day extrapolation of the suppression hazard. Report the 30-day 73.5% result as sensitivity. Run a multi-draw event ensemble.
8. **Make the archive public and honest.** DOI, licence, clean-host run, environment lock, 24 calibration tiles hashed, Dogrib metrics and FireSTARR failure log archived, archive README/protocol corrected ("independent," 23 tiles, current status).
9. **Fix the figures and add a study-area map.** Cite every figure; retitle Fig. 1, Fig. 4, and Fig. 6; add a location map with total hectares and the tile/validation layout.
10. **Resolve the submission metadata.** Author list, affiliations, ORCIDs, CRediT, funding, competing interests, data-provider credit, target journal, and template. Add the archive DOI to the data-availability section.
11. **Choose the venue.** If the archive is public and the paper focuses on the software/API and the negative evaluation, EMS is plausible. If the paper focuses on the calibration/transfer experiment, IJWF or a methods journal is a better fit. GMD requires a fuller model description than this paper has.

## 9. Final recommendation

**Revise; do not submit.** The consolidation is a necessary first step, not a finished paper. It fixed the worst false claims in the prose but left the evidence package, the figures, and the companion reports inconsistent with the text. The paper is still a four-paper bundle, the headline calibration/transfer numbers are not reproducible from the current archive, and the negative result is statistically underpowered. The minimum revision list above is large but feasible; the archive and the 23-tile pipeline are the hard parts.

If the author will not make the archive public and regenerate the numbers from one canonical pipeline, the paper should be killed or converted into a technical report. The negative transfer result is worth publishing, but only with a proper statistical design and a public archive. The integration is worth describing, but only as a software paper with a clear API and a reproducibility test. The current manuscript is neither.
