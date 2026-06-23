# CityGML 2.0 + Energy ADE 3.0 Creator

Two pipelines (per-building, city-scale) that emit CityGML 2.0 + Energy ADE 3.0 documents from Dutch building-stock data. This glossary fixes the vocabulary used across the codebase, the mapping docs, and the thesis text. Mapping decisions live in [docs/adr/](./docs/adr/); per-field tables live in [docs/mapping_building.md](./docs/mapping_building.md) and [docs/mapping_city.md](./docs/mapping_city.md).

## Language

### Cadastral concepts (BAG)

**Pand**:
The BAG cadastral object for a contiguous building footprint at the structural level. Mapped one-to-one to a `bldg:Building` in the output GML.
_Avoid_: structure, complex (use Pand when reasoning at the BAG level).

**VBO**:
*Verblijfsobject*, the BAG legal usable-area unit inside a Pand (one dwelling, one shop, one office suite). One VBO carries one address and at most one EP-Online certificate. Mapped one-to-one to an `nrg3:BuildingUnit`.
_Avoid_: unit, dwelling, apartment, occupant (use VBO when speaking BAG-natively).

### GML features

**Building**:
The `bldg:Building` feature in the output. Always represents one Pand in this project.
_Avoid_: structure, Pand (use Building when naming the GML feature; use Pand when naming the BAG object).

**BuildingUnit**:
The `nrg3:BuildingUnit` feature. Always represents one VBO in this project.
_Avoid_: unit, occupant unit (use BuildingUnit when naming the GML feature).

### Qualified quantities

**Qualified attribute**:
An `nrg3:Qualified…` wrapper (`QualifiedArea`, `QualifiedVolume`, `QualifiedHeight`) carrying one value together with its `type` and its source. When a quantity has diverging sources, each source is kept as its own qualified entry rather than reconciled into one number. The owner-occupier BuildingUnit emits both the BAG gebruiksoppervlakte (122 m², the register's per-VBO usable area) and the measured-model usable area (104.2 m²) as parallel `area` entries typed `netFloorArea`, so a downstream consumer picks the provenance it trusts; the Building keeps only the measured `grossFloorArea`, since BAG registers no Pand-level area.
_Avoid_: collapsing the sources into a single "the" area, height, or volume; placing the BAG oppervlakte on the Building (it is a verblijfsobject attribute).

### Thermal zoning

**Zone**:
The `nrg3:Zone` feature: the conditioned (heated or cooled) volume of a Building, composing one or more ZoneParts. Unconditioned spaces such as an unheated attic are excluded from the Zone. Parents to the `bldg:Building` through the `nrg3:zone` hook.
_Avoid_: thermal zone (the Energy ADE 2.0 class name, dropped in 3.0), room.

**ZonePart**:
The `nrg3:ZonePart` feature: a thermal sub-unit of a Zone with homogeneous thermal behaviour, referencing a `heatingSchedule` / `coolingSchedule` by xlink into the shared `nrg3:ScheduleLibrary` (the schedule definitions live there, ByReference per the Energy ADE 3.0 UML), with its own `nrg3:zoneBoundary` surfaces and its LoD hull geometry. How a Zone is divided into ZoneParts is an author's modelling choice (per room, per room type, per storey, per setpoint regime, and so on); the owner-occupier building uses one ZonePart per storey because the two storeys run different setpoints. Parents to a `nrg3:Zone`.
_Avoid_: room, storey, subzone (a ZonePart maps to whatever granularity the author chooses; do not assume one storey or one room).

**Zone boundary surface**:
A surface on a ZonePart's `nrg3:zoneBoundary`, one of the `nrg3:Zone…Surface` subclasses (`nrg3:ZoneWallSurface`, `nrg3:ZoneRoofSurface`, `nrg3:ZoneGroundSurface`, `nrg3:ZoneIntermediateFloorSurface`, and the rest). It is the thermal boundary of the ZonePart and carries the `nrg3:layeredConstruction` xlink and the `bdgBdrySurf*` attributes. It describes the same physical fabric as the architectural `bldg:_BoundarySurface` shell, but is a separate feature with no xlink between the two.
_Avoid_: the bare names `WallSurface` / `RoofSurface` without a `bldg:` or `nrg3:` prefix.

**Zone opening**:
An opening on a zone boundary surface, attached through the `nrg3:zoneOpening` relation: `nrg3:ZoneWindow` or `nrg3:ZoneDoor`. The zone-side counterpart of the building-shell `bldg:Window` / `bldg:Door`, which ride the inherited `bldg:opening` slot. See ADR-0002 for why zone openings use `nrg3:zoneOpening` rather than `bldg:opening`.
_Avoid_: the bare names `Window` / `Door` without a `bldg:` or `nrg3:` prefix.

### Device scope

**Per-unit device**:
An energy-related device that belongs to exactly one VBO, either by physical containment (an induction cooktop in a VBO kitchen, an in-unit smart meter, an in-unit DHW buffer) or by documented functional ownership (a per-VBO EV charger in a private parking spot, even if physically outside the Pand footprint). Under the [Scope-based parent placement](#scope-based-parent-placement) rule, parents to that `nrg3:BuildingUnit`. Served scope and belongs-to scope coincide for per-unit devices.

**Collective device**:
An energy-related device that belongs to the whole Pand, either by physical attachment to Building-level structure (a rooftop solar array bolted to the roof, a central boiler in a shared basement, a façade-mounted solar thermal collector) or by serving more than one VBO (a riser-fed central boiler, a communal EV charger in a parking garage, a collective ground-source heat pump). Under the [Scope-based parent placement](#scope-based-parent-placement) rule, parents to the `bldg:Building`. When the served set is known (including the single-VBO and full-Pand cases), document it via `nrg3:relatedTo / CityObjectRelation` xlinks (codelist member `serving` from `OtherRelationTypeValue.xml`) to the covered BuildingUnits. The served-set xlinks are always emitted when knowable, even when the served set equals the whole Pand: the redundancy is intentional so a downstream consumer never has to derive the consumption side from the Pand → VBO composition.

### Device relations

**CityObjectRelation**:
The `nrg3:CityObjectRelation` complex type from Energy ADE 3.0: one polymorphic association class carrying a `relationType` (a `gml:CodeType` value drawn from the `RelationTypeValue` codelist family) and one xlink-only `relatedTo` reference to another CityObject. The UML class diagram defines `CityObjectRelation` once, with no per-relation-type subclasses; beta 4 explicitly remodelled the previous N parallel association classes (`installedOn` was its own association before then) into this one polymorphic class. Every CityObject composes a 0..* list of these via the `_GenericApplicationPropertyOfCityObject` ADE hook.

**Relation kind**:
One member of the `RelationTypeValue` codelist family registered in [`device_relations.RELATION_KINDS`](citygml_energy/device_relations.py). Each kind declares its codelist value (e.g. `installedOn`, `serving`, future `connectedTo`), its codespace URL (`OtherRelationTypeValue.xml`, `TopologicalRelationTypeValue.xml`, or `TemporalRelationTypeValue.xml`), and its target-lookup discipline (`surface` for STEP-name + LoD resolution per ADR-0001; `feature` for plain gml:id resolution). Adding a relation kind is one entry in the registry; the loader, schema generator, and applier pick it up automatically.

**`related_to` entry**:
One item in a feature's `related_to` JSON list, shaped `{"relation": str, "target": str | {"name": str, "lod": int}}`. The `relation` field is the [Relation kind](#device-relations) name; the `target` field shape depends on that kind's lookup discipline. Mirrors the Energy ADE 3.0 UML 1:1: each entry becomes one `<nrg3:relatedTo><nrg3:CityObjectRelation>` element in the output GML, preserving author order. Replaces the legacy parallel `installed_on` / `serves` fields, which were a pre-beta-4 authoring shortcut that diverged from the consolidated UML model.

### Energy and resources

**Resource**:
An `nrg3:AbstractResource`: a quantified flow of energy or matter attached to any CityObject through the `nrg3:resource` hook, carrying an `operationType` (flow direction), an amount (a scalar `amount` with a `referencePeriod`, or a `timeDependentAmount` time series), and normalisation flags. `nrg3:Energy` is the only member this project uses; `nrg3:Water`, `nrg3:Waste`, `nrg3:Food`, and `nrg3:ConstructionMaterial` are siblings on the same base.
_Avoid_: using "Energy" for the abstraction (Energy is one Resource kind).

**Energy**:
The `nrg3:Energy` Resource: one quantified energy flow on a Building, BuildingUnit, Zone, or device. Its quantity is either a scalar `amount` (with `year` and `referencePeriod`, as the EV charging figure is) or a `timeDependentAmount` time series (as the house-consumption and PV-production series are). An Energy with `operationType=demands` is the consuming side, and this project records metered consumption there because Energy ADE 3.0 has no separate `consumes`; an Energy with `operationType=produces` is the generating side.
_Avoid_: consumption / production / demand as standalone features (they are `operationType` directions of one Energy resource), meter, reading.

**Time series**:
The periodic profile backing a Resource's amount, attached through `time_dependent_amount`: `nrg3:MonthlyTimeSeries` (calendar-month buckets, used here), or `RegularTimeSeries` / `IrregularTimeSeries` and their typical-value and file variants. There is no `DailyTimeSeries`; daily data is a `RegularTimeSeries` with `timeInterval=P1D`.
_Avoid_: series, profile, curve (use Time series for the GML feature).

**Energy code axes** (orthogonal):
Five independent code axes qualify an Energy resource, and conflating them is the common error. `operationType` is the flow direction (`demands` / `produces`). `type` is the accounting basis (`final` / `primary` / `net`). `endUse` is the purpose the energy serves (`spaceHeating`, `mobility`, and so on). `energyCarrier` is the physical medium (`electricity`, `naturalGas`, and so on). `source` is where the flow originates (`powerGrid`, `photovoltaicPanels`, and so on). A rooftop PV feed-in is `produces` / `final` / `gridFeedIn` / `electricity` / `photovoltaicPanels`: each axis answers a different question. Codelist members are tabulated in [docs/mapping_building.md](docs/mapping_building.md) § 7.

**Acquisition method**:
The `nrg3:Metadata` / `acquisitionMethod` code recording how a value was obtained (`measurement`, `simulation`, `calibratedSimulation`, `estimation`, and the rest of `DataAcquisitionMethodValue.xml`). Set once at Building level as the document's default provenance; an individual Resource overrides it with its own `nrg3:Metadata` only where it differs, so the simulated PV production carries `simulation` while the metered series rely on the building-level `measurement`.
_Avoid_: provenance, source (here `source` is the energy-origin axis, a different concept).

### City pipeline

**3DBAG**:
The national LoD2 building-geometry product (BAG footprints extruded against AHN height), the geometry source for the city-scale pipeline. Distinct from **BAG**, the cadastral register behind Pand and VBO: 3DBAG supplies the shape, BAG supplies the identity and the legal units.
_Avoid_: using BAG and 3DBAG interchangeably.

**gemeente**:
The Dutch municipality, one administrative level above a woonplaats (a gemeente can hold several woonplaatsen). Named by the required `municipality` config key and the largest area a single city-scale run can cover.
_Avoid_: city.

**woonplaats**:
The BAG residential-place unit (a named town or settlement), e.g. Emmer-Compascuum within the gemeente Emmen. One possible clip target for a build extent (defined below), not a fixed build unit.
_Avoid_: city; do not use interchangeably with gemeente.

**Build extent (AOI)**:
The geographic area one city-scale run emits as a single GML, resolved once before any fetch by [`extent.resolve_build_extent`](citygml_energy/city_builder/extent.py) into a `BuildExtent` the orchestrator never branches on. Two extent kinds resolve into it. The **gemeente** kind takes the gemeente named by `municipality`, optionally clipped by a `boundary` polygon or `bbox` to a woonplaats or a smaller area of interest; uncropped it is the whole gemeente (delft / groningen / zwolle), clipped it is a woonplaats (emmer-compascuum) or a sub-woonplaats AOI (emmer-compascuum_small-area). The **address** kind (defined below) derives a square box centred on the buildings a free-text address resolves to. Both reach the same city-scale pipeline; the address kind is not a separate pipeline (see ADR-0003).
_Avoid_: treating the address kind as a third pipeline (it is an extent adapter on the city-scale pipeline).

**Address extract**:
A city-scale run whose [Build extent](#city-pipeline) is resolved from a free-text Dutch address (the optional `address` config block, entry point `examples/create_address.py`). [`address_extent.resolve_address_extent`](citygml_energy/city_builder/address_extent.py) parses the address, geocodes a coarse anchor through PDOK Locatieserver, selects the matching VBOs from authoritative BAG, and centres a square `extent_m` box on the matched buildings. The Panden those buildings sit on become the **target Panden**.
_Avoid_: "address pipeline" in the ADR sense (it is an extent kind, not a pipeline).

**Target Panden**:
The set of BAG Pand identifiers an [Address extract](#city-pipeline) singled out (`BuildExtent.target_pand_ids`), empty for every gemeente extent. When non-empty the run paints with the highlight painter rather than the energy-label painter.
_Avoid_: conflating with the full set of Panden inside the extent; the targets are the subset the query named.

**Building painter**:
The seam ([`painters.BuildingPainter`](citygml_energy/city_builder/painters.py)) that chooses how the Buildings are coloured, selected once from the resolved extent. The **energy-label painter** (the default) colours every Building by the averaged EP-Online label of its BuildingUnits; the **highlight painter** (chosen when the extent has [target Panden](#city-pipeline)) paints the target Panden one colour and their surroundings another under a separate toggleable theme. The solar-collector and vegetation appearances are always-on and orthogonal, so they are not painters.
_Avoid_: deriving the colouring mode from a sentinel; the painter is chosen from `BuildExtent.has_targets`.

**On-demand tree generation**:
The optional `vegetation.generate` block ([`VegetationGenerateSpec`](citygml_energy/city_builder/vegetation.py)) that produces the merged CFTree file for the build AOI when it is missing, rather than skipping trees. It runs CFTree as a subprocess ([`cftree_runner.ensure_tree_file`](citygml_energy/city_builder/cftree_runner.py)) at the requested AHN version, then merges the per-tile output into `vegetation.path`. The build-intent knobs (ahn_version, n_cores, buffer_m, timeout_min, case) live in the config; the machine-specific launch details (`CFTREE_REPO`, `CFTREE_RUNNER`, `CFTREE_PYTHON`) come from the environment, so a config stays shareable across machines. Generation soft-fails to a treeless build, matching the other optional inputs.
_Avoid_: putting the CFTree checkout path or interpreter in the config.

**Matchable VBO**:
A VBO whose BAG record carries both a postcode and a huisnummer, the precondition for emitting a CityGML `bldg:address` and for taking part in the EP-Online join. The predicate lives in [`address_match`](citygml_energy/city_builder/address_match.py), where one `LabelFilter` built from the matchable set drives both the EP-Online CSV row filter and the address join, so a label is only fetched when the join can use it. A VBO that is not matchable is dropped from the city output entirely (no BuildingUnit, no EPC), even when EP-Online carries a label for its BAG id.
_Avoid_: building the wanted-id or wanted-key sets anywhere outside `address_match` (the fetch filter and the join must share the one predicate).

**Tree**:
The `veg:SolitaryVegetationObject` feature the city pipeline emits from the CFTree point dataset, optionally enriched with a species from the BOR register. "Tree" is the colloquial name for it.
_Avoid_: the bare `SolitaryVegetationObject` in prose without noting it is the tree feature; plant.

**Solar collector** (city):
The `nrg3:GenericSolarCollector` feature the city pipeline emits from a solar-panel polygon detected in aerial imagery. Technology-agnostic on purpose: the aerial source carries no module-level metadata, so the array may be photovoltaic, solar-thermal, or hybrid, and the geometry carries no per-array consumer metadata. Every collector carries a `relatedTo[installedOn]` xlink to the `bldg:RoofSurface` polygon it intersects (always emitted, the topological anchor). A `serving` xlink is emitted only when the Pand has exactly one BuildingUnit, where the served set is fixed by elimination; for a zero-VBO or multi-VBO Pand the served set is genuinely unknown, so no `serving` xlink is emitted, unlike the per-building [Collective device](#device-scope) case where the served set is documented. The source polygons are legitimately "solar panels", because the RUG (University of Groningen) aerial-imagery dataset they come from annotates solar-panel footprints. Only the emitted GML feature is a solar collector.
_Avoid_: `nrg3:PhotovoltaicCollector` or calling the emitted feature photovoltaic (the type is deliberately generic); calling the emitted GML feature a "solar panel" (that is the source polygon, not the feature).

**Landcover**:
The family of CityGML features the city pipeline emits from the 3D Basisvoorziening (3DBV) ground. Terrain becomes `luse:LandUse`, roads become `tran:Road`, water becomes `wtr:WaterBody`, vegetation becomes `veg:PlantCover`, bridges become `brid:Bridge`, and anything else becomes `gen:GenericCityObject`. One 3DBV ground object becomes one Landcover feature. The 3DBV building objects are not Landcover and are dropped, since 3DBAG already supplies the Buildings.
_Avoid_: calling the whole family "terrain" (terrain is only the `luse:LandUse` member); using Landcover for a Building.

**Landcover classification**:
Reading one 3DBV ground object and deciding what it becomes, either dropped (a building, which 3DBAG supplies instead) or one Landcover feature carrying its coarse 3DBV class, its BGT function, and its physical appearance. The decision rests on the object's CityObject type together with its `3df_class` tag, because the two can disagree (a building can be filed under the `LandUse` type and marked only by `3df_class` Building).
_Avoid_: judging whether an object is a building from its CityObject type alone.

### Registers and standards

**EP-Online**:
The Dutch national register of energy-performance certificates. One certificate per VBO under NTA 8800; older regimes (NEN 7120, ISSO 82.3) used different units and per-Pand aggregation rules. See [`mapping_city.md` §6](docs/mapping_city.md) for the regime-aware mapping. Per the [Scope-based parent placement](#scope-based-parent-placement) rule, an EP-Online certificate parents to the `nrg3:BuildingUnit` (per-VBO regimes) or to the `bldg:Building` (per-Pand regimes).

**BOR**:
The municipal *Beheer Openbare Ruimte* register of public-space objects (the city pipeline uses Emmen's) that supplies a verified tree species, joined to a CFTree point by nearest match. A register like EP-Online, used to enrich a [Tree](#city-pipeline)'s `veg:species`.
_Avoid_: BGT (a separate topographic register), "tree register" (name it BOR).

**NTA 8800**:
The current Dutch method for determining a building's energy performance, in force since 2021. It fixes the units and aggregation of the EP-Online certificate (one per VBO, `final` energy in kWh/m²·yr) and the reference-climate PV-yield calculation behind the simulated production series. Older regimes (NEN 7120, ISSO 82.3) used different units and per-Pand aggregation; see [`mapping_city.md` §6](docs/mapping_city.md).
_Avoid_: BENG (the new-build norm built on NTA 8800, not the method itself), energy label (the label is the certificate's output grade).

### Units

**uom token**:
The exact unit-of-measure string written on a `@uom` attribute in the output GML, e.g. `m2`, `deg`, `kWh/m2/a`, `kJ/(K*m2)`. Every token the pipelines emit is declared once in [`citygml_energy/units.py`](citygml_energy/units.py) and is registered in the bundled KITModelViewer `Data/UOMList.xml` (as a `UOM/@id` or an `altId` alias); `tools/audit_silent_bugs.py` check H6 cross-references every `uom=` attribute of a generated GML against that catalog. The per-building input loader applies the same gate up front: every `uom` declared in the input JSON must be a member of `units.REGISTERED_UOM_TOKENS` (a test-synced mirror of the catalog spellings), so an off-catalog token is rejected at load time with the JSON path named. Tokens are wire-format labels everywhere except one place: `units.measure_value` normalises construction-layer measures (thickness, density, specific heat capacity) into SI before the thickness and heat-capacity reductions in `boundary_attributes`, converting registered aliases (`mm`, `cm`, `kJ/(kg*K)`) and warning-then-skipping unrecognised tokens.
_Avoid_: `%` (use `percent`), caret forms such as `m^2` or `kWh/(m^2*a)` (use the catalog spellings `m2`, `kWh/m2/a`), inventing tokens that are not in `UOMList.xml`.

## Conventions

### Scope-based parent placement

A feature parents to the smallest CityGML entity it belongs to. "Belongs to" is read off the source data in this order, and the first signal that resolves wins:

1. **Documented functional ownership**, when present in the source (a VBO-owned EV charger contract, a per-Pand asset register, a lease line). The named entity is the parent regardless of where the device physically sits.
2. **Physical attachment or containment**. A device bolted to Building-level structure (roof, façade, foundation, shared basement, shared loft, shared mechanical room) parents to the Building; a device physically contained inside one VBO (induction cooktop in a VBO kitchen, in-unit smart meter, balcony-mounted heat-pump indoor unit) parents to that BuildingUnit.
3. **Energy performance attribution**, when 1 and 2 do not resolve. A device whose production or consumption is fully attributed to one VBO's energy balance parents to that BuildingUnit; one whose flow is aggregated at Pand level parents to the Building.

The same ordering applies to non-device features by analogy. An EPC parents to whichever scope the document was issued for: per VBO under NTA 8800 → BuildingUnit; per Pand under German EnEV or older NL regimes → Building. An `nrg3:Energy` resource parents to whichever scope the measurement covers: a per-VBO smart-meter reading → BuildingUnit; a whole-Pand utility-meter reading → Building.

The signal ordering matters when the signals disagree. A rooftop PV array on a Pand with one VBO has physical attachment at the Building (signal 2 → Building) and energy attribution at the BuildingUnit (signal 3 → BuildingUnit); signal 2 wins, the PV array parents to the Building. A private EV charger physically mounted on a parking-spot post outside the Pand footprint has documented ownership by one VBO (signal 1 → BuildingUnit) and physical position outside the Building (signal 2 → ambiguous); signal 1 wins, the charger parents to the BuildingUnit.

When the served set is known (including the single-VBO and full-Pand cases), emit `nrg3:relatedTo / CityObjectRelation` xlinks (relation type `serving` from `OtherRelationTypeValue.xml`) from the device to each covered BuildingUnit. The served-set xlinks are always emitted when knowable, even when the served set equals the whole Pand: the redundancy is intentional so a downstream consumer never has to derive the consumption side from the Pand → VBO composition. When the served set is unknown (e.g. the city-pipeline aerial-polygon panels, which carry no per-array consumer metadata), no `serving` xlink is emitted.

The signal-ordered rule is a generalisation of Giorgio Agugiaro's guidance during the 2026-05-13 owner-occupier review, where PV was moved from BuildingUnit to Building because "it is a hardware that belongs to the whole building." Physical attachment was the load-bearing signal there; energy attribution and served scope are documented orthogonally via `relatedTo` xlinks.

### Building-shell and zone-boundary families

The pipeline emits two parallel descriptions of the same physical fabric: the architectural shell as `bldg:_BoundarySurface` subclasses with `bldg:Window` / `bldg:Door` openings (from `step-building` geometry), and the thermal envelope as `nrg3:Zone…Surface` subclasses with `nrg3:ZoneWindow` / `nrg3:ZoneDoor` openings (from `step-zonepart` geometry). Both are intentional and both are always emitted; they carry no xlink to each other. The Energy ADE 3.0 revision has no separate `ThermalBoundary` class, so the `nrg3:Zone…Surface` is the thermal boundary: it carries the `nrg3:layeredConstruction` xlink (which holds the assembly U-value and the layer build-up) and the `bdgBdrySurf*` attributes (thickness, heat capacity, areas). The Alderaan reference attaches a `nrg3:layeredConstruction` to every zone boundary surface and zone opening.

A thermal consumer reads the `nrg3:Zone…` family; a geometric or visualisation consumer reads the `bldg:` shell. Both families carry the `bdgBdrySurf*` and `bdgOpn*` area attributes, so a consumer must pick one family before summing areas or heat capacity, otherwise it double-counts the envelope. Always disambiguate the two families by namespace prefix in prose (`bldg:WallSurface` versus `nrg3:ZoneWallSurface`); the bare names are reserved for code tokens.

## Example dialogue

> **Developer:** A new dataset has a 12-VBO apartment block with a single central gas boiler in the basement, individual induction cooktops in each kitchen, a rooftop PV array, and one whole-building EPC issued in 2018 under an older regime. Where does each feature land?
>
> **Domain expert:** Walk the signal-ordered rule device by device. The induction cooktops are physically contained inside each VBO's kitchen (signal 2), so they parent to their respective BuildingUnits. The central boiler is in a shared basement (Building-level structure, signal 2), so it parents to the Building; if the source tells you it serves ten of the twelve VBOs (two are on electric DHW), emit `relatedTo[serving]` xlinks to those ten BuildingUnits. The rooftop PV array is bolted to the roof (signal 2 → Building), so it parents to the Building regardless of how its electricity is consumed; the consumer side gets its own `relatedTo[serving]` xlinks when known. The 2018 whole-building EPC describes the whole Pand, so it parents to the Building, not to any one BuildingUnit; if the same Pand later gets per-VBO NTA 8800 certs, those parent to the BuildingUnits instead.
>
> **Developer:** And if every VBO is served by the central boiler?
>
> **Domain expert:** Emit the `relatedTo[serving]` xlinks to all twelve BuildingUnits anyway. The redundancy is intentional: a downstream consumer should never have to fall back on the Pand → VBO composition to know which units the device serves. The same applies to a PV array on a single-VBO Pand: parent the array to the Building, emit one `relatedTo[serving]` xlink to the lone BuildingUnit.
