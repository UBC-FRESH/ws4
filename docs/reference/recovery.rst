Post-fire recovery
==================

WS4 can consume the public NTEMS post-disturbance recovery layer and attach a
recovery status to blocks. The layer is a **spectral recovery** product, not a
tree-survival or stocking survey.

Source
------

- Canada Forest Post-Disturbance Recovery Rate, fire layer.
- Natural Resources Canada / NTEMS, 30 m, EPSG:3978.
- Wildfire disturbance 1986-2012; observation 1985-2017.
- Classes: `1` faster than the ecozonal baseline, `2` slower, `3` not recovered
  by the end of 2017.
- Open Government Licence - Canada.
- Citation: White et al. 2022, *Mapping, validating, and interpreting
  spatio-temporal trends in post-disturbance forest recovery*, Remote Sensing of
  Environment 271, 112904.

Contract
--------

``ws4 recovery ingest`` samples the raster at block polygons and writes:

``regen_status.csv``
    ``block_id, area_ha, burned_area_ha, valid_pixels, faster_fraction,
    slower_fraction, not_recovered_fraction, dominant_status,
    dominant_fraction``.
``recovery_metadata.json``
    Source version, disturbance/observation windows, resolution, CRS, licence,
    citation, class map, and notes.

A block with no class 1-3 pixels is ``outside_footprint``. That is not a failure
status and is never imputed as one. The dominant status is the largest class
fraction; tied classes are resolved deterministically by the class order.

``regen_status_summary.csv`` groups blocks, total area, and burned recovery area
by dominant status.

Commands
--------

.. code-block:: bash

   ws4 recovery ingest \
     --raster recovery_tsa46_5km.tif \
     --blocks blocks.geojson \
     --block-id-field FEATURE_ID \
     --output regen_status.csv \
     --metadata recovery_metadata.json \
     --summary regen_status_summary.csv \
     --source-version "NTEMS post-disturbance recovery rate / White et al. 2022"

Pilot
-----

``examples/recovery_tsa23`` applies the layer to the TSA 23 instance, which is
the fire-oriented estate. The 30 m subset covers 102,128 blocks and 988,816 ha.

- **1,555 blocks** are in the fire-recovery footprint.
- **1,497 blocks are not recovered**: 21,948 ha, 5,727 ha burned.
- **58 blocks are slower**: 745 ha, 176 ha burned.
- No block is dominated by faster recovery.
- 100,573 blocks are ``outside_footprint``, not failures.
- The existing 2,000-row baseline schedule contains **29 not-recovered blocks**
  (212 ha) and 2 slower blocks (8 ha); 1,969 scheduled blocks are outside the
  footprint.

Using the 44,388-block `ft_warm` schedule, 411 not-recovered blocks (6,048 ha)
are scheduled. Deferring those treatments changes harvested volume from
138.50M to 137.12M m3 (-1.00%) and treated area by -3,579 (-1.13%). Deferring
both not-recovered and slower blocks changes volume by -1.03%. The block area is
larger than the treated-area change because some scheduled treatments are not
operable. This is a scenario result; the layer is not yet a constraint or
objective term.

The earlier ``examples/recovery_tsa46`` is retained as a 5 km mask-based smoke
test.

Caveats
-------

- Spectral recovery is not survival or regeneration success.
- The observation window ends in 2017; recovery may continue after it.
- A block outside the footprint is not a failure.
- A 30 m pixel is not a block-level validation plot.
- The status is read-only; it does not enter the objective or constraints.
