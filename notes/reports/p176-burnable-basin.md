# P176 burnable-basin and stopping diagnosis

Date: 2026-11-11
Phase: P176 (#1041)
Task: P176.2 (#1043)
Manifest: `notes/reports/p176-burnable-basin.json`
CSV: `notes/reports/p176-burnable-basin.csv`

## Result

Across 12 small, large, and fine cases:

- median simulated area / burnable basin: **0.995**
- median observed area / burnable basin: **0.130**
- cases with simulated area ≥95% of basin: **8 of 12**
- cases with observed area <50% of basin: **12 of 12**

| Case | Burnable ha | Observed ha | Simulated ha | Sim/basin | Obs/basin |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2003_526 | 5,385 | 510 | 5,325 | 0.99 | 0.09 |
| 2003_706 | 9,612 | 823 | 9,578 | 1.00 | 0.09 |
| 2009_147 | 7,350 | 566 | 4,629 | 0.63 | 0.08 |
| 2009_79 | 11,376 | 872 | 11,372 | 1.00 | 0.08 |
| 2023_19 | 5,630 | 522 | 5,628 | 1.00 | 0.09 |
| 2023_786 | 14,170 | 1,029 | 14,165 | 1.00 | 0.07 |
| 2003_96 (500 m) | 159,800 | 28,355 | 146,532 | 0.92 | 0.18 |
| 2003_663 (500 m) | 77,925 | 25,490 | 61,263 | 0.79 | 0.33 |
| 2023_331 (500 m) | 517,650 | 133,080 | 514,175 | 0.99 | 0.26 |
| 2023_366 (500 m) | 1,150,350 | 190,388 | 1,149,275 | 1.00 | 0.17 |
| 2003_96 (100 m) | 146,599 | 28,355 | 146,532 | 1.00 | 0.19 |
| 2003_663 (100 m) | 68,087 | 25,490 | 61,263 | 0.90 | 0.37 |

## Interpretation

The model is not underreacting to weather, fuel, or terrain. It is **filling the connected
burnable basin**. Observed fires stop far short because of containment, suppression, fuel
breaks, or a smaller effective burnable area.

This explains both regimes:

- small fires: ~10x bias because the basin is much larger than the contained fire;
- large fires: ~2-4x bias because the fire gets closer to the basin edge but still overfills it.

## Decision

The next change must be a **stopping/containment mechanism** or a defensible **burnable-area
constraint**. A global ROS, fuel, weather, or terrain multiplier is not justified.

P164.3 remains paused.
