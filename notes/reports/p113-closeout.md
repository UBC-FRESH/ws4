# Phase close-out report: P113 SDMD atlas completion

Phase: P113 SDMD atlas completion
Parent issue: #731
Branch: `feature/p107-sdmd-atlas`
Evidence head: `ea78296`
Report commit: this metadata-only report update
Date: 2026-11-03
Status: queued for maintainer approval. Not merged.

## Recommendation

Queue the pull request for `feature/p107-sdmd-atlas` into `main` and wait for the
maintainer's approval. Do not merge, tag, release, or change settings until that
approval is explicit.

After approval:

1. Squash-merge the pull request.
2. Delete `feature/p107-sdmd-atlas`.
3. Close parent issue #731 with a closeout comment that cites the merge commit.
4. The next phase is not launched until the maintainer names it.

Settings changes: none.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Reusable digitisation/QA pipeline | `ws4.sdmd.digitise`, `ws4.sdmd.trace`, `ws4.sdmd.workflow`, `workflows/sdmd-digitise.yaml` | met |
| Remaining natural diagrams | `cdf-cwh-fdc-natural`, `cdf-cwh-ss-natural`, `cwh-hw-natural`, `sbs-sw-natural`, `cwh-cw-natural` | met, provisional |
| Remaining planted diagrams | `cdf-cwh-fdc-planted`, `cdf-cwh-ss-planted`, `cwh-hw-planted`, `cwh-cw-planted`, `sbs-sw-planted` | met, provisional |
| Every catalogued PDF stored | 14 digitizations for 14 diagrams; SHA matches | met |
| Every diagram validates | `validate_diagram` returns no findings for all 14 | met |
| Source catalog current | 14 entries, review status and notes | met |
| Coverage report | `notes/reports/p113-atlas-coverage.md` | met |
| Dashboard green | `OVERALL: GREEN` at the evidence head | met |

## 2. Workflow compliance

- Parent issue #731 and children #735, #736, #737, #739.
- Branch `feature/p107-sdmd-atlas`.
- Commits start with P113.
- #735, #736, and #737 are closed; #739 closes with this report.
- PR queued, not merged; merge waits for approval.

## 3. Tooling

- `figrecover` renders the PDF pages, produces QA overlays, and writes review
  manifests.
- `freshforge` carries the `render -> extract -> overlay -> review` workflow.
- `ws4.sdmd.digitise` keeps the vector-path extractor because the PDFs are vector
  Illustrators.
- `ws4.sdmd.trace` handles dotted crown-closure curves that are not single vector
  paths.

The optional extra is `pip install -e '.[digitise]'`.

## 4. Atlas status

- 14 diagrams: 7 species × natural/planted.
- 4 reviewed: `fdin`, `fdip`, `pln`, `plp`.
- 10 provisional: `fdcn`, `fdcp`, `ssn`, `ssp`, `hwn`, `hwp`, `cwn`, `cwp`, `swn`, `swp`.
- All 14 pass the diagram contract.

The coverage table and BEC counts are in `notes/reports/p113-atlas-coverage.md`.

## 5. Known limits

- The atlas is species/origin-level; it is not a BEC-variant or site-series atlas.
- The ten provisional diagrams use raster-traced crown closure.
- Planted top-height labels are offset in the source PDFs and are the first review
  item.
- The BEC rows are inferred from the BC Tree Species Compendium; a forester must
  confirm them for an AU.
- The CCISS crosswalk still has 30 WS4-only and 34 CCISS-only labels.
- The atlas is not calibrated to AFRF and is not a growth model.

## 6. Verification

```bash
python -m pytest tests/test_sdmd_diagram.py tests/test_sdmd_sources.py -q
python scripts/check_workflow.py
python scripts/dashboard.py
```

Results at the evidence head:

- 68 focused diagram/source tests passed.
- Workflow validator: 0 errors, 0 warnings.
- Dashboard: `OVERALL: GREEN` on all seven gates.

## 7. Pull request

The PR body names the phase, the evidence head, the atlas status, and the known
limits. It is queued for approval. No merge, tag, release, or settings change is
performed by this report.
