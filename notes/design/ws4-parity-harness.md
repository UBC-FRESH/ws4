# The parity harness: what WS4 is compared against, and what it found

The project claims WS4 works as a replacement for the established implementation. This note records
what the comparison is, so a reader can judge it, and what it found.

## What is compared, and why that

The reference sample ships **its own outputs** for the road model: `cost_destination.<mill>.csv` holds
`NODE,SUM_HAUL` — the sum of the segment haul rates from that network node to that mill, and `-1` where
it can reach no such route. That is the same quantity WS4's route model computes, from the same tables,
so comparing them tests the **routing** rather than the data: WS4 loads the reference's segments,
destinations and linkages, computes its own least-haul-cost route for every block and destination, and
checks the sum against the reference's value for that block's node.

The comparison covers the C5-class sample: 36 722 segments, 27 231 vertices, three mills, 12 568 blocks,
which is 37 701 node-and-mill comparisons that a block is linked to.

## Definitions and tolerances, stated

- **Unreachable.** The reference writes `-1`; WS4 returns no route. The two are treated as the same
  answer, and a disagreement in either direction is a difference.
- **Numeric tolerance.** An absolute 1e-6 on the summed haul rate. Both sides sum the same `HAUL`
  column, so the only slack needed is floating-point order.
- **Nodes with no block.** Skipped. WS4 routes from blocks, so a node no block links to is not a
  comparison it can make; the reference reports every node in its vertices table.

## What it found

**No differences.** `python scripts/acceptance.py --roads-sample <sample>/roads` reports

```
parity      PASS  WS4 agrees with the reference on all 37701 routed node-and-mill pairs
```

including every node the reference marks unreachable that a block is linked to. That is a real result
for the routing claim: same network, same least-haul-cost definition, same sums.

## What it does not cover

Stated rather than implied, because the harness is the thing a reviewer will lean on:

- **Schedules and account values.** The sample ships no account report from the reference, so
  "the same schedule produces the same accounts in both tools" is *not* demonstrated here. That is the
  largest remaining gap in the replacement claim, and it needs reference outputs that do not exist in
  the sample.
- **Build and maintenance costs.** The reference ships haul costs per node only; the per-period build
  and maintenance accounts are compared by the WS4 suites, not against the reference.
- **The compiled matrix** is compared by the existing `--case` mechanism in the same tool, against a
  reference matrix directory. Both comparisons live in `scripts/acceptance.py`.

## How to run it

```bash
python scripts/acceptance.py --roads-sample /path/to/sample/roads
```

It prints one line per check and exits non-zero if the parity check finds a difference. Without
`--roads-sample` the check skips, so the tool still runs on a machine that has no reference sample.

## The sample the comparison should run on

The parity comparison needs **one** sample that both tools read, and it needs the reference to report
its account values for a schedule both tools can be given. Two things follow.

**Which sample.** The lab's installer carries a C5 demonstration model — the model tables under
`tracks/`, the inventory and topology under `blocks/`, the four road tables under `roads/`, the
workbooks under `yield/`, and scenarios under `analysis/`. The build extracted on 2026-10-14 (from the
2019 installer) is the one every C5 figure in the repository so far has used, including the benchmark
figures and the routing parity comparison. A newer installer (its inner executable dated 2026-07-29)
was supplied on 2026-10-18, but **it cannot be extracted here**: `innoextract` 1.9, its current release
1.9, and its development build supporting Inno Setup up to 6.3.3 all reject it with "unexpected setup
loader revision: 2" and a loader checksum mismatch, so it is a protected or non-standard build. The
sample inside it therefore has to come from an installed copy rather than from the file.

Parity does not need the *newest* sample, only the *same* one on both sides, so either of these works:

1. run the comparison on the sample already extracted here, which is what the WS4 figures were
   measured against; or
2. have the newer build's `sample/` directory zipped from the installed Windows copy and drop it in,
   which changes the baseline but keeps the method.

**What the reference must report.** A schedule, and the account values it produces per period. The
reference's own sample ships no account report — that is the gap P8.5 exists to close — so the
comparison needs a run that emits one. The cleanest scenario to ask for is a **fixed schedule**, not
an optimized one: pin the blocks, treatments and years in a scenario file, run it in both tools, and
compare the per-period account values. That isolates the simulation, which is what the replacement
claim is ultimately about, and it avoids comparing two different searches. A no-treatment schedule is
worth including as the first case, since it exercises the curves, the tracks and the strata with no
scheduler in the way at all.

## What to export, and how to check it

The comparison is built. `scripts/acceptance.py` can replay a reference's own schedule in WS4 and
compare the accounts, so all that is missing is one export from a licensed reference run.

Export, from a single run of the C5 sample:

1. **`schedule.csv`** — what the reference actually did: one row per decision with a block, a
   treatment and a year. Column names are matched loosely (`block_id`/`block`, `treatment`,
   `period`/`year`), so the reference's own header is fine.
2. **`account_values.csv`** — the realized account values for that same run, one row per account per
   year (`year`, `account`, `value`; the same loose matching applies).

Then check them:

```bash
# once: compile the sample into a dataset WS4 can replay over
python scripts/benchmark.py --scenario c5 --sample-dir <sample> --years 3 --workdir tmp/parity

python scripts/acceptance.py \
    --accounts-report <the export directory> \
    --accounts-dataset tmp/parity/c5_compiled
```

The check replays the exported schedule and compares every account-year cell both sides report, over
the horizon the **reference's own last reported year** sets — not the schedule's last decision, which
under-simulates whenever a reference reports years its last decision does not reach, and reports every
one of them as a difference. (A schedule that decides *beyond* the reported years is the opposite case
and is reported as a difference in so many words.) It uses a **relative tolerance of 1e-4**, because a reference export is typically rounded where WS4's
values are not; an account that only one side reports is a difference too, and is labelled as such,
since that is exactly the kind of finding the comparison is for. A **no-treatment schedule** is worth
running first: with no scheduler in the way it exercises the curves, the tracks and the strata, and if
that agrees the rest of the comparison is about treatments rather than about growth.

### The check rehearsed against itself

While preparing the Windows run, the comparison was exercised end to end without a reference: an
export was written from WS4's own simulate on the C5 sample (300 blocks, `schedule.csv` and
`account_values.csv`), the check was run on it, and then on a copy with one value deliberately
multiplied. The matching export **passes** — "WS4 reproduces the reference's 113 account-year
values" — and the perturbed one **fails** with exactly that cell named. This is what caught the
horizon defect above, which no test had seen because the test helper derived the horizon the same
wrong way the check did.

Until a report exists, the note's earlier section stands: the accounts-parity claim is specified and
checkable, and **unverified**.

## The sample, packaged

The sample is a C5-class demonstration model extracted from the lab's installer: **139 files across
nine subdirectories** (274 MB uncompressed, 88 MB zipped) — the model tables under `tracks/`, the
inventory and topology under `blocks/` and `data/`, the road network under `roads/`, the workbooks
under `yield/`, the scripts and scenarios under `scripts/` and `analysis/`.

It is packaged for the reference run in the workspace's untracked `tmp/` directory:

- `tmp/c5-sample-for-parity.zip` — the whole `sample/` tree, sha256
  `cd0aa1f367720b6e63861437fd725660470aadffeb313331f8b5923eb2cde6fa`;
- `tmp/c5-sample-for-parity.sha256` — a digest for every file it contains, so a copy can be verified
  rather than assumed.

The files the comparison actually reads are these, and a copy with different digests is a different
sample:

| File | sha256 (first 16) |
| --- | --- |
| `tracks/tracknames.csv` | `b20feef30e104f2c...` |
| `tracks/strata.csv` | `3709ff3a89947d91...` |
| `tracks/treatments.csv` | `668d05c5fba9f75a...` |
| `tracks/blocks.csv` | `0326c3139f2c1af7...` |
| `tracks/features.csv` | `f4ccd2b81dcdedf8...` |
| `tracks/products.csv` | `8549cd71aa25580a...` |
| `tracks/curves.csv` | `f543f2d04e52ca80...` |
| `blocks/topology_blocks_200r.csv` | `f6d1549efa15e106...` |
| `blocks/blocks.shp` | `920e185a1d5fc88e...` |
| `roads/vertices.csv` | `6af6fa0b46f684ce...` |
| `roads/segments.csv` | `734a5d4b709b6efc...` |
| `roads/destinations.csv` | `41c03fdee82ca3c3...` |
| `roads/linkages.csv` | `8050ebd24a2c805a...` |
| `roads/cost_destination.MILL1.csv` | `a237e9f49ba5c331...` |
| `roads/cost_destination.MILL2.csv` | `0fe431c98e1f32de...` |
| `roads/cost_destination.MILL3.csv` | `a237e9f49ba5c331...` |

One key is deliberately not listed: `tracks/protoaccounts.csv`. This sample does not ship one — the
compiled dataset derives the proto-accounts table — and the matrix comparison treats a reference file
as optional, comparing only the tables that are present.

## Growth, checked against the reference's own yields

The accounts comparison needs a licensed reference run. Its foundation does not: the sample ships the
reference's own yield curves, and WS4 compiles yield curves from the same matrix, so growth can be
compared today. That is worth doing, because it narrows what the Monday result can mean — if the
growth agrees, a difference in accounts is about treatments, the scheduler and the accounting, not
about the curves underneath them.

**What is compared.** The reference's `yield/*.xml` holds its model's curves, one per stratum and
species, as `Y1.Conif` … `Y9.Decid`, each a list of `(x, y)` points. It also ships the same numbers as
a printed Woodstock table, `Woodstock/C5_yld.prn`; the XML is used because it carries the age of every
value, where the printed table is a bare sequence of values against an assumed grid. Both files were
read while building the check and agree, so the XML is a faithful stand-in for the printed table.

**How.** `scripts/acceptance.py --yield-sample <sample>/yield --yield-dataset <compiled>` resolves each
reference curve to the compiled curve that reproduces most of its ages, then compares every point
there. A missing age, a value outside **5e-3** — the reference's artefacts print two decimals, so half
a unit is the tightest honest tolerance — or a yield curve with no counterpart is a difference.

**The result on the C5 sample.** `growth PASS: WS4 reproduces the reference's 959 yield-curve points,
with 7 recorded upstream conflict(s) reported.` Every one of the 18 curves is covered, no age is
missing anywhere, and every value agrees but for the conflict below.

**The one conflict, and it is the sample's, not WS4's.** At offset age 7 the Decid curve is
`0.001` in the legacy matrix (`tracks/curves.csv`, nine rows) that WS4 is given and ingests, and
`0.01` in the same sample's own `C5_yld.prn` and `ForestModel_C5_strata.xml`. The matrix holds no
value of exactly `0.01` anywhere, and WS4 compiles what the matrix says, so the difference is upstream
of it. It affects seven of the eighteen curves (every Decid stratum shares the one curve), the
magnitude is about 0.009 m³/ha against a curve that peaks at 13.39, and the check **names** it rather
than absorbing it into the tolerance: a different value at that age on a different curve still fails,
and so does a value that differs by more than the conflict's own size.

This is the kind of finding the check exists for. It is also the kind that would otherwise surface on
Monday as an unexplained account difference.

## The 2026 sample: what arrived, and what it took

The reference's 2026 build runs the model in `sample_2025` (the 2019 sample will not load in it), and it
writes its own report tree per scenario: `scenario/schedule.csv` (`BLOCK, DELTA, AGE, TYPE, TREATMENT`,
where `DELTA` is "the time in the future of the proposed treatment" — the year) and
`scenario/targetSummary.csv` (`TARGET, PERIOD, YEAR, PERIODWIDTH, MINIMUM, MAXIMUM, CURRENT, ...`), plus
a report per target and family. `null` is the no-treatment case and `base` the optimized one.

**The check now reads that export as it lands.** `scripts/acceptance.py --accounts-report <a scenario's
report directory> --accounts-dataset <compiled>` takes the reference's own file and column names
(`targetSummary.csv`, `TARGET`/`YEAR`/`CURRENT`, `BLOCK`/`TREATMENT`/`DELTA`), so nothing is converted
between the two tools and nothing can be lost in a translation.

**Three things had to be right before the numbers meant anything.**

1. **The reference's periods are not WS4's years.** `PERIOD 0` is the initial snapshot at year 0, and a
   later period labelled `YEAR` with `PERIODWIDTH` covers that many years **ending** at `YEAR` — period
   1 is years 1-10. What it reports for a period also depends on the account: a product accumulates
   within the period and is reported as the period's total, a feature is a level reported at the
   period's year. Comparing its period totals against WS4's single years made every product account look
   wrong by an order of magnitude; under its own convention they agree.
2. **A report rounds as it computes.** Its values are rounded to three decimals per contribution and a
   period's value is a sum of them, so a relative tolerance alone reports its own arithmetic: across
   both scenarios' 2,646 cells, 101 cells differ at a relative 1e-4, 3 at a 1e-3 floor, and none at
   **2e-3** — two units in the third decimal, which is the tolerance the check uses.
3. **The matrix builder mis-attributed a split block's track** (P9.8, #110): `blocks.csv` lists a block
   more than once, a managed and an unmanaged portion each with its own area on its own track, and the
   builder derived the track from a block-keyed dict while keeping the row's area. That alone was worth
   30-45% on every managed and unmanaged account. It is fixed, and the comparison against the reference
   is what found it.

**The result, on both scenarios:**

| Scenario | Cells | Reference targets with no WS4 account | Verdict |
| --- | ---: | ---: | --- |
| `null` (no treatment) | 1,323 | 178 | **PASS** — every account-period value reproduced |
| `base` (13,377 treatments) | 1,323 | 178 | **PASS** — every account-period value reproduced |

The 178 are the reference's own ratio, flow and route targets (`ratio_route_haul_MILL1`,
`flow_even_product_Yield_Conif`, `patch_harvested_10_50_size`, and so on): they are derived quantities
rather than account values, so they are not compared, and the check says how many it left out.

**What this does not yet cover.** The reference's derived targets — the ratios, the flow constraints,
the patch size distributions — are exactly what a spatial model is for, and they need their own
comparison. On this sample the routing parity check also fails on 10 of 25,134 node-and-mill pairs, and
the reason is visible in the sample rather than in WS4: its `roads/` folder mixes vintages
(`destinations.csv` lists two mills where three `cost_destination.*.csv` files ship, and MILL3's is dated
2018 where the others are 2025, with the column renamed from `SUM_HAUL` to `SUM_LENGTH`). The growth
check finds no `Y<n>` curves in this sample's lookup model and needs retargeting.

## The derived targets: what the reference means by each

The reference declares every derived account in its own model file (`analysis/C5.pin`), so none of them
has to be guessed at. Read from there, with the scale factor each applies:

| Reference account | Numerator | Denominator | Scale |
| --- | --- | --- | --- |
| `ratio.VQO.<code>` | `feature.VQO.<code>` | `total.feature.VQO.<code>` | — |
| `ratio.ECA.Recovery.<ws>` | `feature.ECA.Recovery` | a per-watershed area from a shapefile summary | `100 / area_ha` |
| `ratio.route.build` | `route.total.build` | `route.total.conifer` | `10000` |
| `ratio.route.maint` | `route.total.maint` | `route.total.conifer` | `10000` |
| `ratio.route.haul.MILL1` | `route.haul.MILL1` | `product.Mill1.Yield.Conif` | `10000` |
| `ratio.route.haul.MILL2` | `route.haul.MILL2` | `product.Mill2.Yield.Conif` | `10000` |
| `ratio.route.current.<ws>` | `route.current.<ws>` | the watershed's area | `1000 / area_ha` |
| `ratio.route.recent.<ws>` | `route.recent.<ws>` | the watershed's area | `1000 / area_ha` |
| `ratio.route.lifetime.<ws>` | `route.lifetime.<ws>` | the watershed's area | `1000 / area_ha` |

**Which of them WS4 can compute today, and what each is missing:**

| Family | WS4 has | Missing |
| --- | --- | --- |
| `ratio.ECA.Recovery.<ws>` | the numerator (`feature.ECA.Recovery` is a WS4 account) | **the watershed**: the areas come from a *complete-coverage* shapefile (`../data/fragments.shp`, `WATER_CODE`) that includes non-forest land, and each block's watershed comes from the same source. Neither is in the block matrix WS4 ingests |
| `ratio.VQO.<code>` | nothing on either side | the `feature.VQO.<code>` features are **not in the matrix at all** — the VQO zones are a model layer, not a block attribute |
| `ratio.route.build`, `.maint` | WS4 computes route build and maintenance costs, and routes conifer to the mills | those costs are not *accounts* in its compiled set, and `route.total.conifer` has no WS4 counterpart |
| `ratio.route.haul.MILL1/2` | WS4 computes a least-haul-cost route per block and mill, and routes the volume | `route.haul.MILL1` and `product.Mill1.Yield.Conif` are not accounts WS4 reports |
| `ratio.route.current/recent/lifetime.<ws>` | route build age classes exist in its route model | the watershed assignment and areas, as above |

So the ratios are **not** a case of adding a division to something WS4 already produces: four of the five
families need an input WS4 does not ingest (a complete-coverage watershed table, or the VQO zones), and
the fifth needs route costs and mill volumes exposed as accounts. Which of those WS4 should take on is a
scoping decision, and the next section states the order this note recommends.

## The route accounts: the same report, different accounting

The reference ships its own route cost report (`route/routeCostMILL<mill>.csv`), and it is the **same
table** WS4 writes (`route_cost_report.csv`) — the same columns, including the period and year a change
made WS4's report carry. That makes the comparison direct, and it shows the differences are in the
*accounting*, not the routing (which agrees apart from the sample's stale third mill):

| Column | Reference, period 1 (year 10, width 10) | WS4, period 1 (year 1, width 1) |
| --- | ---: | ---: |
| `LENGTH` | 1,149,647 | 827,926 |
| `BUILD_EXPENSE` | 3,660,367 | 2,038,700 |
| `HAUL_EXPENSE` | 11,174,512 | 10,549,815 |
| `MAINTAIN_EXPENSE` | 1,126,465 | **195,991,566** |
| `TOTAL` | 15,961,345 | 208,580,081 |
| `VOLUME` | 1,029,670 | 1,646,192 |
| `AVERAGEHAULDIST` | **50.3** | **65,261** |
| `AVERAGEMAINTCOST` | **1.1** | **119.1** |

Three of those are *shape*, not error: the reference reports a ten-year period where WS4's report here is
per year, and distances are kilometres against metres. Two are not: **maintenance is about a hundred
times apart** in both the expense and the per-unit cost, and **the volume is 1.6× apart** because WS4's
route volume is every product routed whereas the reference's mill product is the conifer share.

So the derived **ratios cannot be compared honestly yet**: `ratio.route.haul.MILL1` is
`route.haul.MILL1 / product.Mill1.Yield.Conif × 10000`, and both of its sides have to mean the same thing
in both tools first. That reconciliation belongs with the mill-set task, since it is the same subject and
the same report, and the order it should be done in is: maintenance, then the reporting window, then the
per-product split of the routed volume (which the ledger already records and only has to expose).

## The flow targets: the values already match, the reporting is what was wrong

The reference declares four flow accounts in its model file, all scaled by 100 and applied per period:

| Reference account | Account it constrains | Window |
| --- | --- | --- |
| `flow.ndy.feature.Yield.Conif` / `.Decid` | `feature.Yield.managed.Conif` / `.Decid` | `ndy(periods-9, periods, -1)` — the last ten periods |
| `flow.even.product.Yield.Conif` / `.Decid` | `product.Yield.managed.Conif` / `.Decid` | `even()` — the whole horizon |
| `flow.even.product.Yield.Conif.Mill1` / `.Mill2` | the same account per mill | as above |

Comparing them needed one fix, and it was a convention fix: **`flow_values` built its periods
start-labelled**, which P11.1's sweep had not reached. With the periods ending at their year — the same
convention as `Target.cell_years()` — WS4's flow values reproduce the reference's to four decimals:

| Period | Year | Reference | WS4 |
| ---: | ---: | ---: | ---: |
| 1 | 10 | 40.244 | **40.244** |
| 2 | 20 | 6.086 | **6.086** |
| 3 | 30 | 2.722 | **2.723** |
| 4 | 40 | −4.435 | **−4.435** |

**What is still open, and it is reporting rather than arithmetic.** A flow series does not have one value
per period of its window: ``even`` omits its **reference period** (which contributes no value of its
own) and ``ndy`` needs the period before its window only as a base. So a report that emits one row per
period — which is what the reference's `targetSummary.csv` does, with a zero for the snapshot — has to
say which period each value belongs to. `flow_period_ends()` now exposes WS4's own period grid for that,
and the report uses it; what remains is aligning the omitted period with the reference's row, and then
the comparison belongs with the other derived targets.

## The patch distributions: the comparison runs, and it disagrees

The reference's own model file defines them: `addPatchTarget("feature.young", "patch.young.<class>", lo,
hi)` with the classes 0-50, 50-150, 150-250, 250-2500 and 2500-plus hectares, and
`addPatchTarget("product.harvested", "patch.harvested.<class>", ...)` with 0-10, 10-50, 50-150 and
150-plus, over `blocks_topology_200r10.csv` at a 100 m search distance. WS4 can express the first family
today — a patch account needs a criterion, and `feature.young` is one — so the comparison runs:

| Quantity | WS4 / reference, median over the periods |
| --- | --- |
| `area` | 0.81 to 1.12 across the four classes |
| `size` | 0.88 to 1.22 |
| `frequency` | 0.91 to 1.08 |
| `shape` | **0.20 to 12.39** |

**What that says.** The areas, sizes and frequencies are within about 10–20% — the same order, so the
patches are being formed and classed comparably, and the difference is systematic rather than random.
The **shape** metric is definitional: WS4 reports compactness from 0 to 100 and the reference reports
something else, on a different scale. Three of the reference's seven sub-quantities have no WS4
counterpart at all — `blocks`, `freqpercent` and `attractor` — and the reference's last class is labelled
`2500_plus` where WS4 labels the same class by its upper bound, `2500_9999999`.

**And the second family cannot be configured yet:** the reference's harvested patches use
`product.harvested` as their criterion, which is a *product* rather than a feature, so WS4 has nothing to
point a patch account at. That is 28 of the 63 targets.

### The patch gap, measured

Chasing the 10-20% means asking first whether it is a scale or a distribution, and the aggregates answer
that: over the periods, WS4's total young-patch **area is 0.92** of the reference's, its **patch count
1.03**, and its **mean patch size 0.96** — so the two agree on how much young forest there is and how it
is broken up, and the per-class differences are the distribution moving rather than a misplaced
definition. Individually, though, the cells are not close:

| Bound on the relative difference | Cells within it |
| --- | ---: |
| 1e-4 | 5.7% |
| 1% | 7.1% |
| 5% | 16.4% |
| 10% | 27.7% |
| 20% | 50.3% |
| 50% | 74.7% |

| Quantity | Median | 90th percentile |
| --- | ---: | ---: |
| `area` | 14% | 34% |
| `frequency` | 9% | 33% |
| `size` | 18% | 40% |
| `shape` | 83% | >1000% |

So: the aggregate structure agrees to within about 8%, the individual class-period cells typically differ
by 10-30%, and `shape` is a different quantity altogether. The next question is which patches *form* in
which period — where WS4's components merge or split differently from the reference's on the same
schedule — and that is a per-period comparison of the components rather than of their sums.

### The patch sub-accounts, and what each one is

The reference's own documentation for its patch sub-accounts settles what each one means, and it corrected
two of this note's earlier readings:

| Sub-account | What it is | WS4 |
| --- | --- | --- |
| `area` | the total area in the class, in hectares | the same, and agreeing to a median 12% |
| `blocks` | the **mean number of blocks a patch of the class holds** — not a count of blocks | added, from the class's own membership: median 7% |
| `size` | the class's **criterion** sum as a percentage of the criterion over all classes | WS4 reports the area share, which is the same thing for a 0/1 criterion: median 15% |
| `shape` | the perimeter relative to a circle of the same area: 1 or more, higher being more dendritic | **the same definition** — WS4's compactness is its inverse square — so the difference is the patches, not the metric: ~32% once converted |
| `frequency` | the number of patches in the class | the same: median 8% |
| `freqpercent` | the class's share of all patches | added: median 3.5% |
| `attractor` | the account that draws the average patch size towards the class; it is a switch rather than a measurement | not reproduced: the reference reports values of its own for it, and WS4 has no counterpart |

That corrects this note twice over. `shape` is not a different quantity — it is the same one, and what
differs is which patches form. And `blocks` is a mean per patch, which WS4 already held in its state and
simply did not expose.

**The comparison now covers 630 cells over six quantities**, 45% of them within 10% of the reference, and
the five `attractor` cells are the only ones it cannot make. The remaining differences are the *patches
themselves*: WS4's aggregate young-patch area is 0.92 of the reference's, its patch count 1.03 and its
mean patch size 0.96, so the components merge or split differently on the same schedule, and that is what
is left to chase.

### What the reference's two tables ask

Comparing routing needed one more realisation, and the numbers settle it. The 2019 sample ships
`cost_destination.<mill>.csv` with `NODE,SUM_HAUL` — the sum of haul rates along the route the reference
would choose — and WS4's least-haul route reproduces it exactly (37,701 comparisons). The 2026 sample
ships the same file with `NODE,SUM_LENGTH`, and for the ten nodes where the two disagreed the reference's
value is the **shortest path by distance**, not the cheapest route:

| Weighting | Haul sum | Length | Build |
| --- | ---: | ---: | ---: |
| haul (what WS4 minimises) | 12.36 | 97,169 m | 88,715 |
| haul + build | 13.83 | 101,947 m | 13,597 |
| **length only** | 19.25 | **81,098 m** — the reference's number | 300,663 |

So the table answers "how far is this node from the mill", and the like-for-like comparison is WS4's own
shortest distance (`RouteNetwork.route_length`), not the length of the route it would choose. With that,
and with the check skipping a table for a destination the model no longer declares, **WS4 agrees with the
reference on all 25,134 routed node-and-mill pairs** of the 2026 sample.

The general lesson is worth keeping: when a comparison disagrees, the first question is whether the two
sides are being asked the same thing. Three of this phase's largest "differences" were exactly that — the
period convention, the patch `shape` metric, and this one.

### The mill products: the mechanism, and what it exposed

A route account can now name the product whose volume it tracks, so `product.Mill1.Yield.Conif` is
expressible the way the reference means it — a volume account for one product at one destination, tested
both ways (the filtered account sums only that product; a *cost* account naming a product is refused
rather than ignored, because the ledger prices a route and not a tonne of it).

Pointing it at the reference's own numbers exposed the next question rather than closing it. WS4 routes
**24,349** of `product.Yield.managed.Conif` to Mill 1 over the periods, where the reference reports
**1,029,670** — and its all-product routed volume is 1.6× the reference's, so the difference is not
quantity but *attribution*: the products WS4's route model assigns, and the volume it assigns to each,
are not the reference's. The reference makes this explicit in its model — it marks the conifer yield as
an **exclusive** account split between the two mills, and duplicates each mill's share into its
destination and into the conifer total — which is a *proportional allocation* between destinations rather
than WS4's per-block least-cost routing. That is the question #114's route ratios now wait on.

