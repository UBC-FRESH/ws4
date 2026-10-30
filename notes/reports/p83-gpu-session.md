# Resident GPU search session

Date: 2026-10-30

## Purpose

A single full TSA23 run still builds the simulator, candidate map, effect table, and
population option map before searching. A resident session keeps those objects alive and
resets only the random stream, genomes, and incumbent between seeds.

`ws4/opt/gpu_session.py` provides `GpuSearchSession`; `GenomePopulation.reset` performs the
per-run reset without rebuilding the option map or base state.

## Measured batch

Full TSA23 `ft_econ` 20 x 10, 64 genomes, 1,000 generations, seeds 7/8/9, one resident
session:

| Stage | Seconds |
|---|---:|
| Simulator cache load | 7.1 |
| Candidate cache load | 12.9 |
| Targets + seed schedule | 7.1 |
| Lean table load | 1.2 |
| Session/option-map construction | 17.4 |
| Seed 7 first run | 21.0 |
| Seed 8 run | 8.6 |
| Seed 9 run | 8.0 |
| **Total** | **83.2** |

All three returned schedules replayed to exact objective **0.0**.

The separate cached runner measured 32.9 / 33.7 / 35.5 s for the same seeds, or about
100 s for three independent processes. The resident session is about **1.2x faster for this
three-seed batch**. The gain is limited by the first-run GPU warm-up and the shared setup;
for larger seed batches the per-seed cost is the 8 s search, not the setup.

## What it does and does not do

- It reuses the simulator, candidate map, lean effect table, option map, and base state.
- It resets the random stream and population per seed.
- It does not share method state between independent workers; use one session per worker.
- It does not improve the first single run; the one-shot runner remains the right path when
  only one search is needed.
- It is a library session plus a batch example, not a network daemon.

## Evidence

- `ws4/opt/gpu_session.py`
- `examples/gpu_effects/run_full_model_session.py`
- `tests/test_gpu_ga.py`
- Full schedules under
  `/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/session-schedules/`
