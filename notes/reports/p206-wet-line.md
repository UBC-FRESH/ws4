# P206 temporary wet-line suppression

Date: 2026-11-14
Phase: P206 (#1217)
Tasks: P206.1 (#1218), P206.2 (#1219), P206.3 (#1220)
Branch: `feature/p206-wet-line`
Artifacts: `notes/reports/p206-wet-line.json`, `p206-wet-line.csv`

## Question

Does a temporary wet line produce weather-sensitive containment in the FBP path?

## Setup

- case: `2003_96`
- P201 barrier at column 55 with a 5-cell gap
- gap cells non-ignitable until the wet-until time
- wet-until times: 12,000, 14,000 and 16,000 minutes
- five P178 weather members

This is a temporary non-ignitable-cell contract, not a drop-depth or tanker model.

## Result

| Wet until | Members contained | Members crossing | Final area |
| ---: | ---: | ---: | ---: |
| 12,000 min | 0 | 5 | 158,025 ha |
| 14,000 min | 0 | 5 | 158,025 ha |
| 16,000 min | 1 (rh-dry) | 4 | 98,025 / 158,025 ha |

The gap cells dry before most weather members arrive. At 16,000 min the dry member is still wet at
arrival and is contained, while the others cross after drying.

## Decision

**Go** for temporary wet-cell suppression as a mechanism. Wet duration relative to arrival changes
the containment outcome and is weather-sensitive.

**No-go** for operational water/retardant claims. The wet duration is long, geometry is synthetic,
and there is no depth, coverage, drop pattern, tanker, helicopter or refill model.

## Limits

- Temporary non-ignitable cells, not water depth/decay.
- Synthetic, oracle-assisted barrier geometry.
- Five weather members and one case.
- No calibration and no operational claim.
