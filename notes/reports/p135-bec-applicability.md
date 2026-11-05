# P135.1 BC SDMD applicability correction

Date: 2026-11-05
Parent: #824
Child: #825
Branch: `feature/p135-bec-applicability`

## What changed

The coverage registry was treating the 14 public SDMD diagrams as if each were a
variant-specific diagram. They are species/origin curves with zone-level BEC
applicability from the public Atlas catalogue. P135 applies that applicability.

- Added `reviewed_variant`, `reviewed_zone`, `mixed_zone`, and `no_diagram`
  statuses.
- Kept `match_level` visible: `variant`, `zone`, or `zone_rare`.
- Rebuilt the provisional review queue from the actual affected BEC labels.
- Updated the selector, API, tests, source manifest, and report.

## Counts

| Status | BEC labels |
| --- | ---: |
| `reviewed_variant` | 1 |
| `reviewed_zone` | 5 |
| `mixed_zone` | 209 |
| `no_diagram` | 4 |
| total | 219 |

`mixed_zone` means at least one reviewed and one provisional diagram apply. It
does not mean the BEC variant is fully reviewed. The 4 no-diagram labels are
`BAFAun`, `CMAun`, `CMAwh`, and `IMAun`.

The review queue has 10 provisional diagrams and 210 affected BEC labels. It is
a work list, not an approval.

## Evidence

- `scripts/build_bec_coverage.py`: source-catalog applicability and statuses.
- `bec_coverage.csv`, `bec_review_queue.csv`: regenerated registry and queue.
- `ws4/web/static/app.js`, `style.css`: status and review-count display.
- `tests/test_sdmd_coverage.py`, `test_bec_review_queue.py`,
  `test_build_bec_coverage.py`, `test_sdmd_api.py`.
- `scripts/check_bec_authority.py`: counts and manifest.

## Limits

- Zone-level applicability is not a variant-specific claim. The selector says so.
- `mixed_zone` still has a provisional component; review the 10 diagrams.
- Four no-diagram zones need new public source material or a permanent refusal.
- The two pilot AU stores remain the only assembled AUs.

## Verification

Focused tests: 129 passed. BEC authority check: pass. Dashboard:
`OVERALL: GREEN`.
