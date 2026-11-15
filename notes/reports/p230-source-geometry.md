# P230 HWF113 source-distance and drawdown closure

Date: 2026-11-15
Phase: P230 (#1321)
Tasks: P230.1 (#1322), P230.2 (#1323)
Branch: `feature/p230-source-geometry`
Artifact: `notes/reports/p230-source-geometry.json`

## Setup

This check uses the P229 HWF113 source screen and the existing P217/P226 gap schedule:

- eight applications, five gap cells, two 6,000 L drops per cell
- total gap demand: **480,000 L**
- cycle: **4.25 min**
- source refill rate: **4,235.294 L/min**
- payload: **6,000 L**
- service time: 1.417 min
- remaining travel budget: **2.833 min**

For each candidate, the equivalent drawdown is the full gap demand divided by the
waterbody area. The required average speed is the round-trip distance divided by the
travel budget. Both are geometry consistency checks, not aircraft performance claims.

## Result

| Candidate | Area | Distance | Equivalent drawdown | Required average speed |
| --- | ---: | ---: | ---: | ---: |
| perennial lake | 3.29 ha | 0.38 km | 14.57 mm | 16.1 km/h |
| perennial lake | 18.45 ha | 1.19 km | 2.60 mm | 50.3 km/h |
| perennial lake | 81.09 ha | 3.15 km | 0.59 mm | 133.5 km/h |
| Buffalo River | 200.83 ha | 4.35 km | 0.24 mm | 184.1 km/h |

Source proximity is not the limiting assumption. The 18.45 ha lake at 1.19 km requires
only a 50.3 km/h average to preserve the 4.25-minute cycle, and the 480,000 L demand is
only 2.60 mm of equivalent depth over that lake.

The 3.29 ha lake also clears the geometric check, but has the largest equivalent
drawdown, at 14.57 mm.

## Decision

**Go** for source geometry as consistent with the existing gap schedule.

**No-go** for operational or refill claims. The result does not establish:

- bathymetry, usable volume, or drawdown;
- pump or refill rate at the candidate source;
- access, approval, or water quality;
- route distance, wind, altitude, hover, or actual aircraft speed.

The P226 source threshold remains **4,235 L/min**. This phase only removes source
proximity and area as the obvious geometric blockers.

## Limits

- Candidate sources are the P229 nearest-by-area selection.
- The screen uses current waterbody geometry, not a 2003 source inventory.
- Distances are straight-line from the gap centre, not flight routes.
- Required average speed is a lower bound if the source is used directly.
- No calibration and no operational claim.
