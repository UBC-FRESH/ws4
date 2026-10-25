# Phase close-out report: P50 Runtime provenance and release verification

Phase: P50, Runtime provenance and release verification
Parent issue: #345
Pull request: this docs/tracker PR
Companion pull requests: femic-tsa46-instance #34, femic-tsa47-instance #35
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

Approve these actions. The agent carries them out in this order, and reads back each result.

1. Squash-merge this docs/tracker pull request.
2. Close parent issue #345 with a closeout comment that cites the companion merges.
3. Launch P51, Release-candidate verification: reproduce the package and clean-checkout gates,
   verify the docs/Pages and entry points, and prepare release notes. No tag or release without
   explicit approval.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Both runtime matrices carry the current tracked sidecar. | Sidecar hashes match `config/dataset_quality.yaml` in both instances. | Met |
| `ws4 quality --check` exits zero for both. | Both commands exit 0 with status `ok`, 12 tables, no warnings. | Met |
| The report names the matrix path, sidecar hash, quality status, and command. | `docs/runtime-provenance.rst` and `notes/reference/runtime-provenance.md`. | Met |
| The instance docs link the report and both dashboards stay green. | Index, model-build, decisions, and limitations links; dashboards green. | Met |

## 2. Workflow compliance

- Parent issue #345 and children #346–#348 were created before the branches.
- Instance branches: `feature/p50-runtime-provenance`.
- Companion PRs: femic-tsa46-instance #34, femic-tsa47-instance #35.
- Commit messages start with `P50`.

## 3. Merge evidence

- femic-tsa46-instance #34: `41281f1`.
- femic-tsa47-instance #35: `225edeb`.

## 4. Behaviour

- TSA 46 matrix: `runtime/tsa46_full/matrix`; sidecar SHA-256
  `50a48f25c515d0a17f231574ba79b9235af5067bd51e61fcda42baf58d30a13e`; manifest SHA-256
  `8f0c11de84c32c02e6ff9254cb2d6765cb78beeaa456eb33f546ebbe183d4487`.
- TSA 47 matrix: `runtime/tsa47_full/matrix`; sidecar SHA-256
  `a8900e98664e2413ce8522d9d15265b36c4069e5ab48e454fcf0bf52321b9c19`; manifest SHA-256
  `d5d01ad02488f4c559223659e3be20ca4cb640e3564438d641dbb65e0ff298bc`.
- Both quality gates: status `ok`, provenance supplied, 12 tables, no warnings. Target coverage is
  `not-applicable` because no targets were supplied; it is not a coverage pass.
- No matrix table, curve, target, or AAC input changed.
- The dated VDYP-transform backups were not refreshed.

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The matrices had no sidecar before this phase. | P47-P49 changed the tracked sidecar after the last full build; the runtime copies were absent. | Copied the tracked sidecar and verified both matrices. |
| The quality reports are untracked. | Runtime artifacts are intentionally excluded from Git. | Track the hash report and publish the docs page; keep the raw reports local. |
| Target coverage is not asserted. | No target file was supplied to the gate. | State `not-applicable`; run a target-aware check in a later phase if needed. |
| This is not a release tag. | A tag needs explicit approval. | P51 is scoped to release-candidate verification without tagging. |

## 6. Next phase

Goal: verify the release candidate without cutting a release.

Tasks:

- P51.1 Run a clean-checkout install and the full quality/dashboard gate.
- P51.2 Verify the docs/Pages links, provider entry points, and packaged artifacts.
- P51.3 Write release notes and request approval before any tag.

Recommended defaults:

- No tag, release, or settings change without explicit approval.
- Keep the full runtime data out of Git.
- Do not rebuild the matrix unless a gate fails.

## 7. Decision

- [ ] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
