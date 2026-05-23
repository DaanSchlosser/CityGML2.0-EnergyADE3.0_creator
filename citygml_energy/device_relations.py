"""Post-processor: emit ``nrg3:CityObjectRelation`` entries for devices.

Resolves JSON-declared ``installed_on`` references on devices (PV
collectors, heat pumps, etc.) into ``nrg3:CityObjectRelation`` links
with ``relationType="installedOn"`` pointing at specific surface
``gml:id`` values.

Each ``installed_on`` entry can take one of two shapes:

* **Bare string** like ``"RoofSurface_01"``. The resolver looks up the
  STEP layer name in :attr:`CityModel.surface_name_index` (which is
  keyed by ``(name, LoD)``), collapses the LoD axis by picking the
  **highest LoD** present for that name, and falls back to the
  gml:id-keyed feature index when no STEP-name match is found.
* **Object form** like ``{"name": "RoofSurface_01", "lod": 2}``. The
  resolver looks up the exact ``(name, LoD)`` pair and emits a relation
  to that specific LoD's representation. No fallback to gml:id; the
  object form is unambiguous and a missing match is an error.

The highest-LoD default is chosen because it is the dominant consumer
intent: an analysis that wants the area or azimuth of the face a
device sits on will want the most-detailed representation of that
face. Authors who need to target a different LoD opt in explicitly
via the object form.

Unresolved references raise :class:`ValueError` loudly: silent no-op
would let JSON typos slip through as missing relations that nobody
notices until a downstream consumer complains.
"""

from __future__ import annotations

from typing import Any

from .bindings import (
    AbstractCityObjectPropertyType,
    CityObjectRelation,
    CodeType,
    RelatedTo,
    TypeType,
)
from .core import CityModel
from .mapping import iter_instances
from .namespaces import CS_NRG3_RELATION_TYPE

__all__ = ["DEFAULT_INSTALLED_ON_RELATION", "apply_device_relations"]

DEFAULT_INSTALLED_ON_RELATION = "installedOn"


def apply_device_relations(
    model: CityModel,
    device_relations: dict[str, list[Any]],
    *,
    relation_type: str = DEFAULT_INSTALLED_ON_RELATION,
) -> None:
    """Emit ``nrg3:CityObjectRelation`` entries from JSON-declared targets.

    *device_relations* maps a device's ``gml:id`` (e.g. ``"pv_panel_1"``)
    to a list of surface references. Each reference is either a bare
    STEP layer name (string) or an object form ``{"name": str, "lod": int}``.
    See the module docstring for the resolution rules.

    Unresolved references raise :class:`ValueError` to fail loudly rather
    than emit a dangling xlink:href. Devices that are themselves
    unresolved also raise, because a silent no-op here would make typos
    in the JSON invisible until someone checks the GML by hand.

    The default *relation_type* is ``installedOn`` (the EnergyADE 3.0
    codelist value for device-on-surface placement); callers needing
    other relation semantics pass a different code.
    """
    if not device_relations:
        return

    feature_index = _index_features(model)
    surface_name_index = model.surface_name_index

    for device_id, targets in device_relations.items():
        device = feature_index.get(device_id)
        if device is None:
            raise ValueError(
                f"apply_device_relations: device {device_id!r} not found in model; "
                f"installed_on references an unknown feature id"
            )
        if not hasattr(device, "related_to"):
            raise ValueError(
                f"apply_device_relations: feature {device_id!r} "
                f"({type(device).__name__}) has no 'related_to' field; "
                f"the XSD does not permit ADE relations on this type"
            )

        for target_ref in targets:
            target_gml_id = _resolve_target(
                target_ref, surface_name_index, feature_index, device_id
            )
            device.related_to.append(
                RelatedTo(
                    city_object_relation=CityObjectRelation(
                        relation_type=CodeType(
                            value=relation_type,
                            code_space=CS_NRG3_RELATION_TYPE,
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
) -> str:
    """Resolve one ``installed_on`` entry to a surface ``gml:id``.

    Bare strings: collapse the LoD axis by picking the highest LoD
    present for the name; fall back to the gml:id index when no
    STEP-name match is found.

    Object form: look up the exact ``(name, lod)`` pair; no fallback.
    """
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
            f"apply_device_relations: target {name!r} for {device_id!r} "
            f"could not be resolved to any attached surface or indexed "
            f"gml:id. Known STEP surface names: {known}"
        )

    if isinstance(target_ref, dict):
        name = target_ref.get("name")
        lod = target_ref.get("lod")
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"apply_device_relations: installed_on entry {target_ref!r} on "
                f"{device_id!r} must be {{'name': str, 'lod': int}} but 'name' "
                f"is missing or not a non-empty string"
            )
        if not isinstance(lod, int) or isinstance(lod, bool) or lod < 0:
            raise ValueError(
                f"apply_device_relations: installed_on entry {target_ref!r} on "
                f"{device_id!r} must be {{'name': str, 'lod': int}} but 'lod' "
                f"is missing or not a non-negative integer"
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
                f"for {device_id!r} is not attached at LoD {lod}. The name "
                f"resolves at LoDs {known_lods}; pin the object form to one of "
                f"those, or drop the lod key for the highest-LoD default."
            )
        known = _format_known_names(surface_name_index)
        raise ValueError(
            f"apply_device_relations: target {{'name': {name!r}, 'lod': {lod}}} "
            f"for {device_id!r} could not be resolved; the name does not "
            f"appear in the surface index at any LoD. Known STEP surface "
            f"names: {known}"
        )

    raise ValueError(
        f"apply_device_relations: installed_on entry {target_ref!r} on "
        f"{device_id!r} must be a string (bare STEP layer name) or an "
        f"object {{'name': str, 'lod': int}}; got {type(target_ref).__name__}"
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
