FEMIC Hydrology Response Bundles
================================

WS4 consumes versioned FEMIC hydrology response bundles for screening-only
spatial scheduling. It does not run FEMIC discovery, frequency fitting,
surrogate training, or flood-risk calculation.

This page covers the read-only consumer contract implemented across P57, P60,
and P62. It covers bundle validation, registration, mapping, readiness, and
preflight; the actual flood model remains a producer-side input.

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

   ws4 hydrology map --dataset build/compiled --crosswalk crosswalk.csv \
     --out build/hydrology_mapping
   ws4 hydrology screen --dataset build/compiled \
     --mapping build/hydrology_mapping --schedule schedule.csv \
     --out build/hydrology_screen

``validate`` emits a deterministic JSON report by default and exits non-zero on
an invalid bundle. ``inspect`` prints the bundle pin and artifact roles for a
valid bundle; an invalid bundle prints the validation report and exits non-zero.
Pass exactly one of a direct ``BUNDLE`` argument or ``--dataset``.

Preflight
---------

`ws4 hydrology preflight` combines the bundle pin, readiness evidence, crosswalk
review state, and mapping coverage into one fail-closed report. It is
orchestration over the existing validators; it does not run a schedule, write
files, or contact the network.

.. code-block:: bash

   ws4 hydrology preflight \
     --dataset build/compiled \
     --crosswalk reviewed-crosswalk.csv \
     --metadata reviewed-crosswalk.meta.json \
     --policy require_reviewed \
     --json

The default preflight policy is ``require_reviewed``. The report sets
``screening_ready`` to true only when:

- the bundle is structurally valid;
- the readiness state is allowed by the policy;
- a crosswalk was supplied;
- the crosswalk is reviewed under the selected policy; and
- every fragment and block is mapped.

A missing crosswalk is always a blocking reason, so a direct-bundle preflight
can report readiness evidence but cannot declare screening safe. Partial
mapping is available with ``--allow-partial`` for diagnosis, but unmapped
fragments or blocks still block readiness.

The command exits non-zero when ``screening_ready`` is false. A structurally
valid bundle is not a hydrologically reviewed bundle, and a ready preflight is
not a hydrologist review or a regulatory flood map.

Road and Culvert Exposure
-------------------------

The exposure table is an explicit, schedule-bound input:

.. code-block:: json

   {
     "schema_version": "ws4.hydrology.exposure.v1",
     "exposure_id": "exposure-2026-001",
     "generated_utc": "2026-10-26T00:00:00+00:00",
     "source_id": "reviewed-road-and-culvert-inventory",
     "review_status": "reviewed",
     "reviewer_id": "reviewer-id",
     "schedule_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
     "watershed_ids": ["watershed-1"],
     "periods": [0, 1],
     "rows": [
       {
         "watershed_id": "watershed-1",
         "period": 0,
         "road_built_km": 0.0,
         "road_used_km": 1.25,
         "road_decommissioned_km": 0.0,
         "culvert_count": 4,
         "culvert_exposed_count": 1
       },
       {
         "watershed_id": "watershed-1",
         "period": 1,
         "road_built_km": 0.5,
         "road_used_km": 1.75,
         "road_decommissioned_km": 0.0,
         "culvert_count": 4,
         "culvert_exposed_count": 2
       }
     ],
     "caveats": ["Screening input only."]
   }

`watershed_ids` and `periods` declare the complete grid. Every declared
watershed/period pair must have exactly one row; a missing row is an error, not
a zero. Lengths are finite non-negative numbers, counts are non-negative
integers, reviewed metadata requires `reviewer_id`, and `schedule_sha256` must
be a 64-character hex digest.

The table is bound to one schedule hash. Reusing it for a different schedule is
a refusal in the screening path, not a fallback. WS4 does not buffer roads,
match culverts to streams, assign a watershed to a road, or infer missing
periods. There is no geometry in this contract.

Load it with ``ws4.io.hydrology_exposure.load_hydrology_exposure``. The
returned object preserves the file SHA-256, source, review state, declared
watersheds and periods, and the canonical feature values for a watershed and
period.

Validation Evidence
-------------------

P60.1 reads the optional FEMIC validation-report and model-card artifacts. The
readiness command is a report, not a gate:

.. code-block:: bash

   ws4 hydrology readiness data/femic/hydrology-response-2026.10.0 --json
   ws4 hydrology readiness --dataset build/compiled --json

Statuses:

- ``not_available``: no validation report or model card is packaged.
- ``provisional``: evidence exists but the model card is not reviewed.
- ``conditionally_ready``: reviewed with conditions.
- ``ready``: reviewed, with a recorded hydrologist review and no tail-check
  failures.
- ``blocked``: a tail-check failure is recorded.

The report carries the producer validation/model-card IDs, review status,
usable fits, tail-check failures, benchmark pass/fail/not-evaluated counts,
full-pilot readiness, and a deterministic evidence digest. Missing evidence is
reported as missing; it is never treated as approval. The P60.1 command does
not refuse screening or optimization; a later policy task decides how the
evidence gates use.

Readiness Policies
-------------------

P60.2 gates use on the readiness report:

- ``allow_provisional`` (default): allow missing/provisional evidence with the
  recorded warnings, but a tail-check block still refuses.
- ``require_reviewed``: allow ``ready`` or ``conditionally_ready`` only.
- ``require_ready``: allow ``ready`` only.

A tail-check block refuses under every policy. The only override is
``--allow-tail-failures`` with ``allow_provisional``; it is an explicit risk
acceptance, not a claim that the fit is safe.

.. code-block:: bash

   ws4 hydrology screen ... --readiness-policy require_reviewed
   ws4 hydrology screen ... --allow-tail-failures

The flood-screen config accepts the same policy:

.. code-block:: json

   {
     "schema_version": "ws4.hydrology.flood_screen.v1",
     "mapping": "build/hydrology_mapping",
     "covariates": {},
     "scenario_tolerance": 0.05,
     "refusal_penalty": 1000000000000.0,
     "readiness_policy": "require_reviewed",
     "allow_tail_failures": false
   }

``FloodRiskModel`` enforces the policy when it is constructed, so an optimizer
run with disallowed evidence fails early with a clear message instead of
returning refusal penalties for every schedule.

Mapping WS4 Support
--------------------

Mapping requires an explicit, reviewed crosswalk. WS4 never infers a watershed
from a block ID, a centroid, or a nearest-neighbor join. The crosswalk CSV has
exactly one support key per row:

.. code-block:: text

   fragment_id,block_id,unit_id,watershed_id,receptor_id,notes
   1,,unit-1,watershed-1,receptor-1,fragment-level review
   2,,unit-1,watershed-1,receptor-1,fragment-level review
   ,11,unit-2,watershed-2,receptor-2,block-level review

A block-level row expands to every fragment in that block. A block mapping can
also be derived from complete, consistent fragment rows. Fragments in one block
must agree on ``unit_id``, ``watershed_id``, and ``receptor_id`` or mapping
fails.

Optional review metadata records the crosswalk identity and review state:

.. code-block:: json

   {
     "schema_version": "ws4.hydrology.crosswalk.v1",
     "crosswalk_id": "crosswalk-example",
     "created_utc": "2026-10-26T00:00:00+00:00",
     "review_status": "reviewed",
     "reviewed_by": "reviewer-id",
     "method": "Manual fragment/block review against FEMIC units",
     "source": "Reviewed public domain bundle",
     "caveats": ["Screening crosswalk only."]
   }

The optional ``crosswalk_sha256`` field pins the CSV. Missing metadata is
recorded as ``not_reviewed`` with a warning; it is never silently treated as
reviewed.

Run the mapping:

.. code-block:: bash

   ws4 hydrology map \
     --dataset build/compiled \
     --crosswalk reviewed-crosswalk.csv \
     --metadata reviewed-crosswalk.meta.json \
     --out build/hydrology_mapping

The command writes ``hydrology_fragments.csv``, ``hydrology_blocks.csv``, and
``hydrology_mapping.json``. The manifest records the FEMIC bundle pin, crosswalk
checksum, review status, coverage, warnings, and caveats. A crosswalk that does
not cover every fragment and block fails unless ``--allow-partial`` is set; a
partial mapping records the unmapped IDs.

No spatial inference or FEMIC re-run is performed.

Schedule Screening
-------------------

P57.4 screens a WS4 schedule against the pinned response surface and flood-risk
rows. It is read-only: no simulator, optimizer, objective, or FEMIC process is
run.

.. code-block:: bash

   ws4 hydrology screen \
     --dataset build/compiled \
     --mapping build/hydrology_mapping \
     --schedule schedule.csv \
     --out build/hydrology_screen

The screen:

- sums cumulative block area by mapped watershed and schedule period;
- derives ``harvest_fraction`` from the FEMIC domain watershed area;
- adds optional global covariates from ``--covariates features.json``;
- selects the nearest response-surface scenario within
  ``--scenario-tolerance`` (default ``0.05``);
- joins the selected response ratio to flood-risk rows by watershed, receptor,
  and return period; and
- writes ``hydrology_screen.csv`` and a deterministic
  ``hydrology_screen.json`` manifest.

A missing scenario feature, a harvest fraction outside the tolerance, a
missing watershed area, or no flood-risk row is a refusal. Refusals fail the
command by default. ``--allow-refused`` writes the inside-domain rows and records
the refusals in the manifest.

The screening peak flow is ``baseline_peak_flow_m3s * response_ratio``. The
bundle's own scenario flow, exceedance probability, and expected annual damage
are carried alongside it and are not recomputed. The row is a planning screen,
not a schedule-specific process simulation or regulatory flood map.

Flood Accounts In Optimization
------------------------------

P57.5 can expose the screening rows as optional `flood.*` accounts to the
optimizer objective. It does not change the simulator or write flood accounts
from `ws4 simulate`.

Create a flood-screen config:

.. code-block:: json

   {
     "schema_version": "ws4.hydrology.flood_screen.v1",
     "mapping": "build/hydrology_mapping",
     "covariates": {},
     "scenario_tolerance": 0.05,
     "refusal_penalty": 1000000000000.0
   }

Pass it to `ws4 optimize` (or `watch`/`calibrate`):

.. code-block:: bash

   ws4 optimize \
     --dataset build/compiled \
     --targets targets.yaml \
     --flood-screen-config flood-screen.json \
     --out build/run

Targets use the account names:

.. code-block:: text

   flood.<receptor_id>.<return_period>.ratio
   flood.<receptor_id>.<return_period>.peak_flow_m3s
   flood.<receptor_id>.<return_period>.exceedance_probability
   flood.<receptor_id>.<return_period>.expected_annual_damage

For example:

.. code-block:: yaml

   targets:
     - account: flood.receptor-1.100.ratio
       period: 1
       maximum: 1.10
       max_weight: 10000

A schedule outside the response-surface tolerance is not extrapolated. The
optimizer returns the configured `refusal_penalty` for that evaluation. When a
flood-screen config is active, the move-based delta evaluator is disabled and
whole-schedule evaluation is used; this is a deliberate screening-first
boundary, not a performance claim.

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
