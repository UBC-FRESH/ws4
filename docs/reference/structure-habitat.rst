Structure habitat index
=======================

WS4 computes the published **forest structure habitat index** from Coops et al.
(2016), *A forest structure habitat index based on airborne laser scanning data*,
Ecological Indicators 67:346-357, doi:10.1016/j.ecolind.2016.02.057.

Definition
----------

The index has three equal components. It is **not a weighted scalar**: the paper
publishes a three-band class composite. The components are:

``height_p95_m``
    95th percentile of first-return heights, in metres.
``cover_gt_1_37_pct``
    Percentage of first returns above 1.37 m.
``complexity_sd_gt_1_37_m``
    Standard deviation of first-return heights above 1.37 m, in metres.

The published class breaks are 10 and 20 m for height, 33% and 66% for cover,
and 3 and 5 m for complexity. A value exactly on a break is assigned to the lower
class. Each block receives ``height_class``, ``cover_class`` and
``complexity_class`` (0 low, 1 medium, 2 high), a 0-26 ``class_code``, and a
label such as ``H1-C2-K0``.

There are no weights to confirm or tune. WS4 records the equal-component
statement in the provenance rather than inventing coefficients.

Ingest
------

.. code-block:: bash

   ws4 shi ingest \
     --metrics structure_metrics.csv \
     --output structure_habitat_stand.csv \
     --metadata structure_habitat_metadata.json \
     --source-version "ALS-2025-fixture"

The input must contain ``block_id`` and the three exact metric columns. Missing
or non-finite values are an error; they are never imputed. The output is a stand
table plus a versioned metadata file with the index version, citation,
thresholds, boundary rule, weights statement, and required metrics.

Coverage
--------

.. code-block:: bash

   ws4 shi diagnose --metrics structure_metrics.csv
   ws4 shi diagnose --canopy-structure canopy__05__canopy_structure.json

A ``ws4 lidar canopy`` fragment or block mapping can be passed to ``--metrics``;
the diagnostic reports its ``chm_*`` fields as proxies and refuses the index. The
diagnostic reports ``index_computable``, ``present``, ``missing``, and
``proxies``. CHM fields are named as proxies but are not substituted:

- ``chm_p95`` is CHM-derived, not first-return P95.
- ``chm_cover_ge_2`` uses a 2 m threshold, not 1.37 m.
- No first-return height standard deviation field exists in the current FEMIC
  canopy summary.

The current TFL 6 **FEMIC bundle** (`lidarbc-995fb1f771f4d7fe`) exposes the CHM
products only, so a diagnostic of its canopy summary reports
``index_computable: false``. That is a bundle-coverage result, not a zero index.

The underlying LidarBC point clouds are publicly downloadable. The TFL 6
real-data pilot in ``examples/structure_habitat_tfl6`` uses the two public
OP24BMRS001 2024 LAZ tiles over the 1 km AOI, normalizes first returns with the
FEMIC 1 m DEM, and computes the exact metrics for the seven VRI blocks. The
bundle omission is a materialization gap, not a data-access blocker.

Account
-------

With a structure stand table and metadata, ``ws4 simulate`` records:

``feature.SHI.height``
    Area-weighted mean height, unit ``m``.
``feature.SHI.cover``
    Area-weighted mean cover, unit ``%``.
``feature.SHI.complexity``
    Area-weighted mean complexity, unit ``m``.
``feature.SHI.area``
    Surviving area, unit ``ha``.
``feature.SHI.<component>.<class>_area``
    Area in each low/medium/high class, unit ``ha``.

Offset -1 is the whole dataset. A treated block leaves the account for the rest
of the run. The run writes ``structure_habitat_values.csv``,
``structure_habitat_landscape.csv``, and ``structure_habitat_metadata.json``.
``ws4 report`` adds ``report_structure_habitat.csv`` with baseline, final,
change, unit, source, index version, citation, and the caveat.

DHI comparison
--------------

.. code-block:: bash

   ws4 shi compare \
     --structure structure_habitat_stand.csv \
     --dhi-values dhi_values.csv \
     --output dhi_comparison.csv

The comparison joins on ``block_id`` and reports Pearson's r, Spearman's rho,
sample size, direction, and strength for each structure component and DHI band.
It is exploratory: there is no significance test, and a small common sample is
labelled ``insufficient common blocks``. Negative or weak agreement is recorded,
not filtered out.

The synthetic four-block fixture is not evidence about the TFL 6 landscape. The
real TFL 6 pilot has seven VRI blocks: area-weighted mean height 22.95 m, cover
69.82%, complexity 6.86 m. Its DHI comparison is exploratory: structure height
and cover show strong positive rank agreement with DHI variation (Spearman 0.67
and 0.80), while most other pairs are weak or negative. Seven blocks are not a
validation dataset.

Caveats
-------

- The index is a structural descriptor, not a species observation, a habitat
  suitability model, or a causal treatment effect.
- The published index uses first-return point-cloud metrics. CHM-derived
  height and cover are not the same quantities.
- If the exact metrics are absent, the index is unavailable. Do not replace it
  with a proxy and call it the published index.
- Class boundaries are descriptive; do not treat a class as a conservation
  priority.
- The current example metrics are synthetic; the real TFL 6 bundle is used for
  the coverage gap only.
