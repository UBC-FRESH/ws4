# P227 stochastic source-queue envelope

Date: 2026-11-15
Phase: P227 (#1308)
Tasks: P227.1 (#1309), P227.2 (#1310)
Branch: `feature/p227-stochastic-source`
Artifact: `notes/reports/p227-stochastic-source.json`

## Setup

- three aircraft, five-cell gap, eight applications
- source rates 3,500, 4,235, 5,000 and 6,000 L/min
- 100 seeded samples per rate
- service time jitter ±10%
- aircraft cycle jitter ±5%
- no downtime or source drawdown

## Result

| Refill | Feasible fraction | p95 cell gap | p95 end lateness | p95 source wait |
| ---: | ---: | ---: | ---: | ---: |
| 3,500 L/min | 0% | 11.42 min | +15.84 min | 3.78 min |
| 4,235 L/min | 100% | 10.31 min | −1.63 min | 3.15 min |
| 5,000 L/min | 100% | 10.03 min | −1.78 min | 2.71 min |
| 6,000 L/min | 100% | 9.83 min | −1.78 min | 2.32 min |

The P225 minimum of 4,235 L/min remains feasible across all 100 samples under the stated jitter.
At 3,500 L/min every sample fails and p95 end lateness is 15.84 minutes.

## Decision

Go for 4,235 L/min as the deterministic-plus-jitter source threshold. No-go for operational claims:
the jitter envelope is scenario input, not field evidence, and no downtime/drawdown is modeled.

## Limits

- Seeded scenario jitter only.
- No source failures, drawdown or transit variability.
- No calibration and no operational claim.
