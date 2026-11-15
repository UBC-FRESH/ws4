# P217 re-wetting interval at 100 m

Date: 2026-11-15
Phase: P217 (#1262)
Tasks: P217.1 (#1263), P217.2 (#1264), P217.3 (#1265)
Branch: `feature/p217-rewetting`
Artifacts: `notes/reports/p217-rewetting-15.json`, `p217-rewetting-30.json`

## Setup

- `2003_96` fine grid, 100 m
- P201 barrier with a 5-cell gap
- two 6,000 L drops per gap cell
- initial depth 1.18 mm, 0.75 mm threshold, 60-minute decay
- perfect re-wetting at 15 and 30 minutes
- baseline weather member

## Result

| Interval | Final area | Crossing |
| ---: | ---: | ---: |
| 15 min | **92,722 ha** | none |
| 30 min | 146,191 ha | 53,464 cells east |
| 60 min | not completed | — |

At 15 minutes the line remains wet through the arrival window and contains the fire. At 30 minutes
the pseudo-gap opens between applications and the fire crosses. The 60-minute run exceeded the
execution budget and is not claimed.

## Decision

**Go** for perfect 15-minute re-wetting as a persistence mechanism.

**No-go** for operational claims: this is perfect, full-cell re-wetting with no dispatch, tanker,
coverage loss or refill model. It is the first 100 m result that both reaches the depth threshold and
stays wet through arrival.

## Limits

- One weather member; full ensemble not run.
- Perfect re-wetting, no aircraft or water-source constraints.
- Synthetic barrier geometry.
- 60-minute case not completed.
- No calibration and no operational claim.
