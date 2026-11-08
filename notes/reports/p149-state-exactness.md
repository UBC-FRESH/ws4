# P149 state-run exactness

Date: 2026-11-07
Completed: 2026-11-08
Status: complete
Branch: `feature/p149-state-exactness`
Parent issue: #873
Task issues: #874, #883
Merge commits: `2997ea2`, `c745d8b`

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
- Live web run `web-20261108-001933-150`: status `done`, `exact_match: true`,
  objective `8549054.131123843`, verified objective `8549054.13112384`,
  compact `state-watch.json` 358 bytes, and run health showed `exact replay yes`.
