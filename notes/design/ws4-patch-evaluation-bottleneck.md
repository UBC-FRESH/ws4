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

`--lns-weight 0`, 600 iterations on C5, 50 years: **298.9 iterations/s** (3.3 ms per move). For
reference the same objective machinery on an additive product target runs at roughly 2,000-2,600/s,
so a patch target costs about 7-9x with single-block moves.

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

`--lns-weight 0.2` (the default), 300 iterations, 8.22 s = **36.5 iterations/s** (27.4 ms per move),
phase timers:

| phase | inclusive s | calls | us/call |
| --- | ---: | ---: | ---: |
| `pending` (whole delta) | 6.65 | 300 | 22,151 |
| **`_local_cells` / `rebuild_local`** | **4.36** | 1,018 | **4,279** |
| **`_affected`** | **1.82** | 300 | **6,063** |
| `_value` | 1.14 | 1,259,240 | 0.9 |
| `set_value` (single-block path) | 0.04 | 2,540 | 17 |
| `_detach` / `_reachable` / `_split` | 0.07 | 2,253 | 30 |

- **`rebuild_local` (53%)**: an LNS move changes ~1,100 blocks, so the bulk path rebuilds the
  components touched in each affected year (`_REBUILD_ABOVE = 8` switches from per-block updates to
  this). Each call walks a component and recomputes its area and perimeter.
- **`_affected` (22%)**: it compares the old and new criterion series over **all** years for every
  changed block (~1,100 blocks x 50 years per LNS move). The series are dense `{year: value}` dicts.
- `_value` is called 1.26M times; `_affected` and the per-block path are the callers.

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

## The compiled kernel (prototyped, 41x on the dominant routine)

`rebuild_local` and the walks are pointer-chasing over small integers, which is what a compiled kernel
does far better than Python. Prototype (numba, CSR adjacency, explicit stack), measured on the old
4,273-block component: **Python 10.98 ms -> numba 0.269 ms, 41x**, with identical component count and
top-5 areas. The kernel:

```python
@njit(cache=True, fastmath=True)
def label_and_aggregate(indptr, indices, lengths, is_member, value, area, out_comp):
    n = is_member.size
    for i in range(n):
        out_comp[i] = -1
    stack = np.empty(n, dtype=np.int32)
    comp_area = np.empty(n, dtype=np.float64)
    comp_perim = np.empty(n, dtype=np.float64)
    cid = 0
    for start in range(n):
        if not is_member[start] or out_comp[start] != -1:
            continue
        top = 0
        stack[top] = start
        top += 1
        out_comp[start] = cid
        while top:
            top -= 1
            node = stack[top]
            for k in range(indptr[node], indptr[node + 1]):
                other = indices[k]
                if is_member[other] and out_comp[other] == -1:
                    out_comp[other] = cid
                    stack[top] = other
                    top += 1
        cid += 1
    for c in range(cid):
        comp_area[c] = 0.0
        comp_perim[c] = 0.0
    for node in range(n):
        c = out_comp[node]
        comp_area[c] += value[node] * area[node]
        for k in range(indptr[node], indptr[node + 1]):
            if not is_member[indices[k]]:
                comp_perim[c] += lengths[k]
    return cid, comp_area, comp_perim
```

The 41x is on a singleton rebuild; the realistic `rebuild_local` is called ~3.4 times per LNS move
over smaller components, so expect a smaller whole-search factor, but this is the largest single lever.

## Implementation plan

Ordered by value over risk.

1. **Make `_affected` cheap** (22% today, pure Python, no compiled dependency). Two options: store the
   criterion series sparsely (only non-zero years) and compare key sets; or exploit the structure that
   two chains sharing a prefix of events have identical series up to the first differing event year, so
   the differing years are a suffix. Either removes the `blocks x years` inner loop.
2. **Spanning-forest leaf test** (pure Python). Maintain a spanning tree per component; a detach of a
   tree leaf is `O(1)` and proves "no split". Re-measure the leaf fraction on a realistic
   configuration first.
3. **CSR + numba for the bulk rebuild and the walks** (the 41x above). Concrete: per year state keep
   `is_member` (uint8), `value` (float64), `comp` (int32) plus `indptr`/`indices`/`lengths` shared per
   `search_distance`; keep the size-class sums in Python. Keep the Python state as the source of truth
   initially and treat the CSR as a derived buffer so parity is easy to test; invert once green. The
   undo/`revert` path must restore the changed `is_member`/`value` slots and the touched aggregates.
4. **Articulation- and gap-targeted operators**: maintain the negative-space (merge) set incrementally;
   add a `SplitOperator` that detaches a cut vertex and a `MergeOperator` that treats a
   negative-space block (plus its neighbourhood). These change *which* moves are proposed, so they help
   solution quality per move as well as cost.
5. **Consider excluding LNS, or making its destroy set spatially coherent**, for patch targets. LNS
   currently dominates the cost (53%) and buys about 0.8 objective units on the sample problem; a
   k-hop-ball destroy set would shrink the affected components.

## Open questions

- Re-measure everything above on a realistic account (`feature.Seral.regen`, default `search_distance`,
  a period-length horizon). The structure and the bottleneck ranking both came from the pathological
  configuration and the single-block fix has already changed them once.
- Which extra accounts cost what: perimeter (for `compactness`/`shape`) needs a boundary scan that the
  area does not; measure separately.
- Does a compiled port pay once `_affected` and the walk heuristics land? The 41x is real but measured
  on the pathological case; re-measure before committing the complexity.
