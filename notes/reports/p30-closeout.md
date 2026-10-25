# Phase close-out report: P30 Live run surfaces

Phase: P30, Live run surfaces
Parent issue: #242
Pull requests: #246 (P30.1-P30.2), #253 (P30.3), #256 (P30.4)
Evidence head: `d7d949c`
Report commit: the commit that adds this report.
Date: 2026-10-25
Status: queued for approval. Not merged.

## Recommendation

1. Squash-merge pull request #256, and delete the branch `feature/p30-live-surfaces`.
2. Close task issue #255 and parent issue #242 with closeout comments that cite the merge commit.

Settings changes: none. This phase changes no repository setting, tag, release, or external account.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A patch/route run updates its map and target cards before completion. | P30.1: whole-schedule solvers emit `targets` and `schedule` snapshots every 20 iterations. c5 telemetry had targets at 0/20/40/60/80; target cards moved `1,260.7 / 11,083,008.7` → `0 / 11,084,175.8` → `182 / 11,084,018.8`. | Met |
| The target table exposes normalization and priority; kind and notes follow. | P30.2: detail rows with normalization, priority, derived kind, notes; sticky run controls. Edited fields round-tripped through `/api/targets.json`; kind stayed out of the YAML. | Met |
| P28 reports appear in the run and comparison surfaces. | P30.3: Reports ending-inventory card + standard `ending_inventory.csv`; Compare A/B/delta ending table and target kind. c5 showed 35 values at year 50 while the comparison map loaded. | Met |
| A legacy run is refused or normalized with a specific message. | P30.4: shared reader aliases `year`/`period` to `offset`, preserves the legacy year label, and an endpoint test covers accounts, periods, targets, and the treatment map. | Met |
| `python scripts/dashboard.py` is green. | Green on every gate at `d7d949c`. | Met |

## 2. Workflow compliance

- Parent issue #242 existed before the branch; tasks #243, #247, #248, and #255 are sub-issues.
- Branch `feature/p30-live-surfaces` was created from `main` and used for all four tasks.
- Commit messages start with task IDs: `P30.1`, `P30.2`, `P30.3`, `P30.4`.
- Roadmap, changelog, docs, and issue bodies are in step.
- No merge, tag, release, or setting change happened before this report's approval.

## 3. Gate evidence

| Gate | Result at `d7d949c` |
| --- | --- |
| lint | green |
| format | green |
| types | green |
| tests | green |
| validator | green |
| docs | green |
| docstrings | green |

## 4. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The comparison map is still slow on a large AOI. | Compare uses the GeoJSON `/map` path and renders the full geometry. | P30.3 renders the report tables before the map request; moving comparison to MVT is a separate performance item. |
| A non-delta snapshot costs one full objective evaluation. | The whole-schedule solvers have no incremental totals to read. | Snapshots use the same 20-iteration cadence as the delta path; the workload already evaluates whole schedules. |
| A legacy schedule whose period horizon differs from its account horizon can still look sparse. | The alias treats `period` as the clock; it does not invent missing account years. | The run opens without 500s; rewriting legacy artifacts is out of scope. |

## 5. Next

The next web UI work is the comparison map path (MVT instead of the full GeoJSON viewport), the P24
portfolio/tuner surfaces, and the account-browser polish. P31 should be created before that work
starts.
