"""Unit tests for pure GML primitive builders and 3D-math helpers.

These tests protect the geometry layer's foundation from regression:
ring closure, polygon orientation, and envelope computation are all
numerically sensitive and hard to debug once they show up as "the GML
doesn't validate" downstream.
"""

from __future__ import annotations

import pytest

from citygml_energy._gml_builders import (
    build_envelope,
    build_multi_surface,
    build_polygon,
    build_solid,
    flatten_ring,
    mean_point,
    newell_normal,
    open_ring,
    orient_solid_polygons,
)
from citygml_energy._step import GeometryPolygon

_SRS = "urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109"


# ---------------------------------------------------------------------------
# flatten_ring & open_ring
# ---------------------------------------------------------------------------


def test_flatten_ring_closes_an_open_ring() -> None:
    ring = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)]
    flat = flatten_ring(ring)
    # Closed: 4 vertices x 3 coords = 12 floats.
    assert len(flat) == 12
    assert flat[:3] == [0.0, 0.0, 0.0]
    assert flat[-3:] == [0.0, 0.0, 0.0]


def test_flatten_ring_leaves_already_closed_rings_alone() -> None:
    ring = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 0.0, 0.0)]
    flat = flatten_ring(ring)
    assert len(flat) == 12  # not duplicated further


def test_flatten_ring_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least one coordinate"):
        flatten_ring([])


def test_open_ring_always_returns_a_new_list() -> None:
    closed = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    result = open_ring(closed)
    assert result == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    assert result is not closed  # fresh list

    unclosed = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    result = open_ring(unclosed)
    assert result == unclosed
    assert result is not unclosed  # still a fresh list — prevents mutation leakage


# ---------------------------------------------------------------------------
# newell_normal / mean_point
# ---------------------------------------------------------------------------


def test_newell_normal_of_ccw_xy_square_points_up_z() -> None:
    # Counter-clockwise ring in the XY plane → +Z normal.
    ring = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    nx, ny, nz = newell_normal(ring)
    assert abs(nx) < 1e-9
    assert abs(ny) < 1e-9
    assert nz > 0


def test_newell_normal_of_cw_xy_square_points_down_z() -> None:
    ring = [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 0.0)]
    _, _, nz = newell_normal(ring)
    assert nz < 0


def test_mean_point_is_component_wise_average() -> None:
    assert mean_point([(0.0, 0.0, 0.0), (2.0, 4.0, 6.0)]) == (1.0, 2.0, 3.0)


def test_mean_point_rejects_empty() -> None:
    with pytest.raises(ValueError):
        mean_point([])


# ---------------------------------------------------------------------------
# orient_solid_polygons
# ---------------------------------------------------------------------------


def _unit_cube_polygons() -> list[GeometryPolygon]:
    """Six square faces of the unit cube, all CCW when viewed from outside."""
    # Corners of the unit cube.
    p = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),  # bottom
        (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),  # top
    ]
    return [
        GeometryPolygon(exterior=[p[0], p[3], p[2], p[1]]),  # bottom (-z, CCW from below)
        GeometryPolygon(exterior=[p[4], p[5], p[6], p[7]]),  # top    (+z, CCW from above)
        GeometryPolygon(exterior=[p[0], p[1], p[5], p[4]]),  # front  (-y)
        GeometryPolygon(exterior=[p[2], p[3], p[7], p[6]]),  # back   (+y)
        GeometryPolygon(exterior=[p[0], p[4], p[7], p[3]]),  # left   (-x)
        GeometryPolygon(exterior=[p[1], p[2], p[6], p[5]]),  # right  (+x)
    ]


def test_orient_solid_polygons_flips_inward_facing_faces() -> None:
    cube = _unit_cube_polygons()
    # Reverse one face — simulating an inward-facing shared wall.
    cube[0] = GeometryPolygon(exterior=list(reversed(cube[0].exterior)))
    oriented = orient_solid_polygons(cube)

    # All normals should now point away from the centroid (0.5, 0.5, 0.5).
    centroid = (0.5, 0.5, 0.5)
    for polygon in oriented:
        open_ext = open_ring(polygon.exterior)
        normal = newell_normal(open_ext)
        face_center = mean_point(open_ext)
        outward = (
            face_center[0] - centroid[0],
            face_center[1] - centroid[1],
            face_center[2] - centroid[2],
        )
        dot = normal[0] * outward[0] + normal[1] * outward[1] + normal[2] * outward[2]
        assert dot > 0, f"face with exterior {polygon.exterior} still points inward"


# ---------------------------------------------------------------------------
# build_* producing xsdata objects
# ---------------------------------------------------------------------------


def test_build_polygon_emits_interior_rings() -> None:
    polygon = GeometryPolygon(
        exterior=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (0.0, 4.0, 0.0)],
        interiors=[[(1.0, 1.0, 0.0), (2.0, 1.0, 0.0), (2.0, 2.0, 0.0), (1.0, 2.0, 0.0)]],
    )
    result = build_polygon("poly_1", polygon)
    assert result.id == "poly_1"
    assert len(result.interior) == 1
    # 4 exterior corners closed -> 5 pts, 3 coords each = 15 floats.
    assert len(result.exterior.linear_ring.pos_list.value) == 15


def test_build_multi_surface_sets_srs_on_outer_element_only() -> None:
    polygons = [
        GeometryPolygon(exterior=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)]),
    ]
    prop = build_multi_surface("ms_1", polygons, srs_name=_SRS, srs_dimension=3)
    multi = prop.multi_surface
    assert multi.id == "ms_1"
    assert multi.srs_name_attribute == _SRS
    assert multi.srs_dimension == 3
    assert len(multi.surface_member) == 1


def test_build_solid_wraps_in_composite_surface_shell() -> None:
    cube = _unit_cube_polygons()
    prop = build_solid("solid_1", cube, srs_name=_SRS, srs_dimension=3)
    shell = prop.solid.exterior.composite_surface
    assert shell.id == "solid_1_shell"
    assert len(shell.surface_member) == 6


def test_build_envelope_is_axis_aligned_bbox() -> None:
    coords = [(0.0, 0.0, 0.0), (5.0, 7.0, 9.0), (-1.0, 2.0, 3.0)]
    env = build_envelope(coords, srs_name=_SRS, srs_dimension=3)
    assert env.lower_corner.value == [-1.0, 0.0, 0.0]
    assert env.upper_corner.value == [5.0, 7.0, 9.0]
    assert env.srs_name == _SRS


def test_build_envelope_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        build_envelope([], srs_name=_SRS, srs_dimension=3)
