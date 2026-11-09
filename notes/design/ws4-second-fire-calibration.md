# Second observed fire and calibration gate

Status: P161.1 data gate — conditional pass
Phase: P161 (Second observed fire and calibration protocol)
Date: 2026-11-09
Related: P157 (#923), P160 (#947), P161 (#954)

## 1. Decision

The selected candidate is **Hay River / K'atl'odeeche (SS005-23), 14–20 May 2023**. It is
independent of Dogrib, uses Canadian FBP fuels, and has a public hourly weather stream, a
public satellite-derived daily progression and final perimeter, a public ignition location, and
a public fuel dataset.

The gate is a **conditional pass**: the data sources exist and are identified, but P161.2 must
acquire and subset the 2023 FBP fuel dataset and the ASTER terrain tile before the fixture is
valid. If either acquisition fails, P161 closes as a no-go.

## 2. Gate checklist

| Field | Candidate value | Status |
| --- | --- | --- |
| Fire identity | SS005-23 / Hay River / K'atl'odeeche, NWT, 2023 | pass |
| Independence | Different fire, year, region, and fuel/weather stream from Dogrib | pass |
| Observed perimeter | CFSDS `2023_320_krig.tif`, 90 m, final day-of-burning 140 (20 May 2023); 2,770.2 ha | pass with caveat |
| Progression | CFSDS day-of-burning 134–140 (14–20 May 2023) | pass |
| Hourly weather | ECCC Hay River A, climate ID 2202401, hourly May 2023 | pass |
| Ignition | First CFSDS burned centroid near 60.8416 N, 115.7022 W; satellite-inferred, not an official ignition report | pass with caveat |
| Fuel | FireSTARR Fuel 2023 V1.0, FBP 100 m, public index with SHA-256 | pass with acquisition |
| Terrain | ASTER GDEM V003, 30 m, public | pass with acquisition |
| CRS / time zone | CFSDS Lambert Conformal Conic; weather local standard time; reproject to a local metric grid | pass |
| Event duration | 14–20 May 2023, seven daily growth days | pass |
| Licence | CFSDS public OSF, no explicit licence; ECCC open data; FireSTARR fuel index public, no explicit licence; ASTER public | caveat |

## 3. Sources

### 3.1 Perimeter and progression

Canadian Fire Spread Dataset (CFSDS), v1.1, OSF `f48ry`:

- `Firegrowth_groups_v1_1_2023.csv`
- `2023_fireDOYrasters.zip` → `2023_320_krig.tif`
- Raster: 67 × 92 cells, 90 m, Lambert Conformal Conic, NAD83; burned cells 3,420,
  area 2,770.2 ha; day-of-burning 134–140.

The CFSDS final perimeter is satellite-derived and ends on 20 May 2023. A NWT map dated
22 May 2023 reports 3,208.9 ha. P161.2 must state which perimeter is the comparison target; the
default is the CFSDS raster because it is georeferenced and reproducible. The 14 % difference
is an accepted limitation, not a calibration target.

### 3.2 Weather

ECCC station **HAY RIVER A**, climate ID `2202401`, hourly May 2023. The hourly record covers
the event window and includes temperature, relative humidity, wind speed/direction, and
precipitation. The event-day FWI starting codes must be derived and recorded; they are not
assumed from Dogrib.

### 3.3 Fuel and terrain

- FireSTARR Fuel 2023 V1.0: `FireSTARR_Fuel_2023_V1.0.zip`, 2,832,256,903 bytes,
  SHA-256 `3a1c18b85592358ae1031884947dba0640a2703947dcdfd8b637caa02dd40acc`.
  Public index: `https://fgmfiles.spyd.com/datasets/nomad/index.json`.
- ASTER GDEM V003 for the fire footprint, 30 m.

The fuel zip is large and must be subset to the fire tile; it is not committed. Its index has no
explicit licence, so P161.2 treats it as validation data with attribution and no redistribution.

### 3.4 Ignition

The first burned CFSDS centroid is near 60.8416 N, 115.7022 W. This is a satellite-inferred
start, not an official ignition report. P161.2 records it explicitly as an inference. The
candidate uses point ignition; there is no public 14 May start perimeter.

## 4. Rejected candidates

| Candidate | Reason |
| --- | --- |
| Dogrib (RWF085) | Already used in P157/P160; not independent. |
| Horse River 2016, Alberta | Perimeter and hourly weather are public, but the analytic FBP fuel raster requires a token and the public service exposes only a preview image; large WUI/suppression case. Reserve only if a licensed FBP raster is found. |
| WildfireAV / MTBS cases | US LANDFIRE FBFM40 fuels, not Canadian FBP; the current growth path is FBP. |
| Project Nomad Hay River June 2023 run | Real hourly weather and ignition, but the public CFSDS perimeter covers the May growth, not the June run; no matching June perimeter. |
| CFSDS-only alternatives | Daily weather and SCANFI attributes, but no hourly stream and no FBP fuel map without a crosswalk. |

## 5. Risks carried into P161.2

- The CFSDS perimeter is satellite-derived and 14 % smaller than the 22 May agency map.
- The ignition is inferred from the first burned pixel.
- The fuel dataset is 2.8 GB and licence status is unclear; only a subset may be used.
- There is no start perimeter and no suppression, so this is a point-ignition final-perimeter
  case, like the FireSTARR comparison but with Canadian FBP fuels.
- One fire is still not a regional calibration; the result will be a two-case transfer test.

## 6. Next step

P161.2 acquires the CFSDS raster and ECCC weather, subsets the 2023 FBP fuel tile, obtains the
ASTER terrain tile, and builds the second-fire fixture. If the fuel or terrain subset cannot be
produced, close P161 as a data-gate no-go before writing calibration code.
