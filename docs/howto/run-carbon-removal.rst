Run a removal-effect carbon search
===================================

``ws4 carbon-removal`` prices a binary keep/remove decision once, then searches
the bits on the GPU. It is for carbon analyses where the global removal pattern
matters more than local treatment shifts.

The decision is:

- ``1`` — keep the block's current treatment chain;
- ``0`` — leave the block untreated.

The effect table is exact: each block's current-chain delta comes from the same
:class:`ws4.carbon.ledger.CarbonLedger` used by the optimizer. The population
search is an accelerator; run the winning schedule through ``ws4 carbon`` before
reporting it.

Command
-------

.. code-block:: bash

   ws4 carbon-removal \
     --dataset /path/to/compiled-dataset \
     --package /path/to/femic-carbon-package \
     --schedule /path/to/initial.schedule.csv \
     --targets /path/to/targets.yaml \
     --years 50 \
     --hwp-config config/carbon/hwp.bc.yaml \
     --workers 64 \
     --population 2048 \
     --generations 3000 \
     --seed 1 \
     --out runs/carbon-removal

The command writes:

- ``schedule.csv`` — the winning keep/remove schedule;
- ``summary.json`` — build/search times and block counts;
- ``report_targets.csv`` — exact target values (unless ``--no-verify``);
- ``account_values.csv`` — exact account values.

Target contract
---------------

The removal path supports level targets, including accumulating product
accounts. Flow targets are rejected. Each target's cells are read with the same
period semantics as the optimizer: product accounts sum their period, other
accounts read the period end.

Performance
-----------

The effect table is the cost. It is parallel across exact stand states. Once the
rows exist, the CUDA population search is effectively free. For 5,000 TSA41
blocks with the current ``CC@0`` chain and HWP:

- 156 s table build with 64 workers;
- 2.5 s population search;
- 187 s total including exact replay.

Without CUDA the same search falls back to a NumPy implementation. It is slower
and should be used only for small cases or tests.

Example
-------

See ``notes/reports/carbon-tsa41-5k-removal-ga.md`` for the 5,000-block result:
1,604 blocks removed, yield 9,500,005 m3, exact cumulative emissions
5,692,533 tCO2e against a 12,816,648 baseline.
