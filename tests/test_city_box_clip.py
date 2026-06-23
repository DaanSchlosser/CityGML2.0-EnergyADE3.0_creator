"""Tests for the box clip: cut-and-cap building solids, surface landcover clip."""

from __future__ import annotations

from collections import Counter

import pytest

from citygml_energy._step import GeometryPolygon
from citygml_energy.city_builder.box_clip import (
    _key,
    clip_building_to_box,
    clip_landcover_polygons,
)
from citygml_energy.city_builder.cityjson_parse import ParsedBuilding, SemanticPolygon

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extrude(
    footprint_ccw: list[tuple[float, float]],
    z0: float,
    z1: float,
    surface_type: str | None = None,
) -> list[SemanticPolygon]:
    """A coherently outward-oriented prism over a CCW footprint between z0 and z1.

    Bottom face is the reversed footprint (normal down), top is the footprint
    (normal up), and each wall rises from a footprint edge; for a CCW footprint
    that yields outward-facing walls, so the prism is a closed oriented
    manifold the cap assembly can rely on.
    """
    faces: list[SemanticPolygon] = []
    bottom = [(x, y, z0) for (x, y) in reversed(footprint_ccw)]
    top = [(x, y, z1) for (x, y) in footprint_ccw]
    faces.append(
        SemanticPolygon(polygon=GeometryPolygon(exterior=bottom), surface_type="GroundSurface")
    )
    faces.append(SemanticPolygon(polygon=GeometryPolygon(exterior=top), surface_type="RoofSurface"))
    n = len(footprint_ccw)
    for i in range(n):
        ax, ay = footprint_ccw[i]
        bx, by = footprint_ccw[(i + 1) % n]
        wall = [(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)]
        faces.append(
            SemanticPolygon(polygon=GeometryPolygon(exterior=wall), surface_type=surface_type)
        )
    return faces


def _undirected_edges(faces: list[SemanticPolygon]) -> Counter:
    counts: Counter = Counter()
    for face in faces:
        ring = face.polygon.exterior
        n = len(ring)
        for i in range(n):
            a = _key(ring[i])
            b = _key(ring[(i + 1) % n])
            if a == b:
                continue
            counts[tuple(sorted((a, b)))] += 1
    return counts


def _directed_edges(faces: list[SemanticPolygon]) -> Counter:
    counts: Counter = Counter()
    for face in faces:
        ring = face.polygon.exterior
        n = len(ring)
        for i in range(n):
            a = _key(ring[i])
            b = _key(ring[(i + 1) % n])
            if a == b:
                continue
            counts[(a, b)] += 1
    return counts


def _assert_watertight(faces: list[SemanticPolygon]) -> None:
    """Every edge is shared by exactly two faces, traversed in opposite ways."""
    undirected = _undirected_edges(faces)
    assert undirected, "no edges at all"
    bad = {edge: c for edge, c in undirected.items() if c != 2}
    assert not bad, f"non-manifold edges (count != 2): {bad}"
    directed = _directed_edges(faces)
    for (a, b), c in directed.items():
        assert c == 1, f"directed edge {a}->{b} repeated {c}x"
        assert directed[(b, a)] == 1, f"edge {a}->{b} lacks its opposite"


def _xy_bounds(faces: list[SemanticPolygon]) -> tuple[float, float, float, float]:
    xs = [x for f in faces for (x, _y, _z) in f.polygon.exterior]
    ys = [y for f in faces for (_x, y, _z) in f.polygon.exterior]
    return (min(xs), min(ys), max(xs), max(ys))


_UNIT_FOOTPRINT = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def _prism_building(surface_type: str | None = None) -> ParsedBuilding:
    return ParsedBuilding(
        pand_id="test",
        attributes={},
        geometries={"1": _extrude(_UNIT_FOOTPRINT, 0.0, 5.0, surface_type)},
    )


# ---------------------------------------------------------------------------
# Sanity: the synthetic prism is itself watertight
# ---------------------------------------------------------------------------


def test_synthetic_prism_is_watertight() -> None:
    _assert_watertight(_extrude(_UNIT_FOOTPRINT, 0.0, 5.0))


# ---------------------------------------------------------------------------
# Building clip: inside / outside / straddle
# ---------------------------------------------------------------------------


def test_building_fully_inside_is_returned_unchanged() -> None:
    pb = _prism_building()
    clipped = clip_building_to_box(pb, (-1.0, -1.0, 11.0, 11.0))
    assert clipped is pb  # identity: no geometry work for an inside building


def test_building_fully_outside_is_dropped() -> None:
    pb = _prism_building()
    assert clip_building_to_box(pb, (100.0, 100.0, 200.0, 200.0)) is None


def test_straddler_is_cut_and_capped_watertight() -> None:
    pb = _prism_building()
    # Keep x <= 5: the box cuts the prism in half along x.
    clipped = clip_building_to_box(pb, (-100.0, -100.0, 5.0, 100.0))
    assert clipped is not None
    faces = clipped.geometries["1"]
    _assert_watertight(faces)
    xmin, ymin, xmax, ymax = _xy_bounds(faces)
    assert xmin == pytest.approx(0.0)
    assert xmax == pytest.approx(5.0)
    assert ymin == pytest.approx(0.0)
    assert ymax == pytest.approx(10.0)


def test_straddler_cap_lies_on_the_cut_plane() -> None:
    pb = _prism_building()
    clipped = clip_building_to_box(pb, (-100.0, -100.0, 5.0, 100.0))
    assert clipped is not None
    faces = clipped.geometries["1"]
    # Exactly one new cap face: every vertex on x == 5, spanning the full height.
    caps = [f for f in faces if all(abs(x - 5.0) < 1e-6 for (x, _y, _z) in f.polygon.exterior)]
    assert len(caps) == 1
    cap = caps[0]
    zs = [z for (_x, _y, z) in cap.polygon.exterior]
    assert min(zs) == pytest.approx(0.0)
    assert max(zs) == pytest.approx(5.0)
    assert cap.surface_type == "WallSurface"


def test_corner_cut_by_two_planes_is_watertight() -> None:
    pb = _prism_building()
    # Keep the upper-right quarter (x >= 5 and y >= 5): two cap planes.
    clipped = clip_building_to_box(pb, (5.0, 5.0, 100.0, 100.0))
    assert clipped is not None
    faces = clipped.geometries["1"]
    _assert_watertight(faces)
    xmin, ymin, xmax, ymax = _xy_bounds(faces)
    assert (xmin, ymin, xmax, ymax) == pytest.approx((5.0, 5.0, 10.0, 10.0))


def test_lod2_surface_types_preserved_on_kept_faces() -> None:
    # A semantic prism: ground/roof keep their types, the cut adds a wall cap.
    pb = ParsedBuilding(
        pand_id="t",
        attributes={},
        geometries={"2": _extrude(_UNIT_FOOTPRINT, 0.0, 5.0, surface_type="WallSurface")},
    )
    clipped = clip_building_to_box(pb, (-100.0, -100.0, 5.0, 100.0))
    assert clipped is not None
    types = {f.surface_type for f in clipped.geometries["2"]}
    assert "RoofSurface" in types
    assert "GroundSurface" in types
    assert "WallSurface" in types


# ---------------------------------------------------------------------------
# Footprint (LoD 0) clip: open surface, no cap
# ---------------------------------------------------------------------------


def test_lod0_footprint_clipped_without_cap() -> None:
    footprint = [
        SemanticPolygon(
            polygon=GeometryPolygon(
                exterior=[(0.0, 0.0, 2.0), (10.0, 0.0, 2.0), (10.0, 10.0, 2.0), (0.0, 10.0, 2.0)]
            ),
            surface_type="GroundSurface",
        )
    ]
    pb = ParsedBuilding(pand_id="t", attributes={}, geometries={"0": footprint})
    clipped = clip_building_to_box(pb, (-100.0, -100.0, 5.0, 100.0))
    assert clipped is not None
    faces = clipped.geometries["0"]
    assert len(faces) == 1  # one open surface, no added cap
    xmax = max(x for (x, _y, _z) in faces[0].polygon.exterior)
    assert xmax == pytest.approx(5.0)
    # The constant footprint z survives the clip.
    assert all(z == pytest.approx(2.0) for (_x, _y, z) in faces[0].polygon.exterior)


# ---------------------------------------------------------------------------
# Landcover surface clip: 3D edge interpolation, z kept exact at any tilt
# ---------------------------------------------------------------------------


def test_landcover_clip_interpolates_z_along_edges() -> None:
    # A sloped facet z = 0.1 * x: a new vertex on the x == 5 edge takes its z by
    # interpolation along the original edge, so z == 0.1 * x everywhere.
    poly = GeometryPolygon(
        exterior=[(0.0, 0.0, 0.0), (10.0, 0.0, 1.0), (10.0, 10.0, 1.0), (0.0, 10.0, 0.0)]
    )
    out = clip_landcover_polygons([poly], (-100.0, -100.0, 5.0, 100.0))
    assert len(out) == 1
    xs = [x for (x, _y, _z) in out[0].exterior]
    assert max(xs) == pytest.approx(5.0)
    for x, _y, z in out[0].exterior:
        assert z == pytest.approx(0.1 * x, abs=1e-6)


def test_landcover_inside_box_preserves_exact_z() -> None:
    # A warped (non-planar) facet wholly inside the box must pass through with
    # its z untouched. The previous best-fit-plane restore silently reshaped it.
    poly = GeometryPolygon(
        exterior=[(1.0, 1.0, 0.0), (2.0, 1.0, 9.0), (2.0, 2.0, 3.0), (1.0, 2.0, 1.0)]
    )
    out = clip_landcover_polygons([poly], (0.0, 0.0, 10.0, 10.0))
    assert len(out) == 1
    assert out[0].exterior == poly.exterior


def test_landcover_clip_never_extrapolates_z_on_steep_facet() -> None:
    # A near-vertical facet projects to a thin sliver in 2D, where a plane fit
    # is ill-conditioned and used to extrapolate a tall z spike. The 3D edge
    # clip keeps every output z inside the facet's own z-range. Regression for
    # a 3DBV PlantCover facet that clipped to a 92 m spike from a 5 m source.
    poly = GeometryPolygon(
        exterior=[(0.0, 0.0, 0.0), (0.0, 20.0, 0.0), (0.02, 20.0, 5.0), (0.02, 0.0, 5.0)]
    )
    src_lo = min(z for (_x, _y, z) in poly.exterior)
    src_hi = max(z for (_x, _y, z) in poly.exterior)
    out = clip_landcover_polygons([poly], (-100.0, -100.0, 100.0, 5.0))  # cut at y == 5
    zs = [z for p in out for (_x, _y, z) in p.exterior]
    assert zs
    assert min(zs) >= src_lo - 1e-6
    assert max(zs) <= src_hi + 1e-6


def test_landcover_outside_box_yields_nothing() -> None:
    poly = GeometryPolygon(
        exterior=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    )
    assert clip_landcover_polygons([poly], (50.0, 50.0, 60.0, 60.0)) == []


def test_landcover_inside_box_is_unchanged_area() -> None:
    poly = GeometryPolygon(
        exterior=[(1.0, 1.0, 3.0), (2.0, 1.0, 3.0), (2.0, 2.0, 3.0), (1.0, 2.0, 3.0)]
    )
    out = clip_landcover_polygons([poly], (0.0, 0.0, 10.0, 10.0))
    assert len(out) == 1
    assert all(z == pytest.approx(3.0) for (_x, _y, z) in out[0].exterior)
