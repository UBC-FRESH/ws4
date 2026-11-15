# P222 gap-only dispatch queue feasibility

Date: 2026-11-15
Phase: P222 (#1288)
Tasks: P222.1 (#1289), P222.2 (#1290)
Branch: `feature/p222-dispatch-queue`
Artifact: `notes/reports/p222-dispatch-queue.json`

## Setup

- five-cell gap, two 6,000 L drops per cell
- eight applications at 15-minute intervals
- 4.25-minute mean cycle
- earliest-available aircraft queue
- no refill, water-source or weather limits

## Result

| Aircraft | Max cell gap | Max end lateness | Feasible |
| ---: | ---: | ---: | :---: |
| 2 | 12.75 min | +45.75 min | no |
| 3 | 10.75 min | −2.25 min | yes |
| 4 | 10.75 min | −6.50 min | yes |
| 5 | 10.75 min | −10.75 min | yes |

Three aircraft can deliver every application before the next 15-minute interval under perfect
queueing, with about 2.25 minutes of margin. Two aircraft accumulate lateness and are not feasible.

## Decision

Go for the three-aircraft gap-only queue result. It confirms P219’s lower bound survives a simple
round-robin dispatch queue.

No-go for operational claims: no refill, water-source, transit, weather, maintenance or coverage
losses are modeled.

## Limits

- Perfect aircraft availability and no failures.
- Identical sorties and cycle times.
- One gap geometry; no full-line case.
- No fire simulation; this is a dispatch-capacity test.
