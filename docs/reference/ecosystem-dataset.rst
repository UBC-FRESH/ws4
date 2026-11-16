.. _ecosystem-dataset:

Run a process scenario from a compiled dataset
==============================================

``ws4 ecosystem run-dataset`` connects the compiled management dataset to the annual process
engine. It reads ``fragments``, ``tracks``, ``features``, ``curves``, and ``treatments``, builds
one initial cohort per fragment, attaches the compiled track curves, and runs a schedule through
fire, LANDIS succession, management, salvage, and regeneration.

.. code-block:: bash

   ws4 ecosystem run-dataset \
     --dataset build/tsa24 \
     --schedule schedule.csv \
     --output runs/process \
     --topology topology.csv \
     --years 5 \
     --max-blocks 200 \
     --ignition-rate 0.01 \
     --establishment-probability 0.25 \
     --seed 1

The output directory contains:

- ``process_evaluation.json``: final accounts and event counts.
- ``process_evaluation_accounts.csv`` and ``process_evaluation_values.csv``.
- ``process_events.json``: the replayable event log.
- ``process_dataset.json``: the loaded fragment, block, curve, species, and seed metadata.

Assumptions
-----------

The compiled dataset has no biomass column. The command supplies initial live biomass (default
100 t/ha) and initial fuel (default zero; succession adds fuel). Pass ``--initial-biomass`` and
``--initial-fuel`` when the run has better values.

Species are read from the compiled ``feature.SpeciesProp.*`` curves: each fragment is split
into species cohorts whose area fractions come from the curves at its current age. ``--species``
is the fallback when a track has no proportion curve, and ``--no-species-composition`` uses that
fallback everywhere. The default aliases map common BC codes to the published LANDIS reference
traits; pass an explicit ``species_traits`` mapping to ``ProcessDataset.from_directory`` to
override them.

The default curve selection uses ``feature.Volume`` when present, then the managed or unmanaged
``feature.Yield.*.Total`` label that matches the track name. Use ``--volume-label`` to force one
feature label.

Pass ``--topology`` with a block edge list (``src_block,dst_block,distance_m``) to map block
adjacency onto fragment fire edges. Without it, fire ignites independently per fragment and does
not spread.

Succession runs in a vectorized landscape batch by default: one event per year applies the
published LANDIS kernels over every fragment at once. Use ``--no-batch-succession`` to emit one
succession event per fragment for debugging or event-log comparison. ``--max-blocks`` bounds a
pilot run; the batch path handles a full estate-scale dataset.

The Python API carries the same state into the process search and optimization modules:

.. code-block:: python

   prepared = ProcessDataset.from_directory(dataset, topology=topology)
   result = prepared.search(
       candidates,
       horizon_years=5,
       targets=targets,
       fire=FireConfig(ignition_rate_per_fragment_year=0.01),
       seed=1,
   )
   best = result.best.evaluation
