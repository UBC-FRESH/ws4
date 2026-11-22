# P164.8 benchmark and reproducibility package

Status: technical report

This report is the reproducible evidence package for the calibrated TSA24 fire regime. It records
what was run, which inputs and seeds were used, what is tracked, what remains local, and where the
results are.

## Scope

The package covers:

- the 24-tile regional suppression calibration;
- the independent transfer and hierarchical transfer tests;
- the five-seed full-layer risk ensemble;
- the five-year full-layer estate case;
- the sharded full-estate optimizer;
- the reusable estate fire API.

It does not claim an operational fire forecast, a global optimum, or validated suppression
resource deployment.

## Environment

- code commit: `4e63ac46`
- Python: recorded in `work/fire_regime/results/reproducibility-manifest.json`
- NumPy and pandas versions: recorded in the same manifest
- host: Linux workstation with 36-worker runs
- data and logs: `work/fire_regime/data/` and `work/fire_regime/logs/`, Git-ignored
- large caches: local to the work host, not redistributed in Git

## Inputs and provenance

| Input | Source | Handling |
| --- | --- | --- |
| VRI vegetation, crown, species | BC VRI WFS | public; licence check before redistribution |
| Water and non-vegetated polygons | VRI non-vegetated attributes | public; licence check |
| Terrain | SRTM 1 arc-second | public |
| Historical fire perimeters | BC Wildfire perimeter service | public; licence check |
| Historical incidents and durations | BC Wildfire incident service | public; licence check |
| Weather | Open-Meteo archive | public; attribution required |
| Compiled TSA24 inventory | public compiled artifact used by the project | project data contract |

The layer cache has 133 aligned 30 km tiles and 1,111,565 support cells. The cache is 90,375,672
bytes. The DEM cache currently has 34 `.hgt` files and 881,769,668 bytes. The manifest records a
SHA-256 hash for every layer tile.

## Seeded runs

| Run | Seed(s) | Result |
| --- | --- | --- |
| Potential sample | `20261121` | 720 fires, 30 per tile |
| Regional calibration | per tile, recorded in `region-calibration.json` | 23 fitted tiles; in-sample |
| Risk ensemble | `20261122`–`20261126` | 5 seeds |
| Estate case | `20261122` | 5-year schedule |
| Full-estate optimizer | per shard, derived from `20261122` | 112 tiles, 179 events |
| Transfer validation | deterministic tile seeds | fixed `t13`–`t23` holdout |
| Hierarchical validation | deterministic tile seeds | ridge selection by training-only CV |

## Results

| Evidence | Value |
| --- | --- |
| Support coverage | 1,111,565 / 1,111,565 cells |
| Forest support cells | 1,012,231 |
| Regional calibration median | 23.8 ha vs 23.0 historical |
| Regional calibration p90 | 361.5 ha vs 490.2 historical |
| Regional calibration maximum | 20,770.4 ha vs 25,114.8 historical |
| Five-seed burned-area median | 7,889.6 ha |
| Five-seed CVaR95 volume loss | 1.04 million m3 |
| Five-year full-layer burned area | 8,374.1 ha |
| Five-year full-layer harvest | 156,358.8 ha |
| Five-year full-layer volume | 821.6 million m3 |
| Full-estate optimizer | 20,775.6 ha harvested; 859.98 million m3; 655.5 s |
| Independent transfer, in-sample score | 1.495 |
| Independent transfer, global score | 4.799 |
| Independent transfer, potential analogue | 6.121 |
| Hierarchical ridge score | 6.540 |
| Complete-pool mean score | 5.182 |

All scores are relative diagnostics, not the pre-registered P164.8 gates.

## Commands

Run from the repository root on the work host. The analysis scripts are local analysis code under
`work/fire_regime/`; they are not part of the installed package contract.

```bash
# API tests and the reusable handoff
python -m pytest tests/test_estate_fire.py tests/test_ecosystem_growth_fire.py \
  tests/test_ecosystem_dataset.py -q --no-cov

# Full layer cache (local, resumable)
PYTHONPATH=. python work/fire_regime/build_full_layers.py

# Five-seed risk ensemble
PYTHONPATH=. python work/fire_regime/risk_ensemble.py

# Bounded regional optimizer
PYTHONPATH=. python work/fire_regime/optimizer_regional.py

# Sharded full-estate optimizer
PYTHONPATH=. python work/fire_regime/full_estate_optimizer.py
```

The API path used by an estate workflow:

```python
from pathlib import Path
from ws4.ecosystem import build_estate_fire_source

source, grid, regions = build_estate_fire_source(
    support,
    layer_manifest=Path("layers/manifest.json"),
    calibration=Path("region-calibration.json"),
    tiles_manifest=Path("tiles.json"),
    origin_x=0.0,
    origin_y=0.0,
    cell_size_m=250.0,
    ignitions_by_year={0: [ignition]},
    growth=growth_config,
    seed=20261122,
)
```

## Artifact manifest

`work/fire_regime/results/reproducibility-manifest.json` records:

- commit, Python, NumPy, and pandas versions;
- seeds;
- SHA-256 and byte size for tracked result files;
- SHA-256 and byte size for every layer tile;
- DEM cache count and size;
- which results are Git-tracked.

## Known failures and boundaries

- The global P164.8 gate is a no-go.
- The regional map is in-sample; the independent transfer test is negative.
- Hierarchical ridge did not improve transfer with the current covariates.
- The upper tail remains underproduced.
- The full-estate optimizer is sharded with local harvest targets; it is not a global optimum.
- 21 of 133 tiles had no local eligible CC block in the five-year window.
- The layer cache is 100% support coverage, but the suppression map has 24 fitted regions and a
  median default outside them.
- The risk ensemble has five seeds; CVaR95 is the worst observed seed.
- VRI, SRTM, weather, and perimeter licences must be checked before redistributing derived data.

## Archive checklist

- [ ] Confirm redistribution licences for VRI, SRTM, weather, and perimeter products.
- [ ] Archive the layer cache and manifest with a DOI (Zenodo or institutional archive).
- [ ] Archive the calibrated region map and transfer results with the code release.
- [ ] Add a `CITATION.cff` and an environment lock or container.
- [ ] Add a clean-machine reproduction test for the API and result summaries.
- [ ] Keep large rasters out of Git; keep only manifests, code, and compact result JSON/CSV.
- [ ] Record the exact source-data versions and download dates.
- [ ] Publish the known-failure table with the release.

## Evidence map

- `notes/reports/p164-8-region-calibration.md`
- `notes/reports/p164-8-transfer-validation.md`
- `notes/reports/p164-8-hierarchical-validation.md`
- `notes/reports/p164-8-estate-handoff.md`
- `notes/reports/tsa24-calibration-index.md`
- `work/fire_regime/results/reproducibility-manifest.json`
