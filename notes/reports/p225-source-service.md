# P225 water-source service utilization

Date: 2026-11-15
Phase: P225 (#1300)
Tasks: P225.1 (#1301), P225.2 (#1302)
Branch: `feature/p225-source-service`
Artifact: `notes/reports/p225-source-service.json`

## Setup

- three aircraft, 4.25-minute cycle
- 6,000 L per sortie
- refill rates 2,000–5,000 L/min
- one and two sources
- source utilization = aircraft service demand / source service capacity

## Result

| Sources | Refill/source | Service time | Utilization | Feasible |
| ---: | ---: | ---: | ---: | :---: |
| 1 | 4,000 L/min | 1.50 min | 1.059 | no |
| 1 | 5,000 L/min | 1.20 min | 0.847 | yes |
| 2 | 2,000 L/min | 3.00 min | 1.059 | no |
| 2 | 3,000 L/min | 2.00 min | 0.706 | yes |

Minimum refill rate: **4,235 L/min for one source**, or **2,118 L/min per source for two**.

## Interpretation

P224’s 4,000 L/min throughput threshold is exactly 100% on average, but source service time makes
it oversubscribed by about 6%. A single 4,000 L/min source cannot serve three aircraft on a
4.25-minute cycle without a growing queue.

The 5,000 L/min single source and the two 3,000 L/min sources have service margin.

## Decision

Go for source service time as the binding constraint. No-go for operational claims: no stochastic
refill, transit, failure or water-source drawdown model.

## Limits

- Deterministic service times.
- No queue-length simulation or downtime.
- No calibration and no operational claim.
