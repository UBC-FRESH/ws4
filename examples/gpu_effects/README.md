# GPU effect-table examples

These scripts are bounded prototypes for the P83.6 GPU batch path.  They do not change the
CPU optimizer; the compiled dataset and target file are supplied by the caller.

- `benchmark_c5.py` builds a sparse float64 effect table for a block slice and compares
  batched device gather/subtract/segmented-sum with the CPU contribution lookup.
- `search_c5.py` runs the batched best-of-batch LNS prototype next to the stock CPU LNS
  annealer and re-evaluates both final schedules with `IncrementalObjective`.

Both need PyTorch with CUDA and the optional dependency:

```bash
python -m pip install -e '.[gpu]'
```

Pass a local compiled dataset and target file:

```bash
python examples/gpu_effects/benchmark_c5.py \
  --dataset /path/to/compiled \
  --targets /path/to/targets.yaml \
  --seed-schedule /path/to/seed.csv \
  --blocks 2000

python examples/gpu_effects/search_c5.py \
  --dataset /path/to/compiled \
  --targets /path/to/targets.yaml \
  --seed-schedule /path/to/seed.csv \
  --blocks 2000 --rounds 500 --proposals 128 --cpu-iterations 30000
```

The effect table is target-specific.  Rebuild it when the active accounts, period widths,
or feature checkpoints change.  A first run pays the row build; later runs can reuse the
same table while the target set and block slice stay fixed.

`run_full_model.py` is the full-model, exact-replay runner. It reuses a content-validated
simulator cache and candidate cache, loads a lean effect table, writes the best schedule,
and verifies it with a fresh `IncrementalObjective`:

```bash
python examples/gpu_effects/run_full_model.py \
  --dataset /path/to/compiled \
  --targets /path/to/targets.yaml \
  --seed-schedule /path/to/seed.csv \
  --table /path/to/effects-lean.pt \
  --candidates-cache /path/to/candidates.pkl \
  --simulator-cache /path/to/simulator-cache.pkl \
  --out /path/to/best.csv \
  --years 200 --population 64 --generations 1000 --seed 7
```

Pass `--rebuild-cache` after changing the dataset or candidate horizon. The caches are
explicit local artifacts, not model outputs shipped by WS4.

`run_full_model_session.py` keeps the loaded model and option map resident while running
several seeds:

```bash
python examples/gpu_effects/run_full_model_session.py \
  --dataset /path/to/compiled \
  --targets /path/to/targets.yaml \
  --seed-schedule /path/to/seed.csv \
  --table /path/to/effects-lean.pt \
  --candidates-cache /path/to/candidates.pkl \
  --simulator-cache /path/to/simulator-cache.pkl \
  --out-dir /path/to/schedules \
  --seeds 7 8 9 --years 200 --population 64 --generations 1000
```

Use this for repeated seeds or a long-lived worker. Use `run_full_model.py` for one search.

