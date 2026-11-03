# P126 playback control and cadence

Date: 2026-11-03
Status: complete; PR #788

## Change

- Wrapped the period slider and Play/Pause button in a fixed-width `.period-control`.
- Gave the status its own flex slot and fixed the Play/Pause button width, so the
  button no longer moves horizontally as status text changes.
- Reduced the playback settle delay from 900 ms to 500 ms while retaining the
  serialized map-load guard.

## Verification

- Browser smoke: the Play/Pause button kept the same x/y for the full run.
- Periods advanced at roughly one per 1.2 s.
- Rapid paging still ended on the last requested period.
