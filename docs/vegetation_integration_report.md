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
[`inputs/emmer_compascuum_area.geojson`](../inputs/emmer_compascuum_area.geojson)
(41.5 ha, EPSG:28992) carves out the test area. The canonical config
is [`inputs/emmer_compascuum.json`](../inputs/emmer_compascuum.json).
This extension answers:

> Can individual trees be stored meaningfully in a CityGML 2.0 + Energy
> ADE 3.0 output, derived end-to-end from Dutch government open data,
> and does the data model cover what we actually have?

The concrete deliverable is one GML file that XSD-validates and
carries real-world tree locations + LoD3 crown+trunk geometry for the
area:

| Output | Buildings | Trees | PV panels | Size | Valid |
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

## 2. Data sources

Scope is deliberately narrow: **CFTree-derived geometry, BGT-derived
authoritative cross-references**. Non-government attribute sources
(OpenStreetMap, the Bomenstichting's Landelijk Register Monumentale
Bomen) were initially integrated as nearest-neighbour enrichments but
dropped from this build — see §4.3 for the rationale.

| # | Source | What it provides | License | Access method used |
|---|---|---|---|---|
| 1 | **CFTree** ([NoahAlting/CFTree](https://github.com/NoahAlting/CFTree)) | LoD3 watertight crown + trunk triangle meshes, per-tree morphometrics (height, DBH, crown width, porosity, r50) | GPL-3.0 (the tool; outputs are derivatives of AHN, which is open government data) | External preprocessor in a WSL conda env; outputs consumed as `trees_lod3.city.json` tiles |
| 2 | **AHN4** (Actueel Hoogtebestand Nederland, 2020 flight) | Raw LiDAR point cloud at ~10 points/m²; input to CFTree | CC-0 | Downloaded per tile via CFTree's `get_data` stage from the TU Delft GeoTiles mirror (`https://geotiles.citg.tudelft.nl/AHN4_T/<kaartblad>_<subtile>.LAZ`) |
| 3 | **BGT / IMGeo 2.2** `vegetatieobject_punt` (plus_type `boom`) | Authoritative per-tree point register maintained by municipalities / provinces / water boards. No semantic attributes (no species, no leaf class, no planting year, no dimensions) — only an authoritative handle + registry metadata. | CC-0 (PDOK) | PDOK OGC API Features: `https://api.pdok.nl/lv/bgt/ogc/v1/collections/vegetatieobject_punt/items?bbox=…&bbox-crs=EPSG::28992`. Pagination via `rel="next"` links. Cached in the pipeline's `CachedSession`. |

### 2.1 AHN5 / AHN6 availability — why AHN4 is the current input

The Emmer-Compascuum bbox (EPSG:28992 `[264400, 535580, 268720,
538940]`) is in the north-east of the Netherlands. That matters,
because the three most recent AHN flights cover the country in phases:

* **AHN4** (2020, complete nationwide) — **available and open**:
  `https://basisdata.nl/hwh-ahn/ahn4/01_LAZ/C_<kaartblad>.LAZ` and
  mirrored per sub-tile at the TU Delft GeoTiles service. This is the
  only input that runs CFTree end-to-end today.
* **AHN5** (2023 flight) — **does not cover NE Netherlands**. Verified
  against the `EllipsisDrive_index` layer of
  `https://basisdata.nl/hwh-ahn/AUX/bladwijzer.gpkg`: all four
  kaartbladen intersecting Emmer-Compascuum (`18AZ1`, `18AZ2`, `18CN1`,
  `18CN2`) have `AHN5_LAZ = NaN`. Put differently: AHN5 was flown
  mostly in the west + centre of the country.
* **AHN6** (2025 flight) — **scheduled and inventoried, but not yet
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
| `gtid` | — | Global tree id, stable across re-runs |
| `tile_id` | — | Source AHN sub-tile |
| `crown_width_m` | m | Diameter of the circle equal-area to the crown convex hull |
| `crown_median_z` | m (NAP) | Median elevation of the crown alpha-wrap vertices |
| `crown_r50_m` | m | Median nearest-neighbour distance (LAI proxy) |
| `crown_porosity` | — | Voxel-derived porosity ∈ [0, 1] |
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
| Presence in BGT | presence of the `externalReference` element | Acts as a "known to BGT" flag without a dedicated boolean attribute — trees without a BGT match simply omit the reference. |
| `creation_date` | `gen:dateAttribute name="bgtCreationDate"` | Explicitly **not** `core:creationDate`, which in CityGML means "when this CityObject record was created in the dataset" rather than "when the real-world feature was first registered in an external system". Using `creationDate` here would mis-signal dataset lifecycle to any downstream tool that keys on it. |

The 4 m match radius balances BGT's nominal 0.3 m class-D positional
accuracy against CFTree's crown-centroid-to-trunk offset (1–3 m on a
one-sided canopy). Tuned against the grid2 run: 225 of 652 CFTree
trees got a BGT match — a coverage figure that roughly tracks
public-space vs garden-space in the AOI, since BGT only records
publicly-maintained trees.

Note on `ExternalObjectReferenceType`: the CityGML 2.0 type is an
`xs:choice` between `name` and `uri`, not a sequence. Attempting to
emit both produces an XSD-invalid file. We chose `uri` because the
`lokaal_id` (the other option) is still reachable as the URL's tail
segment, so picking the URI loses no information.

### 3.3 Appearance

An `app:Appearance` with theme `"vegetation"` is emitted alongside
the existing `"energyLabel"` and `"pvPanels"` themes. It carries one
`app:X3DMaterial` whose `diffuseColor` is a deep foliage green
(`0.15 0.55 0.15`) and whose `<app:target>` list references every
`gml:MultiSurface` and `gml:Polygon` under every
`veg:SolitaryVegetationObject` in the city model. Per-polygon
targets accompany the container targets to match the KIT
SDM_KITModelViewer family's requirement: those viewers silently skip
appearance targets that point at a container `gml:MultiSurface`, so
emitting both keeps the colour applied everywhere.

Built by
[`append_vegetation_appearance`](../citygml_energy/city_builder/appearance.py#L149)
alongside the existing energy-label and PV-panel appearance steps.

### 3.4 What the XML looks like

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

## 4. Is the data model complete?

### 4.1 CityGML 2.0 vegetation module — adequate, with two genuine gaps

The core of a tree — a point (or solid) location, total height, trunk
and crown diameter, species — is natively represented. Everything
CFTree measures morphologically goes into a native field. That is the
right answer in the sense that any CityGML 2.0 consumer can pick the
tree up and render it correctly without knowing about this pipeline.

Two attributes we have but cannot express natively:

1. **Planting date / age.** CityGML 2.0 has `creationDate` on every
   CityObject, but its semantics are "when this CityObject record was
   created in the dataset", not "when the tree was planted". Using
   `creationDate` for the planting year would silently mis-label the
   data. Workaround: `gen:intAttribute name="plantingYear"`.
2. **Leaf type and leaf cycle.** `class` / `function` are CodeType
   fields, which means they can carry anything behind a codeSpace, but
   there is no standard vocabulary. Workaround: we publish OSM's
   `Key:leaf_type` and `Key:leaf_cycle` wiki URLs as the codeSpace so
   the enumeration is self-documenting.

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

### 4.3 Why no attribute enrichment from OSM or Monumentale Bomen

Both sources were wired up in an earlier revision as optional
nearest-neighbour joins over the CFTree tree set, at an 8 m radius.
They were removed from the production path after a diagnostic pass
over the Emmer-Compascuum grid2 area showed:

* **OpenStreetMap**: 20 `natural=tree` nodes in the bbox. 11 of the
  652 CFTree trees got matched by proximity (1-5 m), but **every
  matched OSM node had only the `natural=tree` tag and no others** —
  no species, no leaf_type, no leaf_cycle, no start_date. The
  "enrichment" contributed nothing beyond a cross-reference link to
  the OSM node id.
* **Landelijk Register Monumentale Bomen**: 0 entries in the bbox
  (expected for a rural Dutch village without nationally-listed
  specimens). The Bomenstichting is an NGO, not a government
  register, which puts this source outside the project's
  Dutch-government-data scope even where it does carry useful
  attributes.

Combined with the decision to scope the pipeline to Dutch government
open data only, both enrichments were removed.

BGT `vegetatieobject_punt` (the one remaining candidate that *is*
Dutch government data) *was* re-evaluated after that decision. The
IMGeo 2.2 catalog documents its schema as carrying only `bgt-type` +
`plus-type` — no species, no leaf class, no planting year, no
dimensions — which initially looked like a reject: a BGT join could
not add any attribute CFTree did not already have. However, closer
inspection shows BGT carries **three non-attribute signals** that
genuinely add information:

1. An **authoritative Dutch-government identifier** (`lokaal_id`)
   usable as a cross-reference by any downstream system that keys on
   BGT (municipal tree-maintenance databases, GreenIndex indicators,
   national asset registers). CFTree alone has no such handle.
2. **Presence/absence** in BGT: a BGT-matched CFTree tree is
   municipally-registered (public space); an unmatched one is almost
   certainly private garden vegetation. That distinction is
   load-bearing for any downstream analysis scoped to the public
   realm.
3. **Feature creation date** in the register: not a planting date,
   but a genuine upper bound on tree age that carries into CFD /
   microclimate modelling as a weak prior.

Only the first two are value-adds that cross the bar for inclusion,
so BGT is integrated as a **cross-reference layer only** (§3.2), not
as an attribute-enrichment layer. No BGT data writes into
`veg:species`, `veg:class`, `veg:function`, or any Latin/vernacular
field. The dropped OSM + Monumentale-Bomen enrichment module
survives as a documented pointer at
[`citygml_energy/city_builder/tree_enrichment.py`](../citygml_energy/city_builder/tree_enrichment.py)
so that a future contributor searching the git history for
"tree enrichment" lands at the reasoning rather than having to
reconstruct it from deleted commits.

### 4.4 Energy ADE 3.0 — silent on vegetation

The Energy ADE 3.0 beta 8 schema set, as bundled in
[`Energy_ADE-3.0beta8/`](../Energy_ADE-3.0beta8/), does not extend
`SolitaryVegetationObject` or `PlantCover`: it focuses on buildings,
building units, zones, devices, constructions, and schedules.

This is **not a gap per se**: vegetation does not produce or consume
energy inside the Energy ADE model. Tree effects that Energy ADE
*could* plausibly care about — external shading, evapotranspiration,
microclimate forcing on an adjacent building's heating/cooling demand
— are currently handled in Energy ADE via
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
   schema-driven tooling (xsdata, FME, KIT SDM).
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
   `CFTree/cases/emmer_compascuum/case_area.geojson` — derived from
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
* **Monumentale Bomen endpoint.** The ArcGIS FeatureServer URL is
  maintained by the Bomenstichting and has been stable for years, but
  is not under our control. A periodic health-check on the endpoint
  would catch a surprise URL change.
* **No OSM / Monumentale Bomen enrichment in this build.** See §4.3.
  Re-integration would take one commit (module already scaffolded at
  `citygml_energy/city_builder/tree_enrichment.py`) but is not in
  scope under the current "Dutch government data only" policy.
* **Boundary polygon format.** Both GeoPackage (`.gpkg` + layer + fid)
  and GeoJSON (`.geojson`, single feature) are accepted by
  [`BoundarySource`](../citygml_energy/city_builder/boundary.py).
  The canonical default is
  [`inputs/emmer_compascuum_area.geojson`](../inputs/emmer_compascuum_area.geojson)
  (~2 KB, EPSG:28992, MultiPolygon).
* **GPL-3.0 contagion.** CFTree is GPL-3.0. We treat it as an external
  preprocessor (subprocess at build time) and do not import from it;
  the CityJSON output is a derivative of AHN (CC-0), not of CFTree
  code, so the generator's own code stays at its permissive license.
  If CFTree were ever imported as a Python library, the project
  license would have to re-align.
