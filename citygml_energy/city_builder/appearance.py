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

from ..bindings import (
    AppearanceMember,
    CompositeSurface,
    MultiSurface,
    PhotovoltaicCollector,
    Polygon,
    SolitaryVegetationObject,
)
from ..mapping import get_fields, iter_instances, resolve_class
from ..schema_types import APPEARANCE, X3D_MATERIAL
from .address_match import ResolvedAddress
from .epc_score import LABEL_TO_KWH, average_labels, label_to_rgb

__all__ = [
    "ENERGY_LABEL_THEME",
    "PV_PANEL_DIFFUSE_COLOR",
    "PV_PANEL_THEME",
    "VEGETATION_DIFFUSE_COLOR",
    "VEGETATION_THEME",
    "append_energy_label_appearance",
    "append_pv_panel_appearance",
    "append_vegetation_appearance",
    "collect_surface_target_ids",
]


ENERGY_LABEL_THEME = "energyLabel"

# PV-panel appearance: "very dark blue, almost black". Darker than any
# EPC-palette blue, still readable as blue rather than pure black.
PV_PANEL_THEME = "pvPanels"
PV_PANEL_DIFFUSE_COLOR: tuple[float, float, float] = (0.03, 0.05, 0.15)

# Vegetation appearance: a deep foliage green that reads clearly against
# both the EU-palette building colors and the dark-blue PV panels. The
# specific RGB is chosen to match the KIT viewer's default background
# rather than a theoretically "correct" chlorophyll reflectance, because
# the pipeline's output is reviewed in FZKViewer / KIT SDM first.
VEGETATION_THEME = "vegetation"
VEGETATION_DIFFUSE_COLOR: tuple[float, float, float] = (0.15, 0.55, 0.15)


def collect_surface_target_ids(building: Any) -> list[str]:
    """Return ``#<gml:id>`` references for every colorable surface under *building*.

    Walks the xsdata tree with :func:`mapping.iter_instances` and picks
    up every :class:`MultiSurface`, :class:`CompositeSurface`, and
    :class:`Polygon` whose ``id`` is populated. All three are valid
    ``app:target`` types per the CityGML 2.0 Appearance XSD, and the
    per-polygon entries are what keeps the EPC color applied in viewers
    that do not resolve container-level targets.
    """
    return [
        f"#{obj.id}"
        for obj in iter_instances(building)
        if isinstance(obj, (MultiSurface, CompositeSurface, Polygon)) and obj.id
    ]


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


def append_pv_panel_appearance(city_model: Any) -> None:
    """Attach an ``app:Appearance`` that paints every PV panel dark blue.

    One ``app:X3DMaterial`` targets every ``gml:MultiSurface`` and
    ``gml:Polygon`` found under a :class:`PhotovoltaicCollector` in the
    model: the collector's ``lod2MultiSurface`` plus each of its
    polygons. Per-polygon targets are included for the same
    viewer-compatibility reason as the energy-label appearance (see
    :func:`collect_surface_target_ids`).

    The appearance lives under its own theme (``"pvPanels"``) so a
    viewer's theme switcher can toggle panels independently of the
    energy-label painting.

    A no-op when the model contains no PV collectors.
    """
    targets = _collect_pv_surface_target_ids(city_model)
    if not targets:
        return

    appearance_cls = resolve_class(APPEARANCE)
    material_cls = resolve_class(X3D_MATERIAL)
    surface_data_inner = _surface_data_property_type(appearance_cls)

    material = surface_data_inner(
        x3_dmaterial=material_cls(
            diffuse_color=list(PV_PANEL_DIFFUSE_COLOR),
            target=targets,
        )
    )
    appearance = appearance_cls(
        id=f"appearance_{PV_PANEL_THEME}",
        theme=PV_PANEL_THEME,
        surface_data_member=[material],
    )
    city_model.xsd.appearance_member.append(AppearanceMember(appearance=appearance))


def append_vegetation_appearance(
    city_model: Any,
    *,
    targets: list[str] | None = None,
) -> None:
    """Attach an ``app:Appearance`` that paints every tree foliage-green.

    *targets* is the list of ``#<gml:id>`` refs collected during tree
    attachment; the pipeline passes it explicitly so the appearance
    step does not re-walk the full xsdata tree a second time
    (mirroring how :func:`append_energy_label_appearance` consumes
    ``targets_by_gml_id`` from the per-pand build). When ``None`` is
    supplied (e.g., tests or future callers that construct an
    already-populated model), :func:`_collect_vegetation_surface_target_ids`
    falls back to a single ``iter_instances`` walk.

    Per-polygon targets accompany the container targets for the same
    viewer-compatibility reason as the energy-label appearance (see
    :func:`collect_surface_target_ids`): KIT SDM_KITModelViewer and its
    family silently skip appearance targets that point at an enclosing
    ``gml:MultiSurface``, so emitting both keeps the color applied in
    every viewer observed so far.

    The appearance lives under its own theme (``"vegetation"``) so the
    viewer's theme switcher can toggle it independently of building /
    PV painting.

    A no-op when the model contains no vegetation objects.
    """
    if targets is None:
        targets = _collect_vegetation_surface_target_ids(city_model)
    if not targets:
        return

    appearance_cls = resolve_class(APPEARANCE)
    material_cls = resolve_class(X3D_MATERIAL)
    surface_data_inner = _surface_data_property_type(appearance_cls)

    material = surface_data_inner(
        x3_dmaterial=material_cls(
            diffuse_color=list(VEGETATION_DIFFUSE_COLOR),
            target=targets,
        )
    )
    appearance = appearance_cls(
        id=f"appearance_{VEGETATION_THEME}",
        theme=VEGETATION_THEME,
        surface_data_member=[material],
    )
    city_model.xsd.appearance_member.append(AppearanceMember(appearance=appearance))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _collect_vegetation_surface_target_ids(city_model: Any) -> list[str]:
    """Return ``#<gml:id>`` refs for every colorable surface under a tree.

    Mirrors :func:`_collect_pv_surface_target_ids`. Yields one target
    per ``gml:MultiSurface`` container plus one per member
    ``gml:Polygon``, covering both viewers that resolve container
    targets and those that only resolve per-polygon targets.
    """
    root = getattr(city_model, "xsd", city_model)
    targets: list[str] = []
    for tree in iter_instances(root):
        if not isinstance(tree, SolitaryVegetationObject):
            continue
        targets.extend(
            f"#{sub.id}"
            for sub in iter_instances(tree)
            if isinstance(sub, (MultiSurface, Polygon)) and sub.id
        )
    return targets


def _collect_pv_surface_target_ids(city_model: Any) -> list[str]:
    """Return ``#<gml:id>`` refs for every colorable surface under a PV collector.

    Walks the underlying xsdata tree once (:func:`iter_instances` is
    cycle-safe and yields each dataclass node once), and for each
    :class:`PhotovoltaicCollector` descends into its subtree to pick up
    MultiSurface / Polygon ids. Re-using the per-collector subtree walk
    keeps the rule consistent with :func:`collect_surface_target_ids`
    and avoids collecting non-PV surfaces by accident.

    Accepts either the :class:`~citygml_energy.core.CityModel` wrapper or
    the raw xsdata ``CityModelType``: :class:`CityModel` is not a
    dataclass so :func:`iter_instances` will not descend into it; we
    unwrap to the ``.xsd`` attribute when present.
    """
    root = getattr(city_model, "xsd", city_model)
    targets: list[str] = []
    for pv in iter_instances(root):
        if not isinstance(pv, PhotovoltaicCollector):
            continue
        targets.extend(
            f"#{sub.id}"
            for sub in iter_instances(pv)
            if isinstance(sub, (MultiSurface, Polygon)) and sub.id
        )
    return targets


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
