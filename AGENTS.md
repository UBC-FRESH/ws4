# AGENTS.md

This file is the working contract for coding agents in WS4.

WS4 is a CLI-first, HPC-ready forest estate model that treats space as
first-class: fragments are the decision units, blocks aggregate them at runtime,
and adjacency, patch structure, and road access are enforced inside simulation
and optimization rather than allocated after the fact.

Keep this file short. Each rule below either checks itself or points to the page
that explains it. The workflow rules come from the UBC-FRESH dev workflow, which
this project follows. Project-specific rules go at the end, each with its reason.

## Session start

Read this file, then the code, tests, and docs that govern the change. The roadmap and
changelog are release context, not a prerequisite for every small fix.

## Working principles

- **Evidence over trust.** Cite command output, diffs, commit hashes, and URLs.
- **Ship the smallest useful change.** Do not turn one task into a phase tree.
- **No oracle, no capability.** A new agent-facing capability needs a validator that can fail.
- **Workflow as scaffold.** Default to one branch and one PR. Create an issue only for work
  spanning sessions or needing a decision.
- **Structured handoff.** The PR body, changed tests, and result artifact carry the state.
- **Preserve uncertainty.** Say what you did not verify, and why.
- **Sanitized output.** Keep private data, credentials, raw transcripts, third-party
  documentation, and personal paths out of tracked files.

## The green dashboard rule

`python scripts/dashboard.py` runs every quality gate: lint, format, strict types, tests with a coverage
gate, the workflow validator, and the docs build with warnings as errors.

- Every commit leaves the dashboard green.
- Any change from green is investigated and fixed immediately. There are no exceptions.
- A failure you did not cause is still yours to fix, or to report with evidence before you continue.
- Do not weaken a gate to make it pass. A gate changes only with a changelog entry that explains why.
- Record the dashboard result in the changelog entry for each task that you close.

## Typing and docstrings

- Every function, method, and test has complete type annotations. `mypy --strict` must pass.
- Every public function has a numpy-style docstring. Its parameters and return value match its annotations.
- Do not use `Any`, `# type: ignore`, or `cast` without a comment that says why. A suppression names its error code.

## Testing policy

- Every function you write or change gets unit tests in the same change set. Tests must be able to
  fail, and each one asserts a specific behavior.
- Keep the layers: unit tests for each function, contract tests for public interfaces, integration
  tests for the command-line tools, property tests for invariants, and the self-check.
- The coverage gate is 90 percent branch coverage. Aim near 100 percent, with tests that assert something.

## CI and merges

- Keep the PR gate fast: lint, format, strict types, and the tests affected by the change.
- The full suite runs once before merge when it fits the budget, and nightly otherwise.
- No pull request merges while required CI is red.
- Merge a green pull request when the maintainer says go. Internal changes do not need a phase
  close-out report.

## Planning workflow

- Default: one branch and one pull request. No parent/child issue tree.
- Use a phase only for multi-session evidence work or a public claim change.
- Update `ROADMAP.md` and `CHANGE_LOG.md` at release, or when a public claim changes. Do not edit them
  for routine internal changes.
- Write a report only when the result changes evidence or a public claim. Otherwise the PR body and
  the test/artifact output are enough.

## Approval gates

You may create and commit to a branch, push it, open and update a pull request, and run local checks.

Merge a green pull request after an explicit go. Do not require a close-out report for routine work.
You must still wait for explicit approval before you: create a tag or a release; change repository
visibility, settings, or branch protection; create an external account, repository, or server; touch
private data or credentials; or delete anything beyond the merged branch.

## GitHub hygiene

- Check existing issues and pull requests before opening a duplicate.
- Write long bodies and comments to files and post them with `--body-file`.
- Read back a comment or edit when the exact posted text matters. Do not post progress
  comments for routine work.

## Formatting

- Put section labels on their own lines, such as `Phase identifier: P0`.
- Use real task-list syntax, one item per line.
- Wrap branch names, paths, commands, and commit hashes in backticks.
- Start commit messages with the task ID, for example `P0.1 add the workflow contract`.

## Verification

Run the checks that govern the change: targeted tests plus `ruff` and `mypy`. Run the full
dashboard once before a merge when it fits the budget; otherwise let nightly CI run it.
Do not repeat the full suite three times in one workflow.

## Public safety

- No private data, credentials, raw transcripts, unpublished documents, or machine-specific paths in
  tracked files.
- Use placeholders, repository-relative paths, or environment variables in examples.
- Do not copy third-party documentation, schemas, or code into tracked files. Use them only to inform
  an original design, and cite concepts, never text.

## Project-specific rules

- **Check the cross-repository threads on a cadence.** The other agent works asynchronously in
  `UBC-FRESH/femic-tsa23-instance`, and GitHub is the shared channel. At session start, after each
  completed task, and before reporting a phase closed, read the new issues and comments in **both**
  `UBC-FRESH/ws4` and `UBC-FRESH/femic-tsa23-instance`, and reply in the thread rather than relying on
  the maintainer to relay. `gh issue view --comments` fails on these repositories (the Projects-classic
  deprecation breaks the GraphQL query); use
  `gh api 'repos/UBC-FRESH/ws4/issues/comments?sort=updated&direction=desc&per_page=20'` and the same
  for `femic-tsa23-instance`, plus `gh api 'repos/<owner>/<repo>/issues?state=all&sort=updated&direction=desc'`
  for newly opened ones. Reason: the maintainer should not have to prompt each check.

- **Spatial structure is part of the model, not a post-processing step.** Fragments, adjacency, and
  access constraints participate in simulation and optimization. Reason: the project exists to make
  spatial relationships first-class.
- **Fragments compile; blocks aggregate.** The compiled matrix is fragment-level. Blocks are a runtime
  view used for operability, reporting, and spatial metrics. Reason: this keeps the compilation unit
  small and lets one matrix serve many block layouts.
- **The compiled dataset is the contract.** Ingest produces a versioned, columnar dataset with a
  manifest. Simulator and optimizer read only that dataset. Reason: a single, inspectable boundary
  between ingestion and execution.
- **Reproducibility is a feature.** Every stochastic search records its seed; the simulator is
  deterministic given a schedule. Reason: results must be re-runnable and auditable.
- **Carbon is a sidecar, not a dataset column.** Read `docs/reference/carbon.rst` and
  `docs/howto/run-carbon.rst` before changing the package join, the SIT compiler, the libcbm
  driver, the HWP lifecycle, or carbon targets. The package and curve method are cross-repo
  contracts; GCBM is a bridge, not a parity target.
- **Do not copy third-party documentation or code.** Public method references such as a thesis or a
  public companion repository may be cited and linked, but the description stays in WS4's own words.
  Reason: provenance is auditable without importing someone else's text or implementation.
