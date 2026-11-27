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

## Modelling boundary and five-tile pilot

TSA24 remains the full process-model calibration core, with matched multi-year weather, a 24-tile
potential sample, and a 133-tile layer cache. The AOI supports block/support compilation, empirical
fire-regime targets, and five no-fire estate baselines.

A five-tile pilot now tests process-model expansion: one 30 km tile per TSA, 30 potential fires per
tile, and 1950-2024 weather. The model was fitted on TSA08, TSA16, and TSA24 and applied unchanged
to TSA40 and TSA41. The training fit overpredicted the median (430.9 vs 93.3 ha); the held-out pooled
median was 532.1 vs 313.9 ha and p90 was 7,037.5 vs 4,352.9 ha. TSA-level median ratios were 0.25
and 8.7. This is a failed spatial-transfer pilot, not a validated five-TSA model.

## Next block

The five-tile pilot pipeline is complete. The remaining work is the full AOI tile cache, not just one
tile per TSA:

1. Tile the AOI at 30 km and materialise VRI/SRTM layers for every tile.
2. Generate potential fires for the full tile set.
3. Fit a hierarchical or spatially explicit retention model.
4. Validate against the five-TSA fire history and report which components transfer and which require
   regional recalibration.
