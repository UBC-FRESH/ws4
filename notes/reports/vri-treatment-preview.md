# BC VRI treatment prescription preview

Date: 2026-11-16
Branch: `fire-treatment-prescription`
Artifact: `notes/reports/vri-treatment-preview.json`
Input: `notes/reports/mkrf-vri-2025.geojson`

## Data

BC VRI 2025 Rank 1, Open Government Licence - British Columbia, queried from the public WFS
around the Malcolm Knapp Research Forest AOI:

`bbox = -122.60, 49.20, -122.45, 49.30`

The response contains five features; three have complete forest attributes and map to a VRI
stand. The closed BC CRI Fuel Treatments layer is not used.

## Prescription

Treatment: **thin-burn**, explicit post-treatment fuel type **C2**.

The prescription uses the open FFS medians:

- canopy cover: −22.9%;
- live basal area: −29.0%;
- surface fuel: −3.5%.

The FBP fuel type is supplied by the caller. It is not inferred.

## Result

| VRI stand | Pre fuel | Post fuel | Pre closure | Post closure |
| ---: | :---: | :---: | ---: | ---: |
| 19974397 | C2 | C2 | 70% | 53.97% |
| 19974680 | C2 | C2 | 60% | 46.26% |
| 19928101 | C2 | C2 | 55% | 42.41% |

The VRI mapper assigns C2 before and after because its fuel rules are not sensitive to canopy
closure above the sparse-cover threshold. The declared basal-area and surface-fuel changes are
recorded but are not inputs to the current VRI→FBP mapper.

## Decision

**Go** for the explicit prescription contract: post-treatment fuel type, canopy change, basal
change, and surface-fuel change are all declared and reproducible.

**No-go** for an automatic fuel-type conversion or a fire-effect claim. This preview shows that
the current VRI→FBP rules alone do not capture the FFS treatment deltas. A fire-grid treatment
needs an explicit conversion beyond this stand-level preview.

## Reproduce

```bash
python scripts/vri_treatment_preview.py \
  --input notes/reports/mkrf-vri-2025.geojson \
  --treatment thin-burn \
  --fuel-type C2 \
  --output notes/reports/vri-treatment-preview.json
```
