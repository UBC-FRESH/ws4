# Spatial accounts beyond the patch distribution

Two families live here. The **patch accounts** (`ws4/patch/accounts.py`) measure the size
distribution of connected clusters of a criterion. The **spread-connectivity account**
(`ws4/spread/accounts.py`) measures how far a fire could run through the blocks a criterion does *not*
mark. They answer different questions and can point opposite ways, which is why both exist.

## The spread-connectivity account

The patch accounts answer "how large are the clusters of a criterion"; this answers "how far could a fire
run through what is left". The distinction matters because the two can disagree: on the TSA23 bridge test
a wind-perpendicular barrier burns least of three equal-area patterns and has the **largest** large-patch
share, so a large-patch target penalizes the arrangement that works.

**The direction is the account's, not the topology's.** The block topology is an undirected edgelist with
no bearings, so the account supplies a bearing in degrees clockwise from north — the way a wind direction
is stated — and a tolerance. An edge transmits when it is within the tolerance of that bearing and no
longer than `search_distance`; it is then oriented from its upwind end to its downwind one, and a treated
block transmits nothing.

**Three sub-accounts, all lower-is-better.**

| sub-account | what it is |
| --- | --- |
| `largest_component` | the area reachable from one untreated block — the compartment a fire runs through from a single ignition |
| `percolation_reach` | the mean reachable area over the untreated blocks — the expected burn from an ignition anywhere |
| `edge_cut` | the share of downwind edges *leaving* the untreated set that the treatment stops — the directed barrier metric |

**What the oracle taught, and it is why the oracle exists.** Three modelling errors were caught by the
synthetic lattice, each of which would have shipped a plausible number:

1. **Undirected reachability is wrong.** With components it does not matter which way an edge points, so a
   band lying *along* the wind separates the landscape as well as one across it — the measure then has no
   direction in it at all.
2. **A 90-degree cone is no cone.** At 90 degrees every edge transmits, so on a regular lattice the
   measure collapses into the undirected one and both bands score identically. The default is 60.
3. **A four-neighbour lattice cannot test a cone.** At 60 degrees only the northward edges qualify, so
   every compartment degenerates into a one-block-wide corridor. The oracle uses eight neighbours, which
   is also how a fire spreads.

**It is wired, and it rides the whole-schedule rail.** A run computes the account per year from the
topology plus a block-coordinate table (a CSV of `block, x, y`, read for the bearings), adds the cells to
`account_values.csv`, and writes `spread_metrics.csv` beside `edge_metrics.csv`. The optimizer prices it
through a full re-simulation: `delta_evaluator` declines when a spread account is configured, because a
graph property of the whole landscape has no per-block delta, and the run folds its own
`spread_metrics.csv` back into `report_targets.csv`. It is declarable as `--spread-accounts` plus
`--block-coordinates` on `optimize`, `watch` and `calibrate`.

**The landscape is every block with a coordinate, not the blocks the criterion mentions.** This is not a
detail: a *product* criterion holds only the blocks that produced in the period, so taking the untreated
set from that mapping leaves an empty landscape and every sub-account reads zero. The end-to-end test
caught exactly that, and it is why `spread_account_values` iterates the points it is given and treats a
block with no criterion value as untreated.

## What the synthetic oracle asserts

`tests/test_spread_accounts.py`, on a seven-by-seven eight-neighbour lattice with the treatment as the
middle **row** (across a northward wind) or the middle **column** (along it), same area and one connected
band either way:

| | largest patch | `largest_component` | `percolation_reach` | `edge_cut` |
| --- | ---: | ---: | ---: | ---: |
| row band (across the wind) | 70 ha | **90 ha** | **42 ha** | **20%** |
| column band (along it) | 70 ha | 190 ha | 94 ha | 12.5% |

The patch column is identical, so a target on it cannot rank the two patterns; the connectivity columns
separate them on every measure. The test also pins that the direction is what does it — turning the wind
90 degrees reverses the ranking — and that a 90-degree cone loses the signal entirely.
