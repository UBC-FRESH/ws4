# P86 close-out: weighted goal-programming target semantics

Date: 2026-11-01
Parent issue: #625
Branch: `feature/p86-target-semantics`
Pull request: pending

## Result

The target documentation now consistently describes weighted goal programming:

- a minimum/maximum is a one-sided penalty hinge, not a hard feasibility bound;
- an unreachable harvest minimum is a valid pull-up aspiration;
- period-level aspirations plus a dominant even-flow target produce the maximum
  even-flow harvest as an emergent level;
- `1e9` priority tiers are near-lexicographic, while weights are softer dominance;
- unit-scale normalization matters when comparing percentage flow penalties with
  volume-level penalties.

## Tasks

- P86.1 (#626): complete.

## Verification

```text
python -m sphinx -W -q -b html docs <build-dir>
sphinx exit 0

python scripts/check_workflow.py
0 error(s), 0 warning(s)
```

Full dashboard: **GREEN** (lint, format, types, tests, validator, docs, docstrings).

## Files

- `docs/concepts/the-objective.rst`
- `docs/howto/even-flow.rst`
- `docs/reference/optimizer.rst`
- `notes/design/weighted-goal-programming-aspirations.md`
- `notes/README.md`

## Closeout

The phase PR is queued for maintainer approval. No merge, settings change, or target
change was made.
