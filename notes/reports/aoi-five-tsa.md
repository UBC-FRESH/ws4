# Five-TSA northeast BC AOI

Date: 2026-11-27
Status: AOI compilation and TSA24 process calibration separated

## Scope

The AOI is the contiguous group **TSA 08, 16, 24, 40, and 41** in northeastern British Columbia.
The dissolved boundary is **31.9 million ha** and is a single polygon.

## Evidence

| Item | Value |
|---|---:|
| AOI boundary area | 31,903,086 ha |
| AOI block layer | 1,550,199 blocks, 17.5 million ha productive |
| Compiled estate blocks | 1,550,468 |
| AOI 250 m support map | 3,763,756 cells, 10,777,196 memberships |
| Multi-fragment cells | 2,948,489 |
| Maximum fragments/cell | 18 |
| Blocks within 20% area | 99.4% |
| Median block-area error | 0.46% |
| Historical fire records | 3,834 |
| Fires >=6.25 ha | 3,015 |
| No-fire estate volume | 2.652 billion m3 |
| No-fire estate biomass | 1.181 billion t |

The AOI support map SHA-256 is
`22d9fd23b0b25f5117913625cc02779c3082d7c8d5c4f6766ea74389ba99685f`; the AOI block layer SHA-256 is
`d1d228d77faecd0e70cd4c7b785b8b8f3f39e43fafcdbd4b6c0cca897a8826c7`. Both large layers are
generated artifacts and are not tracked.

## Fire-regime heterogeneity

Using perimeters clipped to each TSA and the 6.25 ha support floor:

| TSA | Fires | Median ha | p90 ha | p95 ha |
|---|---:|---:|---:|---:|
| 08 | 750 | 159.7 | 7,696.9 | 19,085.2 |
| 16 | 335 | 142.6 | 4,814.1 | 9,226.4 |
| 24 | 677 | 60.1 | 1,502.0 | 4,881.2 |
| 40 | 662 | 95.6 | 1,912.1 | 6,301.8 |
| 41 | 591 | 90.4 | 1,399.9 | 3,154.5 |

TSA24 has the lowest median but not the heaviest tail. It is not representative of the AOI.

## Modelling boundary

The process model remains calibrated in TSA24, which is the only unit with matched multi-year
weather, a 24-tile potential sample, and a 133-tile layer cache. The AOI supports block/support
compilation, empirical fire-regime targets, and five no-fire estate baselines. It is not a
five-TSA process-model calibration.

## Next block

1. Build matched AOI weather and layer caches.
2. Regenerate potential fires for the five TSAs.
3. Fit a hierarchical or spatially explicit retention model and test TSA24-to-AOI transfer.
4. Report which components transfer and which require regional recalibration.
