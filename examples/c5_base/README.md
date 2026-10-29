# c5 20 × 10-year even-flow base scenario

Initial growing stock (`feature.total.Yield` at year 0): **26,556,411.75**.
Final-period target: **90% = 23,900,770.58** at period 20 (years 190–199). This is a
weighted goal-programming target, not a hard constraint.

The scenario has 20 periods of 10 years. The even-flow run uses the two-stage target
files in this directory.

## Two stages

Stage 1 (`targets_stage1.yaml`) pulls harvest without an even-flow term:

- conifer level target: **2,000,000 per period**, weight 1, linear
- deciduous level target: **200,000 per period**, weight 1, linear

Those level targets are deliberately above the maximum achievable harvest. They are a
pull, not a claim about a feasible even-flow ceiling.

Stage 2 (`targets_stage2.yaml`) keeps the same level pull and adds:

- even-flow: **±5%**, referenced to period 1, window periods 1–20
- weight **10,000**, non-linear
- final growing-stock target: **23,900,770.58** at period 20

The stage-2 seed is `seed_stage1.csv`, the schedule produced by stage 1. Priming the
reference period is required: an even-flow target referenced to period 1 is meaningless
when period 1 carries no wood.

## Priority

Every target row must use `priority: 1`.

WS4 treats priority as a tier, not as a weight. Priority 1 is the highest tier; when
mixed tiers exist, lower tiers are separated by a factor of `1e9`. Putting the flow
targets at `priority: 2` makes the level targets dominate the objective by about eight
orders of magnitude, so the flow penalty is effectively ignored even at weight 10,000.

## Seed and rotation age

The mean yield curve is built by area-weighting the `product.Yield.managed.Conif` and
`.Decid` curves over the managed THLB. The maximum mean annual increment for this c5
curve is at **rotation age 112 years** (MAI ≈ 1.447 m³/ha/year for conifer). The managed
THLB in the compiled blocks is **71,138 ha**, which implies roughly **635 ha/year**, or
about **6,352 ha per 10-year period**, harvested oldest-first.

The companion seed is `seed_200y.csv` in this directory: a real 200-year schedule with
7,253 scheduled blocks. It primes every period so the even-flow reference is meaningful.

## Run

```bash
# Stage 1: create the seeded schedule.
ws4 optimize \
  --dataset /srv/shared-data/gep/ws4/ws4/tmp/parity2025/c5_compiled \
  --targets /srv/shared-data/gep/ws4/ws4/tmp/parity2025/scenarios/c5-base/targets_stage1.yaml \
  --out /srv/shared-data/gep/ws4/ws4/tmp/parity2025/scenarios/c5-base/stage1 \
  --years 200 --iterations 1000 --seed 1 \
  --initial-schedule /srv/shared-data/gep/ws4/ws4/tmp/parity2025/scenarios/c5-base/seed_200y.csv

# Stage 2: watch the even-flow search from the stage-1 schedule.
bash run_watch_evenflow.sh 100000
```

The watcher uses `targets_stage2.yaml` and `seed_stage1.csv`. A 100,000-iteration run is
intentionally long; do not judge stability from the first few thousand iterations.

## Caveats

The `targets.yaml` file remains the lighter base scenario (conifer **700,000**, deciduous
**50,000**, even-flow ±5%). It is not the same as the stage-2 over-maximum pull.

The max-flow probe is advisory and has not verified a positive even-flow ceiling. A
zero or infeasible probe is not evidence of a maximum.

The sample runs root contains only `run-base`. Old test runs and scenario fragments are
archived under `/srv/shared-data/gep/ws4/archive/c5-parity2025-scenarios-20261028`.
