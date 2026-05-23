"""Pure GML primitive builders.

Turn flat coordinate lists into xsdata ``gml:Polygon`` / ``gml:MultiSurface``
/ ``gml:Solid`` / ``gml:Envelope`` objects. This module is the stable layer
that sits between the low-level STEP parser (:mod:`._step`) and the
schema-aware attachment code (:mod:`.geometry`):

* It knows about GML 3.1.1 wire types (``Polygon``, ``LinearRing``,
  ``PosList``, ``Envelope``, ``Solid``, ``CompositeSurface``, …);
  these are expected to be stable across any CityGML-derived schema.
* It does **not** know about CityGML semantics (boundary surfaces,
  openings, solar panels) or JSON input format.

Functions here are the only place that constructs GML geometry elements,
so changes to the GML wire format stay localised. The module also exposes
the ring orientation and Newell-normal helpers used for solid assembly;
those are pure 3D-math utilities that deserve focused unit tests.
"""

from __future__ import annotations

from itertools import chain
from math import acos, atan2, degrees, inf, sqrt

from ._step import Coord3D, GeometryPolygon, points_close
from .bindings import (
    CompositeSurface,
    DirectPositionType,
    Envelope,
    Exterior,
    Interior,
    LinearRing,
    MultiPoint,
    MultiPointPropertyType,
    MultiSurface,
    MultiSurfacePropertyType,
    Point,
    PointMember,
    Polygon,
    Pos,
    PosList,
    Solid,
    SolidPropertyType,
    SurfaceMember,
    SurfacePropertyType,
)

__all__ = [
    "build_envelope",
    "build_multi_point",
    "build_multi_surface",
    "build_polygon",
    "build_solid",
    "flatten_ring",
    "mean_point",
    "newell_normal",
    "open_ring",
    "orient_solid_polygons",
    "planar_surface_attributes",
]


# Below this magnitude the Newell normal is too small to derive a stable
# orientation from. 1e-9 (m^2) corresponds to a polygon with sub-µm edge
# scale; anything smaller is degenerate and the caller should drop or
# warn rather than emit a meaningless azimuth.
_DEGENERATE_AREA_EPS: float = 1e-9
# When the unit normal's horizontal component is below this, the surface
# is effectively horizontal and azimuth is geometrically undefined. The
# threshold is intentionally generous (≈ 0.06° from vertical Z) so a
# numerical wobble around a flat roof does not produce a high-variance
# random bearing.
_HORIZONTAL_NORMAL_EPS: float = 1e-6


# Coordinates originate from lidar / photogrammetry at cm-accuracy at best.
# Emitting floats with 14+ significant digits advertises a precision the
# data doesn't have, and values that should be exactly zero (e.g.
# STEP round-trip residuals of order 1e-14) serialise as scientific
# notation, which some CityGML readers reject. Quantising to a micrometre
# grid at emission time addresses both: every ordinate becomes a plain
# fixed-point decimal, and sub-micrometre FP noise collapses to 0.
_COORD_DECIMALS = 6


def _q(value: float) -> float:
    """Quantise an ordinate to the output grid (1 um on real inputs)."""
    return round(value, _COORD_DECIMALS)


# ---------------------------------------------------------------------------
# GML object builders
# ---------------------------------------------------------------------------


def build_multi_surface(
    gml_id: str,
    polygons: list[GeometryPolygon],
    *,
    srs_name: str,
    srs_dimension: int,
) -> MultiSurfacePropertyType:
    """Build a ``gml:MultiSurface`` wrapped in its property type.

    Each polygon is converted to a ``gml:Polygon`` whose ``gml:id`` is
    ``"{gml_id}_poly_{index}"`` (1-based). ``srs_name`` / ``srs_dimension``
    are written on the outer ``gml:MultiSurface`` only; ``gml:posList`` does
    not repeat them (GML 3.1.1 inherits the frame).
    """
    members = [
        SurfaceMember(polygon=build_polygon(f"{gml_id}_poly_{index}", polygon))
        for index, polygon in enumerate(polygons, start=1)
    ]
    return MultiSurfacePropertyType(
        multi_surface=MultiSurface(
            id=gml_id,
            srs_name_attribute=srs_name,
            srs_dimension=srs_dimension,
            surface_member=members,
        ),
    )


def build_solid(
    gml_id: str,
    polygons: list[GeometryPolygon],
    *,
    srs_name: str,
    srs_dimension: int,
    orient: bool = True,
) -> SolidPropertyType:
    """Build a ``gml:Solid`` whose exterior shell is a ``gml:CompositeSurface``.

    When *orient* is ``True`` (the default), polygons are re-oriented outward
    via :func:`orient_solid_polygons` before assembly: shared surfaces between
    adjacent zones often arrive with inward-facing normals because they were
    authored from the neighbouring zone's perspective. Pass ``orient=False``
    when the source is already known-outward (3DBAG CityJSON LoD 1/2), because
    the centroid heuristic can mis-flip walls on concave facades and so
    produces inward-facing faces that viewers back-face-cull.
    """
    oriented = orient_solid_polygons(polygons) if orient else polygons
    members = [
        SurfaceMember(polygon=build_polygon(f"{gml_id}_poly_{index}", polygon))
        for index, polygon in enumerate(oriented, start=1)
    ]
    return SolidPropertyType(
        solid=Solid(
            id=gml_id,
            srs_name_attribute=srs_name,
            srs_dimension=srs_dimension,
            exterior=SurfacePropertyType(
                composite_surface=CompositeSurface(
                    id=f"{gml_id}_shell",
                    surface_member=members,
                ),
            ),
        ),
    )


def build_polygon(polygon_id: str, polygon_geometry: GeometryPolygon) -> Polygon:
    """Build a ``gml:Polygon`` with one exterior ring and zero-or-more holes."""
    exterior = Exterior(
        linear_ring=LinearRing(
            pos_list=PosList(value=flatten_ring(polygon_geometry.exterior)),
        ),
    )
    interiors = [
        Interior(
            linear_ring=LinearRing(
                pos_list=PosList(value=flatten_ring(interior_geometry)),
            ),
        )
        for interior_geometry in polygon_geometry.interiors
    ]
    return Polygon(id=polygon_id, exterior=exterior, interior=interiors)


def build_multi_point(
    gml_id: str,
    points: list[tuple[float, ...]],
    *,
    srs_name: str,
    srs_dimension: int,
) -> MultiPointPropertyType:
    """Build a ``gml:MultiPoint`` wrapped in its property type.

    Each point becomes one ``gml:Point`` wrapped in a ``gml:pointMember``.
    Every point's coordinate list is padded to *srs_dimension* with zeros
    when shorter. BAG's VBO ``geometriePunt`` is 2D, but the enclosing
    CityGML file typically carries a 3D compound CRS; writing ``z = 0``
    keeps the per-element ``srsDimension`` consistent with the file-level
    CRS and avoids a mixed-dimension MultiPoint (which the GML 3.1.1
    spec permits but many readers reject).

    Each member ``gml:Point`` gets id ``"{gml_id}_pt_{index}"`` (1-based)
    so every point is individually addressable (appearance targeting,
    cross-document links, etc.).
    """
    members = []
    for index, coords in enumerate(points, start=1):
        padded = list(coords) + [0.0] * max(0, srs_dimension - len(coords))
        padded = [_q(v) for v in padded[:srs_dimension]]
        members.append(
            PointMember(
                point=Point(
                    id=f"{gml_id}_pt_{index}",
                    srs_name_attribute=srs_name,
                    srs_dimension=srs_dimension,
                    pos=Pos(value=padded, srs_dimension=srs_dimension),
                ),
            )
        )
    return MultiPointPropertyType(
        multi_point=MultiPoint(
            id=gml_id,
            srs_name_attribute=srs_name,
            srs_dimension=srs_dimension,
            point_member=members,
        ),
    )


def build_envelope(
    coordinates: list[Coord3D],
    *,
    srs_name: str,
    srs_dimension: int,
) -> Envelope:
    """Return a ``gml:Envelope`` covering every coordinate in *coordinates*.

    Single-pass min/max scan. ``zip(*coordinates)`` + per-axis
    ``min``/``max`` would walk the list four times and materialise
    three throwaway tuples of length ``N``.
    """
    if not coordinates:
        raise ValueError("Envelope requires at least one coordinate")
    min_x = min_y = min_z = inf
    max_x = max_y = max_z = -inf
    for x, y, z in coordinates:
        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y
        if z < min_z:
            min_z = z
        if z > max_z:
            max_z = z
    return Envelope(
        lower_corner=DirectPositionType(
            value=[_q(min_x), _q(min_y), _q(min_z)], srs_dimension=srs_dimension
        ),
        upper_corner=DirectPositionType(
            value=[_q(max_x), _q(max_y), _q(max_z)], srs_dimension=srs_dimension
        ),
        srs_name=srs_name,
        srs_dimension=srs_dimension,
    )


# ---------------------------------------------------------------------------
# Ring helpers & orientation math
# ---------------------------------------------------------------------------


def flatten_ring(ring: list[Coord3D]) -> list[float]:
    """Close a ring (first == last) and flatten into ``gml:posList`` floats.

    A ring with a single vertex is rejected: every GML polygon needs at
    least three points plus a closing vertex to be well-formed.

    Uses :func:`itertools.chain.from_iterable` (C-level) to flatten
    rather than a nested ``[v for c in coords for v in c]``
    comprehension, which would do tuple unpacking in bytecode per
    coord.
    """
    if not ring:
        raise ValueError("Geometry rings must contain at least one coordinate")
    if points_close(ring[0], ring[-1]):
        return [_q(v) for v in chain.from_iterable(ring)]
    # Closed form: append the first point to the tail via chain, no copy.
    return [_q(v) for v in chain.from_iterable(ring)] + [_q(v) for v in ring[0]]


def open_ring(ring: list[Coord3D]) -> list[Coord3D]:
    """Return *ring* without its closing duplicate vertex, as a new list.

    Always returns a new list (never the input reference) so callers that
    iterate or mutate the result cannot accidentally affect the original
    polygon storage.
    """
    if len(ring) > 1 and points_close(ring[0], ring[-1]):
        return list(ring[:-1])
    return list(ring)


def orient_solid_polygons(polygons: list[GeometryPolygon]) -> list[GeometryPolygon]:
    """Return *polygons* with every face's normal pointing outward.

    For each polygon:

    1. compute the Newell normal of its exterior ring;
    2. compute the vector from the solid's centroid (mean of all exterior
       vertices across every polygon) to the face's own centroid;
    3. if the two point in opposite directions (dot < 0), reverse every
       ring on that polygon.

    Degenerate inputs (empty, single-point) fall through unchanged so
    callers can produce diagnostic errors downstream.
    """
    exterior_vertices = [open_ring(polygon.exterior) for polygon in polygons]

    all_vertices = [v for ring in exterior_vertices for v in ring]
    if not all_vertices:
        return polygons

    centroid = mean_point(all_vertices)

    oriented: list[GeometryPolygon] = []
    for polygon, vertices in zip(polygons, exterior_vertices, strict=True):
        normal = newell_normal(vertices)
        center = mean_point(vertices)
        dot = (
            normal[0] * (center[0] - centroid[0])
            + normal[1] * (center[1] - centroid[1])
            + normal[2] * (center[2] - centroid[2])
        )
        if dot < 0:
            oriented.append(
                GeometryPolygon(
                    exterior=list(reversed(polygon.exterior)),
                    interiors=[list(reversed(i)) for i in polygon.interiors],
                )
            )
        else:
            oriented.append(polygon)

    return oriented


def newell_normal(vertices: list[Coord3D]) -> Coord3D:
    """Return the unnormalised Newell normal of *vertices* (a planar ring).

    Works for non-convex rings and is numerically well-behaved for the
    near-planar faces typical of STEP output; callers that care about
    direction only (as :func:`orient_solid_polygons` does) do not need
    the magnitude.
    """
    nx, ny, nz = 0.0, 0.0, 0.0
    count = len(vertices)
    for i in range(count):
        curr = vertices[i]
        nxt = vertices[(i + 1) % count]
        nx += (curr[1] - nxt[1]) * (curr[2] + nxt[2])
        ny += (curr[2] - nxt[2]) * (curr[0] + nxt[0])
        nz += (curr[0] - nxt[0]) * (curr[1] + nxt[1])
    return (nx, ny, nz)


def planar_surface_attributes(
    polygon_geometry: GeometryPolygon,
) -> tuple[float, float | None, float] | None:
    """Return ``(area_m2, azimuth_deg | None, inclination_deg)`` for *polygon_geometry*.

    Pure 3D geometry. The returned values are exactly what the
    Energy ADE 3.0 ``bdgBdrySurfTotalSurfaceArea``,
    ``bdgBdrySurfAzimuth``, and ``bdgBdrySurfInclination`` elements
    encode for a planar boundary surface; the schema mapping itself
    lives at the call site (the city-builder building module). This
    function is namespace-free so it stays usable for any future caller
    that needs the same per-surface descriptors (per-building input
    LoD 3, vegetation surfaces, …).

    The exterior ring's Newell normal is used as the surface's outward
    normal, **without flipping**. This relies on the CityJSON / 3DBAG
    convention that exterior rings wind counter-clockwise viewed from
    outside the solid, so the Newell normal already points outward
    (down for a GroundSurface, horizontally for a WallSurface, up for a
    RoofSurface). Inverting based on a centroid heuristic — as
    :func:`orient_solid_polygons` does for solid assembly — would
    flatten the up/down distinction this function exists to expose.

    *area_m2* is ``|N(exterior)| / 2`` minus ``|N(hole_i)| / 2`` for
    every interior ring, matching the GML 3.1.1 polygon-with-holes
    area definition. Holes must be co-planar with the exterior (a GML
    requirement); this function does not re-validate that.

    *inclination_deg* is the angle between the outward normal and the
    +Z axis, in ``[0, 180]``: ``0`` for a flat roof, ``90`` for a
    vertical wall, ``180`` for a horizontal floor / ground slab whose
    outward normal points down.

    *azimuth_deg* is the compass bearing (``0`` = N, ``90`` = E,
    clockwise from north) of the outward normal's horizontal
    component, in ``[0, 360)``. Returned as ``None`` when the surface
    is effectively horizontal: azimuth is geometrically undefined
    there and the corresponding GML element should simply be omitted.

    Returns ``None`` for a degenerate (collinear / zero-area) polygon
    so the caller can drop the surface attribute attachment without
    emitting a divide-by-zero NaN.
    """
    nx, ny, nz = newell_normal(polygon_geometry.exterior)
    mag = sqrt(nx * nx + ny * ny + nz * nz)
    if mag < _DEGENERATE_AREA_EPS:
        return None

    area_exterior = mag / 2.0
    area_holes = 0.0
    for ring in polygon_geometry.interiors:
        hx, hy, hz = newell_normal(ring)
        area_holes += sqrt(hx * hx + hy * hy + hz * hz) / 2.0
    area_m2 = area_exterior - area_holes
    if area_m2 < 0.0:
        # A hole larger than the exterior would invert the polygon's
        # net area. GML 3.1.1 forbids that, so any such input is
        # pathological; clamp to 0 rather than ship a negative area.
        area_m2 = 0.0

    n_z = nz / mag
    if n_z > 1.0:
        n_z = 1.0
    elif n_z < -1.0:
        n_z = -1.0
    inclination_deg = degrees(acos(n_z))

    n_x = nx / mag
    n_y = ny / mag
    horizontal2 = n_x * n_x + n_y * n_y
    if horizontal2 < _HORIZONTAL_NORMAL_EPS:
        azimuth_deg: float | None = None
    else:
        # ``atan2(n_x, n_y)`` gives the clockwise angle from +Y (north)
        # by construction, which is exactly the compass bearing convention
        # the existing PV pipeline uses (see ``solar_panels._azimuth_from_normal``).
        azimuth_deg = (degrees(atan2(n_x, n_y)) + 360.0) % 360.0

    return area_m2, azimuth_deg, inclination_deg


def mean_point(points: list[Coord3D]) -> Coord3D:
    """Return the component-wise mean of *points*. Requires a non-empty list."""
    n = len(points)
    if n == 0:
        raise ValueError("mean_point requires at least one point")
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )
