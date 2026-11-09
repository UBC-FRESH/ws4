# Dogrib fire validation fixture

Source: Prometheus sample dataset `Dogrib_v624.zip`, archived from
`http://www.firegrowthmodel.ca/prometheus/downloads/Dogrib_v624.zip` on 2026-11-08.

The Prometheus sample dataset is the standard validation case for the Canadian Forest Fire
Behavior Prediction System. This fixture keeps only the files needed for the WS4 observed-fire
contract:

- `fbp_fuel_type.asc` and `fbp_fuel_type.prj`
- `elevation.asc` and `elevation.prj`
- `fbp_lookup_table.csv`
- `weather_B3_hourly_20010925to1030.csv`
- the 2001-10-16 13:00 and 2001-10-17 11:52 observed perimeters
- the 2001-10-16 13:00 ignition point

The original dataset is public and distributed for Prometheus validation. No explicit licence
file was found in the archive. The fixture is used for non-commercial validation with
attribution; replace or remove it if the source licence requires different terms.

Fire: RWF085, Dogrib fire, Northwest Territories, Canada, 2001. The event window used here is
the second growth spurt starting 2001-10-16 13:00 local time. The projected grid is a custom
NAD83 Transverse Mercator with central meridian -115, scale factor 0.9992, false easting
500000 m. The KML perimeters and ignition point are EPSG:4326 and are transformed to the grid
projection by the loader.
