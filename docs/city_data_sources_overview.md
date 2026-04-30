# City-pipeline data-source overview

This document catalogues every input the city-scale pipeline consumes
(`citygml_energy.city_builder`) and exactly which fields of every
source end up in the CityGML 2.0 + Energy ADE 3.0 output.

**Completeness method.** Every "supply" row was obtained by parsing a
real cached response (BAG, 3DBAG, EP-online, municipality, CFTree,
BGT), the actual GeoPackage schema (PV panels), or a sample GeoJSON
(boundary) — not from documentation, and not from memory. Every "demand"
cell was verified by grepping the pipeline for reads of that field and
linking to the call site. Field names reflect what the source actually
emits; the commentary notes where the source documentation uses a
different name or alias.

Each table has three legend columns:

| Legend | Meaning |
|---|---|
| **Read** | ✓ the pipeline reads this field — either written to an output element or used to decide pipeline behaviour |
| **Filter-only** | ⚙ read but not written to the output (used for joins, bbox clipping, or matching) |
| **(blank)** | fetched but ignored |

The canonical config used throughout is
[`inputs/cities/emmer-compascuum_small-area.json`](../inputs/cities/emmer-compascuum_small-area.json);
concrete counts come from a fresh end-to-end run on the
Emmer-Compascuum small-area AOI (41.5 ha, 674 buildings, 652 trees).

---

## At-a-glance

| # | Source | Supply (fields provided) | Demand (fields read) | CityGML / Energy ADE target |
|---|---|---|---|---|
| 1 | PDOK `bestuurlijkegebieden` | 5 properties + geometry | 2 + geometry | — (drives downstream fetch scope only) |
| 2 | 3DBAG `tile_index.fgb` | 2 properties + geometry | 2 + geometry | — (tile selection + download URL) |
| 3 | PDOK BAG `bag:pand` | 8 properties + geometry | 4 | `bldg:Building` |
| 4 | PDOK BAG `bag:verblijfsobject` | 14 properties + geometry | 11 + geometry | `nrg3:BuildingUnit` + `core:Address` |
| 5 | 3DBAG CityJSON tile | 62 `Building` attributes + LoD 0/1.2/2.2 geometries | 8 attributes + 3 LoD geometries | `bldg:lod0FootPrint` + `bldg:lod1Solid` + `bldg:boundedBy/lod2MultiSurface` + `bldg:measuredHeight` + `bldg:roofType` + `bldg:storeysAboveGround` + `nrg3:bdgVolume` |
| 6 | EP-online `Mutatiebestand` CSV | 42 columns | 20 | `nrg3:EnergyPerformanceCertificate` + `app:Appearance` theme energyLabel + per-VBO `nrg3:QualifiedArea` (thermal-zone) + per-VBO `nrg3:Energy` resources (regime-aware) + native `nrg3:bdgType` (Pand level) + per-VBO `gen:*Attribute` classification + `nrg3:Metadata` source attribution |
| 7 | PV panels GeoPackage | 2 columns + geometry | 2 + geometry | `nrg3:PhotovoltaicCollector` |
| 8 | CFTree `trees_lod3.city.json` | 10 attributes + LoD 3 geometry | 9 + geometry | `veg:SolitaryVegetationObject` + `veg:lod3Geometry` |
| 9 | BGT `vegetatieobject_punt` | 23 properties + geometry | 5 + geometry | `core:externalReference` + `gen:dateAttribute` |
| 10 | Boundary polygon (`.gpkg` or `.geojson`) | geometry + metadata | geometry | — (clips the output to a concave AOI) |

---

## 1. PDOK `bestuurlijkegebieden` — municipality outline

**Endpoint:** `https://service.pdok.nl/kadaster/bestuurlijkegebieden/wfs/v1_0`, typeName `bestuurlijkegebieden:Gemeentegebied`, `outputFormat=application/json`, `srsName=EPSG:28992`.
**Fetcher:** [`fetchers/municipality.py::fetch_municipality_outline`](../citygml_energy/city_builder/fetchers/municipality.py).

| Property | Example | Read | Used for | Notes |
|---|---|---|---|---|
| `naam` | `"Emmen"` | ⚙ | Case-insensitive match against `config.municipality` | `_build_outline`, line 63 |
| `code` | `"0114"` | ⚙ | Normalised to 4-digit CBS prefix; filters BAG panden / VBOs to only those inside the municipality | `_normalise_cbs_code`, line 76 |
| `naam_officieel` | usually absent | ⚙ | Fallback for `naam` in the name lookup | line 63 |
| `identificatie` | `"GM0114"` |  |  | Equivalent info to `code`; not separately consulted. |
| `ligtInProvincieCode`, `ligtInProvincieNaam` | `"22"`, `"Drenthe"` |  |  | Unused. |
| `geometry` (MultiPolygon) | — | ⚙ | (a) bbox → drives BAG / 3DBAG fetch extent; (b) polygon → clips 3DBAG buildings that fall outside the municipality | `_feature_bbox`, `pipeline._fetch_parsed_buildings` |

**No feature is emitted in the GML for the municipality itself.**

---

## 2. 3DBAG tile index — FlatGeoBuf

**Endpoint:** `https://data.3dbag.nl/latest/tile_index.fgb`, read with `flatgeobuf.HTTPReader` so only the bbox-relevant slice is transferred via HTTP range requests.
**Fetcher:** [`fetchers/threedbag.py::fetch_tile_index`](../citygml_energy/city_builder/fetchers/threedbag.py).

| Property | Read | Used for |
|---|---|---|
| `tile_id` | ⚙ | Tile-folder naming + cache key |
| `cj_download` | ⚙ | The CityJSON tile URL to GET |
| every other property the tile index carries (e.g. `gpkg_download`, `obj_download`, version metadata) |  | Ignored. |
| geometry (polygon of the tile footprint) | ⚙ | Filtered against the municipality polygon to drop corner tiles that only share a bbox corner |

---

## 3. PDOK BAG `bag:pand` — building polygons + basic attributes

**Endpoint:** `https://service.pdok.nl/lv/bag/wfs/v2_0`, typeName `bag:pand`.
**Fetcher:** [`fetchers/bag.py::fetch_panden`](../citygml_energy/city_builder/fetchers/bag.py).

| WFS property | Example | Read | CityGML target | Notes |
|---|---|---|---|---|
| `identificatie` | `"0114100000202542"` | ✓ | `bldg:Building/@gml:id` (via `pand_` prefix) + `nrg3:identifier` with `codeSpace=CS_BAG_PAND` | The `identifier` emission matches the owner-occupier-building pattern at [`inputs/buildings/owner_occupier_building.json:35`](../inputs/buildings/owner_occupier_building.json); concatenating `codeSpace + value` reconstructs the full dereferenceable BAG URL (the same URL the WFS `rdf_seealso` column exposes), so the pipeline does not need to round-trip `rdf_seealso` itself. |
| `bouwjaar` | `1955` | ✓ | `bldg:yearOfConstruction` | Wins over any `oorspronkelijkbouwjaar` on the 3DBAG Building attribute dict. |
| `rdf_seealso` | `"http://bag.basisregistraties.overheid.nl/bag/id/pand/<id>"` | ⚙ (implicit) | — | Not read per-feature, but its known URL structure **is** what drives the fixed `CS_BAG_PAND` codeSpace used for the `identifier` emission. |
| `status` | `"Pand in gebruik"` | ⚙ | merged into `ParsedBuilding.attributes["status"]` but **not written to any CityGML element today** | Latent; a future `bldg:condition`-like field could consume this. |
| `gebruiksdoel` | usually `""` on Pand | | | Empty on Pand in the surveyed responses (the real value lives on VBO). Ignored. |
| `aantal_verblijfsobjecten` | `2` | | | Number of VBOs inside the Pand. Ignored. |
| `oppervlakte_min`, `oppervlakte_max` | — | | | Footprint area range. Ignored (3DBAG's geometry wins). |
| WFS feature `id` (e.g. `"pand.<uuid>"`) | | | | The BAG `identificatie` is the stable handle; the UUID prefix is discarded. |
| `geometry` (Polygon) | — | | | Ignored: 3DBAG's CityJSON geometry is used instead, keyed by `identificatie`. |

---

## 4. PDOK BAG `bag:verblijfsobject` — addressable units inside a Pand

**Endpoint:** same WFS, typeName `bag:verblijfsobject`. PDOK joins Nummeraanduiding + OpenbareRuimte server-side, so address fields appear directly on each VBO.
**Fetcher:** [`fetchers/bag.py::fetch_verblijfsobjecten`](../citygml_energy/city_builder/fetchers/bag.py).

| WFS property | Example | Read | CityGML / Energy ADE target | Notes |
|---|---|---|---|---|
| `identificatie` | `"0114010000274521"` | ✓ | `nrg3:BuildingUnit/@gml:id` (via `bu_` prefix) + `nrg3:identifier` with `codeSpace=CS_BAG_VERBLIJFSOBJECT` | Same pattern as the Pand id; concatenating `codeSpace + value` reconstructs the authoritative VBO URL. Also the primary EP-online join key when EP-online carries a `BAGVerblijfsobjectID`. |
| `pandidentificatie` (or `pand_identificatie`) | `"0114100000233256"` | ⚙ | — | Buckets VBOs under their Pand; only the first id is kept when the WFS returns a comma-separated list for rare multi-Pand VBOs. |
| `gebruiksdoel` | `"woonfunctie"` or list | ✓ | `nrg3:BuildingUnit/type` (first entry only) | Additional values (e.g. a dual-use woonfunctie+kantoorfunctie) are dropped. |
| `postcode` | `"7881AD"` | ✓ | `xAL:PostalCode/xAL:PostalCodeNumber`; address-key join | |
| `huisnummer` | `73` | ✓ | Base of `xAL:ThoroughfareNumber`; address-key join | |
| `huisletter` | `""` or `"A"` | ✓ | Appended to `xAL:ThoroughfareNumber` (e.g. `"73A"`); address-key join | Empty string is normalised to `None`. |
| `toevoeging` (or `huisnummertoevoeging`) | `""` or `"003"` | ✓ | Appended to `xAL:ThoroughfareNumber` (e.g. `"73-003"`); address-key join | |
| `openbare_ruimte` | `"Hoofdkanaal WZ"` | ✓ | `xAL:ThoroughfareName` | Street name. |
| `geometry` (Point) | — | ✓ | `core:Address/core:multiPoint/gml:MultiPoint` (single `gml:Point`) | BAG's authoritative address-locating point. `None` when the WFS returned no geometry. |
| `oppervlakte` | `247` | ✓ | `nrg3:BuildingUnit/area` as `QualifiedArea` with `type="netFloorArea"` (codeSpace = `AreaTypeValue.xml`) | **BAG is the emitted source** — recorded verbatim in the `QualifiedArea/source` string (`"BAG bag:verblijfsobject.oppervlakte (PDOK WFS v2.0)"`) and disambiguated against international `netFloorArea` in the `description`, since BAG's `oppervlakte` is strictly NEN 2580 `gebruiksoppervlakte` (usable floor area, excludes walls and vertical shafts) which is slightly narrower than the OGC / Energy-ADE `netFloorArea` definition. uom is `m2`. |
| `status` | `"Verblijfsobject in gebruik"` | ⚙ | — | Latent; no native lifecycle field. |
| `bouwjaar` | `1956` | | | Authoritative value already used via the Pand; VBO-level value is redundant. Ignored. |
| `pandstatus` | `"Pand in gebruik"` | | | Redundant with the Pand's own `status`. Ignored. |
| `woonplaats` | `"Emmer-Compascuum"` | | | **Not** used as the address city name — the builder uses `config.municipality` instead, so villages inside a municipality (like Emmer-Compascuum inside Emmen) show the municipality name. A future improvement could prefer `woonplaats`. |
| `rdf_seealso` | — | | | Linked-data URI; implicit (same URL shape as the Pand rdf_seealso drives the VBO codeSpace). |

---

## 5. 3DBAG CityJSON tile — LoD 0 / 1.2 / 2.2 geometries + building attributes

**Access:** tile URL from the FlatGeoBuf index (served gzipped); one `Building` CityObject per Pand plus zero-or-more child `BuildingPart`s.
**Parser:** [`cityjson_parse.py::parse_buildings`](../citygml_energy/city_builder/cityjson_parse.py).

### 5a. Building-level attributes (62 observed)

3DBAG emits a very rich attribute set (quality metrics per AHN vintage, per-LoD volumes and RMSE, surface areas per facet type, etc.). The pipeline reads only two.

| 3DBAG attribute | Example | Read | CityGML target | Notes |
|---|---|---|---|---|
| `identificatie` | `"NL.IMBAG.Pand.0503100000000153"` | ⚙ | — | Bare BAG id (trailing `"NL.IMBAG.Pand."` stripped) is the join key back to BAG Pand. |
| `oorspronkelijkbouwjaar` | `1933` | ✓ | `bldg:yearOfConstruction` | Only used when BAG's own `bouwjaar` is absent — BAG wins on ties (see `_merge_attributes`). |
| `b3_h_maaiveld` | `0.175` | ✓ | — (drives LoD 0 Z-lift) + **feeds into `measuredHeight`** (see below) | |
| `b3_h_dak_max` | `9.925` | ✓ | — (feeds into `measuredHeight`) | Paired with `b3_h_maaiveld` to compute `bldg:measuredHeight = b3_h_dak_max - b3_h_maaiveld`. Using `_max` (not `_70p`) so antennae and chimney tips register as part of the physical extent. Negative-height results are defensively dropped. |
| `b3_bouwlagen` | `3` | ✓ | `bldg:storeysAboveGround` (non-negative integer) | Direct 1-to-1 mapping. |
| `b3_dak_type` | `"slanted"`, `"horizontal"`, `"multiple horizontal"` | ✓ | `bldg:roofType` with `codeSpace = CS_3DBAG_DAK_TYPE` | The 3DBAG enumeration is NOT a member of SIG3D's numeric roof-type codelist; emitting the 3DBAG value under a 3DBAG-owned codeSpace documents the source enumeration honestly. Consumers that want SIG3D codes can map them downstream. |
| `b3_volume_lod22` | `752.575` | ✓ | `nrg3:bdgVolume` (Energy-ADE extension) as `QualifiedVolume` with `type="grossVolume"`, uom `m3` | Matches the owner-occupier-building `bdg_volume` pattern. `bldg:Building` has no native volume slot; the Energy ADE adds one. |
| `gebruiksdoel` | (when carried) | ✓ | `bldg:function` | Attached as a CodeType with `CS_BUILDING_FUNCTION` codeSpace. Usually empty on 3DBAG Building nodes. |
| `status` | `"Pand in gebruik"` | ⚙ | — | Passed through `_merge_attributes` but not written to any CityGML element (same pattern as BAG Pand status). |
| other `b3_*` fields (roughly 55 attributes not in the rows above): `b3_bag_bag_overlap`, `b3_extrusie`, `b3_h_dak_{50p,70p,min}`, `b3_h_nok`, `b3_is_glas_dak`, `b3_kas_warenhuis`, `b3_kwaliteitsindicator`, `b3_mutatie_ahn{3,4}_ahn{4,5}`, `b3_n_nok`, `b3_n_vlakken`, `b3_nodata_fractie_ahn{3,4,5}`, `b3_nodata_radius_ahn{3,4,5}`, `b3_opp_{buitenmuur,dak_plat,dak_schuin,grond,scheidingsmuur}`, `b3_puntdichtheid_ahn{3,4,5}`, `b3_pw_{bron,datum,onvoldoende,selectie_reden}`, `b3_rmse_lod{12,13,22}`, `b3_t_run`, `b3_val3dity_lod{12,13,22}`, `b3_volume_lod{12,13}` | | | | Quality / statistical / redundant-volume fields. Left latent; `b3_rmse_lod*` would be the natural next wave (quality-indicator generic attributes). |
| BAG-origin duplicates: `documentdatum`, `documentnummer`, `begingeldigheid`, `eindgeldigheid`, `eindregistratie`, `geconstateerd`, `tijdstipeindregistratielv`, `tijdstipinactief`, `tijdstipinactieflv`, `tijdstipnietbaglv`, `tijdstipregistratie`, `tijdstipregistratielv`, `voorkomenidentificatie`, `fid` | | | | Registry-lifecycle fields, same semantics as in BAG itself. Not used. |

### 5b. Geometries

Each Building + its child BuildingParts contributes geometries at up to three LoDs.

| CityJSON `geometry.lod` | Shape | Read | CityGML target |
|---|---|---|---|
| `"0"` | MultiSurface (one polygon) | ✓ | `bldg:lod0FootPrint` (lifted to b3_h_maaiveld, see §5a) |
| `"1.2"` | Solid with thematic `semantics` | ✓ | `bldg:lod1Solid` as a `gml:CompositeSurface` shell |
| `"2.2"` | Solid with per-face `GroundSurface`/`WallSurface`/`RoofSurface` semantics | ✓ | `bldg:boundedBy` with per-type `bldg:lod2MultiSurface` |
| any other LoD (1.3, experimental variants) | | | Dropped in `_LOD_ALIAS` lookup. |

---

## 6. EP-online `Mutatiebestand` CSV — Dutch energy-label register

**Access:** two-step via `https://public.ep-online.nl/api/v5/Mutatiebestand/DownloadInfo?fileType=csv&xmlVersion=4` (needs `Authorization` header with the EP-online API key) → ZIP URL → ~1 GB CSV inside the ZIP.
**Fetcher + parser:** [`fetchers/eponline.py`](../citygml_energy/city_builder/fetchers/eponline.py).

The CSV has **42 columns** plus two header meta-lines (`PublicatieDatum`, `LaatstVerwerkteMutatievolgnummer`). Filter-on-parse drops every row that doesn't match a wanted BAG VBO id or address key before materialising any dataclass.

| CSV column | Read | Energy ADE target | Notes |
|---|---|---|---|
| `BAGVerblijfsobjectID` | ✓ | — | Primary VBO join key (wins over the address-key fallback). |
| `Postcode` | ✓ | — | Address-key fallback join. |
| `Huisnummer` | ✓ | — | Address-key fallback join. |
| `Huisletter` | ✓ | — | Address-key fallback join. |
| `Huisnummertoevoeging` | ✓ | — | Address-key fallback join. |
| `Energieklasse` (`A+++++` … `G`) | ✓ | `nrg3:EnergyPerformanceCertificate/label` + `app:Appearance` (theme `energyLabel`) RGB colour | Drives both the EPC attribute and the building's fill colour via `epc_score.label_to_rgb`. |
| `Registratiedatum` | ✓ | `nrg3:EnergyPerformanceCertificate/validFrom` (XmlDateTime at midnight UTC) | |
| `GeldigTot` | ✓ | `nrg3:EnergyPerformanceCertificate/validTo` | |
| `Opnamedatum` | ✓ | — | Tie-breaker for duplicate rows in `address_match` (latest opname wins). |
| `Berekeningstype` | ✓ | `nrg3:EnergyPerformanceCertificate/certificationMethod` (concatenated with `SoortOpname` via `" / "`) | Raw NTA-8800 variant string. Now joined with `SoortOpname` so the EPC's certification method carries both the inspection rigour and the calculation variant. |
| `SoortOpname` | ✓ | `nrg3:EnergyPerformanceCertificate/certificationMethod` (prepended to `Berekeningstype`) | Inspection rigour ("Basisopname" / "Detailopname"). Native (derived); see [`docs/ep_online_data_model_mapping.md`](ep_online_data_model_mapping.md) §5d. |
| `Gebouwtype` | ✓ | native `nrg3:bdgType` on the **Building** (Pand-level, Dutch RVO term verbatim, `@codeSpace = CS_RVO_GEBOUWTYPE` pointing at the EP-online publication that defines the vocabulary). Picked from the most-recently-registered cert across the Pand's VBOs that carries `Gebouwtype`. | The primary building type is a Pand-level fact: a structure has one primary type regardless of how many VBOs sit inside. Dutch term verbatim because the Energy-ADE 3.0 `BuildingTypeValue.xml` codelist is too coarse for the NTA-8800 typology (mapping doc §5e). |
| `Gebouwsubtype` | ✓ | `gen:stringAttribute name="bdgSubtypeEPOnline"` on each `nrg3:BuildingUnit`, value = Dutch RVO term verbatim. | Per-VBO secondary qualifier (e.g. `appartement-portiekflat`); two VBOs in one Pand can carry different subtypes. EnergyADE 3.0 has no native `nrg3:bdgSubtype` element (mapping doc §5e). |
| `Bouwjaar` | ✓ | `gen:intAttribute name="yearOfConstructionEPOnline"` on the **Building** (Pand level, picked from the most-recently-registered cert across the Pand's VBOs). The EP-online `nrg3:Metadata` block on the Building covers both `yearOfConstructionEPOnline` and `nrg3:bdgType`; the BAG-source block sits next to it. | Year-of-construction is a Pand-level fact regardless of which register reports it; EP-online ships it per-VBO only because the CSV is row-per-cert. Mapping doc §5h. |
| `GebruiksoppervlakteThermischeZone` | ✓ | second `nrg3:QualifiedArea` directly on the `nrg3:BuildingUnit` (sibling of the BAG `oppervlakte` entry, same `netFloorArea` type, distinct `source`). uom `m2`. NTA 8800 only — empty for ~100 % of legacy-regime rows. | Anchor for every per-m² energy metric. The earlier draft wrapped this in an `nrg3:Zone`; the wrapper added no information beyond the area itself, so it was dropped. Mapping doc §5h + §6.2. |
| `Energiebehoefte` | ✓ | `nrg3:Energy` resource on the BuildingUnit via `nrg3:resource`: type `netEnergy`, endUse `spaceHeating`. uom `kWh/m2/a`, `isAmountNormalized=true` with no `normalizationValue` (the per-m² basis is already encoded in the uom). | BENG-1, heating + cooling combined. NTA 8800 only. Mapping doc §5i. |
| `Warmtebehoefte` | ✓ | sibling `nrg3:Energy` resource: type `netEnergy`, distinguished from BENG-1 by the `description` field. uom `kWh/m2/a`. | NTA 8800 net heating demand. NTA 8800 only. Mapping doc §5i. |
| `PrimaireFossieleEnergie` | ✓ | `nrg3:Energy` resource: type `primaryEnergy`. uom `kWh/m2/a`. | BENG-2. NTA 8800 only. Mapping doc §5j. |
| `AandeelHernieuwbareEnergie` | ✓ | `gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie"` on each `nrg3:BuildingUnit`. uom `percent` (NOT `%`). | BENG-3 renewable share. NTA 8800 only. No native Energy ADE slot; the EPC cannot host generic attributes (extends AbstractFeatureWithLifeSpan, not CityObject), so the attribute lives on the BuildingUnit. Mapping doc §5j. |
| `BerekendeCO2Emissie` | ✓ | **Regime-aware.** NTA 8800: `nrg3:Energy/co2Equivalent` on the BENG-2 resource, uom `kg/m2/a`. legacy_total Nader Voorschrift / ISSO: `co2Equivalent` on the legacy `finalEnergy` resource, uom `kg/a` (annual total). Definitief Energielabel: suppressed (the column is a structural ``0,00`` placeholder, not a measurement). | Emissions are a property of `AbstractResource`, not a standalone feature. Mapping doc §5k. |
| `BerekendeEnergieverbruik` | ✓ | **Regime-aware.** NTA 8800: `nrg3:Energy` resource, type `finalEnergy`, uom `kWh/m2/a`. legacy_total: single `nrg3:Energy` resource, type `finalEnergy`, uom `MJ/a` (annual total, NEN 7120 lineage), `isAmountNormalized=false`. | The only column populated in BOTH regimes, but with divergent units (median 150 vs. 93 039 across 5.12 M rows). Mapping doc §5k. |
| **Source attribution** | ✓ | Building level: one `nrg3:Metadata` block for BAG (`bldg:yearOfConstruction`) plus one EP-online-source block covering both `yearOfConstructionEPOnline` and `nrg3:bdgType` whenever either is emitted. BuildingUnit level: one EP-online-source `nrg3:Metadata` block per unit, covering `bdgSubtypeEPOnline`, the EP-online thermal-zone QualifiedArea, the renewable-share measure attribute, and the `nrg3:Energy` resources. | Mapping doc §4 + §6. |
| `PublicatieDatum` (meta row 1) | | | Date of this Mutatiebestand vintage. Not parsed. |
| `LaatstVerwerkteMutatievolgnummer` (meta row 2) | | | Opaque RVO mutation counter. Not parsed. |
| `Opnamedatum` | ⚙ | — | Inspection date. Used as the address-match tiebreak only; deliberately not emitted (Skip-(latent), mapping doc §5b). |
| `Certificaathouder`, `Status`, `OpBasisVanReferentiegebouw`, `Gebouwklasse`, `SBICode`, `Detailaanduiding`, `Projectnaam`, `Projectobject`, `Bouwjaar` agreement diff | | | Skip-(latent) or Drop per the mapping doc §5d, §5e, §5f, §5g. Each has a documented potential target in case of revisit. |
| `Compactheid` | | | Surface-to-volume ratio. Skip-(latent); potentially useful for a future thermal-modelling extension. Mapping doc §5h. |
| `EnergieIndex`, `EnergieIndexEMGForfaitair` | | | Pre-NTA-8800 (legacy). Dropped: mathematically incompatible with BENG metrics. Mapping doc §5i. |
| `PrimaireFossieleEnergieEMGForfaitair`, `AandeelHernieuwbareEnergieEMGForfaitair` | | | Same physical quantity computed under a different convention; not modelled. Dropped (mapping doc §5j). |
| `Temperatuuroverschrijding` | | | Summer overheating hours (BENG-4). Skip-(latent); revisit if thermal-comfort enters scope (mapping doc §5k). |
| `EisEnergiebehoefte`, `EisPrimaireFossieleEnergie`, `EisAandeelHernieuwbareEnergie`, `EisTemperatuuroverschrijding` | | | BENG / Bouwbesluit thresholds. Skip-(latent); not modelled today (mapping doc §5l). |
| `BAGLigplaatsID`, `BAGStandplaatsID` | | | BAG handles for houseboats / caravan plots. Not used (the pipeline only builds VBO-based BuildingUnits). |
| `BAGPandIDs` | | | Comma-separated parent Pand ids. Redundant with the `pandidentificatie` join path; not used. |

**Emitted** `type` on `nrg3:EnergyPerformanceCertificate` is the constant `"EP-online"` with `codeSpace = CS_NRG3_EPC_TYPE`, not a per-label value.

The full per-column rationale, including verdicts (Native / Native (derived) / gen:Attribute / Skip (latent) / Drop) and potential targets for every Skip-(latent) field, lives in [`docs/ep_online_data_model_mapping.md`](ep_online_data_model_mapping.md).

---

## 7. PV panels GeoPackage (UoG Zenodo 14860030)

**Schema:** [`inputs/pv_panels/pv_panels.gpkg`](../inputs/pv_panels/pv_panels.gpkg), layer `pv_panels`. The public dataset is CC-BY-4.0; the shipped extract covers Emmer-Compascuum.
**Loader:** [`pv_panels.py::load_panels_in_bbox`](../citygml_energy/city_builder/pv_panels.py).

The table is deliberately minimal: only geometry and a row identifier.

| GPKG column | Type | Read | Used for |
|---|---|---|---|
| `fid` | INTEGER PK | ✓ | Embedded in the `nrg3:PhotovoltaicCollector/@gml:id` (`pv_{pand_id}_{fid}`) so every emitted collector is traceable back to one GPKG row. |
| `geom` | MULTIPOLYGON (EPSG:28992) | ✓ | Projected onto the matched LoD 2 roof plane to form the collector's `lod2MultiSurface`. |

**Derived PV fields** (computed in-pipeline from the geometry + roof facet, not read from the GPKG):

| Emitted field | Computed from | uom |
|---|---|---|
| `nrg3:moduleArea` | 2D polygon area | `m2` |
| `nrg3:inclination` | angle between roof Newell normal and vertical | `deg` |
| `nrg3:azimuth` | compass bearing of horizontal projection of roof normal (0° = N) | `deg`; `None` on flat roofs |
| `nrg3:referencePoint` (single `gml:Point`) | panel centroid lifted to the roof plane + `z_offset_m` (default 0.1 m) | — |
| `nrg3:cellType` | constant `"unknown"` (codeSpace = `CS_NRG3_CELL_TYPE`) | — |
| `nrg3:CityObjectRelation` with `type="installedOn"` | the `gml:id` of the matched `bldg:RoofSurface` | xlink only |
| every other `nrg3:*Collector` field (`model`, `yearOfManufacture`, `installedPower`, `nominalEfficiency`, `apertureArea`, `heatDissipation*`, `validFrom/validTo`, ...) | | | Deliberately unset: a single 2D aerial polygon carries no information about any of them. |

**Coverage**: 4 389 panels in the full GPKG; 334 project onto 168 LoD 2 roofs inside the Emmer-Compascuum AOI; 178 are skipped because they have no LoD 2 roof overlap (building classified too low to receive them, or no 3DBAG match).

---

## 8. CFTree `trees_lod3.city.json` — LoD 3 tree reconstructions from AHN LiDAR

**Source:** [NoahAlting/CFTree](https://github.com/NoahAlting/CFTree). External preprocessor (Linux / WSL conda env) writes one CityJSON 2.0 tile per AHN sub-tile under `data/<case>/tiles/<tile_id>/trees_lod3.city.json`.
**Loader:** [`vegetation.py::load_trees_in_bbox`](../citygml_energy/city_builder/vegetation.py).
**Parser:** [`cityjson_trees_parse.py::parse_cftree_tile`](../citygml_energy/city_builder/cityjson_trees_parse.py).
**Builder:** [`builders.py::build_solitary_vegetation_object`](../citygml_energy/city_builder/builders.py).

### 8a. CityObject attributes (per tree)

| Attribute | Type | Read | CityGML target | Notes |
|---|---|---|---|---|
| `gtid` | int | ✓ | `veg:SolitaryVegetationObject/@gml:id = "tree_<gtid>"` + `gml:name = "T_<gtid>"` | CFTree's globally unique tree id. |
| `trunk_H_m` | float | ✓ | `veg:height` (`gml:LengthType`, uom `m`) | Total tree height. |
| `trunk_DBH_m` | float | ✓ | `veg:trunkDiameter` (`gml:LengthType`, uom `m`) | Diameter at breast height (allometric estimate). |
| `crown_width_m` | float | ✓ | `veg:crownDiameter` (`gml:LengthType`, uom `m`) | Convex-hull-equivalent circle diameter. |
| `crown_median_z` | float | ✓ | `gen:doubleAttribute name="crown_median_z"` | No native CityGML slot. |
| `crown_r50_m` | float | ✓ | `gen:doubleAttribute name="crown_r50_m"` | Median NN distance (LAI proxy). |
| `crown_porosity` | float | ✓ | `gen:doubleAttribute name="crown_porosity"` | CFD-oriented. |
| `trunk_radius_m` | float | dropped (deliberately) | — | CFTree computes this as exactly `0.5 * trunk_DBH_m` (see [`extract_tree_metrics.estimate_trunk_dimensions`](../../CFTree/src/reconstruction/extract_tree_metrics.py)). Emitting alongside `veg:trunkDiameter` would double-signal the same measurement; any consumer can derive the radius on the fly. |
| `trunk_base_height_m` | float | ✓ | `gen:doubleAttribute name="trunk_base_height_m"` | DTM-sampled NAP elevation at the trunk base. |
| `tile_id` | str | ⚙ | — | Debug aid; not written to the GML. |
| `NaN` / `null` / `""` on any metric | | dropped | — | `_as_finite_float` guards the emission per field so per-tree CityJSONs missing individual metrics still produce a valid SolitaryVegetationObject. |

### 8b. Geometry and file-level fields

| CityJSON element | Read | Notes |
|---|---|---|
| `CityObjects.T_<gtid>.geometry` (list of `Solid`s, crown + trunk) | ✓ | Flattened into one `gml:MultiSurface` attached as `veg:lod3Geometry`. CityGML 2.0 has no per-component slot for a tree, so merging is the correct lossless encoding. |
| `transform.scale` + `transform.translate` | ⚙ | Used to dequantise `vertices` to absolute RD New metres before attachment. |
| `vertices` | ⚙ | Consumed as indices into the geometry; not a standalone source of information. |
| `metadata.referenceSystem` | | Informational only; the builder uses `config.srs_name`. |
| `metadata.geographicalExtent`, `presentLoDs` | | Informational only. |
| top-level `type`, `version` | ⚙ | Validated (`type == "CityJSON"` or `"CityJSONFeature"`); otherwise the parser raises. |

**Appearance:** every tree MultiSurface + member Polygon id is collected during attachment and passed to `append_vegetation_appearance`, which emits an `app:Appearance` with theme `"vegetation"` and `diffuseColor = 0.15 0.55 0.15` (deep foliage green).

---

## 9. BGT `vegetatieobject_punt` — authoritative Dutch tree register

**Endpoint:** `https://api.pdok.nl/lv/bgt/ogc/v1/collections/vegetatieobject_punt/items?bbox=...`. Pagination via RFC 5005 `rel="next"` links.
**Fetcher:** [`fetchers/bgt.py::fetch_bgt_trees`](../citygml_energy/city_builder/fetchers/bgt.py).
**Matcher:** [`bgt_match.py::match_trees_to_bgt`](../citygml_energy/city_builder/bgt_match.py) — nearest-neighbour against CFTree crown centroids at a 4 m radius.

BGT carries **no biological attributes** (no species, leaf class, planting year, or dimensions); it feeds the pipeline **cross-reference metadata only**. See [`docs/vegetation_integration_report.md`](vegetation_integration_report.md) §4.3 for the full reasoning.

| BGT property | Example | Read | CityGML target | Notes |
|---|---|---|---|---|
| `lokaal_id` | `"G0114.703d17f4c978045de05363ab720afc9b"` | ✓ | `core:externalReference/externalObject/uri` (the full PDOK URL; the `lokaal_id` is the URL's final path segment) | |
| `creation_date` | `"2018-07-04T22:00:00Z"` | ✓ | `gen:dateAttribute name="bgtCreationDate"` (xs:date) | Deliberately **not** written to `core:creationDate` — that would mis-signal "our dataset record created on". |
| `plus_type` | `"boom"` | ⚙ (filter) | — | Features where `plus_type != "boom"` (e.g. `"boomstronk"` tree stumps) are dropped at parse time. |
| `status` | `"bestaand"` | ⚙ (filter) | — | `"voormalig"` (terminated) features are dropped so they do not overcount against CFTree's live reconstructions. |
| `bronhouder` | `"G0114"` | ⚙ | — | Parsed into `BgtTree` but not currently written. Latent: a future `core:externalReference/informationSystem` refinement could embed the bronhouder code for multi-municipality routing. |
| `geometry.coordinates` (Point) | `[267050.0, 537780.0]` | ⚙ | — | Drives the 4 m nearest-neighbour join against each CFTree tree's crown centroid. |
| `version` | `"9536138a-...-caf7"` | | | BGT's per-mutation version UUID. Not written (would defeat the stable-handle purpose of `lokaal_id`). |
| `tijdstip_registratie` | `"2022-08-05T13:25:19Z"` | | | When this version was registered. Ignored. |
| `lv_publicatiedatum` | `"2022-08-05T15:09:30Z"` | | | When the PDOK-LV published it. Ignored. |
| `type` | `"niet-bgt"` | | | IMGeo base-type; always `"niet-bgt"` for vegetatieobject. Not useful. |
| `relatieve_hoogteligging` | `0` | | | Height layer (e.g. a tree on a raised structure). Mostly zero in practice; not used. |
| `in_onderzoek` | `null` | | | Whether the feature is flagged as under investigation by the bronhouder. Ignored. |
| `eind_registratie`, `termination_date` | `null` | | | Termination timestamps for removed features (caught earlier by the `status == "voormalig"` filter). |
| `plus_status` | `null` | | | Optional lifecycle status of the plus-attribute. Ignored. |
| 9 codespace / `*_leeg` bookkeeping fields: `plus_status_codespace`, `plus_status_leeg`, `plus_type_codespace`, `plus_type_leeg`, `status_codespace`, `status_leeg`, `termination_date_leeg`, `in_onderzoek_leeg`, `type_codespace` | | | | IMGeo-level metadata describing which code-list the adjacent field belongs to, or why it is empty. Not used in the output. |

---

## 10. Boundary polygon (`.geojson` / `.json`)

**Source:** local file pointed to by the `boundary.path` config. The canonical default is [`inputs/boundaries/emmer-compascuum_small-area.geojson`](../inputs/boundaries/emmer-compascuum_small-area.geojson). Only GeoJSON `Feature` documents are accepted; GeoPackage support was deliberately dropped to keep the loader's dependency footprint identical to the rest of the city builder (shapely only).
**Loader:** [`boundary.py`](../citygml_energy/city_builder/boundary.py).

| Supply | Read | Used for |
|---|---|---|
| GeoJSON `Feature` with `Polygon` or `MultiPolygon` geometry | ⚙ | (a) bbox → drives BAG / 3DBAG / EP-online / BGT fetch extent; (b) polygon → clips 3DBAG buildings + CFTree trees to the concave AOI |
| GeoJSON top-level `crs.properties.name` | ⚙ | CRS validation (must contain `"28992"`); a missing `crs` block is accepted with a WARN log line because some QGIS / geopandas exports strip it |
| every other GeoJSON `properties.*` field | | Ignored (the file is consumed only for the polygon outline). |

**No feature is emitted in the GML for the boundary itself.**

---

## Appendix A — Values that are *computed*, not fetched

A small number of output fields are not read from any source; they are computed inside the pipeline:

| Emitted element | Computed from |
|---|---|
| `gml:Envelope` on the `CityModel` | union of every building LoD vertex + every PV panel projected vertex + every tree crown vertex. Written last so the envelope bounds everything that went into the file. |
| `core:cityObjectMember` container wiring | dispatch by runtime type handled by `CityModel.add`. |
| `app:Appearance` theme `"energyLabel"` | averaged EPC letter of each building's VBOs → EU palette RGB (`epc_score.label_to_rgb`). Buildings without any matched label render grey. |
| `app:Appearance` theme `"pvPanels"` | constant `(0.03, 0.05, 0.15)` deep blue targeting every MultiSurface / Polygon under every `nrg3:PhotovoltaicCollector`. |
| `app:Appearance` theme `"vegetation"` | constant `(0.15, 0.55, 0.15)` foliage green targeting every MultiSurface / Polygon under every `veg:SolitaryVegetationObject`. |
| `nrg3:CityObjectRelation` with `type="installedOn"` | the PV panel's 2D max-overlap with a specific LoD 2 `bldg:RoofSurface` (xlink only, no geometry). |

---

## Appendix B — UoM tokens emitted

The pipeline emits the tokens below, each cross-checked against the KIT FZKViewer's bundled UoM list
([`KITModelViewer_V7.5_Build-3636/Data/UOMList.xml`](../KITModelViewer_V7.5_Build-3636/Data/UOMList.xml)):

| Token | Used on | Matched against UOMList | Status |
|---|---|---|---|
| `m` | `veg:height`, `veg:trunkDiameter`, `veg:crownDiameter` | `UOM name="METRE" id="m"` | primary id ✓ |
| `m2` | `nrg3:moduleArea` on `PhotovoltaicCollector`, `nrg3:QualifiedArea/value` on each `BuildingUnit` (BAG `oppervlakte` + EP-online thermal-zone) | `UOM name="SQUARE_METRE" id="m2"` | primary id ✓ |
| `deg` | `nrg3:inclination`, `nrg3:azimuth` on `PhotovoltaicCollector` | `UOM name="DEGREE" id="grad"`, `altId=deg` | altId (canonical id is `grad`) ✓ |
| `percent` | `gen:measureAttribute name="epOnlineAandeelHernieuwbareEnergie"` | `UOM name="PERCENTAGE" id="percent"` | primary id ✓ |
| `kWh/m2/a` | `nrg3:Energy/amount` on the four NTA-8800 EP-online resources (Energiebehoefte, Warmtebehoefte, PrimaireFossieleEnergie, BerekendeEnergieverbruik) | UOMList has `kWh/m2` (no per-annum) and `MWh/a` (no per-area) but not the composed token | new for this project, pending FZK UOMList revision |
| `kg/m2/a` | `nrg3:Energy/co2Equivalent` on the BENG-2 (primary-energy) resource for NTA-8800 rows | UOMList has `kg`, `kg/m3`; no per-area-mass-per-annum | new for this project, pending FZK UOMList revision |
| `MJ/a` | `nrg3:Energy/amount` on the single legacy `finalEnergy` resource for legacy_total rows (`Rekenmethodiek Definitief Energielabel`, Nader Voorschrift / ISSO75 / ISSO82) | UOMList has `MWh/a` but not `MJ/a` | new for this project, pending FZK UOMList revision |
| `kg/a` | `nrg3:Energy/co2Equivalent` on the legacy `finalEnergy` resource for the Nader Voorschrift / ISSO branch (annual total CO₂) | UOMList has `kg` but not `kg/a` | new for this project, pending FZK UOMList revision |

The four `*/a` tokens are NL convention (NTA 8800 reports BENG metrics
in kWh/m²·jaar; the legacy NEN 7120 lineage reports its totals in
MJ/jaar and kg/jaar). They are documented as gaps to be communicated
upstream to the FZK developers; until the UOMList catches up, viewers
fall back to displaying the raw token verbatim. The regime asymmetry
that requires both per-area (NTA 8800) and absolute-total (legacy)
tokens is documented in [`ep_online_data_model_mapping.md` § 5.0](ep_online_data_model_mapping.md#50-calculation-regimes-and-field-availability-read-first).

---

## Appendix C — Things the pipeline deliberately does *not* fetch

This section exists so a future contributor does not re-propose a
removed or rejected source without knowing the reasoning.

| Rejected source | Why |
|---|---|
| **OpenStreetMap** `natural=tree` | On the Emmer-Compascuum small-area run, 20 OSM nodes fell inside the AOI; every single one carried *only* the `natural=tree` tag and no species / leaf_type / leaf_cycle / start_date. Zero semantic data, and non-Dutch-government source. Removed. |
| **Landelijk Register Monumentale Bomen** (Bomenstichting) | 0 entries in the Emmer-Compascuum AOI (expected — typical village has no nationally-listed specimens). Also: the Bomenstichting is an NGO, not a government register, so out of scope. |
| **Boomregister.nl** (Geodan / NEO / COBRA / WUR cooperative) | The only candidate with crown polygons + heights per tree nationwide. License-gated; no public API; redistribution prohibited. Incompatible with a publicly-reproducible pipeline. |
| **AHN5 / AHN6 LAZ for NE Netherlands** | AHN5 skipped the NE (verified against `bladwijzer.gpkg`). AHN6 is inventoried but not yet publicly downloadable for this area. Pinned to AHN4 in CFTree. |
| **BGT `vegetatieobject_vlak` (hedges)** | Would map to `veg:PlantCover`, not `veg:SolitaryVegetationObject`. Out of scope; separate PR because `veg:PlantCover` needs an `averageHeight` which BGT doesn't provide. |
| **BGT `begroeidterreindeel`** | Vegetation *surfaces* (parks, forests as continuous areas). Maps to `veg:PlantCover`; same scope argument as hedges. |
| **Top10NL** tree points | Coarser than BGT, no additional attributes, already covered by the BGT cross-reference. |
| **PDOK BAG `bag:nummeraanduiding`, `bag:openbareruimte`** | Server-side joined into each VBO response by PDOK, so fetching them separately would duplicate the same data. |
| **PDOK BAG `bag:ligplaats`, `bag:standplaats`** | Boat moorings and caravan plots. Not buildings; cannot host the LoD 0/1/2 geometries the pipeline emits. Out of scope. |

---

## Appendix D — Latent fields (roadmap markers)

Fields the pipeline fetches or could fetch and that carry real
information we are not yet exposing. Listed here in one place so the
roadmap of the pipeline is legible from a single document.

| Field | Source | Natural CityGML / Energy ADE target | Value if wired up |
|---|---|---|---|
| `bag:pand.status`, `bag:verblijfsobject.status` | BAG | `gen:stringAttribute` or a future `bldg:condition` | "in use" / "demolished" / "planned" distinction for every Pand/VBO. |
| `b3_opp_*`, `b3_rmse_lod*`, `b3_h_dak_{50p,70p,min}`, `b3_puntdichtheid_ahn*` | 3DBAG | mix of `nrg3:bdg_area`, quality-indicator generics | Surface-area-per-facet, per-LoD reconstruction quality, LiDAR point density. |
| `Certificaathouder`, `Status`, `OpBasisVanReferentiegebouw`, `Gebouwklasse`, `Gebouwsubtype`, `SBICode`, `Opnamedatum`, `Compactheid`, `Temperatuuroverschrijding`, BENG `Eis*` thresholds, EMG-Forfaitair variants | EP-online | gen:*Attribute or future schema extensions, per [`docs/ep_online_data_model_mapping.md`](ep_online_data_model_mapping.md) §5 | All Skip-(latent) or Drop per the umbrella mapping spec; `Certificaathouder` is privacy-driven, the others were judged not load-bearing for the current thesis question. Each row in the mapping doc names a potential target for revisit. |
| `bag:verblijfsobject.woonplaats` | BAG | `xAL:LocalityName` | Village-level addressing (Emmer-Compascuum vs the Emmen municipality). |
| `bronhouder` | BGT | `core:externalReference/informationSystem` suffix | Multi-municipality merges could disambiguate which authority maintains each cross-referenced tree. |

---

## Appendix E — Answers to open questions

**Q (7): Does EP-online carry any signal about PV install date?**

No — not directly. Reviewed every column of the production CSV
(42 columns, `v20260401`); none of them is a PV-specific install
date, PV power rating, or PV presence flag. The closest proxies are:

* `AandeelHernieuwbareEnergie` (%) — renewable-energy share of the
  label's calculation. Mixes PV, solar thermal, heat-pump electrical
  self-generation, and area-based renewables under one number, so a
  high value *suggests* PV but does not confirm it. Not usable as an
  install date.
* `AandeelHernieuwbareEnergieEMGForfaitair` — same metric with
  EMG-Forfaitair (area-based forfait) applied. A positive value here
  tells you the calculation credited area-based renewables, which is
  the category that covers shared / community PV installations, but
  again gives no date.
* The EPC's `validFrom` is an upper bound on PV install date *if* the
  PV is why the label was re-issued — but we cannot tell that from
  the register, and it is usually not the reason.

**The Groningen PV GeoPackage is the only direct source of PV-panel
observation in the pipeline, and it has no install dates either.** The
emitted `nrg3:PhotovoltaicCollector` inherits `yearOfInstallation`
from `nrg3:AbstractDeviceType` (so the schema slot exists) but it is
deliberately left unset because no source feeds it.

---

**Q (9): What does BGT add on top of CFTree?**

Three concrete additions, all non-attribute:

1. **Authoritative Dutch identifier.** CFTree gives every tree a
   `gtid` scoped to its own run; BGT gives every publicly-maintained
   tree a globally unique `lokaal_id` that municipal maintenance
   systems, the Bomenstichting, Bomenregister.nl and other Dutch
   tree-data consumers all key on. Our output emits this as a
   `core:externalReference/externalObject/uri`, so downstream tools
   can cross-reference our generated vegetation back to the
   authoritative register without any shared state with our pipeline.
2. **"Known to BGT" flag.** A CFTree tree matched to a BGT record is
   a **municipally-maintained (public-space) tree**; an unmatched
   CFTree reconstruction is almost certainly a private garden tree
   (or, rarely, a LiDAR false positive). Encoded via the presence /
   absence of the `externalReference` — no dedicated boolean field
   needed. On the Emmer-Compascuum small-area run: 225 of 652 CFTree trees
   are BGT-matched (~35 %), which roughly tracks the public /
   private split in that AOI.
3. **`bgtCreationDate`.** Not a planting date, but the date the tree
   feature was first registered in BGT — a soft upper bound on tree
   age. Emitted as a `gen:dateAttribute` so it does not collide with
   CityGML's `creationDate` (which means "this dataset record created
   on", a different concept).

BGT contributes **no biological data** (no species, leaf class,
height, crown, planting year). The IMGeo 2.2 schema for
`vegetatieobject_punt` has only `bgt-type` + `plus-type` + registry
bookkeeping; every biological attribute is absent from the register
itself, so no downstream mapping could populate it even with more
engineering. See the full analysis in
[`docs/vegetation_integration_report.md`](vegetation_integration_report.md) §4.3.
