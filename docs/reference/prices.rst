Scenario price paths
====================

Purpose
-------

A ``prices.v1`` table states product prices or costs for named scenarios. WS4 reads
one table, compares every named path with the ``base`` path, and writes the comparison
with its provenance.

The table is a scenario input. It does not enter the compiled dataset, the simulator's
growth, the objective, the schedule, or the solver. WS4 does not forecast a price,
convert a currency, adjust for inflation, or fill a missing product or period.

.. warning::

   The values are assumptions, not a forecast. Every table must say so in its
   ``not_a_forecast`` field, and the command repeats the statement in its output and in
   the written report.

Schema
------

The table is UTF-8 JSON with ``schema_version`` set to ``prices.v1``. Its top-level
fields are:

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Field
     - Contents
   * - ``schema_version``
     - ``prices.v1``.
   * - ``table_id``
     - Stable table identifier.
   * - ``generated_utc``
     - Producer generation timestamp, as text.
   * - ``not_a_forecast``
     - A non-empty statement that includes the words ``not a forecast``. The table is
       rejected when the phrase is absent.
   * - ``caveats``
     - Optional list of additional source or interpretation caveats.
   * - ``rows``
     - One object per path/product/period, described below.

Each row has these fields:

.. list-table::
   :header-rows: 1
   :widths: 24 16 60

   * - Field
     - Type
     - Meaning
   * - ``path_id``
     - string
     - ``base``, ``high``, ``low``, or ``policy_shock``.
   * - ``product``
     - string
     - Product identifier, such as ``sawlog`` or ``pulp``.
   * - ``period``
     - integer
     - Non-negative period index.
   * - ``value``
     - number
     - Finite, non-negative value in ``unit``.
   * - ``unit``
     - string
     - Unit of the value, such as ``CAD/m3``.
   * - ``currency``
     - string
     - Currency code, such as ``CAD``.
   * - ``region``
     - string
     - Region the value applies to.
   * - ``source``
     - string
     - Source identifier for the value.
   * - ``source_version``
     - string
     - Source version, vintage, or access date.

The named paths are ``base``, ``high``, ``low``, and ``policy_shock``. ``base`` is
mandatory because it is the comparison baseline; a table may carry any subset of the
other named paths. Every path must cover exactly the base path's product/period grid.
A product keeps one unit across all paths, and the whole table has one currency and one
region.

Example
-------

.. code-block:: json

   {
     "schema_version": "prices.v1",
     "table_id": "fixture-scenario-prices",
     "generated_utc": "2026-11-03T00:00:00+00:00",
     "not_a_forecast": "Synthetic scenario inputs; not a forecast of market prices.",
     "caveats": ["No inflation adjustment or currency conversion is applied."],
     "rows": [
       {
         "path_id": "base",
         "product": "sawlog",
         "period": 1,
         "value": 72.5,
         "unit": "CAD/m3",
         "currency": "CAD",
         "region": "British Columbia, Canada",
         "source": "synthetic-fixture",
         "source_version": "2026-11-03"
       }
     ]
   }

Command
-------

.. code-block:: bash

   ws4 price-paths --table tests/fixtures/prices/paths.json --out runtime/prices

The command writes three files:

.. list-table::
   :header-rows: 1
   :widths: 36 64

   * - File
     - Contents
   * - ``price_path_comparison.csv``
     - One row per path/product/period with ``value``, ``base_value``, ``delta``,
       and ``delta_pct``. ``delta_pct`` is null when ``base_value`` is zero.
   * - ``price_path_report.md``
     - A human-readable report with the caveat, the table's provenance, a per-path and
       per-product summary, the full comparison, and the limits.
   * - ``price_path_provenance.json``
     - A ``ws4.prices.report.v1`` record with the input file's name, byte size, and
       SHA-256, the path and product/period grid, each distinct
       path/source/source-version combination with the products and periods it covers,
       the caveat, the comparison definition, and each output file's size and digest.

The delta is ``value - base_value`` at the same product and period. The percent delta is
``100 * delta / base_value``. The report does not rank the paths or claim that one is
more likely.

Provenance and limits
---------------------

- The sidecar hashes the input table and the two report files; it does not hash the
  data behind a source or prove who produced it.
- A digest detects change. It is not a signature, a timestamp authority, or a trust
  anchor.
- The loader rejects a table that omits the base path, names an unknown path, repeats a
  row, disagrees on the product/period grid, mixes a product's unit, currency, or
  region, contains a negative or non-finite value, or lacks the ``not a forecast``
  statement.
- Reading the table changes no model behaviour. There is no objective weight,
  constraint, growth curve, schedule, or solver change.

Cross-references
----------------

- :doc:`compiled-dataset`
- :doc:`optimizer`
- :doc:`report-provenance`
