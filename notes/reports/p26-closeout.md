# Phase close-out report: P26 Reproducibility and data quality

Phase: P26, Reproducibility and data quality
Parent issue: #219
Pull request: not opened yet
Evidence head: the commit that adds this report. Its CI run is posted on the pull request.
Date: 2026-10-24
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge the P26 pull request, and delete the branch `feature/p26-repro-quality`.
2. Close parent issue #219 with a closeout comment that cites the merge commit.
3. Launch P27, Goal normalization and priority tiers: add `normalization: auto` and priority tiers
   to targets, report normalized deviations, and keep the existing objective as the default.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Every run writes `run_manifest.json` with code, dataset, config, seeds, environment, and a reproduce command. | `write_reproducibility` writes the manifest from `Optimizer.run`; tests assert the required keys and the engine-level artefact. | Met |
| Every run writes `data_quality.json` and a summary block that names checks and unknowns. | `dataset_quality` reports metadata, table counts, target coverage, checks, and limitations; the summary carries a compact `data_quality` block. | Met |
| `scripts/compare_scenarios.py` compares labelled runs and writes JSON/Markdown/CSV. | `ws4.opt.scenarios` and the CLI read completed runs, write the three tables and reports, and build an optional Pareto front over named metrics. | Met |
| `python scripts/dashboard.py` is green. | Lint, format, types, tests, validator, docs, and docstrings pass at the evidence head. | Met |

## 2. Workflow compliance

- Parent issue before the branch: #219 was created before `feature/p26-repro-quality`.
- Branch from `main`: the worktree starts at `fc9b519`, the P23 head.
- P23 and P25 are complete; this phase did not modify their branches.
- Commit messages start with task IDs: `P26.1-P26.2`, `P26.3`, and the documentation commit.
- Roadmap and changelog in step: P26.1 to P26.3 are checked; the changelog records each.
- Child issues are closed with closeout evidence: #220, #221, and #222.
- Approval gates: the phase opened no pull request until this report; it did not merge, tag, release,
  or change a setting.

## 3. Gate evidence

| Gate | Result at the evidence head |
| --- | --- |
| lint | green |
| format | green |
| types | green |
| tests | green, coverage at or above 90% |
| validator | green |
| docs | green |
| docstrings | green |

## 4. Behaviour

- `run_manifest.json` records the ws4/package versions, Git revision and dirty flag when run from a
  checkout, the dataset reference and manifest/source hashes, the full configuration, one seed per
  start, the Python/package environment, and a principal-settings reproduce command.
- `data_quality.json` reports metadata supplied or missing, Parquet row counts, active target accounts
  checked against `accounts.parquet`, derived accounts separated, and explicit model limitations.
  Empty metadata is `unknown`, never `ok`.
- `scripts/compare_scenarios.py --run label=path ...` writes `scenarios.json`, `scenarios.md`,
  `scenario_runs.csv`, `scenario_targets.csv`, and `scenario_accounts.csv`. A missing report is
  unavailable; a missing metric keeps that run off the front.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Current GBR datasets report data-quality metadata as unknown. | The compiled `manifest.json` metadata block is empty; the source inventory/curve provenance lives in FEMIC run artefacts. | The report names this explicitly. Populating the manifest is a FEMIC/instance follow-up, not silently invented in ws4. |
| Scenario comparison compares artefacts, not new runs. | Running a scenario is the existing optimizer's job; duplicating it would make the comparison irreproducible. | The command names its run inputs and reports missing artefacts. |
| The reproduce command repeats principal settings only. | The full configuration contains every flag and is in the manifest. | The manifest states that the command is a starting point and the full configuration is authoritative. |

## 6. Next phase

Goal: make target weighting explicit and comparable across goals.

Tasks:

- P27.1 Add `normalization: auto` to targets and report normalized deviations.
- P27.2 Add priority tiers and a priority-aware penalty path.
- P27.3 Add a normalized-deviation block to the run report and a comparison column.

Recommended defaults:

- Keep the current weighted goal-programming objective as the default.
- Normalization is opt-in per targets file; a normalized run records its method.
- Priority tiers are advisory unless a target explicitly uses them.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
