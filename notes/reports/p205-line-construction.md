# P205 crew line-construction rate

Date: 2026-11-14
Phase: P205 (#1212)
Tasks: P205.1 (#1213), P205.2 (#1214), P205.3 (#1215)
Branch: `feature/p205-line-construction`
Artifacts: `notes/reports/p205-line-construction.json`, `p205-line-construction.csv`

## Question

Does the rate at which a crew builds a containment line change the final extent, and does weather
change that outcome?

## Setup

- case: `2003_96`
- vertical barrier at P201 column 55
- construction starts at row 0 and proceeds down the line
- rates: 80, 200 and 400 m/h
- five P178 weather members
- no static barrier; each cell is open until its construction time

## Result

| Rate | Final area | Crossing | Weather spread |
| ---: | ---: | --- | --- |
| 80 m/h | 158,325–159,250 ha | all members crossed | ~925 ha |
| 200 m/h | 98,025 ha | none crossed | 0 |
| 400 m/h | 98,025 ha | none crossed | 0 |

At 80 m/h the fire outruns line construction and crosses in every weather member. At 200 m/h and
above the line closes before arrival and contains every member.

## Decision

**Go** for construction rate as a meaningful mechanism: the rate threshold changes containment.

**No-go** for weather-sensitive final extent in this pilot. The rate threshold dominates; within a
rate, all weather members produce the same containment outcome.

## Limits

- One case and one synthetic barrier.
- Construction starts at row 0 and proceeds monotonically.
- No pumps, hose lays, water, fatigue or crew travel.
- Rates are scenario inputs, not calibrated crew production rates.
- No calibration and no operational claim.
