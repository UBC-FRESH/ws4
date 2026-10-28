# Phase close-out report: P78 Warm c5 max-flow probe

Phase: P78, Warm c5 max-flow probe
Parent issue: #554
Pull request: to be opened
Date: 2026-10-28
Status: ready for review. Not merged.

## Result

The longer probe used the cleaned c5 base targets, the 90% final growing-stock floor,
`product.Yield.managed.Conif`, `--flow even`, 1% flow tolerance, 20,000 iterations, and
four probes. It returned:

```json
{"ceiling": 0.0, "feasible": false}
```

A prior 3,000-iteration, six-probe run returned the same zero advisory ceiling. This is a
negative result. It is not a certified maximum and does not prove that a positive floor is
infeasible; the max-flow search is finite and has no warm/primed schedule input.

Reports:

- `/srv/shared-data/gep/ws4/archive/c5-base-max-flow-20261028c/max_flow.md`
- `/srv/shared-data/gep/ws4/archive/c5-base-max-flow-20261028d/max_flow.md`

The base scenario remains a policy floor (700k conifer + 50k deciduous per decade), not a
max-harvest claim. The next useful step is a warm-started/primed probe; the current
`max_flow.py` does not accept an initial schedule.

## Gates

`python scripts/dashboard.py`: lint 0.10 s, format 0.13 s, types 33.12 s, tests 156.44 s,
validator 1.00 s, docs 17.04 s, docstrings 2.96 s. Overall **GREEN**.
