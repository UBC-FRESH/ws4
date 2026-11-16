# BC VRI canopy-only treatment scenario

Date: 2026-11-16
Branch: `fire-canopy-scenario`
Artifact: `notes/reports/vri-canopy-scenario.json`
Input: `notes/reports/mkrf-vri-2025.geojson`

## Question

Does the measured FFS thin-burn canopy reduction change fire behaviour when the FBP fuel type
is held fixed?

## Setup

- open BC VRI 2025 Rank 1 polygons around the Malcolm Knapp Research Forest AOI;
- 100 m grid, rows 20, columns 42;
- fixed FBP fuel type C2, conifer 60%, dead fir 0%;
- control crown closure 55–70%, treated closure −22.9%;
- flat terrain, fixed weather: FFMC 90, BUI 60, wind 20 km/h, 270°;
- 120-minute run, point ignition on the west edge.

This is a controlled canopy-only diagnostic, not a weather forecast or an operational treatment
scenario. Surface fuel and post-treatment FBP fuel type are not changed.

## Result

| Case | Burned area | Perimeter | Head ROS |
| --- | ---: | ---: | ---: |
| control | 228.0 ha | 7,000 m | 16.149 m/min |
| treated | 228.0 ha | 7,000 m | 16.149 m/min |

**No effect.** The area difference is 0.0 ha.

## Decision

**No-go** for crown closure alone as the treatment mechanism in C2. The FBP C2 path is
insensitive to the measured canopy change over this range.

The next treatment scenario needs an explicit post-treatment fuel type or surface-fuel
representation. This is exactly the expert input the prescription contract already requires.

## Limits

- One AOI, one fuel type, one fixed weather case.
- Canopy closure only; no surface-fuel or fuel-type conversion.
- BC CRI treatment locations are Access Only and are not used.
- No operational claim.
