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

### P83.3 Bounded/batched LNS (next issue after #586)

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

Implement P83.2 (dense target state) and rerun the 100k benchmark. Record the result in this
note and the changelog before moving to P83.3.
