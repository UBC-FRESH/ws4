# Live target-window watcher (`ws4 watch`)

Status: **in progress**. Branch `feature/p6-watch`, off P6 head `b725be6`. Checkpoint tag
`p6-watch-checkpoint` for one-command rollback. Issue: #77.

Related: `notes/design/ws4-optimization-stack.md`, `docs/reference/optimizer.rst`.

## 1. Motivation

The reference tool draws a **target chart** for each target account: time along one axis, the
account's units along the other, one bar per period. Each period shows the **minimum** and
**maximum** target levels (a band) and the **realized** account value as a black line; the bands
are coloured where the realized value falls outside the window (red below the minimum, blue above
the maximum). A small readout prints the exact minimum, realized, and maximum at the hovered
period.

WS4 records the objective trajectory to `telemetry.jsonl`, but there is no way to *watch* the
account values themselves as the search runs. This task adds one: a terminal view of the realized
target-window over periods, repainted in place as the heuristic minimizes the summed penalty.

## 2. Goal

`ws4 watch` runs the same metaheuristic and objective as `ws4 optimize`, and paints, in place:

- a header: watched account(s), iteration, best objective, iteration rate, elapsed, temperature;
- a target-window chart: one column per period, the min/max band shaded, the realized value drawn
  as a bar, coloured by status (ok / below minimum / above maximum);
- a period table: window, realized, shortfall, excess, status.

A `--plain` mode prints one static frame (for logs and tests).

## 3. Design

Our `Target` is per-year; the reference chart is per-period. The view therefore aggregates:

- **realized per period** — sum the watched account(s) over the years of the period;
- **window per period** — the sum of the per-year target minima (and maxima) over the period.

The objective the solver minimizes is unchanged (the summed per-year penalty); the header shows it,
and the period table shows the same quantity grouped by period.

To paint the *incumbent* (not the last rejected move), the optimizer exposes the account values of
its most recent evaluation (`Optimizer.last_account_values`). The watcher wraps the problem's
`evaluate`, and whenever a new best objective appears, keeps that evaluation's values.

Units: `ws4/opt/watch.py` (pure aggregation, band, penalty, and rendering functions) and a `watch`
command in `ws4/cli.py`. No change to solver behaviour.

## 4. Correctness plan

- Unit tests for period aggregation, window assembly, per-period penalty, and the chart cell logic.
- An integration test runs the command with `--plain`, a two-iteration budget, and the synthetic
  fixture, asserting it prints the account name and a frame.
- The optimizer change is covered by a test that `last_account_values` returns the values of the
  evaluation.

## 5. Risks

| Risk | Mitigation |
| --- | --- |
| Rendering slows the search | Repaint on a time budget, not every iteration |
| A live TUI breaks pipes/CI | `--plain` mode; live only when the stream is a terminal |
| Period window misread as the objective | Header shows the true objective; the table labels the period grouping |

## 6. Milestones

- **M1** `last_account_values`; aggregation/band/penalty functions with unit tests.
- **M2** chart rendering, `watch` command, plain mode; integration test.
- **M3** docs, roadmap, changelog; dashboard.

## 7. Decision and rollback

- **Adopt** if the command runs, the tests cover the pure functions and a real run, and the
  dashboard is green.
- **Abandon**: `git checkout feature/p6-performance`.

## 8. Log

- 2026-10-16: plan written; issue #77. Starting M1.
