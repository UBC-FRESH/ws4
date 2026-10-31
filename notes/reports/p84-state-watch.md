# P84: Resident Model II state watcher (c5 acceptance)

Date: 2026-10-31
Issue: #613

## Result

WS4 now has a c5-only resident-state watcher:

- compact candidate index (`.npz`) loaded instead of regenerating the candidate graph;
- track/age feature arrays built once;
- `state[period, block, account]` resident pages;
- product accounts kept as treatment-event rows;
- feature and product accounts are never summed together;
- the chart reads the period totals;
- SA starts from a blank schedule;
- final objective is checked against a fresh `IncrementalObjective`.

c5 sample:

| Step | Result |
|---|---:|
| Baseline `watch --iterations 1 --plain` | 6.03 s |
| `state-watch --iterations 50 --plain` | 6.44 s |
| State build | ~2.0 s |
| 50 blank-SA iterations | ~0.28 s |
| State objective, 50 iterations | 2,446,968,145.4810195 |
| Fresh exact objective | 2,446,968,145.481019 |
| Blocks | 12,567 |

The state watcher is exact on the tested c5 schedule, but it is **not yet faster** than
the existing baseline. It proves the resident-page architecture and exposes the remaining
costs: track trajectory construction, state initialization, and the final exact check.

## What changed

- `ws4/opt/model2_index.py`: compact candidate index with `.npz` round-trip.
- `ws4/opt/model2_trajectory.py`: track trajectory, splice timeline, resident pages,
  state objective, blank SA, and state watcher.
- `ws4 state-watch`: CLI path for the resident-state watcher.

## Limits

- c5 sample only; no TSA24/29 acceptance run.
- The live TUI path uses the same state projection but the benchmark above is `--plain`.
- This phase does not yet replace the production CPU watcher or optimize the remaining
  startup costs.
