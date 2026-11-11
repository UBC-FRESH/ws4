# P164.2 multi-fire event benchmark

Date: 2026-11-11
Phase: P164 (Decision-grade wildfire risk validation)
Task: P164.2 (#979)
Evidence: `notes/reports/p164-multi-fire.csv`, `notes/reports/p164-multi-fire.json`
Envelope: `ws4.fire.validation`, `docs/reference/fire-validation.rst`

## Cases

Only two public observed-fire fixtures exist in the repository:

- Dogrib RWF085 Scenario 2b, 402 minutes, with the P160 threshold gate.
- Hay River / K'atl'odeeche `2023_320`, full 9,360-minute event.

No third public fire was invented or substituted. Hay River is retained as a failure case.

## Result

| Case | IoU | Sorensen | Area bias | Perimeter bias | Published Jaccard position |
| --- | ---: | ---: | ---: | ---: | --- |
| Dogrib Scenario 2b | 0.385 | 0.556 | +58.9% | +75.9% | above |
| Hay River full event | 0.275 | 0.431 | +263.1% | +223.1% | within |
| Median | 0.330 | 0.494 | — | — | — |
| Worst | 0.275 | 0.431 | — | — | — |

The published event envelope used here is Jaccard **0.15–0.30**, an envelope around
WildfireAV ELMFIRE/FARSITE means and the Prometheus Dogrib cases. It is context, not a pass
mark.

## Interpretation

- Dogrib overlap is above the published mean envelope; Hay River overlap is inside it.
- Both cases have large area and perimeter biases. Overlap alone does not make either an
  operational match.
- Hay River is saturated: the model burns the full 10,846-cell burnable domain.
- Two fires are still not a regional validation. They are the available public evidence.
- No model selection, tuning, or exclusion of failed cases was performed.

## Decision

P164.2 is complete as a **two-case event benchmark with a data-gap caveat**. It is not a
regional validation and does not establish a pass on its own.

The result is consistent with P164.1: event overlap is only one tier, and the published
benchmark must be interpreted with area/perimeter bias and data limitations.

## Limits

- Only two public fires, both already used in P157/P161.
- Dogrib uses the observed start perimeter and hourly patches.
- Hay River uses a point ignition, satellite-derived perimeter, and no suppression.
- Published envelopes come from different regions, grids, and input data.
- No burn-probability, treatment-effect, or tree-mortality evidence is included here.
