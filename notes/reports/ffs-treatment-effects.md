# Open FFS treatment effects

Date: 2026-11-16
Branch: `fire-ffs-effects`
Artifact: `notes/reports/ffs-treatment-effects.json`

## Scope and licence

Only open data is used. The BC Wildfire **CRI Fuel Treatments** and **BC Wildfire Fire Fuel
Types** layers are marked **Access Only**, not open, so they are excluded.

The source used here is the **National Fire and Fire Surrogate study**, USDA Forest Service
Research Data Archive `RDS-2016-0009`. Archive SHA256:
`6a31b026ff6f7248556eab4ba2e4f6694f75e6f769f5d1c53378c679e73321ff`.

## Method

For each treatment unit, pair the pre-treatment sample (`SAMPLE_YEAR_CODE = -1`) with the
first post-treatment sample (`1`). Compute percent change. Summarize the median and
interquartile range by treatment.

Metrics:

- canopy cover, vertical projection;
- live-tree basal area;
- total surface fuel load (one-, ten-, hundred-, and thousand-hour fuels).

## Result

| Treatment | Canopy cover | Live basal area | Surface fuel |
| --- | ---: | ---: | ---: |
| burn-only | −3.1% | −0.8% | **−45.2%** |
| thin-only | −10.8% | **−28.5%** | **+50.6%** |
| thin-burn | **−22.9%** | **−29.0%** | −3.5% |
| control | +6.4% | +0.8% | −8.3% |

Medians; sample sizes are 6–42 paired units depending on metric and treatment.

The important result is the tradeoff: **thinning alone reduces basal area and canopy cover but
increases surface fuel**, while **burn-only reduces surface fuel** and **thin-burn reduces both
structure and canopy**. This is direct measured evidence for the treatment mapping that was
previously missing.

## Decision

**Go** for using these open measured effects as input to an explicit BC treatment prescription
mapping.

**No-go** for BC-specific or operational claims: the data are from US FFS sites, not BC, and
the mapping from these measurements to FBP fuel/canopy inputs remains a modelling decision.

The closed BC CRI layer cannot be used under the open-data rule. If BC treatment locations are
needed, they require an open release or an explicit data-sharing agreement.

## Reproduce

```bash
python scripts/ffs_treatment_effects.py \
  --vegetation "Data/Vegetation/Unit Vegetation.csv" \
  --trees "Data/Vegetation/Unit Tree Vegetation.csv" \
  --fuels "Data/Fuels/Unit Fuels.csv" \
  --output notes/reports/ffs-treatment-effects.json
```
