# P203 time-dependent containment closure

Date: 2026-11-14
Phase: P203 (#1194)
Tasks: P203.1 (#1195), P203.2 (#1196), P203.3 (#1197)
Branch: `feature/p203-containment-closure`
Artifacts: `notes/reports/p203-containment-closure.json`, `p203-containment-closure.csv`

## Question

Can an explicit closure time on a containment gap produce weather-sensitive final extent without
calibrating an FBP parameter?

## Setup

- case: `2003_96`
- P201 synthetic barrier at column 55
- 5-cell gap centred on row 35
- closure times: 0, 6,000, 9,000, 10,500 and 12,000 minutes
- five P178 weather members
- closure is permanent once the gap cells reach their closure time

## Result

| Closure | Members containing | Members escaping | Final area |
| ---: | ---: | ---: | ---: |
| 0 min | 5 | 0 | 98,025 ha |
| 6,000 min | 5 | 0 | 98,025 ha |
| 9,000 min | 4 | 1 (rh-dry) | 98,025 / 158,025 ha |
| 10,500 min | 3 | 2 (wind-high, rh-dry) | 98,025 / 158,025 ha |
| 12,000 min | 2 | 3 (baseline, wind-high, rh-dry) | 98,025 / 158,025 ha |

This is the first weather-sensitive final-extent result in the FBP path. It comes from a real
time-dependent containment mechanism, not from changing a spread parameter.

## Decision

**Go** for time-dependent containment as a mechanism. Closure timing relative to arrival changes
whether each weather member is contained.

**No-go** for treating the current five closure times as an operational schedule. The barrier is
synthetic and oracle-assisted; no water, retardant, crew, rain or suppression-resource model is
present.

## Limits

- One case and one synthetic barrier.
- Closure is permanent; no reopening or maintenance.
- No water/retardant, rain extinction or suppression resources.
- No calibration and no operational claim.

## Next

Add the next explicit mechanism separately: rain extinction, water/retardant application, or crew
line construction with a documented rate. Do not tune FBP parameters for these effects.
