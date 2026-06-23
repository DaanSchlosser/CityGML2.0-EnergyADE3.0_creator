"""Clip a city scene to an axis-aligned bounding box, capping cut solids.

The address path centres a square fetch box on the matched buildings, but
the bulk fetches return whole objects that merely touch that box: a building
that straddles the edge, a road or terrain polygon that trails far past the
corner. For a visualisation extract the user wants a clean cut-out, so this
module clips the scene to the box and, for closed building solids, caps the
cut so the result still reads as a solid rather than an open shell.

Two clip primitives, both built on one Sutherland-Hodgman half-space clip of
a ring:

* :func:`clip_building_to_box` cuts a :class:`ParsedBuilding` to the box. A
  building wholly inside is returned untouched, one wholly outside is dropped
  (``None``), and a straddler has every LoD clipped. Footprints (LoD 0) are
  open surfaces and are clipped without a cap; the LoD 1 / LoD 2 solids are
  clipped plane by plane and the newly exposed cross-section is rebuilt as a
  cap face per plane, so the shell stays closed. The cap of one plane is fed
  into the next, so a corner building cut by two planes is capped on both.
  Attributes are left untouched: a cut building's 3DBAG volume / area / height
  no longer describe its clipped geometry, which is acceptable for a
  visualisation product (the user accepted this trade explicitly).

* :func:`clip_landcover_polygons` cuts the draped 3D Basisvoorziening surfaces
  to the box. These are open surfaces (a TIN of small planar facets, some near
  vertical), so there is no cap and the clip runs in 3D through the same
  half-space primitive: z is kept exact on every vertex (an original vertex
  keeps its z, a new box-edge vertex interpolates along the original edge),
  which a 2D-projected plane fit cannot do without flattening a vertical facet
  or extrapolating a spike.

The whole module is pure standard library (no shapely), so it stays trivial to
unit-test against synthetic prisms and facets.
"""

from __future__ import annotations

from .._step import Coord3D, GeometryPolygon
from .cityjson_parse import ParsedBuilding, SemanticPolygon

__all__ = [
    "clip_building_to_box",
    "clip_landcover_polygons",
]

Box = tuple[float, float, float, float]

# On-plane endpoint matching tolerance, in metres. Intersection points set the
# clipped axis exactly to the plane value and interpolate the rest, so 1 um is
# ample to chain cut edges into cap loops while never merging distinct corners.
_SNAP_DECIMALS = 6

# Inside-test slack so a vertex sitting exactly on a plane counts as kept on
# both sides of that plane rather than being clipped away by float wobble.
_EPS = 1e-6

# Cap faces created by the cut are vertical, so they read as walls; LoD 2
# classification defaults unknown faces to WallSurface anyway, so this keeps a
# capped LoD 2 building thematically consistent.
_CAP_SURFACE_TYPE = "WallSurface"


# ---------------------------------------------------------------------------
# Half-space clip of one ring (the shared primitive)
# ---------------------------------------------------------------------------


def _intersect(a: Coord3D, b: Coord3D, axis: int, value: float) -> Coord3D:
    """Point where segment *a*->*b* crosses the plane ``coord[axis] == value``.

    The clipped axis is set to *value* exactly (not interpolated) so the new
    vertex lands on the plane to the bit, which keeps cap-edge endpoints from
    neighbouring faces identical after snapping.
    """
    ca, cb = a[axis], b[axis]
    denom = cb - ca
    t = 0.0 if denom == 0.0 else (value - ca) / denom
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    out = [a[k] + t * (b[k] - a[k]) for k in range(3)]
    out[axis] = value
    return (out[0], out[1], out[2])


def _clip_ring_halfspace(
    ring: list[Coord3D],
    axis: int,
    value: float,
    keep_low: bool,
) -> tuple[list[Coord3D], list[tuple[Coord3D, Coord3D]]]:
    """Sutherland-Hodgman clip of one ring against a half-space.

    Keeps the part of *ring* on the inside of the plane ``coord[axis] ==
    value`` (``coord[axis] <= value`` when *keep_low*, else ``>=``) and returns
    ``(kept_ring, cut_edges)``. Each cut edge is the directed segment, in the
    ring's own winding, that the cut newly exposed on the plane: an
    ``exit -> re-entry`` pair. On a closed solid the cut edges of all faces
    chain into the cap loop(s); an open surface simply discards them.
    """
    n = len(ring)
    if n < 3:
        return [], []

    def inside(pt: Coord3D) -> bool:
        c = pt[axis]
        return c <= value + _EPS if keep_low else c >= value - _EPS

    kept: list[Coord3D] = []
    # Per kept vertex: 0 original, +1 an exit cut point, -1 an entry cut point.
    kind: list[int] = []
    for i in range(n):
        cur = ring[i]
        nxt = ring[(i + 1) % n]
        cur_in = inside(cur)
        nxt_in = inside(nxt)
        if cur_in:
            kept.append(cur)
            kind.append(0)
            if not nxt_in:
                kept.append(_intersect(cur, nxt, axis, value))
                kind.append(+1)
        elif nxt_in:
            kept.append(_intersect(cur, nxt, axis, value))
            kind.append(-1)

    if len(kept) < 3:
        # The clipped face collapsed to a sliver or vanished entirely.
        return [], []

    cut_edges: list[tuple[Coord3D, Coord3D]] = []
    m = len(kept)
    for i in range(m):
        # An exit immediately followed by a re-entry spans the removed part of
        # the boundary: that connecting segment lies on the plane and is one
        # edge of the cap. Tracking exit/entry kinds (not just "both on plane")
        # avoids mistaking a grazing entry-then-exit touch for a cap edge.
        if kind[i] == +1 and kind[(i + 1) % m] == -1:
            a = kept[i]
            b = kept[(i + 1) % m]
            if _key(a) != _key(b):
                cut_edges.append((a, b))
    return kept, cut_edges


def _key(pt: Coord3D) -> tuple[float, float, float]:
    """Snap a point to the matching grid so shared cut points compare equal."""
    return (
        round(pt[0], _SNAP_DECIMALS),
        round(pt[1], _SNAP_DECIMALS),
        round(pt[2], _SNAP_DECIMALS),
    )


def _dedup_consecutive(ring: list[Coord3D]) -> list[Coord3D]:
    """Drop consecutive duplicate vertices (cyclically) by snapped identity.

    A vertex sitting exactly on a clip plane makes the intersection point equal
    that vertex, leaving a zero-length edge; collapsing such repeats keeps the
    emitted ring clean without affecting its shape.
    """
    out: list[Coord3D] = []
    for pt in ring:
        if not out or _key(out[-1]) != _key(pt):
            out.append(pt)
    if len(out) > 1 and _key(out[0]) == _key(out[-1]):
        out.pop()
    return out


# ---------------------------------------------------------------------------
# Cap assembly
# ---------------------------------------------------------------------------


def _assemble_loops(edges: list[tuple[Coord3D, Coord3D]]) -> list[list[Coord3D]]:
    """Chain directed cut edges head-to-tail into closed loops.

    Adjacent faces of a closed solid traverse their shared edge in opposite
    directions, so where the plane cuts that edge one face's cut edge ends
    exactly where the next one begins. Following ``end -> next.start`` by
    snapped point identity walks each cross-section boundary back to its start.
    A loop that fails to close (a non-manifold patch in the source solid) is
    dropped rather than emitted half-open.
    """
    if not edges:
        return []
    starts: dict[tuple[float, float, float], list[Coord3D]] = {}
    for a, b in edges:
        starts.setdefault(_key(a), []).append(b)

    loops: list[list[Coord3D]] = []
    remaining = len(edges)
    used_from: dict[tuple[float, float, float], int] = {}
    for a, _b in edges:
        ka = _key(a)
        if used_from.get(ka, 0) >= len(starts.get(ka, [])):
            continue
        loop = [a]
        cur = a
        guard = 0
        while guard <= remaining:
            guard += 1
            kc = _key(cur)
            successors = starts.get(kc)
            idx = used_from.get(kc, 0)
            if not successors or idx >= len(successors):
                loop = []
                break
            used_from[kc] = idx + 1
            nxt = successors[idx]
            if _key(nxt) == _key(a):
                break
            loop.append(nxt)
            cur = nxt
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def _newell_axis_component(ring: list[Coord3D], axis: int) -> float:
    """Return the *axis* component of the ring's Newell normal.

    A cap loop is planar on the clip plane, so only the component along that
    plane's axis is non-zero; its sign tells us which way the loop winds.
    """
    n = len(ring)
    comp = 0.0
    for i in range(n):
        x1, y1, z1 = ring[i]
        x2, y2, z2 = ring[(i + 1) % n]
        if axis == 0:
            comp += (y1 - y2) * (z1 + z2)
        elif axis == 1:
            comp += (z1 - z2) * (x1 + x2)
        else:
            comp += (x1 - x2) * (y1 + y2)
    return comp


def _orient_cap(loop: list[Coord3D], axis: int, keep_low: bool) -> list[Coord3D]:
    """Wind *loop* so its outward normal points away from the kept side.

    The kept side is ``coord[axis] <= value`` when *keep_low*, so the cap's
    outward normal must point toward ``+axis`` (the removed side); reverse the
    loop when Newell says it points the other way.
    """
    comp = _newell_axis_component(loop, axis)
    want_positive = keep_low
    if (comp > 0.0) != want_positive:
        return list(reversed(loop))
    return loop


# ---------------------------------------------------------------------------
# Building clip
# ---------------------------------------------------------------------------


def _planes(box: Box) -> list[tuple[int, float, bool]]:
    """The four vertical box edges as ``(axis, value, keep_low)`` half-spaces."""
    xmin, ymin, xmax, ymax = box
    return [
        (0, xmin, False),
        (0, xmax, True),
        (1, ymin, False),
        (1, ymax, True),
    ]


def _clip_solid_faces(faces: list[SemanticPolygon], box: Box) -> list[SemanticPolygon]:
    """Clip a closed solid's faces to *box*, capping the cut on every plane.

    Interior rings on solid faces are not expected (3DBAG wall / roof / ground
    faces are simple) and are dropped if present, so a hole that straddles the
    edge is filled rather than carried, a negligible artefact on the few cut
    buildings.
    """
    # Carry (ring, surface_type) through each plane; caps are appended as they
    # are created so the next plane clips them too (corner buildings).
    current: list[tuple[list[Coord3D], str | None]] = [
        (face.polygon.exterior, face.surface_type)
        for face in faces
        if len(face.polygon.exterior) >= 3
    ]
    for axis, value, keep_low in _planes(box):
        survivors: list[tuple[list[Coord3D], str | None]] = []
        cut_edges: list[tuple[Coord3D, Coord3D]] = []
        for ring, surface_type in current:
            kept, edges = _clip_ring_halfspace(ring, axis, value, keep_low)
            if len(kept) >= 3:
                survivors.append((kept, surface_type))
            cut_edges.extend(edges)
        survivors.extend(
            (_orient_cap(loop, axis, keep_low), _CAP_SURFACE_TYPE)
            for loop in _assemble_loops(cut_edges)
        )
        current = survivors
        if not current:
            break
    out: list[SemanticPolygon] = []
    for ring, surface_type in current:
        clean = _dedup_consecutive(ring)
        if len(clean) >= 3:
            out.append(
                SemanticPolygon(polygon=GeometryPolygon(exterior=clean), surface_type=surface_type)
            )
    return out


def _clip_surface_faces(faces: list[SemanticPolygon], box: Box) -> list[SemanticPolygon]:
    """Clip open-surface faces (an LoD 0 footprint) to *box* without capping."""
    out: list[SemanticPolygon] = []
    for face in faces:
        clean = _clip_ring_to_box(face.polygon.exterior, box)
        if len(clean) >= 3:
            out.append(
                SemanticPolygon(
                    polygon=GeometryPolygon(exterior=clean),
                    surface_type=face.surface_type,
                )
            )
    return out


def _geometry_xy_bounds(geometries: dict[str, list[SemanticPolygon]]) -> Box | None:
    """Return the xy bounding box over every face of every LoD, or ``None``."""
    xs: list[float] = []
    ys: list[float] = []
    for faces in geometries.values():
        for face in faces:
            for x, y, _z in face.polygon.exterior:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def clip_building_to_box(parsed: ParsedBuilding, box: Box) -> ParsedBuilding | None:
    """Clip *parsed* to *box*: untouched if inside, dropped if outside, else cut.

    A building whose footprint lies wholly inside *box* is returned unchanged
    (the common case, no geometry work). One wholly outside *box* returns
    ``None`` so the caller drops it. A straddler has its LoD 0 footprint clipped
    as an open surface and its LoD 1 / LoD 2 solids clipped and capped, so the
    cut faces close back into a solid. ``None`` is returned when nothing
    survives the clip.
    """
    bounds = _geometry_xy_bounds(parsed.geometries)
    if bounds is None:
        return parsed
    bxmin, bymin, bxmax, bymax = bounds
    xmin, ymin, xmax, ymax = box
    if bxmax < xmin - _EPS or bxmin > xmax + _EPS or bymax < ymin - _EPS or bymin > ymax + _EPS:
        return None
    if (
        bxmin >= xmin - _EPS
        and bxmax <= xmax + _EPS
        and bymin >= ymin - _EPS
        and bymax <= ymax + _EPS
    ):
        return parsed

    clipped: dict[str, list[SemanticPolygon]] = {}
    for lod, faces in parsed.geometries.items():
        cut = _clip_surface_faces(faces, box) if lod == "0" else _clip_solid_faces(faces, box)
        if cut:
            clipped[lod] = cut
    if not clipped:
        return None
    return ParsedBuilding(
        pand_id=parsed.pand_id,
        attributes=parsed.attributes,
        geometries=clipped,
    )


# ---------------------------------------------------------------------------
# Landcover clip (open surfaces, exact z along edges)
# ---------------------------------------------------------------------------


def clip_landcover_polygons(polygons: list[GeometryPolygon], box: Box) -> list[GeometryPolygon]:
    """Clip draped landcover surfaces to *box*, keeping z exact on every vertex.

    The 3D Basisvoorziening ground is a TIN of small planar facets, some of
    them near vertical (a quay wall, the side of a vegetation block). Each
    facet is clipped in 3D against the four box planes with the same half-space
    clip the buildings use: an original vertex keeps its own z, and a vertex
    the cut introduces on the box edge takes its z by linear interpolation
    along the original edge it lies on. That is exact for a planar facet at any
    tilt, so unlike a 2D-projected plane fit it never flattens a vertical facet
    nor extrapolates a spike where the box edge runs far from the facet. Each
    facet is an open surface, so there is no cap; a facet that clips away to
    fewer than three points is dropped.
    """
    out: list[GeometryPolygon] = []
    for gp in polygons:
        exterior = _clip_ring_to_box(gp.exterior, box)
        if len(exterior) < 3:
            continue
        interiors: list[list[Coord3D]] = []
        for ring in gp.interiors:
            clipped = _clip_ring_to_box(ring, box)
            if len(clipped) >= 3:
                interiors.append(clipped)
        out.append(GeometryPolygon(exterior=exterior, interiors=interiors))
    return out


def _clip_ring_to_box(ring: list[Coord3D], box: Box) -> list[Coord3D]:
    """Clip one ring against the four box planes in 3D; return the kept ring.

    Empty (fewer than three points) when the ring falls wholly outside *box*.
    """
    if len(ring) < 3:
        return []
    for axis, value, keep_low in _planes(box):
        ring, _edges = _clip_ring_halfspace(ring, axis, value, keep_low)
        if len(ring) < 3:
            return []
    return _dedup_consecutive(ring)
