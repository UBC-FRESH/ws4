# P138 Pareto member to map/Plan

Date: 2026-11-05
Status: pr-open
PR: #836
Branch: `feature/p138-pareto-to-plan`
Parent issue: #834
Task issue: #835

## Summary

The explorer could inspect a portfolio member's metrics and download its schedule,
but could not open that schedule as a run. This phase promotes a selected member into
a direct, read-only run view under the runs root, then uses the existing map, report,
target, and compare endpoints without copying the portfolio's full data model.

## Outcome-front alignment

`run_portfolio` now computes its reported `front` and `outcome_front` over the declared
outcome metrics only. The scalar weighted penalty remains available as an optional
dimension but does not define dominance. `search_artifact` also enriches older
portfolio artifacts with `outcome_front`, so the Search table and the 3D explorer use
the same count.

## Promotion

`POST /api/search/{name}/members/{key}/promote`:

- finds the member by its `label:seed` key;
- resolves its `run_dir` under the portfolio artifact, accepting absolute,
  artifact-relative, or cwd-relative records;
- creates a direct runs-root child with hard-linked files (copy fallback);
- writes `portfolio_source.json` naming the portfolio, member, factors, metrics,
  objective, and source run;
- is idempotent for the same portfolio/member;
- refuses missing members and paths outside the artifact.

The promoted id starts with `pareto-` and is visible to the normal run APIs.

## Browser

The Pareto workspace now has:

- **Open on map**, which promotes the selected member, refreshes the run selector,
  loads the run context, and switches to Map;
- **Compare pinned**, which promotes the first two pinned members and opens the
  existing spatial comparison workspace.

## Verification

- Unit tests cover outcome-front aliases, idempotent promotion, cwd-relative
  resolution, missing members, and path traversal.
- Chromium tests cover open-on-map and compare-pinned.
- `python scripts/dashboard.py`: `OVERALL: GREEN. Every gate passed.`

## Limits

- The promoted run is a derived read-only view; deleting the portfolio does not
  delete it automatically.
- The current live target file is still the Plan target authority; promotion does not
  mutate live targets to match a member's weights.
