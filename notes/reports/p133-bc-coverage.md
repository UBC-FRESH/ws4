# P133.1 BC-wide SDMD coverage registry

Date: 2026-11-04
Parent: #817
Child: #818
Branch: `feature/p133-bc-coverage`

## What changed

- Added `bec_coverage.csv`: 219 current BEC labels, the applicable Atlas
  diagrams, review state, species/origin, and AU evidence.
- Added `GET /api/sdmd/coverage` and `GET /api/sdmd/coverage/{bec}`.
- Added a **BC coverage** selector to the SDMD workspace with zone and BEC
  selects, status badges, diagram names, species/origin, AU evidence, and a
  named note.
- The registry is derived from the BECdb authority table and the 14 Atlas
  diagrams. It does not infer an AU from a BEC label.

## Counts

| Status | BEC labels |
| --- | ---: |
| reviewed | 1 |
| provisional | 57 |
| no-diagram | 161 |
| total | 219 |

`IDFdk3` is the only reviewed variant and the only BEC with pilot AU evidence:
`AU-IDFdk3-TSA23-FDI` and `AU-IDFdk3-TSA23-PLI`. Every other row names either a
zone-level provisional diagram or no diagram at all.

## Evidence

- `scripts/build_bec_coverage.py`: reproducible registry builder.
- `ws4/sdmd/data/sdmd/bec_coverage.csv`: 219 rows.
- `ws4/sdmd/coverage.py`: loader, filter, and row lookup.
- `ws4/sdmd/api.py`: coverage endpoints.
- `ws4/web/static/index.html`, `app.js`, `style.css`: selector and detail panel.
- `tests/test_sdmd_coverage.py`: counts, reviewed/provisional/gap rows, filters.
- `tests/test_sdmd_api.py`: endpoint contract.
- `tests/test_web.py`: shell wiring.
- `scripts/check_bec_authority.py`: registry counts and manifest coverage.

## Verification

```bash
python -m pytest tests/test_sdmd_coverage.py tests/test_sdmd_api.py tests/test_web.py -q
python scripts/check_bec_authority.py
python scripts/dashboard.py
```

Focused tests: 126 passed. BEC authority check: pass. Dashboard:
`OVERALL: GREEN`.

## Limits

- A provisional diagram is a zone-level lead, not a reviewed BEC-specific claim.
- Most BEC labels have no digitized diagram; the selector says so.
- Most BEC labels have no AU store; the selector says so.
- The registry is coverage metadata, not evidence that an AU exists.
- `IDFdk3` is the only reviewed variant because only its atlas diagrams have been
  reviewed.
