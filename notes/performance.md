# Performance (P3.5)

The compile and simulate paths are measured with `scripts/benchmark.py` (a synthetic landscape
built from the matrix regression fixture) and with the C5 sample. The host is a 72-core Linux
machine with 754 GiB of RAM.

## Hot paths found

- **Builder: re-parsing per fragment.** The builder evaluated each select statement for every
  fragment and re-tokenized and re-parsed it each time. For 100 038 fragments that was 240 048
  `evaluate` calls and about 10.5 s of a 13.8 s run.
- **Simulator: a per-curve `.loc` setitem.** `account_values` assigned each curve group's yields
  with `merged.loc[group.index, "yield"] = ...`. The C5 model has about 130 423 curves, so that
  setitem dominated the run (about 2.9 s of 4.2 s for five years).

## Fixes

- `ws4/io/expressions.py` caches the parsed tree per statement (`lru_cache`). The tree is built
  from immutable tuples and is never mutated, so sharing it across fragments is safe.
- `ws4/sim/engine.py` assigns yields into a positional numpy array instead of using `.loc` per
  curve group.

## Results

### Synthetic build and simulate (fixture recipe, 10-year horizon)

| Fragments | Build before | Build after | Simulate | Peak RSS |
| ---: | ---: | ---: | ---: | ---: |
| 6 240 | 0.29 s | — | 0.08 s | 128 MiB |
| 24 946 | 1.06 s | — | 0.10 s | 157 MiB |
| 100 038 | 3.79 s | **1.66 s** | 0.26 s | 231 MiB |

The build is roughly linear in the fragment count after the parse cache.

### C5 sample (16 174 fragments, 130 423 curves, 20 151 features)

| Step | Result |
| --- | --- |
| Ingest | 0 validation problems; tracks 1558, strata 3551, treatments 1398, features 20151, curves 130423 |
| Simulate, 5 years | 1.2 s |
| Simulate, 30 years | 15.5 s → **4.2 s** |
| Optimize | one objective evaluation is a full simulate, so the iteration budget must fit the horizon |
| Route | 27231 vertices, 36721 segments, 3 destinations |

## Block aggregation

The simulator aggregates fragments to blocks only where a feature needs it (patch metrics and
routing). At the C5 scale the per-curve yield evaluation dominates, so block aggregation is not
the hot path. The architecture note's open question about a cached incremental block aggregate
is therefore deferred.

## Vectorization

Curve evaluation is vectorized per curve: `account_values` calls `np.interp` once per distinct
curve, not once per fragment
(`tests/test_simulator.py::test_curve_evaluation_is_vectorized_per_curve`).

## Reproduce

```bash
python scripts/benchmark.py --fragments 100000 --years 10
python scripts/benchmark.py --fragments 100000 --years 10 --profile
```
