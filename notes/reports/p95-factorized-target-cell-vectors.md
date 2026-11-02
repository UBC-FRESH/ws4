# P95 factorized target-cell vector cache

Date: 2026-11-02
Status: complete

## Result

P94 found that the all-period ±5% stock floor was non-binding but made the 5,000-generation
search about 4x slower. P95 removes that repeated padded-layout recomputation.

| Scenario | P94 search | P95 search |
|---|---:|---:|
| all-period ±5% + stock floor | 218.9 s | **44.0 s** |
| all-period ±5%, no stock | 43.1 s | **43.0 s** |

- exact objective error: **1.7e-9**
- schedules remain byte-identical:
  `44bdba7a6cf95a056410ccda4ab86ed74d144fd5c72e63e9430323060440eb1b`
- 320,064 evaluations per scenario
- host peak RSS: 11.26 GB

## Mechanism

`FactorizedAccountSet.option_values(account, offset)` builds one cached `[options]` vector
for a target cell. The population gathers that vector through its candidate rows, instead
of constructing a `[genomes, blocks, fragments, segments]` intermediate every generation.

The display path continues to use the full padded evaluator, because it is evaluated only
for the incumbent and not on every generation.

## Decision

The P94 recommendation to leave the stock target out for speed is superseded. The stock
floor can remain in the search as a guard at roughly 2% overhead. At this seed it is still
non-binding, so the accepted all-period ±5% schedule remains the same.

This is a performance result, not a new sustainability claim. The managed old-seral and
unmanaged age-class caveats remain.

## Archive

```text
/srv/shared-data/gep/ws4/archive/tsa24-ltsy-vector-cache/
```

Contains the two schedules, exact results, comparison harness, and checksums.
