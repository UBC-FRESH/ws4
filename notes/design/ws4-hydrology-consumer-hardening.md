# WS4 hydrology consumer hardening

Status: P62.1 design note (2026-10-26)

## Context

P57 made WS4 a read-only consumer of the FEMIC hydrology response bundle:
validation, pinning, dataset registration, explicit crosswalk mapping, schedule
screening, and optional `flood.*` optimizer accounts. P60 added readiness states
and policy gating for validation reports and model cards.

Two things are still missing before a real watershed can be screened honestly:

1. There is no single report that says whether a bundle, crosswalk, readiness
   state, and policy are jointly safe to use.
2. There is no explicit input for road and culvert exposure by watershed and
   period. The current screen uses harvest fraction plus global covariates.

The Chapman Creek pilot is closed as data-blocked in FEMIC #383. The Seymour
River work depends on the ungauged domain audit in FEMIC #388 and has no
reviewed FEMIC response bundle yet. P62 therefore does not produce a watershed
flood result.

## Decision

P62 is a consumer-hardening phase. It makes the unsafe paths fail closed and
adds an explicit exposure contract. It uses synthetic fixtures only.

P62 does not reopen Chapman, does not infer Seymour, and does not claim a
current flood baseline, flood map, or regulatory result.

P62 keeps the phase number reserved by issue #437 even though P63 landed
separately. The phase is intentionally out of numeric order.

## Existing contracts

- `femic.hydrology.response.v1` is the bundle manifest.
- Required roles are `response_surface`, `flood_risk`, `domain`, and
  `disturbance_ledger`.
- Optional roles include `validation_report`, `model_card`, and `pilot_run`.
- `femic.hydrology.flood_response.v1` carries the scenario and return-period
  response surface.
- `femic.hydrology.flood_risk.v1` carries receptor rows.
- `ws4.hydrology.crosswalk.v1` is the explicit WS4-to-FEMIC mapping input.
- `ws4.hydrology.mapping.v1` records coverage and review state.
- `ws4.hydrology.screen.v1` records screening rows, refusals, and caveats.
- `ws4.hydrology.flood_screen.v1` configures optional optimizer accounts.
- Readiness states are `not_available`, `provisional`, `conditionally_ready`,
  `ready`, and `blocked`.
- Readiness policies are `allow_provisional`, `require_reviewed`, and
  `require_ready`.

## Preflight contract

P62.2 adds `ws4.hydrology.preflight.v1`. It is orchestration over the existing
validators, not a second source of truth. It reports:

- bundle identity and artifact pin,
- readiness state and policy,
- crosswalk review state,
- fragment/block coverage and unmapped IDs,
- exposure presence and schedule binding when supplied,
- `screening_ready`,
- blocking reasons,
- warnings and caveats.

The command exits non-zero when `screening_ready` is false. It has no file side
effects and never contacts the network.

Blocking conditions include an invalid bundle, a tail-check block, a readiness
state not allowed by the policy, an unreviewed crosswalk under a reviewed
policy, and incomplete mapping without an explicit partial-mapping allowance.

P62.2 defaults to ``require_reviewed`` for this command. A missing crosswalk is
always a blocking reason: a direct-bundle report can show readiness evidence but
cannot declare screening safe. ``--allow-partial`` is diagnostic only; unmapped
fragments or blocks still block readiness.

## Exposure contract

P62.3 adds `ws4.hydrology.exposure.v1`. It is an explicit table by watershed and
period:

```text
watershed_id, period, road_built_km, road_used_km,
road_decommissioned_km, culvert_count, culvert_exposed_count
```

The manifest records `exposure_id`, `generated_utc`, `source_id`,
`review_status`, `reviewer_id` when reviewed, `schedule_sha256`, and caveats.

The table is not a spatial product. WS4 does not buffer roads, match culverts to
streams, assign a watershed to a road, or infer missing periods. A missing row
is a gap, not a zero.

The table is bound to one schedule hash. Using it for a different schedule is a
refusal, not a fallback.

P62.3 makes the table a complete declared grid. `watershed_ids` and `periods`
declare the scope; every watershed/period pair must have exactly one row. A
missing row is an error, not a zero. Counts are non-negative integers, lengths
are finite non-negative numbers, a reviewed table needs a reviewer, and the
schedule hash must be a 64-character hex digest. The loader preserves the file
SHA-256 and never adds geometry.

## Screening and optimizer boundary

P62.4 lets `hydrology screen` use a valid exposure table for the schedule it
names. The screen records the exposure identity and schedule hash. If the bundle
requires an exposure feature that the table does not provide, the screen refuses.

The screen merges the table's raw features with the schedule's harvest fraction:
`road_built_km`, `road_used_km`, `road_decommissioned_km`, `culvert_count`, and
`culvert_exposed_count`. It also computes densities from the FEMIC watershed
area: `road_built_density_km_per_km2`, `road_used_density_km_per_km2`,
`road_decommissioned_density_km_per_km2`, and `culvert_exposure_per_km2`.
Those densities are calculated values, not observed road density.

A global covariate may not duplicate an exposure feature. A mapped watershed or
period missing from the exposure table is a refusal, not a zero. A schedule-hash
mismatch refuses. The screen records the exposure ID, file digest, review state,
and a `coverage.exposure_used` flag. If no response-surface scenario names an
exposure feature, the screen records a warning rather than pretending the table
affected the result.

The optimizer evaluates many candidate schedules. A fixed exposure table cannot
be correct for all of them. P62 therefore makes a flood-screen configuration
that names exposure fail with a specific "not supported until schedule-derived
exposure exists" error. This is a deliberate negative capability, with a test.

A later phase may derive exposure from the route network and evaluate it inside
search. That requires a road-state contract, culvert geometry, and a reviewed
flood response that uses those features. It is not part of P62.

For now, `load_flood_screen_config` rejects a config that names `exposure` or
`exposure_path`. The refusal is deliberate: a table bound to one schedule cannot
be reused across the optimizer's candidate schedules. The capability is recorded
in `notes/backlog.md`, not hidden behind a default.

## Fail-closed rules

- Missing evidence is not approval.
- A structurally valid bundle is not a hydrologically reviewed bundle.
- A mapping is not a spatial join.
- A partial mapping is a recorded gap, not complete coverage.
- A fixed exposure table is valid for one schedule only.
- The optimizer must not reuse a fixed exposure table across candidates.
- No output is a regulatory flood map or an operational safety determination.

## Data preconditions for a later pilot

A later real-watershed phase needs all of the following:

1. A reviewed FEMIC response bundle for that watershed.
2. A current or governed gauge series, or an explicit acceptance of a
   historical-only frequency result.
3. A DEM with consistent horizontal and vertical metadata and bounded gaps.
4. Reviewed receptor geometry and capacity/damage evidence.
5. A reviewed WS4 block/fragment crosswalk.
6. Culvert and road-state evidence if the response surface uses those features.
7. Hydrologist review of the model card, record discontinuities, and diversion
   effects.

Public data do not need an external governance gate. Non-public, Indigenous, or
licence-restricted data need the applicable governance decision before use.

## Task map

- P62.1: re-scope and record this boundary.
- P62.2: add the preflight report.
- P62.3: add the exposure contract.
- P62.4: use exposure in screening and guard the optimizer.
- P62.5: prove the path on synthetic fixtures and document it.
- P62.6: validate, document, and close out.

## Non-goals

- Chapman or Seymour flood results.
- A flood map, design flood, or regulatory claim.
- Spatial joins or inferred road/culvert locations.
- Automatic schedule-derived exposure in the optimizer.
- New external data acquisition.
