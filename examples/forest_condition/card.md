# Forest condition report: tsa23-pilot-2026

- **Scenario:** c5-seeded
- **Period:** 2026
- **Generated:** 2026-11-02T00:00:00Z
- **Review status:** draft
- **Status:** report-only; alerts are advisory, not operational decisions.

## Indicators

| Indicator | Value | Unit | Source | Status | Applicability |
| --- | ---: | --- | --- | --- | --- |
| basal_area | 23.87 | m2/ha | femic.inventory.als (2026.1) | ok | TSA23 IDF; BA-only pilot |
| dhi_cum | 0.42 | index | silvis-dhi (MODIS 6.1 2003-2022) | ok | static surrogate; not species habitat |

## Alerts

| Code | Severity | Indicator | Advisory message |
| --- | --- | --- | --- |
| ba-coverage | watch | basal_area | BA-only pilot covers 14.9% of TSA 23. |

## Provenance

- **instance:** femic-tsa23-instance@b12b051
- **source:** metadata/inv01/tsa23_ba_pilot_manifest.json

## Limits

- This card is report-only and does not change objectives, constraints, growth, or the solver.
- Alerts are advisory and must not be treated as operational decisions.
- Indicator applicability and review status must be checked before use.
