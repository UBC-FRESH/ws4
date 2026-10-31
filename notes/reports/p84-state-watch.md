# P84: Resident Model II state watcher (c5 acceptance)

Date: 2026-10-31
Issue: #613

## Result

The resident-state path is now faster than the baseline c5 watcher and remains exact.
The key change is that a move applies cached block/option rows to the resident pages; it
does not rebuild a block through the splice evaluator or reprice every target from scratch.

The state watcher:

- loads a compact candidate index (`.npz`) instead of regenerating candidates;
- builds track/age feature arrays once;
- stores `state[period, block, account]` and separate product-event rows;
- never sums feature and product account values together;
- uses a cached, fragment-aware row builder for candidate options;
- uses a bounded option-row cache and a cached candidate-index position map;
- runs toggle/shift/swap/LNS moves after a short diversification warm-up;
- checks the final schedule against a fresh `IncrementalObjective`.

The final objective is exact in every recorded run. For example, the 1k run reports
`32,314,646.077074174` from the resident pages and `32,314,646.077071644` from the fresh
checkpoint evaluation.

## c5 benchmarks

All runs use the c5 `seed_stage1.csv` seed and the same balanced stock-79 target file.
Baseline rows are the existing `ws4 watch` path. State rows use `ws4 state-watch`.

| Budget | Path | Wall | Search | Objective |
|---:|---|---:|---:|---:|
| 1,000 | baseline | 6.95 s | 3.83 s | 44.93M |
| 1,000 | resident state | **5.04 s** | **1.74 s** | **32.31M** |
| 20,000 | resident state | 18.29 s | 14.83 s | 14.14M |
| 100,000 | baseline | 120.88 s | 115.90 s | **10.29M** |
| 100,000 | resident state | **71.46 s** | **67.60 s** | 10.46M |

At 100k the resident path is about 41% faster in wall time and about 1.6% higher in
objective. At 1k it is both faster and better. The 20k row is a state-only convergence
checkpoint.

The state run uses:

```text
--seed-state c5-seed-state.npz
--initial-schedule seed_stage1.csv
--lns-weight 0.2 --lns-destroy 0.1 --lns-max-destroy 64
```

The seed-state archive was written once with `--write-seed-state`; later runs load the
resident pages directly. The archive is tied to the account list, block list, horizon, and
period width, and `load_seed` rejects a mismatch.

## What changed

- `ws4/opt/model2_index.py`: cached block-position lookup; `chain`/`option_count` no
  longer rebuild `blocks.tolist()` on every call.
- `ws4/opt/model2_trajectory.py`:
  - fragment-aware, vectorized period-row builder;
  - cached block fragments and watched-product curve lists;
  - bounded LRU cache of per-block/option rows;
  - seed-state save/load and optional empty-page skipping;
  - prepared target descriptors in `StateObjective`;
  - warm-up plus weighted toggle/shift/swap/LNS state SA.
- `ws4 state-watch`: initial schedule, seed-state read/write, and LNS controls.
- `tests/test_model2_state.py`: loaded-index option lookup coverage.

## Limits

- c5 only. No TSA24/29 acceptance run in this phase.
- The 100k objective is still slightly above the baseline; the win is wall-clock and the
  1k/accepted-state exactness.
- The seed-state cache is an optimization, not a new source of truth. A cache built from a
  different seed is a caller error; the current loader validates shape and identity but not
  schedule equivalence.
- The live TUI path and the `--plain` benchmark share the same state projection, but only
  the plain path is recorded here.
