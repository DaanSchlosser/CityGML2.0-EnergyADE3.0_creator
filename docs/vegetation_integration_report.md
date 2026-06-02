# Vegetation integration for the Emmer-Compascuum city pipeline

This report accompanies the vegetation (tree) extension of the
city-scale CityGML 2.0 + Energy ADE 3.0 generator. It documents the
data sources used, the concrete mapping onto the CityGML data model,
and the remaining gaps in the model.

It is written as a thesis-level record of decisions, not as an
end-user manual: the code paths are described in enough detail that a
reader can reproduce the run, but feature documentation lives in the
main `README.md`.

## 1. Goal

Emmer-Compascuum is the city-scale pipeline's primary smoke test.
A single hand-drawn concave polygon in
[`inputs/boundaries/emmer-compascuum_small-area.geojson`](../inputs/boundaries/emmer-compascuum_small-area.geojson)
(41.5 ha, EPSG:28992) carves out the test area. The canonical config
is [`inputs/cities/emmer-compascuum_small-area.json`](../inputs/cities/emmer-compascuum_small-area.json).
This extension answers:

> Can individual trees be stored meaningfully in a CityGML 2.0 + Energy
> ADE 3.0 output, derived end-to-end from Dutch government open data,
> and does the data model cover what we actually have?

The concrete deliverable is one GML file that XSD-validates and
carries real-world tree locations + LoD3 crown+trunk geometry for the
area:

| Output | Buildings | Trees | Solar panels | Size | Valid |
|---|---|---|---|---|---|
| [`generated/emmer_compascuum.gml`](../generated/emmer_compascuum.gml) | 674 | 652 | 334 | 167 MB | XSD-valid |

CFTree processed the 41.5 ha AOI (4 intersecting AHN4 sub-tiles),
producing 652 reconstructed trees in 36.8 min wall-clock on 8 cores.
The city pipeline then loads that tree set and the same boundary
polygon clips it in place. BGT's authoritative per-tree register
(`vegetatieobject_punt`, plus_type `boom`) carries 714 boom points
inside the same AOI; a 4 m nearest-neighbour join cross-references
225 of the 652 CFTree trees back to their BGT `lokaal_id`. The ~35 %
match rate is expected for a mixed residential / rural AOI: BGT only
registers publicly-maintained trees, so private-garden trees
reconstructed by CFTree have no BGT entry by design.

A second 4 m nearest-neighbour join attaches Gemeente Emmen's
`bor_groen_bomen_beschermd` ArcGIS FeatureServer record to each CFTree
tree where one is in range. Unlike BGT, this register carries genuine
attributes (Latin and Dutch species name, planting year, height and
trunk-diameter classes, protection status, growth form). Of those,
only the Latin scientific name fits a typed CityGML 2.0 vegetation
slot honestly (`veg:species`); the rest land in a second
`core:externalReference` and `gen:*Attribute` siblings, because the
CityGML 2.0 vegetation module has no native slots for protection
regimes, growth-form descriptors, or class-band measurements. See
§ 3.3 for the per-field reasoning.

## 2. Data sources

Scope: **CFTree-derived geometry, BGT-derived authoritative
cross-references, and Gemeente Emmen BOR-derived attribute
enrichment**. Non-government attribute sources (OpenStreetMap, the
Bomenstichting's Landelijk Register Monumentale Bomen) were initially
integrated as nearest-neighbour enrichments but dropped from this
build, see §4.3 for the rationale. Emmen's BOR layer is in scope
because it is published by a Dutch municipality (`ago@emmen`),
which keeps the pipeline within the "Dutch government open data
only" policy that excluded the OSM and Bomenstichting sources.

| # | Source | What it provides | License | Access method used |
|---|---|---|---|---|
| 1 | **CFTree** ([NoahAlting/CFTree](https://github.com/NoahAlting/CFTree)) | LoD3 watertight crown + trunk triangle meshes, per-tree morphometrics (height, DBH, crown width, porosity, r50) | GPL-3.0 (the tool; outputs are derivatives of AHN, which is open government data) | External preprocessor in a WSL conda env; outputs consumed as `trees_lod3.city.json` tiles |
| 2 | **AHN4** (Actueel Hoogtebestand Nederland, 2020 flight) | Raw LiDAR point cloud at ~10 points/m²; input to CFTree | CC-0 | Downloaded per tile via CFTree's `get_data` stage from the TU Delft GeoTiles mirror (`https://geotiles.citg.tudelft.nl/AHN4_T/<kaartblad>_<subtile>.LAZ`) |
| 3 | **BGT / IMGeo 2.2** `vegetatieobject_punt` (plus_type `boom`) | Authoritative per-tree point register maintained by municipalities / provinces / water boards. No semantic attributes (no species, no leaf class, no planting year, no dimensions), only an authoritative handle plus registry metadata. | CC-0 (PDOK) | PDOK OGC API Features: `https://api.pdok.nl/lv/bgt/ogc/v1/collections/vegetatieobject_punt/items?bbox=…&bbox-crs=EPSG::28992`. Pagination via `rel="next"` links. Cached in the pipeline's `CachedSession`. |
| 4 | **Gemeente Emmen `bor_groen_bomen_beschermd`** | Per-tree register of trees registered under Emmen's public-space management (~58 k records: 57 503 `Bijzondere boom` + 466 `Monumentale boom`). Carries Latin and Dutch species name, planting year, height and trunk-diameter classes, protection status, growth form, and ecological standplaats. ~26 % of records have a populated species, ~93 % have a planting year. | Free use with attribution (per the layer's `licenseInfo` field; "Bij het overnemen van (delen van) de kaart, moet de bron worden vermeld") | ArcGIS REST FeatureServer query: `https://services3.arcgis.com/YaBq8GMTp0Kh437n/arcgis/rest/services/bor_groen_bomen_beschermd/FeatureServer/0/query?geometry=…&inSR=28992&outSR=28992&f=json`. Bbox-filtered, paged via `resultOffset`, cached by the same `CachedSession`. |

### 2.1 AHN5 / AHN6 availability: why AHN4 is the current input

The Emmer-Compascuum bbox (EPSG:28992 `[264400, 535580, 268720,
538940]`) is in the north-east of the Netherlands. That matters,
because the three most recent AHN flights cover the country in phases:

* **AHN4** (2020, complete nationwide), **available and open**:
  `https://basisdata.nl/hwh-ahn/ahn4/01_LAZ/C_<kaartblad>.LAZ` and
  mirrored per sub-tile at the TU Delft GeoTiles service. This is the
  only input that runs CFTree end-to-end today.
* **AHN5** (2023 flight), **does not cover NE Netherlands**. Verified
  against the `EllipsisDrive_index` layer of
  `https://basisdata.nl/hwh-ahn/AUX/bladwijzer.gpkg`: all four
  kaartbladen intersecting Emmer-Compascuum (`18AZ1`, `18AZ2`, `18CN1`,
  `18CN2`) have `AHN5_LAZ = NaN`. Put differently: AHN5 was flown
  mostly in the west + centre of the country.
* **AHN6** (2025 flight), **scheduled and inventoried, but not yet
  publicly downloadable for this bbox**. The `bladwijzer_AHN6.gpkg`
  published on `basisdata.nl/hwh-ahn/AUX/` does list 20 1×1 km tiles
  over Emmer-Compascuum (all `jaar=2025`, `perceel=3`), but
  `basisdata.nl/hwh-ahn/AHN6/...` returns `403 AccessDenied` on every
  probed path. The AHN dataroom and Ellipsis Drive host the data,
  but without a public HTTP URL pattern or unauthenticated API. This
  matches the rollout pattern of previous AHN versions: the bladwijzer
  metadata is published first, then LAZ tiles land on basisdata.nl
  some months later.

Consequence: the pipeline is wired to the newest publicly-downloadable
AHN version that covers the AOI, which today is AHN4. When AHN6 lands
on `basisdata.nl` or on the GeoTiles mirror, switching is a one-line
base-URL change in [`scripts/get_data.py`](../../CFTree/scripts/get_data.py).

### 2.2 What CFTree writes

CFTree's reconstruction stage produces one
`data/<case>/tiles/<tile_id>/trees_lod3.city.json` per AHN sub-tile.
Each file is a CityJSON 2.0 document containing one
`SolitaryVegetationObject` per tree (`T_<gtid>`) with two Solid
geometries per object (`"crown"` then `"trunk"` by convention, no
role tag inside the CityObject) and a flat attribute dict with keys:

| CFTree attribute | Unit | Meaning |
|---|---|---|
| `gtid` | - | Global tree id, stable across re-runs |
| `tile_id` | - | Source AHN sub-tile |
| `crown_width_m` | m | Diameter of the circle equal-area to the crown convex hull |
| `crown_median_z` | m (NAP) | Median elevation of the crown alpha-wrap vertices |
| `crown_r50_m` | m | Median nearest-neighbour distance (LAI proxy) |
| `crown_porosity` | - | Voxel-derived porosity ∈ [0, 1] |
| `trunk_H_m` | m | Total tree height (DTM base → crown median Z) |
| `trunk_DBH_m` | m | Diameter at breast height (allometric estimate) |
| `trunk_radius_m` | m | Trunk radius at DBH |
| `trunk_base_height_m` | m (NAP) | Elevation of the trunk base, sampled from the DTM under the crown footprint |

## 3. Mapping to CityGML 2.0

All mapping is through `veg:SolitaryVegetationObject`, which the
CityGML 2.0 vegetation module defines with these optional fields
(`minOccurs=0`):

`class`, `function`, `usage`, `species`, `height`, `trunkDiameter`,
`crownDiameter`, `lod{1..4}Geometry`, `lod{1..4}ImplicitRepresentation`,
plus everything inherited from `core:AbstractCityObjectType`
(`gml:id`/`name`/`description`, `creationDate`, `terminationDate`,
`externalReference`, `relativeToTerrain`, `relativeToWater`, and any
`gen:*Attribute` child).

### 3.1 CFTree → CityGML

| CFTree attribute | CityGML field | Notes |
|---|---|---|
| `T_<gtid>` (object id) | `gml:id = "tree_<gtid>"` | Prefix added because `xs:ID` requires a non-digit first character |
| `gtid` | `gml:name` (`T_<gtid>`) | Informational, preserved for traceability |
| Solid triangles (crown + trunk) | `veg:lod3Geometry` → `gml:MultiSurface` | Merged: CityGML 2.0 has no per-component slot for a single tree; the crown and trunk faces live in the same MultiSurface but remain visually coherent because they share global RD coordinates |
| `trunk_H_m` | `veg:height` (`gml:LengthType`, uom `m`) | Direct |
| `trunk_DBH_m` | `veg:trunkDiameter` (`gml:LengthType`, uom `m`) | Direct |
| `crown_width_m` | `veg:crownDiameter` (`gml:LengthType`, uom `m`) | Direct |
| `crown_median_z`, `crown_r50_m`, `crown_porosity`, `trunk_radius_m`, `trunk_base_height_m` | `gen:doubleAttribute name="<cftree_key>"` | No native CityGML slot; preserved so CFD / microclimate tools can still reach them |

### 3.2 BGT cross-reference → CityGML

When a CFTree tree has a BGT `vegetatieobject_punt` (plus_type `boom`)
within 4 m of its crown centroid, the builder attaches:

| BGT field | CityGML field | Notes |
|---|---|---|
| `lokaal_id` | `core:externalReference/externalObject/uri` | Written as the dereferenceable PDOK OGC-API-Features URL (`.../vegetatieobject_punt/items/<lokaal_id>`) so a consumer can `GET` it back as GeoJSON. The raw handle is the URL's final path segment. |
| Presence in BGT | presence of the `externalReference` element | Acts as a "known to BGT" flag without a dedicated boolean attribute; trees without a BGT match simply omit the reference. |
| `creation_date` | `gen:dateAttribute name="bgtCreationDate"` | Explicitly **not** `core:creationDate`, which in CityGML means "when this CityObject record was created in the dataset" rather than "when the real-world feature was first registered in an external system". Using `creationDate` here would mis-signal dataset lifecycle to any downstream tool that keys on it. |

The 4 m match radius balances BGT's nominal 0.3 m class-D positional
accuracy against CFTree's crown-centroid-to-trunk offset (1-3 m on a
one-sided canopy). Tuned against the small-area run: 225 of 652 CFTree
trees got a BGT match, a coverage figure that roughly tracks
public-space vs garden-space in the AOI, since BGT only records
publicly-maintained trees.

Note on `ExternalObjectReferenceType`: the CityGML 2.0 type is an
`xs:choice` between `name` and `uri`, not a sequence. Attempting to
emit both produces an XSD-invalid file. We chose `uri` because the
`lokaal_id` (the other option) is still reachable as the URL's tail
segment, so picking the URI loses no information.

### 3.3 Gemeente Emmen BOR enrichment → CityGML

When a CFTree tree has an Emmen `bor_groen_bomen_beschermd` record
within 4 m of its crown centroid, the builder attaches the source
attributes to the vegetation object. The match runs independently of
the BGT cross-reference, so a tree may carry zero, one, or both
`core:externalReference` siblings (the element is
`maxOccurs="unbounded"` on `core:AbstractCityObjectType`).

The CityGML 2.0 vegetation module exposes four typed `gml:CodeType`
slots (`class`, `function`, `usage`, and `species`), but they have
specific intents (per SIG3D convention): `class` distinguishes
tree-vs-shrub-vs-hedge, `function` and `usage` describe horticultural
roles ("shade tree", "street tree", "production forest"), and
`species` carries the Latin binomial. Of Emmen's per-tree fields,
**only `soortnaam` matches one of these slots honestly**.
Protection regime (`Bijzondere boom`) is a legal / heritage status,
not a function; growth form (`Boom vrij uitgroeiend`) is a canopy
descriptor, not a class. Forcing those into the typed slots would
mis-signal to any consumer reading the vocabulary semantically, so
they go into `gen:stringAttribute` siblings instead.

| Emmen field | CityGML field | Notes |
|---|---|---|
| `boom_id` | `core:externalReference/externalObject/uri` | Dereferenceable ArcGIS REST query URL keyed on `boom_id` (Emmen's stable internal id), not on `OBJECTID` (volatile across server-side rebuilds). `informationSystem` is the public Erfgoed page (`https://gemeente.emmen.nl/erfgoed`) for the same reason BGT uses the PDOK catalogue page rather than the API endpoint. |
| `soortnaam` (Latin, e.g. `Quercus palustris`) | `veg:species` (`gml:CodeType`) | The textbook fit: a Latin binomial is exactly what `species` is for. `codeSpace` points at the Emmen FeatureServer URL because that is where the exact name string was sourced; a botanical authority (GBIF, ITIS) would mislead about provenance. |
| `soortnaam_ned` (Dutch common name) | `gen:stringAttribute name="speciesCommonName"` | `veg:species` is single-valued and already carries the Latin name; no native vernacular-name slot exists. |
| `jaarvanaanleg` | `gen:intAttribute name="plantingYear"` | `core:creationDate` is reserved for record-lifecycle semantics (§4.1 #1), and `xs:date` would force a fake month and day on a year-only source. |
| `boomhoogteklasseactueel` (e.g. `"18 tot 24 m."`) | `gen:stringAttribute name="heightClass"` | Categorical band, not a measurement. CFTree already populates `veg:height` from a precise value, so this is an audit-trail sibling rather than a competing slot. |
| `stamdiameterklasse` (e.g. `"0,5 tot 0,75 m."`) | `gen:stringAttribute name="trunkDiameterClass"` | Same reasoning as above against `veg:trunkDiameter`. |
| `beschermingsstatus` (`Bijzondere boom` / `Monumentale boom`) | `gen:stringAttribute name="protectionStatus"` | A legal / heritage status, not a horticultural function. `veg:function` would mis-label it; this stays a generic. |
| `beschermingsstatus_detail` (`Bomenlijst boom`, `Bomenstructuur boom`) | `gen:stringAttribute name="protectionStatusDetail"` | Sub-classification within the protection regime. |
| `type` (`Boom vrij uitgroeiend` / `Boom niet vrij uitgroeiend`) | `gen:stringAttribute name="growthForm"` | A canopy / growth-form descriptor (free vs constrained / pollarded / pleached). `veg:class` is for tree-vs-shrub kind, not growth form, so this stays a generic. |
| `standplaats` (`Gras- en kruidachtigen`, `Bos`, `Houtwal`, …) | `gen:stringAttribute name="standLocation"` | Ecological context of the *surroundings*; no native slot. |
| `standplaats_detail` (e.g. `Gazon`) | `gen:stringAttribute name="standLocationDetail"` | |

Trees with no BOR record carry only the BGT and CFTree slots filled
in §§ 3.1 and 3.2; nothing else is emitted.

Coverage notes:

* Roughly 26 % of BOR records have `soortnaam_ned` populated (15 150 of
  57 969); the rest sit in the register without a species attribution.
  The CityGML output reflects the source: a BOR-matched tree without
  a species value simply omits `veg:species`.
* Roughly 93 % of records have a `jaarvanaanleg`. The `gen:intAttribute`
  is omitted on the rest.
* The 4 m match radius is identical to BGT's
  ([`tree_matching.MATCH_RADIUS_M`](../citygml_energy/city_builder/tree_matching.py)),
  for the same crown-centroid-vs-trunk-offset reason. BOR points sit
  at the trunk, like BGT, so the same trade-off applies; the constant
  lives once in `tree_matching` because the two registers describe
  the same physical thing.

### 3.4 Appearance

An `app:Appearance` with theme `"vegetation"` is emitted alongside
the existing `"energyLabel"` and `"solarPanels"` themes. It carries one
`app:X3DMaterial` whose `diffuseColor` is a deep foliage green
(`0.15 0.55 0.15`) and whose `<app:target>` list references the
`gml:MultiSurface` container of every `veg:SolitaryVegetationObject` in
the city model. Member polygons are not targeted: an appearance on a
`gml:MultiSurface` is valid for all of its member surfaces per the
CityGML 2.0 Appearance model, so the colour propagates to the polygons
from the container target. This matches the Alderaan reference data,
whose `app:target` list holds only container ids.

Built by
[`append_vegetation_appearance`](../citygml_energy/city_builder/appearance.py#L198)
alongside the existing energy-label and solar-panel appearance steps.

### 3.5 What the XML looks like

A BGT-matched tree serialises to the following CityGML 2.0 fragment
(validated against the bundled XSD set by `tools/validate_xsd.py`):

```xml
<veg:SolitaryVegetationObject gml:id="tree_42">
  <gml:name>T_42</gml:name>
  <core:externalReference>
    <core:informationSystem>https://www.pdok.nl/ogc-apis/-/article/basisregistratie-grootschalige-topografie-bgt-</core:informationSystem>
    <core:externalObject>
      <core:uri>https://api.pdok.nl/lv/bgt/ogc/v1/collections/vegetatieobject_punt/items/G0114.703d17f4c978045de05363ab720afc9b</core:uri>
    </core:externalObject>
  </core:externalReference>
  <gen:dateAttribute name="bgtCreationDate"><gen:value>2018-07-04</gen:value></gen:dateAttribute>
  <gen:doubleAttribute name="crown_porosity"><gen:value>0.35</gen:value></gen:doubleAttribute>
  <gen:doubleAttribute name="crown_r50_m"><gen:value>0.14</gen:value></gen:doubleAttribute>
  <gen:doubleAttribute name="crown_median_z"><gen:value>16.27</gen:value></gen:doubleAttribute>
  <gen:doubleAttribute name="trunk_radius_m"><gen:value>0.07</gen:value></gen:doubleAttribute>
  <gen:doubleAttribute name="trunk_base_height_m"><gen:value>12.26</gen:value></gen:doubleAttribute>
  <veg:height uom="m">12.5</veg:height>
  <veg:trunkDiameter uom="m">0.4</veg:trunkDiameter>
  <veg:crownDiameter uom="m">6.0</veg:crownDiameter>
  <veg:lod3Geometry><gml:MultiSurface ... /></veg:lod3Geometry>
</veg:SolitaryVegetationObject>
```

Trees without a BGT match omit the two first elements
(`core:externalReference` and `gen:dateAttribute`); everything else is
identical.

A tree with both BGT and BOR matches additionally carries the BOR
slots described in §3.3:

```xml
<veg:SolitaryVegetationObject gml:id="tree_42">
  <gml:name>T_42</gml:name>
  <core:externalReference>
    <core:informationSystem>https://www.pdok.nl/ogc-apis/-/article/basisregistratie-grootschalige-topografie-bgt-</core:informationSystem>
    <core:externalObject>
      <core:uri>https://api.pdok.nl/lv/bgt/ogc/v1/collections/vegetatieobject_punt/items/G0114.703d17f4c978045de05363ab720afc9b</core:uri>
    </core:externalObject>
  </core:externalReference>
  <core:externalReference>
    <core:informationSystem>https://gemeente.emmen.nl/erfgoed</core:informationSystem>
    <core:externalObject>
      <core:uri>https://services3.arcgis.com/YaBq8GMTp0Kh437n/arcgis/rest/services/bor_groen_bomen_beschermd/FeatureServer/0/query?where=boom_id%3D25649&amp;outFields=*&amp;outSR=28992&amp;f=geojson</core:uri>
    </core:externalObject>
  </core:externalReference>
  <gen:dateAttribute name="bgtCreationDate"><gen:value>2018-07-04</gen:value></gen:dateAttribute>
  <gen:stringAttribute name="speciesCommonName"><gen:value>Moeraseik</gen:value></gen:stringAttribute>
  <gen:stringAttribute name="heightClass"><gen:value>18 tot 24 m.</gen:value></gen:stringAttribute>
  <gen:stringAttribute name="trunkDiameterClass"><gen:value>0,5 tot 0,75 m.</gen:value></gen:stringAttribute>
  <gen:stringAttribute name="protectionStatus"><gen:value>Bijzondere boom</gen:value></gen:stringAttribute>
  <gen:stringAttribute name="protectionStatusDetail"><gen:value>Bomenstructuur boom</gen:value></gen:stringAttribute>
  <gen:stringAttribute name="growthForm"><gen:value>Boom vrij uitgroeiend</gen:value></gen:stringAttribute>
  <gen:stringAttribute name="standLocation"><gen:value>Gras- en kruidachtigen</gen:value></gen:stringAttribute>
  <gen:stringAttribute name="standLocationDetail"><gen:value>Gazon</gen:value></gen:stringAttribute>
  <gen:intAttribute name="plantingYear"><gen:value>1960</gen:value></gen:intAttribute>
  <gen:doubleAttribute name="crown_porosity"><gen:value>0.35</gen:value></gen:doubleAttribute>
  <!-- … remaining gen:doubleAttribute siblings as above … -->
  <veg:species codeSpace="https://services3.arcgis.com/.../bor_groen_bomen_beschermd/FeatureServer/0">Quercus palustris</veg:species>
  <veg:height uom="m">12.5</veg:height>
  <veg:trunkDiameter uom="m">0.4</veg:trunkDiameter>
  <veg:crownDiameter uom="m">6.0</veg:crownDiameter>
  <veg:lod3Geometry><gml:MultiSurface ... /></veg:lod3Geometry>
</veg:SolitaryVegetationObject>
```

A tree with only a BOR match (no BGT) keeps the BOR
`core:externalReference` and BOR-derived slots and omits the BGT
ones; a tree with neither falls back to the geometry-and-morphometrics-only
shape from §3.1.

## 4. Is the data model complete?

### 4.1 CityGML 2.0 vegetation module: adequate, with two genuine gaps

The core of a tree (a point or solid location, total height, trunk
and crown diameter, species) is natively represented. Everything
CFTree measures morphologically goes into a native field, and Emmen's
BOR enrichment populates `veg:species` for the subset of trees the
register covers (§3.3). That is the right answer in the sense that
any CityGML 2.0 consumer can pick the tree up and render it correctly
without knowing about this pipeline.

The other typed `gml:CodeType` slots (`veg:class`, `veg:function`,
`veg:usage`) stay empty in the current build. Per SIG3D convention
they are reserved for botanical / horticultural classifications
(tree-vs-shrub, shade-vs-fruit-vs-street tree, …) which no Dutch
government source carries per-tree. Emmen's `beschermingsstatus` and
`type` fields look superficially like candidates, but they describe
legal status and growth form respectively, not the horticultural
roles those slots are meant for; emitting them as `function` / `class`
would mis-signal the vocabulary to any semantically-aware consumer.
They live in `gen:stringAttribute` siblings instead (§3.3).

Two attributes we have but cannot express natively:

1. **Planting date / age.** CityGML 2.0 has `creationDate` on every
   CityObject, but its semantics are "when this CityObject record was
   created in the dataset", not "when the tree was planted". Using
   `creationDate` for the planting year would silently mis-label the
   data. The pipeline therefore writes BOR's `jaarvanaanleg` as
   `gen:intAttribute name="plantingYear"` (§3.3), a documented
   workaround rather than a native solution.
2. **Leaf type and leaf cycle.** `class` / `function` are CodeType
   fields, which means they can carry anything behind a codeSpace, but
   there is no standard vocabulary. Workaround: a previous revision
   published OSM's `Key:leaf_type` and `Key:leaf_cycle` wiki URLs as
   the codeSpace; that source was dropped (§4.3) and no Dutch
   government layer carries leaf type or cycle, so this gap remains
   un-filled in the current build.

A third, less clean, limitation is that **CityGML 2.0 has no
concept of "tree component"**: a tree is one `SolitaryVegetationObject`
with one geometry per LoD, not a crown + trunk + root composite. CFTree
reconstructs crown and trunk as separate Solids; we merge them into a
single `gml:MultiSurface` for the `lod3Geometry` without loss of
geometric information, but the component hint is gone. CityGML 3.0
introduced `CityObject` parent/child nesting via `relatedTo`, which
would fix this cleanly; until we migrate, the semantics we preserve
are "this is the whole tree" and not "this triangle belongs to the
crown".

CFTree also computes three genuinely useful non-morphometric metrics
(porosity, r50, median Z) for which there is no native slot and no
clear conventional slot. We preserve them as `gen:doubleAttribute`s so
CFD-facing consumers have access, but a plain CityGML viewer will
display them as "unknown attributes". For a thesis this is the right
cost / benefit balance; for a production pipeline the project would
need to either (a) publish its own ADE that extends
`_GenericApplicationPropertyOfSolitaryVegetationObject` with
`cfdPorosity`, `r50`, etc., or (b) wait for a future vegetation ADE
from SIG3D.

### 4.3 Source selection: OSM and Monumentale Bomen out, BGT and BOR in

Three candidate enrichments were evaluated. Two were dropped, two
were kept:

* **OpenStreetMap (dropped).** Wired up in an earlier revision as an
  8 m nearest-neighbour join. A diagnostic pass over the
  Emmer-Compascuum small-area AOI found 20 `natural=tree` nodes in the
  bbox. 11 of the 652 CFTree trees got matched by proximity (1-5 m),
  but **every matched OSM node had only the `natural=tree` tag and
  no others**: no species, no leaf_type, no leaf_cycle, no
  start_date. The "enrichment" contributed nothing beyond a
  cross-reference link to the OSM node id, while OSM is also outside
  the project's "Dutch government data only" policy. Removed.
* **Landelijk Register Monumentale Bomen (dropped).** 0 entries in
  the Emmer-Compascuum bbox (expected for a rural Dutch village
  without nationally-listed specimens). The Bomenstichting is an
  NGO, not a government register, so this source is also outside
  the project's policy even where it does carry useful attributes.
  Removed.
* **BGT `vegetatieobject_punt` (kept as cross-reference, §3.2).**
  Dutch government data, but the IMGeo 2.2 catalogue documents the
  schema as carrying only `bgt-type` plus `plus-type`: no species,
  no leaf class, no planting year, no dimensions. A BGT join cannot
  add any attribute CFTree does not already have. It does carry
  three non-attribute signals that add information: an authoritative
  Dutch-government identifier (`lokaal_id`), presence/absence as a
  proxy for "publicly-maintained vs private", and a feature creation
  date that bounds tree age. The first two cross the bar for
  inclusion; BGT therefore writes a `core:externalReference` and a
  `gen:dateAttribute name="bgtCreationDate"` and nothing else. No
  BGT data writes into `veg:species`, `veg:class`, `veg:function`,
  or any Latin/vernacular field.
* **Gemeente Emmen `bor_groen_bomen_beschermd` (kept as both
  cross-reference and attribute enrichment, §3.3).** Dutch
  government data (owner `ago@emmen`), so the policy is satisfied;
  unlike BGT it carries genuine per-tree attributes (Latin and
  Dutch species, planting year, height and trunk-diameter classes,
  protection status, growth form). It is the only source in the
  current build that populates the native `veg:species` slot. The
  remaining BOR fields land in `gen:*Attribute` siblings rather
  than the typed `veg:class` / `veg:function` / `veg:usage` slots,
  because protection regime is a legal status and growth form is
  a canopy descriptor, neither of which matches the horticultural intent
  of those typed slots (§3.3 reasoning). Coverage is partial (about
  26 % of records have a populated species and ~93 % have a
  planting year) and the layer is Emmen-specific, both of which
  are honest limitations rather than bugs in the integration: every
  enriched CityGML element reflects exactly what Emmen's authority
  registered.

The BOR matcher is a direct call to the generic
[`tree_matching.match_nearest_within`](../citygml_energy/city_builder/tree_matching.py)
from `vegetation._match_to_bor`, with `register_label="Emmen BOR"`.
There is no longer a BOR-specific wrapper module: the previous
`tree_enrichment.py` shim added no benefit over the inline call,
so it was removed. The git history preserves the previous "intentionally
empty" comment, so a contributor following the trail of "tree enrichment"
back through the log lands first on the active matcher and then on
the rationale for what was dropped.

### 4.4 Energy ADE 3.0: silent on vegetation

The Energy ADE 3.0 beta 8 schema set, as bundled in
[`Energy_ADE-3.0beta8/`](../Energy_ADE-3.0beta8/), does not extend
`SolitaryVegetationObject` or `PlantCover`: it focuses on buildings,
building units, zones, devices, constructions, and schedules.

This is **not a gap per se**: vegetation does not produce or consume
energy inside the Energy ADE model. Tree effects that Energy ADE
*could* plausibly care about (external shading, evapotranspiration,
microclimate forcing on an adjacent building's heating/cooling demand)
are currently handled in Energy ADE via
`nrg3:BoundarySurface`-level transmittance and the WeatherData section,
not via vegetation-aware modelling. Noting this as a deliberate scope
decision, not a bug, feels right.

If a future Energy ADE version wanted to integrate vegetation, the
minimal extension would be a `_GenericApplicationPropertyOfSolitaryVegetationObject`
substitution offering `nrg3:shadingEffect` and `nrg3:evapotranspirationRate`,
both `nrg3:RegularTimeSeries`-valued so they hook into the existing
schedule vocabulary. That is a clean thesis-scope follow-up; it is
not part of this pipeline today.

## 5. Proposed amendments to the model

Concrete proposals, ranked by how likely they are to affect real use
cases:

1. **Publish a tiny CFTree ADE.** A handful of
   `_GenericApplicationPropertyOfSolitaryVegetationObject` extensions
   for `cfdPorosity`, `crownR50`, `crownMedianZ`, and
   `trunkBase`-as-`gml:Point`. That converts all of
   section 3.1's `gen:doubleAttribute` rows into typed fields with
   schema-level documentation, and makes them discoverable by any
   schema-driven tooling (xsdata, FME, KITModelViewer).
2. **Register a `plantingYear` generic attribute convention.** Until
   a native `plantingYear` exists in a vegetation ADE, pinning the
   attribute name + semantics to a documented codeSpace in the
   project would let other tools consume it without guessing the name.
3. **Use CityGML 3.0's parent/child `relatedTo` when we migrate.**
   The crown + trunk components then become first-class child
   `GenericCityObject`s of the parent `SolitaryVegetationObject`. No
   information is invented; the geometric split that CFTree already
   computes becomes expressible.
4. **Do not lift `creationDate` to mean "planting date".** Leave it
   for what it is (dataset record creation date). The temptation to
   reuse it for planting date is strong because it is the only
   xs:date on the CityObject, but the semantic mismatch leaks into
   every downstream consumer that keys lifecycle logic on it.

## 6. Implementation notes (for reproducibility)

The pipeline, end-to-end, on a fresh WSL Ubuntu 24.04 machine:

1. `wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && bash ~/miniconda.sh -b`
2. `conda env create -f CFTree/environment.yml` (≈ 20 min, 5.9 GB
   env, 7 GB conda package cache)
3. **CGAL header patch.** CGAL 5.6.1 as shipped by conda-forge has
   three `this->base()` call sites in
   `CGAL/boost/graph/iterator.h` that GCC 15 (the compiler conda-forge
   pulls in) rejects. Applied surgical fix: replace
   `this->base() == nullptr` with `this->g == nullptr` at lines 219,
   313, 405. Equivalent semantics (both test "iterator not bound to a
   Graph"); unblocks the AlphaWrap build.
4. Build the two C++ binaries:
   `cmake -S src/reconstruction/AlphaWrap -B .../AlphaWrap/build && make -C .../AlphaWrap/build` and the
   equivalent for `src/segmentation/TreeSeparation`.
5. **Line endings.** CFTree's shell scripts (`tiles_clipper_robust.sh`
   and friends) are checked out with CRLF on Windows. Fix:
   `find CFTree -name '*.sh' -exec sed -i 's/\r$//' {} \;`.
6. **AHN URL base.** `scripts/get_data.py` hardcodes
   `https://geotiles.citg.tudelft.nl/AHN5_T`, which does not exist
   (see §2.1). Patched to `AHN4_T`.
7. Drop the Emmer-Compascuum AOI polygon in
   `CFTree/cases/emmer_compascuum/case_area.geojson`, derived from
   the `grids.gpkg` bbox `[264400, 535580, 268720, 538940]` in
   EPSG:28992.
8. `python CFTree/main.py --case emmer_compascuum --n-cores 8 --overwrite`.

The Python integration on the city-builder side needs no WSL; the
conda env is only needed for the CFTree preprocessor. The city builder
reads CFTree's CityJSON output directly through the Windows filesystem
share.

## 7. Known limitations / follow-ups

* **Run on AHN6 when it publishes.** Will happen by the next AHN
  release cycle (probably Q3-Q4 2026 for this perceel). Action:
  retest the URL pattern `basisdata.nl/hwh-ahn/AHN6/01_LAZ/` and bump
  the CFTree `base_url`.
* **Emmen BOR FeatureServer endpoint.** The ArcGIS REST URL
  (`services3.arcgis.com/YaBq8GMTp0Kh437n/.../bor_groen_bomen_beschermd`)
  is owned by Gemeente Emmen, not by the project. The fetcher pins
  it as a single constant
  ([`fetchers.emmen_bor.BOR_FEATURESERVER_URL`](../citygml_energy/city_builder/fetchers/emmen_bor.py))
  and degrades soft on any network or parse failure, so a surprise
  URL change manifests as "tree enrichment skipped, see warning"
  rather than a build failure. A periodic health-check would still
  catch the change earlier.
* **BOR enrichment is Emmen-specific.** Outside the Emmen
  municipality the bbox query returns zero features. This is by
  design for the city pipeline's PoC scope; a generic
  `MunicipalTreeRegisterSource` abstraction is a clean follow-up
  but not part of this build.
* **No OSM / Monumentale Bomen enrichment in this build.** See §4.3.
  The Bomenstichting's national register and OSM `natural=tree`
  are out of scope under the current "Dutch government data only"
  policy. The `tree_enrichment.py` module that previously held the
  scaffold for those sources was first repurposed for BOR and then
  removed when the BOR-specific wrapper proved to add nothing
  over an inline call to `tree_matching.match_nearest_within`.
* **Boundary polygon format.** Only single-feature GeoJSON
  (`.geojson` / `.json`) is accepted by
  [`BoundarySource`](../citygml_energy/city_builder/boundary.py);
  `load_boundary_polygon` raises `CityBuildError` on any other
  extension, and `BoundarySource` carries only a `path` (no layer / fid).
  The canonical default is
  [`inputs/boundaries/emmer-compascuum_small-area.geojson`](../inputs/boundaries/emmer-compascuum_small-area.geojson)
  (~2 KB, EPSG:28992, MultiPolygon).
* **GPL-3.0 contagion.** CFTree is GPL-3.0. We treat it as an external
  preprocessor (subprocess at build time) and do not import from it;
  the CityJSON output is a derivative of AHN (CC-0), not of CFTree
  code, so the generator's own code stays at its permissive license.
  If CFTree were ever imported as a Python library, the project
  license would have to re-align.
