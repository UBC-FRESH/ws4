# Harvest, track change, and annual ordering

Date: 2026-11-15
Related: `notes/design/ws4-succession-offset.md`,
`notes/design/ws4-compiled-curves.md`

## Purpose

A clearcut moves a block from its natural track to a managed track. The process side must carry
that track identity, use the compiled managed curve after harvest, and apply the treatment at the
same point in the year as the estate simulator.

## Implemented state

- Cohorts may carry an optional `track_id`.
- `ScheduleSource` accepts compiled `(source_track, treatment)` to target-track transitions and
  writes the target track on newly created cohorts. Survivors keep their source track.
- The volume bridge prefers a track's compiled age curve and falls back to the species curve.
- The canonical event phases put `treatment` before `growth`, matching the estate's
  treatment-then-age order. Age-zero recruits age on the next succession transition.

## Evidence

With the synthetic five-year CC at offset 2:

| Case | Estate | Process | Difference |
| --- | --- | --- | --- |
| four transitions | 390 | 390 | 0 |
| five transitions | 390 | 410 | +20 |

Four process transitions match the five-year estate final offset. Five transitions carry both the
natural and managed cohorts one annual step ahead, which is the known offset convention from P235.

## Limits

- The compiled treatment and feature tables are supplied by the caller; the process evaluator
  does not read them from a dataset directory itself.
- Single species in this test. Track curves are already keyed independently of species.
- Fire and regeneration are disabled in the comparison so the harvest signal is isolated.
