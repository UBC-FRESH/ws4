# Combined optimizer/process risk verification bundle

Status: implemented (P220)
Phase: P220 (#1276)
Date: 2026-11-15
Related: `notes/design/ws4-process-risk-validation.md`

## 1. Purpose

The optimizer writes an account-overlay risk verification summary; P218 writes a process
train/validation gap. P220 bundles both into one JSON artifact for review.

## 2. Contract

`write_risk_verification_bundle` writes `risk_verification_bundle.json`:

```json
{
  "schema_version": "ws4.risk-verification-bundle.v1",
  "optimizer": { "...": "..." },
  "process": { "...": "..." }
}
```

The optimizer mapping is copied unchanged. The process block is the P218 summary, including the
generalization gap.

## 3. Evidence

- Two-scenario process validation bundled with a synthetic optimizer summary.
- The written JSON round-trips to the returned payload.
- The process gap is preserved exactly.
- Empty optimizer summaries and invalid process reports fail loudly.

## 4. Limits

- The bundle does not run the optimizer or process engine.
- The two risk summaries remain separate; no combined decision rule is introduced.
- No calibration or observed-perimeter validation.
