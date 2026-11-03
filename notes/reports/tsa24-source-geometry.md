# P115 TSA 24 source geometry

Date: 2026-11-03
Status: complete

## Source

The compiled WS4 dataset carries block attributes but not polygons. The exact
source block layer for this model is the legacy public-data TSA24 stand
shapefile:

- repository: `https://github.com/gparadis/wbi_ria_yield`
- path: `jupyterhub07-tmp/wbi_ria_yield/data/shp/tsa24.shp/stands.shp`
- CRS: `EPSG:3005`
- features: **458,708**

All 458,708 source rows match `archive/tsa24-ws4/fragments.csv` on
`BLOCK`, `AREA_HA`, `F_AGE`, and `AU`. The source hashes are recorded in
`runtime/geometry/README.md` beside the generated layer.

## Generated layer

`runtime/geometry/tsa24-blocks.geojson` is simplified to 5 m with topology
preserved, keeps `block_id`, `area_ha`, `age`, and `au`, and has 458,708
features. It is 1.1 GB in the instance runtime.

Regenerate with:

```bash
python scripts/build_tsa24_geometry.py \
  --source /srv/shared-data/gep/jupyterhub07-tmp/wbi_ria_yield/data/shp/tsa24.shp/stands.shp \
  --output runtime/geometry/tsa24-blocks.geojson
```

## Verification

- `/api/geometry/bounds` returned
  `[834450.0001, 878258.9981, 1393593.6151, 1367370.0001]` in EPSG:3005.
- A viewport query over the first source block returned 11 real block features;
  block 1 carried `area_ha: 6.8`, `age: 155`, `au: 2401007`.
- The portal TSA 24 instance points at
  `runtime/geometry/tsa24-blocks.geojson`.

The map fallback remains for datasets genuinely without a geometry layer.
