# C5 even-flow performance plan

Phase identifier: P83
Task identifier: P83.1
Parent phase issue: #579 (P83)
Branch: `feature/p83-two-stage-flow`
Status: active
Date: 2026-10-30

## Scope

Make the seeded c5 even-flow search fast enough for the 100,000-iteration budget without
changing the exact target semantics. The plan covers the optimizer's seeded startup, the
move-delta path, LNS, and the optional GPU batch path. It does not change the target set or
the even-flow policy.

## Current evidence

The original seeded 20,000-iteration run took **6,118 s** at **3.27 eval/s**. After the
feature-checkpoint, account-filter, flow-delta, incumbent-update, and startup changes, the
same class of run takes **12.4 s**, and a 100,000-iteration no-LNS run takes **36.1 s**
(~2,770 eval/s end-to-end).

The 100,000-iteration result still misses the joint targets:

- conifer flow worst **-8.12% / +6.01%**
- deciduous flow worst **-5.28% / +4.74%**
- final stock **20.96M** against 23.9M
- objective **39,133,750**

The optimization speed improved; the target set is still in tension. Performance work must
not present this as a solved even-flow case.

## Findings

- The seeded reset, candidate generation, and three simulator constructions were startup
  costs; reusing the simulator and single-pass seed parsing removed most of that.
- Feature targets forced a full 200-year feature scan per block/chain. Evaluating only the
  target period ends and jumping between treatment events removed that cost.
- Flow penalties were priced with four full 20-period scans per move. Caching the period
  balances and pricing only touched periods removed most of that cost.
- The incumbent copy was O(schedule) on every improvement. A journal of accepted changes
  makes it O(changed blocks).
- LNS with 10% destroy changes hundreds of blocks and was ~4.7x the no-LNS loop. A
  bounded destroy count (64 blocks) keeps the move cost bounded.
- A dense 1.4M-chain contribution table costs ~44 s and ~1.8 GB. It is not worth it for a
  single 100k run; the lazy cache touches only a fraction of the candidates with LNS off.

## Work packages

### P83.2 Seeded startup and delta state (#586)

- Keep the reusable simulator in candidate generation and report replay.
- Keep the one-pass schedule parser.
- Convert the remaining target state and pending work to dense integer cell indices.
- Acceptance: objective and account values are bit-identical on the regression fixtures;
  the 100k benchmark is faster than the 36.1 s baseline.

### P83.3 Bounded/batched LNS (#587)

- Keep the 64-block destroy cap.
- Batch contribution construction for the changed blocks and sum the effect rows.
- Acceptance: LNS moves are exact against `_evaluate`; LNS benchmark is faster than the
  current bounded-LNS path; no change to one-block moves.

### P83.4 Seeded process-pool islands

- Allow the process-pool search to load the same seed in each worker.
- Use independent islands and periodic elite migration.
- Acceptance: seeded islands produce the same objective semantics; a multi-island run
  completes in less wall-clock time than a serial run; seed and migration are recorded.

### P83.5 Flow-directed search

- Add moves that shift harvest from above-reference periods to below-reference periods.
- Test an LP/network-flow period-volume initialization before block assignment.
- Acceptance: ±5% flow is reached in fewer iterations than the random-move baseline, or the
  negative result is recorded with the measured gap.

### P83.6 GPU batch path (optional)

- Use CUDA/PyTorch for batched LNS or batched proposals, not one sequential move per kernel.
- Do not build a dense effect table unless it is persisted and reused across runs.
- Acceptance: a GPU batch path is exact against the CPU path and faster on this host;
  otherwise record the negative result and keep the CPU path.

## Oracles

- `pytest tests/test_incremental.py tests/test_optimizer.py tests/test_flow_targets.py`
- A random-walk comparison of `evaluator.objective + evaluator.delta` against
  `optimizer._evaluate` on the fixture, including feature and flow targets.
- The 100k benchmark command and its wall-clock, objective, flow, stock, and seed.
- `python scripts/dashboard.py` before closing the task.

## Non-goals

- Do not change `priority: 1` targets or reintroduce tiered priorities.
- Do not claim a maximum even-flow ceiling from a zero or infeasible probe.
- Do not claim the stock target is met while it is below 23.9M.

## Next bounded move

P83.2 was a neutral probe, not a claimed speedup. The next bounded move is P83.3 (batched
LNS contributions) or P83.5 (flow-directed moves), then rerun the 100k benchmark and record
the result in this note and the changelog.

## P83.2 evidence (2026-10-30)

- Precomputed target cell metadata (target cells, accumulation flags, end cells) removed
  repeated `cell_offsets()` and priority-set construction from the delta path. The 100k
  objective is unchanged. Timing was **not a clear win**: 44.3 s in one run against the
  36.1 s baseline; a 20k run was 14.8 s against 12.4 s. Treat this as neutral until a
  quieter benchmark says otherwise.
- The process-pool path now accepts an initial schedule and shares it with every start or
  island. Eight 20k starts completed in **24.2 s** (160k evaluations, ~6.7k eval/s
  aggregate), but a single 20k run was faster in wall-clock. This is a throughput and
  multi-seed capability, not a single-run speedup. Keep it off by default until a
  multi-seed quality test justifies it.
- Next bounded performance move: batch LNS contributions or flow-directed moves. Do not
  claim the dense metadata as a speedup yet.

## P83.3 evidence (2026-10-30)

- A full ragged-numpy `block_chain_many` batch was prototyped first and was **exact but
  slower** on c5: blocks average 1.3 fragments and the balanced target set has a single
  feature checkpoint (offset 199), so numpy per-batch overhead exceeded the per-block
  Python loop (0.6-0.8x at 64 pairs). It was not kept.
- The exact win is a direct path for the dominant chain shape (no event or one event):
  `Simulator._block_chain_short` skips the checkpoint set and the fourteen-feature /
  eighteen-product scan, using cached filtered row tables. A cold `_block_delta` over 2000
  pairs fell from 0.057-0.062 s to 0.031-0.034 s (about 1.8x).
- `IncrementalObjective.prefetch` plus `Optimizer._block_deltas` now fill the contribution
  cache for a multi-block move before `delta` prices it; one-block moves never call it.
  Random-walk tests compare the batched/multi-block deltas with the single-pair path and
  `_evaluate`, including product, feature, and product-flow targets.
- CLI LNS benchmark (`--lns-weight 0.2 --lns-max-destroy 64`, seed 1, balanced targets,
  `seed_stage1.csv`): 20k 17.2-17.3 s before, 16.1-16.3 s after; 5k 9.7 s before, 9.0-9.5 s
  after. The search loop alone (no telemetry) is 8.1-8.5 s before and 6.6-7.3 s after at
  20k. The objective is unchanged to 1e-8 (float summation order differs).
- A pre-existing gap remains out of scope: a **flow target on a feature account** leaves
  the flow window's feature years out of `_wanted_feature_offsets`, so the incremental
  totals understate that account. Product flow (the c5 scenario) is unaffected. Recorded
  here so the next task does not mistake it for a regression.

## P83.3/P83.4 100k checks (2026-10-30)

- P83.3 LNS 100k (cap 64): **53.1 s**, objective **39,501,948**; conifer flow
  **-7.99% / +6.08%**, deciduous **-5.57% / +4.93%**, stock **20.98M**. This is not better
  than the no-LNS 100k result (36.1 s, objective 39,133,750).
- P83.4 eight seeded 100k starts: **58.5 s**, best objective **39,133,750** (the same
  result as the best single start). Aggregate throughput rose, but single-run quality and
  wall-clock did not improve. Keep multi-start off by default.
- Next bounded move is P83.5 flow-directed moves (#589); do not claim a target win from
  LNS or multiple starts.

## P83.5 evidence (2026-10-30)

- Added `ws4/opt/flow_repair.py`: a bounded post-search repair pass over an incumbent
  schedule. For each even-flow target on an accumulating account it ranks scheduled blocks
  by the volume they contribute to periods above the target's maximum, tries that block's
  candidate chains whose first event falls below the target's minimum, and prices each
  proposal with `IncrementalObjective.delta`. A move is applied only when the exact
  full-objective delta is negative, the target's own flow penalty falls, and no other
  even-flow target's penalty rises. The pass is bounded by candidate trials, not wall
  clock. The CLI exposes it as `--flow-repair-trials` and `--flow-repair-chains` (default
  0 = off). Target semantics are unchanged.
- Exactness: `tests/test_flow_repair.py` compares the repaired objective with a fresh
  incremental evaluator and with `Optimizer._evaluate`, checks that accepted moves lower
  both the objective and the flow penalty, and checks the no-flow and invalid-bound cases.
  Focused suite (`test_flow_repair`, `test_flow_targets`, `test_incremental`,
  `test_optimizer`): 97 passed.
- Benchmarks use seed 1, `--lns-weight 0`, years 200, balanced targets, and
  `seed_stage1.csv`; the repair pass used 20,000 trials and 8 chains per block:

  | run | search iters | wall s | objective | final stock | conifer flow | decid flow |
  | --- | ---: | ---: | ---: | ---: | --- | --- |
  | baseline | 5,000 | 7.8 | 51,620,713 | 19.20M | -9.33% / +7.63% | -6.28% / +8.72% |
  | + repair | 5,000 | 12.2 | 51,344,366 | 19.18M | -8.27% / +5.38% | -2.64% / +7.50% |
  | baseline | 10,000 | 9.4 | 47,266,580 | 19.73M | -8.66% / +6.39% | -5.36% / +4.91% |
  | + repair | 10,000 | 13.1 | 47,174,058 | 19.72M | -7.44% / +6.07% | -5.35% / +4.81% |
  | baseline | 20,000 | 12.9 | 44,719,123 | 20.11M | -8.43% / +6.44% | -5.35% / +5.08% |
  | + repair | 20,000 | 16.2 | 44,671,405 | 20.10M | -7.72% / +6.26% | -5.31% / +4.85% |

- At 20k the pass accepted 16 moves in 1.9 s. The summed flow penalty fell from 430,171
  to 280,718 (-35%); every reported minimum and maximum moved toward zero, but the stock
  fell by 6.6k and the objective only improved by 47.7k. The ±5% flow band is **not**
  reached at 20k, so this is a gap reduction, not a target win.
- The gain is largest at short search budgets: 5k + repair improved the conifer worst
  gap from -9.33%/+7.63% to -8.27%/+5.38%, and 10k + repair reached a better conifer
  minimum (-7.44%) than the 20k baseline (-8.43%). A longer search lowers the objective
  and raises stock but leaves a harder flow shape for the same repair budget, so the pass
  is not a substitute for more search and its result depends on the incumbent.
- Remaining risks: a move is accepted on the full objective and the flow penalty, not on
  the worst single period, so a later accepted move can shift which period is worst. The
  pass only sees candidate chains, so a seed chain that is not in the candidate list
  cannot be preserved by an event-level shift. It only repairs accumulating accounts; the
  pre-existing feature-account flow gap noted under P83.3 is unchanged. A 30k-trial,
  8-chain run is similar (objective 44.6687M, conifer -7.71%/+6.18%, decid -5.31%/+4.85%),
  so 20k trials is the better default.
- Next bounded move is P83.6 (GPU batch path); do not claim a ±5% target win from this
  repair.

