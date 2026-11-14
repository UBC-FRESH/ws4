# P204 rain-driven fire stopping

Date: 2026-11-14
Phase: P204 (#1205)
Tasks: P204.1 (#1206), P204.2 (#1207), P204.3 (#1208)
Branch: `feature/p204-rain-stopping`
Artifacts: `notes/reports/p204-rain-stopping.json`, `p204-rain-stopping-2023-366.json`

## Criterion

Latham and Rothermel (1993) fire-stopping precipitation criterion: at least 0.5 inch
(~12.7 mm) accumulated over five days or fewer. This is an expert-opinion criterion, not a
calibrated physical threshold.

The model applies a **hard stop** when the rolling five-day accumulation reaches 12.7 mm.

## Screening

The criterion first becomes reachable at:

| Case | First 12.7 mm event | Free-burn outcome |
| --- | ---: | --- |
| 2003_96 | 31,020 min | basin already filled |
| 2023_366 | 7,380 min | still growing |
| 2003_663 | never in event | no effect |
| 2023_331 | 46,500 min | basin already filled |

## Pilot

`2023_366`, five P178 weather members:

| Member | Rain-stopped area | Free-burn area |
| --- | ---: | ---: |
| baseline | 438,175 ha | 1,149,275 ha |
| wind-low | 396,175 ha | 1,149,275 ha |
| wind-high | 496,875 ha | 1,149,275 ha |
| rh-dry | 692,050 ha | 1,149,275 ha |
| rh-moist | 296,475 ha | 1,149,275 ha |

The same criterion has no effect on `2003_96`, where the five-day threshold is not reached until
after the basin is already full.

## Decision

**Go** for rain-driven stopping as an explicit mechanism. It produces weather-sensitive final
extent when the documented rain event occurs while the fire is still growing.

**No-go** for an operational rain-extinction claim. The criterion is expert opinion, the hard stop
does not allow reignition, and only one case shows a useful effect.

## Limits

- Expert-opinion criterion, not a physical extinction model.
- Hard stop; no smouldering or reignition.
- One positive case and one null case.
- No water, retardant, crews or suppression resources.
- No calibration and no operational claim.
