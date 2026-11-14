# Small spatial Biomass_core reference

Status: implemented (P200)
Phase: P200 (#1180)
Date: 2026-11-14
Related: `notes/design/ws4-landis-r-parity.md`,
`scripts/landis_spatial_reference.R`

## 1. Purpose

P199 proved kernel parity against the published R functions. P200 runs the full Biomass_core
module on a tiny spatial landscape and captures its trajectory. This is the first spatial
reference, not a regional LBSE reproduction.

## 2. Case

- 10 × 10 raster at 100 m, 100 pixels;
- one ecoregion;
- two species, `Pice_Gla` and `Popu_Tre`;
- two pixel groups with two cohorts each;
- 10-year horizon, 10-year succession timestep;
- fixed R seed `20261114`.

The run uses hand-built deterministic inputs. It does not download species layers or use a
real study area.

## 3. Command

```bash
WS4_R_LIB=<isolated-library> \
BIOMASS_CORE_DIR=<directory-containing-Biomass_core> \
P200_OUT=<output-directory> \
Rscript --vanilla scripts/landis_spatial_reference.R
```

The script writes `simulationOutput.csv` and `sessionInfo.txt`.

## 4. Captured trajectory

| Year | N pixels | Biomass | ANPP | Mortality | Regeneration |
| --- | --- | --- | --- | --- | --- |
| 0 | 100 | 2000 | 0 | 0 | 0 |
| 0 | 100 | 2694 | 762 | 66 | 0 |
| 10 | 100 | 9460 | 920 | 294 | 2 |

Two independent runs with the fixed seed produced byte-identical CSV output.

## 5. Runtime

- R 4.3.3
- LandR 1.2.0.9064
- SpaDES.core 3.2.1.9067
- SpaDES.tools 2.2.0
- reproducible 3.2.1.9087
- Biomass_core commit `21b3392324c2787a47751be808cbf9e595f308c0`

The optional `LandR.CS` package was absent; the module warned and completed.

## 6. Limits

- Toy landscape and hand-built inputs, not a real forest.
- No downloaded species layers, climate modifiers, fire, insects, or management.
- No WS4-vs-reference trajectory comparison yet.
- The output is a reference fact, not an observed-data validation.
