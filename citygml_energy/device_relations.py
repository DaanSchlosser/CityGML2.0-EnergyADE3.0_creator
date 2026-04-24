"""Post-processor: emit ``nrg3:CityObjectRelation`` entries for devices.

Resolves JSON-declared ``installed_on`` references on devices (PV
collectors, heat pumps, etc.) into ``nrg3:CityObjectRelation`` links
with ``relationType="installedOn"`` pointing at specific surface
``gml:id`` values.

Two resolution strategies are tried in order:

1. Match against :attr:`CityModel.surface_name_index`, so author-facing
   STEP layer names (``"RoofSurface_01"``) keep working.
2. Fall back to the gml:id-keyed feature index, allowing JSON to cite
   any indexable ``gml:id`` directly.

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
)
from .core import CityModel
from .mapping import iter_instances
from .namespaces import CS_NRG3_RELATION_TYPE

__all__ = ["DEFAULT_INSTALLED_ON_RELATION", "apply_device_relations"]

DEFAULT_INSTALLED_ON_RELATION = "installedOn"


def apply_device_relations(
    model: CityModel,
    device_relations: dict[str, list[str]],
    *,
    relation_type: str = DEFAULT_INSTALLED_ON_RELATION,
) -> None:
    """Emit ``nrg3:CityObjectRelation`` entries from JSON-declared targets.

    *device_relations* maps a device's ``gml:id`` (e.g. ``"pv_panel_1"``)
    to a list of surface references. Each reference is first looked up in
    :attr:`CityModel.surface_name_index` (so author-facing STEP layer
    names like ``"RoofSurface_01"`` work), then falls back to the
    gml:id-keyed feature index, meaning JSON may cite any indexable
    ``gml:id`` directly too.

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
            target_gml_id = surface_name_index.get(target_ref) or (
                target_ref if target_ref in feature_index else None
            )
            if target_gml_id is None:
                known = ", ".join(sorted(surface_name_index)) or "(none attached yet)"
                raise ValueError(
                    f"apply_device_relations: target {target_ref!r} for "
                    f"{device_id!r} could not be resolved to any attached "
                    f"surface or indexed gml:id. Known STEP surface names: {known}"
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
    return AbstractCityObjectPropertyType(href=f"#{gml_id}")
