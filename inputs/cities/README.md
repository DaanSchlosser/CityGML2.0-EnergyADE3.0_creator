# City-scale configs

JSON configs for the city-scale pipeline ([`citygml_energy/city_builder/`](../../citygml_energy/city_builder/), entry point [`examples/create_city.py`](../../examples/create_city.py)). Each file declares one Dutch municipality (or AOI within one), and the pipeline assembles a single CityGML 2.0 + Energy ADE 3.0 GML for it.

The JSON schema is at [`../../schemas/city_input.schema.json`](../../schemas/city_input.schema.json); see §4.2 of the [project README](../../README.md) for the full key reference.

## Files

| Config | Area | Notes |
|---|---|---|
| `emmer-compascuum_small-area.json` | Emmer-Compascuum (~41.5 ha AOI) | Uses every optional input: `boundary` (GeoJSON), `solar_panels`, and `vegetation` (CFTree LoD3 trees). Doubles as the canonical smoke test. |
| `emmer-compascuum_small-area_solar-only.json` | Emmer-Compascuum (~41.5 ha AOI) | Same boundary and solar panels, no vegetation input. |
| `emmer-compascuum.json` | Emmer-Compascuum woonplaats (within Emmen) | Full settlement clipped to the BAG woonplaats boundary: BAG + 3DBAG LoD0 + EP-Online. |
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

## Adding a new config

1. Copy the closest existing config and rename.
2. Update `municipality`, `bbox` (or `boundary`), `output`, and `city_model.name` / `description`.
3. Run `python examples/create_city.py --input inputs/cities/<your-config>.json`. Note that the first run populates the cache so takes longer.
4. EP-Online energy labels need an API key: set `EP_ONLINE_API_KEY` in `.env` at repo root, or set `include_energy_labels: false` to skip.
