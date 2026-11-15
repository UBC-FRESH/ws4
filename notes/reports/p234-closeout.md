# P234 close-out: compiled yield curves in the process bridge

Date: 2026-11-15
Phase: P234 (#1335)
Branch: `feature/p234-compiled-curves`
Tasks: P234.1 (#1336), P234.2 (#1337), P234.3 (#1338)
Design note: `notes/design/ws4-compiled-curves.md`
Report: `notes/reports/p234-compiled-curves.md`

## Result

The process bridge loads the compiled dataset yield curve and matches the estate schedule at
**340 m3** after CC.

## What changed

- `age_volume_curves_from_frame`.
- Compiled curve validation and loading.
- A second shared-schedule test using `curves.parquet`.
- Documentation and report.

## Evidence

- Bridge tests: 8 passed.
- Shared-schedule tests: 2 passed.
- Full dashboard: **OVERALL: GREEN** on all seven gates.
- Compiled `PL` natural curve: 0->0, 40->120, 80->220.
- Estate and process final volume: 340 m3; difference 0.

## Boundary

Single species and one compiled curve. No track-change semantics beyond the harvested age-0 case.
No fire, succession, or regeneration. Not an observed-data validation.

## Next

Use the compiled curve table for multiple species and tracks, then add fire/succession to the
shared schedule.

## Pull request

PR: #1339 is queued for maintainer approval. Do not merge without approval.
