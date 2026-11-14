# Process-ensemble fire-regime artifact

Status: implemented (P213)
Phase: P213 (#1241)
Date: 2026-11-14
Related: `notes/design/ws4-process-fire-regime.md`

## 1. Purpose

P212 made per-scenario fire-regime summaries available in memory. P213 writes them into the
process ensemble artifact directory, so callers do not recompute or reimplement the JSON shape.

## 2. Contract

`ProcessEnsembleResult.write_fire_regime` writes `fire_regime.json`:

```json
{
  "schema_version": "ws4.process-fire-regime.v1",
  "scenarios": {
    "scenario-id": { "schema_version": "ws4.fire-regime-risk.v1", "...": "..." }
  }
}
```

Scenarios are sorted by id. The existing process artifacts are unchanged.

## 3. Evidence

`tests/test_ecosystem_ensemble.py`:

- writes the artifact for a real two-scenario ensemble;
- checks the top-level schema and scenario keys;
- checks each scenario's burned area and fire count against the in-memory summary;
- checks a zero-fire scenario has count 0 and a null FRI.

## 4. Limits

- The artifact is distributional, not an observed-perimeter comparison.
- No calibration.
- No optimizer risk integration.
