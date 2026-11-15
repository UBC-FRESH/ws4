# Optimizer risk verification bundle

Status: implemented (P221)
Phase: P221 (#1281)
Date: 2026-11-15
Related: `notes/design/ws4-risk-bundle.md`

## 1. Purpose

P220 bundles an optimizer summary and process validation in memory. P221 reads the optimizer's
actual `risk_verification.json` from its output directory and writes the bundle there.

## 2. Contract

`bundle_existing_risk_verification(out_dir, process=...)`:

- requires `out_dir/risk_verification.json`;
- requires `search_objective`, `full_objective`, and `gap`;
- writes `risk_verification_bundle.json` in the same directory.

Missing, malformed, or incomplete optimizer verification fails loudly.

## 3. Evidence

- A synthetic optimizer verification file is bundled with a real two-scenario process validation.
- The written bundle equals the returned payload.
- Optimizer values and process gap are preserved.
- A missing file fails.

## 4. Limits

- The optimizer run is still separate from the process run.
- No combined decision rule.
- No calibration or observed-perimeter validation.
