# P230 close-out: shared-schedule process/estate comparison

Date: 2026-11-15
Phase: P230 (#1313)
Branch: `feature/p230-shared-schedule`
Tasks: P230.1 (#1314), P230.2 (#1315)
Design note: `notes/design/ws4-shared-schedule.md`
Report: `notes/reports/p230-shared-schedule.md`

## Result

The same CC schedule now runs through both the estate simulator and the process engine and reports
the same final volume: **340 m3**.

## What changed

- `tests/test_process_estate_shared_schedule.py`.
- Same schedule through the synthetic estate fixture and the process management bridge.
- P223 comparison reports absolute difference 0.
- Design note and report.

## Evidence

- Shared-schedule test: 1 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Estate `feature.Volume`: 340.
- Process `bridge.volume_m3`: 340.
- Comparison absolute difference: 0.

## Boundary

Synthetic fixture and provisional linear bridge. No fire, succession, regeneration, or real yield
curves in this comparison. Not an observed-data validation.

## Next

Replace the linear bridge with real yield curves and run on a compiled dataset with an ecosystem
package.

## Pull request

PR: #TBD is queued for maintainer approval. Do not merge without approval.
