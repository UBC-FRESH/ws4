# Phase close-out report: P4 Release and deploy

Phase: P4 Release and deploy
Parent issue: #36
Pull request: #43, `feature/p4-release` into `main`
Evidence head: `4516345`, the head that the gates and the CI runs below cover
Report commit: the commit that adds this report. Its CI run is posted on pull request #43.
Date: 2026-10-15
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge pull request #43, and delete the branch `feature/p4-release`.
2. P4.5 Tag and publish (on the merge commit): create and push the annotated tag `v0.1.0`, and create
   the GitHub release with the built artifacts.
3. P4.4 (finish) Publish the documentation site: confirm the `Docs` workflow builds and deploys from
   `main`, and verify the published site from a clean checkout.
4. P4.6 Verify the published release: install the published artifact into a fresh environment, run the
   acceptance checks, and confirm reproducibility.
5. Close parent issue #36 with a closeout comment that cites the merge commit and the tag, and set P4
   to `complete` in `ROADMAP.md`.
6. Launch P5 (Operate and maintain): create its branch, set the phase statuses, create its child
   issues as sub-issues, and start its first task.

Settings changes, each with its exact command. Each one runs only after its own approval.

```bash
# P4.5 — tag and publish (run on the merge commit of pull request #43)
git checkout main && git pull
git tag -a v0.1.0 -m "WS4 0.1.0"
git push origin v0.1.0
gh release create v0.1.0 \
  dist/ws4-0.1.0.tar.gz dist/ws4-0.1.0-py3-none-any.whl \
  --title "WS4 0.1.0" --notes-file RELEASE_NOTES.md

# P4.4 — publish the docs (Pages already enabled in P3; the Docs workflow deploys from main)
gh workflow run Docs --ref main
```

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Release version and metadata prepared (#37) | `pyproject.toml`, `ws4/__init__.py`, `CITATION.cff` at `0.1.0` (`a0628ec`) | met |
| Release notes and known-gaps list (#38) | `RELEASE_NOTES.md` (`b38243d`, refreshed at `e587fc2`, `635f259`, `4516345`) | met |
| The sdist and wheel build from a clean checkout; the wheel installs fresh and the CLI runs end to end (#39) | commit `e587fc2`; the PR #39 progress comment | met |
| The artifacts contain the package, not the tests or the notes (#39) | `MANIFEST.in`; wheel and sdist listings in the PR #39 comment | met |
| The subsystem docs pages exist (simulator, optimizer, spatial, roads) (#40) | `docs/reference/{simulator,optimizer,spatial,roads}.rst` (`b3f5bf1`, extended `1da81f8`, `635f259`) | met |
| The published docs site is reachable and matches the checkout (#40) | pending the phase merge | not met (post-merge) |
| `python scripts/dashboard.py` stays green | `OVERALL: GREEN` at `4516345` | met |
| The nine core reference variants and the full MKRF canonical model build exactly | `scripts/acceptance.py`; `notes/backlog.md` | met |
| The release is tagged and its artifacts published (#41) | pending approval | not met (approval required) |
| The published release is verified from a fresh install (#42) | pending publish | not met (post-publish) |

## 2. Workflow compliance

- Parent issue before the branch: parent #36 was created before the branch `feature/p4-release`.
- Branch from `main`: merge-base `83e2d60` (the Phase 3 squash merge).
- Commit messages that start with task IDs: 13 of 13 (`90dbeb9` P4 activation through `4516345`).
- Gates for each commit: section 3.
- Roadmap and changelog in step: `ROADMAP.md` (P4 task boxes, the performance-plan pointer) and
  `CHANGE_LOG.md` were updated in the same change sets as the work.
- Child issues closed with closeout evidence: none yet. #37 to #40 close with the phase, each with a
  closeout comment; #41 and #42 close after the tag and the post-publish verification.
- Approval gates: the branch, commits, pushes, issues, and the pull request are within the active
  phase. The tag, the release, and the docs publish are named above with their exact commands and wait
  for approval; nothing outside the phase was touched.

## 3. Gate evidence

| Commit | Gates | Result |
| --- | --- | --- |
| `90dbeb9` P4 activation through `4516345` plan (13 commits) | `python scripts/dashboard.py` | `OVERALL: GREEN` at each commit |
| `4516345` (evidence head) | `python scripts/dashboard.py` | `OVERALL: GREEN`; lint, format, strict types, 300 tests with the 90 percent coverage gate (94.28 percent), the workflow validator, and the docs build all pass |
| `4516345` (evidence head) | `scripts/acceptance.py` (builder), C5 end to end | nine core variants match; the MKRF canonical model matches; the C5 route and spatial accounts resolve |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 38773492760 | `4516345` | success | The pull request CI run (lint, format, types, tests, validator, docs). |
| 38685908031 (Docs, `main`) | — | success | The docs deploy from `main` succeeds after the P3 merge. |

CI runs on pull requests and `main` only, so the branch commits before the pull request have no CI
run. The CI run for the report commit is posted on pull request #43.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Maintainer-directed functional work landed in the release phase (the canonical MKRF builder, the C5 route model and patch accounts, core-area rules and edge contrast) | The release must be functionally complete, and the maintainer directed these fixes during the phase | Recorded in `CHANGE_LOG.md`; the dashboard stayed green; the acceptance comparisons pass |
| The MKRF canonical model was recorded as "blocked" in the release notes | It was blocked when the release notes were written, then reproduced during the phase | Refreshed `RELEASE_NOTES.md` and `notes/backlog.md` (`e587fc2`) |
| The optimizer objective is slow with routing, spatial metrics, and edge contrast | All of it runs inside the objective; the implementation is Python-first and from scratch | Accepted for this release ("functionally complete but slow"); the plan is `notes/design/ws4-performance.md`, deferred to after the release |
| P4.4 could not publish and verify the site before the merge | The `Docs` workflow deploys from `main` | Named as a post-merge step in the recommendation |

## 6. Next phase

Phase 5: Operate and maintain.

Goal: keep the project current — triage incoming ideas, review on a cadence, and close out cleanly.

Tasks (to create as child issues of the P5 parent):

- P5.1 Set a review cadence and record the first review.
- P5.2 Stand up issue triage: labels, templates, and a triage cadence.
- P5.3 Dependency and security maintenance: automated updates and a review cadence.
- P5.4 Keep the roadmap, backlog, and changelog in step on a cadence.
- P5.5 Define the release cadence and the patch policy.
- P5.6 Write the maintainer and handover guide.

Acceptance criteria:

- A review cadence exists and the first review is recorded.
- Dependency updates and triage have an automated, documented cadence.
- A maintainer and handover guide exists.

Recommended defaults, each with its reason:

- **Run the performance work as its own build phase (P6), after P5 starts.** Reason: it is a large,
  multi-work-package effort (`notes/design/ws4-performance.md`), not maintenance; it should not block
  the release or the operate phase.
- **Patch releases on a needs basis, tagged `vX.Y.Z`.** Reason: the release is functionally complete;
  the next changes are fixes and the deferred performance work.
- **Keep the release artifacts on the GitHub release (not PyPI) for now.** Reason: there is no external
  account approval for PyPI yet; it is a separate decision.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
