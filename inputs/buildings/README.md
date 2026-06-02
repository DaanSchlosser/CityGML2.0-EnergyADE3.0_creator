# Per-building feature collections

JSON inputs for the per-building pipeline ([`citygml_energy/generation.py`](../../citygml_energy/generation.py), entry point [`examples/create_building.py`](../../examples/create_building.py)). Each file is a hand-authored "feature collection" describing one building in full Energy ADE detail (zones, schedules, devices, layered constructions, material libraries, per-surface appearances).

The JSON schema is at [`../../schemas/citygml_energy_input.schema.json`](../../schemas/citygml_energy_input.schema.json); see §3 of the [project README](../../README.md) for the full key reference.

## Files

| File | Purpose |
|---|---|
| `owner_occupier_building.json` | The owner-occupier reference building. This is a single-family residence in Delft, modelled LoD0-3 with one zone consisting of two zone parts. The default input for `examples/create_building.py` and the worked example for §3-§9 of the README. |
| `owner_occupier_building_sample.json` | Shareable, anonymised clone of the reference building. Same structural shape, but every data value is a placeholder. Used by [`tools/create_anonymised_sample.py`](../../tools/create_anonymised_sample.py) to produce a geometry-free sample GML safe to attach to upstream issue trackers. |

## Path conventions

`geometry_sources[*].path` entries are resolved against the JSON file's own directory (i.e. `inputs/buildings/`). The reference building's STEP files all live in [`../stp/`](../stp/), so paths read `../stp/Owner-Occupier1_*.stp`.
