"""CityJSON 1.x parser: extract LoD 0/1/2 geometries per 3DBAG Pand.

The 3DBAG dataset publishes each tile as a CityJSON file where every
``BuildingPart`` carries (up to) three geometries tagged ``lod`` ``0``
``1.2`` and ``2.2``. We want:

* **LoD 0**: the 2D footprint, published as a ``MultiSurface`` (one
  polygon in practice). We map it onto ``bldg:lod0FootPrint``.
* **LoD 1.2**: the prismatic block, a ``Solid``. Maps to ``bldg:lod1Solid``.
* **LoD 2.2**: the roof-shape model, a ``Solid`` with semantic
  ``RoofSurface`` / ``WallSurface`` / ``GroundSurface`` surfaces. We
  parse the per-face semantics from ``geometry.semantics`` and preserve
  them in :class:`SemanticPolygon` so the builder can emit proper
  ``bldg:boundedBy`` thematic surfaces.

This module is **pure parser**: it never touches the xsdata bindings
and depends only on standard-library types, so it's trivial to unit-
test against fixtures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

_LOG = logging.getLogger(__name__)

from .._step import Coord3D, GeometryPolygon

_LOD_ALIAS: dict[str, str] = {
    "0": "0",
    "1.2": "1",
    "1": "1",
    "2.2": "2",
    "2": "2",
}


@dataclass(frozen=True, slots=True)
class SemanticPolygon:
    """A geometry polygon annotated with its CityGML thematic surface type.

    ``surface_type`` is one of ``"GroundSurface"``, ``"WallSurface"``,
    ``"RoofSurface"`` when the source CityJSON carries ``semantics``, or
    ``None`` when no semantic information was available.

    ``slots=True`` avoids the 48-byte instance ``__dict__``. With
    70 k+ instances per Delft-scale city build (2286 buildings × up to
    3 LoDs × ~10 polygons), the memory and allocation savings are
    directly visible in the parse path.
    """

    polygon: GeometryPolygon
    surface_type: str | None


@dataclass(frozen=True, slots=True)
class ParsedBuilding:
    """Per-Pand geometry extracted from a CityJSON tile.

    ``slots=True`` for the same reason as :class:`SemanticPolygon`: one
    instance per building makes the per-attribute dict nothing but
    overhead. Pickling remains well-supported on slotted frozen
    dataclasses, which matters for the on-disk 3DBAG parsed-tile cache.

    Attributes:
        pand_id: the BAG identificatie (``attributes.identificatie``).
        attributes: the raw CityObject attribute dict.
        geometries: ``{"0": [...], "1": [...], "2": [...]}``, where each
            value is a list of :class:`SemanticPolygon`. Missing LoDs
            simply don't appear.
    """

    pand_id: str
    attributes: dict[str, Any]
    geometries: dict[str, list[SemanticPolygon]]


@dataclass
class CityJSONTile:
    """Minimal view of a parsed CityJSON document."""

    metadata: dict[str, Any]
    city_objects: dict[str, dict[str, Any]]
    vertices: list[Coord3D]
    transform: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CityJSONTile:
        if not isinstance(data, dict):
            raise ValueError("CityJSON payload must be a dict")
        if data.get("type") not in {"CityJSON", "CityJSONFeature"}:
            raise ValueError(f"Expected CityJSON or CityJSONFeature, got {data.get('type')!r}")

        transform = data.get("transform") or {}
        scale = transform.get("scale", [1.0, 1.0, 1.0])
        translate = transform.get("translate", [0.0, 0.0, 0.0])
        raw_vertices = data.get("vertices") or []
        if scale == [1.0, 1.0, 1.0] and translate == [0.0, 0.0, 0.0]:
            vertices: list[Coord3D] = [
                (float(v[0]), float(v[1]), float(v[2])) for v in raw_vertices
            ]
        else:
            sx, sy, sz = (float(s) for s in scale)
            tx, ty, tz = (float(t) for t in translate)
            vertices = [
                (
                    round(float(v[0]) * sx + tx, 3),
                    round(float(v[1]) * sy + ty, 3),
                    round(float(v[2]) * sz + tz, 3),
                )
                for v in raw_vertices
            ]

        return cls(
            metadata=data.get("metadata") or {},
            city_objects=data.get("CityObjects") or {},
            vertices=vertices,
            transform=transform,
        )


def parse_buildings(tile_data: dict[str, Any]) -> list[ParsedBuilding]:
    """Return one :class:`ParsedBuilding` per top-level ``Building`` in *tile_data*.

    A 3DBAG CityJSON tile encodes each pand as a ``Building`` whose
    geometry lives on one or more child ``BuildingPart`` objects. We
    aggregate every part under the same pand: that gives the caller a
    single geometry set per BAG identificatie, which is what CityGML
    2.0 ``bldg:Building`` expects.
    """
    tile = CityJSONTile.from_dict(tile_data)

    children_of: dict[str, list[str]] = {}
    for obj_id, obj in tile.city_objects.items():
        for parent_id in obj.get("parents", []):
            children_of.setdefault(parent_id, []).append(obj_id)

    buildings: list[ParsedBuilding] = []
    for obj_id, obj in tile.city_objects.items():
        if obj.get("type") != "Building":
            continue

        attributes = dict(obj.get("attributes") or {})
        raw_id = str(attributes.get("identificatie") or obj_id)
        pand_id = raw_id.split(".")[-1] if "." in raw_id else raw_id

        geometries = _collect_building_geometries(
            tile=tile,
            building_obj=obj,
            part_ids=children_of.get(obj_id, []),
        )

        buildings.append(
            ParsedBuilding(pand_id=pand_id, attributes=attributes, geometries=geometries)
        )

    return buildings


def _collect_building_geometries(
    *,
    tile: CityJSONTile,
    building_obj: dict[str, Any],
    part_ids: list[str],
) -> dict[str, list[SemanticPolygon]]:
    accumulated: dict[str, list[SemanticPolygon]] = {}
    for geom in building_obj.get("geometry") or []:
        _extend_lod_map(accumulated, _parse_geometry(geom, tile.vertices))
    for part_id in part_ids:
        part = tile.city_objects.get(part_id)
        if part is None:
            continue
        for geom in part.get("geometry") or []:
            _extend_lod_map(accumulated, _parse_geometry(geom, tile.vertices))
    return accumulated


def _extend_lod_map(
    acc: dict[str, list[SemanticPolygon]],
    new_entries: dict[str, list[SemanticPolygon]],
) -> None:
    for lod, polygons in new_entries.items():
        if not polygons:
            continue
        acc.setdefault(lod, []).extend(polygons)


def _parse_geometry(
    geometry: dict[str, Any],
    vertices: list[Coord3D],
) -> dict[str, list[SemanticPolygon]]:
    """Return ``{lod: [SemanticPolygon]}`` for a single CityJSON geometry object."""
    lod_raw = str(geometry.get("lod", ""))
    lod = _LOD_ALIAS.get(lod_raw)
    if lod is None:
        return {}

    boundaries = geometry.get("boundaries") or []
    geom_type = geometry.get("type")

    sem_obj = geometry.get("semantics") or {}
    surfaces: list[dict[str, Any]] = sem_obj.get("surfaces") or []
    sem_values: list[Any] = sem_obj.get("values") or []

    # CityJSON boundary nesting:
    #   MultiSurface / CompositeSurface  → [ [ring, ...], ... ]          (faces)
    #   Solid                            → [ [face, ...], ... ]          (shells)
    #   MultiSolid / CompositeSolid      → [ [shell, ...], ... ]         (solids)
    #
    # semantics.values mirrors the same nesting but replaces each face with
    # an integer index into semantics.surfaces (or null when unclassified).
    polygons: list[SemanticPolygon] = []
    if geom_type in {"MultiSurface", "CompositeSurface"}:
        face_types = _resolve_face_types(sem_values, surfaces)
        polygons.extend(_parse_semantic_faces(boundaries, vertices, face_types))
    elif geom_type == "Solid":
        for shell_i, shell in enumerate(boundaries):
            shell_sem = sem_values[shell_i] if shell_i < len(sem_values) else []
            face_types = _resolve_face_types(shell_sem, surfaces)
            polygons.extend(_parse_semantic_faces(shell, vertices, face_types))
    elif geom_type in {"MultiSolid", "CompositeSolid"}:
        for solid_i, solid in enumerate(boundaries):
            solid_sem = sem_values[solid_i] if solid_i < len(sem_values) else []
            for shell_i, shell in enumerate(solid):
                shell_sem = (
                    solid_sem[shell_i]
                    if isinstance(solid_sem, list) and shell_i < len(solid_sem)
                    else []
                )
                face_types = _resolve_face_types(shell_sem, surfaces)
                polygons.extend(_parse_semantic_faces(shell, vertices, face_types))
    else:
        return {}

    return {lod: polygons}


def _resolve_face_types(
    sem_values: list[Any],
    surfaces: list[dict[str, Any]],
) -> list[str | None]:
    """Map a flat list of semantic indices to surface type strings.

    Each entry in *sem_values* is either an integer index into *surfaces*
    or ``None`` (no semantics for that face). Unknown indices also yield
    ``None``.
    """
    result: list[str | None] = []
    for v in sem_values:
        if v is None or not isinstance(v, int) or v >= len(surfaces):
            result.append(None)
        else:
            result.append(surfaces[v].get("type"))
    return result


def _parse_semantic_faces(
    faces: list[Any],
    vertices: list[Coord3D],
    face_types: list[str | None],
) -> list[SemanticPolygon]:
    out: list[SemanticPolygon] = []
    for i, face in enumerate(faces):
        if not face:
            continue
        exterior = _ring_from_indices(face[0], vertices)
        if exterior is None:
            continue
        if _polygon_3d_area(exterior) < MIN_FACE_AREA_M2:
            _LOG.debug(
                "Dropped sliver face: 3D area below %.0e m^2 threshold "
                "(3DBAG LoD 2.2 wall slivers between adjacent roof facets). "
                "See docs/threedbag_sliver_walls.md.",
                MIN_FACE_AREA_M2,
            )
            continue
        interiors_raw = face[1:]
        interiors: list[list[Coord3D]] = []
        for ring in interiors_raw:
            resolved = _ring_from_indices(ring, vertices)
            if resolved is not None:
                interiors.append(resolved)
        surface_type = face_types[i] if i < len(face_types) else None
        out.append(
            SemanticPolygon(
                polygon=GeometryPolygon(exterior=exterior, interiors=interiors),
                surface_type=surface_type,
            )
        )
    return out


# 10 cm^2 = 1000 mm^2. Sits inside the gap between documented 3DBAG
# LoD 2.2 wall slivers (largest observed 481 mm^2, see
# docs/threedbag_sliver_walls.md) and any plausible real LoD 2.2 wall
# facet (small dormer side walls start around 5 000 cm^2 = 500 000 mm^2;
# typical walls 5-20 m^2). The chosen value is ~2x above the largest
# measured sliver and ~500x below the smallest plausible real wall, so
# it tolerates a future sliver in the 500-1000 mm^2 range without
# touching the conservative-against-real-walls end of the gap. Shared
# with the build-time guard in
# citygml_energy.city_builder.builders.building so the two filters
# cannot drift apart silently. Bumping this constant invalidates
# parsed-tile pickles; the schema-version stamp in
# citygml_energy.city_builder.fetchers.threedbag must bump in lockstep
# (see _PARSED_TILE_SCHEMA_VERSION).
MIN_FACE_AREA_M2: float = 1e-3


def _polygon_3d_area(ring: list[Coord3D]) -> float:
    """Newell's-formula 3D polygon area for a (possibly non-closed) ring."""
    n = len(ring)
    if n < 3:
        return 0.0
    nx = ny = nz = 0.0
    for i in range(n):
        x1, y1, z1 = ring[i]
        x2, y2, z2 = ring[(i + 1) % n]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return 0.5 * (nx * nx + ny * ny + nz * nz) ** 0.5


def _ring_from_indices(
    indices: list[int],
    vertices: list[Coord3D],
) -> list[Coord3D] | None:
    """Resolve vertex indices to 3D coordinates, dropping degenerate rings.

    3DBAG LoD2 roof reconstruction occasionally emits degenerate wall
    triangles whose boundary index arrays reference duplicate vertex
    positions — i.e. different CityJSON vertex indices that map to the
    same (x, y, z) coordinate.  These arise as artefacts of the roof
    mesh triangulation and are already present in the raw tile data
    before any pipeline processing (verified by inspecting tile
    8/1008/920 at sub-millimetre precision).  A ring with fewer than
    three distinct points cannot form a valid polygon and would produce
    an invalid ``gml:LinearRing`` in the output GML, which causes strict
    viewers such as KITModelViewer to abort loading the entire file.

    Dedup precision is the output grid (``citygml_energy.gml_builders.
    _COORD_DECIMALS``, 1 µm). A coarser threshold (e.g. mm) lets vertices
    that differ at sub-mm survive the dedup and then collapse to
    identical strings once the µm quantiser rounds them at write time,
    producing a degenerate ring that XSD's ``gml:LinearRingType`` doesn't
    catch (the 4-point minimum is enforced only on ``gml:pos`` children,
    not on ``gml:posList`` content). Matching the output grid here closes
    that window.

    A DEBUG log entry is emitted for each dropped ring to aid diagnosis.
    """
    if not indices:
        return None
    try:
        ring = [vertices[i] for i in indices]
    except IndexError:
        return None

    from ..gml_builders import _COORD_DECIMALS

    distinct = {
        (round(pt[0], _COORD_DECIMALS), round(pt[1], _COORD_DECIMALS), round(pt[2], _COORD_DECIMALS))
        for pt in ring
    }
    if len(distinct) < 3:
        _LOG.debug(
            "Dropped degenerate ring: %d indices resolve to only %d distinct "
            "point(s) at output precision (10^-%d m) — 3DBAG source artefact "
            "(duplicate or near-duplicate vertex positions in boundary array).",
            len(indices),
            len(distinct),
            _COORD_DECIMALS,
        )
        return None

    return ring
