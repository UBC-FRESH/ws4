# GPU effect-table build postmortem

Date: 2026-11-01
Severity: production-host outage
Status: corrective design required before another build

## Incident

A TSA24 GPU effect-table build was launched to add a second watched account,
`feature.Yield.managed.Total`, to the existing harvest-product effect table. The build
used the new parallel, lean-table path with up to 32 forked workers.

The process exhausted host memory, entered sustained swap thrashing, and degraded other
services on the shared machine, including the reverse proxy and SSH. The host required a
hard reboot.

This postmortem records the cause and the controls that must exist before another
full-table build is attempted. No active build should be run on a shared host without a
hard memory budget and an isolated resource limit.

## What the requested cache would have been

The existing harvest-product-only table is approximately:

```text
rows:        50,096,750
nonzeros:    65.0M
indptr:      400.8 MB
indices:     520 MB
values:      520 MB
total:       1.44 GB
```

The requested table used `watchable_cells` for both:

```text
product.HarvestedVolume.managed.Total.CC
feature.Yield.managed.Total
```

`watchable_cells` includes **every year offset**, not only period ends. For the feature
account, every `(block, candidate option)` row has a feature value at essentially every
offset. The order-of-magnitude estimate is:

```text
feature nonzeros ≈ 50,096,750 rows × 200 offsets
                 ≈ 10.0 billion

indices + values ≈ 10.0B × 16 bytes ≈ 160 GB
indptr            ≈ 0.4 GB
final sparse cache ≈ 160 GB
```

That is the final on-disk/device representation. During construction, the builder was also
holding Python lists of row ids, column ids, and float values, each with Python object
overhead. Peak RAM was therefore in the hundreds of gigabytes before counting worker
copies and inherited optimizer/candidate caches.

Even a feature-only table restricted to the 20 period-end offsets is roughly:

```text
50,096,750 × 20 × 16 bytes ≈ 16 GB sparse
```

plus build-time object overhead.

## Root causes

1. **No preflight size estimate.** The builder computed cells and started pricing without
   estimating nonzero count, final cache size, or peak construction memory.
2. **Wrong cell basis for a display account.** A watched feature account was treated as a
   full effect-table column set, including every offset, rather than a display-only value
   or a small period-end basis.
3. **Unbounded in-memory accumulation.** The parallel builder collected all COO row,
   column, and value entries in the parent process and converted lists to tensors at the
   end. That is not a streaming build.
4. **Unbounded worker fan-out.** Up to 32 forked workers were allowed. Each worker inherited
   large read-only caches and independently built Python delta objects. There was no
   worker-memory budget or cgroup cap.
5. **No process guard.** The build had no `RLIMIT_AS`, cgroup memory limit, swap guard, or
   early-abort threshold.
6. **The display requirement was misclassified.** The requirement was to watch total
   growing stock while the solver ran. That does not require a per-option feature effect
   table for every block/option row.

## Corrective design

### 1. Split objective cells from display cells

The effect table should contain only cells the GPU objective actually prices. A watched
feature account should use a separate display path. It must not automatically inflate the
objective table.

### 2. Preflight memory accounting

Before building, compute:

```text
rows
candidate options
requested cells
estimated nonzeros
final sparse bytes
estimated peak construction bytes
worker count × per-worker peak
```

Abort before launching workers if the estimate exceeds the configured budget. Print the
estimate even for a successful build.

### 3. Stream, do not accumulate

Write sparse chunks to temporary memmaps or ordered chunk files. Merge them in a
memory-bounded pass. Do not hold the complete COO representation as Python lists.

### 4. Hard resource limits

- Default to one worker.
- Make multi-worker builds opt-in.
- Set `RLIMIT_AS` in each worker.
- Run large builds in a cgroup with a hard memory limit.
- Cap worker count from a measured per-worker budget, not CPU count.
- Do not run large builds on the shared interactive host.

### 5. Right-size display accounts

For a feature display account, evaluate only the values the watcher needs, preferably
through the resident state or a period-end display cache. A 20-offset feature table is
already about 16 GB sparse and is still too large for an unconditional watcher path.

### 6. Cache metadata and validation

Persist and validate:

- dataset fingerprint;
- candidate identity;
- account/cell basis;
- row count and nonzero count;
- build memory estimate and actual peak;
- whether the table is objective-only, display-only, or both.

## Immediate operational rules

- Do not run the effect-table builder against TSA24 without a written memory estimate.
- Do not use more than one worker unless the budget explicitly allows it.
- Do not launch a build on the shared host without a cgroup or equivalent isolation.
- Do not add a watched account to the GPU table as a shortcut for chart support.
- Treat a table build as a batch job with a hard failure mode, not an interactive setup
  step.

## Acceptance for the next build

1. A preflight report states rows, cells, estimated nonzeros, final bytes, worker peak, and
   host/container memory limit.
2. The build refuses to start if the estimate exceeds the approved budget.
3. The build streams and never holds the full COO in Python lists.
4. Workers have a hard memory cap and a bounded count.
5. The host remains responsive throughout.
6. The resulting table's nonzero count and file size match the estimate.
