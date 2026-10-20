# Spatial accounts beyond the patch distribution

Two families live here. The **patch accounts** (`ws4/patch/accounts.py`) measure the size
distribution of connected clusters of a criterion. The **spread-connectivity account**
(`ws4/spread/accounts.py`) measures how fragmented the connected fuel body a fire could run through is.
They answer different questions and can point opposite ways, which is why both exist.

## The spread-connectivity account

The patch accounts answer "how large are the clusters of a criterion"; this answers "how fragmented is
what is left". The distinction matters because the two can disagree: on the TSA23 bridge test a
wind-perpendicular barrier burns least of three equal-area patterns and has the **largest** large-patch
share, so a large-patch target penalizes the arrangement that works.

**The direction is the account's, not the topology's.** The block topology is an undirected edgelist with
no bearings, so the account supplies a bearing in degrees clockwise from north — the way a wind direction
is stated — and a tolerance. An edge is **fast** when it is within the tolerance of that bearing and no
longer than `search_distance`. A treated block transmits nothing. The traversal over the fast edges is
**undirected**: a fire travels on its flanks and behind it and therefore goes *around* an obstacle, so
what confines it is the connected fuel body it can wander through, not a one-way corridor.

**Two sub-accounts, both lower-is-better.**

| sub-account | what it is |
| --- | --- |
| `largest_component` | the area of the largest connected set of untreated blocks over the fast edges — the fuel body a fire can wander through from one ignition |
| `percolation_reach` | the area-weighted mean compartment area, `sum(area**2) / sum(area)` — what a random *hectare* sees |

The per-block mean is deliberately not used: on a fragmented map it is dominated by the many isolated
blocks, and on the bridge instance it read 9.5 ha for all three patterns while the area-weighted mean
separated them cleanly.

## What the bridge instance taught: the directed reading does not survive a real map

The first version of this account was **directed** — an edge transmitted only from its upwind end, and
the sub-accounts were the largest reach and the mean reach. The synthetic lattice liked it. Run against
the real TSA23 instance (102,128 blocks, 410,823 topology edges, wind bearing 225°), it failed:

| pattern | fire mean (ha) | `largest_component` (directed) | `percolation_reach` (directed) |
| --- | ---: | ---: | ---: |
| barrier | 19,640 | 3,390.6 | 44.6 |
| clumped | 19,870 | 3,390.6 | 44.3 |
| random | 20,298 | 3,390.6 | 43.0 |

`largest_component` was identical to the hectare for all three: the largest directed run is a boundary
corridor no treatment touches, so the account read the map, not the pattern. `percolation_reach`
*reversed* the ranking, because a thin barrier only shortens the runs that cross it while scattered
treatment shortens every run.

The compartment reading, on the same edges and bearing, orders the patterns as the fire model did:

| pattern | fire mean (ha, 177k treated) | largest compartment (ha) | area-weighted mean (ha) |
| --- | ---: | ---: | ---: |
| barrier | 19,640 | **82,874** | **25,697** |
| clumped | 19,870 | **105,020** | **32,250** |
| random | 20,298 | **196,767** | **50,281** |

**That agreement does not survive a matched footprint, and the validation is withdrawn.** The published
fire runs treat 177,088 ha of whole scheduled blocks (17.9% of the model); WS4's FT product reaches
~54,000 ha (5.5%). Rerunning the instance's own fire model on the WS4-treated masks across five seeds
gives the *reverse* mean order (clumped 22,775 < random 22,816 < barrier 22,861 ha), with a largest mean
gap of **86 ha (0.38%)** against a seed-to-seed range of **~3,400 ha (15%)**, and the ranking flips
across seeds. At the area WS4 can actually treat, the arrangement effect is inside noise. The full
table is `notes/reports/p16-bridge-matched.md`.

So the account is a **defined fragmentation metric**, not a validated fire-response proxy. What
survives is the computation and the oracle below; what does not is the claim that its ordering predicts
the fire model at the intervention this estate model can deliver. A separate bounded-footprint case
(1,877 blocks, 20,019 ha, ~20% treated, three equal-area patterns) does not rescue it either: the
compartment's largest values there are **23 / 94 / 6 ha** at a 60° cone and **49 / 105 / 10 ha** at 90°
(barrier / clumped / random), so the order is not barrier < clumped < random at any cone width, nor
undirected.

**Caveats, recorded rather than buried.** The ordering of `largest_component` on the *fixed* landscape
holds from a 60° to a 90° cone; the *magnitude* depends on how near the cone is to the percolation
threshold (at 60° the barrier's giant compartment is 8.9% of the untreated area against random's
20.0%; at 90° they are 93.7% and 94.7%). At 45° or narrower the map is below threshold and the ordering
flips. The fire spread at the original footprint is only 3%, on one seed, and the matched rerun shows
that it is smaller than the seed noise at 5.5% treatment.

**Direction is in the cone, not in the traversal.** A full-span band lying along the wind fragments an
undirected graph just as much as one across it. The account can say *how fragmented the fast-edge fuel
body is*, not *which way a band runs*. Separating those needs anisotropic rates and a burn duration,
which is a fire model rather than an account.

## Wiring

**It rides the whole-schedule rail.** A run computes the account per year from the topology plus a
block-coordinate table (a CSV of `block, x, y`, read for the bearings), adds the cells to
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
middle **row**, the middle **column**, or a **partial** band open at both ends:

| pattern | largest patch | `largest_component` | `percolation_reach` |
| --- | ---: | ---: | ---: |
| none | 0 ha | 490 ha | 490 ha |
| row, full span | 70 ha | **210 ha** | **210 ha** |
| column, full span | 70 ha | **210 ha** | **210 ha** |
| four-block partial band | 40 ha | 450 ha | 450 ha |

The patch column cannot rank the two full bands, and neither can the compartment — that is the honest
claim, and the test pins it. What the test *does* pin is that a span fragments the fuel body and a
partial band does not, that a 20° cone keeps only the northward edges and fragments the map into columns
(70 ha), that a short hop leaves every block its own compartment, and that an empty landscape reads zero.
