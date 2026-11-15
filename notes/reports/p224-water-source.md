# P224 water-source throughput lower bound

Date: 2026-11-15
Phase: P224 (#1295)
Tasks: P224.1 (#1296), P224.2 (#1297)
Branch: `feature/p224-water-source`
Artifact: `notes/reports/p224-water-source.json`

## Setup

- P222 demand: 40 sorties/h
- 6,000 L per sortie
- required water: 240,000 L/h
- one and two sources
- refill rates 2,000–5,000 L/min
- perfect aircraft availability

## Result

| Sources | Refill/source | Supplied/h | Utilization | Feasible |
| ---: | ---: | ---: | ---: | :---: |
| 1 | 2,000 L/min | 120,000 L | 200% | no |
| 1 | 3,000 L/min | 180,000 L | 133% | no |
| 1 | 4,000 L/min | 240,000 L | 100% | yes |
| 1 | 5,000 L/min | 300,000 L | 80% | yes |
| 2 | 2,000 L/min | 240,000 L | 100% | yes |

Minimum refill rate: **4,000 L/min for one source**, or **2,000 L/min per source for two**.

## Interpretation

The three-aircraft queue has no water-source margin at the threshold: one 4,000 L/min source is
exactly saturated, and two 2,000 L/min sources are exactly saturated. Any refill variability or
additional aircraft demand creates a queue.

The next test should add source service time and queueing, not just throughput.

## Limits

- Throughput only; no refill service time or queue.
- No source capacity, weather, transit or maintenance limits.
- No calibration and no operational claim.
