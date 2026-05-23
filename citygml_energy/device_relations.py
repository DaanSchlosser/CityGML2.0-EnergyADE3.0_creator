"""Post-processor: emit ``nrg3:CityObjectRelation`` entries on CityObjects.

Resolves JSON-declared ``related_to`` entries on feature dicts into
``nrg3:CityObjectRelation`` links. Each entry carries an explicit
``relation`` value (an ``OtherRelationTypeValue`` codelist member such as
``installedOn`` or ``serving``) plus a ``target`` reference.

The JSON shape mirrors the EnergyADE 3.0 UML class structure 1:1: each
CityObject composes a list of CityObjectRelation instances, each carrying
one ``relationType`` value and one ``relatedTo`` xlink. There is no
per-relation-type subclass at the model level (``CityObjectRelation`` was
explicitly remodelled in EnergyADE 3.0 beta 4 to consolidate the previous
N parallel association classes into one polymorphic class discriminated
by ``relationType``); the input layer matches that shape.

The driver routes each entry through the relation registry
(:data:`RELATION_KINDS`). Each registered :class:`RelationKind` declares:

* its codelist value (the literal ``relation`` field value in JSON),
* the codespace URL that names the dictionary the value lives in
  (``OtherRelationTypeValue.xml`` for the three current values;
  ``TopologicalRelationTypeValue.xml`` for future ``adjacentTo`` /
  ``sharedWith``; ``TemporalRelationTypeValue.xml`` for any future
  temporal members),
* a target kind that selects the resolver path:

  - ``"surface"`` looks up STEP layer names against
    :attr:`CityModel.surface_name_index` (which is keyed by
    ``(name, LoD)``), collapses the LoD axis by picking the **highest LoD**
    present for that name, and falls back to the gml:id-keyed feature
    index when no STEP-name match is found. The bare-string form
    ``"RoofSurface_01"`` resolves under this path; the object form
    ``{"name": "RoofSurface_01", "lod": 2}`` pins the relation to one
    specific LoD's representation and does not fall back. ADR-0001
    locks this resolution semantic.
  - ``"feature"`` resolves only against the feature index; surface-name
    lookup is intentionally skipped so a typo against a STEP layer name
    raises rather than silently emitting a relation to a surface gml:id
    when none was intended. Only the bare-string shape is accepted in
    this mode (LoD has no meaning for a feature-id reference).

The highest-LoD default on ``surface`` targets is conservative: it does
not claim to match consumer intent in general, but minimises the risk of
pointing at an under-specified face when the author has not authored a
LoD signal. Authors who need a different LoD opt in explicitly via the
object form.

Unresolved references raise :class:`ValueError` loudly: silent no-op
would let JSON typos slip through as missing relations that nobody
notices until a downstream consumer complains.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .bindings import (
    AbstractCityObjectPropertyType,
    CityObjectRelation,
    CodeType,
    RelatedTo,
    TypeType,
)
from .core import CityModel
from .mapping import iter_instances
from .namespaces import CS_NRG3_OTHER_RELATION_TYPE

__all__ = [
    "DEFAULT_INSTALLED_ON_RELATION",
    "RELATION_KINDS",
    "RelationKind",
    "TargetKind",
    "apply_device_relations",
]

# Kept for back-compat with any caller that imports the constant; the
# canonical source for the value is now ``RELATION_KINDS["installedOn"]``.
DEFAULT_INSTALLED_ON_RELATION = "installedOn"

TargetKind = Literal["surface", "feature"]


@dataclass(frozen=True, slots=True)
class RelationKind:
    """One member of the ``RelationTypeValue`` codelist family.

    :attr:`codelist_value` is the literal token written into
    ``<nrg3:relationType>`` (and matched against the ``relation`` field of
    each JSON ``related_to`` entry). :attr:`codespace` names the dictionary
    the token lives in (one of ``OtherRelationTypeValue.xml``,
    ``TopologicalRelationTypeValue.xml``, ``TemporalRelationTypeValue.xml``).
    :attr:`target_kind` selects the resolver path; see the module docstring.
    """

    codelist_value: str
    codespace: str
    target_kind: TargetKind


RELATION_KINDS: dict[str, RelationKind] = {
    # OtherRelationTypeValue members (beta 8 populated).
    "installedOn": RelationKind(
        codelist_value="installedOn",
        codespace=CS_NRG3_OTHER_RELATION_TYPE,
        target_kind="surface",
    ),
    "serving": RelationKind(
        codelist_value="serving",
        codespace=CS_NRG3_OTHER_RELATION_TYPE,
        target_kind="feature",
    ),
    # ``connectedTo`` (third OtherRelationTypeValue member) is not yet
    # exercised by any fixture; uncomment the registry entry when a
    # device-to-device connection (e.g. heat pump → thermal storage) is
    # first authored. The target kind is ``feature`` because the target
    # is another device, not a surface.
    #
    # TopologicalRelationTypeValue members (``adjacentTo``, ``sharedWith``)
    # would slot in here when the pipeline starts authoring Pand-to-Pand
    # adjacency, both with ``target_kind="feature"`` and codespace
    # CS_NRG3_TOPOLOGICAL_RELATION_TYPE.
}


def apply_device_relations(
    model: CityModel,
    related_to_by_device: dict[str, list[tuple[str, Any]]],
) -> None:
    """Emit ``nrg3:CityObjectRelation`` entries from parsed ``related_to`` entries.

    *related_to_by_device* maps a device's ``gml:id`` (e.g. ``"pv_panel_1"``)
    to a list of ``(relation_name, target_ref)`` tuples in author order.
    ``relation_name`` must be a key in :data:`RELATION_KINDS`;
    ``target_ref`` is the raw JSON-side reference (bare string, or
    ``{"name": str, "lod": int}`` for surface targets).

    The emitted ``<nrg3:relatedTo>`` siblings preserve the input order of
    the source list — author order in the JSON `related_to` field maps 1:1
    to element order in the GML output. (CityGML 2.0 + EnergyADE 3.0 do
    not assign semantic meaning to the order; preserving it just keeps
    diffs stable.)

    Unresolved references raise :class:`ValueError` to fail loudly rather
    than emit a dangling xlink:href. Devices that are themselves
    unresolved also raise, because a silent no-op here would make typos
    in the JSON invisible until someone checks the GML by hand.
    """
    if not related_to_by_device:
        return

    feature_index = _index_features(model)
    surface_name_index = model.surface_name_index

    for device_id, entries in related_to_by_device.items():
        device = feature_index.get(device_id)
        if device is None:
            raise ValueError(
                f"apply_device_relations: device {device_id!r} not found in model; "
                f"'related_to' references an unknown feature id"
            )
        if not hasattr(device, "related_to"):
            raise ValueError(
                f"apply_device_relations: feature {device_id!r} "
                f"({type(device).__name__}) has no 'related_to' field; "
                f"the XSD does not permit ADE relations on this type"
            )

        for relation_name, target_ref in entries:
            kind = RELATION_KINDS.get(relation_name)
            if kind is None:
                known = ", ".join(sorted(RELATION_KINDS)) or "(no relations registered)"
                raise ValueError(
                    f"apply_device_relations: unknown relation {relation_name!r} on "
                    f"{device_id!r}. Known relations: {known}"
                )
            target_gml_id = _resolve_target(
                target_ref,
                surface_name_index,
                feature_index,
                device_id,
                kind=kind,
            )
            device.related_to.append(
                RelatedTo(
                    city_object_relation=CityObjectRelation(
                        relation_type=CodeType(
                            value=kind.codelist_value,
                            code_space=kind.codespace,
                        ),
                        related_to=_make_city_object_ref(target_gml_id),
                    ),
                )
            )


def _resolve_target(
    target_ref: Any,
    surface_name_index: dict[tuple[str, int], str],
    feature_index: dict[str, Any],
    device_id: str,
    *,
    kind: RelationKind,
) -> str:
    """Resolve one relation target entry to a ``gml:id``.

    ``target_kind="surface"`` (e.g. ``installedOn``): bare strings collapse
    the LoD axis by picking the highest LoD present for the name; fall
    back to the gml:id index when no STEP-name match is found. The object
    form ``{"name": str, "lod": int}`` looks up the exact ``(name, lod)``
    pair; no fallback. ADR-0001 documents the rationale.

    ``target_kind="feature"`` (e.g. ``serving``): only the bare-string
    shape is accepted. The string is treated as a plain gml:id reference
    and resolved against the feature index only; surface lookup is
    intentionally skipped so a typo against a STEP surface name raises
    rather than silently emitting an xlink to a surface gml:id.
    """
    if kind.target_kind == "feature":
        if not isinstance(target_ref, str):
            raise ValueError(
                f"apply_device_relations: 'related_to' entry for relation "
                f"{kind.codelist_value!r} on {device_id!r} must have a gml:id "
                f"string target; the {{'name': str, 'lod': int}} object form "
                f"is only valid for surface-targeted relations (e.g. "
                f"'installedOn'), got {target_ref!r}"
            )
        if target_ref in feature_index:
            return target_ref
        known_ids = ", ".join(sorted(feature_index)[:20]) or "(no indexed features)"
        suffix = "" if len(feature_index) <= 20 else f" (+{len(feature_index) - 20} more)"
        raise ValueError(
            f"apply_device_relations: target {target_ref!r} for relation "
            f"{kind.codelist_value!r} on {device_id!r} could not be resolved "
            f"against the feature index. Known gml:ids: {known_ids}{suffix}"
        )

    # target_kind == "surface"
    if isinstance(target_ref, str):
        name = target_ref
        matches = [
            (lod, gml_id)
            for (idx_name, lod), gml_id in surface_name_index.items()
            if idx_name == name
        ]
        if matches:
            matches.sort(key=lambda pair: pair[0])
            return matches[-1][1]
        if name in feature_index:
            return name
        known = _format_known_names(surface_name_index)
        raise ValueError(
            f"apply_device_relations: target {name!r} for relation "
            f"{kind.codelist_value!r} on {device_id!r} could not be resolved "
            f"to any attached surface or indexed gml:id. Known STEP surface "
            f"names: {known}"
        )

    if isinstance(target_ref, dict):
        name = target_ref.get("name")
        lod = target_ref.get("lod")
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"apply_device_relations: 'related_to' entry for relation "
                f"{kind.codelist_value!r} on {device_id!r} has target "
                f"{target_ref!r}; the {{'name': str, 'lod': int}} object form "
                f"requires 'name' to be a non-empty string"
            )
        if not isinstance(lod, int) or isinstance(lod, bool) or lod < 0:
            raise ValueError(
                f"apply_device_relations: 'related_to' entry for relation "
                f"{kind.codelist_value!r} on {device_id!r} has target "
                f"{target_ref!r}; the {{'name': str, 'lod': int}} object form "
                f"requires 'lod' to be a non-negative integer"
            )
        gml_id = surface_name_index.get((name, lod))
        if gml_id is not None:
            return gml_id
        known_lods = sorted(
            {idx_lod for (idx_name, idx_lod) in surface_name_index if idx_name == name}
        )
        if known_lods:
            raise ValueError(
                f"apply_device_relations: target {{'name': {name!r}, 'lod': {lod}}} "
                f"for relation {kind.codelist_value!r} on {device_id!r} is not "
                f"attached at LoD {lod}. The name resolves at LoDs {known_lods}; "
                f"pin the object form to one of those, or drop the lod key for "
                f"the highest-LoD default."
            )
        known = _format_known_names(surface_name_index)
        raise ValueError(
            f"apply_device_relations: target {{'name': {name!r}, 'lod': {lod}}} "
            f"for relation {kind.codelist_value!r} on {device_id!r} could not be "
            f"resolved; the name does not appear in the surface index at any "
            f"LoD. Known STEP surface names: {known}"
        )

    raise ValueError(
        f"apply_device_relations: 'related_to' entry target for relation "
        f"{kind.codelist_value!r} on {device_id!r} must be a string (bare STEP "
        f"layer name or gml:id) or an object {{'name': str, 'lod': int}} for "
        f"surface targets; got {type(target_ref).__name__}"
    )


def _format_known_names(surface_name_index: dict[tuple[str, int], str]) -> str:
    """Render the index as a sorted ``name@lodN`` list for error messages."""
    if not surface_name_index:
        return "(none attached yet)"
    return ", ".join(
        f"{name}@lod{lod}" for (name, lod) in sorted(surface_name_index)
    )


# ---------------------------------------------------------------------------
# Internal helpers shared with the geometry-source pipeline.
#
# ``_index_features`` also serves :func:`geometry.apply_geometry_sources`;
# it lives here (with ``device_relations`` as its primary caller) so that
# the geometry module can import it without pulling any
# construction-mapping state. A one-line import is cheaper than making
# every concern depend on a neutral ``_shared`` helper module.
# ---------------------------------------------------------------------------


def _index_features(model: CityModel) -> dict[str, Any]:
    """Build ``{gml:id -> object}`` for every indexable feature under *model*.

    Walks the whole dataclass tree via :func:`iter_instances` so nested
    features (device under Building, ZonePart under Zone, ...) are all
    indexed, not just the top-level ``city_object_member`` entries.
    """
    index: dict[str, Any] = {}
    for obj in iter_instances(model.xsd):
        gml_id = getattr(obj, "id", None)
        if isinstance(gml_id, str) and gml_id:
            # First occurrence wins. XSD requires ids to be unique, so
            # collisions would surface at serialization; we don't second-guess
            # the input here.
            index.setdefault(gml_id, obj)
    return index


def _make_city_object_ref(gml_id: str) -> AbstractCityObjectPropertyType:
    ref = AbstractCityObjectPropertyType(href=f"#{gml_id}")
    ref.type_value = TypeType.SIMPLE
    return ref
