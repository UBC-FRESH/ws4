# P121 BEC crosswalk

Date: 2026-11-03
Primary source: BC BECdb v13 (2026), current and retired BGC unit tables,
Open Government Licence - British Columbia.
Secondary source: BC BEC Map Attribute Catalogue,
`BEC_BIOGEOCLIMATIC_POLY` version 13.1 (2026-07-08).
Inputs: `bec_variants.csv` (WS4, 229 rows), `bec_official.csv` (219 current
BEC 13 labels), `bec_retired.csv` (107 retired BEC labels), and
`bec_crosswalk.csv` (CCISS union).
Outputs: `bec_official_crosswalk.csv`, `bec_crosswalk_review.csv`.

## Result

Every WS4 label is accounted for against the official BECdb:

| Relationship | Rows |
| --- | --- |
| exact current BEC 13 label | 165 |
| retired BEC label, with retirement version | 48 |
| current BEC 13 label absent from the WS4 coverage table | 54 |
| WS4 label absent from both BECdb tables | 0 |
| total relationship rows | 267 |

There are no “unresolved” WS4 labels. The 48 WS4 labels that are not current
are retired in a named BEC version. The 54 current labels missing from WS4 are a
coverage gap, not an unknown classification.

## Retirements

The 48 retired labels cover 14 labels retired in BEC v13, 5 in v12, 7 in v11,
9 in v10, 7 in v8, 3 in v7, 2 in v6, and 1 in v3.

### Retired in BEC v13

`BAFAunp`, `CMAunp`, `CWHdm`, `CWHms1`, `CWHms2`, `CWHxm1`, `CWHxm2`,
`ESSFmw`, `IDFww1`, `IMAunp`, `MHun`, `MHwh1`, `SBSun`, `SWBun`.

Recorded successors or candidate current labels:

| Retired | Successor candidates | Evidence |
| --- | --- | --- |
| `CWHxm1` | `CWHdm1` | BECdb note: “was CWHxm1” |
| `CWHxm2` | `CWHdm2` | BECdb note: “was CWHxm2” |
| `CWHdm` | `CWHdm1`, `CWHdm2`, `CWHdm3` | BECdb note on `CWHdm3`: “was CWHdm”; shared prefix |
| `CWHms2` | `CWHws3` | BECdb note: “was part of old CWHms2” |
| `ESSFmw` | `ESSFun1`, `ESSFmw1`, `ESSFmw2`, `ESSFmwp`, `ESSFmww` | BECdb note on `ESSFun1`: “was ESSFmw”; shared prefix |
| `MHun` | `MHun1`, `MHunp` | BECdb note on `MHun1`: “replaces Mhun from version 12” |
| `SBSun` | `SBSmz`, `SBSun1`, `SBSvc` | BECdb notes: “replacing SBSun in part”; shared prefix |
| `SWBun` | `SWBun1`, `SWBuns` | BECdb note on `SWBun1`: “replacing SWBun”; shared prefix |

The remaining v13 retirements (`BAFAunp`, `CMAunp`, `CWHms1`, `IDFww1`,
`IMAunp`, `MHwh1`) have no successor recorded in BECdb. They are retired, not
unresolved.

### Retired in BEC v12 and v11

- v12: `IDFmw1`, `IDFxh4`, `MSmw1`, `MSmw2`, `PPxh3`.
- v11: `CWHun`, `ESSFwm`, `IDFun`, `MSdk1`, `MSdk2`, `MSun`, `PPdh2`.
  `ESSFwm` candidates are `ESSFwm1`–`ESSFwm4`, `ESSFwmp`, `ESSFwmw`;
  `MSun` has `MSun1`.

### Retired in BEC v10 and earlier

- v10: `ESSFdku`, `ESSFdm`, `ESSFdmp`, `ESSFdmw`, `ESSFwc1`, `ESSFwc5`,
  `ESSFwc6`, `ICHdw2`, `SWBdks`.
- v8: `BWBSdk1`, `BWBSdk2`, `BWBSmw1`, `BWBSmw2`, `BWBSun`, `CWHvm`,
  `SWBdk`. `CWHvm` candidates are `CWHvm1`–`CWHvm4`.
- v7: `ESSFxc` (candidates `ESSFxc1`–`ESSFxc3`, `ESSFxcp`, `ESSFxcw`),
  `MSxk` (`MSxk1`–`MSxk3`), `PPdh1`.
- v6: `ESSFvv`, `ESSFvvp`.
- v3: `MHwh2` → `MHvh`.

## Current labels missing from WS4

These 54 current BEC 13 labels are absent from `bec_variants.csv`:

`BWBSdk`, `BWBSmk`, `BWBSmw`, `CMAwh`, `CWHdm1`, `CWHdm2`, `CWHdm3`,
`CWHms3`, `CWHms4`, `CWHms5`, `CWHvh3`, `CWHvm4`, `CWHws3`, `CWHxs`,
`ESSFdh1`, `ESSFdh2`, `ESSFmcw`, `ESSFmh`, `ESSFmkw`, `ESSFmm3`, `ESSFun1`,
`ESSFun2`, `ESSFunp`, `ESSFwc7`, `ESSFwh1`–`ESSFwh3`, `ESSFwm1`–`ESSFwm4`,
`ESSFwvw`, `ICHdw4`, `ICHmk5`, `ICHun1`, `ICHwm5`, `ICHxm1`, `IDFdh`,
`IDFxx1`, `IDFxx2`, `MHms`, `MHmsp`, `MHun1`, `MHunp`, `MHvh`, `MHvhp`,
`MHwh`, `MSdw`, `MSun1`, `SBSmz`, `SBSun1`, `SBSvc`, `SWBun1`, `SWBuns`.

The WS4 coverage table is a species/origin inference table, not a current BEC
register. Adding these labels without species evidence would fabricate coverage.
They are recorded as a coverage gap.

## CCISS comparison

`bec_crosswalk_review.csv` compares WS4 with CCISS directly:

| Relationship | Rows |
| --- | --- |
| exact label | 183 |
| WS4 label finer than a CCISS parent | 7 |
| CCISS label finer than a WS4 parent | 16 |
| WS4 label absent from CCISS | 19 |
| CCISS label absent from WS4 | 22 |

The absent labels are named in the CSV. They are source-list differences, not
unresolved classifications. The BECdb crosswalk is the stronger evidence and
should be used first.

## Sources

- BECdb v13 download:
  `https://www.for.gov.bc.ca/hre/becweb/resources/codes-standards/standards-becdb.html`
- BEC Map Attribute Catalogue:
  `https://catalogue.data.gov.bc.ca/dataset/bec-map-attribute-catalogue`
- BEC map service:
  `https://test.maps.gov.bc.ca/arcgis/rest/services/whse/bcgw_pub_whse_forest_vegetation/MapServer/21`
- Licence: Open Government Licence - British Columbia.

## Limits

- The BECdb is a nomenclature and classification register, not a legal AU
  boundary or a site-series assignment for every polygon.
- Phase codes are ignored in the label comparison; WS4 labels are
  zone+subzone+variant.
- A successor candidate is a lead from a BECdb note or a shared prefix. It is not
  an equivalence claim and does not transfer species evidence.
- A current BEC label absent from WS4 has no SDMD coverage assignment until the
  coverage table is deliberately extended.

## Verification

`tests/test_sdmd_bec.py` checks the CCISS counts, the BECdb counts, the
retirement version and successor for `CWHxm1`, the absent-current label
`CWHvh3`, and the invariant that every WS4 label absent from current BECdb is in
the retired table.
