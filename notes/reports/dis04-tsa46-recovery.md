# DIS-04 TSA 46 post-fire recovery pilot

Date: 2026-10-27
Candidate: DIS-04
Scope: ingest one published post-fire recovery layer and attach recovery status
to a pilot block set. No new recovery model, no objective change.

## Source

- Canada Forest Post-Disturbance Recovery Rate, fire layer.
- NTEMS / Natural Resources Canada, 30 m, EPSG:3978.
- Wildfire disturbance 1986-2012; observation 1985-2017.
- Classes: 1 faster than baseline, 2 slower, 3 not recovered by 2017.
- Licence: Open Government Licence - Canada.
- Citation: White et al. 2022, Remote Sensing of Environment 271, 112904.

## Implementation

- `ws4/recovery.py`: source metadata, block sampling, status fractions,
  dominant status, and summary.
- `ws4 recovery ingest` writes `regen_status.csv`, `recovery_metadata.json`, and
  an optional summary.
- Blocks with no class 1-3 pixels are `outside_footprint`, not failures.
- Tests cover fractions, outside-footprint handling, source version, and summary.
- Example: `examples/recovery_tsa46/` with a real 5 km TSA 46 subset.

## Pilot result

- 33 VRI blocks, 19,806 ha.
- 31 blocks with recovery pixels; 2 outside the footprint.
- **31/31 recovered-footprint blocks are dominated by `not_recovered`**.
- Burned recovery area: **5,224 ha**.
- Only 13 class-2 pixels in the subset; no block is dominated by slower recovery.
- No block is dominated by faster recovery.

## Interpretation and limits

- The product is a Landsat spectral recovery metric, not tree survival or
  stocking. It is not a regeneration survey.
- The observation window ends in 2017; recovery may continue.
- A block outside the fire footprint is not a failure.
- This is a 5 km TSA46 pilot, not a provincial failure map.
- The status is read-only and does not enter the objective.

## Verification

- `python -m pytest tests/test_recovery.py -q --no-cov` -> 4 passed.
- Full dashboard -> GREEN (tests 130.22 s).
