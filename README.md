# CityGML 2.0 + Energy ADE 3.0 Creator

A Python toolkit for generating standards-compliant CityGML 2.0 files
extended with the Energy ADE 3.0 (beta8) application domain extension.
Reads JSON inputs, attaches STEP or CityJSON geometry, and emits a
fully XSD-validated GML file without hand-written XML.

> **Viewing the output in KIT FZKViewer?** The viewer ships with an
> incompatible Energy ADE 2.0 schema. See
> [§6 KIT FZKViewer compatibility](#6-kit-fzkviewer-compatibility) for
> the one-time XSD swap.

---

## 1. Research context

This toolkit is a contribution to
**[RenoDAT](https://3d.bk.tudelft.nl/projects/renodat/)**
(*Accelerating building **RENO**vation and decarbonization through
**DAT**a integration*), a TU Delft–led,
[NWO](https://www.nwo.nl/en/projects/xqbeg97133)-funded research project
(autumn 2025 to summer 2029) developing the data infrastructure for
**Building Renovation Passports (BRPs)**.

**The question this toolkit tests:** *Is CityGML 2.0 + Energy ADE 3.0 a
meaningful starting point for BRPs?* Energy ADE 3.0 (beta8) was developed
well before RenoDAT; the project is a catalyst for its real-world
testing, extension, and de-facto standardisation.

**Two pipelines, two test cases for that question:**

| Pipeline | Input | Purpose in RenoDAT |
|---|---|---|
| **Per-building** | Hand-authored feature-collection JSON + Rhino STEP geometry | Can the standard carry the full detail of a single renovation passport (zones, schedules, devices, layered constructions, material libraries) for one dwelling? The [owner-occupier reference building](inputs/buildings/owner_occupier_building.json) (a single-family residence in Delft, LoD 0–3 with thermal zone parts) is the worked example. |
| **City-scale** | JSON config naming a Dutch municipality | Does the same data model scale to the dwelling stock? Fetches BAG + 3DBAG + EP-online (+ optional PV panels, BGT/BOR tree register, CFTree vegetation) for an entire area and assembles one GML file. |

Both pipelines emit the same CityGML 2.0 + Energy ADE 3.0 wire format,
validated against the same XSD set. The output:

- validates against the Energy ADE 3.0 beta8 XSD and the CityGML 2.0 +
  GML 3.1.1 XSD set,
- renders correctly in KIT FZKViewer (after the §6 XSD swap),
- carries real-world coordinates in EPSG:28992 (RD) + EPSG:5109 (NAP).

---

## 2. Quick start

```powershell
# one-time setup (Python 3.12+)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# per-building: generate the GML file for the reference building
python examples/create_building.py

# validate the output offline against the bundled XSDs
python tools/validate_xsd.py generated/owner_occupier_building.gml

# run the test suite
python -m pytest -q
```

Custom paths are supported via `--input` / `--output`. The city-scale
pipeline needs the `city` extras and an EP-online API key in `.env` if
energy labels are requested (see §4). Optional extras: `city-fast`
adds `polars` for faster EP-online CSV filtering. All declared in
[pyproject.toml](pyproject.toml).

---

## 3. Per-building pipeline

Everything the generator needs lives in a single JSON document
([inputs/buildings/owner_occupier_building.json](inputs/buildings/owner_occupier_building.json))
with these top-level keys:

```jsonc
{
  "city_model":          { "name": "...", "description": "..." },
  "coordinate_origin":   [85182.085, 446868.675, 0.105],
  "construction_mapping": {
    "by_type": { "WallSurface": "constr_external_wall", "Window": "constr_window_hr" },
    "by_id":   { "id_building_1_Door2_1": "constr_front_door" }
  },
  "geometry_sources": [
    { "type": "step-building-lod3",
      "path": "Owner-Occupier1_LOD3_STEP.stp",
      "target_building_id": "id_building_1",
      "target_pv_id": "pv_panel_1" }
  ],
  "features": [
    { "type": "bldg:Building", "id": "id_building_1", "name": ["..."], ... },
    { "type": "nrg3:PhotovoltaicCollector", "parent": "id_building_1", "id": "pv_panel_1", ... }
  ]
}
```

- **`features`** is a flat list. Each entry has a `type`
  (`prefix:ElementName`, resolved against the xsdata bindings), an `id`
  (XML NCName), and an optional `parent` (parent's gml:id). Children
  attach to the field on the parent whose type matches; if more than
  one field qualifies, `parent_field` disambiguates.
- **`geometry_sources`** lists STEP files to import.
  `step-building-lod{0..4}` drives building geometry (LoD 2/3 emit
  per-face thematic surfaces and openings, and accept an optional
  `target_pv_id`); `step-zonepart-lod{0..3}` does the same for
  ZoneParts. STEP layer names (`WallSurface_04`, `RoofSurface_02`,
  `Window_05`, `Door_01`, `SolarPanelSurface_*`) drive classification;
  openings are matched to their parent surface by interior-ring
  geometry, not by name.
- **`construction_mapping`** routes surfaces to constructions in the
  in-document `LayeredConstructionLibrary`. `by_type` maps a class to a
  construction id; `by_id` maps a specific surface gml:id to a
  construction id and wins on conflict.
- **`coordinate_origin`** is added to every imported STEP coordinate,
  placing local Rhino models on RD/NAP. **`srs_name`** and
  **`srs_dimension`** override the default
  `urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109` / `3`.

A JSON schema for editor autocomplete lives at
[schemas/citygml_energy_input.schema.json](schemas/citygml_energy_input.schema.json).
See [docs/mapping_building.md](docs/mapping_building.md) for field-to-XSD
mapping notes and [inputs/buildings/README.md](inputs/buildings/README.md)
for the shareable sanitised sample fixture.

### 3.1 Pipeline

```mermaid
flowchart TD
    J["inputs/buildings/*.json"]:::input
    S["inputs/stp/*.stp"]:::input

    L["<b>load_feature_collection</b><br/>validate + normalise paths"]:::stage
    B1["<b>Phase 1: build</b><br/>resolve_class + build_from_dict per feature"]:::stage
    B2["<b>Phase 2: attach</b><br/>parent-by-id, field auto-detection"]:::stage
    G["<b>apply_geometry_sources</b><br/>STEP → polygons → Building / ZonePart / PV"]:::stage
    D["<b>apply_device_relations</b><br/>installed_on → nrg3:CityObjectRelation xlinks"]:::stage
    A["<b>apply_derived_attributes</b><br/>one model walk; per-ADE emitter plug-ins<br/>(layeredConstruction xlinks, bdgBdrySurf*, bdgOpn*)"]:::stage

    CM(["<b>CityModel</b> (xsdata)"]):::model
    W["<b>model.write</b> / serialize_to_file"]:::stage
    OUT["generated/*.gml"]:::output
    VAL["tools/validate_xsd.py<br/>(post-hoc, offline)"]:::stage

    J --> L --> B1 --> B2 --> G --> D --> A --> CM --> W --> OUT
    S --> G
    OUT -.-> VAL

    classDef input fill:#eef6ff,stroke:#4a7fb8,color:#1a2a3a;
    classDef stage fill:#f5f5f5,stroke:#888,color:#111;
    classDef model fill:#fff7e0,stroke:#d0a030,color:#4a3000;
    classDef output fill:#e6f6e6,stroke:#4a8a4a,color:#1a3a1a;
```

Every stage runs offline. No FME, no schema downloads, no XML templates.

### 3.2 Design notes

- **xsdata as the binding layer.** All xsdata classes are auto-generated
  from the official XSDs. Regenerating `citygml_energy/bindings.py`
  (~84k lines) after an XSD change requires no code changes elsewhere:
  downstream code resolves classes through
  `mapping.resolve_class("prefix:LocalName")` at call time, and `NSMAP`
  is built at import time from the bindings plus
  [schemas/namespace_prefixes.json](schemas/namespace_prefixes.json).
  To add an ADE, drop its XSD in, append the path to `_STAGED_ROOTS`
  in `tools/generate_bindings.py`, and rerun.
- **Flat-dict input, parent-by-id.** Children reference parents by
  `gml:id` rather than nesting. The validator rejects unknown types,
  duplicate or non-NCName ids, parent cycles, Energy ADE containment
  violations, dangling `construction_mapping` references, and
  mistyped or missing geometry-source targets.
- **STEP geometry separate from data.** The JSON contains no vertex
  coordinates. Geometry comes from Rhino `.stp` files, offset by
  `coordinate_origin` on import. Ordinate output is quantised to a µm
  grid (6 fractional digits, fixed-point), so reruns are byte-stable.
- **Plug-in seam for ADE properties.** `derived_attributes.py` owns
  one model walk; each ADE plug-in module exports `EMITTERS` (and
  optional `SETUPS`). The current Energy ADE 3.0 plug-ins are
  `construction_mapping.py` (layeredConstruction xlinks) and
  `boundary_attributes.py` (`bdgBdrySurf*` / `bdgOpn*` area,
  inclination, azimuth, thickness, heat capacity).
- **Offline everything.** The repository ships every XSD it needs;
  validation, binding regeneration, and tests run without network
  access.

---

## 4. City-scale pipeline

A separate pipeline in
[`citygml_energy/city_builder/`](citygml_energy/city_builder/) produces
a CityGML + Energy ADE file for an entire Dutch municipality by
combining:

- **BAG** (PDOK WFS): authoritative `bag:pand` outlines and
  `bag:verblijfsobject` units with embedded address fields.
- **3DBAG** ([data.3dbag.nl](https://data.3dbag.nl)): per-Pand
  LoD 0 / 1 / 2 CityJSON tiles.
- **EP-online** ([public.ep-online.nl](https://public.ep-online.nl)):
  the Dutch energy-label register, joined by `BAGVerblijfsobjectID`
  when present, falling back to a normalised address key.
- **PV panels** *(optional)*: 2D roof-panel polygons from a GeoPackage,
  projected onto LoD 2 roof surfaces as
  `nrg3:GenericSolarCollector` (technology-agnostic, because the aerial
  source has no module-level metadata).
- **Trees** *(optional)*: per-tree LoD 3 crown + trunk meshes from
  [CFTree](https://github.com/NoahAlting/CFTree), optionally enriched
  with **BGT** (authoritative-register cross-reference) and **Emmen BOR**
  (species + planting year). Full rationale in
  [docs/vegetation_integration_report.md](docs/vegetation_integration_report.md).
- **CBS Postcode6** *(optional)*: per-PC6 dwelling-energy aggregates
  emitted as `nrg3:UrbanFunctionArea` features, with
  `grp:groupMember` xlinks to the buildings inside each polygon.

### 4.1 Quick start

```powershell
python -m pip install -e ".[city]"
python examples/create_city.py --input inputs/cities/emmer-compascuum_small-area.json
```

The default config (~41.5 ha Emmer-Compascuum AOI) doubles as the
canonical smoke test.

**EP-online API key.** Set `EP_ONLINE_API_KEY` in `.env` at the project
root (git-ignored). Without it, set `include_energy_labels: false`.
The first run fills `cache_dir` with BAG/3DBAG/EP-online responses;
subsequent runs are near-instant.

### 4.2 Config

```jsonc
{
  "$schema": "../../schemas/city_input.schema.json",
  "municipality": "Delft",                    // required
  "bbox": [84000, 445000, 86000, 447000],     // optional clip, EPSG:28992
  "lods": [0, 1, 2],
  "include_addresses": true,
  "include_energy_labels": true,
  "cache_dir": "../../.cache/citygml_energy_city",
  "output": "../../generated/delft.gml",      // required
  "srs_name": "urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
  "srs_dimension": 3,
  "city_model": { "name": "Delft", "description": "..." }
}
```

Optional `pv_panels`, `vegetation`, and `cbs_postcode6` blocks enable
the corresponding inputs. The full schema lives at
[schemas/city_input.schema.json](schemas/city_input.schema.json),
generated from `CityBuildConfig` by
[tools/generate_city_input_schema.py](tools/generate_city_input_schema.py)
and drift-checked by `tests/test_city_input_schema.py`. Example
configs live in [inputs/cities/](inputs/cities/).

### 4.3 Output shape per Pand

- `bldg:Building` (`gml:id = "pand_<identificatie>"`) with
  `yearOfConstruction` from 3DBAG.
- `lod0FootPrint`, `lod1Solid`, and per-planar-polygon LoD 2
  `bldg:boundedBy` surfaces (`GroundSurface` / `WallSurface` /
  `RoofSurface`), each carrying a single-polygon `lod2MultiSurface` and
  the three Energy ADE 3.0 per-surface descriptors derivable from
  geometry alone (`bdgBdrySurfTotalSurfaceArea`,
  `bdgBdrySurfInclination`, `bdgBdrySurfAzimuth`). LoD set filtered by
  the `lods` config.
- One `core:Address` per VBO at Building level (xAL street + house
  number + postcode + woonplaats + suffixes), with each
  `nrg3:BuildingUnit` xlink-referencing its own address.
- One `nrg3:BuildingUnit` per VBO (`gml:id = "bu_<vbo_identificatie>"`)
  with `nrg3:energyPerformanceCertificate` (when EP-online matched) and
  up to four regime-aware `nrg3:Energy` resources (NTA 8800 vs legacy
  NEN-7120). The regime table lives in
  [city_builder/energy_resources.py](citygml_energy/city_builder/energy_resources.py).
- When `pv_panels` is configured: one `nrg3:GenericSolarCollector` per
  panel intersecting a LoD 2 roof, with an `installedOn` xlink onto
  that roof surface.
- When `vegetation` is configured: one `veg:SolitaryVegetationObject`
  per CFTree mesh with LoD 3 geometry and CFTree / BGT / BOR
  morphometrics.
- When `include_energy_labels` is enabled: a single
  `app:Appearance` colouring every building's surfaces by the averaged
  EPC label of its BuildingUnits (EU energy-label palette; buildings
  with no match render grey). Separate themes are emitted for PV
  panels and vegetation when configured.

Everything validates against the bundled XSD set;
`tests/test_city_pipeline.py` asserts that end-to-end with fully-mocked
fetchers.

### 4.4 Performance and further reading

Per-Pand build can be parallelised via `CITYGML_ENERGY_ASSEMBLY_WORKERS`
(default `1`; pickle/spawn cost only pays off past a few thousand
panden). Module layout is in [§5](#5-repository-layout); the full
data-source-to-XSD mapping and design rationale live in
[docs/mapping_city.md](docs/mapping_city.md).

---

## 5. Repository layout

```
citygml_energy/                Core package
├── bindings.py                 xsdata-generated dataclasses (Energy ADE 3.0 + CityGML 2.0)
├── mapping.py                  Generic dict → xsdata, parent linking, tree traversal
├── input_loader.py             JSON loader, validator, two-phase orchestrator
├── geometry.py                 STEP → xsdata attachment, auto-discovered taxonomy
├── _step.py                    ISO 10303-21 parser (xsdata-independent)
├── gml_builders.py             Pure GML primitive builders (µm-quantised output)
├── device_relations.py         installed_on → nrg3:CityObjectRelation resolver
├── derived_attributes.py       Plug-in seam for ADE-property emitters
├── construction_mapping.py     Energy ADE 3.0 plug-in: layeredConstruction xlinks
├── boundary_attributes.py      Energy ADE 3.0 plug-in: bdgBdrySurf* / bdgOpn*
├── core.py                     CityModel wrapper
├── serialization.py            XmlSerializer wrapper (NSMAP + tab indent)
├── namespaces.py               NSMAP from bindings + namespace_prefixes.json
├── schema_types.py             "prefix:LocalName" constants used in Python
├── generation.py               generate_city_model / generate_gml_file
├── errors.py                   CityGMLError → InputFileError / CityBuildError
├── _xsdata_patches.py          Runtime patches for xsdata edge cases
└── city_builder/               City-scale pipeline
    ├── pipeline.py             Orchestrator: build_city_model(config)
    ├── pand_executor.py        Per-Pand build executor (sequential or pool)
    ├── config.py, http.py, boundary.py, pdok_wfs.py     Config, cached HTTP, AOI loader, WFS paginator
    ├── cityjson_parse.py, cityjson_trees_parse.py       CityJSON tile parsers
    ├── address_key.py, address_match.py                 VBO ↔ EP-online address join
    ├── epc_score.py, energy_resources.py, appearance.py EPC palette, regime-aware Energy, app:Appearance
    ├── pv_panels.py, vegetation.py, tree_matching.py    Optional input loaders + nearest-neighbour join
    ├── postcode6.py            CBS Postcode6 → nrg3:UrbanFunctionArea
    ├── _helpers.py             Shared helpers (type coercion, cache keys, gml:id sanitisation)
    ├── builders/               Per-feature builders (building, address, epc, vegetation)
    └── fetchers/               One module per remote source (BAG, 3DBAG, EP-online, BGT, Emmen BOR, CBS, PDOK)

examples/
├── create_building.py          Per-building CLI + library entry point
└── create_city.py              City-scale CLI + library entry point (default INFO; -v drops to DEBUG)

tools/
├── generate_bindings.py            Regenerate bindings.py from XSD
├── generate_input_schema.py        Regenerate per-building JSON schema
├── generate_city_input_schema.py   Regenerate city-scale JSON schema
├── validate_xsd.py                 Offline XSD validation
├── create_anonymised_sample.py     Produce the shareable sanitised sample input
├── merge_cftree_tiles.py           Merge CFTree CityJSON tile exports
└── bench.py                        Benchmarking utilities

inputs/                         See inputs/README.md
├── buildings/                  Per-building feature-collection JSONs
├── stp/                        STEP geometry for the per-building JSONs
├── cities/                     City-scale configs
├── boundaries/                 GeoJSON AOI polygons
├── vegetation/                 CFTree LoD 3 tree meshes (CityJSON)
└── pv_panels/                  PV panel GeoPackage (UoG Zenodo 14860030, CC-BY-4.0)

schemas/
├── citygml_energy_input.schema.json   Generated per-building JSON schema
├── city_input.schema.json             Generated city-scale JSON schema
└── namespace_prefixes.json            Hand-maintained URI → prefix map

xsd/                            CityGML 2.0 + GML 3.1.1 + xLink + xAL (offline copies)
Energy_ADE-3.0beta8/            Authoritative Energy ADE 3.0 beta8 XSD + Alderaan reference

tests/                          Per-building, city-scale, and infra tests
docs/
├── mapping_building.md         Per-building BAG / EP-online field-to-XSD mapping notes
├── mapping_city.md             City-scale data-source mapping + design notes
└── vegetation_integration_report.md   CFTree + BGT + BOR analysis

generated/                      Pipeline output (git-ignored)
```

> The KIT FZKViewer install directory
> (`KITModelViewer_V7.5.2_Build-3777/`) may sit next to this repo for
> the §6 fix but is git-ignored and not part of the project.

---

## 6. KIT FZKViewer compatibility

The KIT FZKViewer ships with an Energy ADE **2.0** schema
(`EnergyADE-local.xsd`, namespace
`http://www.sig3d.org/citygml/2.0/energy/2.0`). GML files using Energy
ADE **3.0** (`http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0`)
will not display correctly until you replace that schema. The generated
GML is XSD-valid either way; `tools/validate_xsd.py` never consults the
viewer's schemas.

**Symptoms without the fix:** child element names ("ZoneWallSurface 4")
shown instead of building names; PV panels invisible; building tree
garbled.

**Fix** (applied to your own KIT viewer install, not this repo):

1. Copy
   [Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd](Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd)
   to `<KITModelViewer>/GMLSchemata/CityGML_2_0/CityGML/EnergyADE-local.xsd`.
2. In the copied file, replace each online `<import>` `schemaLocation`
   URL with the local relative path. All
   `http://schemas.opengis.net/citygml/.../<name>.xsd` URLs map to
   `<name>.xsd` in the same directory, except:
   - `http://schemas.opengis.net/gml/3.1.1/base/gml.xsd` → `../3.1.1/base/gml.xsd`
3. Restart the KIT FZKViewer and reload the GML file.

---

## 7. Tests

Run with `python -m pytest -q`. The [tests/](tests/) tree groups by
concern:

- **End-to-end.**
  [test_reference_building.py](tests/test_reference_building.py) (per-building)
  and [test_city_pipeline.py](tests/test_city_pipeline.py) (city-scale)
  both build a full model and assert XSD validity plus completeness
  (every input feature id appears as a `gml:id` in the output; XSD
  validation alone cannot detect silently-dropped features, since most
  Energy ADE children are `minOccurs=0`).
- **Pipeline invariants.**
  [test_pipeline_invariants.py](tests/test_pipeline_invariants.py)
  asserts completeness, byte-for-byte determinism, coordinate
  formatting, and XML / Unicode round-trips across both pipelines.
- **Negative tests.**
  [test_invalid_inputs_rejected.py](tests/test_invalid_inputs_rejected.py)
  applies targeted corruptions (missing fields, parent cycles,
  containment violations, dangling construction-mapping references,
  mistyped geometry-source targets, and so on) to each owner-occupier
  fixture and asserts the loader raises `InputFileError` with a
  field-specific message.
- **Schema drift.** `test_input_schema.py`, `test_city_input_schema.py`,
  and `test_generate_bindings_staging.py` keep the generated JSON
  schemas and the bindings build pipeline in sync.
- **Unit tests.** Auto-discovery contracts (`test_namespaces_discovery`,
  `test_mapping*`, `test_geometry_discovery`), low-level parsers
  (`test_step`, `test_gml_builders`, `test_factory`,
  `test_multisource_metadata`, `test_epc_score`), and one
  `test_city_*` module per city-scale fetcher and stage.

---

## 8. Supported feature types

The owner-occupier reference input exercises the following types,
round-tripped through the loader and validated against the XSD:

- `bldg:Building`, `nrg3:BuildingUnit`, `core:Address`
- `nrg3:EnergyPerformanceCertificate`
- `nrg3:PhotovoltaicCollector`, `nrg3:HeatPump`,
  `nrg3:EVChargingStation`, `nrg3:ThermalDistribution`,
  `nrg3:ThermalStorageDevice`, `nrg3:GenericElectricalDevice`
- `nrg3:Occupants`, `nrg3:Energy`
- `nrg3:Zone`, `nrg3:ZonePart`
- `nrg3:ConstantValueSchedule`, `nrg3:MonthlyTimeSeries`
- `nrg3:MaterialLibrary`, `nrg3:LayeredConstructionLibrary`

Any other class defined in `bindings.py` can be added to the input
without code changes; the loader resolves it dynamically by
`prefix:ElementName`.
