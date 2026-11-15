# Five-year harvest and track-change gap

Status: implemented (P236)
Phase: P236 (#1344)
Date: 2026-11-15
Related: `notes/design/ws4-succession-offset.md`,
`notes/design/ws4-compiled-curves.md`

## 1. Purpose

P230 compared a single-year clearcut. P235 compared five years without harvest. P236 combines
them: five estate years with a CC at offset 2.

## 2. Result

Estate final offset 4, after CC at offset 2:

- fragment 2 natural age 64: 2 × 180 = 360;
- fragment 1 managed age 2: 3 × 10 = 30;
- total **390 m3**.

Process final:

- four transitions: **360 m3**, difference **-30** (-7.69%);
- five transitions: **365 m3**, difference **-25** (-6.41%).

## 3. Why

The process bridge has no track state. It applies the compiled natural curve 2 to every `PL`
cohort. After harvest, the estate moves block 1 to the managed curve 3, whose age-2 value is 10
m3/ha. The process uses the natural curve and keeps the bare cohort at age 0, so block 1
contributes zero.

The five-transition case adds the one-step offset from P235: fragment 2 is age 65, not 64.

## 4. Evidence

- `tests/test_landis_harvest_track.py`: 1 passed.
- Exact estate 390, four-transition 360, five-transition 365.
- Differences -30 and -25.

## 5. Limits

- No track-change state in the process bridge.
- Single species and one natural curve.
- No fire or regeneration.
- This is a diagnostic mismatch, not a fix.
