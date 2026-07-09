"""Convert a creator CityGML file into a Rhino 8 ``.3dm``, keeping the thematic
layers and the CityGML appearance colours.

Unlike the KITModelViewer STL export (raw triangle soup: no names, no grouping,
no colour), this writes a native Rhino file where

* each thematic surface type is its own nested layer
  (``Buildings::WallSurface``, ``LandCover::Road``, ``Vegetation::Trees`` ...),
* every object is coloured from the ``app:X3DMaterial`` ``diffuseColor`` that
  targets it (energy-label building highlight, landcover, vegetation), and
* surfaces with no appearance fall back to a sensible per-type colour.

Building surfaces are emitted as clean planar Breps (one editable trimmed-plane
surface per polygon, oriented outward), and every building's surfaces are put
in one Rhino group so a single click selects the whole building before you
drill into its faces. A holed building polygon (rare) falls back to a mesh.
Landcover and vegetation stay meshes: they are context you look at, not edit,
and keeping the ~250k tree/landcover polygons as meshes keeps the file small.

The reader streams with lxml, so the multi-hundred-MB city files parse in
bounded memory. Coordinates are RD New (EPSG:28992); they are translated to a
local origin (floored envelope lower corner) so Rhino stays numerically happy.
The offset is written to the model base point (``Settings.ModelBasePoint``) so
the RD New coordinates can be recovered exactly, and also noted in prose in the
model's application details.

Run:
    python tools/gml_to_rhino.py generated/annie-romeinsingel-72-152-leiden_400m.gml
    python tools/gml_to_rhino.py input.gml -o output.3dm

Requires the optional ``rhino`` extra (rhino3dm + shapely):
    uv pip install "rhino3dm>=8.0" "shapely>=2.0"
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import lxml.etree as ET  # noqa: N812

if TYPE_CHECKING:
    from collections.abc import Iterator

# ── CityGML 2.0 namespaces ──────────────────────────────────────────────
GML = "http://www.opengis.net/gml"
APP = "http://www.opengis.net/citygml/appearance/2.0"
CORE = "http://www.opengis.net/citygml/2.0"
NRG3 = "http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0"

# Colour is 0-255 RGB throughout.
RGB = tuple[int, int, int]

# ── Layer scheme (nested by feature + semantic surface type) ────────────
# Feature-class local element name -> child layer name. Only these carry
# geometry we want; anything else is ignored (e.g. nrg3 thermal-zone
# surfaces, which duplicate the building envelope, are skipped separately).
SEMANTIC: dict[str, str] = {
    "WallSurface": "WallSurface",
    "RoofSurface": "RoofSurface",
    "GroundSurface": "GroundSurface",
    "ClosureSurface": "ClosureSurface",
    "OuterCeilingSurface": "OuterCeilingSurface",
    "OuterFloorSurface": "OuterFloorSurface",
    "Window": "Window",
    "Door": "Door",
    "Building": "Building",  # geometry directly on the building (no boundedBy)
    "BuildingPart": "Building",
    "SolitaryVegetationObject": "Trees",
    "PlantCover": "PlantCover",
    "LandUse": "LandUse",
    "Road": "Road",
    "TransportationComplex": "Road",
    "Track": "Road",
    "Square": "Road",
    "Railway": "Road",
    "WaterBody": "WaterBody",
    "Bridge": "Bridge",
    "BridgePart": "Bridge",
    "GenericCityObject": "GenericCityObject",
}

# Child layer -> (parent layer, fallback colour used when a surface has no
# appearance material of its own).
CHILDREN: dict[str, tuple[str, RGB]] = {
    "WallSurface": ("Buildings", (230, 225, 215)),
    "RoofSurface": ("Buildings", (170, 90, 70)),
    "GroundSurface": ("Buildings", (90, 90, 90)),
    "ClosureSurface": ("Buildings", (200, 200, 200)),
    "OuterCeilingSurface": ("Buildings", (200, 200, 200)),
    "OuterFloorSurface": ("Buildings", (160, 160, 160)),
    "Window": ("Buildings", (150, 190, 220)),
    "Door": ("Buildings", (120, 80, 50)),
    "Building": ("Buildings", (200, 200, 200)),
    "Trees": ("Vegetation", (60, 140, 50)),
    "PlantCover": ("Vegetation", (120, 180, 80)),
    "LandUse": ("LandCover", (200, 190, 150)),
    "Road": ("LandCover", (110, 110, 110)),
    "WaterBody": ("LandCover", (70, 120, 180)),
    "Bridge": ("LandCover", (150, 140, 130)),
    "GenericCityObject": ("LandCover", (160, 160, 160)),
}
PARENT_ORDER = ("Buildings", "LandCover", "Vegetation")
PARENT_COLOUR: RGB = (80, 80, 80)
OTHER_COLOUR: RGB = (180, 180, 180)


def _r3d() -> Any:
    """Import rhino3dm lazily, typed as ``Any``.

    rhino3dm's shipped stubs mark every writable property (``Layer.Name``,
    ``ObjectAttributes.ObjectColor`` ...) as read-only and omit the enum
    modules, so a typed handle would reject the assignments this tool must
    make. Going through ``Any`` restores normal attribute access; the import
    is lazy so ``--help`` works without the optional ``rhino`` extra."""
    import rhino3dm

    return rhino3dm


def _localname(tag: str) -> str:
    """Strip the ``{namespace}`` prefix from a qualified lxml tag."""
    return tag.rsplit("}", 1)[-1]


def _to_byte(x: float) -> int:
    return max(0, min(255, round(x * 255)))


def _parse_colour(text: str) -> RGB:
    """``"0.98 0.78 0.42"`` (0-1 floats) -> ``(250, 199, 107)`` RGB."""
    parts = [float(v) for v in text.split()]
    r, g, b = (parts + [0.0, 0.0, 0.0])[:3]
    return (_to_byte(r), _to_byte(g), _to_byte(b))


def _parse_poslist(text: str) -> list[tuple[float, float, float]]:
    """Flat ``X Y Z X Y Z ...`` posList text -> list of 3D points, with the
    closing duplicate vertex dropped."""
    vals = text.split()
    pts = [
        (float(vals[i]), float(vals[i + 1]), float(vals[i + 2]))
        for i in range(0, len(vals) - len(vals) % 3, 3)
    ]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _newell_normal(pts: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """Area-weighted polygon normal (robust for any planar ring)."""
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0, z0 = pts[i]
        x1, y1, z1 = pts[(i + 1) % n]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    return nx, ny, nz


def _plane_basis(
    normal: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """Two orthonormal in-plane axes (u, v) for the given normal, or None if
    the normal is degenerate (zero-area ring)."""
    nx, ny, nz = normal
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-12:
        return None
    nx, ny, nz = nx / ln, ny / ln, nz / ln
    ax = (1.0, 0.0, 0.0) if abs(nx) < 0.9 else (0.0, 1.0, 0.0)
    ux = ax[1] * nz - ax[2] * ny
    uy = ax[2] * nx - ax[0] * nz
    uz = ax[0] * ny - ax[1] * nx
    lu = math.sqrt(ux * ux + uy * uy + uz * uz)
    if lu < 1e-12:
        return None
    ux, uy, uz = ux / lu, uy / lu, uz / lu
    vx = ny * uz - nz * uy
    vy = nz * ux - nx * uz
    vz = nx * uy - ny * ux
    return (ux, uy, uz), (vx, vy, vz)


def _triangulate(
    exterior: list[tuple[float, float, float]],
    holes: list[list[tuple[float, float, float]]],
) -> Iterator[tuple[tuple[float, float, float], ...]]:
    """Yield 3D triangles covering a planar polygon (holes respected).

    Triangles and quads fan directly; anything else (concave, many-vertex, or
    holed) is projected onto its plane, triangulated by Shapely's constrained
    Delaunay, and lifted back exactly (all points are coplanar, so the inverse
    projection is exact)."""
    if len(exterior) < 3:
        return
    if not holes and len(exterior) == 3:
        yield (exterior[0], exterior[1], exterior[2])
        return
    if not holes and len(exterior) == 4:
        yield (exterior[0], exterior[1], exterior[2])
        yield (exterior[0], exterior[2], exterior[3])
        return

    basis = _plane_basis(_newell_normal(exterior))
    if basis is None:
        return
    (ux, uy, uz), (vx, vy, vz) = basis
    ox, oy, oz = exterior[0]

    def to2d(p: tuple[float, float, float]) -> tuple[float, float]:
        dx, dy, dz = p[0] - ox, p[1] - oy, p[2] - oz
        return (dx * ux + dy * uy + dz * uz, dx * vx + dy * vy + dz * vz)

    def to3d(u: float, v: float) -> tuple[float, float, float]:
        return (ox + u * ux + v * vx, oy + u * uy + v * vy, oz + u * uz + v * vz)

    from shapely import Polygon, constrained_delaunay_triangles

    try:
        poly = Polygon([to2d(p) for p in exterior], [[to2d(p) for p in h] for h in holes])
        if not poly.is_valid:
            poly = poly.buffer(0)
        tris = constrained_delaunay_triangles(poly)
        geoms = list(getattr(tris, "geoms", []))
    except Exception:  # malformed polygon: fall back to a fan
        geoms = []

    if not geoms:  # fan the exterior (ignores holes, but never drops the face)
        for i in range(1, len(exterior) - 1):
            yield (exterior[0], exterior[i], exterior[i + 1])
        return

    for g in geoms:
        coords = list(g.exterior.coords)[:3]
        yield tuple(to3d(u, v) for u, v in coords)


def _prune(elem: ET._Element) -> None:
    """Free a finished element and its already-processed left siblings so the
    streamed tree stays small."""
    elem.clear()
    parent = elem.getparent()
    if parent is not None:
        while elem.getprevious() is not None:
            del parent[0]


def read_appearances(path: Path) -> tuple[dict[str, RGB], tuple[float, float, float] | None]:
    """Pass 1: map every appearance-target ``gml:id`` to its RGB colour, and
    read the model's envelope lower corner (the local-origin offset)."""
    colour_by_id: dict[str, RGB] = {}
    origin: tuple[float, float, float] | None = None
    material_tag = f"{{{APP}}}X3DMaterial"
    envelope_tag = f"{{{GML}}}Envelope"
    member_tag = f"{{{CORE}}}cityObjectMember"

    for _event, elem in ET.iterparse(str(path), events=("end",)):
        tag = elem.tag
        if tag == material_tag:
            diffuse = elem.find(f"{{{APP}}}diffuseColor")
            if diffuse is not None and diffuse.text:
                rgb = _parse_colour(diffuse.text)
                for target in elem.findall(f"{{{APP}}}target"):
                    if target.text:
                        colour_by_id[target.text.strip().lstrip("#")] = rgb
            elem.clear()
        elif origin is None and tag == envelope_tag:
            lower = elem.find(f"{{{GML}}}lowerCorner")
            if lower is not None and lower.text:
                vals = [float(v) for v in lower.text.split()]
                if len(vals) >= 3:
                    origin = (math.floor(vals[0]), math.floor(vals[1]), math.floor(vals[2]))
            elem.clear()
        elif tag == member_tag:
            _prune(elem)  # geometry we do not need this pass
    return colour_by_id, origin


def _build_layers(model) -> dict[str, int]:
    """Create the nested layer tree; return child-layer-name -> layer index."""
    rh = _r3d()
    index: dict[str, int] = {}
    parent_id: dict[str, object] = {}
    for name in PARENT_ORDER:
        layer = rh.Layer()
        layer.Name = name
        layer.Color = (*PARENT_COLOUR, 255)
        i = model.Layers.Add(layer)
        parent_id[name] = model.Layers[i].Id
    for child, (parent, fallback) in CHILDREN.items():
        layer = rh.Layer()
        layer.Name = child
        layer.Color = (*fallback, 255)
        layer.ParentLayerId = parent_id[parent]
        index[child] = model.Layers.Add(layer)
    other = rh.Layer()
    other.Name = "Other"
    other.Color = (*OTHER_COLOUR, 255)
    index["Other"] = model.Layers.Add(other)
    return index


def _mesh_from_triangles(triangles, origin):
    """Build a welded rhino3dm.Mesh from 3D triangles, offset to local origin."""
    ox, oy, oz = origin
    mesh = _r3d().Mesh()
    vertex_id: dict[tuple[float, float, float], int] = {}

    def vid(p: tuple[float, float, float]) -> int:
        key = (round(p[0] - ox, 4), round(p[1] - oy, 4), round(p[2] - oz, 4))
        i = vertex_id.get(key)
        if i is None:
            i = mesh.Vertices.Add(key[0], key[1], key[2])
            vertex_id[key] = i
        return i

    for a, b, c in triangles:
        ia, ib, ic = vid(a), vid(b), vid(c)
        if len({ia, ib, ic}) < 3:
            continue  # degenerate after welding
        mesh.Faces.AddFace(ia, ib, ic)
    return mesh


def _is_building(child: str) -> bool:
    """True for the surface types that live under the ``Buildings`` parent and
    are therefore emitted as editable Breps rather than context meshes."""
    return CHILDREN.get(child, ("", OTHER_COLOUR))[0] == "Buildings"


def _brep_from_polygon(exterior, holes, origin):
    """Build a trimmed planar Brep from one polygon's exterior ring, offset to
    the local origin. The trim plane is oriented by the ring's Newell normal so
    the resulting face normal points outward (the CityGML CCW-from-outside
    convention). Returns the Brep, or None when it has holes, is degenerate, or
    is too non-planar to trim (the caller then falls back to a mesh)."""
    if holes or len(exterior) < 3:
        return None
    nx, ny, nz = _newell_normal(exterior)
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln < 1e-9:
        return None
    rh = _r3d()
    ox, oy, oz = origin
    pts = [(x - ox, y - oy, z - oz) for (x, y, z) in exterior]
    poly = rh.Polyline()
    for x, y, z in pts:
        poly.Add(x, y, z)
    poly.Add(pts[0][0], pts[0][1], pts[0][2])  # close the ring
    plane = rh.Plane(rh.Point3d(*pts[0]), rh.Vector3d(nx / ln, ny / ln, nz / ln))
    try:
        brep = rh.Brep.CreateTrimmedPlane(plane, poly.ToPolylineCurve())
    except Exception:
        return None
    if brep is None or not brep.IsValid:
        return None
    return brep


def _obj_attrs(layer_index, child, colour):
    """Object attributes for one emitted object: its layer, and its per-object
    colour (the appearance colour, or the per-type fallback)."""
    rh = _r3d()
    attrs = rh.ObjectAttributes()
    attrs.LayerIndex = layer_index.get(child, layer_index["Other"])
    rgb = colour if colour is not None else CHILDREN.get(child, ("", OTHER_COLOUR))[1]
    attrs.ColorSource = rh.ObjectColorSource.ColorFromObject
    attrs.ObjectColor = (*rgb, 255)
    return attrs


def convert(
    gml_path: Path,
    out_path: Path,
    *,
    max_members: int | None = None,
    verbose: bool = True,
) -> dict[str, int]:
    """Convert one CityGML file to a Rhino ``.3dm``. Returns run statistics."""
    rh = _r3d()

    if verbose:
        print(f"[1/2] reading appearances + envelope from {gml_path.name} ...")
    colour_by_id, origin = read_appearances(gml_path)
    if origin is None:
        origin = (0.0, 0.0, 0.0)
    if verbose:
        print(f"      {len(colour_by_id)} coloured surfaces, local origin {origin}")

    model = rh.File3dm()
    model.Settings.ModelUnitSystem = rh.UnitSystem.Meters
    # Record the local-origin offset in Rhino's canonical georeference slot so
    # the RD New coordinates can be recovered exactly (Rhino origin = this point).
    model.Settings.ModelBasePoint = rh.Point3d(float(origin[0]), float(origin[1]), float(origin[2]))
    layer_index = _build_layers(model)

    gmlid_attr = f"{{{GML}}}id"
    poly_tag = f"{{{GML}}}Polygon"
    member_tag = f"{{{CORE}}}cityObjectMember"

    id_stack: list[str | None] = []
    sem_stack: list[str | None] = []
    nrg3_depth = 0
    building_id: str | None = None
    # accumulate one merged mesh per (child layer, colour) within a member
    accum: dict[tuple[str, RGB | None], list[tuple[tuple[float, float, float], ...]]] = {}
    # building surfaces emitted per-polygon as Breps: (child, colour, exterior, holes)
    building_polys: list[tuple[str, RGB | None, list, list]] = []
    stats = {
        "members": 0,
        "objects": 0,
        "polygons": 0,
        "breps": 0,
        "building_mesh_fallback": 0,
        "skipped_nrg3": 0,
        "skipped_geometry": 0,
    }

    if verbose:
        print("[2/2] streaming geometry ...")
    for event, elem in ET.iterparse(str(gml_path), events=("start", "end")):
        tag = elem.tag
        if event == "start":
            local = _localname(tag)
            id_stack.append(elem.get(gmlid_attr))
            sem_stack.append(SEMANTIC.get(local))
            if local == "Building" and building_id is None:
                building_id = elem.get(gmlid_attr)  # group name = the whole building
            if tag.startswith(f"{{{NRG3}}}"):
                nrg3_depth += 1
            continue

        # event == "end"
        if tag == poly_tag:
            if nrg3_depth == 0:
                _accumulate_polygon(
                    elem, id_stack, sem_stack, colour_by_id, accum, building_polys, stats
                )
                stats["polygons"] += 1
            else:
                stats["skipped_nrg3"] += 1
        elif tag == member_tag:
            _flush_member(model, layer_index, accum, building_polys, origin, stats, building_id)
            building_id = None
            _prune(elem)
            stats["members"] += 1
            if verbose and stats["members"] % 500 == 0:
                print(f"      {stats['members']} members, {stats['objects']} objects ...")
            if max_members is not None and stats["members"] >= max_members:
                break

        if tag.startswith(f"{{{NRG3}}}"):
            nrg3_depth -= 1
        id_stack.pop()
        sem_stack.pop()

    # trailing (if broken early)
    _flush_member(model, layer_index, accum, building_polys, origin, stats, building_id)

    offset = " ".join(str(v) for v in origin)
    note = (
        f"Converted from {gml_path.name}. CRS EPSG:28992 + EPSG:5109 (RD New / NAP). "
        f"Add local origin [{offset}] to every coordinate to recover RD New."
    )
    try:
        model.ApplicationName = "CityGML2.0-EnergyADE3.0 creator (gml_to_rhino)"
        model.ApplicationDetails = note
        model.StartSectionComments = note
    except Exception:  # metadata is a nicety, not essential
        pass

    if not model.Write(str(out_path), 8):
        raise RuntimeError(f"rhino3dm failed to write {out_path}")
    return stats


def _accumulate_polygon(
    elem, id_stack, sem_stack, colour_by_id, accum, building_polys, stats
) -> None:
    """Route one gml:Polygon: building surfaces are kept whole for per-polygon
    Brep emission; everything else is triangulated into the (layer, colour)
    mesh accumulator. A polygon with no parseable exterior posList is counted
    as skipped rather than silently dropped."""
    exterior: list[tuple[float, float, float]] | None = None
    holes: list[list[tuple[float, float, float]]] = []
    for ring_parent in elem:
        local = _localname(ring_parent.tag)
        if local not in ("exterior", "interior"):
            continue
        poslist = ring_parent.find(f".//{{{GML}}}posList")
        if poslist is None or not poslist.text:
            continue
        pts = _parse_poslist(poslist.text)
        if local == "exterior":
            exterior = pts
        elif len(pts) >= 3:
            holes.append(pts)
    if not exterior or len(exterior) < 3:
        stats["skipped_geometry"] += 1
        return

    colour: RGB | None = None
    for gid in reversed(id_stack):
        if gid is not None:
            hit = colour_by_id.get(gid)
            if hit is not None:
                colour = hit
                break

    child = "Other"
    for sem in reversed(sem_stack):
        if sem is not None:
            child = sem
            break

    if _is_building(child):
        building_polys.append((child, colour, exterior, holes))
    else:
        accum.setdefault((child, colour), []).extend(_triangulate(exterior, holes))


def _flush_member(model, layer_index, accum, building_polys, origin, stats, building_id) -> None:
    """Emit a finished member. Context (landcover / vegetation) becomes one
    merged mesh per (layer, colour); building surfaces become one editable Brep
    per polygon (mesh fallback when holed or non-planar), all placed in a single
    per-building group. Resets the accumulators."""
    rh = _r3d()
    for (child, colour), triangles in accum.items():
        if not triangles:
            continue
        mesh = _mesh_from_triangles(triangles, origin)
        if mesh.Faces.Count == 0:
            continue
        model.Objects.AddMesh(mesh, _obj_attrs(layer_index, child, colour))
        stats["objects"] += 1

    group_index: int | None = None
    for child, colour, exterior, holes in building_polys:
        attrs = _obj_attrs(layer_index, child, colour)
        brep = _brep_from_polygon(exterior, holes, origin)
        mesh = None
        if brep is None:
            mesh = _mesh_from_triangles(_triangulate(exterior, holes), origin)
            if mesh.Faces.Count == 0:
                continue  # nothing to emit; never happens for well-formed data
        # one group per building: created lazily on the first real face
        if group_index is None:
            grp = rh.Group()
            grp.Name = f"Building {building_id}" if building_id else "Building"
            model.Groups.Add(grp)
            group_index = len(model.Groups) - 1
        attrs.AddToGroup(group_index)
        if brep is not None:
            model.Objects.AddBrep(brep, attrs)
            stats["breps"] += 1
        else:
            model.Objects.AddMesh(mesh, attrs)
            stats["building_mesh_fallback"] += 1
        stats["objects"] += 1

    accum.clear()
    building_polys.clear()


def _default_output(gml_path: Path) -> Path:
    return gml_path.with_suffix(".3dm")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert creator CityGML (.gml) to a Rhino 8 .3dm with "
        "thematic layers and appearance colours."
    )
    parser.add_argument("gml", nargs="+", type=Path, help="input .gml file(s)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output .3dm (only valid with a single input; default: alongside input)",
    )
    parser.add_argument(
        "--max-members",
        type=int,
        default=None,
        help="stop after N cityObjectMembers (quick preview / testing)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="suppress progress output")
    args = parser.parse_args(argv)

    if args.output is not None and len(args.gml) > 1:
        parser.error("-o/--output cannot be used with multiple inputs")

    for gml_path in args.gml:
        if not gml_path.is_file():
            print(f"error: {gml_path} not found", file=sys.stderr)
            return 2
        out_path = args.output or _default_output(gml_path)
        stats = convert(gml_path, out_path, max_members=args.max_members, verbose=not args.quiet)
        fallback = (
            f" ({stats['building_mesh_fallback']} holed, kept as mesh)"
            if stats["building_mesh_fallback"]
            else ""
        )
        print(
            f"wrote {out_path}  "
            f"({stats['objects']} objects: {stats['breps']} building surfaces{fallback} "
            f"from {stats['polygons']} polygons, {stats['members']} members"
            + (f", {stats['skipped_nrg3']} nrg3 polygons skipped" if stats["skipped_nrg3"] else "")
            + (
                f", {stats['skipped_geometry']} unparseable polygons skipped"
                if stats["skipped_geometry"]
                else ""
            )
            + ")"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
