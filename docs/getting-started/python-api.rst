==========================
Quickstart: the Python API
==========================

This page does what :doc:`quickstart` does — compile, simulate, target, search — as library calls.
It is the path to take when a study has to be automated: parameter sweeps, custom diagnostics,
integrating WS4 with another tool, or resuming a run to inspect it.

Every snippet below was run against the two-block example in ``examples/synthetic``, and the output
shown is the output it produced. For a complete session with its real output — compiling the sample
estate, simulating in memory, searching, and checking the result — see the
:doc:`library-path example <../examples/070_library_path>` in the gallery.

Compile a dataset
-----------------

.. code-block:: python

   from pathlib import Path

   from ws4.build.compiler import build_canonical_dataset

   dataset = build_canonical_dataset(
       Path("examples/synthetic/recipe.xml"),
       Path("examples/synthetic/fragments.csv"),
       Path("tmp/getting-started/compiled"),
   )

.. code-block:: text

   dataset: tmp/getting-started/compiled

The compiled dataset is the contract between ingestion and execution: a directory of Parquet tables
plus a manifest (see :doc:`../reference/compiled-dataset`). Inspect it with the model API, which
holds one frame per table:

.. code-block:: python

   from ws4.model.api import Model

   model = Model.from_dataset(dataset)
   print(sorted(model.tables))
   print(model.table("fragments").to_string(index=False))

.. code-block:: text

   ['accounts', 'blocks', 'curves', 'features', 'fragments', 'groups', 'messages',
    'products', 'protoaccounts', 'strata', 'tracks', 'treatments']
    fragment_id  block_id  area_ha  age  track_id
              1         1      3.0   40         1
              2         2      2.0   60         1

Simulate a schedule
-------------------

A schedule is a frame with ``block_id``, ``treatment``, and ``period`` columns, where the period is
in years. ``Simulator.simulate`` replays it and returns the account values as a frame:

.. code-block:: python

   import pandas as pd

   from ws4.sim.engine import Simulator

   schedule = pd.DataFrame({"block_id": [1], "treatment": ["CC"], "period": [0]})
   values = Simulator.from_dataset(dataset).simulate(schedule, 5)
   print(values.head(4).to_string(index=False))

.. code-block:: text

    year        account  value
       0 feature.Volume  340.0
       0 product.Volume  360.0
       1 feature.Volume  360.0
       2 feature.Volume  380.0

That is the figure from the walkthrough: clearing block 1 at year 0 moves its 3.0 ha from the natural
track to the managed track, leaving ``2.0 * 170 = 340``.

Search for a schedule
---------------------

``Optimizer.run`` performs the search the ``ws4 optimize`` command performs and writes the same run
directory. Targets come from a YAML file, exactly as on the command line:

.. code-block:: python

   from ws4.opt.engine import OptimizeConfig, Optimizer

   targets_path = Path("tmp/getting-started/targets.yaml")   # write it as in :doc:`quickstart`
   optimizer = Optimizer.from_dataset(
       dataset,
       OptimizeConfig(years=5, iterations=200, seed=1, targets_path=str(targets_path)),
   )
   summary = optimizer.run(Path("tmp/getting-started/api-run"))
   print({key: summary[key] for key in ("incumbent_objective", "iterations", "seed", "status")})

.. code-block:: text

   {'incumbent_objective': 0.0, 'iterations': 200, 'seed': 1, 'status': 'ok'}

The run directory holds ``schedule.csv``, ``summary.json``, the incumbent's account and product
values, the target report, and ``telemetry.jsonl``.

Drive the search yourself
-------------------------

The search is priced by **exact per-move deltas** rather than by re-simulating, which is what makes
a long run affordable. That evaluator is public, so a script can hold targets in memory, drive the
solver, and read the running state between steps:

.. code-block:: python

   import random

   from ws4.opt.objective import Target
   from ws4.opt.solvers import solve_sa_delta

   candidates = optimizer.candidates()
   evaluator = optimizer.delta_evaluator([Target("feature.Volume", 0, minimum=700.0)])
   best, objective = solve_sa_delta(
       evaluator,
       random.Random(1),
       iterations=200,
       temperature=1000.0,
       cooling=0.99,
       candidates=candidates,
       registry=optimizer.registry,
   )
   print("objective:", objective, " blocks scheduled:", len(best))

.. code-block:: text

   objective: 0.0  blocks scheduled: 0

.. note::

   An empty schedule is the right answer here: leaving the two-block stand alone holds
   ``feature.Volume`` at 700, which meets the floor, so nothing can improve on a penalty of zero.

Where to go next
----------------

- :doc:`../howto/automate-a-study` — sweeps, seeds, and reading results back, which is what the API
  is for.
- :doc:`../howto/write-targets` and :doc:`../howto/even-flow` — the target vocabulary, in YAML and
  as ``Target`` objects.
- :doc:`../reference/optimizer` — the objective, the operators, and the search stack.
