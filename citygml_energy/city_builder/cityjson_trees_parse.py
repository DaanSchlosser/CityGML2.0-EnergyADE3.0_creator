"""CityJSON tile parser for CFTree tree-reconstruction output.

CFTree (https://github.com/NoahAlting/CFTree) reconstructs LoD3 watertight
tree meshes from AHN LiDAR and writes one CityJSON 2.0 tile per AHN sub-tile
under ``data/<case>/tiles/<tile_id>/trees_lod3.city.json``. Each tree is a
``SolitaryVegetationObject`` with one or more ``Solid`` geometries (one per
component: crown, trunk) and morphometric attributes.

This module is a pure parser. Given the bytes of a CityJSON tile it
returns flat :class:`ParsedTree` records; it does not touch the xsdata
bindings and depends only on the standard library + :mod:`citygml_energy._step`.

CFTree output shape (as produced by
``src/reconstruction/write_cityjson.py``):

.. code-block:: json

    {
      "type": "CityJSON",
      "version": "2.0",
      "transform": {"scale": [0.001, 0.001, 0.001], "translate": [x0, y0, z0]},
      "metadata": {
        "referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/28992",
        "geographicalExtent": [xmin, ymin, zmin, xmax, ymax, zmax],
        "presentLoDs": [3.0]
      },
      "CityObjects": {
        "T_<gtid>": {
          "type": "SolitaryVegetationObject",
          "geometry": [
            {"type": "Solid", "lod": 3.0, "boundaries": [[[[v1,v2,v3]], ...]]},
            ...
          ],
          "attributes": {... crown_width, height, trunk_* ...}
        }
      },
      "vertices": [[x_int, y_int, z_int], ...]
    }
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .._step import Coord3D, GeometryPolygon

__all__ = [
    "ParsedTree",
    "parse_cftree_tile",
    "parse_cftree_tile_file",
]


@dataclass(frozen=True, slots=True)
class ParsedTree:
    """A single tree extracted from a CFTree CityJSON tile.

    ``slots=True`` because a municipality scan can easily produce tens of
    thousands of these records. Field choices:

    Attributes:
        gtid: global tree id, the integer suffix of CFTree's
            ``T_<gtid>`` object id. Stable across CFTree re-runs of the
            same AOI, so it is a reasonable primary key for any
            downstream join.
        centroid: XYZ centroid of the tree triangles in EPSG:28992,
            metres (crown + trunk vertices averaged). Used for the
            bbox / boundary clip and as a stable anchor for any future
            spatial join.
        polygons: flat list of triangular faces (crown + trunk merged
            into one list) suitable for feeding to
            :func:`citygml_energy.gml_builders.build_multi_surface`.
            CityGML 2.0 ``veg:SolitaryVegetationObject`` has no
            per-component slot for a tree, so the merged list is the
            correct lossless encoding.
        attributes: the raw CityJSON ``attributes`` dict. Keys observed
            in CFTree (verified against a real generated tile):
            ``gtid``, ``tile_id``, ``crown_width_m``, ``crown_median_z``,
            ``crown_r50_m``, ``crown_porosity``, ``trunk_H_m``,
            ``trunk_DBH_m``, ``trunk_radius_m``, ``trunk_base_height_m``.
            Any future CFTree attribute flows through untouched; the
            builder in :mod:`citygml_energy.city_builder.builders`
            decides which keys become native CityGML fields vs.
            ``gen:doubleAttribute`` generics.
        lod: the LoD value written on the source geometry (``3.0`` for
            CFTree). Kept as a string for downstream consistency with
            :mod:`citygml_energy.city_builder.cityjson_parse`.
    """

    gtid: str
    centroid: Coord3D
    polygons: list[GeometryPolygon]
    attributes: dict[str, Any]
    lod: str = "3"


def parse_cftree_tile_file(path: Path) -> list[ParsedTree]:
    """Read a CFTree CityJSON tile from disk and return parsed trees.

    Empty file or no ``SolitaryVegetationObject`` → empty list. The
    caller is expected to fan this out across every
    ``tiles/*/trees_lod3.city.json`` found in the CFTree output.
    """
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return []
    data = json.loads(raw)
    return parse_cftree_tile(data)


def parse_cftree_tile(data: dict[str, Any]) -> list[ParsedTree]:
    """Parse an in-memory CityJSON dict produced by CFTree.

    Accepts both dequantized (identity ``transform``) and quantized
    (CFTree's default millimetre quantization) layouts. Quantized
    vertices are expanded to absolute coordinates up-front so that
    downstream code sees plain RD New metres.

    Non-``SolitaryVegetationObject`` CityObjects are skipped with no
    error: CFTree writes only vegetation objects today, but if future
    versions add auxiliary features (terrain tiles, test markers, ...)
    this parser must not silently ingest them as trees.
    """
    if not isinstance(data, dict):
        raise ValueError("CFTree CityJSON payload must be a dict")
    if data.get("type") not in {"CityJSON", "CityJSONFeature"}:
        raise ValueError(
            f"Expected CityJSON/CityJSONFeature, got {data.get('type')!r}"
        )

    vertices = _dequantize_vertices(
        data.get("vertices") or [],
        data.get("transform") or {},
    )
    city_objects = data.get("CityObjects") or {}

    parsed: list[ParsedTree] = []
    for obj_id, obj in city_objects.items():
        if not isinstance(obj, dict):
            continue
        if obj.get("type") != "SolitaryVegetationObject":
            continue
        parsed.append(_parse_tree_object(obj_id, obj, vertices))
    return parsed


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _dequantize_vertices(
    raw_vertices: list[list[float]], transform: dict[str, Any],
) -> list[Coord3D]:
    scale = transform.get("scale") or [1.0, 1.0, 1.0]
    translate = transform.get("translate") or [0.0, 0.0, 0.0]
    if scale == [1.0, 1.0, 1.0] and translate == [0.0, 0.0, 0.0]:
        return [
            (float(v[0]), float(v[1]), float(v[2])) for v in raw_vertices
        ]
    sx, sy, sz = (float(s) for s in scale)
    tx, ty, tz = (float(t) for t in translate)
    # CFTree quantizes to millimetre precision; rounding here mirrors the
    # rounding in :class:`CityJSONTile.from_dict` so coordinates compare
    # equal across the two parsers.
    return [
        (
            round(float(v[0]) * sx + tx, 3),
            round(float(v[1]) * sy + ty, 3),
            round(float(v[2]) * sz + tz, 3),
        )
        for v in raw_vertices
    ]


def _parse_tree_object(
    obj_id: str, obj: dict[str, Any], vertices: list[Coord3D],
) -> ParsedTree:
    merged: list[GeometryPolygon] = []
    lod_observed: str | None = None

    for geom in obj.get("geometry") or []:
        if not isinstance(geom, dict):
            continue
        if geom.get("type") != "Solid":
            # CFTree only emits Solids today. Defensive: skip any other
            # geometry type so the parser is forward-compatible.
            continue
        merged.extend(_solid_to_polygons(geom.get("boundaries") or [], vertices))
        if lod_observed is None:
            lod_raw = geom.get("lod")
            if lod_raw is not None:
                lod_observed = _normalize_lod(lod_raw)

    centroid = _centroid_xyz(merged)

    # CFTree writes ``"T_<gtid>"`` as the CityObject id. Strip the prefix
    # for the ``gtid`` field but keep the full id available via
    # ``attributes['gtid']`` for downstream diagnostics.
    gtid = obj_id[2:] if obj_id.startswith("T_") else obj_id

    return ParsedTree(
        gtid=gtid,
        centroid=centroid,
        polygons=merged,
        attributes=dict(obj.get("attributes") or {}),
        lod=lod_observed or "3",
    )


def _solid_to_polygons(
    boundaries: list[Any], vertices: list[Coord3D],
) -> list[GeometryPolygon]:
    """Flatten a CityJSON Solid ``boundaries`` tree into polygons.

    CityJSON 2.0 Solid encoding: ``Solid → [shell]``,
    ``shell → [surface]``, ``surface → [ring]``, ``ring → [vertex_idx]``.
    CFTree emits triangular surfaces with one exterior ring and no
    interior rings (it is a watertight triangle soup), so this parser
    treats every ring as the exterior ring of its own polygon and does
    not recover interior holes. For a future CFTree that emits
    non-triangular faces or holes, extend :func:`_ring_to_coords`
    accordingly.
    """
    polys: list[GeometryPolygon] = []
    for shell in boundaries:
        if not isinstance(shell, list):
            continue
        for surface in shell:
            if not isinstance(surface, list) or not surface:
                continue
            # First ring is the exterior; remaining rings would be holes.
            exterior = _ring_to_coords(surface[0], vertices)
            if not exterior:
                continue
            interiors = [
                ring_coords
                for ring in surface[1:]
                if (ring_coords := _ring_to_coords(ring, vertices))
            ]
            polys.append(GeometryPolygon(exterior=exterior, interiors=interiors))
    return polys


def _ring_to_coords(
    ring: Any, vertices: list[Coord3D],
) -> list[Coord3D]:
    if not isinstance(ring, list):
        return []
    pts: list[Coord3D] = []
    for vi in ring:
        if not isinstance(vi, int):
            return []
        if vi < 0 or vi >= len(vertices):
            return []
        pts.append(vertices[vi])
    # Close the ring if the source omits the closing vertex. GML 3.1.1
    # LinearRings require the first and last point to be identical.
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _centroid_xyz(polygons: Iterable[GeometryPolygon]) -> Coord3D:
    total = 0
    sx = sy = sz = 0.0
    for poly in polygons:
        # Skip the duplicated closing vertex so the centroid is not
        # pulled toward the first point.
        pts = poly.exterior[:-1] if len(poly.exterior) >= 2 else poly.exterior
        for x, y, z in pts:
            sx += x
            sy += y
            sz += z
            total += 1
    if total == 0:
        return (0.0, 0.0, 0.0)
    return (sx / total, sy / total, sz / total)


def _normalize_lod(raw: Any) -> str:
    """Reduce CityJSON's ``lod`` field to the ``"0"/"1"/"2"/"3"`` keys.

    CFTree writes ``3.0`` (float). The rest of this codebase keys per-LoD
    dicts on ``"0"``/``"1"``/``"2"`` strings, so normalise accordingly.
    """
    try:
        return str(int(float(raw)))
    except (TypeError, ValueError):
        return str(raw)
