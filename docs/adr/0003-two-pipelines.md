# 0003. Two independent pipelines: per-building and city-scale

## Status

accepted

## Decision

The repository runs two separate generation pipelines that both emit CityGML 2.0 + Energy ADE 3.0, and a given building goes through one or the other, never both.

- **Per-building pipeline** (`citygml_energy/generation.py` / `input_loader.py`, entry point `examples/create_building.py`): driven by a hand-authored JSON feature collection plus STEP geometry. It produces the full Energy ADE detail a renovation passport needs: thermal zones and zone parts, layered constructions and materials, the device stack, energy resources and time series, and LoD2 / LoD3 boundary surfaces with per-surface thermal attributes. One building at a time, authored by a person.
- **City-scale pipeline** (`citygml_energy/city_builder/`, entry point `examples/create_city.py`): driven by national open data for a whole gemeente or a clipped area of interest. It fetches 3DBAG LoD2 geometry, BAG Pand / VBO records, EP-Online certificates, BGT / BOR vegetation, and aerial-imagery solar-panel polygons, and emits the whole extent in bulk. It has no source of layered constructions, thermal zones, hand-authored device stacks, or STEP geometry, so it deliberately does not emit them; the only devices it emits are solar collectors (`nrg3:GenericSolarCollector`), one per detected aerial polygon, with no technology asserted. Building types use the RVO Dutch verbatim vocabulary rather than the Energy ADE codelist.

The two share the bindings, the namespace / codespace layer, and the serializer, but have separate loaders, builders, input schemas, and mapping docs (`docs/mapping_building.md` versus `docs/mapping_city.md`).

## Considered Options

**One unified pipeline with optional detail.** Rejected. The two regimes have almost disjoint inputs (one hand-authored JSON + STEP per building; the other bulk national datasets keyed by municipality) and almost disjoint outputs (rich per-building physics versus bulk LoD2 stock). Forcing them through one code path would mean a single loader carrying both the STEP-geometry / construction-library machinery and the WFS-fetch / tile-parse machinery, with most of each unused on any run.

## Consequences

The split is why several asymmetries between the two outputs are deliberate rather than gaps: the city pipeline emits no `Thickness` / `HeatCapacity` (it has no constructions) and no zones, and its only devices are the aerial-detected solar collectors; per-building `bdgType` may use the Energy ADE codelist while the city pipeline uses the RVO verbatim term; default provenance differs. A reader comparing the two outputs must not treat the city pipeline's omissions as missing data to be filled by the per-building emitters. For any building authored in full detail, the per-building pipeline supersedes the city path.
