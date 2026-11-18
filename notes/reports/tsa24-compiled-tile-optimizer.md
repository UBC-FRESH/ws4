# TSA24 compiled tile: growth fire through the canonical dataset optimizer

This run replaces the hand-built cohort frame with a canonical compiled dataset. It is the
first time the calibrated FBP growth fire drives the actual `ProcessDataset` evaluator and
optimizer.

## Dataset

The 30 km real-layer tile was compiled into a canonical dataset:

- 11,203 fragments, one per burnable 250 m cell
- 6.25 ha per fragment
- VRI projected age per fragment (range 2-265 years, mean 77.3; 3,534 fragments aged 40-100)
- one natural stratum and the sample-estate volume, treatment, and transition curves
- recipe treatment window extended to age 1,000 so older VRI stands remain selectable

Compilation took 0.2 s and `ProcessDataset` loading took 1.6 s. Every raster fragment id maps
directly to the compiled `fragment_id`; no fragment is missing from the raster.

## Growth fire

The growth source is the same real-layer FBP run used in the fire-regime pilot:

- real VRI fuel, crown closure, conifer fraction
- real SRTM slope, aspect, elevation
- VRI water-edge wetting
- FFMC 93.8, BUI 108.2, wind 6.8 km/h at 270 degrees
- 240 minutes

It reached 169 fragments (1,056.25 ha). Thirty-two burned fragments had an age inside the
40-100 treatment window. Eight of those blocks formed the optimizer grammar.

## Evaluation and optimizer

The baseline three-year schedule harvested the eight blocks (50 ha) at offset 1:

| Account | Baseline |
| --- | ---: |
| `bridge.volume_m3` | 12,051,520 |
| `state.biomass_t` | 3,348,740 |
| `harvest.area_ha_total` | 50.0 |
| `fire.burned_area_ha_total` | 1,056.25 |
| `fire.count_total` | 169 |

`ProcessDataset.optimize` used the same growth source and a 50 ha harvest target. It completed
eight strict-improvement rounds and reached objective `0.0`:

- harvested area: 50.0 ha
- final volume: 12,051,470 m3
- final biomass: 3,348,964 t
- burned area: 1,056.25 ha
- fire events: 169

The optimizer selected a mix of offsets 0, 1, and 2 because the compiled age window made those
treatments legal.

## Risk ensemble

Five scenarios varied the ignition cell and weather (FFMC 90.8-94.0, BUI 103-115, wind
5.2-10.0 km/h). Each built its own growth source and ran the compiled dataset for three years.

| Scenario | Fire (ha) | Final volume (m3) |
| --- | ---: | ---: |
| 1 | 193.8 | 12,171,125.0 |
| 2 | 6.2 | 12,189,106.2 |
| 3 | 631.2 | 12,122,681.2 |
| 4 | 556.2 | 12,130,425.0 |
| 5 | 1,206.2 | 12,025,569.6 |

The 90% lower-tail CVaR of final volume was 12,025,569.6 m3.

## Boundary

The tile dataset is a canonical compile, but it is still a 30 km pilot, not the full TSA24
estate. Species is the fallback `PL`; VRI species composition, topology edges, and calibrated
volume curves are not included. The optimizer covers eight burned-adjacent blocks, not the
whole tile. The risk ensemble has five scenarios and no suppression model.
