# TSA24 LTSY scenario comparison

Date: 2026-11-02
Status: 5,000-generation comparison complete; PR pending

Three LTSY formulations were compared on the same TSA24 model, seed schedule, population
(64), random seed (7), and 5,000-generation budget:

- **baseline**: flow on periods 11–20, ±1%, reference 11; no stock floor.
- **allperiod5_stock**: flow on periods 1–20, ±5%, reference 1; managed-stock floor at
  90% of initial.
- **allperiod5_nostock**: the same all-period flow without the stock floor.

The level aspirations remain in all three.

## Exact results

| Scenario | Objective | Exact error | Search time |
|---|---:|---:|---:|
| baseline | 275.34471086 | 2.4e-12 | 42.8 s |
| allperiod5_stock | 2,751.96469866 | 1.3e-9 | 218.9 s |
| allperiod5_nostock | 2,751.96469866 | 1.0e-9 | 43.1 s |

Objective values are not directly comparable across different target sets.

## Key finding

`allperiod5_stock` and `allperiod5_nostock` produced **byte-identical schedules**:

```text
44bdba7a6cf95a056410ccda4ab86ed74d144fd5c72e63e9430323060440eb1b
```

The stock floor is **non-binding** at this seed and budget. Pricing the factorized stock
cell every generation makes the search about **4x slower** without changing the schedule.

The comparison exactly reproduces the accepted P89 all-period scenario.

## Post-run outcomes

| Metric | Baseline | All-period ±5% |
|---|---:|---:|
| Period-1 harvest | 48.8M | 51.7M |
| Harvest periods 1–10 | 19.7–48.8M | 48.7–54.2M |
| Harvest periods 11–20 | 71.7–73.4M | 53.9–54.6M |
| Final managed stock | **356.1M** | **477.5M** |
| Final unmanaged stock | 521.1M | 521.1M |
| Stock floor | not present | **met** |

Managed age classes:

| State | <40 | 40–199 | ≥200 |
|---|---:|---:|---:|
| Baseline final | 31.7% | 67.4% | 0.9% |
| All-period final | 24.3% | 75.1% | 0.6% |

The unmanaged estate is 100% ≥200 years in both cases after the 200-year horizon.

## Recommendation

Use **all-period ±5% even flow without the stock target in the search** as the base LTSY
formulation:

- it gives the accepted near-flat flow;
- it is about 4x faster than the stock-cell variant;
- it produces the same schedule as the stock variant because the floor is non-binding.

Monitor managed stock post-run. Add the stock target when a scenario approaches the floor,
or after the factorized feature-cell pricing is made cheaper.

This remains a base formulation, not a definitive sustainable scenario. The managed
old-seral decline and the unmanaged 100% ≥200 age are policy caveats.

## Archive

```text
/srv/shared-data/gep/ws4/archive/tsa24-ltsy-scenario-comparison/
```

It contains the three target files, schedules, exact results, post-run replays, age-class
tables, checksums, and the comparison harness.

## Pull request

PR #672 contains the harness and notes. The archive is outside git.
