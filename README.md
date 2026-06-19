# CityGML 2.0 + Energy ADE 3.0 Creator

[![CI](https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator/actions/workflows/ci.yml/badge.svg)](https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](pyproject.toml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20612452-blue.svg)](https://doi.org/10.5281/zenodo.20612452)

A Python toolkit for generating CityGML 2.0 files extended with Energy
ADE 3.0 (beta8), CityGML's extension mechanism for energy data. The
point is an easier authoring path: you describe the model in JSON and
attach STEP or CityJSON geometry, and the toolkit assembles and
serialises the Energy ADE GML so you never write the XML by hand.

<div align="center">
  <img src="docs/img/city-scale_EPC-coloring_and_solar-panels_trees.png" alt="City-scale CityGML 2.0 + Energy ADE 3.0 output: a Dutch neighbourhood with buildings coloured by energy label, roof-mounted solar collectors, and LoD3 trees" width="820">
  <br>
  <em>City-scale output for a Dutch neighbourhood, with each building coloured by the averaged energy label of its dwellings, roof-mounted solar collectors, and LoD3 trees from the optional vegetation input.</em>
  <br>
  <br>
</div>

> **Viewing the output in KITModelViewer?** The viewer ships with an
> incompatible Energy ADE 2.0 schema. See
> [§6 KITModelViewer compatibility](#6-kitmodelviewer-compatibility) for
> the one-time XSD swap.

---

## 1. Research context

This toolkit contributes to
**[RenoDAT](https://3d.bk.tudelft.nl/projects/renodat/)**
(*Accelerating building **RENO**vation and decarbonization through
**DAT**a integration*), a TU Delft-led,
[NWO](https://www.nwo.nl/en/projects/xqbeg97133)-funded project
(2025 to 2029) building the data infrastructure for Building Renovation
Passports. It tests whether CityGML 2.0 + Energy ADE 3.0 (beta8,
developed well before RenoDAT) is a workable starting point for those
passports, through two pipelines that exercise the question on
different inputs.

| Pipeline | Input | Purpose in RenoDAT |
|---|---|---|
| **Per-building** | Hand-authored feature-collection JSON + Rhino STEP geometry | Can the standard carry the full detail of a single renovation passport (zones, schedules, devices, layered constructions, material libraries) for one dwelling? The [owner-occupier reference building](inputs/buildings/NL-single-family-house.json) (a single-family residence in Delft, LoD0-LoD3 with thermal zone parts) is the worked example. |
| **City-scale** | JSON config naming a Dutch municipality | Does the same data model scale to the dwelling stock? Fetches BAG + 3DBAG + EP-Online (+ optional solar panels, BGT/BOR tree register, CFTree vegetation) for an entire area and assembles one GML file. |

Both pipelines emit the same wire format, so a consumer reads one
schema no matter which pipeline produced the file. The output renders
in KITModelViewer after the §6 XSD swap and carries real-world
coordinates in EPSG:28992 (RD) + EPSG:5109 (NAP).

---

## 2. Quick start

The toolchain is pinned for reproducibility: the Python version is fixed
in [.python-version](.python-version) (3.12) and the full dependency graph
is locked in [uv.lock](uv.lock), so [uv](https://docs.astral.sh/uv/)
recreates the exact environment this toolkit was developed and tested
against. CI runs the same steps on every push.

```powershell
# one-time setup with uv (fetches Python 3.12 if needed, installs from uv.lock)
uv sync --all-extras

# per-building: generate the GML file for the reference building
uv run python examples/create_building.py

# validate the output offline against the bundled XSDs
uv run python tools/validate_xsd.py generated/NL-single-family-house.gml

# run the test suite
uv run pytest -q
```

<details>
<summary>Prefer a plain venv + pip (Python 3.12+)?</summary>

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"            # add ,city,city-fast for the city pipeline

python examples/create_building.py
python tools/validate_xsd.py generated/NL-single-family-house.gml
python -m pytest -q
```

</details>

Custom paths are supported via `--input` / `--output`. The city-scale
pipeline needs the `city` extras and an EP-Online API key in `.env` if
energy labels are requested (see §4); `uv sync --all-extras` already
includes them. The optional `city-fast` extra adds `polars` for faster
EP-Online CSV filtering. All extras are declared in
[pyproject.toml](pyproject.toml).

---

## 3. Per-building pipeline

The owner-occupier reference dwelling, built from a single JSON document
plus Rhino STEP geometry, shown at each level of detail and split into
its thermal zone parts:

<div align="center">
  <table>
    <tr>
      <td align="center"><img src="docs/img/owner-occupier-lod0.png" width="155" alt="LoD0 footprint"><br><sub><b>LoD0</b><br>footprint</sub></td>
      <td align="center"><img src="docs/img/owner-occupier-lod1.png" width="155" alt="LoD1 massing block"><br><sub><b>LoD1</b><br>massing block</sub></td>
      <td align="center"><img src="docs/img/owner-occupier-lod2.png" width="155" alt="LoD2 thematic surfaces"><br><sub><b>LoD2</b><br>thematic surfaces</sub></td>
      <td align="center"><img src="docs/img/owner-occupier-lod3.png" width="155" alt="LoD3 with openings and a photovoltaic array"><br><sub><b>LoD3</b><br>openings + PV</sub></td>
      <td align="center"><img src="docs/img/owner-occupier-lod2-zoneparts.png" width="155" alt="The reference dwelling split into per-storey thermal zone parts"><br><sub><b>ZoneParts</b><br>thermal zones</sub></td>
    </tr>
  </table>
  <em>LoD0 footprint through LoD3 openings and photovoltaics, then the two thermal <code>nrg3:ZonePart</code> volumes (lower storey red, upper storey blue) that the Energy ADE attaches schedules and energy resources to.</em>
  <br>
  <br>
</div>

Everything the generator needs lives in a single JSON document
([inputs/buildings/NL-single-family-house.json](inputs/buildings/NL-single-family-house.json))
with these top-level keys:

```jsonc
{
  "file_header":         "...provenance / licence banner...",
  "city_model":          { "name": "...", "description": "..." },
  "coordinate_origin":   [85182.085, 446868.675, 0.105],
  "construction_mapping": {
    "by_type": { "WallSurface": "constr_external_wall", "Window": "constr_window_hr" },
    "by_id":   { "id_building_1_Door2_1": "constr_front_door" }
  },
  "geometry_sources": [
    { "type": "step-building-lod3",
      "path": "NL-single-family-house_LOD3_STEP.stp",
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
  `step-building-lod{0..4}` drives building geometry (LoD2/LoD3 emit
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
- **`file_header`** (optional) is a free-text string emitted as an XML
  comment between the `<?xml ?>` declaration and the root
  `<core:CityModel>` (schema-invisible). It must be non-empty and must
  not contain `--` (illegal inside an XML comment). The reference
  building and both deposited GMLs use it for a provenance / licence
  banner. The same key works in the city config (§4.2).

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
    D["<b>apply_device_relations</b><br/>related_to → nrg3:CityObjectRelation xlinks"]:::stage
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

Every stage runs offline. No schema downloads, no XML templates.

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
  `boundary_attributes.py` (`bdgBdrySurf*` / `bdgOpn*` area, opaque
  area, inclination, azimuth, thickness, heat capacity).
- **Ships its own schemas.** The repository ships every XSD it needs,
  so validation, binding regeneration, and tests run without network
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
  LoD0/LoD1/LoD2 CityJSON tiles.
- **EP-Online** ([public.ep-online.nl](https://public.ep-online.nl)):
  the Dutch energy-label register, joined by `BAGVerblijfsobjectID`
  when present, falling back to a normalised address key.
- **Solar panels** *(optional)*: 2D roof-panel polygons from a GeoPackage,
  projected onto LoD2 roof surfaces as
  `nrg3:GenericSolarCollector` (technology-agnostic, because the aerial
  source has no module-level metadata).
- **Trees** *(optional)*: per-tree LoD3 crown + trunk meshes from
  [CFTree](https://github.com/NoahAlting/CFTree), optionally enriched
  with **BGT** (authoritative-register cross-reference) and **Emmen BOR**
  (species + planting year). Full rationale in
  [docs/vegetation_integration_report.md](docs/vegetation_integration_report.md).
- **CBS Postcode6** *(optional)*: per-PC6 dwelling-energy aggregates
  emitted as `nrg3:UrbanFunctionArea` features, with
  `grp:groupMember` xlinks to the buildings inside each polygon.

### 4.1 Quick start

The shipped configs reproduce the thesis runs, so they fetch live data and, for
energy labels, need a free EP-Online API key (the one non-open input). Get a key
from RVO (`epbdwebservices.rvo.nl`) and set `EP_ONLINE_API_KEY` in `.env` at the
project root (git-ignored); or set `"include_energy_labels": false` to build from
open data alone. The key is only used while the EP-Online bundle cache is cold:
once `.cache/citygml_energy_city` holds the bundle, repeat runs skip the
EP-Online network round-trip entirely and need neither the key nor a
connection for that source. For a fully offline run with no key and no
network, use the per-building pipeline ([§3](#3-per-building-pipeline)).

```powershell
python -m pip install -e ".[city]"
python examples/create_city.py --input inputs/cities/emmer-compascuum_small-area.json
```

The default config (~41.5 ha Emmer-Compascuum AOI) doubles as the canonical
smoke test. The first run fills `cache_dir` with BAG/3DBAG/EP-Online responses;
subsequent runs read from cache instead of refetching.

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

Optional `solar_panels`, `vegetation`, and `cbs_postcode6` blocks enable
the corresponding inputs. Instead of `bbox`, a `boundary` block pointing
at a GeoJSON polygon clips to a (possibly concave) area of interest, and
`ep_online_api_key_file` points at a file holding the EP-Online key as an
alternative to the `.env` variable. Instead of `municipality` (+ `bbox` or
`boundary`), an `address` block resolves the extent from a free-text Dutch
address and highlights the matched buildings ([§4.5](#45-address-driven-extract)).
A nested `vegetation.generate` block produces the CFTree tree file on demand
when it is missing ([§4.6](#46-on-demand-tree-generation)) rather than
skipping trees. An optional top-level `file_header`
string is emitted as an XML comment in the generated GML, exactly as in
the per-building pipeline (§3); the deposited
`emmer-compascuum_small-area_no-energy-labels.json` config carries one.
The full schema lives at
[schemas/city_input.schema.json](schemas/city_input.schema.json),
generated from `CityBuildConfig` by
[tools/generate_city_input_schema.py](tools/generate_city_input_schema.py)
and drift-checked by `tests/test_city_input_schema.py`. Example
configs live in [inputs/cities/](inputs/cities/).

### 4.3 Output shape per Pand

- `bldg:Building` (`gml:id = "pand_<identificatie>"`) with
  `yearOfConstruction` from 3DBAG.
- `lod0FootPrint`, `lod1Solid`, and per-planar-polygon LoD2
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
  with `nrg3:energyPerformanceCertificate` (when EP-Online matched) and
  up to four regime-aware `nrg3:Energy` resources (NTA 8800 vs legacy
  NEN-7120). The regime table lives in
  [city_builder/energy_resources.py](citygml_energy/city_builder/energy_resources.py).
- When `solar_panels` is configured: one `nrg3:GenericSolarCollector` per
  panel intersecting a LoD2 roof, with an `installedOn` xlink onto
  that roof surface.
- When `vegetation` is configured: one `veg:SolitaryVegetationObject`
  per CFTree mesh with LoD3 geometry and CFTree / BGT / BOR
  morphometrics.
- When `include_energy_labels` is enabled: a single
  `app:Appearance` colouring every building's surfaces by the averaged
  EPC label of its BuildingUnits (EU energy-label palette; buildings
  with no match render grey). Separate themes are emitted for solar
  collectors and vegetation when configured.

<div align="center">
  <table>
    <tr>
      <td align="center"><img src="docs/img/city-scale_tree-coloring-per-vegetation-species.png" width="380" alt="City-scale trees coloured by vegetation species"><br><sub><b>Trees by species</b></sub></td>
      <td align="center"><img src="docs/img/city-scale_UrbanAreaFunction-highlight.png" width="380" alt="Urban function area polygons highlighted over the building stock"><br><sub><b>Urban function areas</b></sub></td>
    </tr>
  </table>
  <em>LoD3 trees coloured by vegetation species from CFTree and Emmen BOR, beside <code>nrg3:UrbanFunctionArea</code> polygons aggregated from CBS Postcode6 and highlighted over the building stock.</em>
  <br>
  <br>
</div>

### 4.4 Performance and further reading

Per-Pand build can be parallelised via `CITYGML_ENERGY_ASSEMBLY_WORKERS`
(default `1`; pickle/spawn cost only pays off past a few thousand
panden). Module layout is in [§5](#5-repository-layout); the full
data-source-to-XSD mapping and design rationale live in
[docs/mapping_city.md](docs/mapping_city.md).

<div align="center">
  <table>
    <tr>
      <td align="center"><img src="docs/img/delft_topview_northoriented.png" width="410" alt="Whole-city EPC-coloured building stock of Delft, north-oriented top view"><br><sub><b>Delft</b></sub></td>
      <td align="center"><img src="docs/img/groningen_topview_northoriented.png" width="410" alt="Whole-city EPC-coloured building stock of Groningen, north-oriented top view"><br><sub><b>Groningen</b></sub></td>
    </tr>
  </table>
  <em>Two entire municipalities run through the city-scale pipeline, with every building coloured by its averaged energy label (north-oriented; grey where EP-Online has no match).</em>
  <br>
  <br>
</div>

### 4.5 Address-driven extract

The city-scale pipeline can take its extent from a free-text Dutch
address instead of a municipality. Give it an address and it builds a
square extract centred on the building(s) the address covers, painting
those buildings a light yellow-orange and everything around them white,
so the subject of the extract reads at a glance against its context.

```powershell
python examples/create_address.py --address "Annie Romeinsingel 72-152 Leiden"
```

The address may be a single house, a house-number range, or several
streets, and it tolerates the loose formatting of a typical listing
(`"Lange gracht 76-214 Leiden"`, `"Etta Palmstraat en Joke Smitstraat
z.n. Leiden"`). Resolution splits the work between two services by what
each does well: PDOK Locatieserver supplies only a coarse anchor
coordinate and the authoritative gemeente / woonplaats name, and the BAG
WFS then decides exactly which addresses, and therefore which Panden, the
query covers. The fuzzy geocoder never decides membership.

This is an extent mode of the city-scale pipeline, not a third pipeline
(see [ADR-0003](docs/adr/0003-two-pipelines.md)): it reuses the same BAG,
3DBAG, and EP-Online fetch and the same output shape, and only the extent
resolution and the building colouring differ. Settings other than the
address come from a profile JSON (`--profile`, default
[inputs/address/leiden_example.json](inputs/address/leiden_example.json)),
whose `address` block carries the `query`, the square `extent_m` side
length, and the optional `target_color` / `surroundings_color`. The
`address` block is mutually exclusive with `bbox` and `boundary`, and
makes `municipality` optional since the gemeente comes from the geocode.

### 4.6 On-demand tree generation

A `vegetation` block normally points at a pre-merged CFTree file. Add a
nested `generate` block and the build produces that file on demand when
it is missing, instead of skipping trees:

```jsonc
"vegetation": {
  "path": "../vegetation/leiden_250.city.json",
  "geometry_only": true,
  "generate": { "ahn_version": 5, "n_cores": 8, "buffer_m": 20 }
}
```

The build writes the AOI as a CFTree case, runs
[CFTree](https://github.com/NoahAlting/CFTree) for it (CGAL plus PDAL,
minutes to a couple of hours) as a subprocess, then merges the result
into `path`. CFTree is a heavy, separately-installed pipeline, so the
machine-specific launch details stay in the environment rather than the
config: `CFTREE_REPO`, `CFTREE_RUNNER` (`wsl` or `native`), and
`CFTREE_PYTHON` in `.env` (see [.env.example](.env.example)). The
build-intent knobs (`ahn_version`, `n_cores`, `buffer_m`, optional
`timeout_min` and `case`) stay in the config so it remains shareable. A
completion manifest records the AOI, buffer, AHN version, and
geometry-only mode of a clean run, so an interrupted run or a changed AOI
regenerates rather than reusing stale tiles. Setting `geometry_only`
emits trees with CFTree geometry only, skips the BGT / BOR register
cross-reference, and runs CFTree with `--geometry-only` for a several-
times-faster reconstruction; it is the address extract's default.
Generation soft-fails to a treeless build when CFTree is unavailable,
matching the other optional inputs.
[inputs/address/leiden_250.json](inputs/address/leiden_250.json) is the
generate-enabled address profile.

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
├── device_relations.py         related_to → nrg3:CityObjectRelation resolver (RELATION_KINDS registry)
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
    ├── extent.py, painters.py  Build-extent seam (gemeente / address) and building-painter seam (energy-label / highlight)
    ├── address_query.py, address_extent.py    Free-text address → parsed query → centred extent + target Panden
    ├── cftree_runner.py, _env.py    On-demand CFTree subprocess runner (WSL / native) and shared .env loader
    ├── config.py, http.py, boundary.py, pdok_wfs.py     Config, cached HTTP, AOI loader, WFS paginator
    ├── cityjson_parse.py, cityjson_trees_parse.py       CityJSON tile parsers
    ├── address_key.py, address_match.py                 VBO ↔ EP-online address join
    ├── epc_score.py, energy_resources.py, appearance.py EPC palette, regime-aware Energy, app:Appearance
    ├── solar_panels.py, vegetation.py, tree_matching.py    Optional input loaders + nearest-neighbour join
    ├── postcode6.py            CBS Postcode6 → nrg3:UrbanFunctionArea
    ├── _helpers.py             Shared helpers (type coercion, cache keys, gml:id sanitisation)
    ├── builders/               Per-feature builders (building, address, epc, vegetation)
    └── fetchers/               One module per remote source (BAG, 3DBAG, EP-online, Locatieserver, BGT, Emmen BOR, CBS, PDOK)

examples/
├── create_building.py          Per-building CLI + library entry point
├── create_city.py              City-scale CLI + library entry point (default INFO; -v drops to DEBUG)
└── create_address.py           Address-driven extract CLI (city pipeline; highlights the matched buildings)

tools/
├── generate_bindings.py            Regenerate bindings.py from XSD
├── generate_input_schema.py        Regenerate per-building JSON schema
├── generate_city_input_schema.py   Regenerate city-scale JSON schema
├── generate_pv_simulation.py       Compute NTA 8800 monthly PV-yield series
├── validate_xsd.py                 Offline XSD validation
├── reproduce.ps1                   One-command Docker reproduction (Windows)
├── reproduce.sh                    One-command Docker reproduction (Linux/macOS)
├── create_anonymised_sample.py     Produce the shareable sanitised sample input
├── merge_cftree_tiles.py           Merge CFTree CityJSON tile exports
├── audit_extra.py                  Audit generated GML: non-positive quantities, out-of-range angles, ADE hooks
├── audit_silent_bugs.py            Audit for silent data-loss bugs
├── bench.py                        Benchmarking utilities
└── schemas/xml.xsd                 W3C xml.xsd for offline validation

inputs/                         See inputs/README.md
├── buildings/                  Per-building feature-collection JSONs
├── stp/                        STEP geometry for the per-building JSONs
├── cities/                     City-scale configs
├── address/                    Address-driven extract profiles (city pipeline)
├── boundaries/                 GeoJSON AOI polygons
├── vegetation/                 CFTree LoD 3 tree meshes (CityJSON)
└── solar_panels/                Solar panel GeoPackage (UoG Zenodo 14860030, CC-BY-4.0)

schemas/
├── citygml_energy_input.schema.json   Generated per-building JSON schema
├── city_input.schema.json             Generated city-scale JSON schema
└── namespace_prefixes.json            Hand-maintained URI → prefix map

xsd/                            CityGML 2.0 + GML 3.1.1 + xLink + xAL (offline copies)
Energy_ADE-3.0beta8/            Energy ADE 3.0 beta8 XSD + Alderaan reference (Apache-2.0; see PROVENANCE.md)

tests/                          Per-building, city-scale, and infra tests
docs/
├── adr/                        Architecture decision records (0001-0003)
├── mapping_building.md         Per-building BAG / EP-online field-to-XSD mapping notes
├── mapping_city.md             City-scale data-source mapping + design notes
├── kitmodelviewer.md           One-time Energy ADE 3.0 schema swap for the KIT viewer
├── threedbag_sliver_walls.md   3DBAG near-zero-area wall handling
└── vegetation_integration_report.md   CFTree + BGT + BOR analysis

generated/                      Pipeline output (git-ignored)

.github/workflows/ci.yml        CI: ruff + ruff format + mypy + pytest (uv-based)
CITATION.cff                    Citation metadata (CFF 1.2.0)
LICENSE                         MIT licence for the toolkit
pyproject.toml                  Metadata, dependencies, ruff / mypy / pytest config
uv.lock                         Locked dependency graph
.python-version                 Pinned interpreter (3.12)
```

> The KITModelViewer install directory
> (`KITModelViewer_V7.5.2_Build-3777/`) may sit next to this repo for
> the §6 fix but is git-ignored and not part of the project.

---

## 6. KITModelViewer compatibility

The [KITModelViewer](https://www.iai.kit.edu/english/1266_4808.php) (KIT
IAI's CityGML and IFC viewer, successor to the FZKViewer) is a separate,
free download from KIT and is **not** bundled in this repository. Get it
from the KIT IAI page above, then apply the one-time schema swap below.

The viewer ships with an Energy ADE **2.0** schema, so GML files using
Energy ADE **3.0** will not display correctly until you swap in the 3.0
schema. The generated GML is XSD-valid either way; the swap only touches
your own viewer install, not this repo. The one-time procedure (plus the
symptoms it fixes) is in
[docs/kitmodelviewer.md](docs/kitmodelviewer.md).

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
round-tripped through the loader:

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

---

## 9. Reproducibility and environment

- **Pinned toolchain.** [.python-version](.python-version) fixes Python 3.12
  and [uv.lock](uv.lock) locks every transitive dependency, so `uv sync`
  rebuilds the tested environment exactly.
- **Continuous integration.**
  [.github/workflows/ci.yml](.github/workflows/ci.yml) runs `ruff check`,
  `ruff format --check`, `mypy`, and the full `pytest` suite on every push
  and pull request.
- **Offline validation.** `tools/validate_xsd.py` validates output against
  the CityGML 2.0 + GML 3.1.1 schemas in [xsd/](xsd/) and the Energy ADE 3.0
  beta8 schema in [Energy_ADE-3.0beta8/](Energy_ADE-3.0beta8/), with no
  network access.
- **Sample data.** The owner-occupier reference building ships as a sanitised
  JSON + STEP fixture (see
  [inputs/buildings/README.md](inputs/buildings/README.md)).
- **Reproducible container.** A pinned [Dockerfile](Dockerfile) builds the full
  runtime as a frozen image, so the toolkit runs with no local Python or uv
  install and validation behaves identically across hosts (see §9.1).

### 9.1 Reproducible container

The image pins its base by digest and resolves the environment from
[uv.lock](uv.lock), freezing the exact `lxml` / `libxml2` build that schema
validation depends on. CI publishes it to the GitHub Container Registry on each
release ([.github/workflows/docker.yml](.github/workflows/docker.yml)), and the
release pipeline runs the image offline to regenerate and validate the
per-building document before it publishes, so a release never ships an image
that fails to reproduce.

The fastest path is the one-command reproduction script, which pulls (or builds,
with `--build`) the image, regenerates the per-building document, and validates
it, all offline:

```powershell
.\tools\reproduce.ps1            # Linux/macOS: tools/reproduce.sh
```

Or run the steps directly:

```powershell
# Pull the published image (or `docker build -t citygml2.0-energyade3.0-beta8-creator:1.0.0 .` to build it)
docker pull ghcr.io/daanschlosser/citygml2.0-energyade3.0-beta8-creator:1.0.0

# Regenerate the offline per-building document into ./out (no network needed)
docker run --rm -v "${PWD}/out:/app/generated" ghcr.io/daanschlosser/citygml2.0-energyade3.0-beta8-creator:1.0.0

# Validate the result against the bundled XSDs, still offline
docker run --rm -v "${PWD}/out:/app/generated" ghcr.io/daanschlosser/citygml2.0-energyade3.0-beta8-creator:1.0.0 `
  python tools/validate_xsd.py generated/NL-single-family-house.gml
```

The city-scale pipeline needs network access and, for energy labels, an
EP-Online key. Mount your inputs and `.env`, then call `create_city.py`:

```powershell
docker run --rm --env-file .env `
  -v "${PWD}/inputs:/app/inputs" -v "${PWD}/generated:/app/generated" `
  ghcr.io/daanschlosser/citygml2.0-energyade3.0-beta8-creator:1.0.0 `
  python examples/create_city.py --input inputs/cities/emmer-compascuum_small-area_no-energy-labels.json
```

Optionally, for a registry-independent copy of the environment that rebuilds
even if the base image or wheels later change, archive the built image as a file
alongside the Zenodo code release:

```powershell
docker save ghcr.io/daanschlosser/citygml2.0-energyade3.0-beta8-creator:1.0.0 | gzip > citygml2.0-energyade3.0-beta8-creator-1.0.0-image.tar.gz
```

---

## 10. Licence and citation

This toolkit is released under the **MIT License** (see [LICENSE](LICENSE)).

The GML **datasets** produced by the toolkit (including the deposited 4TU
bundle) are a separate work, released under **CC-BY-4.0** and carrying their
own provenance and dataset DOI in the file-header comment; the MIT licence
above covers the toolkit code only. See the dataset README in the 4TU deposit
for the per-source attribution table.

Bundled third-party components keep their own licences:

- [Energy_ADE-3.0beta8/](Energy_ADE-3.0beta8/) is the CityGML Energy ADE 3.0
  (beta 8) schema set by Dr. Giorgio Agugiaro (TU Delft), redistributed
  unmodified under the **Apache License 2.0** (see
  [Energy_ADE-3.0beta8/LICENSE](Energy_ADE-3.0beta8/LICENSE) and
  [Energy_ADE-3.0beta8/PROVENANCE.md](Energy_ADE-3.0beta8/PROVENANCE.md)).
- The two tracked files under `KITModelViewer_V7.5.2_Build-3777/` support the
  Energy ADE 3.0 upgrade for the KIT viewer (see §6). `EnergyADE-local.xsd` is
  the same Apache-2.0 schema by Dr. Giorgio Agugiaro (an earlier beta 8
  vintage, with `<import>` URLs rewritten to local paths); `UOMList.xml` is the
  KITModelViewer's unit-of-measurement config, tracked in the version this
  project's emitted `@uom` tokens are checked against. The viewer itself is a
  separate KIT download and is not part of this repository. See
  [docs/kitmodelviewer.md](docs/kitmodelviewer.md) for the full provenance.
- The CityGML 2.0 / GML 3.1.1 / xAL / XLink schemas in [xsd/](xsd/) and the W3C
  [xml.xsd](tools/schemas/xml.xsd) are third-party standards (OGC, OASIS, W3C),
  redistributed for offline validation. Each keeps its original copyright
  notice; one file is modified and one was added by this project. See
  [xsd/PROVENANCE.md](xsd/PROVENANCE.md) for the licences and the exact changes.

To cite the software, use the metadata in [CITATION.cff](CITATION.cff) (GitHub
renders a "Cite this repository" button from it). The releases are archived on
Zenodo under the concept DOI
[10.5281/zenodo.20612452](https://doi.org/10.5281/zenodo.20612452), which always
resolves to the latest archived version; each release also has its own version
DOI (v1.0.1: [10.5281/zenodo.20669526](https://doi.org/10.5281/zenodo.20669526),
v1.0.0: [10.5281/zenodo.20612453](https://doi.org/10.5281/zenodo.20612453)). The
**DOI** badge at the top of this README resolves to the latest version, and
every archived version is listed on the
[Releases](https://github.com/DaanSchlosser/CityGML2.0-EnergyADE3.0_creator/releases)
page.
