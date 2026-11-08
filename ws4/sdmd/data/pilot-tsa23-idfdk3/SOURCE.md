# TSA 23 IDFdk3 real PSP pilot extract

This store is a small, derived extract from the public BC Forest Inventory Ground
Plot compilation. It is the first real-data pilot AU. It replaces neither the
provincial compilation nor an AU inventory; it is a documented sample for the
SDMD evidence layer.

## Source

- Publisher: Forest Analysis and Inventory Branch, Government of British Columbia.
- Dataset: *Forest Inventory Ground Plot Data and Interactive Map*.
- Catalogue: `https://catalogue.data.gov.bc.ca/dataset/824e684b-4114-4a05-a490-aa56332b57f4`.
- Files used: `faib_header.csv`, `faib_plot_header.csv`, `faib_sample_byvisit.csv`,
  `faib_compiled_spcsmries.csv`, `faib_compiled_spcsmries_siteage.csv`, and
  `faib_tree_detail.csv` from
  `https://www.for.gov.bc.ca/ftp/HTS/external/!publish/ground_plot_compilations/psp/`.
- Licence: Open Government Licence - British Columbia.
- Retrieved: 2026-11-02.

Only the selected rows are stored. The full compilation is not copied into the
repository, and no third-party documentation is reproduced.

## Selection

The AU is `AU-IDFdk3-TSA23-FDI`:

- TSA 23, BEC zone `IDF`, subzone `dk`, variant `3`.
- Dominant species `FD` (interior Douglas-fir) by live basal area.
- Eleven reviewed PSP cluster visits, ages 52 to 139.
- Species summaries at the 2 cm close-utilization limit, so total live stems and
  whole-stem volume use the same tree population.

The public header has 145 `IDFdk3` sites in TSA 23. TSA 24 has none, which is why
the earlier synthetic `TSA-24` label could not carry a real extract.

## Field derivation

| Field | Source |
| --- | --- |
| `tph` | sum of `STEMS_HA_LIV` over species at `UTIL=2` |
| `ba_m2_ha` | sum of `BA_HA_LIV` at `UTIL=2` |
| `volume_m3_ha` | sum of `VHA_WSV_LIV` at `UTIL=2` |
| `mean_tree_volume_m3` | `volume_m3_ha / tph` |
| `qmd_cm` | `sqrt(40000 * ba_m2_ha / (pi * tph))` |
| `age`, `top_height_m`, `site_index` | `AGE_TOT1`, `HTOP1`, `SI1` for the dominant species |
| `slope`, `aspect`, `elevation`, `plot_area_ha` | mean of the plot-header rows, with area summed |
| `sdi` | Reineke index from TPH and QMD, reference 25.4 cm, exponent 1.605 |
| `sdi_max` | 1482, the Drew and Flewelling (1979) Douglas-fir default |
| `rd` | `sdi / sdi_max` |
| `zone` | `place_point` on the provisional `fdin` diagram |

The tree list keeps live trees (`LV_D=L`) and uses `PHF_TREE` as trees per hectare.
`crown_ratio` is `(HEIGHT - HT_BRCH) / HEIGHT`, clipped to 0.89 because FVS's
one-digit field cannot represent a larger ratio; a missing branch height uses
0.4 and is not used in the SDMD placement.

## FVS trajectory

- Model: `fresh-fvsbc` 0.20.0, BC variant.
- Tree list: the live trees of three clusters — `4024520-PSP2` (age 76),
  `4025005-PSP1` (age 89), and `4024520-PSP4` (age 101) — each as a plot. Tree
  counts are scaled by `1063 / 2967.0 = 0.3583` so the composite initial TPH
  matches the AU median TPH.
- Site: `SITECODE FD,60`.
- Stand: `STDINFO CAR IDFdk3/01 0 200 35 16`.
- Horizon: 8 cycles of 10 years; `RANNSEED 1`.
- CT60: `THINBBA` at the first 10-year cycle with 60% basal-area removal. The
  projection starts at the plot ages above, so this is a first-entry treatment,
  not a literal age-60 entry.
- Conversion: `tph = tpa * 2.4710538146716536`; `volume_m3_ha = tcuft *
  0.06997084548`; `mean_tree_volume_m3 = volume_m3_ha / tph`.

The full provenance record is in the FVS run directory, not in this store. The
stored path is labelled `provisional`.

## Limits

- The observed points are an extract, not a full TSA 23 inventory.
- The FVS path is a multi-plot composite of three clusters with different ages,
  not a statistical ensemble. The stand summary is a composite, not a single
  even-aged stand.
- `sdi_max` is a species default, not a site-specific estimate.
- The `fdin` diagram is still provisional; the curve review is P95.1.
- The CT60 path regenerates aspen after thinning; that is the model's response,
  not a silvicultural recommendation.
- No initial volume is supplied, so that gate warns.
