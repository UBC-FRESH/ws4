# P229 Alberta HWF113 water-source screen

Date: 2026-11-15
Phase: P229 (#1316)
Tasks: P229.1 (#1317), P229.2 (#1318)
Branch: `feature/p229-alberta-water`
Artifact: `notes/reports/p229-alberta-water-source.json`

## Setup

The P217 gap case `2003_96` is Alberta fire **HWF113**, not a BC fire. The Alberta historical
wildfire table gives:

- location: 59.2778 N, 114.8919 W
- recorded size: 29,936 ha
- start: 2003-07-29 15:00
- cause: lightning

The P217 gap centre is at UTM zone 11N **(636250, 6572250)**, or
**59.26721 N, 114.60959 W**. It is roughly 1 km west of the HWF113 ignition point.

Candidate waterbodies come from the **Alberta Base Waterbody Polygon Update** service,
layer 69, under the Open Government Licence - Alberta. The query envelope was
`-115.0, 59.08, -114.22, 59.45`, covering a 40 x 40 km window around the gap. The raw
response contained 718 waterbody polygons. The screen keeps polygons of at least 1 ha
within 20 km of the gap.

The raw response was retrieved on 2026-11-15 from the service above. Its SHA256 is
`ed3bd27a94b905fae043641d62bcb101f27bbe8b55601b51bbafdc3173cc4bf1`.

## Result

There are **405 candidate waterbodies** of at least 1 ha within 20 km. The nearest
candidates by area threshold are:

| Minimum area | Distance | Area | Feature |
| ---: | ---: | ---: | --- |
| 1 ha | 0.38 km | 3.29 ha | perennial lake |
| 5 ha | 1.19 km | 18.45 ha | perennial lake |
| 10 ha | 1.19 km | 18.45 ha | perennial lake |
| 50 ha | 3.15 km | 81.09 ha | perennial lake |
| 100 ha | 4.35 km | 200.83 ha | major river |

The nearest source is a 3.29 ha perennial lake 0.38 km from the gap centre. The more
robust nearby candidate is an 18.45 ha perennial lake 1.19 km away.

## Decision

Source proximity is not the obvious limiting factor for the P217 gap tactic: an 18.45 ha
perennial lake lies within 1.2 km of the gap. This is consistent with the P226 4.25-minute
cycle assumption.

This is **not** a refill or drawdown result. The current waterbody layer has no depth,
volume, access, approval, or source-downtime data. It is also a current layer, not a
2003 source inventory. The P226 source threshold remains **4,235 L/min**, and the P227
jitter envelope remains a model bound, not field evidence.

## Limits

- Current Alberta waterbody geometry, not 2003 historical source availability.
- No bathymetry, volume, drawdown, pump rate, access or approval.
- No aircraft performance or dispatch validation.
- The 40 x 40 km query window and 1 ha filter are screening choices, not operational rules.
- No calibration and no operational claim.

## Query

Service:
`https://geospatial.alberta.ca/titan/rest/services/base/base_water_feature_gcs_nad83/MapServer/69/query`

Parameters:
`where=1=1`, envelope `-115.0,59.08,-114.22,59.45`, `inSR=4326`,
`outFields=OBJECTID,FEATURE_TYPE,NAME,GDB.BF_HYDRO_POLYGON.AREA`,
`returnGeometry=true`, `outSR=4326`, `f=json`.

The screen can be reproduced with:

```bash
python scripts/alberta_water_sources.py \
  --features alberta_lakes_40km.json \
  --gap-x 636250 --gap-y 6572250 \
  --min-area-ha 1 --max-distance-km 20 \
  --output notes/reports/p229-alberta-water-source.json
```
