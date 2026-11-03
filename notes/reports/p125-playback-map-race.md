# P125 period playback and map race fix

Date: 2026-11-03
Status: complete

## Root cause

Period playback and manual paging both started asynchronous map loads. A later
period could start while an earlier request was still in flight, and an older
response could paint after a newer one. The first Play implementation also used
a fixed interval that started another period without waiting for the current
map load to settle.

## Change

- Added a monotonic `mapLoadSequence` guard. Every async map response checks its
  request generation before mutating map features, counts, or status.
- Playback ticks are serialized with `periodPlayBusy`: no next period starts
  while a map request or settle delay is active.
- Each playback period gets a 900 ms settle interval after its map load.
- The full-screen loading overlay is suppressed during playback so periods do
  not flash an overlay between frames.

## Data check

The apparent “same blocks every period” report was checked against the actual
GPU schedules and map tiles:

- TSA27 period 1 tile: 322 treated blocks.
- TSA27 period 2 tile: 361 treated blocks.
- Shared block ids: **0**.
- Adjacent-period overlap across TSA24, TSA27, and TSA29 GPU schedules: **0**.

The schedule is not reusing the same blocks every decade.
