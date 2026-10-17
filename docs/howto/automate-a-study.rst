================
Automate a study
================

The command line is the fastest way to run one study. The Python API is the way to run **many**:
sweeps over seeds, targets, and weights; custom diagnostics mid-search; results collected into a
frame; WS4 embedded in something else. This guide is the set of patterns that make that practical.

Prerequisites
-------------

* The API walkthrough read once (:doc:`../getting-started/python-api`).
* A compiled dataset and a targets file you are happy with.

Patterns
--------

**1. Run many configurations and collect the summaries.** Every run writes the same files, so a sweep
is a loop:

.. code-block:: python

   import pandas as pd
   from pathlib import Path

   from ws4.opt.engine import OptimizeConfig, Optimizer

   rows = []
   for seed in range(1, 11):
       out = Path(f"tmp/study/seed-{seed}")
       optimizer = Optimizer.from_dataset(
           dataset,
           OptimizeConfig(
               years=100,
               iterations=5000,
               seed=seed,
               targets_path="tmp/howto/targets.yaml",
               starts=1,
           ),
       )
       summary = optimizer.run(out)
       rows.append({"seed": seed, "objective": summary["incumbent_objective"],
                    "blocks": summary["blocks_scheduled"]})

   print(pd.DataFrame(rows).describe())

The objective spread across seeds tells you whether a single run is worth reporting.

**2. Build targets in memory.** A sweep over a target value does not need a file per case:

.. code-block:: python

   from ws4.opt.objective import Target

   for floor in (20_000, 30_000, 40_000):
       targets = [
           Target("product.Harvested.CC", period * 10, minimum=floor, period_width=10)
           for period in range(10)
       ]
       evaluator = optimizer.delta_evaluator(targets)
       # ... drive a solver, or hand the evaluator to your own loop

**3. Price a move yourself.** The evaluator holds the running totals and returns the **exact** change
a move would make, without re-simulating. That is what makes a custom acceptance rule, a diagnostic,
or a different solver cheap:

.. code-block:: python

   import random

   from ws4.opt.solvers import solve_sa_delta

   candidates = optimizer.candidates()
   evaluator = optimizer.delta_evaluator(targets)
   best, objective = solve_sa_delta(
       evaluator,
       random.Random(1),
       iterations=20_000,
       temperature=1000.0,
       cooling=0.99,
       candidates=candidates,
       registry=optimizer.registry,
   )

Change ``random.Random(1)`` for any random source, and swap ``solve_sa_delta`` for ``solve_sa``,
``solve_tabu``, or ``solve_ils`` to try another metaheuristic on the same problem.

**4. Resume, warm-start, and watch.** ``solve_sa_delta`` and its siblings take an ``initial``
schedule, which is how a study fragments a long run — prime, then add a term, then continue:

.. code-block:: python

   primed, _ = solve_sa_delta(evaluator, rng, iterations=20_000, ..., initial=None)
   even, _ = solve_sa_delta(evaluator_with_flow, rng, iterations=20_000, ..., initial=primed)

**5. Scale out.** A single search is one process. Two configurations scale:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Setting
     - What it does
   * - ``starts`` and ``workers``
     - Run independent multi-starts across worker processes and keep the best. Reproducible: the
       parallel path returns what the serial path returns for the same seed.
   * - ``islands`` and ``episodes``
     - Run the island model: several islands in parallel, migrating the global elite between
       episodes. The result is deterministic for a given seed.

.. code-block:: python

   optimizer = Optimizer.from_dataset(
       dataset,
       OptimizeConfig(years=100, iterations=3000, islands=8, episodes=2, workers=8,
                      targets_path="tmp/howto/targets.yaml", seed=1),
   )
   summary = optimizer.run(Path("tmp/study/islands"))

Threads do **not** help the numeric core: the curve evaluation holds the GIL and is already close to
the NumPy floor (`notes/performance.md` in the repository records the measurement). Process-level
parallelism is the lever.

**6. Read the run back.** The model and run outputs are ordinary files and frames, so a study's
results go straight into analysis:

.. code-block:: python

   from ws4.model.api import Model

   model = Model.from_dataset(dataset)
   schedule = pd.read_csv("tmp/study/islands/schedule.csv")
   values = pd.read_csv("tmp/study/islands/account_values.csv")
   report = pd.read_csv("tmp/study/islands/report_targets.csv")

   print(report.groupby("status").size())

Troubleshooting
---------------

* **The API returns nothing useful for account values** — the run's own files are the reliable
  source: ``account_values.csv``, ``report_targets.csv``, ``report_accounts.csv``.
* **A sweep is slower than the CLI** — the CLI sets threads for BLAS and the search; a script should
  set ``threads`` in ``OptimizeConfig`` the same way it does, or run with ``workers``/``islands`` and
  keep each process single-threaded.
* **Results differ between machines** — the search is deterministic for a given seed *and* the same
  code path; a different ``workers`` or ``islands`` setting is a different search, not a different
  answer to the same question. Pin those in a study's configuration and record them next to the
  results.
