# P58 follow-on: fertilization runtime wiring

Date: 2026-10-26
Phase: P58 (follow-on)
Branch: `feature/p58-fertilization-runtime`

## 1. What this change delivers

The FEMIC public TIPSY fertilization artifacts are now usable in a WS4 carbon run
and in the optimizer ledger.

- **Curve mode.** A fertilization YAML may list materialized curve applications
  (`treatment`, `source_track`, optional `target_track`, `curve`). WS4 adds the target
  track and its fertilized yield/curve rows in memory, adds a source-to-target transition,
  and sets the transition reset age to `-1` so the stand keeps its age.
- **Multiplier fallback.** Without applications, an `f1`/`f2`/`f3` event applies the
  configured growth multiplier for the response window.
- **Emissions.** `fertilization.area_ha`, `dose_kg_n`, `co2_t`, `ch4_t`, `n2o_t`, and
  `co2e_t` are merged into `carbon_accounts.csv`, the run report, and
  `carbon_manifest.json`.
- **Optimizer.** `ws4 optimize --carbon-package <package> --carbon-fertilization <yaml>`
  passes the same configuration to the block-level ledger, so optimization sees both the
  growth delta and the emissions.

The FEMIC side is unchanged: `femic carbon fertilization-curve` writes the curve and its
provenance sidecar, and `femic carbon fertilization-audit` writes the standalone emissions
accounts.

## 2. Evidence

- 35 targeted carbon/SIT/engine/ledger/report/parity/GCBM tests pass after the change
  (includes the new `tests/test_carbon_fertilization.py`).
- `ruff check`, `ruff format --check`, and `mypy --strict` pass on the changed modules.
- Sphinx `-W` documentation build passes.
- Real TSA24 subset (`/tmp/opencode/tsa24_subset_2401005`) and v2 package:
  - a public TIPSY curve for track
    `AU(2401005)+IFM(unmanaged)+ORIGIN(natural)+SILV_STATE(baseline)+RETENTION(0)+treatment()`
    was materialized with `SW`, site index 20, response age 40;
  - the compiled SIT transitions show `f1` with `reset_age=-1` to the `+F1` target
    track;
  - the full 14-step curve run writes `fertilization.co2e_t = 215.007` for 22.3 ha and
    records `"mode": "curve"` plus the application in the manifest;
  - the block ledger for block 424 (17.0 ha) reports a `+1.0466 tC` ecosystem delta at
    offset 14 and `93.1474 tCO2e` of fertilization emissions.

## 3. Boundary

SIT events target a classifier set and area, not a block id. When several blocks share a
source track, a full-schedule event can be distributed across that track's stands rather
than the exact scheduled block. The block-level ledger runs one block at a time and does
not have this ambiguity; it is the exact path used by the optimizer. A full run keeps the
existing SIT behavior and should be read as a track-level allocation for events on
multi-block tracks.

## 4. Verification commands

```bash
pytest tests/test_carbon_fertilization.py tests/test_carbon_sit.py \
  tests/test_carbon_ledger.py tests/test_carbon_engine.py \
  tests/test_carbon_report.py tests/test_carbon_parity.py tests/test_carbon_gcbm.py

ruff check ws4/carbon tests/test_carbon_fertilization.py
mypy ws4/carbon ws4/cli.py ws4/opt/engine.py
python -m sphinx -b html -W docs docs/_build/html

ws4 carbon --dataset <dataset> --package <package> --schedule <schedule> \
  --out <out> --fertilization-config <fertilization.yaml>
ws4 optimize --dataset <dataset> --targets <targets> \
  --carbon-package <package> --carbon-fertilization <fertilization.yaml> --out <out>
```
