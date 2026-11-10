# P159 surrogate evaluation

Date: 2026-11-10
Phase: P159 (Fire surrogate feasibility)
Tasks: P159.3 (#968)
Model: `notes/reports/p159-model/`
Evaluation: `notes/reports/p159-evaluation.csv`, `notes/reports/p159-evaluation.json`

## Held-out synthetic

The frozen model was evaluated on the 24 validation samples from the same 120-sample corpus.
The corpus seed and split are recorded in the model card.

| Metric | Value |
| --- | ---: |
| Samples | 24 |
| Mask IoU, mean | 0.374 |
| Mask IoU, min | 0.000 |
| Mask IoU, max | 0.859 |
| Sorensen, mean | 0.494 |
| Centroid distance, mean | 0.223 km |
| Inference time, mean | 0.90 ms |

The validation loss is 0.615 against a training loss of 0.206. The model overfits the small
training set.

## Dogrib out-of-distribution

The model was run on the Dogrib fixture at 402 minutes. It was not trained on Dogrib or on any
observed fire. The model has no duration input and was trained on 60-minute 32 × 32 burns, so
this is a domain- and duration-shift case, not a like-for-like comparison.

| Metric | Value | P157 screen |
| --- | ---: | --- |
| Simulated area | 11,315 ha | — |
| Observed area | 10,219 ha | — |
| Area bias | +10.7% | pass |
| Perimeter bias | +148.2% | fail |
| Centroid distance | 5.23 km | fail |
| IoU | 0.203 | fail |
| Sorensen | 0.337 | fail |
| Orientation error | 24.6° | pass |
| Inference time | 67.5 ms | — |

The area is coincidentally close, but the footprint is wrong: perimeter is 2.48× observed,
overlap is low, and the centroid is outside the 5 km screen.

## Interpretation

- The surrogate is fast on CPU, but its synthetic validation overlap is moderate and
  per-sample worst cases are complete misses (IoU 0).
- It does not transfer to Dogrib OOD. The close area is not useful because the shape and
  location fail.
- The absence of a duration feature is a design flaw for any comparison against a 402-minute
  observed fire.
- This is sufficient for the P159.4 integration gate: do not integrate, do not depend on it in
  the web/UI, and do not describe it as a validated fire model.

## Limits

- Synthetic samples are 32 × 32, 60-minute, point-ignition, flat/constant-slope burns.
- No spotting, suppression, or hourly BUI.
- Dogrib is OOD evidence only; it was never used for training or model selection.
- The model is a screening candidate at best, not a replacement for the FBP kernel.
