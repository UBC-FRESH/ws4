# P159 close-out: fire surrogate feasibility

Date: 2026-11-10
Parent issue: #946
Tasks: P159.1 (#966), P159.2 (#967), P159.3 (#968), P159.4 (#969)
Branch: `feature/p159-fire-surrogate`
Status: no-go for integration; research artifact retained
Report: `notes/reports/p159-evaluation.md`

## Result

The surrogate is fast but not accurate enough to integrate.

- Held-out synthetic mask IoU: 0.374 mean, 0.000–0.859 range.
- Validation loss 0.615 against training loss 0.206: overfit.
- Dogrib OOD: area +10.7%, perimeter +148.2%, centroid 5.23 km, IoU 0.203,
  Sorensen 0.337, orientation 24.6°.
- Dogrib passes area and orientation only; fails perimeter, centroid, IoU, and Sorensen.
- Inference is fast: 0.90 ms per synthetic sample, 67.5 ms for the full Dogrib grid.

## Gate decision

**No integration.** The model is a research artifact only.

- No web or UI dependency.
- No replacement for the P156 kernel.
- No claim of observed-fire validation.
- No claim that the close Dogrib area is a successful prediction.

## Why it failed

- The model has no duration input and was trained only on 60-minute burns.
- The corpus is small and the validation loss shows overfitting.
- Per-cell features with only ignition distance and bearing cannot represent the spatial
  connectivity of the Huygens front.
- Worst-case synthetic samples are complete misses.

## What is retained

- `ws4.fire.surrogate` deterministic corpus generator.
- `ws4.fire.surrogate_model` NumPy MLP and model card.
- Corpus manifest and training artifacts.
- Evaluation harness with held-out synthetic and Dogrib OOD reporting.
- Tests for corpus determinism, training, evaluation, and split integrity.

## Recommendation

Do not continue surrogate work on this architecture. A future attempt would need:

- a duration or sequence input;
- a larger, more diverse synthetic corpus;
- held-out distribution shifts before Dogrib;
- an integration gate tied to footprint and latency, not area alone.

P159 closes as a no-go. A future surrogate phase must be a new pre-registration.

## Pull request

PR: to be opened.
