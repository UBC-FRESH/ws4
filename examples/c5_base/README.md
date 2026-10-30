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

## 100,000-iteration verification

The fixed-priority 100,000-iteration run is recorded in
`/srv/shared-data/gep/ws4/archive/c5-stage2-priorityfix-100k/watch.log`. It finished at
69.6 evaluations/s after 1,436 seconds.

It did **not** meet all targets:

- conifer even flow: period 1 = 1.52M; periods 2–20 range 1.13M–1.35M, worst deviation
  about **−25.7%**
- deciduous even flow: 118k–135k against a 124k reference, worst deviation about
  **+8.9%**
- final growing stock: **18.5M** against the 23.9M target

The priority fix made the flow term count; it did not make this target set jointly
feasible. The 2,000,000/200,000 level pull, the 90% final-stock target, and ±5% even flow
are in tension. The next run should change the target balance rather than only add
iterations.

## Fast-LNS watcher

`run_watch_c5_fast_lns.sh` runs the accepted stock-79 policy with the latest bounded
LNS path:

- LNS weight `0.2`
- destroy fraction `0.1`
- max destroy **64 blocks**
- `targets_balanced_stock79.yaml`
- `seed_stage1.csv`

```bash
bash run_watch_c5_fast_lns.sh 100000
PLAIN=1 bash run_watch_c5_fast_lns.sh 100000
```

The script uses the latest WS4 source at `/tmp/opencode/ws4-p83` by default; set
`WS4_REPO` if that worktree moves.

## Balanced target variant

`targets_balanced.yaml` is the pilot for the joint target balance:

- conifer level: **1,200,000 per period**, weight 1
- deciduous level: **125,000 per period**, weight 1
- even flow: **±5%**, weight 10,000, reference period 1
- final stock: **23,900,770.58**, weight **10** (pilot calibration)
- every row: `priority: 1`

Run it with the same stage-1 seed:

```bash
TARGETS="$PWD/targets_balanced.yaml" bash run_watch_evenflow.sh 100000
```

The level targets are no longer an over-maximum pull; they are near the observed feasible
harvest. The stock weight is a starting calibration, not a final policy weight.

The 100,000-iteration pilot (`/srv/shared-data/gep/ws4/archive/c5-balanced-100k/watch.log`)
finished in 1,368 seconds. It still did **not** meet the joint targets:

- conifer flow: period 1 = 1.52M; periods 2–20 range 1.12M–1.35M; worst about **−26%**
- deciduous flow: 115k–132k against 125k; worst about **−8%**
- final growing stock: **18.7M** against 23.9M

The stock weight of 10 was not enough to close a 5.2M stock gap, and the conifer flow
plateau did not improve when the level pull was lowered.

A 20,000-iteration sensitivity with the stock weight at **100** is recorded in
`/srv/shared-data/gep/ws4/archive/c5-balanced-stock100-20k/watch.log`. It moved the final
stock only to **20.0M**, still 3.9M short, while making the flow much worse:

- conifer: period 1 = 1.52M, falling to **0.77M** by period 17; worst about **−49%**
- deciduous: 100k–121k; worst about **−20%**

Weight alone trades flow for stock; it does not close the stock gap. The 23.9M target is
not compatible with the current 1.2M/125k harvest and ±5% flow. The next test should lower
the harvest levels, not raise the stock weight again.

A 20,000-iteration lower-harvest pilot (conifer 1.05M, deciduous 105k, stock weight 10)
is recorded in `/srv/shared-data/gep/ws4/archive/c5-lower-harvest-20k/watch.log`. It also
did not meet the set:

- conifer: period 1 still **1.52M**; worst deviation about **−32%**
- deciduous: 110k–123k against a 114k reference; worst about **+8%**
- final stock: **19.0M** against 23.9M

Lowering the level pull did not move the period-1 conifer spike, and the stock target
remains far short. The next useful step is to explain why period 1 is pinned at 1.52M
before changing target weights again.

## Split-block candidate fix

The pin was a candidate-generation bug. Blocks split across several tracks can have a
first fragment whose track has no treatments; `Optimizer.candidates()` took that first
track and returned no options. The fix uses the largest treatment-bearing fragment.

With the fix, a 20,000-iteration balanced pilot (`c5-balanced-fixed-20k`) gives:

- conifer: period 1 = **743k**; periods 2–14 = **776–793k**; periods 15–20 = **683–704k**
- conifer deviation: about **+6.7% / −8.1%**
- deciduous: **67–75k**, about ±6%
- final stock: about **20.6M** against 23.9M

The flow is now responsive and nearly even, but not yet inside ±5%, and the stock target
is still short. The run was also much slower at **3.27 eval/s** because the corrected
candidate set is larger.

The watch chart also had a level-display bug: it summed ten annual feature values for
stock (displaying 206M instead of about 20.6M). That is fixed; feature levels now show the
period-end value.

## Caveats

The `targets.yaml` file remains the lighter base scenario (conifer **700,000**, deciduous
**50,000**, even-flow ±5%). It is not the same as the stage-2 over-maximum pull.

The max-flow probe is advisory and has not verified a positive even-flow ceiling. A
zero or infeasible probe is not evidence of a maximum.

The sample runs root contains only `run-base`. Old test runs and scenario fragments are
archived under `/srv/shared-data/gep/ws4/archive/c5-parity2025-scenarios-20261028`.
