"""Energy ADE 3.0 emitters: per-surface and per-opening derived attributes.

Plug-in module for the :mod:`citygml_energy.derived_attributes` seam.
Exports :data:`EMITTERS` (one entry per emitted ``bdgBdrySurf*`` /
``bdgOpn*`` property) and :data:`SETUPS` (one hook that pre-indexes the
in-document MaterialLibrary + LayeredConstructionLibrary so each
thickness / heat-capacity compute is O(1)).

Per-surface attributes emitted (BoundarySurface, when geometry present):

* ``bdgBdrySurfTotalSurfaceArea`` (m²): full geometric face area of the
  surface, **including** the area occupied by openings. Computed per
  Polygon as the exterior-ring area minus the area of *true geometric
  holes only* (interior rings that do not match any child opening's
  exterior ring; e.g. courtyards, tower intrusions). Interior rings
  punched in the parent wall to host a Window/Door opening are not
  subtracted here — the total represents the underlying face before
  openings are deducted.
* ``bdgBdrySurfOpaqueSurfaceArea`` (m²): the conductive (opaque) part
  of the face, ``Total − Σ child_opening.bdgOpnArea``. **Only emitted
  when the surface carries one or more openings**; on a surface with
  no openings the opaque area equals the total and the absence is the
  schema-honest signal. Uses the opening's own MultiSurface area, not
  the parent's interior-ring area, so standalone-shell openings (LoD3+
  without an interior ring on the parent) are handled correctly.
* ``bdgBdrySurfInclination`` (deg, [0, 180]): angle between the outward
  normal and ``+Z``: ``0`` for a flat roof, ``90`` for a vertical wall,
  ``180`` for a horizontal floor with downward outward normal.
* ``bdgBdrySurfAzimuth`` (deg, [0, 360)): compass bearing of the
  outward normal's horizontal component. Omitted when the surface is
  effectively horizontal (azimuth is geometrically undefined there).
* ``bdgBdrySurfThickness`` (m): Σ ``Layer.thickness`` over the
  LayeredConstruction referenced by the surface's
  ``layeredConstruction`` xlink. Skipped when no construction is
  mapped, or when no layer has a thickness.
* ``bdgBdrySurfHeatCapacity`` (kJ/(K·m²)): areal thermal mass,
  ``Σᵢ thicknessᵢ · densityᵢ · cpᵢ / 1000`` over every solid layer of
  the LayeredConstruction. Layers whose material lacks ``density`` or
  ``specificHeatCapacity`` (e.g. ``Gas`` panes inside a window cavity)
  are excluded from the sum but **not** from ``Thickness``.

Per-opening attributes emitted (Window/Door, when geometry present):

* ``bdgOpnArea`` (m²), ``bdgOpnInclination`` (deg), ``bdgOpnAzimuth``
  (deg): same definitions as the boundary-surface analogues, computed
  from the opening's own ``lod{0..4}MultiSurface``.

Idempotence, field-presence, and iteration are owned by the seam:
each compute function below assumes its target list field exists and
is empty, and returns the values to append. Absent or ambiguous inputs
yield ``None`` (skip), never placeholder values — an absent attribute
on the output is the schema-honest signal that the value could not be
derived.

Inclination + azimuth are taken from the largest-area polygon in the
surface's MultiSurface, not averaged. A ``bldg:_BoundarySurface`` is a
planar entity per CityGML semantics; in practice the per-building STEP
import emits one polygon per surface, so the choice does not bite.

Opening / true-hole classification: the per-building geometry pipeline
(:mod:`citygml_energy.geometry`) punches a Window/Door opening into its
parent wall as both (a) a child element on ``parent.opening`` and (b)
an interior ring on the parent polygon. Interior rings that do not
match any child opening's exterior ring (vertex-key equality at
0.1 mm) are treated as true geometric holes and subtracted from the
total. Rings that *do* match an opening are left in the total and only
deducted in the opaque area, via the opening's own ``bdgOpnArea``.

The construction lookup goes through the in-document
LayeredConstructionLibrary / MaterialLibrary indices built once per
``apply`` call by :func:`_setup_construction_info`. Cross-document
xlinks (xlinks pointing outside the CityModel) silently no-op: this
module's contract is "compute what we can prove locally", not "fetch
arbitrary remote XML".
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from math import sqrt
from typing import Any

from ._step import Coord3D, GeometryPolygon
from .bindings import (
    BdgBdrySurfAzimuth,
    BdgBdrySurfHeatCapacity,
    BdgBdrySurfInclination,
    BdgBdrySurfOpaqueSurfaceArea,
    BdgBdrySurfThickness,
    BdgBdrySurfTotalSurfaceArea,
    BdgOpnArea,
    BdgOpnAzimuth,
    BdgOpnInclination,
    LayeredConstruction1,
    LayeredConstructionLibrary,
    MaterialLibrary,
    SolidMaterial,
)
from .core import CityModel
from .derived_attributes import DerivedAttribute, DerivedContext, Setup
from .gml_builders import newell_normal, open_ring, planar_surface_attributes
from .mapping import iter_instances

__all__ = ["EMITTERS", "SETUPS"]


# uom strings used on the emitted elements. Pinned to the existing
# project conventions (no caret superscripts; m2 instead of m^2; deg
# instead of "decimal degree"); see neighbouring writes in
# :mod:`citygml_energy.city_builder.builders.building` for the same
# tokens. ``kJ/K*m2`` keeps numbers human-readable (typical wall is
# ~50–500 kJ/(K·m²), thus 4-digit numbers); J/(K·m²) would push to
# 5-6 digits.
_UOM_AREA_M2: str = "m2"
_UOM_DEGREES: str = "deg"
_UOM_METRES: str = "m"
_UOM_HEAT_CAPACITY: str = "kJ/K*m2"

# Decimal precisions: 3 dp on metric quantities (mm² / mm / kJ/(K·m²)),
# 2 dp on angles. Coordinates entering this module were quantised to a
# micrometre grid by :func:`citygml_energy.gml_builders.build_polygon`,
# so any extra precision past these would be spurious.
_DEC_AREA: int = 3
_DEC_LENGTH: int = 3
_DEC_ANGLE: int = 2
_DEC_HEAT_CAPACITY: int = 3

# Field names declared by the bindings on each LoD MultiSurface property
# accessor. Order is highest-first; we use whichever LoD is populated.
# Building-side LoD names; opening-side names are identical
# (``bldg:_BoundarySurface`` and ``bldg:_Opening`` share the LoD
# repertoire).
_LOD_MULTISURFACE_FIELDS: tuple[str, ...] = (
    "lod4_multi_surface",
    "lod3_multi_surface",
    "lod2_multi_surface",
    "lod1_multi_surface",
)

# Context keys this module reads and writes.
_CTX_KEY_CONSTRUCTION_INFO: str = "construction_info_by_id"
_CTX_KEY_MATERIAL_INDEX: str = "material_index"


# ---------------------------------------------------------------------------
# Setup: index materials + constructions onto the context
# ---------------------------------------------------------------------------


def _setup_construction_info(model: CityModel, ctx: DerivedContext) -> None:
    """Pre-compute ``_ConstructionInfo`` per construction once per ``apply`` call.

    Without this, thickness + heat capacity would re-reduce the same
    layer list once per surface that references it; a real building
    reuses one external-wall construction across 20+ walls. Stashing
    the result on the context behind a stable key lets the per-surface
    compute functions do O(1) lookups.
    """
    materials = _build_material_index(model)
    setattr(ctx, _CTX_KEY_MATERIAL_INDEX, materials)
    setattr(
        ctx,
        _CTX_KEY_CONSTRUCTION_INFO,
        _build_construction_info_index(model, materials),
    )


SETUPS: tuple[Setup, ...] = (_setup_construction_info,)


# ---------------------------------------------------------------------------
# Boundary-surface compute functions
# ---------------------------------------------------------------------------


def _compute_total_area(surf: Any, ctx: DerivedContext) -> list[Any] | None:
    total, _ = _surface_areas(surf)
    if total is None:
        return None
    return [
        BdgBdrySurfTotalSurfaceArea(
            value=round(total, _DEC_AREA),
            uom=_UOM_AREA_M2,
        )
    ]


def _compute_opaque_area(surf: Any, ctx: DerivedContext) -> list[Any] | None:
    _, opaque = _surface_areas(surf)
    if opaque is None:
        return None
    return [
        BdgBdrySurfOpaqueSurfaceArea(
            value=round(opaque, _DEC_AREA),
            uom=_UOM_AREA_M2,
        )
    ]


def _compute_inclination(surf: Any, ctx: DerivedContext) -> list[Any] | None:
    attrs = _largest_polygon_attributes(surf)
    if attrs is None:
        return None
    _, _, inclination_deg = attrs
    return [
        BdgBdrySurfInclination(
            value=round(inclination_deg, _DEC_ANGLE),
            uom=_UOM_DEGREES,
        )
    ]


def _compute_azimuth(surf: Any, ctx: DerivedContext) -> list[Any] | None:
    attrs = _largest_polygon_attributes(surf)
    if attrs is None:
        return None
    _, azimuth_deg, _ = attrs
    if azimuth_deg is None:
        return None
    # ``round`` can promote 359.998 to 360.0 and lift the value out of
    # the [0, 360) compass-bearing range. Apply the modular reduction
    # after rounding so the canonical 0/360 boundary stays at 0.
    canonical = round(azimuth_deg, _DEC_ANGLE) % 360.0
    return [
        BdgBdrySurfAzimuth(
            value=canonical,
            uom=_UOM_DEGREES,
        )
    ]


def _compute_thickness(surf: Any, ctx: DerivedContext) -> list[Any] | None:
    cinfo = _resolve_construction_info(surf, ctx)
    if cinfo is None or cinfo.thickness_m is None:
        return None
    return [
        BdgBdrySurfThickness(
            value=round(cinfo.thickness_m, _DEC_LENGTH),
            uom=_UOM_METRES,
        )
    ]


def _compute_heat_capacity(surf: Any, ctx: DerivedContext) -> list[Any] | None:
    cinfo = _resolve_construction_info(surf, ctx)
    if cinfo is None or cinfo.heat_capacity_kj_per_k_m2 is None:
        return None
    return [
        BdgBdrySurfHeatCapacity(
            value=round(cinfo.heat_capacity_kj_per_k_m2, _DEC_HEAT_CAPACITY),
            uom=_UOM_HEAT_CAPACITY,
        )
    ]


# ---------------------------------------------------------------------------
# Opening compute functions
#
# Note: ``bdgOpnThickness`` does not exist on the XSD's opening side
# (windows / doors carry their own LayeredConstruction, but the
# per-opening thickness element family is not declared); thickness and
# heat capacity for an opening live only on the construction itself,
# not as separate ``bdgOpn*`` siblings of ``bdgBdrySurf*``.
# ---------------------------------------------------------------------------


def _compute_opening_area(opening: Any, ctx: DerivedContext) -> list[Any] | None:
    total = _total_multisurface_area(opening)
    if total is None:
        return None
    return [BdgOpnArea(value=round(total, _DEC_AREA), uom=_UOM_AREA_M2)]


def _compute_opening_inclination(
    opening: Any,
    ctx: DerivedContext,
) -> list[Any] | None:
    attrs = _largest_polygon_attributes(opening)
    if attrs is None:
        return None
    _, _, inclination_deg = attrs
    return [
        BdgOpnInclination(
            value=round(inclination_deg, _DEC_ANGLE),
            uom=_UOM_DEGREES,
        )
    ]


def _compute_opening_azimuth(
    opening: Any,
    ctx: DerivedContext,
) -> list[Any] | None:
    attrs = _largest_polygon_attributes(opening)
    if attrs is None:
        return None
    _, azimuth_deg, _ = attrs
    if azimuth_deg is None:
        return None
    # See ``_compute_azimuth``: round-then-mod keeps the canonical
    # [0, 360) bearing when rounding pushes ~359.998 up to 360.0.
    canonical = round(azimuth_deg, _DEC_ANGLE) % 360.0
    return [
        BdgOpnAzimuth(
            value=canonical,
            uom=_UOM_DEGREES,
        )
    ]


# ---------------------------------------------------------------------------
# Registration
#
# Per-object emitter order matters: total + opaque area both read the
# parent geometry and the opening MultiSurfaces, so they are
# self-contained; inclination/azimuth are independent; thickness +
# heat capacity read the layered_construction xlink that
# construction_mapping.EMITTERS must have already populated earlier in
# the registration sequence.
# ---------------------------------------------------------------------------


EMITTERS: tuple[DerivedAttribute, ...] = (
    DerivedAttribute(
        field_name="bdg_bdry_surf_total_surface_area",
        compute=_compute_total_area,
    ),
    DerivedAttribute(
        field_name="bdg_bdry_surf_opaque_surface_area",
        compute=_compute_opaque_area,
    ),
    DerivedAttribute(
        field_name="bdg_bdry_surf_inclination",
        compute=_compute_inclination,
    ),
    DerivedAttribute(
        field_name="bdg_bdry_surf_azimuth",
        compute=_compute_azimuth,
    ),
    DerivedAttribute(
        field_name="bdg_bdry_surf_thickness",
        compute=_compute_thickness,
    ),
    DerivedAttribute(
        field_name="bdg_bdry_surf_heat_capacity",
        compute=_compute_heat_capacity,
    ),
    DerivedAttribute(
        field_name="bdg_opn_area",
        compute=_compute_opening_area,
    ),
    DerivedAttribute(
        field_name="bdg_opn_inclination",
        compute=_compute_opening_inclination,
    ),
    DerivedAttribute(
        field_name="bdg_opn_azimuth",
        compute=_compute_opening_azimuth,
    ),
)


# ---------------------------------------------------------------------------
# Library indices (LayeredConstruction + Material)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ConstructionInfo:
    """Pre-computed thickness + heat capacity for one LayeredConstruction.

    Computed once per construction and reused across every surface that
    references it. Both fields are None when the underlying data is
    insufficient (no thickness on any layer, or no solid material with
    both density + cp), so callers can decide independently whether to
    emit each ``bdgBdrySurf*`` element.
    """

    thickness_m: float | None
    heat_capacity_kj_per_k_m2: float | None


def _build_material_index(model: CityModel) -> dict[str, Any]:
    """Index every in-document ``SolidMaterial`` / ``Gas`` by ``gml:id``."""
    index: dict[str, Any] = {}
    for obj in iter_instances(model.xsd):
        if not isinstance(obj, MaterialLibrary):
            continue
        for member in obj.library_member:
            for attr in ("solid_material", "gas"):
                inner = getattr(member, attr, None)
                if inner is None:
                    continue
                gml_id = getattr(inner, "id", None)
                if isinstance(gml_id, str):
                    index[gml_id] = inner
    return index


def _build_construction_info_index(
    model: CityModel,
    materials: dict[str, Any],
) -> dict[str, _ConstructionInfo]:
    """Pre-compute ``_ConstructionInfo`` for every in-document construction."""
    index: dict[str, _ConstructionInfo] = {}
    for obj in iter_instances(model.xsd):
        if not isinstance(obj, LayeredConstructionLibrary):
            continue
        for member in obj.library_member:
            inner = getattr(member, "layered_construction", None)
            if not isinstance(inner, LayeredConstruction1):
                continue
            gml_id = getattr(inner, "id", None)
            if not isinstance(gml_id, str):
                continue
            index[gml_id] = _reduce_construction(inner, materials)
    return index


def _reduce_construction(
    construction: LayeredConstruction1,
    materials: dict[str, Any],
) -> _ConstructionInfo:
    """Sum thickness + areal heat capacity over *construction*'s layers."""
    thickness_total = 0.0
    has_thickness = False
    heat_capacity_total = 0.0
    has_heat_capacity = False
    for layer in construction.layer:
        layer_inner = getattr(layer, "layer", None)
        if layer_inner is None:
            continue
        thickness = _measure_value(getattr(layer_inner, "thickness", None))
        if thickness is None:
            continue
        thickness_total += thickness
        has_thickness = True
        material = _resolve_material(layer_inner.material, materials)
        if not isinstance(material, SolidMaterial):
            # Gas layers contribute to total thickness but not to areal
            # heat capacity (the Energy ADE Gas dataclass carries
            # ``rValue`` only — no density or specific heat capacity to
            # multiply through). Excluding them is the schema-honest
            # choice: their thermal mass per area is genuinely
            # negligible compared with the surrounding solid layers
            # (argon ~1.78 kg/m³ · 520 J/(K·kg) · 0.016 m → 14.8 J/(K·m²),
            # versus glass ~2500 · 750 · 0.004 → 7500 J/(K·m²)).
            continue
        density = _measure_value(material.density)
        cp = _measure_value(material.specific_heat_capacity)
        if density is None or cp is None:
            continue
        heat_capacity_total += thickness * density * cp
        has_heat_capacity = True
    return _ConstructionInfo(
        thickness_m=thickness_total if has_thickness else None,
        heat_capacity_kj_per_k_m2=(heat_capacity_total / 1000.0 if has_heat_capacity else None),
    )


def _measure_value(measure: Any | None) -> float | None:
    """Return the numeric ``value`` on a ``gml:MeasureType``, or ``None``."""
    if measure is None:
        return None
    value = getattr(measure, "value", None)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _resolve_material(
    material_property: Any,
    materials: dict[str, Any],
) -> Any | None:
    """Resolve a ``Layer.material`` to its underlying ``SolidMaterial`` / ``Gas``."""
    for attr in ("solid_material", "gas"):
        inner = getattr(material_property, attr, None)
        if inner is not None:
            return inner
    href = getattr(material_property, "href", None)
    if isinstance(href, str) and href.startswith("#"):
        return materials.get(href[1:])
    return None


def _resolve_construction_info(
    surf: Any,
    ctx: DerivedContext,
) -> _ConstructionInfo | None:
    """Trace ``surf.layered_construction[0]`` xlink to its pre-computed info.

    Returns ``None`` when the surface has no construction xlink, when the
    xlink is not local, or when the referenced construction is not in
    the in-document index. Cross-document xlinks (xlinks pointing at an
    external Library document) silently no-op: the per-building
    pipeline is self-contained, so this should not happen in practice.
    """
    layered_construction = getattr(surf, "layered_construction", None)
    if not isinstance(layered_construction, list) or not layered_construction:
        return None
    href = getattr(layered_construction[0], "href", None)
    if not isinstance(href, str) or not href.startswith("#"):
        return None
    index: dict[str, _ConstructionInfo] = (
        getattr(
            ctx,
            _CTX_KEY_CONSTRUCTION_INFO,
            None,
        )
        or {}
    )
    return index.get(href[1:])


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _multisurface(obj: Any) -> Any | None:
    """Return the first populated ``lod{0..4}MultiSurface`` on *obj*, if any."""
    for field_name in _LOD_MULTISURFACE_FIELDS:
        prop = getattr(obj, field_name, None)
        if prop is None:
            continue
        ms = getattr(prop, "multi_surface", None)
        if ms is not None:
            return ms
    return None


def _iter_polygons(obj: Any) -> list[GeometryPolygon]:
    ms = _multisurface(obj)
    if ms is None:
        return []
    polygons: list[GeometryPolygon] = []
    for member in ms.surface_member:
        polygon = getattr(member, "polygon", None)
        if polygon is None:
            continue
        geom = _polygon_to_geometry(polygon)
        if geom is not None:
            polygons.append(geom)
    return polygons


def _polygon_to_geometry(polygon: Any) -> GeometryPolygon | None:
    """Convert an xsdata ``gml:Polygon`` to a :class:`GeometryPolygon`."""
    exterior_ring = _ring_coords(getattr(polygon, "exterior", None))
    if exterior_ring is None or len(exterior_ring) < 3:
        return None
    interior_rings: list[list[tuple[float, float, float]]] = []
    for interior in polygon.interior:
        ring = _ring_coords(interior)
        if ring is not None and len(ring) >= 3:
            interior_rings.append(ring)
    return GeometryPolygon(exterior=exterior_ring, interiors=interior_rings)


def _ring_coords(
    ring_property: Any | None,
) -> list[tuple[float, float, float]] | None:
    if ring_property is None:
        return None
    linear_ring = getattr(ring_property, "linear_ring", None)
    if linear_ring is None:
        return None
    pos_list = getattr(linear_ring, "pos_list", None)
    if pos_list is None:
        return None
    flat = pos_list.value
    if not isinstance(flat, list) or len(flat) < 9 or len(flat) % 3 != 0:
        return None
    return [
        (float(flat[i]), float(flat[i + 1]), float(flat[i + 2])) for i in range(0, len(flat), 3)
    ]


def _largest_polygon_attributes(
    obj: Any,
) -> tuple[float, float | None, float] | None:
    """Return ``planar_surface_attributes`` for the largest polygon on *obj*.

    A ``bldg:_BoundarySurface`` is planar by CityGML semantics; in the
    rare case where the source emits multiple polygons, the largest is
    the most representative for inclination/azimuth (small adjacent
    fragments can have wildly different normals due to numerical noise
    on a single physical face). Returns ``None`` when no non-degenerate
    polygon is found.
    """
    best: tuple[float, float | None, float] | None = None
    best_area = 0.0
    for geom in _iter_polygons(obj):
        attrs = planar_surface_attributes(geom)
        if attrs is None:
            continue
        area, _, _ = attrs
        if area > best_area:
            best = attrs
            best_area = area
    return best


def _total_multisurface_area(obj: Any) -> float | None:
    """Sum the ``planar_surface_attributes`` area of every polygon on *obj*."""
    total = 0.0
    counted = False
    for geom in _iter_polygons(obj):
        attrs = planar_surface_attributes(geom)
        if attrs is None:
            continue
        area, _, _ = attrs
        total += area
        counted = True
    return total if counted else None


# Vertex-key precision (decimal places, m → 0.1 mm grain) for opening /
# interior-ring matching. Pinned to the same value
# :func:`citygml_energy.geometry._ring_vertex_key` uses on the geometry
# side so the two predicates agree.
_VERTEX_KEY_PRECISION: int = 4

# Below this Newell magnitude the ring is degenerate (sub-µm² area) and
# cannot contribute meaningfully. Mirrors gml_builders'
# ``_DEGENERATE_AREA_EPS``; redeclared here because it is a module-
# private constant on the gml_builders side.
_RING_AREA_EPS: float = 1e-9


def _ring_area(ring: list[Coord3D]) -> float | None:
    """Return ``|Newell(ring)| / 2`` (m²), or ``None`` for a degenerate ring."""
    nx, ny, nz = newell_normal(ring)
    mag = sqrt(nx * nx + ny * ny + nz * nz)
    if mag < _RING_AREA_EPS:
        return None
    return mag / 2.0


def _ring_vertex_key(
    ring: list[Coord3D],
    precision: int = _VERTEX_KEY_PRECISION,
) -> frozenset[tuple[float, float, float]]:
    """Hashable vertex set for matching opening exteriors against parent interior rings.

    Mirrors :func:`citygml_energy.geometry._ring_vertex_key`. Kept as a
    tiny in-module copy (rather than importing across modules) because
    the predicate's contract — vertex equality at 0.1 mm — is the
    load-bearing semantic, not the call site.
    """
    return frozenset(
        (round(v[0], precision), round(v[1], precision), round(v[2], precision))
        for v in open_ring(ring)
    )


def _opening_objects(surf: Any) -> list[Any]:
    """Walk ``surf.opening`` and return its inline opening dataclasses."""
    out: list[Any] = []
    properties = getattr(surf, "opening", None)
    if not isinstance(properties, list):
        return out
    for prop in properties:
        if not dataclasses.is_dataclass(prop):
            continue
        for f in dataclasses.fields(prop):
            inner = getattr(prop, f.name, None)
            if inner is not None and _has_bdg_opn_area(inner):
                out.append(inner)
                break
    return out


def _has_bdg_opn_area(obj: Any) -> bool:
    """True iff *obj* exposes a ``bdg_opn_area`` list field.

    Sentinel for "this object is an Opening" in the binding-driven
    walker. Keeps Opening recognition tied to the schema property the
    XSD declares ``Opening``-side, rather than to a hard-coded class
    list that breaks on regeneration.
    """
    field_value = getattr(obj, "bdg_opn_area", None)
    return isinstance(field_value, list)


def _surface_areas(surf: Any) -> tuple[float | None, float | None]:
    """Return ``(total_area, opaque_area_or_none)`` for a boundary surface.

    *total_area* sums every parent polygon's exterior area minus only
    its **true geometric holes** — interior rings that do not match
    any child opening's exterior ring (vertex-key equality at 0.1 mm).
    Interior rings backing a Window/Door are *not* subtracted; the
    total represents the underlying face including opening areas, per
    the Energy ADE 3.0 ``bdgBdrySurfTotalSurfaceArea`` semantics.

    *opaque_area* is ``total − Σ(child opening MultiSurface area)``
    and is returned only when the surface carries one or more
    openings. Surfaces without openings get ``None`` so the caller
    omits the element (an opaque area equal to the total is the
    schema-honest signal of "no openings", and emitting both would
    duplicate the value). The opening's own MultiSurface area is used
    for the subtraction — not the parent's interior-ring area — so
    LoD3+ standalone-shell openings (with no interior ring on the
    parent) work correctly.

    Falls back to ``opaque = None`` when any opening's MultiSurface is
    unusable (no LoD geometry, all-degenerate polygons): emitting a
    Total computed from the geometry we have but skipping Opaque is
    more honest than guessing a shortfall.
    """
    polygons = _iter_polygons(surf)
    if not polygons:
        return None, None

    openings = _opening_objects(surf)
    opening_keys: set[frozenset[tuple[float, float, float]]] = set()
    sum_opening_area = 0.0
    every_opening_has_area = True
    for opening in openings:
        opening_total = _total_multisurface_area(opening)
        if opening_total is None:
            every_opening_has_area = False
        else:
            sum_opening_area += opening_total
        for geom in _iter_polygons(opening):
            opening_keys.add(_ring_vertex_key(geom.exterior))

    total = 0.0
    counted = False
    for geom in polygons:
        exterior_area = _ring_area(geom.exterior)
        if exterior_area is None:
            continue
        true_hole_area = 0.0
        for ring in geom.interiors:
            ring_area = _ring_area(ring)
            if ring_area is None:
                continue
            if _ring_vertex_key(ring) in opening_keys:
                # Opening ring: stays in Total, only deducted in Opaque.
                continue
            true_hole_area += ring_area
        polygon_total = exterior_area - true_hole_area
        if polygon_total <= 0.0:
            # A true hole larger than the exterior is pathological
            # (GML 3.1.1 forbids it). Drop the polygon rather than
            # ship a negative contribution.
            continue
        total += polygon_total
        counted = True

    if not counted:
        return None, None
    if not openings or not every_opening_has_area:
        return total, None

    opaque = total - sum_opening_area
    if opaque < 0.0:
        # Floating-point noise on shared edges occasionally pushes the
        # sum of opening areas slightly above the parent face; clamp
        # to 0 rather than emit a negative opaque area.
        opaque = 0.0
    return total, opaque
