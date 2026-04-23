"""CityGML Appearance builder: paints buildings by averaged EPC label.

Produces a single ``app:Appearance`` (theme ``"energyLabel"``) attached
to the :class:`CityModel` via ``app:appearanceMember``. The appearance
carries one ``app:X3DMaterial`` per EU-palette color that appears in
the city: every building's surfaces are grouped by the averaged EPC
letter, and each group becomes the ``<app:target>`` list of one
material. Buildings without any energy label are colored grey (the
fallback for :func:`epc_score.label_to_rgb`).

Targeting rule: we target every ``gml:MultiSurface``, ``gml:CompositeSurface``
and ``gml:Polygon`` id found under each building:

* LoD 0 → the ``gml:MultiSurface`` inside ``bldg:lod0FootPrint`` plus each
  of its member ``gml:Polygon`` elements.
* LoD 1 → the ``gml:CompositeSurface`` shell inside ``bldg:lod1Solid``
  plus each of its member ``gml:Polygon`` elements.
* LoD 2 → the ``gml:MultiSurface`` inside each thematic surface's
  ``bldg:lod2MultiSurface`` plus each of its member ``gml:Polygon``
  elements.

The CityGML 2.0 Appearance XSD annotates ``app:target`` as accepting
"gml:MultiSurface or descendants of gml:AbstractSurfaceType"; all three
targeted classes satisfy that constraint. Individual ``gml:Polygon``
targets are included in addition to the containers because some
viewers (KIT SDM_KITModelViewer observed, and its family of viewers)
only resolve appearance targets that point at individual polygons and
silently skip targets that point at an enclosing ``gml:MultiSurface``
or ``gml:CompositeSurface`` that lives directly under
``bldg:lod0FootPrint`` or ``bldg:lod1Solid`` (i.e. outside a thematic
boundary surface). Emitting both keeps the file readable and makes the
color apply in every viewer observed so far.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from ..bindings import AppearanceMember, CompositeSurface, MultiSurface, Polygon
from ..mapping import get_fields, iter_instances, resolve_class
from ..schema_types import APPEARANCE, X3D_MATERIAL
from .address_match import ResolvedAddress
from .epc_score import LABEL_TO_KWH, average_labels, label_to_rgb

__all__ = [
    "ENERGY_LABEL_THEME",
    "append_energy_label_appearance",
    "collect_surface_target_ids",
]


ENERGY_LABEL_THEME = "energyLabel"


def collect_surface_target_ids(building: Any) -> list[str]:
    """Return ``#<gml:id>`` references for every colorable surface under *building*.

    Walks the xsdata tree with :func:`mapping.iter_instances` and picks
    up every :class:`MultiSurface`, :class:`CompositeSurface`, and
    :class:`Polygon` whose ``id`` is populated. All three are valid
    ``app:target`` types per the CityGML 2.0 Appearance XSD, and the
    per-polygon entries are what keeps the EPC color applied in viewers
    that do not resolve container-level targets.
    """
    targets: list[str] = []
    for obj in iter_instances(building):
        if isinstance(obj, (MultiSurface, CompositeSurface, Polygon)) and obj.id:
            targets.append(f"#{obj.id}")
    return targets


def append_energy_label_appearance(
    city_model: Any,
    building_label_pairs: list[tuple[Any, list[ResolvedAddress]]],
    *,
    targets_by_gml_id: dict[str, list[str]] | None = None,
) -> None:
    """Attach one ``app:Appearance`` grouping *buildings* by averaged EPC color.

    *building_label_pairs* is the list of ``(building, resolved_addresses)``
    tuples that were added to *city_model*. For each building, the EPC
    letters of its VBOs are averaged via :func:`epc_score.average_labels`;
    the resulting letter drives the building's color. Buildings without
    any matched label render grey.

    *targets_by_gml_id* lets callers hand in the colorable surface ids
    they already collected while building each object (keyed by
    ``building.id``). When present, the dict is consulted first and we
    skip the :func:`iter_instances` walk entirely. Callers that do not
    pre-collect (e.g. most tests) pass ``None`` and the walking path
    is used.

    A no-op when there are no buildings or no colorable surfaces.
    """
    if not building_label_pairs:
        return

    # Group surface-id targets by the averaged letter (None = unknown).
    targets_by_letter: dict[str | None, list[str]] = {}
    for building, resolved in building_label_pairs:
        surface_targets = _resolve_surface_targets(building, targets_by_gml_id)
        if not surface_targets:
            continue
        letter = average_labels(
            r.energy_label.energieklasse for r in resolved if r.energy_label is not None
        )
        targets_by_letter.setdefault(letter, []).extend(surface_targets)

    if not targets_by_letter:
        return

    appearance_cls = resolve_class(APPEARANCE)
    material_cls = resolve_class(X3D_MATERIAL)
    surface_data_inner = _surface_data_property_type(appearance_cls)

    materials = [
        surface_data_inner(
            x3_dmaterial=material_cls(
                diffuse_color=list(label_to_rgb(letter)),
                target=targets,
            )
        )
        for letter, targets in _sorted_letters(targets_by_letter)
    ]

    appearance = appearance_cls(
        id=f"appearance_{ENERGY_LABEL_THEME}",
        theme=ENERGY_LABEL_THEME,
        surface_data_member=materials,
    )
    city_model.xsd.appearance_member.append(AppearanceMember(appearance=appearance))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_surface_targets(
    building: Any,
    targets_by_gml_id: dict[str, list[str]] | None,
) -> list[str]:
    """Return pre-collected appearance targets when available, else walk.

    Looking ``building.id`` up in the pipeline-supplied dict costs O(1)
    and skips the :func:`iter_instances` traversal that
    :func:`collect_surface_target_ids` would otherwise run per building.
    The walking path remains the fallback for callers (mainly tests)
    that construct buildings without tracking ids.
    """
    if targets_by_gml_id is not None:
        gml_id = getattr(building, "id", None)
        if gml_id is not None and gml_id in targets_by_gml_id:
            return targets_by_gml_id[gml_id]
    return collect_surface_target_ids(building)


@cache
def _surface_data_property_type(appearance_cls: type) -> type:
    """Resolve the inner class of ``AppearanceType.surface_data_member``.

    We introspect the field rather than import ``SurfaceDataPropertyType``
    directly so xsdata bindings regenerations that rename the property
    type don't silently break this module: the single failure path is
    a clear field-lookup error at call time. Cached because the answer
    is a pure function of the binding class.
    """
    info = get_fields(appearance_cls).get("surface_data_member")
    if info is None or not isinstance(info.inner_type, type):
        raise RuntimeError(
            "AppearanceType has no 'surface_data_member' list field; "
            "bindings may have been regenerated against a different XSD."
        )
    return info.inner_type


_LETTER_ORDER_INDEX: dict[str, int] = {letter: i for i, letter in enumerate(LABEL_TO_KWH)}


def _sorted_letters(
    by_letter: dict[str | None, list[str]],
) -> list[tuple[str | None, list[str]]]:
    """Deterministic ordering: known letters best to worst, unknown last."""
    return sorted(
        by_letter.items(),
        key=lambda kv: (1, 0) if kv[0] is None else (0, _LETTER_ORDER_INDEX.get(kv[0], 999)),
    )
