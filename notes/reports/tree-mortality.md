# Tree-mortality validation

Date: 2026-11-16
Branch: `fire-tree-mortality`
Artifact: `notes/reports/tree-mortality.json`

## Model

Generic FOFEM crown-scorch equation, using species bark-thickness coefficients from the FTM
species table:

`Pm = 1 / (1 + exp(-1.941 - 6.316 * (1 - exp(-BT)) + 0.000535 * CS^2))`

- `BT` is single bark thickness in inches, `coefficient * DBH_in`.
- `CS` is crown volume scorched in percent.
- DBH is restricted to at least 2.54 cm.

This is a published screening equation, not a BC-calibrated model.

## Data

Fire and Tree Mortality Database, 2nd edition (2022), USDA Forest Service Research Data Archive,
DOI `10.2737/RDS-2020-0001-2`.

- FTM tree table SHA256: `94eedbbacc807b57cc0864c892b7739213ecb6d4cf72761b24501ed975afa1c5`
- Archive SHA256: `9da3b6a02129ae580e9189aaaf691d349f6ab3b20defd4c6d5ebbff6717b416b`
- Kept rows with a supported species, valid DBH and scorch, and three-year status.
- The split is by dataset, not by tree.

## Result

| Subset | n | Prevalence | AUC | Brier | Brier skill |
| --- | ---: | ---: | ---: | ---: | ---: |
| All | 65,663 | 0.375 | 0.882 | 0.159 | 0.324 |
| Train | 49,915 | 0.393 | 0.880 | 0.175 | 0.266 |
| Validation | 15,748 | 0.318 | 0.912 | 0.105 | 0.514 |
| BC-relevant conifers | 65,413 | 0.375 | 0.882 | 0.158 | 0.325 |

The model beats a constant-prevalence Brier baseline on held-out datasets.

## Decision

**Go** for screening mortality probability.

**No-go** for operational or BC-specific mortality. The data are mostly US species and fires,
the equation is generic, and the 3D visual states are not a mortality observation.

## Reproduce

```bash
python scripts/validate_tree_mortality.py \
  --trees FTM_trees.csv \
  --bark Species_BarkThickness.csv \
  --output notes/reports/tree-mortality.json
```

## Limits

- The equation is applied outside its original species mix.
- No calibration by BC species, fuel type, or fire weather.
- Three-year status is the endpoint; delayed mortality is not modeled.
- DBH < 2.54 cm and species without coefficients are excluded.
- The 3D classes remain visual, not validation.
