# Factorized account basis for GPU target switching

P88 keeps the target-independent structural facts of each option and prices an account
from small track/age or track/treatment/age curve tables. It replaces the rejected
all-account matrix.

## Why the matrix is rejected

TSA24 has 50,096,749 candidate options. A 78-account basis with 20 period ends and every
option would need roughly 1.25 TB of sparse values before row/column offsets, and about
12.5 TB if every offset is stored. The previous attempt to build a 160.7 GB product plus
feature table exhausted host memory and required a hard reboot; the new builder refuses
that shape before starting workers.

## Structural basis

The persisted archive
`runtime/factorized/tsa24-factorized.npz` contains:

- block and option offsets;
- fragment and segment boundaries;
- segment `(start, track, age, area)`;
- treatment events `(offset, track, age, label, area)`;
- the treatment-label index.

It is account-independent. A target account is a lookup over the same structure.

## Padded GPU layouts

TSA24 has two fragments per option, at most four segments per fragment, and at most three
product events per option. P88 pads only those small axes:

- feature segments: `[options, fragments, segments]`;
- product events: `[options, events]`;
- one account lookup: `[tracks, ages]` for features and
  `[tracks, labels, ages]` for products.

The feature and product lookup tables are float64 and a few hundred kilobytes. The
padded structural tensors are the only large resident objects.

## Exactness and limits

The base and active segment rule is the same as the flat array evaluator. Feature totals
are `area * feature_value(track, age + offset - start)` for the last segment that starts
at or before the offset. Product totals are point contributions at the event offset.

Limits:

- the padded shape is TSA24-specific; another model must declare its maxima;
- a factorized account is priced for candidate rows, not seed-only rows that are absent
  from the candidate list;
- a watched feature offset of `-1` is not a target cell and is not supported by this
  path;
- account switching still needs a one-time build of the structural tensors; the account
  lookup itself is cheap.

## Integration

`GenomePopulation` accepts an optional `FactorizedAccountSet`. When a new target reads a
cell absent from the sparse table, the population keeps the table unchanged, prices only
that cell set from the factorized account, and concatenates the values before the
existing objective pricer. Disabling the target removes the extra cells again.

## Evidence

- Feature: 64 genomes, 20 ten-year periods, `feature.Yield.managed.Total`; **0.706 s**, exact error
  **2.2e-5**, GPU peak **7.2 GB**.
- Product: 64 genomes, `product.Yield.managed.Total`; **0.0255 s**, exact error
  **8.9e-7**, GPU peak **4.6 GB**.
- Mixed switch: four cells across `feature.Yield.managed.Total` and
  `product.Yield.managed.Total`; **0.093 s**, exact error **1.1e-5**, GPU peak
  **9.3 GB**.
