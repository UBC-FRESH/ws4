Running a carbon study
======================

This guide takes a compiled WS4 dataset and a FEMIC carbon package through a baseline
carbon run, an optional simulation merge, a carbon-aware optimization, and optional
fertilization. It is the task path; the package tables, failure codes, and engine boundary
are in :doc:`../reference/carbon`.

Before you start
----------------

You need three things:

* A **compiled WS4 dataset** that passes ``ws4 validate``. The package joins to the
  dataset by exact ``tracks.name``; a name that differs by one state token is a hard
  failure.
* A **FEMIC carbon package**. The producer guide is `FEMIC carbon package export
  <https://ubc-fresh.github.io/femic/guides/carbon-export.html>`_. The package is static
  inventory plus crosswalks; it contains no WS4 schedule.
* The optional carbon engine: ``python -m pip install -e ".[carbon]"``. A core WS4
  install does not import ``libcbm``.

Carbon is a sidecar, not a new dataset column. The compiled dataset remains the runtime
contract, and the package can be replaced without rebuilding the matrix.

1. Validate the package
-----------------------

Run the producer-side validator once, then let WS4 load it on the first carbon command:

.. code-block:: bash

   femic carbon validate output/carbon/tsa24

   ws4 carbon \
     --dataset output/ws4/tsa24/compiled \
     --package output/carbon/tsa24 \
     --schedule schedules/baseline.csv \
     --out out/carbon/tsa24-baseline \
     --audit-sit

The loader checks the manifest, table hashes, units, classifiers, inventory, yield rows,
and every track's declared eco boundary. Keep the package id, fingerprint, and CBM
defaults hash in the study record.

2. Read the baseline outputs
----------------------------

A carbon-only run writes:

* ``carbon_pools.csv`` and ``carbon_pools_long.csv``
* ``carbon_flux.csv`` and ``carbon_flux_long.csv``
* ``carbon_accounts.csv``
* ``carbon_manifest.json``
* ``carbon_sit/`` when ``--audit-sit`` is set

Check the manifest first. It records the package id and fingerprint, the dataset and
schedule hashes, the engine version, and the CBM defaults version and hash. Then read the
``carbon.ecosystem.total`` and ``carbon.stock.change`` series. ``--density`` writes
``tC/ha`` instead of ``tC`` when you want a per-hectare view.

3. Merge carbon into a simulation run
-------------------------------------

Use ``--merge-into`` when the schedule already has a simulation run and you want one
report:

.. code-block:: bash

   ws4 carbon \
     --dataset output/ws4/tsa24/compiled \
     --package output/carbon/tsa24 \
     --schedule out/ws4/tsa24-baseline/schedule.csv \
     --out out/carbon/tsa24-baseline \
     --merge-into out/ws4/tsa24-baseline

``carbon.*`` and, when fertilization is configured, ``fertilization.*`` rows are replaced
so a rerun is idempotent. Other accounts are preserved.

4. Add a carbon target to the optimizer
---------------------------------------

A carbon target uses the same weighted-goal objective, periods, normalization, and
priority tiers as any other account. Pass the package so the target can be priced:

.. code-block:: bash

   ws4 optimize \
     --dataset output/ws4/tsa24/compiled \
     --targets targets/tsa24-carbon.yaml \
     --carbon-package output/carbon/tsa24 \
     --out out/ws4/tsa24-carbon-search

A minimal target is a ceiling on ecosystem carbon in one period:

.. code-block:: yaml

   targets:
     - account: carbon.ecosystem.total
       period: 5
       maximum: 134000
       period_width: 1

The block-level ledger is area-additive and caches per-block trajectories. It is the
search path, not the final authority: re-run the winning schedule with ``ws4 carbon`` and
record the exact result. When several blocks share a source track, a full-schedule event
is allocated at the track/classifier-set level; the ledger is block-exact, so the two can
differ slightly after disturbances. Always verify the final schedule with the exact run.

5. Add fertilization
--------------------

Fertilization has two modes. **Curve mode** is the materialized path: produce a public
TIPSY response curve with FEMIC, then declare it as an application in the YAML.

.. code-block:: bash

   femic carbon fertilization-curve \
     --package output/carbon/tsa24 \
     --track "AU(2401005)+IFM(unmanaged)+ORIGIN(natural)+SILV_STATE(baseline)+RETENTION(0)+treatment()" \
     --species SW \
     --site-index 20 \
     --response-age 40 \
     --fertilization-config config/carbon/fertilization.bc.yaml \
     --out output/carbon/tsa24/fertilized/f1-2401005.csv

.. code-block:: yaml

   applications:
     - treatment: f1
       source_track: "AU(2401005)+IFM(unmanaged)+ORIGIN(natural)+SILV_STATE(baseline)+RETENTION(0)+treatment()"
       target_track: "AU(2401005)+IFM(unmanaged)+ORIGIN(natural)+SILV_STATE(baseline)+RETENTION(0)+treatment()+F1"
       curve: output/carbon/tsa24/fertilized/f1-2401005.csv

Then pass the config to either runtime:

.. code-block:: bash

   ws4 carbon \
     --dataset output/ws4/tsa24/compiled \
     --package output/carbon/tsa24 \
     --schedule schedules/fertilization.csv \
     --fertilization-config config/carbon/fertilization.bc.yaml \
     --out out/carbon/tsa24-fertilized

   ws4 optimize \
     --dataset output/ws4/tsa24/compiled \
     --targets targets/tsa24-carbon.yaml \
     --carbon-package output/carbon/tsa24 \
     --carbon-fertilization config/carbon/fertilization.bc.yaml \
     --out out/ws4/tsa24-fertilized-search

Curve mode preserves stand age across the source and target tracks, adds a recovery event
after the response window, and records the gas accounts. Without ``applications``, WS4
falls back to a scalar growth multiplier; use that only for calibration or a quick run,
not for a species/site-specific claim. The public TIPSY response and emissions factors
are documented in `FEMIC fertilization audit
<https://ubc-fresh.github.io/femic/guides/fertilization-audit.html>`_.

6. Add the HWP lifecycle and system balance
-------------------------------------------

Ecosystem carbon is only one part of the forest-sector balance. Add an HWP configuration
to count product storage, end-of-life emissions, and displacement:

.. code-block:: bash

   ws4 carbon \
     --dataset output/ws4/tsa24/compiled \
     --package output/carbon/tsa24 \
     --schedule schedules/baseline.csv \
     --hwp-config config/carbon/hwp.bc.yaml \
     --out out/carbon/tsa24-hwp

The public config in FEMIC uses the corrected ``fresh-yan`` conventions: 85% utilized
fibre, a 50/50 paper/solid split, exact half-life survival, and a displacement credit on
solid-wood inflow. Those parameters are scenario assumptions, not a single calibrated
truth. Run a grid over plausible half-lives and displacement factors.

The new accounts include ``carbon.hwp.total``, ``carbon.co2e.hwp.eol``,
``carbon.co2e.displacement``, ``carbon.system.total``, and
``carbon.co2e.system.emissions``. A system target needs the same config on the optimizer:

.. code-block:: bash

   ws4 optimize \
     --dataset output/ws4/tsa24/compiled \
     --targets targets/tsa24-system.yaml \
     --carbon-package output/carbon/tsa24 \
     --carbon-hwp config/carbon/hwp.bc.yaml \
     --out out/ws4/tsa24-system-search

See `FEMIC HWP lifecycle <https://ubc-fresh.github.io/femic/guides/hwp-lifecycle.html>`_
for the equations and boundaries.

7. Compile carbon yield curves
------------------------------

``ws4 carbon-curves`` runs one stand per track through libcbm and writes stock and
emission yield curves. Managed curves use the public simulated-clearcut method, so age 0
is the post-harvest state rather than a spun-up reset.

.. code-block:: bash

   ws4 carbon-curves \
     --dataset output/ws4/tsa24/compiled \
     --package output/carbon/tsa24 \
     --out out/carbon/tsa24-curves \
     --rotation-age 120 \
     --years 300 \
     --mode cycle

The output is ``carbon_curves.csv`` plus ``carbon_curves_manifest.json``. Use the curves
for a reduced LP or external scenario formulation; label a curve-based result as a
surrogate and verify the final schedule with the exact ``ws4 carbon`` run.

8. Read a GCBM result (optional bridge)
---------------------------------------

``ws4 gcbm`` reads a raw GCBM results database without FLINT, Wine, or the GCBM runtime:

.. code-block:: bash

   ws4 gcbm --results gcbm_output.db --out out/gcbm/tsa46 \
     --compare-carbon out/carbon/tsa46-baseline

This is a **format and bridge** check. GCBM and libcbm are separate CFS CBM
implementations, and WS4 does not target numerical equality between them. The FEMIC
walltowall export is the producer side; see :doc:`../reference/carbon` and
:doc:`../guides/limitations-and-boundaries` before interpreting a comparison.

Common problems
---------------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Symptom
     - What it usually means
   * - ``ModuleNotFoundError: libcbm``
     - The carbon engine is optional. Install ``ws4[carbon]``.
   * - ``CARBON-UNMATCHED-TRACK``
     - The dataset and package disagree on a track name. Rebuild the package against the
       compiled dataset; do not rename a dataset track by hand.
   * - CBM defaults hash mismatch
     - The package and installed database differ. Rebuild the package, or use
       ``--allow-defaults-mismatch`` only for an explicit comparison and record it.
   * - A carbon target is rejected before search
     - Add ``--carbon-package``. A carbon target without a package is a configuration
       error, not a zero-carbon result.
   * - An HWP or system target is rejected before search
     - Add ``--carbon-hwp <yaml>``. The system accounts are not produced without the
       lifecycle assumptions.
   * - Ledger and exact run differ after disturbance
     - The full run allocates events at track/classifier-set level. Use the exact
       ``ws4 carbon`` result as the reported outcome.
   * - GCBM comparison is empty
     - Check the GCBM 2.5.x schema and whether the run has the same footprint. The reader
       is tabular; it does not map GCBM rasters to WS4 blocks.

Next
----

* :doc:`../reference/carbon` — package tables, SIT compilation, optimizer ledger,
  fertilization, HWP lifecycle, curve method, failure codes, and the GCBM boundary.
* :doc:`../guides/limitations-and-boundaries` — carbon runtime and evidence caveats.
* `FEMIC carbon package workflow
  <https://ubc-fresh.github.io/femic/guides/carbon-overview.html>`_ — producer-side
  export, validation, and crosswalk provenance.
* `FEMIC HWP lifecycle
  <https://ubc-fresh.github.io/femic/guides/hwp-lifecycle.html>`_ — public product
  assumptions and their boundaries.
