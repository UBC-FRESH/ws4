# Phase close-out report: P16 The bridge at the same footprint

Phase: P16 The bridge at the same footprint
Parent issue: #141
Pull request: #142 (`P16.2`, merged as `8f0f6d4`) and the documentation pull request that adds this
report
Evidence head: `e412059`, plus the report commit
Date: 2026-10-19
Status: closing.

## Recommendation

1. Close parent issue #141 with a closeout comment that cites `8f0f6d4`, the report commit, and
   `notes/reports/p16-bridge-matched.md`.
2. Do not open a new phase for the bridge. The result is a scope decision for the paper, not a code
   task; the next WS4 phase remains gated on the maintainer's decision about the route report's
   `LENGTH` (P13).

Settings changes, each with its exact command. Each one runs only after its own approval.

- None.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Repeat the fire model on the WS4-treated masks across five seeds | The instance's own `_block_fuel_types`, `_adjacency` and `simulate`, 50 ignitions, 480 min, wind 225°, ROS × 0.3; the published barrier run reproduced exactly (`19640.448328143004`, p90 `37637.13355349601`); 3 patterns × 5 seeds on 54,368 / 55,837 / 53,697 ha | met |
| Report whether the ranking survives | It does **not**: seeds 1–2 order barrier, clumped, random; 3–4 order clumped, random, barrier; 5 orders barrier, random, clumped. Mean order clumped 22,775 < random 22,816 < barrier 22,861 ha, a largest gap of 86 ha (0.38%) against a seed range of ~3,400 ha (15%) | met, with a negative result |
| One product row per `(track, treatment, label)` and curve | `ws4/model/checks.py`, the builder, `tests/test_dataset_checks.py`; the TSA23 dataset has 1,515,465 exact duplicate rows and `(16, FT, product.Treated.managed.FT)` appears four times | met in WS4; the dataset recompile is requested in `femic-tsa23-instance` #12 |
| The loader names a dataset that repeats a row | `Simulator.from_dataset` warns with the count and labels; six tests; `docs/reference/simulator.rst` | met |
| Record the account's final scope | `docs/reference/spatial.rst` and the design note now state the withdrawal | met |

## 2. Workflow compliance

- Parent issue before the branch: #141 was opened before `feature/p16-bridge-matched`.
- Branch from `main`: yes; P16.2 merged by pull request #142; the branch was deleted with it.
- Commit messages that start with task IDs: P16.2; the report commit is the close-out.
- Gates: section 3.
- Roadmap and changelog in step: P16 section and tracker row, the P16.1 result, the P15 correction, and
  the P16.2 entry.
- Approval gates: the phase work, the pull request and the issue comment were within allowance. No
  settings changes.

## 3. Gate evidence

| Commit | Gates | Result |
| --- | --- | --- |
| `8f0f6d4` P16.2 | `python scripts/dashboard.py` | GREEN, seven gates, 585 tests |
| `e412059` backlog | CI and Docs | GREEN on both workflows |
| report commit | `python scripts/dashboard.py` | GREEN, seven gates |

## 4. CI evidence

| Run ID | Head commit | Conclusion | Notes |
| --- | --- | --- | --- |
| 39328846225 | `8f0f6d4` (PR #142) | success | All four jobs green before merge |
| 39330168542 / 39330168718 | `8f0f6d4` | success | CI and Docs on `main` |
| 39330783000 | `e412059` | success | CI on `main` |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The first 4× diagnosis was wrong | The note inferred a 4.0 curve from the arithmetic; the curve is `(0, 1.0)` | The duplicate-row cause was measured, the finding rewritten, and the prompt corrected before the thesis agent used it |
| P16.1 was delegated, then run locally | The instance is on the shared drive and the fire model's functions are importable | The local run reproduced the published result exactly; independent confirmation remains requested in `femic-tsa23-instance` #11 |
| The P15 bridge validation is withdrawn | The original comparison used a 3.3× larger fire-side treatment | Recorded in the P15 close-out, the roadmap, the design note and the reference docs |

## 6. Next phase

No new phase is proposed. The negative result is a paper-scope decision (at 5.5% treatment the
arrangement effect is inside seed noise), not a feature to build. The WS4 roadmap's next item is P13's
remaining route-report `LENGTH` question, which waits on the maintainer.

## 7. Decision

- [x] Approve as written.
- [ ] Approve with the changes stated here: <changes>.
