# P57.9 GCBM results reader and comparison lane

Date: 2026-10-26
Phase: P57
Task: P57.9
Related: `notes/design/ws4-carbon.md`, `docs/reference/carbon.rst`

## 1. What was added

- `ws4/carbon/gcbm.py` reads a raw GCBM results database (`gcbm_output.db`) without
  FLINT, Wine, or the GCBM executable.
- It joins `Pools` to `LocationDimension`, `DateDimension`, and `PoolDimension`; reads
  `Fluxes`, `ClassifierSetDimension`, and the location dimension.
- `gcbm_accounts` maps the GCBM pools to the WS4 `carbon.*` account names
  (`biomass`, `dom`, `ecosystem`, `products`, CO2e, and stock change).
- `write_gcbm_results` writes `gcbm_pools.csv`, `gcbm_fluxes.csv`, `gcbm_accounts.csv`,
  and `gcbm_manifest.json`.
- `compare_gcbm_to_carbon` compares a GCBM account table with a WS4
  `carbon_accounts.csv` by offset and account.
- `ws4 gcbm --results ... --out ... [--compare-carbon ...]` exposes the reader and the
  comparison.

## 2. Real GCBM run

The maintainer supplied the GCBM software and training ZIP. It was downloaded
(866 MB) and extracted. The bundled Standalone Template was run under **Wine 9.0** with
`moja.cli.exe`:

- GCBM processed **11,347 land units**.
- Runtime: **85 seconds**.
- Raw output: `gcbm_project/output/gcbm_output.db`, plus the spatial indicator
  directories.

The PROJ database was not on the Wine path, so GDAL emitted `proj.db` warnings. They did
not stop the run; the tabular results are complete.

## 3. Reader result on the real output

`ws4 gcbm --results gcbm_output.db --out ...` produced:

- **120 locations**
- **12 steps** (initial + 11 annual years)
- Ecosystem carbon start: **67,388.5 tC**
- Ecosystem carbon end: **52,880.9 tC**

The output contains `gcbm_pools.csv`, `gcbm_fluxes.csv`, `gcbm_accounts.csv`, and
`gcbm_manifest.json`, so the GCBM tabular results can be inspected with the same account
names as the WS4 carbon path.

## 4. Comparison status

The comparator is implemented and tested on a synthetic GCBM-shaped database and a
synthetic WS4 account table. A **same-landscape** GCBM-vs-WS4 comparison is not claimed
here:

- The bundled GCBM project is the national training sample, not TSA24 or MKRF.
- A same-landscape comparison needs the FEMIC GCBM walltowall export (P115.4), which
  writes the TSA24/MKRF inventory, yield table, disturbances, and AIDB reference in the
  GCBM project shape.
- The GCBM spatial GeoTIFFs are not yet mapped to WS4 blocks; the current reader is
  tabular. The spatial mapping belongs with the P115.4 export and a follow-up comparison.

This is a deliberate boundary: the reader and comparison surface are ready; the
same-footprint data is the remaining prerequisite.

## 5. Limits

- The GCBM run used the Windows GCBM build under Wine. The PROJ path issue is an
  environment caveat, not a model result.
- The reader assumes the GCBM 2.5.x results schema (`Pools`, `Fluxes`,
  `LocationDimension`, `DateDimension`, `PoolDimension`, `ModuleInfoDimension`,
  `DisturbanceTypeDimension`, `ClassifierSetDimension`).
- GCBM flux indicators are retained in `gcbm_fluxes.csv`; the account layer currently
  uses pools plus stock change, not a full flux closure.
