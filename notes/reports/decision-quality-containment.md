# Decision quality: containment timing under weather uncertainty

Date: 2026-11-16
Input: `notes/reports/p203-containment-closure.csv`
Artifacts: `notes/reports/decision-quality-containment/`

## Question

Which closure timing should be preferred when the weather member is uncertain?

The five decisions are the P203 closure times:

- 0, 6,000, 9,000, 10,500 and 12,000 minutes.

The five scenarios are the P178 weather members. The outcome is final area, lower is better.

## Result

| Closure | Expected area | Worst case | Mean regret | Max regret | Rank stability |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 min | 98,025 ha | 98,025 ha | 0 ha | 0 ha | 1.00 |
| 6,000 min | 98,025 ha | 98,025 ha | 0 ha | 0 ha | 1.00 |
| 9,000 min | 110,025 ha | 158,025 ha | 12,000 ha | 60,000 ha | 0.50 |
| 10,500 min | 122,025 ha | 158,025 ha | 24,000 ha | 60,000 ha | 0.25 |
| 12,000 min | 134,025 ha | 158,025 ha | 36,000 ha | 60,000 ha | 0.00 |

The deterministic (lowest expected area), robust (lowest worst case), and minimax-regret
choices are all the earliest closure times, with 0 and 6,000 minutes tied. Later closure has no
upside in this matrix and loses in adverse weather.

## Decision

**Go** for the decision-quality contract: it produces expected outcome, worst case, regret,
rank stability, and constraint satisfaction from a long decision-by-scenario matrix.

**No-go** for operational use. The matrix is the P203 synthetic containment experiment, not a
real suppression schedule. It has one case, one synthetic barrier, five weather members, and no
water, crew, or dispatch model.

## Reproduce

```bash
python scripts/decision_quality.py \
  --input notes/reports/p203-containment-closure.csv \
  --decision closure_min \
  --scenario member \
  --outcome area_sim_ha \
  --output notes/reports/decision-quality-containment
```

## Limits

- Lower-is-better area only; no multi-objective tradeoff.
- Equal scenario weights; no probability model for the weather members.
- The earlier closure times are tied, so the matrix does not distinguish 0 from 6,000 minutes.
- No operational claim.
