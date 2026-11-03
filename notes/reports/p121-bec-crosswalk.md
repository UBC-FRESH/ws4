# P121 BEC crosswalk

Date: 2026-11-03
Inputs: `bec_variants.csv` (WS4, 229 rows) and `bec_crosswalk.csv` (247-row union).
Output: `bec_crosswalk_review.csv`.
Classifier: `ws4.sdmd.bec.classify_crosswalk`.

## Counts

| Relationship | Rows |
| --- | --- |
| exact match | 183 |
| WS4 split of a CCISS parent | 7 |
| CCISS split of a WS4 parent | 16 |
| unresolved | 41 |
| total | 247 |

## WS4 splits

`BWBSdk1`, `BWBSdk2`, `BWBSmw1`, `BWBSmw2`, `MHwh2`, `MSdk1`, and `MSdk2` are
finer WS4 labels under a broader CCISS label.

## CCISS splits

`ESSFmcw`, `ESSFmkw`, `ESSFwm1`–`ESSFwm4`, `ESSFwvw`, `ICHmc1a`, `ICHxwa`,
`MHunp`, `SBSwk3a`, and `SWBuns` are finer CCISS labels under a broader WS4
label. Four parent labels (`CWHvm`, `ESSFwm`, `ESSFxc`, `MSxk`) are represented
by their child split rows instead of being counted as unresolved.

## Unresolved

The 41 unresolved rows are explicit. Examples:

- WS4-only: `BWBSun`, `CWHun`, `CWHvm3`, `ESSFdku`, `ESSFvv`, `IDFun`, `PPdh1`.
- CCISS-only: `CMAwh`, `CWHvh3`, `ESSFdh1`, `ICHdw4`, `IDFdh`, `IDFxx2`.

These are version, aggregation, or classification differences that a simple
prefix rule cannot settle. They are not silently mapped.

## Limits

- A prefix relationship is a lead, not a scientific equivalence.
- The crosswalk does not replace the BEC classification or the source catalog.
- An AU using an unresolved label must still be reviewed by a forester.
- The 229-row WS4 table remains the coverage table; this file is a review aid.

## Verification

`tests/test_sdmd_bec.py` checks the relationship counts, exact matches, and
prefix-split examples. Dashboard gate is recorded in the phase changelog.
