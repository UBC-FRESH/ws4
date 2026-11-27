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

## Full AOI process-model cache

The full 30 km cache contains **484 usable tiles**: 351 non-TSA24 tiles built from public VRI plus
133 canonical TSA24 tiles. It has **14,520 potential fires** (30 per tile). Non-TSA24 weather is
TSA-level, not tile-level.

Fit on TSA08, TSA16, TSA24; hold out TSA40, TSA41. Training: median **100.6 vs 99.9 ha**, p90
**3,820.1 vs 4,489.1 ha**, p95 **8,714.6 vs 11,633.1 ha**. Held-out: median **106.3 vs 92.2 ha**,
p90 **2,437.5 vs 1,687.7 ha**, p95 **4,971.1 vs 4,516.4 ha**. Held-out TSA median ratios: **0.98**
and **1.38** (pooled 1.15). The upper tail remains high, and weather is TSA-level; this is partial
spatial transfer, not a universal model.

## Next block

The full tile-cache pipeline is complete. The next improvement is tile-level weather and a
hierarchical retention model; the current holdout uses TSA-level weather and an aggregate TSA
target.
