# P201 firebreak-gap sensitivity pilot

Date: 2026-11-14
Phase: P201 (#1185)
Tasks: P201.1 (#1186), P201.2 (#1187), P201.3 (#1188)
Branch: `feature/p201-firebreak-gap`
Artifacts: `notes/reports/p201-firebreak-gap.json`, `p201-firebreak-gap.csv`

## Question

Does a synthetic full-height firebreak with a gap produce weather-sensitive final extent on
`2003_96`?

## Geometry

- barrier column: 55
- full-height barrier
- gap centred on row 35, the observed final-fire centroid
- gap widths: 0, 5 and 10 cells
- five P178 weather members
- barrier placement is oracle-assisted: 60% of the distance from the mean start column to the
  eastern observed extent

## Result

| Gap | Area | Area bias | IoU | East of barrier | Time to observed area |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 98,025 ha | 2.142 | 0.210 | 0 | 3,540–9,000 min |
| 5 | 158,025 ha | 4.065 | 0.191 | 2,396 cells | 3,540–9,000 min |
| 10 | 158,150 ha | 4.069 | 0.191 | 2,396 cells | 3,540–9,000 min |

All five weather members have identical final area and IoU at each gap width. Weather changes the
time to observed area, not whether the fire crosses the gap or how much it burns.

## Decision

**No-go** for extending the gap pilot to the other three cases. The gap/containment geometry
dominates the final extent; a larger weather ensemble cannot make the result weather-sensitive.

This is consistent with P198/P178: the missing mechanism is a dynamic stopping or containment
model, not a different weather member.

## Limits

- One case.
- Synthetic, oracle-assisted barrier geometry.
- No surveyed firebreak or road/water layer.
- No calibration and no operational claim.

## Next

Do not run gap-width sweeps on the remaining cases. P202 (minimum ROS/intensity stopping) is not
justified by this pilot; it would need a published, pre-registered threshold first.
