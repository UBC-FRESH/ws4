# Phase close-out report: P51 Release-candidate verification

Phase: P51, Release-candidate verification
Parent issue: #351
Pull request: this docs/tracker PR
Companion pull requests: none
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #351 with a closeout comment.
3. Launch P52, Version and release-notes decision: choose the next version, update
   `pyproject.toml`, `ws4/__init__.py`, `CITATION.cff`, and `RELEASE_NOTES.md`, then re-run the P51
   gates. Do not tag until that PR is approved.

Settings changes: none. This phase creates no tag, release, PyPI upload, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The clean-checkout test and dashboard pass. | `tests/test_clean_checkout.py`: 1 passed; dashboard green. | Met |
| The sdist and wheel build and install in an isolated environment. | `twine check` passed; wheel and sdist installs both pass `pip check`. | Met |
| `ws4` and `python -m ws4.cli` work from the installed wheel. | Both entry points print the command help; synthetic smoke passes. | Met |
| Docs/Pages return 200 for the key pages. | ws4 index, limitations, API index, and both instance indexes return 200. | Met |
| The report states whether the candidate is ready for a tag and names any blocker. | This report: green code, not tag-ready (version collision). | Met |
| No tag, release, version bump, or production-data change. | No tag/release created; version stays `0.1.0`. | Met |

## 2. Workflow compliance

- Parent issue #351 and children #352–#354 were created before the branch.
- Branch: `feature/p51-release-candidate`.
- No companion PRs; this is a ws4-only verification.
- Commit messages start with `P51`.

## 3. Environment and gates

- Clean worktree from `origin/main` at `f30cd5b`.
- Python 3.12.3 in a fresh virtual environment.
- Install: `pip install -e ".[geo,opt]"` plus `requirements-dev.txt`.
- `tests/test_clean_checkout.py`: 1 passed (FastAPI/httpx deprecation warning only).
- `scripts/dashboard.py`: green for lint, format, types, tests (104.70 s), workflow validator,
  docs (14.49 s), and docstrings.

## 4. Artifacts and isolated installs

| Artifact | Size | SHA-256 | Check |
| --- | ---: | --- | --- |
| `ws4-0.1.0-py3-none-any.whl` | 547 KB | `944aad5a167d714e7d0f55cecc4b41886a5d5d0a459991badde17906a939194c` | `twine check` passed |
| `ws4-0.1.0.tar.gz` | 519 KB | `2d7b870479caec89adce85c1e8219e3edbd42eb8452e4feef1fa6278201b71ee` | `twine check` passed |

- Wheel installed in a fresh environment; `pip check` reports no broken requirements.
- `ws4 --help` and `python -m ws4.cli --help` work from the wheel.
- `import ws4` reports `0.1.0` from the site-packages path.
- Synthetic smoke from the wheel: `build` (13 matrix files), `validate`, `simulate` (7 run files),
  and `report` all succeed.
- Sdist installed in a second fresh environment; `pip check`, version import, and the `ws4`
  entry point pass.
- Build warning: the `License :: OSI Approved :: Apache Software License` classifier is deprecated.
  It is non-blocking but should move to an SPDX expression in the version/release-notes PR.

## 5. Docs and Pages

| URL | Status |
| --- | ---: |
| https://ubc-fresh.github.io/ws4/ | 200 |
| https://ubc-fresh.github.io/ws4/guides/limitations-and-boundaries.html | 200 |
| https://ubc-fresh.github.io/ws4/api/index.html | 200 |
| https://ubc-fresh.github.io/femic-tsa46-instance/ | 200 |
| https://ubc-fresh.github.io/femic-tsa47-instance/ | 200 |
| https://ubc-fresh.github.io/femic-tsa46-instance/runtime-provenance.html | 200 |
| https://ubc-fresh.github.io/femic-tsa47-instance/runtime-provenance.html | 200 |

## 6. Release metadata audit

- `pyproject.toml`: `0.1.0`.
- `ws4/__init__.py`: `0.1.0`.
- `CITATION.cff`: `0.1.0`.
- `RELEASE_NOTES.md`: still `WS4 0.1.0`, released 2026-10-15.
- `v0.1.0` tag: tag object `d3486c0`, peeled commit `d8ecd72`.
- `v0.1.0` GitHub release: 2026-10-15, `https://github.com/UBC-FRESH/ws4/releases/tag/v0.1.0`.
- Verification head: `f30cd5b`.
- `main` after verification: `05c3b44` (P44 merged), then `1b4500e` (P44 closeout).

**Verdict:** the code and artifacts are green, but the candidate is **not tag-ready**. The version
metadata still says `0.1.0`, the `v0.1.0` tag and release already exist, and there are no release
notes for a new version. Tagging `f30cd5b` as `v0.1.0` would be wrong; tagging it as a new version
without updating the metadata would be inconsistent.

This is a version/release-notes blocker, not a code failure. P44 was open during the run and
merged after it as `05c3b44`; the P51 evidence does not cover that commit.

## 7. Draft candidate notes, not for publication

The changes since `0.1.0` are broad enough for a feature release, not a patch: target operations,
search-artifact depth, comparison/map operations, provenance and validation surfaces, provider
workflows, and instance boundaries. P44 merged after the verification run; P52 must re-verify the
final head before tagging.

## 8. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The candidate was not tagged. | `0.1.0` is already tagged and released; a new version needs approval. | P52 chooses the version and writes the notes; no tag until approved. |
| P44 was not in the verified candidate. | It was open during the run and merged afterwards as `05c3b44`. | Re-run P51 on the final release head after the version bump. |
| The docs API URL first tried (`api/ws4.html`) returned 404. | Wrong guessed page name. | The real index `api/index.html` returns 200. |
| The build emitted a deprecated license-classifier warning. | Setuptools metadata guidance changed. | Fix in P52 with an SPDX license expression. |

## 9. Next phase

Goal: choose and apply the next version, then re-verify.

Tasks:

- P52.1 Choose `0.2.0` (feature) or `0.1.1` (patch) using the release policy and the merged scope.
- P52.2 Update `pyproject.toml`, `ws4/__init__.py`, `CITATION.cff`, and `RELEASE_NOTES.md`.
- P52.3 Re-run the P51 clean-checkout, artifact, and Pages checks on the final head; request approval
  before any tag.

Recommended default: `0.2.0`, because the changes since `0.1.0` include feature-level surfaces.
Do not tag or publish in P52 without explicit approval.

## 10. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
