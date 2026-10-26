# FEMIC hydrology response-bundle consumer contract

Status: P57.1 design note (2026-10-26)

## Context

FEMIC P114 produces versioned hydrology response and flood-risk bundles. WS4 is
a consumer: it must pin the producer identity and artifact checksums, preserve
native CRS/units/return periods/caveats, and avoid re-running FEMIC discovery,
frequency fitting, or surrogate training.

The producer contract is `femic.hydrology.response.v1`. Required artifacts are
`response_surface`, `flood_risk`, `domain`, and `disturbance_ledger`.
`femic.hydrology.flood_response.v1` carries the return-period surface;
`femic.hydrology.flood_risk.v1` carries receptor rows.

## Decision

P57.1 implements a read-only, stdlib-only validator in `ws4/io/hydrology.py`.
It mirrors the P52 LidarBC consumer split:

- `load_femic_hydrology_bundle` raises on invalid input;
- `validate_femic_hydrology_bundle` returns a specific report;
- `bundle_pin` returns a stable pin for later dataset registration;
- `read_femic_flood_risk` returns typed rows.

The validator checks manifest and role schemas, path containment, declared size
and SHA-256, response-surface summary identity/periods, flood-risk identity/row
count/row arithmetic, domain and ledger IDs, and consumer-contract keys. It
does not repair, infer, download, or re-run the producer.

## Why not register or map yet

WS4 has fragments and blocks, but no watershed/HRU/receptor crosswalk. A block
ID is not a FEMIC unit ID. Registration and mapping need an explicit reviewed
crosswalk or the separate FEMIC domain bundle; guessing would create a false
spatial claim. P57.1 therefore stops at validation and pinning.

## Producer phase labels

FEMIC writes `consumer_contract.consumer_phases = {"ws4": "P49", "fhops":
"P14"}`. Those are producer-side workstream labels. WS4 P49 is already a
closed managed/young validation phase; FHOPS P14 is its LidarBC phase. WS4's
hydrology consumer phase is P57. Preserve the labels as metadata and do not
rewrite the manifest.

## Boundaries and failure modes

- A valid bundle is internally consistent, not hydrologically correct.
- The P114.9 handoff is screening-only and conditional on hydrologist review.
- Fits that fail the producer tail check must not be used for risk reporting.
- Applicability-domain refusal belongs to the later lookup task; P57.1 only
  preserves the domain metadata.
- Later tasks must not infer watersheds, receptor capacity, or damage curves.

## Follow-on tasks

- P57.2: register a pinned bundle in a compiled WS4 dataset without copying it.
- P57.3: explicit block/fragment -> FEMIC unit/watershed/receptor crosswalk.
- P57.4: read-only flood-risk screening for a schedule.
- P57.5: optional `flood.*` accounts and objective/constraint integration, with
  the screening-only boundary preserved.

## P57.2 registration decision

A compiled dataset stores the validated pin under
`metadata.hydrology_products` and in a `hydrology_products.json` sidecar. The
bundle is referenced, not copied. A bundle inside the dataset is stored as a
relative reference; an external bundle keeps its absolute path, which the
operator must treat as an external-data boundary.

Revalidation compares the registered bundle id/version, manifest SHA-256, and
every artifact checksum. A changed manifest fails even when the JSON still
parses. This catches stale pins without re-running FEMIC.

Registration does not imply a watershed crosswalk, schedule lookup, or a
flood-risk objective. Those remain P57.3+.

## P57.3 mapping decision

Mapping is an explicit reviewed crosswalk, not a spatial join. A CSV row names
either one `fragment_id` or one `block_id`, plus a FEMIC `unit_id`,
`watershed_id`, and optional `receptor_id`. Block rows expand to their
fragments; block rows are derived from fragment rows only when every fragment in
the block is mapped and all mappings agree.

Review metadata is a separate document. Missing metadata becomes
`not_reviewed` with a warning; `reviewed` requires a reviewer id. The mapping
manifest records the bundle pin, crosswalk SHA-256, review state, coverage, and
unmapped IDs.

Complete coverage is required by default. `--allow-partial` is for exploratory
mapping and records the gap rather than hiding it. No centroid, nearest
watershed, or geometry join is used.
