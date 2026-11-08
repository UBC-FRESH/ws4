# P149 state-run exactness

Date: 2026-11-07
Status: active
Branch: `fix/p149-summary-trim`
Parent issue: #873
Task issues: #874, #883

## Summary

`ws4 state-watch` already compares the state objective with an exact
`IncrementalObjective` replay, but the web state runner discarded the result.

The CLI now accepts `--summary-out` and writes objective, verified objective, exact
flag, iterations, evaluations, blocks, elapsed, and the schedule path. The web state
runner persists that payload in `state_search.json` and `summary.json`; run health
shows an exact-replay badge only when the flag is a boolean.

## Verification

- A live TSA 27 state run finished in 30.2 seconds with objective
  `8505284.61515741`, verified objective `8505284.61515741`, and `exact_match: true`.
- The first payload embedded the full schedule mapping, producing a 147 KiB
  `state-watch.json`; P149.2 replaces it with the output path, and a focused browser
  test covers the badge.
- `tests/test_pareto_browser.py`: 4 passed.

Dashboard: `OVERALL: GREEN`.
