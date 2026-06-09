# Per-building pipeline: JSON input → CityGML 2.0 / Energy ADE 3.0 mapping

**Purpose.** This document is the single answer to "where does field *X* land in the GML?" for the per-building pipeline (`citygml_energy.generation.generate_city_model`), which consumes hand-authored JSON feature collections plus STEP geometry files and emits a CityGML 2.0 + Energy ADE 3.0 file. Each per-class table enumerates the JSON fields **exercised by the canonical input** (and their GML targets); the loader additionally accepts every typed slot in the bindings, because `build_from_dict` introspects the dataclass fields directly. So the tables describe the contract for the canonical input shape; the underlying schema surface is wider. Required fields per class are catalogued in [Appendix A](#appendix-a--required-json-fields-per-feature-class) so authors do not discover them via build-time errors.

**Companion documents.**

- [`mapping_city.md`](mapping_city.md): the same level of per-field detail for the city-scale pipeline (BAG + 3DBAG + EP-Online + PV + CFTree + BGT + BOR + municipality + boundary). The two pipelines share the bindings and the `core.CityModel` object but consume different inputs and emit different feature subsets.
- [`README.md` § 3 / § 4 / § 5](../README.md): authoring guide, pipeline-stage walkthrough, and module reference. This document focuses on the *mapping*; the README covers the *mechanics* of the pipeline (when to run what, file layout, geometry source semantics).

**Reference inputs.** [`inputs/buildings/NL-single-family-house.json`](../inputs/buildings/NL-single-family-house.json) is the canonical thesis-grade input; [`inputs/buildings/NL-single-family-house_sample.json`](../inputs/buildings/NL-single-family-house_sample.json) is a placeholder-data clone for sharing in upstream issue trackers (KITModelViewer, etc.). Both share the same structural shape; this doc references both interchangeably.

## Conventions

| Concept | Meaning |
|---|---|
| **Native slot** | An XSD element typed for the value (e.g. `bldg:yearOfConstruction` is `xs:gYear`, `nrg3:Energy/amount` is `gml:MeasureType`). Native slots get the typed value. |
| **JSON feature** | One dict in the top-level `features` array, identified by `type` (e.g. `"bldg:Building"`, `"nrg3:Zone"`) and `id` (the GML id). Other dict keys are xsdata-style attribute names (`year_of_construction`) or XML names (`yearOfConstruction`); both are accepted. |
| **`parent` / `parent_field`** | Optional feature-level keys that direct child attachment. `parent` names the parent feature's `id`; `parent_field` disambiguates which of several candidate slots to attach into (e.g. `heating_schedule` vs `cooling_schedule` on a ZonePart). Children with no `parent` are model roots. |
| **`related_to`** | Pseudo-field on any CityObject-descended feature that lists `{"relation": str, "target": str | {"name": str, "lod": int}}` entries. Mirrors the Energy ADE 3.0 UML 1:1: each entry becomes one `nrg3:CityObjectRelation` with one `relationType` (the `relation` field, a member of `OtherRelationTypeValue.xml` such as `installedOn` or `serving`) and one `xlink:href` target. Resolved post-build by [`device_relations.apply_device_relations`](../citygml_energy/device_relations.py) using the [`RELATION_KINDS`](../citygml_energy/device_relations.py) registry, which dispatches on each kind's `target_kind` (surface-typed lookup with LoD collapse for `installedOn`; feature-id lookup for `serving`). |
| **`construction_mapping`** | Top-level block mapping each surface (by gml:id or by XSD type name) to a `nrg3:LayeredConstruction` library entry. Resolved post-build by the [`construction_mapping.EMITTERS`](../citygml_energy/construction_mapping.py) registration on the [`derived_attributes`](../citygml_energy/derived_attributes.py) seam: every dataclass with a `layered_construction` list field receives an xlink:href. |
| **Library xlink** | Materials and constructions live in JSON-authored library features (`nrg3:MaterialLibrary`, `nrg3:LayeredConstructionLibrary`). Layers reference materials via `{"href": "#mat_*"}`; surfaces reference constructions via the `construction_mapping` block. |
| **Cardinality of `identifier` / `validFrom` / `validTo` / `status`** | Beta8 removed `nrg3:AbstractFeatureWithLifeSpan` entirely and re-rooted every former subclass (Energy, Occupants, every TimeSeries, every Schedule, EnergyPerformanceCertificate, SolidMaterial, Gas, LayeredConstruction, Layer, …) under `core:AbstractCityObject` directly. All four fields are therefore multi-valued (`list[Identifier]`, `list[ValidFrom]`, `list[ValidTo]`, `list[Status]`) on every CityObject-descended feature, since they are substituted ADE-hook elements on `core:_GenericApplicationPropertyOfCityObject` whose substitution-group default permits unbounded occurrences. The **UML cardinality is 0..1** (`taggedValue tag="maxOccurs">1</taggedValue>` in the appinfo on each substituting element), so the engineering convention is single-element lists almost always; multiple entries are only XSD-legal, never UML-honest. Author as a scalar in JSON and the loader wraps it into a singleton list, or author as a list explicitly. |
| **`metadata` cardinality and placement** | `nrg3:Metadata` substitutes onto **two** XSD elements: the global `Metadata` element on `gml:metaDataProperty` (XSD line 347, typed `MetadataType`) *and* the `metadata` ADE-hook element on `core:_GenericApplicationPropertyOfCityObject` (XSD line 1260, typed `MetadataPropertyType`). The bindings expose a single `metadata: list[Metadata]` slot on every CityObject-descended type, and the loader writes there: the emitted XML is a direct `<nrg3:Metadata>` child of the host element (no `<gml:metaDataProperty>` wrapper around it), placed before `gml:description` / `gml:name` in the serialized output because xsdata orders fields by their declaration position on the dataclass. The slot is multi-valued: multiple Metadata blocks document multiple data sources for the same feature. |

## Pipeline order

[`generation.py::generate_city_model`](../citygml_energy/generation.py) is a thin wrapper over [`input_loader.load_city_model_from_feature_collection`](../citygml_energy/input_loader.py); the actual orchestration lives in [`input_loader.build_city_model_from_feature_collection`](../citygml_energy/input_loader.py), which drives:

1. **Load** the JSON via [`input_loader.load_feature_collection`](../citygml_energy/input_loader.py). Validates the schema (top-level keys, feature shapes, parent cycles, geometry-source paths, construction-mapping references), then resolves geometry-source paths against the input file's parent directory.
2. **Build** every feature into an xsdata dataclass via the schema-agnostic [`mapping.build_from_dict`](../citygml_energy/mapping.py). Two-phase: first construct + index by id, then attach children via [`mapping.attach_child`](../citygml_energy/mapping.py) (so a parent can appear after its child in the JSON).
3. **Apply geometry** via [`geometry.apply_geometry_sources`](../citygml_energy/geometry.py): import each STEP file, attach LoD slots to the right Building / ZonePart, build BoundarySurfaces / Openings from STEP layer names, populate the model's `surface_name_index`.
4. **Apply CityObjectRelation entries** via [`device_relations.apply_device_relations`](../citygml_energy/device_relations.py) (re-exported from [`geometry`](../citygml_energy/geometry.py) so the call site in `input_loader` reads `from .geometry import apply_device_relations`): resolve every `related_to` entry through the [`RELATION_KINDS`](../citygml_energy/device_relations.py) registry. The kind's `target_kind` selects the resolver path: `surface` looks up STEP layer names against the `surface_name_index` with LoD collapse (highest-LoD-wins; falls back to the gml:id index), `feature` resolves only against the gml:id index. Each entry emits one `nrg3:CityObjectRelation` with the kind's codelist member as `relationType` and the resolved gml:id as the `xlink:href` target. Unresolved references raise loudly. Stays on its own driver because its shape (iterate per-device JSON `related_to` lists and raise on missing keys) does not fit the model-walk seam used for the derived attributes below.
5. **Apply derived attributes** via [`derived_attributes.apply_derived_attributes`](../citygml_energy/derived_attributes.py) in one walk of the model, dispatching to per-ADE emitter registrations:
   - [`construction_mapping.EMITTERS`](../citygml_energy/construction_mapping.py): for each dataclass with a `layered_construction` list field, resolve a construction id via `by_id` (gml:id keyed) or `by_type` (XSD-element-name keyed) and append an xlink:href via the binding-resolved property-type wrapper.
   - [`boundary_attributes.EMITTERS`](../citygml_energy/boundary_attributes.py) + [`boundary_attributes.SETUPS`](../citygml_energy/boundary_attributes.py): compute up to six `bdgBdrySurf*` per BoundarySurface (`TotalSurfaceArea`, `OpaqueSurfaceArea`, `Inclination`, `Azimuth`, `Thickness`, `HeatCapacity`) and three `bdgOpn*` per Opening from the geometry and the layered-construction xlinks the construction emitter has just written. The setup hook pre-indexes the in-document `MaterialLibrary` and `LayeredConstructionLibrary` once per call so per-surface lookups are O(1).

   Registration order at the call site (construction first, boundary second) means that per object, the construction xlink is set before the boundary thickness / heat-capacity compute functions read it. Each emitter is idempotent on its own list field: already-populated lists are left untouched, so the seam can be re-run safely. Verification at the top of `apply` resolves every registered `field_name` against the loaded bindings and raises if a name no longer exists, catching XSD renames loud instead of letting them silently degrade the output.

Step 5 must run **after** step 3 (the geometry populates the polygon vertices the boundary emitters measure) and **after** step 4 in spirit (`device_relations` writes a different list field but is conceptually a sibling post-processor on the assembled tree). Every emitter is a no-op on features that lack the relevant data.

**Adding another ADE.** A new ADE (Scenario, Noise, …) means dropping a sibling module that exports its own `EMITTERS` (and optional `SETUPS`) list and appending them at the call site in `input_loader`. The seam itself does not change. The XSD pattern these emitters target (`<element substitutionGroup="..._GenericApplicationPropertyOf..."/>` becoming a `list[...]` field on every subclass of the target type) is shared across every CityGML ADE.

## At-a-glance: feature classes the pipeline knows

| JSON `type` | Bindings class | Where it parents | Native GML target |
|---|---|---|---|
| `bldg:Building` | `Building` | model root | `bldg:Building` (Pand or single building) |
| `nrg3:BuildingUnit` | `BuildingUnit` | Building | `nrg3:BuildingUnit` |
| `nrg3:Zone` | `Zone` | Building | `nrg3:Zone` |
| `nrg3:ZonePart` | `ZonePart` | Zone (enforced) | `nrg3:ZonePart` |
| `nrg3:ConstantValueSchedule` | `ConstantValueSchedule` | ScheduleLibrary (`library_member`, InLine); referenced from a ZonePart's `heating_schedule` / `cooling_schedule` by xlink | `nrg3:ConstantValueSchedule` |
| `nrg3:PhotovoltaicCollector` | `PhotovoltaicCollector` | Building (physical-structure-level: the panel array sits on the Pand, not inside any one occupied unit) | `nrg3:PhotovoltaicCollector` |
| `nrg3:SolarThermalCollector` | `SolarThermalCollector` | Building (same rooftop / physical-structure reasoning as PV; not exercised in the canonical input) | `nrg3:SolarThermalCollector` |
| `nrg3:HeatPump` | `HeatPump` | BuildingUnit (serves and meters the occupied unit) | `nrg3:HeatPump` |
| `nrg3:ThermalDistribution` | `ThermalDistribution` | BuildingUnit (per-unit distribution circuit) | `nrg3:ThermalDistribution` |
| `nrg3:ThermalStorageDevice` | `ThermalStorageDevice` | BuildingUnit (per-unit DHW buffer) | `nrg3:ThermalStorageDevice` |
| `nrg3:Boiler` | `Boiler` | BuildingUnit (per-unit heat source, analogue of HeatPump; not exercised) | `nrg3:Boiler` |
| `nrg3:EVChargingStation` | `EvchargingStation` | BuildingUnit (dedicated to the unit's occupants) | `nrg3:EVChargingStation` |
| `nrg3:GenericElectricalDevice` | `GenericElectricalDevice` | BuildingUnit (per-unit appliances; the XSD also permits Building) | `nrg3:GenericElectricalDevice` |
| `nrg3:Occupants` | `Occupants` | BuildingUnit | `nrg3:Occupants` |
| `nrg3:Energy` | `Energy` | any AbstractCityObject (Building, BuildingUnit, Device) via `nrg3:resource` | `nrg3:Energy` |
| `nrg3:MonthlyTimeSeries` / `nrg3:RegularTimeSeries` / `nrg3:IrregularTimeSeries` (and their `TypicalValues*` / `*File` variants) | corresponding TimeSeries class | Energy (`time_dependent_amount`) | `nrg3:*TimeSeries` |
| `nrg3:MaterialLibrary` | `MaterialLibrary` | model root | `nrg3:MaterialLibrary` (top-level library) |
| `nrg3:LayeredConstructionLibrary` | `LayeredConstructionLibrary` | model root | `nrg3:LayeredConstructionLibrary` (top-level library) |
| `nrg3:ScheduleLibrary` | `ScheduleLibrary` | model root | `nrg3:ScheduleLibrary` (top-level library; holds the schedule definitions referenced by ZoneParts) |

The list above is the set actually exercised in the canonical input. Any other Energy ADE 3.0 feature class declared in the bindings can also be authored: the pipeline's `build_from_dict` + `attach_child` machinery is XSD-driven and discovers field slots via type introspection, so adding a new feature requires no code changes (only a `type` value matching the bindings class). [`README.md` § 8](../README.md) maintains the live list.

## Top-level JSON shape

```json
{
  "file_header": "...provenance / licence banner...",
  "city_model": {"name": "...", "description": "..."},
  "coordinate_origin": [x, y, z],
  "construction_mapping": {
    "by_type": {"WallSurface": "constr_external_wall", ...},
    "by_id":   {"id_building_1_Door2_1": "constr_front_door", ...}
  },
  "geometry_sources": [
    {"type": "step-building-lod0", "path": "...", "target_building_id": "..."},
    {"type": "step-building-lod2", "path": "...", "target_building_id": "...", "target_pv_id": "..."},
    {"type": "step-zonepart-lod3", "path": "...", "target_zone_part_id": "..."}
  ],
  "features": [ /* the feature collection */ ],
  "srs_name": "urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109",
  "srs_dimension": 3
}
```

| Top-level key | Required | Purpose |
|---|---|---|
| `file_header` | optional | Free-text banner (copyright / provenance / read-me) emitted as an XML comment between the `<?xml ...?>` declaration and the root `<core:CityModel>` (schema-invisible). Validated non-empty and must not contain `--` (forbidden inside an XML comment). The reference building and both deposited GMLs use it. See [`schemas/citygml_energy_input.schema.json`](../schemas/citygml_energy_input.schema.json). |
| `city_model` | ✓ | Wrapper for `gml:name` and `gml:description` on the root `<core:CityModel>`. |
| `features` | ✓ | Flat list of feature dicts. Each dict carries `type`, `id`, optional `parent` / `parent_field` / `related_to`, and the XSD-typed attributes for that class. |
| `coordinate_origin` | optional (default `[0,0,0]`) | Offset added to every imported STEP vertex; lets STEP files authored at the origin land in real-world RD New / NAP coordinates. |
| `construction_mapping` | optional | See [§ Construction mapping](#construction-mapping). |
| `geometry_sources` | optional (no geometry if absent) | List of `{"type": "step-...", "path": "...", "target_*_id": "..."}` entries. Spec registry: [`geometry.GEOMETRY_SOURCE_SPECS`](../citygml_energy/geometry.py). |
| `srs_name`, `srs_dimension` | optional (defaults `urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109` and `3`) | Stamped on every `gml:Polygon` / `gml:MultiSurface` / `gml:Solid`. The default is the compound RD New + NAP CRS URN ([`namespaces.DEFAULT_SRS_NAME`](../citygml_energy/namespaces.py)). |

`_FEATURE_META_KEYS = {"type", "parent", "parent_field", "related_to"}` are stripped from each feature dict before `build_from_dict` sees it; all other keys are passed through to the dataclass coercer.

---

## 1. `bldg:Building`

The Pand-equivalent container. One per building file (the per-building pipeline is single-Pand by convention; multi-Pand inputs are accepted by the loader but the city pipeline is the right tool for that scope).

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `bldg:Building/@gml:id` | Required. NCName-validated. |
| `name` | list[str] | `gml:name[]` | |
| `description` | str | `gml:description` | |
| `creation_date` | date | `core:creationDate` | |
| `class_value` | CodeType | `bldg:class` | SIG3D codespace `_AbstractBuilding_class.xml` (residential / commercial / etc.). |
| `function` | list[CodeType] | `bldg:function[]` | SIG3D codespace `_AbstractBuilding_function.xml`. Multi-valued. |
| `usage` | list[CodeType] | `bldg:usage[]` | SIG3D codespace `_AbstractBuilding_usage.xml`. Multi-valued. |
| `year_of_construction` | gYear (string `"YYYY"`) | `bldg:yearOfConstruction` | `xs:gYear`. |
| `year_of_demolition` | gYear | `bldg:yearOfDemolition` | |
| `roof_type` | CodeType | `bldg:roofType` | SIG3D codespace `_AbstractBuilding_roofType.xml`. Same vocabulary as the city pipeline. |
| `storeys_above_ground` | int | `bldg:storeysAboveGround` | `xs:nonNegativeInteger`. |
| `storeys_below_ground` | int | `bldg:storeysBelowGround` | |
| `measured_height` | Measure | `bldg:measuredHeight` | uom `m`. |
| `identifier` | list[Identifier] | `nrg3:identifier[]` | `{value, code_space}`. The `code_space + value` concatenation should reconstruct a dereferenceable register URL: keep a trailing slash on `code_space` so `<base>/<id>` parses cleanly (the canonical input uses `http://bag.basisregistraties.overheid.nl/bag/id/pand/` for Pand and `.../verblijfsobject/` for VBO, matching [`citygml_energy.namespaces.CS_BAG_PAND`](../citygml_energy/namespaces.py) and `CS_BAG_VERBLIJFSOBJECT`). |
| `metadata` | list[Metadata] | `nrg3:Metadata[]` | `{author, acquisition_method, owner, quality_description, source}`. Multiple Metadata blocks document multiple data sources for the same Building. |
| `bdg_is_protected` | list[bool] | `nrg3:bdgIsProtected[]` | Heritage / conservation flag. |
| `bdg_number_of_building_units` | list[int] | `nrg3:bdgNumberOfBuildingUnits[]` | |
| `bdg_type` | list[CodeType] | `nrg3:bdgType[]` | Energy ADE primary building-type codelist (e.g. `singleFamilyHouse` from `BuildingTypeValue.xml`). The per-building pipeline can use either the Energy ADE codelist or the RVO Dutch verbatim term (the city pipeline uses the latter; either is schema-permissible because `gml:CodeType` is open and the `@codeSpace` names the vocabulary). |
| `bdg_area` | list[QualifiedArea] | `nrg3:bdgArea[]` (Building-level aggregate area) | Multi-source pattern: each entry wraps a `qualified_area` object, `{"qualified_area": {description, source, value: {value, uom}, type_value: {value, code_space}}}`. Repeating with different `source` strings is the documented way to record register vs measured values for the same physical quantity. |
| `bdg_height` | list[QualifiedHeight] | `nrg3:bdgHeight[]` | Same multi-source pattern, each entry wrapping a `qualified_height` object. `type_value` from `HeightTypeValue.xml` (`topOfConstruction`, `highestPoint`, `generalEave`, `bottomOfConstruction`, etc.; see the codelist for the full vocabulary). |
| `bdg_volume` | list[QualifiedVolume] | `nrg3:bdgVolume[]` | Same multi-source pattern, each entry wrapping a `qualified_volume` object. `type_value` from `VolumeTypeValue.xml` (`grossVolume`, etc.). |

All `bdgArea` / `bdgHeight` / `bdgVolume` values are themselves `QualifiedAttribute` (XSD line 227) and therefore carry their own `description` + `source` (so a downstream consumer can quantify how often two registers disagree on the same building's footprint area, for instance).

**Authoring `bldg:address`.** Addresses are emitted as children of the Building, not as a JSON field on the Building dict. Each VBO's address is authored as a separate top-level feature with `type: "core:Address"` and `parent: <building_id>`; the loader's two-phase build attaches it to `bldg:address[]` (CityGML 2.0 composition slot, `building.xsd` line 78). Each `nrg3:BuildingUnit` then declares an `address` field of the form `[{"href": "#<address_id>"}]` to xlink-reference its own address; see § 2 below. The XSD allows `bldg:address` to repeat (`[0..*]`), so a multi-VBO Pand emits one `core:Address` per VBO at Building level, each pointed at by exactly one BuildingUnit.

---

## 2. `nrg3:BuildingUnit`

Parents to a Building. One BuildingUnit per VBO-equivalent (apartment / commercial unit). The per-VBO BuildingUnit hosts the per-occupier energy-performance certificate (in city-pipeline runs) or any per-unit Occupants / Energy resources (in per-building runs).

The XSD permits `nrg3:energyPerformanceCertificate` on **both** AbstractBuilding (XSD line 1538) and BuildingUnit (XSD line 1438). Which slot the certificate parents to follows the [scope-based parent placement rule](../CONTEXT.md#scope-based-parent-placement): a certificate that describes one VBO parents to the corresponding BuildingUnit; a certificate that describes the whole Pand parents to the Building. For the NL canonical input that means BuildingUnit, because EP-Online's NTA 8800 issues one certificate per VBO (the BAG `verblijfsobject`, the legal usable-area unit inside a Pand). A multi-VBO Pand ends up with one EPC per unit, each with its own letter and registration-method metadata. For non-NL inputs whose register issues a single certificate per Pand (German EnEV, some older NL regimes), the same rule places the certificate on the Building. The pipeline does not enforce the rule; it is an authoring convention that follows from the cert's scope.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `nrg3:BuildingUnit/@gml:id` | |
| `name`, `description`, `creation_date` | as on Building | `gml:name`, `gml:description`, `core:creationDate` | |
| `identifier` | list[Identifier] | `nrg3:identifier[]` | |
| `type_value` | CodeType | `nrg3:type` | E.g. `woonfunctie` (BAG `gebruiksdoel` codespace) for a Dutch dwelling. |
| `number_of_rooms` | int | `nrg3:numberOfRooms` | |
| `owner_name` | str | `nrg3:ownerName` | |
| `ownership_type` | CodeType | `nrg3:ownershipType` | `OwnershipTypeValue.xml`. |
| `area` | list[QualifiedArea] | `nrg3:area[]` (BuildingUnit-level area) | Same multi-source pattern as Building's `bdgArea`, each entry wrapping a `qualified_area` object. Typically one entry for the per-VBO usable area. |
| `address` | `list[AddressPropertyType]` (xlink-only on the BuildingUnit) | `nrg3:address[]` carrying `@xlink:href` to a `core:Address` owned by the parent `bldg:Building` | The address itself is authored as a **separate top-level feature** of `type: "core:Address"` with `parent` set to the **Building** `id` (not the BuildingUnit). The loader's two-phase build attaches it to `bldg:address[]` (CityGML 2.0 composition slot, XSD `building.xsd` line 78). The BuildingUnit then declares `"address": [{"href": "#<address_id>"}]`, emitting a pure-xlink `nrg3:address` on the unit. This matches the Energy ADE 3.0 UML: `BuildingUnit.address` is tagged `relationType="association"` (XSD line 1431-1437), i.e. a pointer, not a composition. The address dict itself carries `xal_address.address_details.country.{country_name_code, country_name, locality.{locality_name, thoroughfare.{thoroughfare_number, thoroughfare_name}, postal_code.postal_code_number}}`, mirroring the xAL element tree. The full canonical-input shape lives in [`inputs/buildings/NL-single-family-house.json`](../inputs/buildings/NL-single-family-house.json) and the city pipeline's [`builders/address.py`](../citygml_energy/city_builder/builders/address.py) is the single source of truth on the xAL conventions (Locality/@Type=`Town`, Thoroughfare/@Type=`Street`, ISO 3166-1 alpha-2 country code, BAG-canonical hyphen separator for `huisnummertoevoeging`). The per-building pipeline does not auto-translate flat fields: author the nested form directly. |
| `energy_performance_certificate` | list[EPC] | `nrg3:EnergyPerformanceCertificate[]` (auto-wrapped in `nrg3:energyPerformanceCertificate` property element) | The EPC slot. See [`mapping_city.md` § 6](mapping_city.md#6-ep-online-mutatiebestand-csv-dutch-energy-label-register) for the regime-aware EP-Online mapping; the per-building pipeline authors an EPC directly in JSON with the same field shape (`type_value`, `label`, optional `value: {value, uom}`, optional `certification_method`, `creation_date`, `valid_from`, `valid_to`, `status`). The canonical input picks the schema-honest `totalEnergyDemand` for `type_value` (NTA 8800 EPCs cover the full building energy budget), `actual` for `status` (registered EP-Online certs are *rechtsgeldig*), and pins `value`'s uom to `kWh/m2/a` for an NTA 8800 cert. The **registration ID** lives on `nrg3:identifier` with `code_space=https://www.ep-online.nl/` to keep it dereferenceable; in the canonical input the EP-Online ID has been anonymised (replaced with placeholder digits) to protect the owner's privacy while preserving the BAG VBO ↔ EPC linkage shape. |

---

## 3. `nrg3:Zone` and `nrg3:ZonePart`

The Energy ADE 3.0 thermal-zone hierarchy is `Building → Zone → ZonePart`. The XSD permits `Building → ZonePart` directly via the `ZonePropertyType` slot, but the conceptual model says zones group zone-parts. The validator enforces `nrg3:ZonePart` parents to `nrg3:Zone` ([`input_loader._ALLOWED_PARENT_TYPES`](../citygml_energy/input_loader.py)) so authoring slips are caught before they corrupt the hierarchy.

Zone and ZonePart inherit from the same `nrg3:AbstractZoneType`, so **everything in the ZonePart table is also legal on a Zone** per the XSD: `is_heated`, `is_cooled`, `is_mechanically_ventilated`, `infiltration_rate`, `heat_capacity`, `internal_heat_gains` (+ convective / latent / radiant fractions), `number_of_building_units`, `building_unit`, `heating_schedule`, `cooling_schedule`, `mechanical_ventilation_schedule`, `zone_boundary`, plus the AbstractCityObjectSpace LoD slots (`lod0_multi_surface`, `lod{1,2,3}_solid`) and `area` / `volume`. The Zone table below lists only what the canonical input puts on the Zone level; richer authoring is permitted. The conceptual rule (Zone groups ZoneParts; thermal-envelope geometry and per-room schedules live on ZonePart, with the Zone aggregating across them) is a modelling convention, not an XSD constraint.

When the conditioning regime is modelled per ZonePart, the parent `nrg3:Zone` deliberately leaves `is_heated` / `is_cooled` / `is_mechanically_ventilated` **absent** (null, not false) and the two `nrg3:ZonePart` children each carry all three. Per the Energy ADE 3.0 author, modelling the parent zone with `false` flags while the parts say `true` is contradictory; leaving the parent null is the intended encoding.

### `nrg3:Zone`

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `nrg3:Zone/@gml:id` | |
| `name`, `description` | as above | `gml:name`, `gml:description` | |
| `type_value` | CodeType | `nrg3:type` | `CurrentUseValue.xml` (e.g. `residential`). |
| `coincides_with_lod2_hull` | bool | `nrg3:coincidesWithLod2Hull` | Whether the Zone spatially equals the building's LoD2 outer shell. |
| `coincides_with_lod3_hull` | bool | `nrg3:coincidesWithLod3Hull` | Same for LoD3. |
| `number_of_building_units` | int | `nrg3:numberOfBuildingUnits` | Count of BuildingUnits the Zone covers (the canonical Zone sets `1`). |
| `building_unit` | list[xlink] | `nrg3:buildingUnit[]` | xlink-only references to the BuildingUnits inside the Zone, e.g. `[{"href": "#id_building_unit_1"}]`. |

Geometry: Zones rarely carry their own geometry; their LoD geometry is usually inherited via the ZonePart children's surfaces.

### `nrg3:ZonePart`

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `nrg3:ZonePart/@gml:id` | |
| `type_value` | CodeType | `nrg3:type` | `CurrentUseValue.xml`. |
| `is_heated` | bool | `nrg3:isHeated` | |
| `is_cooled` | bool | `nrg3:isCooled` | |
| `is_mechanically_ventilated` | bool | `nrg3:isMechanicallyVentilated` | |
| `coincides_with_lod*_hull` | bool | as above | |
| `heating_schedule` | xlink, e.g. `{"href": "#zone_part_1_heating_schedule"}` | `nrg3:heatingSchedule xlink:href=…` | ByReference into the `nrg3:ScheduleLibrary`. See § 4. |
| `cooling_schedule` | xlink, e.g. `{"href": "#zone_part_1_cooling_schedule"}` | `nrg3:coolingSchedule xlink:href=…` | ByReference into the `nrg3:ScheduleLibrary`. See § 4. |
| `lod0_multi_surface` / `lod{1,2,3}_solid` | inline GML geometry | `nrg3:lod0MultiSurface` / `nrg3:lod{1,2,3}Solid` | Aggregate hull of the ZonePart. Populated from a `step-zonepart-lod{0,1,2,3}` source whose `target_zone_part_id` matches this ZonePart's `id`. ZonePart has no aggregated `volumeGeometry` slot; the standard CityGML LoD ladder fills the same role. |
| ZoneBoundary surfaces (children, attached via STEP geometry) | inline GML | `nrg3:zoneBoundary` (one ZoneWallSurface / ZoneGroundSurface / ZoneRoofSurface / ZoneIntermediateFloorSurface / etc. per ZonePart face; openings as `nrg3:ZoneWindow` / `nrg3:ZoneDoor` attached via the `nrg3:zoneOpening` relation on the parent face) | Built by `apply_geometry_sources` for `step-zonepart-lod{2,3}` sources from each STEP layer name. The classifier maps the building-style STEP layer names (`WallSurface_*`, `GroundSurface_*`, `RoofSurface_*`) to the matching `nrg3:Zone…Surface` subclass; `Window_*` / `Door_*` shells parented (via STEP `|parent=…`) to a wall become `nrg3:ZoneWindow` / `nrg3:ZoneDoor` children attached through the `nrg3:zoneOpening` relation on the matched ZoneWallSurface. |

ZonePart is the natural carrier of per-room thermal-envelope geometry: a multi-zone building (e.g. a heated living area + an unheated attic) maps to one `nrg3:Zone` per thermal regime and one `nrg3:ZonePart` per geometric subdivision inside it. The aggregate Solid and the per-face ZoneBoundary children are emitted together: a viewer that needs the closed hull uses the Solid, a thermal-analysis consumer iterates the ZoneBoundary children for per-face thermal-envelope attributes (the ADE `bdgBdrySurf*` attribute computation in [`boundary_attributes.py`](../citygml_energy/boundary_attributes.py) is binding-driven and runs against ZoneBoundary children too).

---

## 4. `nrg3:ScheduleLibrary` and `nrg3:ConstantValueSchedule`

The schedule definitions are **not** authored on the ZoneParts. They live inside a single top-level `nrg3:ScheduleLibrary` feature (parent: model root) as `library_member` entries — each member is a `{"constant_value_schedule": {...}}` wrapper, mirroring how `nrg3:MaterialLibrary` / `nrg3:LayeredConstructionLibrary` hold their members. Every ZonePart's `heating_schedule` / `cooling_schedule` field then carries an xlink reference `{"href": "#<schedule_id>"}` into that library, emitted as `<nrg3:heatingSchedule xlink:href="#…"/>`.

This is the Energy ADE 3.0 UML split: the schedule association on a thermal zone is tagged **ByReference** (so it must be an xlink), and the library association is **InLine** (the definitions live there). The XSD cannot enforce it — both `nrg3:heatingSchedule` and `libraryMember` are `AbstractSchedulePropertyType`, which accepts an inline child *or* an href — so authoring an inline schedule on a ZonePart still validates; keeping the definitions in the library is the modelling convention.

The `nrg3:ScheduleLibrary` itself takes `id`, optional `name` / `description`, a `type_value` of `{"value": "scheduleLibrary"}`, and a non-empty `library_member` list. Each `nrg3:ConstantValueSchedule` member:

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `nrg3:ConstantValueSchedule/@gml:id` | The xlink target referenced from the ZonePart. |
| `type_value` | CodeType | `nrg3:type` | `ScheduleTypeValue.xml` (`typicalYear`, etc.). |
| `value` | Measure | `nrg3:value` | uom `C` for setpoint temperatures. |

Energy ADE 3.0 defines three concrete `AbstractAtomicSchedule` subclasses (`nrg3:ConstantValueSchedule` (used here), `nrg3:DualValueSchedule` (idle / usage values with day-time switch points), and `nrg3:TimeSeriesSchedule` (wraps any `AbstractTimeSeries` so a periodic profile drives the schedule)), plus the aggregating non-atomic `nrg3:CompositeSchedule` (a sequence of `nrg3:ScheduleComponent` references, with per-component repetition counts and gaps) and the top-level wrapper `nrg3:ScheduleLibrary` that holds them. Any of these schedule types can be authored as a `library_member` of the `nrg3:ScheduleLibrary` and referenced from a zone by xlink (the ByReference form above); the generic builder also still accepts an inline schedule attached via `parent_field`, but the library form is the convention. Daily resolution is expressed as a `RegularTimeSeries` with `timeInterval = P1D` rather than a dedicated daily class; there is no `DailyPatternSchedule` or `DailyTimeSeries` in this XSD revision.

---

## 5. Devices

Six device types are exercised in the canonical input: `PhotovoltaicCollector`, `HeatPump`, `ThermalDistribution`, `ThermalStorageDevice`, `EVChargingStation`, `GenericElectricalDevice`. The two further device classes documented below (`SolarThermalCollector`, `Boiler`) are not exercised but documented for symmetry with the XSD. `Occupants` was previously colocated here in early revisions of this document; it is now [§ 6](#6-nrg3occupants), since `nrg3:Occupants` does **not** extend `nrg3:AbstractDevice` (it extends `core:AbstractCityObject` directly in beta8).

**Parent placement: Building vs BuildingUnit.** The XSD lets `nrg3:device` ride on any `core:_CityObject` (it substitutes onto `core:_GenericApplicationPropertyOfCityObject`, XSD line 1222), so Building, BuildingUnit, Zone, and any concrete CityObject all expose a `device` slot. Energy ADE's containment hierarchy is permissive here; the canonical input authoring choice is driven by the [scope-based parent placement rule](../CONTEXT.md#scope-based-parent-placement), which asks for the smallest entity whose extent fully covers the device's served scope. Applied to the canonical input:

- **`PhotovoltaicCollector` (and by analogy `SolarThermalCollector`) parents to the Building.** The panel array is physically attached to the Pand's roof, a fact about the structure rather than about who occupies it. This matches the Energy ADE Alderaan reference and is the placement the city pipeline's solar-panel matcher emits (see [`solar_panels.py::attach_solar_collectors_to_building`](../citygml_energy/city_builder/solar_panels.py)), so both pipelines produce isomorphic GML for PV. The same parent applies to any collective device whose served scope spans more than one VBO (a central boiler feeding a riser, a shared rooftop solar-thermal array, a communal EV charger). When the served set is a strict subset of the Pand's VBOs, the device still parents to the Building and emits `nrg3:relatedTo / CityObjectRelation` xlinks (relation type `serving`) to the covered BuildingUnits.
- **A per-unit device parents to the BuildingUnit it serves.** Heat pump, thermal distribution, thermal storage, boiler (if exercised), EV charger, and the per-unit electrical appliances each serve one VBO and meter that VBO's flows. For the canonical single-VBO Pand, this lands them all under the lone `nrg3:BuildingUnit`. For a multi-VBO Pand, each VBO carries its own per-unit device set.

The canonical input has nine device features under the BuildingUnit (HeatPump, ThermalDistribution, ThermalStorageDevice, EVChargingStation, and five `GenericElectricalDevice` appliances) and one under the Building (the PV collector); see [`tests/test_reference_building.py::test_devices_split_between_building_and_building_unit`](../tests/test_reference_building.py) for the assertion.

All device classes below extend `nrg3:AbstractDevice`, so they share inherited slots: `name`, `description`, `creation_date`, `model`, `year_of_installation`, `year_of_manufacture`, `number_of_devices`, `installed_power`, `nominal_efficiency`, `efficiency_indicator`, `heat_dissipation` (+ convective / latent / radiant fractions), `device_operation`, `identifier` (multi-valued via the CityObject regime), `metadata`, `valid_from` / `valid_to` / `status` (also multi-valued via CityObject regime), plus the JSON pseudo-field `related_to` (the ADE-hook list of `nrg3:CityObjectRelation` entries). They add device-specific slots on top. Energy ADE 3.0 has no `installed_in` slot; in-envelope vs outside-envelope placement has to be encoded via the `description` or via a project-defined `nrg3:CityObjectRelation` to the relevant Zone.

### 5.1. `nrg3:PhotovoltaicCollector`

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | |
| `name`, `description`, `creation_date`, `model`, `year_of_installation`, `number_of_devices`, `installed_power` (Measure, uom `W`) | inherited | inherited slots | |
| `azimuth` | Measure | `nrg3:azimuth` | uom `deg`, compass bearing of horizontal projection of the panel normal (0° = N). |
| `inclination` | Measure | `nrg3:inclination` | uom `deg`, [0, 90]. 0 = flat. |
| `cell_type` | CodeType (REQUIRED) | `nrg3:cellType` | `CellTypeValue.xml`. The canonical input emits `unknown` because the actual cell type was not on the panel datasheet collected from the owner-occupier; emitting a defaulted `monocrystalline` would over-report. |
| `module_area` | Measure | `nrg3:moduleArea` | uom `m2`. The total module area (number_of_devices × per-panel module area). The canonical input authors `module_area = 59.4 m²` for the 36-panel array (≈ 1.65 m²/panel, the typical footprint of a 270 Wp residential module from that era). |
| `nominal_efficiency` | Measure | `nrg3:nominalEfficiency` | uom `W/W` (dimensionless module efficiency). The canonical input authors `0.164`, consistent with 9720 W / 59.4 m² at 1000 W/m² STC; a typical-product estimate from the panel rating, not a measured datasheet figure. |
| `aperture_area` | Measure | `nrg3:apertureArea` | uom `m2`. The canonical input authors `55.8 m²`, the active light-receiving cell area (conventionally about 94% of the module footprint for crystalline-silicon panels of this generation). |
| `related_to` (pseudo-field) | list[{relation, target}] | resolved to `nrg3:relatedTo[] / CityObjectRelation` entries, one per list item, with `relationType` set from the entry's `relation` value | See [§ 10](#10-related_to-cityobjectrelation-entries). |
| `lod{2,3}_multi_surface` | inline GML MultiSurface | `nrg3:lod2MultiSurface` / `nrg3:lod3MultiSurface` | Populated from a `step-building-lod{2,3}` source whose `target_pv_id` matches this PV id; the per-LoD MultiSurface is built from the STEP shells classified as solar (layer-name prefix `SolarPanelSurface_`, or any shell that does not match the surface/opening taxonomy when the source has `target_pv_id` set, accommodating aggregated-array Rhino exports where the whole field is one unnamed `shell_1`). The XSD's `AbstractSolarCollectorType` defines geometry only at LoD2 and LoD3 (no LoD0 / 1 / 4). |

### 5.2. `nrg3:SolarThermalCollector`

Solar collector subclass (XSD class `nrg3:SolarThermalCollector`, **not** `SolarThermalSystem`). Inherits the LoD2/LoD3 MultiSurface slots, `azimuth`, `inclination`, `module_area`, `aperture_area` from `AbstractSolarCollectorType`. Adds the slots below; not exercised in the canonical input.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `type_value` | CodeType (REQUIRED) | `nrg3:type` | `SolarCollectorTypeValue.xml` (`flatPlate`, `evacuatedTube`, etc.). |
| `optical_efficiency` | Measure (`gml:ScaleType`, dimensionless [0, 1]) | `nrg3:opticalEfficiency` | The `η₀` zero-loss intercept of the collector's efficiency curve. |
| `linear_heat_loss_coefficient` | float | `nrg3:linearHeatLossCoefficient` | `a₁` in the EN 12975 efficiency curve, W/(K·m²). |
| `quadratic_heat_loss_coefficient` | float | `nrg3:quadraticHeatLossCoefficient` | `a₂` in the EN 12975 efficiency curve, W/(K²·m²). |

`nominal_efficiency` is inherited from `AbstractDevice` and remains available, but the EN 12975 triple (`opticalEfficiency`, `linearHeatLossCoefficient`, `quadraticHeatLossCoefficient`) is the schema-honest way to characterise a thermal collector: those three are what plug into the standard solar-thermal yield equation. Energy ADE 3.0 has **no** `heat_storage` or `peak_thermal_power` slot on this class; storage is modelled separately as a child `nrg3:ThermalStorageDevice` ([§ 5.7](#57-nrg3thermalstoragedevice)) and peak thermal output is implied by `installed_power` (inherited from `AbstractDevice`).

### 5.3. `nrg3:HeatPump`

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| inherited device fields | - | inherited slots | |
| `heat_source` | CodeType | `nrg3:heatSource` | `HeatSourceValue.xml`. Codelist values: `unknown`, `ambientAir`, `aquifer`, `exhaustAir`, `horizontalGroundCollector`, `verticalGroundCollector`. The `code_space` URL names the vocabulary; off-codelist values remain schema-permissible (`gml:CodeType` is open) but stay inside the codelist when a fitting term exists. |
| `cop_source_temperature` | Measure | `nrg3:copSourceTemperature` | uom `C`. |
| `cop_operation_temperature` | Measure | `nrg3:copOperationTemperature` | uom `C`. |
| `nominal_efficiency` | Measure | `nrg3:nominalEfficiency` | The COP at the (source temp, operation temp) pair above. |

**Mapping gap: in-envelope vs outside-envelope placement.** Energy ADE 3.0 has no native attribute on `AbstractDevice` (or any subclass) for whether a device sits inside the building's thermal envelope. For an in-envelope heat pump, pipework insulation, or a hot-water buffer, this fact has nowhere structured to live. The canonical input records it in `gml:description`; a more rigorous solution would be a `nrg3:CityObjectRelation` to the relevant `Zone` with a project-defined relation type, but the Energy ADE `OtherRelationTypeValue.xml` codelist (`installedOn`, `connectedTo`, `serving`) does not yet include an `isInsideThermalEnvelope`-style entry.

### 5.4. `nrg3:Boiler`

Inherited device fields plus a single Boiler-specific slot:

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `has_condensation` | bool (REQUIRED) | `nrg3:hasCondensation` | Whether the boiler is a condensing unit. |

`nominal_efficiency` (combustion efficiency) is inherited from `AbstractDevice`, not Boiler-specific. Energy ADE 3.0 has **no** `fuel_type` slot on Boiler; the fuel is encoded indirectly via the `energy_carrier` field on the Boiler's child `nrg3:Energy` resources (e.g. `naturalGas`, `electricity`). Boiler-emitted `nrg3:Energy` resources typically attach via `parent: "<boiler_id>"` so the demand reads as a property of the device. Not exercised in the canonical input.

### 5.5. `nrg3:EVChargingStation`

This device is the canonical input's example of a **post-construction addition**: the Pand was completed in 2020, the EV charger was installed in mid-2022. Energy ADE 3.0 has no `Intervention` / renovation-event class on `AbstractDevice`; the schema-honest way to record "added later than the Pand" is the pair (`year_of_installation` = the year, inherited from `AbstractDevice`) plus (`valid_from` = the dateTime the device entered service, an ADE-hook list element on every CityObject in beta8). Both ride on the device, not on the host surface, because the surface itself was not modified: only the device was added. See § 15 gap #6 for what an explicit `BoundarySurface/lifecycle` slot would buy.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| inherited device fields | - | inherited slots | |
| `year_of_installation` | int (gYear) | `nrg3:yearOfInstallation` | Inherited from `AbstractDevice`. The year the device was physically installed. |
| `valid_from` | dateTime (string `"YYYY-MM-DDTHH:MM:SS"`) | `nrg3:validFrom[]` | List-valued (ADE-hook element on every CityObject). The canonical input sets a single `valid_from` to the exact day the charger entered service (2022-07-18) so a downstream consumer can distinguish the device's lifecycle from the Pand's `bldg:yearOfConstruction` (2020). Authored as a scalar, the loader wraps it in a singleton list. |
| `type_value` | CodeType | `nrg3:type` | `EVChargingStationTypeValue.xml` (e.g. `AC`). |
| `charging_speed_level` | CodeType | `nrg3:chargingSpeedLevel` | `EVChargingSpeedLevelValue.xml`. The canonical input emits `Level 2` (the IEC 61851 / SAE J1772 Mode-3 AC speed bracket, 7-22 kW), which is the verbatim codelist member. |
| `connector_type` | CodeType | `nrg3:connectorType` | `EVChargingConnectorTypeValue.xml`. |
| `has_load_management` | bool | `nrg3:hasLoadManagement` | |
| `access_type` | CodeType | `nrg3:accessType` | `EVChargingAccessTypeValue.xml` (`private`, `public`, etc.). Renamed from `access` in beta8. |

### 5.6. `nrg3:ThermalDistribution`

Hydronic / air distribution circuit fed by a heat source. Exercised in the canonical input as the floor-heating circuit driven by the heat pump.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| inherited device fields | - | inherited slots | |
| `medium` | CodeType | `nrg3:medium` | `MediumTypeValue.xml` (`water`, `air`, `steam`, `unknown`). |
| `supply_temperature` | Measure | `nrg3:supplyTemperature` | uom `C`. The temperature delivered to the emitter side. |
| `return_temperature` | Measure | `nrg3:returnTemperature` | uom `C`. Optional; not collected in the canonical input. |
| `nominal_flow` | Measure | `nrg3:nominalFlow` | Optional. |
| `is_circulation` | bool | `nrg3:isCirculation` | Whether the circuit recirculates DHW (`true` for closed loops). Optional. |
| `distribution_perimeter` | CodeType | `nrg3:distributionPerimeter` | `DistributionPerimeterTypeValue.xml`. Optional. |
| `thermal_losses_factor` | Measure | `nrg3:thermalLossesFactor` | Optional. |

### 5.7. `nrg3:ThermalStorageDevice`

Hot- or cold-water buffer (DHW tank, ice store, etc.). Exercised in the canonical input as the 200-litre DHW buffer downstream of the heat pump.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| inherited device fields | - | inherited slots | |
| `medium` | CodeType | `nrg3:medium` | `MediumTypeValue.xml`. |
| `volume` | Volume | `nrg3:volume` | uom `m3`. Storage capacity. |
| `preparation_temperature` | Measure | `nrg3:preparationTemperature` | uom `C`. Optional. |
| `thermal_losses_factor` | Measure | `nrg3:thermalLossesFactor` | Optional. |

### 5.8. `nrg3:GenericElectricalDevice`

Catch-all for electrical appliances that have no dedicated Energy ADE class (cooktops, microwaves, dishwashers, kettles, coffee machines, etc.). The XSD adds **no** device-specific slots: a `GenericElectricalDevice` is exactly an `AbstractDevice` with no extras. Exercised in the canonical input as five appliance instances under the BuildingUnit. Useful for completeness even when no per-device energy figures are recorded: the `description` carries the human-readable identification of what the appliance is.

---

## 6. `nrg3:Occupants`

Parents to a `BuildingUnit` (not a Building): occupants are a property of a dwelling unit, not the structure. Beta8 re-rooted `nrg3:Occupants` under `core:AbstractCityObject` directly (the former `nrg3:AbstractFeatureWithLifeSpan` base was removed), so `identifier` / `valid_from` / `valid_to` / `status` are list-valued ADE hooks on every CityObject. The only XSD attachment point is the local `nrg3:occupiedBy` element inside `AbstractBuildingSpaceType` ([Energy_ADE_3.0_beta8.xsd:1400](../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd#L1400)), inherited by every `BuildingUnit` and `Zone`; the formerly-substituted global `nrg3:occupiedBy` onto `bldg:_GenericApplicationPropertyOfAbstractBuilding` was commented out in the 2026-05-14 beta8 update, so Buildings can no longer carry occupants directly. The canonical input parents to BuildingUnit, and the loader walks the XSD to land the occupant in `nrg3:occupiedBy` on the unit.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | |
| `type_value` | CodeType (REQUIRED) | `nrg3:type` | `OccupantsTypeValue.xml` (`residents`, `employees`, etc.). |
| `number_of_occupants` | int | `nrg3:numberOfOccupants` | The canonical input authors only this slot (plus `type_value`) and deliberately omits the cohort-statistical and thermal-load slots below: those data points were not collected from the owner-occupier survey, and authoring zero / placeholder values would silently bias any downstream thermal-comfort or social-energy model. The schema-honest signal for "we did not measure this" is **absent element**, not a defaulted one. |
| `heat_dissipation` | Measure | `nrg3:heatDissipation` | uom `W`, internal heat gain per occupant. *Not exercised in the canonical input* (see row above). |
| `heat_dissipation_convective_fraction` / `_latent_fraction` / `_radiant_fraction` | Scale (`gml:ScaleType`) | `nrg3:heatDissipation*Fraction` | Three-way split of `heat_dissipation` for thermal-comfort modelling; not exercised. |
| `average_diet_type` / `average_income_level` / `average_instruction_level` | CodeType | `nrg3:averageDietType` / `nrg3:averageIncomeLevel` / `nrg3:averageInstructionLevel` | Cohort-statistical attributes (`DietTypeValue.xml`, `IncomeLevelValue.xml`, `InstructionLevelValue.xml`); not exercised. The owner-occupier collection deliberately stops short of cohort statistics for privacy reasons. |
| `occupancy_schedule` (via child Schedule with `parent_field="occupancy_schedule"`) | xlink to AbstractSchedule | `nrg3:occupancySchedule` | The presence-fraction profile that scales `number_of_occupants` over time; not exercised. |

---

## 7. `nrg3:Energy` (resource)

Attaches via the `nrg3:resource` substitution slot on **any** `core:AbstractCityObject` (XSD line 1277). Every Building, BuildingUnit, Zone, and Device hosts it. The canonical input exercises three patterns:

- **Device-scoped Energy**: hangs off a device, describing the demand or production of that device. Examples: PV production on `pv_panel_1` (`operation_type=produces`); EV charging demand on `id_ev_charging_station_1` (`operation_type=demands`, `end_use=mobility`).
- **BuildingUnit-scoped house-wide Energy**: hangs off the VBO, describing whole-house net electricity consumption (smart-meter import readings). The canonical input's BuildingUnit carries one such resource (`operation_type=demands`, `end_use=otherOrCombination`, `energy_carrier=electricity`, 42-month `MonthlyTimeSeries`). This is the schema-honest place for total household consumption when no per-end-use breakdown was collected: `otherOrCombination` is the codelist member designed for "mixed end uses on a single carrier".
- **Building-scoped Energy**: would hang off the Building when an aggregate figure is recorded at Pand level rather than VBO level. Not exercised by the canonical input (single-VBO Pand → BuildingUnit is the natural carrier).

In city-pipeline inputs the dominant pattern is the second (BuildingUnit) one, because EP-Online ships per-VBO totals.

**`end_use` is required, even for production-side resources.** Energy ADE 3.0 makes both `type` and `endUse` mandatory on `EnergyType` (XSD lines 2048-2049), but `EnergyEndUseValue.xml` enumerates only consumption end-uses (`spaceHeating`, `domesticHotWater`, `lighting`, `electricalAppliances`, `mobility`, `otherOrCombination`, plus a handful of others). For an `operation_type=produces` resource, no codelist member names where the produced energy actually goes. The canonical input emits the off-codelist value **`gridFeedIn`** on the PV's `nrg3:Energy`, under the same `@codeSpace=EnergyEndUseValue.xml` (the project's stance on codelists treats them as suggestions, not enums, so off-codelist values are valid as long as the codespace names the relevant vocabulary). `gridFeedIn` names the activity exclusive to local generation and aligns with the EU / IEA standard terminology for renewable-energy export. See [§ 15.9](#159-no-production-side-member-in-the-energy-end-use-codelist) for the schema gap.

**`amount` is optional; the time-series can carry the data alone.** The canonical input's PV production `Energy` and the BuildingUnit consumption `Energy` both omit `amount` entirely and only emit `time_dependent_amount` (each a 42-month `MonthlyTimeSeries` covering Jan 2022 → Jul 2025; data source = smart-meter import / export readings, recorded in the time-series `description`). Schema-valid (`amount` is `minOccurs=0`), but downstream tooling that expects a scalar annual figure has to sum the values list itself.

**Tariff-1 / Tariff-2 (NL dual-tariff smart meters): combined vs split.** Dutch P1-port smart meters expose two billing-tariff totals: **tariff 1** (peak / *dag*, typically 07:00-23:00 weekdays) and **tariff 2** (off-peak / *nacht*, 23:00-07:00 + weekends). Energy ADE 3.0 has no native tariff dimension on `nrg3:Energy`. The canonical input **combines** the two into a single `Energy` resource on the BuildingUnit, summing both tariffs per month. This is the simpler shape and matches what most aggregators expect for "household consumption", but it loses the peak / off-peak signal that is increasingly relevant for renovation-passport workflows (dynamic tariffs, load-shifting analysis, grid-stress modelling). Authors who want to retain the tariff-level resolution should emit **two parallel `nrg3:Energy` resources** under the same BuildingUnit, both with `operation_type=demands`, `end_use=otherOrCombination`, `energy_carrier=electricity`, and per-tariff `MonthlyTimeSeries` children; the tariff label lives in `gml:description` (e.g. *"Tariff 1 (peak / dag)"* vs *"Tariff 2 (off-peak / nacht)"*) and optionally in a `nrg3:Metadata` block, since neither `nrg3:source` (which names the *generation* source: `powerGrid`, `photovoltaicPanels`, …) nor the `EnergyEndUseValue.xml` codelist carries a tariff axis. The two-resource pattern is schema-honest, lossless, and binding-compatible without code changes; it does double the feature count for the same physical meter and forces the "this is the same electricity, billed differently" framing to live in the descriptions rather than in a structural slot. A future Energy ADE revision adding a `nrg3:tariff` slot on `EnergyType` would let the distinction land natively.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | |
| `name`, `description`, `creation_date` | as above | `gml:name`, `gml:description`, `core:creationDate` | |
| `operation_type` | CodeType | `nrg3:operationType` | `ResourceOperationTypeValue.xml` (`demands`, `produces`). |
| `reference_period` | CodeType | `nrg3:referencePeriod` | `ReferencePeriodValue.xml` (`year`, `month`, `day`). |
| `amount` | Measure | `nrg3:amount` | The carrier of the value. uom must match the `reference_period`: `kWh/m2/a` or `MWh/a` for annual, `kWh` for monthly time-series amounts, etc. |
| `year` | int | `nrg3:year` | The year the figure refers to. |
| `is_amount_normalized` | bool | `nrg3:isAmountNormalized` | `true` when `amount`'s uom encodes a per-area (or per-volume / per-occupant) intensity; `false` for absolute totals. |
| `normalization_value` | Measure | `nrg3:normalizationValue` | Optional; the normaliser (e.g. the building's net floor area). Omitted when the uom string already encodes the basis (city-pipeline NTA 8800 emissions do this; § 6.3 in `mapping_city.md` documents the rationale). |
| `normalization_parameter` | str | `nrg3:normalizationParameter` | E.g. `"netFloorArea"`. |
| `type_value` | CodeType | `nrg3:type` | `EnergyTypeValue.xml`: `net`, `primary`, `final`. |
| `end_use` | CodeType | `nrg3:endUse` | `EnergyEndUseValue.xml`: `spaceHeating`, `spaceCooling`, `domesticHotWater`, `lighting`, `electricalAppliances`, `mobility`, `otherOrCombination`. |
| `energy_carrier` | CodeType | `nrg3:energyCarrier` | `EnergyCarrierValue.xml`: `electricity`, `naturalGas`, `districtHeat`, `solarThermal`, etc. |
| `source` | CodeType | `nrg3:source` | `EnergySourceValue.xml`: `powerGrid`, `photovoltaicPanels`, `boiler`, etc. |
| `maximum_load` | Measure | `nrg3:maximumLoad` | uom `kW`. Peak demand. |
| `co2_equivalent` | Measure | `nrg3:co2Equivalent` | Inherited from `AbstractResource` (XSD line 557). uom `kg/a` or `kg/m2/a` per the regime. |
| `time_dependent_amount` (via child TimeSeries with `parent_field="time_dependent_amount"`) | xlink to TimeSeries | `nrg3:timeDependentAmount` | See [§ 8](#8-time-series). |

---

## 8. Time series

Parents to an Energy resource (or any other AbstractResource subclass, or to a `nrg3:TimeSeriesSchedule`) via `parent_field="time_dependent_amount"`. Carries the periodic profile that backs the Energy's scalar `amount`.

Energy ADE 3.0 beta 8 defines six concrete TimeSeries classes documented below (plus six `*File` companions for out-of-line CSV / netCDF backed series, plus the related `nrg3:SensorConnection` element which inherits from the same `AbstractTimeSeriesType` but is intended to point at a live sensor stream rather than carry inline values; the loader accepts it via the same `parent_field` mechanism but the canonical input does not exercise it). There is **no** `DailyTimeSeries`. Daily resolution is expressed as a `RegularTimeSeries` with `timeInterval = P1D`.

| Class | When to use | Distinguishing fields |
|---|---|---|
| `nrg3:RegularTimeSeries` | Fixed sampling interval, arbitrary start / end timestamps. | `start_timestamp`, `end_timestamp`, `time_interval` (gml:TimeIntervalLengthType, e.g. `P1D` for daily, `PT1H` for hourly), `values_list`. |
| `nrg3:MonthlyTimeSeries` (canonical input) | Calendar-month sampling, dates rather than timestamps. | `start_date`, `end_date`, `values_list`. |
| `nrg3:IrregularTimeSeries` | Variable spacing between samples. | `uom`, `contains` (≥ 1 `TimestampedValue`, each carrying its own `time` and `value`). |
| `nrg3:TypicalValuesRegularTimeSeries` | Repeating typical-day / typical-week pattern at regular intervals. | `start_time` / `start_day` / `start_month` (optional), `temporal_extent`, `time_interval`, `values_list`. |
| `nrg3:TypicalValuesMonthlyTimeSeries` | 12 typical-month values (one per month). | `start_month` (optional), `temporal_extent`, `values_list`. |
| `nrg3:TypicalValuesIrregularTimeSeries` | Repeating typical-day pattern at irregular intervals. | `uom`, `contains` (≥ 1 `GenericTimeValue`, each carrying its own time-of-day / day-of-month / month and `value`). |

Fields below describe the canonical input's `MonthlyTimeSeries` shape; the other subclasses substitute their own start / end / cadence slots per the table above.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | |
| `description` | str | `gml:description` | |
| `interpolation_type` | str | `nrg3:interpolationType` | Inherited from `AbstractTimeSeries`; e.g. `averageInSucceedingInterval` (the 13 enumeration values are listed in the XSD `InterpolationTypeValueType` simpleType, line 81). |
| `start_date`, `end_date` | date | `nrg3:startDate`, `nrg3:endDate` | Required on MonthlyTimeSeries. |
| `values_list` | `{value: list[float], uom: str}` | `nrg3:valuesList` | One value per period; the period count must match `(end_date - start_date) / period`. The 42-monthly-value example in the canonical input covers Jan 2022 → Jul 2025. |

---

## 9. Material and construction libraries

Both libraries are JSON-authored top-level features (`parent` is absent). They hold the reusable `LayeredConstruction` and `Material` definitions; the actual surface-to-construction wiring happens via the top-level `construction_mapping` block ([§ 11](#11-construction_mapping-surface-to-construction-wiring)).

### 9.1. `nrg3:MaterialLibrary`

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | |
| `name`, `description`, `type_value` | as above | inherited | `type_value` typically `materialLibrary`. |
| `library_member` | list[`{solid_material}` or `{gas}`] | `nrg3:libraryMember[]` | Each member wraps one `SolidMaterial` or `Gas`. |

#### 9.1.1. `nrg3:SolidMaterial`

Authored as `{"solid_material": {...}}` inside `library_member`.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | The id used by Layer xlinks (`{"href": "#mat_*"}`). |
| `name`, `description`, `type_value` | as above | inherited | |
| `is_transparent` | bool | `nrg3:isTransparent` | True for glass; constrains the layer's role in opaque vs transparent assemblies. |
| `thermal_conductivity` | Measure | `nrg3:thermalConductivity` | uom `W/(K*m)`. The canonical input bracket-encloses the denominator (`W/(K*m)`, `J/(K*kg)`) on per-material thermal properties for SI-conformant readability; the older bracket-free `W/K*m` shape is still schema-permissible (no UOMList entry pins the bracket placement) but kept for the legacy `u_value` / `r_value` slots below to match the KIT UOMList tokens (`UVALUE` / `THERMAL_RESISTANCE` rows). |
| `density` | Measure | `nrg3:density` | uom `kg/m3`. |
| `specific_heat_capacity` | Measure | `nrg3:specificHeatCapacity` | uom `J/(K*kg)`. Same SI-bracket convention as `thermal_conductivity`. |

`density` and `specific_heat_capacity` together drive the per-surface heat-capacity computation in [`boundary_attributes.py`](../citygml_energy/boundary_attributes.py): a layer that omits either is excluded from the heat-capacity sum but **not** from the thickness sum (so a Gas pane in a window assembly contributes to total wall thickness without contributing to thermal mass; [§ 12](#12-boundary_attributes-per-surface-descriptors)).

#### 9.1.2. `nrg3:Gas`

Authored as `{"gas": {...}}` inside `library_member`.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id`, `name`, `description`, `type_value` | as above | inherited | |
| `is_ventilated` | bool | `nrg3:isVentilated` | |
| `r_value` | Measure | `nrg3:rValue` | uom `K*m2/W`. Insulating cavities pre-computed instead of derived from k / d / cp. |

### 9.2. `nrg3:LayeredConstructionLibrary`

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | |
| `name`, `description`, `type_value` | as above | inherited | |
| `library_member` | list[`{layered_construction}`] | `nrg3:libraryMember[]` | One construction per member. |

#### 9.2.1. `nrg3:LayeredConstruction1` (the construction itself)

Authored as `{"layered_construction": {...}}` inside `library_member`. The `1` suffix on the binding class is xsdata's de-collision suffix; XSD-wise this is `nrg3:LayeredConstruction`.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | The id referenced by `construction_mapping.by_type` / `by_id` and resolved to xlink:href on each surface. |
| `name`, `description`, `type_value` | as above | inherited | |
| `u_value` | Measure | `nrg3:uValue` | uom `W/K*m2`. The pre-computed conductance through the assembly. |
| `g_value` | Measure | `nrg3:gValue` | uom `scale`. Solar heat-gain coefficient (windows only). |
| `glazing_ratio` | Measure | `nrg3:glazingRatio` | uom `scale`. The glazed fraction of a window assembly's frame-plus-pane area. |
| `layer` | list[`{layer}`] | `nrg3:layer[]` | The ordered layer stack; first entry = inner face, last entry = outer face. |

#### 9.2.2. `nrg3:Layer` (one layer in the construction)

Authored as `{"layer": {...}}` inside the construction's `layer` list.

| JSON field | Type | GML target | Notes |
|---|---|---|---|
| `id` | str | `@gml:id` | |
| `description` | str | `gml:description` | |
| `thickness` | Measure | `nrg3:thickness` | uom `m`. |
| `material` | `{href: "#mat_*"}` | xlink to a SolidMaterial / Gas in the MaterialLibrary | Not validated at load time: [`input_loader._validate_construction_mapping`](../citygml_energy/input_loader.py) checks only the `construction_mapping` block's `by_type` / `by_id` construction ids, not layer `material` hrefs. A dangling material href is silently skipped during the per-surface heat-capacity computation ([`boundary_attributes`](../citygml_energy/boundary_attributes.py)) rather than raising. |

---

## 10. `related_to`: CityObjectRelation entries

Any feature whose XSD permits ADE relations can declare a list of `nrg3:CityObjectRelation` entries via the `related_to` pseudo-field. Each entry mirrors the Energy ADE 3.0 UML 1:1, with one `relationType` (the `relation` field, a member of the `RelationTypeValue` codelist family) and one `relatedTo` xlink target:

```json
{
  "type": "nrg3:PhotovoltaicCollector",
  "id": "pv_panel_1",
  "related_to": [
    {"relation": "installedOn", "target": "RoofSurface_01"},
    {"relation": "installedOn", "target": {"name": "RoofSurface_02", "lod": 3}},
    {"relation": "serving",     "target": "id_building_unit_1"}
  ],
  ...
}
```

The shape was chosen to match the data model at every layer (UML class, XSD type, GML serialisation, 3DCityDB schema-mapping all treat `CityObjectRelation` as a single polymorphic class discriminated by `relationType`; the Energy ADE 3.0 beta-4 UML changelog explicitly remodelled the previous N parallel association classes (installedOn was its own UML association before then) into this one polymorphic class). The JSON `relation` field equals the XML `relationType` value verbatim.

Resolved post-build by [`device_relations.apply_device_relations`](../citygml_energy/device_relations.py). Each entry's `relation` value is looked up in the [`RELATION_KINDS`](../citygml_energy/device_relations.py) registry; the registered kind names the codespace URL and selects the resolver path via its `target_kind`:

- **`target_kind="surface"`** (used by `installedOn`). The target is either a bare STEP layer name or an LoD-pinned `{"name": str, "lod": int}` object. The model-wide [`surface_name_index`](../citygml_energy/core.py) is keyed by `(STEP layer name, LoD level)`, so the same layer name appearing at multiple LoDs (e.g. `RoofSurface_01` present in both LoD2 and LoD3 STEPs) does not silently overwrite. The resolver collapses the LoD axis differently for the two entry shapes:
  - **Bare string** like `"RoofSurface_01"`: pick the highest LoD present for that name. When no STEP-name match exists, fall back to the gml:id-keyed feature index (so JSON can cite any indexable `gml:id` directly). The highest-LoD default matches the dominant consumer intent: an analysis that wants area or azimuth of the face a device sits on will want the most-detailed representation of that face.
  - **Object form** like `{"name": "RoofSurface_01", "lod": 2}`: pin the relation to the exact LoD's gml:id. No fallback to the gml:id index. Use this when the bare-name default is not what you want, e.g. when the same STEP layer name refers to different physical faces at different LoDs (the canonical pattern in this pipeline, since LoD3 routinely subdivides an LoD2 face and authors number sub-faces fresh per LoD; see ADR-0001).

- **`target_kind="feature"`** (used by `serving` and any other feature-targeted relation). The target is a plain gml:id string only; the `{name, lod}` object form is intentionally rejected because LoD has no meaning for a feature-id reference. STEP-name lookup is skipped entirely, so a typo against a STEP surface name raises rather than silently emitting a `serving` xlink to a surface gml:id.

Each entry emits one `nrg3:CityObjectRelation` with `relationType=CodeType(value=<entry.relation>, code_space=<kind.codespace>)` and the resolved gml:id as the related object. Author order in the JSON list is preserved as element order in the emitted `<nrg3:relatedTo>` siblings.

Unresolved refs raise `ValueError`: silent no-op would let JSON typos slip through as missing relations that nobody notices until a downstream consumer complains. Object-form entries with a missing LoD raise a focused error that lists the LoDs the name does resolve at (so the author can fix the LoD or drop the key). Features whose XSD type lacks a `related_to` list (i.e. the schema does not permit ADE relations on that type) raise loudly too.

The emitted GML is xlink-only; no geometry is duplicated. The resolved `xlink:href` is the auto-assigned `gml:id` from STEP import (which encodes the bindings class name, including xsdata's de-collision suffix, plus a per-type counter, e.g. `id_building_1_RoofSurface2_7`), not the author-facing STEP layer name:

```xml
<nrg3:relatedTo>
  <nrg3:CityObjectRelation>
    <nrg3:relationType codeSpace=".../OtherRelationTypeValue.xml">installedOn</nrg3:relationType>
    <nrg3:relatedTo xlink:type="simple" xlink:href="#id_building_1_RoofSurface2_7"/>
  </nrg3:CityObjectRelation>
</nrg3:relatedTo>
```

### Adding a new relation kind

The registry is the single edit point. Adding `connectedTo` (the third `OtherRelationTypeValue` member, suitable for device-to-device thermal-network connections) is one entry in [`device_relations.RELATION_KINDS`](../citygml_energy/device_relations.py):

```python
"connectedTo": RelationKind(
    codelist_value="connectedTo",
    codespace=CS_NRG3_OTHER_RELATION_TYPE,
    target_kind="feature",
),
```

The JSON-schema generator picks the new entry up automatically on the next regeneration. Topological members (`adjacentTo` / `sharedWith` from `TopologicalRelationTypeValue.xml`) slot in the same way, with `codespace=CS_NRG3_TOPOLOGICAL_RELATION_TYPE` and `target_kind="feature"`.

---

## 11. `construction_mapping`: surface-to-construction wiring

The top-level `construction_mapping` block declares which surfaces / openings carry which `LayeredConstruction`. Two routing strategies are tried in order:

```json
"construction_mapping": {
  "by_type": {
    "WallSurface": "constr_external_wall",
    "GroundSurface": "constr_ground_floor",
    "RoofSurface": "constr_reed_roof",
    "Window": "constr_window_hr",
    "Door": "constr_back_door"
  },
  "by_id": {
    "id_building_1_Door2_1": "constr_front_door",
    "id_building_1_Door2_2": "constr_front_door"
  }
}
```

Resolved post-build by the [`construction_mapping.EMITTERS`](../citygml_energy/construction_mapping.py) registration on the [`derived_attributes`](../citygml_energy/derived_attributes.py) seam. The seam walks every dataclass instance reachable from the model's GML root and, for each instance:

1. If the instance has a `layered_construction` list field (per the bindings) AND the field's element type is the `nrg3:layeredConstruction` property-type wrapper, it becomes a candidate target.
2. The construction id is resolved by:
   - first trying `by_id[instance.gml_id]` (specific override),
   - then falling back to `by_type[instance.xsd_element_name]` (e.g. `"WallSurface"`). The key is the **XSD element name** taken from the dataclass `Meta.name` (or the class name when `Meta.name` is absent; see [`construction_mapping._xsd_type_name`](../citygml_energy/construction_mapping.py)). xsdata's de-collision suffix (the `2` in `WallSurface2` / `Door2` etc.) is **not** part of the key: author against the schema element name (`WallSurface`, `Door`, `Window`, `RoofSurface`, `GroundSurface`, `ZoneWallSurface`, ...), never against the binding's class name.
3. The xsdata-generated property-type wrapper class (resolved at runtime via [`construction_mapping._layered_construction_ref_cls`](../citygml_energy/construction_mapping.py), so the doc does not hardcode a class name; xsdata's de-collision suffix on the wrapper class can shift between binding regenerations) is instantiated as an `xlink:href` reference and appended to the field's list. The serialized form is:

```xml
<nrg3:layeredConstruction xlink:href="#constr_external_wall" xlink:type="simple"/>
```

**Binding-driven scope.** Every class with a `layered_construction: list[…PropertyType]` field in the bindings receives mapping coverage automatically: the discovery walk visits every dataclass instance reachable from the model root and inspects its fields ([`construction_mapping._compute_layered_construction`](../citygml_energy/construction_mapping.py)). The surface-class set is therefore controlled by the XSD, not by a hand-maintained taxonomy in `construction_mapping.py`. The CityGML 2.0 thematic surfaces (`bldg:WallSurface`, `bldg:GroundSurface`, `bldg:RoofSurface`, `bldg:Window`, `bldg:Door`) all carry the field. So do the Energy ADE ZoneBoundary subclasses (`nrg3:ZoneWallSurface`, `nrg3:ZoneGroundSurface`, `nrg3:ZoneRoofSurface`, `nrg3:ZoneIntermediateFloorSurface`, etc.).

**`by_type` keys are exact XSD element names.** A `by_type` entry of `"WallSurface"` matches `bldg:WallSurface` only, *not* `nrg3:ZoneWallSurface`, which has a different XSD element name. Authors who want zone-side surfaces to carry a layered construction must add explicit `by_type` entries or use `by_id`. The canonical input does exactly this: `by_type` keys the zone classes too (`"ZoneWallSurface": "constr_external_wall"`, `"ZoneGroundSurface": "constr_ground_floor"`, `"ZoneRoofSurface": "constr_reed_roof"`, `"ZoneWindow": "constr_window_hr"`, `"ZoneDoor": "constr_back_door"`), so every zone boundary surface carries a construction xlink and emits the `Thickness` and `HeatCapacity` per-surface attributes computed in [§ 12](#12-boundary_attributes-per-surface-descriptors), matching the Alderaan reference. See [§ 12.1](#121-per-surface-attributes-boundarysurface) for why the `nrg3:Zone*Surface` family is the schema-intended carrier of the construction in Energy ADE 3.0 (which has no separate `ThermalBoundary` class).

**Validation.** [`input_loader._validate_construction_mapping`](../citygml_energy/input_loader.py) checks at load time that every construction id referenced by `by_type` / `by_id` exists as a library member in some `LayeredConstructionLibrary` feature; an unmapped id raises before the build phase starts.

---

## 12. `boundary_attributes`: per-surface descriptors

After geometry and construction mapping have run, the [`boundary_attributes.EMITTERS`](../citygml_energy/boundary_attributes.py) registration on the [`derived_attributes`](../citygml_energy/derived_attributes.py) seam computes a fixed set of Energy ADE 3.0 `bdgBdrySurf*` and `bdgOpn*` attributes from the attached LoD MultiSurface and the resolved layered constructions. This is the per-building pipeline's main quantitative deliverable for surface-level thermal analysis. A single `SETUPS` hook pre-indexes the in-document `MaterialLibrary` and `LayeredConstructionLibrary` once per call so per-surface lookups are O(1).

### 12.1. Per-surface attributes (BoundarySurface)

Emitted on every `bldg:_BoundarySurface` (WallSurface / GroundSurface / RoofSurface / FloorSurface / OuterFloorSurface / OuterCeilingSurface / ClosureSurface) that carries an LoD MultiSurface.

| Element | Computed from | uom | Skipped when |
|---|---|---|---|
| `nrg3:bdgBdrySurfTotalSurfaceArea` | exterior-ring area minus *true geometric holes* (interior rings that do not match any child opening's exterior ring; e.g. courtyards, tower intrusions). Interior rings punched into the parent wall to host a Window/Door opening are **not** subtracted: the total is the underlying face before openings are deducted. | `m2` | no LoD MultiSurface |
| `nrg3:bdgBdrySurfOpaqueSurfaceArea` | `Total − Σ child_opening.bdgOpnArea`. Uses the opening's own MultiSurface area, not the parent's interior-ring area, so standalone-shell openings (LoD3+ without an interior ring on the parent) are handled correctly. | `m2` | no openings (the absence is the schema-honest signal that opaque area = total) |
| `nrg3:bdgBdrySurfInclination` | angle between the outward normal and `+Z`: `0` for a flat roof, `90` for a vertical wall, `180` for a horizontal floor whose outward normal points down. Taken from the largest-area polygon in the surface's MultiSurface. | `deg` (range [0, 180]) | degenerate geometry (sub-µm edge scale) |
| `nrg3:bdgBdrySurfAzimuth` | compass bearing of the outward normal's horizontal component (0° = N). | `deg` (range [0, 360)) | surface is effectively horizontal (azimuth geometrically undefined) |
| `nrg3:bdgBdrySurfThickness` | Σ `Layer.thickness` over every layer of the LayeredConstruction the surface's `layeredConstruction` xlink points at. | `m` | no construction mapped, OR no layer has a thickness |
| `nrg3:bdgBdrySurfHeatCapacity` | areal thermal mass: `Σᵢ thicknessᵢ · densityᵢ · cpᵢ / 1000` over every solid layer. Layers whose material lacks `density` or `specificHeatCapacity` (e.g. Gas argon panes) are excluded from the sum but **not** from `Thickness`. | `kJ/(K*m2)` | no solid layer carries both `density` AND `specificHeatCapacity` |

**Zone-side surfaces emit the full set.** `nrg3:ZoneWallSurface` / `ZoneGroundSurface` / `ZoneRoofSurface` (and the other `Zone*Surface` subclasses) carry the same `bdg_bdry_surf_*` fields as their `bldg:*` counterparts, so the discovery walk in [§ 12.4](#124-discovery-mechanism) reaches them too. They emit `TotalSurfaceArea`, `OpaqueSurfaceArea` (when openings are present), `Inclination`, `Azimuth`, and, because the canonical `construction_mapping.by_type` now keys the zone surface classes too (`"ZoneWallSurface": "constr_external_wall"`, `"ZoneGroundSurface": "constr_ground_floor"`, `"ZoneRoofSurface": "constr_reed_roof"`), also `Thickness` and `HeatCapacity`. This matches the Alderaan reference, which attaches a `nrg3:layeredConstruction` to every zone boundary surface and zone opening: the `nrg3:Zone…Surface` is the thermal boundary in this Energy ADE 3.0 revision (the schema has no separate `ThermalBoundary` class), so it is the schema-intended carrier of the construction. The same construction is shared with the `bldg:*` thematic surface at the same physical face. Both families therefore carry the layer stack and the area attributes; an aggregator must pick **one** family before summing `bdgBdrySurfTotalSurfaceArea` or heat capacity, or it double-counts the envelope (see [§ 13.1](#131-per-lod-distinct-boundarysurfaces-and-the-modelling-rules-question)).

**XSD slots not computed by this pipeline.** `nrg3:bdgBdrySurfIsShared` (party-wall flag) and `nrg3:bdgBdrySurfAdditionalThermalBridgeUValue` (junction-correction U-value) are defined on `bldg:_BoundarySurface` in the Energy ADE 3.0 XSD but the boundary-attributes computation does **not** populate them. They can be authored inline on the BoundarySurface JSON dict (the schema-agnostic loader will accept them), but no implicit derivation runs: the canonical input leaves them unset because the reference building is free-standing (no shared walls) and no thermal-bridge survey was conducted. See [§ 15 gap #1](#15-schema-gap-analysis-per-building-specific) for the XSD context. Similarly, the four sky / ground view-factor slots (`bdgBdrySurfGroundViewFactor`, `bdgBdrySurfSkyViewFactor`, `bdgOpnGroundViewFactor`, `bdgOpnSkyViewFactor`) are XSD-defined but not computed by the pipeline.

### 12.2. Per-opening attributes (Window / Door, ZoneWindow / ZoneDoor)

Same definitions as the boundary-surface analogues, computed from the opening's own `lod{0..4}MultiSurface`. The `bdgOpn*` family applies equally to the building openings `bldg:Window` / `bldg:Door` and to the zone openings `nrg3:ZoneWindow` / `nrg3:ZoneDoor`: the zone opening classes inherit the `bdg_opn_area` family from the same `bldg:_Opening` base, so the binding-driven discovery in [§ 12.4](#124-discovery-mechanism) reaches both.

| Element | Computed from | uom |
|---|---|---|
| `nrg3:bdgOpnArea` | sum of Polygon areas in the opening's MultiSurface | `m2` |
| `nrg3:bdgOpnInclination` | angle between outward normal and `+Z` | `deg` |
| `nrg3:bdgOpnAzimuth` | compass bearing of outward normal | `deg` (omitted when horizontal) |

Openings deliberately do not get `Thickness` / `HeatCapacity` / `Opaque`: those are defined per assembly, not per opening face. The window's layered construction (`constr_window_hr` in the canonical input) carries the layered build-up; the per-surface attributes summarise it once at the wall level.

### 12.3. uom + precision conventions

Pinned to the existing project conventions ([`boundary_attributes.py`](../citygml_energy/boundary_attributes.py) `_UOM_*` and `_DEC_*` constants):

| Quantity | uom | precision |
|---|---|---|
| Areas | `m2` | 3 dp |
| Lengths | `m` | 3 dp |
| Angles | `deg` (project convention; KIT UOMList, [iai.kit.edu/uomList](https://www.iai.kit.edu/uomList), also publishes `grad` as the German-language token for the same unit, but every emitted file in this project uses `deg` for cross-language readability) | 2 dp |
| Heat capacity | `kJ/(K*m2)` | 3 dp |

`kJ/(K*m2)` is the SI-conformant areal heat capacity token (`k` = kilo prefix, `K` = kelvin per BIPM SI Brochure §3.1; ISO 13786 building-physics convention is identical); a typical wall sits at 50-500 kJ/(K·m²), so `J/(K·m²)` would push values to 5-6 digits. Coordinates entering this module were quantised to a micrometre grid in [`gml_builders.build_polygon`](../citygml_energy/gml_builders.py); precision past these would be spurious.

### 12.4. Discovery mechanism

Binding-driven: any dataclass that has a `bdg_bdry_surf_total_surface_area` *list* field is treated as a boundary-surface emit target; any class with a `bdg_opn_area` field is an opening target. Regenerating the bindings with new surface or opening classes therefore picks up matching emissions automatically.

The function is a no-op for any surface or opening that has no LoD multisurface, an unrecognised construction xlink, or a degenerate (zero-area) polygon. It does not write placeholder values; an absent attribute on the output is the schema-honest signal that the value could not be derived from the inputs.

### 12.5. Relationship to the city pipeline

The city-builder uses an analogous geometry-only path ([`builders/building.py::_attach_planar_surface_ade_attributes`](../citygml_energy/city_builder/builders/building.py)) that fills `Total` / `Inclination` / `Azimuth` from 3DBAG LoD2 polygons. That path **stops there**: the city pipeline has no source of layered constructions, so `Thickness` / `HeatCapacity` are deliberately absent. The per-building pipeline supersedes the city path for the additional thickness + heat-capacity computation; the two are not run together because a building authored in JSON does not also pass through the city builder.

---

## 13. Geometry sources

JSON cannot author 3D geometry inline (the wire format would be unusable). Geometry comes from STEP files referenced under the `geometry_sources` list. The full registry lives in [`geometry.GEOMETRY_SOURCE_SPECS`](../citygml_energy/geometry.py); the table below covers what the canonical input exercises.

| `type` | Target field | Output GML element | Notes |
|---|---|---|---|
| `step-building-lod0` | `target_building_id` | `bldg:lod0FootPrint` | Single MultiSurface (the footprint polygon). |
| `step-building-lod1` | `target_building_id` | `bldg:lod1Solid` | Solid (assembled via `gml_builders.build_solid`). |
| `step-building-lod2` | `target_building_id`, optional `target_pv_id` | thematic `bldg:boundedBy` (one BoundarySurface per STEP layer name); optionally `nrg3:lod2MultiSurface` on the PV collector if `target_pv_id` matches an authored PV feature. | **No `bldg:lod2Solid` is emitted**: only the per-face `boundedBy` children are. A consumer that wants the closed hull at LoD2 must assemble it from the boundary surfaces. The STEP layer names (`WallSurface_01`, `RoofSurface_03`, etc.) drive both the BoundarySurface gml:id assignment and the `surface_name_index` that surface-targeted `related_to` entries (e.g. `installedOn`) resolve against. |
| `step-building-lod3` | `target_building_id`, optional `target_pv_id` | thematic `bldg:boundedBy` (with Window/Door openings punched into walls); optional `nrg3:lod3MultiSurface` on the PV collector. | **No `bldg:lod3Solid` is emitted.** The pipeline matches each Window/Door child to its parent wall by exterior-ring vertex equality (rounded to 0.1 mm) and emits an interior ring on the wall plus the opening as a `bldg:Opening`. |
| `step-zonepart-lod0` | `target_zone_part_id` | `nrg3:lod0MultiSurface` | Aggregate footprint of the zone part. No per-face surfaces. |
| `step-zonepart-lod1` | `target_zone_part_id` | `nrg3:lod1Solid` | Aggregate hull. No per-face surfaces. |
| `step-zonepart-lod{2,3}` | `target_zone_part_id` | `nrg3:lod{2,3}Solid` (aggregate hull) **plus** `nrg3:zoneBoundary` children (one `nrg3:Zone…Surface` per STEP layer name; openings attached via `nrg3:zoneOpening` as `nrg3:ZoneWindow` / `nrg3:ZoneDoor`). | The classifier maps building-style STEP layer names to their `nrg3:Zone…Surface` and `nrg3:Zone…Opening` equivalents (single source of truth: [`geometry._BLDG_TO_ZONE_NAME_REMAP`](../citygml_energy/geometry.py)): `WallSurface_*` → `ZoneWallSurface`, `GroundSurface_*` → `ZoneGroundSurface`, `RoofSurface_*` → `ZoneRoofSurface`, `CeilingSurface_*` → `ZoneOuterCeilingSurface`, `FloorSurface_*` → `ZoneOuterFloorSurface`, `IntermediateFloorSurface_*` → `ZoneIntermediateFloorSurface`, `ClosureSurface_*` → `ZoneClosureSurface`. The same remap also promotes the opening names: `Window_*` → `ZoneWindow`, `Door_*` → `ZoneDoor`, so opening shells parented (via STEP `\|parent=…`) to a wall attach as `nrg3:ZoneWindow` / `nrg3:ZoneDoor` children routed through the `nrg3:zoneOpening` relation of the matched ZoneWallSurface (not the inherited `bldg:opening` slot). The aggregate Solid is still emitted for viewers that want a closed hull; the per-face children carry the `bdgBdrySurf*` thermal-envelope attributes for analysis consumers. **Inter-floor slabs** that sit fully indoors (e.g. the slab between an upstairs and a downstairs ZonePart of the same heated envelope) belong to `ZoneIntermediateFloorSurface`, not to either `Zone…Floor` or `Zone…Ceiling` *Outer* class: those Outer subclasses are reserved for surfaces whose other side faces ambient air or unheated space. |
| `step-building-lod4` | `target_building_id` | Same shape as `step-building-lod3` but on the `lod4MultiSurface` slot. | Registered in [`geometry.GEOMETRY_SOURCE_SPECS`](../citygml_energy/geometry.py) for completeness; not exercised by the canonical input (LoD 4 = full interior detail; out of scope for the renovation-passport use case). The aggregate `lod4Solid` is **not** emitted (same shape as LoD2/3); only thematic `bldg:boundedBy` children with `lod4MultiSurface`. **`target_pv_id` is *not* accepted on this source type**: the registry's PV-target slot is wired only for LoD2 and LoD3 ([`geometry.py`](../citygml_energy/geometry.py): `if lod in (2, 3): target_fields["target_pv_id"] = _PV_TARGET`). LoD 4 PV geometry would need a separate registry entry. |

STEP layer names attached under a **building source** (`step-building-lod{2,3,4}`) are registered in `model.surface_name_index[(layer_name, lod)] = surface.gml_id`; this is what makes a JSON entry like `{"relation": "installedOn", "target": "RoofSurface_01"}` resolve. ZonePart-source faces (`step-zonepart-lod{2,3}`) are deliberately **not** indexed (`register_surface_name_index=False` in [`geometry._apply_zonepart_boundary_surfaces`](../citygml_energy/geometry.py)): zonepart faces are an internal thermal-envelope description, not the publicly-attachable surface vocabulary that devices physically sit on. Indexing them under the same STEP layer names would silently overwrite the building-source entries (the canonical input has `RoofSurface_01` shells in *both* the LoD3 building export and the upstairs ZonePart export). A roof-mounted PV is therefore `installedOn` the building's `bldg:RoofSurface`, never on a ZonePart's `nrg3:ZoneRoofSurface`. Author-facing layer names are not duplicated into the GML (the `gml:id` is what gets written); the index only exists in memory for the duration of the build.

### 13.1. Per-LoD distinct BoundarySurfaces (and the modelling-rules question)

The canonical input drives both `step-building-lod2` and `step-building-lod3` against the same `target_building_id`. The pipeline emits **one `bldg:_BoundarySurface` per (physical face, LoD)**: the LoD2 STEP shells produce one `bldg:WallSurface` / `bldg:GroundSurface` / `bldg:RoofSurface` per polygon with a `bldg:lod2MultiSurface`, and the LoD3 STEP shells produce a separate set of thematic surfaces with `bldg:lod3MultiSurface` (and Window / Door openings). Each set has independent gml:ids.

**This is intentional**, not a duplication bug: the LoD2 hull and the LoD3 hull are not the same surfaces. LoD3 splits a single LoD2 façade into multiple smaller faces (a wall around windows + door, a chimney face, a dormer cheek), so the count of thematic surfaces *and* their per-face areas / azimuths legitimately differ between LoDs. Collapsing them into one BoundarySurface with both `lod2MultiSurface` and `lod3MultiSurface` populated would force the document to assert that the LoD2 face and the LoD3 face represent the same thematic surface, which is false when LoD3 subdivides.

CityGML 2.0 itself permits both shapes: one BoundarySurface carrying multiple LoD MultiSurfaces, **or** distinct BoundarySurfaces per LoD. Both are XSD-valid. The choice is a project-level modelling rule, not something the schema settles. Consequences for downstream consumers:

- **Per-building totals**: a sum over `bdgBdrySurfTotalSurfaceArea` includes both LoD2 and LoD3 contributions and double-counts the underlying physical envelope. Filter by LoD before aggregating.
- **Surface-targeted `related_to` resolution**: the `surface_name_index` is keyed by `(STEP layer name, LoD level)`, so the same layer name appearing at multiple LoDs is preserved end-to-end. A bare-string target in JSON (e.g. `{"relation": "installedOn", "target": "RoofSurface_01"}`) resolves to the highest LoD present for that name. The order of entries in `geometry_sources` therefore does not affect resolution. Authors who need to target a specific LoD (e.g. when the same layer name refers to different physical faces at different LoDs, which is the dominant pattern) use the explicit `{"name": "RoofSurface_01", "lod": 2}` object-form target documented in [§ 10](#10-related_to-cityobjectrelation-entries).
- **Per-face thermal attributes**: `bdgBdrySurfThickness` / `bdgBdrySurfHeatCapacity` are construction-driven and identical across LoDs (same `constr_external_wall` xlink). `bdgBdrySurfTotalSurfaceArea` differs: LoD2 is the simpler hull, LoD3 has the openings deducted via the opaque-area mechanism ([§ 12.1](#121-per-surface-attributes-boundarysurface)).

**Modelling rules will need to be written** to make these choices explicit for downstream users (which LoD's surfaces to consume for energy analysis, how to dedupe in totals, when collapsing into one BoundarySurface is appropriate vs when keeping LoDs distinct preserves a real semantic distinction). That is out of scope for this mapping doc; the point here is just to flag that "one BoundarySurface per (face, LoD)" is a *deliberate* shape, not an accident.

---

## 14. Cross-pipeline comparison

| Aspect | Per-building pipeline | City pipeline |
|---|---|---|
| **Input source** | Hand-authored JSON feature dicts + STEP geometry files | Config file naming a Dutch municipality; fetches BAG + 3DBAG + EP-Online + PV + CFTree + BGT + (optional) BOR |
| **Layered constructions** | Full support: MaterialLibrary + LayeredConstructionLibrary authored in JSON; layer thickness, thermal conductivity, density, specific heat capacity all explicit; per-surface mapping via `construction_mapping`. | None: city pipeline has no source for layered constructions; only EP-Online label + per-VBO Energy resources. |
| **Devices (Boiler / HeatPump / PV / EVChargingStation / SolarThermal)** | Fully modelled: separate JSON features per device, wired with `related_to` CityObjectRelation entries (installedOn / serving), Energy resources and device-specific parameters. | Partial: rooftop solar arrays only (from the optional UoG GeoPackage), emitted as technology-agnostic `nrg3:GenericSolarCollector` rather than `nrg3:PhotovoltaicCollector` because the aerial-imagery source has no cell-type metadata; heat sources inferred from EP-Online label, not modelled as Device objects. |
| **Thermal zones and zone parts** | Full: `Zone` → `ZonePart` hierarchy, LoD3 boundary surfaces from STEP, heating/cooling schedules, occupant loads on zone parts. | None: city pipeline does not author Zones at all. |
| **Boundary surface attributes** | Six per-surface attributes computed (`Total` / `Opaque` / `Inclination` / `Azimuth` / `Thickness` / `HeatCapacity`) plus three per-opening (`Area` / `Inclination` / `Azimuth`). | Three per-surface attributes (`Total` / `Inclination` / `Azimuth`); no opaque-area or thickness/heat-capacity (no source). |
| **Energy resources** | Devices carry Energy for demand / production; BuildingUnit can carry occupant heat; user-authored per device + per building. | BuildingUnit carries EP-Online energy flows (regime-aware: kWh/(m²·yr) for NTA 8800, MJ/yr for legacy). See `mapping_city.md` § 6. |
| **EP-Online integration** | Possible but manual: EPC values can be authored directly under each BuildingUnit in JSON. | Automatic: 20 of 42 EP-Online columns mapped, regime-aware emission, multi-VBO canonical-pick logic. |
| **Geometry LoD levels** | Up to LoD3 for buildings (step-building-lod0/1/2/3) + LoD3 for zone parts. Hand-modelled STEP files; quality is whatever the STEP author achieved. | LoD0 / 1.2 / 2.2 from 3DBAG. No hand-modelled geometry; all procedural. |
| **Appearance** | Author-controlled via JSON (per-feature `app:Appearance` xlinks via the schema-agnostic dict-to-dataclass coercer). | Three pipeline-controlled themes: `energyLabel` (per-Building EU palette colour from EPC letter), `solarPanels` (constant deep blue), `vegetation` (constant foliage green). |
| **Address (`core:Address`)** | Authored as a separate top-level feature parented to the Building; emitted under `bldg:address` (CityGML 2.0 composition slot, `building.xsd` line 78). Each `nrg3:BuildingUnit` xlink-references its own address via `nrg3:address/@xlink:href` (Energy ADE 3.0 UML tags `BuildingUnit.address` as `relationType=association`, XSD line 1431-1437, i.e. a pointer, not a composition). The canonical input includes one address (Julianalaan 134, 2628 BZ Delft, used as a stand-in for the actual owner-occupier address, which is held privately). See § 2 for the JSON shape and Appendix A for the required-fields cross-check. | Same ownership pattern: one `core:Address` per BAG VBO authored once at Building level under `bldg:address`, each `nrg3:BuildingUnit` xlink-references its own address. Always populated from BAG VBO with full Dutch xAL structure. |

The two pipelines are complementary: per-building authors a single, deeply-modelled building; city builds a large stock of shallowly-modelled buildings. Output GMLs from both pipelines validate against the same XSDs and can be merged downstream.

---

## 15. Schema gap analysis (per-building specific)

This section catalogues gaps that affect the per-building pipeline specifically.

1. **No native slot for inter-surface view factors.** Energy ADE 3.0's `BoundarySurface` has slots for `bdgBdrySurfTotalSurfaceArea`, `bdgBdrySurfOpaqueSurfaceArea`, `bdgBdrySurfThickness`, `bdgBdrySurfHeatCapacity`, `bdgBdrySurfInclination`, `bdgBdrySurfAzimuth`, `bdgBdrySurfIsShared`, `bdgBdrySurfAdditionalThermalBridgeUValue`, **plus** `bdgBdrySurfGroundViewFactor` and `bdgBdrySurfSkyViewFactor` (with `bdgOpnGroundViewFactor` / `bdgOpnSkyViewFactor` siblings on the opening side, XSD lines 1963-2014). What is **missing** is a per-surface-pair view factor: the geometric visibility coefficient between two specific surfaces inside the model, used in long-wave radiative coupling and detailed daylighting. The sky / ground pair captures the dominant terms for a typical residential thermal model; an inter-surface coupling matrix would need a new association type. Workaround: emit as `gen:doubleAttribute name="viewFactor_<otherSurfaceId>"` per pair.

2. **`nrg3:Layer` has no `r_value` slot for solid materials.** Gas materials carry `r_value` (XSD line 2798) directly, but solid materials must be characterised via `thermal_conductivity` + `density` + `specific_heat_capacity` and have their R-value derived. For older renovation work where the thermal properties of an existing wall are *measured* (in situ R-value via heat-flux meters) but the layer composition is unknown, the model has to pretend the wall is one homogeneous layer with synthetic conductivity / density. Workaround: write the synthetic material plus a `gen:stringAttribute` describing the in-situ measurement provenance.

3. **`construction_mapping` is global across all surfaces of a Pand**, not per-storey or per-orientation. A building with different external-wall constructions on the ground floor vs upper floors must encode each individually via `by_id`; there is no regex or multi-criteria matching. This is a tooling limitation rather than a schema gap, and acceptable because per-floor constructions are rare in residential renovation work; commercial or mixed-use buildings would need either richer mapping syntax or pre-resolved per-id entries.

4. **No native slot for renovation-scenario branches.** A Building Renovation Passport stores both the *current* state of the building and one or more *proposed* renovation states (different insulation thicknesses, different heating systems, etc.). Energy ADE 3.0 has no concept of a scenario branch; the only schema-permissible way to encode "what would the heat capacity be if the wall were re-insulated to 200mm mineral wool" is to author multiple `LayeredConstruction` library entries and switch the `construction_mapping` between them by hand.

5. **`nrg3:Layer.material` xlink can only point at a SolidMaterial or Gas, not a composite.** Modern building envelopes increasingly use *engineered* assemblies that are themselves layered (e.g. an insulation panel with integrated vapour barrier and finish layer) but treated as a single product line. The schema models them as the inner layered build-up, which means a manufacturer's product catalogue cannot be one-to-one mapped onto a single `Material` entry. Workaround: expand the engineered assembly into its constituent layers in the JSON; the loss of "this is one product" framing is currently carried by the `description` field on the construction.

6. **No native slot for installation date on the BoundarySurface.** A wall built in 1955 and re-insulated in 2018 has two relevant dates (the structural age and the thermal-envelope age). `core:creationDate` records when the *dataset record* was created, not when the structure was built; `bldg:yearOfConstruction` is on the Building level. A renovation passport that needs per-surface ages must author them as `gen:dateAttribute name="thermalEnvelopeRenovationDate"`.

7. **No native slot for layer-level material variants.** A `Layer` can xlink to one Material, but cannot easily encode "this layer is mineral wool + 2% binder" or "this layer is reclaimed timber sourced from..." style provenance / sustainability data. The Material itself could carry such metadata in its `description`, but the granularity is coarser than `Layer`. Workaround: extend the description.

8. **Device-to-surface relations are ambiguous along two axes when the same physical face is modelled at multiple LoDs.** See [§ 10](#10-related_to-cityobjectrelation-entries) and the LoD-aware-resolver ADR (`docs/adr/0001-installed-on-lod-aware-resolver.md`) for the authoring rule and rationale; the gap is part schema, part modelling discipline, and it appears every time a device touches a face that has been re-modelled at higher detail.

9. **No production-side member in the energy-end-use codelist.** `nrg3:Energy` requires `endUse` (XSD line 2049), but `EnergyEndUseValue.xml` enumerates only consumption end-uses (`spaceHeating`, `domesticHotWater`, `lighting`, `electricalAppliances`, `mobility`, `otherOrCombination`, and a handful of others). For a `produces`-typed resource (PV electricity, battery discharge, locally generated district heat being exported), no member describes where the produced energy goes. The canonical PV emits the off-codelist value `gridFeedIn` under `@codeSpace=EnergyEndUseValue.xml`; this is schema-valid because `gml:CodeType` is open, and matches the international standard term for renewable-energy export (EU / IEA *feed-in*, German *Netzeinspeisung*, Dutch *teruglevering*).

---

## 16. Canonical input data gaps

This section catalogues places where the canonical owner-occupier input ([`inputs/buildings/NL-single-family-house.json`](../inputs/buildings/NL-single-family-house.json)) is incomplete or approximate. Gaps are split into two types:

- **16a (Estimated values)**: the spec or source data did not supply a figure, so a typical or derived value was used. The model serialises cleanly but the flagged values should be confirmed before being relied on for thermal analysis.
- **16b (Not yet modelled)**: the spec supplies the data clearly but it has not been authored into the JSON, either because there is no matching LOD3 surface to attach it to or because the feature class has not been added yet.

### 16a. Estimated values

1. **Reed thatch thickness and thermal properties (`mat_reed_thatch`, layers `constr_reed_roof_L6` and `constr_uninsulated_reed_roof_L3`).** The arch. spec lists the 'SPORENDAKEN TPV RIET' variants with 15 mm OSB3 as the outermost named layer; the reed thatch itself (which sits on top of the OSB3) is not given a thickness or product reference. The canonical input uses 300 mm / λ=0.09 W/(m·K) / ρ=190 kg/m³, all typical values for a Dutch rieten dak from published literature. To resolve, obtain the thatching contractor's datasheet or carry out an in-situ thickness measurement and update both the material entry and the two affected construction layers.

2. **Ground-floor insulation product and acoustic layer (`constr_ground_floor`, layers `constr_floor_L4` and `constr_floor_L2`).** *(Partially resolved 2026-05-05.)* Build-up confirmed from the owner-occupier's CAD drawing as a kanaalplaatvloer: 192 mm insulation below slab | 260 mm kanaalplaatvloer | 20 mm decoupling layer | 70 mm screed with vloerverwarming. Computed Rc≈6.10 m²K/W. Remaining open: (a) the exact EPS product below the slab is unnamed, so the thermal conductivity of 0.036 W/(m·K) is a typical EPS value; (b) the 20 mm full-black layer (ontkoppelingslaag) between slab and screed is inferred as an acoustic decoupling board, with the actual product (PE-foam, EPS acoustic, rubber mat) unconfirmed. Neither affects macro-level thermal performance significantly.

3. **Outer wall cladding 'DCV' (`mat_dcv_cladding`, layer `constr_ext_wall_L8`).** *(Partially resolved 2026-05-05.)* Owner-occupier confirmed the DCV cladding is timber. Canonical input already modelled as a generic 22 mm timber cladding (λ=0.13 W/(m·K)). Remaining open: exact timber species, board profile, and surface finish were not specified.

4. **Membrane thermal properties (`mat_pe_vapour_barrier`, `mat_morgo_vent_120`, `mat_morgo_top_solar`).** The arch. spec names three membranes (PE folie 0.15 mm dampremmende laag, Morgo-Vent 120 3-laags PP-spunbond, Morgo Top Solar underlayment) but provides no per-product datasheet figures for thermal conductivity, density, or heat capacity. The canonical input uses generic polymer-membrane values (λ ≈ 0.33-0.40 W/(m·K), ρ ≈ 200-950 kg/m³). At sub-millimetre thickness the contribution to the assembly's Thickness and HeatCapacity attributes is negligible (<1 %), so this gap is cosmetic.

5. **Door-leaf build-up (`constr_front_door_L1`, `constr_back_door_L1`).** The arch. spec states only frame-included U-values ('Voordeuren U=1,43 W/m²K incl. kozijn'; 'Achterdeuren U=1,64 W/m²K incl. kozijn'). The canonical input uses a single solid timber-leaf placeholder (54 mm / 48 mm); the `u_value` on the construction is the authoritative thermal figure. The actual leaf composition (insulation core, glazed inserts, hardware cut-outs) is unspecified and would need the door-supplier's datasheet for an honest layer build-up.

### 16b. Not yet modelled

1. **Uninsulated reed sub-roof geometric extent (`constr_uninsulated_reed_roof`).** The arch. spec lists 'SPORENDAKEN TPV RIET opbouw (ongeisoleerd)' (rafters 36x196 mm + 15 mm OSB3, no insulation, no inner cladding) alongside the insulated reed and PV variants, consistent with an unheated overhang or thatched canopy. The canonical input declares the construction in the library but no `RoofSurface_*` in the current LOD3 STEP geometry is mapped to it via `construction_mapping.by_id`. To resolve: identify which (if any) STEP layers correspond to uninsulated overhangs and add the appropriate `by_id` entries.

2. **Internal walls and intermediate floors (library-only).** The arch. spec details four interior build-ups: stability walls (11 mm spaanplaat V313 + 38x89 mm vuren cavity), partition walls (38x89 mm vuren studs only), 1st-floor deck (38x285 mm vuren joists + 18 mm OSB3 veer-en-groef), 2nd-floor deck (38x270 mm vuren joists + 18 mm OSB3). The canonical input declares all four as `constr_stability_internal_wall`, `constr_internal_wall`, `constr_first_floor`, `constr_second_floor` so the build-up is in the audit trail, but none is mapped to geometry: the LOD3 envelope carries only external `WallSurface` / `RoofSurface` / `GroundSurface`. A future LOD4 (`bldg:Room` + interior boundary surfaces) authoring pass should reuse these library entries. The spec also leaves internal-wall finish materials unspecified; cavities are modelled as ventilated air for now.

3. **Frame-included window U-value ('Kozijn incl. glas U=variabel min. 1,65 W/m²K').** The arch. spec gives a frame+glass combined U-value floor of 1.65 W/(m²·K), distinct from the centre-of-glass U=1.1 stored on `constr_window_hr`. Energy ADE 3.0's `LayeredConstruction` carries one `u_value`; the frame-included figure is not separately stored. A consumer needing it must combine `u_value`, `glazing_ratio`, and per-surface area attributes; it cannot read it directly.

4. **WTW balanced heat-recovery ventilation system.** The arch. spec states 'Ventilatievoorzieningen: mechanische toevoer en afvoer d.m.v. een gebalanceerd WTW systeem op basis van CO2-sturing.' Energy ADE 3.0 beta8 has no air-distribution or mechanical-ventilation device class (the only distribution devices are `nrg3:PowerDistribution` and `nrg3:ThermalDistribution`), and no `heatRecovery` attribute anywhere in the schema. Mechanical ventilation is representable only as the `isMechanicallyVentilated` flag and the `mechanicalVentilationSchedule` aggregation on a zone (`AbstractZoneType`), not as a device. The WTW unit itself would therefore have to be modelled as an `nrg3:GenericElectricalDevice` parented to the BuildingUnit, with the heat-recovery efficiency and CO2-controlled operation carried as `gen:*Attribute` values (no native slots); the recovery efficiency is not in the spec extract and would need the unit's datasheet.

5. **Performance-only specs without a native Energy ADE slot.** The arch. spec includes several regulatory compliance figures: 'EPC bouwbesluit-eis 0,4 (nul op de meter woning)', 'Politiekeurmerk klasse 2' anti-burglary rating, 'Equivalente daglichtoppervlakte ≥10 % V.G.' per NEN 2057, 'Karakteristiek geluidsniveau max. 30 dB', 'Hoofddraagconstructie 60 min. brandwerend', and 'Project onder FSC: JA / SKH-COC-000076 claim FSC mix'. The EPC figure is captured via `nrg3:EnergyPerformanceCertificate`; the remainder have no native slot in Energy ADE 3.0 and would need `gen:stringAttribute` / `gen:doubleAttribute` workarounds on `bldg:Building` or the relevant material/construction entry.

---

## Code reference legend

The `Implementation` columns reference Python identifiers in the modules linked at the top of each section. `mapping_building.md`, like its city counterpart, is parsed by [`tests/test_mapping_index_in_sync.py`](../tests/test_mapping_index_in_sync.py) so that renaming a referenced symbol fails the test until the doc is updated.

---

## Appendix A: Required JSON fields per feature class

This is the catalogue of fields the XSD makes mandatory (no `minOccurs="0"`) per class, so an author writing a new feature can budget the minimum payload up front instead of discovering omissions through build-time errors. All fields beyond `id` (which is mandatory on every gml-rooted feature via `gml:id`) come from the per-class XSD complexType or its inherited bases. Fields marked **(REQUIRED via inherited type)** sit on an abstract ancestor.

| JSON `type` | Required JSON fields (besides `id`) |
|---|---|
| `bldg:Building` | (none on bldg:BuildingType: every native slot is `minOccurs="0"`) |
| `nrg3:BuildingUnit` | `type_value` |
| `nrg3:Zone` | `type_value` |
| `nrg3:ZonePart` | `type_value` |
| `nrg3:ConstantValueSchedule` | `type_value` (REQUIRED via inherited `AbstractScheduleType`), `value` |
| `nrg3:PhotovoltaicCollector` | `cell_type` |
| `nrg3:SolarThermalCollector` | `type_value` |
| `nrg3:HeatPump` | `heat_source` |
| `nrg3:Boiler` | `has_condensation` |
| `nrg3:EVChargingStation` | `type_value` |
| `nrg3:ThermalDistribution` | (none) |
| `nrg3:ThermalStorageDevice` | (none) |
| `nrg3:GenericElectricalDevice` | (none: `AbstractDevice` itself adds none) |
| `nrg3:Occupants` | `type_value` |
| `nrg3:Energy` | `operation_type` and `is_amount_normalized` (REQUIRED via inherited `AbstractResourceType`); `type_value` and `end_use` (own type) |
| `nrg3:MonthlyTimeSeries` | `start_date`, `end_date`, `values_list` |
| `nrg3:RegularTimeSeries` | `start_timestamp`, `end_timestamp`, `time_interval`, `values_list` |
| `nrg3:MaterialLibrary` | at least one `library_member` |
| `nrg3:LayeredConstructionLibrary` | at least one `library_member` |
| `nrg3:ScheduleLibrary` | at least one `library_member` |
| `nrg3:LayeredConstruction1` (inside library) | `type_value` |
| `nrg3:SolidMaterial` | `type_value`, `is_transparent` |
| `nrg3:Gas` | `type_value` |
| `nrg3:Layer` | `thickness`, `material` |
| `nrg3:EnergyPerformanceCertificate` | `type_value`, `label` (REQUIRED on `EnergyPerformanceCertificateType`); `value` / `certification_method` are optional, `valid_from` / `valid_to` / `status` are list-valued ADE hooks on every CityObject and optional, `creation_date` is inherited from `core:AbstractCityObject` and optional |
| `core:Address` (inside `bldg:Building.address[*].address`; the BuildingUnit's `nrg3:address` references it via xlink) | `xal_address` (REQUIRED on `AddressType`). The xAL substructure is itself nested but has no required leaves at the AddressDetails level: every xAL element below `AddressDetails` is `minOccurs="0"`, so the schema accepts an `<AddressDetails/>` carrying nothing. The canonical input populates `country.country_name_code` + `country.country_name` + `country.locality.{locality_name, thoroughfare.{thoroughfare_number, thoroughfare_name}, postal_code.postal_code_number}` to match the city pipeline's BAG-derived shape. |
| `QualifiedArea` / `QualifiedHeight` / `QualifiedVolume` (data type used inside `bdg_area` / `bdg_height` / `bdg_volume` / `area`) | `value`, `type_value` |

`nrg3:Metadata` itself has no required subfields; every `author` / `acquisition_method` / `owner` / `quality_description` / `source` field is `minOccurs="0"`. The library's outer `nrg3:MaterialLibrary` and `nrg3:LayeredConstructionLibrary` require ≥ 1 `library_member` (the XSD models the wrapper as `minOccurs="1" maxOccurs="unbounded"`); the canonical input always populates one.

**Cross-checking required fields against `gml:CodeType`-typed slots.** Most "required" entries above are `gml:CodeType`. The XSD's `CodeType` is open: any string is schema-accepted as long as the codeSpace identifies the vocabulary. In practice that means a missing required CodeType raises at build time (no value to write), but a *misspelled* value silently passes XSD validation; consumers are expected to validate against the codespace at consume time. The pipeline does not enforce codelist membership.
