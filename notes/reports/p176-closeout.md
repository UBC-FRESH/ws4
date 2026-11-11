# P176 close-out: burnable basin and stopping

Date: 2026-11-11
Phase: P176 (#1041)
Branch: `feature/p176-burnable-basin`
Pull request: #1045

## Outcome

Computed burnable-basin fractions for 12 small, large, and fine cases.

## Result

- median simulated area / burnable basin: 0.995;
- median observed area / burnable basin: 0.130;
- 8 of 12 simulations fill at least 95% of the basin;
- all 12 observed fires burn less than 50% of the basin.

The model is **basin-limited**, not weather/fuel/terrain-limited.

## Decision

P176 is complete. Implement containment/stopping or a defensible burnable-area constraint.
Do not apply a global multiplier. P164.3 remains paused.

## Limits

- Burnable area comes from the FireSTARR fuel map.
- Twelve cases across three grid scales.
- Reanalysis weather and daily perimeters.
- Some fire edges may be non-fuel or unburnable in reality but not in the map.

## Verification

- Dashboard: GREEN.
- Basin diagnostic test green.
- No merge without maintainer approval.
