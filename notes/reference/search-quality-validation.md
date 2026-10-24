# Search quality and validation (P21)

Status: P21.1 and P21.2 implemented; P21.3 and P21.4 planned.
Phase: P21, parent issue #190, branch `feature/p21-search-quality`.

## Why

A heuristic result is only useful if its quality is measurable. A single seed is an anecdote; a
single engine is not a comparison. P21 adds the smallest set of changes that make the search's
quality visible and improve it without replacing the existing solver stack.

## P21.1 — Reversion

`OptimizeConfig.reversion` (`ws4 optimize --reversion N`) resets the current solution to the
incumbent every *N* accepted moves, then continues from there. `0` disables it. It is applied by:

- `solve_sa` (whole-schedule evaluation);
- `solve_sa_delta` (incremental evaluation, with `evaluator.reset`);
- `solve_tabu`;
- `solve_ils`.

The run summary records `reversion`. The helper `ws4.opt.solvers.reversion_due` is unit-tested, and a
small optimizer run asserts that the setting reaches the summary and still writes a schedule.

Reversion is an intensification step: it recovers a search that has wandered into a poor
neighbourhood. It is not a substitute for a good move set or a proper cooling schedule.

## P21.2 — Validation sweep

`scripts/validate_search.py` runs the same targets, horizon, and iteration budget through SA, tabu,
and ILS over several seeds. It reports:

- runs, best, mean, median, worst, and population standard deviation per engine;
- the objective of every run and its output directory;
- `zero_penalty` (all targets met) per run;
- the MIP lower bound and gap when `--mip-bound` is set;
- the reversion interval when `--reversion` is set.

It writes `validation.json` and `validation.md`. It is an orchestrator over `Optimizer`, not a second
solver, so a record can be reproduced with the equivalent `ws4 optimize` command.

Example:

```bash
python scripts/validate_search.py \
  --dataset runtime/tsa47_full/matrix \
  --targets config/targets.tsa47_full.yaml \
  --engines sa,tabu --seeds 1,2 \
  --iterations 50 --years 100 --reversion 10 \
  --out /tmp/ws4-validation
```

A small 50-iteration sweep on the TSA 47 model, with reversion 10:

| Engine | Runs | Best | Mean | Worst | Stdev |
| --- | ---: | ---: | ---: | ---: | ---: |
| sa | 2 | 82,964,537.6 | 82,971,840.8 | 82,979,144.1 | 7,303.2 |
| tabu | 2 | 82,573,151.0 | 82,593,242.0 | 82,613,332.9 | 20,091.0 |

This is a harness demonstration, not a benchmark claim: 50 iterations is far below the budget the
TSA 47 benchmark uses, and neither engine reached a zero penalty. The value is that the harness makes
the spread and the engine comparison visible.

## P21.3 — Sensitivity report (planned)

The MIP layer already returns a penalty lower bound and a gap. The next step is an advisory
sensitivity report: for each target, whether it is binding, its slack, and the marginal effect of
relaxing it. This extends `ws4.opt.mip` rather than replacing it. It must not change a schedule.

## P21.4 — Threshold accepting (planned)

A threshold-accepting solver would share the operator registry and incremental evaluator. It accepts
a feasible move when the objective decline is within a current threshold, and shrinks the threshold
over time. It is simpler to explain and tune than SA and is competitive on spatial harvest scheduling.

## Related

- `docs/reference/optimizer.rst` — user-facing options and the validation sweep.
- `notes/design/ws4-optimization-stack.md` — the layered stack this phase extends.
- `notes/backlog.md` — the wider tuner, portfolio, and multi-objective work.
