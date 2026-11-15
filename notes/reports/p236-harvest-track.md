# Five-year harvest and track change

Date: 2026-11-15
Design: `notes/design/ws4-harvest-track.md`

## Result

The process engine now matches the estate after a timed clearcut that changes the block from its
natural track to its managed track.

| Case | Estate | Process | Difference |
| --- | --- | --- | --- |
| four transitions | 390 | 390 | 0 |
| five transitions | 390 | 410 | +20 |

The managed age-2 cohort contributes 30 m3 (3 ha x 10 m3/ha). The natural cohort contributes
360 m3 (2 ha x 180 m3/ha).

## Evidence

- `tests/test_landis_harvest_track.py`: one test, both cases.
- `tests/test_ecosystem_bridge.py`: track-curve override, serialization, validation, loader.
- `tests/test_ecosystem_management.py`: survivor/recruit track split and transition validation.
- `tests/test_ecosystem_state.py`: optional `track_id` preservation and validation.

## Boundary

The caller builds the track curves and treatment transitions from the compiled feature and
treatment tables. The evaluator does not load a dataset directory by itself. Fire and regeneration
are disabled in this comparison.
