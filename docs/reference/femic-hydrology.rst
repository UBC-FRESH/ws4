FEMIC Hydrology Response Bundles
================================

WS4 consumes versioned FEMIC hydrology response bundles for screening-only
spatial scheduling. It does not run FEMIC discovery, frequency fitting,
surrogate training, or flood-risk calculation.

This page covers the read-only consumer contract implemented in P57.1.
Registration, WS4-to-FEMIC unit mapping, schedule lookup, and `flood.*`
objective terms are later tasks.

Bundle Contract
---------------

A FEMIC response bundle contains ``manifest.json``, ``artifacts/<role>/``, and
``provenance/response_plan.json``. WS4 validates and pins:

- ``bundle_id`` and ``bundle_version``;
- the manifest SHA-256;
- every artifact role, schema, media type, size, and SHA-256;
- the response-surface and flood-risk summaries;
- the domain and disturbance-ledger identifiers; and
- the producer applicability domain, uncertainty, caveats, and consumer
  contract.

Required artifact roles are ``response_surface``, ``flood_risk``, ``domain``,
and ``disturbance_ledger``. Optional roles include the surrogate model and
validation artifacts, frequency fits, Tier 0 screening, benchmark checks, and
the validation report, model card, and pilot run.

``ws4.io.hydrology.load_femic_hydrology_bundle`` raises on an invalid bundle.
``validate_femic_hydrology_bundle`` returns a report with specific errors.
``bundle_pin`` returns the stable downstream pin. The module uses only the
standard library and never contacts FEMIC or the network.

Python Usage
------------

.. code-block:: python

   from pathlib import Path

   from ws4.io.hydrology import (
       bundle_pin,
       load_femic_hydrology_bundle,
       read_femic_flood_risk,
       validate_femic_hydrology_bundle,
   )

   bundle_path = Path("data/femic/hydrology-response-2026.10.0")
   report = validate_femic_hydrology_bundle(bundle_path)
   if not report.is_valid:
       raise RuntimeError("; ".join(report.errors))

   bundle = load_femic_hydrology_bundle(
       bundle_path,
       expected_bundle_id="hydro-response-example",
       expected_bundle_version="2026.10.0",
   )
   pin = bundle_pin(bundle)
   risk = read_femic_flood_risk(bundle)

   print(pin["manifest_sha256"])
   for row in risk.rows:
       print(row.receptor_id, row.return_period, row.ratio)

Validation Rules
----------------

The validator rejects:

- a wrong manifest or artifact schema;
- an absolute artifact path, a ``..`` traversal, or a path outside the bundle;
- a missing, duplicate, or unknown required role;
- a size or SHA-256 mismatch;
- a response-surface ID, baseline, or return-period mismatch;
- a flood-risk source-surface, table-ID, baseline, row-count, or row-ratio
  mismatch;
- a domain or disturbance-ledger ID mismatch; and
- a malformed consumer contract.

The validator reports warnings for unknown optional roles. It does not infer
missing watersheds from block IDs, does not repair a producer bundle, and does
not turn a valid checksum into a hydrologic claim.

Registration
------------

Register a validated bundle in a compiled dataset:

.. code-block:: bash

   ws4 hydrology register \
     --dataset build/compiled \
     --bundle data/femic/hydrology-response-2026.10.0 \
     --bundle-id hydro-response-example \
     --bundle-version 2026.10.0

Registration writes the pin to ``manifest.json`` under
``metadata.hydrology_products`` and to a ``hydrology_products.json`` sidecar.
The bundle is referenced, not copied. A bundle inside the dataset is stored as a
relative path; an external bundle keeps its absolute path. Do not copy a private
bundle into a tracked dataset.

Inspect and validate the registered pin:

.. code-block:: bash

   ws4 hydrology inspect --dataset build/compiled --json
   ws4 hydrology validate --dataset build/compiled

Revalidation checks the registered ``bundle_id``, ``bundle_version``, manifest
SHA-256, and every artifact size/checksum. A changed bundle manifest fails even
if its schema still parses.

CLI
---

Direct bundle inspection and validation remain available:

.. code-block:: bash

   ws4 hydrology validate data/femic/hydrology-response-2026.10.0
   ws4 hydrology validate data/femic/hydrology-response-2026.10.0 \
     --bundle-id hydro-response-example \
     --bundle-version 2026.10.0

   ws4 hydrology inspect data/femic/hydrology-response-2026.10.0 --json

``validate`` emits a deterministic JSON report by default and exits non-zero on
an invalid bundle. ``inspect`` prints the bundle pin and artifact roles for a
valid bundle; an invalid bundle prints the validation report and exits non-zero.
Pass exactly one of a direct ``BUNDLE`` argument or ``--dataset``.

Flood-Risk Table
----------------

Each row records a receptor, watershed, return period, baseline and scenario
peak flow in cubic metres per second, the scenario/baseline ratio, and optional
exceedance probability and expected annual damage. The table is a
decision-support screening surface. It is not a regulatory flood map, design
flood, or operational safety determination.

Producer Phase Labels
---------------------

FEMIC records producer-side workstream labels in
``consumer_contract.consumer_phases`` (currently ``ws4: P49`` and
``fhops: P14``). Those are not WS4 or FHOPS phase numbers. WS4's hydrology
consumer phase is P57, and FHOPS has its own phase numbering. Preserve the
labels as producer metadata; do not rewrite the manifest.

Boundary
--------

- Use only a pinned, validated bundle.
- Registration references the bundle; it does not copy, download, or re-run FEMIC.
- Preserve the producer CRS, units, return periods, caveats, and provenance.
- Refuse queries outside the recorded applicability domain.
- Do not use the bundle as a regulatory flood map or design-flood service.
- The FEMIC P114.9 handoff is conditional on hydrologist review and a completed
  process-model pilot. A valid bundle is internally consistent, not
  hydrologically validated.

See Also
--------

- :doc:`femic-lidar`
- :doc:`compiled-dataset`
- :doc:`optimizer`
- The FEMIC producer contract in the FEMIC repository:
  ``docs/reference/contracts/hydrology-response-bundles.rst``.
