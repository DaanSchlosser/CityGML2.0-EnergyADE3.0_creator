# City-scale configs

JSON configs for the city-scale pipeline ([`citygml_energy/city_builder/`](../../citygml_energy/city_builder/), entry point [`examples/create_city.py`](../../examples/create_city.py)). Each file declares one Dutch municipality (or AOI within one), and the pipeline assembles a single CityGML 2.0 + EnergyADE 3.0 GML for it.

The JSON schema is at [`../../schemas/city_input.schema.json`](../../schemas/city_input.schema.json); see §4.2 of the [project README](../../README.md) for the full key reference.

## Files

| Config | Area | Notes |
|---|---|---|
| `emmer-compascuum_small-area.json` | Emmer-Compascuum (~41.5 ha) | Uses every optional input: `boundary` (GeoJSON), `solar_panels`, and `vegetation` (CFTree LoD3 trees). |
| `emmer-compascuum_small-area_pv-only.json` | Emmer-Compascuum (~41.5 ha) | Same boundary, just no vegetation input. |
| `delft.json` | Delft (full municipality) | |
| `groningen.json` | Groningen (full municipality) |  |
| `zwolle.json` | Zwolle (full municipality) |  |

## Path conventions

Relative paths inside a config are resolved against the config file's own directory (i.e. `inputs/cities/`):

- `../boundaries/*.geojson` — AOI polygons in [`../boundaries/`](../boundaries/)
- `../solar_panels/*.gpkg` — solar panel layers in [`../solar_panels/`](../solar_panels/)
- `../../schemas/city_input.schema.json` — JSON schema for editor autocomplete (`$schema`)
- `../../.cache/citygml_energy_city` — cache directory at repo root
- `../../generated/<name>.gml` — output path at repo root
- `../../../CFTree/data/<area>` — external CFTree tree reconstructions (CFTree repo is a sibling of this one)

## Adding a new config

1. Copy the closest existing config and rename.
2. Update `municipality`, `bbox` (or `boundary`), `output`, and `city_model.name` / `description`.
3. Run `python examples/create_city.py --input inputs/cities/<your-config>.json`. Note that the first run populates the cache so takes longer.
4. EP-online energy labels need an API key: set `EP_ONLINE_API_KEY` in `.env` at repo root, or set `include_energy_labels: false` to skip.
