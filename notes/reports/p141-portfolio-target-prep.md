# P141 portfolio target preparation

Date: 2026-11-06
Status: pr-open
PR: #845
Branch: `feature/p141-portfolio-target-prep`
Parent issue: #843
Task issue: #844

## Summary

Live TSA27 portfolio scans exposed a target-preparation problem: the live target file has
an even-flow row, and a search from an empty schedule cannot satisfy it. Every member can
finish with zero blocks and an infinite objective.

The Search launcher now prepares a safe target set per portfolio run:

- `level_only` writes a flow-free target file inside the run output directory and passes
  that file to the portfolio script;
- `use_initial_schedule` forwards the instance's configured seed schedule;
- the CLI accepts `--initial-schedule`;
- the UI defaults to level-only targets with a visible explanation.

The live target file itself is never mutated.

## Verification

- API tests assert the level-only target file and path.
- API tests assert a configured initial schedule is forwarded.
- A service without an initial schedule rejects the request with 422.
- CLI test covers `--initial-schedule` wiring.
- `python scripts/dashboard.py`: `OVERALL: GREEN. Every gate passed.`

## Limits

- Level-only removes flow targets from the scan; it is not a substitute for flow-aware
  planning.
- Arbitrary target-file paths remain unavailable through the web API.
