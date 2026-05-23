# Solar panels

Solar panel polygon data for the Emmer-Compascuum test area.

## Files

| File | Purpose |
|---|---|
| `solar_panels.gpkg` (layer `solar_panels`) | The actual solar panel polygons (4 389 features) consumed by the city pipeline when a config sets a `solar_panels` block. Loader: [`solar_panels.py::load_panels_in_bbox`](../../citygml_energy/city_builder/solar_panels.py). |
| `solar_panels_extent.geojson` | Reference / documentation polygon (single rectangle, EPSG:28992) showing the geographic extent covered by `solar_panels.gpkg`. Not consumed by the pipeline. |

All files are EPSG:28992 (Amersfoort / RD New).

## Source of `solar_panels.gpkg`

- Zenodo: <https://zenodo.org/records/14860030> (DOI 10.5281/zenodo.14860030)
- RUG page: <https://research.rug.nl/en/datasets/annotated-high-resolution-aerial-imagery-of-the-dutch-landscape-f/>
- Companion model code (not data): <https://git.lwp.rug.nl/cs.projects/solarpanel_segmentation/>
- License: CC-BY-4.0 (attribution required).

The Zenodo record contains the polygons as a shapefile (`annotations/annotations.shp`); it has been re-exported as a GeoPackage for further processing.

## How `solar_panels.gpkg` was made

Aerial true-ortho imagery was captured in 2023 by the local government of Emmen (NL). Solar panel polygons were then annotated across 18.55 km² of that imagery using an AI pipeline.

See the Zenodo record and the dataset's accompanying paper for the full methodology.

## What the city pipeline does with it

Each panel polygon that intersects a LoD 2 roof is emitted as one
`nrg3:GenericSolarCollector` parented to the matched `bldg:Building`,
carrying the projected `lod2MultiSurface`, `nrg3:moduleArea`,
`nrg3:inclination`, optional `nrg3:azimuth`, `nrg3:referencePoint`,
and an `nrg3:relatedTo[installedOn]` xlink to the LoD 2
`bldg:RoofSurface` it sits on. The technology-agnostic
`GenericSolarCollector` is used (rather than `PhotovoltaicCollector`)
because the source annotation only marks "solar panel" footprints
and carries no module-level metadata — the panels may be
photovoltaic, solar-thermal, or hybrid, and emitting
`PhotovoltaicCollector` would require an asserted `cellType` we have
no source for. Full mapping in [`docs/mapping_city.md` §7](../../docs/mapping_city.md).
