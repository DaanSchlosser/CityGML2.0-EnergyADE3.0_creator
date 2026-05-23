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
An energy-related device whose served scope is exactly one VBO (e.g. an individual heat pump, a kitchen appliance, a per-VBO EV charger, a per-VBO DHW buffer). Under the [Scope-based parent placement](#scope-based-parent-placement) rule, parents to that `nrg3:BuildingUnit`.

**Collective device**:
An energy-related device whose served scope is the whole Pand or any set of VBOs larger than one (e.g. a central boiler feeding multiple VBOs via a riser, a shared rooftop solar array, a shared EV charger in a building's parking garage, a collective ground-source heat pump). Under the [Scope-based parent placement](#scope-based-parent-placement) rule, parents to the `bldg:Building`. When the served set is a proper subset of the Pand's VBOs, document it via `nrg3:relatedTo / CityObjectRelation` xlinks (codelist member `serving` from `OtherRelationTypeValue.xml`) to the covered BuildingUnits.

### Registers

**EP-online**:
The Dutch national register of energy-performance certificates. One certificate per VBO under NTA 8800; older regimes (NEN 7120, ISSO 82.3) used different units and per-Pand aggregation rules. See [[reference_eponline_dates_and_regimes]] for the regime-aware mapping. Per the [Scope-based parent placement](#scope-based-parent-placement) rule, an EP-online certificate parents to the `nrg3:BuildingUnit` (per-VBO regimes) or to the `bldg:Building` (per-Pand regimes).

## Conventions

### Scope-based parent placement

A feature parents to the smallest entity whose scope it fully describes. The rule asks one question: what is the smallest CityGML entity whose extent contains the thing this feature describes? Use the answer as the parent. The rule applies to devices, energy-performance certificates, energy resources, and any future per-something feature.

Worked applications:

- A device that serves exactly one VBO is a [Per-unit device](#device-scope) and parents to the BuildingUnit.
- A device that serves the whole Pand or several VBOs (a central boiler, a shared rooftop solar array, a communal EV charger) is a [Collective device](#device-scope) and parents to the Building.
- An EPC issued per VBO (NL NTA 8800) parents to the BuildingUnit; one issued per Pand (German EnEV, some older NL regimes) parents to the Building.
- An `nrg3:Energy` resource that measures one VBO's consumption (a per-unit smart meter) parents to the BuildingUnit; one that measures whole-Pand consumption (a building-level utility meter) parents to the Building.

When the scope is a strict subset of the Pand's VBOs (more than one, but not all), parent to the Building and emit `nrg3:relatedTo / CityObjectRelation` xlinks (relation type `serving` from `OtherRelationTypeValue.xml`) to the covered BuildingUnits. This keeps the parent at the smallest fully-covering entity and uses the relation system to document the partial coverage.

The rule is a generalisation of Giorgio Agugiaro's guidance during the 2026-05-13 owner-occupier review, where PV was moved from BuildingUnit to Building because "it is a hardware that belongs to the whole building." The same reasoning extends to any feature whose scope is wider or narrower than one VBO.

## Example dialogue

> **Developer:** A new dataset has a 12-VBO apartment block with a single central gas boiler in the basement, individual induction cooktops in each kitchen, and one whole-building EPC issued in 2018 under an older regime. Where does each feature land?
>
> **Domain expert:** Run them through the scope-based rule one by one. The induction cooktops each serve exactly one VBO, so they are per-unit devices and parent to their respective BuildingUnits. The central boiler serves more than one VBO, so it is a collective device and parents to the Building; if you have data on which VBOs it serves (maybe ten of the twelve, with two on electric DHW), document the served set as `relatedTo` xlinks to those ten BuildingUnits. The 2018 whole-building EPC describes the whole Pand, so it parents to the Building, not to any one BuildingUnit; if the same Pand later gets per-VBO NTA 8800 certs, those parent to the BuildingUnits instead.
>
> **Developer:** And if every VBO is served by the central boiler?
>
> **Domain expert:** Then the served set equals the Pand's full VBO list and the xlinks are redundant, so omit them. The device's placement on the Building is already the schema-honest signal for "serves the whole Pand."
