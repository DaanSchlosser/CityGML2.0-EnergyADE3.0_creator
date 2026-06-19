# City-scale configs

JSON configs for the city-scale pipeline ([`citygml_energy/city_builder/`](../../citygml_energy/city_builder/), entry point [`examples/create_city.py`](../../examples/create_city.py)). Each file declares one Dutch municipality (or AOI within one), and the pipeline assembles a single CityGML 2.0 + Energy ADE 3.0 GML for it.

The JSON schema is at [`../../schemas/city_input.schema.json`](../../schemas/city_input.schema.json); see §4.2 of the [project README](../../README.md) for the full key reference.

## Files

| Config | Area | Notes |
|---|---|---|
| `emmer-compascuum_small-area.json` | Emmer-Compascuum (~41.5 ha AOI) | Uses every optional input: `boundary` (GeoJSON), `solar_panels`, and `vegetation` (CFTree LoD3 trees). Doubles as the canonical smoke test. |
| `emmer-compascuum_small-area_solar-only.json` | Emmer-Compascuum (~41.5 ha AOI) | Same boundary and solar panels, no vegetation input. |
| `emmer-compascuum_small-area_no-energy-labels.json` | Emmer-Compascuum (~41.5 ha AOI) | Same small-area build but `include_energy_labels: false`, so no EP-Online labels are fetched or emitted. Source config for the openly-shareable city GML in the 4TU deposit; carries a `file_header` banner. |
| `emmer-compascuum.json` | Emmer-Compascuum woonplaats (within Emmen) | Full settlement clipped to the BAG woonplaats boundary: BAG + 3DBAG LoD0 + EP-Online. |
| `emmer-compascuum_solar.json` | Emmer-Compascuum woonplaats (within Emmen) | Full woonplaats with LoD2 roofs so University of Groningen solar panels project as `nrg3:GenericSolarCollector` across the whole panel population. |
| `delft.json` | Delft (full municipality) | |
| `groningen.json` | Groningen (full municipality) |  |
| `zwolle.json` | Zwolle (full municipality) |  |
| `city_example.json`, `city_smoke_test.json`, `emmer_compascuum_solar_smoke.json` | — | Minimal example and smoke-test fixtures. |

## Path conventions

Relative paths inside a config are resolved against the config file's own directory (i.e. `inputs/cities/`):

- `../boundaries/*.geojson`: AOI polygons in [`../boundaries/`](../boundaries/)
- `../solar_panels/*.gpkg`: solar panel layers in [`../solar_panels/`](../solar_panels/)
- `../../schemas/city_input.schema.json`: JSON schema for editor autocomplete (`$schema`)
- `../../.cache/citygml_energy_city`: cache directory at repo root
- `../../generated/<name>.gml`: output path at repo root
- `../../../CFTree/data/<area>`: external CFTree tree reconstructions (CFTree repo is a sibling of this one)

## On-demand tree generation

A `vegetation` block normally points at a pre-merged CFTree file (produced by `tools/merge_cftree_tiles.py`). Add a nested `generate` block and the build produces that file on demand when it is missing, instead of skipping trees:

```json
"vegetation": {
  "path": "../vegetation/leiden_250.city.json",
  "generate": { "ahn_version": 5, "n_cores": 8, "buffer_m": 20 }
}
```

The build writes the AOI as a CFTree case, runs CFTree for it (CGAL plus PDAL, minutes to a couple of hours), then merges the result into `path` in-process. `ahn_version` (4, 5, or 6) is the swappable LiDAR release; each version is cached under its own case, so to regenerate at a newer release, bump `ahn_version` and delete the merged file. A run is reused only when a completion manifest records that the same AOI, buffer, AHN version, and geometry-only mode finished cleanly, so an interrupted run or a changed AOI regenerates rather than merging stale tiles. Optional knobs: `timeout_min` caps the CFTree subprocess (default 360, so a stuck run cannot hang the build forever) and `case` overrides the derived case name. CFTree runs as a subprocess in its own environment: point the build at it with `CFTREE_REPO`, `CFTREE_RUNNER` (`wsl` or `native`), and `CFTREE_PYTHON` in `.env` (see `.env.example`). Generation soft-fails to a treeless build when CFTree is unavailable, matching the other optional inputs.

Set `geometry_only: true` on the `vegetation` block (alongside or instead of `generate`) to emit trees with CFTree geometry only and skip the authoritative-register cross-reference (the national BGT `vegetatieobject_punt` layer) and its PDOK round-trip. When the file is generated on demand, the same flag runs CFTree with `--geometry-only`, which skips the descriptive morphometrics (r50, porosity) for a several-times-faster reconstruction. This is the address pipeline's default, since that workflow usually wants just the tree geometries.

## Adding a new config

1. Copy the closest existing config and rename.
2. Update `municipality`, `bbox` (or `boundary`), `output`, and `city_model.name` / `description`.
3. Run `python examples/create_city.py --input inputs/cities/<your-config>.json`. Note that the first run populates the cache so takes longer.
4. EP-Online energy labels need an API key: set `EP_ONLINE_API_KEY` in `.env` at repo root, or set `include_energy_labels: false` to skip.
