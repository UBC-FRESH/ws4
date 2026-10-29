# Phase close-out report: P81 Seed schedules from the UI

Phase: P81, Seed schedules from the UI
Parent issue: #570
Pull request: #572, `feature/p81-ui-seed` into `main`
Evidence head: pending CI
Date: 2026-10-29
Status: queued for approval. Not merged.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| `serve` accepts `--initial-schedule`. | CLI option and `create_app` parameter added. | Met |
| UI-started optimize includes it. | The c5 test service process command included `--initial-schedule .../seed_200y.csv`. | Met |
| A Solve from c5 uses the seed. | API-started run process inspection confirmed the flag. | Met |
| No-seed services are unchanged. | Optional parameter defaults to None; command omits it. | Met |
| Dashboard green. | All seven gates green. | Met |

The service now passes the configured seed to every UI-started optimize command. The c5 base
scenario uses `seed_200y.csv`, `flow_reference_period: 1`, and ±5% even flow; the final stock
target remains a soft goal-programming target.

## Limits

- The UI does not expose a seed picker; the service config owns it.
- Max-flow still needs a seeded probe implementation.
