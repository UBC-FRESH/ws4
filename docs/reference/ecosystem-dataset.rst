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

The compiled dataset has no species or biomass column. The command supplies a provisional
species label (default ``PL``), initial live biomass (default 100 t/ha), and initial fuel
(default zero; succession adds fuel). Pass ``--species``, ``--initial-biomass``, and
``--initial-fuel`` when the run has better values.

The default curve selection uses ``feature.Volume`` when present, then the managed or unmanaged
``feature.Yield.*.Total`` label that matches the track name. Use ``--volume-label`` to force one
feature label.

Pass ``--topology`` with a block edge list (``src_block,dst_block,distance_m``) to map block
adjacency onto fragment fire edges. Without it, fire ignites independently per fragment and does
not spread. ``--max-blocks`` bounds a pilot run; a full estate-scale dataset needs the vectorized
path before it is practical.
