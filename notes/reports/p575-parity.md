# P57.5 carbon parity, mass balance, and replay

Date: 2026-10-25
Phase: P57
Task: P57.5
Related: `notes/design/ws4-carbon.md`, `docs/reference/carbon.rst`

## 1. Question

Does the WS4 carbon path reproduce the WS3 CBM path on the same model, and are its
outputs deterministic and internally consistent?

## 2. WS3/WS4 parity method

The comparison used the WS3 `tsa24_clipped` fixture, which is small enough to inspect and
already has a known-good `ForestModel.to_cbm_sit()` export.

1. Build the WS3 model, import its sections, and call `to_cbm_sit()`.
2. Convert the resulting SIT tables into a WS4 carbon package and compiled dataset:
   - one WS4 track per WS3 classifier set (the five theme values plus species);
   - the initial inventory from `sit_inventory`;
   - the yield table from the `v0..v100` columns on the 10-year age grid;
   - the transition rules from `sit_transitions`;
   - each track's last disturbance from its inventory row;
   - a package manifest with the same CBM defaults hash.
3. Run both paths through `libcbm==2.10.2` for 20 timesteps with no scheduled events.
4. Compare every numeric pool and flux column on `(timestep, identifier)`.

The WS3 run used its own SIT tables and mapping configuration. The WS4 run used
`build_sit_tables` and `run_libcbm_tables` with the package mapping.

## 3. Result

- WS3 inventory rows: 25; WS4 inventory rows: 25.
- WS3 yield rows: 24; WS4 yield rows: 24.
- Pool comparison: **exact** (`max_abs = 0.0`, `max_rel = 0.0`).
- Flux comparison: **exact** (`max_abs = 0.0`, `max_rel = 0.0`).
- Initial totals matched exactly:
  - `SoftwoodMerch`: 36,160.8059 tC
  - `HardwoodMerch`: 97.4853 tC
  - `AboveGroundSlowSoil`: 33,866.2300 tC
  - `Products`: 7,355.0559 tC

The conversion first mismatched because every WS4 track was given `fire` as its last
disturbance; preserving each inventory row's last disturbance made the two paths
identical. That is a conversion-fixture defect, not a WS4 defect.

## 4. Mass balance and replay

- **Account-to-pool reconciliation:** the `carbon.biomass.total`, `carbon.dom.total`,
  `carbon.ecosystem.total`, `carbon.products.total`, and `carbon.stock.change` accounts
  match the pool table.
- **Non-negativity:** every reported pool is finite and non-negative on the TSA24 real
  package run.
- **Replay:** two runs of the same TSA24 package, mini dataset, and schedule produced
  byte-identical `carbon_accounts.csv`, `carbon_pools.csv`, `carbon_flux.csv`, and
  `carbon_manifest.json`.
- **Units:** the writer distinguishes mass (tC) from density (tC/ha) and records the choice
  in the carbon manifest.

A simplified flux-closure check (`delta(total) = NPP - decay - disturbance emissions`)
leaves a residual of about 2.5 tC/year on the TSA24 run. CBM's flux indicators include
transfers between pools that the simplified ledger does not name, so this residual is
recorded as a diagnostic, not used as a pass/fail gate. The gated checks are the account
reconciliation, non-negativity, and exact WS3/WS4 table parity.

## 5. Reproduce

The generic comparison is tracked as `scripts/carbon_parity.py`:

```bash
python scripts/carbon_parity.py --left out/ws3 --right out/ws4 --out parity.json
```

It compares `carbon_pools.csv` and `carbon_flux.csv` on `(timestep, identifier)` and exits
nonzero when a numeric column is outside the tolerance.

The WS3-to-WS4 conversion is a local parity adapter. A durable shared fixture belongs to
P57.8, where the TSA24 and MKRF production runs will use the same package and dataset
contract end to end.

## 6. Caveats

- The WS3 fixture is the clipped TSA24 model, not the full TSA24 package.
- The parity run has no scheduled events; disturbance-event parity is covered by the SIT
  compiler tests and the real TSA24 mini run.
- The simplified flux closure is not a physical CBM mass balance; the report names the
  residual rather than claiming zero.
