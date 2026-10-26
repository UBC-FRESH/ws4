# Phase close-out report: P61 Carbon and libcbm in the web UI

Phase: P61, Carbon and libcbm in the web UI
Parent issue: #430
Pull request: #436
Status: queued for approval. Not merged.
Date: 2026-10-26

## Recommendation

1. Squash-merge the P61 pull request and delete `feature/p61-carbon-ui`.
2. Close tasks #431/#432/#433 and parent #430.
3. Accept the limits below; no carbon science or libcbm execution was added.

Settings changes: none.

## Acceptance

| Criterion | Evidence | Status |
| --- | --- | --- |
| Carbon run shows package, libcbm, units, defaults, hashes. | TSA24 standalone run: `femic-carbon-24-84dbc9cf549d`, libcbm `2.10.2`, tC, defaults `1.2.9300.391`, fingerprint/schedule hash; MKRF run also read. | Met |
| Carbon accounts render over time and match the CSV. | TSA24 and MKRF API account series match `carbon_accounts.csv` at every point (`max_abs = 0.0`); browser chart selected `carbon.ecosystem.total`. | Met |
| Pool composition is aggregated by timestep from the real pool table. | TSA24 12 timesteps; biomass/DOM-soil/products groups from `carbon_pools.csv`; browser shows three bars. | Met |
| A run with `carbon_ledger.json` shows its status. | TSA24 optimizer run: `Ledger: block-level · 5 years · /tmp/opencode/tsa24_carbon_package_ds`. | Met |
| A GCBM comparison renders when present. | API/table branch covered by `test_the_carbon_api_aggregates_real_artifacts_and_carbon_only_runs`; no real `gcbm_compare.csv` exists in the workspace. | Partial |
| c5/non-carbon run shows an explicit unavailable state. | c5 run: `this run has no carbon artifacts`, selector disabled. | Met |
| Dashboard green. | Green at the report commit. | Met |

## Real-data evidence

TSA24 standalone carbon run:

- 12 carbon accounts, 12 timesteps, six artifacts;
- `carbon_pools.csv` and `carbon_flux.csv` read and aggregated by timestep;
- API accounts match the CSV exactly.

TSA24 carbon-aware optimizer run:

- 12 `carbon.*` accounts in `account_values.csv`;
- `carbon_ledger.json` shows block-level, 5 years;
- no standalone manifest/pools, so the panel shows ledger provenance and accounts only.

MKRF standalone carbon run:

- `mkrf-carbon`, 12 accounts, six artifacts;
- API accounts match the CSV exactly.

Browser: `scripts/check_carbon_browser.py` exits 0 for `carbon-full` and `carbon-opt`.
The first selects the account (12 options), draws a polyline, shows three composition bars, six
artifact links, and the package metadata; the second shows the ledger and no pools.

## Deviations and limits

- **GCBM real comparison not evidenced.** No real `gcbm_compare.csv` exists in the workspace; the
  reader/table branch is covered by the API fixture. The P58.9 GCBM sample is a different
  landscape, so a same-footprint comparison still needs the FEMIC walltowall export.
- **Carbon-only runs have no schedule or map.** The panel is usable and periods come from carbon
  accounts; other tabs degrade to their existing empty/error states. This is expected, not a
  carbon failure.
- **Aggregation, not recomputation.** Pools and fluxes are summed by timestep over libcbm
  identifiers; the raw files remain the authority and are downloadable.
- **No browser libcbm execution.** The UI is read-only.
