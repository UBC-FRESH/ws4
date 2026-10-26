# Phase close-out report: P55 Final 0.2.0 release candidate

Phase: P55, Final 0.2.0 release candidate
Parent issue: #388
Pull request: this release-candidate PR
Companion pull requests: P55.1 release notes were merged separately as #421
Date: 2026-10-26
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this pull request.
2. Close parent issue #388 with a closeout comment.
3. If release is approved, tag the squash-merge commit as `v0.2.0`, push the tag, and publish the
   GitHub release with artifacts rebuilt from the tag. This report does **not** create the tag.

Settings changes: none. This phase creates no tag, release, PyPI upload, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Notes include carbon, LiDAR, hydrology, disturbance, and route-event caching. | P55.1 merge #421; `RELEASE_NOTES.md`. | Met |
| The final head is verified with all declared extras installed. | `.[geo,opt,carbon,lidar]`; clean-checkout and dashboard green. | Met |
| Release metadata is consistent. | `0.2.0` in `pyproject.toml`, `ws4/__init__.py`, `CITATION.cff`; date `2026-10-26`. | Met |
| Artifacts build and install in isolation. | sdist/wheel build, `twine check`, wheel-with-extras and sdist installs. | Met |
| No tag is created without explicit approval. | No `v0.2.0` tag exists. | Met |

## 2. Workflow compliance

- Parent issue #388 and children #389–#391 existed before the branches.
- P55.1 landed separately as `feature/p55.1-release-notes`, PR #421.
- This branch is `feature/p55-final-rc`, based on `a7a9405`.
- Commit messages start with `P55`.

## 3. Final scope

The final head includes:

- P46 cached route-event ledger (8.25x warm speedup on c5; parity within `1.9e-8`).
- P52 LidarBC bundle consumption (7-polygon TFL 6 pilot; producer/FHOPS parity).
- P56 disturbance event reporting (`ws4 disturbance`; report-only).
- P57 FEMIC hydrology response-bundle screening (pinned bundles, reviewed crosswalk,
  receptor/watershed/return-period rows, optional `flood.*` accounts, refusal outside the
  envelope).
- P58 forest carbon accounting and carbon-aware planning (FEMIC package, libcbm,
  `ws4 carbon`, accounts, ledger, optimizer targets, TSA24/MKRF validation, GCBM reader).
- P42–P44 search/target/comparison surfaces, P47–P50 provenance and validation, and the GBR
  instance work already recorded in the 0.2.0 notes.

Environmental accounts (P54) remain open and are not included.

## 4. Verification

- Clean worktree from `a7a9405`; Python 3.12.3; fresh environment with
  `.[geo,opt,carbon,lidar]` plus dev requirements.
- Clean-checkout test: 1 passed.
- Dashboard: green — lint, format, types, tests (112.88 s), validator, docs (2.06 s), docstrings.
- The carbon extra exposed a mypy `import-untyped` failure in `tests/test_carbon_sit.py`.
  Added a `libcbm` mypy override and removed the narrow inline ignore; final mypy is clean.
- CI quality, dashboard, and pre-commit jobs now install `.[geo,opt,carbon,lidar]`, so the
  optional carbon/LiDAR tests run instead of being skipped. Without them, coverage fell to
  89.71%; with them the gate is green.
- sdist and wheel build; `twine check` passed.
- Wheel installed with all extras in a fresh environment; `pip check` clean; `ws4` and
  `python -m ws4.cli` work; `ws4 carbon|lidar|hydrology|disturbance --help` work; synthetic
  build → validate → simulate → report passes.
- Sdist installed in a separate fresh environment; version import and `ws4` entry point pass.
- Pages return 200 for the main docs, limitations, API, carbon, LidarBC, FEMIC hydrology,
  disturbance, and both GBR instance sites.

| Artifact | SHA-256 |
| --- | --- |
| `ws4-0.2.0-py3-none-any.whl` | `2421d96e8358b54357dc88f2fcaa1a246ee636093cc7f2cccaa4155c46be1978` |
| `ws4-0.2.0.tar.gz` | `f9a8836dee8ac3ca90ebe5eadb5d378acdbdc5353ee062fcc0c249b0cbaaef2c` |

The release policy requires rebuilding the published artifacts from the final tag, so these hashes
are candidate evidence rather than the final release hashes.

## 5. Release metadata

- `pyproject.toml`: `0.2.0`
- `ws4/__init__.py`: `0.2.0`
- `CITATION.cff`: `0.2.0`, date-released `2026-10-26`
- `RELEASE_NOTES.md`: `Target release: 2026-10-26`
- `v0.2.0` tag: **absent**
- Existing release: `v0.1.0` at `d8ecd72` (2026-10-15)

## 6. Tag and release, only after approval

```bash
# after this PR is squash-merged
git tag -a v0.2.0 -m "WS4 0.2.0"
git push origin v0.2.0
# rebuild from the tag, then publish
gh release create v0.2.0 \
  ws4-0.2.0.tar.gz ws4-0.2.0-py3-none-any.whl \
  --title "WS4 0.2.0" --notes-file RELEASE_NOTES.md
```

PyPI publishing remains out of scope.

## 7. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| P55.1 was merged outside this branch. | Release-notes work was landed separately as #421. | This branch builds on it; no duplicate notes. |
| The carbon extra broke the type and coverage gates. | `libcbm` has no `py.typed`, and CI did not install optional extras. | Added the mypy override and installed `.[geo,opt,carbon,lidar]` in the three test jobs. |
| The final head includes more than P51/P52. | P46, P56, P57, and P58 merged while P55 was blocked. | Updated the scope and notes to the actual final head. |
| Candidate artifact hashes are not final release hashes. | Release policy rebuilds from the tag. | Rebuild and record the hashes after tag approval. |

## 8. Decision

- [ ] Approve as written, including the `v0.2.0` tag and GitHub release.
- [ ] Approve the merge only; hold the tag for later.
- [ ] Approve with the changes stated here: <changes>.
