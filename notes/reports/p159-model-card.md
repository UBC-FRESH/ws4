# P159 fire surrogate model card

Date: 2026-11-10
Phase: P159 (Fire surrogate feasibility)
Task: P159.2 (#967)
Model: `ws4.fire-surrogate.mlp.v1`
Status: trained; evaluation is P159.3

## Purpose

A compact CPU surrogate that predicts a burned-cell mask from fuel, terrain, weather, and
ignition-relative features. It is a screening candidate, not a replacement for the P156 FBP
growth kernel and not observed-fire validation.

## Training data

- Generator: `ws4.fire.surrogate`, kernel version `ws4.fire.growth.v1`.
- 120 synthetic samples, 32 × 32 cells, 100 m, 60-minute burns.
- Deterministic split: 96 train, 24 validation, by sample index.
- Seed: 159.
- Fuel order: the 17 FBP types plus non-fuel.
- Dogrib was not used for training or model selection.

The full training record is `notes/reports/p159-model/training.json`.

## Architecture

- Per-cell input: 29 features
  - 17 FBP fuel one-hots plus non-fuel;
  - slope, aspect sin/cos;
  - wind speed, wind-direction sin/cos;
  - FFMC, BUI;
  - normalized distance from ignition;
  - bearing sin/cos.
- One hidden layer: 32 tanh units.
- One logistic output.
- 993 parameters.
- Prediction is zeroed on non-fuel cells.

## Training

- Optimizer: full-batch Adam.
- Learning rate: 0.01.
- Epochs: 200.
- Weight initialisation seed: 159.
- Weighted binary cross-entropy for class imbalance.

## Training result

| Metric | Value |
| --- | ---: |
| Final training loss | 0.2063 |
| Final validation loss | 0.6151 |
| Validation mask IoU, mean | 0.374 |
| Validation mask IoU, min | 0.000 |
| Validation mask IoU, max | 0.859 |

The validation loss is substantially higher than the training loss. The model is overfitting
the 96-sample training set; P159.3 must judge it on held-out synthetic samples and Dogrib
out-of-distribution. A no-go is a valid outcome.

## Artifacts

- `notes/reports/p159-model/model.json`
- `notes/reports/p159-model/weights.npz`
- `notes/reports/p159-model/training.json`
- `scripts/train_fire_surrogate.py`

## Limitations

- One hidden layer and 29 per-cell features; no spatial context beyond ignition distance and
  bearing.
- Trained on synthetic 32 × 32, 60-minute burns only.
- Binary mask target, not a calibrated arrival-time surface.
- No spotting, suppression, or observed-fire calibration.
- The model is not integrated into any web or UI path.

## Next

P159.3 evaluates held-out synthetic samples and Dogrib as out-of-distribution evidence with
the P157 metrics. P159.4 applies the integration gate.
