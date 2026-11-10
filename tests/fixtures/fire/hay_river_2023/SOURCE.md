# Hay River / K'atl'odeeche second-fire fixture

Fire: SS005-23 / Hay River / K'atl'odeeche, NWT, 2023.

- Perimeter and progression: Canadian Fire Spread Dataset (CFSDS) v1.1, OSF `f48ry`,
  `2023_320_krig.tif`. The raster is reprojected from NAD83 Lambert Conformal Conic to
  UTM zone 11N (EPSG:26911). The daily masks are satellite-derived; day-of-burning 134-140
  is 14-20 May 2023.
- Weather: ECCC HAY RIVER CLIMATE (climate ID 2202402), hourly May 2023, local standard
  time. The event rows are 14 May 12:00 through 20 May 23:00 LST.
- Fuel and elevation: FireSTARR Fuel 2023 V1.0, 100 m, `fuel_11_0.tif` and `dem_11_0.tif`,
  UTM zone 11N. Fuel codes are the FireSTARR/Default Fuel Types codes.
- Ignition: centroid of the first-day (DOY 134) burned cells, not an official ignition
  report.

The CFSDS and FireSTARR datasets are public but have no explicit licence file in the
reviewed copies. They are used for non-commercial validation with attribution; the derived
subset is kept small and the raw datasets are not committed.
