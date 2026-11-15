# P235 report: five-year succession offset

Date: 2026-11-15
Phase: P235 (#1340)
Branch: `feature/p235-succession-offset`
Design note: `notes/design/ws4-succession-offset.md`

## Result

Four process transitions match the five-year estate final offset. Five transitions are one annual
step ahead.

## Evidence

- Test: 1 passed.
- Four transitions: estate 750, process 750, difference 0.
- Five transitions: estate 750, process 762.5, difference +12.5 (1.667%).
- Full dashboard: **OVERALL: GREEN**.

## Boundary

No fire, harvest, or regeneration. Single species and one compiled curve. This is an offset
convention finding, not calibration.

## Next

Use four transitions per five estate accounting years in future comparisons, or change the
process API to accept an explicit final offset.
