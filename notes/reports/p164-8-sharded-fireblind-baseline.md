# P164.8 sharded optimizer: fire-blind baseline

Status: diagnostic

This run repeats the 112-tile sharded optimizer with the calibrated fire source removed from the
local objective, then evaluates the resulting aggregate schedule on the full estate with the fire
source. It tests whether the current shard objective is actually fire-aware.

## Result

| Run | Scheduled events | Harvest (ha) | Final volume (m3) | Burned (ha) | Fire events | Wall time (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fire-evaluated shards | 179 | 20,775.6 | 859,981,233.9 | 74.25 | 16 | 655.5 |
| Fire-blind shards | 179 | 20,775.6 | 859,981,233.9 | 74.25 | 16 | 865.7 |

The schedules and accounts are identical.

## Finding

The local shard objective is a 10% harvest-area target. It does not contain a fire-risk term. The
calibrated fire source is therefore used for the full-estate evaluation but does not change the
local schedule. Calling the current workflow “fire-aware optimization” would be an overclaim.

The next step for a genuinely fire-aware sharded optimizer is to add a local risk target or
penalty, such as burned-area CVaR, volume-loss CVaR, or a fire-sensitive harvest rule, and rerun the
comparison.

## Artifacts

- `work/fire_regime/results/optimizer-full-estate-fireblind.json`
- `work/fire_regime/results/optimizer-full-estate-fireblind-schedule.csv`

## Boundary

Both runs use the same 112 eligible tiles, local harvest targets, and aggregate full-estate
evaluation. The fire-blind run removes the fire source only from the local optimization; the
aggregate evaluation still uses it. The result is a diagnostic, not a new optimization algorithm.
