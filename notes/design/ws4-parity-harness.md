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

