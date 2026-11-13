Schedule management bridge
==========================

Purpose
-------

``ws4.ecosystem.management`` maps a block-level schedule to the ecological cohort state. It
emits controlled harvest events in the treatment phase and applies a simplified removal
transition, so later succession, fire, and regeneration see the harvested state.

Inputs
------

- ``load_schedule`` reads ``block_id,treatment,offset``.
- ``load_block_fragments`` reads ``block_id,fragment_id``.
- ``ScheduleSource`` validates the schedule, mapping, harvest fraction, and scenario id.

Harvest transition
------------------

For each scheduled fragment, the source removes ``area_fraction × harvest_fraction`` from every
live cohort. The survivor remains in the original cohort. A bare age-zero cohort with the same
species and zero biomass/fuel/snag receives the removed fraction. Total fragment area is
conserved.

This is a clearcut-like bridge, not the compiled dataset's full treatment semantics.

Integration
-----------

``ProcessEnsembleConfig.management`` accepts a ``DecisionSource``. The ensemble runs it in the
treatment phase before salvage.

Limits
------

- No retention trees, product curves, or treatment-specific track transitions.
- Block-level schedule with an explicit fragment mapping.
- No optimizer coupling yet.
- The volume bridge remains provisional.
