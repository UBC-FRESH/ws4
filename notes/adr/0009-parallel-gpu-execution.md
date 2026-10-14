# ADR 0009: Parallel and GPU execution strategy

Status: accepted
Date: 2026-10-14
Issues: TBD

## Context

The target host is a two-socket node with 72 logical CPUs across two NUMA nodes and an NVIDIA RTX PRO
6000 Blackwell with 96 GB of memory. The search is stochastic and embarrassingly parallel at several
levels, but some work (neighbourhood evaluation) is also data-parallel and suits a GPU.

## Decision

Use four execution lanes: (1) a NUMA-aware process pool over the CPUs with per-worker seeds; (2) island
metaheuristics that exchange elites asynchronously; (3) GPU move evaluation by tensorizing the hot
operators and evaluating many candidate moves at once, starting with PyTorch and falling back to the
CPU when the GPU is not the bottleneck; and (4) parallel math-heuristics that run MIP subproblems
concurrently and a MIP lane beside the heuristic lane.

## Consequences

- A parallel sweep reproduces a serial one when seeds are assigned per worker.
- The GPU is used only where it helps; the design does not assume GPU acceleration everywhere.
- The tensor representation of a schedule adds a second view of the same state, which must stay in
  sync with the CPU view.
- Parallel math-heuristics add a solver dependency and a scheduling policy between the lanes.

## Alternatives considered

- **CPU only.** Rejected: leaves the GPU idle for a data-parallel workload.
- **GPU only.** Rejected: much of the search is latency-bound and sequential.
- **CUDA from the start.** Rejected: a high barrier; a tensor library reaches the same operators with
  far less code, and a hand-written kernel can follow if profiling demands it.
