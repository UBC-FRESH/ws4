Resilience metrics
==================

WS4 reports three descriptive resilience families from the state it already
simulates. They are accounts, not constraints or objective terms, and they add no
spatial model. See :doc:`spatial` for the patch and spread accounts they reuse.

Definitions
-----------

Connectivity
    ``resilience.connectivity.largest_component``
        Level, hectares. Area of the largest connected set of untreated blocks
        over the full block topology.
    ``resilience.connectivity.percolation_reach``
        Level, hectares. Area-weighted mean untreated component area,
        ``sum(area**2) / sum(area)``.
    ``resilience.connectivity.component_count``
        Level, count. Number of untreated components.
    ``resilience.connectivity.untreated_area``
        Level, hectares. Total untreated area in the graph.

    This is an undirected topology measure. It is not the directional
    ``spread`` account: no wind bearing or cone is applied. The existing
    ``spread_metrics.csv`` remains the place for the barrier/fire-direction
    question.

Age-class diversity
    ``resilience.age_class.shannon``
        Level, index. Shannon diversity of fragment area across 20-year age
        classes.
    ``resilience.age_class.evenness``
        Level, index 0-1. Shannon evenness across occupied classes.
    ``resilience.age_class.count``
        Level, count. Number of occupied 20-year classes.

    Ages are the simulator's current fragment ages, including the age reset from
    a treatment. The width is metadata, not a hidden constant.

Fragmentation
    ``resilience.fragmentation.patch_count``
        Flow, count. Number of opening patches created in the current year.
    ``resilience.fragmentation.mean_patch_area``
        Flow, hectares. Mean opening-patch area in the current year.
    ``resilience.fragmentation.largest_patch_area``
        Flow, hectares. Largest opening-patch area in the current year.
    ``resilience.fragmentation.area``
        Flow, hectares. Area treated in the current year.

    Fragmentation uses the same connected-component definition as the existing
    patch metrics. An opening is current-year treated blocks, not cumulative
    disturbance. Because these are flows, the report shows their total, mean,
    and peak; a final-year value of zero simply means no opening was created in
    that year.

Using it
--------

.. code-block:: bash

   ws4 simulate --dataset build/estate --schedule schedule.csv --years 10 \
     --topology examples/estate/topology.csv --resilience --out runs/compact

   ws4 resilience compare --run-a runs/compact --run-b runs/scattered \
     --output runs/resilience_comparison.csv

   ws4 report --run runs/compact --targets targets.yaml

The run writes:

``resilience_metrics.csv``
    ``offset,account,value`` for every account and year.
``resilience_metadata.json``
    Schema, topology source, age-class width, patch breaks, metric definitions,
    units, semantics, and caveat.
``report_resilience.csv``
    Written by ``ws4 report``: definitions, units, semantics, baseline/final,
    total/mean/peak, and the caveat.

``ws4 resilience compare`` writes one row per account with each run's baseline,
final, mean, total, peak, and change, plus the unit, semantics, and a
``same_direction`` flag. For flow accounts the flag compares totals; for level
accounts it compares changes.

The Python entry points are :func:`ws4.resilience.compute_resilience`,
:func:`ws4.resilience.connectivity_metrics`,
:func:`ws4.resilience.age_class_diversity`,
:func:`ws4.resilience.fragmentation_metrics`, and
:func:`ws4.resilience.compare_resilience_runs`.

Pilot and non-redundancy
------------------------

``examples/resilience_pilot`` runs two schedules over the sample estate. At
offset 0 the compact schedule opens one patch (42.9 ha); the scattered schedule
opens four isolated patches (38.6 ha total). The age-class count is the same (5)
for both, while the fragmentation accounts differ. That is the redundancy check:
not every metric is a restatement of the same pattern.

The existing spread accounts and the connectivity account are related but not
identical. Connectivity uses the full undirected topology; spread uses a bearing
and a cone and reports the fuel body a fire could reach. Neither is a fire model.

Caveats
-------

- Topology and block aggregation set the scale. A block-level graph cannot see
  within-block structure.
- Connectivity is an undirected graph measure, not a species-connectivity model.
- Age-class diversity depends on the declared width (20 years by default); the
  metadata records it.
- Fragmentation is current-year opening geometry. It does not model regrowth,
  edge effects, or cumulative disturbance.
- The metrics are descriptive and are not in the objective or constraints.
