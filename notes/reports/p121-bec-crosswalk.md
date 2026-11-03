# P121 BEC crosswalk

Date: 2026-11-03
Official source: BC BEC Map Attribute Catalogue, `BEC_BIOGEOCLIMATIC_POLY`
version 13.1 (2026-07-08), Open Government Licence - British Columbia.
Inputs: `bec_variants.csv` (WS4, 229 rows), `bec_official.csv` (219 unique
BEC 13.1 labels), `bec_crosswalk.csv` (CCISS union).
Outputs: `bec_official_crosswalk.csv`, `bec_crosswalk_review.csv`.

## Official BEC 13.1 crosswalk

| Relationship | Rows |
| --- | --- |
| exact BEC 13.1 label | 165 |
| WS4 label finer than an official parent | 12 |
| official label finer than a WS4 parent | 17 |
| WS4 label absent from BEC 13.1 | 26 |
| official label absent from the WS4 table | 37 |
| total relationship rows | 257 |

The 26 WS4 labels absent from BEC 13.1 are named, not left as “unresolved”:

`BWBSun`, `CWHms1`, `CWHms2`, `CWHun`, `CWHxm1`, `CWHxm2`, `ESSFdku`,
`ESSFdm`, `ESSFdmp`, `ESSFdmw`, `ESSFvv`, `ESSFvvp`, `ESSFwc1`, `ESSFwc5`,
`ESSFwc6`, `ICHdw2`, `IDFmw1`, `IDFun`, `IDFxh4`, `MSmw1`, `MSmw2`, `PPdh1`,
`PPdh2`, `PPxh3`, `SWBdk`, `SWBdks`.

These are old, aggregated, or renamed labels in the WS4 table. They are not in the
current official list, so the WS4 coverage table should not be presented as the
current BEC 13.1 nomenclature without this qualification.

The 37 official labels absent from WS4 include new or finer BEC 13.1 units such as
`CWHms3`, `CWHms4`, `CWHms5`, `CWHvh3`, `CWHws3`, `ESSFdh1`, `ESSFdh2`,
`ESSFmh`, `ESSFmm3`, `ESSFwh1`–`ESSFwh3`, `ICHdw4`, `ICHmk5`, `ICHmw5`,
`IDFdh`, `IDFxx1`, `IDFxx2`, `MHms`, `MHmsp`, `MHvh`, `MHvhp`, `SBSmz`, `SBSvc`.
The WS4 coverage table needs a deliberate update if those units must be supported.

## WS4 and official splits

- 12 WS4 labels are finer than an official parent, for example `BWBSdk1`,
  `BWBSdk2`, `BWBSmw1`, `BWBSmw2`, `MHwh2`.
- 17 official labels are finer than a WS4 parent, for example `CWHdm1`–`CWHdm3`,
  `CWHvm4`, `ESSFwm1`–`ESSFwm4`, `ESSFxc1`–`ESSFxc3`, `MSxk1`–`MSxk3`.

A parent plus child is an aggregation/split relationship, not a renaming.

## CCISS crosswalk

The separate CCISS comparison remains in `bec_crosswalk_review.csv`:

- 183 exact
- 7 WS4 splits
- 16 CCISS splits
- 41 explicitly unresolved

Those 41 are unresolved **against CCISS**, not against BEC 13.1. The official
crosswalk is the stronger evidence and should be used first.

## Sources

- BEC Map Attribute Catalogue:
  `https://catalogue.data.gov.bc.ca/dataset/bec-map-attribute-catalogue`
- BEC map service:
  `https://test.maps.gov.bc.ca/arcgis/rest/services/whse/bcgw_pub_whse_forest_vegetation/MapServer/21`
- Licence: Open Government Licence - British Columbia.

## Limits

- The official table is a spatial attribute catalogue, not a legal AU boundary.
- Phase codes are ignored in the label comparison; the WS4 labels are
  zone+subzone+variant.
- An official label absent from WS4 has no SDMD coverage assignment in the current
  table.
- A WS4 label absent from BEC 13.1 should not be used as current nomenclature
  without a review.

## Verification

`tests/test_sdmd_bec.py` checks both crosswalks, the official counts, exact labels,
and split examples.
