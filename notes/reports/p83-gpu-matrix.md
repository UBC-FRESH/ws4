# Full TSA23 GPU seed matrix

Date: 2026-10-31

## Result

The checked-in `ws4 gpu-run` command ran **ten population seeds** on the full TSA23
`ft_econ` 20 x 10 target. Every returned schedule replayed to exact objective **0.0**.

Command:

```bash
ws4 gpu-run \
  --dataset .../compiled_ft_econ \
  --targets .../evenflow_ft_econ_20x10.yaml \
  --seed-schedule .../seed_evenflow_ft_econ_20x10.csv \
  --table .../effects-lean.pt \
  --cache-dir /tmp/opencode/gpu-cache-cli \
  --out-dir .../matrix-seeds \
  --seeds 1,2,3,4,5,6,7,8,9,10 \
  --generations 1000
```

| Seed | Exact objective | Search s |
|---:|---:|---:|
| 1 | 0.0 | 12.7 |
| 2 | 0.0 | 4.2 |
| 3 | 0.0 | 8.3 |
| 4 | 0.0 | 4.0 |
| 5 | 0.0 | 4.5 |
| 6 | 0.0 | 5.8 |
| 7 | 0.0 | 6.0 |
| 8 | 0.0 | 5.7 |
| 9 | 0.0 | 4.0 |
| 10 | 0.0 | 4.7 |

- Session build: **33.6 s**
- Total for all ten seeds: **110.0 s**
- Outputs: `/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/matrix-seeds/`
- Record: `/srv/shared-data/gep/ws4/archive/tsa23-gpu-full/matrix-seeds.json`

The CPU reference for the same target is 386 s for one seed. The ten-seed GPU batch is
therefore about **35x** the per-seed CPU reference in aggregate, but this is not a controlled
ten-seed CPU matrix. The table build and cache construction are excluded.

## Exactness comparison fix

A one-generation smoke run exposed a reporting bug, not a schedule error. The device score
was `14055909.097210389` and the fresh exact replay `14055909.097210424`; the difference is
3.5e-8, but the runner compared them with `==` and printed `exact_match=false`.

The CLI and both GPU example runners now use the same tolerance as the tests:
`rel_tol=1e-9, abs_tol=1e-6`. The one-generation smoke run reports `exact_match=true` after
the fix. The ten-seed matrix already returned objective 0 on both sides, so its conclusion
did not depend on the comparison bug.

## Scope

- One target, ten seeds.
- Effect table, simulator cache, and candidate cache reused; cache build excluded.
- The GPU path keeps the prototype contract: one priority tier, no patch accounts, no
  route accounts, no spatial rules.
- All schedules are saved under `matrix-seeds/`.
