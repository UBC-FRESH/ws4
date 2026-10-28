# Phase close-out report: P79 Flow targets are not level bands

Phase: P79, Flow targets are not level bands
Parent issue: #559
Pull request: #561, `feature/p79-flow-bands` into `main`
Evidence head: `e515203`, CI run `40728364308`
Date: 2026-10-28
Status: queued for approval. Not merged.

## Recommendation

1. Squash-merge #561 and delete `feature/p79-flow-bands`.
2. Close task #560 and parent #559.
3. Deploy `v84` and re-check the c5 base charts.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Level charts show level bounds, not -1/+1. | c5 base chart readout: conifer `min 700,000`, deciduous `min 50,000`; flow is a separate meta label. | Met |
| Flow targets remain priced and visible in the table. | Target table still has the 43 rows; the flow rows remain active. | Met |
| c5 base charts read correctly at 20 periods. | 3 charts · 20 periods; conifer and deciduous level floors; stock final-period indicator. | Met |
| Regression test covers level + flow. | Target-series test writes a level and an even-flow target and asserts the level minimum remains 12.0, maximum null, flow even. | Met |
| Dashboard green. | All seven gates green; CI `40728364308`. | Met |

## What changed

- `run_target_series` now skips minimum/maximum folding for `target.flow`; it stores the flow
  label on the cell but leaves level bounds intact.
- Client fallback chart cells use only non-flow rows for min/max and keep the flow annotation.
- Chart meta labels the account as `even flow`/`ndy flow` without changing the y-axis.
- c5 base scenario charts now show **700,000** and **50,000** level floors, plus the final stock
  floor, instead of the -1/+1 flow bands.

## Limits

The target table still shows flow rows with their percent bounds; that is the optimizer contract.
The chart explicitly separates them.

## Decision

- [x] Approve as written.
