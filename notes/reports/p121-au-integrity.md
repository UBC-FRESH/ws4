# P121 AU integrity check

Date: 2026-11-03
Data: `ws4/sdmd/data/sdmd/tsa_bec_counts.csv` (340 rows).
BEC authority: `bec_official.csv` and `bec_retired.csv` from BC BECdb v13.
Source: FAIB PSP header and BC BECdb, Open Government Licence - British Columbia.
Code: `ws4.sdmd.au_integrity`.

## Rules

An AU label is parsed as `AU-<bec>[-TSA<number>]-<species>`.

The validator returns:

- `SDMD-AU-LABEL` when the label is malformed.
- `SDMD-AU-BEC` when the BEC label is in neither the current BECdb nor the WS4
  coverage table.
- `SDMD-AU-BEC-RETIRED` when the label is in the WS4 table but BECdb retired it.
  The message names the retirement version.
- `SDMD-AU-BEC-NO-COVERAGE` when the label is current in BECdb but absent from
  the WS4 coverage table. This is a coverage gap, not an unknown BEC.
- `SDMD-AU-TSA-BEC` when the TSA/BEC pair has no public PSP sites.

The counts are public PSP site counts, not a claim that an AU is legally defined.

## Examples

- `AU-IDFdk3-TSA23-FDI`: passes.
- `AU-IDFdk3-TSA24-FDI`: fails with `SDMD-AU-TSA-BEC`.
- `AU-CWHxm1-FDI`: fails with `SDMD-AU-BEC-RETIRED`; BECdb retired it in v13.
- `AU-CWHvh3-FDI`: fails with `SDMD-AU-BEC-NO-COVERAGE`; current BEC, no WS4
  coverage yet.
- `AU-XYZ99-TSA23-FDI`: fails with `SDMD-AU-BEC` and `SDMD-AU-TSA-BEC`.
- `bad-label`: fails with `SDMD-AU-LABEL`.

## Limits

- The check is evidence support, not an AU boundary or legal determination.
- A current BEC label without WS4 coverage cannot pass; the coverage table has to
  be deliberately extended with species evidence.
- The species component is parsed but not yet checked against a species catalog.
- The check runs at store load; it does not repair an existing store.
