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

The P165.1 observed-registry gate is currently **blocked** for depth: 0 fully ready depth
cases. Two depth cases are usable with limits. The P165.3 daily breadth coverage gate passes
separately, as described below.

Daily breadth corpus
--------------------

P165.3 adds an observation-only daily breadth corpus from CFSDS 2003, 2009, and 2023:

- 20 ready cases;
- 3 years;
- 4 ecozones;
- final areas from 510 to 49,766 ha;
- growth durations from 2 to 75 days.

The breadth coverage gate **passes**. This is a corpus and integrity result, not hourly/FBP
model skill. The cases are inside one FireSTARR fuel/terrain tile (UTM 11N), use daily weather,
and have satellite-derived perimeters. No WS4 simulation was run.

See ``notes/reports/p165-daily-corpus.md`` and
``notes/reports/p165-daily-corpus.json``.


Limits
------

- Daily CFSDS cases are not hourly/FBP validation.
- Model-only outputs are not observations.
- Missing data is recorded, not inferred.
- The corpus does not resume P164.3 calibration until the gate passes.
