# The patch-account evaluation bottleneck

Status: analysis complete, first fixes landed, compiled port designed and prototyped.

This note records what makes the optimizer slow when a patch size-distribution target is active,
what was measured, what was fixed, and what remains. It is written to be picked up cold by another
engineer or model.

## Summary

- A patch target costs roughly a **30x to 70x** drop in search iterations per second against an
  additive product target on C5 (50-year horizon): about **2,000-2,600 -> 37 iterations/s**.
- The cost is **not** the objective arithmetic, the string formatting, or the criterion curves. It is
  **graph work on the patch connectivity**: walking a connected component of the member blocks.
- Two facts dominate everything:
  1. The member graph is **one giant component** (4,273 of 4,695 members in the largest year state)
     plus ~70 fragments. Almost any change touches the giant component.
  2. Only **189 of 4,695 members (4%) are articulation points** (cut vertices). The other 96% cannot
     split a patch, yet the code walked the whole component to prove it.
- **Landed**: an exact early-exit connectivity test and the removal of per-call work. Single-block
  moves went **37.9 -> 142.5 iterations/s (3.8x)**; the default configuration went
  **37.2 -> 43.2 iterations/s** because it is dominated by the bulk (LNS) rebuild instead.
- **Prototyped**: the dominant bulk rebuild as a numba kernel over CSR arrays is **41x faster**
  (10.98 ms -> 0.269 ms) with identical component areas. This is the single largest remaining lever.

## How to measure this (do not trust `cProfile`)

`cProfile` **misattributes this workload by an order of magnitude**. The hot loops are pure Python
over `dict`/`set`, so profiling overhead lands almost entirely on them. Under `cProfile` the
single-block rate read 18.6 iterations/s; measured directly it was 37.9. `rebuild_local` showed as
63% of runtime under `cProfile` but LNS moves were shown to be *not* dominant by a direct A/B.

Use one of:

- **Phase timers**: monkeypatch the `PatchGroupYear` / `PatchModel` methods to accumulate
  `perf_counter()` around each call, then run the search unguarded. This is what the tables below use.
- A sampling profiler (`py-spy`) would also be safe; `cProfile` is not.

## The shape of the problem

Patch accounts are a **dynamic connectivity aggregation** problem:

- Graph `G`: fixed. Nodes are blocks, edges are topology adjacency (C5: ~12.5k blocks, ~68.6k edges).
  An account's `search_distance` filters edges by length.
- Membership `M_t` per year: block `b` is a member in year `t` iff its criterion value
  (`block_criteria_series(block, chain)[label][t]`) exceeds the account threshold.
- A **patch** is a connected component of the induced subgraph `G[M_t]`. Per component the accounts
  need: area (`sum value * block_area`), perimeter (`sum length of edges leaving the component`),
  and a size class.
- A move changes one block's treatment chain, which changes `M_t` and the values for a contiguous
  range of years. Only those years' components change ("spatial locality"), but see below.

Measured on the largest year state of C5's `feature.Seral.young` patch account (threshold 0.5):

| quantity | value |
| --- | --- |
| members | 4,695 |
| components | 70 |
| largest component | 4,273 (91% of members) |
| component sizes | min 1, median 2, max 4,273; next largest 137 |
| member degree within component | 0: 34, 1: 113, 2: 270, >=3: 4,278 |
| **exact articulation points** | **189 (4.0%)**, computable in 0.02 s with one Tarjan pass |

The important structural fact: the giant patch is a **dense blob with very few cut vertices**. It is
essentially 2-connected, so removing one block almost never splits it.

## Where the time goes

### Single-block move, default 50-year C5 patch target, before any fix

300 iterations, `lns_weight=0`, phase timers (inclusive seconds):

| phase | inclusive s | calls | us/call |
| --- | ---: | ---: | ---: |
| `pending` (whole delta) | 7.83 | 300 | 26,102 |
| `set_value` | 7.66 | 5,275 | 1,452 |
| `_detach` | 7.64 | 3,332 | 2,293 |
| **`_component_from`** | **7.30** | 3,244 | **2,251** |
| `_value` | 0.48 | 570,075 | 0.8 |
| `_split` | 0.23 | 205 | 1,114 |
| `_cells` | 0.06 | 4,266 | 13 |
| `_affected` | 0.05 | 300 | 163 |
| `_attach` | 0.01 | 773 | 17 |

**`_component_from` was 86% of a single-block move**: every detach of a member with two or more
member neighbours ran a full BFS of the component (~2.25 ms for the 4,273-block blob) purely to
discover that it does **not** split (96% of the time).

### Bulk (LNS) move, `lns_weight=0.2`, after the single-block fix

300 iterations, 8.90 s = 33.7 iterations/s (29.7 ms per move):

| phase | inclusive s | calls | us/call |
| --- | ---: | ---: | ---: |
| `pending` | 7.89 | 300 | 26,309 |
| **`_local_cells` / `rebuild_local`** | **5.66** | 1,015 | **5,572** |
| `_affected` | 1.95 | 300 | 6,488 |
| `_value` | 1.02 | 1,138,289 | 0.9 |
| `set_value` (single-block path) | 0.21 | 3,031 | 69 |
| `_reachable` (new) | 0.13 | 1,034 | 123 |
| `_component_from` | 0.01 | 239 | 36 |

So the bulk path is now: **`rebuild_local` 64% + `_affected` 22%**. `_value` was called 1.14M times
because `rebuild_local` took a `lookup` closure and invoked it per changed block per affected year.

## What was fixed (landed)

1. **Exact early-exit connectivity test** (`PatchGroupYear._reachable`). A detach of `v` only
   disconnects `C` if `v` is an articulation point. It is enough to BFS from **one** member-neighbour
   of `v` and stop the moment **every other** member-neighbour has been reached: if all neighbours of
   `v` lie in one component of `C - v`, then `C - v` is connected (any vertex of `C` reaches a
   neighbour of `v`, and there is no edge to `v`). If the walk exhausts first, `v` **is** an
   articulation point and the reached set is one of the pieces for `_split`.
   - Exact, no new state. Measured 3.7x on the walk alone (median 23 nodes vs 4,273; p90 still 4,267).
2. **Cached size-class labels.** `class_of` recomputed `size_class_labels(...)` on every call
   (188k calls in the profiled run). Bounds and labels are now computed once per state; the dead
   `class_of` wrapper was removed and `class_index` is used directly.
3. **Inlined the value lookup.** `_local_cells` now builds `{block: value}` directly instead of
   passing a closure that called `_value` (1.14M Python calls, ~1.0 s, removed).

Result on the same benchmark:

| configuration | before | after | speed-up |
| --- | ---: | ---: | ---: |
| single-block (`lns_weight=0`), 600 iters | 37.9/s | 142.5/s | 3.8x |
| default (`lns_weight=0.2`) | 37.2/s | 43.2/s | 1.16x |
| `lns_weight=0.5`, destroy 0.02 | 29.1/s | 34.0/s | 1.17x |

Parity is held by `tests/test_patch_state.py` and `tests/test_patch_objective.py`, which compare
against the from-scratch and reporting paths.

## The design insight: articulation points and negative space

For **split** moves, a patch move is only structurally interesting at an articulation point of the
patch. Everything else just shaves area off a component. So proposals should target cut vertices.

For **merge** moves, the target is the **negative space** between proximal patches: a non-member
block whose member-neighbours span two or more distinct components. Adding it merges them.

Both are cheap to maintain or detect locally:

- **Negative space**: for each non-member block, look at its member-neighbours' component ids. It is
  a merge point iff those ids span >= 2 components. `O(degree)` per block, and the set can be
  maintained incrementally (a block's gap status changes only when it or a neighbour changes).
- **Cut vertices**: exactly the output of a Tarjan pass (0.02 s for the whole C5 year state). Detecting
  *whether a given* `v` is a cut vertex is what `_reachable` now does exactly and adaptively.

### Cheap exact "not a cut vertex" predicates

Measured over the 4,273-member giant component (all have **zero false positives**):

| predicate | proves not-cut for | fraction |
| --- | ---: | ---: |
| degree <= 1 | 65 | 1.5% |
| member-neighbourhood is a clique | 615 | 14.4% |
| **`v` is a leaf of a BFS spanning tree of the component** | **2,778** | **65.0%** |

The spanning-tree leaf test is the strong one: removing a leaf of any spanning tree leaves a
spanning tree of `C - v`, so `C - v` is connected. Maintaining a spanning forest of each component
under vertex toggles would let **65% of detaches skip the walk entirely**.

Combined with the early-exit test for the remaining 35%, the walk cost should fall by roughly 3-5x
again on top of the 3.8x already landed.

## The compiled kernel (prototyped, 41x on the dominant routine)

The bulk rebuild and the walks are pointer-chasing over small integers. That is exactly what a
compiled kernel does 40x better than Python. Prototype (numba, CSR adjacency, explicit stack):

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

Same data, same machine, 50 repeats:

| implementation | per full rebuild |
| --- | ---: |
| Python (dict/set walk, the current `rebuild`) | 10.98 ms |
| numba CSR kernel | **0.269 ms** |
| speed-up | **41x** |

Parity: identical component count (70) and identical top-5 component areas to one decimal.

## Implementation plan

Ordered by (value / risk). Steps 1-2 are the cheapest meaningful wins.

1. **Spanning-forest leaf test** (pure Python, no compiled code). Maintain, per component, a spanning
   tree with parent pointers and a child count. Attach links `v` as a child of a member neighbour
   (`O(degree)`). Detach of a leaf is `O(1)` and proves "no split". Detach of a non-leaf falls back to
   `_reachable` and, if not a cut, repairs the tree (re-link the children's subtrees using a
   non-tree edge, or rebuild the component's tree). Merges re-root the smaller side to bound the copy.
   Expected: another 2-4x on detaches, no compiled dependency.
2. **Cache `_affected` per block.** Two chains with the same events up to year `t` have identical
   series up to `t`; the differing years are a suffix `[first_difference, years)`. Computing the first
   differing event year is `O(events)` instead of `O(years)` per block. Alternatively store the series
   sparsely (only non-zero years) and compare key sets. Expected: most of the 22% `_affected` cost.
3. **CSR + numba for the bulk rebuild and the walks.** This is the big one (41x measured). It needs
   the state to hold, per year state: `indptr`/`indices`/`lengths` (shared per `search_distance`),
   `is_member` (uint8), `value` (float64), `comp` (int32), plus per-component `area`/`perimeter` and
   the size-class sums kept in Python. Keep the Python state as the source of truth and treat the CSR
   as a derived buffer to keep parity easy, then invert once the tests hold. The undo/`revert` path
   needs care: save the changed `is_member`/`value` slots and the touched component aggregates.
4. **Articulation- and gap-targeted operators.** Maintain the negative-space (merge) set
   incrementally (`O(degree)` updates). Add a `SplitOperator` that proposes detaching a cut vertex,
   and a `MergeOperator` that proposes treating a negative-space block (plus its neighbourhood) to
   join two patches. These change *which* moves are proposed, improving solution quality per move;
   they also make patch moves structurally meaningful rather than random.
5. **Reconsider `_affected` granularity for LNS.** An LNS move changes ~1,100 blocks and touches ~17
   year states (pending + revert). If the destroy set is spatially coherent (a k-hop ball rather than
   random blocks) the affected components shrink and the rebuild gets cheaper.

## Correctness / parity strategy

- `tests/test_patch_state.py` and `tests/test_patch_objective.py` already compare the incremental
  state cell-for-cell against the from-scratch computation over random mutation sequences. Any change
  must keep those green; add cases that force splits, merges, articulation detaches, leaf detaches,
  and negative-space merges.
- For the compiled port, keep a pure-Python reference path and assert equality of the cells (not the
  internals) on random schedules before switching the default.

## Reproduction

The scratch harnesses used for these numbers are not tracked (they reference local datasets). To
reproduce: compile a dataset with a topology, define a patch account on a criterion with a
threshold, and run `ws4 optimize --patch-accounts ... --topology ...` with `--lns-weight 0` for the
single-block case. Add phase timers by wrapping the `PatchGroupYear` and `PatchModel` methods. The
structural probes are a Tarjan pass, a BFS spanning tree, and an inclusive neighbour-degree count
over the largest year state.

## Open questions

- Does the bulk path stay dominant when the criterion forms *many small* patches rather than one
  giant one? The whole analysis above is for a single huge blob; a different criterion could favour
  the incremental path instead. Worth measuring before committing to the compiled port.
- How stable is "65% are spanning-tree leaves" across criteria, thresholds, and `search_distance`?
  The spanning-forest step is only worth its complexity if that fraction stays high.
- Is a full compiled port worth it against simply disabling LNS for patch targets? No: LNS is worth
  about 0.8 objective units on the patch target (11.598 vs 12.437 at equal iterations).
