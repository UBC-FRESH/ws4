# Phase verification report: P3 Verify

Phase: P3 Verify
Parent issue: #26
Branch: `feature/p3-verify`
Evidence head: the P3.7 commit (this report); the task commits are listed per finding below.
Date: 2026-10-15
Status: verification complete; queued for the phase close-out.

## 1. Method

Each acceptance criterion in the P2 scope is checked with a repeatable command or test, and the
evidence is recorded in `CHANGE_LOG.md`, in a focused note, or in a committed test. The checks are:

- `python -m pytest` (unit, contract, integration, and property tests, with the coverage gate)
- `python scripts/acceptance.py --case ...` (the builder against reference matrices, and the
  synthetic end-to-end checks)
- `python scripts/benchmark.py` (scale and performance)
- the C5 sample end to end (`notes/functional-test.md`)
- a clean-checkout install, command-line run, and docs build (`notes/packaging.md`)

## 2. Findings

| Task | Check | Result | Evidence |
| --- | --- | --- | --- |
| P3.1 | Acceptance checks | met | `notes/acceptance.md` (`47f47f2`) |
| P3.1 | Matrix builder vs reference | met: 9 of 9 core variants match on tracks, strata, treatments, blocks, features, products, and `protoaccounts` | `scripts/acceptance.py` |
| P3.1 | Simulator, C5 | met: 0 validation problems; 30 years in 4.2 s | `notes/acceptance.md`, `notes/functional-test.md` |
| P3.1 | Optimizer, roads, API | met | `scripts/acceptance.py`, `tests/` |
| P3.2 | Determinism and reproducibility | met | `2189229` |
| P3.2 | Run directory self-describing | met: `summary.json` and `dataset.json` record the dataset manifest | `ws4/model/schema.py` |
| P3.3 | Reference regression and invariants | met: a committed fixture, expansion property tests, strengthened schema invariants | `tests/fixtures/matrix/`, `3fb90bf` |
| P3.4 | Spatial constraints | met after P3.8 | `f71c7e7`, `e21eb92` |
| P3.5 | Scale and performance | met: two hot paths fixed (builder parse cache; positional yield assignment) | `notes/performance.md` (`7d4a7f7`) |
| P3.6 | Packaging and docs | met: clean install, CLI end to end, docs `-W`, site HTTP 200 | `notes/packaging.md` (`cd45a24`) |
| P3.7 | Deferred-item triage | met: every item has a reason and a target phase | `notes/backlog.md` |

Gates at the evidence head: `python -m pytest` reports 264 passed at 94.28 percent branch coverage
(the gate is 90), and `python scripts/dashboard.py` reports `OVERALL: GREEN`.

## 3. Gaps found and their disposition

| Gap | Found | Disposition |
| --- | --- | --- |
| No enforcement of adjacency, a maximum opening size, or green-up | P3.4 | Closed in P3.8 (`ws4/patch/constraints.py`; simulator report; optimizer penalty with an explicit override) |
| A run directory did not identify its dataset | P3.2 | Closed in P3.2 (`dataset_reference`) |
| The builder re-parsed each select expression per fragment | P3.5 | Closed in P3.5 (parse cache; build 3.79 s to 1.66 s at 100 038 fragments) |
| A per-curve `.loc` setitem dominated the simulator | P3.5 | Closed in P3.5 (positional assignment; C5 30-year simulate 15.5 s to 4.2 s) |
| `ws4/patch/topology.py` is a stub that duplicates the loader | P3.4 | Recorded; target post-release |
| The wider operator set, GPU moves, tuners, portfolio, core-area rules, edge contrast, destination eligibility, route cost accounts, duplicate/meta accounts, unit conversion | P2 | Recorded with a target phase in `notes/backlog.md`; none is release-blocking |
| The full MKRf canonical model | P2 | Blocked on its generated XML |

## 4. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| The roadmap criterion "a warm start produces the same result as a cold start" did not hold | A warm start intentionally changes the initial solution | The criterion was corrected to determinism (same seed reproduces the same result), which holds |
| The Verify phase began with one task | It was scoped thin in P0 | Expanded to eight tasks (P3.1 to P3.8) with the maintainer's approval |
| The P3.4 gap needed a build move | A verification finding was a missing feature | Added P3.8 with the maintainer's approval and implemented the constraints |
| CI was red on the P2 branch (an undeclared `scipy` import) | The MIP layer imported `scipy` at module load | Fixed on the P2 branch before its merge; the import is now lazy |

## 5. Release recommendation

**Proceed to P4 (Release and deploy).** Every in-scope success criterion from the scope is met:

- A synthetic landscape compiles, simulates, and optimizes end to end from the CLI.
- The optimizer satisfies its targets within tolerance, and replaying its schedule reproduces the
  account values.
- The spatial constraints are visible in the outputs and are violated only by the explicit
  `--spatial-override`.
- The compiled dataset round-trips through the documented schema and validates against its manifest.
- A full run is reproducible from its configuration and seed.

The open items are enhancements and maintenance, none of which blocks a first release. Two deserve a
mention in the release notes: the full MKRf canonical model is blocked on external inputs, and the
wider operator set and the tuning portfolio are future work.

## 6. Next

Queue the P3 close-out: the pull request from `feature/p3-verify` into `main` and the phase report
`notes/reports/p3-closeout.md`.
