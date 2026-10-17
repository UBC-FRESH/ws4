# The patch-account evaluation bottleneck

Status: representation corrected, first fixes landed, compiled port designed and prototyped.

This note records how patch accounts are represented, what the optimizer costs when a patch
size-distribution target is active, what was fixed, and what remains. It is written to be picked up
cold by another engineer or model.

## Read this first: the representation

A patch is a **connected component of member blocks** in the block adjacency graph, where a block is a
member in a year when its criterion value exceeds the account threshold. Two configuration choices
decide whether the result means anything:

- **`search_distance`**, in metres. It is the largest gap between two block polygons that still counts
  as adjacency; the topology's `DISTANCE` column is the shortest distance between the two polygons, so
  `0` means the blocks literally touch (share a vertex). **The default is `0.0`.** A larger value
  admits more neighbour edges, so patches can only get *larger*. `None` admits every edge in the
  topology, which on the sample topology means up to 200 m across roads and creeks — mathematically
  valid, never what a resources analyst wants to express.
- **`criteria`**: what a patch *is*. `feature.Seral.regen` (value 1 for ages 0-37) is a recently
  disturbed stand, which is what a harvest opening looks like. `feature.Seral.young` (1 for ages
  42-97) is a seral *stage*, so a patch of it is a band of young forest decades after the cut, not an
  opening. The curve tables are the authority; check them before naming an account.

Two bugs in this area were found and fixed in this work; both made the optimizer's patch values
disagree with the reporting path:

1. **Untreated blocks were dropped.** `PatchModel.reset` iterated only the blocks present in the
   schedule, and a block absent from the schedule was priced at criterion `0.0` instead of its
   inventory series. With an empty schedule the optimizer therefore saw **zero patches** where the
   reporting path saw 262 (26,384.9 ha). Fixed: an untreated block keeps its inventory series, and the
   model iterates every block.
2. **The reporting path ignored `search_distance`.** `PatchLedger` used every topology edge for every
   account. Fixed: the ledger filters per account, so the report and the optimizer agree.

Correctness is now held by `tests/test_patch_accounts.py` (including a monotonicity property: a larger
`search_distance` can only *merge* patches, never split them) and `tests/test_patch_objective.py`
(including the empty-schedule regression and the reporting-path parity).

## How to measure this (do not trust `cProfile`)

`cProfile` **misattributes this workload by an order of magnitude**. The hot loops are pure Python over
`dict`/`set`, so profiling overhead lands almost entirely on them. Under `cProfile` the single-block
rate read 18.6 iterations/s; measured directly it was 37.9. Use phase timers (wrap the
`PatchGroupYear` and `PatchModel` methods to accumulate `perf_counter()` around each call and run the
search unguarded), or a sampling profiler such as `py-spy`. Do not use `cProfile` for this.

## The shape of the problem

Graph `G` is fixed: nodes are blocks, edges are adjacency (sample topology: 12,561 blocks; 68,586
block-pair edges, of which 28,727 (42%) are distance 0 and the rest reach up to 200 m). Membership
`M_t` is per year. A patch is a connected component of `G[M_t]`; each component contributes area
(`sum value * block_area`), perimeter (`sum length of boundary edges`), and a size class.

Structure at the inventory state, **with the corrected defaults** (touching adjacency), for candidate
criteria:

| criterion | members | components | largest component | median component |
| --- | ---: | ---: | ---: | ---: |
| `feature.Seral.young` | 2,737 | 858 | 178 (6.5% of members) | 1 |
| `feature.Seral.regen` | 825 | 276 | 45 (5.5%) | 1 |
| `feature.young` | 1,063 | 341 | 55 (5.2%) | 1 |
| `feature.Seral.mature` | 7,143 | 650 | 4,122 (57.7%) | 1 |

So the realistic patch is small (median 1 block) and the distribution is broad. **Do not tune for the
pathological configuration**: with `search_distance=None` and a mature criterion the whole forest
collapses into one 4,273-block component, and almost every measurement becomes about that one blob.
That configuration was measured early in this work and its numbers (a 4% articulation fraction, a
2.25 ms component walk dominating 86% of a move) describe the blob, not normal use.

## Where the time goes

### Single-block move, default configuration, current

`--lns-weight 0`, 600 iterations on C5, 50 years: **387.9 iterations/s** (2.6 ms per move). For
reference the same objective machinery on an additive product target runs at roughly 2,000-2,600/s,
so a patch target costs about 5-7x with single-block moves.

The dominant cost used to be the connectivity walk: every detach of a member with two or more member
neighbours ran a full BFS of the component to discover it does **not** split. That is now an
**exact early-exit test**: a detach of `v` only disconnects its patch if `v` is an articulation point,
so it suffices to BFS from one member-neighbour of `v` and stop the moment every *other*
member-neighbour has been reached (if all of `v`'s neighbours lie in one component of `C - v`, then
`C - v` is connected). If the walk exhausts first, `v` is an articulation point and the reached set is
one of the pieces. Combined with cached size-class labels and an inlined value lookup this took
single-block moves from 37.9 to 142.5 iterations/s *on the old pathological configuration*, and the
corrected representation reaches 298.9/s.

### Bulk (LNS) move, the current bottleneck

`--lns-weight 0.2` (the default), 300 iterations, 10.8 s = **55.7 iterations/s** (18 ms per move),
phase timers:

| phase | inclusive s | calls | us/call |
| --- | ---: | ---: | ---: |
| `pending` (whole delta) | 5.42 | 300 | 18,079 |
| **`_local_cells` / `rebuild_local`** | **4.36** | 1,018 | **4,283** |
| `_affected` | 0.78 | 300 | 2,613 |
| `set_value` (single-block path) | 0.04 | 2,540 | 17 |
| `_detach` / `_reachable` / `_split` | 0.05 | 2,253 | 22 |

- **`rebuild_local` (~62%)**: an LNS move changes ~40 blocks, so the bulk path rebuilds the
  components touched in each affected year (`_REBUILD_ABOVE = 8` switches from per-block updates to
  this). Each call walks a component and recomputes its area and perimeter.
- `_affected` was the second cost (1.84 s, 22%) and is now 0.78 s; see below.

### `_affected` was not what it looked like

The obvious reading of `_affected` is "it compares old and new series over every year for every
changed block, so make the comparison cheaper". That is wrong. Measured with call counters, `series()`
is called 1.25M times per run but only ~11k are cache misses, and those misses dominate: the cost was
**constructing new chains' criterion series**, not comparing them. The comparison loop itself costs
well under a millisecond per call.

So the fix was to the primitive, `Simulator.block_criteria_series`, which was **159 us per call** (a
Python loop over every year, and inside it a Python loop over every fragment calling
`_curve_value`). It is now **58.7 us (2.7x)**: an integer-age gather over the curve table, filling the
horizon in one numpy operation per treatment event (not per year — a per-year numpy loop was tried
first and was *not* faster, because numpy call overhead on a 50-element array is ~1.5 us, the same as
the Python work it replaced). `_affected` fell from 1.84 s to 0.78 s, and two smaller wins went with
it: hoisting the per-block series lookup out of the per-year loops in `pending`, `_local_cells` and
`reset` (it was being redone once per year for a value that covers all years), and caching the
size-class labels.

Result: default 41.9 -> **55.7 iterations/s (+33%)**, single-block 298.9 -> **387.9 (+30%)**.

## The design insight: articulation points and negative space

For **split** moves, a patch move is only structurally interesting at an articulation point of the
patch. For **merge** moves, the target is the **negative space** between proximal patches: a
non-member block whose member-neighbours span two or more distinct components. Adding it merges them.

Both are cheap to detect locally:

- **Negative space**: for a non-member block, collect the component ids of its member-neighbours; it is
  a merge point iff they span >= 2 components. `O(degree)`, and maintainable incrementally because a
  block's status changes only when it or a neighbour changes.
- **Cut vertices**: one Tarjan pass gives all of them (0.01-0.02 s for a whole year state at C5
  scale); whether a *given* `v` is one is what the early-exit test answers, cheaply in the common case.

Cheap exact "not a cut vertex" predicates, measured **on the old pathological blob** (all with zero
false positives; re-measure on a realistic configuration before relying on them):

| predicate | proves not-cut for | fraction |
| --- | ---: | ---: |
| degree <= 1 | 65 | 1.5% |
| member-neighbourhood is a clique | 615 | 14.4% |
| leaf of a BFS spanning tree of the component | 2,778 | 65.0% |

Removing a leaf of a spanning tree leaves a spanning tree of `C - v`, so `C - v` is connected.
Maintaining a spanning forest per component would let a large share of detaches skip the walk
entirely, with no compiled dependency.

## Measurement discipline (learned the hard way)

**Run each configuration in its own process.** A single process that runs several configurations
warms numba, the criterion-series cache, and the optimizer's delta caches, so the *second* config
measured can look 2-4x faster than the first for no reason that matters. Several numbers earlier in
this note were taken that way and were wrong by up to 2x in both directions; the numbers below are
from one-config-per-process runs, back to back, and repeat within a few percent.

`cProfile` is also unusable here (pure-Python inner loops are inflated by an order of magnitude). Use
phase timers, or a sampling profiler.

## The array-backed state (landed)

`PatchGroupYear` now holds the membership, criterion value and component of each block in arrays
(`array.array`, so Python indexing is about list speed) and hands the compiled kernels a **writable,
zero-copy numpy view** (`np.frombuffer(...)` with `flags.writeable = True`), so no marshalling happens
in either direction. The per-component aggregates stay dictionaries indexed by component id and only
the components a move touches are written back. The `members` sets are gone: a component's size is
`count_of[cid]`, a merge re-points by walking `comp`, a split is found by walking from the removed
block's member-neighbours, and the walks themselves are kernels (`reachable_from`, `component_from`,
`piece_aggregate` in `ws4/opt/patch_kernels.py`), with generation-stamped scratch so nothing is
cleared between calls.

Fresh-process A/B, 600 iterations, C5, 50 years, one patch target, two to three runs each:

| configuration | dicts | arrays + kernels | |
| --- | ---: | ---: | --- |
| `--lns-weight 0.2` (default) | 31.0 | **56.4** | **+82%** |
| `--lns-weight 0` (single block) | 153.3 | 141.2 | -8% |

The single-block path pays a little for the array representation: the walks are compiled now, but the
per-edge `comp`/`member` reads in `_attach`/`_detach` and the per-component write-back are still
Python over arrays, where the old code used dict membership tests. An earlier version without the walk
kernels cost 22% there; kernelising the walks recovered most of it. Two further things came out of
measuring rather than guessing: the `covered` set in `_split` was redundant (the first piece's
component id is already restamped, so later walks cannot re-traverse it), and the bulk relabel now
reports its own stale component ids, which removed a Python scan of every changed block's
neighbourhood (~0.8-1.5 ms per bulk call, worth 13% of the default).

`array.array` + a writable `np.frombuffer` view is worth remembering: it gives Python near-list
indexing and numba a zero-copy array in the same object, with no per-call marshalling.

### What the walks cost now

Phase timers on the default configuration, after all of the above (600 iterations, 49 iterations/s):

| phase | share |
| --- | ---: |
| `rebuild_local` (the bulk relabel) | 43% |
| `series` (criterion series lookups) | 19% |
| `_affected` | 15% |
| `set_value` + `_detach` + `_split` + `_attach` (the whole single-block path) | 4% |

The connectivity walks are no longer a measurable cost — compiling them worked. What is left is the
bulk relabel's own bookkeeping and the criterion series.

## Quality, at last

Every performance number in this note above was measured against a target satisfied at iteration 0
(`objective=0.000`) — overhead on a solved problem, not the cost of optimising patches. With a binding
target (`patch.harvest.0_5.frequency <= 60`, year 0) the search drives the penalty from 88 into the
low 20s over 4,000 iterations, so it does optimise patches.

Added the **gap/merge operator** (`--merge-weight`, default 0). A *gap* is a non-member block whose
member-neighbours span two or more components — the negative space between proximal patches; adding it
would join them. `is_gap` is `O(degree)` and needs no incremental index (the operator samples blocks),
and `PatchModel.focus_years` records the years the objective reads so the move targets one of them
rather than a random year (that distinction was worth most of the operator's effect).

Over five seeds at 4,000 iterations, weight 0.5 against 0.0:

| | final penalty (mean of 5) | iteration rate |
| --- | ---: | ---: |
| without | 16.4 | 56-69/s |
| with merge | **14.6** | 67-77/s |

Three seeds improve, one ties, one worsens. The rate rises because a merge move is a single block and
displaces expensive LNS moves. It is opt-in and not yet a clear win — the next step is to target the
*class* the objective cares about (and the split side of the same idea) rather than any gap.

## The compiled kernel: measured on realistic components

The first prototype measured a full relabel of the old 4,273-block blob and reported 41x. That is not
the relevant number. The relevant test captures **real `rebuild_local` calls from a real search** on
the corrected touching adjacency, then runs the Python implementation and an equivalent numba kernel
on identical inputs. Workload captured: 60 bulk calls, 564 changed blocks per call, state of ~3,332
members over 12,567 blocks and 57,454 directed CSR edges.

| per call | time | speed-up |
| --- | ---: | ---: |
| Python `rebuild_local` | 6.768 ms | — |
| numba kernel (relabel + area + perimeter) | **0.279 ms** | **24.3x** |
| kernel + marshalling the dicts into arrays | 1.377 ms | 4.9x |

Parity is exact: zero area mismatches and zero perimeter mismatches over the 60 calls.

**The design decision this forces.** A "wrapper" that keeps the Python dicts and marshals into arrays
per call measures 4.9x, and that still excludes writing the kernel's result back into the Python
structures. `rebuild_local` spends roughly half its time building the `members` sets and dict entries
for the rebuilt components, and a wrapper still has to do that. So a wrapper is worth about 2x, not
24x, and is not worth the complexity.

The 24x needs the arrays to be the **source of truth**, which means eliminating the `members` sets:

- Hold `comp` (int32 per block), `count` (per component), and the per-component area/perimeter, with
  `is_member`/`value` per state; `class_of`/sums stay as they are.
- `members` is then only ever needed to (a) know a component's size — use `count`; (b) re-point a
  merged component — a BFS over `comp`; (c) find the pieces of a split — a BFS over `comp`, which the
  kernel already does.
- That is a *simplification* of `PatchGroupYear`, and it is what lets the kernel own the bulk path
  with no write-back.

Expected end to end: `rebuild_local` is ~62% of a bulk move, so at 24x the default search should go
from ~56 to ~200+ iterations/s, subject to the remaining ~38%.

The kernel (from the prototype, parity-checked against the Python implementation):

```python
@njit(cache=True, fastmath=True)
def rebuild_kernel(
    ptr,
    indices,
    lengths,
    is_member,
    value,
    areas,
    changed,
    new_value,
    threshold,
    stack,
    walk,
    visited,
    gen,
    area_out,
    perim_out,
):
    """Apply a change and relabel the components holding a changed block or its neighbours."""
    for k in range(changed.size):
        b = changed[k]
        v = new_value[k]
        if v > threshold:
            is_member[b] = 1
            value[b] = v
        else:
            is_member[b] = 0
            value[b] = 0.0
    seeds = 0
    for k in range(changed.size):
        b = changed[k]
        if is_member[b] and visited[b] != gen:
            visited[b] = gen
            stack[seeds] = b
            seeds += 1
        for e in range(ptr[b], ptr[b + 1]):
            o = indices[e]
            if is_member[o] and visited[o] != gen:
                visited[o] = gen
                stack[seeds] = o
                seeds += 1
    count = 0
    for s in range(seeds):
        start = stack[s]
        if visited[start] == gen + 1:
            continue
        area = 0.0
        perim = 0.0
        sp = 0
        walk[sp] = start
        sp += 1
        visited[start] = gen + 1
        while sp > 0:
            sp -= 1
            node = walk[sp]
            area += value[node] * areas[node]
            for e in range(ptr[node], ptr[node + 1]):
                o = indices[e]
                if is_member[o]:
                    if visited[o] != gen + 1:
                        visited[o] = gen + 1
                        walk[sp] = o
                        sp += 1
                else:
                    perim += lengths[e]
        area_out[count] = area
        perim_out[count] = perim
        count += 1
    return count
```

## Implementation plan

Ordered by value over risk.

1. **Make the criterion series primitive cheaper — done.** `block_criteria_series` is 2.7x faster
   (159 -> 58.7 us) via a segment-based table gather; `_affected` fell 1.84 -> 0.78 s. The lesson to
   keep: do not vectorise per *year* with numpy on tiny arrays, vectorise per *event* over the whole
   horizon.
2. **The array-backed state and the compiled relabels — done.** Default search +62% (29.6 -> 48.1
   iterations/s, fresh process); single-block -8%. The walks are kernels too. See above.
3. **Spanning-forest leaf test — measured, not worth it.** On the realistic configuration 50.3% (peak
   year state) and 43.8% (year 25) of the detaches that currently take the walk are leaves of a BFS
   spanning forest, so about half could skip it in `O(1)`. But the other half would then need their
   component's spanning tree repaired, which is a full component BFS, and the walks are compiled now
   anyway. At or below the ~50% break-even, with a repair cost of the same order as the walk it
   replaces, it does not pay. Recorded so nobody has to re-derive it.
4. **Articulation- and gap-targeted operators**: the merge side is in (`MergeOperator`, `is_gap`,
   `focus_years`); it needs to target the *class* the objective scores, not any gap, and the split
   side (`reachable_from` already identifies articulation detaches exactly) is not built yet.
5. **Consider excluding LNS, or making its destroy set spatially coherent**, for patch targets. LNS
   is what the compiled path is for, and buys about 0.8 objective units on the sample problem; a
   k-hop-ball destroy set would shrink the affected components further.

## Open questions

- Re-measure everything above on a realistic account (`feature.Seral.regen`, default `search_distance`,
  a period-length horizon). The structure and the bottleneck ranking both came from the pathological
  configuration and the single-block fix has already changed them once.
- Which extra accounts cost what: perimeter (for `compactness`/`shape`) needs a boundary scan that the
  area does not; measure separately.
- Does a compiled port pay? **Answered: yes for the kernel (24.3x measured on real calls), but it
  requires the array-backed state — a dict-marshalling wrapper is only ~2x.** See the kernel section.
