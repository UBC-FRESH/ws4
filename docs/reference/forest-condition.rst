Forest condition report card
============================

WS4 can package already-computed condition indicators into a small Markdown or
JSON report card.  The card is a reporting surface, not a new condition model and
not an operational early-warning system.

Contract
--------

The schema is ``ws4.forest_condition.report.v1``.  A report has:

``report_id``, ``scenario_id``, ``generated_utc``, ``period``
    Identity and reporting window.
``review_status``
    One of ``draft``, ``provisional``, or ``reviewed``.
``indicators``
    A list of condition indicators.
``alerts``
    Advisory alert rows.  Every alert is explicitly advisory.
``provenance``
    Source and version metadata.

Each indicator carries:

``name``, ``value``, ``unit``
    The measured value.
``source``, ``source_version``
    The product, model card, or calculation that produced it.
``uncertainty``, ``uncertainty_kind``
    Optional error or interval metadata.
``applicability``
    Domain or abstention statement.
``status``
    ``ok``, ``outside_domain``, ``missing``, or ``review_required``.
``trend``
    ``improving``, ``stable``, ``declining``, or ``not_available``.

Example
-------

.. code-block:: bash

   python - <<'PY'
   from ws4.forest_condition import load_report
   report = load_report("examples/forest_condition/card.json")
   print(report.to_markdown())
   PY

The fixture at ``examples/forest_condition`` contains a JSON card and its
rendered Markdown.  It combines a BA-only inventory indicator with a DHI
indicator to show the provenance and abstention fields.

Boundaries
----------

- The card does not compute indicators, run the simulator, or change the
  objective, constraints, growth, or solver.
- Alerts are advisory.  They are not treatment triggers, constraints, or
  liability-bearing operational warnings.
- The card must carry a review status.  ``draft`` and ``provisional`` cards must
  not be presented as reviewed.
- Missing or non-finite values are rejected; they are not silently imputed.
- ``DEC-02`` remains dependent on a real condition/alert source (`DIS-03`); this
  contract alone is not an early-warning product.
