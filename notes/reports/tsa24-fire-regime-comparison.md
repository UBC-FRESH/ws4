# TSA24 historical fire-regime comparison

Date: 2026-11-17
Related: `docs/reference/fire-regime.rst`, `notes/design/ws4-fire-regime-benchmarks.md`,
`notes/design/ws4-process-fire-regime.md`

## Source

Historical perimeters: BC Data Catalogue, **Fire Perimeters - Historical**, dataset
`22c7cb44-1463-48f7-8e47-88857f207702`, accessed through the BC Wildfire feature service.
TSA24 boundary: BC Data Catalogue, **FADM - Timber Supply Areas (TSA)**
(`dab3daa4-d502-4b95-b39e-5f746a1041ed`), TSA number 24, Prince George TSA.

Both layers are published under the Open Government Licence - British Columbia. The raw
perimeters are not copied into this repository; this note records the derived comparison only.

## Method

- Query historical perimeters intersecting the Prince George TSA envelope in EPSG:3005.
- Clip each perimeter to the TSA polygon and keep intersections larger than 0.01 ha.
- Use 1950-2024: **1,078 fires**, **757,988 ha** burned, 75 years.
- Historical target: 14.37 fires/year and 10,106 ha/year over the 5,899,680 ha modeled area.
- Simulated run: 458,419 fragments, 942,587 species cohorts, 116,194-block first-five-year
  schedule, five process years, fire 0.01 per fragment-year, regeneration 0.25.
- Model fire count: 18,502; burned area: 240,678 ha.

## Result

| Diagnostic | Historical target | Simulated |
| --- | ---: | ---: |
| Ignitions per year | 14.37 | 3,700.4 |
| Escaped fires per year | 13.33 | 3,606.8 |
| Mean escaped fire size | 757.97 ha | 13.33 ha |
| Median fire size | 27.39 ha (escaped) | 7.9 ha (all) |
| Annual burn rate | 0.00171 | 0.00816 |
| Fire return interval | 583.75 years | 122.72 years |

The model produces roughly **257 times** as many fires per year, with a mean escaped fire
about **57 times smaller**, and burns about **4.8 times** the historical area per year.

## Interpretation

This is a calibration gap, not a runtime failure. The model's `0.01` ignitions per
fragment-year is not derived from the TSA24 record. The historical perimeter layer also
under-represents small fires, so the ignition-count comparison is an upper bound on the
mismatch; the burned-area and fire-size comparisons are more robust.

The result separates three claims:

- **Distributional benchmark:** the scfm formulas and diagnostics run correctly.
- **Observed-fire comparison:** the simulated regime is much more frequent and much smaller
  than the TSA24 perimeter record.
- **Model-to-model validation:** still separate; no LANDIS or LandR fire-regime run is used here.

## Topology and calibration pilot

The 3,700 fires/year figure comes from the no-topology run. A connected block graph changes
the result qualitatively. On a 10,000-block subset with a k-nearest-neighbour graph
(8 neighbours, 5 km maximum), 50 seeds, and no harvest or regeneration:

| Parameters | Fires/year | Burn rate | Mean size | Median size |
| --- | ---: | ---: | ---: | ---: |
| ign 4e-5, spread 1.0, scale 2750 m | 0.38 | 0.00160 | 534 ha | 188 ha |
| target scaled to the subset | 0.31 | 0.00171 | 758 ha | 27 ha |
| ign 1e-4, spread 1.0, scale 2500 m | 0.88 | 0.00187 | 272 ha | 100 ha |

The best candidate matches the scaled ignition count and annual burn rate within about 25%,
but the size distribution is still too coarse: too few small fires and too few very large
ones.

## Full kNN topology attempt

The full TSA24 k-nearest-neighbour graph with 8 neighbours and a 5 km maximum contains
**2,111,955 edges**. One full-estate run with ign 4e-5, spread 1.0 and scale 2750 m burned
**5.29 million ha** in five years. The block graph is close to a spanning cluster, so that
candidate is far too connected at estate scale.

An all-pairs 5 km topology was abandoned: 200,000 blocks produced 94 million edges and a
2.6 GB partial file.

## Near-critical instability

A spatially contiguous 50,000-block subset (684,553 ha, 229,308 kNN edges) was used to test
the transition. The fire size is not smoothly controllable:

- spread 0.48: one fire, 118 ha
- spread 0.49: one fire, 1,242 ha
- spread 0.52, one seed: 1,255 ha
- spread 0.52, 50 seeds: 272 fires, mean 39,251 ha, burn rate 0.0624

The homogeneous kNN graph has a sharp percolation threshold. Below it, fires stay small;
above it, a single ignition can burn most of the connected subset. There is no stable
parameter pair in this graph that matches both the historical mean size and annual burn rate.

This is a structural result: ignition rate and spread probability alone cannot calibrate the
block-only graph to the TSA24 distribution. Spatial heterogeneity, fuel/weather variation, or
a different spread closure is required.

## Next

Do not tune further on the homogeneous block graph. The next model change is a heterogeneous
spread surface: fuel/weather classes or a raster support between blocks. The full TSA24 kNN
graph and 50-seed results are recorded above as the evidence for that decision.
