# TSA46 harvest-floor carbon frontier

Date: 2026-10-29
Status: bounded frontier complete; exact replay recorded
Scope: 500-block TSA46 subset, high-displacement HWP, 50-year horizon

## Setup

- Dataset: `/tmp/opencode/tsa46-carbon-opt-dataset` (500 blocks, 535 fragments)
- Package: `femic-carbon-46-346e66598638`
- HWP: high-displacement sensitivity (`df solid = 2.4`)
- Initial schedule: 95 CC rows at offset 0
- Search: SA, seed 1, 50 iterations, 8 carbon workers
- Objective: satisfy a managed-yield floor and minimize cumulative system emissions

Priority convention matters here: **priority 1 is the strongest tier**. The first
attempt gave yield priority 2 and emissions priority 1; emissions dominated, the floor was
not enforced, and every point collapsed to the same schedule. The run below uses
**yield priority 1** and **emissions priority 2**; every floor is met.

## Frontier

| Yield floor (m3) | Blocks | Yield (m3) | Harvest (m3) | System C (tC) | Exact cumulative emissions (tCO2e) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 86 | 205,537 | 326,177 | 2,057,647 | 160,457 |
| 100,000 | 86 | 205,537 | 326,177 | 2,057,647 | 160,457 |
| 200,000 | 86 | 205,537 | 326,177 | 2,057,647 | 160,457 |
| 300,000 | 88 | 300,609 | 326,956 | 2,047,097 | 195,345 |
| 350,000 | 91 | 350,368 | 354,732 | 2,031,711 | 216,749 |
| 370,000 | 94 | 370,197 | 371,516 | 2,024,495 | 229,691 |

The 0–200k range is a flat plateau: the harvest floor is not binding above the
minimum-harvest solution. From 300k upward the frontier is monotone: yield and harvest
rise, cumulative emissions rise, and system carbon falls.

Ledger-vs-exact differences were 0.08–0.29% on cumulative emissions and under 0.02% on
system carbon across the set. The exact runs use the same package, HWP config, and
schedule; no defaults override was used.

## Reading

Within this subset and displacement assumption, **stock carbon and emissions move
together**: increasing harvest lowers system carbon and increases cumulative emissions.
The actual policy trade-off is between harvested yield and carbon outcomes, not between
maximizing stock and minimizing emissions independently.

This is a bounded 500-block mechanism result, not a provincial optimum. It uses one seed,
50 iterations, and a high displacement factor. A production frontier should add multiple
seeds, the public displacement range, and the full TSA landscapes.

## Artifacts

- `/tmp/opencode/tsa46-frontier2-yield1-opt-<floor>/`
- `/tmp/opencode/tsa46-frontier2-yield1-opt-<floor>-exact/`
- `/tmp/opencode/tsa46-frontier2-yield1-summary.csv`
- `notes/reports/carbon-500block-tradeoff.md`
- `notes/reports/carbon-ledger-performance.md`
