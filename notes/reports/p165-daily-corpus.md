# P165.3 daily CFSDS breadth corpus

Date: 2026-11-11
Phase: P165 (#985)
Task: P165.3 (#988)
Registry: `ws4/fire/daily_corpus.py`
Manifest: `notes/reports/p165-daily-corpus.json`
Inventory: `notes/reports/p165-daily-corpus.csv`

## Result

20 ready daily cases across 3 years and 4 ecozones. The breadth coverage gate **passes**.

- Candidate events inspected: 903
- Candidates rejected by integrity checks: 14
- Final area range: 510.3 to 49765.6 ha
- Growth-duration range: 2 to 75 days
- Year counts: {'2003': 7, '2009': 6, '2023': 7}
- Ecozone counts: {'14': 13, '4': 2, '5': 3, '9': 2}

## Gate

| Check | Required | Observed | Result |
| --- | ---: | ---: | --- |
| Ready cases | 20 | 20 | pass |
| Distinct years | 2 | 3 | pass |
| Distinct ecozones | 2 | 4 | pass |

## Checks applied

- Daily summary and raster area agree within 2%.
- Daily weather fields (`ffmc`, `bui`, `ws`, `rh`, `prec`) are complete for every growth day.
- The final centroid is inside the FireSTARR UTM 11N fuel/terrain tile.
- The centroid fuel code is burnable, not non-fuel or nodata.
- The terrain sample is valid.
- Each event is an independent CFSDS identifier.

## Selected cases

| Case | Year | Days | Final ha | Ecozone | Fuel | Elevation m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2003_526 | 2003 | 16 | 510.3 | 14 | 415 | 1605 |
| 2003_679 | 2003 | 13 | 660.1 | 14 | 675 | 1550 |
| 2003_706 | 2003 | 5 | 823.0 | 14 | 3 | 1408 |
| 2003_647 | 2003 | 24 | 1517.1 | 14 | 675 | 2013 |
| 2003_730 | 2003 | 10 | 3179.2 | 14 | 675 | 2076 |
| 2003_709 | 2003 | 28 | 6351.2 | 14 | 3 | 1603 |
| 2003_663 | 2003 | 23 | 25489.9 | 14 | 31 | 1060 |
| 2009_147 | 2009 | 2 | 566.2 | 9 | 650 | 564 |
| 2009_79 | 2009 | 2 | 871.6 | 4 | 675 | 336 |
| 2009_258 | 2009 | 34 | 1207.7 | 14 | 3 | 1812 |
| 2009_360 | 2009 | 10 | 2229.1 | 14 | 675 | 1299 |
| 2009_338 | 2009 | 65 | 4037.0 | 14 | 675 | 1240 |
| 2009_386 | 2009 | 23 | 8243.4 | 14 | 7 | 983 |
| 2023_19 | 2023 | 15 | 522.5 | 5 | 13 | 430 |
| 2023_786 | 2023 | 28 | 1028.7 | 14 | 3 | 1837 |
| 2023_894 | 2023 | 16 | 1880.8 | 14 | 31 | 2169 |
| 2023_241 | 2023 | 31 | 4544.9 | 5 | 31 | 259 |
| 2023_240 | 2023 | 39 | 6774.0 | 5 | 2 | 397 |
| 2023_706 | 2023 | 18 | 13081.5 | 9 | 11 | 905 |
| 2023_686 | 2023 | 75 | 49765.6 | 4 | 2 | 854 |

## Interpretation

- This is an **observation-only breadth corpus**. No WS4 simulation was run against these cases.
- It is not hourly/FBP validation and not a regional validation. It is a multi-year, multi-ecozone daily sample inside one fuel/terrain tile.
- The daily basis is CFSDS daily progression and daily weather, not hourly weather.
- The corpus is suitable for a future daily event check and for sampling observed event distributions.
- P164.3 burn-probability calibration remains paused: this corpus is not model-ready hourly evidence.

## Sources

- Canadian Fire Spread Dataset v1.1, OSF `f48ry`: 2003, 2009, and 2023 group summaries and fire DOY rasters.
- FireSTARR 2023 Fuel V1.0 and NRCan DEM tile `11_0` for the fuel/terrain checks.
- CFSDS daily weather attributes in the group summaries.

## Limits

- One fuel/terrain tile (UTM 11N); spatial coverage is not national.
- Three years; no 2004-2008 or 2010-2022 sample.
- Daily rather than hourly weather.
- Satellite-derived perimeters and reconstructed first-day centroids.
- Integrity checks only; no model skill or treatment effect is claimed.

