# CityGML 2.0 + EnergyADE 3.0 Creator

Two pipelines (per-building, city-scale) that emit CityGML 2.0 + Energy ADE 3.0 documents from Dutch building-stock data. This glossary fixes the vocabulary used across the codebase, the mapping docs, and the thesis text. Mapping decisions live in [docs/adr/](./docs/adr/); per-field tables live in [docs/mapping_building.md](./docs/mapping_building.md) and [docs/mapping_city.md](./docs/mapping_city.md).

## Language

### Cadastral concepts (BAG)

**Pand**:
The BAG cadastral object for a contiguous building footprint at the structural level. Mapped one-to-one to a `bldg:Building` in the output GML.
_Avoid_: structure, complex (use Pand when reasoning at the BAG level).

**VBO**:
*Verblijfsobject*, the BAG legal usable-area unit inside a Pand (one dwelling, one shop, one office suite). One VBO carries one address and at most one EP-online certificate. Mapped one-to-one to an `nrg3:BuildingUnit`.
_Avoid_: unit, dwelling, apartment, occupant (use VBO when speaking BAG-natively).

### GML features

**Building**:
The `bldg:Building` feature in the output. Always represents one Pand in this project.
_Avoid_: structure, Pand (use Building when naming the GML feature; use Pand when naming the BAG object).

**BuildingUnit**:
The `nrg3:BuildingUnit` feature. Always represents one VBO in this project.
_Avoid_: unit, occupant unit (use BuildingUnit when naming the GML feature).

### Device scope

**Per-unit device**:
An energy-related device that belongs to exactly one VBO, either by physical containment (an induction cooktop in a VBO kitchen, an in-unit smart meter, an in-unit DHW buffer) or by documented functional ownership (a per-VBO EV charger in a private parking spot, even if physically outside the Pand footprint). Under the [Scope-based parent placement](#scope-based-parent-placement) rule, parents to that `nrg3:BuildingUnit`. Served scope and belongs-to scope coincide for per-unit devices.

**Collective device**:
An energy-related device that belongs to the whole Pand, either by physical attachment to Building-level structure (a rooftop solar array bolted to the roof, a central boiler in a shared basement, a façade-mounted solar thermal collector) or by serving more than one VBO (a riser-fed central boiler, a communal EV charger in a parking garage, a collective ground-source heat pump). Under the [Scope-based parent placement](#scope-based-parent-placement) rule, parents to the `bldg:Building`. When the served set is known — including the single-VBO and full-Pand cases — document it via `nrg3:relatedTo / CityObjectRelation` xlinks (codelist member `serving` from `OtherRelationTypeValue.xml`) to the covered BuildingUnits. The served-set xlinks are always emitted when knowable, even when the served set equals the whole Pand: the redundancy is intentional so a downstream consumer never has to derive the consumption side from the Pand → VBO composition.

### Device relations

**CityObjectRelation**:
The `nrg3:CityObjectRelation` complex type from EnergyADE 3.0: one polymorphic association class carrying a `relationType` (a `gml:CodeType` value drawn from the `RelationTypeValue` codelist family) and one xlink-only `relatedTo` reference to another CityObject. The UML class diagram defines `CityObjectRelation` once, with no per-relation-type subclasses — beta 4 explicitly remodelled the previous N parallel association classes (`installedOn` was its own association before then) into this one polymorphic class. Every CityObject composes a 0..* list of these via the `_GenericApplicationPropertyOfCityObject` ADE hook.

**Relation kind**:
One member of the `RelationTypeValue` codelist family registered in [`device_relations.RELATION_KINDS`](citygml_energy/device_relations.py). Each kind declares its codelist value (e.g. `installedOn`, `serving`, future `connectedTo`), its codespace URL (`OtherRelationTypeValue.xml`, `TopologicalRelationTypeValue.xml`, or `TemporalRelationTypeValue.xml`), and its target-lookup discipline (`surface` for STEP-name + LoD resolution per ADR-0001; `feature` for plain gml:id resolution). Adding a relation kind is one entry in the registry; the loader, schema generator, and applier pick it up automatically.

**`related_to` entry**:
One item in a feature's `related_to` JSON list, shaped `{"relation": str, "target": str | {"name": str, "lod": int}}`. The `relation` field is the [Relation kind](#device-relations) name; the `target` field shape depends on that kind's lookup discipline. Mirrors the EnergyADE 3.0 UML 1:1 — each entry becomes one `<nrg3:relatedTo><nrg3:CityObjectRelation>` element in the output GML, preserving author order. Replaces the legacy parallel `installed_on` / `serves` fields, which were a pre-beta-4 authoring shortcut that diverged from the consolidated UML model.

### Registers

**EP-online**:
The Dutch national register of energy-performance certificates. One certificate per VBO under NTA 8800; older regimes (NEN 7120, ISSO 82.3) used different units and per-Pand aggregation rules. See [[reference_eponline_dates_and_regimes]] for the regime-aware mapping. Per the [Scope-based parent placement](#scope-based-parent-placement) rule, an EP-online certificate parents to the `nrg3:BuildingUnit` (per-VBO regimes) or to the `bldg:Building` (per-Pand regimes).

## Conventions

### Scope-based parent placement

A feature parents to the smallest CityGML entity it belongs to. "Belongs to" is read off the source data in this order, and the first signal that resolves wins:

1. **Documented functional ownership**, when present in the source (a VBO-owned EV charger contract, a per-Pand asset register, a lease line). The named entity is the parent regardless of where the device physically sits.
2. **Physical attachment or containment**. A device bolted to Building-level structure (roof, façade, foundation, shared basement, shared loft, shared mechanical room) parents to the Building; a device physically contained inside one VBO (induction cooktop in a VBO kitchen, in-unit smart meter, balcony-mounted heat-pump indoor unit) parents to that BuildingUnit.
3. **Energy performance attribution**, when 1 and 2 do not resolve. A device whose production or consumption is fully attributed to one VBO's energy balance parents to that BuildingUnit; one whose flow is aggregated at Pand level parents to the Building.

The same ordering applies to non-device features by analogy. An EPC parents to whichever scope the document was issued for: per VBO under NTA 8800 → BuildingUnit; per Pand under German EnEV or older NL regimes → Building. An `nrg3:Energy` resource parents to whichever scope the measurement covers: a per-VBO smart-meter reading → BuildingUnit; a whole-Pand utility-meter reading → Building.

The signal ordering matters when the signals disagree. A rooftop PV array on a Pand with one VBO has physical attachment at the Building (signal 2 → Building) and energy attribution at the BuildingUnit (signal 3 → BuildingUnit); signal 2 wins, the PV array parents to the Building. A private EV charger physically mounted on a parking-spot post outside the Pand footprint has documented ownership by one VBO (signal 1 → BuildingUnit) and physical position outside the Building (signal 2 → ambiguous); signal 1 wins, the charger parents to the BuildingUnit.

When the served set is known — including the single-VBO and full-Pand cases — emit `nrg3:relatedTo / CityObjectRelation` xlinks (relation type `serving` from `OtherRelationTypeValue.xml`) from the device to each covered BuildingUnit. The served-set xlinks are always emitted when knowable, even when the served set equals the whole Pand: the redundancy is intentional so a downstream consumer never has to derive the consumption side from the Pand → VBO composition. When the served set is unknown (e.g. the city-pipeline aerial-polygon panels, which carry no per-array consumer metadata), no `serving` xlink is emitted.

The signal-ordered rule is a generalisation of Giorgio Agugiaro's guidance during the 2026-05-13 owner-occupier review, where PV was moved from BuildingUnit to Building because "it is a hardware that belongs to the whole building." Physical attachment was the load-bearing signal there; energy attribution and served scope are documented orthogonally via `relatedTo` xlinks.

## Example dialogue

> **Developer:** A new dataset has a 12-VBO apartment block with a single central gas boiler in the basement, individual induction cooktops in each kitchen, a rooftop PV array, and one whole-building EPC issued in 2018 under an older regime. Where does each feature land?
>
> **Domain expert:** Walk the signal-ordered rule device by device. The induction cooktops are physically contained inside each VBO's kitchen (signal 2), so they parent to their respective BuildingUnits. The central boiler is in a shared basement — Building-level structure (signal 2) — so it parents to the Building; if the source tells you it serves ten of the twelve VBOs (two are on electric DHW), emit `relatedTo[serving]` xlinks to those ten BuildingUnits. The rooftop PV array is bolted to the roof (signal 2 → Building), so it parents to the Building regardless of how its electricity is consumed; the consumer side gets its own `relatedTo[serving]` xlinks when known. The 2018 whole-building EPC describes the whole Pand, so it parents to the Building, not to any one BuildingUnit; if the same Pand later gets per-VBO NTA 8800 certs, those parent to the BuildingUnits instead.
>
> **Developer:** And if every VBO is served by the central boiler?
>
> **Domain expert:** Emit the `relatedTo[serving]` xlinks to all twelve BuildingUnits anyway. The redundancy is intentional — a downstream consumer should never have to fall back on the Pand → VBO composition to know which units the device serves. The same applies to a PV array on a single-VBO Pand: parent the array to the Building, emit one `relatedTo[serving]` xlink to the lone BuildingUnit.
