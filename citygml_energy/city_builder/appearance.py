"""CityGML Appearance builders: one ``app:Appearance`` per visual theme.

The module emits up to four independent appearances on the same
:class:`CityModel`, each attached via ``app:appearanceMember`` and
each carrying its own ``app:theme`` so a viewer's theme switcher can
toggle them in isolation:

* :func:`append_energy_label_appearance` (theme ``"energyLabel"``) —
  paints every building's surfaces by averaged EPC label, with one
  ``app:X3DMaterial`` per EU-palette color (grey fallback for
  buildings without a matched label, via
  :func:`epc_score.label_to_rgb`).
* :func:`append_solar_panel_appearance` (theme ``"solarPanels"``) — paints
  every solar collector (``nrg3:GenericSolarCollector``) dark blue.
* :func:`append_vegetation_appearance` (theme ``"vegetation"``) —
  paints every solitary-vegetation object foliage-green and slightly
  transparent, so a canopy does not fully occlude what is behind it.
* :func:`append_landcover_appearance` (theme ``"landcover"``) — paints
  the 3D Basisvoorziening ground by CityGML feature class (terrain,
  road, water, plant cover, bridge, generic) from a natural map palette,
  one ``app:X3DMaterial`` per class present.

Solar collectors and vegetation share the same shape (one color, one theme, one
material over a set of targets) and route through
:func:`_append_uniform_appearance`; the energy-label, building-highlight, and
landcover painters paint several target sets in different colors under one
theme and route through :func:`_append_multi_material_appearance` (the
energy-label painter groups by averaged letter before doing so).

Targeting rule (used by every theme): we target the outermost surface
aggregate of each colorable geometry and let the color propagate to its
members. The CityGML 2.0 Appearance model defines an appearance on an
aggregate or composite geometry as valid for all of its member surfaces,
so a single container target colors every child polygon. The EnergyADE
3.0 Alderaan reference data follows the same convention: its
``app:X3DMaterial`` targets list only ``MultiSurf_lodN`` containers,
never the member polygons. For buildings:

* LoD 0 targets the ``gml:MultiSurface`` inside ``bldg:lod0FootPrint``.
* LoD 1 targets the ``gml:CompositeSurface`` shell inside
  ``bldg:lod1Solid``.
* LoD 2 targets the ``gml:MultiSurface`` inside each thematic surface's
  ``bldg:lod2MultiSurface``.

The CityGML 2.0 Appearance XSD annotates ``app:target`` as accepting
"gml:MultiSurface or descendants of gml:AbstractSurfaceType", and all
targeted classes satisfy that constraint. We do not target the
``gml:Solid`` of ``bldg:lod1Solid`` directly: a solid is not a surface
type and so is not a valid ``app:target``, which is why the LoD 1 target
is the solid's ``gml:CompositeSurface`` shell.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from ..bindings import (
    AppearanceMember,
    CompositeSurface,
    GenericSolarCollector,
    MultiSurface,
    SolitaryVegetationObject,
)
from ..mapping import get_fields, iter_instances, resolve_class
from ..schema_types import (
    APPEARANCE,
    BRIDGE,
    GENERIC_CITY_OBJECT,
    LAND_USE,
    PLANT_COVER,
    ROAD,
    WATER_BODY,
    X3D_MATERIAL,
)
from .address_match import ResolvedAddress
from .epc_score import LABEL_TO_KWH, average_labels, label_to_rgb
from .landcover_class import LANDCOVER_FEATURE_QNAMES

__all__ = [
    "BUILDING_HIGHLIGHT_THEME",
    "ENERGY_LABEL_THEME",
    "LANDCOVER_BRIDGE_DIFFUSE_COLOR",
    "LANDCOVER_GENERIC_DIFFUSE_COLOR",
    "LANDCOVER_PLANT_DIFFUSE_COLOR",
    "LANDCOVER_ROAD_DIFFUSE_COLOR",
    "LANDCOVER_TERRAIN_DIFFUSE_COLOR",
    "LANDCOVER_THEME",
    "LANDCOVER_WATER_DIFFUSE_COLOR",
    "SOLAR_PANEL_DIFFUSE_COLOR",
    "SOLAR_PANEL_THEME",
    "SURROUNDINGS_DIFFUSE_COLOR",
    "TARGET_BUILDING_DIFFUSE_COLOR",
    "VEGETATION_DIFFUSE_COLOR",
    "VEGETATION_THEME",
    "VEGETATION_TRANSPARENCY",
    "append_building_highlight_appearance",
    "append_energy_label_appearance",
    "append_landcover_appearance",
    "append_solar_panel_appearance",
    "append_vegetation_appearance",
    "collect_surface_target_ids",
    "count_landcover_members",
]


ENERGY_LABEL_THEME = "energyLabel"

# Building-highlight appearance: paints the buildings a query singled out
# in a light yellow-orange and everything around them white, so the
# subject of an address-driven extract reads at a glance against its
# context. Lives under its own theme so a viewer can toggle it apart from
# the energy-label painting.
BUILDING_HIGHLIGHT_THEME = "buildingHighlight"
TARGET_BUILDING_DIFFUSE_COLOR: tuple[float, float, float] = (0.98, 0.78, 0.42)
SURROUNDINGS_DIFFUSE_COLOR: tuple[float, float, float] = (1.0, 1.0, 1.0)

# Solar-panel appearance: "very dark blue, almost black". Darker than any
# EPC-palette blue, still readable as blue rather than pure black.
SOLAR_PANEL_THEME = "solarPanels"
SOLAR_PANEL_DIFFUSE_COLOR: tuple[float, float, float] = (0.03, 0.05, 0.15)

# Vegetation appearance: a deep foliage green that reads clearly against
# both the EU-palette building colors and the dark-blue solar panels.
VEGETATION_THEME = "vegetation"
VEGETATION_DIFFUSE_COLOR: tuple[float, float, float] = (0.15, 0.55, 0.15)
# Trees render slightly see-through so a viewer can read the buildings, terrain,
# and other trees behind a canopy rather than having it fully occlude them. 0.0
# is opaque and 1.0 fully transparent; ~0.3 reads as lightly transparent.
VEGETATION_TRANSPARENCY: float = 0.3

# Landcover appearance: a natural map palette, one diffuse color per CityGML
# feature class the 3D Basisvoorziening ground produces (terrain a grassed tan,
# road asphalt grey, water steel blue, plant cover grass green, bridge warm
# concrete, and the generic fallback a neutral grey), so the ground reads like a
# basemap. One theme groups them, so a viewer toggles the whole layer at once.
LANDCOVER_THEME = "landcover"
LANDCOVER_TERRAIN_DIFFUSE_COLOR: tuple[float, float, float] = (0.76, 0.70, 0.50)
LANDCOVER_ROAD_DIFFUSE_COLOR: tuple[float, float, float] = (0.55, 0.55, 0.55)
LANDCOVER_WATER_DIFFUSE_COLOR: tuple[float, float, float] = (0.27, 0.51, 0.71)
LANDCOVER_PLANT_DIFFUSE_COLOR: tuple[float, float, float] = (0.45, 0.70, 0.30)
LANDCOVER_BRIDGE_DIFFUSE_COLOR: tuple[float, float, float] = (0.62, 0.60, 0.56)
LANDCOVER_GENERIC_DIFFUSE_COLOR: tuple[float, float, float] = (0.70, 0.70, 0.72)


def collect_surface_target_ids(building: Any) -> list[str]:
    """Return ``#<gml:id>`` references for every colorable surface container under *building*.

    Walks the xsdata tree with :func:`mapping.iter_instances` and picks
    up every :class:`MultiSurface` and :class:`CompositeSurface` whose
    ``id`` is populated: the LoD 0 footprint MultiSurface, the LoD 1
    CompositeSurface shell, and each LoD 2 thematic surface's
    MultiSurface. The color propagates from each container to its member
    polygons per the CityGML 2.0 Appearance model, so the member
    ``gml:Polygon`` ids are deliberately not targeted, which matches the
    Alderaan reference data (its targets list only containers).
    """
    return [
        f"#{obj.id}"
        for obj in iter_instances(building)
        if isinstance(obj, (MultiSurface, CompositeSurface)) and obj.id
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

    materials = [
        (label_to_rgb(letter), targets) for letter, targets in _sorted_letters(targets_by_letter)
    ]
    _append_multi_material_appearance(city_model, theme=ENERGY_LABEL_THEME, materials=materials)


def append_solar_panel_appearance(city_model: Any) -> None:
    """Attach an ``app:Appearance`` that paints every solar panel dark blue.

    One ``app:X3DMaterial`` targets the ``gml:MultiSurface`` of each
    :class:`GenericSolarCollector`'s ``lod2MultiSurface`` in the model.
    The material propagates from that container to its member polygons
    per the CityGML 2.0 Appearance model, so the polygons are not
    targeted individually (see :func:`collect_surface_target_ids`).

    The appearance lives under its own theme (``"solarPanels"``) so a
    viewer's theme switcher can toggle panels independently of the
    energy-label painting. The theme name is retained for source-data
    continuity (the GeoPackage layer is named ``solar_panels``) even
    though the XSD type the city pipeline emits is the
    technology-agnostic ``nrg3:GenericSolarCollector``.

    A no-op when the model contains no solar collectors.
    """
    targets = _collect_per_feature_targets(city_model, GenericSolarCollector)
    _append_uniform_appearance(
        city_model,
        theme=SOLAR_PANEL_THEME,
        diffuse_color=SOLAR_PANEL_DIFFUSE_COLOR,
        targets=targets,
    )


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
    already-populated model), :func:`_collect_per_feature_targets`
    falls back to a single ``iter_instances`` walk filtered to
    :class:`SolitaryVegetationObject`.

    Only the container ``gml:MultiSurface`` of each tree is targeted; the
    color propagates to its member polygons per the CityGML 2.0
    Appearance model (see :func:`collect_surface_target_ids`), matching
    the Alderaan reference convention.

    The appearance lives under its own theme (``"vegetation"``) so the
    viewer's theme switcher can toggle it independently of building /
    solar-collector painting.

    A no-op when the model contains no vegetation objects.
    """
    if targets is None:
        targets = _collect_per_feature_targets(city_model, SolitaryVegetationObject)
    _append_uniform_appearance(
        city_model,
        theme=VEGETATION_THEME,
        diffuse_color=VEGETATION_DIFFUSE_COLOR,
        targets=targets,
        transparency=VEGETATION_TRANSPARENCY,
    )


def append_building_highlight_appearance(
    city_model: Any,
    *,
    target_surface_ids: list[str],
    surrounding_surface_ids: list[str],
    target_color: tuple[float, float, float] = TARGET_BUILDING_DIFFUSE_COLOR,
    surroundings_color: tuple[float, float, float] = SURROUNDINGS_DIFFUSE_COLOR,
) -> None:
    """Attach one ``app:Appearance`` that contrasts target buildings with their surroundings.

    *target_surface_ids* and *surrounding_surface_ids* are the
    ``#<gml:id>`` surface-container refs collected during the per-pand
    build (the same ids :func:`collect_surface_target_ids` produces),
    partitioned by whether the building is one the run singled out. The
    appearance carries up to two ``app:X3DMaterial`` entries, the
    surroundings color and the target color, under a single
    ``"buildingHighlight"`` theme so a viewer toggles the whole contrast
    at once.

    A no-op when neither set has any targets.
    """
    materials: list[tuple[tuple[float, float, float], list[str]]] = []
    if surrounding_surface_ids:
        materials.append((surroundings_color, surrounding_surface_ids))
    if target_surface_ids:
        materials.append((target_color, target_surface_ids))
    _append_multi_material_appearance(
        city_model, theme=BUILDING_HIGHLIGHT_THEME, materials=materials
    )


def append_landcover_appearance(city_model: Any) -> None:
    """Attach one ``app:Appearance`` painting the 3DBV ground by feature class.

    Walks the assembled model once and buckets each landcover feature's
    ``gml:MultiSurface`` container id by its CityGML class, then emits one
    ``app:X3DMaterial`` per class present (terrain, road, water, plant cover,
    bridge, and the generic fallback) under a single ``"landcover"`` theme so a
    viewer toggles the whole ground layer together. The color propagates from
    each container to its member polygons per the CityGML 2.0 Appearance model,
    so polygons are not targeted individually (see
    :func:`collect_surface_target_ids`).

    A no-op when the model holds no landcover features.
    """
    targets_by_class = _collect_landcover_targets(city_model)
    materials = [
        (color, targets_by_class[feature_cls])
        for feature_cls, color in _LANDCOVER_PALETTE
        if targets_by_class.get(feature_cls)
    ]
    _append_multi_material_appearance(city_model, theme=LANDCOVER_THEME, materials=materials)


def count_landcover_members(city_model: Any) -> int:
    """Return how many 3DBV landcover features the model holds.

    Counts every instance of a landcover palette class in the assembled model,
    so the pipeline's done-line stays in step with the taxonomy without
    re-listing the feature classes (the membership comes from
    :data:`~citygml_energy.city_builder.landcover_class.LANDCOVER_FEATURE_QNAMES`,
    resolved into the palette). One ``iter_instances`` walk, O(model), like the
    painters; landcover features are top-level ``core:cityObjectMember``
    features, so their own member surfaces are never miscounted.
    """
    root = getattr(city_model, "xsd", city_model)
    return sum(1 for inst in iter_instances(root) if isinstance(inst, _LANDCOVER_CLASSES))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _collect_per_feature_targets(city_model: Any, feature_cls: type) -> list[str]:
    """Return ``#<gml:id>`` refs for every colorable surface under instances of *feature_cls*.

    Walks the underlying xsdata tree once (:func:`iter_instances` is
    cycle-safe and yields each dataclass node once); for each instance
    of *feature_cls*, descends into its subtree to pick up
    ``gml:MultiSurface`` container ids. The color propagates from each
    container to its member polygons, so the polygons are not targeted
    individually. Used by the solar-panel
    (:class:`GenericSolarCollector`) and vegetation
    (:class:`SolitaryVegetationObject`) painters; the energy-label
    painter walks the per-Building subtree via
    :func:`collect_surface_target_ids` instead because each building
    needs its own per-letter grouping.

    Accepts either the :class:`~citygml_energy.core.CityModel` wrapper
    or the raw xsdata ``CityModelType``: :class:`CityModel` is not a
    dataclass so :func:`iter_instances` will not descend into it; we
    unwrap to the ``.xsd`` attribute when present.
    """
    root = getattr(city_model, "xsd", city_model)
    targets: list[str] = []
    for feat in iter_instances(root):
        if not isinstance(feat, feature_cls):
            continue
        targets.extend(
            f"#{sub.id}" for sub in iter_instances(feat) if isinstance(sub, MultiSurface) and sub.id
        )
    return targets


def _append_uniform_appearance(
    city_model: Any,
    *,
    theme: str,
    diffuse_color: tuple[float, float, float],
    targets: list[str],
    transparency: float | None = None,
) -> None:
    """Append an ``app:Appearance`` with one ``app:X3DMaterial`` painting *targets* in *diffuse_color*.

    Used by the solar-collector and vegetation painters: both want exactly one
    color over one set of targets, distinguished only by theme (and, for
    vegetation, an optional *transparency*). The multi-color painters
    (energy-label, building-highlight, landcover) route through
    :func:`_append_multi_material_appearance` instead.

    A no-op when *targets* is empty so the GML stays free of empty
    Appearances on models that have no features of the relevant kind.
    """
    if not targets:
        return
    _append_multi_material_appearance(
        city_model,
        theme=theme,
        materials=[(diffuse_color, targets)],
        transparency=transparency,
    )


def _append_multi_material_appearance(
    city_model: Any,
    *,
    theme: str,
    materials: list[tuple[tuple[float, float, float], list[str]]],
    transparency: float | None = None,
) -> None:
    """Append one ``app:Appearance`` with one ``app:X3DMaterial`` per (color, targets) pair.

    Shared by every painter that puts several disjoint target sets in different
    colors under a single theme (energy-label, building-highlight, landcover)
    and, with a single pair, by the uniform solar/vegetation painter. The
    optional *transparency* (0.0 opaque to 1.0 fully transparent) applies to
    every material in the appearance.

    A no-op when *materials* is empty, so the GML stays free of empty
    Appearances on models that have no features of the relevant kind.
    """
    if not materials:
        return

    appearance_cls = resolve_class(APPEARANCE)
    material_cls = resolve_class(X3D_MATERIAL)
    surface_data_inner = _surface_data_property_type(appearance_cls)

    surface_data = [
        surface_data_inner(
            x3_dmaterial=material_cls(
                diffuse_color=list(color),
                transparency=transparency,
                target=targets,
            )
        )
        for color, targets in materials
    ]
    appearance = appearance_cls(
        id=f"appearance_{theme}",
        theme=theme,
        surface_data_member=surface_data,
    )
    city_model.xsd.appearance_member.append(AppearanceMember(appearance=appearance))


# 3DBV-derived feature qname -> diffuse color. The membership and paint order of
# the landcover layer live once in landcover_class.LANDCOVER_FEATURE_QNAMES; this
# map only attaches a color to each qname, so a new taxonomy row needs a color
# here and nothing else (test_city_landcover guards that every qname has one).
_LANDCOVER_COLOR_BY_QNAME: dict[str, tuple[float, float, float]] = {
    LAND_USE: LANDCOVER_TERRAIN_DIFFUSE_COLOR,
    ROAD: LANDCOVER_ROAD_DIFFUSE_COLOR,
    WATER_BODY: LANDCOVER_WATER_DIFFUSE_COLOR,
    PLANT_COVER: LANDCOVER_PLANT_DIFFUSE_COLOR,
    BRIDGE: LANDCOVER_BRIDGE_DIFFUSE_COLOR,
    GENERIC_CITY_OBJECT: LANDCOVER_GENERIC_DIFFUSE_COLOR,
}

# (binding class, diffuse color) in paint order, derived from the taxonomy so the
# palette can never enumerate a different class set than the classifier emits.
# resolve_class maps each qname to its xsdata binding class (the same classes the
# landcover builder constructs).
_LANDCOVER_PALETTE: tuple[tuple[type, tuple[float, float, float]], ...] = tuple(
    (resolve_class(qname), _LANDCOVER_COLOR_BY_QNAME[qname]) for qname in LANDCOVER_FEATURE_QNAMES
)
_LANDCOVER_CLASSES: tuple[type, ...] = tuple(cls for cls, _ in _LANDCOVER_PALETTE)


def _collect_landcover_targets(city_model: Any) -> dict[type, list[str]]:
    """Bucket every landcover feature's MultiSurface container id by its class.

    One walk of the assembled model: for each instance of a palette class,
    descend into its subtree for ``gml:MultiSurface`` container ids (the
    ``lod1MultiSurface`` of the themed features and the ``lod1Geometry``
    MultiSurface of the generic fallback). One walk rather than one per class
    keeps this O(model), like the solar/vegetation collectors. Building and
    tree surfaces are skipped because their feature is not a palette class.
    """
    root = getattr(city_model, "xsd", city_model)
    buckets: dict[type, list[str]] = {cls: [] for cls in _LANDCOVER_CLASSES}
    for feat in iter_instances(root):
        for feature_cls in _LANDCOVER_CLASSES:
            if isinstance(feat, feature_cls):
                buckets[feature_cls].extend(
                    f"#{sub.id}"
                    for sub in iter_instances(feat)
                    if isinstance(sub, MultiSurface) and sub.id
                )
                break
    return buckets


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
