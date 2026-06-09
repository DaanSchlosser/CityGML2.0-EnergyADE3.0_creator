# Boundary AOI polygons

GeoJSON polygons used as `boundary` inputs by city-scale configs in [`../cities/`](../cities/). The city pipeline uses a boundary polygon for two things: (a) deriving the bbox that drives BAG / 3DBAG / EP-Online / BGT fetches, and (b) clipping fetched buildings + trees to the (potentially concave) AOI.

Loader: [`citygml_energy/city_builder/boundary.py`](../../citygml_energy/city_builder/boundary.py). Only `.geojson` files are accepted. The file must be a single GeoJSON `Feature` with a `Polygon` or `MultiPolygon` geometry. CRS must be EPSG:28992.

## Files

| File | Used by | Notes |
|---|---|---|
| `emmer-compascuum_small-area.geojson` | [`../cities/emmer-compascuum_small-area.json`](../cities/emmer-compascuum_small-area.json), [`../cities/emmer-compascuum_small-area_solar-only.json`](../cities/emmer-compascuum_small-area_solar-only.json), [`../cities/emmer-compascuum_small-area_no-energy-labels.json`](../cities/emmer-compascuum_small-area_no-energy-labels.json) | Hand-drawn concave AOI over Emmer-Compascuum. |
| `emmer-compascuum_woonplaats.geojson` | [`../cities/emmer-compascuum.json`](../cities/emmer-compascuum.json), [`../cities/emmer-compascuum_solar.json`](../cities/emmer-compascuum_solar.json) | Full BAG woonplaats boundary of Emmer-Compascuum. |
| `emmer_compascuum_area.geojson` | — | Not currently referenced by any config. |

## Adding a new boundary

1. Save the polygon as a GeoJSON `Feature` (not a `FeatureCollection`) in EPSG:28992 with a `Polygon` or `MultiPolygon` geometry.
2. Reference it from a city config under `boundary.path: "../boundaries/<name>.geojson"`.
3. The pipeline will validate the CRS and use the polygon as both bbox source and clipping mask.
