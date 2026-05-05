# City pipeline: source data → CityGML 2.0 / Energy ADE 3.0 mapping

**Purpose.** This document is the single answer to "where does field *X* land in the GML?" for every input the city-scale pipeline (`citygml_energy.city_builder`) reads. Every row points to (a) the source field, (b) its CityGML 2.0 / Energy ADE 3.0 destination, and (c) the implementing helper in code. Where a value cannot be carried natively, the workaround is documented alongside the schema gap.

**Companion document.** [`mapping_building.md`](mapping_building.md) covers the per-building pipeline (hand-authored JSON + STEP geometry input). The two pipelines share data structures and bindings but consume different inputs and emit different feature subsets; mapping is split per pipeline so each table is self-contained.

**Drift guard.** [`tests/test_mapping_index_in_sync.py`](../tests/test_mapping_index_in_sync.py) asserts that every module path linked in this document exists, that a curated list of cited symbols is reachable in its module, and that every enrichment helper in [`citygml_energy/city_builder/`](../citygml_energy/city_builder/) — private (`_apply_bgt_*`, `_apply_bor_*`, `_apply_cftree_*`, `_apply_eponline_*`) and public (`apply_bag_*`, `apply_eponline_*`, `build_building*`, `build_address`, `build_solitary_vegetation_object`) — is mentioned at least once below. A merge that adds a new helper or renames an existing one will fail that test until this doc is updated. Inline line-number citations are not enforced by the test and may drift; the symbol names are authoritative.

**Completeness method.** Every "supply" row was obtained by parsing a real cached response (BAG, 3DBAG, EP-online, municipality, CFTree, BGT), the actual GeoPackage schema (PV panels), or a sample GeoJSON (boundary). Field names reflect what the source actually emits; the commentary notes where the source documentation uses a different name or alias. Counts come from a fresh end-to-end run on the Emmer-Compascuum small-area AOI (41.5 ha, 674 buildings, 652 trees) using [`inputs/cities/emmer-compascuum_small-area.json`](../inputs/cities/emmer-compascuum_small-area.json).

**Snapshot vintages.** Concrete counts in this document (building / tree counts, EP-online row distributions, BGT match ratios) were recorded against the **EP-online v20260401 mutatiebestand** and the BAG / 3DBAG / BGT responses cached on **2026-04-29**. Run `tests/test_mapping_index_in_sync.py` to verify the symbol-level invariants, but expect the absolute counts to drift with each upstream republication; the *shapes* (proportions, regime distributions) are stable.

## Conventions

| Concept | Meaning |
|---|---|
| **Native slot** | An XSD element typed for the value (e.g. `bldg:yearOfConstruction` is `xs:gYear`, `veg:species` is `gml:CodeType`). Native slots get the typed value with the right `codeSpace` where applicable. |
| **Generic attribute** | `gen:stringAttribute` / `gen:intAttribute` / `gen:doubleAttribute` / `gen:dateAttribute` / `gen:measureAttribute`, attached to any object inheriting from `core:AbstractCityObject`. Used when no native slot fits the source. |
| **Cross-reference** | `core:externalReference` element with `informationSystem` (catalog page) plus `externalObject/uri` (dereferenceable feature URL). Used to link our output back to the authoritative source, not to ship attributes. |
| **QualifiedAttribute multi-source pattern** | Energy ADE 3.0 encodes diverging sources for the same physical quantity (area, height, volume) by repeating the slot with different `source` strings. The pipeline uses this pattern wherever BAG and EP-online disagree. |

| Legend (per-source supply tables) | Meaning |
|---|---|
| **✓** | The pipeline reads this field and writes it to an output element. |
| **⚙** | The pipeline reads this field for joins, bbox clipping, or matching, but does not write it. |
| **(blank)** | The source ships the field but the pipeline ignores it. |

All `codeSpace` URLs are pinned in [`citygml_energy/namespaces.py`](../citygml_energy/namespaces.py). The two `core:externalReference/informationSystem` URLs (`BGT_INFORMATION_SYSTEM_URL`, `BOR_INFORMATION_SYSTEM_URL`) are pinned in their respective fetcher modules ([`fetchers/bgt.py`](../citygml_energy/city_builder/fetchers/bgt.py), [`fetchers/emmen_bor.py`](../citygml_energy/city_builder/fetchers/emmen_bor.py)) because they are not codeSpaces. The codeSpace of a `gml:CodeType` identifies the vocabulary, not the field; off-codelist values are valid as long as the codeSpace names the vocabulary they belong to.

**Output features.** Every BAG Pand becomes one `bldg:Building`; every BAG VBO becomes one `nrg3:BuildingUnit` parented to its Pand. Every CFTree reconstruction becomes one `veg:SolitaryVegetationObject`. Every PV panel polygon becomes one `nrg3:PhotovoltaicCollector` parented to a Building.

## At-a-glance

| # | Source | Supply (fields shipped) | Demand (fields read) | CityGML / Energy ADE target |
|---|---|---|---|---|
| 1 | PDOK `bestuurlijkegebieden` | 5 properties + geometry | 2 + geometry | (drives downstream fetch scope only) |
| 2 | 3DBAG `tile_index.fgb` | 2 properties + geometry | 2 + geometry | (tile selection + download URL) |
| 3 | PDOK BAG `bag:pand` | 8 properties + geometry | 4 | `bldg:Building` |
| 4 | PDOK BAG `bag:verblijfsobject` | 14 properties + geometry | 11 + geometry | `nrg3:BuildingUnit` + `core:Address` |
| 5 | 3DBAG CityJSON tile | 62 `Building` attributes + LoD 0/1.2/2.2 geometries | 8 attributes + 3 LoD geometries | `bldg:lod0FootPrint` + `bldg:lod1Solid` + `bldg:boundedBy/lod2MultiSurface` + `nrg3:bdgHeight` (`QualifiedHeight`, `type="maxHeightAboveGround"`) + `bldg:roofType` + `bldg:storeysAboveGround` + `nrg3:bdgVolume` |
| 6 | EP-online `Mutatiebestand` CSV | 42 columns | 20 | `nrg3:EnergyPerformanceCertificate` + `app:Appearance` (theme `energyLabel`) + per-VBO `nrg3:QualifiedArea` (thermal-zone) + per-VBO `nrg3:Energy` resources (regime-aware) + native `nrg3:bdgType` (Pand level) + per-VBO `gen:*Attribute` classification + `nrg3:Metadata` source attribution |
| 7 | PV panels GeoPackage | 2 columns + geometry | 2 + geometry | `nrg3:PhotovoltaicCollector` |
| 8 | CFTree `trees_lod3.city.json` | 10 attributes + LoD 3 geometry | 9 + geometry | `veg:SolitaryVegetationObject` + `veg:lod3Geometry` |
| 9 | BGT `vegetatieobject_punt` | 23 properties + geometry | 5 + geometry | `core:externalReference` + `gen:dateAttribute` (cross-reference layer; no biological attributes) |
| 10 | Gemeente Emmen `bor_groen_bomen_beschermd` | 11 fields | 11 | `veg:species` + `core:externalReference` + `gen:*Attribute` siblings (BOR enrichment, only used in Emmen runs) |
| 11 | Boundary polygon (`.geojson`) | geometry + metadata | geometry | (clips the output to a concave AOI) |
| 12 | CBS Postcode6 WFS (`postcode6:postcode6`) | 132 properties + polygon geometry | 5 + geometry | `nrg3:UrbanFunctionArea` (one per postcode) with polygon, area, two `nrg3:Energy` resources (`type=actual`, carrier `naturalGas` / `electricity`), two `gen:intAttribute` (`dwellingCount` / `vacantDwellingCount`), `core:externalReference`, `nrg3:Metadata`, and `grp:groupMember` xlinks to constituent buildings |

---

## 1. PDOK `bestuurlijkegebieden` — municipality outline

**Endpoint:** `https://service.pdok.nl/kadaster/bestuurlijkegebieden/wfs/v1_0`, typeName `bestuurlijkegebieden:Gemeentegebied`, `outputFormat=application/json`, `srsName=EPSG:28992`.
**Fetcher:** [`fetchers/municipality.py::fetch_municipality_outline`](../citygml_energy/city_builder/fetchers/municipality.py).

The outline drives the build (bbox + CBS code filter); none of its fields are written into the GML output. Listed here for completeness so a reader looking for `naam` or `code` does not search for a target that does not exist.

| Property | Example | Read | Used for |
|---|---|---|---|
| `naam` | `"Emmen"` | ⚙ | Case-insensitive match against `config.municipality` (in `_build_outline`'s caller loop). |
| `naam_officieel` | usually absent | ⚙ | Fallback for `naam` in the name lookup |
| `code` | `"0114"` | ⚙ | Normalised to 4-digit CBS prefix; filters BAG panden / VBOs to only those inside the municipality (`_normalise_cbs_code`). |
| `identificatie` | `"GM0114"` |   | Equivalent info to `code`; not separately consulted. |
| `ligtInProvincieCode`, `ligtInProvincieNaam` | `"22"`, `"Drenthe"` |   | Unused. |
| `geometry` (MultiPolygon) | — | ⚙ | (a) bbox drives BAG / 3DBAG fetch extent; (b) polygon clips 3DBAG buildings that fall outside the municipality. `_feature_bbox`, `pipeline._fetch_parsed_buildings`. |

No feature is emitted in the GML for the municipality itself.

---

## 2. 3DBAG tile index — FlatGeoBuf

**Endpoint:** `https://data.3dbag.nl/latest/tile_index.fgb`, read with `flatgeobuf.HTTPReader` so only the bbox-relevant slice is transferred via HTTP range requests.
**Fetcher:** [`fetchers/threedbag.py::fetch_tile_index`](../citygml_energy/city_builder/fetchers/threedbag.py).

| Property | Read | Used for |
|---|---|---|
| `tile_id` | ⚙ | Tile-folder naming + cache key |
| `cj_download` | ⚙ | The CityJSON tile URL to GET |
| every other property the tile index carries (e.g. `gpkg_download`, `obj_download`, version metadata) |   | Ignored. |
| geometry (polygon of the tile footprint) | ⚙ | Filtered against the municipality polygon to drop corner tiles that only share a bbox corner. |

---

## 3. PDOK BAG `bag:pand` — building polygons + basic attributes

**Endpoint:** `https://service.pdok.nl/lv/bag/wfs/v2_0`, typeName `bag:pand`.
**Fetcher:** [`fetchers/bag.py::fetch_panden`](../citygml_energy/city_builder/fetchers/bag.py).
**Builder:** [`builders/building.py::build_building`](../citygml_energy/city_builder/builders/building.py).

Pand-level attributes go on the `bldg:Building` (one Pand per Building).

| WFS property | Example | Read | CityGML target | Implementation |
|---|---|---|---|---|
| `identificatie` | `"0114100000202542"` | ✓ | `bldg:Building/@gml:id` (via `pand_` prefix) + `nrg3:identifier` with `codeSpace=CS_BAG_PAND`. `gml:name` is **not set**: BAG carries no per-Pand human-readable label, and repeating the 16-digit identifier in a slot reserved for human-readable labels would mislead viewers (the authoritative identifier is already on `nrg3:identifier`). | `build_building` |
| `bouwjaar` | `1955` | ✓ | `bldg:yearOfConstruction` (`xs:gYear`) | `build_building` (via `_apply_building_attributes` reading `oorspronkelijkbouwjaar` after `pand_executor._merge_attributes` overlays the BAG value over any 3DBAG fallback). BAG wins on ties. |
| presence of `bouwjaar` | — | ✓ | `nrg3:Metadata` block on Building attributing BAG as the source of `bldg:yearOfConstruction` | [`builders/epc.py::apply_bag_year_metadata_to_building`](../citygml_energy/city_builder/builders/epc.py) |
| `rdf_seealso` | `"http://bag.basisregistraties.overheid.nl/bag/id/pand/<id>"` | ⚙ (implicit) | — | Not read per-feature. The known URL structure is what drives `CS_BAG_PAND`; concatenating `codeSpace + identifier` reconstructs the dereferenceable URL. |
| `status` | `"Pand in gebruik"` | ⚙ | merged into `ParsedBuilding.attributes["status"]` but **not written** to any CityGML element | `pand_executor._merge_attributes`. Latent: a future `bldg:condition`-like field could consume this. |
| `gebruiksdoel` | usually empty on Pand |   |   | Empty on Pand in the surveyed responses (the real value lives on VBO). Ignored. |
| `aantal_verblijfsobjecten` | `2` |   |   | Number of VBOs inside the Pand. Ignored. |
| `oppervlakte_min`, `oppervlakte_max` | — |   |   | Footprint area range. Ignored (3DBAG geometry wins). |
| WFS feature `id` (e.g. `"pand.<uuid>"`) |   |   |   | The BAG `identificatie` is the stable handle; the UUID prefix is discarded. |
| `geometry` (Polygon) | — |   |   | Ignored: 3DBAG's CityJSON geometry is used instead, keyed by `identificatie`. |

---

## 4. PDOK BAG `bag:verblijfsobject` — addressable units inside a Pand

**Endpoint:** same WFS, typeName `bag:verblijfsobject`. PDOK joins Nummeraanduiding + OpenbareRuimte server-side, so address fields appear directly on each VBO.
**Fetcher:** [`fetchers/bag.py::fetch_verblijfsobjecten`](../citygml_energy/city_builder/fetchers/bag.py).
**Builders:** [`builders/building.py::build_building_unit`](../citygml_energy/city_builder/builders/building.py), [`builders/address.py::build_address`](../citygml_energy/city_builder/builders/address.py).

VBO-level attributes go on `nrg3:BuildingUnit` (one VBO per BuildingUnit, parented to its Pand's Building).

| WFS property | Example | Read | CityGML / Energy ADE target | Notes |
|---|---|---|---|---|
| `identificatie` | `"0114010000274521"` | ✓ | `nrg3:BuildingUnit/@gml:id` (via `bu_` prefix) + `nrg3:identifier` with `codeSpace=CS_BAG_VERBLIJFSOBJECT` | Same pattern as the Pand id; concatenating `codeSpace + value` reconstructs the authoritative VBO URL. Also the primary EP-online join key. |
| `pandidentificatie` (or `pand_identificatie`) | `"0114100000233256"` | ⚙ | — | Buckets VBOs under their Pand; only the first id is kept when the WFS returns a comma-separated list for rare multi-Pand VBOs. |
| `gebruiksdoel[0]` | `"woonfunctie"` | ✓ | `nrg3:type` (`gml:CodeType`) with `codeSpace=CS_BAG_GEBRUIKSDOEL`. Kept verbatim as the Dutch term rather than mapped to the EnergyADE `CurrentUseValue.xml` codelist (which would lose distinctions like `logiesfunctie` vs `woonfunctie`). | Additional values in a dual-use VBO are dropped. |
| `oppervlakte` | `247` | ✓ | `nrg3:area` → `nrg3:QualifiedArea` (`type="netFloorArea"`, `source="BAG bag:verblijfsobject.oppervlakte (PDOK WFS v2.0)"`). uom `m2`. | Lives natively on `BuildingUnit/area` (inherited from `AbstractCityObjectSpace`). The `description` notes that BAG `oppervlakte` is NEN 2580 `gebruiksoppervlakte` (excludes walls and shafts), slightly narrower than the OGC / Energy-ADE `netFloorArea` definition. |
| `geometry` (Point) | — | ✓ | `core:Address/core:multiPoint` (`gml:MultiPoint`). | **Caveat**: the CityGML 2.0 docstring describes `multiPoint` as "locating the entrance(s)", but BAG `geometriePunt` is just a per-VBO address-locating point. It always lies inside the parent Pand but is not guaranteed to be at or near the entrance. Every Dutch BAG-to-CityGML converter populates the field this way. |
| `woonplaats` | `"Emmer-Compascuum"` | ✓ | `core:Address/xAL:Country/xAL:Locality/xAL:LocalityName` (`Locality/@Type="Town"`). | The IMBAG-canonical locality component of a Dutch BAG address (a woonplaats can span multiple gemeenten, e.g. gemeente Emmen contains the woonplaatsen Emmen, Klazienaveen, Nieuw-Amsterdam). Falls back to the pipeline's caller-supplied `city_name` when the WFS record has no `woonplaats`. |
| `postcode` | `"7881AD"` | ✓ | `xAL:PostalCode/xAL:PostalCodeNumber` | |
| `huisnummer` | `73` | ✓ | `xAL:Thoroughfare/xAL:ThoroughfareNumber` (`@NumberType="Single"`). Mixed-content text **also** embeds the flat form: huisnummer + huisletter (no separator) + toevoeging (prefixed by `-`). Example: `(38, "B", "rood")` → `"38B-rood"`. A downstream consumer reading only this slot still sees the full canonical identifier. | See the 3DCityDB tooling caveat below. |
| `huisletter` | `""` or `"A"` | ✓ | `xAL:Thoroughfare/xAL:ThoroughfareNumberSuffix` with `@Type="huisletter"`. | The xAL XSD allows multiple `ThoroughfareNumberSuffix` siblings (`maxOccurs="unbounded"`); the `Type` attribute disambiguates the two suffix slots that BAG distinguishes. Empty string is normalised to `None`. |
| `huisnummertoevoeging` (PDOK alias `toevoeging`) | `""` or `"003"` | ✓ | `xAL:Thoroughfare/xAL:ThoroughfareNumberSuffix` with `@Type="huisnummertoevoeging"` and `@NumberSuffixSeparator="-"`. | The hyphen separator mirrors BAG's canonical-string rendering (`38-rood`). |
| `openbare_ruimte` | `"Hoofdkanaal WZ"` | ✓ | `xAL:Thoroughfare/xAL:ThoroughfareName` (`Thoroughfare/@Type="Street"`) | Street name. |
| (NL country wrapper) | — | ✓ | `xAL:Country/xAL:CountryNameCode Scheme="iso.3166-1 alpha-2"`=`NL` + `xAL:CountryName="The Netherlands"`. | Mirrors the EnergyADE 3.0 Alderaan reference shape. |
| `status` | `"Verblijfsobject in gebruik"` | ⚙ | — | Latent; no native lifecycle field. |
| `bouwjaar` | `1956` |   |   | Authoritative value already used via the Pand; VBO-level value is redundant. Ignored. |
| `pandstatus` | `"Pand in gebruik"` |   |   | Redundant with the Pand's own `status`. Ignored. |
| `rdf_seealso` | — |   |   | Linked-data URI; implicit (same URL shape as the Pand `rdf_seealso` drives the VBO codeSpace). |

**Address property element is `nrg3:address`, not `bldg:address`.** The address attaches to `nrg3:BuildingUnit` via the Energy ADE-defined `address` element on `BuildingUnitType` (XSD line 1520, `core:AddressPropertyType`, `[0..*]`), not via the CityGML 2.0 `bldg:address` slot on `bldg:Building`. The `core:Address` payload inside is identical, but a consumer that walks CityGML 2.0 buildings looking for `bldg:address` will miss every Dutch address this pipeline emits; consumers should look under `nrg3:address` of each `nrg3:BuildingUnit` instead.

**Tooling caveat for huisletter / huisnummertoevoeging.** 3DCityDB v5's `XALAddressWalker` overrides `visit()` for `ThoroughfareName` / `ThoroughfareNumber` / `LocalityName` / `PostalCodeNumber` / `CountryName` / `PostBoxNumber` only; the `ThoroughfareNumberSuffix` elements are never copied into the `HOUSE_NUMBER` column. Round-tripping a BAG address through 3DCityDB therefore loses the structured suffixes. The flat-form denormalisation embedded in `ThoroughfareNumber` (`38B-rood-2`) keeps the full identifier accessible to such consumers; the structured suffix elements remain available for tools that look for them.

---

## 5. 3DBAG CityJSON tile — LoD 0 / 1.2 / 2.2 geometries + building attributes

**Access:** tile URL from the FlatGeoBuf index (served gzipped); one `Building` CityObject per Pand plus zero-or-more child `BuildingPart`s.
**Parser:** [`cityjson_parse.py::parse_buildings`](../citygml_energy/city_builder/cityjson_parse.py).
**Builder:** geometry + attribute attachment in [`builders/building.py`](../citygml_energy/city_builder/builders/building.py).

3DBAG provides per-Pand 3D geometry and ~62 attributes. Geometry maps directly to CityGML LoD slots; the pipeline reads only eight of the attributes.

### 5a. Building-level attributes

| 3DBAG attribute | Example | Read | CityGML target | Implementation |
|---|---|---|---|---|
| `identificatie` | `"NL.IMBAG.Pand.0503100000000153"` | ⚙ | — | Bare BAG id (trailing `"NL.IMBAG.Pand."` stripped) is the join key back to BAG Pand. |
| `oorspronkelijkbouwjaar` | `1933` | ✓ | `bldg:yearOfConstruction` | Only used when BAG's own `bouwjaar` is absent. BAG wins on ties (`pand_executor._merge_attributes`). |
| `b3_h_maaiveld` | `0.175` | ✓ | feeds into `nrg3:bdgHeight` (subtrahend in `b3_h_dak_max - b3_h_maaiveld`) | `_apply_building_attributes`. Not stamped onto LoD 0; LoD 0 is a 2D footprint with no defined elevation, and the per-building terrain height already lives on LoD 1 / 2. |
| `b3_h_dak_max` | `9.925` | ✓ | feeds into `nrg3:bdgHeight` | `_apply_building_attributes` computes `nrg3:bdgHeight` as a `QualifiedHeight` with `type="maxHeightAboveGround"` (codeSpace `CS_NRG3_HEIGHT_TYPE`), value = `b3_h_dak_max - b3_h_maaiveld`, uom `m`. The Energy ADE `QualifiedHeight` slot is used rather than the CityGML core `bldg:measuredHeight` because it carries source attribution and a typed height-class code. Using `_max` (not `_70p`) so antennae and chimney tips register as part of the physical extent. Negative-height results are defensively dropped. |
| `b3_bouwlagen` | `3` | ✓ | `bldg:storeysAboveGround` (`xs:nonNegativeInteger`) | `_apply_building_attributes`. Direct 1-to-1 mapping. |
| `b3_dak_type` | `"slanted"`, `"horizontal"`, `"multiple horizontal"` | ✓ | `bldg:roofType` (`gml:CodeType`, `codeSpace = CS_BUILDING_ROOFTYPE`, the SIG3D `_AbstractBuilding_roofType.xml` codelist URL). 3DBAG → SIG3D mapping in `_3DBAG_TO_SIG3D_ROOF_TYPE`: `horizontal` → `1000` (flat), `slanted` → `1030` (gabled, deterministic fallback for ambiguous pitched roofs), `multiple horizontal` → `1130` (combination of roof forms). | `_apply_building_attributes`, `_3DBAG_TO_SIG3D_ROOF_TYPE`. The lossiness on `slanted` is intrinsic to 3DBAG; consumers needing finer disambiguation must consult the LoD 2 roof geometry directly. An alternative codespace constant `CS_3DBAG_DAK_TYPE` (`https://docs.3dbag.nl/en/schema/attributes/#b3_dak_type`) is defined in [`namespaces.py`](../citygml_energy/namespaces.py) and would carry the raw 3DBAG term verbatim under its own vocabulary; it is **not** wired up today (the SIG3D-mapped form is the canonical emission), but it stays in the namespace module so a future decision to drop the lossy mapping has a documented home. |
| `b3_volume_lod22` | `752.575` | ✓ | `nrg3:bdgVolume` (Energy-ADE extension) as `QualifiedVolume` with `type="grossVolume"`, uom `m3` | `_apply_building_attributes`. Matches the per-building pipeline's `bdg_volume` pattern. `bldg:Building` has no native volume slot; Energy ADE adds one. |
| `gebruiksdoel` | (when carried) | ✓ | `bldg:function` (CodeType, `CS_BUILDING_FUNCTION`) | Usually empty on 3DBAG Building nodes. |
| `status` | `"Pand in gebruik"` | ⚙ | — | Passed through `_merge_attributes` but not written. |
| other `b3_*` fields (~55 attributes): `b3_bag_bag_overlap`, `b3_extrusie`, `b3_h_dak_{50p,70p,min}`, `b3_h_nok`, `b3_is_glas_dak`, `b3_kas_warenhuis`, `b3_kwaliteitsindicator`, `b3_mutatie_ahn{3,4}_ahn{4,5}`, `b3_n_nok`, `b3_n_vlakken`, `b3_nodata_fractie_ahn{3,4,5}`, `b3_nodata_radius_ahn{3,4,5}`, `b3_opp_{buitenmuur,dak_plat,dak_schuin,grond,scheidingsmuur}`, `b3_puntdichtheid_ahn{3,4,5}`, `b3_pw_{bron,datum,onvoldoende,selectie_reden}`, `b3_rmse_lod{12,13,22}`, `b3_t_run`, `b3_val3dity_lod{12,13,22}`, `b3_volume_lod{12,13}` |   |   |   | Quality / statistical / redundant-volume fields. Latent; `b3_rmse_lod*` would be the natural next wave (quality-indicator generic attributes). |
| BAG-origin duplicates: `documentdatum`, `documentnummer`, `begingeldigheid`, `eindgeldigheid`, `eindregistratie`, `geconstateerd`, `tijdstipeindregistratielv`, `tijdstipinactief`, `tijdstipinactieflv`, `tijdstipnietbaglv`, `tijdstipregistratie`, `tijdstipregistratielv`, `voorkomenidentificatie`, `fid` |   |   |   | Registry-lifecycle fields, same semantics as in BAG itself. Not used. |

### 5b. Geometries

Each Building + its child BuildingParts contributes geometries at up to three LoDs.

| CityJSON `geometry.lod` | Shape | Read | CityGML target | Implementation |
|---|---|---|---|---|
| `"0"` | MultiSurface (one polygon) | ✓ | `bldg:lod0FootPrint` with the source-Z preserved (3DBAG ships LoD 0 at nominal Z = 0 / NAP). LoD 0 is a 2D footprint representation with no defined elevation; consumers needing a height-anchored ground plane should consult LoD 1 / LoD 2 instead. | `build_building` |
| `"1.2"` | Solid with thematic `semantics` | ✓ | `bldg:lod1Solid` as a `gml:CompositeSurface` shell | `build_building` |
| `"2.2"` | Solid with per-face `GroundSurface` / `WallSurface` / `RoofSurface` semantics | ✓ | `bldg:boundedBy` → `bldg:GroundSurface` / `WallSurface` / `RoofSurface`, **one element per polygon** with a single-polygon `bldg:lod2MultiSurface`. Each surface also carries `nrg3:bdgBdrySurfTotalSurfaceArea` (m², holes subtracted), `nrg3:bdgBdrySurfInclination` (deg, [0, 180] from +Z, so a flat roof is 0, a wall is 90, a downward-facing ground slab is 180), and `nrg3:bdgBdrySurfAzimuth` (deg, compass bearing, omitted on horizontal surfaces). | `_attach_lod2_thematic_surfaces`, `_attach_planar_surface_ade_attributes`. Construction / radiation properties (Thickness, HeatCapacity, IsShared, view factors, OpaqueSurfaceArea, ThermalBridgeUValue) are deliberately absent in this pipeline because the city pipeline has no source for them; populating with placeholders would silently contaminate downstream energy analyses. The per-building pipeline, which *does* have layered constructions, additionally fills `nrg3:bdgBdrySurfThickness` and `nrg3:bdgBdrySurfHeatCapacity` from the LayeredConstruction layer stack (see [`mapping_building.md`](mapping_building.md) and [`citygml_energy/boundary_attributes.py`](../citygml_energy/boundary_attributes.py)). |
| any other LoD (1.3, experimental variants) |   |   |   | Dropped in `_LOD_ALIAS` lookup. |

---

## 6. EP-online `Mutatiebestand` CSV — Dutch energy-label register

**Access:** two-step via `https://public.ep-online.nl/api/v5/Mutatiebestand/DownloadInfo?fileType=csv&xmlVersion=4` (needs `Authorization` header with the EP-online API key) → ZIP URL → ~1 GB CSV inside the ZIP.
**Fetcher and parser:** [`fetchers/eponline.py`](../citygml_energy/city_builder/fetchers/eponline.py).
**Builders:** [`builders/epc.py`](../citygml_energy/city_builder/builders/epc.py), [`builders/building.py::build_building_unit`](../citygml_energy/city_builder/builders/building.py).
**Per-resource energy emission:** [`energy_resources.py::attach_energy_resources_to_building_unit`](../citygml_energy/city_builder/energy_resources.py).

The CSV has **42 columns** plus two header meta-lines (`PublicatieDatum`, `LaatstVerwerkteMutatievolgnummer`). Filter-on-parse drops every row that does not match a wanted BAG VBO id or address key before materialising any dataclass.

EP-online is per-VBO. Most metrics ride on the `BuildingUnit`. Year of construction and primary `Gebouwtype` are exceptional: they lift to the `Building` level because they are Pand-level facts (a building is constructed once and has one primary type regardless of how many VBOs sit inside).

This section is the umbrella spec for every EP-online column. Three constraints govern every verdict:

- **XSD adherence.** Every native target is cited by file:line in [Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd](../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd) and cross-checked against the UML diagrams ([Energy_ADE-3.0beta8/documentation/Energy_ADE_3.0_beta8_UML_diagrams.pdf](../Energy_ADE-3.0beta8/documentation/Energy_ADE_3.0_beta8_UML_diagrams.pdf), pages 8 / 10 / 12 / 19-20). When the XSD says no, the verdict is no.
- **Personal data stays out.** EP-online is openly licensed but contains certifier and inspection metadata that is not strictly load-bearing for energy modelling. Where redaction is the senior call, the verdict is *Drop* with reasoning.
- **Existing pipeline shape preserved.** Address-key joining, multi-VBO buildings, and the existing per-building input format set the aggregation rules (§ 6.2).

### 6.1. Target inventory: what the schema offers

A consolidated list of the destination types referenced in the per-column tables.

| Target | XSD location | Cardinality on parent | What it carries |
|---|---|---|---|
| `nrg3:EnergyPerformanceCertificate` | line 1424 | `[0..*]` natively on BuildingUnit (XSD line 1527, composition slot on `BuildingUnitType`); also `[0..*]` on Building via the `nrg3:energyPerformanceCertificate` substitution element (XSD line 1627). The pipeline uses the BuildingUnit slot because every EP-online cert is per-VBO. | Slots: `type`, `label`, optional `value` (`gml:MeasureType`), optional `certificationMethod`; inherited `validFrom` / `validTo`. |
| `nrg3:Energy` (extends `AbstractResource`) | line 2133 | child of any `AbstractCityObject` via the `nrg3:resource` substitution element (line 1366) | One per (energy-type, end-use) pair. Slots: `type` (Code, e.g. `net` / `primary` / `final`), `endUse` (Code, e.g. `spaceHeating` / `spaceCooling` / `domesticHotWater`), `energyCarrier`, `source`. Inherited from `AbstractResource` (line 633): `amount` (Measure), `referencePeriod` (Code, e.g. `"year"`), `isAmountNormalized` (boolean, required), `normalizationValue` (Measure, optional), `normalizationParameter` (string, optional, e.g. `"netFloorArea"`), `co2Equivalent` (Measure, optional). |
| `nrg3:QualifiedArea` | line 243 (extends `AbstractQualifiedAttribute` at line 227) | `[0..*]` on `nrg3:AbstractCityObjectSpace.area` | Single measure with `type` (Code), inherited `description` / `source` / `value` (Measure). Used for both the BAG `oppervlakte` and the EP-online `GebruiksoppervlakteThermischeZone` on each BuildingUnit, distinguished by `source`. |
| `nrg3:bdgType` (extension on `_AbstractBuilding`) | line 1599 | XSD `[0..*]` on Building, but the UML `taggedValue` annotation on the element declares `maxOccurs=1`, so the conceptual cardinality is `[0..1]`; the pipeline emits exactly one canonical Pand-level value. | `gml:CodeType`. The `@codeSpace` attribute identifies the vocabulary; this pipeline uses the Dutch RVO NTA-8800 typology verbatim with `@codeSpace = CS_RVO_GEBOUWTYPE`. |
| `gen:stringAttribute` / `doubleAttribute` / `dateAttribute` / `measureAttribute` / `intAttribute` | [xsd/citygml/2.0/generics.xsd:76-164](../xsd/citygml/2.0/generics.xsd) | `[0..*]` on any city object | Fallback for fields with no native Energy ADE slot. `measureAttribute` carries `name`, `value`, `uom`. |

Two structural facts that constrain everything below:

1. **`nrg3:Energy` attaches directly to any `AbstractCityObject` via the `nrg3:resource` substitution element** (line 1366: `<element name="resource" substitutionGroup="core:_GenericApplicationPropertyOfCityObject" type="nrg3:AbstractResourcePropertyType">`). Building, BuildingUnit, Zone, Device, all of them host an `nrg3:resource` slot. EP-online metrics are VBO-scoped, so they parent under the BuildingUnit. No xlink, no top-level workaround.
2. **There is no native slot for regulatory thresholds, thermal-comfort metrics, EMG-Forfaitair calculation conventions, or a multi-source `yearOfConstruction`.** Each of these is a deliberately-skipped column or a documented schema gap; see § 6.7.

### 6.2. Aggregation model: per-VBO vs. per-Pand

EP-online ships one row per certificate, keyed on `BAGVerblijfsobjectID` or address. A Pand may contain multiple VBOs, each with its own certificate. The pipeline already builds one `bldg:Building` per Pand and one `nrg3:BuildingUnit` per VBO. EP-online metrics inherit this split:

| Metric kind | Lives on | Reason |
|---|---|---|
| Identifying / certifying metadata (label, dates, methodology) | `nrg3:EnergyPerformanceCertificate` under each `BuildingUnit` | Per-VBO is correct because each apartment can hold its own certificate. |
| Primary type (Gebouwtype) | native `nrg3:bdgType` on the Building, value = Dutch RVO NTA-8800 term verbatim, `@codeSpace = CS_RVO_GEBOUWTYPE` | The primary building type is fixed at the structure level: a Pand has one primary type regardless of how many VBOs sit inside. EP-online ships `Gebouwtype` per-VBO only because the CSV is row-per-cert. Multi-VBO Pands take the most-recently-registered cert's `Gebouwtype` (mirroring `address_match._label_timestamp`). The Dutch term goes through verbatim because translating to the Energy ADE `BuildingTypeValue.xml` codelist would silently merge `Hoekwoning` / `Tussenwoning` / `2-onder-1-kap` under a single `singleFamilyHouse` member; the `@codeSpace` URL identifies the source vocabulary so consumers do not mistake the value for an Energy-ADE codelist member. |
| Secondary qualifier (Gebouwsubtype) | `nrg3:BuildingUnit` via `gen:stringAttribute name="bdgSubtypeEPOnline"` (Dutch RVO term verbatim) | Two VBOs in one Pand can carry different subtypes (mixed-use, partial conversion). EnergyADE 3.0 has no native `nrg3:bdgSubtype` element. The `EPOnline` suffix flags the source vocabulary so a downstream reader does not mistake the Dutch term for an Energy-ADE codelist member. |
| Year of construction | `bldg:yearOfConstruction` (BAG, existing) **and** `gen:intAttribute name="yearOfConstructionEPOnline"` (EP-online), both on the Building. Two `nrg3:Metadata` blocks on the Building, one per source. The EP-online block also covers `nrg3:bdgType` since both Pand-level emissions share the source. | A building is constructed once: year of construction is a Pand-level fact regardless of how many VBOs sit inside. Multi-VBO Pands take the most-recently-registered cert's `Bouwjaar` (mirroring `address_match._label_timestamp`); inter-VBO disagreement surfaces as data-quality noise but the canonical pick stays single-valued. `Bouwjaar` and `Gebouwtype` canonical picks are independent (per-field) so each can come from a different cert when one cert leaves the field empty. |
| Thermal-zone area (`GebruiksoppervlakteThermischeZone`) | second `nrg3:QualifiedArea` on the BuildingUnit (sibling of the BAG `oppervlakte`), `type="netFloorArea"` and `source="EP-online Mutatiebestand v4 (RVO)"` | The schema lets `BuildingUnit/area` repeat: emitting the EP-online thermal-zone area as a sibling QualifiedArea (same type, distinct source) keeps both numbers queryable without an intermediate `nrg3:Zone` wrapper. Every per-m² energy metric on that BuildingUnit normalises against this same area. |
| Energy-flow metrics (Energiebehoefte, primary, renewable share, CO₂) | `nrg3:Energy` attached to the BuildingUnit via the `nrg3:resource` substitution slot | The XSD lets any AbstractCityObject host an Energy resource (line 1366); the BuildingUnit is the right scope because EP-online ships these as per-VBO numbers. The renewable-share `gen:measureAttribute` also lives on the BuildingUnit (the EPC cannot host generic attributes; see § 6.5j). |

This mirrors how RVO publishes the data: a certificate is a per-VBO event. **No Pand-level reduction or tiebreak** for the per-VBO fields: each VBO surfaces its own EP-online classification independently.

### 6.3. Calculation regimes (read first)

Every per-column rationale below depends on the *regime* the row's `Berekeningstype` falls into. EP-online ships three families of calculation methods side by side, with **divergent units and field availability** for the same CSV columns. Skipping this distinction was the bug that produced the original v1 of this mapping (which assumed every row was an NTA 8800 row); recording it explicitly is the only honest way to keep the per-column tables short.

#### 6.3.1. Empirical distribution (full v20260401 vintage, 5.12 M rows)

Counts and value distributions across the entire register, partitioned by `Berekeningstype`. Run from [`fetchers/eponline.py`](../citygml_energy/city_builder/fetchers/eponline.py)'s cached bundle on 2026-04-29.

| Regime | Match string(s) | n | `BerekendeEnergieverbruik` median | range (p10–p90) | `BerekendeCO2Emissie` zero-rate | `GebruiksoppervlakteThermischeZone` populated | `EnergieIndex` populated | `PrimaireFossieleEnergie` populated |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **NTA 8800** | `NTA 8800:...` | 3 282 787 | **150** | 28 — 273 | 0.0% | **100%** | 0% | **100%** |
| **legacy_total: Definitief Energielabel** | `Rekenmethodiek Definitief Energielabel` | 1 438 444 | **93 039** | 55 182 — 157 578 | **100%** (placeholder) | 0% | 0% | 0% |
| **legacy_total: Nader Voorschrift / ISSO** | `Nader Voorschrift`, `ISSO75.3` (etc.) | 1 401 002 | **50 883** | 13 650 — 90 877 | 0.1% (real zeros) | 0% | 100% (`EnergieIndex` field) | 0% |

The **three-orders-of-magnitude gap** between the NTA 8800 median (150) and the legacy medians (50 000-100 000) is the smoking gun: the same CSV column carries kWh/(m²·yr) for NTA 8800 and **MJ/yr (total)** for legacy methods. Cross-checking with NEN 7120 documentation (the legacy calculation standard) confirms MJ/yr as the legacy convention; NTA 8800 explicitly switched to kWh/(m²·yr) in 2021.

#### 6.3.2. Field-availability matrix

| Column | NTA 8800 | Definitief Energielabel | Nader Voorschrift / ISSO |
|---|:---:|:---:|:---:|
| `GebruiksoppervlakteThermischeZone` | ✓ kWh/(m²·yr) denominator | — | — |
| `Energiebehoefte` (BENG-1) | ✓ kWh/(m²·yr) | — | — |
| `Warmtebehoefte` | ✓ kWh/(m²·yr) | — | — |
| `PrimaireFossieleEnergie` (BENG-2) | ✓ kWh/(m²·yr) | — | — |
| `AandeelHernieuwbareEnergie` (BENG-3) | ✓ % | — | — |
| `BerekendeEnergieverbruik` | ✓ kWh/(m²·yr) | ✓ MJ/yr (total) | ✓ MJ/yr (total) |
| `BerekendeCO2Emissie` | ✓ kg/(m²·yr) | placeholder `0,00` | ✓ kg/yr (total) |
| `EnergieIndex` (legacy EI) | — | — | ✓ dimensionless |

`✓` = populated as data; `—` = empty for ~100% of rows in the regime; `placeholder` = column is filled with a non-data sentinel (always `0,00` in this case).

#### 6.3.3. Regime classification rule

Implemented as [`EnergyLabel.calculation_regime()`](../citygml_energy/city_builder/fetchers/eponline.py) and dispatched by [`attach_energy_resources_to_building_unit()`](../citygml_energy/city_builder/energy_resources.py):

- `nta8800` ← `Berekeningstype` contains `"NTA 8800"`
- `legacy_total` ← contains any of `"Definitief Energielabel"`, `"Nader Voorschrift"`, `"ISSO75"`, `"ISSO 75"`, `"ISSO82"`, `"ISSO 82"`
- `unknown` otherwise (including empty / null). Emit no Energy resources, because the unit semantics of an unrecognised method cannot be defended.

`co2_is_placeholder()` is a per-regime helper that returns `True` only for the Definitief Energielabel branch (the only regime where `0,00` is structural padding rather than a measurement).

#### 6.3.4. Why this matters for emission

The unit asymmetry forces a regime-aware emitter:

- **NTA 8800:** emit up to four `nrg3:Energy` resources in `kWh/m2/a`; CO₂ on the BENG-2 resource in `kg/m2/a`. `isAmountNormalized=true` and **omit `normalizationValue`**: the per-m² basis is already encoded in the uom string, so a redundant `<nrg3:normalizationValue uom="m2">…</nrg3:normalizationValue>` next to `<nrg3:amount uom="kWh/m2/a">…</nrg3:amount>` is clutter. `normalizationValue` is optional in the XSD ([Energy_ADE_3.0_beta8.xsd:642](../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd#L642)).
- **legacy_total:** emit ONE `primary` resource in `MJ/a` carrying the raw `BerekendeEnergieverbruik` total. CO₂ rides on this same resource in `kg/a` (total) for the Nader Voorschrift / ISSO branch; the Definitief Energielabel placeholder `0,00` is suppressed via `co2_is_placeholder()`. `isAmountNormalized=false` because the value is an absolute total.
- **unknown:** nothing is emitted.

`type` values match `EnergyTypeValue.xml` exactly (`net | primary | final`); an earlier draft wrote `netEnergy` / `primaryEnergy` / `finalEnergy` (with the spurious `Energy` suffix), which were not codelist members. Per-metric `endUse` routing is per `EnergyEndUseValue.xml`: only `Warmtebehoefte` is `spaceHeating`; the three multi-end-use figures (BENG-1 = heating + cooling demand, BENG-2 = aggregate primary, BerekendeEnergieverbruik = aggregate delivered or legacy total) use `otherOrCombination`. The codelist has no explicit `spaceHeatingAndCooling` entry that would fit BENG-1 cleanly; `otherOrCombination` is the schema-honest fallback. A future EnergyADE codelist extension that introduced a combined-thermal-demand value would fit BENG-1 better.

The `BerekendeEnergieverbruik` `type` choice deserves emphasis because the same column ships different physical quantities across regimes:

| Regime | What `BerekendeEnergieverbruik` ships | `nrg3:Energy/type` |
|---|---|---|
| NTA 8800 | Delivered final energy in kWh/(m²·yr), per RVO v5 Public API ("het berekende totale energieverbruik in kWh/m²·jaar") | `final` |
| legacy_total | Karakteristiek primair fossiel energiegebruik EP_tot in MJ/yr, per NEN 7120 §5 formula 5.9 | `primary` |

The cross-regime divergence on the same column name is intentional and grounded in RVO's own historical methodology bridge. Code: [`energy_resources.py::_attach_legacy_total_resource`](../citygml_energy/city_builder/energy_resources.py) sets `type=_ENERGY_TYPE_PRIMARY`; [`energy_resources.py::_attach_nta8800_resources`](../citygml_energy/city_builder/energy_resources.py) sets `type=_ENERGY_TYPE_FINAL` for the BerekendeEnergieverbruik resource.

### 6.4. Verdict legend

For every column, one verdict:
- **Native:** direct fit; the column has a one-element XSD slot.
- **Native (derived):** the column needs a small lookup or normalisation before it can fill a native slot.
- **Filter-only:** read for joining or de-duplication; never written.
- **gen:Attribute:** no native slot; emit as a typed `gen:*Attribute` to preserve the value losslessly under a documented `name`. Used sparingly: only where the value is load-bearing for the thesis question and the schema offers no native home.
- **Skip (latent):** fetched but not written. Could be added later either via a `gen:*Attribute` or via a future schema extension; this doc records the potential target and the reason it is not mapped today.
- **Drop:** privacy, redundancy with another source, or out of scope. Not a candidate for later mapping.

### 6.5. Per-column mapping (the 42 columns)

#### 6.5a. Address and identifier columns (5)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Postcode` | NL postcode | address-key join only | Filter-only | Already on `core:Address` from BAG; duplicating would create source-attribution ambiguity. |
| `Huisnummer` | House number | address-key join only | Filter-only | Same. |
| `Huisletter` | House letter | address-key join only | Filter-only | Same. |
| `Huisnummertoevoeging` | House number suffix | address-key join only | Filter-only | Same. |
| `BAGVerblijfsobjectID` | BAG VBO id | primary join key | Filter-only | Already on `nrg3:BuildingUnit/identifier` (codeSpace `CS_BAG_VERBLIJFSOBJECT`) from BAG. |

#### 6.5b. Date columns (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Registratiedatum` | Cert registration date | `nrg3:EnergyPerformanceCertificate.validFrom` (`xs:dateTime`, midnight, naive — no timezone offset; xsdata serialises `T00:00:00` without a `Z` or `+HH:MM` suffix, matching the rest of the project) | Native | The day the cert became legally valid in the EP-online registry; only registered labels are *rechtsgeldig* per RVO's `Handleiding EP-online: opvragen van bestanden` (v1.0, feb 2025), §1. Implementation: [`builders/epc.py::_build_epc`](../citygml_energy/city_builder/builders/epc.py). Also drives multi-VBO tiebreak (§ 6.2). |
| `GeldigTot` (= Opnamedatum + 10 years per RVO) | Cert expiry | `nrg3:EnergyPerformanceCertificate.validTo` (`xs:dateTime`, midnight, naive — same convention as `validFrom`) | Native | `_build_epc`. |
| `Opnamedatum` | Energy-advisor inspection date | `nrg3:EnergyPerformanceCertificate.creationDate` (`xs:date`) | Native | The day the certificate document came into existence on-site, before registration. Distinct from `Registratiedatum`: the inspection may be months earlier (RVO Bijlage 2 documents the two as explicitly distinct dates). `_build_epc`. Also tie-breaker for duplicate rows in `address_match` (latest opname wins). |

#### 6.5c. Label (1)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Energieklasse` | Letter grade A+++++ to G | `nrg3:EnergyPerformanceCertificate.label` (`xs:string`, required) + `app:Appearance` theme `energyLabel` colour | Native | Drives both the EPC attribute and the building's fill colour via `epc_score.label_to_rgb`. The numeric backing the letter is on `EnergyPerformanceCertificate.value` and is sourced from `BerekendeEnergieverbruik` (regime-aware uom; § 6.5k). |

#### 6.5d. Methodology and quality flags (5)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Berekeningstype` | NTA 8800 calculation variant string | `nrg3:EnergyPerformanceCertificate.certificationMethod` | Native | Verbatim string; no codelist in NTA 8800 maps cleanly. Joined with `SoortOpname` via ` / ` (no em dash). Implementation: [`builders/epc.py::_certification_method_string`](../citygml_energy/city_builder/builders/epc.py). |
| `SoortOpname` | `Basisopname` / `Detailopname` | concatenated into `certificationMethod` (e.g. `"Basisopname / NTA 8800:2024 (basisopname woningbouw)"`) | Native (derived) | Inspection-rigour qualifier. Concatenation chosen over a separate field. |
| (no source column) | XSD-required cert validity flag | `nrg3:EnergyPerformanceCertificate.status` (inherited from `nrg3:AbstractFeatureWithLifeSpan`, `gml:CodeType`, codeSpace = `EPCStatusValue.xml`) | Native (constant) | Hard-coded `"actual"` for every emitted cert. Every row in the EP-online Mutatiebestand is by definition the registered, legally-valid certificate for the VBO ("alleen deze geregistreerde labels zijn rechtsgeldig" — RVO Handleiding EP-online: opvragen van bestanden, v1.0 feb 2025, §1), so the codelist member `actual` (vs. `potential` / `unknown`) is correct unconditionally. Implementation: [`builders/epc.py::_build_epc`](../citygml_energy/city_builder/builders/epc.py) line ~452. Distinct from EP-online's `Status` column (Bestaand / Nieuwbouw / Verbouw) directly below — that is a *lifecycle* signal, not a *cert-validity* one. |
| `Status` | `Bestaand` / `Nieuwbouw` / `Verbouw` | none today; potential target = `gen:stringAttribute name="epOnlineStatus"` on the BuildingUnit, OR a future `bldg:condition`-style lifecycle field | Skip (latent) | Lifecycle signal at certification time. SIG3D's `bldg:class` is a CityGML usage codelist (residential / commercial), not a lifecycle one. No native Energy ADE lifecycle slot. The cert-level `nrg3:status` row above is a *different* field and is always emitted. |
| `OpBasisVanReferentiegebouw` | `Ja`/`Nee`: was the cert based on a reference building rather than measured | none today; potential target = `gen:stringAttribute name="epOnlineReferenceBuildingBased"` on the EPC | Skip (latent) | Quality flag. Important for thesis-grade interpretation but not load-bearing for the building-physics output. The information is also encodable as part of `certificationMethod` if needed later. |
| `Certificaathouder` | Name of the certifying organisation | none | Drop | Personal-ish data and not load-bearing for energy modelling. The cert *type* (`type="totalEnergyDemand"` on the EPC) plus `nrg3:Metadata/source = "EP-online Mutatiebestand v4 (RVO)"` already attributes the source register; adding the certifier introduces FAIR-data noise without modelling value. |

#### 6.5e. Building classification (4)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Gebouwklasse` | `W` (woning) / `U` (utility) | none today; potential target = `gen:stringAttribute name="epOnlineGebouwklasse"` on Building, OR derivable from the `Gebouwtype` lookup | Skip (latent) | Coarse class. Mostly redundant with `Gebouwtype` (every Gebouwtype belongs unambiguously to one Gebouwklasse). |
| `Gebouwtype` | RVO NTA-8800 building-type taxonomy (e.g. `Rijwoning hoek`, `Vrijstaande woning`, `Kantoorgebouw`) | native `nrg3:bdgType` on the Building, value = Dutch RVO term verbatim, `@codeSpace = CS_RVO_GEBOUWTYPE` | Native | The codeSpace points at Dictu's canonical NTA 8800 generic-upload XSD (`monitoringsbestand.xsd v4.4`) on GitHub, which declares the closed `TypeBuilding` simpleType the values are drawn from. Pinned to the `master` branch; the closed enumeration of basic terms has been stable across v4.0–v4.4. Per-field canonical pick via `_pick_canonical_eponline_label`. Implementation: [`builders/epc.py::apply_eponline_pand_attribution_to_building`](../citygml_energy/city_builder/builders/epc.py). |
| `Gebouwsubtype` | RVO secondary qualifier (e.g. `appartement-portiekflat`, `rijwoning-tussen`) | `gen:stringAttribute name="bdgSubtypeEPOnline"` on each `nrg3:BuildingUnit`, value = Dutch RVO term verbatim | Native (derived) | Per-VBO because two VBOs in one Pand can carry different subtypes (mixed-use, partial conversion). EnergyADE 3.0 has no native `nrg3:bdgSubtype` element. The `EPOnline` suffix on the attribute name flags the source vocabulary so a downstream reader does not mistake the Dutch term for an Energy-ADE codelist member. Implementation: `_apply_eponline_classification_to_building_unit`. |
| `SBICode` | Economic-activity code (utility buildings only) | none today; potential target = `gen:stringAttribute name="sbiCode"` on Building | Skip (latent) | Applies only to utility buildings. The ISO-registered SBI codelist is well-known so a future map-on-demand step can recover it. |

#### 6.5f. BAG cross-references (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `BAGLigplaatsID` | BAG handle for a houseboat mooring | none | Drop | The pipeline only builds Pand-based Buildings; ligplaatsen are out of scope. |
| `BAGStandplaatsID` | BAG handle for a caravan plot | none | Drop | Same reason as ligplaats. |
| `BAGPandIDs` | Comma-separated parent Pand ids | none | Drop | Redundant with `pandidentificatie` from BAG VBO; the join already resolves this. |

#### 6.5g. Project metadata (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Projectnaam` | Free-text project name | none | Drop | Operator-entered free text whose semantics RVO does not document; not load-bearing for energy modelling. |
| `Projectobject` | Free-text project sub-identifier | none | Drop | Same. |
| `Detailaanduiding` | Long-form address supplement | none | Drop | BAG's structured xAL is the authoritative address; EP-online's free-text supplement adds noise without resolving anything BAG cannot. |

#### 6.5h. Building physics / area (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `Bouwjaar` | Year of construction | (a) `bldg:yearOfConstruction` (CityGML core, not Energy ADE) populated from BAG `bouwjaar`, behaviour unchanged at Building level; (b) `gen:intAttribute name="yearOfConstructionEPOnline"` on the **Building** (Pand level, picked from the most-recently-registered EP-online cert across the Pand's VBOs); (c) two `nrg3:Metadata` blocks on the Building, one attributing BAG, one attributing EP-online. | Native (BAG) + gen:Attribute with metadata (EP-online, per-Pand) | A building is constructed once: year-of-construction is a Pand-level fact. EP-online ships `Bouwjaar` per-VBO only because the Mutatiebestand CSV is one-row-per-cert. Multi-VBO Pands take the most-recently-registered cert's `Bouwjaar` (mirroring `address_match._label_timestamp` so the per-Pand reduction order matches the per-VBO de-duplication order earlier in the pipeline); inter-VBO disagreement is a data-quality signal. The native multi-source pattern in Energy ADE (`bdgArea` / `bdgHeight` / `bdgVolume` repeating with different `source` strings) is Measure-typed and cannot be used for an `xs:gYear`; documented as a schema gap in § 6.7. |
| `GebruiksoppervlakteThermischeZone` | Thermal-zone floor area (m²) | second `nrg3:QualifiedArea` on the BuildingUnit (sibling of the BAG `oppervlakte` entry), `type="netFloorArea"` (codeSpace `AreaTypeValue.xml`), `source="EP-online Mutatiebestand v4 (RVO)"`, uom `m2` | Native (NTA 8800 only) | The denominator for every per-m² NTA 8800 energy metric below. `BuildingUnit/area` is `[0..*]` so emitting the EP-online value as a sibling of the BAG `oppervlakte` (same type, distinct `source`) is the cleanest schema-permissible encoding; both numbers stay queryable side-by-side without an intermediate `nrg3:Zone` wrapper. The two values typically differ slightly because the EP-online thermal envelope excludes some annex spaces that NEN 2580 `gebruiksoppervlakte` includes. Empty for ~100% of legacy-regime rows (§ 6.3); only NTA 8800 certs populate it. Implementation: `build_building_unit`. |
| `Compactheid` | Surface-to-volume ratio (m²/m³) | none today; potential target = `gen:doubleAttribute name="compactheid"` on the BuildingUnit, OR a future Energy ADE `Zone/compactness` field | Skip (latent) | No native slot for a scalar building-shape descriptor. Useful research signal (low compactness correlates with high heating demand) and a candidate for a future Energy ADE extension. |

#### 6.5i. Energy indices (4)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `EnergieIndex` | Pre-NTA-8800 EI metric | none | Drop (legacy) | Pre-2021 metric, mathematically incompatible with NTA 8800 BENG metrics. Including it would confuse longitudinal analysis rather than help it. |
| `EnergieIndexEMGForfaitair` | Same with EMG forfait correction | none | Drop (legacy) | Same as above. |
| `Energiebehoefte` (BENG-1) | Net energy demand for heating + cooling (kWh/m²·yr) | `nrg3:Energy` resource attached to BuildingUnit via `<nrg3:resource>`: `type="net"`, `endUse="otherOrCombination"`, `operationType="demands"`, `referencePeriod="year"`, `amount` carries the value with uom `kWh/m2/a`, `isAmountNormalized=true` (and **no `normalizationValue`** since the uom string already encodes the per-m² basis). | Native (NTA 8800 only) | This is BENG-1. Empty for legacy-regime rows. The CSV ships one combined heating+cooling number; `endUse=otherOrCombination` because the codelist has no explicit "spaceHeatingAndCooling" entry that would fit cleanly. Both the uom (`kWh/m2/a`) and `referencePeriod="year"` carry the annual scope. Implementation: `attach_energy_resources_to_building_unit`. |
| `Warmtebehoefte` | Net heating-only demand (kWh/m²·yr) | second `nrg3:Energy` resource on the same BuildingUnit: `type="net"`, `endUse="spaceHeating"`, `description="Warmtebehoefte (NTA 8800 net heating demand)"`, otherwise as above. | Native (NTA 8800 only) | NTA 8800 reports both numbers and they are not redundant: `Warmtebehoefte` is heating-only, `Energiebehoefte` is the BENG-1 sum. `description` field carries the unambiguous Dutch source name (`Energiebehoefte (BENG-1, heating + cooling)` vs. `Warmtebehoefte (NTA 8800 net heating demand)`). The difference between the two values is implicitly the cooling component. Empty for legacy-regime rows. |

#### 6.5j. Primary energy and renewable share (4)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `PrimaireFossieleEnergie` (BENG-2) | Primary fossil energy use (kWh/m²·yr) | `nrg3:Energy` resource on the BuildingUnit: `type="primary"`, `endUse="otherOrCombination"`, `operationType="demands"`, `referencePeriod="year"`, `amount` with uom `kWh/m2/a`, `isAmountNormalized=true`. The BENG-2 resource also carries `co2Equivalent` (see `BerekendeCO2Emissie` in § 6.5k). | Native (NTA 8800 only) | The clean BENG-2 fit. `EnergyTypeValue.xml` includes `primary` exactly for this purpose (UML page 20). BENG-2 aggregates every NTA-8800 demand category, so `endUse=otherOrCombination`. Empty for legacy-regime rows; the legacy "total annual primary energy" is reported instead in `BerekendeEnergieverbruik` in MJ/yr. |
| `PrimaireFossieleEnergieEMGForfaitair` | Same with EMG-Forfaitair correction | none | Drop | Same physical quantity computed under a different convention; the schema has no slot for "the same metric, calculated differently". The Forfaitair correction is an internal NTA 8800 calculation step, not an independent metric. |
| `AandeelHernieuwbareEnergie` (BENG-3) | Renewable-energy share (%) | `gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie"` on the **BuildingUnit** (not the EPC), uom `percent` | gen:Attribute (NTA 8800 only) | Energy ADE 3.0 has no renewable-share slot. `nrg3:EnergyPerformanceCertificateType` extends `AbstractFeatureWithLifeSpanType` directly (not via CityObject), so the EPC cannot host `gen:*Attribute` children. The BuildingUnit (which descends from CityObject) is the closest container at the same per-VBO scope. Empty for legacy-regime rows. |
| `AandeelHernieuwbareEnergieEMGForfaitair` | Same with EMG-Forfaitair | none | Drop | Same Forfaitair-convention reasoning as `PrimaireFossieleEnergieEMGForfaitair`. |

#### 6.5k. Calculated emissions and use (3)

| Column | Meaning | Target | Verdict | Rationale |
|---|---|---|---|---|
| `BerekendeCO2Emissie` | Calculated CO₂ emission. **Unit depends on regime** (§ 6.3): kg/(m²·yr) for NTA 8800; placeholder `0,00` for Definitief Energielabel (skipped); kg/yr (total) for Nader Voorschrift / ISSO. | NTA 8800: `nrg3:Energy.co2Equivalent` on the `PrimaireFossieleEnergie` resource, uom `kg/m2/a`. legacy_total Nader Voorschrift / ISSO: `co2Equivalent` on the single legacy `primary` resource, uom `kg/a` (total). Definitief Energielabel: no emission (placeholder filtered via `co2_is_placeholder()`). | Native (regime-aware) | `co2Equivalent` is a property of `AbstractResource` (line 646), not a standalone feature. Attaching it to the regime's natural energy carrier (BENG-2 for NTA 8800, the legacy total for Nader Voorschrift / ISSO) is the conceptually correct place: emissions are downstream of fossil energy. The Definitief Energielabel branch reports `0,00` for 1 438 399 of 1 438 444 rows in the v20260401 vintage (99.997%); the field is structural padding rather than a measurement, so suppressing it avoids fabricating "zero CO₂ emission" claims for old houses that demonstrably emit CO₂. |
| `BerekendeEnergieverbruik` | Calculated total annual energy use. **Unit depends on regime** (§ 6.3): kWh/(m²·yr) for NTA 8800 (delivered final energy); MJ/yr **total** for legacy_total (NEN 7120 lineage). | (1) `nrg3:Energy` resource via `nrg3:resource`. NTA 8800: `type="final"`, `amount` uom `kWh/m2/a`, `isAmountNormalized=true`, no `normalizationValue`. legacy_total: `type="primary"` (NEN 7120 §5 formula 5.9 EP_tot), `amount` uom `MJ/a`, `isAmountNormalized=false` (it is an absolute total, not per-m²); description marks it as "legacy NEN 7120 method, total annual primary fossil energy in MJ/yr" so a downstream consumer cannot mistake it for the NTA 8800 figure. (2) **Same value also lands on `nrg3:EnergyPerformanceCertificate.value`** (`gml:MeasureType`, optional, XSD line 1430) as the numeric backing the letter on `nrg3:label`. The `value` element uses the **same regime-aware uom** as the matching `nrg3:Energy.amount` (`kWh/m2/a` for NTA 8800, `MJ/a` for legacy_total) — both wired through the public `UOM_KWH_PER_M2_PER_A` / `UOM_MJ_PER_A` constants in `energy_resources.py`, so EPC.value and the Energy resource cannot drift apart. `unknown` regime: `EPC.value` skipped (no defensible uom). | Native (regime-aware) | The only column populated in BOTH regimes, but with **divergent units** (median 150 vs. 93 039 across 5.12 M rows; § 6.3 has the magnitude evidence). Distinct from `Energiebehoefte` (net) and `PrimaireFossieleEnergie` (primary): for NTA 8800 this is the delivered final-energy figure; for legacy this is the absolute primary-energy total in megajoules. Cross-regime numerical comparison is *not* a goal of `EPC.value`. `gml:MeasureType` requires `@uom` exactly so heterogeneous regimes can coexist without forcing a fictive common unit. Aggregate longitudinal analysis should aggregate from `nrg3:resource`/`nrg3:Energy` (where the `EnergyTypeValue` tagging already disambiguates `primary` vs `final`), not from `EPC.value`. |
| `Temperatuuroverschrijding` (BENG-4) | Summer overheating hours | none today; potential target = `gen:measureAttribute` on the BuildingUnit with uom `h`, OR a future Energy ADE `Zone/comfortIndicator` field | Skip (latent) | No thermal-comfort indicator slot in `AbstractZone` even though the type carries `isCooled` / `isMechanicallyVentilated`. |

#### 6.5l. BENG / Bouwbesluit thresholds (4)

All four thresholds skipped. Reasoning: Energy ADE 3.0 has no native slot for regulatory requirements (the schema models actual values only); committing to a `gen:measureAttribute` encoding for every threshold is generic-attribute clutter for a category of data the thesis does not currently analyse against. Skipping is reversible: each threshold has a clean potential target listed below.

| Column | Meaning | Potential target if revisited | Verdict |
|---|---|---|---|
| `EisEnergiebehoefte` | BENG-1 threshold (kWh/m²·yr) | `gen:measureAttribute name="epOnlineEisEnergiebehoefte"` uom `kWh/m2/a`, OR a future Energy ADE `Resource/threshold` field | Skip (latent) |
| `EisPrimaireFossieleEnergie` | BENG-2 threshold (kWh/m²·yr) | `gen:measureAttribute name="epOnlineEisPrimaireFossieleEnergie"` uom `kWh/m2/a` | Skip (latent) |
| `EisAandeelHernieuwbareEnergie` | BENG-3 threshold (%) | `gen:measureAttribute name="epOnlineEisAandeelHernieuwbareEnergie"` uom `percent` | Skip (latent) |
| `EisTemperatuuroverschrijding` | BENG-4 threshold (h) | `gen:measureAttribute name="epOnlineEisTemperatuuroverschrijding"` uom `h` | Skip (latent) |

### 6.6. Worked examples

#### 6.6.1. NTA 8800 cert: full XML output for one VBO

A residential VBO with a 2024 NTA 8800 Detailopname certificate. Every field shown is *written*; nothing in this example is a Skip-(latent) or Drop column.

Structural distribution to keep in mind:

- `bldg:yearOfConstruction` (BAG) and `gen:intAttribute name="yearOfConstructionEPOnline"` (EP-online) both live at Building level: a building is constructed once. The native `nrg3:bdgType` (Pand-level primary type, sourced from EP-online's `Gebouwtype` and carrying the Dutch RVO term verbatim) sits next to it on the same Building. Two `nrg3:Metadata` blocks on the Building (one BAG, one EP-online) document the two sources.
- The thermal-zone area (`GebruiksoppervlakteThermischeZone`) rides as a second `nrg3:QualifiedArea` on each BuildingUnit, alongside the BAG `oppervlakte` entry. `BuildingUnit/area` is `[0..*]`.
- The remaining EP-online emissions (`bdgSubtypeEPOnline`, `epOnlineAandeelHernieuwbareEnergie`, and however many `nrg3:Energy` resources the regime emits) live on each `nrg3:BuildingUnit`.
- One `nrg3:Metadata` block per BuildingUnit attributes EP-online for the per-VBO emissions on that unit.

The snippet below is **schema-derived, not byte-verified against a city-pipeline run**: the surrounding fact tables are exercised by `tests/test_mapping_index_in_sync.py`, but the exact xsdata serialization order shown here has not been diffed against a fresh AOI output. Element ordering follows the XSD sequence as resolved by xsdata: inside `nrg3:Metadata`, `qualityDescription` precedes `source`; on `bldg:Building`, every `_GenericApplicationPropertyOfCityObject` substitution (`nrg3:Metadata`, `nrg3:identifier`, `gen:intAttribute`) appears *before* the `bldg:Building` sequence (`yearOfConstruction`, `roofType`, `storeysAboveGround`, `buildingUnit`), and every `_GenericApplicationPropertyOfAbstractBuilding` substitution (`nrg3:bdgType`, `nrg3:bdgVolume`, `nrg3:bdgHeight`) appears *after* it; on `nrg3:BuildingUnit`, children fall as `Metadata`, then resources, identifier, generic attributes, areas, type, address, EPC. No `gml:name` on the Building (BAG carries no per-Pand human-readable label, see §3); no `gml:id` on the `nrg3:Energy` resources (the code does not assign one). The four NTA 8800 resources are emitted in the order BENG-2 → BENG-1 → Warmtebehoefte → BerekendeEnergieverbruik (the order in [`_attach_nta8800_resources`](../citygml_energy/city_builder/energy_resources.py)). When this section is reconciled against a real city-AOI GML, any divergence should update the snippet rather than the code.

```xml
<bldg:Building gml:id="pand_0114100000206140">
  <!-- Year-of-construction is per-Pand: BAG and EP-online both report a single
       value for the whole building. Two Metadata blocks document each source. -->
  <nrg3:Metadata>
    <nrg3:qualityDescription>Source for bldg:yearOfConstruction on this Pand.</nrg3:qualityDescription>
    <nrg3:source>BAG bag:pand.bouwjaar (PDOK WFS v2.0)</nrg3:source>
  </nrg3:Metadata>
  <nrg3:Metadata>
    <nrg3:qualityDescription>Source for the EP-online Pand-level emissions on this Building: gen:intAttribute name="yearOfConstructionEPOnline" and nrg3:bdgType (both picked from the most-recently-registered EP-online certificate across this Pand's VBOs that carries the field). The per-VBO Gebouwsubtype, renewable-energy share, thermal-zone area, and Energy resources have their own EP-online Metadata block on each BuildingUnit.</nrg3:qualityDescription>
    <nrg3:source>EP-online Mutatiebestand v4 (RVO)</nrg3:source>
  </nrg3:Metadata>
  <nrg3:identifier codeSpace="http://bag.basisregistraties.overheid.nl/bag/id/pand/">0114100000206140</nrg3:identifier>

  <!-- gen:intAttribute substitutes into _GenericApplicationPropertyOfCityObject,
       which falls in the inherited core:CityObject sequence position — ahead of
       bldg:Building's own sequence start (yearOfConstruction). -->
  <gen:intAttribute name="yearOfConstructionEPOnline">
    <gen:value>1956</gen:value>
  </gen:intAttribute>

  <bldg:yearOfConstruction>1955</bldg:yearOfConstruction>

  <!-- ...remaining 3DBAG-derived bldg:* attributes (bldg:roofType,
       bldg:storeysAboveGround) and LoD 0/1/2 geometries elided for
       brevity; see §5 for the full inventory... -->

  <nrg3:buildingUnit>
    <nrg3:BuildingUnit gml:id="bu_0114010000274521">

      <nrg3:Metadata>
        <nrg3:qualityDescription>Source for the EP-online-derived per-VBO emissions on this BuildingUnit: gen:stringAttribute name="bdgSubtypeEPOnline" (Dutch RVO Gebouwsubtype, verbatim); gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie" (BENG-3 renewable-energy share, %); nrg3:QualifiedArea type="netFloorArea" sourced from GebruiksoppervlakteThermischeZone (NTA 8800 thermal-zone area); nrg3:Energy resources via nrg3:resource: Energiebehoefte (BENG-1, net), Warmtebehoefte (NTA 8800 net heating demand), PrimaireFossieleEnergie (BENG-2, primary), BerekendeEnergieverbruik (NTA 8800 delivered/finaal total). Year of construction (yearOfConstructionEPOnline) and the primary building type (nrg3:bdgType) are at the Building level: a Pand is constructed once and its primary type is fixed at the structure level.</nrg3:qualityDescription>
        <nrg3:source>EP-online Mutatiebestand v4 (RVO)</nrg3:source>
      </nrg3:Metadata>

      <!-- Four nrg3:Energy resources via the nrg3:resource substitution
           (no xlink, no top-level cityObjectMember workaround). Emitted in
           the order BENG-2 → BENG-1 → Warmtebehoefte → BerekendeEnergieverbruik
           by _attach_nta8800_resources. -->

      <nrg3:resource>
        <nrg3:Energy>
          <gml:description>PrimaireFossieleEnergie (BENG-2)</gml:description>
          <nrg3:operationType codeSpace="...ResourceOperationTypeValue.xml">demands</nrg3:operationType>
          <nrg3:referencePeriod codeSpace="...ReferencePeriodValue.xml">year</nrg3:referencePeriod>
          <nrg3:amount uom="kWh/m2/a">63.0</nrg3:amount>
          <nrg3:isAmountNormalized>true</nrg3:isAmountNormalized>
          <!-- No <nrg3:normalizationValue>: the kWh/m2/a uom already
               encodes the per-m² basis. -->
          <nrg3:co2Equivalent uom="kg/m2/a">14.7</nrg3:co2Equivalent>
          <nrg3:type codeSpace="...EnergyTypeValue.xml">primary</nrg3:type>
          <nrg3:endUse codeSpace="...EnergyEndUseValue.xml">otherOrCombination</nrg3:endUse>
        </nrg3:Energy>
      </nrg3:resource>

      <nrg3:resource>
        <nrg3:Energy>
          <gml:description>Energiebehoefte (BENG-1, heating + cooling)</gml:description>
          <nrg3:operationType codeSpace="...">demands</nrg3:operationType>
          <nrg3:referencePeriod codeSpace="...">year</nrg3:referencePeriod>
          <nrg3:amount uom="kWh/m2/a">28.5</nrg3:amount>
          <nrg3:isAmountNormalized>true</nrg3:isAmountNormalized>
          <nrg3:type codeSpace="...">net</nrg3:type>
          <nrg3:endUse codeSpace="...">otherOrCombination</nrg3:endUse>
        </nrg3:Energy>
      </nrg3:resource>

      <nrg3:resource>
        <nrg3:Energy>
          <gml:description>Warmtebehoefte (NTA 8800 net heating demand)</gml:description>
          <nrg3:operationType codeSpace="...">demands</nrg3:operationType>
          <nrg3:referencePeriod codeSpace="...">year</nrg3:referencePeriod>
          <nrg3:amount uom="kWh/m2/a">25.1</nrg3:amount>
          <nrg3:isAmountNormalized>true</nrg3:isAmountNormalized>
          <nrg3:type codeSpace="...">net</nrg3:type>
          <nrg3:endUse codeSpace="...">spaceHeating</nrg3:endUse>
        </nrg3:Energy>
      </nrg3:resource>

      <nrg3:resource>
        <nrg3:Energy>
          <gml:description>BerekendeEnergieverbruik (delivered final energy)</gml:description>
          <nrg3:operationType codeSpace="...">demands</nrg3:operationType>
          <nrg3:referencePeriod codeSpace="...">year</nrg3:referencePeriod>
          <nrg3:amount uom="kWh/m2/a">35.4</nrg3:amount>
          <nrg3:isAmountNormalized>true</nrg3:isAmountNormalized>
          <nrg3:type codeSpace="...">final</nrg3:type>
          <nrg3:endUse codeSpace="...">otherOrCombination</nrg3:endUse>
        </nrg3:Energy>
      </nrg3:resource>

      <nrg3:identifier codeSpace="http://bag.basisregistraties.overheid.nl/bag/id/verblijfsobject/">0114010000274521</nrg3:identifier>

      <gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie">
        <gen:value uom="percent">42.0</gen:value>
      </gen:measureAttribute>
      <gen:stringAttribute name="bdgSubtypeEPOnline">
        <gen:value>rijwoning-hoek-kopgevel</gen:value>
      </gen:stringAttribute>

      <!-- Two QualifiedArea entries: same type ("netFloorArea"), distinct source.
           BAG oppervlakte and the EP-online thermal-zone area sit side-by-side. -->
      <nrg3:area>
        <nrg3:QualifiedArea>
          <nrg3:description>Usable floor area ('gebruiksoppervlakte' per NEN 2580) as recorded by the Dutch BAG register for this verblijfsobject.</nrg3:description>
          <nrg3:source>BAG bag:verblijfsobject.oppervlakte (PDOK WFS v2.0)</nrg3:source>
          <nrg3:value uom="m2">115.0</nrg3:value>
          <nrg3:type codeSpace="...AreaTypeValue.xml">netFloorArea</nrg3:type>
        </nrg3:QualifiedArea>
      </nrg3:area>
      <nrg3:area>
        <nrg3:QualifiedArea>
          <nrg3:description>EP-online thermal-zone floor area: the denominator every per-m² energy metric on this BuildingUnit is normalised against.</nrg3:description>
          <nrg3:source>EP-online Mutatiebestand v4 (RVO)</nrg3:source>
          <nrg3:value uom="m2">112.5</nrg3:value>
          <nrg3:type codeSpace="...AreaTypeValue.xml">netFloorArea</nrg3:type>
        </nrg3:QualifiedArea>
      </nrg3:area>

      <nrg3:type codeSpace="http://bag.basisregistraties.overheid.nl/id/concept/Gebruiksdoel">woonfunctie</nrg3:type>

      <!-- Address property on nrg3:BuildingUnit lives in the Energy ADE
           namespace (nrg3:address), NOT bldg:address. The xAL payload
           inside is identical to the per-building pipeline's address. -->
      <nrg3:address>
        <core:Address gml:id="addr_0114010000274521">
          <core:xalAddress>...xAL...</core:xalAddress>
          <core:multiPoint>...gml:MultiPoint...</core:multiPoint>
        </core:Address>
      </nrg3:address>

      <nrg3:energyPerformanceCertificate>
        <nrg3:EnergyPerformanceCertificate gml:id="epc_0114010000274521">
          <!-- Dates are inherited from nrg3:AbstractADEFeatureType /
               AbstractFeatureWithLifeSpanType (Energy_ADE_3.0_beta8.xsd
               lines 454, 477-478) and therefore serialise in the
               Energy ADE namespace, NOT in core:. -->
          <nrg3:creationDate>2024-05-01</nrg3:creationDate>
          <nrg3:validFrom>2024-05-14T00:00:00</nrg3:validFrom>
          <nrg3:validTo>2034-05-13T00:00:00</nrg3:validTo>
          <!-- Every cert in the EP-online register is rechtsgeldig per
               RVO § 1; "actual" is the EPCStatusValue codelist member.
               The pipeline hard-codes this value (see §6.5d). -->
          <nrg3:status codeSpace="...EPCStatusValue.xml">actual</nrg3:status>
          <!-- type = energy-domain scope (totalEnergyDemand: NTA 8800
               covers the full building budget). The "EP-online" provenance
               lives on the surrounding Metadata block. -->
          <nrg3:type codeSpace="...EPCTypeValue.xml">totalEnergyDemand</nrg3:type>
          <nrg3:label>A++</nrg3:label>
          <!-- value is the numeric backing the letter, sourced from
               BerekendeEnergieverbruik with regime-aware uom. -->
          <nrg3:value uom="kWh/m2/a">35.4</nrg3:value>
          <nrg3:certificationMethod>Detailopname / NTA 8800:2024 (detailopname woningbouw)</nrg3:certificationMethod>
        </nrg3:EnergyPerformanceCertificate>
      </nrg3:energyPerformanceCertificate>
    </nrg3:BuildingUnit>
  </nrg3:buildingUnit>

  <!-- Native nrg3:bdgType: Pand-level primary type, Dutch RVO term verbatim,
       @codeSpace points at the Dictu monitoringsbestand.xsd that declares
       the closed TypeBuilding simpleType the value is drawn from.
       Falls AFTER nrg3:buildingUnit because both substitute into
       bldg:_GenericApplicationPropertyOfAbstractBuilding, and xsdata
       walks the substitution group in attribute-iteration order
       (buildingUnit precedes bdgType / bdgVolume / bdgHeight). -->
  <nrg3:bdgType codeSpace="https://raw.githubusercontent.com/Dictu/EP-online-API/master/XSD/Energielabel/generieke%20xml%20v4.4/monitoringsbestand.xsd">Rijwoning hoek</nrg3:bdgType>

  <!-- ...nrg3:bdgVolume and nrg3:bdgHeight (3DBAG-derived) follow here,
       in that order; elided for brevity. See §5 for the full inventory. -->
</bldg:Building>
```

#### 6.6.2. legacy-regime cert: shape comparison

For comparison, here is what a row from VBO `0114010000280857` (Hoofdkanaal WZ 38, Emmer-Compascuum) — a 2019 G-label issued under the "Rekenmethodiek Definitief Energielabel, versie 1.2, 16 september 2014" method — looks like under the regime-aware emitter. Source CSV cells: `BerekendeEnergieverbruik=293361,52`, `BerekendeCO2Emissie=0,00`, every NTA 8800 BENG field empty, `GebruiksoppervlakteThermischeZone` empty, Bouwjaar=1930.

```xml
<nrg3:BuildingUnit gml:id="bu_0114010000280857">

  <nrg3:Metadata>
    <nrg3:qualityDescription>Source for the EP-online-derived per-VBO emissions ...</nrg3:qualityDescription>
    <nrg3:source>EP-online Mutatiebestand v4 (RVO)</nrg3:source>
  </nrg3:Metadata>

  <!-- ONE Energy resource in MJ/a (legacy total). No co2Equivalent because
       the Definitief Energielabel branch reports 0,00 as a method-level
       placeholder, not a measurement. -->
  <nrg3:resource>
    <nrg3:Energy>
      <gml:description>BerekendeEnergieverbruik (legacy NEN 7120 method, total annual primary fossil energy EP_tot per NEN 7120 §5 formula 5.9, in MJ/yr)</gml:description>
      <nrg3:operationType codeSpace="...">demands</nrg3:operationType>
      <nrg3:referencePeriod codeSpace="...">year</nrg3:referencePeriod>
      <nrg3:amount uom="MJ/a">293361.52</nrg3:amount>
      <nrg3:isAmountNormalized>false</nrg3:isAmountNormalized>
      <!-- Tagged "primary" not "final": the legacy NEN 7120 regime's
           BerekendeEnergieverbruik is the karakteristiek primair fossiel
           energiegebruik EP_tot per NEN 7120 §5 formula 5.9. The same
           column on NTA 8800 rows ships delivered/finaal energy
           (kWh/(m²·yr)) and is tagged "final". -->
      <nrg3:type codeSpace="...">primary</nrg3:type>
      <nrg3:endUse codeSpace="...">otherOrCombination</nrg3:endUse>
    </nrg3:Energy>
  </nrg3:resource>

  <nrg3:identifier codeSpace="http://bag.basisregistraties.overheid.nl/bag/id/verblijfsobject/">0114010000280857</nrg3:identifier>

  <gen:stringAttribute name="bdgSubtypeEPOnline">
    <gen:value>rijwoning-tussen</gen:value>
  </gen:stringAttribute>

  <!-- Single QualifiedArea: BAG only (no EP-online thermal-zone area
       because GebruiksoppervlakteThermischeZone is empty 100% of the
       time on legacy-regime rows; see §6.3.2). -->
  <nrg3:area>
    <nrg3:QualifiedArea>
      <nrg3:description>Usable floor area ('gebruiksoppervlakte' per NEN 2580) as recorded by the Dutch BAG register for this verblijfsobject.</nrg3:description>
      <nrg3:source>BAG bag:verblijfsobject.oppervlakte (PDOK WFS v2.0)</nrg3:source>
      <nrg3:value uom="m2">172.0</nrg3:value>
      <nrg3:type codeSpace="...AreaTypeValue.xml">netFloorArea</nrg3:type>
    </nrg3:QualifiedArea>
  </nrg3:area>

  <nrg3:type codeSpace="http://bag.basisregistraties.overheid.nl/id/concept/Gebruiksdoel">woonfunctie</nrg3:type>

  <nrg3:address>
    <core:Address gml:id="addr_0114010000280857">
      <core:xalAddress>...xAL...</core:xalAddress>
      <core:multiPoint>...gml:MultiPoint...</core:multiPoint>
    </core:Address>
  </nrg3:address>

  <nrg3:energyPerformanceCertificate>
    <nrg3:EnergyPerformanceCertificate gml:id="epc_0114010000280857">
      <!-- Dates inherited from nrg3:AbstractFeatureWithLifeSpanType
           serialise in the Energy ADE namespace, not in core:. -->
      <nrg3:creationDate>2019-06-14</nrg3:creationDate>
      <nrg3:validFrom>2019-06-14T00:00:00</nrg3:validFrom>
      <nrg3:validTo>2029-06-14T00:00:00</nrg3:validTo>
      <nrg3:status codeSpace="...EPCStatusValue.xml">actual</nrg3:status>
      <nrg3:type codeSpace="...EPCTypeValue.xml">totalEnergyDemand</nrg3:type>
      <nrg3:label>G</nrg3:label>
      <!-- Same source column as the NTA 8800 example (BerekendeEnergieverbruik),
           but the legacy regime ships it as a total in MJ/yr. The uom carries
           the divergence. -->
      <nrg3:value uom="MJ/a">293361.52</nrg3:value>
      <nrg3:certificationMethod>Rekenmethodiek Definitief Energielabel, versie 1.2, 16 september 2014</nrg3:certificationMethod>
    </nrg3:EnergyPerformanceCertificate>
  </nrg3:energyPerformanceCertificate>
</nrg3:BuildingUnit>
```

The contrast against the NTA 8800 example is the regime asymmetry in microcosm: four resources vs. one, kWh/(m²·yr) vs. MJ/yr, CO₂ populated vs. suppressed, thermal-zone area present vs. absent. Every divergence is dictated by the dataset (§ 6.3) rather than by mapping choices.

#### 6.6.3. Why the EP-online thermal-zone area is a second QualifiedArea

`BuildingUnit/area` is `[0..*]` and the QualifiedAttribute multi-source pattern (different `source` strings, same `type`) is the schema's documented way to keep two readings of the same quantity queryable side-by-side. An earlier draft of this mapping wrapped the EP-online area in an `nrg3:Zone` (Building-level, xlink to BuildingUnit) so the Zone could carry `UsageZoneTypeValue="occupied"` plus the area, but the Zone added no information beyond the area itself: the BuildingUnit already exists, every per-m² Energy resource on it already normalises against this same area, and the xlink hop back from Zone to BuildingUnit only existed to recover the per-VBO scope that the Zone wrapper had blurred. Dropping the wrapper keeps the schema-permissible encoding and removes the round-trip.

### 6.7. Privacy and data-quality caveats

| Concern | Decision | Reasoning |
|---|---|---|
| `Certificaathouder` (certifier name) | Drop | Names of certifying inspectors / firms. While EP-online's open licence permits redistribution, the certifier name is not a building-physics signal and adds attack surface for unintended deanonymisation when joined with other registers. |
| `OpBasisVanReferentiegebouw=Ja` | Skip (latent) | A `Ja` value indicates the cert was computed from a reference-building shortcut, not from in-building measurement. Roughly 20-30% of utility certs carry this flag and their numbers are statistically softer. Currently not emitted because the thesis is not analysing per-cert fidelity; if that changes, `gen:stringAttribute name="epOnlineReferenceBuildingBased"` is the documented fallback. |
| `Status` lifecycle (`Bestaand` / `Nieuwbouw` / `Verbouw`) | Skip (latent) | A `Verbouw` cert was issued mid-renovation and may not reflect a stable thermal envelope. Currently not filtered or emitted; a downstream consumer can re-derive it from the EP-online CSV if needed. |
| EP-online's per-VBO area disagrees with BAG's `oppervlakte` | Both are emitted; `QualifiedArea/source` strings disambiguate | Already the precedent for BAG-side multi-source. Two same-typed but differently-sourced `QualifiedArea` siblings are a feature, not a conflict. |
| BAG `bouwjaar` disagrees with EP-online `Bouwjaar` | Both are emitted, BAG on `bldg:yearOfConstruction`, EP-online as `gen:intAttribute name="yearOfConstructionEPOnline"` | Same explicit-source pattern: a downstream consumer can compare per-Pand and quantify how often the two sources disagree. |

---

## 7. PV panels GeoPackage (UoG Zenodo 14860030)

**Schema:** [`inputs/pv_panels/pv_panels.gpkg`](../inputs/pv_panels/pv_panels.gpkg), layer `pv_panels`. The public dataset is CC-BY-4.0; the shipped extract covers Emmer-Compascuum.
**Loader:** [`pv_panels.py::load_panels_in_bbox`](../citygml_energy/city_builder/pv_panels.py).
**Builder:** [`pv_panels.py::attach_pv_collectors_to_building`](../citygml_energy/city_builder/pv_panels.py).

The table is deliberately minimal: only geometry and a row identifier.

| GPKG column | Type | Read | Used for |
|---|---|---|---|
| `fid` | INTEGER PK | ✓ | Embedded in the `nrg3:PhotovoltaicCollector/@gml:id` (`pv_{pand_id}_{fid}`) so every emitted collector is traceable back to one GPKG row. |
| `geom` | MULTIPOLYGON (EPSG:28992) | ✓ | Projected onto the matched LoD 2 roof plane to form the collector's `lod2MultiSurface`. |

Derived PV fields (computed in-pipeline from the geometry + roof facet, not read from the GPKG):

| Emitted field | Computed from | uom |
|---|---|---|
| `nrg3:moduleArea` | 2D polygon area | `m2` |
| `nrg3:inclination` | angle between roof Newell normal and vertical | `deg` |
| `nrg3:azimuth` | compass bearing of horizontal projection of roof normal (0° = N) | `deg`; `None` on flat roofs |
| `nrg3:referencePoint` (single `gml:Point`) | panel centroid lifted to the roof plane + `z_offset_m` (default 0.1 m) | — |
| `nrg3:cellType` | constant `"unknown"` (codeSpace = `CS_NRG3_CELL_TYPE`) | — |
| `nrg3:CityObjectRelation` with `type="installedOn"` | the `gml:id` of the matched `bldg:RoofSurface` | xlink only |
| every other `nrg3:*Collector` field (`model`, `yearOfManufacture`, `installedPower`, `nominalEfficiency`, `apertureArea`, `heatDissipation*`, `validFrom/validTo`, ...) | — | Deliberately unset: a single 2D aerial polygon carries no information about any of them. |

**Coverage:** 4 389 panels in the full GPKG; the AOI bbox returns 512 panels (the remaining 3 877 fall outside the small-area extent and are clipped at load time by `load_panels_in_bbox`); of those 512, 334 project onto 168 LoD 2 roofs and 178 are skipped because they have no LoD 2 roof overlap (building classified too low to receive them, or no 3DBAG match).

---

## 8. CFTree `trees_lod3.city.json` — LoD 3 tree reconstructions from AHN LiDAR

**Source:** [NoahAlting/CFTree](https://github.com/NoahAlting/CFTree). External preprocessor (Linux / WSL conda env) writes one CityJSON 2.0 tile per AHN sub-tile under `data/<case>/tiles/<tile_id>/trees_lod3.city.json`.
**Loader:** [`vegetation.py::load_trees_in_bbox`](../citygml_energy/city_builder/vegetation.py).
**Parser:** [`cityjson_trees_parse.py::parse_cftree_tile`](../citygml_energy/city_builder/cityjson_trees_parse.py).
**Builder:** [`builders/vegetation.py::build_solitary_vegetation_object`](../citygml_energy/city_builder/builders/vegetation.py) (calls `_apply_cftree_morphometrics`).

CFTree's per-tree morphometric attribute dict is the only source for native CityGML 2.0 vegetation measurements. The mapping table is encoded as Python constants so a new CFTree metric is a one-line edit.

### 8a. CityObject attributes (per tree)

| CFTree key | CityGML target | Implementation |
|---|---|---|
| `gtid` | `veg:SolitaryVegetationObject/@gml:id = "tree_<gtid>"` + `gml:name = "T_<gtid>"` | `build_solitary_vegetation_object`. CFTree's globally unique tree id. |
| `trunk_H_m` | `veg:height` (`gml:LengthType`, uom `m`) | `_CFTREE_NATIVE_FIELDS` → `_apply_cftree_morphometrics` |
| `trunk_DBH_m` | `veg:trunkDiameter` (`gml:LengthType`, uom `m`) | `_CFTREE_NATIVE_FIELDS` → `_apply_cftree_morphometrics` |
| `crown_width_m` | `veg:crownDiameter` (`gml:LengthType`, uom `m`) | `_CFTREE_NATIVE_FIELDS` → `_apply_cftree_morphometrics` |
| `crown_median_z` | `gen:doubleAttribute name="crown_median_z"` | `_CFTREE_GENERIC_DOUBLE` |
| `crown_r50_m` | `gen:doubleAttribute name="crown_r50_m"` | `_CFTREE_GENERIC_DOUBLE`. Median NN distance (LAI proxy). |
| `crown_porosity` | `gen:doubleAttribute name="crown_porosity"` | `_CFTREE_GENERIC_DOUBLE`. CFD-oriented. |
| `trunk_base_height_m` | `gen:doubleAttribute name="trunk_base_height_m"` | `_CFTREE_GENERIC_DOUBLE`. DTM-sampled NAP elevation at the trunk base. |
| `trunk_radius_m` | (omitted) | redundant with `trunk_DBH_m` (CFTree computes it as exactly `0.5 * trunk_DBH_m`); see comment in `_CFTREE_GENERIC_DOUBLE`. |
| `tile_id` | — | Debug aid; not written to the GML. |
| `NaN` / `null` / `""` on any metric | dropped | `to_finite_float` guards the emission per field so per-tree CityJSONs missing individual metrics still produce a valid SolitaryVegetationObject. |

### 8b. Geometry and file-level fields

| CityJSON element | Read | Notes |
|---|---|---|
| `CityObjects.T_<gtid>.geometry` (list of `Solid`s, crown + trunk) | ✓ | Flattened into one `gml:MultiSurface` attached as `veg:lod3Geometry`. CityGML 2.0 has no per-component slot for a tree, so merging is the correct lossless encoding. |
| `transform.scale` + `transform.translate` | ⚙ | Used to dequantise `vertices` to absolute RD New metres before attachment. |
| `vertices` | ⚙ | Consumed as indices into the geometry; not a standalone source of information. |
| `metadata.referenceSystem` |   | Informational only; the builder uses `config.srs_name`. |
| `metadata.geographicalExtent`, `presentLoDs` |   | Informational only. |
| top-level `type`, `version` | ⚙ | Validated (`type == "CityJSON"` or `"CityJSONFeature"`); otherwise the parser raises. |

**Appearance:** every tree MultiSurface + member Polygon id is collected during attachment and passed to `append_vegetation_appearance`, which emits an `app:Appearance` with theme `"vegetation"` and `diffuseColor = 0.15 0.55 0.15` (deep foliage green).

**Rationale:** [`vegetation_integration_report.md` § 3.1](vegetation_integration_report.md).

---

## 9. BGT `vegetatieobject_punt` — authoritative Dutch tree register

**Endpoint:** `https://api.pdok.nl/lv/bgt/ogc/v1/collections/vegetatieobject_punt/items?bbox=...`. Pagination via RFC 5005 `rel="next"` links.
**Fetcher:** [`fetchers/bgt.py::fetch_bgt_trees`](../citygml_energy/city_builder/fetchers/bgt.py).
**Matcher:** [`bgt_match.py::match_trees_to_bgt`](../citygml_energy/city_builder/bgt_match.py) — nearest-neighbour against CFTree crown centroids at a 4 m radius (algorithm in [`tree_matching.match_nearest_within`](../citygml_energy/city_builder/tree_matching.py)).
**Builder:** [`builders/vegetation.py::_apply_bgt_cross_reference`](../citygml_energy/city_builder/builders/vegetation.py).

BGT carries **no biological attributes** (no species, leaf class, planting year, or dimensions); it feeds the pipeline **cross-reference metadata only**.

| BGT property | Example | Read | CityGML target | Notes |
|---|---|---|---|---|
| `lokaal_id` | `"G0114.703d17f4c978045de05363ab720afc9b"` | ✓ | `core:externalReference`: `externalObject/uri` is the full PDOK OGC API Features URL (the `lokaal_id` is its final path segment, built via `bgt_feature_uri`); `informationSystem` carries the BGT product page (`BGT_INFORMATION_SYSTEM_URL`, `https://www.pdok.nl/ogc-apis/-/article/basisregistratie-grootschalige-topografie-bgt-`), which is the same on every BGT-matched tree. The product page is preferred over the bare collection endpoint because it documents the dataset semantics for a human follower; the per-feature payload is reachable via `externalObject/uri`. | `_apply_bgt_cross_reference` |
| `creation_date` | `"2018-07-04T22:00:00Z"` | ✓ | `gen:dateAttribute name="bgtCreationDate"` (`xs:date`) | Deliberately **not** written to `core:creationDate`; that would mis-signal "our dataset record created on". |
| presence in BGT | — | ✓ | presence of the `core:externalReference` element | A CFTree tree matched to a BGT record is a **municipally-maintained (public-space) tree**; an unmatched CFTree reconstruction is almost certainly a private garden tree. Encoded via the presence / absence of the `externalReference`. On the Emmer-Compascuum small-area run: 225 of 652 CFTree trees are BGT-matched (~35 %). |
| `plus_type` | `"boom"` | ⚙ (filter) | — | Features where `plus_type != "boom"` (e.g. `"boomstronk"`) are dropped in the fetcher (`fetch_bgt_trees`) before the `BgtTree` dataclass is constructed. |
| `status` | `"bestaand"` | ⚙ (filter) | — | `"voormalig"` features are dropped in the fetcher (`fetch_bgt_trees`) so they do not overcount against CFTree's live reconstructions. |
| `bronhouder` | `"G0114"` | ⚙ | — | Parsed into `BgtTree` but not currently written. Latent: a future `core:externalReference/informationSystem` refinement could embed the bronhouder code for multi-municipality routing. |
| `geometry.coordinates` (Point) | `[267050.0, 537780.0]` | ⚙ | — | Drives the 4 m nearest-neighbour join against each CFTree tree's crown centroid. |
| `version` | `"9536138a-...-caf7"` |   |   | BGT's per-mutation version UUID. Not written (would defeat the stable-handle purpose of `lokaal_id`). |
| `tijdstip_registratie`, `lv_publicatiedatum` | — |   |   | When this version was registered / published. Ignored. |
| `type` | `"niet-bgt"` |   |   | IMGeo base-type; always `"niet-bgt"` for vegetatieobject. Not useful. |
| `relatieve_hoogteligging` | `0` |   |   | Height layer (e.g. tree on a raised structure). Mostly zero in practice. |
| `in_onderzoek` | `null` |   |   | Whether the feature is flagged as under investigation. Ignored. |
| `eind_registratie`, `termination_date` | `null` |   |   | Termination timestamps for removed features (caught earlier by `status == "voormalig"`). |
| `plus_status` | `null` |   |   | Optional lifecycle status of the plus-attribute. Ignored. |
| 9 codespace / `*_leeg` bookkeeping fields |   |   |   | IMGeo-level metadata. Not used. |

**Rationale:** [`vegetation_integration_report.md` § 3.2 / § 4.3](vegetation_integration_report.md).

---

## 10. Gemeente Emmen `bor_groen_bomen_beschermd`

Emmen's BOR (Beheer Openbare Ruimte) tree register is the only source that fills `veg:species`. The remaining BOR fields land in `gen:*Attribute` siblings because the CityGML 2.0 vegetation module has no typed slots for protection regimes, growth-form descriptors, or class-band measurements.

**Fetcher:** [`fetchers/emmen_bor.py`](../citygml_energy/city_builder/fetchers/emmen_bor.py).
**Matcher:** [`tree_enrichment.py::match_trees_to_bor`](../citygml_energy/city_builder/tree_enrichment.py) — nearest-neighbour against CFTree crown centroids at a 4 m radius.
**Builder:** [`builders/vegetation.py::_apply_bor_enrichment`](../citygml_energy/city_builder/builders/vegetation.py).

| BOR field | CityGML target | Implementation |
|---|---|---|
| `boom_id` | `core:externalReference`: `externalObject/uri` is the ArcGIS REST `query` URL keyed on `boom_id` (built via `bor_feature_uri`; chosen over the OBJECTID dereference because `boom_id` survives a server-side layer rebuild); `informationSystem` carries the gemeente Emmen Erfgoed page (`BOR_INFORMATION_SYSTEM_URL` = `https://gemeente.emmen.nl/erfgoed`), constant across every BOR-matched tree. The Erfgoed page is preferred over the raw FeatureServer URL because it documents the dataset semantics for a human follower; the FeatureServer endpoint itself is captured in the `veg:species` codeSpace (`CS_EMMEN_BOR_TREES`) and is reachable through `externalObject/uri`. | `_apply_bor_enrichment` |
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

**Rationale:** [`vegetation_integration_report.md` § 3.3](vegetation_integration_report.md). Protection regime is a *legal* status, not a horticultural function, so it stays a generic; growth form is a canopy descriptor, not a class. Forcing those into `veg:function` / `veg:class` would mis-signal vocabulary semantics.

---

## 11. Boundary polygon (`.geojson` / `.json`)

**Source:** local file pointed to by the `boundary.path` config. The canonical default is [`inputs/boundaries/emmer-compascuum_small-area.geojson`](../inputs/boundaries/emmer-compascuum_small-area.geojson). Only GeoJSON `Feature` documents are accepted; GeoPackage support was dropped to keep the loader's dependency footprint identical to the rest of the city builder (shapely only).
**Loader:** [`boundary.py`](../citygml_energy/city_builder/boundary.py).

| Supply | Read | Used for |
|---|---|---|
| GeoJSON `Feature` with `Polygon` or `MultiPolygon` geometry | ⚙ | (a) bbox drives BAG / 3DBAG / EP-online / BGT fetch extent; (b) polygon clips 3DBAG buildings + CFTree trees to the concave AOI |
| GeoJSON top-level `crs.properties.name` | ⚙ | CRS validation (must contain `"28992"`); a missing `crs` block is accepted with a WARN log line because some QGIS / geopandas exports strip it |
| every other GeoJSON `properties.*` field |   | Ignored. |

No feature is emitted in the GML for the boundary itself.

---

## 12. CBS Postcode6 WFS — per-postcode dwelling-energy aggregates

**Endpoint:** `https://service.pdok.nl/cbs/postcode6/{year}/wfs/v1_0`, typeName `postcode6:postcode6`, `outputFormat=application/json`, `srsName=EPSG:28992`. The year is selected via `cbs_postcode6.year` in the city config.
**Fetcher:** [`fetchers/cbs_postcode6.py::fetch_postcode6_areas`](../citygml_energy/city_builder/fetchers/cbs_postcode6.py) (returns `Postcode6Area` records).
**Step module:** [`postcode6.py::attach_postcode6_areas_to_model`](../citygml_energy/city_builder/postcode6.py) — single seam owning fetch (soft-fail wrapper [`safely_fetch_postcode6_areas`](../citygml_energy/city_builder/postcode6.py)) + boundary clip + xsdata builder + ``grp:groupMember`` join + model attach.

**Sentinel codes** (per CBS Longread §4 Beschrijving cijfers):

| Sentinel | CBS verbatim | Pipeline reading |
|---|---|---|
| `-99997` | *"0 tot en met 4 / geheim / niet aanwezig"* | < 5 dwellings, statistically disclosed, or absent — value not published. |
| `-99995` | *"Onderwerp wordt in een latere versie gepubliceerd"* | Field reserved in this vintage, will be filled in a later version. Distinct from the 6-dwelling privacy suppression rule that applies to the energy fields specifically (CBS rounds energy figures to 50 and only publishes them for postcodes with ≥6 occupied dwellings; suppressed energy fields are encoded as `-99997`, not `-99995`). |

The fetcher folds *any* value at-or-below `-99000` to `None` (`_value_or_suppressed` uses a threshold rather than a sentinel set, because CBS has shipped at least three distinct codes — `-99995`, `-99997`, `-99999` — across vintages and the code block is reserved by construction; energy / dwelling counts are physical totals that cannot be negative).

**Publication cadence note.** CBS publishes geometry + dwelling counts immediately for each vintage but releases energy values (gemiddeldGasverbruikWoning, gemiddeldElektriciteitsverbruikWoning) on a one-year lag (CBS Longread §4: *"De jaarbestanden bevatten per jaar onderwerpen voor zover deze beschikbaar zijn rond de jaarwisseling. In een volgende versie zullen jaarbestanden worden aangevuld met dan beschikbaar gestelde gegevens"*). Empirical state at time of writing (2026-05): vintages 2022 and 2023 ship populated energy fields nationwide; the 2024 vintage ships every energy value as the deferred-publication code `-99995`. For the Emmer-Compascuum small-area smoke test we pin `year=2023` (most recent populated vintage; 64 of 82 postcodes inside the AOI carry real values, the other 18 are below the 6-dwelling privacy threshold and are correctly suppressed via `-99997`). Future runs should bump to 2024 once CBS publishes energy values for that vintage.

CBS publishes per-6-position-postcode aggregates derived from utility-grid connection registers. The values are **postcode-area averages**, not per-building measurements: attaching them to a `bldg:Building` or `nrg3:BuildingUnit` would misrepresent the source. EnergyADE 3.0 provides a purpose-built aggregate feature, `nrg3:UrbanFunctionArea` ([`Energy_ADE_3.0_beta8.xsd:2638-2655`](../Energy_ADE-3.0beta8/xsd/Energy_ADE_3.0_beta8.xsd)), which extends `grp:CityObjectGroup` and therefore carries its own polygon geometry, `groupMember` xlinks to constituent CityObjects, source attribution via `nrg3:Metadata`, and the `nrg3:Energy` resource hook for measured aggregates. One UrbanFunctionArea is emitted per postcode polygon that intersects the build extent (boundary clip mirrors the per-building clip in [`pipeline._filter_by_boundary`](../citygml_energy/city_builder/pipeline.py)).

The fetcher reads only the two energy fields out of the ~130 columns the WFS publishes; the rest (demographics, amenity proximities, educational attainment) are out of scope for this thesis.

### 12.1. Per-record mapping

| WFS property | Example | Read | Target | Notes |
|---|---|---|---|---|
| `postcode6` | `"7881AD"` | ✓ | `nrg3:UrbanFunctionArea/@gml:id` (via `pc6_` prefix), `gml:name`, `nrg3:code` (`gml:CodeType`, codeSpace `CS_NL_POSTCODE_PC6`), `core:externalReference/externalObject/name` | Defensively normalised to canonical `NNNNAA` shape; non-conforming values are dropped (CBS already ships canonical, but a future WFS shape change must not silently corrupt the join with BAG). |
| `gemiddeldGasverbruikWoning` | `1860` | ✓ | `nrg3:Energy` resource via `nrg3:resource`: `type="actual"`, `energyCarrier="naturalGas"`, `endUse="otherOrCombination"`, `operationType="demands"`, `referencePeriod="year"`, `amount` uom `m3/a`, `isAmountNormalized=true`, `normalizationParameter="dwelling"`. | Average annual natural-gas consumption per occupied private dwelling in the postcode (m³/yr, rounded to 50). Includes `stadsverwarming`-connected dwellings (district heating), which lowers the average for postcodes on a shared heat network. CBS suppresses the value (no resource emitted) when the postcode contains <6 occupied dwellings — encoded as `-99997` per CBS sentinel table above — or when CBS has not yet published the field for the vintage (encoded as `-99995`). Both forms, plus `null`, fold to "not emitted" via `_value_or_suppressed`. |
| `gemiddeldElektriciteitsverbruikWoning` | `2790` | ✓ | second `nrg3:Energy` resource on the same UrbanFunctionArea: `type="actual"`, `energyCarrier="electricity"`, `endUse="otherOrCombination"`, `amount` uom `kWh/a`, otherwise as above. | Same suppression / deferred-publication semantics. Individual connections only; excludes self-generated electricity from rooftop PV and excludes collective consumption (lifts, gallery lighting). |
| `aantalWoningen` | `87` | ✓ | `gen:intAttribute name="dwellingCount"` on the UrbanFunctionArea | Total dwellings registered in BAG for the postcode. Surfaced as a generic attribute because EnergyADE 3.0 has no first-class slot for "dwelling count" on UrbanFunctionArea; the gen:intAttribute substitution group on the inherited `core:AbstractCityObject` is the schema-honest place. Sourced from BAG via CBS, so it is **not** subject to the 6-dwelling privacy suppression that gates the energy figures — a postcode with suppressed energy still carries its dwelling count. |
| `aantalNietBewoondeWoningen` | `4` | ✓ | `gen:intAttribute name="vacantDwellingCount"` on the UrbanFunctionArea | Vacant-dwelling count. The CBS suppression rule keys on *occupied* dwellings, so a postcode with high vacancy can carry suppressed energy values even when `aantalWoningen` is well above the 6-dwelling threshold. The two counts together let a downstream consumer reason about *why* an energy figure was suppressed: `dwellingCount - vacantDwellingCount < 6` is below CBS's privacy threshold by construction. |
| `geom` (Polygon / MultiPolygon) | — | ✓ | `grp:geometry` (`gml:GeometryPropertyType`) holding a `gml:MultiSurface`. Vertices ride at `z=0` (CBS publishes 2D administrative boundaries; the polygons are not elevation-anchored). The polygon's 2D area lands on `nrg3:UrbanFunctionArea/area` (uom `m2`). | `_extract_polygons` parses the GeoJSON ring lists; [`postcode6._polygons_to_shapely`](../citygml_energy/city_builder/postcode6.py) is the single seam that converts to a shapely (Multi)Polygon for the boundary clip, the centroid-in-polygon group-member join, and the area calculation. CBS occasionally ships disjoint MultiPolygon for fragmented postcodes (an island plus its mainland sliver); each ring becomes its own polygon under one shared MultiSurface. |
| every other property (~125 demographic / amenity / educational columns) |   |   |   | Drop; out of scope for the city pipeline. |

### 12.2. Type, externalReference, Metadata

| Emitted element | Value | Rationale |
|---|---|---|
| `nrg3:UrbanFunctionArea/type` | `"postalCode6"` with codeSpace `CS_NRG3_URBAN_FUNCTION_AREA_TYPE` (project-internal vocabulary URL pinned in [`namespaces.py`](../citygml_energy/namespaces.py)) | EnergyADE 3.0 declares `UrbanFunctionArea/type` as an open `gml:CodeType` (no upstream codelist), so the publishing application supplies the vocabulary. The single value emitted today is `"postalCode6"`; future extensions (CBS buurt / wijk / vierkant) would land as additional members of the same vocabulary. |
| `core:externalReference/informationSystem` | `CBS_POSTCODE6_INFORMATION_SYSTEM_URL` (PDOK dataset metadata page, UUID `ed2f2381-873b-4d88-9c55-616e3a78d711`) | Pinned to the metadata page rather than the WFS URL because the metadata page describes the dataset semantics (definitions, vintage, suppression rules) even when the WFS endpoint eventually moves. |
| `core:externalReference/externalObject/name` | the postcode (e.g. `"7881AD"`) | The CBS layer has no per-postcode dereferenceable URI: the `name` branch of the `xs:choice` between `name` and `uri` is the schema-honest encoding for "stable handle inside the named information system, no canonical URL". |
| `nrg3:Metadata/source` | `"CBS Statistische gegevens per postcode (PDOK postcode6:postcode6)"` | Single Metadata block per area, emitted whenever **any** CBS-derived datum lands on the area: an energy figure that survived suppression, or a dwelling count from the BAG-via-CBS read. An UrbanFunctionArea with no CBS data still receives the polygon + groupMember xlinks (the polygon is itself CBS but is provenance-attributed via `core:externalReference`) but no Metadata block, mirroring how the EP-online builder skips its block when no resources land on a unit. |
| `nrg3:Metadata/qualityDescription` | warns that the values are postcode aggregates (NOT per-building measurements), documents the <6-dwelling suppression rule, the rounded-to-50 convention, the gas / electricity scope caveats (district-heating-bias for gas; PV / collective exclusion for electricity), and notes that the `dwellingCount` / `vacantDwellingCount` generic attributes are sourced from BAG via CBS and are **not** subject to the 6-dwelling privacy suppression | The warning text is structural protection against misuse: a downstream consumer that treats the value as a per-VBO measurement will at least find the disclaimer co-located with the figure. |

### 12.3. Group membership

`grp:groupMember` xlinks are populated inside [`attach_postcode6_areas_to_model`](../citygml_energy/city_builder/postcode6.py) via 2D centroid-in-polygon containment: each `bldg:Building`'s LoD 0 footprint centroid (LoD 1 fallback for buildings without LoD 0) is tested against the postcode polygon, and a match emits one `grp:groupMember` element with `xlink:href="#<building_gml_id>"`. The centroid extraction (`_building_centroids_for_join`, `_representative_ring`) and the area's prepared shapely geometry are co-located with the join loop so all spatial state lives in one function. The `CityObjectGroupMemberType` XSD allows either an inline CityObject *or* an xlink reference, never both; we always populate `href` because the `bldg:Building` is already emitted as a top-level `core:cityObjectMember` and inlining it under the group would produce a duplicate gml:id.

The centroid join matches CBS's own per-VBO postcode classification semantically — CBS keys per-VBO consumption against the BAG `geometriePunt` (a single representative point inside the dwelling), which is the same containment notion. A building straddling a postcode boundary lands in whichever postcode hosts its LoD 0 centroid; this is deterministic and not chosen by area-overlap, because a centroid-based join is unambiguous for any valid simple polygon and cheap to compute at city scale.

### 12.4. Calculation regime separation (vs § 6 EP-online)

EP-online emits *calculated* per-VBO indices on `nrg3:BuildingUnit/resource`: `type` is `net` (BENG-1 / Warmtebehoefte), `primary` (BENG-2 / legacy NEN 7120 EP_tot), or `final` (NTA 8800 BerekendeEnergieverbruik). CBS emits *measured* per-postcode aggregates on `nrg3:UrbanFunctionArea/resource`: `type=actual` is the EnergyADE 3.0 codelist member ([`EnergyTypeValue.xml`](../Energy_ADE-3.0beta8/xsd/codelists/EnergyTypeValue.xml)) for measured / observed energy. Because the two source types land on different parent CityObjects and carry distinct `EnergyTypeValue` codelist members, a downstream consumer can filter unambiguously: *measured aggregates* via `type=actual` on UrbanFunctionAreas, *calculated indices* via `type ∈ {net, primary, final}` on BuildingUnits.

### 12.5. Why no aggregate-to-building back-distribution

The pipeline does not multiply CBS's per-dwelling average by `aantalWoningen` to create a per-Pand or per-VBO total, and it does not synthesise a per-VBO measurement by re-distributing the postcode average to its constituent buildings. Both transformations would erase CBS's privacy boundary: the suppression rule (<6 occupied dwellings) is designed precisely to prevent identification of individual households, and a downstream consumer that received a per-VBO "measured" figure for a 5-dwelling postcode would have lost the suppression. Source attribution at the `UrbanFunctionArea` level is the only schema-honest encoding — it preserves the aggregation level CBS publishes the figures at.

---

## Appendix A — Computed (not fetched) values

A small number of output fields are not read from any source; they are computed inside the pipeline:

| Emitted element | Computed from |
|---|---|
| `gml:Envelope` on the `CityModel` | union of every building LoD vertex + every PV panel projected vertex + every tree crown vertex. Written last so the envelope bounds everything that went into the file. |
| `core:cityObjectMember` container wiring | dispatch by runtime type handled by `CityModel.add`. |
| `app:Appearance` theme `"energyLabel"` | averaged EPC letter of each building's VBOs → EU palette RGB (`epc_score.label_to_rgb`). Targets every `gml:MultiSurface`, `gml:CompositeSurface`, and `gml:Polygon` under each building (the LoD 0 footprint MultiSurface, the LoD 1 CompositeSurface shell, each LoD 2 thematic surface's MultiSurface, plus every member Polygon — see [`appearance.collect_surface_target_ids`](../citygml_energy/city_builder/appearance.py)). The CompositeSurface target is what keeps LoD 1 shells coloured in viewers that resolve container-level targets; per-polygon targets keep colour applied in viewers that only resolve per-polygon `app:target` xlinks (KIT SDM_KITModelViewer family). Buildings without any matched label render grey. |
| `app:Appearance` theme `"pvPanels"` | constant `(0.03, 0.05, 0.15)` deep blue targeting every `gml:MultiSurface` and `gml:Polygon` under every `nrg3:PhotovoltaicCollector`. |
| `app:Appearance` theme `"vegetation"` | constant `(0.15, 0.55, 0.15)` foliage green targeting every `gml:MultiSurface` and `gml:Polygon` under every `veg:SolitaryVegetationObject`. |
| `nrg3:CityObjectRelation` with `type="installedOn"` | the PV panel's 2D max-overlap with a specific LoD 2 `bldg:RoofSurface` (xlink only, no geometry). |
| `nrg3:bdgBdrySurfTotalSurfaceArea` / `Inclination` / `Azimuth` on every LoD 2 BoundarySurface | computed from the polygon geometry by `_attach_planar_surface_ade_attributes`. |

---

## Appendix B — uom token inventory

The pipeline emits the tokens below, each cross-checked against the KIT FZKViewer's bundled UoM list ([`KITModelViewer_V7.5_Build-3636/Data/UOMList.xml`](../KITModelViewer_V7.5_Build-3636/Data/UOMList.xml)):

| Token | Used on | Matched against UOMList | Status |
|---|---|---|---|
| `m` | `veg:height`, `veg:trunkDiameter`, `veg:crownDiameter`, `nrg3:bdgHeight/value` | `UOM name="METRE" id="m"` | primary id ✓ |
| `m2` | `nrg3:moduleArea` on `PhotovoltaicCollector`, `nrg3:QualifiedArea/value` on each `BuildingUnit`, `nrg3:bdgBdrySurfTotalSurfaceArea` | `UOM name="SQUARE_METRE" id="m2"` | primary id ✓ |
| `m3` | `nrg3:bdgVolume/value` on Building | `UOM name="CUBIC_METRE" id="m3"` | primary id ✓ |
| `deg` | `nrg3:inclination`, `nrg3:azimuth` on `PhotovoltaicCollector`, `nrg3:bdgBdrySurfInclination` / `Azimuth` | `UOM name="DEGREE" id="grad"`, `altId=deg` | altId (canonical id is `grad`) ✓ |
| `percent` | `gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie"` | `UOM name="PERCENTAGE" id="percent"`. **Do not use `%` literally**: it is a sign-glyph on UOMList, not an id. | primary id ✓ |
| `kWh/m2/a` | `nrg3:Energy/amount` on the four NTA-8800 EP-online resources, `nrg3:EnergyPerformanceCertificate/value` on NTA 8800 certs | UOMList has `kWh/m2` (no per-annum) and `MWh/a` (no per-area), but not the composed token. | new for this project, pending FZK UOMList revision |
| `kg/m2/a` | `nrg3:Energy/co2Equivalent` on the BENG-2 resource for NTA-8800 rows | UOMList has `kg`, `kg/m3`; no per-area-mass-per-annum. | new for this project, pending FZK UOMList revision |
| `MJ/a` | `nrg3:Energy/amount` on the single legacy `primary` resource for legacy_total rows, `nrg3:EnergyPerformanceCertificate/value` on legacy_total certs | UOMList has `MWh/a` but not `MJ/a`. Required by the regime asymmetry: legacy methods report an absolute MJ/yr total, not a per-m² intensity. | new for this project, pending FZK UOMList revision |
| `kg/a` | `nrg3:Energy/co2Equivalent` on the legacy `primary` resource for the Nader Voorschrift / ISSO branch | UOMList has `kg` but not `kg/a`. Companion to `MJ/a`. | new for this project, pending FZK UOMList revision |
| `m3/a` | `nrg3:Energy/amount` on the CBS Postcode6 `naturalGas` resource for each `nrg3:UrbanFunctionArea` | UOMList has `m3` and `MWh/a`; no annual gas-volume token. | new for this project, pending FZK UOMList revision |
| `kWh/a` | `nrg3:Energy/amount` on the CBS Postcode6 `electricity` resource for each `nrg3:UrbanFunctionArea` | UOMList has `kWh` and `MWh/a`; no per-year-kWh token. | new for this project, pending FZK UOMList revision |

The six `*/a` tokens are NL convention (NTA 8800 reports BENG metrics in kWh/m²·jaar; the legacy NEN 7120 lineage reports its totals in MJ/jaar and kg/jaar; CBS Postcode6 reports per-dwelling annual averages in m³/jaar and kWh/jaar). They are documented as gaps to be communicated upstream to the FZK developers; until the UOMList catches up, viewers fall back to displaying the raw token verbatim.

---

## Appendix C — Rejected sources (and why)

This section exists so a future contributor does not re-propose a removed or rejected source without knowing the reasoning.

| Rejected source | Why |
|---|---|
| **OpenStreetMap** `natural=tree` | On the Emmer-Compascuum small-area run, 20 OSM nodes fell inside the AOI; every single one carried *only* the `natural=tree` tag and no species / leaf_type / leaf_cycle / start_date. Zero semantic data, and non-Dutch-government source. |
| **Landelijk Register Monumentale Bomen** (Bomenstichting) | 0 entries in the Emmer-Compascuum AOI (expected: a typical village has no nationally-listed specimens). Also: the Bomenstichting is an NGO, not a government register, so out of scope. |
| **Boomregister.nl** (Geodan / NEO / COBRA / WUR cooperative) | The only candidate with crown polygons + heights per tree nationwide. License-gated; no public API; redistribution prohibited. Incompatible with a publicly-reproducible pipeline. |
| **AHN5 / AHN6 LAZ for NE Netherlands** | AHN5 skipped the NE (verified against `bladwijzer.gpkg`). AHN6 is inventoried but not yet publicly downloadable for this area. Pinned to AHN4 in CFTree. |
| **BGT `vegetatieobject_vlak`** (hedges) | Would map to `veg:PlantCover`, not `veg:SolitaryVegetationObject`. Out of scope; separate PR because `veg:PlantCover` needs an `averageHeight` which BGT does not provide. |
| **BGT `begroeidterreindeel`** | Vegetation *surfaces* (parks, forests as continuous areas). Maps to `veg:PlantCover`; same scope argument. |
| **Top10NL** tree points | Coarser than BGT, no additional attributes, already covered by the BGT cross-reference. |
| **PDOK BAG `bag:nummeraanduiding`, `bag:openbareruimte`** | Server-side joined into each VBO response by PDOK, so fetching them separately would duplicate the same data. |
| **PDOK BAG `bag:ligplaats`, `bag:standplaats`** | Boat moorings and caravan plots. Not buildings; cannot host the LoD 0/1/2 geometries the pipeline emits. |

---

## Appendix D — Latent fields (roadmap markers)

Fields the pipeline fetches or could fetch and that carry real information not yet exposed.

| Field | Source | Natural CityGML / Energy ADE target | Value if wired up |
|---|---|---|---|
| `bag:pand.status`, `bag:verblijfsobject.status` | BAG | `gen:stringAttribute` or a future `bldg:condition` | `in use` / `demolished` / `planned` distinction for every Pand / VBO. |
| `b3_opp_*`, `b3_rmse_lod*`, `b3_h_dak_{50p,70p,min}`, `b3_puntdichtheid_ahn*` | 3DBAG | mix of `nrg3:bdg_area`, quality-indicator generics | Surface-area-per-facet, per-LoD reconstruction quality, LiDAR point density. |
| `Certificaathouder`, `Status`, `OpBasisVanReferentiegebouw`, `Gebouwklasse`, `SBICode`, `Compactheid`, `Temperatuuroverschrijding`, BENG `Eis*` thresholds, EMG-Forfaitair variants | EP-online | gen:*Attribute or future schema extensions, per § 6.5 | Each row in § 6.5 names a potential target for revisit. |
| `bronhouder` | BGT | `core:externalReference/informationSystem` suffix | Multi-municipality merges could disambiguate which authority maintains each cross-referenced tree. |
| `floorNumberFrom`, `floorNumberTo`, `numberOfRooms`, `ownerName`, `ownershipType` | (no source in this pipeline) | native `nrg3:BuildingUnit/{floorNumberFrom,floorNumberTo,numberOfRooms,ownerName,ownershipType}` (XSD lines 1515-1519) | BAG VBO carries no per-VBO floor number, room count, owner identity, or tenure category, so these stay empty on every `BuildingUnit`. Listed here so a future enrichment source (e.g. WOZ for ownership, BAG `verdieping` extensions for floor numbers) has a documented landing slot rather than a `gen:*Attribute` improvisation. |
| `occupiedBy` (`nrg3:Occupants` composition on AbstractBuildingSpace) | (no source) | `nrg3:BuildingUnit/occupiedBy` (XSD line 1489) | No occupancy schedule, dietType, income / instruction level, heat-dissipation breakdown, or schedule are sourced. CBS micro-data could in principle fill `Occupants/numberOfOccupants` per-VBO; out of scope today. |

---

## Appendix E — Schema gap analysis (thesis-relevant)

Honest accounting of where Energy ADE 3.0 beta8 falls short of the data the city pipeline reads. Listed in priority for the BRP / RenoDAT thesis (gaps that affect *load-bearing* energy fields first, then quality / metadata gaps):

1. **The `BerekendeEnergieverbruik` column carries divergent units across regimes inside the same dataset.** This is a property of EP-online itself, not of Energy ADE: NTA 8800 rows (3.28 M of 5.12 M) ship the value in kWh/(m²·yr), while the legacy NEN 7120 / ISSO rows (2.84 M of 5.12 M) ship it in MJ/yr (total). No single uom is correct across the dataset. The mitigation in this code is the regime-aware emitter (§ 6.3), but consuming tools that index energy use by uom-naive aggregation across the EP-online register **will silently produce nonsense** unless they also classify by `Berekeningstype`. A future Energy ADE revision adding a `Resource/calculationMethod` codelist would let consumers reason about regime explicitly without parsing the description string.

2. **`EnergyEndUseValue.xml` has no all-uses / total / unspecified entry.** Most EP-online `nrg3:Energy` resources emitted with `endUse="otherOrCombination"` are whole-building totals across every end-use, not heating-only. The Dutch source name in each Energy's `description` field disambiguates, but a downstream consumer that filters by `endUse` (the natural Energy ADE query path) sees a stack of multi-end-use buckets and misses the breakdown. Same shape applies to `Energiebehoefte` vs `Warmtebehoefte` (the heating + cooling sum and the heating-only number both ride non-`spaceHeating` / `spaceHeating` `endUse` codes that fail to express the BENG-1 vs heating-only distinction directly). A future Energy ADE revision adding `total` / `unspecified` to `EnergyEndUseValue.xml`, or specifically a `spaceHeatingAndCooling` member, would close this. **This is the most thesis-relevant of the gaps because it directly limits machine-readability of the BENG metrics, which is exactly the BRP question the schema is being tested on.**

3. **No native renewable-share slot.** `AandeelHernieuwbareEnergie` (BENG-3) has no home; the workaround is `gen:measureAttribute`. A future Energy ADE revision could add `Building/renewableEnergyFraction` (or treat it as derived from per-source Energy resources, which would require richer per-source breakdowns than EP-online ships).

4. **No native multi-source `yearOfConstruction` in CityGML core.** `bldg:yearOfConstruction` is a CityGML 2.0 core field (not Energy ADE), single-valued (`xs:gYear`). Energy ADE's QualifiedAttribute multi-source pattern (`bdgArea` / `bdgHeight` / `bdgVolume`) is Measure-typed and cannot be used for a year. Workaround: keep `bldg:yearOfConstruction` BAG-authoritative and ride the EP-online value as `gen:intAttribute name="yearOfConstructionEPOnline"` (also at Building level), with two `nrg3:Metadata` blocks on the Building documenting each source. The cleanest schema-level fix would be a CityGML core extension allowing repeated `yearOfConstruction` values with source attribution, which is out of scope for Energy ADE alone.

5. **No native `nrg3:bdgSubtype` analogue at the BuildingUnit level.** EnergyADE 3.0 has `nrg3:bdgType` on Building but no per-VBO primary type slot, and no `bdgSubtype`. The mapping places the Dutch RVO subtype as `gen:stringAttribute name="bdgSubtypeEPOnline"` on each BuildingUnit. A future EnergyADE revision adding either a per-VBO primary type slot or a `bdgSubtype` extension element would let the value land natively.

6. **FZKViewer UOMList is incomplete for the NL energy domain.** `kWh/m2/a`, `kg/m2/a`, `MJ/a`, `kg/a`, `m3/a`, and `kWh/a` are introduced by this project to match the NTA 8800 + legacy NEN 7120 + CBS Postcode6 conventions. Listed in Appendix B so a future UOMList revision can pick them up.

7. **No standalone Emission feature.** Multi-gas GHG accounting (CH₄, N₂O, refrigerants) is impossible; we only get the CO₂-equivalent value on each Energy resource. Acceptable for EP-online (which only ships CO₂-eq) but not for richer LCA data.

8. **`gebruiksdoel` (BAG) and `Gebouwtype` (EP-online) live at different levels with different vocabularies.** BAG's per-VBO `gebruiksdoel` (`woonfunctie`, `kantoorfunctie`, …) lands on `nrg3:type` of each `BuildingUnit` with `codeSpace = CS_BAG_GEBRUIKSDOEL` — not on `bldg:function`. EP-online's `Gebouwtype` (NTA-8800 typology) lands on `nrg3:bdgType` of the parent Building with `codeSpace = CS_RVO_GEBOUWTYPE`. The 3DBAG-attribute path *would* fill `bldg:function` on the Building (with the SIG3D codespace) but 3DBAG ships `gebruiksdoel` empty on the Pand node in the surveyed responses, so in practice that slot stays empty. Net effect: each value sits in its own slot with its own codeSpace, so a downstream consumer can recover both without disambiguation. A future schema revision could collapse the per-VBO Bouwbesluit-2012 use category and the per-Pand NTA-8800 typology under one explicit relation, but the current encoding is conflict-free.

9. **No native slots for the deliberately-skipped fields** (Status, OpBasisVanReferentiegebouw, Compactheid, Temperatuuroverschrijding, BENG `Eis*` thresholds, Gebouwklasse, SBICode). Each is a candidate for either a `gen:*Attribute` workaround or a future Energy ADE extension; § 6.5 records the potential target alongside the verdict, so a later thesis chapter can quote the schema-extension proposals directly.

10. **No `core:externalReference/informationSystem` per-source code.** BGT's `bronhouder` is currently dropped because `informationSystem` carries the catalog page, not the per-feature authority. A small extension (e.g. `informationSystem/@authorityCode`) would let the pipeline disambiguate which municipality maintains each cross-referenced tree.

Each of these is a thesis-relevant finding: they identify where the schema would benefit from extension if the BRP work proceeds beyond the standardisation status quo.

---

## Code reference legend

The `Implementation` column references either a Python identifier inside an already-linked module file in the section heading (no link, just the name), or a Python identifier on a different module path (link with the full file path). The drift-detection test parses both forms; renaming or moving a referenced symbol fails the test until this document is updated.
