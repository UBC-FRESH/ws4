# P157.9 FireSTARR side-by-side benchmark

Date: 2026-11-09
Parent: #923 P157
Task: #944 P157.9
Status: first external-model comparison complete; not operational validation

## What ran

- Model: FireSTARR v0.9.29, Ubuntu x64 release binary.
- Mode: deterministic, 1,372 minutes from the observed 13:00 start perimeter to the observed
  11:52 final time.
- Grid: 200 m resampling of the Dogrib fuel and elevation grids, covering the full 35.7 km ×
  22.3 km observed extent. FireSTARR's 256-cell working window cannot cover the full 357-cell
  100 m grid, so 200 m is the comparison resolution.
- Inputs: Dogrib observed fuel grid, elevation grid, hourly weather stream advanced from the
  sample FFMC/DMC/DC startup codes, observed 13:00 start perimeter as a raster fuel break.
- WS4: raw-wind heterogeneous hourly run, 1,372 minutes, downsampled from 100 m to the same
  200 m grid.
- Observed: final perimeter rasterized to the same 200 m grid with centre-cell sampling.
- No Scenario 2b polygon wind patch was applied to FireSTARR. The WS4 comparison is therefore
  the raw-wind case, not the Scenario 2b case.

## Result

| Model | Area (ha) | Area bias | Perimeter bias | Centroid (km) | IoU | Sorensen | Orientation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Observed final | 10,132 | — | — | — | — | — | — |
| WS4 raw wind | 29,480 | +191.0% | +157.1% | 3.09 | 0.252 | 0.403 | 9.1° |
| FireSTARR deterministic | 13,808 | +36.3% | +94.0% | 6.91 | 0.140 | 0.246 | 5.5° |

Artifacts:

- `notes/reports/p157-firestarr-comparison.csv`
- `notes/reports/p157-firestarr-comparison.png`

## Interpretation

FireSTARR is much closer on total area: +36% instead of WS4's +191%. WS4 is closer on shape
and location: IoU 0.252 vs 0.140, Sorensen 0.403 vs 0.246, centroid 3.09 km vs 6.91 km.
Both models overpredict the perimeter; neither is operational.

This is a useful model-to-model result because it shows the two models fail differently. It
does not say WS4 is better or worse overall, and it is not a comparison against Prometheus
Scenario 2b or FARSITE.

## Reproduction notes

- FireSTARR requires tiled GeoTIFF inputs. With striped GeoTIFFs the binary failed with SIGFPE
  while reading the raster; writing 256 × 256 tiled GeoTIFFs fixed it.
- FireSTARR's simulation mode needs weather from the start of the start date, not only from the
  ignition hour. The comparison stream runs from 2001-10-16 00:00 to 2001-10-17 12:00 local.
- The start perimeter must be a GeoTIFF in the same projection and cell size as the fuel grid,
  with 1 inside and 0 outside. A KML is not accepted by `--perim` in this version.
- FireSTARR output probability values are 0/1/4; 4 marks the initial perimeter processing
  status. The comparison treats every positive value as burned.
- FireSTARR writes a 256-cell-wide window. The 200 m grid (192 × 112) fits the full observed
  extent; the 100 m grid (357 × 223) does not.

## Free model availability

- FireSTARR: open source, Linux-native. https://github.com/CWFMF/firestarr-cpp/releases/latest
- Prometheus: free EOL Windows installer.
  https://fgmfiles.spyd.com/Prometheus_2023.06.01_EOL.exe
- FlamMap 6.2 (includes FARSITE): free 64-bit Windows installer.
  https://research.fs.usda.gov/sites/default/files/2026-10/firelab-flammap6.2_setup_oct2026_0.zip
- Dogrib sample archive: https://fgmfiles.spyd.com/Dogrib_v624.zip

Prometheus and FlamMap/FARSITE were downloaded but not run. Both are Windows GUI
applications; the container has Wine, but this task did not produce a reliable headless run.
That remains a separate Windows-host or Wine-automation task.

## Next

1. Run Prometheus Scenario 2b on a Windows host, or automate its GUI under Wine, and compare
   the same metrics.
2. Run FireSTARR with the Scenario 2b weather patch if a supported input path exists.
3. Add FARSITE/FlamMap if a reliable headless path is available.
4. Keep WS4's Scenario 2b result separate from the raw-wind external comparison.
