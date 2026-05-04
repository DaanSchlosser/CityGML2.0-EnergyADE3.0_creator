"""Post-processor: attach Energy ADE 3.0 per-surface descriptors to BoundarySurfaces and Openings.

Computes the five (BoundarySurface) and three (Opening) attributes the
Energy ADE 3.0 ``bdgBdrySurf*`` / ``bdgOpn*`` element families publish,
from the geometry already populated by :mod:`citygml_energy.geometry`
and the layered constructions already cross-linked by
:mod:`citygml_energy.construction_mapping`. Run after both — this module
reads, never edits, the layeredConstruction xlinks set there.

Per-surface attributes emitted (BoundarySurface, when geometry present):

* ``bdgBdrySurfTotalSurfaceArea`` (m²) — full geometric face area of the
  surface, **including** the area occupied by openings. Computed per
  Polygon as the exterior-ring area minus the area of *true geometric
  holes only* (interior rings that do not match any child opening's
  exterior ring; e.g. courtyards, tower intrusions). Interior rings
  punched in the parent wall to host a Window/Door opening are not
  subtracted here — the total is meant to represent the underlying face
  before openings are deducted.
* ``bdgBdrySurfOpaqueSurfaceArea`` (m²) — the conductive (opaque) part
  of the face: ``Total − Σ child_opening.bdgOpnArea``. **Only emitted
  when the surface carries one or more openings**; on a surface with no
  openings the opaque area equals the total and the absence is the
  schema-honest signal. Uses the opening's own MultiSurface area (the
  same value emitted on ``bdgOpnArea``), not the parent's interior-ring
  area, so standalone-shell openings (LoD3+ without an interior ring on
  the parent) are handled correctly.
* ``bdgBdrySurfInclination`` (deg, [0, 180]) — angle between the outward
  normal and ``+Z``: ``0`` for a flat roof, ``90`` for a vertical wall,
  ``180`` for a horizontal floor whose outward normal points down.
* ``bdgBdrySurfAzimuth`` (deg, [0, 360)) — compass bearing of the
  outward normal's horizontal component. **Omitted** when the surface
  is effectively horizontal (azimuth is geometrically undefined there).
* ``bdgBdrySurfThickness`` (m) — Σ ``Layer.thickness`` over every layer
  of the LayeredConstruction the surface's ``layeredConstruction`` xlink
  points at. Skipped when no construction is mapped, or when no layer
  has a thickness.
* ``bdgBdrySurfHeatCapacity`` (kJ/(K·m²)) — areal thermal mass,
  ``Σᵢ thicknessᵢ · densityᵢ · cpᵢ / 1000`` over every solid layer of
  the LayeredConstruction. Layers whose material lacks ``density`` or
  ``specificHeatCapacity`` (e.g. ``Gas`` argon panes inside a window
  cavity) are excluded from the sum but **not** from ``Thickness``.
  Skipped entirely when no solid layer carries both numerics.

Per-opening attributes emitted (Window/Door, when geometry present):

* ``bdgOpnArea`` (m²), ``bdgOpnInclination`` (deg), ``bdgOpnAzimuth``
  (deg) — same definitions as the boundary-surface analogues, computed
  from the opening's own ``lod{0..4}MultiSurface``.

Inclination + azimuth are taken from the **largest-area** polygon in
the surface's MultiSurface, not averaged. A bldg:_BoundarySurface is a
planar entity per CityGML semantics; in practice the per-building STEP
import emits one polygon per surface, so the choice does not bite here.

Opening / true-hole classification: the per-building geometry pipeline
(:mod:`citygml_energy.geometry`) punches a Window/Door opening into its
parent wall as both (a) a child element on ``parent.opening`` and (b)
an interior ring on the parent polygon. Interior rings that do not
match any child opening's exterior ring (vertex-key equality, same
predicate as :func:`citygml_energy.geometry._match_opening_to_parent`,
rounded to 0.1 mm) are treated as true geometric holes and subtracted
from the total. Rings that *do* match an opening are left in the total
and only deducted in the opaque area, via the opening's own
``bdgOpnArea`` value.

Discovery is binding-driven: any dataclass that has a
``bdg_bdry_surf_total_surface_area`` *list* field is treated as a
boundary-surface emit target; any class with a ``bdg_opn_area`` field
is an opening target. Regenerating the bindings with a new surface or
opening class therefore picks up matching emissions automatically. The
city-builder uses an analogous geometry-only path
(:func:`citygml_energy.city_builder.builders.building._attach_planar_surface_ade_attributes`);
this module supersedes that pattern for the per-building pipeline by
*also* computing thickness + heat capacity from the wired-up
LayeredConstruction.

The function is a no-op for any surface or opening that has no LoD
multisurface, an unrecognised construction xlink, or a degenerate
(zero-area) polygon. It does not write placeholder values; an absent
attribute on the output is the schema-honest signal that the value
could not be derived from the inputs.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from math import sqrt
from typing import Any

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
from ._step import Coord3D, GeometryPolygon
from .core import CityModel
from .gml_builders import newell_normal, open_ring, planar_surface_attributes
from .mapping import iter_instances

__all__ = ["attach_boundary_surface_attributes"]


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

# Fields names declared by the bindings on each LoD MultiSurface
# property accessor. Order is highest-first; we use whichever LoD is
# populated. Building-side LoD names; opening-side names are identical
# (``bldg:_BoundarySurface`` and ``bldg:_Opening`` share the LoD
# repertoire).
_LOD_MULTISURFACE_FIELDS: tuple[str, ...] = (
    "lod4_multi_surface",
    "lod3_multi_surface",
    "lod2_multi_surface",
    "lod1_multi_surface",
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def attach_boundary_surface_attributes(model: CityModel) -> None:
    """Attach ``bdgBdrySurf*`` and ``bdgOpn*`` attributes across *model*.

    Idempotent: each attribute list is only appended to when empty, so a
    re-run on the same model does not duplicate entries (this matches
    :func:`citygml_energy.construction_mapping.apply_construction_mapping`'s
    once-per-surface contract).

    Walks every dataclass instance reachable from the model's GML root
    (the same traversal used by :mod:`citygml_energy.construction_mapping`).
    A surface is recognised by the presence of the
    ``bdg_bdry_surf_total_surface_area`` list field on its dataclass; an
    opening by the presence of ``bdg_opn_area``. This is binding-driven,
    not list-driven: regenerating the bindings with new surface /
    opening classes picks them up automatically.

    The construction lookup goes through the in-document
    LayeredConstructionLibrary / MaterialLibrary indices built once per
    call. Cross-document xlinks (xlinks that point outside the
    CityModel) are silently skipped — this module's contract is
    "compute what we can prove locally", not "fetch arbitrary remote
    XML".
    """
    material_index = _build_material_index(model)
    construction_index = _build_construction_info_index(model, material_index)

    for obj in iter_instances(model.xsd):
        if _is_boundary_surface_target(obj):
            _attach_boundary_surface(obj, construction_index)
        elif _is_opening_target(obj):
            _attach_opening(obj)


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
    model: CityModel, materials: dict[str, Any],
) -> dict[str, _ConstructionInfo]:
    """Pre-compute ``_ConstructionInfo`` for every in-document construction.

    Walks every ``LayeredConstructionLibrary``, reduces each member's
    layer list against *materials*, and stores the resulting thickness
    + areal heat capacity by the construction's ``gml:id`` so the
    per-surface attacher can look it up in O(1) without re-walking
    layers per surface (a real building can reuse one external-wall
    construction across 20+ wall faces).
    """
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
    construction: LayeredConstruction1, materials: dict[str, Any],
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
        heat_capacity_kj_per_k_m2=(
            heat_capacity_total / 1000.0 if has_heat_capacity else None
        ),
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
    material_property: Any, materials: dict[str, Any],
) -> Any | None:
    """Resolve a ``Layer.material`` to its underlying ``SolidMaterial`` / ``Gas``.

    Two possible shapes per the bindings: the property can either inline
    the material (``solid_material``/``gas`` attributes set) or carry an
    ``href`` xlink into the MaterialLibrary. We handle both. The href
    form (``#mat_xxx``) is the one the per-building input format uses.
    """
    for attr in ("solid_material", "gas"):
        inner = getattr(material_property, attr, None)
        if inner is not None:
            return inner
    href = getattr(material_property, "href", None)
    if isinstance(href, str) and href.startswith("#"):
        return materials.get(href[1:])
    return None


# ---------------------------------------------------------------------------
# BoundarySurface attachment
# ---------------------------------------------------------------------------


def _is_boundary_surface_target(obj: Any) -> bool:
    """True iff *obj* exposes a ``bdg_bdry_surf_total_surface_area`` list field."""
    field_value = getattr(obj, "bdg_bdry_surf_total_surface_area", None)
    return isinstance(field_value, list)


def _attach_boundary_surface(
    surf: Any,
    constructions: dict[str, _ConstructionInfo],
) -> None:
    geometry_attrs = _largest_polygon_attributes(surf)
    total_area_m2, opaque_area_m2 = _surface_areas(surf)
    cinfo = _resolve_construction_info(surf, constructions)

    if (
        not surf.bdg_bdry_surf_total_surface_area
        and total_area_m2 is not None
    ):
        surf.bdg_bdry_surf_total_surface_area.append(
            BdgBdrySurfTotalSurfaceArea(
                value=round(total_area_m2, _DEC_AREA), uom=_UOM_AREA_M2,
            )
        )

    if (
        not surf.bdg_bdry_surf_opaque_surface_area
        and opaque_area_m2 is not None
    ):
        surf.bdg_bdry_surf_opaque_surface_area.append(
            BdgBdrySurfOpaqueSurfaceArea(
                value=round(opaque_area_m2, _DEC_AREA), uom=_UOM_AREA_M2,
            )
        )

    if geometry_attrs is not None and not surf.bdg_bdry_surf_inclination:
        _, azimuth_deg, inclination_deg = geometry_attrs
        surf.bdg_bdry_surf_inclination.append(
            BdgBdrySurfInclination(
                value=round(inclination_deg, _DEC_ANGLE), uom=_UOM_DEGREES,
            )
        )
        if azimuth_deg is not None and not surf.bdg_bdry_surf_azimuth:
            surf.bdg_bdry_surf_azimuth.append(
                BdgBdrySurfAzimuth(
                    value=round(azimuth_deg, _DEC_ANGLE), uom=_UOM_DEGREES,
                )
            )

    if cinfo is not None:
        if (
            cinfo.thickness_m is not None
            and not surf.bdg_bdry_surf_thickness
        ):
            surf.bdg_bdry_surf_thickness.append(
                BdgBdrySurfThickness(
                    value=round(cinfo.thickness_m, _DEC_LENGTH),
                    uom=_UOM_METRES,
                )
            )
        if (
            cinfo.heat_capacity_kj_per_k_m2 is not None
            and not surf.bdg_bdry_surf_heat_capacity
        ):
            surf.bdg_bdry_surf_heat_capacity.append(
                BdgBdrySurfHeatCapacity(
                    value=round(
                        cinfo.heat_capacity_kj_per_k_m2, _DEC_HEAT_CAPACITY,
                    ),
                    uom=_UOM_HEAT_CAPACITY,
                )
            )


# ---------------------------------------------------------------------------
# Opening attachment
# ---------------------------------------------------------------------------


def _is_opening_target(obj: Any) -> bool:
    """True iff *obj* exposes a ``bdg_opn_area`` list field."""
    field_value = getattr(obj, "bdg_opn_area", None)
    return isinstance(field_value, list)


def _attach_opening(opening: Any) -> None:
    """Emit ``bdgOpnArea`` / ``bdgOpnInclination`` / ``bdgOpnAzimuth``.

    ``bdgOpnThickness`` does not exist on the XSD's opening side
    (windows / doors carry their own LayeredConstruction1, but the
    per-opening thickness element family is not declared); thickness
    and heat capacity for an opening therefore live only on the
    construction itself (via ``layeredConstruction``), not as
    separate ``bdgOpn*`` siblings of ``bdgBdrySurf*``.
    """
    geometry_attrs = _largest_polygon_attributes(opening)
    total_area_m2 = _total_multisurface_area(opening)

    if not opening.bdg_opn_area and total_area_m2 is not None:
        opening.bdg_opn_area.append(
            BdgOpnArea(
                value=round(total_area_m2, _DEC_AREA), uom=_UOM_AREA_M2,
            )
        )

    if geometry_attrs is not None and not opening.bdg_opn_inclination:
        _, azimuth_deg, inclination_deg = geometry_attrs
        opening.bdg_opn_inclination.append(
            BdgOpnInclination(
                value=round(inclination_deg, _DEC_ANGLE), uom=_UOM_DEGREES,
            )
        )
        if azimuth_deg is not None and not opening.bdg_opn_azimuth:
            opening.bdg_opn_azimuth.append(
                BdgOpnAzimuth(
                    value=round(azimuth_deg, _DEC_ANGLE), uom=_UOM_DEGREES,
                )
            )


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
    """Convert an xsdata ``gml:Polygon`` to a :class:`GeometryPolygon`.

    Reads ``exterior/LinearRing/posList`` (and each ``interior/...``)
    and chunks the flat coordinate list into ``(x, y, z)`` tuples. Any
    structural shortfall — missing exterior, missing posList, mod-3
    alignment failure — yields ``None`` so the caller can drop the
    polygon without error.
    """
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
        (float(flat[i]), float(flat[i + 1]), float(flat[i + 2]))
        for i in range(0, len(flat), 3)
    ]


def _largest_polygon_attributes(
    obj: Any,
) -> tuple[float, float | None, float] | None:
    """Return ``planar_surface_attributes`` for the largest polygon on *obj*.

    A bldg:_BoundarySurface is planar by CityGML semantics; in the rare
    case where the source emits multiple polygons, the largest is the
    most representative for inclination/azimuth (small adjacent fragments
    can have wildly different normals due to numerical noise on a single
    physical face). Returns ``None`` when no non-degenerate polygon is
    found.
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
    """Sum the ``planar_surface_attributes`` area of every polygon on *obj*.

    Used for openings and as the building block for the surface
    side's *opaque*-flavoured (all-rings-deducted) reduction. The
    boundary-surface *total* path uses :func:`_surface_areas` instead,
    which classifies interior rings into opening rings vs true holes.
    """
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
    ring: list[Coord3D], precision: int = _VERTEX_KEY_PRECISION,
) -> frozenset[tuple[float, float, float]]:
    """Hashable vertex set for matching opening exteriors against parent interior rings.

    Mirrors :func:`citygml_energy.geometry._ring_vertex_key`. Kept as
    a tiny in-module copy (rather than importing across modules)
    because the predicate's contract — vertex equality at 0.1 mm — is
    the load-bearing semantic, not the call site.
    """
    return frozenset(
        (round(v[0], precision), round(v[1], precision), round(v[2], precision))
        for v in open_ring(ring)
    )


def _opening_objects(surf: Any) -> list[Any]:
    """Walk ``surf.opening`` and return its inline opening dataclasses.

    Each ``OpeningPropertyType*`` either inlines an opening on a
    discriminator field (``door``, ``window``, ...) or carries an
    ``href`` xlink with no inline payload. We pick whichever non-None
    field on the property is itself an opening target. Cross-document
    href-only properties contribute no inline object, so the surface
    is treated as having no openings for the purpose of opaque-area
    reconciliation — emitting ``Opaque`` against an opening whose
    geometry lives outside the model would be a guess, not a
    derivation.
    """
    out: list[Any] = []
    properties = getattr(surf, "opening", None)
    if not isinstance(properties, list):
        return out
    for prop in properties:
        if not dataclasses.is_dataclass(prop):
            continue
        for f in dataclasses.fields(prop):
            inner = getattr(prop, f.name, None)
            if inner is not None and _is_opening_target(inner):
                out.append(inner)
                break
    return out


def _surface_areas(surf: Any) -> tuple[float | None, float | None]:
    """Return ``(total_area, opaque_area_or_none)`` for a boundary surface.

    *total_area* sums every parent polygon's exterior area minus only
    its **true geometric holes** — interior rings that do not match
    any child opening's exterior ring (vertex-key equality at 0.1 mm,
    same predicate as the geometry-side opening-to-parent matcher).
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


def _resolve_construction_info(
    surf: Any, constructions: dict[str, _ConstructionInfo],
) -> _ConstructionInfo | None:
    """Trace ``surf.layered_construction[0]`` xlink to its pre-computed info.

    Returns ``None`` when the surface has no construction xlink, when the
    xlink is not local, or when the referenced construction is not in
    the in-document index. Cross-document xlinks (xlinks pointing at an
    external Library document) silently no-op — the per-building
    pipeline is self-contained, so this should not happen in practice.
    """
    layered_construction = getattr(surf, "layered_construction", None)
    if not isinstance(layered_construction, list) or not layered_construction:
        return None
    href = getattr(layered_construction[0], "href", None)
    if not isinstance(href, str) or not href.startswith("#"):
        return None
    return constructions.get(href[1:])
