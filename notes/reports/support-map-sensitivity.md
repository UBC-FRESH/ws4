# Support-map sensitivity

Date: 2026-11-26
Status: material applied-case sensitivity

## Comparison

The frozen TSA24 support map and the general builder described in `support-map-builder.md` do not
produce the same memberships:

- frozen: 1,310,129 memberships, 1,111,565 cells
- general builder: 1,053,254 memberships, 960,506 cells
- membership Jaccard: about 0.30

The same deterministic five-year estate case gives:

| Metric | Frozen | General builder |
| --- | ---: | ---: |
| Burned area | 5,842.3 ha | 4,265.0 ha |
| Fire events | 565 | 460 |
| Volume loss | 0.835 million m3 | 0.637 million m3 |

## Implication

Calibration, temporal, and transfer tables use potential-fire/layer-tile data, not the support map;
they are unaffected by this choice. The estate, risk, event, and optimizer results depend on the
support map and must be either rerun with the general builder or labelled as conditional on the
frozen map.

Do not describe the two maps as equivalent.

## Decision required

1. Keep the frozen TSA24 map as canonical and report the sensitivity.
2. Switch to the general builder and rerun all applied cases.
