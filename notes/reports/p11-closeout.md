# Phase close-out report: P11 the derived targets and the sample's own files

Phase: P11
Parent issue: #112
Branch: `feature/p11-derived-targets`
Pull request: opened against `main`
Report written: 2026-10-18

## Recommendation

**Close P11. Launch P12 (Spatial decision match)**, scoped in section 6: the three capabilities this
phase named — a patch criterion that can be a product, the reference's destination policy for its mill
products, and a parity mode with the traffic-weighted maintenance behind it — plus the two smaller
reporting gaps.

## 1. Objectives and acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| A target written the reference's way means the same thing in WS4, verified against the reference's own period values | a target's period **ends** at its year and only a `product.` account accumulates; measured against the reference's own values, products were 24% low and features **ten times high** before, and agree to six or seven digits after (`acbfe89` and earlier) | met |
| Each family of derived targets is compared and agreeing, or has a measured reason and a recorded gap | **flows** compared, matching to four decimals and included in the acceptance run; **patches** compared over 630 cells with two measured stops; **ratios** specified and blocked on a named modelling difference | met, two families by comparison and one by recorded reason |
| The routing parity check compares against the model's actual destinations | the check skips a table for a destination the model does not declare, and picks the quantity the table's own column names; **WS4 agrees with the reference on all 25,134 node-and-mill pairs** of the 2026 sample | met |
| The growth check reads the 2026 sample's shape and passes | it reads a 2019 `<curve>` element or a 2026 `<curvetable>` table and reports **959 yield-curve points** reproduced | met |
| The dashboard green at every commit, with the docs and docstrings gates | seven gates GREEN at the evidence head; the deviations below are recorded, and each was fixed rather than waived | met |

## 2. What shipped

**A convention, and its consequences.** A target now names the year its period **ends** on, and only an
accumulating account sums its period: everything else — a feature, a patch, a size class's share — is a
level read at that year. Three separate paths had to follow it (the objective, the flow windows, the
patch accounting points), and the docs that described the old mapping are corrected. Products went from
24% low to six-digit agreement; features from **ten times high** to six-digit agreement.

**The comparison, and what it forced.** The acceptance check now reads the reference's own export as it
lands — `targetSummary.csv`, `TARGET`/`YEAR`/`CURRENT`, `BLOCK`/`TREATMENT`/`DELTA` — and covers
**1,383 account-period and flow values** on both scenarios, the flow series included. Three of the
biggest "differences" it reported were the comparison asking a different question rather than a defect:
the period convention, the patch `shape` metric (WS4's compactness is its exact inverse square), and the
routing table (the 2026 sample ships a distance where 2019 shipped a haul sum).

**Two WS4 defects fixed.** The route ledger charged each used segment's maintenance **per routed flow**,
making maintenance a function of traffic and putting it about **170×** the reference's figure; with the
reference's reading, maintenance is 1.12 of it. And a volume account can now name the product it tracks,
with a destination **allocation** that partitions a master product across the destinations it is routed
to and accounts for the remainder.

**A comparison widened.** The patch family is compared over **630 cells across six quantities** — area,
blocks, size, shape, frequency and freqpercent — after the reference's own documentation of its
sub-accounts corrected two of this project's readings and supplied two sub-accounts WS4 already held the
data for.

## 3. Gate evidence

`python scripts/dashboard.py` at the evidence head: lint, format, types, tests, validator, docs and
docstrings all GREEN; **526 tests** in the suite.

## 4. CI evidence

| Run ID | Head commit | Conclusion |
| --- | --- | --- |
| (the pull request's own runs) | see the pull request | the four jobs, green |

## 5. Deviations

| Deviation | Cause | Remedy |
| --- | --- | --- |
| Three comparisons reported differences that were not defects | the two sides were being asked different questions: the period convention, the patch `shape` metric, and the routing table's quantity | each was pinned from the reference's own numbers before anything changed; the lesson is in the parity note |
| The first destination-allocation run doubled the mill volumes | the configuration had both a volume route account **and** an allocation writing the same account name | caught by the master guard, once the guard checked every year either side knows rather than only the master's own; recorded |
| `shape` was first read as a different metric | WS4 reports compactness 0–100 and the reference's shape is 1-and-up, which looks like a different quantity | the reference's own documentation showed it is the same quantity; the code was right and the *patches* differ |
| The trend of one harness flag | `--yield-sample`, `--accounts-report` and `--roads-sample` now feed checks that overlap in subject | accepted deliberately: each check owns one input shape, and the derived families are named by the comparison that reads the same export |

## 6. Next phase: P12, spatial decision match

The phase that takes the claim from "the account values and the routes match" to "the spatial decisions
match". Its tasks, in order:

1. **A patch criterion can be a product.** The reference's harvested patches use `product.harvested`,
   and WS4's patch state evaluates a criterion as a feature: configured, it runs and returns *every cell
   zero*. That is 28 of the reference's 63 patch targets, and it is the largest single hole left in the
   patch comparison.
2. **The reference's destination policy for its mill products.** WS4 sends each block's product to its
   cheapest mill (118,498 / 251,703 for the conifer yield); the reference's near-balanced 54/46
   (1,029,670 / 892,306) comes from its own exclusive-account allocation under mill minimums. The route
   ratios' denominator is that product, so the ratios are comparable only once the two tools decide the
   split the same way.
3. **Report the route accounts over the model's periods.** WS4's route report is per year where the
   reference's is a ten-year period; the ledger already takes a period width, so this is wiring rather
   than arithmetic.
4. **The `attractor` sub-account as the reference defines it.** Its values draw the average patch size
   towards a class; WS4 reports a flag.
5. **A Patchworks-parity mode**, with the **traffic-weighted maintenance** behind it as the first
   deliberate divergence — the maintainer's direction, specified as an affine cost that is zero at no
   traffic and jumps to a fixed intercept once any traffic uses a road.
6. **Compare the patch components against a reference export of patch membership.** The export the
   reference ships holds class aggregates and map images, not membership, so this needs a new export —
   carried as a task, not held open.

## 7. Decision

Awaiting the maintainer's approval to squash-merge this pull request into `main`, delete
`feature/p11-derived-targets`, close #112 with a comment citing the merge commit, and launch P12.
