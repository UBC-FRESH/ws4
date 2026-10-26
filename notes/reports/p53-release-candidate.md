# Phase close-out report: P53 Version 0.2.0 release preparation

Phase: P53, Version 0.2.0 release preparation
Parent issue: #371
Pull request: this docs/tracker PR
Companion pull requests: none
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #371 with a closeout comment.
3. If release is approved, tag the merge commit as `v0.2.0`, push the tag, and publish a GitHub
   release with the 0.2.0 sdist and wheel. This report does **not** create the tag.

Settings changes: none. This phase creates no tag, release, PyPI upload, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| All version fields read 0.2.0. | `pyproject.toml`, `ws4/__init__.py`, `CITATION.cff`. | Met |
| Release notes cover the changes since 0.1.0. | `RELEASE_NOTES.md` 0.2.0 section. | Met |
| The package builds without the license-classifier warning. | Build log clean; METADATA has `License-Expression: Apache-2.0`. | Met |
| Clean-checkout, dashboard, artifacts, isolated installs, entry points, and Pages pass. | See sections 3–5. | Met |
| No tag or release is created. | No `v0.2.0` tag exists. | Met |

## 2. Workflow compliance

- Parent issue #371 and children #372–#374 were created before the branch.
- Branch: `feature/p53-v020`.
- No companion PRs; this is a ws4-only release-prep phase.
- Commit messages start with `P53`.

## 3. Version and release notes

- `pyproject.toml`: `0.2.0`
- `ws4/__init__.py`: `0.2.0`
- `CITATION.cff`: `0.2.0`, date-released `2026-10-25`
- `RELEASE_NOTES.md`: new 0.2.0 section above the retained 0.1.0 notes
- License metadata: `license = "Apache-2.0"`, `license-files = ["LICENSE"]`; deprecated classifier removed
- Build-system floor: `setuptools>=77`

The notes cover search and decision review, artifact depth, target operations, map/account
surfaces, provenance and limitations, FreshForge execution, and the GBR reference instances.
They explicitly exclude the open P51 and P52 phases; P45 is complete and its profiling/design is
present without incremental route code.

## 4. Verification

- Clean worktree from the P53 branch based on `6e49f12`; Python 3.12.3 fresh virtual environment.
- Clean-checkout test: 1 passed (FastAPI/httpx deprecation warning only).
- Dashboard: green — lint, format, strict types, tests (94.03 s), workflow validator, docs
  (5.16 s), docstrings.
- Build: `ws4-0.2.0-py3-none-any.whl` and `ws4-0.2.0.tar.gz`; no license-classifier warning.
- `twine check`: passed for both artifacts.
- Wheel and sdist installed in separate fresh environments; `pip check` clean.
- `ws4 --help` and `python -m ws4.cli --help` pass; `import ws4` reports 0.2.0 from site-packages.
- Synthetic build → validate → simulate → report passes; 13 matrix files and 7 run files.

| Artifact | SHA-256 |
| --- | --- |
| `ws4-0.2.0-py3-none-any.whl` | `11984b156cd6a3ae9c999d3849d9de788ab0646a531c90b0817bfd20f4a24df4` |
| `ws4-0.2.0.tar.gz` | `118fc573e598fa01733907e4c3d31244f41eb47148267ac28287a39a81e6a68c` |

Wheel metadata: `Version: 0.2.0`, `License-Expression: Apache-2.0`, `License-File: LICENSE`,
`Requires-Python: >=3.11`.

## 5. Docs and Pages

| URL | Status |
| --- | ---: |
| https://ubc-fresh.github.io/ws4/ | 200 |
| https://ubc-fresh.github.io/ws4/guides/limitations-and-boundaries.html | 200 |
| https://ubc-fresh.github.io/ws4/api/index.html | 200 |
| https://ubc-fresh.github.io/femic-tsa46-instance/ | 200 |
| https://ubc-fresh.github.io/femic-tsa47-instance/ | 200 |

## 6. Tag readiness

The 0.2.0 candidate is ready for tag approval. No `v0.2.0` tag exists. The recommended tag target is
the squash-merge commit of this PR.

Artifacts are candidate evidence. The release process should rebuild from a clean checkout of the
final tag, per `notes/release-policy.md`.

Tag and release, only after approval:

```bash
git tag -a v0.2.0 -m "WS4 0.2.0"
git push origin v0.2.0
gh release create v0.2.0 \
  /tmp/opencode/ws4-p53-dist/ws4-0.2.0.tar.gz \
  /tmp/opencode/ws4-p53-dist/ws4-0.2.0-py3-none-any.whl \
  --title "WS4 0.2.0" --notes-file RELEASE_NOTES.md
```

PyPI publishing remains out of scope.

## 7. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The phase number is P53, not the earlier suggested P52. | P52 is the LiDAR phase (#317/#323) and P51 was reused for carbon (#357). | Use P53 to avoid collision; no prior P53 issue/branch existed. |
| The release notes say "Target release". | The tag is not approved yet. | Change to "Released" only when the tag is created, if required by the release process. |
| The build uses `setuptools>=77`. | PEP 639 SPDX `license` and `license-files` support. | Verified the build and artifact metadata; no warning. |

## 8. Next phase

No new feature phase is needed for the release itself. After tag approval, verify the published
release artifacts with the P51 install/entry-point checks, then resume the open P45/P51/P52 work.

## 9. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
- [ ] Approve the `v0.2.0` tag and GitHub release in addition to the merge.
