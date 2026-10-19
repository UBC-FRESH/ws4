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

## The route accounts: the same report, in the reference's own periods

The reference ships its own route cost report (`route/routeCostMILL<mill>.csv`), and it is the **same
table** WS4 writes — the same columns, and now the same rows. P12.3 gave the report the model's period
width, so a period is labelled by the year it ends at and carries that width, the extensive columns are
summed over the period's years, and the averages are recomputed from those sums — which is what the
reference's own arithmetic does: its `AVERAGEHAULCOST` is `HAUL_EXPENSE / VOLUME` to four decimals. WS4
writes the report **per destination** as well now, which is how the reference ships it (one table per
mill), and a period width of one still leaves one row per year, so nothing about the older report moved.

Compared over the twenty periods of the 2026 base scenario, same schedule and same periods:

| Column | MILL 1: reference / WS4 | MILL 2: reference / WS4 |
| --- | ---: | ---: |
| `VOLUME` | 15,371,727 / 16,617,632 (+8.1%) | 12,135,638 / 10,889,737 (−10.3%) |
| `TOTAL` | 187,025,907 / 150,580,419 | 180,525,485 / 161,730,453 |
| `BUILTLENGTH` | 1,440,618 / 1,713,065 | 1,926,641 / 2,211,294 |
| `HAUL_EXPENSE` | 138,919,438 / 88,248,589 | 112,074,151 / 67,071,801 |
| `LENGTH` | 18,757,567 / 49,207,309 | 27,277,007 / 90,145,237 |
| `MAINTAIN_EXPENSE` | 18,433,382 / 57,381,362 | 26,982,130 / 87,536,005 |
| `AVERAGEHAULDIST` | 877 / 1,075,870 | 1,023 / 1,236,013 |

**Three of those are explained, and they were the three worth fixing.**

1. **`VOLUME` is now the same quantity on both sides**, to within the destination policy. It is the
   delivered wood, not the delivered wood *and* the areas: WS4 had been routing **27 products** to the
   mills — `product.Area.managed.PL`, the `product.vph.*` classes, `product.total.Yield` — because a
   product with no entry in the eligibility map went to every destination. The report is what made it
   visible: its volume was **2.26 times** the reference's, and once a map that names products became the
   list of what is *delivered*, the two differ by the 8% and 10% that #122 measured in the destination
   decision itself.
2. **`AVERAGEHAULDIST` is a unit.** WS4 counts metres and the reference kilometres: per period WS4
   reports 53,794 m for MILL 1 against the reference's 43.9, so 1.2× rather than the 1,200× a raw ratio
   of the column suggests. The 1.2 is the same routing difference the other rows carry. Converting WS4's
   own column is a decision about its report rather than about the comparison, and is in
   `notes/backlog.md`.
3. **`BUILTLENGTH` was zero in the per-destination report**, because the per-destination state recorded a
   segment's build expense and never its built length. Writing the report per destination is what
   exposed it.

**One quantity is not explained: `LENGTH`, and what follows from it.** It is a segment-set quantity —
the length of the distinct road in use during a period, independent of how much wood travels it — so the
routed-product fix did not move it (49,207,309 before and after), and WS4 reports 2.6× the reference's
for MILL 1 and 3.3× for MILL 2. Maintenance is *consistent with* it on both sides rather than a separate
difference (1.17 a metre in WS4, 0.98 in the reference), and the haul expense being *lower* than the
reference's while more road is in use says the two runs use **different roads**, not different amounts of
wood. WS4's own figure is a property of the network it routes over (11,606 km of 36,721 segments) and is
well inside it. What the reference's `LENGTH` counts is not established from its own tables; the
candidate — that its report counts only the roads its own run has opened, where WS4 routes over the
whole planned network — is **unverified**, and is recorded as such in `notes/backlog.md` rather than
asserted.

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
| `attractor` | a per-patch size statistic (P12.4): zero exactly when the class holds no patches, and otherwise a fraction of the class's **mean patch area** that falls as the class grows | **refused**: the reference's own exported tables do not determine it, and WS4's old `1.0` flag was not a value |

That corrects this note twice over. `shape` is not a different quantity — it is the same one, and what
differs is which patches form. And `blocks` is a mean per patch, which WS4 already held in its state and
simply did not expose.

**The comparison now covers 630 cells over six quantities**, 45% of them within 10% of the reference,
and the `attractor` is the one sub-account it does not make — because the quantity is not in the export,
which is the next section. The remaining differences are the *patches themselves*: WS4's aggregate
young-patch area is 0.92 of the reference's, its patch count 1.03 and its mean patch size 0.96, so the
components merge or split differently on the same schedule, and that is what is left to chase.

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

A route account can name the product whose volume it tracks, so `product.Mill1.Yield.Conif` is
expressible the way the reference means it — a volume account for one product at one destination, tested
both ways (the filtered account sums only that product; a *cost* account naming a product is refused
rather than ignored, because the ledger prices a route and not a tonne of it).

The reference divides each master product among its destinations with `addExclusiveAccount`, and exports
the choice it made per block and per period, so the *decision* is in the export and can be compared
rather than guessed at. Two things followed, both measured (P12.2):

- **The reference's destinations are per master, not per mill.** Conifer may go to Mill 1 or Mill 2;
  **deciduous may go to Mill 2 only**, with `product.unutilized.Decid` for what reaches none. WS4 routed
  both products to whichever mill was nearest, so **62.7% of the deciduous area** went to a mill the
  reference's model does not give it at all — an error, not a policy difference. With the eligibility
  declared, `product.Mill2.Yield.Decid` agrees with the reference to **4 units in 2.78 million** over 21
  periods.
- **What is left is a planning decision, not a routing consequence.** WS4's rule is the reference's
  declared destinations, then the least haul-cost one. Against the reference's own exported choice that
  agrees on **12,266 of 13,377 conifer block-periods (91.7%)**; the rest is the reference holding Mill 1
  at a **delivery target of 800,000 a period** (its own `MINIMUM` and `MAXIMUM` for that target are both
  800,000, and the achieved value sits on it in 13 of 20 periods) and giving Mill 2 the remainder. Only
  631 of the reference's 7,257 blocks (8.7%) ever change mill between periods, and those are the ones
  the target moves.

The stale comparison this section used to carry — "WS4 routes 24,349 where the reference reports
1,029,670" — was a single *year* of WS4's against a whole *period* of the reference's, which is the same
mistake this project keeps finding: the two sides were not being asked the same thing. Over the horizon,
and over the same periods:

| conifer yield, periods 1-20 | Mill 1 | Mill 2 |
| --- | ---: | ---: |
| Reference, its own destination policy | 15,371,727 | 9,356,805 |
| WS4, least cost among the reference's own eligible destinations | 16,617,630 | 8,110,900 |
| difference | +8.1% | −13.3% |

### The destination allocation, and what is left of it

WS4 has the capability: a route configuration partitions a **master product across the destinations it
is routed to**, with an account for whatever does not move — which is how the reference expresses its
mill products. `resolve_allocation_values` takes the shares from the ledger's routed volumes and the
master's total from the simulated values, so the parts always sum back to the whole; shares that exceed
their master are refused rather than reported. The surplus account is declarable **per product**, because
the reference declares one per master: conifer has none, so an unreachable conifer block is dropped
rather than quietly filed under the deciduous surplus. Measured: none of the 7,257 blocks the reference's
schedule treats is unreachable from every one of its destinations, so this is not exercised on the 2026
sample.

`check_destinations` compares the decision and its consequences in one place: the reference's declared
splits are read from its own model file (`analysis/C5.pin`, the same source the flow targets come from),
WS4's model is built from them, and the two decisions are compared block-period by block-period. Where
the split leaves the reference **one** destination the mill product must be reproduced — and the
deciduous one is, to four units in 2.78 million — while where it leaves **several** the choice is free
and only the agreement is measured: 91.7% on conifer, and the conifer mill products differ by up to
**342,151** a period, which is the delivery target rather than an error. What remains for the route
ratios is that target: reproducing it means adopting the reference's allocation policy wholesale, which
changes where wood goes, so it belongs behind the parity mode (#125) rather than as WS4's only
behaviour.

One correction worth keeping: the first run of the allocation doubled the mill volumes, because the
configuration had both a volume route account *and* an allocation writing the same account name. The
comparison caught it because the parts then exceeded the master — which is exactly what the guard is for,
once it checks every year either side knows about rather than only the master's own.

### The growth check, retargeted for the 2026 sample

The 2019 sample states its yields as one `<curve id="Y1.Conif">` element per stratum and species; the 2026
sample states the same data as one **table** — `<curvetable split=",">` with an `Age` column and then a
column per curve, `Y1.Conif` through `Y9.Decid`. The check reads both shapes now, so the same comparison
runs on either vintage: every value of the reference's own yields against WS4's compiled curves, at a
tolerance set by the decimals the artefacts print. On the 2026 sample it reports **959 yield-curve points
reproduced** across all eighteen curves.

One property of the 2019 sample does not carry over, and it is worth recording: there the matrix held
`0.001` at offset age 7 on the Decid curve where the sample's own artefacts held `0.01`, which the check
reported as a conflict. The 2026 matrix holds **0.01** — 1,399 curves with that point and none with the
other value — so that conflict is a property of the 2019 sample's files, not of the model, and the check
has nothing to report here.

### Where the patch comparison ends, and why

The comparison covers the reference's `patch.young` family — **630 cells over six quantities** — and it
stops there for two reasons, both measured rather than assumed:

**The harvested family cannot be configured.** Its criterion is `product.harvested`, a *product* rather
than a feature, and WS4's patch state evaluates a criterion as a feature: pointed at a product it runs
without complaint and produces **every cell zero**, which is exactly the kind of silence worth refusing.
That is 28 of the reference's 63 patch targets. Making them comparable means letting a patch criterion be
a product — small, but it changes what a criterion *is*, so it belongs with the destination policy as a
modelling decision rather than a comparison fix.

**The components are not in the export.** The reference publishes patch *class aggregates* and map
*images* (`.png`), not patch membership, so a component-level comparison has no oracle. What can be said
is what the aggregates say: WS4's young-patch area is **0.92** of the reference's, its patch count **1.03**
and its mean patch size **0.96** — the structure is within about 8% — while the individual class-period
cells differ by a median of 9% to 18% depending on the quantity. So the components form comparably in
aggregate and differently in detail, and the instrument to say *where* is not in what the reference ships.

The `attractor` is the third, and P12.4 is what it is: the next section.

### The attractor sub-account: what the reference's own values say, and why it is refused

The reference reports a sixth sub-account per size class, `attractor`, and WS4 used to write a `1.0` for
it whenever an account declared one — a flag, not a value. P12.4 established what the reference's values
are, from its own numbers across both scenarios and all eight classes (360 cells), and the answer is that
**the reference's export does not determine them**:

- It is a **per-class landscape quantity, not a flag**: it is zero in exactly the cells where the class
  holds no patches, and non-zero everywhere else — checked over the no-treatment scenario, where the
  young classes empty out by period 10, and the optimised one.
- It is **not the class's mean patch size**: the class whose bounds are 50 to 150 hectares reports values
  of 15.7 to 21.3, and a mean of a class bounded below by 50 cannot be below 50. Nor is it the class's
  `size` share: the ratio of the two ranges from **0.26 to 2.57** cell by cell, so the reading that one
  set of the reference's documentation invites — "a flag that draws the average patch size toward the
  class; its value mimics `size`" — is contradicted by the values.
- It is **not a function of the sub-accounts the export publishes**. A log-linear fit of the attractor
  against `area`, `blocks`, `size`, `shape`, `frequency` and `freqpercent` leaves a **9% median and a 58%
  worst** relative residual: the attractor carries information the other five do not.
- What it *does* look like is a lower quantile of the class's patch sizes: within the `young.0_50` class
  it sits at a stable **0.52 to 0.69** of the class's mean patch area, and that fraction falls as the
  class grows — **0.015** in the largest class. A per-patch distribution is exactly what the reference
  does not ship, the same gap that leaves the patch components incomparable (#126).
- Its target carries the class's own size range as `MINIMUM`/`MAXIMUM`, and **278 of the 360 cells sit
  outside it** with a `SUMMARY` of 0 — so the reference's own report does not evaluate it as an objective
  term, which is consistent with the reading that it guides a search rather than measuring a landscape.

So WS4 **refuses** an `attractor` sub-account, naming that reason, rather than reporting a number it
cannot stand behind — the same call as the product patch criterion above. The `1.0` flag and the field
that held it are gone rather than left in as a trap; no shipped configuration asked for one, so nothing
that worked changed.

### Parity mode, and the one divergence it names

**Parity is the default, and a divergence has to be asked for by name.** Everything WS4 computes the
way the reference does needs no configuration; what it computes *differently* is declared under a route
configuration's ``divergences``, one named entry per quantity, so that what a run does is explicit
rather than implicit — and so that something deliberately different cannot be mistaken for something
wrong. An entry WS4 does not know is refused rather than ignored, and so is a maintenance reading it
does not have.

The one divergence declared so far is **maintenance as a function of the traffic a road carries**. The
reference charges each road it uses once for the period, whatever traffic passes over it — ``f(0) = 0``,
``f(x > 0) = b``. WS4 offers the affine form the maintainer specified, which is what a road budget
actually looks like: nothing at no traffic, then a fixed cost the moment any traffic uses the segment,
plus a cost proportional to the traffic — ``f(x > 0) = b + a x``. The reference's reading is the ``a = 0``
case and is the default; asking for the other one is what ``divergences.maintenance`` is for.

**Its effect is measured rather than asserted**, on the 2026 base scenario replayed with each reading.
The maintenance the run charges, summed over both mills, and what it does to the cost:

| ``a`` (cost a unit of traffic) | maintenance | against parity | maintenance and haul |
| ---: | ---: | ---: | ---: |
| parity (``a = 0``) | 144,917,367 | — | 300,237,757 |
| 0.001 | 151,064,075 | +4.2% | 306,384,465 |
| 0.01 | 206,384,450 | +42.4% | 361,704,840 |
| 0.1 | 759,588,194 | ×5.24 | 914,908,584 |

So the term is what a user's choice makes it: negligible at a thousandth of a unit of traffic, a material
part of the cost at a hundredth, and dominant at a tenth. The haul is unchanged in all four runs, which
is the check that only the reading moved.

**Two things had to be fixed for that to be a reading at all.** Maintenance used to be charged once per
produced product in the route *accounts* while the route *report* charged it once per segment per period:
on MILL 1 the account was **7.0 times** the report for the same mill. Both now go through one charge,
computed after every flow of the period is in — from the traffic, which is what makes it a function of
the traffic — and MILL 1's account and its report agree to **1.0000**. A destination's report counts a
shared segment for each destination, so the sum over destinations is not the network-wide figure (1.28
times it on this run); that is the reference's own per-mill reading rather than an error.

The optimizer's **incremental path** prices route accounts as a per-block sum, which cannot see the
traffic on a shared road. It now defers to the full simulation whenever a configured route account is one
of the two that are charged per segment — ``build`` and ``maintain`` — so a search and the report it
writes price the same thing. The additive accounts (``haul`` and ``volume``) still take the delta path,
and a test pins both.

### The patch components: the listing, and why the aggregates are the ceiling

P11 compared the patch **class aggregates** and they agree to about 8% — WS4's young-patch area 0.92 of
the reference's, its patch count 1.03, its mean patch size 0.96 — while the individual class-period cells
differ by a median 9% to 18%. That says the components form comparably in aggregate and differently in
detail, and it cannot say **where**. Saying where needs patch **membership**: which blocks formed which
patch, in which period.

**The reference does not ship it, and this is now established rather than assumed.** Every report group
of the 2026 export was read: `patch/` holds four reports whose `Source` is *Target table*
(`youngPatchSize`, `youngPatchFreq`, `harvestPatchSize`, `harvestPatchFreq`) — the same class
sub-accounts in a different shape — `harvest/maps/` is `MapReport` output, images with a field list and
no data, `nta/` carries aggregates, and `scenario/` holds block *attributes* (availability, the
schedule) but no patch attribute. The maintainer has confirmed that everything Patchworks can export has
been exported. So the aggregate comparison is the **ceiling**, and the note says so rather than implying
more was checked than was.

**The specification, for the day a listing exists.** A component listing is one row per member block of
every patch:

``period``, ``year``, ``account``, ``class``, ``patch``, ``block``, ``area_ha``

Only ``year``, ``account``, ``patch`` and ``block`` are compared, and a tool's own names are read as
they come. ``patch`` is each tool's own id and the two **never need to agree**: what is compared is the
**partition** — which blocks are together — so a listing from another tool is comparable as it stands.
The reference's own ``addPatchTarget`` declarations say which accounts and size classes to form, and its
``inputTopology`` says which topology and search distance to form them over, so WS4 can form the same
components from the same schedule. WS4 writes the listing as ``patch_membership.csv`` beside
``patch_accounts.csv`` on a run.

**The instrument is built and tested.** ``compare_patch_components`` compares two listings over their
partitions: two listings agree on a period when every patch on one side is exactly a patch on the other,
and a patch spanning more than one on the other side is a *merge* against it, reported with an example
and the block counts. It is tested against a listing with a **known** difference — a merge and its
reverse — so it can fail, and the ``patchcomponents`` acceptance check runs it against a listing found
under the export's ``patch`` directory, skipping with the reason above when there is none. On every
acceptance run today that skip is the visible statement of the ceiling.

### A patch criterion that is a product: why it is refused

The reference's harvested patches name `product.harvested` as their criterion, and WS4's patch state
evaluated a criterion as a feature — so the account was accepted, ran, and produced **every cell zero**.
P12.1 established what is actually wrong, and it is not the lookup. Resolving a product is a small
change (`(track, treatment, label)` rather than `(track, label)`, since what a treatment produces depends
on the treatment) and it was implemented: the series is no longer zero. But its values land at the
**wrong time** — a block the schedule harvests in year 44 had its product's value appear in year **150** —
because a product's curve read against a fragment's age is not the same as the product of the treatment
that happened. A wrong value that looks like a right one is worse than a zero that looks like a zero.

So the criterion is **refused** instead, with the reason: a patch criterion must be a feature, and a
product names something whose value depends on when it was produced, which the patch state does not
model. A label that is neither a feature nor a product is refused too, naming the mistake rather than
returning nought. The product path itself is reverted rather than left in as a trap, and what a real fix
needs — the product evaluated on the treatment's own timeline rather than the fragment's age — is in
`notes/backlog.md`.

