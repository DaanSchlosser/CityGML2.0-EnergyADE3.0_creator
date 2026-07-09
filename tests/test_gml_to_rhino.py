"""Tests for the CityGML -> Rhino ``.3dm`` exporter (tools/gml_to_rhino.py).

The geometry helpers (posList parsing, colour parsing, triangulation) are
pure Python and always run. Triangulation of concave / holed polygons needs
Shapely, and the end-to-end convert/read-back needs rhino3dm; both are the
optional ``rhino`` extra and are skipped when absent.
"""

from __future__ import annotations

import math

import pytest

from tools.gml_to_rhino import (
    _newell_normal,
    _parse_colour,
    _parse_poslist,
    _to_byte,
    _triangulate,
    convert,
)

Point = tuple[float, float, float]


def _tri_area(a: Point, b: Point, c: Point) -> float:
    """Area of a 3D triangle via half the cross-product magnitude."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


def _polygon_area(ring: list[Point]) -> float:
    """Planar polygon area = half the Newell normal magnitude."""
    nx, ny, nz = _newell_normal(ring)
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def _triangulated_area(exterior: list[Point], holes: list[list[Point]]) -> float:
    return sum(_tri_area(*tri) for tri in _triangulate(exterior, holes))


# ── pure-Python helpers ─────────────────────────────────────────────────


def test_parse_poslist_drops_closing_duplicate() -> None:
    pts = _parse_poslist("0 0 0 1 0 0 1 1 0 0 0 0")
    assert pts == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)]


def test_parse_poslist_keeps_open_ring() -> None:
    pts = _parse_poslist("0 0 5 3 0 5 3 4 5")
    assert pts == [(0.0, 0.0, 5.0), (3.0, 0.0, 5.0), (3.0, 4.0, 5.0)]


def test_parse_colour_scales_and_clamps() -> None:
    assert _parse_colour("1.0 1.0 1.0") == (255, 255, 255)
    assert _parse_colour("0.98 0.78 0.42") == (250, 199, 107)
    assert _parse_colour("0 0 0") == (0, 0, 0)


def test_to_byte_clamps_out_of_range() -> None:
    assert _to_byte(-0.5) == 0
    assert _to_byte(2.0) == 255


# ── triangulation ───────────────────────────────────────────────────────


def test_triangulate_quad_is_two_triangles() -> None:
    quad: list[Point] = [(0, 0, 0), (2, 0, 0), (2, 3, 0), (0, 3, 0)]
    tris = list(_triangulate(quad, []))
    assert len(tris) == 2
    assert math.isclose(sum(_tri_area(*t) for t in tris), 6.0)


def test_triangulate_vertical_wall_quad() -> None:
    # a wall stands in the x-z plane; the fan path must keep its 3D area
    wall: list[Point] = [(0, 0, 0), (4, 0, 0), (4, 0, 2.5), (0, 0, 2.5)]
    assert math.isclose(_triangulated_area(wall, []), 10.0)


def test_triangulate_concave_conserves_area() -> None:
    pytest.importorskip("shapely")
    # L-shape: 2x2 square minus the top-right 1x1 notch -> area 3
    l_shape: list[Point] = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
    assert math.isclose(_triangulated_area(l_shape, []), _polygon_area(l_shape))
    assert math.isclose(_triangulated_area(l_shape, []), 3.0)


def test_triangulate_tilted_concave_conserves_area() -> None:
    pytest.importorskip("shapely")
    # same L-shape lifted onto the 45-degree plane z = x: area scales by sqrt(2),
    # which only comes out right if the inverse projection (to3d) is exact
    flat = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
    l_shape: list[Point] = [(x, y, x) for (x, y) in flat]
    assert math.isclose(_triangulated_area(l_shape, []), 3.0 * math.sqrt(2), rel_tol=1e-9)


def test_triangulate_polygon_with_hole() -> None:
    pytest.importorskip("shapely")
    outer: list[Point] = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
    hole: list[Point] = [(3, 3, 0), (7, 3, 0), (7, 7, 0), (3, 7, 0)]
    assert math.isclose(_triangulated_area(outer, [hole]), 100.0 - 16.0)


# ── end-to-end ──────────────────────────────────────────────────────────

_GML = """<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel
    xmlns:core="http://www.opengis.net/citygml/2.0"
    xmlns:gml="http://www.opengis.net/gml"
    xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
    xmlns:luse="http://www.opengis.net/citygml/landuse/2.0"
    xmlns:app="http://www.opengis.net/citygml/appearance/2.0">
  <gml:boundedBy>
    <gml:Envelope srsDimension="3">
      <gml:lowerCorner>1000 2000 0</gml:lowerCorner>
      <gml:upperCorner>1010 2010 5</gml:upperCorner>
    </gml:Envelope>
  </gml:boundedBy>
  <app:appearanceMember>
    <app:Appearance>
      <app:theme>buildingHighlight</app:theme>
      <app:surfaceDataMember>
        <app:X3DMaterial>
          <app:diffuseColor>1.0 0.0 0.0</app:diffuseColor>
          <app:target>#roof_ms</app:target>
        </app:X3DMaterial>
      </app:surfaceDataMember>
    </app:Appearance>
  </app:appearanceMember>
  <core:cityObjectMember>
    <bldg:Building gml:id="b1">
      <bldg:boundedBy>
        <bldg:RoofSurface gml:id="roof">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface gml:id="roof_ms">
              <gml:surfaceMember>
                <gml:Polygon gml:id="roof_poly">
                  <gml:exterior><gml:LinearRing>
                    <gml:posList>1000 2000 5 1004 2000 5 1004 2004 5 1000 2004 5 1000 2000 5</gml:posList>
                  </gml:LinearRing></gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:RoofSurface>
      </bldg:boundedBy>
      <bldg:boundedBy>
        <bldg:WallSurface gml:id="wall">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface gml:id="wall_ms">
              <gml:surfaceMember>
                <gml:Polygon gml:id="wall_poly">
                  <gml:exterior><gml:LinearRing>
                    <gml:posList>1000 2000 0 1004 2000 0 1004 2000 5 1000 2000 5 1000 2000 0</gml:posList>
                  </gml:LinearRing></gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:WallSurface>
      </bldg:boundedBy>
    </bldg:Building>
  </core:cityObjectMember>
  <core:cityObjectMember>
    <luse:LandUse gml:id="lu1">
      <luse:lod1MultiSurface>
        <gml:MultiSurface gml:id="lu1_ms">
          <gml:surfaceMember>
            <gml:Polygon gml:id="lu1_poly">
              <gml:exterior><gml:LinearRing>
                <gml:posList>1000 2000 0 1010 2000 0 1010 2010 0 1000 2010 0 1000 2000 0</gml:posList>
              </gml:LinearRing></gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </luse:lod1MultiSurface>
    </luse:LandUse>
  </core:cityObjectMember>
</core:CityModel>
"""


def _layer_path(model, layer) -> str:
    by_id = {str(lyr.Id): lyr for lyr in model.Layers}
    root = "00000000-0000-0000-0000-000000000000"
    names = [layer.Name]
    parent = str(layer.ParentLayerId)
    while parent != root and parent in by_id:
        names.append(by_id[parent].Name)
        parent = str(by_id[parent].ParentLayerId)
    return "::".join(reversed(names))


def test_convert_end_to_end(tmp_path) -> None:
    rhino3dm = pytest.importorskip("rhino3dm")
    gml_path = tmp_path / "mini.gml"
    gml_path.write_text(_GML, encoding="utf-8")
    out_path = tmp_path / "mini.3dm"

    stats = convert(gml_path, out_path, verbose=False)
    assert stats["objects"] == 3  # roof brep + wall brep + landuse mesh
    assert stats["breps"] == 2  # both building surfaces are clean Breps
    assert stats["building_mesh_fallback"] == 0  # neither is holed
    assert stats["skipped_geometry"] == 0
    assert out_path.is_file()

    model = rhino3dm.File3dm.Read(str(out_path))
    layers = {_layer_path(model, lyr) for lyr in model.Layers}
    assert {"Buildings::RoofSurface", "Buildings::WallSurface", "LandCover::LandUse"} <= layers

    by_layer = {}
    for obj in model.Objects:
        path = _layer_path(model, model.Layers[obj.Attributes.LayerIndex])
        by_layer[path] = obj

    # building surfaces are Breps; landcover stays a mesh (context)
    assert type(by_layer["Buildings::RoofSurface"].Geometry).__name__ == "Brep"
    assert type(by_layer["Buildings::WallSurface"].Geometry).__name__ == "Brep"
    assert type(by_layer["LandCover::LandUse"].Geometry).__name__ == "Mesh"

    # the roof is targeted by the red X3DMaterial; the wall has no material and
    # falls back to the wall default; landuse falls back to the landuse default
    assert tuple(by_layer["Buildings::RoofSurface"].Attributes.ObjectColor[:3]) == (255, 0, 0)
    assert tuple(by_layer["Buildings::WallSurface"].Attributes.ObjectColor[:3]) == (230, 225, 215)
    assert tuple(by_layer["LandCover::LandUse"].Attributes.ObjectColor[:3]) == (200, 190, 150)

    # both building faces share one group named for the building; landcover is ungrouped
    roof_groups = by_layer["Buildings::RoofSurface"].Attributes.GetGroupList()
    wall_groups = by_layer["Buildings::WallSurface"].Attributes.GetGroupList()
    assert roof_groups and tuple(roof_groups) == tuple(wall_groups)  # same single group
    assert not by_layer["LandCover::LandUse"].Attributes.GetGroupList()
    assert model.Groups.FindIndex(roof_groups[0]).Name == "Building b1"

    # the offset is recoverable from the model base point (floored lower corner)
    base = model.Settings.ModelBasePoint
    assert (base.X, base.Y, base.Z) == (1000.0, 2000.0, 0.0)

    # coordinates were translated to that local origin
    bbox_max_x = max(obj.Geometry.GetBoundingBox().Max.X for obj in model.Objects)
    assert bbox_max_x < 100  # ~10 m, not ~1010


_GML_HOLED = """<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel
    xmlns:core="http://www.opengis.net/citygml/2.0"
    xmlns:gml="http://www.opengis.net/gml"
    xmlns:bldg="http://www.opengis.net/citygml/building/2.0">
  <core:cityObjectMember>
    <bldg:Building gml:id="b9">
      <bldg:boundedBy>
        <bldg:GroundSurface gml:id="g">
          <bldg:lod2MultiSurface>
            <gml:MultiSurface gml:id="g_ms">
              <gml:surfaceMember>
                <gml:Polygon gml:id="g_poly">
                  <gml:exterior><gml:LinearRing>
                    <gml:posList>0 0 0 10 0 0 10 10 0 0 10 0 0 0 0</gml:posList>
                  </gml:LinearRing></gml:exterior>
                  <gml:interior><gml:LinearRing>
                    <gml:posList>3 3 0 7 3 0 7 7 0 3 7 0 3 3 0</gml:posList>
                  </gml:LinearRing></gml:interior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:MultiSurface>
          </bldg:lod2MultiSurface>
        </bldg:GroundSurface>
      </bldg:boundedBy>
    </bldg:Building>
  </core:cityObjectMember>
</core:CityModel>
"""


def test_holed_building_surface_falls_back_to_mesh(tmp_path) -> None:
    rhino3dm = pytest.importorskip("rhino3dm")
    pytest.importorskip("shapely")  # the fallback triangulates the hole
    gml_path = tmp_path / "holed.gml"
    gml_path.write_text(_GML_HOLED, encoding="utf-8")
    out_path = tmp_path / "holed.3dm"

    stats = convert(gml_path, out_path, verbose=False)
    assert stats["breps"] == 0  # a holed polygon cannot be a trimmed-plane Brep
    assert stats["building_mesh_fallback"] == 1
    assert stats["objects"] == 1

    model = rhino3dm.File3dm.Read(str(out_path))
    obj = next(iter(model.Objects))
    assert type(obj.Geometry).__name__ == "Mesh"
    # the hole is preserved: area is 100 - 16 = 84, not the solid 100
    mesh = obj.Geometry
    area = _mesh_area(mesh)
    assert math.isclose(area, 84.0, abs_tol=1e-6)
    # still grouped as a building
    assert obj.Attributes.GetGroupList()


def _mesh_area(mesh) -> float:
    """Total area of a rhino3dm triangle/quad mesh."""
    total = 0.0
    verts = [
        (mesh.Vertices[i].X, mesh.Vertices[i].Y, mesh.Vertices[i].Z)
        for i in range(len(mesh.Vertices))
    ]
    for i in range(mesh.Faces.Count):
        f = mesh.Faces[i]
        idx = list(dict.fromkeys(f))  # A,B,C,(D) with D==C for triangles
        for k in range(1, len(idx) - 1):
            total += _tri_area(verts[idx[0]], verts[idx[k]], verts[idx[k + 1]])
    return total
