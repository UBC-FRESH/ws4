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

Initial live biomass comes from ``--biomass-source``:

- ``auto`` uses a compiled feature label containing ``biomass`` when one exists, otherwise
  converts the track volume curve with ``--wood-density`` and ``--biomass-expansion``.
- ``feature`` requires a compiled biomass curve; ``--biomass-label`` selects it exactly.
- ``volume`` always uses the track volume conversion.
- ``fixed`` uses ``--initial-biomass`` (default 100 t/ha).

The default conversion is 0.5 t/m3 wood density and a 1.5 biomass expansion factor. These are
explicit provisional coefficients, not a hidden calibration. Initial fuel remains zero by
default; succession adds fuel.

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

Optimize a schedule
-------------------

``ws4 ecosystem optimize`` runs the process hill-climb against a targets file and writes the
best schedule in the estate input format:

.. code-block:: bash

   ws4 ecosystem optimize \
     --dataset build/tsa24 \
     --targets targets.yaml \
     --output runs/process-opt \
     --topology topology.csv \
     --years 5 \
     --max-iterations 2 \
     --max-blocks 200

The output contains ``process_optimization.json``, the search trace, ``schedule.csv``,
``block_fragments.csv``, the best evaluation, and the best event log. The grammar uses every
compiled treatment and every block in the selected dataset, with an empty schedule as the
default starting point; pass ``--initial-schedule`` to start elsewhere.

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
