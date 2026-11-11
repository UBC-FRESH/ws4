# P165.2 depth-case review

Date: 2026-11-11
Phase: P165 (#985)
Task: P165.2 (#987)
Candidate: CFSDS `2023_321`
Decision: **no-go for the hourly/FBP depth tier**

## What was checked

The strongest untried public candidate in the repository is CFSDS `2023_321`, the large
Enterprise/Hay River-area event. I checked it against the P165.1 depth contract:

| Requirement | Result |
| --- | --- |
| Observed or satellite perimeter | pass, CFSDS daily raster |
| Hourly weather | fail, CFSDS provides daily weather |
| Ignition | partial, first-day burned centroid only |
| FBP fuel | available from FireSTARR 2023 tile, year-limited |
| Terrain | available from FireSTARR/NRCan DEM |
| Provenance | available |
| Licence | open data, third-party fuel terms still need review |

## Scale evidence

- 53 growth days.
- 433,036 ha final area.
- About 104 km east-west by 106 km north-south.
- 534,613 burned cells at 90 m.

The nearest ECCC station is close to the eastern edge, but the fire centroid is about 36 km
away and the western half is much farther. One station cannot represent hourly weather across
a 100 km fire.

## Decision

`2023_321` is **not admitted to the depth tier**. It remains a breadth candidate for P165.3.

No other public case in the repository meets the depth contract:

- WildfireAV is blocked on LANDFIRE FBFM40 fuel and an adapter.
- The Prometheus archive beyond Dogrib is not inventoried with complete inputs.
- FireSTARR and BurnP3 are model-only evidence.

Adding `2023_321` as depth would require calling daily weather hourly and treating one station
as representative of a 100 km footprint. That would weaken the corpus rather than expand it.

## Consequence

P165.2 is a **recorded no-go**. The depth corpus remains at two limited cases. P165.3 is the
next viable step: build the daily CFSDS breadth sample, where `2023_321` is admissible on its
actual daily basis.

P164.3 calibration remains paused.
