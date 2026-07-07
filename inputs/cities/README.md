# City-scale configs

JSON configs for the city-scale pipeline ([`citygml_energy/city_builder/`](../../citygml_energy/city_builder/), entry point [`examples/create_city.py`](../../examples/create_city.py)). Each file declares one Dutch municipality (or AOI within one), and the pipeline assembles a single CityGML 2.0 + Energy ADE 3.0 GML for it.

The JSON schema is at [`../../schemas/city_input.schema.json`](../../schemas/city_input.schema.json); see §4.2 of the [project README](../../README.md) for the full key reference.

## Files

| Config | Area | Notes |
|---|---|---|
| `emmer-compascuum_small-area.json` | Emmer-Compascuum (~50 ha AOI) | Uses the optional inputs `boundary` (GeoJSON), `solar_panels`, `vegetation` (CFTree LoD3 trees), and `cbs_postcode6` (CBS Postcode-6 aggregates). Doubles as the canonical smoke test. |
| `emmer-compascuum_small-area_solar-only.json` | Emmer-Compascuum (~50 ha AOI) | Same boundary and solar panels, no vegetation input. |
| `emmer-compascuum_small-area_no-energy-labels.json` | Emmer-Compascuum (~50 ha AOI) | Same small-area build but `include_energy_labels: false`, so no EP-Online labels are fetched or emitted. Adds `cbs_postcode6`. Source config for the openly-shareable city GML in the 4TU deposit; carries a `file_header` banner. |
| `emmer-compascuum.json` | Emmer-Compascuum woonplaats (within Emmen) | Full settlement clipped to the BAG woonplaats boundary: BAG + 3DBAG LoD0 + EP-Online. |
| `emmer-compascuum_solar.json` | Emmer-Compascuum woonplaats (within Emmen) | Full woonplaats with LoD2 roofs so University of Groningen solar panels project as `nrg3:GenericSolarCollector` across the whole panel population. |
| `delft.json` | Delft (full municipality) | |
| `groningen.json` | Groningen (full municipality) |  |
| `zwolle.json` | Zwolle (full municipality) |  |
| `city_example.json`, `city_smoke_test.json`, `emmer_compascuum_solar_smoke.json` | n/a | Minimal example and smoke-test fixtures. |

## Path conventions

Relative paths inside a config are resolved against the config file's own directory (i.e. `inputs/cities/`):

- `../boundaries/*.geojson`: AOI polygons in [`../boundaries/`](../boundaries/)
- `../solar_panels/*.gpkg`: solar panel layers in [`../solar_panels/`](../solar_panels/)
- `../../schemas/city_input.schema.json`: JSON schema for editor autocomplete (`$schema`)
- `../../.cache/citygml_energy_city`: cache directory at repo root
- `../../generated/<name>.gml`: output path at repo root

## On-demand tree generation

A `vegetation` block normally points at a pre-merged CFTree file (produced by `tools/merge_cftree_tiles.py`). Add a nested `generate` block and the build produces that file on demand when it is missing, instead of skipping trees:

```json
"vegetation": {
  "path": "../vegetation/<area>.city.json",
  "generate": { "ahn_version": 5, "n_cores": 8, "buffer_m": 20 }
}
```

The build writes the AOI as a CFTree case, runs CFTree for it (CGAL plus PDAL, minutes to a couple of hours), then merges the result into `path` in-process. `ahn_version` (4, 5, or 6) is the swappable LiDAR release; each version is cached under its own case, so to regenerate at a newer release, bump `ahn_version` and delete the merged file. A run is reused only when a completion manifest records that the same AOI, buffer, AHN version, geometry-only mode, and (for the docker runner) image digest finished cleanly, so an interrupted run, a changed AOI, or a re-pulled image regenerates rather than merging stale tiles. Optional settings: `timeout_min` caps the CFTree subprocess (default 360, so a stuck run cannot hang the build forever) and `case` overrides the derived case name. CFTree runs as a subprocess in its own environment, configured by the `CFTREE_*` variables in `.env` (see `.env.example`): the docker runner (the default on Windows) runs the prebuilt image named by `CFTREE_IMAGE` and needs no checkout, while the `wsl` and `native` runners run a local checkout via `CFTREE_REPO` and `CFTREE_PYTHON`. A setup problem (a missing `CFTREE_IMAGE`, an unreachable docker daemon, a missing checkout) fails the build with the missing piece named; a runtime failure in a correctly-set-up run soft-fails to a treeless build, matching the other optional inputs. [docs/address-pipeline.md](../../docs/address-pipeline.md) walks through the docker setup step by step.

Set `geometry_only: true` on the `vegetation` block (alongside or instead of `generate`) to emit trees with CFTree geometry only and skip the authoritative-register cross-reference (the national BGT `vegetatieobject_punt` layer) and its PDOK round-trip. When the file is generated on demand, the same flag runs CFTree with `--geometry-only`, which skips the descriptive morphometrics (r50, porosity) for a several-times-faster reconstruction. This is the address pipeline's default, since that workflow usually wants just the tree geometries.

## Adding a new config

1. Copy the closest existing config and rename.
2. Update `municipality`, `bbox` (or `boundary`), `output`, and `city_model.name` / `description`.
3. Run `python examples/create_city.py --input inputs/cities/<your-config>.json`. Note that the first run populates the cache so takes longer.
4. EP-Online energy labels need an API key: set `EP_ONLINE_API_KEY` in `.env` at repo root, or set `include_energy_labels: false` to skip.
