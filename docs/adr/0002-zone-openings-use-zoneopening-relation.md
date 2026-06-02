# 0002. Zone-boundary openings use the nrg3:zoneOpening relation

## Status

accepted

## Decision

Openings on an Energy ADE zone boundary surface (`nrg3:ZoneWallSurface` and the other `nrg3:Zone…Surface` subclasses, attached to a `nrg3:ZonePart` from a `step-zonepart-lod{2,3}` source) are emitted as `nrg3:ZoneWindow` / `nrg3:ZoneDoor` through the `nrg3:zoneOpening` relation, not as `bldg:Window` / `bldg:Door` through the inherited `bldg:opening` slot. The geometry pipeline promotes the STEP opening layer names (`Window_*`, `Door_*`) to the zone opening classes through `geometry._BLDG_TO_ZONE_NAME_REMAP` and attaches them on the `zone_opening` field. Building-shell openings (from `step-building-lod{2,3}`) are unchanged: they stay `bldg:Window` / `bldg:Door` on `bldg:opening`.

## Considered Options

**Inherited `bldg:opening` slot with `bldg:Window` / `bldg:Door`.** Rejected. `nrg3:AbstractZoneBoundarySurfaceType` extends `bldg:AbstractBoundarySurfaceType`, so a zone boundary surface inherits the `bldg:opening` relation, and both `bldg:Window` / `Door` and `nrg3:ZoneWindow` / `ZoneDoor` substitute into `bldg:_Opening`. A `bldg:Window` inside the inherited `bldg:opening` of a zone surface therefore passes XSD validation, which is why the original pipeline emitted it that way and no validation step caught it. It does not match the Energy ADE 3.0 intent: the schema adds a dedicated `nrg3:zoneOpening` composition on the zone boundary surface specifically to carry the zone opening classes, and the Alderaan reference data uses `nrg3:zoneOpening` with `nrg3:ZoneWindow` / `nrg3:ZoneDoor` exclusively for zone-boundary openings.

## Consequences

Zone openings now land on the classes the reference data uses, so the output is correct in spirit, not merely XSD-valid. The `bdgOpn*` derived attributes still apply, because `nrg3:ZoneWindow` / `nrg3:ZoneDoor` inherit the `bdg_opn_area` family from the shared `bldg:_Opening` base. The opaque-area computation on the parent zone surface reads openings from both the `opening` and `zone_opening` relations (`boundary_attributes._OPENING_RELATION_FIELDS`), so it still deducts the opening area. Construction mapping keys on the XSD type name, so `construction_mapping.by_type` carries `ZoneWindow` and `ZoneDoor` entries alongside the building openings.

Both encodings validate against the XSD, so the choice is invisible to a validator. It is recorded here to stop a future reader from moving zone openings back onto the inherited `bldg:opening` slot on the assumption that the two are equivalent.

## References

Alderaan reference data: `Energy_ADE-3.0beta8/test_data/Alderaan_Energy_ADE_All.gml` (the `ZoneWallSurface` blocks carry `nrg3:zoneOpening` / `nrg3:ZoneWindow`). Per-field documentation: `docs/mapping_building.md` § 3 (Zone and ZonePart) and § 12.2 (per-opening attributes).
