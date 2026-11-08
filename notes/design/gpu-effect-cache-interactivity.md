# GPU effect cache and interactive target editing

Status: design issue
Date: 2026-11-01
Related: `ws4-fast-startup.md`, `ws4-optimization-stack.md`

## Problem

The persisted GPU effect table is built from the **active target cell set**:

```text
EffectTable cells = target_cells(IncrementalObjective(targets))
```

Each table cell is an `(offset, account)` pair. The table rows are
`(block, candidate chain)` effects. This is fast for a fixed scenario, but it couples the
cache to the target configuration in a way that is hostile to interactive use.

The Patchworks usability pattern is:

- analysts watch multiple accounts, including accounts that are not active targets;
- the solver runs while the analyst changes target minimums, maximums, weights, penalty
  shapes, or activates/deactivates targets;
- the analyst sees the solution and target windows react immediately;
- the analyst “nudges” the search through solution space until the scenario is acceptable.

The current cache cannot support that loop for changes that alter the cell set.

## What is safe without rebuild

These are price-only changes and should not rebuild the effect table:

- `minimum`, `maximum`
- `min_weight`, `max_weight`
- `shape`
- `normalization`
- `priority`
- `flow_reference_period`
- the flow band (`±1%`, `±5%`, etc.)
- activating/deactivating a target whose accounts/periods are already in the cell basis

## What currently invalidates the design

A full rebuild is required when the cell basis changes:

- adding or removing a target account;
- adding a new target period or extending a flow window into periods not in the table;
- changing `period_width` or `years`;
- watching a display account that is not in the effect-table cell set (the GPU watcher
  cannot price or chart an account that is absent from the table);
- changing a seed schedule to a chain that is neither a candidate nor an existing extra
  row (the table needs a new option row);
- changing candidate generation limits or the candidate row order.

For the full TSA24 model the effect-table build was about **4,351 s** (about 72 minutes).
Interactive “add a target / watch another account” therefore becomes a one-hour cache
rebuild. That is unacceptable in production and is the main design flaw to fix before the
interactive solver is treated as a general product.

## Why this is architectural, not just a cache miss

The table mixes three identities:

1. model identity — dataset, blocks, fragments, tracks, treatments, curves;
2. candidate identity — the block/option rows;
3. scenario identity — the active target accounts and periods.

Only the first two should determine the expensive table. The third belongs in the pricer,
which is cheap.

## Design directions

### 1. Target-independent cell basis

Build the effect table over a **superset of model cells** rather than the active target
cells:

```text
cells = watchable accounts × accounting periods/offsets
```

Target activation then becomes a mask over columns. A target add/remove/activate/deactivate
only changes the pricer mask and weights; the table stays resident. The display path also
reads the same basis, so inactive/un-targeted watched accounts have values.

The cost is a larger sparse table and a larger build. The benefit is that the expensive
object depends on the model, not on the analyst's current target set.

### 2. Lazy column extension

Allow the effect table to append a new account-period column without rebuilding all rows:

```text
existing table + new cells -> compute only the new cells for every (block, option)
```

If the new column can be produced in seconds/minutes, adding a watched account is
interactive even when it is not in the predeclared basis. This needs a column-add API and
an on-device table update, not a new archive.

### 3. Separate display path

The objective table should not also be the chart table. A target-independent display path
can read arbitrary watched accounts from the resident state/simulator, while the GPU table
prices only the active objective cells. This avoids putting every possible display account
into the effect table.

### 4. Two-tier cache

- **Tier A:** model/candidate rows, expensive, stable.
- **Tier B:** account-period column subset for the current scene, cheap/lazy.

The cache key must not include active target membership.

## Acceptance criteria for the fix

1. Change target min/max/weight/shape/priority while the solver is running: no rebuild.
2. Add or remove an active target account whose cells are in the watchable basis: no
   rebuild.
3. Activate/deactivate a target: no rebuild.
4. Add a watched account that is not currently a target: no full rebuild; either already
   in the basis or appended incrementally.
5. Change a flow window within the horizon: no full rebuild; add columns if needed.
6. Dataset or candidate-generation changes may still trigger a full rebuild.
7. The table cache key is the model + candidate identity, not the scenario target set.

## Current workaround

For a fixed benchmark, predeclare every account and period that will be watched, build the
cell superset once, and keep target edits price-only. This is acceptable for a paper
benchmark or a frozen production scenario, but it is not the interactive product contract.


## Implemented foundation

The first slice is now in the code:

- `EffectTable.build(..., cells=...)` accepts an explicit target-independent cell basis.
- `watchable_cells(accounts, years)` creates an all-offset basis for a configured account
  set.
- The table persists `basis_accounts`, so a loaded cache declares what it covers.
- The GPU pricer now rejects a target cell that is absent from the table instead of
  silently dropping the term.
- `examples/gpu_effects/build_effect_table.py --cell-accounts ...` builds a table over the
  configured watchable basis.

Target weights, bounds, shapes, and priorities are price-only changes. A target account or
period already covered by the basis is also live-safe.

Target hot reload is now wired into the GPU watcher: the target YAML is polled for mtime
changes, the resident population re-prices its existing genomes, and the watch windows are
rebuilt without recreating the effect table or option map. A target change outside the
basis is reported as a reload failure rather than silently changing the objective.

Lazy column extension is now implemented through `EffectTable.extend_cells`: new
account/offset columns are priced for existing rows and appended to the resident CSR,
without rebuilding the old columns. `GenomePopulation` calls it automatically when a target
edit introduces cells outside the table basis.

The remaining production gap is the display/account UX around that extension: decide when
to persist the enlarged table, how to show extension latency, and how to make an arbitrary
watched account available without forcing it into the objective cell set.
