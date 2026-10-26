# Structure habitat index pilot

This directory exercises the **published Coops et al. (2016) structure habitat
index** and its coverage behaviour. The four blocks are a synthetic fixture with
the exact first-return metrics the index requires; they are **not** field or ALS
observations. The real TFL 6 FEMIC bundle is used only to show which metrics are
missing.

## Published definition

The index has three equal components; the paper publishes a three-band class
composite, not a weighted scalar:

| Component | Required metric | Class breaks |
| --- | --- | --- |
| Height | P95 of first returns, `height_p95_m` | 10 m, 20 m |
| Cover | first returns above 1.37 m, `cover_gt_1_37_pct` | 33%, 66% |
| Complexity | SD of first-return heights above 1.37 m, `complexity_sd_gt_1_37_m` | 3 m, 5 m |

A value exactly on a break is assigned to the lower class. The stand table gains
`height_class`, `cover_class`, `complexity_class`, a 0-26 `class_code`, and a
label such as `H1-C2-K0`.

Source: Coops et al. 2016, *A forest structure habitat index based on airborne
laser scanning data*, Ecological Indicators 67:346-357,
doi:10.1016/j.ecolind.2016.02.057.

## Files

| File | Purpose |
| --- | --- |
| `structure_metrics.csv` | Synthetic exact-metric input for four blocks. |
| `structure_habitat_stand.csv` | Computed component values, classes, and codes. |
| `structure_habitat_metadata.json` | Index version, thresholds, citation, and source version. |
| `dhi_values.csv` / `dhi_metadata.json` | DHI pilot values for the same block ids. |
| `dhi_comparison.csv` | Exploratory component-versus-DHI rank comparison. |
| `tfl6_coverage.json` | Real TFL 6 FEMIC canopy summary coverage check. |
| `targets.yaml` | Empty target file for the report smoke. |

## Commands

```bash
ws4 shi ingest \
  --metrics examples/structure_habitat_pilot/structure_metrics.csv \
  --output examples/structure_habitat_pilot/structure_habitat_stand.csv \
  --metadata examples/structure_habitat_pilot/structure_habitat_metadata.json \
  --source-id coops-2016-fixture \
  --source-version "synthetic-fixture-v1"

ws4 shi compare \
  --structure examples/structure_habitat_pilot/structure_habitat_stand.csv \
  --dhi-values examples/structure_habitat_pilot/dhi_values.csv \
  --output examples/structure_habitat_pilot/dhi_comparison.csv

ws4 shi diagnose \
  --canopy-structure /path/to/femic/bundle/products/canopy__05__canopy_structure.json \
  --output examples/structure_habitat_pilot/tfl6_coverage.json

# A ws4 lidar canopy fragment/block mapping takes the same diagnostic:
ws4 shi diagnose --metrics build/canopy_mapping/canopy_fragments.csv

ws4 build --xml examples/dhi_pilot/recipe.xml \
  --fragments examples/dhi_pilot/fragments.csv --out build/shi_pilot

ws4 simulate --dataset build/shi_pilot \
  --schedule examples/dhi_pilot/schedule_harvest.csv --years 10 \
  --structure-values examples/structure_habitat_pilot/structure_habitat_stand.csv \
  --structure-metadata examples/structure_habitat_pilot/structure_habitat_metadata.json \
  --out runs/shi_harvest

ws4 report --run runs/shi_harvest \
  --targets examples/structure_habitat_pilot/targets.yaml
```

The baseline keeps 40 ha and component means of 20.75 m height, 56.25% cover,
and 5.0 m complexity. The harvest schedule treats block 1 (low class) and block
3 (high class); the surviving 20 ha has means of 25.0 m, 67.5%, and 6.0 m. The
run writes `structure_habitat_values.csv`, `structure_habitat_landscape.csv`,
and `structure_habitat_metadata.json`; the report adds
`report_structure_habitat.csv`.

## Real TFL 6 gap

The real FEMIC TFL 6 bundle exposes CHM-derived P95 and cover ≥2 m, not the
published first-return P95, 1.37 m cover, or first-return height SD. The
diagnostic therefore reports:

- `index_computable: false`
- missing: all three required first-return metrics
- proxies: `chm_p95` and `chm_cover_ge_2`, explicitly not substituted

This is the intended failure mode: report the gap instead of inventing a new
index from different metrics.

## Caveats

- The four-block metrics are synthetic test values, not ALS observations.
- The DHI comparison is exploratory, has n=4, and is not a significance test or
  a management finding. It happens to show negative rank agreement with DHI
  cumulative in this fixture; that is recorded, not explained away.
- The index is a structural descriptor, not a species observation or a habitat
  suitability model. The paper has no weights to tune.
- Do not read a block class as a conservation priority.
