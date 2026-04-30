# Boundary AOI polygons

GeoJSON polygons used as `boundary` inputs by city-scale configs in [`../cities/`](../cities/). The city pipeline uses a boundary polygon for two things: (a) deriving the bbox that drives BAG / 3DBAG / EP-online / BGT fetches, and (b) clipping fetched buildings + trees to the (potentially concave) AOI.

Loader: [`citygml_energy/city_builder/boundary.py`](../../citygml_energy/city_builder/boundary.py). Only `.geojson` files are accepted. The file must be a single GeoJSON `Feature` with a `Polygon` or `MultiPolygon` geometry. CRS must be EPSG:28992.

## Files

| File | Used by | Notes |
|---|---|---|
| `emmer-compascuum_small-area.geojson` | [`../cities/emmer-compascuum_small-area.json`](../cities/emmer-compascuum_small-area.json), [`../cities/emmer-compascuum_small-area_pv-only.json`](../cities/emmer-compascuum_small-area_pv-only.json) | Hand-drawn concave AOI over Emmer-Compascuum. |

## Adding a new boundary

1. Save the polygon as a GeoJSON `Feature` (not a `FeatureCollection`) in EPSG:28992 with a `Polygon` or `MultiPolygon` geometry.
2. Reference it from a city config under `boundary.path: "../boundaries/<name>.geojson"`.
3. The pipeline will validate the CRS and use the polygon as both bbox source and clipping mask.
