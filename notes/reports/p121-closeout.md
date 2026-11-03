# Phase close-out report: P121 BEC crosswalk and AU integrity

Phase: P121 BEC crosswalk and AU integrity
Parent issue: #769
Branch: `feature/p121-bec-integrity`
Evidence head: `pending final code commit`
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
| Classify every WS4 BEC label | 165 current exact, 48 retired, 0 absent from BECdb | met |
| No silent “unresolved” labels | BECdb retirement version and successor candidates in `bec_official_crosswalk.csv` | met |
| CCISS difference table | 183 exact, 7 WS4 splits, 16 CCISS splits, 19/22 absent | met |
| AU label parser | `ws4.sdmd.au_integrity.parse_au_label` | met |
| BEC/TSA/species integrity check | retired, no-coverage, unknown, and impossible TSA/BEC findings | met |
| Store wiring | `SdmdStore.from_directory` fails before reading the other tables | met |
| Tests | crosswalk, parser, valid, invalid, retired, no-coverage, store negative | met |
| Dashboard green | `OVERALL: GREEN` at the evidence head | met |

## 2. Workflow compliance

- Parent issue #769 and children #770-#773.
- Branch `feature/p121-bec-integrity`.
- Commits start with P121.
- #770, #771, and #772 are closed; #773 closes with this report.
- PR queued, not merged; merge waits for approval.

## 3. Evidence

### Official BECdb crosswalk

The official source is BC BECdb v13 (2026), current and retired BGC unit tables,
downloaded from the BEC program:

`https://www.for.gov.bc.ca/hre/becweb/resources/codes-standards/standards-becdb.html`

Counts:

- 165 WS4 labels are exact current BEC 13 labels.
- 48 WS4 labels are retired. Every one carries its retirement version: 14 in
  v13, 5 in v12, 7 in v11, 9 in v10, 7 in v8, 3 in v7, 2 in v6, 1 in v3.
- 0 WS4 labels are absent from both BECdb tables.
- 54 current BEC 13 labels are absent from the WS4 coverage table; this is a
  coverage gap, not an unknown classification.

Recorded renames include `CWHxm1` → `CWHdm1`, `CWHxm2` → `CWHdm2`,
`ESSFmw` → `ESSFun1`, `MHwh2` → `MHvh`, and `SWBun` → `SWBun1`/`SWBuns`.
The CSV also lists candidate successors where BECdb records only a partial
replacement, such as `CWHms2` → `CWHws3`.

### CCISS crosswalk

The separate CCISS table is `bec_crosswalk_review.csv`:

- 183 exact
- 7 WS4 splits
- 16 CCISS splits
- 19 WS4 labels absent from CCISS
- 22 CCISS labels absent from WS4

The absent labels are named. They are source-list differences, not unresolved
classifications. BECdb is the stronger nomenclature authority.

### AU integrity

- `AU-IDFdk3-TSA23-FDI` passes.
- `AU-IDFdk3-TSA24-FDI` fails with `SDMD-AU-TSA-BEC`.
- `AU-CWHxm1-FDI` fails with `SDMD-AU-BEC-RETIRED` (BEC v13).
- `AU-CWHvh3-FDI` fails with `SDMD-AU-BEC-NO-COVERAGE`.
- An unknown BEC fails with `SDMD-AU-BEC`.
- A malformed label fails with `SDMD-AU-LABEL`.
- `SdmdStore.from_directory` raises `SdmdApiError` for an invalid or retired
  label.

The support table is `tsa_bec_counts.csv`, 340 rows derived from the public FAIB
PSP header, Open Government Licence - British Columbia.

## 4. Known limits

- The validator checks public PSP support, not legal AU definition or boundary.
- 48 WS4 labels are retired; existing stores that use them now fail at load.
- 54 current BEC labels have no WS4 coverage and fail with
  `SDMD-AU-BEC-NO-COVERAGE` until coverage is deliberately extended.
- A successor candidate is a lead from a BECdb note or shared prefix, not an
  equivalence claim.
- The species component is parsed but not checked against a species catalog.
- The check runs at store load; it does not repair an existing store.

## 5. Verification

```bash
python -m pytest tests/test_sdmd_bec.py tests/test_sdmd_au_integrity.py tests/test_sdmd_api.py -q
python scripts/check_workflow.py
python scripts/dashboard.py
```

At the evidence head: focused tests pass, validator 0 errors, dashboard
`OVERALL: GREEN`.

## 6. Pull request

PR #782 names the phase, the evidence head, the BECdb and CCISS counts, the
validator rules, and the known limits. It is queued for approval. No merge, tag,
release, or settings change is performed by this report.
