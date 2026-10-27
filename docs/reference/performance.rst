Performance and scale
=====================

WS4 is designed for large spatial models. The heavy paths — the simulator, the spatial metrics, and
the route model — run inside the optimizer's objective, so the work is measured and held with
performance tests and a reproducible benchmark.

Measured figures (C5-class sample: 16 174 fragments, 130 423 curves, 27 231 vertices, 36 721
segments; a 72-core host):

.. list-table::
   :header-rows: 1
   :widths: 52 24 24

   * - Workload
     - Target
     - Achieved
   * - C5 30-year ``simulate``
     - < 1 s
     - ~0.10 s (cold, 16 174 fragments)
   * - C5 3-year ``simulate`` + routing (300 blocks)
     - < 5 s
     - ~0.69 s
   * - Patch accounts / edge contrast / core area, per year
     - < 0.2 s
     - 29 / 39 / 31 ms, amortised over 30 years; a single cold year adds ~0.3 s of setup
   * - One optimizer move (the incremental evaluation)
     - < 50 ms
     - ~0.003 ms against a volume target, ~1 ms per iteration on a binding volume-plus-patch workload
   * - Island throughput at 8 / 32 islands
     - near-linear
     - 6.0k / 18.7k iterations/s (5.7x / 17.7x, at the loads recorded below)

The incremental objective
-------------------------

Feature account values are additive over blocks, so the optimizer evaluates a schedule as the
empty-schedule base plus a per-block delta (the base and each block's delta are cached). This is
exact: it matches a full re-simulation to floating-point tolerance. Haul, maintenance, and volume
route accounts are additive as well, so they are priced by a per-move route delta. Edge contrast, a
route **build** account, and duplicate accounts are not additive, so a configuration that uses any of
them falls back to the full simulation.

Carbon uses the same additive logic at block level: CBM is stand-level and area-additive, so the
``CarbonLedger`` caches one block's treatment chain and sums the blocks. Inventory and event
aggregation keep full-landscape schedules practical. P120 measured a one-step full-landscape baseline
at 60-107 s for TSA08/16/40/41 after inventory aggregation (down from more than 20 minutes), and
50-year all-block schedules at 358-738 s after event aggregation. The exact ``ws4 carbon`` run remains
the authority; the ledger is the fast search path. See ``notes/reports/p120-multi-boundary.md``.

Patch targets are not additive either: a patch spans adjacent blocks, so the optimizer prices them
through a patch model instead (a move touches only the components near the moved block). Because the
simulation is annual while the accounting is periodic, the patch statistics are maintained only at
the offsets a patch target reads — the end offset of its period — which is what took the patch
benchmark from 62 to 310 iterations/s.

Threads and scaling
-------------------

``OptimizeConfig.threads`` is the number of BLAS threads **each process** may use, and on the command
line ``--threads`` also sets the number of worker processes. It is applied where an optimizer is
built, which covers the parent and every worker process: the environment variables are set for
libraries loaded later and inherited by children, and ``threadpoolctl`` (installed with the ``opt``
extra) retunes the pools already loaded in the process — needed because a forked worker inherits its
parent's initialised BLAS, so the environment alone cannot reach it.

The default is one thread per process. Measured on the C5-class binding workload (a volume floor plus
a patch ramp, 4 000 iterations per island), BLAS parallelism buys the search nothing: one island ran
at 1 037 iterations/s with one thread and 1 033 with eight, and 32 islands ran at 13 660 / 14 385
iterations/s pinned against 12 318 / 15 877 unpinned — overlapping, so the difference is noise.

Parallelism is **process-level**, and the island model is the lever: independent islands, elite
migration between episodes, a deterministic result for a given seed. Scaling measured on the binding
workload (4,000 iterations per island, one thread each) with the host's load recorded for each run:

| Islands | Throughput | Speedup | Efficiency |
| ---: | ---: | ---: | ---: |
| 1 | 1,055 iterations/s | 1.0x | - |
| 8 | 6,014 iterations/s | 5.7x | 71% |
| 32 | 18,685 iterations/s | **17.7x** | 55% |

The limit is the **memory hierarchy**, not the BLAS pools (pinning them is measurably neutral), not the
per-process setup (~1 s), and not CPU oversubscription: efficiency is already ~56% at 16 islands on a
36-physical-core host, and the CPU accounting shows every process holding roughly one core while its
rate falls. More islands still win in absolute terms, so use them; expect the curve, not the line.
One way of attacking it has been measured and rejected. A worker builds its own copy of the dataset, so
a pool could in principle share one — but a worker builds it from the dataset directory and never uses
anything its parent built, so preloading the parent's caches shares nothing a worker reads and puts
about a second of setup on the critical path instead: roughly **-12%** at 16 and 32 islands, measured
against a paired control. Sharing pages would not have reduced bandwidth in any case, since every
process still reads the same bytes. `notes/performance.md` records the attempt, the confound that first
made it look like a regression from load alone, and the numbers, with the loads for each run.

Reproduce
---------

The figures above come from ``scripts/benchmark.py`` on a C5-class sample: a model the lab maintains,
with an established matrix under ``tracks/`` (``tracknames``, ``strata``, ``treatments``, ``blocks``,
``features``, ``products``, ``protoaccounts``), a fragment/block inventory under ``blocks/``, a
topology edge list there too, and the four road tables under ``roads/``. It is not in this repository,
so the commands take its directory:

.. code-block:: bash

   SAMPLE=/path/to/c5/sample
   python scripts/benchmark.py --scenario c5 --sample-dir $SAMPLE \
       --years 30 --route-blocks 300 --spatial-years 1 --workdir tmp/benchmark
   python scripts/benchmark.py --scenario c5 --sample-dir $SAMPLE \
       --years 3  --route-blocks 300 --spatial-years 1 --workdir tmp/benchmark-3y
   python scripts/benchmark.py --scenario c5 --sample-dir $SAMPLE \
       --years 30 --route-blocks 300 --spatial-years 30 --workdir tmp/benchmark-spatial

The first gives the 30-year ``simulate`` and the other components, the second the 3-year ``simulate``
with routing, and the third the patch-account figure **amortised** over 30 years — a single year
carries about 0.3 s of one-off setup (the topology, the block areas, the patch store), which is why the
per-year figure is the sum divided by the horizon.

Two kinds of figure come out of this, and only one of them travels:

- **Portable:** the counts — 16 174 fragments on this sample, and the table sizes. A re-run must
  reproduce these exactly, and does.
- **Host-dependent:** every timing. Reproducing a timing needs a comparable machine and the load it
  was taken at, which is why the tables above record both.

The recorded results, with the reproducibility check that Phase 8 ran against them, are in
``notes/performance.md``; the plan (bottleneck map, targets, and work packages) is
``notes/design/ws4-performance.md``.

Guardrails
----------

``tests/test_performance.py`` holds the fast path fast and correct: the incremental objective must be
strictly faster than a full simulation, and it must match it on random schedules. The simulator is
deterministic given a schedule.
