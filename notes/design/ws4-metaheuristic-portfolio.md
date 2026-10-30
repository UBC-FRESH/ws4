# WS4 metaheuristic portfolio plan

Phase identifier: P83
Task identifier: P83.9
Parent phase issue: #579
Branch: `feature/p83-meta-portfolio`
Status: active
Date: 2026-10-30

## Decision

Yes. A master/worker portfolio that mixes SA, tabu search, ILS, GA, and LNS is a
reasonable next experiment. The archive's AGrp prototype already demonstrates the
master/7-worker elite-migration structure, and the different methods explore different
parts of the solution space.

Important distinction:

- share **schedules and elite solutions** between methods;
- do not share each method's internal state or pretend the methods are one monolithic
  operator.

This is a portfolio / hyper-heuristic master, not a new local-search move.

## Architecture

```text
master
  elite archive
  method allocation / credit
  migration and restart policy
  common objective evaluator
        |
        +-- SA worker(s)
        +-- tabu worker(s)
        +-- ILS worker(s)
        +-- GA / island GA worker(s)
        +-- LNS worker(s)
```

### Master responsibilities

- Hold the global elite archive and the best schedule.
- Seed new workers from one or more elites.
- Record each method's recent improvement, cost, and diversity contribution.
- Allocate worker slots by a simple bandit/credit rule.
- Migrate elites at generation boundaries.
- Restart a stalled worker from the global elite or a diverse elite.
- Keep the exact objective and reproducibility record.

### Worker responsibilities

- Run one method for a bounded budget.
- Accept only its own internal state transitions.
- Return the best schedule(s), objective, evaluations, and timing.
- Never mutate the global archive directly.

## Method mix

### SA

Parallel chains are already GPU-friendly and produce the current large batched throughput.
Use SA workers for broad exploration and annealing from elite seeds.

### Tabu search

Use short tabu tenures to escape local optima and diversify away from recently visited
blocks/chains. A tabu worker can share only its returned elite, not its tabu list.

### ILS

Use perturbation plus local search. Good for intensification around a promising elite.
Keep the perturbation size as a worker parameter.

### GA / island GA

Population crossover and mutation. This is the P83.8 implementation; it provides
recombination and diversity that single-trajectory methods lack.

### LNS

Large-neighbourhood repair around an elite. Use the sparse GPU effect table for
batched neighbourhood pricing; keep the CPU LNS as the exact reference.

## Master allocation

Start with a fixed but diverse allocation, then adapt:

- 2 SA workers,
- 1 tabu worker,
- 1 ILS worker,
- 1 GA worker,
- 1 LNS worker,
- 2 general/restart workers.

After each generation/budget slice:

- reward a method by objective improvement per wall-second,
- reward diversity if its elite differs materially from the archive,
- decay stale rewards,
- reallocate one slot at a time; do not churn every generation.

The first version should use a **fixed round-robin** allocation so quality differences are
not confounded with credit-assignment bugs.

## State sharing

The archive's `pp` implementation passed the best genome to workers and returned an
elite; it did not share memory. Keep that.

For WS4:

- common representation: schedule (block -> treatment chain),
- master sends one or more elite schedules,
- worker returns one or more schedules,
- migration is an explicit, recorded event,
- no shared mutable Python objects across processes,
- no hidden global state.

## GPU layout

- SA/parallel chains: batched chain-row state, as in the existing GPU prototype.
- GA: batched genome fitness over the sparse effect table.
- LNS: batched segmented deltas.
- Tabu/ILS: parallel independent chains; use GPU where the move evaluation is batchable.
- Master and credit assignment stay on CPU/GPU host; workers use the shared tablet.

## Benchmarks

Compare at equal wall-clock budgets:

1. Best tuned SA.
2. Best tuned tabu.
3. Best tuned ILS.
4. Best tuned GA.
5. Best tuned LNS.
6. Portfolio with fixed round-robin.
7. Portfolio with adaptive credit.

On c5 2k first, then TSA23 5k, then full TSA23 with the persisted effect table.

Record:

- objective,
- best feasible objective,
- mean over seeds,
- time to best,
- evaluations,
- GPU utilization/VRAM,
- method contribution,
- migration count.

## Acceptance

- The portfolio must use the exact WS4 objective for final verification.
- It must beat the best single method on at least one quality metric, or record a clear
  negative result.
- No claim of wall-clock superiority without equal-budget comparisons.
- A method that never contributes an elite is reported, not hidden.
- Dashboard green before closing.

## First bounded move

Implement the master/worker protocol as a CPU orchestration prototype around the existing
CPU/GPU methods:

- fixed round-robin allocation first,
- one elite archive,
- explicit migration,
- no adaptive credit yet.

Then add the adaptive allocation only after the fixed portfolio is measured.
