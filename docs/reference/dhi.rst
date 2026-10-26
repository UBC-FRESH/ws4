Dynamic Habitat Index account
=============================

WS4 can attach one published **Dynamic Habitat Index (DHI)** product to a compiled
dataset and report the surviving DHI area under a schedule. The account is a static
biodiversity surrogate; it does not change growth or claim a species response.

Product and provenance
----------------------

The pilot uses the SILVIS Lab **MODIS 6.1 Terra NDVI Composite RGB** product for
2003-2022 at 500 m, in EPSG:4326. The three bands are cumulative DHI (``cum``),
minimum DHI (``min``), and variation DHI (``var``); the delivered 8-bit values are
divided by 255. The source is public with no restrictions; see
<https://silvis.forest.wisc.edu/data/dhis/>. The public page also lists annual
1 km zips; the WCS subset used here is the 2003-2022 composite. No annual layer is
claimed by this pilot.

A DHI source descriptor is required whenever values are used. It records:

``source_id``, ``source_version``, ``year_range``
    The product identity and the version/vintage. ``source_version`` is not optional.
``resolution_m``, ``crs``, ``bands``, ``scale``
    The nominal pixel size, raster CRS, band names, and the divisor that maps stored
    values to the account's 0-1 index.
``bbox``, ``valid_pixels``
    The raster subset extent and its count of valid pixels.
``source_path``, ``source_sha256``, ``retrieved_utc``, ``licence``
    The exact artifact and when/how it was obtained.

The descriptor is validated before the account is used: dropping a required field,
an empty source version, a non-positive scale, or a non-positive valid-pixel count
fails. A missing source version is never treated as "current".

Ingest
------

.. code-block:: bash

   pip install 'ws4[dhi]'
   ws4 dhi ingest \
     --raster dhi_subset.tif \
     --blocks blocks.geojson \
     --output dhi_values.csv \
     --metadata dhi_metadata.json \
     --source-version "MODIS 6.1 Terra NDVI Composite RGB (2003-2022)"

``--blocks`` is a polygon layer with a ``block_id`` column (aliases ``BLOCK``,
``block``, and ``id`` are accepted). Block polygons are reprojected to the raster CRS;
each block's mean is calculated over all touched pixels, divided by ``--scale``, and
clipped to ``[0, 1]``. A block with no valid pixels is an error: the layer does not
cover the AOI. Duplicate block ids are an error. ``--band-names`` defaults to
``cum,min,var``; a raster with fewer bands than names is rejected.

``--resolution-m`` is the nominal product resolution, because an EPSG:4326 raster's
transform is in degrees. It defaults to 500 for this product; set it explicitly for
another product. The ingest writes:

``dhi_values.csv``
    ``block_id,cum,min,var`` (or the requested band names), normalized to 0-1.
``dhi_metadata.json``
    The source descriptor above.

The pair is a portable contract: a run can be reproduced from the two files and the
compiled dataset. The values are joined by ``block_id``; every dataset block must have
a value before the simulator records the account.

Account semantics
-----------------

For each band and each simulated offset, WS4 records:

``feature.DHI.<band>``
    **Level**, unit ``index_ha``: sum of block DHI × block area over blocks not yet
    treated. This is the account to target or plot when the question is "how much
    DHI-weighted forest remains?".
``feature.DHI.<band>.mean``
    **Level**, unit ``index``: area-weighted mean DHI over the same surviving blocks.
``feature.DHI.area``
    **Level**, unit ``ha``: surviving block area.

At offset -1 the account covers the whole dataset. At each later offset a block is
removed when any scheduled treatment is applied to it. A block stays removed for the
rest of the run. This is deliberately simple: the product is static, and the model
does not simulate regrowth, recovery, or species recolonization. Two schedules differ
only through which blocks they treat and when.

The account is a level, not a flow. It is recorded in ``account_values.csv`` and is
therefore available to the normal report, charts, and account API. It does not alter
the optimiser objective, growth curves, or treatment eligibility.

Run outputs
-----------

When ``ws4 simulate`` receives both ``--dhi-values`` and ``--dhi-metadata``, the run
directory also holds:

``dhi_values.csv``
    The normalized values used by the run.
``dhi_metadata.json``
    The source descriptor, so the run explains its own provenance.
``report_dhi.csv``
    Written by ``ws4 report``: baseline, final, change, percent change, unit, source
    fields, and the interpretation caveat for each DHI account.

The Python API is ``Simulator.run(..., dhi_account=DhiAccount(...))`` or
``ws4.dhi.read_dhi_account(values_path, metadata_path)``.

Web layer
---------

``GET /api/runs/{run}/dhi`` returns the run's source metadata, band names, and block
values. ``GET /api/runs/{run}/dhi?format=geojson`` joins those values to the
configured ``--geometry`` and returns a ``FeatureCollection`` with one ``dhi``
property (the first band) plus each band's property. Without configured geometry the
GeoJSON form is a 404 naming the missing artifact.

The layer is a reader over the files the run wrote; it computes no new value.

Caveats and limits
------------------

- **Scale.** The pilot product is 500 m. Blocks smaller than a pixel inherit the
  touched pixel value. Do not treat block values as field measurements, and do not
  map the account below the product's support.
- **Vintage.** The public SILVIS composite covers 2003-2022 as one layer. It is not
  an annual time series. The trajectory is schedule-driven, not climate-driven.
- **No species model.** DHI is a productivity/seasonality surrogate. It is not a
  species observation, a habitat-suitability model, or evidence of a causal
  treatment effect.
- **No recovery.** A treated block leaves the account permanently for that run.
  This is a conservative pilot convention, not a regeneration model.
- **No optimisation coupling.** The DHI account is reported, not optimised. Targets
  on it can be added by the ordinary account-target path, but the default objective
  is unchanged.

Pilot
-----

``examples/dhi_pilot`` holds a real WCS subset, four synthetic blocks, two schedules,
and the committed values/metadata. Its README gives the end-to-end commands and the
expected direction of change. The pilot is a software fixture, not a management
recommendation.
