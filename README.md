# CityGML 2.0 + Energy ADE 3.0 Creator

This repository has one supported generation workflow for user data:

1. Edit the FME-style JSON input in `inputs/renodat_input.json`.
2. Run `python examples/create_renodat.py`.
3. Get a GML file in `generated/renodat.gml`.

That single path is the canonical workflow. It supports the curated flat-field
input catalog, parent-child linking with `gml_parent_id`, and STEP geometry
import through `geometry_sources`.

The Alderaan tooling remains in the repository as reference-fixture maintenance
code for the checked-in sample dataset. It is not the primary workflow for
generating your own GML files.

## Requirements

- Python 3.12
- `lxml`
- `pytest` for running the verification suite

If you need to set up a fresh environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install lxml pytest
```

If you prefer not to activate the environment on Windows, run commands through
`.\.venv\Scripts\python.exe`.

## Quick start

Create a GML file from the JSON input file:

```powershell
python examples/create_renodat.py
```

The default input lives at `inputs/renodat_input.json`, and the default output
path is `generated/renodat.gml`.

If you need to maintain the Alderaan reference dataset, keep using
`examples/create_alderaan.py`. Treat that as reference tooling, not as a
parallel authoring workflow.

## Canonical Workflow

The primary and only supported authoring path is data-only.

- Edit `inputs/renodat_input.json`.
- Keep one feature record per object you have data for.
- Use `gml_parent_id` to attach child objects like PV panels to a building.
- Run `python examples/create_renodat.py`.

The JSON file already references `schemas/citygml_energy_input.schema.json` via
`$schema`, so VS Code can validate the structure while you edit it.

Inside each `attributes` object, VS Code autocomplete now offers the supported
input keys for the selected `feature_type`. You can use either the existing
canonical keys or the matching raw FME field names for the supported subset.
Any field may be omitted when you do not have a value for it.

If you have Rhino-exported geometry for the same building, add a
`geometry_sources` entry with type `step-renodat-lod3`. The STEP importer keeps
the semantic face boundaries and writes wall polygons with interior rings for
openings.

The STEP importer understands RenoDAT-style object naming such as
`WallSurface_04`, `RoofSurface_02`, `GroundSurface_01`,
`Window_05|parent=WallSurface_04`, `Door_01|parent=WallSurface_01`, and
`SolarPanelSurface_*|parent=RoofSurface_02` for the configured PV collector.

Input shape:

```json
{
  "$schema": "../schemas/citygml_energy_input.schema.json",
  "schema_version": 1,
  "city_model": {
    "description": "This is a description",
    "name": "RenoDAT City"
  },
  "geometry_sources": [
    {
      "type": "step-renodat-lod3",
      "path": "../Owner-Occupier1_LOD3.0_STEP.stp",
      "target_building_id": "id_building_1",
      "target_pv_id": "pv_panel_1"
    }
  ],
  "features": [
    {
      "feature_type": "bldg_Building",
      "attributes": {
        "gml_id": "id_building_1",
        "gml_name": "Han solo's house"
      }
    },
    {
      "feature_type": "nrg3_PhotovoltaicCollector",
      "attributes": {
        "gml_id": "pv_panel_1",
        "gml_parent_id": "id_building_1"
      }
    }
  ]
}
```

This format is intentionally close to the existing FME-style factory model, but
the collected data is now stored in JSON instead of being duplicated across
Python scripts.

## Alderaan workflow

`examples/create_alderaan.py` exposes a few helper functions so the template can
be customized without manually traversing XML on day one.

List the available top-level buildings:

```powershell
python examples/create_alderaan.py --list-buildings
```

Rename a building from the command line:

```powershell
python examples/create_alderaan.py --building-id id_building_1 --building-name "My custom building"
```

Change the city metadata at the same time:

```powershell
python examples/create_alderaan.py --city-name "My City" --city-description "Custom ADE sample"
```

The same operations are available from Python:

```python
from examples.create_alderaan import (
    apply_basic_customizations,
    create_alderaan,
    list_buildings,
)

model = create_alderaan()

for building_id, building_name in list_buildings(model):
    print(building_id, building_name)

apply_basic_customizations(
    model,
    city_name="My City",
    city_description="Customized from the Alderaan template",
    building_name_updates={
        "id_building_1": "My custom building",
    },
)

model.write("my_alderaan_variant.gml")
```

## Editing deeper Alderaan content

The Alderaan loader stores top-level city objects as raw XML-backed members so
you can still edit datasets that go beyond the typed API.

Example:

```python
from examples.create_alderaan import create_alderaan
from citygml_energy import find_city_object_by_gml_id

model = create_alderaan(normalize_for_beta8=False)
building = find_city_object_by_gml_id(model, "id_building_1")

building.set_child_text("gml", "name", "My custom building")
model.write("customized_reference.gml")
```

For more advanced edits you can use `building.xpath(...)` on the raw XML-backed
object, or move to the typed API if the feature you need is already implemented
in `citygml_energy`.

## Tests

Run the verification suite:

```powershell
python -m pytest -q
```

## Practical advice for extending inputs

- Prefer `inputs/*.json` for collected project data you want to maintain over
  time without touching the generator code.
- Use one building row per building and add more rows later as your data
  collection expands.
- Prefer the Alderaan template workflow when you need complex ADE structures that
  are not yet represented by Python dataclasses.
- Add tests each time you introduce a new input mapping. The existing tests are
  good patterns to copy.

## Current entry points

- `examples/create_renodat.py`: the canonical JSON-input-driven generation path.
- `examples/create_alderaan.py`: reference-fixture tooling for the Alderaan sample dataset.
