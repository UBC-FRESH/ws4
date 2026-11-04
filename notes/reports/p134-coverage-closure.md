# P134.1 SDMD coverage closure and review queue

Date: 2026-11-04
Parent: #820
Child: #821
Branch: `feature/p134-coverage-closure`

## What changed

- Added `gap_reason` and `gap_action` to every coverage row.
- The 161 no-diagram labels are now split into:
  - **150** `variant_not_digitized`: the BEC zone has an Atlas diagram, but the
    specific variant is not digitized and reviewed.
  - **11** `no_atlas_zone`: no diagram in the 14-public Atlas covers the zone.
- Added `bec_review_queue.csv`: 10 provisional diagrams and the 57 BEC labels
  they affect.
- The SDMD coverage detail shows the gap reason and next action.
- Audited the TSA 24/27/29 AU evidence paths and named each blocker.

## Gap triage

| Gap reason | Labels | Meaning |
| --- | ---: | --- |
| `variant_not_digitized` | 150 | The zone has an Atlas diagram, but this variant is not covered by a digitized/reviewed diagram. |
| `no_atlas_zone` | 11 | No diagram in the 14-public Atlas covers this zone. |

The 11 `no_atlas_zone` labels are in `BAFA`, `BG`, `CMA`, `IMA`, and `PP`.
The 150 variant gaps are concentrated in `ESSF` (71), `ICH` (29), `IDF` (19),
`MS` (14), `BWBS` (7), `SWB` (6), and `SBPS` (4).

## Review queue

`bec_review_queue.csv` has 10 rows, all `provisional`:

`cwn`, `cwp`, `fdcn`, `fdcp`, `hwn`, `hwp`, `ssn`, `ssp`, `swn`, `swp`.

Their union is 57 BEC labels. The queue names the source PDF URL and the affected
labels. It does **not** mark any diagram reviewed.

## AU evidence audit

### TSA 24

No PSP store is present under the instance data. The instance has a compiled
matrix and geometry, but no plot/tree evidence that could populate the six SDMD
tables. SDMD on TSA 24 is a data-acquisition blocker, not a portal flag.

### TSA 27

`data/shp/tsa27.shp/stands.shp` has 37,463 polygons with `SPECIES_CD`, `age`,
`area`, and theme/curve fields. It does not carry TPH, basal area, top height,
QMD, or tree lists. It cannot produce an SDMD stand summary without additional
evidence.

### TSA 29

The PSP file
`data/downloads/bcdc/WHSE_FOREST_VEGETATION_GRY_PSP_STATUS_ACTIVE/GRY_PSP_STATUS_ACTIVE.gpkg`
is **67 bytes of ASCII text**, not a GeoPackage. It cannot be used.

### Knife Creek / IDF Cariboo

Public derived PSP summaries exist, but the Knife Creek 24-plot summary has no
age or site index and is uneven-aged. The IDF Cariboo 51-plot summary has age,
BEC, TSA, TPA, BA, and QMD, but no topography, volume, or plot area, and its tree
list is explicitly synthetic. It is a candidate for a regional evidence build,
not a validated AU store.

## Next actions

1. Review the 10 provisional diagrams; maintainer decides `reviewed` or
   `rejected`.
2. For the 150 variant gaps, digitize or reject a variant-specific diagram; do
   not promote zone-level provisional coverage.
3. For the 11 no-atlas-zone labels, decide whether to acquire/digitize a new
   public diagram or keep the named refusal.
4. Build an AU only where plot/tree/stand evidence supports all six tables.
5. Keep the selector's gap reason visible; no unrelated AU substitution.

## Verification

```bash
python -m pytest tests/test_sdmd_coverage.py tests/test_bec_review_queue.py \
  tests/test_build_bec_coverage.py tests/test_sdmd_api.py tests/test_web.py -q
python scripts/check_bec_authority.py
python scripts/dashboard.py
```

Focused tests: 129 passed. BEC authority check: pass. Dashboard:
`OVERALL: GREEN`.
