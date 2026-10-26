# Resilience pilot

Two schedules over the sample estate (`examples/estate`) exercise the descriptive
resilience accounts. Both treat four eligible blocks at offset 0; one creates a
single compact opening, the other creates four scattered openings.

| Schedule | Blocks | Expected opening pattern |
| --- | --- | --- |
| `compact.csv` | 1, 2, 9, 10 | one 42.9 ha patch |
| `scattered.csv` | 1, 12, 25, 41 | four isolated patches (38.6 ha total) |

## Commands

```bash
ws4 build --xml examples/estate/recipe.xml \
  --fragments examples/estate/fragments.csv --out build/resilience

ws4 simulate --dataset build/resilience \
  --schedule examples/resilience_pilot/compact.csv --years 10 \
  --topology examples/estate/topology.csv --resilience \
  --out runs/compact

ws4 simulate --dataset build/resilience \
  --schedule examples/resilience_pilot/scattered.csv --years 10 \
  --topology examples/estate/topology.csv --resilience \
  --out runs/scattered

ws4 resilience compare \
  --run-a runs/compact --run-b runs/scattered \
  --output runs/resilience_comparison.csv

ws4 report --run runs/compact \
  --targets examples/resilience_pilot/targets.yaml
```

## What to look for

- `resilience.fragmentation.patch_count` is **1** for the compact schedule and
  **4** for the scattered schedule at offset 0.
- `resilience.fragmentation.mean_patch_area` is larger for the compact opening.
- The age-class count is the same for both at offset 0; fragmentation is therefore
  not a restatement of age diversity.
- `resilience.connectivity.largest_component` is the largest connected untreated
  block area over the full topology. It does not use a wind bearing; the existing
  directional `spread_metrics.csv` remains a separate account.
- `ws4 report` writes `report_resilience.csv` with definitions, units, semantics,
  baseline/final, total/mean/peak, and the caveat.

The numbers are a software smoke test on the sample estate, not a management
recommendation. Connectivity and fragmentation depend on the topology and block
aggregation; the age-class width is 20 years. Nothing here enters the objective.
