# 0001. Device-to-surface relations: LoD-aware resolver

## Status

accepted

## Decision

`installed_on` resolves through a `(STEP layer name, LoD level)` index instead of a flat `{name: gml:id}` dictionary. A bare-name entry like `"RoofSurface_01"` collapses the LoD axis by picking the highest LoD present for the name, falling back to the gml:id-keyed feature index when no STEP-name match exists. An object-form entry like `{"name": "RoofSurface_01", "lod": 2}` pins the relation to one specific LoD's representation and does not fall back. Each entry emits one `nrg3:CityObjectRelation` with `relationType="installedOn"` pointing at the resolved `gml:id`.

The highest-LoD default is the conservative pick when the author has not authored a LoD signal. It does not claim to match consumer intent in general, since a consumer's preferred LoD is application-specific. It minimises the risk of pointing at an under-specified face by picking the most fully-modelled representation the model actually carries.

## Considered Options

**Status quo (flat `{name: gml:id}` index, last write wins).** Rejected. The output silently depended on the ordering of `geometry_sources`, with LoD-specific relations dropped on overwrite. Listing LoD3 after LoD2 happened to produce correct output for the canonical input, but the dependency on author discipline was never validator-enforced and never visible from the GML.

**Fan-out per LoD on bare names (one relation per LoD where the name resolves).** Rejected. STEP layer names are not preserved-identity across LoDs in this pipeline. The author numbers sub-faces fresh per LoD, and the same label can refer to different physical faces at LoD2 and LoD3. A bare-name fan-out would emit a relation to every LoD's namesake regardless of whether the physical face is the same, creating false relations to faces the device does not sit on. The canonical input demonstrates the problem: at LoD2 there are two main pitched-roof slopes named `RoofSurface_01` and `_02`; at LoD3 those same names label two sub-faces of a lower extension roof; the LoD2 faces and the LoD3 faces are different physical objects.

**Refactor to the standard's canonical multi-LoD-per-feature shape.** Rejected for this fix. It is a research-grade refactor that requires deciding what to do when LoD3 subdivides an LoD2 face into multiple smaller features. CityGML 3.0 itself does not resolve this (Kutzner et al. 2020 confirms that `Space` and `SpaceBoundary` subclasses are still intended to carry multiple LoD geometries colocated on one feature, which only works for the 1:1 case). Out of scope for the per-building pipeline today.

**Semantic LoD-invariant naming convention (require authors to use the same label at every LoD for the same physical face).** Rejected. The naming convention would require a parallel taxonomy with no home in the schema, would not survive LoD subdivision (1:1 name correspondence breaks the moment LoD3 splits one LoD2 face into multiple sub-faces), and would push the verification burden onto authors with no machine-readable check.

## Consequences

Existing canonical behaviour is preserved end-to-end. The canonical owner-occupier input lists `geometry_sources` in ascending-LoD order (LoD0, LoD1, LoD2, LoD3), and the highest-LoD-wins default reproduces the same two relations to the same two LoD3 RoofSurface gml:ids (`_7` and `_6`) as the previous flat-index implementation. The full test suite passes unchanged. The two new tests in `tests/test_reference_building.py` cover the object form, asserting that `{"name": "RoofSurface_01", "lod": 2}` pins to the LoD2 gml:id even when LoD3 is present, and that an object-form entry with a LoD where the name is not attached raises a focused `InputFileError`.

Authors gain an opt-in escape hatch for LoD-specific targeting through the object form. The bare-name form remains the canonical authoring shape and what the canonical input uses. The object form is only required when the author intentionally wants a non-highest-LoD representation, which is rare in practice because most consumers prefer the most-detailed available representation.

The horizontal axis remains structurally inexpressible in Energy ADE 3.0. A device whose footprint covers part of multiple roof faces still produces a list of qualitative `installedOn` relations with no native quantification slot on `nrg3:CityObjectRelation`. The workaround documented in `docs/mapping_building.md` § 15.8 (one PV feature per face plus a master aggregator that holds the energy resource) stays the schema-honest shape until a future Energy ADE revision adds an `installationCoverage` measure or equivalent. This ADR is scoped to the vertical axis; the horizontal axis is recorded as a schema gap, not a decision.

`docs/mapping_building.md` § 10 documents both authoring shapes. § 13.1's obsolete "ascending-LoD ordering convention" paragraph has been replaced with a forward-pointer to § 15.8, which contains the thesis-grade writeup of the two-axis problem.

JSON schema accepts both shapes through a `oneOf` on each `installed_on` entry. The schema is generated, so any future change to the authoring shape must go through `tools/generate_input_schema.py`.

## References

Kutzner, T., Chaturvedi, K., Kolbe, T. H. (2020). *CityGML 3.0: New Functions Open Up New Applications.* PFG 88, 43-61. <https://doi.org/10.1007/s41064-020-00095-z>
