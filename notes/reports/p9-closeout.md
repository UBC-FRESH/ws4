# Phase close-out report: P9 spatial performance and memory

Phase: P9
Parent issue: #97
Branch: `feature/p9-memory`
Pull request: opened against `main`, carrying Phase 10 with it (see "Why one pull request covers two phases")
Report written: 2026-10-18

## Why one pull request covers two phases

Phase 10 was branched from `feature/p9-memory` and its pull request was stacked on it, so Phase 10 was
merged *into* this branch when the maintainer approved it (`b512cd9`). The two are one line of history
now: this pull request to `main` carries both. Phase 10 is already closed and its own report is
`notes/reports/p10-closeout.md`; nothing here re-opens it.

## Recommendation

**Close P9.** The next phase is the derived targets — the reference's ratios, flow constraints and
patch-size distributions — together with the three sample-side gaps this phase uncovered: WS4's period
convention against the reference's, the C5 sample's mill set (two mills, MILL2 and MILL3 merged), and
the growth check's retargeting for the 2026 sample's shape.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| The dataset is shared across workers, or there is a measured reason it cannot be | shared — P9.1's preload put 174 MB in a forked child's shared pages and 2 MB private — and then **rejected by measurement**: it shares nothing a worker reads (`_island_job` builds its own optimiser), so its 0.789 s of serial setup moved onto the critical path, worth **−12.2%** at 16 islands and **−12.7%** at 32 in paired, order-alternated runs. Removed (`472ab59`) | met by measurement, with the change reverted |
| Island scaling re-measured at a recorded load, compared against P8.4's 17.7× at 55% | the control reproduces P8.4: **1,089 it/s** at one island against 1,055, and **18,870** at 32 against 18,685, at recorded loads (`472ab59`) | met |
| The patch-state and curve-gather costs judged against the P8.3 profile, with the measurements recorded | the patch-state construction **25.9 → 2.79 ms** per state (−89%) and a full reset **3.3 s → 0.7 s** (−80%), taking the C5 patch-ramp workload **+5.9%** (`3959d71`); the curve gather **1,133 → 858 µs** (−24.3%) and the 30-year simulate **−6.1%**, with the documented benchmark at `simulate_base_seconds` **0.100 s** (`4ac2d23`) | met |
| The dashboard green at every commit, with the docs and docstrings gates | seven gates GREEN at the evidence head; the deviations below are recorded, and each was fixed rather than waived | met |
| **Added:** the accounts comparison against a reference report (#95) | **PASS** on both 2026 scenarios — `WS4 reproduces the reference's 1323 account-period values` — reading the reference's own export as it lands (`46aa909`) | met |
| **Added:** put the package under the type gate (#102) | the gate now checks **93 files where it checked 50**; a planted package error is caught (`7eee2d5`) | met |
| **Added:** growth parity from the reference's own yields (#103) | 959 yield-curve points reproduced with one upstream conflict recorded (`ba8d6ef`) — **built for the 2019 sample's shape, and the 2026 sample needs it retargeted** | met for the 2019 sample; carried forward for the 2026 one |
| **Added:** the matrix builder's track attribution (#110) | fixed; worth **30–45%** on every managed and unmanaged account, and live since the 2019 sample (`a93213e`) | met |

## 2. What shipped

**Performance.** The dataset-sharing attempt, measured and removed (P9.1, P9.2); the patch-state
construction shared across a group's years (P9.3, −89% per state); the curve gather addressed flat
(P9.4, −24.3%). **Parity.** The accounts comparison built in P8 and blocked on an export, now running
against the 2026 reference's own report tree and passing on both scenarios (P9.5); the matrix-builder
fix that the comparison found (P9.8). **Quality.** The type gate widened to the package (P9.6).

**The end of the phase is not where it started.** P9 was scoped as spatial performance and memory. It
ends as the phase that verified the replacement claim on the current reference: three of its four
added tasks exist because the 2019 sample could not be run on the 2026 build, and the numbers that
matter are in the accounts comparison rather than in the scaling curve.

## 3. Gate evidence

`python scripts/dashboard.py` at the evidence head: lint, format, types, tests, validator, docs and
docstrings all GREEN. The notebook drift check is a separate CI job (`Notebook outputs`) because it
takes about eight minutes against the dashboard's fifty seconds.

## 4. CI evidence

| Run ID | Head commit | Conclusion |
| --- | --- | --- |
| (the pull request's own runs) | see the pull request | CI runs the four jobs; the phase's evidence head is green |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The shared-dataset change was reverted after being landed | P9.1 measured the wrong path — a forked child calling the *inherited* optimiser, which a worker never does | P9.2 caught it with a paired A/B, the change was removed, and the note records the wrong measurement alongside the right one |
| The growth check reads a shape the 2026 sample does not have | it reads `Y<n>.<species>` curves from a sample's yield XML, which the 2019 sample ships and the 2026 lookup model does not | carried into the next phase: the yields the 2026 sample has live in `tracks/curves.csv` |
| The routing parity check fails 10 of 25,134 node-and-mill pairs on the 2026 sample | the sample's own `roads/` folder mixes vintages: `destinations.csv` lists two mills while three `cost_destination.*.csv` files ship, MILL3's is dated 2018, and the column was renamed `SUM_HAUL`→`SUM_LENGTH`. **The maintainer confirms the model now has two mills, with MILL2 and MILL3 merged.** | the check needs the model's actual mill set rather than every table in the folder; carried into the next phase |
| Targets with `flow` set are mis-reported by `report_targets.csv` | `target_status` prices every target as a level target over its period, while the objective prices a `flow` target as a per-period percent series | recorded with measurements in `notes/backlog.md`; fixing it means deciding what the report should show for a flow target, which the next phase is the right place for |
| WS4's period convention is start-labelled where the reference's is end-labelled | `Target.cell_years()` is `range(year, year + period_width)`; the reference labels a period by its **end** year and treats period 0 as the initial snapshot | the acceptance check translates, so the comparison passes; the maintainer directs **matching the reference**, so it is the next phase's first modelling task |
| The 2019 sample's accounts were never verifiable | the sample ships no account report, and the checks that did pass (fragment counts, routing) do not depend on feature attribution | this is what the 2026 sample's own reports changed; the accounts comparison now runs and passes on it |

## 6. Next phase

**The derived targets, and the sample's own files.** In order:

1. **WS4's period convention matched to the reference's** (end-labelled periods, period 0 as the initial
   snapshot) so a target written the reference's way means the same thing in both tools.
2. **The derived targets compared** — the 178 the accounts check names: the ratios
   (`ratio_route_haul_*`, `ratio_ECA_Recovery_*`), the flow constraints (`even`, `ndy`), and the patch
   size and age-class distributions (`patch_harvested_*`, `patch_young_*`). They need their own
   definitions on WS4's side, and they are what a spatial model is for.
3. **The routing parity check given the model's mill set** (two mills, MILL2 and MILL3 merged) so the
   sample's stale third table stops reporting as a WS4 difference.
4. **The growth check retargeted** for the 2026 sample's shape.
5. **The flow-target reporting gap** closed, once the report's semantics for a flow series are decided.

## 7. Decision

Awaiting the maintainer's approval to squash-merge this pull request into `main` (which also lands the
already-approved Phase 10), delete `feature/p9-memory`, close #97 with a comment citing the merge
commit, and launch the next phase as scoped in section 6.
