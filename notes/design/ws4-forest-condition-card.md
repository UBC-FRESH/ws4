# Forest condition report card

Status: design note for P90.1

## Decision

Add a small, report-only `ws4.forest_condition.report.v1` contract instead of a
new condition model or alert engine.  The card consumes already-computed values
from DHI, structure habitat, resilience, fire recovery, and the FEMIC BA-only
inventory pilot.

## Why a separate contract

The existing report module aggregates account values.  A condition card needs
source, version, uncertainty, applicability, trend, and review status per
indicator.  Putting those fields into the account table would turn provenance
and review state into ordinary columns and make it easier to lose them.

The card is deliberately typed and independent of the simulator.  It can be
rendered from a JSON fixture today and wired into a run later without changing
the solver.

## Safety rules

- Alerts are always advisory.
- `review_status` is required.
- Non-finite values are rejected.
- Missing source or version is rejected.
- No card changes objectives, constraints, growth, schedules, or treatment
  eligibility.
- The card does not claim operational early warning; that remains `DIS-03`.

## Pilot

The example fixture combines a BA-only inventory indicator (14.9% TSA coverage,
8.86 m2/ha strict RMSE) and a DHI indicator.  It is a format and provenance
demonstration, not a claim that either source is reviewed for management use.

## Run-derived card

`build_report_from_accounts` consumes `account_values.csv` and turns each
`feature.*` account into a `review_required` indicator.  It records the final
value and first/last trend, uses `ws4.account_values` as the source, and does
not attach an RMSE.  The `ws4 condition-card` CLI writes JSON and optional
Markdown into a run's `condition/` directory.
