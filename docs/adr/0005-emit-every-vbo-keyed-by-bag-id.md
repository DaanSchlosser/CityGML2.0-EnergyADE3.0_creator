# 0005. Emit every VBO as a BuildingUnit, keyed by its BAG id

## Status

accepted

## Decision

Every BAG verblijfsobject (VBO) in the build extent becomes one `nrg3:BuildingUnit`, identified by its `verblijfsobject_id` (the BAG identificatie). That id is always present, and it is emitted both as the `bu_<id>` gml:id and as an `nrg3:identifier` carrying a BAG codeSpace. A VBO is never dropped for a missing or partial address: postcode and huisnummer are optional, and whatever address parts exist are emitted as a (possibly partial) `bldg:address`, or none at all for a unit such as a garage or storage box that carries no postcode.

EP-Online energy labels are matched primarily on the `verblijfsobject_id` (the `BAGVerblijfsobjectID` column), which every VBO has. The normalised `(postcode, huisnummer, huisletter, toevoeging)` address key is only a fallback for older labels that predate the BAG-id enrichment. A unit with an incomplete address does not take part in that fallback, and no looser address guess is attempted, so a unit is never given the wrong certificate.

## Considered Options

**Drop VBOs that lack a postcode and huisnummer (the previous behaviour).** Rejected. It treated address completeness as a precondition for existence, deleting real units from a model whose purpose is dwelling-stock completeness. Dutch storage boxes and garages are registered verblijfsobjecten with a `verblijfsobject_id` but frequently no postcode, so the drop lost genuine units while the authoritative id that identifies them was available all along.

**Emit the unit but guess its label from a partial address.** Rejected for the matching step. A partial-address guess (postcode-only, or street-only) risks attaching the wrong certificate to a unit, which is worse than no certificate. The BAG-id match already covers every unit the register actually holds a label for.

**Require at least one address part before emitting.** Rejected. The `verblijfsobject_id`, not the address, is the unit's identity, so no address part is load-bearing for emission. Gating on "at least one part" would reintroduce the same class of silent loss for a smaller set of units.

## Consequences

The output can now contain `nrg3:BuildingUnit`s with a partial `bldg:address` or none. A consumer must read the `verblijfsobject_id` (the `nrg3:identifier` and the gml:id), not the address, as the unit's stable key, and must not assume every unit carries a full address. Such a unit may also carry no `nrg3:EnergyPerformanceCertificate`, which is correct, since a garage or storage box rarely has one.

Building geometry was never affected by the old drop, because the Pand was always emitted regardless. The change only restores the missing units inside it.

This supersedes the gating sense of the former "Matchable VBO" concept. The `(postcode, huisnummer)` predicate survives only as the EP-Online address-key fallback, not as a gate on emission or on the id match. The glossary entry is now "Address-key VBO" in `CONTEXT.md`.

Implementation: the city pipeline builds its EP-Online row filter and join from the full VBO-id set (every unit) plus the address keys of the address-key VBOs, so a label is fetched for any unit the register can match either by BAG id or by a full address.

## References

`citygml_energy/city_builder/address_match.py` (`match_addresses`, `wanted_label_filter`, and the address-key predicate), `citygml_energy/city_builder/builders/building.py` (`build_building_unit` emits the `verblijfsobject_id` `nrg3:identifier`, and the Pand emits its `pand_id`), the "Address-key VBO", "BuildingUnit", and "EP-Online" entries in `CONTEXT.md`, and ADR-0003 (the city-scale pipeline this rule applies to).
