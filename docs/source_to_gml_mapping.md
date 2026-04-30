# Source → GML mapping master index

**Purpose.** A single answer to "where does field *X* land in the GML?",
keyed by source dataset. Every row points to (a) the source field, (b)
its CityGML 2.0 / Energy ADE 3.0 destination, and (c) the implementing
helper in code. Long-form rationale lives in the source-specific
companion docs; this file is the routing table.

**Drift guard.** [`tests/test_mapping_index_in_sync.py`](../tests/test_mapping_index_in_sync.py)
asserts that every code reference in this document resolves to an
existing module and that every public `_apply_*` enrichment helper in
[`citygml_energy/city_builder/`](../citygml_energy/city_builder/) is
mentioned at least once below. A merge that adds a new helper or
renames an existing one will fail that test until this doc is
updated.

**Companion docs (rationale and source schema details):**

* [`vegetation_integration_report.md`](vegetation_integration_report.md): CFTree, BGT, BOR per-tree decisions.
* [`ep_online_data_model_mapping.md`](ep_online_data_model_mapping.md): every EP-online column with verdict.
* [`city_data_sources_overview.md`](city_data_sources_overview.md): high-level overview of every source.

## Conventions

* "Native slot" = an XSD element typed for the value (e.g. `bldg:yearOfConstruction` is `xs:gYear`, `veg:species` is `gml:CodeType`). Native slots get the typed value with the right `codeSpace` where applicable.
* "Generic attribute" = `gen:stringAttribute` / `gen:intAttribute` / `gen:doubleAttribute` / `gen:dateAttribute` / `gen:measureAttribute`, attached to any object inheriting from `core:AbstractCityObject`. Used when no native slot fits the source.
* "Cross-reference" = `core:externalReference` element with `informationSystem` (catalog page) plus `externalObject/uri` (dereferenceable feature URL). Used to link our output back to the authoritative source, not to ship attributes.
* All `codeSpace` URLs are pinned in [`citygml_energy/namespaces.py`](../citygml_energy/namespaces.py).

## 1. CFTree (`trees_lod3.city.json` morphometrics)

CFTree's per-tree morphometric attribute dict is the only source for native CityGML 2.0 vegetation measurements. The mapping table is encoded as Python constants so a new CFTree metric is a one-line edit. Implementation in [`builders/vegetation.py`](../citygml_energy/city_builder/builders/vegetation.py).

| CFTree key | CityGML target | Implementation |
|---|---|---|
| `trunk_H_m` | `veg:height` (`gml:LengthType`, uom `m`) | `_CFTREE_NATIVE_FIELDS` → `_apply_cftree_morphometrics` |
| `trunk_DBH_m` | `veg:trunkDiameter` (`gml:LengthType`, uom `m`) | `_CFTREE_NATIVE_FIELDS` → `_apply_cftree_morphometrics` |
| `crown_width_m` | `veg:crownDiameter` (`gml:LengthType`, uom `m`) | `_CFTREE_NATIVE_FIELDS` → `_apply_cftree_morphometrics` |
| `crown_median_z` | `gen:doubleAttribute name="crown_median_z"` | `_CFTREE_GENERIC_DOUBLE` |
| `crown_r50_m` | `gen:doubleAttribute name="crown_r50_m"` | `_CFTREE_GENERIC_DOUBLE` |
| `crown_porosity` | `gen:doubleAttribute name="crown_porosity"` | `_CFTREE_GENERIC_DOUBLE` |
| `trunk_base_height_m` | `gen:doubleAttribute name="trunk_base_height_m"` | `_CFTREE_GENERIC_DOUBLE` |
| `trunk_radius_m` | (omitted) | redundant with `trunk_DBH_m`; see comment in `_CFTREE_GENERIC_DOUBLE` |
| Solid triangles | `veg:lod3Geometry` → `gml:MultiSurface` | `build_solitary_vegetation_object` |

**Rationale:** [`vegetation_integration_report.md` § 3.1](vegetation_integration_report.md#31-cftree--citygml).

## 2. BGT `vegetatieobject_punt` (boom)

BGT carries no per-tree attributes (no species, no leaf class, no planting year). Used as a **cross-reference layer only**. Implementation in [`builders/vegetation.py:_apply_bgt_cross_reference`](../citygml_energy/city_builder/builders/vegetation.py).

| BGT field | CityGML target | Implementation |
|---|---|---|
| `lokaal_id` | `core:externalReference/externalObject/uri` (PDOK feature URL) | `_apply_bgt_cross_reference` |
| `creation_date` | `gen:dateAttribute name="bgtCreationDate"` | `_apply_bgt_cross_reference` |
| presence in BGT | presence of the `core:externalReference` element | `_apply_bgt_cross_reference` |

**Match:** 4 m nearest-neighbour join from CFTree centroids, see [`bgt_match.match_trees_to_bgt`](../citygml_energy/city_builder/bgt_match.py) (algorithm in [`tree_matching.match_nearest_within`](../citygml_energy/city_builder/tree_matching.py)).

**Rationale:** [`vegetation_integration_report.md` § 3.2](vegetation_integration_report.md#32-bgt-cross-reference--citygml).

## 3. Gemeente Emmen `bor_groen_bomen_beschermd`

Emmen's BOR (Beheer Openbare Ruimte) tree register is the only source that fills `veg:species`. The remaining BOR fields land in `gen:*Attribute` siblings because the CityGML 2.0 vegetation module has no typed slots for protection regimes, growth-form descriptors, or class-band measurements. Implementation in [`builders/vegetation.py:_apply_bor_enrichment`](../citygml_energy/city_builder/builders/vegetation.py).

| BOR field | CityGML target | Implementation |
|---|---|---|
| `boom_id` | `core:externalReference/externalObject/uri` (ArcGIS REST query URL keyed on `boom_id`) | `_apply_bor_enrichment` |
| `soortnaam` (Latin) | `veg:species` (`gml:CodeType`, codeSpace = FeatureServer URL) | `_apply_bor_enrichment` |
| `soortnaam_ned` (Dutch) | `gen:stringAttribute name="speciesCommonName"` | `_apply_bor_enrichment` |
| `jaarvanaanleg` | `gen:intAttribute name="plantingYear"` | `_apply_bor_enrichment` |
| `boomhoogteklasseactueel` | `gen:stringAttribute name="heightClass"` | `_apply_bor_enrichment` |
| `stamdiameterklasse` | `gen:stringAttribute name="trunkDiameterClass"` | `_apply_bor_enrichment` |
| `beschermingsstatus` | `gen:stringAttribute name="protectionStatus"` | `_apply_bor_enrichment` |
| `beschermingsstatus_detail` | `gen:stringAttribute name="protectionStatusDetail"` | `_apply_bor_enrichment` |
| `type` | `gen:stringAttribute name="growthForm"` | `_apply_bor_enrichment` |
| `standplaats` | `gen:stringAttribute name="standLocation"` | `_apply_bor_enrichment` |
| `standplaats_detail` | `gen:stringAttribute name="standLocationDetail"` | `_apply_bor_enrichment` |

**Match:** 4 m nearest-neighbour join from CFTree centroids, see [`tree_enrichment.match_trees_to_bor`](../citygml_energy/city_builder/tree_enrichment.py) (algorithm in [`tree_matching.match_nearest_within`](../citygml_energy/city_builder/tree_matching.py)).

**Rationale:** [`vegetation_integration_report.md` § 3.3](vegetation_integration_report.md#33-gemeente-emmen-bor-enrichment--citygml). Note that protection regime is a *legal* status, not a horticultural function, so it stays a generic; growth form is a canopy descriptor, not a class. Forcing those into `veg:function` / `veg:class` would mis-signal vocabulary semantics.

## 4. BAG (`bag:pand` + `bag:verblijfsobject`)

BAG is the authoritative Dutch building register. Pand-level attributes go on `bldg:Building`; VBO-level attributes go on `nrg3:BuildingUnit`. Implementation in [`builders/building.py`](../citygml_energy/city_builder/builders/building.py) and [`builders/epc.py:apply_bag_year_metadata_to_building`](../citygml_energy/city_builder/builders/epc.py).

### Pand → Building (per-Pand facts)

| BAG field | CityGML target | Implementation |
|---|---|---|
| `identificatie` | `nrg3:identifier` with `codeSpace=CS_BAG_PAND` and `gml:name` | `build_building` |
| `bouwjaar` | `bldg:yearOfConstruction` (`xs:gYear`) | `build_building` (via `_apply_building_attributes` reading `oorspronkelijkbouwjaar` after `_merge_attributes` overlays the BAG value) |
| presence of `bouwjaar` | `nrg3:Metadata` block with BAG source | `apply_bag_year_metadata_to_building` |
| `status` | (no CityGML target; surfaced into the parsed attribute dict only) | `pand_executor._merge_attributes` |

### VBO → BuildingUnit (per-VBO facts)

| BAG field | CityGML target | Implementation |
|---|---|---|
| `identificatie` | `nrg3:identifier` with `codeSpace=CS_BAG_VERBLIJFSOBJECT` | `build_building_unit` |
| `gebruiksdoel[0]` | `nrg3:type` (`gml:CodeType`, e.g. `woonfunctie`) | `build_building_unit` |
| `oppervlakte` | `nrg3:QualifiedArea` (type `netFloorArea`) | `build_building_unit` |
| `geometriePunt` | `core:Address/core:multiPoint` (`gml:MultiPoint`) | `build_address` |
| `postcode` / `huisnummer` / `huisletter` / `toevoeging` / `openbare_ruimte` | `core:Address` xAL structure | `build_address` |

## 5. 3DBAG (LoD 0 / 1 / 2 CityJSON tile)

3DBAG provides per-Pand 3D geometry and ~60 attributes. Geometry maps directly to CityGML LoD slots; attributes map to a curated subset documented in [`builders/building.py:_apply_building_attributes`](../citygml_energy/city_builder/builders/building.py).

| 3DBAG field | CityGML target | Implementation |
|---|---|---|
| LoD 0 footprint polygons | `bldg:lod0FootPrint` (`gml:MultiSurface`); footprint Z lifted to `b3_h_maaiveld` | `build_building`, `_lift_lod0_to_ground` |
| LoD 1 solid polygons | `bldg:lod1Solid` (`gml:CompositeSurface` shell) | `build_building` |
| LoD 2 polygons (per `surface_type`) | `bldg:boundedBy` → `bldg:GroundSurface` / `WallSurface` / `RoofSurface`, each with `bldg:lod2MultiSurface` | `_attach_lod2_thematic_surfaces` |
| `b3_h_maaiveld` | (read by `_lift_lod0_to_ground`; not emitted directly) | `_lift_lod0_to_ground` |
| `b3_h_dak_max` minus `b3_h_maaiveld` | `bldg:measuredHeight` (`gml:LengthType`, uom `m`) | `_apply_building_attributes` |
| `b3_bouwlagen` | `bldg:storeysAboveGround` (`xs:nonNegativeInteger`) | `_apply_building_attributes` |
| `b3_dak_type` | `bldg:roofType` (`gml:CodeType`, codeSpace = `CS_3DBAG_DAK_TYPE`) | `_apply_building_attributes` |
| `b3_volume_lod22` | `nrg3:bdgVolume` (`QualifiedVolume` with type `grossVolume`) | `_apply_building_attributes` |

## 6. EP-online (Mutatiebestand v4)

EP-online is per-VBO. Year of construction is exceptional: it lifts to the Building level because a building is constructed once. Implementation in [`builders/epc.py`](../citygml_energy/city_builder/builders/epc.py) and [`builders/building.py:build_building_unit`](../citygml_energy/city_builder/builders/building.py); per-resource energy emissions in [`energy_resources.attach_energy_resources_to_building_unit`](../citygml_energy/city_builder/energy_resources.py).

### Per-VBO (BuildingUnit)

| EP-online field | CityGML target | Implementation |
|---|---|---|
| `Energieklasse` | `nrg3:EnergyPerformanceCertificate.label` | `_build_epc` |
| `Registratiedatum` | `nrg3:EnergyPerformanceCertificate.validFrom` | `_build_epc` |
| `GeldigTot` | `nrg3:EnergyPerformanceCertificate.validTo` | `_build_epc` |
| `SoortOpname` + `Berekeningstype` | `nrg3:EnergyPerformanceCertificate.certificationMethod` (joined with ` / `) | `_certification_method_string` (called by `_build_epc`) |
| `Gebouwsubtype` | `gen:stringAttribute name="bdgSubtypeEPOnline"` (Dutch RVO term verbatim; no native `nrg3:bdgSubtype` slot in EnergyADE 3.0) | `_apply_eponline_classification_to_building_unit` |
| `GebruiksoppervlakteThermischeZone` | `nrg3:QualifiedArea` (type `netFloorArea`, source = EP-online) | `build_building_unit` |
| `AandeelHernieuwbareEnergie` | `gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie"` (uom `percent`) | `build_building_unit` |
| `Energiebehoefte` / `Warmtebehoefte` / `PrimaireFossieleEnergie` / `BerekendeEnergieverbruik` | `nrg3:Energy` resources via `nrg3:resource` | `attach_energy_resources_to_building_unit` |
| `BerekendeCO2Emissie` | `nrg3:Energy.co2Equivalent` on the appropriate energy resource | `attach_energy_resources_to_building_unit` |
| presence of any of the above | `nrg3:Metadata` block on the BuildingUnit (EP-online source) | `_apply_eponline_classification_to_building_unit` |

### Lifted to Building (per-Pand fact)

| EP-online field | CityGML target | Implementation |
|---|---|---|
| `Bouwjaar` (canonical pick across all VBOs of a Pand) | `gen:intAttribute name="yearOfConstructionEPOnline"` | `apply_eponline_pand_attribution_to_building` (canonical pick via `_pick_canonical_eponline_label` + `_eponline_label_recency_key`) |
| `Gebouwtype` (canonical pick across all VBOs of a Pand) | native `nrg3:bdgType` carrying the Dutch RVO NTA-8800 term verbatim, with `@codeSpace` = `CS_RVO_GEBOUWTYPE` (the official RVO EP-online landing page) | `apply_eponline_pand_attribution_to_building` (per-field canonical pick via `_pick_canonical_eponline_label`) |
| presence of either of the above | one shared `nrg3:Metadata` block on the Building attributing both Pand-level emissions to the EP-online source | `apply_eponline_pand_attribution_to_building` |

**Rationale:** [`ep_online_data_model_mapping.md`](ep_online_data_model_mapping.md). The full EP-online column verdict table includes every column shipped by the CSV (42 columns), including the ones that are deliberately dropped (privacy, redundancy).

## 7. Municipality outline (PDOK `bestuurlijkegebieden:Gemeentegebied`)

The outline is used to drive the build (bbox + CBS code filter); none of its fields are written into the GML output. Listed here for completeness so a reader looking for `naam` or `code` does not search for a target that does not exist.

| Field | Use | Implementation |
|---|---|---|
| `naam` / `code` | filter to the requested municipality, derive 4-digit CBS code for the BAG fetch | [`fetchers/municipality.py:fetch_municipality_outline`](../citygml_energy/city_builder/fetchers/municipality.py) |
| polygon geometry | bbox for downstream BAG / 3DBAG fetches; polygon clip in `_filter_by_boundary` | [`fetchers/municipality.py:_feature_bbox`](../citygml_energy/city_builder/fetchers/municipality.py) |

## 8. PV panels (per-Pand input file)

PV panels are user-supplied geometry (no fetcher). Mapping is in [`pv_panels.attach_pv_collectors_to_building`](../citygml_energy/city_builder/pv_panels.py).

| Input field | CityGML target | Implementation |
|---|---|---|
| panel polygon | `nrg3:SolarThermalSystem` / `nrg3:PhotovoltaicSystem` solar collector geometry (LoD 2 multisurface lifted onto a `roofSurface`) | `attach_pv_collectors_to_building` |

(Detailed mapping for PV panels is out of scope here; this row exists so the index is complete.)

## Code reference legend

The `Implementation` column references either:

* a Python identifier inside an already-linked module file in the section heading (no link, just the name), or
* a Python identifier on a different module path (link with the full file path).

The drift-detection test parses both forms; renaming or moving a referenced symbol fails the test until this document is updated.
