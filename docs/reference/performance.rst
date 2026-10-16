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
     - ~0.1 s (warm) / ~0.3 s (cold)
   * - C5 3-year ``simulate`` + routing (300 blocks)
     - < 5 s
     - ~3.9 s
   * - Patch accounts / edge contrast / core area, per year
     - < 0.2 s
     - ~0.07 s
   * - One optimizer objective evaluation
     - < 50 ms
     - ~7 ms

The incremental objective
-------------------------

Feature account values are additive over blocks, so the optimizer evaluates a schedule as the
empty-schedule base plus a per-block delta (the base and each block's delta are cached). This is
exact: it matches a full re-simulation to floating-point tolerance. Edge contrast and route accounts
are not additive over blocks, so a configuration that uses them falls back to the full simulation.

Reproduce
---------

.. code-block:: bash

   python scripts/benchmark.py --scenario c5 --sample-dir <sample> \
       --years 3 --route-blocks 300 --spatial-years 1 --workdir tmp/benchmark
   python scripts/benchmark.py --scenario c5 --sample-dir <sample> --profile

The benchmark times each component (ingest, simulate, edge contrast, routing, patch accounts, one
objective evaluation) and reports peak memory. The recorded results are in
``notes/performance.md``; the plan (bottleneck map, targets, and work packages) is
``notes/design/ws4-performance.md``.

Guardrails
----------

``tests/test_performance.py`` holds the fast path fast and correct: the incremental objective must be
strictly faster than a full simulation, and it must match it on random schedules. The simulator is
deterministic given a schedule.
