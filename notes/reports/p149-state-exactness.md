# P149 state-run exactness

Date: 2026-11-07
Status: active
Branch: `feature/p149-state-exactness`
Parent issue: #873
Task issue: #874

## Summary

`ws4 state-watch` already compares the state objective with an exact
`IncrementalObjective` replay, but the web state runner discarded the result.

The CLI now accepts `--summary-out` and writes objective, verified objective, exact
flag, iterations, evaluations, blocks, and elapsed. The web state runner will persist
that payload in `state_search.json` and `summary.json`; run health shows an exact-replay
badge.

## Verification

- CLI summary wiring and live state replay pending.
