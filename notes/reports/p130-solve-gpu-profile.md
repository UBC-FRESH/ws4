# P130 Solve through the GPU profile path

Date: 2026-11-03
Status: complete

## Change

When a GPU scenario profile is available, the primary Solve action now routes
through the profile worker with the current edited targets and the configured
wall-clock budget. Run profile remains an alternate entry point to the same
current-target GPU path.

The profile bar hint now states this behavior.

## Verification

- TSA27 Solve with a chart edit to 400,000 and `00:00:02`:
  - run kind `gpu-profile`
  - target cache path used
  - stopped after 701 generations
  - exact replay `true`
- Dashboard and focused tests pass.
