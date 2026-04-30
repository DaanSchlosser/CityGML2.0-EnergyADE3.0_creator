# PV panels

Solar panel polygon data for the Emmer-Compascuum test area.

## Files

| File | Purpose |
|---|---|
| `pv_panels.gpkg` (layer `pv_panels`) | The actual PV panel polygons (4 389 features) consumed by the city pipeline when a config sets a `pv_panels` block. Loader: [`pv_panels.py::load_panels_in_bbox`](../../citygml_energy/city_builder/pv_panels.py). |
| `pv_panels_extent.geojson` | Reference / documentation polygon (single rectangle, EPSG:28992) showing the geographic extent covered by `pv_panels.gpkg`. Not consumed by the pipeline. |

All files are EPSG:28992 (Amersfoort / RD New).

## Source of `pv_panels.gpkg`

- Zenodo: <https://zenodo.org/records/14860030> (DOI 10.5281/zenodo.14860030)
- RUG page: <https://research.rug.nl/en/datasets/annotated-high-resolution-aerial-imagery-of-the-dutch-landscape-f/>
- Companion model code (not data): <https://git.lwp.rug.nl/cs.projects/solarpanel_segmentation/>
- License: CC-BY-4.0 (attribution required).

The Zenodo record contains the polygons as a shapefile (`annotations/annotations.shp`); it has been re-exported as a GeoPackage for further processing.

## How `pv_panels.gpkg` was made

Aerial true-ortho imagery was captured in 2023 by the local government of Emmen (NL). Solar panel polygons were then annotated across 18.55 km² of that imagery using an AI pipeline.

See the Zenodo record and the dataset's accompanying paper for the full methodology.
