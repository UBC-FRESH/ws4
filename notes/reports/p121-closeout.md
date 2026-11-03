# Phase close-out report: P121 BEC crosswalk and AU integrity

Phase: P121 BEC crosswalk and AU integrity
Parent issue: #769
Branch: `feature/p121-bec-integrity`
Evidence head: `401745a`
Report commit: this metadata-only report update
Date: 2026-11-03
Status: queued as PR #782 for maintainer approval. Not merged.

## Recommendation

Queue the pull request for `feature/p121-bec-integrity` into `main` and wait for
the maintainer's approval. Do not merge, tag, release, or change settings until
that approval is explicit.

After approval:

1. Squash-merge the pull request.
2. Delete `feature/p121-bec-integrity`.
3. Close parent issue #769 with a closeout comment that cites the merge commit.
4. The next phase is not launched until the maintainer names it.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Classify the 247-row BEC union | 183 exact, 7 WS4 splits, 12 CCISS splits, 45 unresolved | met |
| Explicit unresolved rows | `bec_crosswalk_review.csv` | met |
| AU label parser | `ws4.sdmd.au_integrity.parse_au_label` | met |
| BEC/TSA/species integrity check | invalid TSA/BEC pair fails with `SDMD-AU-TSA-BEC` | met |
| Store wiring | `SdmdStore.from_directory` fails before reading the other tables | met |
| Tests | crosswalk, parser, valid, invalid, unknown, store negative | met |
| Dashboard green | `OVERALL: GREEN` at the evidence head | met |

## 2. Workflow compliance

- Parent issue #769 and children #770-#773.
- Branch `feature/p121-bec-integrity`.
- Commits start with P121.
- #770, #771, and #772 are closed; #773 closes with this report.
- PR queued, not merged; merge waits for approval.

## 3. Evidence

### Crosswalk

- 183 exact, 7 WS4 splits, 12 CCISS splits, 45 unresolved.
- The unresolved set is explicit; a prefix is a lead, not an equivalence.

### AU integrity

- `AU-IDFdk3-TSA23-FDI` passes.
- `AU-IDFdk3-TSA24-FDI` fails with `SDMD-AU-TSA-BEC`.
- An unknown BEC fails with `SDMD-AU-BEC`.
- A malformed label fails with `SDMD-AU-LABEL`.
- `SdmdStore.from_directory` raises `SdmdApiError` for the invalid label.

The support table is `tsa_bec_counts.csv`, 340 rows derived from the public FAIB
PSP header, Open Government Licence - British Columbia.

## 4. Known limits

- The validator checks public PSP support, not legal AU definition or boundary.
- 45 BEC labels remain unresolved.
- The species component is parsed but not checked against a species catalog.
- The check runs at store load; it does not repair an existing store.
- A valid BEC/TSA pair can still be a poor AU for other reasons.

## 5. Verification

```bash
python -m pytest tests/test_sdmd_bec.py tests/test_sdmd_au_integrity.py tests/test_sdmd_api.py -q
python scripts/check_workflow.py
python scripts/dashboard.py
```

At the evidence head: 45 focused tests pass, validator 0 errors, dashboard
`OVERALL: GREEN`.

## 6. Pull request

PR #782 names the phase, the evidence head, the crosswalk counts, the validator
rules, and the known limits. It is queued for approval. No merge, tag,
release, or settings change is performed by this report.
