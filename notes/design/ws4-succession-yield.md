# Succession, regeneration, and the yield bridge

Status: implemented (P180)
Phase: P180 (#1062)
Date: 2026-11-12
Related: `notes/design/ws4-stochastic-landscape.md`,
`notes/design/ws4-process-executor.md`, `ws4/ecosystem/succession.py`,
`ws4/ecosystem/regeneration.py`, `ws4/ecosystem/bridge.py`

## 1. Scope

P180 adds the first living ecological processes to the P179 executor and a provisional
species-biomass-to-volume bridge. It is deliberately not a full LANDIS-II or SpaDES clone.

The state remains the P144 cohort/fraction model. The compiled management dataset remains
authoritative. The bridge is a versioned view, not a replacement for the yield curves.

## 2. Succession

`SuccessionProcess` runs in the `growth` phase and emits one event per covered fragment.
Applying the event:

- increments every cohort age by one year;
- grows live biomass toward a species maximum with a logistic rate;
- accumulates fuel to at least `biomass × fuel_fraction`;
- decays snags by `snag_decay_rate`.

Parameters are explicit in `SpeciesGrowth` and `SuccessionConfig`. The defaults are
provisional planning values, not calibrated to observed stands.

## 3. Regeneration

`RegenerationProcess` runs in the `regeneration` phase. It finds juvenile cohorts
(`age <= max_regeneration_age` and biomass at or below a ceiling) and draws establishment from
the scenario random tape with key `(process, fragment, year, 0)`.

On establishment it raises juvenile biomass and fuel to declared minimums. It does not change
area fractions; the cohort already occupies the disturbed area. The process is stochastic but
replayable and uses common random numbers.

## 4. Yield bridge

`SpeciesVolumeBridge` maps cohort biomass to merchantable volume:

```text
volume_m3 = biomass_t_ha × area_fraction × fragment_area_ha
            × volume_m3_per_t[species] × merchantable_fraction
```

It returns a fragment table with `volume_m3_ha` and `volume_m3`, and can attach those columns
to a management frame keyed by `fragment_id`.

The parameter table records `schema_version`, species rates, the default rate, the
merchantable fraction, `calibration_status`, and `calibration_source`. The default status is
`provisional`: the coefficients are not fitted to observed data, and the compiled dataset's
yield curves remain the management authority.

## 5. Integration

The P179 executor runs fire, salvage, succession, and regeneration in one year. Phase ordering
is canonical; the bridge runs after the state transition as an observer/view.

## 6. Validation

- Succession ages cohorts, grows biomass, respects the biomass ceiling, and preserves area.
- Regeneration is reproducible, probability-sensitive, and skips mature cohorts.
- The bridge arithmetic is checked against known area and biomass.
- The integration test runs fire, succession, salvage, regeneration, and the bridge on one
  state and checks area conservation and non-negative volume.
- Replay tokens are equal for identical runs.

## 7. Limits

- The parameters are provisional; there is no observed ecological calibration.
- Regeneration is a single-cohort establishment rule, not species competition.
- Succession has no disturbance interactions beyond fire mortality.
- The bridge does not replace or modify the compiled yield curves.
- The processes are annual and fragment-level.
