# P90 forest-condition report cards — close-out package

## Header

Phase: P90
Parent issue: #650
Pull request: TBD
Evidence head: `P90.1` commit on `feature/p90-forest-condition-cards`
Report date: 2026-11-02
Status: pr-open; awaiting review

## Recommendation

1. Approve the report-only forest-condition card contract.
2. Keep `DEC-02` shortlisted; do not claim operational early warning.
3. Merge the phase after CI is green.
4. Leave web UI and real condition-source integration to a later phase.

## Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Typed report and indicator schema | `ws4.forest_condition` models | met |
| JSON round-trip | focused tests | met |
| Invalid status/provenance/non-finite values rejected | focused tests | met |
| Markdown names indicators and limits | `card.md` fixture and test | met |
| Valid, invalid, and empty cases tested | 10 focused tests | met |
| Dashboard green | all seven gates green | met |
| PR queued | TBD | pending |

## Workflow compliance

- Parent issue #650 and child #651 exist and are linked.
- Branch `feature/p90-forest-condition-cards` was created from `origin/main` in
  a separate worktree at `/srv/shared-data/gep/ws4/tmp/ws4-p90`.
- This parallel phase was explicitly authorised by the maintainer; it does not
  modify P87/P89 branches or worktrees.
- Commit subject starts with `P90.1`.
- Roadmap, changelog, design note, docs, and fixture are in the change set.
- No objective, constraint, growth, schedule, solver, tag, or release changed.

## Gate evidence

`python scripts/dashboard.py` -> **OVERALL: GREEN**:

- lint
- format
- types
- tests
- validator
- docs
- docstrings

Focused tests: `python -m pytest tests/test_forest_condition.py -q --no-cov` ->
10 passed.

## CI evidence

To be recorded after the phase pull request is opened.

## Deviations and risks

- P87/P89 are active; this phase is intentionally parallel and isolated.
- The card consumes existing indicators; no real alert source is included.
- VRI/THLB or condition-source coverage is not claimed.
- Alerts are advisory only.

## Next phase

No next phase until this card contract is approved. Candidate `DEC-02` remains
shortlisted; implementation of a UI or real alert source is separate.

## Decision

Approve the report-only contract and merge after green CI. Do not promote it to
an operational early-warning product.
