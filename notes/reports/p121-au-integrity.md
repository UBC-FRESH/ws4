# P121 AU integrity check

Date: 2026-11-03
Data: `ws4/sdmd/data/sdmd/tsa_bec_counts.csv` (340 rows).
Source: FAIB PSP header, Open Government Licence - British Columbia.
Code: `ws4.sdmd.au_integrity`.

## Rules

An AU label is parsed as `AU-<bec>[-TSA<number>]-<species>`.

The validator returns:

- `SDMD-AU-LABEL` when the label is malformed.
- `SDMD-AU-BEC` when the BEC label is absent from `bec_variants.csv`.
- `SDMD-AU-TSA-BEC` when the TSA/BEC pair has no public PSP sites.

The counts are public PSP site counts, not a claim that an AU is legally defined.

## Examples

- `AU-IDFdk3-TSA23-FDI`: passes.
- `AU-IDFdk3-TSA24-FDI`: fails with `SDMD-AU-TSA-BEC`.
- `AU-XYZ99-TSA23-FDI`: fails with `SDMD-AU-BEC` and `SDMD-AU-TSA-BEC`.
- `bad-label`: fails with `SDMD-AU-LABEL`.

## Limits

- The check is evidence support, not an AU boundary or legal determination.
- A BEC label can be valid in the coverage table but still unresolved in the
  crosswalk.
- The next step is wiring it into the store/report path.
