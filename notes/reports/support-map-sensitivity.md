# Support-map sensitivity

Date: 2026-11-26
Status: resolved by replacing the legacy map

## Comparison

The canonical positive-overlap builder and the legacy frozen TSA24 map do not produce the same
memberships:

- legacy frozen: 1,310,129 memberships, 1,111,565 cells, median block-area error 64.1%
- canonical overlap: 3,546,374 memberships, 1,116,185 cells, median block-area error 0.4%

The canonical map assigns every block to every cell with positive overlap and uses cell-share
weights. The legacy map normalizes away partial cell coverage and assigns some blocks to cells with
no geometric overlap. The two maps are not equivalent.

## Applied case

The same deterministic five-year estate case gives:

| Metric | Legacy frozen | Canonical overlap |
| --- | ---: | ---: |
| Burned area | 5,842.3 ha | 6,360.7 ha |
| Fire events | 565 | 728 |
| Volume loss | 0.835 million m3 | 0.911 million m3 |

The five-seed risk case gives a median burned area of 7,478.8 ha under the legacy map and
10,822.6 ha under the canonical map; the worst-of-five volume loss is 1.384 and 2.069 million m3.

## Implication

Calibration, temporal, and transfer tables use potential-fire and layer-tile data, not the support
map, so they are unaffected. Estate, risk, and optimizer results depend on the support map and are
reported under the canonical map. The legacy numbers remain as a sensitivity comparison.

The earlier 10-event reconstruction used the legacy map and is no longer used as canonical
evidence. The temporal claim rests on the distributional holdout.
