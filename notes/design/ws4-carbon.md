# WS4 Carbon Accounting and Carbon-Aware Planning

Status: draft
Phase: P51
Date: 2026-10-25
Related: `ROADMAP.md` (Phase 51), `notes/design/ws4-architecture.md`,
`notes/design/ws4-optimization-stack.md`, `notes/adr/0005`, `notes/adr/0012`

## 1. Context

WS4 is a spatially explicit forest estate model. Its compiled dataset is the runtime contract, and
the simulator and optimizer read only that dataset. Carbon is currently out of scope in
`notes/design/ws4-scope.md`.

The lab already has a working CBM linkage in WS3: `ForestModel.to_cbm_sit()` compiles the lab's
model vocabulary into the CBM Standard Import Tool (SIT) format, and the example helpers run the
open-source `libcbm` engine. WS3 also demonstrates a carbon-curve approximation (the "Neilson hack")
for using CBM output inside an estate model.

P51 turns that precedent into a WS4 capability without making the compiled dataset depend on a
particular carbon engine.

## 2. Decision

Use `libcbm` as the first in-process carbon engine. FEMIC produces a versioned, static carbon input
package. WS4 joins that package to the compiled dataset, adds schedule-dependent events and
treatment-dependent transitions, runs the engine, and reports carbon as `carbon.*` accounts.

GCBM/FLINT is not embedded. It remains a separate spatially explicit runtime with a file-based
export/import bridge. CBM4 is a future engine behind the same driver boundary.

## 3. Why this boundary

- **The compiled dataset stays the contract.** Carbon does not add columns to the matrix. It reads
  the dataset plus a package plus a schedule.
- **The science crosswalks live with the producer.** FEMIC owns species, eco-boundary, land-class,
  and disturbance mappings, and the provenance of the inventory and curves.
- **The engine is replaceable.** libcbm now; CBM4 later; GCBM as a separate spatial lane.
- **Carbon is auditable.** The generated SIT tables, the package, the schedule, the engine version,
  and the `cbm_defaults` hash are all recorded.

## 4. Data flow

```text
FEMIC carbon package (static)
        +
WS4 compiled dataset        +  schedule
        \                       /
         \                     /
          v                   v
     +--------------------------------+
     | ws4/carbon/sit.py              |
     | classifiers, inventory, yield, |
     | events, transitions, audit     |
     +--------------------------------+
                    |
                    v
     +--------------------------------+
     | ws4/carbon/libcbm.py           |
     | driver protocol, version/hash  |
     +--------------------------------+
                    |
                    v
   carbon_pools / carbon_flux / carbon_accounts / manifest
```

The package is described in the FEMIC carbon-domain contract. WS4 consumes it through
`ws4/carbon/package.py`; it must not re-implement the crosswalks.

## 5. Package join

The join key is the **track name**, not the dataset-local `track_id`. Track ids are stable within a
compiled dataset but not across rebuilds; names carry the state vocabulary and are the durable
semantic key. The package's `track_carbon_map.csv` maps `track_name` to the classifier set, leading
species, shares, land class, default disturbance, eco boundary, and the feature label that carries
merchantable volume.

An unmatched track is a hard failure by default. A maintainer may pass an explicit override, and
the override is recorded in the run manifest.

## 6. SIT compilation

`ws4/carbon/sit.py` builds:

- **classifiers** from the package track map and species classifier;
- **inventory** from `fragments` and the package defaults;
- **yield** by sampling the dataset's merchantable volume curve on the package age grid;
- **events** from the schedule, with `time_step = offset + 1` and area taken from the same fragment
  portions the simulator treats;
- **transitions** from `treatments` and the package disturbance map.

The compiler asserts area conservation and rejects unsupported retention with a clear message.
Every generated table can be written to `carbon_sit/` for audit.

## 7. Outputs and accounts

Files:

- `carbon_pools.csv`, `carbon_pools_long.csv`
- `carbon_flux.csv`, `carbon_flux_long.csv`
- `carbon_accounts.csv`
- `carbon_manifest.json`
- optional `carbon_sit/`

Account names use the `carbon.` prefix:

- `carbon.biomass.total`
- `carbon.dom.total`
- `carbon.ecosystem.total`
- `carbon.products.total`
- `carbon.flux.npp`
- `carbon.flux.decay`
- `carbon.flux.disturbance`
- `carbon.flux.net`
- `carbon.co2e.ecosystem.total`
- `carbon.co2e.flux.net`
- `carbon.stock.change`

Every reported value names its unit. Mass is tonnes of carbon (tC); density is tC/ha; CO2e uses
the 44/12 conversion and names the gas basis.

## 8. Optimizer integration

CBM is stand-level and area-additive. That makes a **block-level carbon ledger** viable:

1. Precompute each block's carbon trajectory for the no-treatment case and for each offered
   treatment.
2. Evaluate a schedule by summing the block trajectories.
3. On a local move, recompute only the blocks the move touches.
4. Verify the final schedule with a full-engine run.

If the ledger cannot meet the search budget, a precomputed carbon response curve may be used for
screening. A surrogate result is labeled as such and never reported as the exact carbon outcome.

Carbon targets enter the existing weighted goal programming as `carbon.*` accounts. Units,
normalization, and period semantics are explicit; a carbon target must not silently dominate the
objective because of a scale mismatch.

## 9. GCBM bridge

The FEMIC GCBM exporter produces a walltowall project and spatial layers. WS4 may ingest the
compiled GCBM results for a spatial comparison. This is a separate lane:

- GCBM is not a WS4 runtime dependency.
- The tested GCBM version and output schema are pinned in the comparison report.
- Differences from resolution, boundaries, and disturbance layers are explained, not hidden.

## 10. Validation

- **Contract tests:** package load, join, units, and failure modes.
- **SIT tests:** every generated table parses in libcbm; area is conserved.
- **Parity:** WS4 vs WS3 on the TSA24 fixture, initial pools and a no-disturbance trajectory.
- **Mass balance:** pools, fluxes, and products reconcile within a stated tolerance.
- **Replay:** the same dataset, schedule, package, and engine version produce identical outputs.
- **Performance:** the ledger's speedup is measured on a representative instance.
- **Optimizer:** a carbon target changes a schedule; the winning schedule is verified exactly.

## 11. Risks

- Track names can drift; the join must fail loudly.
- A coarse species crosswalk biases stocks; it is documented as a fallback.
- Retention and partial harvest may not be representable in v1; reject them explicitly.
- libcbm and `cbm_defaults` versions must be pinned and hashed.
- The ledger can grow without bound; define a cache policy.
- GCBM output schemas and spatial alignment can dominate a comparison.

## 12. Open questions

1. Which retention cases must the first version support on MKRF?
2. Does the first optimizer integration need exact carbon on every move, or is the ledger plus a
   final exact run sufficient for the first acceptance?
3. Which GCBM version and output tables are the comparison baseline?
4. When CBM4 is released, does it expose a SIT-compatible package or a different input contract?

## 13. Task map

| Task | Deliverable |
| --- | --- |
| P51.1 | Package loader and contract tests |
| P51.2 | SIT compiler and schedule events |
| P51.3 | libcbm driver and `ws4 carbon` |
| P51.4 | Carbon accounts, reports, provenance |
| P51.5 | Parity, mass balance, replay |
| P51.6 | Block-level carbon ledger |
| P51.7 | Carbon targets in the optimizer |
| P51.8 | TSA24 and MKRF validation |
| P51.9 | GCBM output consumption and comparison |
| P51.10 | Documentation, release, closeout |
