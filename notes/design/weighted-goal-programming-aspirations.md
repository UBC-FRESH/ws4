# Weighted goal programming: targets as aspirations

Status: normative clarification
Date: 2026-10-31
Related: `adr/0004-goal-programming-metaheuristic.md`, `adr/0007-layered-optimization-stack.md`

## Purpose

This note fixes the interpretation of a WS4 target. A target is an **aspiration with a weighted
one-sided penalty**, not a hard feasibility bound. The names `minimum` and `maximum` describe the hinge
of the penalty; they do not mean that the solution must remain inside a feasible interval.

This matters most for harvest-level and even-flow target sets. A minimum that is deliberately set above
the achievable level is a valid **pull-up** mechanism, not a modelling error and not an infeasible
problem.

## The objective

For each active target `t` and accounting period, WS4 computes a weighted deviation:

```text
shortfall = max(minimum_t - value_t, 0)
excess    = max(value_t - maximum_t, 0)

term_t = min_weight_t  * shape(shortfall)
       + max_weight_t  * shape(excess)
```

`shape` is linear or squared (`non_linear`). The per-period terms are summed over the target's window.
Targets at the same priority tier are added. A priority-tier gap multiplies the lower tier by
`PRIORITY_SCALE` (`1e9`) per step; that is a nearly lexicographic ordering, not an ordinary weight.

Consequences:

- A minimum is not a floor in the constraint-programming sense. Over-performance is free unless a
  maximum is also set.
- A target set can be jointly unreachable and still be a valid objective. The search returns the best
  weighted compromise, and the report exposes the remaining penalty for every target.
- “Infeasible” is the wrong word for an unreachable minimum. It is a statement about hard constraints;
  WS4 is solving weighted goal programming.

## Maximum even-flow harvest

The pattern for “find the highest flat harvest profile this estate can sustain” is:

1. **Shape target.** One even-flow target on the harvest account over the desired horizon, with a band
   (for example ±1%), a high weight, and a reference period. The band measures deviation from the
   realized reference level.
2. **Level aspirations.** One minimum target on the same account in every period. Set each minimum
   above the level you expect to be achievable. These targets create a persistent downward penalty, so
   the search keeps pulling harvest up across the horizon.
3. **Let the level emerge.** The realized level is not declared. It is the level where the level
   aspirations and the flow band reach their best weighted compromise.

The deliberately unattainable level targets are the point of the construction. They make every period
carry a gradient toward more harvest, including periods that would otherwise be underused. The flow
target then selects the flattest profile at the resulting level.

## Dominance is a dial, not a binary switch

There are two ways to make even flow dominant, and they are not equivalent:

- **Use weights.** Keep the shape and level targets in one priority tier, give the flow target a much
  higher weight (for example 10,000 versus 1), and keep the level weight nonzero. Shape wins most
  trade-offs while the level pull remains active.
- **Use priority tiers.** Put the flow target at priority 1 and the level targets at priority 2. The
  level tier is then multiplied by `1e-9` relative to flow. This is appropriate only when the intent is
  a near-lexicographic order: satisfy flow first, then use the level targets as a weak tie-break.

The second form is not a stronger weight; it is a different decision. Do not use it when the level
targets are supposed to pull the solution upward.

## Failure modes

| Observation | Likely cause | Adjustment |
|---|---|---|
| Flat profile, but much lower than expected | Flow weight or priority gap overwhelms the level pull | Lower flow dominance, raise level aspirations, or keep level targets in the flow tier |
| High but ragged profile | Level pull overwhelms shape | Raise flow weight |
| Profile improves, then stops | Flow band is satisfied and only level terms remain | Raise the level aspiration if more volume is wanted |
| Solver reports a large residual penalty | The target set is a compromise; one or more aspirations are unreachable | Inspect per-target penalties; do not relabel it as infeasible |
| Some periods over-perform while others under-perform | One target per period is missing or the period coverage is incomplete | Put a level target in every period of the window |

## Anti-patterns

- Treating `minimum: 70000000` as a hard floor and concluding that the scenario is infeasible.
- Removing level targets because they are unreachable; that removes the pull-up gradient.
- Using a priority-tier gap for “a bit more important than level.” The gap is `1e9` per tier.
- Setting only one aggregate level target and expecting the search to distribute harvest across every
  period.
- Describing a weighted goal-programming result as a constraint violation without naming which target
  and what its reported penalty is.

## Where this is documented

- User guide: `docs/concepts/the-objective.rst`
- Even-flow recipe: `docs/howto/even-flow.rst`
- Optimizer reference: `docs/reference/optimizer.rst`
- Objective implementation: `ws4/opt/objective.py`
