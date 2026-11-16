Tree mortality
==============

Purpose
-------

This page records the generic FOFEM crown-scorch mortality equation and its validation against
the public Fire and Tree Mortality Database (FTM). It is a screening model, not a BC-calibrated
mortality model.

Equation
--------

For DBH at least 2.54 cm:

``Pm = 1 / (1 + exp(-1.941 - 6.316 * (1 - exp(-BT)) + 0.000535 * CS^2))``

- ``Pm`` is the probability of mortality within three years;
- ``BT`` is single bark thickness in inches, ``coefficient * DBH_in``;
- ``CS`` is crown volume scorched in percent.

Species bark coefficients come from the FTM species table. Supported BC-relevant codes include
PICO, PSME, PIPO, LAOC, ABLA, ABCO, PIEN, PIMA, and PIGL.

Validation
----------

Data: FTM 2nd edition, 2022 release. Rows require a supported species, valid DBH, crown volume
scorched, and three-year status. The model is fixed; the validation split is by dataset.

.. list-table::
   :header-rows: 1

   * - Subset
     - n
     - Prevalence
     - AUC
     - Brier
     - Brier skill
   * - All
     - 65,663
     - 0.375
     - 0.882
     - 0.159
     - 0.324
   * - Dataset split, train
     - 49,915
     - 0.393
     - 0.880
     - 0.175
     - 0.266
   * - Dataset split, validation
     - 15,748
     - 0.318
     - 0.912
     - 0.105
     - 0.514
   * - BC-relevant conifers
     - 65,413
     - 0.375
     - 0.882
     - 0.158
     - 0.325

Decision
--------

**Go** for screening tree-mortality probabilities. The model discriminates better than a
constant baseline on held-out FTM datasets.

**No-go** for operational or BC-specific use: the data are mostly US species and fires, the
generic equation is not species- or region-calibrated, and the 3D scorched/torched/consumed
classes remain visual states, not mortality observations.

The full report is ``notes/reports/tree-mortality.md``.

Fire-scene integration
----------------------

The scene viewer adds a per-tree ``mortality_probability`` for species with a bark coefficient.
It estimates crown volume scorched from local flame length and crown geometry, then applies the
FOFEM equation. Unsupported species return ``None``.

The viewer shows a mean **screening mortality** statistic. This is separate from the
unburned/scorched/torched/consumed visual classes, which remain visual states rather than
mortality observations.
