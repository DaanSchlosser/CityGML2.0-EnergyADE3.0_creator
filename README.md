# CityGML 2.0 + Energy ADE 3.0 Creator

This repository gives you three practical ways to generate CityGML 2.0 files
with Energy ADE 3.0 content:

1. A data-only JSON input workflow for collecting RenoDAT-style feature data.
2. A typed Python API for building valid files from scratch.
3. A template-backed Alderaan workflow for regenerating and customizing the
   large reference dataset.

The important distinction is this:

- `examples/create_renodat.py` reads only `inputs/renodat_input.json` and turns
  that collected data into a schema-valid CityGML + Energy ADE file.
- `examples/create_renodat_typed.py` shows the same RenoDAT subset built
  directly with the typed Python API.
- `examples/create_alderaan.py` starts from the checked-in Alderaan reference,
  preserves XML classes that are not yet wrapped by the typed API, and can emit
  either an exact structural reproduction or a beta8-normalized, schema-valid
  variant.

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

Create a small, schema-valid file from the JSON input file:

```powershell
python examples/create_renodat.py
```

The default input lives at `inputs/renodat_input.json`, and the default output
path is `generated/renodat.gml`.

Create the same RenoDAT example via the typed API:

```powershell
python examples/create_renodat_typed.py
```

Rebuild the Alderaan file as a beta8-valid output:

```powershell
python examples/create_alderaan.py --output generated/alderaan.gml
```

Rebuild the Alderaan file as an exact reference reproduction:

```powershell
python examples/create_alderaan.py --exact-reference --output generated/alderaan_exact.gml
```

Notes:

- Exact-reference mode reproduces the checked-in Alderaan structure.
- Exact-reference mode intentionally skips schema validation so the canonical
  repository template can be preserved verbatim.
- Default Alderaan mode applies a deterministic normalization pass for the
  bundled beta8 schema and validates the written output against
  `Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd`.

## Which workflow should you use?

Use `examples/create_renodat.py` if:

- you want your collected data to live outside Python code
- you want to add or remove buildings by editing a single input file
- you want the tool to generate output from that input file only

Use `examples/create_renodat_typed.py` if:

- you want to start from an empty document
- you only need a subset of the full data model
- you want the cleanest starting point for your own building

Use `examples/create_alderaan.py` if:

- you want to keep the Alderaan structure as a rich template
- you want an output that stays close to the reference dataset
- you need XML content that is not yet covered by the typed builders

## RenoDAT Input Workflow

The primary RenoDAT path is now data-only.

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

If you have OBJ geometry for the same building, add a `geometry_sources` entry.
The current importer understands RenoDAT-style LOD3 groups such as
`nrg3_ZoneWallSurface`, `nrg3_ZoneRoofSurface`, `nrg3_ZoneGroundSurface`,
`nrg3_ZoneWindow`, and `nrg3_ZoneDoor`, plus `SolarPanelSurface_*` objects for
the configured PV collector. Openings can use names like
`Window_05|parent=WallSurface_04` so the importer can attach them to the
correct wall surface.

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
      "type": "obj-renodat-lod3",
      "path": "../Owner-Occupier1_LOD3.0_OBJ.obj",
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

## Minimal Typed Workflow

You do not need to populate every Energy ADE property to create a valid file.
The typed `create_renodat_typed()` example already proves that a smaller subset
can be schema-valid.

Core pattern:

```python
from citygml_energy import (
    Building,
    CodeValue,
    GMLDocument,
    MeasureValue,
    Metadata,
    PhotovoltaicCollector,
)

doc = GMLDocument(description="My city", name="Example City")

pv = PhotovoltaicCollector(
    gml_id="pv_1",
    gml_name="PV collector",
    creation_date="2026-04-09",
    installed_power=MeasureValue(5000, "W"),
)

building = Building(
    gml_id="building_1",
    gml_name="My building",
    creation_date="2026-04-09",
    devices=[pv],
    nrg3_metadata=Metadata(author="Your name"),
    bldg_class=CodeValue("1000"),
)

doc.add_building(building)
doc.write("generated/my_building.gml")
```

Start with the minimum your downstream consumer needs, then add fields only
when they carry real meaning for your use case.

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

## Validation and tests

Run the full verification suite:

```powershell
python -m pytest -q
```

Focused checks:

```powershell
python -m pytest tests/test_alderaan_reference.py -q
python -m pytest tests/test_renodat_reference.py -q
```

What is verified today:

- Alderaan exact-reference generation structurally matches the checked-in file.
- Alderaan default generation is valid against the bundled beta8 schema.
- The typed RenoDAT example is schema-valid.
- The generated XML is well-formed and editable from Python.

## Practical advice for extending inputs

- Prefer `inputs/*.json` for collected project data you want to maintain over
  time without touching the generator code.
- Use one building row per building and add more rows later as your data
  collection expands.
- Prefer the typed API when the class you need already exists. It gives you a
  clearer, more maintainable starting point.
- Prefer the Alderaan template workflow when you need complex ADE structures that
  are not yet represented by Python dataclasses.
- Add tests each time you introduce a new input mapping. The existing tests are
  good patterns to copy.

## Current examples

- `examples/create_renodat.py`: JSON-input-driven RenoDAT workflow.
- `examples/create_renodat_typed.py`: typed, from-scratch example.
- `examples/create_renodat_factory.py`: backward-compatible factory entry point
  using the same JSON input file.
- `examples/create_alderaan.py`: template-backed Alderaan reproduction and
  customization path.