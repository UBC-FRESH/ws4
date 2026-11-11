# P170 close-out: reanalysis weather consistency

Date: 2026-11-11
Phase: P170 (#1011)
Branch: `feature/p170-fwi-consistency`
Pull request: #1015

## Outcome

Compared Open-Meteo-derived daily FFMC, BUI, and ISI with CFSDS daily fields for all six
reanalysis cases.

## Result

- median absolute FFMC delta: 0.77;
- median absolute BUI delta: 11.62;
- median absolute ISI delta: 0.88;
- reanalysis ISI higher on 56 of 68 days;
- maximum absolute ISI delta: 7.90.

FFMC and ISI are close enough that weather is not the primary cause of the 10–14x area bias.
BUI is systematically higher, but BUI is not the dominant ROS driver in FBP.

## Decision

Do not replace the weather source yet. The next test is containment/stopping or an event-timing
correction. No calibration was applied. P164.3 remains paused.

## Limits

- CFSDS FWI fields are daily summaries.
- The diagnostic uses a fixed 13:00 sample and previous-24h precipitation.
- BUI differences may still affect fuel consumption and crown behaviour.
- Six cases, one fuel/terrain tile.

## Verification

- Dashboard: GREEN.
- FWI diagnostic test green.
- No merge without maintainer approval.
