=================
Report provenance
=================

A run's report tables are only useful if a reader can tell which files they came from and
whether they changed after they were written. ``write_report`` writes a
``report_provenance.json`` sidecar beside the tables. The sidecar is a manifest, not a
signature: it records SHA-256 digests so a reader can detect a changed file, but it does not
prove who produced it.

Schema
------

The sidecar uses ``ws4.report.provenance.v1``. Its top-level fields are:

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Field
     - Contents
   * - ``schema_version``
     - ``ws4.report.provenance.v1``.
   * - ``generated_utc``
     - The UTC time the sidecar was written, as an ISO-8601 timestamp.
   * - ``run``
     - ``id``, the run identifier supplied by the caller or the report directory's name.
   * - ``dataset``
     - The dataset ``id``, ``manifest_sha256``, ``schema_version``, and source list when a
       dataset is known. It is ``null`` when no dataset identifier is available.
   * - ``reports``
     - One entry per report table the writer produced: ``name``, ``bytes``, ``sha256``, and
       ``status``.
   * - ``sources``
     - One entry per source metadata file that exists: the same fields as ``reports``, plus
       ``status`` and, for malformed JSON, an ``error``.
   * - ``uncertainty``
     - ``status``, ``source``, and ``statement``. See `Uncertainty`_.
   * - ``warnings``
     - Text messages for missing report files or malformed source metadata. Missing metadata
       is normal and does not produce a warning by itself.

The writer hashes these report tables when it writes them:

- ``report_accounts.csv``
- ``report_targets.csv``
- ``ending_inventory.csv``
- ``report_dhi.csv``, when DHI accounts are present
- ``report_structure_habitat.csv``, when structure-habitat accounts are present
- ``report_resilience.csv``, when resilience accounts are present

It hashes these run-local source metadata files when they exist:

- ``dhi_metadata.json``
- ``structure_habitat_metadata.json``
- ``resilience_metadata.json``

Example
-------

.. code-block:: json

   {
     "schema_version": "ws4.report.provenance.v1",
     "generated_utc": "2026-11-03T00:00:00+00:00",
     "run": {"id": "tsa24-base"},
     "dataset": {
       "id": "tsa24",
       "manifest_sha256": "2f6c...",
       "schema_version": "ws4.dataset.v1",
       "status": "ok"
     },
     "reports": [
       {
         "name": "report_accounts.csv",
         "bytes": 4812,
         "sha256": "24d1...",
         "status": "hashed"
       }
     ],
     "sources": [
       {
         "name": "dhi_metadata.json",
         "bytes": 912,
         "sha256": "ab90...",
         "status": "ok"
       }
     ],
     "uncertainty": {
       "status": "not_stated",
       "source": null,
       "statement": null
     },
     "warnings": []
   }

Check a digest with the standard tool::

   sha256sum report_accounts.csv

Uncertainty
-----------

The sidecar does not invent an uncertainty statement. Its status is ``not_stated`` unless a
source metadata file carries one of these fields:

- ``uncertainty`` as an object with a ``status`` (or ``level``), and an optional
  ``statement`` or ``notes``;
- ``uncertainty`` as a non-empty string, recorded as ``stated``;
- ``uncertainty_status`` as a non-empty string.

When a source supplies one, ``uncertainty.source`` names that file. A report that has no
uncertainty metadata therefore says ``not_stated`` rather than presenting silence as
agreement.

Missing and invalid inputs
--------------------------

A missing source metadata file is simply absent from ``sources``. A malformed file is still
hashed and recorded with ``status`` ``invalid`` and an ``error``; report writing continues.
A missing report file named in the record is kept with null ``bytes`` and ``sha256`` and
``status`` ``missing`` plus a warning. A missing dataset manifest leaves the dataset ``id``
in place with ``status`` ``missing``.

Web service
-----------

``GET /api/runs/{run}/reports`` keeps the existing ``name`` and ``bytes`` fields and adds
``sha256`` where the sidecar recorded one. The ``report_provenance.json`` entry also carries
the decoded sidecar under ``provenance``. The Reports tab shows a provenance badge with the
uncertainty status and links to the sidecar and any source metadata files. The browser
renders those values as text nodes; it does not recompute a digest or a status.

Limits
------

- A digest detects change; it is not a signature, a timestamp authority, or a trust anchor.
- The sidecar records the report tables and the three run-local metadata files. It does not
  hash the whole dataset or the schedule.
- The writer records the identifiers the caller supplies. A report run outside a managed
  run directory may have no dataset identity.
- ``not_stated`` means exactly that. It is not a claim that the model is free of
  uncertainty.
