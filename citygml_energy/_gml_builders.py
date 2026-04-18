"""Pure GML primitive builders.

Turn flat coordinate lists into xsdata ``gml:Polygon`` / ``gml:MultiSurface``
/ ``gml:Solid`` / ``gml:Envelope`` objects. This module is the stable layer
that sits between the low-level STEP parser (:mod:`._step`) and the
schema-aware attachment code (:mod:`.geometry`):

* It knows about GML 3.1.1 wire types (``Polygon``, ``LinearRing``,
  ``PosList``, ``Envelope``, ``Solid``, ``CompositeSurface``, …) —
  these are expected to be stable across any CityGML-derived schema.
* It does **not** know about CityGML semantics (boundary surfaces,
  openings, solar panels) or JSON input format.

Functions here are the only place that constructs GML geometry elements,
so changes to the GML wire format stay localised. The module also exposes
the ring orientation and Newell-normal helpers used for solid assembly;
those are pure 3D-math utilities that deserve focused unit tests.
"""

from __future__ import annotations

from ._step import Coord3D, GeometryPolygon, points_close
from .bindings import (
    CompositeSurface,
    DirectPositionType,
    Envelope,
    Exterior,
    Interior,
    LinearRing,
    MultiSurface,
    MultiSurfacePropertyType,
    Polygon,
    PosList,
    Solid,
    SolidPropertyType,
    SurfaceMember,
    SurfacePropertyType,
)

__all__ = [
    "build_envelope",
    "build_multi_surface",
    "build_polygon",
    "build_solid",
    "flatten_ring",
    "mean_point",
    "newell_normal",
    "open_ring",
    "orient_solid_polygons",
]


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
) -> SolidPropertyType:
    """Build a ``gml:Solid`` whose exterior shell is a ``gml:CompositeSurface``.

    Polygons are re-oriented outward before assembly (see
    :func:`orient_solid_polygons`): shared surfaces between adjacent zones
    often arrive with inward-facing normals because they were authored from
    the neighbouring zone's perspective.
    """
    oriented = orient_solid_polygons(polygons)
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


def build_envelope(
    coordinates: list[Coord3D],
    *,
    srs_name: str,
    srs_dimension: int,
) -> Envelope:
    """Return a ``gml:Envelope`` covering every coordinate in *coordinates*."""
    if not coordinates:
        raise ValueError("Envelope requires at least one coordinate")
    xs, ys, zs = zip(*coordinates, strict=True)
    return Envelope(
        lower_corner=DirectPositionType(
            value=[min(xs), min(ys), min(zs)], srs_dimension=srs_dimension
        ),
        upper_corner=DirectPositionType(
            value=[max(xs), max(ys), max(zs)], srs_dimension=srs_dimension
        ),
        srs_name=srs_name,
        srs_dimension=srs_dimension,
    )


# ---------------------------------------------------------------------------
# Ring helpers & orientation math
# ---------------------------------------------------------------------------


def flatten_ring(ring: list[Coord3D]) -> list[float]:
    """Close a ring (first == last) and flatten into ``gml:posList`` floats.

    A ring with a single vertex is rejected — every GML polygon needs at
    least three points plus a closing vertex to be well-formed.
    """
    if not ring:
        raise ValueError("Geometry rings must contain at least one coordinate")
    coordinates = list(ring)
    if not points_close(coordinates[0], coordinates[-1]):
        coordinates.append(coordinates[0])
    return [value for coord in coordinates for value in coord]


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
