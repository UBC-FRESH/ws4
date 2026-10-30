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
