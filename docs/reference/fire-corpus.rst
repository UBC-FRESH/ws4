Public fire corpus
==================

Purpose
-------

Two observed fires are enough to exercise a code path, not enough to estimate model skill. The
public fire corpus is a tiered admission contract for observed event evidence. It keeps hourly
FBP cases, daily CFSDS cases, and model-only outputs separate.

The design note is ``notes/design/ws4-public-fire-corpus.md``. The machine-readable registry is
``ws4.fire.corpus``.

Tiers
-----

Depth - hourly/FBP
   Observed perimeter, hourly weather, ignition, FBP fuel, terrain, provenance, and documented
   licence terms. Used for the hourly FBP path.

Breadth - daily CFSDS
   Daily progression, daily weather, fuel, terrain, provenance, and documented licence terms.
   Used for a cross-fire event distribution, not hourly validation.

Model-only
   FireSTARR, BurnP3, or other model output. Never counted as an observed fire.

Status
------

- ``ready`` - all required inputs are present.
- ``ready_with_limit`` - usable, with a documented limitation.
- ``candidate`` - potentially usable, but inputs or provenance are incomplete.
- ``blocked`` - needs a missing adapter or dataset.
- ``rejected`` - duplicate or otherwise inadmissible.
- ``model_only`` - model output, not observed evidence.

Admission gate
--------------

The observed-corpus gate requires:

- **3** fully ready independent depth cases;
- **20** fully ready independent breadth cases.

``ready_with_limit`` cases are reported separately and do not count toward the minimum.

Current inventory
-----------------

.. list-table::
   :header-rows: 1

   * - Case
     - Tier
     - Status
     - Missing inputs
   * - Dogrib Scenario 2b
     - depth
     - ready_with_limit
     - licence documentation
   * - Hay River 2023_320
     - depth
     - ready_with_limit
     - none
   * - CFSDS 2023_321
     - breadth
     - candidate
     - not acquired
   * - CFSDS 2023_320 daily
     - breadth
     - rejected duplicate
     - none
   * - WildfireAV US
     - depth
     - blocked
     - ignition, FBP fuel, licence
   * - FireSTARR
     - model-only
     - model_only
     - not applicable
   * - BurnP3
     - model-only
     - model_only
     - not applicable

The gate is currently **blocked**: 0 fully ready depth cases and 0 fully ready breadth cases.
Two depth cases are usable with limits.

Limits
------

- Daily CFSDS cases are not hourly/FBP validation.
- Model-only outputs are not observations.
- Missing data is recorded, not inferred.
- The corpus does not resume P164.3 calibration until the gate passes.
