# P226 source queue and refill feasibility

Date: 2026-11-15
Phase: P226 (#1304)
Tasks: P226.1 (#1305), P226.2 (#1306)
Branch: `feature/p226-source-queue`
Artifact: `notes/reports/p226-source-queue.json`

## Setup

- three aircraft, five-cell gap
- eight 15-minute applications
- 6,000 L per sortie, 4.25-minute cycle
- one source, refill rates 4,235 / 5,000 / 6,000 L/min
- deterministic service plus source queue

## Result

| Refill | Max cell gap | End lateness | Max source wait | Feasible |
| ---: | ---: | ---: | ---: | :---: |
| 3,000 L/min | 12.25 min | +36.25 min | 4.00 min | no |
| 4,235 L/min | 9.92 min | −2.25 min | 2.83 min | yes |
| 5,000 L/min | 9.70 min | −2.25 min | 2.40 min | yes |
| 6,000 L/min | 9.50 min | −2.25 min | 2.00 min | yes |

At the P225 minimum rate, the source queue peaks at 2.83 minutes but the three-aircraft schedule
still completes each application before the next interval. At 3,000 L/min the queue grows and the
schedule fails.

## Decision

Go for the deterministic source-queue result. No-go for operational claims: no stochastic refill,
downtime, source drawdown or transit variability.

## Limits

- Deterministic service times.
- One eight-application window.
- No failures or source capacity limits.
- No calibration and no operational claim.
